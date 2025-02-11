"use client"
import React, { useMemo, useCallback, useRef } from "react"
import { useState, useEffect } from "react"
import type { Schema } from "@/amplify/data/resource"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, RectangleVertical, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown, Trash2, MoreHorizontal, Eye } from "lucide-react"
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
import EvaluationTask, { type EvaluationTaskProps, type EvaluationTaskData as ImportedEvaluationTaskData } from "@/components/EvaluationTask"
import { EvaluationListAccuracyBar } from "@/components/EvaluationListAccuracyBar"
import { CardButton } from '@/components/CardButton'
import { formatDuration } from '@/utils/format-duration'
import { EvaluationDashboardSkeleton } from "@/components/loading-skeleton"
import { ModelListResult, AmplifyListResult, AmplifyGetResult } from '@/types/shared'
import { listFromModel, observeQueryFromModel, getFromModel, observeScoreResults } from "@/utils/amplify-helpers"
import { useAuthenticator } from '@aws-amplify/ui-react';
import { useRouter } from 'next/navigation';
import { Observable } from 'rxjs';
import { client, getClient } from "@/utils/amplify-client"  // Import both client and getClient
import { GraphQLResult } from '@aws-amplify/api';
import { TaskStatus } from '@/components/ui/task-status';
import { TaskDispatchButton, evaluationsConfig } from '@/components/task-dispatch'

const ACCOUNT_KEY = 'call-criteria'

const formatStatus = (status: string) => {
  return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
};

const getBadgeVariant = (status: string) => {
  const formattedStatus = status.toLowerCase();
  if (formattedStatus === 'done') {
    return 'bg-true text-primary-foreground';
  }
  return 'bg-neutral text-primary-foreground';
};

const calculateProgress = (processedItems?: number | null, totalItems?: number | null): number => {
  if (!processedItems || !totalItems || totalItems === 0) return 0;
  return Math.round((processedItems / totalItems) * 100);
};

// Add proper type for task data
interface TaskData {
  accountId: string;
  type: string;
  status: string;
  target: string;
  command: string;
  stages?: {
    items?: Array<{
      name: string;
      status: string;
      processedItems: number;
    }>;
  };
}

// Update the transformation logic to maintain all fields
const transformEvaluation = (rawEvaluation: any): Schema['Evaluation']['type'] => {
  if (!rawEvaluation) {
    throw new Error('Cannot transform null Evaluation');
  }

  // Create a strongly typed base object with ALL fields
  const safeEvaluation = {
    id: rawEvaluation.id || '',
    type: rawEvaluation.type || '',
    parameters: rawEvaluation.parameters || {},
    metrics: (() => {
      try {
        if (!rawEvaluation.metrics) return [];
        if (Array.isArray(rawEvaluation.metrics)) return rawEvaluation.metrics;
        if (typeof rawEvaluation.metrics === 'string') {
          const parsed = JSON.parse(rawEvaluation.metrics);
          return Array.isArray(parsed) ? parsed : [];
        }
        return [];
      } catch (e) {
        console.warn('Error parsing metrics:', e);
        return [];
      }
    })(),
    inferences: rawEvaluation.inferences || 0,
    cost: rawEvaluation.cost || 0,
    createdAt: rawEvaluation.createdAt || new Date().toISOString(),
    updatedAt: rawEvaluation.updatedAt || new Date().toISOString(),
    status: rawEvaluation.status || '',
    startedAt: rawEvaluation.startedAt || null,
    totalItems: rawEvaluation.totalItems || 0,
    processedItems: rawEvaluation.processedItems || 0,
    errorMessage: rawEvaluation.errorMessage || null,
    errorDetails: rawEvaluation.errorDetails || null,
    accountId: rawEvaluation.accountId || '',
    scorecardId: rawEvaluation.scorecardId || null,
    scoreId: rawEvaluation.scoreId || null,
    confusionMatrix: rawEvaluation.confusionMatrix || null,
    elapsedSeconds: rawEvaluation.elapsedSeconds || 0,
    estimatedRemainingSeconds: rawEvaluation.estimatedRemainingSeconds || 0,
    scoreGoal: rawEvaluation.scoreGoal || null,
    datasetClassDistribution: rawEvaluation.datasetClassDistribution || null,
    isDatasetClassDistributionBalanced: rawEvaluation.isDatasetClassDistributionBalanced ?? null,
    predictedClassDistribution: rawEvaluation.predictedClassDistribution || null,
    isPredictedClassDistributionBalanced: rawEvaluation.isPredictedClassDistributionBalanced || null,
    metricsExplanation: rawEvaluation.metricsExplanation || null,
    accuracy: typeof rawEvaluation.accuracy === 'number' ? rawEvaluation.accuracy : null,
    task: rawEvaluation.task ? {
      ...rawEvaluation.task,
      stages: rawEvaluation.task.stages ? {
        items: (rawEvaluation.task.stages.items || []).map((stage: any) => ({
          name: stage.name,
          status: stage.status,
          processedItems: stage.processedItems || 0,
          totalItems: stage.totalItems || 0,
          statusMessage: stage.statusMessage,
          estimatedCompletionAt: stage.estimatedCompletionAt,
          label: stage.label || stage.name,
          order: stage.order || 0,
          color: stage.color || 'bg-primary'
        }))
      } : { items: [] }
    } : null,
    items: async (options?: any) => ({ data: [], nextToken: null }),
    scoreResults: async (options?: any) => ({ data: [], nextToken: null }),
    scoringJobs: async (options?: any) => ({ data: [], nextToken: null }),
    resultTests: async (options?: any) => ({ data: [], nextToken: null }),
  };

  return {
    ...safeEvaluation,
    account: async () => ({
      data: {
        id: rawEvaluation.account?.id || '',
        name: rawEvaluation.account?.name || '',
        key: rawEvaluation.account?.key || '',
        scorecards: async () => ({ data: [], nextToken: null }),
        evaluations: async () => ({ data: [], nextToken: null }),
        batchJobs: async () => ({ data: [], nextToken: null }),
        items: async () => ({ data: [], nextToken: null }),
        scoringJobs: async () => ({ data: [], nextToken: null }),
        scoreResults: async () => ({ data: [], nextToken: null }),
        actions: async () => ({ data: [], nextToken: null }),
        tasks: async () => ({ data: [], nextToken: null }),
        createdAt: rawEvaluation.account?.createdAt || new Date().toISOString(),
        updatedAt: rawEvaluation.account?.updatedAt || new Date().toISOString(),
        description: rawEvaluation.account?.description || ''
      }
    }),
    scorecard: async () => {
      if (rawEvaluation.scorecard?.data) {
        return { data: rawEvaluation.scorecard.data };
      }
      return { data: null };
    },
    score: async () => {
      if (rawEvaluation.score?.data) {
        return { data: rawEvaluation.score.data };
      }
      return { data: null };
    }
  };
};

// Update the item transformation
const transformItem = (item: any) => ({
  // ... existing fields ...
  type: item.type,
  hasTask: !!item.task,
  taskStatus: item.task?.status,
  stagesCount: item.task?.stages?.items?.length || 0
});

// Add missing interfaces
interface ConfusionMatrix {
  matrix: number[][]
  labels: string[]
}

interface EvaluationRowProps {
  evaluation: Schema['Evaluation']['type']
  selectedEvaluationId: string | undefined | null
  scorecardNames: Record<string, string>
  scoreNames: Record<string, string>
  onSelect: (evaluation: Schema['Evaluation']['type']) => void
  onDelete: (evaluationId: string) => Promise<boolean>
}

// Add this near the top with other helper functions
function mapStatus(status: string | undefined | null): 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' {
  if (!status) return 'PENDING';
  
  const normalizedStatus = status.toUpperCase();
  switch (normalizedStatus) {
    case 'PENDING':
    case 'RUNNING':
    case 'COMPLETED':
    case 'FAILED':
      return normalizedStatus;
    case 'DONE':
      return 'COMPLETED';
    case 'ERROR':
      return 'FAILED';
    default:
      return 'PENDING';
  }
}

// Add a helper function for safe date formatting
const formatCreatedAt = (dateString: string | null | undefined) => {
  if (!dateString) return '';
  
  try {
    const date = new Date(dateString);
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return '';
    }
    return formatDistanceToNow(date, { addSuffix: true });
  } catch (e) {
    console.warn('Invalid date format:', dateString);
    return '';
  }
};

const EvaluationRow = React.memo(({ 
  evaluation, 
  selectedEvaluationId, 
  scorecardNames, 
  scoreNames,
  onSelect,
  onDelete
}: EvaluationRowProps) => {
  const taskData = typeof evaluation.task === 'function' ? (evaluation.task() as any) : evaluation.task;
  
  const stageConfigs = useMemo(() => {
    if (!taskData?.stages?.items) return [];
    return taskData.stages.items.map((stage: any) => ({
      key: stage.name,
      label: stage.name,
      color: stage.status === 'COMPLETED' ? 'bg-primary' :
             stage.status === 'FAILED' ? 'bg-false' :
             'bg-neutral',
      name: stage.name,
      order: stage.order,
      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
      processedItems: stage.processedItems,
      totalItems: stage.totalItems,
      statusMessage: stage.statusMessage,
      completed: stage.status === 'COMPLETED',
      startedAt: stage.startedAt,
      completedAt: stage.completedAt,
      estimatedCompletionAt: stage.estimatedCompletionAt
    }));
  }, [taskData?.stages?.items]);

  const stages = useMemo(() => {
    if (!taskData?.stages?.items) return [];
    return taskData.stages.items.map((stage: any) => ({
      key: stage.name,
      label: stage.name,
      color: stage.status === 'COMPLETED' ? 'bg-primary' :
             stage.status === 'FAILED' ? 'bg-false' :
             'bg-neutral',
      name: stage.name,
      order: stage.order,
      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
      processedItems: stage.processedItems,
      totalItems: stage.totalItems,
      statusMessage: stage.statusMessage,
      startedAt: stage.startedAt,
      completedAt: stage.completedAt,
      estimatedCompletionAt: stage.estimatedCompletionAt
    }));
  }, [taskData?.stages?.items]);

  // Convert null to undefined for string fields with explicit null checks
  const estimatedCompletionAt = taskData?.stages?.items?.find((s: TaskStage) => s.estimatedCompletionAt)?.estimatedCompletionAt === null ? 
    undefined : 
    taskData?.stages?.items?.find((s: TaskStage) => s.estimatedCompletionAt)?.estimatedCompletionAt;
  const startedAt = taskData?.startedAt === null ? undefined : taskData?.startedAt || 
                   evaluation.startedAt === null ? undefined : evaluation.startedAt;
  const errorMessage = evaluation.errorMessage === null ? undefined : evaluation.errorMessage;

  return (
    <TableRow 
      onClick={() => onSelect(evaluation)} 
      className="group cursor-pointer transition-colors duration-200 relative hover:bg-muted"
    >
      <TableCell className="font-medium">
        <div className="block @[630px]:hidden">
          <div className="flex justify-between">
            <div className="w-[40%] space-y-0.5">
              <div className="font-semibold truncate">
                <span className={evaluation.id === selectedEvaluationId ? 'text-focus' : ''}>
                  {scorecardNames[evaluation.id] || 'Unknown Scorecard'}
                </span>
              </div>
              <div className="text-sm text-muted-foreground">
                {scoreNames[evaluation.id] || 'Unknown Score'}
              </div>
              <div className="text-sm text-muted-foreground">
                {formatCreatedAt(evaluation.createdAt)}
              </div>
              <div className="text-sm text-muted-foreground">
                {evaluation.type || ''}
              </div>
            </div>
            <div className="w-[55%] space-y-2">
              <TaskStatus
                variant="list"
                showStages={true}
                status={mapStatus(taskData?.status || evaluation.status)}
                stageConfigs={stageConfigs}
                stages={stages}
                processedItems={taskData ? undefined : Number(evaluation.processedItems || 0)}
                totalItems={taskData ? undefined : Number(evaluation.totalItems || 0)}
                startedAt={startedAt}
                estimatedCompletionAt={estimatedCompletionAt}
                errorMessage={errorMessage}
              />
            </div>
          </div>
          <div className="mt-2 flex justify-end space-x-2">
            <CardButton 
              icon={Eye}
              onClick={() => onSelect(evaluation)}
            />
            <DropdownMenu>
              <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                <Button 
                  variant="ghost" 
                  size="icon"
                  className="h-8 w-8 p-0"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={async (e) => {
                  e.stopPropagation();
                  if (window.confirm('Are you sure you want to delete this evaluation?')) {
                    await onDelete(evaluation.id);
                  }
                }}>
                  <Trash2 className="h-4 w-4 mr-2" /> Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        <div className="hidden @[630px]:block">
          <div className="font-semibold">
            <span className={evaluation.id === selectedEvaluationId ? 'text-focus' : ''}>
              {scorecardNames[evaluation.id] || 'Unknown Scorecard'}
            </span>
          </div>
          <div className="text-sm text-muted-foreground">
            {scoreNames[evaluation.id] || 'Unknown Score'}
          </div>
          <div className="text-sm text-muted-foreground">
            {formatCreatedAt(evaluation.createdAt)}
          </div>
        </div>
      </TableCell>
      <TableCell className="hidden @[630px]:table-cell text-sm text-muted-foreground">
        {evaluation.type || ''}
      </TableCell>
      <TableCell className="hidden @[630px]:table-cell w-[15%] text-right">
        <TaskStatus
          variant="list"
          showStages={true}
          status={mapStatus(taskData?.status || evaluation.status)}
          stageConfigs={stageConfigs}
          stages={stages}
          processedItems={taskData ? undefined : Number(evaluation.processedItems || 0)}
          totalItems={taskData ? undefined : Number(evaluation.totalItems || 0)}
          startedAt={startedAt}
          estimatedCompletionAt={estimatedCompletionAt}
          errorMessage={errorMessage}
        />
      </TableCell>
      <TableCell className="hidden @[630px]:table-cell w-[15%]">
        <EvaluationListAccuracyBar 
          progress={calculateProgress(evaluation.processedItems, evaluation.totalItems)}
          accuracy={evaluation.accuracy ?? 0}
          isFocused={evaluation.id === selectedEvaluationId}
        />
      </TableCell>
      <TableCell className="hidden @[630px]:table-cell w-[10%] text-right">
        <div className="flex items-center justify-end space-x-2">
          <CardButton 
            icon={Eye}
            onClick={() => onSelect(evaluation)}
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button 
                variant="ghost" 
                size="icon"
                className="h-8 w-8 p-0"
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={async (e) => {
                e.stopPropagation();
                if (window.confirm('Are you sure you want to delete this evaluation?')) {
                  await onDelete(evaluation.id);
                }
              }}>
                <Trash2 className="h-4 w-4 mr-2" /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </TableCell>
    </TableRow>
  );
});

EvaluationRow.displayName = 'EvaluationRow';

// Add viewport hook
function useViewportWidth() {
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)

  useEffect(() => {
    const checkWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640)
    }
    
    checkWidth()
    window.addEventListener('resize', checkWidth)
    return () => window.removeEventListener('resize', checkWidth)
  }, [])

  return isNarrowViewport
}

// Initialize models once, but lazily
let evaluationModel: any = null;
let accountModel: any = null;

function getModels() {
  if (!evaluationModel || !accountModel) {
    const currentClient = getClient();
    console.log('Initializing models with client:', {
      hasModels: !!currentClient.models,
      modelNames: Object.keys(currentClient.models || {}),
      evaluationModel: currentClient.models?.Evaluation,
      evaluationModelFunctions: Object.keys(currentClient.models?.Evaluation || {}).filter(key => key.startsWith('list'))
    });
    evaluationModel = currentClient.models.Evaluation;
    accountModel = currentClient.models.Account;
  }
  return { evaluationModel, accountModel };
}

// Add these helper functions at the top
async function listAccounts(): ModelListResult<Schema['Account']['type']> {
  const { accountModel } = getModels();
  if (!accountModel) {
    throw new Error('Account model not found in client');
  }
  return listFromModel<Schema['Account']['type']>(
    accountModel,
    { key: { eq: ACCOUNT_KEY } }
  );
}

async function listEvaluations(accountId: string): ModelListResult<Schema['Evaluation']['type']> {
  const currentClient = getClient();
  
  console.log('Listing evaluations for account:', { accountId });
  
  type EvaluationItem = Schema['Evaluation']['type'];
  
  interface ListEvaluationResponse {
    listEvaluationByAccountIdAndUpdatedAt: {
      items: EvaluationItem[];
      nextToken: string | null;
    };
  }
  
  try {
    // Use the graphql query directly
    const response = await currentClient.graphql<ListEvaluationResponse>({
      query: `
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
              scoreId
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
            }
            nextToken
          }
        }
      `,
      variables: {
        accountId,
        sortDirection: 'DESC',
        limit: 100
      }
    }) as GraphQLResult<ListEvaluationResponse>;

    console.log('GraphQL response for evaluation list:', {
      hasData: !!response.data,
      hasErrors: !!response.errors,
      errors: response.errors?.map(e => ({
        message: e.message,
        path: e.path
      })),
      firstEvaluation: response.data?.listEvaluationByAccountIdAndUpdatedAt?.items[0] ? {
        id: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].id,
        hasTask: !!response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task,
        taskData: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task || null,
        taskFields: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task ? 
          Object.keys(response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task) : [],
        taskStages: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task?.stages?.items?.map(s => ({
          name: s.name,
          status: s.status,
          processedItems: s.processedItems,
          totalItems: s.totalItems
        }))
      } : null,
      allEvaluations: response.data?.listEvaluationByAccountIdAndUpdatedAt?.items.map(item => ({
        id: item.id,
        type: item.type,
        hasTask: !!item.task,
        taskStatus: item.task?.status,
        stagesCount: item.task?.stages?.items?.length
      }))
    });

    if (response.errors?.length) {
      throw new Error(`GraphQL errors: ${response.errors.map(e => e.message).join(', ')}`);
    }

    const result = response.data;
    if (!result) {
      throw new Error('No data returned from GraphQL query');
    }

    return {
      data: result.listEvaluationByAccountIdAndUpdatedAt.items.map((item: EvaluationItem) => transformEvaluation(item)),
      nextToken: result.listEvaluationByAccountIdAndUpdatedAt.nextToken
    };
  } catch (error) {
    console.error('Error in listEvaluations:', error);
    throw error;
  }
}

// Add this interface near the top of the file
interface EvaluationParameters {
  scoreType?: string
  dataBalance?: string
  scoreGoal?: string
  [key: string]: any  // Allow other parameters
}

// Add this type at the top with other interfaces
interface SubscriptionResponse {
  items: Schema['ScoreResult']['type'][]
}

// Add this type to help with the state update
type EvaluationTaskPropsType = EvaluationTaskProps['task']

interface EvaluationWithResults {
  id: string
  scoreResults: Array<{
    id: string
    value: number
    confidence: number | null
    metadata: any
    correct: boolean | null
    createdAt: string
    itemId: string
    EvaluationId: string
    scorecardId: string
  }>
}

interface EvaluationQueryResponse {
  data: {
    id: string
    scoreResults: Array<{
      id: string
      value: number
      confidence: number | null
      metadata: any
      correct: boolean | null
      createdAt: string
      itemId: string
      EvaluationId: string
      scorecardId: string
    }>
  }
}

// Define the structure of scoreResults
interface ScoreResult {
  id: string
  value: number
  confidence: number | null
  metadata: any
  correct: boolean | null
  createdAt: string
  itemId: string
  EvaluationId: string
  scorecardId: string
}

// Define the structure of the Evaluation with scoreResults
interface EvaluationWithResults {
  id: string
  scoreResults: ScoreResult[]
}

// Add this helper function near the top with other helpers
async function getEvaluationScoreResults(client: any, EvaluationId: string, nextToken?: string) {
  console.log('Fetching score results for Evaluation:', {
    EvaluationId,
    nextToken,
    usingNextToken: !!nextToken
  })

  // Remove sortDirection from initial query
  const params: any = {
    EvaluationId,
    limit: 10000
  }
  
  if (nextToken) {
    params.nextToken = nextToken
  }

  const response = await client.models.ScoreResult.listScoreResultByEvaluationId(params)

  // Sort the results in memory instead
  const sortedData = response.data ? 
    [...response.data].sort((a, b) => 
      new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    ) : []

  return {
    data: sortedData,
    nextToken: response.nextToken
  }
}

// Add this type near other interfaces
interface DragState {
  isDragging: boolean
  startX: number
  startWidth: number
}

// Add this new function near the top with other helper functions
async function loadRelatedData(
  evaluations: Schema['Evaluation']['type'][],
  setScorecardNames: (names: Record<string, string>) => void,
  setScoreNames: (names: Record<string, string>) => void
): Promise<Schema['Evaluation']['type'][]> {
  // Get unique IDs
  const scorecardIds = [...new Set(evaluations
    .filter(e => e.scorecardId)
    .map(e => e.scorecardId as string))]
  const scoreIds = [...new Set(evaluations
    .filter(e => e.scoreId)
    .map(e => e.scoreId as string))]

  console.log('Loading related data:', {
    evaluationCount: evaluations.length,
    scorecardIds,
    scoreIds,
    evaluationsWithoutScoreId: evaluations.filter(e => !e.scoreId).map(e => ({
      id: e.id,
      type: e.type,
      createdAt: e.createdAt
    }))
  })

  // Load all scorecards and scores in parallel with error handling
  const [scorecards, scores] = await Promise.all([
    Promise.all(
      scorecardIds.map(async id => {
        try {
          return await getFromModel<Schema['Scorecard']['type']>(
            client.models.Scorecard, 
            id
          )
        } catch (error) {
          console.error('Error loading scorecard:', { id, error })
          return { data: null }
        }
      })
    ),
    Promise.all(
      scoreIds.map(async id => {
        try {
          console.log('Attempting to load score:', { id })
          const result = await getFromModel<Schema['Score']['type']>(
            client.models.Score,
            id
          )
          if (!result.data) {
            console.warn('Score not found:', { id })
          }
          return result
        } catch (error) {
          console.error('Error loading score:', { id, error })
          return { data: null }
        }
      })
    )
  ])

  // Log score loading results with more detail
  console.log('Score loading results:', scores.map((result, index) => ({
    id: result.data?.id,
    requestedId: scoreIds[index],
    name: result.data?.name,
    success: !!result.data,
    found: result.data !== null && result.data !== undefined
  })))

  // Create maps for quick lookups
  const scorecardMap = new Map(
    scorecards.map(result => [result.data?.id, result.data])
  )
  const scoreMap = new Map(
    scores.map(result => [result.data?.id, result.data])
  )

  console.log('Score mapping:', {
    scoreIds,
    scoreMapEntries: Array.from(scoreMap.entries()).map(([id, score]) => ({
      id,
      name: score?.name,
      found: !!score
    }))
  });

  // Create name mappings
  const newScorecardNames: Record<string, string> = {}
  const newScoreNames: Record<string, string> = {}

  evaluations.forEach(evaluation => {
    const scorecard = scorecardMap.get(evaluation.scorecardId || '')
    const score = evaluation.scoreId ? scoreMap.get(evaluation.scoreId) : null
    
    if (scorecard) {
      newScorecardNames[evaluation.id] = scorecard.name
    }
    
    if (score) {
      newScoreNames[evaluation.id] = score.name
    } else if (evaluation.scoreId) {
      console.log('Missing score data for evaluation:', {
        evaluationId: evaluation.id,
        scoreId: evaluation.scoreId,
        type: evaluation.type,
        createdAt: evaluation.createdAt,
        scoreMapKeys: Array.from(scoreMap.keys()),
        scoreMapValues: Array.from(scoreMap.values()).map((s: Schema['Score']['type'] | null) => ({
          id: s?.id,
          name: s?.name
        }))
      })
    }
  })

  // Log final name mappings with more detail
  console.log('Final name mappings:', {
    scoreNames: newScoreNames,
    unmappedEvaluations: evaluations
      .filter(e => !newScoreNames[e.id])
      .map(e => ({
        id: e.id,
        scoreId: e.scoreId,
        type: e.type,
        createdAt: e.createdAt,
        scoreFound: e.scoreId ? scoreMap.has(e.scoreId) : false
      }))
  })

  // Update the state with the new names
  setScorecardNames(newScorecardNames)
  setScoreNames(newScoreNames)

  // Transform evaluations with pre-loaded data and explicitly return the result
  return evaluations.map(evaluation => ({
    ...evaluation,
    scorecard: async () => ({
      data: scorecardMap.get(evaluation.scorecardId || '') || null
    }),
    score: async () => ({
      data: evaluation.scoreId ? scoreMap.get(evaluation.scoreId) || null : null
    })
  }))
}

interface EvaluationMetric {
  name?: string;
  value?: number;
  unit?: string;
  maximum?: number;
  priority?: boolean;
}

interface ParsedScoreResult {
  id: string
  value: string
  confidence: number | null
  explanation: string | null
  metadata: {
    human_label: string | null
    correct: boolean
    human_explanation?: string | null
    text?: string | null
  }
  itemId: string | null
}

interface ScoreResultMetadata {
  item_id?: number | string
  results?: {
    [key: string]: {
      value?: string | number
      confidence?: number
      explanation?: string
      metadata?: {
        human_label?: string
        correct?: boolean
        human_explanation?: string
        text?: string
      }
    }
  }
}

function parseScoreResult(result: Schema['ScoreResult']['type']): ParsedScoreResult {
  // Handle double-stringified JSON
  const parsedMetadata = (() => {
    try {
      let metadata = result.metadata
      if (typeof metadata === 'string') {
        metadata = JSON.parse(metadata)
        if (typeof metadata === 'string') {
          metadata = JSON.parse(metadata)
        }
      }
      return metadata as ScoreResultMetadata
    } catch (e) {
      console.error('Error parsing metadata:', e)
      return {} as ScoreResultMetadata
    }
  })()

  console.log('Raw score result:', {
    id: result.id,
    metadata: result.metadata,
    parsedMetadata
  })

  const firstResultKey = parsedMetadata?.results ? 
    Object.keys(parsedMetadata.results)[0] : null
  const scoreResult = firstResultKey && parsedMetadata.results ? 
    parsedMetadata.results[firstResultKey] : null

  console.log('Parsed score result:', {
    firstResultKey,
    scoreResult,
    value: scoreResult?.value,
    confidence: scoreResult?.confidence,
    explanation: scoreResult?.explanation,
    metadata: scoreResult?.metadata
  })

  return {
    id: result.id,
    value: String(scoreResult?.value ?? ''),
    confidence: result.confidence ?? scoreResult?.confidence ?? null,
    explanation: scoreResult?.explanation ?? null,
    metadata: {
      human_label: scoreResult?.metadata?.human_label ?? null,
      correct: Boolean(scoreResult?.metadata?.correct),
      human_explanation: scoreResult?.metadata?.human_explanation ?? null,
      text: scoreResult?.metadata?.text ?? null
    },
    itemId: parsedMetadata?.item_id?.toString() ?? null
  }
}

// Handle delete evaluation
const handleDeleteEvaluation = async (client: any, evaluationId: string) => {
  try {
    // First, get all score results for this evaluation
    const scoreResultsResponse = await client.models.ScoreResult.list({
      filter: { evaluationId: { eq: evaluationId } },
      limit: 10000,
      fields: ['id']
    });

    // Delete all score results first
    if (scoreResultsResponse.data && scoreResultsResponse.data.length > 0) {
      console.log(`Deleting ${scoreResultsResponse.data.length} score results for evaluation ${evaluationId}`);
      await Promise.all(
        scoreResultsResponse.data.map((result: { id: string }) => 
          client.models.ScoreResult.delete({ id: result.id })
        )
      );
    }

    // Get and delete all scoring jobs for this evaluation
    const scoringJobsResponse = await client.models.ScoringJob.list({
      filter: { evaluationId: { eq: evaluationId } },
      limit: 10000,
      fields: ['id']
    });

    if (scoringJobsResponse.data && scoringJobsResponse.data.length > 0) {
      console.log(`Deleting ${scoringJobsResponse.data.length} scoring jobs for evaluation ${evaluationId}`);
      await Promise.all(
        scoringJobsResponse.data.map((job: { id: string }) => 
          client.models.ScoringJob.delete({ id: job.id })
        )
      );
    }

    // Then delete the evaluation itself
    await client.models.Evaluation.delete({ id: evaluationId });
    return true;
  } catch (error) {
    console.error('Error deleting evaluation:', error);
    return false;
  }
};

// Add interface for Task near the top of the file with other interfaces
interface Task {
  id: string
  type: string
  command?: string
  status: string
  startedAt?: string
  completedAt?: string
  dispatchStatus?: string
  celeryTaskId?: string
  workerNodeId?: string
  stages?: {
    items: TaskStage[]
    nextToken?: string | null
  }
}

// Update the TaskStage interface
interface TaskStage {
  id: string
  name: string
  status: string
  processedItems?: number
  totalItems?: number
  startedAt?: string
  completedAt?: string
  estimatedCompletionAt?: string
  statusMessage?: string
  order: number
}

// Update the EvaluationTaskData interface to use the Task type
interface EvaluationTaskData {
  id: string
  title: string
  accuracy: number | null
  metrics: EvaluationMetric[]
  metricsExplanation?: string | null
  processedItems: number
  totalItems: number
  progress: number
  inferences: number
  cost: number | null
  status: string
  elapsedSeconds: number | null
  estimatedRemainingSeconds: number | null
  startedAt?: string | null
  errorMessage?: string
  errorDetails?: any | null
  confusionMatrix?: {
    matrix: number[][] | null
    labels: string[] | null
  } | null
  scoreGoal?: string | null
  datasetClassDistribution?: { label: string, count: number }[]
  isDatasetClassDistributionBalanced?: boolean | null
  predictedClassDistribution?: { label: string, count: number }[]
  isPredictedClassDistributionBalanced?: boolean | null
  scoreResults?: Array<{
    id: string
    value: string | number
    confidence?: number | null
    explanation?: string | null
    metadata?: any
    createdAt?: string
    itemId?: string
    EvaluationId?: string
    scorecardId?: string
    [key: string]: any
  }>
  task?: Task | null
}

export default function EvaluationsDashboard(): JSX.Element {
  const { authStatus, user } = useAuthenticator(context => [context.authStatus]);
  const router = useRouter();
  
  // State hooks
  const [Evaluations, setEvaluations] = useState<NonNullable<Schema['Evaluation']['type']>[]>([])
  const [EvaluationTaskProps, setEvaluationTaskProps] = useState<EvaluationTaskProps['task'] | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [selectedEvaluation, setSelectedEvaluation] = useState<Schema['Evaluation']['type'] | null>(null)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [scorecardName, setScorecardName] = useState('Unknown Scorecard')
  const [scorecardNames, setScorecardNames] = useState<Record<string, string>>({})
  const [hasMounted, setHasMounted] = useState(false)
  const [scoreResults, setScoreResults] = useState<Schema['ScoreResult']['type'][]>([])
  const [leftPanelWidth, setLeftPanelWidth] = useState<number>(50)
  const [scoreNames, setScoreNames] = useState<Record<string, string>>({})
  const [selectedScoreResultId, setSelectedScoreResultId] = useState<string | null>(null)

  // Ref hooks
  const selectedEvaluationRef = useRef<Schema['Evaluation']['type'] | null>(null)
  const dragStateRef = useRef<DragState>({
    isDragging: false,
    startX: 0,
    startWidth: 50
  })
  const containerRef = useRef<HTMLDivElement>(null)

  // Custom hooks
  const isNarrowViewport = useViewportWidth()

  // Memoized values
  const filteredEvaluations = useMemo(() => {
    return Evaluations.filter(Evaluation => {
      if (!selectedScorecard) return true
      return Evaluation.scorecardId === selectedScorecard
    })
  }, [Evaluations, selectedScorecard])

  // Memoized components
  const EvaluationList = useMemo(() => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[40%]">Evaluation</TableHead>
          <TableHead className="w-[10%] @[630px]:table-cell hidden">Type</TableHead>
          <TableHead className="w-[20%] @[630px]:table-cell hidden text-right">Progress</TableHead>
          <TableHead className="w-[20%] @[630px]:table-cell hidden text-right">Accuracy</TableHead>
          <TableHead className="w-[10%] @[630px]:table-cell hidden text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {filteredEvaluations.map((Evaluation) => (
          <EvaluationRow 
            key={Evaluation.id} 
            evaluation={Evaluation}
            selectedEvaluationId={selectedEvaluation?.id ?? null}
            scorecardNames={scorecardNames}
            scoreNames={scoreNames}
            onSelect={(evaluation) => {
              setScoreResults([])
              setSelectedScoreResultId(null)
              setSelectedEvaluation(evaluation)
            }}
            onDelete={async (evaluationId) => {
              const success = await handleDeleteEvaluation(client, evaluationId);
              if (success) {
                setEvaluations(prev => prev.filter(e => e.id !== evaluationId));
                if (selectedEvaluation?.id === evaluationId) {
                  setSelectedEvaluation(null);
                }
              }
              return success;
            }}
          />
        ))}
      </TableBody>
    </Table>
  ), [filteredEvaluations, selectedEvaluation?.id, scorecardNames, scoreNames])

  const EvaluationTaskComponent = useMemo(() => {
    if (!selectedEvaluation || !EvaluationTaskProps) {
      console.log('Cannot render EvaluationTask:', {
        hasSelectedEvaluation: !!selectedEvaluation,
        hasTaskProps: !!EvaluationTaskProps,
        selectedEvaluationId: selectedEvaluation?.id
      });
      return null;
    }
    
    console.log('Rendering EvaluationTask with props:', {
      taskId: EvaluationTaskProps.id,
      taskType: EvaluationTaskProps.type,
      hasTaskData: !!EvaluationTaskProps.data,
      taskInData: EvaluationTaskProps.data?.task ? {
        id: EvaluationTaskProps.data.task.id,
        status: EvaluationTaskProps.data.task.status,
        stagesCount: EvaluationTaskProps.data.task.stages?.items?.length,
        stages: EvaluationTaskProps.data.task.stages?.items?.map(s => ({
          name: s.name,
          status: s.status,
          processedItems: s.processedItems,
          totalItems: s.totalItems
        }))
      } : null
    });
    
    return (
      <EvaluationTask
        variant="detail"
        task={EvaluationTaskProps}
        isFullWidth={isFullWidth}
        selectedScoreResultId={selectedScoreResultId}
        onSelectScoreResult={setSelectedScoreResultId}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={() => {
          setSelectedEvaluation(null)
          setSelectedScoreResultId(null)
          setIsFullWidth(false)
        }}
      />
    )
  }, [selectedEvaluation?.id, EvaluationTaskProps, isFullWidth, selectedScoreResultId])

  // Event handlers
  const handleDragStart = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault()
    dragStateRef.current = {
      isDragging: true,
      startX: e.clientX,
      startWidth: leftPanelWidth
    }
    document.addEventListener('mousemove', handleDragMove)
    document.addEventListener('mouseup', handleDragEnd)
  }, [leftPanelWidth])

  const handleDragMove = useCallback((e: MouseEvent) => {
    if (!dragStateRef.current.isDragging || !containerRef.current) return

    const containerWidth = containerRef.current.getBoundingClientRect().width
    const deltaX = e.clientX - dragStateRef.current.startX
    const newWidthPercent = (dragStateRef.current.startWidth * 
      containerWidth / 100 + deltaX) / containerWidth * 100

    const constrainedWidth = Math.min(Math.max(newWidthPercent, 20), 80)
    setLeftPanelWidth(constrainedWidth)
  }, [])

  const handleDragEnd = useCallback(() => {
    dragStateRef.current.isDragging = false
    document.removeEventListener('mousemove', handleDragMove)
    document.removeEventListener('mouseup', handleDragEnd)
  }, [])

  // Add escape key handler
  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (selectedEvaluation && event.key === 'Escape') {
      setSelectedEvaluation(null)
      setIsFullWidth(false)
    }
  }, [selectedEvaluation])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  // Effects
  useEffect(() => {
    if (authStatus === 'unauthenticated') {
      router.push('/');
      return;
    }
  }, [authStatus, router]);

  useEffect(() => {
    setHasMounted(true);
  }, []);

  useEffect(() => {
    selectedEvaluationRef.current = selectedEvaluation;

    if (selectedEvaluation) {
      const subscription = observeScoreResults(client, selectedEvaluation.id).subscribe({
        next: (data) => {
          const parsedResults = data.items.map(parseScoreResult)
          setScoreResults(parsedResults)
        },
        error: (error) => {
          console.error('Error observing score results:', error)
        }
      })

      return () => {
        subscription.unsubscribe()
      }
    }
  }, [selectedEvaluation])

  // Move the handler outside useEffect and declare with useCallback
  const handleEvaluationUpdate = useCallback((data: any) => {
    // Add null checks and logging
    if (!data) {
      console.warn('Received null subscription data');
      return;
    }

    // Log the raw data to help debug
    console.debug('Subscription update received:', data);

    // Safely access the evaluation data
    const evaluation = data.data?.onUpdateEvaluation;
    if (!evaluation || !evaluation.id) {
      console.warn('Received invalid evaluation data:', evaluation);
      return;
    }

    // Now we can safely use the evaluation data
    setEvaluations(prev => {
      const index = prev.findIndex(e => e.id === evaluation.id);
      if (index === -1) return prev;
      
      const updated = [...prev];
      updated[index] = transformEvaluation(evaluation);
      return updated;
    });
  }, []); // Empty dependency array since we only use setState functions

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const { data: accounts } = await listAccounts();
        if (!accounts?.length) {
          setIsLoading(false);
          return;
        }

        const foundAccountId = accounts[0].id;
        setAccountId(foundAccountId);

        const { data: evaluations } = await listEvaluations(foundAccountId);
        if (!evaluations) {
          setIsLoading(false);
          return;
        }

        console.log('Raw evaluations from listEvaluations:', evaluations.map(e => ({
          id: e.id,
          updatedAt: e.updatedAt,
          type: e.type
        })));

        const transformedEvaluations = await loadRelatedData(
          evaluations,
          setScorecardNames,
          setScoreNames
        );

        setEvaluations(transformedEvaluations);
        setIsLoading(false);

        const handleError = (error: unknown) => {
          console.error('Subscription error:', error);
          setError(error instanceof Error ? error : new Error(String(error)));
        };

        // Subscribe to create events
        const createSub = (client.models.Evaluation as any).onCreate().subscribe({
          next: handleEvaluationUpdate,
          error: handleError
        });

        // Subscribe to update events
        const updateSub = (client.models.Evaluation as any).onUpdate().subscribe({
          next: handleEvaluationUpdate,
          error: handleError
        });

        // Clean up subscriptions
        return () => {
          createSub.unsubscribe();
          updateSub.unsubscribe();
        };
      } catch (error) {
        console.error('Error loading evaluations:', error);
        setError(error instanceof Error ? error : new Error(String(error)));
        setIsLoading(false);
      }
    };

    loadInitialData();
  }, [handleEvaluationUpdate]); // Add handleEvaluationUpdate to dependencies

  // Add effect to update EvaluationTaskProps when selectedEvaluation changes
  useEffect(() => {
    if (!selectedEvaluation) {
      console.log('No selected evaluation, clearing task props');
      setEvaluationTaskProps(null);
      return;
    }

    console.log('Raw selected evaluation:', {
      id: selectedEvaluation.id,
      type: selectedEvaluation.type,
      status: selectedEvaluation.status,
      task: selectedEvaluation.task
    });

    const taskData = typeof selectedEvaluation.task === 'function' ? 
      (selectedEvaluation.task() as any) : 
      selectedEvaluation.task;

    // Ensure task data is properly structured
    const normalizedTaskData = taskData ? {
      ...taskData,
      stages: {
        items: Array.isArray(taskData.stages?.items) ? taskData.stages.items : []
      }
    } : null;

    const rawMetrics = (() => {
      try {
        if (typeof selectedEvaluation.metrics === 'string') {
          return JSON.parse(selectedEvaluation.metrics);
        }
        if (Array.isArray(selectedEvaluation.metrics)) {
          return selectedEvaluation.metrics;
        }
        return [];
      } catch (e) {
        console.error('Error parsing metrics:', e);
        return [];
      }
    })();

    const metrics = rawMetrics.map((metric: EvaluationMetric) => ({
      name: String(metric?.name || ''),
      value: Number(metric?.value || 0),
      unit: String(metric?.unit || '%'),
      maximum: Number(metric?.maximum || 100),
      priority: Boolean(metric?.priority)
    }));

    const taskProps = {
      id: selectedEvaluation.id,
      type: selectedEvaluation.type,
      scorecard: scorecardNames[selectedEvaluation.id] || 'Unknown Scorecard',
      score: scoreNames[selectedEvaluation.id] || 'Unknown Score',
      time: selectedEvaluation.createdAt,
      data: {
        id: selectedEvaluation.id,
        title: scorecardNames[selectedEvaluation.id] || 'Unknown Scorecard',
        accuracy: selectedEvaluation.accuracy ?? null,
        metrics,
        metricsExplanation: selectedEvaluation.metricsExplanation ?? null,
        processedItems: selectedEvaluation.processedItems ?? 0,
        totalItems: selectedEvaluation.totalItems ?? 0,
        progress: calculateProgress(selectedEvaluation.processedItems, selectedEvaluation.totalItems),
        inferences: selectedEvaluation.inferences ?? 0,
        cost: selectedEvaluation.cost ?? null,
        status: selectedEvaluation.status || '',
        elapsedSeconds: selectedEvaluation.elapsedSeconds ?? null,
        estimatedRemainingSeconds: selectedEvaluation.estimatedRemainingSeconds ?? null,
        startedAt: selectedEvaluation.startedAt ?? null,
        errorMessage: selectedEvaluation.errorMessage ?? undefined,
        errorDetails: selectedEvaluation.errorDetails ?? null,
        confusionMatrix: selectedEvaluation.confusionMatrix,
        scoreGoal: selectedEvaluation.scoreGoal ?? null,
        datasetClassDistribution: selectedEvaluation.datasetClassDistribution,
        isDatasetClassDistributionBalanced: selectedEvaluation.isDatasetClassDistributionBalanced ?? null,
        predictedClassDistribution: selectedEvaluation.predictedClassDistribution,
        isPredictedClassDistributionBalanced: selectedEvaluation.isPredictedClassDistributionBalanced ?? null,
        scoreResults: scoreResults,
        task: normalizedTaskData
      }
    };

    setEvaluationTaskProps(taskProps);
  }, [selectedEvaluation, scorecardNames, scoreNames, scoreResults]);

  // Early return for unauthenticated state
  if (authStatus !== 'authenticated') {
    return <EvaluationDashboardSkeleton />;
  }

  // Early return for loading state
  if (!hasMounted) {
    return <EvaluationDashboardSkeleton />;
  }

  // Early return for error state
  if (error) {
    return (
      <div className="p-4 text-red-500">
        Error loading Evaluations: {error.message}
      </div>
    );
  }

  return (
    <ClientOnly>
      <div className="h-full flex flex-col" ref={containerRef}>
        <div className={`flex ${isNarrowViewport ? 'flex-col' : ''} flex-1 h-full w-full`}>
          <div className={`
            flex flex-col
            ${isFullWidth ? 'hidden' : ''} 
            ${(!selectedEvaluation || !isNarrowViewport) ? 'flex h-full' : 'hidden'}
            ${(!selectedEvaluation || isNarrowViewport) ? 'w-full' : ''}
          `}
          style={!isNarrowViewport && selectedEvaluation && !isFullWidth ? {
            width: `${leftPanelWidth}%`
          } : undefined}>
            <div className="mb-4 flex-shrink-0 flex justify-between items-start">
              <ScorecardContext 
                selectedScorecard={selectedScorecard}
                setSelectedScorecard={setSelectedScorecard}
                selectedScore={selectedScore}
                setSelectedScore={setSelectedScore}
                availableFields={[]}
              />
              <TaskDispatchButton config={evaluationsConfig} />
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto @container">
              {EvaluationList}
            </div>
          </div>

          {selectedEvaluation && !isNarrowViewport && !isFullWidth && (
            <div
              className="w-2 relative cursor-col-resize flex-shrink-0 group"
              onMouseDown={handleDragStart}
            >
              <div className="absolute inset-0 rounded-full transition-colors duration-150 
                group-hover:bg-accent" />
            </div>
          )}

          {selectedEvaluation && EvaluationTaskProps && (
            <div 
              className={`
                flex flex-col flex-1 
                ${isNarrowViewport || isFullWidth ? 'w-full' : ''}
                h-full
              `}
              style={!isNarrowViewport && !isFullWidth ? {
                width: `${100 - leftPanelWidth}%`
              } : undefined}
            >
              {EvaluationTaskComponent}
            </div>
          )}
        </div>
      </div>
    </ClientOnly>
  );
}

// Create a ClientOnly wrapper component
function ClientOnly({ children }: { children: React.ReactNode }) {
  const [hasMounted, setHasMounted] = useState(false);

  useEffect(() => {
    setHasMounted(true);
  }, []);

  if (!hasMounted) {
    return null; // Or a loading skeleton that matches server render
  }

  return <>{children}</>;
}
