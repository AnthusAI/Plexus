"use client"
import React from "react"
import { useState, useEffect, useMemo, useCallback, useRef } from "react"
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
import { AmplifyTask, ProcessedTask, Evaluation, TaskStageType, TaskSubscriptionEvent } from '@/utils/data-operations'
import { listRecentEvaluations, transformAmplifyTask as transformEvaluationData, standardizeScoreResults } from '@/utils/data-operations'
import { TaskDisplay } from "@/components/TaskDisplay"
import { getValueFromLazyLoader, unwrapLazyLoader } from '@/utils/data-operations'
import type { LazyLoader } from '@/utils/types'
import { observeRecentEvaluations, observeTaskUpdates, observeTaskStageUpdates } from '@/utils/subscriptions'
import { useEvaluationData } from '@/features/evaluations/hooks/useEvaluationData'
import { toast } from "sonner"

type TaskResponse = {
  items: Evaluation[]
  nextToken: string | null
}

type ScoreResultItem = {
  id: string;
  value: string | number;
  confidence: number | null;
  metadata: any;
  itemId: string | null;
};

interface TaskStagesResponse {
  data?: {
    items: TaskStageType[];
  };
}

interface ScoreResultsResponse {
  items?: ScoreResult[];
}

interface RawTask {
  id: string;
  type: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  target: string;
  command: string;
  description?: string;
  dispatchStatus?: string;
  metadata?: any;
  createdAt?: string;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  errorMessage?: string;
  errorDetails?: any;
  currentStageId?: string;
  stages?: {
    data?: {
      items: TaskStageType[];
    };
  };
  celeryTaskId?: string;
  workerNodeId?: string;
}

interface RawTaskData {
  data?: RawTask;
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
  console.debug('transformEvaluation input:', {
    evaluationId: evaluation?.id,
    hasTask: !!evaluation?.task,
    taskType: typeof evaluation?.task,
    taskData: evaluation?.task,
    taskKeys: evaluation?.task ? Object.keys(evaluation.task) : [],
    status: evaluation?.status,
    type: evaluation?.type
  });

  if (!evaluation) return null;

  // Unwrap the lazy loader and cast task data properly
  const rawTask = getValueFromLazyLoader(evaluation.task);
  // Cast through unknown first to avoid type overlap errors
  const taskData = ((rawTask ? rawTask : evaluation.task) as any) as AmplifyTask & { stages?: any };
  if (!taskData) {
    console.debug('No task data found in evaluation:', {
      evaluationId: evaluation.id,
      status: evaluation.status,
      type: evaluation.type
    });
  }

  // Get the score results
  const scoreResults = evaluation.scoreResults as unknown as {
    items?: Array<{
      id: string;
      value: string | number;
      confidence: number | null;
      metadata: any;
      itemId: string | null;
    }>;
  } | null;

  // Helper function to transform stages
  const transformStages = (stages: any): { items: TaskStageType[] } | undefined => {
    if (!stages) return undefined;

    // Get the items array from either format
    const stageItems = (stages.data && Array.isArray(stages.data.items)) ? stages.data.items : 
                      (Array.isArray(stages.items) ? stages.items : []);

    // Transform the stages without an extra nesting level
    return {
      items: stageItems.map((stage: any) => ({
        id: stage.id,
        name: stage.name,
        order: stage.order,
        status: stage.status,
        processedItems: stage.processedItems,
        totalItems: stage.totalItems,
        startedAt: stage.startedAt,
        completedAt: stage.completedAt,
        estimatedCompletionAt: stage.estimatedCompletionAt,
        statusMessage: stage.statusMessage
      }))
    };
  };

  // Get stages from task data
  const rawStages = taskData?.stages;
  const transformedStages = transformStages(rawStages);

  console.debug('Processing evaluation data:', {
    evaluationId: evaluation.id,
    hasTaskData: !!taskData,
    taskType: typeof taskData,
    taskKeys: taskData ? Object.keys(taskData) : [],
    hasScoreResults: !!scoreResults?.items?.length,
    rawStages,
    transformedStages
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
    task: taskData ? ({
      ...taskData,
      stages: transformedStages
    } as AmplifyTask) : null,
    scoreResults: scoreResults
  };

  console.debug('Final transformed evaluation:', {
    evaluationId: transformedEvaluation.id,
    hasTask: !!transformedEvaluation.task,
    taskType: typeof transformedEvaluation.task,
    taskKeys: transformedEvaluation.task ? Object.keys(transformedEvaluation.task) : [],
    taskStages: transformedEvaluation.task?.stages
  });

  return transformedEvaluation;
}

export default function EvaluationsDashboard() {
  const { user } = useAuthenticator()
  const router = useRouter()
  const [accountId, setAccountId] = useState<string | null>(null)
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<string | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [accountError, setAccountError] = useState<string | null>(null)
  const isNarrowViewport = useMediaQuery("(max-width: 768px)")
  const { ref, inView } = useInView({
    threshold: 0,
  })
  const [selectedScoreResultId, setSelectedScoreResultId] = useState<string | null>(null)

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
          setAccountError('No account found')
        }
      } catch (error) {
        console.error('Error fetching account:', error)
        setAccountError('Error fetching account')
      }
    }
    fetchAccountId()
  }, [])

  // Use the new hook for evaluation data
  const { evaluations, isLoading, error } = useEvaluationData({ accountId });

  // Combine errors from account fetching and evaluation data
  const combinedError = accountError || error;

  const handleDelete = async (evaluationId: string) => {
    try {
      const currentClient = getClient()
      await currentClient.graphql({
        query: `
          mutation DeleteEvaluation($input: DeleteEvaluationInput!) {
            deleteEvaluation(input: $input) {
              id
            }
          }
        `,
        variables: { 
          input: {
            id: evaluationId
          }
        }
      })
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
    const evaluation = evaluations.find((e: { id: string }) => e.id === selectedEvaluationId)
    if (!evaluation) return null

    console.log('Rendering selected task:', {
      evaluationId: evaluation.id,
      hasScoreResults: !!evaluation.scoreResults,
      scoreResultsType: typeof evaluation.scoreResults,
      scoreResultsIsArray: Array.isArray(evaluation.scoreResults),
      scoreResultsCount: Array.isArray(evaluation.scoreResults) ? evaluation.scoreResults.length : 
                        (evaluation.scoreResults && typeof evaluation.scoreResults === 'object' && 'items' in evaluation.scoreResults ? 
                         (evaluation.scoreResults as any).items.length : 0),
      firstScoreResult: Array.isArray(evaluation.scoreResults) ? evaluation.scoreResults[0] : 
                       (evaluation.scoreResults && typeof evaluation.scoreResults === 'object' && 'items' in evaluation.scoreResults ? 
                        (evaluation.scoreResults as any).items[0] : undefined)
    });

    return (
      <TaskDisplay
        variant="detail"
        task={evaluation.task}
        evaluationData={{
          ...evaluation,
          // Pass the raw score results - they will be standardized in the components
          scoreResults: evaluation.scoreResults
        }}
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
              <DropdownMenuItem onClick={copyLinkToClipboard}>
                <Eye className="mr-2 h-4 w-4" />
                Share
              </DropdownMenuItem>
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
        selectedScoreResultId={selectedScoreResultId}
        onSelectScoreResult={(id) => setSelectedScoreResultId(id)}
      />
    )
  }

  // Add filtering logic for evaluations based on selected scorecard and score
  const filteredEvaluations = useMemo(() => {
    return evaluations.filter((evaluation: any) => {
      if (!selectedScorecard && !selectedScore) return true;
      if (selectedScorecard && evaluation.scorecard?.name !== selectedScorecard) return false;
      if (selectedScore && evaluation.score?.name !== selectedScore) return false;
      return true;
    });
  }, [evaluations, selectedScorecard, selectedScore]);

  // Add this handler
  const handleScoreResultSelect = useCallback((id: string | null) => {
    setSelectedScoreResultId(id);
  }, []);

  const copyLinkToClipboard = () => {
    navigator.clipboard.writeText(window.location.href + '/' + selectedEvaluationId).then(
      () => {
        toast.success("Link copied to clipboard", {
          description: "You can now share this evaluation with others"
        });
      },
      () => {
        toast.error("Failed to copy link", {
          description: "Please try again"
        });
      }
    );
  };

  interface EvaluationsGridProps {
    evaluations: Evaluation[];
    selectedEvaluationId: string | null;
    setSelectedEvaluationId: (id: string | null) => void;
    isNarrowViewport: boolean;
    setIsFullWidth: (isFullWidth: boolean) => void;
    selectedScoreResultId: string | null;
    onSelectScoreResult: (id: string | null) => void;
  }

  const EvaluationsGrid: React.FC<EvaluationsGridProps> = React.memo(({ 
    evaluations, 
    selectedEvaluationId, 
    setSelectedEvaluationId, 
    isNarrowViewport, 
    setIsFullWidth,
    selectedScoreResultId,
    onSelectScoreResult
  }) => {
    return (
      <div className={`
        grid gap-3
        ${selectedEvaluationId && !isNarrowViewport && !isFullWidth ? 'grid-cols-1' : 'grid-cols-1 @[640px]:grid-cols-2'}
      `}>
        {evaluations.map((evaluation) => (
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
              selectedScoreResultId={selectedScoreResultId}
              onSelectScoreResult={onSelectScoreResult}
            />
          </div>
        ))}
      </div>
    );
  }, (prevProps, nextProps) => {
    // Custom comparison to prevent unnecessary re-renders
    return (
      prevProps.evaluations === nextProps.evaluations &&
      prevProps.selectedEvaluationId === nextProps.selectedEvaluationId &&
      prevProps.isNarrowViewport === nextProps.isNarrowViewport &&
      prevProps.selectedScoreResultId === nextProps.selectedScoreResultId
    );
  });

  if (isLoading) {
    return (
      <div>
        <div className="mb-4 text-sm text-muted-foreground">
          {combinedError ? `Error: ${combinedError}` : 'Loading evaluations...'}
        </div>
        <EvaluationDashboardSkeleton />
      </div>
    )
  }

  if (combinedError) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">Evaluations</h1>
        </div>
        <div className="text-sm text-destructive">Error: {combinedError}</div>
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
              {filteredEvaluations.map((evaluation: any) => {
                return (
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
                      evaluationData={{
                        ...evaluation,
                        // Pass the raw score results - they will be standardized in the components
                        scoreResults: evaluation.scoreResults
                      }}
                      isSelected={evaluation.id === selectedEvaluationId}
                      onClick={() => {
                        setSelectedEvaluationId(evaluation.id)
                        if (isNarrowViewport) {
                          setIsFullWidth(true)
                        }
                      }}
                      extra={true}
                      selectedScoreResultId={selectedScoreResultId}
                      onSelectScoreResult={handleScoreResultSelect}
                    />
                  </div>
                );
              })}
              <div ref={ref} className="h-4" />
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

// Add the ScoreResult type
interface ScoreResult {
  id: string;
  value: string | number;
  confidence: number | null;
  metadata: any;
  itemId: string | null;
}

// Add TaskStageSubscriptionEvent type
type TaskStageSubscriptionEvent = {
  type: 'create' | 'update';
  data: {
    stageId?: string;
    taskId?: string;
    name?: string;
    status?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
    processedItems?: number;
    totalItems?: number;
    startedAt?: string;
    completedAt?: string;
    estimatedCompletionAt?: string;
    statusMessage?: string;
  } | null;
};

// Update the merge functions to properly handle the LazyLoader type
function mergeTaskUpdate(evaluations: Evaluation[], taskData: TaskSubscriptionEvent['data']): Evaluation[] {
  if (!evaluations || !taskData) {
    console.warn('mergeTaskUpdate called with invalid data:', { hasEvaluations: !!evaluations, hasTaskData: !!taskData });
    return evaluations || [];
  }

  return evaluations.map(evaluation => {
    // Skip if evaluation is null or doesn't have a task
    if (!evaluation?.task) {
      return evaluation;
    }

    const task = getValueFromLazyLoader(evaluation.task);
    if (!task?.id || !taskData?.id || task.id !== taskData.id) {
      return evaluation;
    }

    // Create updated task with new data, preserving all existing fields
    const updatedTask = {
      ...task,
      status: taskData.status,
      startedAt: taskData.startedAt,
      completedAt: taskData.completedAt,
      stages: taskData.stages
    };

    // Return updated evaluation while preserving all other fields
    return {
      ...evaluation,
      task: updatedTask as AmplifyTask,
      // Explicitly preserve score results
      scoreResults: evaluation.scoreResults
    };
  });
}

function mergeTaskStageUpdate(
  evaluations: Evaluation[], 
  stageData: TaskStageType,
  taskId: string
): Evaluation[] {
  if (!evaluations || !stageData || !taskId) {
    console.warn('mergeTaskStageUpdate called with invalid data:', { 
      hasEvaluations: !!evaluations, 
      hasStageData: !!stageData,
      taskId 
    });
    return evaluations || [];
  }

  return evaluations.map(evaluation => {
    // Skip if evaluation is null or doesn't have a task
    if (!evaluation?.task) {
      return evaluation;
    }

    const task = getValueFromLazyLoader(evaluation.task);
    // Check if this is the task we're looking for
    if (!task || task.id !== taskId) {
      return evaluation;
    }

    const stages = getValueFromLazyLoader(task.stages);
    if (!stages?.data?.items) {
      // If no stages exist yet, create new stages array
      const updatedStages = {
        data: {
          items: [stageData]
        }
      };

      const updatedTask = {
        ...task,
        stages: updatedStages
      };

      // Return updated evaluation while preserving all other fields
      return {
        ...evaluation,
        task: updatedTask as AmplifyTask,
        // Explicitly preserve score results
        scoreResults: evaluation.scoreResults
      };
    }

    // Find if this stage already exists
    const stageIndex = stages.data.items.findIndex(
      (stage: TaskStageType) => stage?.id === stageData.id || stage?.name === stageData.name
    );

    const updatedStages = {
      data: {
        items: stageIndex === -1 
          ? [...stages.data.items, stageData] // Add new stage
          : stages.data.items.map((stage: TaskStageType, index: number) => // Update existing stage
              index === stageIndex ? { ...stage, ...stageData } : stage
            )
      }
    };

    // Create updated task with new stages
    const updatedTask = {
      ...task,
      stages: updatedStages
    };

    // Return updated evaluation while preserving all other fields
    return {
      ...evaluation,
      task: updatedTask as AmplifyTask,
      // Explicitly preserve score results
      scoreResults: evaluation.scoreResults
    };
  });
}
