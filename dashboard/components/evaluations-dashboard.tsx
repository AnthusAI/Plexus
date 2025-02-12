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

// Add subscription queries after the ACCOUNT_KEY constant
const EVALUATION_UPDATE_SUBSCRIPTION = `
  subscription OnUpdateEvaluation {
    onUpdateEvaluation {
      id
      type
      accuracy
      parameters
      metrics
      metricsExplanation
      inferences
      cost
      createdAt
      updatedAt
      status
      startedAt
      totalItems
      processedItems
      errorMessage
      errorDetails
      accountId
      scorecardId
      scoreId
      confusionMatrix
      elapsedSeconds
      estimatedRemainingSeconds
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
  }
`;

const TASK_UPDATE_SUBSCRIPTION = `
  subscription OnUpdateTask {
    onUpdateTask {
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
`;

const TASK_STAGE_UPDATE_SUBSCRIPTION = `
  subscription OnUpdateTaskStage {
    onUpdateTaskStage {
      id
      taskId
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
`;

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

interface TaskData {
  id: string;
  accountId: string;
  type: string;
  status: string;
  target: string;
  command: string;
  completedAt?: string;
  startedAt?: string;
  dispatchStatus?: string;
  celeryTaskId?: string;
  workerNodeId?: string;
  description?: string;
  metadata?: any;
  createdAt?: string;
  estimatedCompletionAt?: string;
  errorMessage?: string;
  errorDetails?: string;
  currentStageId?: string;
  stages?: {
    items: TaskStage[];
    nextToken?: string | null;
  };
}

interface ConfusionMatrix {
  matrix: number[][];
  labels: string[];
}

interface EvaluationData {
  id: string;
  type: string;
  status: string;
  createdAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
  processedItems?: number | null;
  totalItems?: number | null;
  accuracy?: number | null;
  metricsExplanation?: string | null;
  errorMessage?: string | null;
  errorDetails?: string | null;
  confusionMatrix?: ConfusionMatrix | null;
  scoreGoal?: string | null;
  datasetClassDistribution?: Array<{ label: string; count: number }> | string | null;
  isDatasetClassDistributionBalanced?: boolean | null;
  predictedClassDistribution?: Array<{ label: string; count: number }> | string | null;
  isPredictedClassDistributionBalanced?: boolean | null;
  task?: TaskData;
}

const transformEvaluation = (rawEvaluation: any): Schema['Evaluation']['type'] => {
  if (!rawEvaluation) {
    return null;
  }

  console.log('Raw evaluation in transform:', {
    hasTask: !!rawEvaluation.task,
    taskData: rawEvaluation.task ? {
      id: rawEvaluation.task.id,
      status: rawEvaluation.task.status,
      stageCount: rawEvaluation.task.stages?.items?.length,
      stages: rawEvaluation.task.stages?.items?.map(s => ({
        name: s.name,
        status: s.status,
        processedItems: s.processedItems,
        totalItems: s.totalItems
      }))
    } : null
  });

  // Create a safe copy of the evaluation with all required fields
  const safeEvaluation = {
    id: rawEvaluation.id || '',
    type: rawEvaluation.type || '',
    parameters: rawEvaluation.parameters || {},
    metrics: rawEvaluation.metrics || {},
    metricsExplanation: rawEvaluation.metricsExplanation || '',
    inferences: rawEvaluation.inferences || 0,
    accuracy: rawEvaluation.accuracy || 0,
    cost: rawEvaluation.cost || 0,
    createdAt: rawEvaluation.createdAt || new Date().toISOString(),
    updatedAt: rawEvaluation.updatedAt || new Date().toISOString(),
    status: rawEvaluation.status || 'PENDING',
    startedAt: rawEvaluation.startedAt || null,
    elapsedSeconds: rawEvaluation.elapsedSeconds || 0,
    estimatedRemainingSeconds: rawEvaluation.estimatedRemainingSeconds || 0,
    totalItems: rawEvaluation.totalItems || 0,
    processedItems: rawEvaluation.processedItems || 0,
    errorMessage: rawEvaluation.errorMessage || '',
    errorDetails: rawEvaluation.errorDetails || {},
    accountId: rawEvaluation.accountId || '',
    scorecardId: rawEvaluation.scorecardId || '',
    scoreId: rawEvaluation.scoreId || '',
    confusionMatrix: (() => {
      try {
        if (!rawEvaluation.confusionMatrix) return null;
        
        // First try to parse if it's a string
        let parsedMatrix = rawEvaluation.confusionMatrix;
        if (typeof parsedMatrix === 'string') {
          try {
            parsedMatrix = JSON.parse(parsedMatrix);
          } catch (e) {
            console.error('Error parsing confusion matrix string in transform:', e);
            return null;
          }
        }

        // Now check if the parsed data has the correct structure
        if (!parsedMatrix || !parsedMatrix.matrix || !parsedMatrix.labels) {
          console.error('Invalid confusion matrix structure in transform:', parsedMatrix);
          return null;
        }

        // Validate the data types
        if (!Array.isArray(parsedMatrix.matrix) || !Array.isArray(parsedMatrix.labels)) {
          console.error('Invalid confusion matrix data types in transform:', {
            matrixIsArray: Array.isArray(parsedMatrix.matrix),
            labelsIsArray: Array.isArray(parsedMatrix.labels)
          });
          return null;
        }

        return {
          matrix: parsedMatrix.matrix,
          labels: parsedMatrix.labels
        };
      } catch (e) {
        console.error('Error processing confusion matrix in transform:', e);
        return null;
      }
    })(),
    scoreGoal: rawEvaluation.scoreGoal || '',
    datasetClassDistribution: rawEvaluation.datasetClassDistribution || {},
    isDatasetClassDistributionBalanced: rawEvaluation.isDatasetClassDistributionBalanced || false,
    predictedClassDistribution: rawEvaluation.predictedClassDistribution || {},
    isPredictedClassDistributionBalanced: rawEvaluation.isPredictedClassDistributionBalanced || false,
    taskId: rawEvaluation.taskId || '',
    task: rawEvaluation.task ? {
      id: rawEvaluation.task.id,
      accountId: rawEvaluation.task.accountId || '',
      type: rawEvaluation.task.type || '',
      status: rawEvaluation.task.status || '',
      target: rawEvaluation.task.target || '',
      command: rawEvaluation.task.command || '',
      description: rawEvaluation.task.description || '',
      dispatchStatus: rawEvaluation.task.dispatchStatus || '',
      metadata: rawEvaluation.task.metadata || {},
      createdAt: rawEvaluation.task.createdAt || '',
      startedAt: rawEvaluation.task.startedAt || null,
      completedAt: rawEvaluation.task.completedAt || null,
      estimatedCompletionAt: rawEvaluation.task.estimatedCompletionAt || null,
      errorMessage: rawEvaluation.task.errorMessage || '',
      errorDetails: rawEvaluation.task.errorDetails || {},
      currentStageId: rawEvaluation.task.currentStageId || '',
      stages: rawEvaluation.task.stages ? {
        items: (rawEvaluation.task.stages.items || []).map((stage: any) => ({
          id: stage.id || '',
          name: stage.name || '',
          order: stage.order || 0,
          status: stage.status || '',
          statusMessage: stage.statusMessage || '',
          startedAt: stage.startedAt || null,
          completedAt: stage.completedAt || null,
          estimatedCompletionAt: stage.estimatedCompletionAt || null,
          processedItems: stage.processedItems || 0,
          totalItems: stage.totalItems || 0
        })),
        nextToken: rawEvaluation.task.stages.nextToken || null
      } : undefined
    } : null
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

const transformItem = (item: any) => ({
  type: item.type,
  hasTask: !!item.task,
  taskStatus: item.task?.status,
  stagesCount: item.task?.stages?.items?.length
});

interface EvaluationRowProps {
  evaluation: Schema['Evaluation']['type']
  selectedEvaluationId: string | undefined | null
  scorecardNames: Record<string, string>
  scoreNames: Record<string, string>
  onSelect: (evaluation: Schema['Evaluation']['type']) => void
  onDelete: (evaluationId: string) => Promise<boolean>
}

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

const formatCreatedAt = (dateString: string | null | undefined) => {
  if (!dateString) return '';
  
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) {
      return '';
    }
    return formatDistanceToNow(date, { addSuffix: true });
  } catch (e) {
    console.warn('Invalid date format:', dateString);
    return '';
  }
};

// Replace EvaluationCard with this simplified version that uses EvaluationTask
const EvaluationCard = React.memo(({ 
  evaluation, 
  selectedEvaluationId, 
  scorecardNames, 
  scoreNames,
  onSelect,
  onDelete
}: EvaluationRowProps) => {
  const taskData = typeof evaluation.task === 'function' ? (evaluation.task() as TaskData) : evaluation.task as TaskData;
  
  // Transform evaluation data into EvaluationTask format
  const evaluationTaskData: EvaluationTaskData = {
    id: evaluation.id,
    title: scorecardNames[evaluation.id] || 'Unknown Scorecard',
    accuracy: evaluation.accuracy ?? null,
    metrics: [], // Add metrics if available
    processedItems: Number(evaluation.processedItems || 0),
    totalItems: Number(evaluation.totalItems || 0),
    progress: calculateProgress(evaluation.processedItems, evaluation.totalItems),
    inferences: evaluation.inferences || 0,
    cost: evaluation.cost || null,
    status: evaluation.status || 'PENDING',
    elapsedSeconds: evaluation.elapsedSeconds || null,
    estimatedRemainingSeconds: evaluation.estimatedRemainingSeconds || null,
    startedAt: evaluation.startedAt,
    errorMessage: evaluation.errorMessage,
    errorDetails: evaluation.errorDetails,
    task: taskData
  };

  return (
    <div 
      onClick={() => onSelect(evaluation)}
      className={`
        transition-colors duration-200
        ${evaluation.id === selectedEvaluationId ? 'bg-card' : 'bg-frame'}
      `}
    >
      <EvaluationTask
        variant="grid"
        task={{
          id: evaluation.id,
          type: evaluation.type,
          scorecard: scorecardNames[evaluation.id] || 'Unknown Scorecard',
          score: scoreNames[evaluation.id] || 'Unknown Score',
          time: evaluation.createdAt,
          data: evaluationTaskData
        }}
        onClick={() => onSelect(evaluation)}
        controlButtons={
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-8 w-8 p-0">
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
        }
      />
    </div>
  );
});

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
              scoreResults {
                items {
                  id
                  value
                  confidence
                  metadata
                  explanation
                  itemId
                  evaluationId
                  scorecardId
                  createdAt
                }
                nextToken
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

interface EvaluationParameters {
  scoreType?: string
  dataBalance?: string
  scoreGoal?: string
  [key: string]: any  // Allow other parameters
}

interface SubscriptionResponse {
  items: Schema['ScoreResult']['type'][]
}

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

interface ScoreResult {
  id: string
  value: string | number
  confidence: number | null
  explanation: string | null
  metadata: any
  correct: boolean | null
  createdAt: string
  itemId: string
  evaluationId: string
  scorecardId: string
}

interface EvaluationWithResults {
  id: string
  scoreResults: ScoreResult[]
}

async function getEvaluationScoreResults(client: any, EvaluationId: string, nextToken?: string) {
  console.log('Fetching score results for Evaluation:', {
    EvaluationId,
    nextToken,
    usingNextToken: !!nextToken
  })

  const params: any = {
    EvaluationId,
    limit: 10000,
    fields: [
      'id',
      'value',
      'confidence',
      'metadata',
      'explanation',
      'correct',
      'itemId',
      'accountId',
      'scoringJobId',
      'evaluationId',
      'scorecardId',
      'createdAt'
    ]
  }
  
  if (nextToken) {
    params.nextToken = nextToken
  }

  const response = await client.models.ScoreResult.listScoreResultByEvaluationId(params)

  const sortedData = response.data ? 
    [...response.data].sort((a, b) => 
      new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    ) : []

  return {
    data: sortedData,
    nextToken: response.nextToken
  }
}

interface DragState {
  isDragging: boolean
  startX: number
  startWidth: number
}

async function loadRelatedData(
  evaluations: Schema['Evaluation']['type'][],
  setScorecardNames: (names: Record<string, string>) => void,
  setScoreNames: (names: Record<string, string>) => void
): Promise<Schema['Evaluation']['type'][]> {
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

  console.log('Score loading results:', scores.map((result, index) => ({
    id: result.data?.id,
    requestedId: scoreIds[index],
    name: result.data?.name,
    success: !!result.data,
    found: result.data !== null && result.data !== undefined
  })))

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

  const newScorecardNames: Record<string, string> = {};
  const newScoreNames: Record<string, string> = {};

  evaluations.forEach(evaluation => {
    const scorecard = scorecardMap.get(evaluation.scorecardId || '');
    const score = evaluation.scoreId ? scoreMap.get(evaluation.scoreId) : null;
    
    if (scorecard) {
      newScorecardNames[evaluation.id] = scorecard.name;
    }
    
    if (score) {
      newScoreNames[evaluation.id] = score.name;
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
      });
    }
  });

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

  setScorecardNames(newScorecardNames)
  setScoreNames(newScoreNames)

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

function parseScoreResult(result: any): ParsedScoreResult {
  if (!result) {
    console.warn('Received null or undefined score result')
    return {
      id: '',
      value: '',
      confidence: null,
      explanation: null,
      metadata: {
        human_label: null,
        correct: false,
        human_explanation: null,
        text: null
      },
      itemId: null
    }
  }

  // Handle metadata parsing with better error handling
  const parsedMetadata = (() => {
    try {
      let metadata = result.metadata
      if (typeof metadata === 'string') {
        metadata = JSON.parse(metadata)
        if (typeof metadata === 'string') {
          metadata = JSON.parse(metadata)
        }
      }
      return metadata || {}
    } catch (e) {
      console.error('Error parsing metadata:', e)
      return {}
    }
  })()

  // Extract results from nested structure if present
  const firstResultKey = parsedMetadata?.results ? 
    Object.keys(parsedMetadata.results)[0] : null
  const scoreResult = firstResultKey && parsedMetadata.results ? 
    parsedMetadata.results[firstResultKey] : null

  // Log the parsing process for debugging
  console.debug('Score result parsing:', {
    originalResult: result,
    parsedMetadata,
    firstResultKey,
    scoreResult
  })

  return {
    id: result.id || '',
    value: String(result.value || scoreResult?.value || ''),
    confidence: result.confidence ?? scoreResult?.confidence ?? null,
    explanation: result.explanation ?? scoreResult?.explanation ?? null,
    metadata: {
      human_label: scoreResult?.metadata?.human_label ?? parsedMetadata.human_label ?? null,
      correct: Boolean(scoreResult?.metadata?.correct ?? parsedMetadata.correct),
      human_explanation: scoreResult?.metadata?.human_explanation ?? parsedMetadata.human_explanation ?? null,
      text: scoreResult?.metadata?.text ?? parsedMetadata.text ?? null
    },
    itemId: result.itemId || parsedMetadata.item_id?.toString() || null
  }
}

const handleDeleteEvaluation = async (client: any, evaluationId: string) => {
  try {
    const scoreResultsResponse = await client.models.ScoreResult.list({
      filter: { evaluationId: { eq: evaluationId } },
      limit: 10000,
      fields: ['id']
    });

    if (scoreResultsResponse.data && scoreResultsResponse.data.length > 0) {
      console.log(`Deleting ${scoreResultsResponse.data.length} score results for evaluation ${evaluationId}`);
      await Promise.all(
        scoreResultsResponse.data.map((result: { id: string }) => 
          client.models.ScoreResult.delete({ id: result.id })
        )
      );
    }

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

    await client.models.Evaluation.delete({ id: evaluationId });
    return true;
  } catch (error) {
    console.error('Error deleting evaluation:', error);
    return false;
  }
};

interface TaskStage {
  id: string;
  name: string;
  order: number;
  status: string;
  statusMessage?: string;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  processedItems?: number;
  totalItems?: number;
}

interface EvaluationTaskPropsInternal {
  id: string;
  type: string;
  scorecard: string;
  score: string;
  time: string;
  data: {
    id: string;
    title: string;
    accuracy: number | null;
    metrics: any[];
    metricsExplanation: string | null;
    processedItems: number;
    totalItems: number;
    progress: number;
    inferences: number;
    cost: number | null;
    status: string;
    elapsedSeconds: number | null;
    estimatedRemainingSeconds: number | null;
    startedAt: string | null;
    errorMessage?: string;
    errorDetails: string | null;
    confusionMatrix: ConfusionMatrix | null;
    scoreGoal: string | null;
    datasetClassDistribution?: Array<{ label: string; count: number }>;
    isDatasetClassDistributionBalanced: boolean | null;
    predictedClassDistribution?: Array<{ label: string; count: number }>;
    isPredictedClassDistributionBalanced: boolean | null;
    scoreResults: any[];
    task: TaskData | null;
  };
}

// Add these interfaces near the top of the file with other interfaces
interface TaskUpdateSubscriptionData {
  onUpdateTask: TaskData;
}

interface TaskStageUpdateSubscriptionData {
  onUpdateTaskStage: {
    id: string;
    taskId: string;
    name: string;
    order: number;
    status: string;
    statusMessage?: string;
    startedAt?: string;
    completedAt?: string;
    estimatedCompletionAt?: string;
    processedItems?: number;
    totalItems?: number;
  };
}

interface GetTaskQueryResponse {
  getTask: TaskData;
}

// Update the observeTaskUpdates function with proper types
function observeTaskUpdates(taskId: string, onUpdate: (task: TaskData) => void) {
  const subscriptions: { unsubscribe: () => void }[] = [];
  const currentClient = getClient();

  // Subscribe to task updates
  const taskSub = (currentClient.graphql({
    query: TASK_UPDATE_SUBSCRIPTION
  }) as unknown as { subscribe: Function }).subscribe({
    next: ({ data }: { data?: TaskUpdateSubscriptionData }) => {
      if (data?.onUpdateTask?.id === taskId) {
        // Transform the task data to match our TaskData type
        const updatedTask: TaskData = {
          id: data.onUpdateTask.id,
          accountId: data.onUpdateTask.accountId || '',
          type: data.onUpdateTask.type || '',
          status: data.onUpdateTask.status || '',
          target: data.onUpdateTask.target || '',
          command: data.onUpdateTask.command || '',
          description: data.onUpdateTask.description,
          dispatchStatus: data.onUpdateTask.dispatchStatus,
          metadata: data.onUpdateTask.metadata,
          createdAt: data.onUpdateTask.createdAt,
          startedAt: data.onUpdateTask.startedAt,
          completedAt: data.onUpdateTask.completedAt,
          estimatedCompletionAt: data.onUpdateTask.estimatedCompletionAt,
          errorMessage: data.onUpdateTask.errorMessage,
          errorDetails: data.onUpdateTask.errorDetails,
          currentStageId: data.onUpdateTask.currentStageId,
          stages: data.onUpdateTask.stages ? {
            items: data.onUpdateTask.stages.items.map(stage => ({
              id: stage.id,
              name: stage.name,
              order: stage.order,
              status: stage.status,
              statusMessage: stage.statusMessage,
              startedAt: stage.startedAt,
              completedAt: stage.completedAt,
              estimatedCompletionAt: stage.estimatedCompletionAt,
              processedItems: stage.processedItems,
              totalItems: stage.totalItems
            })),
            nextToken: null
          } : undefined
        };
        onUpdate(updatedTask);
      }
    },
    error: (error: Error) => {
      console.error('Error in task update subscription:', error);
    }
  });
  subscriptions.push(taskSub);

  // Subscribe to stage updates
  const stageSub = (currentClient.graphql({
    query: TASK_STAGE_UPDATE_SUBSCRIPTION
  }) as unknown as { subscribe: Function }).subscribe({
    next: ({ data }: { data?: TaskStageUpdateSubscriptionData }) => {
      if (data?.onUpdateTaskStage?.taskId === taskId) {
        // When a stage updates, fetch the full task to get all stages
        (async () => {
          try {
            const result = await (currentClient.graphql({
              query: `
                query GetTask($id: ID!) {
                  getTask(id: $id) {
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
              `,
              variables: { id: taskId }
            }) as Promise<{ data?: GetTaskQueryResponse }>);

            if (result.data?.getTask) {
              // Transform the task data to match our TaskData type
              const updatedTask: TaskData = {
                id: result.data.getTask.id,
                accountId: result.data.getTask.accountId || '',
                type: result.data.getTask.type || '',
                status: result.data.getTask.status || '',
                target: result.data.getTask.target || '',
                command: result.data.getTask.command || '',
                description: result.data.getTask.description,
                dispatchStatus: result.data.getTask.dispatchStatus,
                metadata: result.data.getTask.metadata,
                createdAt: result.data.getTask.createdAt,
                startedAt: result.data.getTask.startedAt,
                completedAt: result.data.getTask.completedAt,
                estimatedCompletionAt: result.data.getTask.estimatedCompletionAt,
                errorMessage: result.data.getTask.errorMessage,
                errorDetails: result.data.getTask.errorDetails,
                currentStageId: result.data.getTask.currentStageId,
                stages: result.data.getTask.stages ? {
                  items: result.data.getTask.stages.items.map(stage => ({
                    id: stage.id,
                    name: stage.name,
                    order: stage.order,
                    status: stage.status,
                    statusMessage: stage.statusMessage,
                    startedAt: stage.startedAt,
                    completedAt: stage.completedAt,
                    estimatedCompletionAt: stage.estimatedCompletionAt,
                    processedItems: stage.processedItems,
                    totalItems: stage.totalItems
                  })),
                  nextToken: null
                } : undefined
              };
              onUpdate(updatedTask);
            }
          } catch (error) {
            console.error('Error fetching updated task:', error);
          }
        })();
      }
    },
    error: (error: Error) => {
      console.error('Error in task stage update subscription:', error);
    }
  });
  subscriptions.push(stageSub);

  return {
    unsubscribe: () => {
      subscriptions.forEach(sub => sub.unsubscribe());
    }
  };
}

export default function EvaluationsDashboard(): JSX.Element {
  const { authStatus, user } = useAuthenticator(context => [context.authStatus]);
  const router = useRouter();
  
  const [evaluations, setEvaluations] = useState<NonNullable<Schema['Evaluation']['type']>[]>([]);
  const [selectedEvaluation, setSelectedEvaluation] = useState<Schema['Evaluation']['type'] | null>(null);
  const [scorecardNames, setScorecardNames] = useState<Record<string, string>>({});
  const [scoreNames, setScoreNames] = useState<Record<string, string>>({});
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null);
  const [selectedScore, setSelectedScore] = useState<string | null>(null);
  const [selectedScoreResultId, setSelectedScoreResultId] = useState<string | null>(null);
  const [isFullWidth, setIsFullWidth] = useState(false);
  const [leftPanelWidth, setLeftPanelWidth] = useState(50);
  const [hasMounted, setHasMounted] = useState(false);
  const [evaluationTaskProps, setEvaluationTaskProps] = useState<EvaluationTaskPropsInternal | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [accountId, setAccountId] = useState<string | null>(null);

  const selectedEvaluationRef = useRef<Schema['Evaluation']['type'] | null>(null)
  const dragStateRef = useRef<DragState>({
    isDragging: false,
    startX: 0,
    startWidth: 50
  })
  const containerRef = useRef<HTMLDivElement>(null)

  const isNarrowViewport = useViewportWidth()

  const filteredEvaluations = useMemo(() => {
    return evaluations.filter(Evaluation => {
      if (!selectedScorecard) return true
      return Evaluation.scorecardId === selectedScorecard
    })
  }, [evaluations, selectedScorecard])

  // Replace the EvaluationList memo with a grid layout
  const EvaluationGrid = useMemo(() => (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {filteredEvaluations.map((evaluation) => (
        <EvaluationCard
          key={evaluation.id}
          evaluation={evaluation}
          selectedEvaluationId={selectedEvaluation?.id ?? null}
          scorecardNames={scorecardNames}
          scoreNames={scoreNames}
          onSelect={(evaluation) => {
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
    </div>
  ), [filteredEvaluations, selectedEvaluation?.id, scorecardNames, scoreNames]);

  const EvaluationTaskComponent = useMemo(() => {
    if (!selectedEvaluation || !evaluationTaskProps) {
      console.log('Cannot render EvaluationTask:', {
        hasSelectedEvaluation: !!selectedEvaluation,
        hasTaskProps: !!evaluationTaskProps,
        selectedEvaluationId: selectedEvaluation?.id
      });
      return null;
    }
    
    console.log('Rendering EvaluationTask with props:', {
      taskId: evaluationTaskProps.id,
      taskType: evaluationTaskProps.type,
      hasTaskData: !!evaluationTaskProps.data,
      taskInData: evaluationTaskProps.data?.task ? {
        id: evaluationTaskProps.data.task.id,
        status: evaluationTaskProps.data.task.status,
        stagesCount: evaluationTaskProps.data.task.stages?.items?.length,
        stages: evaluationTaskProps.data.task.stages?.items?.map(s => ({
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
        task={{
          id: evaluationTaskProps.id,
          type: evaluationTaskProps.type,
          scorecard: evaluationTaskProps.scorecard,
          score: evaluationTaskProps.score,
          time: evaluationTaskProps.time,
          data: evaluationTaskProps.data
        }}
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
  }, [selectedEvaluation?.id, evaluationTaskProps, isFullWidth, selectedScoreResultId])

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

    if (selectedEvaluation?.id) {  // Add explicit check for id
      console.log('Setting up score results subscription for evaluation:', selectedEvaluation.id);
      
      const subscription = observeScoreResults(client, selectedEvaluation.id).subscribe({
        next: (data) => {
          if (!data?.items?.length) {
            console.log('No score results received:', { data });
            return;
          }
          
          try {
            const parsedResults = data.items.map(parseScoreResult);
            console.log('Parsed score results:', {
              count: parsedResults.length,
              firstResult: parsedResults[0],
              lastResult: parsedResults[parsedResults.length - 1]
            });

            // Update evaluationTaskProps with the new score results
            setEvaluationTaskProps(prevProps => {
              if (!prevProps) return null;
              return {
                ...prevProps,
                data: {
                  ...prevProps.data,
                  scoreResults: parsedResults
                }
              };
            });
          } catch (error) {
            console.error('Error processing score results:', error);
          }
        },
        error: (error) => {
          console.error('Error observing score results:', error);
        }
      });

      return () => {
        console.log('Cleaning up score results subscription');
        subscription.unsubscribe();
      };
    }
  }, [selectedEvaluation]);

  const handleEvaluationUpdate = useCallback(async (rawData: any) => {
    // Extract the actual evaluation data from the subscription response
    const data = rawData?.data?.onCreateEvaluation || 
                rawData?.data?.onUpdateEvaluation || 
                rawData?.data?.onDeleteEvaluation || 
                rawData;

    // Skip if we've already processed this update
    const updateId = data?.id;
    if (!updateId) {
      console.debug('Skipping invalid evaluation data:', rawData);
      return;
    }

    console.log('Processing evaluation update:', {
      id: data.id,
      type: data.type,
      status: data.status,
      processedItems: data.processedItems,
      totalItems: data.totalItems,
      accuracy: data.accuracy,
      updatedAt: data.updatedAt,
      isCreate: !!rawData?.data?.onCreateEvaluation,
      task: data.task ? {
        id: data.task.id,
        status: data.task.status,
        stagesCount: data.task.stages?.items?.length,
        stages: data.task.stages?.items?.map(s => ({
          name: s.name,
          status: s.status,
          processedItems: s.processedItems,
          totalItems: s.totalItems
        }))
      } : null
    });

    if (!accountId) return;

    // Transform the evaluation data
    const transformedEvaluation = transformEvaluation(data);
    
    // Load related data (scorecard and score names)
    const [loadedEvaluation] = await loadRelatedData(
      [transformedEvaluation],
      (newNames) => {
        setScorecardNames(prev => ({ ...prev, ...newNames }));
      },
      (newNames) => {
        setScoreNames(prev => ({ ...prev, ...newNames }));
      }
    );

    // Update evaluations list
    setEvaluations(prevEvaluations => {
      return prevEvaluations.map(evaluation => {
        if (evaluation.id === data.id) {
          return {
            ...evaluation,
            ...loadedEvaluation,
            // Preserve the async functions
            account: evaluation.account,
            scorecard: evaluation.scorecard,
            score: evaluation.score
          };
        }
        return evaluation;
      });
    });

    // Update selectedEvaluation and task props if this is the currently selected evaluation
    if (selectedEvaluation && data.id === selectedEvaluation.id) {
      const updatedEvaluation = {
        ...selectedEvaluation,
        ...loadedEvaluation,
        // Preserve the async functions
        account: selectedEvaluation.account,
        scorecard: selectedEvaluation.scorecard,
        score: selectedEvaluation.score
      };
      setSelectedEvaluation(updatedEvaluation);

      // Normalize task data
      let normalizedTaskData: TaskData | null = null;
      if (data.task) {
        normalizedTaskData = {
          id: data.task.id,
          accountId: data.task.accountId,
          type: data.task.type,
          status: data.task.status,
          target: data.task.target,
          command: data.task.command,
          completedAt: data.task.completedAt,
          startedAt: data.task.startedAt,
          dispatchStatus: data.task.dispatchStatus,
          celeryTaskId: data.task.celeryTaskId,
          workerNodeId: data.task.workerNodeId,
          stages: data.task.stages ? {
            items: data.task.stages.items?.map(stage => ({
              id: stage.id,
              name: stage.name,
              order: stage.order,
              status: stage.status,
              statusMessage: stage.statusMessage,
              startedAt: stage.startedAt,
              completedAt: stage.completedAt,
              estimatedCompletionAt: stage.estimatedCompletionAt,
              processedItems: stage.processedItems || 0,
              totalItems: stage.totalItems || 0
            })) || [],
            nextToken: null
          } : undefined
        };
      }

      // Parse metrics
      const rawMetrics = (() => {
        try {
          if (typeof updatedEvaluation.metrics === 'string') {
            return JSON.parse(updatedEvaluation.metrics);
          }
          if (Array.isArray(updatedEvaluation.metrics)) {
            return updatedEvaluation.metrics;
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

      // Parse confusion matrix
      console.log('Raw evaluation data:', {
        hasConfusionMatrix: !!updatedEvaluation.confusionMatrix,
        confusionMatrixType: typeof updatedEvaluation.confusionMatrix,
        rawValue: updatedEvaluation.confusionMatrix
      });

      const confusionMatrixData = (() => {
        try {
          if (!updatedEvaluation.confusionMatrix) return null;
          
          // First try to parse if it's a string
          let parsedMatrix = updatedEvaluation.confusionMatrix;
          if (typeof parsedMatrix === 'string') {
            try {
              parsedMatrix = JSON.parse(parsedMatrix);
            } catch (e) {
              console.error('Error parsing confusion matrix string:', e);
              return null;
            }
          }

          // Now check if the parsed data has the correct structure
          if (!parsedMatrix || !parsedMatrix.matrix || !parsedMatrix.labels) {
            console.error('Invalid confusion matrix structure:', parsedMatrix);
            return null;
          }

          // Validate the data types
          if (!Array.isArray(parsedMatrix.matrix) || !Array.isArray(parsedMatrix.labels)) {
            console.error('Invalid confusion matrix data types:', {
              matrixIsArray: Array.isArray(parsedMatrix.matrix),
              labelsIsArray: Array.isArray(parsedMatrix.labels)
            });
            return null;
          }

          return {
            matrix: parsedMatrix.matrix,
            labels: parsedMatrix.labels
          };
        } catch (e) {
          console.error('Error processing confusion matrix:', e);
          return null;
        }
      })();

      console.log('Raw Confusion Matrix:', updatedEvaluation.confusionMatrix);
      console.log('Parsed Confusion Matrix:', confusionMatrixData);

      // Update task props with the latest data
      const taskProps = {
        id: updatedEvaluation.id,
        type: updatedEvaluation.type,
        scorecard: scorecardNames[updatedEvaluation.id] || 'Unknown Scorecard',
        score: scoreNames[updatedEvaluation.id] || 'Unknown Score',
        time: updatedEvaluation.createdAt,
        data: {
          id: updatedEvaluation.id,
          title: scorecardNames[updatedEvaluation.id] || 'Unknown Scorecard',
          accuracy: updatedEvaluation.accuracy ?? null,
          metrics,
          metricsExplanation: updatedEvaluation.metricsExplanation ?? null,
          processedItems: normalizedTaskData?.stages?.items?.reduce((total, stage) => total + (stage.processedItems || 0), 0) ?? updatedEvaluation.processedItems ?? 0,
          totalItems: normalizedTaskData?.stages?.items?.reduce((total, stage) => total + (stage.totalItems || 0), 0) ?? updatedEvaluation.totalItems ?? 0,
          progress: calculateProgress(
            normalizedTaskData?.stages?.items?.reduce((total, stage) => total + (stage.processedItems || 0), 0) ?? updatedEvaluation.processedItems,
            normalizedTaskData?.stages?.items?.reduce((total, stage) => total + (stage.totalItems || 0), 0) ?? updatedEvaluation.totalItems
          ),
          inferences: updatedEvaluation.inferences ?? 0,
          cost: updatedEvaluation.cost ?? null,
          status: normalizedTaskData?.status || updatedEvaluation.status || '',
          elapsedSeconds: updatedEvaluation.elapsedSeconds ?? null,
          estimatedRemainingSeconds: updatedEvaluation.estimatedRemainingSeconds ?? null,
          startedAt: normalizedTaskData?.startedAt ?? updatedEvaluation.startedAt ?? null,
          errorMessage: normalizedTaskData?.errorMessage ?? updatedEvaluation.errorMessage ?? undefined,
          errorDetails: updatedEvaluation.errorDetails ?? null,
          confusionMatrix: confusionMatrixData,
          scoreGoal: updatedEvaluation.scoreGoal ?? null,
          datasetClassDistribution: Array.isArray(updatedEvaluation.datasetClassDistribution) 
            ? updatedEvaluation.datasetClassDistribution 
            : typeof updatedEvaluation.datasetClassDistribution === 'string'
              ? JSON.parse(updatedEvaluation.datasetClassDistribution)
              : undefined,
          isDatasetClassDistributionBalanced: updatedEvaluation.isDatasetClassDistributionBalanced ?? null,
          predictedClassDistribution: Array.isArray(updatedEvaluation.predictedClassDistribution)
            ? updatedEvaluation.predictedClassDistribution
            : typeof updatedEvaluation.predictedClassDistribution === 'string'
              ? JSON.parse(updatedEvaluation.predictedClassDistribution)
              : undefined,
          isPredictedClassDistributionBalanced: updatedEvaluation.isPredictedClassDistributionBalanced ?? null,
          scoreResults: evaluationTaskProps?.data?.scoreResults ?? [],
          task: normalizedTaskData
        }
      };

      console.log('Updating task props:', {
        id: taskProps.id,
        status: taskProps.data.status,
        taskStatus: taskProps.data.task?.status,
        stageCount: taskProps.data.task?.stages?.items?.length,
        stages: taskProps.data.task?.stages?.items?.map(s => ({
          name: s.name,
          status: s.status,
          processedItems: s.processedItems,
          totalItems: s.totalItems
        }))
      });

      setEvaluationTaskProps(taskProps);
    }
  }, [accountId, selectedEvaluation, scorecardNames, scoreNames]);

  // Add ref to track last update time for each evaluation
  const lastUpdateRef = useRef<Record<string, string>>({});

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

        const transformedEvaluations = await loadRelatedData(
          evaluations,
          setScorecardNames,
          setScoreNames
        );

        setEvaluations(transformedEvaluations);
        setIsLoading(false);

        // Track existing evaluation IDs to prevent duplicates
        const existingIds = new Set(transformedEvaluations.map(e => e.id));

        // Set up subscriptions using Amplify Gen2 pattern
        const createSub = client.graphql({
          query: `
            subscription OnCreateEvaluation {
              onCreateEvaluation {
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
                  nextToken
                }
              }
            }
          `
        }).subscribe({
          next: async ({ data }) => {
            if (data?.onCreateEvaluation) {
              const evaluationId = data.onCreateEvaluation.id;
              
              // Skip if we've already seen this ID
              if (existingIds.has(evaluationId)) {
                console.log('Skipping duplicate create event:', evaluationId);
                return;
              }

              console.log('Processing new create event:', {
                id: evaluationId,
                type: data.onCreateEvaluation.type,
                status: data.onCreateEvaluation.status,
                alreadyExists: existingIds.has(evaluationId)
              });

              // Add to tracking set
              existingIds.add(evaluationId);

              // Transform the evaluation
              const transformedEvaluation = transformEvaluation(data.onCreateEvaluation);
              
              // Load related data and update names
              const [loadedEvaluation] = await loadRelatedData(
                [transformedEvaluation],
                (newNames) => {
                  setScorecardNames(prevNames => ({ ...prevNames, ...newNames }));
                },
                (newNames) => {
                  setScoreNames(prevNames => ({ ...prevNames, ...newNames }));
                }
              );

              // Update evaluations list
              setEvaluations(prev => {
                // Double check one more time in case another update snuck in
                if (prev.some(e => e.id === evaluationId)) {
                  console.log('Evaluation was added by another update:', evaluationId);
                  return prev;
                }
                return [loadedEvaluation, ...prev];
              });
            }
          },
          error: (error) => console.error('Create subscription error:', error)
        });

        const updateSub = client.graphql({
          query: `
            subscription OnUpdateEvaluation {
              onUpdateEvaluation {
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
                  nextToken
                }
              }
            }
          `
        }).subscribe({
          next: async ({ data }) => {
            if (data?.onUpdateEvaluation) {
              console.log('Received update event:', {
                id: data.onUpdateEvaluation.id,
                type: data.onUpdateEvaluation.type,
                status: data.onUpdateEvaluation.status
              });
              
              // Transform the evaluation
              const transformedEvaluation = transformEvaluation(data.onUpdateEvaluation);
              
              // Load related data
              const [loadedEvaluation] = await loadRelatedData(
                [transformedEvaluation],
                (newNames) => {
                  setScorecardNames(prev => ({ ...prev, ...newNames }));
                },
                (newNames) => {
                  setScoreNames(prev => ({ ...prev, ...newNames }));
                }
              );

              // Update the existing evaluation in the list
              setEvaluations(prev => {
                const index = prev.findIndex(e => e.id === data.onUpdateEvaluation.id);
                if (index >= 0) {
                  const updated = [...prev];
                  updated[index] = {
                    ...loadedEvaluation,
                    // Preserve async functions
                    account: prev[index].account,
                    scorecard: prev[index].scorecard,
                    score: prev[index].score
                  };
                  return updated;
                }
                return prev;
              });

              // Update selected evaluation if this is the one being viewed
              if (selectedEvaluation?.id === data.onUpdateEvaluation.id) {
                setSelectedEvaluation(loadedEvaluation);
              }
            }
          },
          error: (error) => console.error('Update subscription error:', error)
        });

        const deleteSub = client.graphql({
          query: `
            subscription OnDeleteEvaluation {
              onDeleteEvaluation {
                id
                type
                accountId
                updatedAt
              }
            }
          `
        }).subscribe({
          next: ({ data }) => {
            if (data?.onDeleteEvaluation) {
              console.log('Received delete event:', {
                id: data.onDeleteEvaluation.id
              });
              
              // Remove the evaluation from the list
              setEvaluations(prev => prev.filter(e => e.id !== data.onDeleteEvaluation.id));
              
              // Clear selected evaluation if it was deleted
              if (selectedEvaluation?.id === data.onDeleteEvaluation.id) {
                setSelectedEvaluation(null);
              }
            }
          },
          error: (error) => console.error('Delete subscription error:', error)
        });

        return () => {
          createSub.unsubscribe();
          updateSub.unsubscribe();
          deleteSub.unsubscribe();
          // Clear the last update ref on cleanup
          lastUpdateRef.current = {};
        };

      } catch (error) {
        console.error('Error loading initial data:', error);
        setError(error instanceof Error ? error : new Error('Failed to load initial data'));
        setIsLoading(false);
      }
    };

    loadInitialData();

    // No cleanup needed here as it's handled in the async function
    return undefined;
  }, []); // Keep empty dependency array

  // Fix the endless loop by memoizing the stage configs
  const getStageConfigs = useCallback((stages?: { items?: any[] }) => {
    if (!stages?.items) return [];
    return stages.items.map((stage) => ({
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
  }, []);

  useEffect(() => {
    const updateTaskProps = async () => {
      if (!selectedEvaluation) return;

      let normalizedTaskData: TaskData | null = null;
      if (typeof selectedEvaluation.task === 'function') {
        try {
          const taskResult = await selectedEvaluation.task();
          normalizedTaskData = taskResult.data as TaskData;
        } catch (error) {
          console.error('Error getting task data:', error);
          normalizedTaskData = null;
        }
      } else {
        normalizedTaskData = selectedEvaluation.task as TaskData;
      }

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

      const confusionMatrixData = selectedEvaluation.confusionMatrix ? {
        matrix: Array.isArray(selectedEvaluation.confusionMatrix.matrix) 
          ? selectedEvaluation.confusionMatrix.matrix 
          : null,
        labels: Array.isArray(selectedEvaluation.confusionMatrix.labels)
          ? selectedEvaluation.confusionMatrix.labels
          : null
      } : null;

      // Reset score results when switching evaluations
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
          processedItems: normalizedTaskData?.stages?.items?.reduce((total, stage) => total + (stage.processedItems || 0), 0) ?? selectedEvaluation.processedItems ?? 0,
          totalItems: normalizedTaskData?.stages?.items?.reduce((total, stage) => total + (stage.totalItems || 0), 0) ?? selectedEvaluation.totalItems ?? 0,
          progress: calculateProgress(
            normalizedTaskData?.stages?.items?.reduce((total, stage) => total + (stage.processedItems || 0), 0) ?? selectedEvaluation.processedItems,
            normalizedTaskData?.stages?.items?.reduce((total, stage) => total + (stage.totalItems || 0), 0) ?? selectedEvaluation.totalItems
          ),
          inferences: selectedEvaluation.inferences ?? 0,
          cost: selectedEvaluation.cost ?? null,
          status: normalizedTaskData?.status || selectedEvaluation.status || '',
          elapsedSeconds: selectedEvaluation.elapsedSeconds ?? null,
          estimatedRemainingSeconds: selectedEvaluation.estimatedRemainingSeconds ?? null,
          startedAt: normalizedTaskData?.startedAt ?? selectedEvaluation.startedAt ?? null,
          errorMessage: normalizedTaskData?.errorMessage ?? selectedEvaluation.errorMessage ?? undefined,
          errorDetails: selectedEvaluation.errorDetails ?? null,
          confusionMatrix: confusionMatrixData,
          scoreGoal: selectedEvaluation.scoreGoal ?? null,
          datasetClassDistribution: Array.isArray(selectedEvaluation.datasetClassDistribution) 
            ? selectedEvaluation.datasetClassDistribution 
            : typeof selectedEvaluation.datasetClassDistribution === 'string'
              ? JSON.parse(selectedEvaluation.datasetClassDistribution)
              : undefined,
          isDatasetClassDistributionBalanced: selectedEvaluation.isDatasetClassDistributionBalanced ?? null,
          predictedClassDistribution: Array.isArray(selectedEvaluation.predictedClassDistribution)
            ? selectedEvaluation.predictedClassDistribution
            : typeof selectedEvaluation.predictedClassDistribution === 'string'
              ? JSON.parse(selectedEvaluation.predictedClassDistribution)
              : undefined,
          isPredictedClassDistributionBalanced: selectedEvaluation.isPredictedClassDistributionBalanced ?? null,
          scoreResults: [], // Initialize with empty array when switching evaluations
          task: normalizedTaskData
        }
      };

      setEvaluationTaskProps(taskProps);
    };

    updateTaskProps();
  }, [selectedEvaluation, scorecardNames, scoreNames]);

  // Update the task update handling section
  useEffect(() => {
    if (!selectedEvaluation?.task) return;

    let taskId: string | null = null;
    let subscription: { unsubscribe: () => void } | null = null;
    
    const getTaskId = async () => {
      if (typeof selectedEvaluation.task === 'function') {
        const result = await selectedEvaluation.task();
        if (result.data?.id) {
          taskId = result.data.id;
          setupTaskSubscription(taskId);
        }
      } else {
        const task = selectedEvaluation.task as unknown as TaskData;
        taskId = task.id;
        setupTaskSubscription(taskId);
      }
    };

    function setupTaskSubscription(id: string) {
      subscription = observeTaskUpdates(id, (updatedTask) => {
        console.log('Task update received:', {
          taskId: updatedTask.id,
          status: updatedTask.status,
          stageCount: updatedTask.stages?.items?.length,
          stages: updatedTask.stages?.items?.map(s => ({
            name: s.name,
            status: s.status,
            processedItems: s.processedItems,
            totalItems: s.totalItems
          }))
        });

        // Batch update both states together
        const processedItems = updatedTask.stages?.items?.reduce((total, stage) => total + (stage.processedItems || 0), 0);
        const totalItems = updatedTask.stages?.items?.reduce((total, stage) => total + (stage.totalItems || 0), 0);

        console.log('Calculated task totals:', {
          processedItems,
          totalItems,
          hasStages: !!updatedTask.stages?.items?.length
        });

        setSelectedEvaluation(prev => {
          if (!prev) return null;

          // Create updated evaluation with resolved task data
          const updated = {
            ...prev,
            task: updatedTask,
            status: updatedTask.status || prev.status,
            processedItems: processedItems || prev.processedItems,
            totalItems: totalItems || prev.totalItems,
            startedAt: updatedTask.startedAt || prev.startedAt
          };

          console.log('Updating selected evaluation:', {
            id: updated.id,
            status: updated.status,
            taskStatus: updated.task?.status,
            processedItems: updated.processedItems,
            totalItems: updated.totalItems
          });

          // Immediately update task props to stay in sync
          if (evaluationTaskProps) {
            const updatedTaskProps: EvaluationTaskPropsInternal = {
              ...evaluationTaskProps,
              data: {
                ...evaluationTaskProps.data,
                task: updatedTask,
                processedItems: processedItems || evaluationTaskProps.data.processedItems,
                totalItems: totalItems || evaluationTaskProps.data.totalItems,
                status: updatedTask.status || evaluationTaskProps.data.status,
                startedAt: updatedTask.startedAt || evaluationTaskProps.data.startedAt,
                progress: calculateProgress(processedItems, totalItems)
              }
            };

            console.log('Updating evaluation task props:', {
              id: updatedTaskProps.id,
              status: updatedTaskProps.data.status,
              taskStatus: updatedTaskProps.data.task?.status,
              processedItems: updatedTaskProps.data.processedItems,
              totalItems: updatedTaskProps.data.totalItems,
              progress: updatedTaskProps.data.progress
            });

            setEvaluationTaskProps(updatedTaskProps);
          }

          return updated;
        });
      });
    }

    getTaskId();

    return () => {
      if (subscription) {
        subscription.unsubscribe();
      }
    };
  }, [selectedEvaluation?.id, evaluationTaskProps]);

  useEffect(() => {
    if (!accountId) return;

    const currentClient = getClient();
    const subscriptions: { unsubscribe: () => void }[] = [];

    // Subscribe to evaluation updates
    const evaluationSub = (currentClient.graphql({
      query: EVALUATION_UPDATE_SUBSCRIPTION
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onUpdateEvaluation: Schema['Evaluation']['type'] } }) => {
        if (data?.onUpdateEvaluation) {
          const updatedEvaluation = transformEvaluation(data.onUpdateEvaluation);
          if (updatedEvaluation) {
            setEvaluations(prev => {
              const index = prev.findIndex(e => e.id === updatedEvaluation.id);
              if (index === -1) return prev;
              const newEvaluations = [...prev];
              newEvaluations[index] = updatedEvaluation;
              return newEvaluations;
            });

            // Update selected evaluation if it's the one being updated
            if (selectedEvaluation?.id === updatedEvaluation.id) {
              setSelectedEvaluation(updatedEvaluation);
            }
          }
        }
      },
      error: (error: Error) => {
        console.error('Error in evaluation update subscription:', error);
      }
    });
    subscriptions.push(evaluationSub);

    // Subscribe to task updates
    const taskSub = (currentClient.graphql({
      query: TASK_UPDATE_SUBSCRIPTION
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onUpdateTask: TaskData } }) => {
        if (data?.onUpdateTask) {
          const updatedTask = data.onUpdateTask;
          
          // Transform stages for TaskStatus component
          const transformedStages = updatedTask.stages?.items?.map(stage => ({
            key: stage.name,
            label: stage.name,
            color: stage.name.toLowerCase() === 'processing' ? 'bg-secondary' : 'bg-primary',
            name: stage.name,
            order: stage.order,
            status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
            processedItems: stage.processedItems ?? undefined,
            totalItems: stage.totalItems ?? undefined,
            startedAt: stage.startedAt ?? undefined,
            completedAt: stage.completedAt ?? undefined,
            estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
            statusMessage: stage.statusMessage ?? undefined
          })) || [];

          // Get current stage info
          const currentStage = transformedStages.length > 0 ? 
            transformedStages.reduce((current, stage) => {
              if (!current) return stage;
              
              if (updatedTask.status === 'COMPLETED') {
                return stage.order > current.order ? stage : current;
              }
              
              if (stage.status === 'RUNNING') return stage;
              if (current.status === 'RUNNING') return current;
              
              if (stage.status === 'PENDING' && current.status === 'PENDING') {
                return stage.order < current.order ? stage : current;
              }
              
              if (stage.status === 'PENDING') return stage;
              if (current.status === 'PENDING') return current;
              
              return stage.order > current.order ? stage : current;
            }, null) : null;

          setEvaluations(prev => {
            return prev.map(evaluation => {
              if (evaluation.task && typeof evaluation.task !== 'function' && evaluation.task.id === updatedTask.id) {
                return {
                  ...evaluation,
                  task: {
                    ...updatedTask,
                    stages: {
                      items: transformedStages
                    }
                  },
                  processedItems: currentStage?.processedItems ?? 0,
                  totalItems: currentStage?.totalItems ?? 0
                };
              }
              return evaluation;
            });
          });

          // Update selected evaluation if its task was updated
          if (selectedEvaluation?.task && typeof selectedEvaluation.task !== 'function' && selectedEvaluation.task.id === updatedTask.id) {
            setSelectedEvaluation(prev => prev ? {
              ...prev,
              task: {
                ...updatedTask,
                stages: {
                  items: transformedStages
                }
              },
              processedItems: currentStage?.processedItems ?? 0,
              totalItems: currentStage?.totalItems ?? 0
            } : null);
          }
        }
      },
      error: (error: Error) => {
        console.error('Error in task update subscription:', error);
      }
    });
    subscriptions.push(taskSub);

    // Subscribe to task stage updates
    const stageSub = (currentClient.graphql({
      query: TASK_STAGE_UPDATE_SUBSCRIPTION
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onUpdateTaskStage: TaskStageUpdateSubscriptionData['onUpdateTaskStage'] } }) => {
        if (data?.onUpdateTaskStage) {
          // When a stage updates, fetch the full task to get all stages
          (async () => {
            try {
              const result = await currentClient.graphql({
                query: `
                  query GetTask($id: ID!) {
                    getTask(id: $id) {
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
                `,
                variables: {
                  id: data.onUpdateTaskStage.taskId
                }
              });

              if (result.data?.getTask) {
                const updatedTask = result.data.getTask;
                
                // Transform stages for TaskStatus component
                const transformedStages = updatedTask.stages?.items?.map(stage => ({
                  key: stage.name,
                  label: stage.name,
                  color: stage.name.toLowerCase() === 'processing' ? 'bg-secondary' : 'bg-primary',
                  name: stage.name,
                  order: stage.order,
                  status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
                  processedItems: stage.processedItems ?? undefined,
                  totalItems: stage.totalItems ?? undefined,
                  startedAt: stage.startedAt ?? undefined,
                  completedAt: stage.completedAt ?? undefined,
                  estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
                  statusMessage: stage.statusMessage ?? undefined
                })) || [];

                // Get current stage info
                const currentStage = transformedStages.length > 0 ? 
                  transformedStages.reduce((current, stage) => {
                    if (!current) return stage;
                    
                    if (updatedTask.status === 'COMPLETED') {
                      return stage.order > current.order ? stage : current;
                    }
                    
                    if (stage.status === 'RUNNING') return stage;
                    if (current.status === 'RUNNING') return current;
                    
                    if (stage.status === 'PENDING' && current.status === 'PENDING') {
                      return stage.order < current.order ? stage : current;
                    }
                    
                    if (stage.status === 'PENDING') return stage;
                    if (current.status === 'PENDING') return current;
                    
                    return stage.order > current.order ? stage : current;
                  }, null) : null;

                setEvaluations(prev => {
                  return prev.map(evaluation => {
                    if (evaluation.task && typeof evaluation.task !== 'function' && evaluation.task.id === updatedTask.id) {
                      return {
                        ...evaluation,
                        task: {
                          ...updatedTask,
                          stages: {
                            items: transformedStages
                          }
                        },
                        processedItems: currentStage?.processedItems ?? 0,
                        totalItems: currentStage?.totalItems ?? 0
                      };
                    }
                    return evaluation;
                  });
                });

                // Update selected evaluation if its task was updated
                if (selectedEvaluation?.task && typeof selectedEvaluation.task !== 'function' && selectedEvaluation.task.id === updatedTask.id) {
                  setSelectedEvaluation(prev => prev ? {
                    ...prev,
                    task: {
                      ...updatedTask,
                      stages: {
                        items: transformedStages
                      }
                    },
                    processedItems: currentStage?.processedItems ?? 0,
                    totalItems: currentStage?.totalItems ?? 0
                  } : null);
                }
              }
            } catch (error) {
              console.error('Error fetching updated task:', error);
            }
          })();
        }
      },
      error: (error: Error) => {
        console.error('Error in task stage update subscription:', error);
      }
    });
    subscriptions.push(stageSub);

    return () => {
      subscriptions.forEach(sub => sub.unsubscribe());
    };
  }, [accountId, selectedEvaluation?.id]);

  if (authStatus !== 'authenticated') {
    return <EvaluationDashboardSkeleton />;
  }

  if (!hasMounted) {
    return <EvaluationDashboardSkeleton />;
  }

  if (error) {
    return (
      <div className="p-4 text-red-500">
        Error loading Evaluations: {error.message}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full p-1.5">
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
      <div className="flex h-full">
        <div 
          className={`
            ${selectedEvaluation && !isNarrowViewport && !isFullWidth ? '' : 'w-full'}
            ${selectedEvaluation && !isNarrowViewport && isFullWidth ? 'hidden' : ''}
            h-full overflow-auto
          `}
          style={selectedEvaluation && !isNarrowViewport && !isFullWidth ? {
            width: `${leftPanelWidth}%`
          } : undefined}
        >
          {EvaluationGrid}
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
        
        {selectedEvaluation && evaluationTaskProps && (
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
  );
}

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
