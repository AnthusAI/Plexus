"use client"
import React, { useState, useEffect, useCallback, useRef } from "react"
import { useRouter, usePathname, useParams } from "next/navigation"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Button } from "@/components/ui/button"
import { Plus, Waypoints, FileText, Shrink, BookOpenCheck } from "lucide-react"
import { toast } from "sonner"
import ProcedureTask, { ProcedureTaskData } from "@/components/ProcedureTask"
import ProcedureTaskEdit from "@/components/ProcedureTaskEdit"
import ProcedureConversationViewer from "@/components/procedure-conversation-viewer"
import ScorecardContext from "@/components/ScorecardContext"
import TemplateSelector from "@/components/template-selector"
import { motion, AnimatePresence } from "framer-motion"
import { useMediaQuery } from "@/hooks/use-media-query"
import { useAccount } from '@/app/contexts/AccountContext'
import { observeTaskUpdates, observeTaskStageUpdates } from "@/utils/subscriptions"
import { ProceduresGauges } from "@/components/ProceduresGauges"
import { ProceduresDashboardSkeleton } from "@/components/loading-skeleton"
import { load as parseYaml, dump as stringifyYaml } from "js-yaml"
import { useInView } from "react-intersection-observer"
import {
  EVALUATION_CREATE_SUBSCRIPTION_FOR_CARDS,
  EVALUATION_DELETE_SUBSCRIPTION_FOR_CARDS,
  EVALUATION_UPDATE_SUBSCRIPTION_FOR_CARDS,
  evaluationToScoreEvaluationView,
  feedbackEvaluationSummaryFromView,
  hydrateProcedureRunsFeedbackEvaluations,
  PROCEDURE_CARD_FIELDS,
  PROCEDURE_CREATE_SUBSCRIPTION_FOR_CARDS,
  PROCEDURE_UPDATE_SUBSCRIPTION_FOR_CARDS,
  procedureIdFromTaskTarget,
  procedureToOptimizerRunView,
  TASK_CARD_FIELDS,
  type ProcedureFeedbackEvaluationSummary,
} from "@/components/ui/optimizer-results-utils"

type Procedure = Schema['Procedure']['type']
type Task = Schema['Task']['type']
type ProcedureWithTask = Procedure & {
  task?: Task | null
  feedbackEvaluationSummary?: ProcedureFeedbackEvaluationSummary | null
}

const PROCEDURE_PAGE_SIZE = 25

const getProcedureStartTimeMs = (procedure: ProcedureWithTask): number => {
  const startCandidate =
    procedure.task?.startedAt ||
    procedure.task?.createdAt ||
    procedure.createdAt ||
    procedure.updatedAt
  const timestamp = startCandidate ? new Date(startCandidate).getTime() : 0
  return Number.isFinite(timestamp) ? timestamp : 0
}

const sortProceduresByStartTime = (procedures: ProcedureWithTask[]): ProcedureWithTask[] =>
  [...procedures].sort((a, b) => getProcedureStartTimeMs(b) - getProcedureStartTimeMs(a))

let amplifyClient: ReturnType<typeof generateClient<Schema>> | null = null
const getAmplifyClient = () => (amplifyClient ??= generateClient<Schema>())

interface ProceduresDashboardProps {
  initialSelectedProcedureId?: string | null
}

function ProceduresDashboard({ initialSelectedProcedureId }: ProceduresDashboardProps = {}) {
  const router = useRouter()
  const pathname = usePathname()
  const params = useParams()
  const { selectedAccount, isLoadingAccounts } = useAccount()
  
  // Extract procedure ID from URL params if present, or use the prop
  const procedureIdFromParams = (params && 'id' in params) ? params.id as string : null
  const finalInitialProcedureId = initialSelectedProcedureId || procedureIdFromParams
  
  const [procedures, setProcedures] = useState<ProcedureWithTask[]>([])
  const [isInitialLoading, setIsInitialLoading] = useState(true)
  const [isFetchingProcedures, setIsFetchingProcedures] = useState(false)
  const [isHydratingTasks, setIsHydratingTasks] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [nextToken, setNextToken] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedProcedureId, setSelectedProcedureId] = useState<string | null>(finalInitialProcedureId)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [isEditMode, setIsEditMode] = useState(false)
  const [showTemplateSelector, setShowTemplateSelector] = useState(false)
  const [isConversationFullscreen, setIsConversationFullscreen] = useState(false)
  const isNarrowViewport = useMediaQuery("(max-width: 768px)")
  const lastLoadTimeRef = useRef(0)
  const loadRequestIdRef = useRef(0)
  const hasLoadedProceduresOnceRef = useRef(false)
  const procedureTaskMapRef = useRef<Map<string, Task>>(new Map())
  const { ref: sentinelRef, inView } = useInView({ threshold: 0 })

  const hydrateProcedurePerformanceSummaries = useCallback(async (
    procedureItems: ProcedureWithTask[]
  ): Promise<ProcedureWithTask[]> => {
    const runs = await Promise.all(
      procedureItems.map((procedure) => procedureToOptimizerRunView(procedure, procedure.task ?? null))
    )
    const hydratedRuns = await hydrateProcedureRunsFeedbackEvaluations(runs)
    const summariesByProcedureId = new Map(
      hydratedRuns.map((run) => [run.procedureId, run.feedbackEvaluationSummary ?? null])
    )
    return procedureItems.map((procedure) => ({
      ...procedure,
      feedbackEvaluationSummary: summariesByProcedureId.get(procedure.id) ?? null,
    }))
  }, [])

  // All hooks must be at the top before any conditional returns
  const handleSelectProcedure = useCallback((id: string | null) => {
    setSelectedProcedureId(id)
    // Update URL without causing full rerender
    const newPathname = id ? `/lab/procedures/${id}` : '/lab/procedures'
    window.history.pushState(null, '', newPathname)
    
    if (isNarrowViewport && id) {
      setIsFullWidth(true)
    }
  }, [isNarrowViewport])

  const handleCloseProcedure = useCallback(() => {
    setSelectedProcedureId(null)
    setIsFullWidth(false)
    setIsEditMode(false)
    
    // Update URL without triggering a navigation/re-render
    window.history.pushState(null, '', '/lab/procedures')
  }, [])

  // Memoize click handler - moved to top with other hooks
  const getProcedureClickHandler = useCallback((procedureId: string) => {
    return (e?: React.MouseEvent | React.SyntheticEvent | any) => {
      if (e && typeof e.preventDefault === 'function') {
        e.preventDefault()
      }
      setIsFullWidth(false)
      try { (document.activeElement as HTMLElement | null)?.blur?.() } catch {}
      handleSelectProcedure(procedureId)
    }
  }, [handleSelectProcedure])

  const loadProcedures = useCallback(async (force = false) => {
    const requestId = ++loadRequestIdRef.current

    if (!selectedAccount?.id) {
      setProcedures([])
      setNextToken(null)
      setHasMore(false)
      setError(null)
      setIsInitialLoading(isLoadingAccounts)
      setIsFetchingProcedures(isLoadingAccounts)
      setIsHydratingTasks(false)
      hasLoadedProceduresOnceRef.current = false
      procedureTaskMapRef.current = new Map()
      return
    }

    const shouldBlockInitialRender = !hasLoadedProceduresOnceRef.current

    try {
      if (shouldBlockInitialRender) {
        setIsInitialLoading(true)
      }
      setIsFetchingProcedures(true)
      setError(null)
      lastLoadTimeRef.current = Date.now()
      // Phase A: fetch first procedure page and render immediately without task hydration
      const proceduresResult: any = await getAmplifyClient().graphql({
        query: `
          query ListProcedureByAccountIdAndUpdatedAt(
            $accountId: String!
            $sortDirection: ModelSortDirection
            $limit: Int
            $nextToken: String
          ) {
            listProcedureByAccountIdAndUpdatedAt(
              accountId: $accountId
              sortDirection: $sortDirection
              limit: $limit
              nextToken: $nextToken
            ) {
              items {
                ${PROCEDURE_CARD_FIELDS}
              }
              nextToken
            }
          }
        `,
        variables: {
          accountId: selectedAccount.id,
          sortDirection: 'DESC',
          limit: PROCEDURE_PAGE_SIZE,
          nextToken: null
        }
      })

      if (requestId !== loadRequestIdRef.current) return

      const procedureResponse: any = proceduresResult.data?.listProcedureByAccountIdAndUpdatedAt
      const firstPageItems: Procedure[] = procedureResponse?.items || []
      const newNextToken: string | null = procedureResponse?.nextToken ?? null
      const firstPageWithoutTasks = sortProceduresByStartTime(
        firstPageItems.map((procedure: Procedure) => ({ ...procedure, task: null }))
      )

      setProcedures(firstPageWithoutTasks)
      setNextToken(newNextToken)
      setHasMore(!!newNextToken)
      setIsInitialLoading(false)
      setIsFetchingProcedures(false)
      hasLoadedProceduresOnceRef.current = true
      void hydrateProcedurePerformanceSummaries(firstPageWithoutTasks).then((hydrated) => {
        if (requestId !== loadRequestIdRef.current) return
        setProcedures((previous) =>
          sortProceduresByStartTime(
            previous.map((procedure) => {
              const hydratedProcedure = hydrated.find((item) => item.id === procedure.id)
              return hydratedProcedure
                ? { ...procedure, feedbackEvaluationSummary: hydratedProcedure.feedbackEvaluationSummary ?? null }
                : procedure
            })
          )
        )
      })

      // Phase B: hydrate task/status data in background without blocking rendered cards
      setIsHydratingTasks(true)
      try {
        const tasksResult = await getAmplifyClient().graphql({
          query: `
            query ListTaskByAccountIdAndUpdatedAt(
              $accountId: String!
              $sortDirection: ModelSortDirection
              $limit: Int
            ) {
              listTaskByAccountIdAndUpdatedAt(
                accountId: $accountId
                sortDirection: $sortDirection
                limit: $limit
              ) {
                items {
                  ${TASK_CARD_FIELDS}
                }
              }
            }
          `,
          variables: {
            accountId: selectedAccount.id,
            sortDirection: 'DESC',
            limit: 1000
          }
        })

        if (requestId !== loadRequestIdRef.current) return

        const allTasks = (tasksResult as any).data?.listTaskByAccountIdAndUpdatedAt?.items || []
        const procedureTaskMap = new Map<string, Task>()
        allTasks.forEach((task: Task) => {
          const procedureId = procedureIdFromTaskTarget(task.target)
          if (procedureId) procedureTaskMap.set(procedureId, task)
        })

        procedureTaskMapRef.current = procedureTaskMap

        const proceduresWithTasks = proceduresResult.data?.listProcedureByAccountIdAndUpdatedAt?.items
          ? firstPageItems.map((procedure: Procedure) => ({
              ...procedure,
              task: procedureTaskMap.get(procedure.id) || null,
            }))
          : []
        const hydratedProceduresWithTasks = await hydrateProcedurePerformanceSummaries(proceduresWithTasks)

        setProcedures(prev =>
          sortProceduresByStartTime(
            prev.map(procedure => {
              const hydratedProcedure = hydratedProceduresWithTasks.find((item) => item.id === procedure.id)
              return {
                ...procedure,
                task: procedureTaskMap.get(procedure.id) || null,
                feedbackEvaluationSummary: hydratedProcedure?.feedbackEvaluationSummary ?? procedure.feedbackEvaluationSummary ?? null,
              }
            })
          )
        )

        if (force) {
          console.log('Forced reload completed for procedures first page')
        }
      } catch (taskErr) {
        if (requestId !== loadRequestIdRef.current) return
        console.error('Error hydrating procedure tasks:', taskErr)
        setError(taskErr instanceof Error ? taskErr.message : 'Failed to hydrate procedure task state')
      } finally {
        if (requestId === loadRequestIdRef.current) {
          setIsHydratingTasks(false)
        }
      }
    } catch (err) {
      if (requestId !== loadRequestIdRef.current) return
      console.error('Error loading procedures:', err)
      setError(err instanceof Error ? err.message : 'Failed to load procedures')
      setIsInitialLoading(false)
      setIsFetchingProcedures(false)
      setIsHydratingTasks(false)
    }
  }, [hydrateProcedurePerformanceSummaries, selectedAccount?.id, isLoadingAccounts])

  const loadMoreProcedures = useCallback(async () => {
    if (!selectedAccount?.id || !nextToken || isLoadingMore) return
    setIsLoadingMore(true)
    try {
      const moreResult = await getAmplifyClient().graphql({
        query: `
          query ListProcedureByAccountIdAndUpdatedAt(
            $accountId: String!
            $sortDirection: ModelSortDirection
            $limit: Int
            $nextToken: String
          ) {
            listProcedureByAccountIdAndUpdatedAt(
              accountId: $accountId
              sortDirection: $sortDirection
              limit: $limit
              nextToken: $nextToken
            ) {
              items {
                ${PROCEDURE_CARD_FIELDS}
              }
              nextToken
            }
          }
        `,
        variables: {
          accountId: selectedAccount.id,
          sortDirection: 'DESC',
          limit: PROCEDURE_PAGE_SIZE,
          nextToken
        }
      })
      const moreResponse = (moreResult as any).data?.listProcedureByAccountIdAndUpdatedAt
      const moreItems: Procedure[] = moreResponse?.items || []
      const newNextToken: string | null = moreResponse?.nextToken ?? null

      const taskMap = procedureTaskMapRef.current
      const merged: ProcedureWithTask[] = moreItems.map((procedure) => ({
        ...procedure,
        task: taskMap.get(procedure.id) ?? null
      }))
      const hydratedMerged = await hydrateProcedurePerformanceSummaries(merged)

      setProcedures(prev => sortProceduresByStartTime([...prev, ...hydratedMerged]))
      setNextToken(newNextToken)
      setHasMore(!!newNextToken)
    } catch (err) {
      console.error('[procedures] loadMoreProcedures failed', err)
    } finally {
      setIsLoadingMore(false)
    }
  }, [hydrateProcedurePerformanceSummaries, selectedAccount?.id, nextToken, isLoadingMore])

  useEffect(() => {
    loadProcedures()
  }, [loadProcedures])

  useEffect(() => {
    if (inView && hasMore && !isLoadingMore) {
      loadMoreProcedures()
    }
  }, [inView, hasMore, isLoadingMore, loadMoreProcedures])

  // Task monitoring with real-time subscriptions for procedure tasks
  useEffect(() => {
    const taskSubscription = observeTaskUpdates().subscribe({
      next: (value: any) => {
        const { type, data } = value;
        
        const procedureId = procedureIdFromTaskTarget(data?.target);
        if (procedureId) {
          console.log(`Updating procedure ${procedureId} with task data:`, data);

          // Update the procedures list with new task data, preserving stages
          setProcedures(prevProcedures =>
            sortProceduresByStartTime(prevProcedures.map(procedure => {
              if (procedure.id === procedureId) {
                // Merge new task data with existing task, preserving stages
                const updatedTask = procedure.task
                  ? { ...procedure.task, ...data, stages: procedure.task.stages } // Preserve existing stages
                  : data;
                return { ...procedure, task: updatedTask };
              }
              return procedure;
            }))
          );
        }
      },
      error: (error: any) => {
        console.error('Task subscription error:', error);
      }
    });

    const stageSubscription = observeTaskStageUpdates().subscribe({
      next: (value: any) => {
        const { type, data } = value;
        
        if (data?.taskId) {
          // Update the procedures list with new stage data
          setProcedures(prevProcedures =>
            sortProceduresByStartTime(prevProcedures.map((procedure: ProcedureWithTask) => {
              if (procedure.task?.id === data.taskId) {
                console.log(`Updating procedure ${procedure.id} stages with:`, data);
                
                // Handle LazyLoader for stages - access synchronously if available
                const currentStages = procedure.task?.stages as any;
                const updatedStages = currentStages?.items ? [...currentStages.items] : [];
                const existingStageIndex = updatedStages.findIndex((stage: any) => stage.id === data.id);
                
                if (existingStageIndex >= 0) {
                  updatedStages[existingStageIndex] = { ...updatedStages[existingStageIndex], ...data };
                } else {
                  updatedStages.push(data);
                }
                
                const updatedTask = {
                  ...procedure.task!,
                  stages: currentStages ? {
                    ...currentStages,
                    items: updatedStages.sort((a: any, b: any) => a.order - b.order)
                  } : { items: updatedStages.sort((a: any, b: any) => a.order - b.order) },
                  currentStageId: data.status === 'RUNNING' ? data.name : procedure.task?.currentStageId
                };

                console.log('Updated procedure task with stages:', {
                  procedureId: procedure.id,
                  taskId: updatedTask.id,
                  stagesCount: updatedTask.stages?.items?.length,
                  currentStageId: updatedTask.currentStageId
                });

                return { ...procedure, task: updatedTask };
              }
              return procedure;
            }))
          );
        }
      },
      error: (error: any) => {
        console.error('TaskStage subscription error:', error);
      }
    });

    return () => {
      taskSubscription.unsubscribe();
      stageSubscription.unsubscribe();
    };
  }, []); // Empty dependency array since we want this to run once

  // Realtime subscriptions for procedure create/update events
  useEffect(() => {
    if (!selectedAccount?.id) return;
    const accountId = selectedAccount.id;
    const subscriptionHandlers: { unsubscribe: () => void }[] = [];

    try {
      const createSub = (getAmplifyClient().graphql({
        query: PROCEDURE_CREATE_SUBSCRIPTION_FOR_CARDS
      }) as unknown as { subscribe: Function }).subscribe({
        next: ({ data }: { data?: { onCreateProcedure: any } }) => {
          const procedure = data?.onCreateProcedure;
          if (!procedure || procedure.accountId !== accountId) return;
          // Subscription payloads don't resolve @belongsTo relations — re-fetch the full record.
          void (getAmplifyClient().graphql({
            query: `query GetProcedureForCard($id: ID!) { getProcedure(id: $id) { ${PROCEDURE_CARD_FIELDS} } }`,
            variables: { id: procedure.id }
          }) as any).then((result: any) => {
            const full = result?.data?.getProcedure ?? procedure
            const procedureWithTask = { ...full, task: null } as ProcedureWithTask
            setProcedures(prev => {
              if (prev.some(p => p.id === full.id)) return prev;
              return sortProceduresByStartTime([procedureWithTask, ...prev]);
            });
            void hydrateProcedurePerformanceSummaries([procedureWithTask]).then(([hydratedProcedure]) => {
              if (!hydratedProcedure) return
              setProcedures(prev =>
                sortProceduresByStartTime(
                  prev.map(p => p.id === hydratedProcedure.id ? { ...p, ...hydratedProcedure, task: p.task ?? hydratedProcedure.task } : p)
                )
              )
            })
          }).catch(() => {
            // Fall back to bare subscription payload
            const procedureWithTask = { ...procedure, task: null } as ProcedureWithTask
            setProcedures(prev => {
              if (prev.some(p => p.id === procedure.id)) return prev;
              return sortProceduresByStartTime([procedureWithTask, ...prev]);
            });
          })
        },
        error: (error: Error) => console.error('Error in create procedure subscription:', error)
      });
      subscriptionHandlers.push(createSub);
    } catch (error) {
      console.error('Failed to set up create procedure subscription:', error);
    }

    try {
      const updateSub = (getAmplifyClient().graphql({
        query: PROCEDURE_UPDATE_SUBSCRIPTION_FOR_CARDS
      }) as unknown as { subscribe: Function }).subscribe({
        next: ({ data }: { data?: { onUpdateProcedure: any } }) => {
          const updated = data?.onUpdateProcedure;
          if (!updated || updated.accountId !== accountId) return;
          // Subscription payloads don't resolve @belongsTo relations — preserve existing
          // scorecard/score/metadata from the stored record so they don't get wiped.
          let existingTask: Task | null | undefined = null
          setProcedures(prev =>
            sortProceduresByStartTime(
              prev.map(p => {
                if (p.id !== updated.id) return p
                existingTask = p.task
                return {
                  ...p,
                  ...updated,
                  scorecard: updated.scorecard ?? p.scorecard,
                  score: updated.score ?? p.score,
                  metadata: updated.metadata ?? p.metadata,
                  task: p.task,
                }
              })
            )
          );
          void hydrateProcedurePerformanceSummaries([{ ...updated, task: existingTask ?? null } as ProcedureWithTask]).then(([hydratedProcedure]) => {
            if (!hydratedProcedure) return
            setProcedures(prev =>
              sortProceduresByStartTime(
                prev.map(p => {
                  if (p.id !== hydratedProcedure.id) return p
                  return {
                    ...p,
                    ...hydratedProcedure,
                    scorecard: hydratedProcedure.scorecard ?? p.scorecard,
                    score: hydratedProcedure.score ?? p.score,
                    metadata: hydratedProcedure.metadata ?? p.metadata,
                    task: p.task ?? hydratedProcedure.task,
                  }
                })
              )
            )
          })
        },
        error: (error: Error) => console.error('Error in update procedure subscription:', error)
      });
      subscriptionHandlers.push(updateSub);
    } catch (error) {
      console.error('Failed to set up update procedure subscription:', error);
    }

    const upsertEvaluationSummary = (rawEvaluation: any) => {
      if (!rawEvaluation?.id) return
      const summary = feedbackEvaluationSummaryFromView(evaluationToScoreEvaluationView(rawEvaluation))
      if (!summary) return
      setProcedures(prev =>
        prev.map(procedure =>
          procedure.feedbackEvaluationSummary?.id === summary.id
            ? { ...procedure, feedbackEvaluationSummary: summary }
            : procedure
        )
      )
    }

    try {
      const evaluationCreateResult = getAmplifyClient().graphql({
        query: EVALUATION_CREATE_SUBSCRIPTION_FOR_CARDS
      }) as unknown as { subscribe?: Function }
      if (typeof evaluationCreateResult.subscribe === 'function') {
        const evaluationCreateSub = evaluationCreateResult.subscribe({
          next: ({ data }: { data?: { onCreateEvaluation: any } }) => upsertEvaluationSummary(data?.onCreateEvaluation),
          error: (error: Error) => console.error('Error in create evaluation subscription:', error)
        })
        subscriptionHandlers.push(evaluationCreateSub)
      }
    } catch (error) {
      console.error('Failed to set up create evaluation subscription:', error)
    }

    try {
      const evaluationUpdateResult = getAmplifyClient().graphql({
        query: EVALUATION_UPDATE_SUBSCRIPTION_FOR_CARDS
      }) as unknown as { subscribe?: Function }
      if (typeof evaluationUpdateResult.subscribe === 'function') {
        const evaluationUpdateSub = evaluationUpdateResult.subscribe({
          next: ({ data }: { data?: { onUpdateEvaluation: any } }) => upsertEvaluationSummary(data?.onUpdateEvaluation),
          error: (error: Error) => console.error('Error in update evaluation subscription:', error)
        })
        subscriptionHandlers.push(evaluationUpdateSub)
      }
    } catch (error) {
      console.error('Failed to set up update evaluation subscription:', error)
    }

    try {
      const evaluationDeleteResult = getAmplifyClient().graphql({
        query: EVALUATION_DELETE_SUBSCRIPTION_FOR_CARDS
      }) as unknown as { subscribe?: Function }
      if (typeof evaluationDeleteResult.subscribe === 'function') {
        const evaluationDeleteSub = evaluationDeleteResult.subscribe({
          next: ({ data }: { data?: { onDeleteEvaluation: any } }) => {
            const deleted = data?.onDeleteEvaluation
            if (!deleted?.id) return
            setProcedures(prev =>
              prev.map(procedure =>
                procedure.feedbackEvaluationSummary?.id === deleted.id
                  ? { ...procedure, feedbackEvaluationSummary: null }
                  : procedure
              )
            )
          },
          error: (error: Error) => console.error('Error in delete evaluation subscription:', error)
        })
        subscriptionHandlers.push(evaluationDeleteSub)
      }
    } catch (error) {
      console.error('Failed to set up delete evaluation subscription:', error)
    }

    return () => {
      subscriptionHandlers.forEach(sub => {
        try { sub.unsubscribe(); } catch {}
      });
    };
  }, [hydrateProcedurePerformanceSummaries, selectedAccount?.id]);

  const handleEditProcedure = useCallback((procedureId: string) => {
    console.log('Edit procedure:', procedureId)
    setIsEditMode(true)
  }, [])

  const handleDuplicateProcedure = useCallback(async (procedureId: string) => {
    console.log('handleDuplicateProcedure called with:', procedureId)
    try {
      const procedure = procedures.find(proc => proc.id === procedureId)
      console.log('Found procedure:', procedure)
      if (!procedure) {
        toast.error('Procedure not found')
        return
      }

      console.log('Creating duplicate procedure...')
      console.log('Selected account:', selectedAccount?.id)
      
      if (!selectedAccount?.id) {
        toast.error('No account selected')
        return
      }
      
      // Create a duplicate
      const { data: newProcedure } = await (getAmplifyClient().models.Procedure.create as any)({
        featured: procedure.featured || false,
        code: procedure.code || null, // Copy the code if it exists
        scorecardId: procedure.scorecardId,
        scoreId: procedure.scoreId,
        accountId: selectedAccount.id,
      })

      console.log('New procedure created:', newProcedure)
      if (newProcedure) {
        // TODO: Copy the procedure nodes and versions from the original
        // For now, just refresh the procedures list
        await loadProcedures(true) // Force reload to ensure duplicate appears
        // Select the newly created duplicate procedure
        handleSelectProcedure(newProcedure.id)
        toast.success('Procedure duplicated successfully')
      }
    } catch (error) {
      console.error('Error duplicating procedure:', error)
      toast.error('Failed to duplicate procedure')
    }
  }, [procedures, loadProcedures, handleSelectProcedure, selectedAccount])

  // Handle URL synchronization for browser back/forward navigation
  useEffect(() => {
    const syncFromUrl = () => {
      const procedureMatch = window.location.pathname.match(/\/lab\/procedures\/([^\/]+)/)
      const idFromUrl = procedureMatch ? (procedureMatch[1] as string) : null
      // Only sync on back/forward, not on programmatic changes immediately after click
      setSelectedProcedureId(prev => prev === idFromUrl ? prev : idFromUrl)
    }
    
    // Listen for browser back/forward navigation
    window.addEventListener('popstate', syncFromUrl)
    return () => window.removeEventListener('popstate', syncFromUrl)
  }, [])

  // Focus handler disabled to prevent unwanted reloads when returning to browser
  // Data will refresh naturally through other user interactions or manual refresh

  const handleCreateProcedure = () => {
    setShowTemplateSelector(true)
  }

  // Helper function to create Task with stages for a procedure
  const createTaskWithStagesForProcedure = async (
    procedureId: string,
    accountId: string,
    runParameters?: Record<string, any>,
  ) => {
    console.log('[createTaskWithStagesForProcedure] Starting for procedure:', procedureId, 'account:', accountId)
    
    // Create Task
    const metadata: Record<string, any> = {
      type: 'Procedure',
      procedure_id: procedureId,
      task_type: 'Procedure',
    }
    if (runParameters && Object.keys(runParameters).length > 0) {
      metadata.run_parameters = runParameters
    }

    const taskInput = {
      accountId: accountId,
      type: 'Procedure',
      status: 'PENDING',
      target: `procedure/run/${procedureId}`,
      command: `procedure run ${procedureId}`,
      description: `Procedure workflow for ${procedureId}`,
      dispatchStatus: 'PENDING',
      metadata: JSON.stringify(metadata)
    }

    const taskResult = await getAmplifyClient().graphql({
      query: `
        mutation CreateTask($input: CreateTaskInput!) {
          createTask(input: $input) {
            id
            accountId
            type
            status
          }
        }
      `,
      variables: { input: taskInput }
    })

    const task = (taskResult as any).data?.createTask
    console.log('[createTaskWithStagesForProcedure] Task created:', task)
    
    if (!task) {
      console.error('[createTaskWithStagesForProcedure] No task returned from mutation')
      throw new Error('Failed to create Task')
    }

    // Define stages matching the state machine
    const stages = [
      { name: 'Start', order: 1, statusMessage: 'Initializing procedure...' },
      { name: 'Evaluation', order: 2, statusMessage: 'Running initial evaluation...' },
      { name: 'Hypothesis', order: 3, statusMessage: 'Analyzing results and generating hypotheses...' },
      { name: 'Test', order: 4, statusMessage: 'Testing hypothesis with score version...' },
      { name: 'Insights', order: 5, statusMessage: 'Analyzing test results and generating insights...' }
    ]

    // Create each stage
    console.log('[createTaskWithStagesForProcedure] Creating', stages.length, 'stages (Start, Evaluation, Hypothesis, Test, Insights) for task:', task.id)
    for (const stage of stages) {
      console.log('[createTaskWithStagesForProcedure] Creating stage:', stage.name, 'order:', stage.order)
      await getAmplifyClient().graphql({
        query: `
          mutation CreateTaskStage($input: CreateTaskStageInput!) {
            createTaskStage(input: $input) {
              id
              taskId
              name
              order
              status
            }
          }
        `,
        variables: {
          input: {
            taskId: task.id,
            name: stage.name,
            order: stage.order,
            status: 'PENDING',
            statusMessage: stage.statusMessage
          }
        }
      })
    }

    console.log(`✓ Created Task ${task.id} with ${stages.length} stages (Start, Evaluation, Hypothesis, Test, Insights)`)
    return task
  }

  const handleCreateProcedureFromTemplate = async (template: Schema['Procedure']['type'], parameters?: Record<string, any>) => {
    if (!selectedAccount?.id) {
      toast.error('No account selected')
      return
    }

    try {
      console.log('Creating procedure from template:', {
        parentProcedureId: template.id,
        templateName: template.name,
        templateCode: template.code?.substring(0, 100) + '...',
        parameters
      })

      // Process template YAML to inject parameter values
      let processedCode = template.code || ''

      if (parameters && template.code) {
        // Parse the YAML to find the parameters section
        try {
          const parsed = parseYaml(template.code) as any
          
          // If there's a parameters section, add values to it
          if (parsed.parameters && Array.isArray(parsed.parameters)) {
            parsed.parameters = parsed.parameters.map((param: any) => ({
              ...param,
              value: parameters[param.name] // Add the actual value
            }))
          }

          // Tactus params mapping format
          if (parsed.params && typeof parsed.params === 'object') {
            for (const [name, value] of Object.entries(parameters)) {
              if (parsed.params[name] && typeof parsed.params[name] === 'object') {
                parsed.params[name].value = value
              }
            }
          }
          
          // Convert back to YAML
          processedCode = stringifyYaml(parsed)
        } catch (yamlError) {
          console.warn('Could not parse template YAML, using original:', yamlError)
        }
      }
      
      const resolvedScorecardId = parameters?.scorecard_id || selectedScorecard || null
      const resolvedScoreId = parameters?.score_id || selectedScore || null

      // Create procedure run from template. Name is required by schema.
      const createInput: Record<string, any> = {
        name: template.name || 'Procedure Run',
        description: template.description || undefined,
        featured: false,
        isTemplate: false,
        parentProcedureId: template.id,
        code: processedCode,
        category: template.category || undefined,
        version: template.version || undefined,
        status: 'PENDING',
        metadata: JSON.stringify({
          templateId: template.id,
          templateName: template.name || 'Procedure Template'
        }),
        accountId: selectedAccount.id,
      }

      if (resolvedScorecardId) {
        createInput.scorecardId = resolvedScorecardId
      }
      if (resolvedScoreId) {
        createInput.scoreId = resolvedScoreId
      }
      
      console.log('Create input:', createInput)
      
      // Use direct GraphQL mutation instead of getAmplifyClient().models
      const result = await getAmplifyClient().graphql({
        query: `
          mutation CreateProcedure($input: CreateProcedureInput!) {
            createProcedure(input: $input) {
              ${PROCEDURE_CARD_FIELDS}
            }
          }
        `,
        variables: { input: createInput }
      })

      const newProcedure = (result as any).data?.createProcedure
      const errors = (result as any).errors

      if (errors && errors.length > 0) {
        console.error('GraphQL errors creating procedure:', errors)
        toast.error('Failed to create procedure: ' + errors.map((e: any) => e.message).join(', '))
        return
      }

      if (newProcedure) {
        console.log('Procedure created successfully:', newProcedure)
        
        // Create Task with stages for the new procedure
        let createdTask = null
        try {
          console.log('Creating Task with stages for procedure:', newProcedure.id)
          createdTask = await createTaskWithStagesForProcedure(newProcedure.id, selectedAccount.id, parameters)
          console.log('✓ Task and stages created:', createdTask)
        } catch (taskError) {
          console.error('Failed to create Task for procedure:', taskError)
          // Don't fail the whole operation - procedure is still created
          toast.warning('Procedure created but task stages may not be set up')
        }
        
        // Small delay to ensure database writes complete
        await new Promise(resolve => setTimeout(resolve, 500))
        
        // Refresh procedures list and select the new procedure
        console.log('About to reload procedures for newly created procedure:', newProcedure.id)
        await loadProcedures(true) // Force reload to ensure new procedure appears
        console.log('Finished reloading procedures')
        handleSelectProcedure(newProcedure.id)
        // Close template selector
        setShowTemplateSelector(false)
        toast.success(`Procedure created from template "${template.name}"`)
      } else {
        console.error('No procedure data returned')
        toast.error('Failed to create procedure: No data returned')
      }
    } catch (error) {
      console.error('Error creating procedure from template:', error)
      toast.error('Failed to create procedure from template')
    }
  }

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.pageX
    const startWidth = leftPanelWidth

    const handleDrag = (e: MouseEvent) => {
      const delta = e.pageX - startX
      const newWidth = Math.min(Math.max(startWidth + (delta / window.innerWidth) * 100, 20), 80)
      setLeftPanelWidth(newWidth)
    }

    const handleDragEnd = () => {
      document.removeEventListener('mousemove', handleDrag)
      document.removeEventListener('mouseup', handleDragEnd)
    }

    document.addEventListener('mousemove', handleDrag)
    document.addEventListener('mouseup', handleDragEnd)
  }

  const handleDelete = async (procedureId: string) => {
    try {
      await (getAmplifyClient().models.Procedure.delete as any)({ id: procedureId })
      setProcedures(prev => prev.filter(proc => proc.id !== procedureId))
      if (selectedProcedureId === procedureId) {
        setSelectedProcedureId(null)
        setIsEditMode(false)
        // Update URL when deleting the currently selected procedure
        window.history.pushState(null, '', '/lab/procedures')
      }
      toast.success('Procedure deleted successfully')
    } catch (error) {
      console.error('Error deleting procedure:', error)
      toast.error('Failed to delete procedure')
    }
  }

  // Transform procedures to ProcedureTaskData - memoized to prevent unnecessary re-renders
  const transformProcedure = useCallback((procedure: ProcedureWithTask): ProcedureTaskData => {
    let procedureType = 'Procedure'
    try {
      const meta = typeof procedure.metadata === 'string' ? JSON.parse(procedure.metadata) : procedure.metadata
      if (meta?.procedure_type) {
        procedureType = meta.procedure_type
      } else if (
        procedure.name?.startsWith('Optimizer:') ||
        procedure.name === 'Feedback Alignment Optimizer'
      ) {
        procedureType = 'Optimizer Procedure'
      }
    } catch { /* ignore malformed metadata */ }
    return ({
    id: procedure.id,
    title: procedure.scorecard?.name
      ? procedure.scorecard.name
      : (procedure.name || 'Procedure'),
    featured: procedure.featured || false,
    createdAt: procedure.createdAt,
    updatedAt: procedure.updatedAt,
    scorecard: procedure.scorecard
      ? { name: procedure.scorecard.name }
      : null,
    score: procedure.score ? { name: procedure.score.name } : null,
    procedureType: procedureType,
    description: procedure.description || undefined,
    task: procedure.task ? {
      id: procedure.task.id,
      type: procedureType,
      status: procedure.task.status || 'PENDING',
      target: procedure.task.target || '',
      command: procedure.task.command || '',
      description: procedure.task.description || undefined,
      dispatchStatus: procedure.task.dispatchStatus || undefined,
      metadata: typeof procedure.task.metadata === 'string' ? procedure.task.metadata : JSON.stringify(procedure.task.metadata),
      createdAt: procedure.task.createdAt || undefined,
      startedAt: procedure.task.startedAt || undefined,
      completedAt: procedure.task.completedAt || undefined,
      estimatedCompletionAt: procedure.task.estimatedCompletionAt || undefined,
      errorMessage: procedure.task.errorMessage || undefined,
      errorDetails: typeof procedure.task.errorDetails === 'string' ? procedure.task.errorDetails : JSON.stringify(procedure.task.errorDetails) || undefined,
      currentStageId: procedure.task.currentStageId || undefined,
      stages: procedure.task.stages ? {
        items: (procedure.task.stages as any)?.items || []
      } : undefined
    } : undefined,
    feedbackEvaluationSummary: procedure.feedbackEvaluationSummary ?? null,
  })}, [])
  

  if ((isInitialLoading || isFetchingProcedures || isLoadingAccounts) && procedures.length === 0) {
    return <ProceduresDashboardSkeleton />
  }


  // Render selected procedure detail or edit form
  const renderSelectedProcedure = () => {
    if (!selectedProcedureId) return null
    const procedure = procedures.find(proc => proc.id === selectedProcedureId)
    if (!procedure) return null

    // If in edit mode, render the edit form instead of the detail view
    if (isEditMode) {
      return (
        <ProcedureTaskEdit 
          procedureId={selectedProcedureId}
          initialEditMode={true}
          onSave={() => {
            // Exit edit mode and refresh procedures list after save
            setIsEditMode(false)
            // Reload procedures to get updated data
            loadProcedures(true)
          }}
          onCancel={() => {
            // Exit edit mode without saving
            setIsEditMode(false)
          }}
        />
      )
    }

    return (
      <ProcedureTask
        variant="detail"
        procedure={transformProcedure(procedure)}
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={handleCloseProcedure}
        onDelete={handleDelete}
        onEdit={handleEditProcedure}
        onDuplicate={handleDuplicateProcedure}
        onConversationFullscreenChange={setIsConversationFullscreen}
      />
    )
  }

  return (
    <div className="@container flex flex-col h-full p-3 overflow-hidden">
      {/* Fixed header */}
      <div className="flex @[600px]:flex-row flex-col @[600px]:items-center @[600px]:justify-between items-stretch gap-3 pb-3 flex-shrink-0">
        <div className="@[600px]:flex-grow w-full">
          <ScorecardContext 
            selectedScorecard={selectedScorecard}
            setSelectedScorecard={setSelectedScorecard}
            selectedScore={selectedScore}
            setSelectedScore={setSelectedScore}
          />
        </div>
        <div className="flex-shrink-0">
          <Button onClick={handleCreateProcedure}>
            <Plus className="h-4 w-4 mr-2" />
            Create
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Unable to fully refresh procedures: {error}
        </div>
      )}

      {isHydratingTasks && procedures.length > 0 && (
        <div className="pb-2 text-xs text-muted-foreground">
          Updating procedure statuses...
        </div>
      )}

      {/* Procedures Content */}
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        <AnimatePresence mode="popLayout">
          <motion.div
            key="procedures-layout"
            className="flex flex-1 min-h-0"
            layout
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{
              type: "spring",
              stiffness: 300,
              damping: 30,
              opacity: { duration: 0.2 }
            }}
          >
            {/* Left panel - grid content */}
            <motion.div
              className={`${selectedProcedureId && !isNarrowViewport && isFullWidth ? 'hidden' : 'flex-1'} h-full overflow-auto`}
              style={selectedProcedureId && !isNarrowViewport && !isFullWidth ? {
                width: `${leftPanelWidth}%`
              } : undefined}
              layout
              transition={{
                type: "spring",
                stiffness: 300,
                damping: 30
              }}
            >
              <div className="@container space-y-3 overflow-visible">
                {/* ProceduresGauges at the top - only show when not in mobile selected procedure view */}
                {!(selectedProcedureId && isNarrowViewport) && (
                  <ProceduresGauges />
                )}
                {procedures.length === 0 &&
                !!selectedAccount?.id &&
                !isLoadingAccounts &&
                !isInitialLoading &&
                !isFetchingProcedures &&
                !isHydratingTasks ? (
                  <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
                    No procedures found
                  </div>
                ) : procedures.length > 0 ? (
                  <div className={`
                    grid gap-3
                    ${selectedProcedureId && !isNarrowViewport && !isFullWidth ? 'grid-cols-1' : 'grid-cols-1 @[640px]:grid-cols-2'}
                  `}>
                    {procedures.map((procedure) => {
                      const clickHandler = getProcedureClickHandler(procedure.id)

                      return (
                        <div
                          key={procedure.id}
                          role="button"
                          tabIndex={0}
                          onClick={clickHandler}
                          onKeyDown={(ev) => {
                            if (ev.key === 'Enter' || ev.key === ' ') {
                              ev.preventDefault()
                              clickHandler()
                            }
                          }}
                          aria-pressed={procedure.id === selectedProcedureId}
                          data-selected={procedure.id === selectedProcedureId ? 'true' : 'false'}
                        >
                          <ProcedureTask
                            variant="grid"
                            procedure={transformProcedure(procedure)}
                            onClick={clickHandler}
                            isSelected={procedure.id === selectedProcedureId}
                            onDelete={handleDelete}
                            onEdit={handleEditProcedure}
                            onDuplicate={handleDuplicateProcedure}
                          />
                        </div>
                      )
                    })}
                  </div>
                ) : null}
                {/* Infinite scroll sentinel */}
                <div ref={sentinelRef} className="h-4" />
                {isLoadingMore && (
                  <div className="animate-pulse space-y-3 pb-3">
                    <div className="h-24 bg-muted rounded-lg" />
                    <div className="h-24 bg-muted rounded-lg" />
                  </div>
                )}
              </div>
            </motion.div>

            {/* Divider for split view */}
            {selectedProcedureId && !isNarrowViewport && !isFullWidth && (
              <div
                className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
                onMouseDown={handleDragStart}
              >
                <div className="absolute inset-0 rounded-full transition-colors duration-150 
                  group-hover:bg-accent" />
              </div>
            )}

            {/* Right panel - procedure detail view */}
            <AnimatePresence>
              {selectedProcedureId && !isNarrowViewport && !isFullWidth && !isConversationFullscreen && (
                <motion.div 
                  key={`procedure-detail-${selectedProcedureId}`}
                  className="h-full overflow-hidden flex-shrink-0"
                  style={{ width: `${100 - leftPanelWidth}%` }}
                  initial={{ width: 0, opacity: 0 }}
                  animate={{ 
                    width: `${100 - leftPanelWidth}%`, 
                    opacity: 1 
                  }}
                  exit={{ 
                    width: 0, 
                    opacity: 0 
                  }}
                  transition={{ 
                    type: "spring", 
                    stiffness: 300, 
                    damping: 30 
                  }}
                >
                  {renderSelectedProcedure()}
                </motion.div>
              )}
            </AnimatePresence>

          </motion.div>
        </AnimatePresence>
        
        {/* Full-screen view for mobile or full-width mode */}
        {selectedProcedureId && (isNarrowViewport || isFullWidth) && !isConversationFullscreen && (
          <div className="fixed inset-0 z-50 overflow-y-auto">
            {renderSelectedProcedure()}
          </div>
        )}
        
        {/* Conversation full-screen view - renders when conversation is fullscreen */}
        {selectedProcedureId && isConversationFullscreen && (
          <div className="fixed inset-0 z-50 bg-background">
            <div className="w-full h-screen bg-background py-6 px-3 flex flex-col">
              <div className="flex items-center justify-between mb-4 flex-shrink-0 px-3">
                <h3 className="text-lg font-semibold flex items-center gap-2 text-muted-foreground">
                  <BookOpenCheck className="h-5 w-5" />
                  Conversations
                </h3>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                  onClick={() => setIsConversationFullscreen(false)}
                  aria-label="Exit fullscreen"
                >
                  <Shrink className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex-1 min-h-0">
                <ProcedureConversationViewer
                  procedureId={selectedProcedureId}
                  onSessionCountChange={() => {}}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Template Selector Modal */}
      {selectedAccount && (
        <TemplateSelector
          accountId={selectedAccount.id}
          open={showTemplateSelector}
          onOpenChange={setShowTemplateSelector}
          onTemplateSelect={handleCreateProcedureFromTemplate}
        />
      )}
    </div>
  )
}

// Memoize the component to prevent unnecessary re-renders from parent
export default React.memo(ProceduresDashboard)
