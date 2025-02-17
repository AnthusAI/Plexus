import { generateClient } from 'aws-amplify/data';
import type { GraphQLResult, GraphQLSubscription } from '@aws-amplify/api';
import { Schema } from '@/amplify/data/resource';
import { Observable } from 'rxjs';
import { LazyLoader } from './types';
import type { AmplifyTask } from '@/types/tasks/amplify';
import type { ProcessedTask } from '@/types/tasks/processed';

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
  task?: LazyLoader<AmplifyTask>;
};

export type AmplifyTask = {
  id: string;
  command: string;
  type: string;
  status: string;
  target: string;
  description?: string;
  metadata?: Record<string, unknown> | string;
  createdAt?: string;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  errorMessage?: string;
  errorDetails?: any;
  stdout?: string;
  stderr?: string;
  currentStageId?: string;
  stages?: {
    items: TaskStageType[];
  };
  dispatchStatus?: 'DISPATCHED';
  celeryTaskId?: string;
  workerNodeId?: string;
  updatedAt?: string;
  scorecardId?: string;
  scoreId?: string;
  scorecard?: LazyLoader<{
    id: string;
    name: string;
  }>;
  score?: LazyLoader<{
    id: string;
    name: string;
  }>;
  evaluation?: LazyLoader<EvaluationType>;
};

export type ProcessedTask = {
  id: string;
  command: string;
  type: string;
  status: string;
  target: string;
  description?: string;
  metadata?: string;
  createdAt?: string;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  errorMessage?: string;
  errorDetails?: string;
  stdout?: string;
  stderr?: string;
  currentStageId?: string;
  stages: TaskStageType[];
  dispatchStatus?: 'DISPATCHED';
  celeryTaskId?: string;
  workerNodeId?: string;
  updatedAt?: string;
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
    metricsExplanation?: string;
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

type SubscriptionResponse<T> = {
  provider: any;
  value: {
    data: T;
  };
};

type GraphQLSubscriptionResponse<T> = {
  provider: any;
  value: {
    data: T;
  };
};

export async function transformAmplifyTask(task: AmplifyTask): Promise<ProcessedTask> {
  // Handle evaluation - if it's a function (LazyLoader), await it
  const evaluation = task.evaluation && typeof task.evaluation === 'function' ? 
    await task.evaluation() : task.evaluation;

  // Handle scorecard - if it's a function (LazyLoader), await it
  const scorecard = task.scorecard && typeof task.scorecard === 'function' ? 
    await task.scorecard() : task.scorecard;

  // Handle score - if it's a function (LazyLoader), await it
  const score = task.score && typeof task.score === 'function' ? 
    await task.score() : task.score;

  return {
    ...task,
    evaluation,
    scorecard,
    score,
    // Ensure description is never null, only undefined or string
    description: task.description || undefined
  };
}

export function observeRecentTasks(limit: number = 12): Observable<{ items: ProcessedTask[], isSynced: boolean }> {
  console.warn('observeRecentTasks called with limit:', limit);
  return new Observable(subscriber => {
    let isSynced = false;
    let currentTasks: ProcessedTask[] = [];
    const client = getClient();

    // Initial load
    async function loadInitialTasks() {
      try {
        const tasks = await listRecentTasks(limit);
        currentTasks = tasks;
        subscriber.next({ items: currentTasks, isSynced: true });
        isSynced = true;
      } catch (error) {
        console.error('Error in initial task load:', error);
        subscriber.next({ items: [], isSynced: false });
      }
    }

    // Load initial data
    loadInitialTasks();

    // Set up subscriptions
    const taskSubscription = client.models.Task.onCreate({}).subscribe({
      next: (response: GraphQLSubscriptionResponse<{ onCreateTask: AmplifyTask }>) => {
        const taskData = response.value.data.onCreateTask;
        if (taskData) {
          handleTaskUpdate(taskData);
        }
      },
      error: (error: any) => {
        console.error('Error in task subscription:', error);
      }
    });

    // Subscribe to task updates
    const taskUpdateSubscription = client.models.Task.onUpdate({}).subscribe({
      next: (response: GraphQLSubscriptionResponse<{ onUpdateTask: AmplifyTask }>) => {
        const taskData = response.value.data.onUpdateTask;
        if (taskData) {
          handleTaskUpdate(taskData);
        }
      },
      error: (error: any) => {
        console.error('Error in task update subscription:', error);
      }
    });

    // Subscribe to stage updates
    const stageSubscription = client.models.TaskStage.onUpdate({}).subscribe({
      next: (response: GraphQLSubscriptionResponse<{ onUpdateTaskStage: TaskStageType }>) => {
        const stageData = response.value.data.onUpdateTaskStage;
        if (stageData) {
          handleStageUpdate(stageData);
        }
      },
      error: (error: any) => {
        console.error('Error in stage subscription:', error);
      }
    });

    // ... existing code ...
  });
}

async function processTask(task: AmplifyTask): Promise<ProcessedTask> {
  // Unwrap any LazyLoader properties
  const unwrappedTask = {
    ...task,
    scorecard: task.scorecard ? await unwrapLazyLoader(task.scorecard) : undefined,
    score: task.score ? await unwrapLazyLoader(task.score) : undefined,
    evaluation: task.evaluation ? await unwrapLazyLoader(task.evaluation) : undefined,
    stages: task.stages ? {
      items: task.stages.items ? await Promise.all(task.stages.items.map(async (stage) => ({
        ...stage,
        task: stage.task ? await unwrapLazyLoader(stage.task) : undefined
      }))) : []
    } : undefined
  };

  // Handle evaluation data
  let evaluation = undefined;
  if (unwrappedTask.evaluation) {
    try {
      evaluation = {
        id: unwrappedTask.evaluation.id,
        type: unwrappedTask.evaluation.type,
        metrics: unwrappedTask.evaluation.metrics,
        metricsExplanation: unwrappedTask.evaluation.metricsExplanation ?? undefined,
        inferences: Number(unwrappedTask.evaluation.inferences) || 0,
        accuracy: typeof unwrappedTask.evaluation.accuracy === 'number' ? unwrappedTask.evaluation.accuracy : null,
        cost: unwrappedTask.evaluation.cost ?? null,
        status: unwrappedTask.evaluation.status || 'PENDING',
        startedAt: unwrappedTask.evaluation.startedAt,
        elapsedSeconds: unwrappedTask.evaluation.elapsedSeconds ?? null,
        estimatedRemainingSeconds: unwrappedTask.evaluation.estimatedRemainingSeconds ?? null,
        totalItems: Number(unwrappedTask.evaluation.totalItems) || 0,
        processedItems: Number(unwrappedTask.evaluation.processedItems) || 0,
        errorMessage: unwrappedTask.evaluation.errorMessage,
        errorDetails: unwrappedTask.evaluation.errorDetails,
        confusionMatrix: unwrappedTask.evaluation.confusionMatrix,
        scoreGoal: unwrappedTask.evaluation.scoreGoal,
        datasetClassDistribution: unwrappedTask.evaluation.datasetClassDistribution,
        isDatasetClassDistributionBalanced: unwrappedTask.evaluation.isDatasetClassDistributionBalanced ?? null,
        predictedClassDistribution: unwrappedTask.evaluation.predictedClassDistribution,
        isPredictedClassDistributionBalanced: unwrappedTask.evaluation.isPredictedClassDistributionBalanced ?? null,
        scoreResults: unwrappedTask.evaluation.scoreResults ? {
          items: unwrappedTask.evaluation.scoreResults.items?.map(item => ({
            id: item.id,
            value: item.value,
            confidence: item.confidence ?? null,
            metadata: item.metadata,
            explanation: item.explanation ?? null,
            itemId: item.itemId ?? null,
            createdAt: item.createdAt
          }))
        } : undefined
      };
    } catch (error) {
      console.error('Error transforming evaluation data:', error);
    }
  }

  return {
    id: unwrappedTask.id,
    command: unwrappedTask.command,
    type: unwrappedTask.type,
    status: unwrappedTask.status,
    target: unwrappedTask.target,
    description: unwrappedTask.description ?? undefined,
    metadata: typeof unwrappedTask.metadata === 'string' ? unwrappedTask.metadata : JSON.stringify(unwrappedTask.metadata ?? null),
    createdAt: unwrappedTask.createdAt ?? undefined,
    startedAt: unwrappedTask.startedAt ?? undefined,
    completedAt: unwrappedTask.completedAt ?? undefined,
    estimatedCompletionAt: unwrappedTask.estimatedCompletionAt ?? undefined,
    errorMessage: unwrappedTask.errorMessage ?? undefined,
    errorDetails: typeof unwrappedTask.errorDetails === 'string' ? unwrappedTask.errorDetails : JSON.stringify(unwrappedTask.errorDetails ?? null),
    stdout: unwrappedTask.stdout ?? undefined,
    stderr: unwrappedTask.stderr ?? undefined,
    currentStageId: unwrappedTask.currentStageId ?? undefined,
    stages: unwrappedTask.stages?.items ?? [],
    dispatchStatus: unwrappedTask.dispatchStatus === 'DISPATCHED' ? 'DISPATCHED' : undefined,
    celeryTaskId: unwrappedTask.celeryTaskId ?? undefined,
    workerNodeId: unwrappedTask.workerNodeId ?? undefined,
    updatedAt: unwrappedTask.updatedAt ?? undefined,
    scorecardId: unwrappedTask.scorecardId ?? undefined,
    scoreId: unwrappedTask.scoreId ?? undefined,
    scorecard: unwrappedTask.scorecard ? {
      id: unwrappedTask.scorecard.id,
      name: unwrappedTask.scorecard.name
    } : undefined,
    score: unwrappedTask.score ? {
      id: unwrappedTask.score.id,
      name: unwrappedTask.score.name
    } : undefined,
    evaluation
  };
}

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

async function handleTaskUpdate(updatedTask: AmplifyTask) {
  try {
    // Unwrap any LazyLoader properties first
    const unwrappedTask = {
      ...updatedTask,
      scorecard: updatedTask.scorecard ? await unwrapLazyLoader(updatedTask.scorecard) : undefined,
      score: updatedTask.score ? await unwrapLazyLoader(updatedTask.score) : undefined,
      evaluation: updatedTask.evaluation ? await unwrapLazyLoader(updatedTask.evaluation) : undefined,
      stages: updatedTask.stages ? {
        items: updatedTask.stages.items ? await Promise.all(updatedTask.stages.items.map(async (stage) => ({
          ...stage,
          task: stage.task ? await unwrapLazyLoader(stage.task) : undefined
        }))) : []
      } : undefined
    };

    // Process the unwrapped task
    const processedTask = await processTask(unwrappedTask);
    
    // Update task status if needed
    if (processedTask.status === 'FAILED') {
      unwrappedTask.status = 'FAILED';
    } else if (processedTask.status === 'COMPLETED' && 
              processedTask.stages?.every(s => s.status === 'COMPLETED')) {
      unwrappedTask.status = 'COMPLETED';
    }

    // Update the task list
    const taskIndex = currentTasks.findIndex(t => t.id === processedTask.id);
    if (taskIndex !== -1) {
      currentTasks[taskIndex] = processedTask;
    } else {
      currentTasks.unshift(processedTask);
    }

    // Sort and trim tasks
    currentTasks.sort((a, b) => {
      if ((a.status === 'COMPLETED' || a.status === 'FAILED') && 
          (b.status === 'COMPLETED' || b.status === 'FAILED')) {
        return new Date(b.updatedAt || b.createdAt || '').getTime() - 
               new Date(a.updatedAt || a.createdAt || '').getTime();
      }
      return new Date(b.createdAt || '').getTime() - new Date(a.createdAt || '').getTime();
    });

    if (currentTasks.length > limit) {
      currentTasks = currentTasks.slice(0, limit);
    }

    subscriber.next({ items: [...currentTasks], isSynced: true });
  } catch (error) {
    console.error('Error processing task update:', error);
  }
}

async function handleStageUpdate(updatedStage: TaskStageType) {
  try {
    // Find the task containing this stage
    const taskIndex = currentTasks.findIndex(task => 
      task.stages?.some(stage => stage.id === updatedStage.id)
    );

    if (taskIndex === -1) {
      console.warn('Stage update received for unknown task:', updatedStage);
      return;
    }

    const task = currentTasks[taskIndex];
    const stageIndex = task.stages?.findIndex(s => s.id === updatedStage.id) ?? -1;

    if (stageIndex === -1) {
      console.warn('Stage update received for unknown stage:', updatedStage);
      return;
    }

    // Update the stage
    if (task.stages) {
      task.stages[stageIndex] = {
        ...task.stages[stageIndex],
        ...updatedStage
      };
    }

    // Update task status if needed
    if (updatedStage.status === 'FAILED') {
      task.status = 'FAILED';
    } else if (updatedStage.status === 'COMPLETED' && 
              task.stages?.every(s => s.status === 'COMPLETED')) {
      task.status = 'COMPLETED';
    }

    subscriber.next({ items: [...currentTasks], isSynced: true });
  } catch (error) {
    console.error('Error processing stage update:', error);
  }
}

// Handle GraphQL responses
async function handleGraphQLResponse<T>(response: GraphQLResult<T> | GraphQLSubscription<T>): Promise<T | undefined> {
  if ('data' in response) {
    return response.data;
  }
  return undefined;
}

// Update scorecard and score data
if (updatedTask.scorecardId && !updatedTask.scorecard) {
  const scorecardResponse = await client.graphql({
    query: `
      query GetScorecard($id: ID!) {
        getScorecard(id: $id) {
          id
          name
          key
        }
      }
    `,
    variables: {
      id: updatedTask.scorecardId
    }
  });
  const scorecardData = await handleGraphQLResponse(scorecardResponse);
  updatedTask.scorecard = scorecardData?.getScorecard;
}

if (updatedTask.scoreId && !updatedTask.score) {
  const scoreResponse = await client.graphql({
    query: `
      query GetScore($id: ID!) {
        getScore(id: $id) {
          id
          name
          key
        }
      }
    `,
    variables: {
      id: updatedTask.scoreId
    }
  });
  const scoreData = await handleGraphQLResponse(scoreResponse);
  updatedTask.score = scoreData?.getScore;
} 