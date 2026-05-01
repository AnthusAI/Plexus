'use client'

import * as React from 'react'
import { generateClient } from 'aws-amplify/api'
import { Copy, Link as LinkIcon, MoreHorizontal } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import ProcedureTask, { type ProcedureTaskData } from '@/components/ProcedureTask'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import {
  copyText,
  currentProcedureFeedbackEvaluationId,
  EVALUATION_CREATE_SUBSCRIPTION_FOR_CARDS,
  EVALUATION_DELETE_SUBSCRIPTION_FOR_CARDS,
  EVALUATION_UPDATE_SUBSCRIPTION_FOR_CARDS,
  evaluationToScoreEvaluationView,
  evaluationUrl,
  findBestOptimizerEvaluation,
  hydrateProcedureRunFeedbackEvaluation,
  hydrateProcedureRunsFeedbackEvaluations,
  loadOptimizerRuns,
  mergeFeedbackEvaluationIntoProcedureRun,
  mergeTaskIntoProcedureRun,
  mergeTaskStageIntoProcedureRun,
  manifestTouchesVersion,
  OPTIMIZER_DATASETS,
  OPTIMIZER_METRICS,
  optimizerDatasetLabel,
  optimizerMetricLabel,
  compareOptimizerMetricValues,
  openArtifactText,
  procedureIdFromTaskTarget,
  procedureRunMatchesTask,
  procedureToOptimizerRunView,
  PROCEDURE_CREATE_SUBSCRIPTION_FOR_CARDS,
  PROCEDURE_DELETE_SUBSCRIPTION_FOR_CARDS,
  PROCEDURE_UPDATE_SUBSCRIPTION_FOR_CARDS,
  refreshOptimizerRunManifest,
  scorecardGuideRelativePath,
  scoreVersionUrl,
  TASK_CREATE_SUBSCRIPTION_FOR_CARDS,
  TASK_STAGE_CREATE_SUBSCRIPTION_FOR_CARDS,
  TASK_STAGE_UPDATE_SUBSCRIPTION_FOR_CARDS,
  TASK_UPDATE_SUBSCRIPTION_FOR_CARDS,
  type OptimizerDatasetKey,
  type OptimizerMetricKey,
  type OptimizerRunView,
} from '@/components/ui/optimizer-results-utils'

type ProcedureScope = 'score' | 'version'
type ProcedureSort =
  | 'updated'
  | 'status'
  | 'cycles'
  | `${OptimizerDatasetKey}_${OptimizerMetricKey}`

const getAmplifyClient = (() => {
  let client: any = null
  return () => (client ??= generateClient())
})()

export interface ScoreProcedureListProps {
  scoreId: string
  scorecardId?: string | null
  scoreName: string
  scorecardName: string
  scope: ProcedureScope
  versionId?: string | null
  showHeader?: boolean
  surface?: 'plain' | 'slot'
  className?: string
}

function sortProcedureRuns(runs: OptimizerRunView[], sortBy: ProcedureSort) {
  const updatedAtMs = (run: OptimizerRunView) => new Date(run.updatedAt ?? 0).getTime()
  const completedCycles = (run: OptimizerRunView) => run.manifest?.summary?.completed_cycles ?? -1

  return [...runs].sort((left, right) => {
    if (sortBy === 'status') {
      const statusCompare = String(left.status ?? '').localeCompare(String(right.status ?? ''))
      return statusCompare !== 0 ? statusCompare : updatedAtMs(right) - updatedAtMs(left)
    }
    if (sortBy === 'cycles') {
      const delta = completedCycles(right) - completedCycles(left)
      return delta !== 0 ? delta : updatedAtMs(right) - updatedAtMs(left)
    }
    const [dataset, metric] = sortBy.split('_') as [OptimizerDatasetKey, OptimizerMetricKey]
    if (OPTIMIZER_DATASETS.includes(dataset) && OPTIMIZER_METRICS.includes(metric)) {
      const leftBest = findBestOptimizerEvaluation(left.manifest, dataset, metric)?.value ?? null
      const rightBest = findBestOptimizerEvaluation(right.manifest, dataset, metric)?.value ?? null
      const metricCompare = compareOptimizerMetricValues(metric, leftBest, rightBest)
      return metricCompare !== 0 ? metricCompare : updatedAtMs(right) - updatedAtMs(left)
    }
    return updatedAtMs(right) - updatedAtMs(left)
  })
}

function toProcedureTaskData(
  run: OptimizerRunView,
  scorecardName: string,
  scoreName: string
): ProcedureTaskData {
  const summary = run.manifest?.summary
  const best = run.manifest?.best
  const operationalSummary = [
    summary?.completed_cycles != null || summary?.configured_max_iterations != null
      ? `Cycles: ${summary?.completed_cycles ?? '—'}/${summary?.configured_max_iterations ?? '—'}`
      : null,
    summary?.stop_reason ? `Stop: ${summary.stop_reason}` : null,
    best?.winning_version_id ? `Winning: ${best.winning_version_id}` : null,
  ].filter(Boolean)

  return {
    id: run.procedureId,
    title: run.name || run.procedureId,
    featured: false,
    createdAt: run.updatedAt || new Date().toISOString(),
    updatedAt: run.updatedAt || new Date().toISOString(),
    status: run.task?.status || run.status || 'PENDING',
    scorecard: scorecardNameFromRun(scorecardName),
    score: scoreFromRun(scoreName),
    description: run.procedureDescription ?? undefined,
    taskId: run.procedureId,
    task: {
      id: run.task?.id || run.procedureId,
      type: run.task?.type || 'Procedure',
      status: run.task?.status || run.status || 'PENDING',
      target: run.task?.target || run.procedureId,
      command: run.task?.command || '',
      description: operationalSummary.join(' · '),
      dispatchStatus: run.task?.dispatchStatus || undefined,
      celeryTaskId: run.task?.celeryTaskId || undefined,
      workerNodeId: run.task?.workerNodeId || undefined,
      metadata: run.task?.metadata,
      createdAt: run.task?.createdAt || run.updatedAt || new Date().toISOString(),
      startedAt: run.task?.startedAt || undefined,
      completedAt: run.task?.completedAt || undefined,
      estimatedCompletionAt: run.task?.estimatedCompletionAt || undefined,
      errorMessage: run.task?.errorMessage || undefined,
      errorDetails: run.task?.errorDetails,
      currentStageId: run.task?.currentStageId || undefined,
      stages: {
        items:
          run.task?.stages?.items?.map((stage) => ({
            id: stage.id,
            name: stage.name,
            order: stage.order,
            status: stage.status,
            statusMessage: stage.statusMessage ?? undefined,
            startedAt: stage.startedAt ?? undefined,
            completedAt: stage.completedAt ?? undefined,
            estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
            processedItems: stage.processedItems ?? undefined,
            totalItems: stage.totalItems ?? undefined,
          })) ?? [],
      },
    },
    feedbackEvaluationSummary: run.feedbackEvaluationSummary ?? null,
  }
}

function scorecardNameFromRun(scorecardName: string) {
  return scorecardName ? { id: '', name: scorecardName } : null
}

function scoreFromRun(scoreName: string) {
  return scoreName ? { id: '', name: scoreName } : null
}

function ProcedureListSkeleton() {
  return (
    <div className="space-y-3" aria-label="Loading procedures">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="rounded-lg bg-card p-4">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div className="space-y-2">
              <div className="h-4 w-48 rounded bg-muted animate-pulse" />
              <div className="h-3 w-64 rounded bg-muted animate-pulse" />
            </div>
            <div className="h-8 w-8 rounded bg-muted animate-pulse" />
          </div>
          <div className="space-y-2">
            <div className="h-3 w-full rounded bg-muted animate-pulse" />
            <div className="h-3 w-2/3 rounded bg-muted animate-pulse" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function ScoreProcedureList({
  scoreId,
  scorecardId = null,
  scoreName,
  scorecardName,
  scope,
  versionId = null,
  showHeader = true,
  surface = 'plain',
  className,
}: ScoreProcedureListProps) {
  const [runs, setRuns] = React.useState<OptimizerRunView[]>([])
  const [isLoading, setIsLoading] = React.useState(false)
  const [isApplyingControls, setIsApplyingControls] = React.useState(false)
  const [artifactViewer, setArtifactViewer] = React.useState<{
    title: string
    content: string
  } | null>(null)
  const [bestEvaluationDialog, setBestEvaluationDialog] = React.useState<{
    run: OptimizerRunView
  } | null>(null)
  const [bestEvaluationDataset, setBestEvaluationDataset] = React.useState<OptimizerDatasetKey>('feedback')
  const [bestEvaluationMetric, setBestEvaluationMetric] = React.useState<OptimizerMetricKey>('alignment')
  const [sortBy, setSortBy] = React.useState<ProcedureSort>('updated')
  const runsRef = React.useRef<OptimizerRunView[]>([])
  const manifestRefreshTimersRef = React.useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  React.useEffect(() => {
    runsRef.current = runs
  }, [runs])

  React.useEffect(
    () => () => {
      manifestRefreshTimersRef.current.forEach((timer) => clearTimeout(timer))
      manifestRefreshTimersRef.current.clear()
    },
    []
  )
  const metricSortOptions = React.useMemo(
    () =>
      OPTIMIZER_DATASETS.flatMap((dataset) =>
        OPTIMIZER_METRICS.map((metric) => ({
          value: `${dataset}_${metric}` as ProcedureSort,
          label: `Best ${optimizerDatasetLabel(dataset)} ${optimizerMetricLabel(metric)}`,
        }))
      ),
    []
  )

  React.useEffect(() => {
    let cancelled = false

    const loadRuns = async () => {
      setRuns([])
      setIsLoading(true)
      try {
        const loadedRuns = await loadOptimizerRuns(scoreId)
        const hydratedRuns = await hydrateProcedureRunsFeedbackEvaluations(loadedRuns)
        if (!cancelled) {
          setRuns(hydratedRuns)
        }
      } catch (error) {
        console.error('Failed to load procedures:', error)
        if (!cancelled) {
          toast.error('Failed to load procedures')
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    void loadRuns()
    return () => {
      cancelled = true
    }
  }, [scoreId])

  const scheduleManifestRefresh = React.useCallback((procedureId: string) => {
    const existingTimer = manifestRefreshTimersRef.current.get(procedureId)
    if (existingTimer) clearTimeout(existingTimer)

    const timer = setTimeout(() => {
      manifestRefreshTimersRef.current.delete(procedureId)
      const currentRun = runsRef.current.find((run) => run.procedureId === procedureId)
      if (!currentRun?.manifestKey) return
      void refreshOptimizerRunManifest(currentRun).then((refreshedRun) => {
        void hydrateProcedureRunFeedbackEvaluation(refreshedRun).then((hydratedRun) => {
          setRuns((previous) =>
            previous.map((run) => (run.procedureId === hydratedRun.procedureId ? hydratedRun : run))
          )
        })
      })
    }, 1500)

    manifestRefreshTimersRef.current.set(procedureId, timer)
  }, [])

  React.useEffect(() => {
    if (!scoreId) return

    const subscriptions: Array<{ unsubscribe: () => void }> = []
    const subscribe = (query: string, onNext: (data: any) => void, label: string) => {
      try {
        const result = getAmplifyClient().graphql({ query }) as any
        if (!result || typeof result.subscribe !== 'function') return
        const subscription = result.subscribe({
          next: ({ data }: { data?: any }) => onNext(data),
          error: (error: Error) => {
            console.error(`${label} subscription error:`, error)
          },
        })
        subscriptions.push(subscription)
      } catch (error) {
        console.error(`Failed to set up ${label} subscription:`, error)
      }
    }

    const upsertProcedure = (rawProcedure: any) => {
      if (!rawProcedure?.id) return
      if (rawProcedure.scoreId && rawProcedure.scoreId !== scoreId) return
      void procedureToOptimizerRunView(rawProcedure, null).then((nextRun) => {
        setRuns((previous) => {
          const existingIndex = previous.findIndex((run) => run.procedureId === nextRun.procedureId)
          if (existingIndex < 0) return [nextRun, ...previous]
          const next = [...previous]
          next[existingIndex] = {
            ...previous[existingIndex],
            ...nextRun,
            task: previous[existingIndex].task ?? nextRun.task,
            feedbackEvaluationSummary: previous[existingIndex].feedbackEvaluationSummary ?? nextRun.feedbackEvaluationSummary,
          }
          return next
        })
        scheduleManifestRefresh(nextRun.procedureId)
      })
    }

    subscribe(
      PROCEDURE_CREATE_SUBSCRIPTION_FOR_CARDS,
      (data) => upsertProcedure(data?.onCreateProcedure),
      'create procedure'
    )
    subscribe(
      PROCEDURE_UPDATE_SUBSCRIPTION_FOR_CARDS,
      (data) => upsertProcedure(data?.onUpdateProcedure),
      'update procedure'
    )
    subscribe(
      PROCEDURE_DELETE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const deleted = data?.onDeleteProcedure
        if (!deleted?.id) return
        if (deleted.scoreId && deleted.scoreId !== scoreId) return
        setRuns((previous) => previous.filter((run) => run.procedureId !== deleted.id))
      },
      'delete procedure'
    )
    subscribe(
      EVALUATION_CREATE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const rawEvaluation = data?.onCreateEvaluation
        if (!rawEvaluation?.id) return
        if (rawEvaluation.scoreId && rawEvaluation.scoreId !== scoreId) return
        const evaluation = evaluationToScoreEvaluationView(rawEvaluation)
        setRuns((previous) => previous.map((run) => mergeFeedbackEvaluationIntoProcedureRun(run, evaluation)))
      },
      'create evaluation'
    )
    subscribe(
      EVALUATION_UPDATE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const rawEvaluation = data?.onUpdateEvaluation
        if (!rawEvaluation?.id) return
        if (rawEvaluation.scoreId && rawEvaluation.scoreId !== scoreId) return
        const evaluation = evaluationToScoreEvaluationView(rawEvaluation)
        setRuns((previous) => previous.map((run) => mergeFeedbackEvaluationIntoProcedureRun(run, evaluation)))
      },
      'update evaluation'
    )
    subscribe(
      EVALUATION_DELETE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const deleted = data?.onDeleteEvaluation
        if (!deleted?.id) return
        if (deleted.scoreId && deleted.scoreId !== scoreId) return
        setRuns((previous) =>
          previous.map((run) =>
            currentProcedureFeedbackEvaluationId(run.manifest) === deleted.id
              ? { ...run, feedbackEvaluationSummary: null }
              : run
          )
        )
      },
      'delete evaluation'
    )
    subscribe(
      TASK_CREATE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const task = data?.onCreateTask
        const procedureId = procedureIdFromTaskTarget(task?.target)
        if (!procedureId) return
        setRuns((previous) =>
          previous.map((run) =>
            procedureRunMatchesTask(run, task) ? mergeTaskIntoProcedureRun(run, task) : run
          )
        )
        scheduleManifestRefresh(procedureId)
      },
      'task create'
    )
    subscribe(
      TASK_UPDATE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const task = data?.onUpdateTask
        const procedureId = procedureIdFromTaskTarget(task?.target)
        if (!procedureId) return
        setRuns((previous) =>
          previous.map((run) =>
            procedureRunMatchesTask(run, task) ? mergeTaskIntoProcedureRun(run, task) : run
          )
        )
        scheduleManifestRefresh(procedureId)
      },
      'task update'
    )
    subscribe(
      TASK_STAGE_CREATE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const stage = data?.onCreateTaskStage
        if (!stage?.taskId) return
        let touchedProcedureId: string | null = null
        setRuns((previous) =>
          previous.map((run) => {
            if (run.task?.id !== stage.taskId) return run
            touchedProcedureId = run.procedureId
            return mergeTaskStageIntoProcedureRun(run, stage)
          })
        )
        if (touchedProcedureId) scheduleManifestRefresh(touchedProcedureId)
      },
      'task stage create'
    )
    subscribe(
      TASK_STAGE_UPDATE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const stage = data?.onUpdateTaskStage
        if (!stage?.taskId) return
        let touchedProcedureId: string | null = null
        setRuns((previous) =>
          previous.map((run) => {
            if (run.task?.id !== stage.taskId) return run
            touchedProcedureId = run.procedureId
            return mergeTaskStageIntoProcedureRun(run, stage)
          })
        )
        if (touchedProcedureId) scheduleManifestRefresh(touchedProcedureId)
      },
      'task stage update'
    )

    return () => {
      subscriptions.forEach((subscription) => {
        try {
          subscription.unsubscribe()
        } catch {
          // Ignore unsubscribe errors from already-closed observables.
        }
      })
    }
  }, [scheduleManifestRefresh, scoreId])

  const applySort = React.useCallback((nextSort: ProcedureSort) => {
    setIsApplyingControls(true)
    setSortBy(nextSort)
    requestAnimationFrame(() => {
      setIsApplyingControls(false)
    })
  }, [])

  const visibleRuns = React.useMemo(() => {
    const filtered = scope === 'version' && versionId
      ? runs.filter((run) => {
          if (manifestTouchesVersion(run.manifest, versionId)) return true
          if (run.scoreVersionId === versionId) return true
          if (run.metadataText?.includes(versionId)) return true
          return false
        })
      : runs
    return sortProcedureRuns(filtered, sortBy)
  }, [runs, scope, sortBy, versionId])

  const title = scope === 'score' ? 'Procedures' : 'Version Procedures'
  const description =
    scope === 'score'
      ? 'All procedures for this score, newest first by default.'
      : 'Procedures that touched the selected version.'
  const usesSlotSurface = surface === 'slot'
  const shouldShowListSkeleton = isLoading || isApplyingControls

  const openArtifactViewer = React.useCallback(async (artifactKey: string | null | undefined, title: string) => {
    if (!artifactKey) {
      toast.error(`${title} is not available for this run`)
      return
    }
    try {
      const content = await openArtifactText(artifactKey)
      setArtifactViewer({ title, content })
    } catch (error) {
      console.error(`Failed to load ${title}:`, error)
      toast.error(`Failed to load ${title}`)
    }
  }, [])

  const selectedBestEvaluation = React.useMemo(
    () =>
      bestEvaluationDialog
        ? findBestOptimizerEvaluation(bestEvaluationDialog.run.manifest, bestEvaluationDataset, bestEvaluationMetric)
        : null,
    [bestEvaluationDataset, bestEvaluationDialog, bestEvaluationMetric]
  )

  if (scope === 'version' && !versionId) {
    return (
      <div className={cn('h-full min-h-0 rounded-md bg-muted/50 p-4', className)}>
        <div className="text-sm text-muted-foreground">Select a version to inspect its procedures.</div>
      </div>
    )
  }

  return (
    <div className={cn('flex h-full min-h-0 flex-col', className)}>
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className={cn(usesSlotSurface ? 'h-full' : 'px-4 pb-4')}>
        <div className={cn(usesSlotSurface && 'min-h-full bg-background p-3')}>
        {showHeader && (
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold">{title}</h3>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>
            {isLoading && <span className="text-sm text-muted-foreground">Loading…</span>}
          </div>
        )}

        <div className="mb-4 flex items-center gap-3">
          <label className="text-sm text-muted-foreground" htmlFor={`procedure-sort-${scope}`}>
            Sort
          </label>
          <select
            id={`procedure-sort-${scope}`}
            className="rounded-md border-0 bg-background px-3 py-1.5 text-sm focus:outline-none"
            value={sortBy}
            onChange={(event) => applySort(event.target.value as ProcedureSort)}
          >
            <option value="updated">Updated</option>
            <option value="status">Status</option>
            <option value="cycles">Completed cycles</option>
            {metricSortOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {shouldShowListSkeleton ? (
          <ProcedureListSkeleton />
        ) : (
        <div className="space-y-3">
          {!isLoading && visibleRuns.length === 0 && (
            <div className="text-sm text-muted-foreground">No procedures found for this scope yet.</div>
          )}
          {visibleRuns.map((run, index) => {
            const summary = run.manifest?.summary
            const best = run.manifest?.best
            const winningVersionId = best?.winning_version_id ?? null
            const hasMetricEvaluations = OPTIMIZER_DATASETS.some((dataset) =>
              OPTIMIZER_METRICS.some((metric) => findBestOptimizerEvaluation(run.manifest, dataset, metric))
            )

            return (
              <div
                key={run.procedureId}
                className={!usesSlotSurface && index % 2 !== 0 ? 'bg-muted/60' : ''}
              >
                <ProcedureTask
                  variant="grid"
                  procedure={toProcedureTaskData(run, scorecardName, scoreName)}
                  controlButtons={
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 rounded-md bg-border" aria-label="More options">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem asChild>
                          <a href={`/lab/procedures/${run.procedureId}`} target="_blank" rel="noreferrer">
                            <LinkIcon className="mr-2 h-3.5 w-3.5" />
                            Open procedure
                          </a>
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => void copyText(run.procedureId, 'Procedure ID copied')}>
                          <Copy className="mr-2 h-3.5 w-3.5" />
                          Copy procedure ID
                        </DropdownMenuItem>
                        {!run.indexed && (
                          <DropdownMenuItem
                            onSelect={() =>
                              void copyText(
                                `plexus procedure index-optimizer-run ${run.procedureId}`,
                                'Index command copied'
                              )
                            }
                          >
                            <Copy className="mr-2 h-3.5 w-3.5" />
                            Copy index command
                          </DropdownMenuItem>
                        )}
                        {winningVersionId && (
                          <DropdownMenuItem
                            onSelect={() =>
                              void copyText(
                                JSON.stringify(
                                  {
                                    score: scoreName,
                                    version_id: winningVersionId,
                                    feedback_evaluation_url: evaluationUrl(best?.best_feedback_evaluation_id),
                                    regression_evaluation_url: evaluationUrl(best?.best_accuracy_evaluation_id),
                                    guidelines_relative_path: scorecardGuideRelativePath(scorecardName, scoreName),
                                  },
                                  null,
                                  2
                                ),
                                'Promotion packet copied'
                              )
                            }
                          >
                            <Copy className="mr-2 h-3.5 w-3.5" />
                            Copy promotion packet
                          </DropdownMenuItem>
                        )}
                        {run.artifactPointer?.runtime_log && (
                          <DropdownMenuItem onSelect={() => void openArtifactViewer(run.artifactPointer?.runtime_log, 'Runtime log')}>
                            Runtime log
                          </DropdownMenuItem>
                        )}
                        {run.artifactPointer?.events && (
                          <DropdownMenuItem onSelect={() => void openArtifactViewer(run.artifactPointer?.events, 'Event stream')}>
                            Event stream
                          </DropdownMenuItem>
                        )}
                        {hasMetricEvaluations && (
                          <DropdownMenuItem
                            onSelect={() => {
                              setBestEvaluationDataset('feedback')
                              setBestEvaluationMetric('alignment')
                              setBestEvaluationDialog({ run })
                            }}
                          >
                            <LinkIcon className="mr-2 h-3.5 w-3.5" />
                            Find best evaluation…
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  }
                />
              </div>
            )
          })}
        </div>
        )}
        </div>
        </div>
      </div>

      <Dialog open={Boolean(artifactViewer)} onOpenChange={(open) => !open && setArtifactViewer(null)}>
        <DialogContent className="max-w-5xl max-h-[80vh] overflow-hidden">
          <DialogHeader>
            <DialogTitle>{artifactViewer?.title ?? 'Artifact'}</DialogTitle>
          </DialogHeader>
          <div className="overflow-auto rounded-md bg-muted/50 p-3">
            <pre className="whitespace-pre-wrap break-words text-xs leading-5">
              {artifactViewer?.content ?? ''}
            </pre>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(bestEvaluationDialog)} onOpenChange={(open) => !open && setBestEvaluationDialog(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Find Best Evaluation</DialogTitle>
            <DialogDescription>
              Choose the optimizer dataset and metric to open the stored best evaluation or version for this procedure.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm text-muted-foreground" htmlFor={`best-evaluation-dataset-${scope}`}>
                  Dataset
                </label>
                <select
                  id={`best-evaluation-dataset-${scope}`}
                  className="w-full rounded-md border-0 bg-background px-3 py-2 text-sm focus:outline-none"
                  value={bestEvaluationDataset}
                  onChange={(event) => setBestEvaluationDataset(event.target.value as OptimizerDatasetKey)}
                >
                  {OPTIMIZER_DATASETS.map((dataset) => (
                    <option key={dataset} value={dataset}>
                      {optimizerDatasetLabel(dataset)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm text-muted-foreground" htmlFor={`best-evaluation-metric-${scope}`}>
                  Metric
                </label>
                <select
                  id={`best-evaluation-metric-${scope}`}
                  className="w-full rounded-md border-0 bg-background px-3 py-2 text-sm focus:outline-none"
                  value={bestEvaluationMetric}
                  onChange={(event) => setBestEvaluationMetric(event.target.value as OptimizerMetricKey)}
                >
                  {OPTIMIZER_METRICS.map((metric) => (
                    <option key={metric} value={metric}>
                      {optimizerMetricLabel(metric)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="rounded-md bg-muted/50 p-3 text-sm">
              {selectedBestEvaluation ? (
                <div className="space-y-1">
                  <div>
                    Best {optimizerDatasetLabel(bestEvaluationDataset)} {optimizerMetricLabel(bestEvaluationMetric)}:{' '}
                    <span className="font-medium tabular-nums">{selectedBestEvaluation.value.toFixed(4)}</span>
                  </div>
                  <div className="text-muted-foreground">Evaluation: {selectedBestEvaluation.evaluationId}</div>
                  <div className="text-muted-foreground">Version: {selectedBestEvaluation.versionId ?? 'not available'}</div>
                </div>
              ) : (
                <div className="text-muted-foreground">
                  No stored optimizer evaluation was found for that dataset and metric.
                </div>
              )}
            </div>
          </div>

          <DialogFooter className="gap-2 sm:justify-between">
            <Button variant="ghost" onClick={() => setBestEvaluationDialog(null)}>
              Close
            </Button>
            <div className="flex gap-2">
              {selectedBestEvaluation?.versionId && scorecardId && (
                <Button variant="secondary" asChild>
                  <a
                    href={scoreVersionUrl(scorecardId, scoreId, selectedBestEvaluation.versionId) ?? '#'}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open version
                  </a>
                </Button>
              )}
              {selectedBestEvaluation && (
                <Button asChild>
                  <a href={evaluationUrl(selectedBestEvaluation.evaluationId) ?? '#'} target="_blank" rel="noreferrer">
                    Open evaluation
                  </a>
                </Button>
              )}
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
