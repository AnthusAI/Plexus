"use client"
import React, { useMemo, useCallback, useRef } from "react"
import { useState, useEffect } from "react"
import { useInView } from 'react-intersection-observer'
import type { Schema } from "@/amplify/data/resource"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, RectangleVertical, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown, Trash2, MoreHorizontal, Eye, RefreshCw } from "lucide-react"
import { format, formatDistanceToNow, parseISO } from "date-fns"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { TimeRangeSelector } from "@/components/time-range-selector"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import ReactMarkdown from 'react-markdown'
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import Link from 'next/link'
import { FilterControl, FilterConfig } from "@/components/filter-control"
import { Progress } from "@/components/ui/progress"
import ScorecardContext from "@/components/ScorecardContext"
import { EvaluationDashboardSkeleton } from "@/components/loading-skeleton"
import { ModelListResult, AmplifyListResult, AmplifyGetResult } from '@/types/shared'
import { listFromModel, observeQueryFromModel, getFromModel, observeScoreResults } from "@/utils/amplify-helpers"
import { useAuthenticator } from '@aws-amplify/ui-react'
import { useRouter } from 'next/navigation'
import { Observable } from 'rxjs'
import { getClient } from '@/utils/amplify-client'
import type { GraphQLResult, GraphQLSubscription } from '@aws-amplify/api'
import { TaskDispatchButton, evaluationsConfig } from '@/components/task-dispatch'
import { EvaluationCard, EvaluationGrid } from '@/features/evaluations'
import { useEvaluationSubscriptions, useTaskUpdates } from '@/features/evaluations'
import { formatStatus, getBadgeVariant, calculateProgress } from '@/features/evaluations'
import EvaluationTask from '@/components/EvaluationTask'
import { useMediaQuery } from "@/hooks/use-media-query"
import { CardButton } from "@/components/CardButton"
import { GraphQLResult as APIGraphQLResult } from '@aws-amplify/api-graphql'
import type { EvaluationTaskProps } from '@/components/EvaluationTask'
import type { TaskData } from '@/types/evaluation'
import { transformAmplifyTask } from '@/utils/data-operations'
import type { AmplifyTask, ProcessedTask } from '@/utils/data-operations'
import { listRecentEvaluations, observeRecentEvaluations, transformAmplifyTask as transformEvaluationData } from '@/utils/data-operations'
import { TaskDisplay } from "@/components/TaskDisplay"
import { getValueFromLazyLoader, unwrapLazyLoader } from '@/utils/data-operations'

type Evaluation = {
  id: string
  type: string
  scorecard?: { name: string } | null
  score?: { name: string } | null
  createdAt: string
  metrics?: any
  metricsExplanation?: string | null
  accuracy?: number | null
  processedItems?: number | null
  totalItems?: number | null
  inferences?: number | null
  cost?: number | null
  status?: string | null
  elapsedSeconds?: number | null
  estimatedRemainingSeconds?: number | null
  startedAt?: string | null
  errorMessage?: string | null
  errorDetails?: any
  confusionMatrix?: any
  scoreGoal?: string | null
  datasetClassDistribution?: any
  isDatasetClassDistributionBalanced?: boolean | null
  predictedClassDistribution?: any
  isPredictedClassDistributionBalanced?: boolean | null
  task: AmplifyTask | null
  scoreResults?: {
    items?: Array<{
      id: string
      value: string | number
      confidence: number | null
      metadata: any
      itemId: string | null
    }>
  } | null
}

type TaskResponse = {
  items: Evaluation[]
  nextToken: string | null
}

const ACCOUNT_KEY = 'call-criteria'

const LIST_ACCOUNTS = `
  query ListAccounts($filter: ModelAccountFilterInput) {
    listAccounts(filter: $filter) {
      items {
        id
        key
      }
    }
  }
`

const LIST_EVALUATIONS = `
  query ListEvaluationByAccountIdAndUpdatedAt(
    $accountId: String!
    $sortDirection: ModelSortDirection
    $limit: Int
  ) {
    listEvaluationByAccountIdAndUpdatedAt(
      accountId: $accountId
      sortDirection: $sortDirection
      limit: $limit
    ) {
      items {
        id
        type
        parameters
        metrics
        metricsExplanation
        inferences
        accuracy
        cost
        createdAt
        updatedAt
        status
        startedAt
        elapsedSeconds
        estimatedRemainingSeconds
        totalItems
        processedItems
        errorMessage
        errorDetails
        accountId
        scorecardId
        scorecard {
          id
          name
        }
        scoreId
        score {
          id
          name
        }
        confusionMatrix
        scoreGoal
        datasetClassDistribution
        isDatasetClassDistributionBalanced
        predictedClassDistribution
        isPredictedClassDistributionBalanced
        taskId
        task {
          id
          type
          status
          target
          command
          description
          dispatchStatus
          metadata
          createdAt
          startedAt
          completedAt
          estimatedCompletionAt
          errorMessage
          errorDetails
          currentStageId
          stages {
            items {
              id
              name
              order
              status
              statusMessage
              startedAt
              completedAt
              estimatedCompletionAt
              processedItems
              totalItems
            }
          }
        }
        scoreResults {
          items {
            id
            value
            confidence
            metadata
            explanation
            itemId
            createdAt
          }
        }
      }
      nextToken
    }
  }
`

interface GraphQLError {
  message: string;
  path?: string[];
}

interface ListAccountResponse {
  listAccounts: {
    items: Array<{
      id: string;
      key: string;
    }>;
  };
}

interface ListEvaluationResponse {
  listEvaluationByAccountIdAndUpdatedAt: {
    items: Schema['Evaluation']['type'][];
    nextToken: string | null;
  };
}

export function transformEvaluation(evaluation: Schema['Evaluation']['type']) {
  if (!evaluation) return null;

  const rawTaskResponse = getValueFromLazyLoader(evaluation.task);
  const rawTask = rawTaskResponse?.data;
  const rawStages = getValueFromLazyLoader(rawTask?.stages);
  const task: AmplifyTask | null = rawTask ? {
    id: rawTask.id,
    command: rawTask.command,
    type: rawTask.type,
    status: rawTask.status,
    target: rawTask.target,
    stages: () => Promise.resolve({
      data: {
        items: (rawStages?.data || []).map(stage => ({
          id: stage.id,
          name: stage.name,
          order: stage.order,
          status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
          processedItems: stage.processedItems ?? undefined,
          totalItems: stage.totalItems ?? undefined,
          startedAt: stage.startedAt ?? undefined,
          completedAt: stage.completedAt ?? undefined,
          estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
          statusMessage: stage.statusMessage ?? undefined
        }))
      }
    })
  } : null;

  // Transform score results
  const rawScoreResultsResponse = getValueFromLazyLoader(evaluation.scoreResults);
  const rawScoreResults = rawScoreResultsResponse?.data;
  const scoreResults = rawScoreResults ? {
    items: rawScoreResults.map(result => {
      const metadata = typeof result.metadata === 'string' ? 
        JSON.parse(result.metadata) : result.metadata;
      return {
        id: result.id,
        value: result.value,
        confidence: result.confidence ?? null,
        metadata: metadata || {},
        itemId: result.itemId
      };
    })
  } : undefined;

  // Log the raw evaluation data for debugging
  console.log('Raw evaluation data:', {
    id: evaluation.id,
    metrics: evaluation.metrics,
    scoreResults: evaluation.scoreResults,
    task: task
  });

  // Transform the evaluation into the format expected by components
  const transformedEvaluation: Evaluation = {
    id: evaluation.id,
    type: evaluation.type,
    scorecard: evaluation.scorecard,
    score: evaluation.score,
    createdAt: evaluation.createdAt,
    metrics: typeof evaluation.metrics === 'string' ? 
      JSON.parse(evaluation.metrics) : evaluation.metrics,
    metricsExplanation: evaluation.metricsExplanation,
    accuracy: evaluation.accuracy,
    processedItems: evaluation.processedItems,
    totalItems: evaluation.totalItems,
    inferences: evaluation.inferences,
    cost: evaluation.cost,
    status: evaluation.status,
    elapsedSeconds: evaluation.elapsedSeconds,
    estimatedRemainingSeconds: evaluation.estimatedRemainingSeconds,
    startedAt: evaluation.startedAt,
    errorMessage: evaluation.errorMessage,
    errorDetails: evaluation.errorDetails,
    confusionMatrix: typeof evaluation.confusionMatrix === 'string' ? 
      JSON.parse(evaluation.confusionMatrix) : evaluation.confusionMatrix,
    datasetClassDistribution: typeof evaluation.datasetClassDistribution === 'string' ?
      JSON.parse(evaluation.datasetClassDistribution) : evaluation.datasetClassDistribution,
    isDatasetClassDistributionBalanced: evaluation.isDatasetClassDistributionBalanced,
    predictedClassDistribution: typeof evaluation.predictedClassDistribution === 'string' ?
      JSON.parse(evaluation.predictedClassDistribution) : evaluation.predictedClassDistribution,
    isPredictedClassDistributionBalanced: evaluation.isPredictedClassDistributionBalanced,
    task,
    scoreResults
  };

  // Log the transformed data for debugging
  console.log('Transformed evaluation:', transformedEvaluation);

  return transformedEvaluation;
}

export default function EvaluationsDashboard() {
  const { user } = useAuthenticator()
  const router = useRouter()
  const [accountId, setAccountId] = useState<string | null>(null)
  const [evaluations, setEvaluations] = useState<Evaluation[]>([])
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const isNarrowViewport = useMediaQuery("(max-width: 768px)")
  const { ref, inView } = useInView({
    threshold: 0,
  })
  const [processedTaskData, setProcessedTaskData] = useState<ProcessedTask | null>(null);

  // Fetch account ID
  useEffect(() => {
    const fetchAccountId = async () => {
      try {
        console.log('Fetching account ID...')
        const accountResponse = await getClient().graphql<ListAccountResponse>({
          query: LIST_ACCOUNTS,
          variables: {
            filter: { key: { eq: ACCOUNT_KEY } }
          }
        })

        if ('data' in accountResponse && accountResponse.data?.listAccounts?.items?.length) {
          const id = accountResponse.data.listAccounts.items[0].id
          console.log('Found account ID:', id)
          setAccountId(id)
        } else {
          console.warn('No account found with key:', ACCOUNT_KEY)
          setError('No account found')
          setIsLoading(false)
        }
      } catch (error) {
        console.error('Error fetching account:', error)
        setError('Error fetching account')
        setIsLoading(false)
      }
    }
    fetchAccountId()
  }, [])

  // Fetch evaluations
  useEffect(() => {
    if (!accountId) return

    console.log('Setting up real-time evaluations subscription');
    const subscription = observeRecentEvaluations(100).subscribe({
      next: async ({ items, isSynced }) => {
        console.log('Raw evaluations data:', {
          count: items.length,
          firstEvaluation: items[0] ? {
            id: items[0].id,
            type: items[0].type,
            metrics: items[0].metrics,
            accuracy: items[0].accuracy,
            scorecard: items[0].scorecard,
            score: items[0].score,
            task: items[0].task,
            scoreResults: items[0].scoreResults
          } : null
        });

        // Transform the items before setting state
        const transformedItems = await Promise.all(items.map(transformEvaluation));
        console.log('Transformed evaluations:', {
          count: transformedItems.length,
          firstEvaluation: transformedItems[0] ? {
            id: transformedItems[0].id,
            type: transformedItems[0].type,
            metrics: transformedItems[0].metrics,
            accuracy: transformedItems[0].accuracy,
            scorecard: transformedItems[0].scorecard,
            score: transformedItems[0].score,
            task: transformedItems[0].task,
            scoreResults: transformedItems[0].scoreResults
          } : null
        });

        const nonNullEvaluations = transformedItems.filter((item): item is Evaluation => item !== null);
        setEvaluations(nonNullEvaluations);
        if (isSynced) {
          setIsLoading(false);
        }
      },
      error: (error) => {
        console.error('Evaluations subscription error:', error);
        setError('Error fetching evaluations');
        setIsLoading(false);
      }
    });

    return () => {
      console.log('Cleaning up evaluations subscription');
      subscription.unsubscribe();
    };
  }, [accountId]);

  const handleDelete = async (evaluationId: string) => {
    try {
      const currentClient = getClient()
      await currentClient.graphql({
                query: `
          mutation DeleteEvaluation($id: ID!) {
            deleteEvaluation(id: $id) {
              id
            }
          }
        `,
        variables: { id: evaluationId }
      })
      setEvaluations(prev => prev.filter(evaluation => evaluation.id !== evaluationId))
      if (selectedEvaluationId === evaluationId) {
        setSelectedEvaluationId(null)
      }
      return true
            } catch (error) {
      console.error('Error deleting evaluation:', error)
      return false
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

  const renderSelectedTask = () => {
    if (!selectedEvaluationId) return null
    const evaluation = evaluations.find(e => e.id === selectedEvaluationId)
    if (!evaluation) return null

    console.log('Rendering task for evaluation:', {
      evaluationId: evaluation.id,
      evaluationData: {
        type: evaluation.type,
        metrics: evaluation.metrics,
        accuracy: evaluation.accuracy,
        scorecard: evaluation.scorecard,
        score: evaluation.score,
        task: evaluation.task,
        scoreResults: evaluation.scoreResults
      }
    });

    return (
      <TaskDisplay
        variant="detail"
        task={evaluation.task}
        evaluationData={evaluation}
        controlButtons={
          <DropdownMenu>
            <DropdownMenuTrigger>
              <CardButton
                icon={MoreHorizontal}
                onClick={() => {}}
                aria-label="More options"
              />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleDelete(evaluation.id)}>
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        }
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={() => {
          setSelectedEvaluationId(null)
          setIsFullWidth(false)
        }}
      />
    )
  }

  // Add filtering logic for evaluations based on selected scorecard and score
  const filteredEvaluations = useMemo(() => {
    return evaluations.filter(evaluation => {
      if (!selectedScorecard && !selectedScore) return true;
      if (selectedScorecard && evaluation.scorecard?.name !== selectedScorecard) return false;
      if (selectedScore && evaluation.score?.name !== selectedScore) return false;
      return true;
    });
  }, [evaluations, selectedScorecard, selectedScore]);

  if (isLoading) {
    return (
      <div>
        <div className="mb-4 text-sm text-muted-foreground">
          {error ? `Error: ${error}` : 'Loading evaluations...'}
        </div>
        <EvaluationDashboardSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">Evaluations</h1>
        </div>
        <div className="text-sm text-destructive">Error: {error}</div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full p-1.5">
      <div className="flex justify-between items-start mb-3">
        <ScorecardContext 
          selectedScorecard={selectedScorecard}
          setSelectedScorecard={setSelectedScorecard}
          selectedScore={selectedScore}
          setSelectedScore={setSelectedScore}
        />
        <TaskDispatchButton config={evaluationsConfig} />
      </div>
      
      <div className="flex h-full">
        <div 
          className={`
            ${selectedEvaluationId && !isNarrowViewport && !isFullWidth ? '' : 'w-full'}
            ${selectedEvaluationId && !isNarrowViewport && isFullWidth ? 'hidden' : ''}
            h-full overflow-y-auto overflow-x-hidden @container
          `}
          style={selectedEvaluationId && !isNarrowViewport && !isFullWidth ? {
            width: `${leftPanelWidth}%`
          } : undefined}
        >
          {filteredEvaluations.length === 0 ? (
            <div className="text-sm text-muted-foreground">No evaluations found</div>
          ) : (
            <div className={`
              grid gap-3
              ${selectedEvaluationId && !isNarrowViewport && !isFullWidth ? 'grid-cols-1' : 'grid-cols-1 @[640px]:grid-cols-2'}
            `}>
              {filteredEvaluations.map((evaluation) => (
                <div 
                  key={evaluation.id} 
                  onClick={() => {
                    setSelectedEvaluationId(evaluation.id)
                    if (isNarrowViewport) {
                      setIsFullWidth(true)
                    }
                  }}
                >
                  <TaskDisplay
                    variant="grid"
                    task={evaluation.task}
                    evaluationData={evaluation}
                    isSelected={evaluation.id === selectedEvaluationId}
                    onClick={() => {
                      setSelectedEvaluationId(evaluation.id)
                      if (isNarrowViewport) {
                        setIsFullWidth(true)
                      }
                    }}
                    extra={true}
                  />
                </div>
              ))}
              <div ref={ref} />
            </div>
          )}
        </div>

        {selectedEvaluationId && !isNarrowViewport && !isFullWidth && (
          <div
            className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
            onMouseDown={handleDragStart}
          >
            <div className="absolute inset-0 rounded-full transition-colors duration-150 
              group-hover:bg-accent" />
          </div>
        )}

        {selectedEvaluationId && !isNarrowViewport && !isFullWidth && (
          <div 
            className="h-full overflow-hidden"
            style={{ width: `${100 - leftPanelWidth}%` }}
          >
            {renderSelectedTask()}
          </div>
        )}

        {selectedEvaluationId && (isNarrowViewport || isFullWidth) && (
          <div className="fixed inset-0 z-50">
            {renderSelectedTask()}
          </div>
        )}
      </div>
    </div>
  )
}
