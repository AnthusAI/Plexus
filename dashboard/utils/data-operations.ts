import { generateClient } from 'aws-amplify/data';
import { GraphQLResult, GraphQLSubscription } from '@aws-amplify/api';
import type { Schema } from '../amplify/data/resource';
import { Observable } from 'rxjs';
import { LazyLoader } from './types';
import type { BaseTaskData, BaseActivity } from '../types/base';
import type { BatchJobTaskData, EvaluationTaskData, ActivityData } from '../types/tasks';
import { getClient } from './amplify-client';
export { getClient };
import { TASK_UPDATE_SUBSCRIPTION } from '../graphql/evaluation-queries';
import { Hub } from 'aws-amplify/utils';
import type { ScoreResult } from "@/types/evaluation";
import type { AmplifyListResult } from "@/types/shared";

// Define base types for nested objects
type TaskStageType = {
  id: string;
  name: string;
  order: number;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  processedItems?: number;
  totalItems?: number;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  statusMessage?: string;
};

type EvaluationType = {
  id: string;
  type: string;
  metrics: any;
  metricsExplanation?: string;
  inferences: number;
  accuracy: number;
  cost: number | null;
  status: string;
  startedAt?: string;
  elapsedSeconds: number | null;
  estimatedRemainingSeconds: number | null;
  totalItems: number;
  processedItems: number;
  errorMessage?: string;
  errorDetails?: any;
  confusionMatrix?: any;
  scoreGoal?: string;
  datasetClassDistribution?: any;
  isDatasetClassDistributionBalanced?: boolean;
  predictedClassDistribution?: any;
  isPredictedClassDistributionBalanced?: boolean;
  scoreResults?: {
    items?: Array<{
      id: string;
      value: string | number;
      confidence: number | null;
      metadata: any;
      explanation: string | null;
      itemId: string | null;
      createdAt: string;
    }>;
  };
};

// Update AmplifyTask type to properly handle lazy-loaded properties
export type AmplifyTask = {
  id: string;
  command: string;
  type: string;
  status: string;
  target: string;
  description?: string | null;
  metadata?: any;  // Simplified to match API's JSON field
  createdAt?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
  estimatedCompletionAt?: string | null;
  errorMessage?: string | null;
  errorDetails?: any;
  stdout?: string | null;
  stderr?: string | null;
  currentStageId?: string | null;
  stages?: LazyLoader<{
    data?: {
      items: TaskStageType[];
    } | null;
  }>;
  dispatchStatus?: string | null;
  celeryTaskId?: string | null;
  workerNodeId?: string | null;
  updatedAt?: string | null;
  scorecardId?: string | null;
  scoreId?: string | null;
  scorecard?: LazyLoader<{
    data?: {
      id: string;
      name: string;
    } | null;
  }>;
  score?: LazyLoader<{
    data?: {
      id: string;
      name: string;
    } | null;
  }>;
  evaluation?: LazyLoader<{
    data?: {
      id: string;
      type: string;
      metrics: any;
      metricsExplanation?: string;
      inferences: number;
      accuracy: number;
      cost: number | null;
      status: string;
      startedAt?: string;
      elapsedSeconds: number | null;
      estimatedRemainingSeconds: number | null;
      totalItems: number;
      processedItems: number;
      errorMessage?: string;
      errorDetails?: any;
      confusionMatrix?: any;
      scoreGoal?: string;
      datasetClassDistribution?: any;
      isDatasetClassDistributionBalanced?: boolean;
      predictedClassDistribution?: any;
      isPredictedClassDistributionBalanced?: boolean;
      scoreResults?: {
        data?: {
          items?: Array<{
            id: string;
            value: string | number;
            confidence: number | null;
            metadata: any;
            explanation: string | null;
            itemId: string | null;
            createdAt: string;
          }>;
        } | null;
      };
    } | null;
  }>;
};

export type ProcessedTask = {
  id: string;
  command: string;
  type: string;
  status: string;
  target: string;
  description?: string;
  metadata?: Record<string, unknown> | null;
  createdAt?: string;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  errorMessage?: string;
  errorDetails?: string;
  stdout?: string;
  stderr?: string;
  currentStageId?: string;
  stages: ProcessedTaskStage[];
  dispatchStatus?: 'DISPATCHED';
  celeryTaskId?: string;
  workerNodeId?: string;
  updatedAt?: string;  // Add updatedAt field
  scorecardId?: string;
  scoreId?: string;
  scorecard?: {
    id: string;
    name: string;
  };
  score?: {
    id: string;
    name: string;
  };
  evaluation?: {
    id: string;
    type: string;
    metrics: any;
    metricsExplanation?: string | null;
    inferences: number;
    accuracy: number | null;
    cost: number | null;
    status: string;
    startedAt?: string;
    elapsedSeconds: number | null;
    estimatedRemainingSeconds: number | null;
    totalItems: number;
    processedItems: number;
    errorMessage?: string;
    errorDetails?: any;
    confusionMatrix?: any;
    scoreGoal?: string;
    datasetClassDistribution?: any;
    isDatasetClassDistributionBalanced?: boolean;
    predictedClassDistribution?: any;
    isPredictedClassDistributionBalanced?: boolean;
    scoreResults?: {
      items?: Array<{
        id: string;
        value: string | number;
        confidence: number | null;
        metadata: any;
        explanation: string | null;
        itemId: string | null;
        createdAt: string;
      }>;
    };
  };
};

export type ProcessedTaskStage = {
  id: string;
  name: string;
  order: number;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  processedItems?: number;
  totalItems?: number;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  statusMessage?: string;
};

type AmplifyClient = ReturnType<typeof generateClient<Schema>> & {
  graphql: {
    query: (options: { query: string }) => Promise<GraphQLResult<any>>;
    subscribe: (options: { query: string }) => {
      subscribe: (handlers: SubscriptionHandler<any>) => { unsubscribe: () => void };
    };
  };
  models: {
    Task: {
      list: (options: { 
        limit?: number; 
        include?: string[];
      }) => Promise<{
        data: Array<Schema['Task']['type']>;
        nextToken?: string | null;
      }>;
    };
    TaskStage: {
      onUpdate: (options: {}) => { subscribe: (handlers: { next: () => void; error: (error: any) => void }) => { unsubscribe: () => void } };
    };
    Evaluation: {
      list: (options: any) => Promise<AmplifyListResult<Schema['Evaluation']['type']>>;
      listEvaluationByAccountIdAndUpdatedAt: (options: {
        accountId: string;
        sortDirection?: 'ASC' | 'DESC';
        limit?: number;
        nextToken?: string;
      }) => Promise<AmplifyListResult<Schema['Evaluation']['type']>>;
    };
  };
}

export type ModelListResult<T> = {
  items: T[];
  nextToken?: string | null;
};

let client: AmplifyClient;

// Add back the type definitions at the top
interface GraphQLError {
  message: string;
  path?: string[];
}

type ListTaskResponse = {
  listTaskByAccountIdAndUpdatedAt: {
    items: Schema['Task']['type'][];
    nextToken: string | null;
  };
};

// Add GraphQL response types
type GraphQLResponse<T> = {
  data?: T;
  errors?: Array<{
    message: string;
    locations?: Array<{
      line: number;
      column: number;
    }>;
    path?: string[];
  }>;
};

// Update the subscription type to match activity dashboard
type SubscriptionResponse<T> = {
  data: T;
};

// Add a type for the subscription handler
type SubscriptionHandler<T> = {
  next: (response: SubscriptionResponse<T>) => void;
  error: (error: any) => void;
};

// Add a type guard for GraphQL results
function isGraphQLResult<T>(response: GraphQLResult<T> | GraphQLSubscription<T>): response is GraphQLResult<T> {
  return !('subscribe' in response);
}

export async function listFromModel<T>(
  modelName: keyof AmplifyClient['models'],
  options?: {
    limit?: number,
    filter?: Record<string, any>,
    nextToken?: string,
    sortDirection?: 'ASC' | 'DESC'
  }
): Promise<{ data?: T[], nextToken?: string }> {
  const currentClient = getClient();
  
  try {
    const response = await (currentClient.models[modelName] as any).list({
      limit: options?.limit,
      filter: options?.filter,
      nextToken: options?.nextToken,
      sortDirection: options?.sortDirection,
      include: modelName === 'Task' ? ['stages', 'scorecard', 'score'] : undefined
    });

    return {
      data: response.data,
      nextToken: response.nextToken
    };
  } catch (error) {
    console.error(`Error in listFromModel for ${modelName}:`, error);
    return { data: [] };
  }
}

// Helper function to safely get value from a LazyLoader
export function getValueFromLazyLoader<T>(loader: LazyLoader<T>): T | undefined {
  if (!loader) return undefined;
  if (typeof loader === 'function') {
    return undefined; // We can't synchronously get the value from a promise
  }
  return loader;
}

export async function unwrapLazyLoader<T>(loader: LazyLoader<T>): Promise<T> {
  if (!loader) return Promise.reject(new Error('Loader is null or undefined'));
  if (typeof loader === 'function') {
    return (loader as () => Promise<T>)();
  }
  return loader;
}

export async function transformAmplifyTask(task: AmplifyTask): Promise<ProcessedTask> {
  console.debug('transformAmplifyTask input:', {
    taskId: task.id,
    hasStages: !!task.stages,
    stagesType: task.stages ? typeof task.stages : 'undefined',
    rawStages: task.stages,
    hasEvaluation: !!task.evaluation,
    evaluationData: task.evaluation
  });

  // Handle stages
  const stages: ProcessedTaskStage[] = (typeof task.stages === 'function' ? 
    [] : // Can't synchronously get data from a promise
    task.stages?.data?.items?.map((stage: TaskStageType) => ({
      id: stage.id,
      name: stage.name,
      order: stage.order,
      status: (stage.status ?? 'PENDING') as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
      processedItems: stage.processedItems ?? undefined,
      totalItems: stage.totalItems ?? undefined,
      startedAt: stage.startedAt ?? undefined,
      completedAt: stage.completedAt ?? undefined,
      estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
      statusMessage: stage.statusMessage ?? undefined
    }))) ?? [];

  // Convert metadata from string to JSON object if needed
  let processedMetadata: Record<string, unknown> | null = null;
  if (task.metadata) {
    try {
      processedMetadata = task.metadata;  // Already a JSON object from API
    } catch (e) {
      console.error('Error handling metadata:', e);
      processedMetadata = null;
    }
  }

  // Transform evaluation data if present
  let evaluation = undefined;
  if (task.evaluation) {
    try {
      const evaluationData = typeof task.evaluation === 'function' ? 
        await task.evaluation() : task.evaluation;

      // Parse metrics if it's a string
      let metrics = evaluationData.data?.metrics;
      try {
        if (typeof metrics === 'string') {
          metrics = JSON.parse(metrics);
        }
      } catch (e) {
        console.error('Error parsing metrics:', e);
      }

      // Parse confusion matrix if it's a string
      let confusionMatrix = evaluationData.data?.confusionMatrix;
      try {
        if (typeof confusionMatrix === 'string') {
          confusionMatrix = JSON.parse(confusionMatrix);
        }
      } catch (e) {
        console.error('Error parsing confusion matrix:', e);
      }

      // Parse dataset class distribution if it's a string
      let datasetClassDistribution = evaluationData.data?.datasetClassDistribution;
      try {
        if (typeof datasetClassDistribution === 'string') {
          datasetClassDistribution = JSON.parse(datasetClassDistribution);
        }
      } catch (e) {
        console.error('Error parsing dataset class distribution:', e);
      }

      // Parse predicted class distribution if it's a string
      let predictedClassDistribution = evaluationData.data?.predictedClassDistribution;
      try {
        if (typeof predictedClassDistribution === 'string') {
          predictedClassDistribution = JSON.parse(predictedClassDistribution);
        }
      } catch (e) {
        console.error('Error parsing predicted class distribution:', e);
      }

      evaluation = evaluationData?.data?.id && evaluationData.data.type ? {
        id: evaluationData.data.id,
        type: evaluationData.data.type,
        metrics: metrics,
        metricsExplanation: evaluationData.data.metricsExplanation ?? undefined,
        inferences: Number(evaluationData.data.inferences) || 0,
        accuracy: typeof evaluationData.data.accuracy === 'number' ? evaluationData.data.accuracy : null,
        cost: evaluationData.data.cost ?? null,
        status: evaluationData.data.status || 'PENDING',
        startedAt: evaluationData.data.startedAt,
        elapsedSeconds: evaluationData.data.elapsedSeconds ?? null,
        estimatedRemainingSeconds: evaluationData.data.estimatedRemainingSeconds ?? null,
        totalItems: Number(evaluationData.data.totalItems) || 0,
        processedItems: Number(evaluationData.data.processedItems) || 0,
        errorMessage: evaluationData.data.errorMessage,
        errorDetails: evaluationData.data.errorDetails,
        confusionMatrix,
        scoreGoal: evaluationData.data.scoreGoal,
        datasetClassDistribution,
        isDatasetClassDistributionBalanced: evaluationData.data.isDatasetClassDistributionBalanced,
        predictedClassDistribution,
        isPredictedClassDistributionBalanced: evaluationData.data.isPredictedClassDistributionBalanced,
        scoreResults: evaluationData.data.scoreResults?.data?.items ? {
          items: evaluationData.data.scoreResults.data.items.map(item => ({
            id: item.id,
            value: item.value,
            confidence: item.confidence ?? null,
            metadata: item.metadata,
            explanation: item.explanation ?? null,
            itemId: item.itemId,
            createdAt: item.createdAt
          }))
        } : undefined
      } : undefined;
    } catch (error) {
      console.error('Error transforming evaluation data:', error);
    }
  }

  // Handle scorecard and score
  const scorecard = task.scorecard ? await unwrapLazyLoader(task.scorecard) : undefined;
  
  const score = task.score ? await unwrapLazyLoader(task.score) : undefined;

  return {
    id: task.id,
    command: task.command,
    type: task.type,
    status: task.status,
    target: task.target,
    description: task.description ?? undefined,
    metadata: processedMetadata,
    createdAt: task.createdAt ?? undefined,
    startedAt: task.startedAt ?? undefined,
    completedAt: task.completedAt ?? undefined,
    estimatedCompletionAt: task.estimatedCompletionAt ?? undefined,
    errorMessage: task.errorMessage ?? undefined,
    errorDetails: typeof task.errorDetails === 'string' ? task.errorDetails : JSON.stringify(task.errorDetails ?? null),
    stdout: task.stdout ?? undefined,
    stderr: task.stderr ?? undefined,
    currentStageId: task.currentStageId ?? undefined,
    stages,
    dispatchStatus: task.dispatchStatus === 'DISPATCHED' ? 'DISPATCHED' : undefined,
    celeryTaskId: task.celeryTaskId ?? undefined,
    workerNodeId: task.workerNodeId ?? undefined,
    updatedAt: task.updatedAt ?? undefined,
    scorecardId: task.scorecardId ?? undefined,
    scoreId: task.scoreId ?? undefined,
    scorecard: scorecard?.data?.id && scorecard.data.name ? {
      id: scorecard.data.id,
      name: scorecard.data.name
    } : undefined,
    score: score?.data?.id && score.data.name ? {
      id: score.data.id,
      name: score.data.name
    } : undefined,
    evaluation
  };
}

// Add this type at the top with other types
type ErrorHandler = (error: Error) => void;

export function observeRecentTasks(limit: number = 10) {
  const client = getClient();
  
  return {
    subscribe(handler: SubscriptionHandler<any>) {
      const subscription = client.graphql({
        query: TASK_UPDATE_SUBSCRIPTION
      }) as unknown as { subscribe: Function };

      return subscription.subscribe({
        next: ({ data }: { data?: { onUpdateTask: Schema['Task']['type'] } }) => {
          if (data?.onUpdateTask) {
            const updatedTask = data.onUpdateTask;
            handler.next({ data: updatedTask });
          }
        },
        error: (error: Error) => {
          handler.error(error);
          console.error('Error in task subscription:', error);
        }
      });
    }
  };
}

type TaskStageData = Schema['TaskStage']['type'];

async function processTask(task: AmplifyTask): Promise<ProcessedTask> {
  // Parse metadata if it's a string
  let parsedMetadata: Record<string, unknown> | null = null;
  if (task.metadata) {
    if (typeof task.metadata === 'string') {
      try {
        parsedMetadata = JSON.parse(task.metadata);
      } catch (e) {
        console.warn('Failed to parse task metadata:', e);
      }
    } else if (typeof task.metadata === 'object') {
      parsedMetadata = task.metadata;
    }
  }

  // Handle stages - ensure we handle both function and direct data cases
  const stages: ProcessedTaskStage[] = await (async () => {
    if (typeof task.stages === 'function') {
      try {
        const stagesResult = await task.stages();
        return stagesResult.data?.items?.map((stage: TaskStageType) => ({
          id: stage.id,
          name: stage.name,
          order: stage.order,
          status: (stage.status ?? 'PENDING') as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
          processedItems: stage.processedItems ?? undefined,
          totalItems: stage.totalItems ?? undefined,
          startedAt: stage.startedAt ?? undefined,
          completedAt: stage.completedAt ?? undefined,
          estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
          statusMessage: stage.statusMessage ?? undefined
        })) ?? [];
      } catch (e) {
        console.warn('Failed to fetch stages:', e);
        return [];
      }
    }
    return task.stages?.data?.items?.map((stage: TaskStageType) => ({
      id: stage.id,
      name: stage.name,
      order: stage.order,
      status: (stage.status ?? 'PENDING') as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
      processedItems: stage.processedItems ?? undefined,
      totalItems: stage.totalItems ?? undefined,
      startedAt: stage.startedAt ?? undefined,
      completedAt: stage.completedAt ?? undefined,
      estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
      statusMessage: stage.statusMessage ?? undefined
    })) ?? [];
  })();

  // Transform evaluation data if present
  let evaluation = undefined;
  if (task.evaluation) {
    try {
      const evaluationData = typeof task.evaluation === 'function' ? 
        await task.evaluation() : task.evaluation;

      // Parse metrics if it's a string
      let metrics = evaluationData.data?.metrics;
      try {
        if (typeof metrics === 'string') {
          metrics = JSON.parse(metrics);
        }
      } catch (e) {
        console.error('Error parsing metrics:', e);
      }

      // Parse confusion matrix if it's a string
      let confusionMatrix = evaluationData.data?.confusionMatrix;
      try {
        if (typeof confusionMatrix === 'string') {
          confusionMatrix = JSON.parse(confusionMatrix);
        }
      } catch (e) {
        console.error('Error parsing confusion matrix:', e);
      }

      // Parse dataset class distribution if it's a string
      let datasetClassDistribution = evaluationData.data?.datasetClassDistribution;
      try {
        if (typeof datasetClassDistribution === 'string') {
          datasetClassDistribution = JSON.parse(datasetClassDistribution);
        }
      } catch (e) {
        console.error('Error parsing dataset class distribution:', e);
      }

      // Parse predicted class distribution if it's a string
      let predictedClassDistribution = evaluationData.data?.predictedClassDistribution;
      try {
        if (typeof predictedClassDistribution === 'string') {
          predictedClassDistribution = JSON.parse(predictedClassDistribution);
        }
      } catch (e) {
        console.error('Error parsing predicted class distribution:', e);
      }

      evaluation = {
        id: evaluationData.data?.id || '',
        type: evaluationData.data?.type || 'unknown',
        metrics,
        metricsExplanation: evaluationData.data?.metricsExplanation,
        inferences: Number(evaluationData.data?.inferences) || 0,
        accuracy: typeof evaluationData.data?.accuracy === 'number' ? evaluationData.data?.accuracy : null,
        cost: evaluationData.data?.cost ?? null,
        status: evaluationData.data?.status || 'PENDING',
        startedAt: evaluationData.data?.startedAt,
        elapsedSeconds: evaluationData.data?.elapsedSeconds ?? null,
        estimatedRemainingSeconds: evaluationData.data?.estimatedRemainingSeconds ?? null,
        totalItems: Number(evaluationData.data?.totalItems) || 0,
        processedItems: Number(evaluationData.data?.processedItems) || 0,
        errorMessage: evaluationData.data?.errorMessage,
        errorDetails: evaluationData.data?.errorDetails,
        confusionMatrix,
        scoreGoal: evaluationData.data?.scoreGoal,
        datasetClassDistribution,
        isDatasetClassDistributionBalanced: evaluationData.data?.isDatasetClassDistributionBalanced,
        predictedClassDistribution,
        isPredictedClassDistributionBalanced: evaluationData.data?.isPredictedClassDistributionBalanced,
        scoreResults: evaluationData.data?.scoreResults?.data?.items ? {
          items: evaluationData.data.scoreResults.data.items.map(item => ({
            id: item.id,
            value: item.value,
            confidence: item.confidence ?? null,
            metadata: item.metadata,
            explanation: item.explanation ?? null,
            itemId: item.itemId,
            createdAt: item.createdAt
          }))
        } : undefined
      };
    } catch (error) {
      console.error('Error transforming evaluation data:', error);
    }
  }

  // Handle scorecard and score
  const scorecard = task.scorecard ? await unwrapLazyLoader(task.scorecard) : undefined;
  
  const score = task.score ? await unwrapLazyLoader(task.score) : undefined;

  return {
    id: task.id,
    command: task.command,
    type: task.type,
    status: task.status,
    target: task.target,
    description: task.description ?? undefined,
    metadata: parsedMetadata,
    createdAt: task.createdAt ?? undefined,
    startedAt: task.startedAt ?? undefined,
    completedAt: task.completedAt ?? undefined,
    estimatedCompletionAt: task.estimatedCompletionAt ?? undefined,
    errorMessage: task.errorMessage ?? undefined,
    errorDetails: typeof task.errorDetails === 'string' ? task.errorDetails : JSON.stringify(task.errorDetails ?? null),
    stdout: task.stdout ?? undefined,
    stderr: task.stderr ?? undefined,
    currentStageId: task.currentStageId ?? undefined,
    stages,
    dispatchStatus: task.dispatchStatus === 'DISPATCHED' ? 'DISPATCHED' : undefined,
    celeryTaskId: task.celeryTaskId ?? undefined,
    workerNodeId: task.workerNodeId ?? undefined,
    updatedAt: task.updatedAt ?? undefined,
    scorecardId: task.scorecardId ?? undefined,
    scoreId: task.scoreId ?? undefined,
    scorecard: scorecard?.data?.id && scorecard.data.name ? {
      id: scorecard.data.id,
      name: scorecard.data.name
    } : undefined,
    score: score?.data?.id && score.data.name ? {
      id: score.data.id,
      name: score.data.name
    } : undefined,
    evaluation
  };
}

// Add this helper function to convert raw API response to AmplifyTask
function convertToAmplifyTask(rawData: any): AmplifyTask {
  // Create a lazy loader for stages
  const stagesLoader = () => Promise.resolve({
    data: {
      items: (rawData.stages?.items ?? []).map((stage: any) => ({
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
    }
  });

  // Create lazy loaders for scorecard and score
  const scorecardLoader = rawData.scorecard ? () => Promise.resolve({
    data: {
      id: rawData.scorecard.id,
      name: rawData.scorecard.name
    }
  }) : undefined;

  const scoreLoader = rawData.score ? () => Promise.resolve({
    data: {
      id: rawData.score.id,
      name: rawData.score.name
    }
  }) : undefined;

  // Create lazy loader for evaluation
  const evaluationLoader = rawData.evaluation ? () => Promise.resolve({
    data: rawData.evaluation
  }) : undefined;

  return {
    id: rawData.id,
    command: rawData.command,
    type: rawData.type,
    status: rawData.status,
    target: rawData.target,
    description: rawData.description ?? null,
    metadata: rawData.metadata,
    createdAt: rawData.createdAt ?? null,
    startedAt: rawData.startedAt ?? null,
    completedAt: rawData.completedAt ?? null,
    estimatedCompletionAt: rawData.estimatedCompletionAt ?? null,
    errorMessage: rawData.errorMessage ?? null,
    errorDetails: rawData.errorDetails,
    stdout: rawData.stdout ?? null,
    stderr: rawData.stderr ?? null,
    currentStageId: rawData.currentStageId ?? null,
    stages: stagesLoader,
    dispatchStatus: rawData.dispatchStatus ?? null,
    celeryTaskId: rawData.celeryTaskId ?? null,
    workerNodeId: rawData.workerNodeId ?? null,
    updatedAt: rawData.updatedAt ?? null,
    scorecardId: rawData.scorecardId ?? null,
    scoreId: rawData.scoreId ?? null,
    scorecard: scorecardLoader,
    score: scoreLoader,
    evaluation: evaluationLoader
  };
}

export async function listRecentTasks(
  limit = 10,
  nextToken?: string
): Promise<{ tasks: ProcessedTask[]; nextToken?: string }> {
  try {
    const currentClient = getClient();
    const taskClient = currentClient.models.Task as {
      list: (options: {
        limit?: number;
        nextToken?: string;
        filter?: Record<string, any>;
      }) => Promise<{ data: Schema['Task']['type'][], nextToken?: string | null }>;
    };

    const response = await taskClient.list({
      limit,
      nextToken,
      filter: {
        createdAt: {
          gt: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString()
        }
      }
    });

    if (response.data) {
      const tasks = await Promise.all(
        response.data.map(async (task) => {
          const convertedTask = convertToAmplifyTask(task);
          return processTask(convertedTask);
        })
      );
      return {
        tasks: tasks.filter((t): t is ProcessedTask => t !== null),
        nextToken: response.nextToken || undefined
      };
    }

    return { tasks: [] };
  } catch (error) {
    console.error('Error listing tasks:', error);
    return { tasks: [] };
  }
}

export async function getFromModel<T extends { id: string }>(
  modelName: keyof AmplifyClient['models'],
  id: string
): Promise<{ data: T | null }> {
  try {
    const currentClient = getClient();
    const response = await (currentClient.models[modelName] as any).get({ id });
    if (modelName === 'Task' && response.data) {
      return { data: convertToAmplifyTask(response.data) as unknown as T };
    }
    return response;
  } catch (error) {
    console.error(`Error getting ${modelName}:`, error);
    return { data: null };
  }
}

export async function createTask(
  input: Omit<AmplifyTask, 'id' | 'createdAt' | 'updatedAt'> & { accountId: string }
): Promise<ProcessedTask | null> {
  try {
    const currentClient = getClient();
    const response = await (currentClient.models.Task as any).create({
      ...input,
      createdAt: new Date().toISOString()
    });

    if (response.data) {
      const convertedTask = convertToAmplifyTask(response.data);
      return processTask(convertedTask);
    }

    return null;
  } catch (error) {
    console.error('Error creating task:', error);
    return null;
  }
}

export async function updateTask(
  id: string,
  input: Partial<AmplifyTask> | Partial<Schema['TaskStage']['type']>,
  modelName: 'Task' | 'TaskStage' = 'Task'
): Promise<ProcessedTask | null> {
  try {
    const currentClient = getClient();
    if (!currentClient.models[modelName]) {
      throw new Error(`${modelName} model not found`);
    }

    const response = await (currentClient.models[modelName] as any).update({
      id,
      ...input
    });

    if (response.data) {
      return modelName === 'Task' ? processTask(convertToAmplifyTask(response.data)) : null;
    }

    return null;
  } catch (error) {
    console.error('Error updating task:', error);
    return null;
  }
}

export async function listRecentEvaluations(limit: number = 100): Promise<any[]> {
  console.debug('listRecentEvaluations called with limit:', limit);
  try {
    const currentClient = getClient();

    // Get the account ID by key
    const ACCOUNT_KEY = 'call-criteria';
    const accountResponse = await listFromModel<Schema['Account']['type']>(
      'Account',
      { filter: { key: { eq: ACCOUNT_KEY } } }
    );

    if (!accountResponse.data?.length) {
      console.error('No account found with key:', ACCOUNT_KEY);
      return [];
    }

    const accountId = accountResponse.data[0].id;
    console.debug('Fetching evaluations for account:', accountId);

    const response = await currentClient.graphql({
      query: `
        query ListEvaluationByAccountIdAndUpdatedAt(
          $accountId: String!
          $sortDirection: ModelSortDirection!
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
                  correct
                  createdAt
                  scoringJob {
                    id
                    status
                    metadata
                  }
                }
              }
            }
            nextToken
          }
        }
      `,
      variables: {
        accountId: accountId.trim(),
        sortDirection: 'DESC',
        limit: limit || 100
      }
    });

    console.debug('GraphQL response:', {
      hasData: isGraphQLResult(response) && !!response.data,
      hasErrors: isGraphQLResult(response) && !!response.errors,
      itemCount: isGraphQLResult(response) ? response.data?.listEvaluationByAccountIdAndUpdatedAt?.items?.length : 0,
      firstItem: isGraphQLResult(response) && response.data?.listEvaluationByAccountIdAndUpdatedAt?.items?.[0] ? {
        id: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].id,
        type: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].type,
        metrics: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].metrics,
        task: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task,
        scoreResults: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].scoreResults
      } : null
    });

    if (!isGraphQLResult(response)) {
      console.error('Unexpected response type');
      return [];
    }

    if (response.errors?.length) {
      console.error('GraphQL errors:', response.errors);
      throw new Error(`GraphQL errors: ${response.errors.map(e => e.message).join(', ')}`);
    }

    if (!response.data) {
      console.error('No data returned from GraphQL query');
      return [];
    }

    const result = response.data;
    if (!result?.listEvaluationByAccountIdAndUpdatedAt?.items) {
      console.error('No items found in GraphQL response');
      return [];
    }

    return result.listEvaluationByAccountIdAndUpdatedAt.items;
  } catch (error) {
    console.error('Error listing recent evaluations:', error);
    return [];
  }
}

export function observeRecentEvaluations(limit: number = 100): Observable<{ items: any[], isSynced: boolean }> {
  return new Observable(subscriber => {
    let evaluations: any[] = [];
    let subscriptionCleanup: { unsubscribe: () => void } | null = null;

    // Load initial data
    async function loadInitialEvaluations() {
      try {
        const response = await listRecentEvaluations(limit);
        console.debug('Initial evaluations response:', {
          count: response.length,
          firstEvaluation: response[0] ? {
            id: response[0].id,
            type: response[0].type,
            metrics: response[0].metrics,
            task: response[0].task,
            scoreResults: response[0].scoreResults,
            rawResponse: response[0]
          } : null
        });
        
        evaluations = response;
        subscriber.next({ items: evaluations, isSynced: true });
      } catch (error) {
        console.error('Error loading initial evaluations:', error);
        subscriber.error(error);
      }
    }

    // Set up subscription
    try {
      console.debug('Setting up evaluation subscription...');
      const client = getClient();
      subscriptionCleanup = (client.graphql({
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
                  correct
                  createdAt
                  scoringJob {
                    id
                    status
                    metadata
                  }
                }
              }
            }
          }
        `
      }) as unknown as { subscribe: Function }).subscribe({
        next: ({ data }: { data?: { onUpdateEvaluation: any } }) => {
          if (data?.onUpdateEvaluation) {
            const updatedEvaluation = data.onUpdateEvaluation;
            console.debug('Received evaluation update:', {
              id: updatedEvaluation.id,
              scoreResultsCount: updatedEvaluation.scoreResults?.items?.length,
              firstScoreResult: updatedEvaluation.scoreResults?.items?.[0]
            });
            evaluations = evaluations.map(evaluation => 
              evaluation.id === updatedEvaluation.id ? updatedEvaluation : evaluation
            );
            subscriber.next({ items: evaluations, isSynced: true });
          }
        },
        error: (error: Error) => {
          console.error('Error in evaluation subscription:', error);
          subscriber.error(error);
        }
      });
    } catch (error) {
      console.error('Error setting up evaluation subscription:', error);
      subscriber.error(error);
    }

    // Load initial data
    loadInitialEvaluations();

    // Cleanup function
    return () => {
      console.debug('Cleaning up evaluation subscription');
      if (subscriptionCleanup) {
        subscriptionCleanup.unsubscribe();
      }
    };
  });
}

// Update the ScoreResult type to include createdAt
export interface LocalScoreResult {
  id: string;
  value: string | number;
  confidence: number | null;
  metadata: {
    human_label: string | null;
    correct: boolean;
    human_explanation: string | null;
    text: string | null;
  };
  explanation: string | null;
  itemId: string | null;
  createdAt: string;
}

// Add type for score results data structure
type ScoreResultsData = {
  data?: {
    items: Array<Schema['ScoreResult']['type']>;
  };
};

// Add these type definitions at the top of the file
type RawScoreResult = {
  id: string;
  value: string | number;
  confidence: number | null;
  metadata: any;
  explanation: string | null;
  itemId: string | null;
  correct: boolean;
  createdAt: string;
  scoringJob?: {
    id: string;
    status: string;
    metadata: any;
  };
};

type RawScoreResults = {
  items: RawScoreResult[];
};

// Update the transformEvaluation function's score results handling
export function transformEvaluation(evaluation: Schema['Evaluation']['type']) {
  console.log('TRANSFORM EVALUATION CALLED - TEST'); // Simple test log
  
  console.debug('transformEvaluation entry point:', {
    evaluationId: evaluation?.id,
    hasScoreResults: !!evaluation?.scoreResults,
    scoreResultsType: evaluation?.scoreResults ? typeof evaluation.scoreResults : 'undefined',
    rawScoreResults: evaluation?.scoreResults,
    rawScoreResultsKeys: evaluation?.scoreResults ? Object.keys(evaluation.scoreResults) : [],
    fullEvaluation: evaluation // Log the full evaluation object
  });

  if (!evaluation) {
    console.debug('Early return: evaluation is null');
    return null;
  }

  console.debug('About to get rawTaskResponse');
  const rawTaskResponse = getValueFromLazyLoader(evaluation.task);
  console.debug('rawTaskResponse:', rawTaskResponse);

  const rawTask = rawTaskResponse?.data;
  console.debug('rawTask:', rawTask);

  const rawStages = getValueFromLazyLoader(rawTask?.stages);
  console.debug('rawStages:', rawStages);
  
  console.debug('About to start score results transformation');
  
  // Transform score results with improved error handling and logging
  const scoreResults = (() => {
    try {
      console.debug('Inside score results transformation try block');
      console.debug('Starting score results transformation - CHECKPOINT 1:', {
        hasScoreResults: !!evaluation.scoreResults,
        scoreResultsType: typeof evaluation.scoreResults,
        rawValue: evaluation.scoreResults,
        isFunction: typeof evaluation.scoreResults === 'function'
      });

      // First unwrap the lazy-loaded score results
      const rawResultsResponse = getValueFromLazyLoader(evaluation.scoreResults);
      console.debug('After getValueFromLazyLoader - CHECKPOINT 2:', {
        hasResponse: !!rawResultsResponse,
        responseType: typeof rawResultsResponse,
        rawResponse: rawResultsResponse,
        responseKeys: rawResultsResponse ? Object.keys(rawResultsResponse) : []
      });

      // Extract items from the response structure
      const items = (() => {
        if (!rawResultsResponse) {
          console.debug('CHECKPOINT 3A: No rawResultsResponse');
          return undefined;
        }
        
        // Handle both direct items array and nested data structure
        if (Array.isArray(rawResultsResponse)) {
          console.debug('CHECKPOINT 3B: Found items as direct array', {
            itemCount: rawResultsResponse.length,
            firstItem: rawResultsResponse[0]
          });
          return rawResultsResponse as RawScoreResult[];
        }
        
        const response = rawResultsResponse as any;
        if (Array.isArray(response.items)) {
          console.debug('CHECKPOINT 3C: Found items directly in response', {
            itemCount: response.items.length,
            firstItem: response.items[0]
          });
          return response.items as RawScoreResult[];
        }
        if (response.data?.items && Array.isArray(response.data.items)) {
          console.debug('CHECKPOINT 3D: Found items in data property', {
            itemCount: response.data.items.length,
            firstItem: response.data.items[0]
          });
          return response.data.items as RawScoreResult[];
        }
        console.debug('CHECKPOINT 3E: Could not find items in response structure:', {
          responseKeys: Object.keys(response),
          hasData: 'data' in response,
          dataKeys: response.data ? Object.keys(response.data) : null,
          fullResponse: response
        });
        return undefined;
      })();

      console.debug('After items extraction - CHECKPOINT 4:', {
        hasItems: !!items,
        itemCount: items?.length,
        firstItem: items?.[0]
      });

      if (!items?.length) {
        console.debug('CHECKPOINT 5: No score result items found to transform');
        return undefined;
      }

      const transformedItems = items.map((result: RawScoreResult, index: number) => {
        console.debug(`Transforming score result ${index} - CHECKPOINT 6:`, {
          id: result.id,
          value: result.value,
          metadata: result.metadata,
          rawResult: result
        });

        // Parse metadata if it's a string
        const metadata = (() => {
          try {
            if (typeof result.metadata === 'string') {
              console.debug(`CHECKPOINT 7A: Parsing metadata string for result ${result.id}`);
              const parsed = JSON.parse(result.metadata);
              if (typeof parsed === 'string') {
                console.debug(`CHECKPOINT 7B: Double parsing metadata for result ${result.id}`);
                return JSON.parse(parsed);
              }
              return parsed;
            }
            return result.metadata || {};
          } catch (e) {
            console.error(`CHECKPOINT 7C: Error parsing metadata for result ${result.id}:`, e);
            return {};
          }
        })();

        return {
          id: result.id,
          value: result.value,
          confidence: result.confidence ?? null,
          explanation: result.explanation ?? null,
          metadata: {
            human_label: metadata.human_label ?? null,
            correct: Boolean(metadata.correct ?? result.correct),
            human_explanation: metadata.human_explanation ?? null,
            text: metadata.text ?? null
          },
          itemId: result.itemId,
          createdAt: result.createdAt || new Date().toISOString()
        };
      });

      console.debug('Final transformed score results - CHECKPOINT 8:', {
        count: transformedItems.length,
        items: transformedItems
      });

      return { items: transformedItems };
    } catch (error: unknown) {
      console.error('Error in score results transformation - CHECKPOINT 9:', error);
      if (error instanceof Error) {
        console.error('Error details:', {
          errorName: error.name,
          errorMessage: error.message,
          errorStack: error.stack
        });
      }
      return undefined;
    }
  })();

  const task: AmplifyTask | null = rawTask ? {
    id: rawTask.id,
    command: rawTask.command,
    type: rawTask.type,
    status: rawTask.status,
    target: rawTask.target,
    stages: { 
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
    }
  } : null;

  // Add debug logging for the final evaluation object
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

  console.debug('Transformed evaluation:', {
    id: transformedEvaluation.id,
    hasScoreResults: !!transformedEvaluation.scoreResults,
    scoreResultsCount: transformedEvaluation.scoreResults?.items?.length,
    firstScoreResult: transformedEvaluation.scoreResults?.items?.[0],
    rawScoreResults: evaluation.scoreResults
  });

  return transformedEvaluation;
}

// Add to the existing types at the top
export type Evaluation = {
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