import { generateClient } from 'aws-amplify/data';
import type { GraphQLResult, GraphQLSubscription } from '@aws-amplify/api';
import { Schema } from '@/amplify/data/resource';
import { Observable } from 'rxjs';
import { LazyLoader } from './types';

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
  metadata?: Record<string, unknown> | string;
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
  models: {
    Task: {
      list: (options: { 
        limit?: number; 
        include?: string[];
      }) => Promise<{
        data: Array<Schema['Task']['type']>;
        nextToken?: string | null;
      }>;
      onCreate: (options: {}) => { subscribe: (handlers: { next: () => void; error: (error: any) => void }) => { unsubscribe: () => void } };
      onUpdate: (options: {}) => { subscribe: (handlers: { next: () => void; error: (error: any) => void }) => { unsubscribe: () => void } };
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

export type AmplifyListResult<T> = {
  data: T[];
  nextToken?: string | null;
}

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

type SubscriptionResponse<T> = {
  provider: any;
  value: {
    data: T;
  };
};

function isGraphQLResult<T>(response: GraphQLResult<T> | GraphQLSubscription<T>): response is GraphQLResult<T> {
  return 'data' in response && 'errors' in response;
}

export function getClient(): AmplifyClient {
  if (!client) {
    client = generateClient<Schema>() as AmplifyClient;
  }
  return client;
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
function getValueFromLazyLoader<T>(loader: LazyLoader<T>): T | undefined {
  if (typeof loader === 'function') {
    return undefined; // We can't synchronously get the value from a promise
  }
  return loader;
}

async function unwrapLazyLoader<T>(loader: LazyLoader<T>): Promise<T> {
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
  const stages: ProcessedTaskStage[] = task.stages?.items?.map((stage: TaskStageType) => ({
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

  // Transform evaluation data if present
  let evaluation = undefined;
  if (task.evaluation) {
    try {
      const evaluationData = typeof task.evaluation === 'function' ? 
        await task.evaluation() : task.evaluation;

      // Parse metrics if it's a string
      let metrics = evaluationData.metrics;
      try {
        if (typeof metrics === 'string') {
          metrics = JSON.parse(metrics);
        }
      } catch (e) {
        console.error('Error parsing metrics:', e);
      }

      // Parse confusion matrix if it's a string
      let confusionMatrix = evaluationData.confusionMatrix;
      try {
        if (typeof confusionMatrix === 'string') {
          confusionMatrix = JSON.parse(confusionMatrix);
        }
      } catch (e) {
        console.error('Error parsing confusion matrix:', e);
      }

      // Parse dataset class distribution if it's a string
      let datasetClassDistribution = evaluationData.datasetClassDistribution;
      try {
        if (typeof datasetClassDistribution === 'string') {
          datasetClassDistribution = JSON.parse(datasetClassDistribution);
        }
      } catch (e) {
        console.error('Error parsing dataset class distribution:', e);
      }

      // Parse predicted class distribution if it's a string
      let predictedClassDistribution = evaluationData.predictedClassDistribution;
      try {
        if (typeof predictedClassDistribution === 'string') {
          predictedClassDistribution = JSON.parse(predictedClassDistribution);
        }
      } catch (e) {
        console.error('Error parsing predicted class distribution:', e);
      }

      evaluation = {
        id: evaluationData.id,
        type: evaluationData.type,
        metrics,
        metricsExplanation: evaluationData.metricsExplanation,
        inferences: Number(evaluationData.inferences) || 0,
        accuracy: typeof evaluationData.accuracy === 'number' ? evaluationData.accuracy : null,
        cost: evaluationData.cost ?? null,
        status: evaluationData.status,
        startedAt: evaluationData.startedAt,
        elapsedSeconds: evaluationData.elapsedSeconds ?? null,
        estimatedRemainingSeconds: evaluationData.estimatedRemainingSeconds ?? null,
        totalItems: Number(evaluationData.totalItems) || 0,
        processedItems: Number(evaluationData.processedItems) || 0,
        errorMessage: evaluationData.errorMessage,
        errorDetails: evaluationData.errorDetails,
        confusionMatrix,
        scoreGoal: evaluationData.scoreGoal,
        datasetClassDistribution,
        isDatasetClassDistributionBalanced: evaluationData.isDatasetClassDistributionBalanced,
        predictedClassDistribution,
        isPredictedClassDistributionBalanced: evaluationData.isPredictedClassDistributionBalanced,
        scoreResults: evaluationData.scoreResults
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
    metadata: typeof task.metadata === 'string' ? task.metadata : JSON.stringify(task.metadata ?? null),
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
    scorecard: scorecard ? {
      id: scorecard.id,
      name: scorecard.name
    } : undefined,
    score: score ? {
      id: score.id,
      name: score.name
    } : undefined,
    evaluation
  };
}

// Add this type at the top with other types
type ErrorHandler = (error: Error) => void;

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

    // Handle task updates in-memory
    async function handleTaskUpdate(updatedTask: AmplifyTask) {
      try {
        console.debug('Processing task update/create - Raw Input:', {
          taskId: updatedTask.id,
          type: updatedTask.type,
          status: updatedTask.status,
          hasStages: !!updatedTask.stages,
          scorecardId: updatedTask.scorecardId,
          scoreId: updatedTask.scoreId,
          rawScorecard: updatedTask.scorecard,
          rawScore: updatedTask.score
        });

        // If we have IDs but no data, fetch the related data
        if (updatedTask.scorecardId && !updatedTask.scorecard) {
          console.debug('Fetching scorecard data for ID:', updatedTask.scorecardId);
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
          if (isGraphQLResult(scorecardResponse)) {
            updatedTask.scorecard = scorecardResponse.data?.getScorecard;
          }
          console.debug('Fetched scorecard:', updatedTask.scorecard);
        }

        if (updatedTask.scoreId && !updatedTask.score) {
          console.debug('Fetching score data for ID:', updatedTask.scoreId);
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
          if (isGraphQLResult(scoreResponse)) {
            updatedTask.score = scoreResponse.data?.getScore;
          }
          console.debug('Fetched score:', updatedTask.score);
        }

        const processedTask = await processTask(updatedTask);
        console.debug('Task after processing:', {
          taskId: processedTask.id,
          hasStages: processedTask.stages?.length,
          scorecardId: processedTask.scorecardId,
          scoreId: processedTask.scoreId,
          processedScorecard: processedTask.scorecard,
          processedScore: processedTask.score
        });

        const taskIndex = currentTasks.findIndex(t => t.id === processedTask.id);
        
        if (taskIndex !== -1) {
          const existingTask = currentTasks[taskIndex];
          console.debug('Existing task state:', {
            taskId: existingTask.id,
            existingScorecard: existingTask.scorecard,
            existingScore: existingTask.score,
            existingScorecardId: existingTask.scorecardId,
            existingScoreId: existingTask.scoreId
          });
          
          // Create the updated task, prioritizing new data
          const updatedTaskData = {
            ...existingTask,
            ...processedTask,
            stages: processedTask.stages?.length ? processedTask.stages : existingTask.stages,
          };

          // Handle scorecard updates with tracing
          if (updatedTask.scorecardId) {
            console.debug('Updating scorecard:', {
              taskId: updatedTask.id,
              newScorecardId: updatedTask.scorecardId,
              oldScorecardId: existingTask.scorecardId,
              newScorecard: updatedTask.scorecard,
              oldScorecard: existingTask.scorecard
            });
            updatedTaskData.scorecardId = updatedTask.scorecardId;
            if (updatedTask.scorecard) {
              const scorecardValue = getValueFromLazyLoader(updatedTask.scorecard);
              if (scorecardValue) {
                updatedTaskData.scorecard = {
                  id: scorecardValue.id,
                  name: scorecardValue.name
                };
              }
            }
          }

          // Handle score updates with tracing
          if (updatedTask.scoreId) {
            console.debug('Updating score:', {
              taskId: updatedTask.id,
              newScoreId: updatedTask.scoreId,
              oldScoreId: existingTask.scoreId,
              newScore: updatedTask.score,
              oldScore: existingTask.score
            });
            updatedTaskData.scoreId = updatedTask.scoreId;
            if (updatedTask.score) {
              const scoreValue = getValueFromLazyLoader(updatedTask.score);
              if (scoreValue) {
                updatedTaskData.score = {
                  id: scoreValue.id,
                  name: scoreValue.name
                };
              }
            }
          }

          currentTasks[taskIndex] = updatedTaskData;

          console.debug('Final updated task state:', {
            taskId: currentTasks[taskIndex].id,
            scorecardId: currentTasks[taskIndex].scorecardId,
            scoreId: currentTasks[taskIndex].scoreId,
            finalScorecard: currentTasks[taskIndex].scorecard,
            finalScore: currentTasks[taskIndex].score
          });
        } else {
          // For new tasks, add to the beginning of the array
          currentTasks.unshift(processedTask);
          console.debug('Added new task:', {
            taskId: processedTask.id,
            totalTasks: currentTasks.length,
            scorecardId: processedTask.scorecardId,
            scoreId: processedTask.scoreId,
            scorecard: processedTask.scorecard,
            score: processedTask.score
          });
        }

        // Sort tasks
        currentTasks.sort((a, b) => {
          if ((a.status === 'COMPLETED' || a.status === 'FAILED') && 
              (b.status === 'COMPLETED' || b.status === 'FAILED')) {
            return new Date(b.updatedAt || b.createdAt || '').getTime() - 
                   new Date(a.updatedAt || a.createdAt || '').getTime();
          }
          return new Date(b.createdAt || '').getTime() - new Date(a.createdAt || '').getTime();
        });

        // Trim to limit if needed
        if (currentTasks.length > limit) {
          currentTasks = currentTasks.slice(0, limit);
        }

        console.debug('Emitting updated task list:', {
          count: currentTasks.length,
          taskIds: currentTasks.map(t => ({
            id: t.id,
            scorecardId: t.scorecardId,
            scoreId: t.scoreId,
            scorecard: t.scorecard?.name,
            score: t.score?.name
          }))
        });
        subscriber.next({ items: [...currentTasks], isSynced: true });
      } catch (error) {
        console.error('Error processing task update:', error);
      }
    }

    // Handle stage updates in-memory
    async function handleStageUpdate(updatedStage: any) {
      try {
        console.debug('Stage update received:', updatedStage);
        
        // Extract taskId from the stage data - handle both possible structures
        const taskId = updatedStage?.taskId || updatedStage?.data?.taskId;
        if (!taskId) {
          console.warn('No taskId found in stage update:', updatedStage);
          return;
        }

        const taskIndex = currentTasks.findIndex(t => t.id === taskId);
        if (taskIndex === -1) {
          console.debug(`Task ${taskId} not found in current tasks`);
          return;
        }

        const task = currentTasks[taskIndex];
        if (!task.stages) {
          console.debug(`Task ${taskId} has no stages array`);
          return;
        }

        // Get the actual stage data, handling both possible structures
        const stageData = updatedStage?.data || updatedStage;
        const stageIndex = task.stages.findIndex(s => s.id === stageData.id);
        
        if (stageIndex === -1) {
          console.debug(`Stage ${stageData.id} not found in task ${taskId}`);
          return;
        }

        // Update the specific stage
        task.stages[stageIndex] = {
          ...task.stages[stageIndex],
          status: stageData.status ?? task.stages[stageIndex].status,
          processedItems: stageData.processedItems ?? task.stages[stageIndex].processedItems,
          totalItems: stageData.totalItems ?? task.stages[stageIndex].totalItems,
          startedAt: stageData.startedAt ?? task.stages[stageIndex].startedAt,
          completedAt: stageData.completedAt ?? task.stages[stageIndex].completedAt,
          estimatedCompletionAt: stageData.estimatedCompletionAt ?? task.stages[stageIndex].estimatedCompletionAt,
          statusMessage: stageData.statusMessage ?? task.stages[stageIndex].statusMessage
        };
        
        // Update task status if needed
        if (stageData.status === 'FAILED') {
          task.status = 'FAILED';
        } else if (stageData.status === 'COMPLETED' && 
                  task.stages.every(s => s.status === 'COMPLETED')) {
          task.status = 'COMPLETED';
        }
        
        subscriber.next({ items: [...currentTasks], isSynced: true });
      } catch (error) {
        console.error('Error processing stage update:', error);
      }
    }

    // Load initial data
    loadInitialTasks();

    // Set up subscriptions
    const taskSubscription = client.models.Task.onCreate({}).subscribe({
      next: (response: SubscriptionResponse<{ onCreateTask: AmplifyTask }>) => {
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
      next: (response: SubscriptionResponse<{ onUpdateTask: AmplifyTask }>) => {
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
      next: (response: SubscriptionResponse<{ onUpdateTaskStage: TaskStageType }>) => {
        const stageData = response.value.data.onUpdateTaskStage;
        if (stageData) {
          handleStageUpdate(stageData);
        }
      },
      error: (error: any) => {
        console.error('Error in stage subscription:', error);
      }
    });

    // Cleanup function
    return () => {
      console.log('Cleaning up task subscriptions');
      taskSubscription.unsubscribe();
      taskUpdateSubscription.unsubscribe();
      stageSubscription.unsubscribe();
    };
  });
}

type TaskStageData = Schema['TaskStage']['type'];

async function processTask(task: AmplifyTask): Promise<ProcessedTask> {
  // Unwrap any LazyLoader properties
  const unwrappedTask = {
    ...task,
    scorecard: task.scorecard ? await unwrapLazyLoader(task.scorecard) : undefined,
    score: task.score ? await unwrapLazyLoader(task.score) : undefined,
    evaluation: task.evaluation ? await unwrapLazyLoader(task.evaluation) : undefined,
    stages: task.stages ? {
      items: task.stages.items ? await Promise.all(task.stages.items.map(async (stage) => ({
        ...stage
      }))) : []
    } : undefined
  };

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
    evaluation: unwrappedTask.evaluation ? {
      id: unwrappedTask.evaluation.id,
      type: unwrappedTask.evaluation.type,
      metrics: unwrappedTask.evaluation.metrics,
      accuracy: unwrappedTask.evaluation.accuracy,
      processedItems: unwrappedTask.evaluation.processedItems,
      totalItems: unwrappedTask.evaluation.totalItems,
      scoreResults: unwrappedTask.evaluation.scoreResults,
      inferences: unwrappedTask.evaluation.inferences,
      cost: unwrappedTask.evaluation.cost,
      status: unwrappedTask.evaluation.status,
      elapsedSeconds: unwrappedTask.evaluation.elapsedSeconds,
      estimatedRemainingSeconds: unwrappedTask.evaluation.estimatedRemainingSeconds
    } : undefined
  };
}

export async function listRecentTasks(limit: number = 10): Promise<ProcessedTask[]> {
  console.warn('listRecentTasks called with limit:', limit);
  try {
    const currentClient = getClient();
    if (!currentClient.models.Task) {
      throw new Error('Task model not found');
    }

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
    console.debug('Fetching tasks for account:', accountId);

    const response = await currentClient.graphql({
      query: `
        query ListTaskByAccountIdAndUpdatedAt(
          $accountId: String!
          $sortDirection: ModelSortDirection!
          $limit: Int
        ) {
          listTaskByAccountIdAndUpdatedAt(
            accountId: $accountId
            sortDirection: $sortDirection
            limit: $limit
          ) {
            items {
              id
              accountId
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
              stdout
              stderr
              currentStageId
              scorecardId
              scoreId
              celeryTaskId
              workerNodeId
              updatedAt
              scorecard {
                id
                name
              }
              score {
                id
                name
              }
              stages {
                items {
                  id
                  name
                  order
                  status
                  processedItems
                  totalItems
                  startedAt
                  completedAt
                  estimatedCompletionAt
                  statusMessage
                }
              }
              evaluation {
                id
                type
                metrics
                metricsExplanation
                inferences
                accuracy
                cost
                status
                startedAt
                elapsedSeconds
                estimatedRemainingSeconds
                totalItems
                processedItems
                errorMessage
                errorDetails
                confusionMatrix
                scoreGoal
                datasetClassDistribution
                isDatasetClassDistributionBalanced
                predictedClassDistribution
                isPredictedClassDistributionBalanced
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
            }
            nextToken
          }
        }
      `,
      variables: {
        accountId: accountId.trim(),
        sortDirection: 'DESC',
        limit: limit || 100
      },
      authMode: 'userPool'
    }) as unknown as GraphQLResult<ListTaskResponse>;

    if (response.errors?.length) {
      console.error('GraphQL errors:', response.errors);
      throw new Error(`GraphQL errors: ${response.errors.map(e => e.message).join(', ')}`);
    }

    if (!response.data) {
      console.error('No data returned from GraphQL query');
      return [];
    }

    console.debug('Raw GraphQL response - Task with evaluation:', {
      taskCount: response.data?.listTaskByAccountIdAndUpdatedAt?.items?.length,
      firstTask: response.data?.listTaskByAccountIdAndUpdatedAt?.items?.[0] ? {
        id: response.data.listTaskByAccountIdAndUpdatedAt.items[0].id,
        type: response.data.listTaskByAccountIdAndUpdatedAt.items[0].type,
        hasEvaluation: !!response.data.listTaskByAccountIdAndUpdatedAt.items[0].evaluation,
        evaluation: response.data.listTaskByAccountIdAndUpdatedAt.items[0].evaluation ? 
          (() => {
            const evaluationValue = getValueFromLazyLoader(response.data.listTaskByAccountIdAndUpdatedAt.items[0].evaluation);
            return evaluationValue ? {
              id: evaluationValue.id,
              type: evaluationValue.type,
              metrics: evaluationValue.metrics,
              accuracy: evaluationValue.accuracy,
              processedItems: evaluationValue.processedItems,
              totalItems: evaluationValue.totalItems,
              scoreResults: evaluationValue.scoreResults
            } : undefined;
          })() : undefined
      } : null
    });

    const result = response.data;
    if (!result?.listTaskByAccountIdAndUpdatedAt?.items) {
      console.error('No items found in GraphQL response');
      return [];
    }

    // Process tasks and load their stages
    const processedTasks = await Promise.all(
      result.listTaskByAccountIdAndUpdatedAt.items.map(async (task) => {
        console.debug(`Processing task ${task.id}, raw data:`, {
          id: task.id,
          type: task.type,
          scorecard: task.scorecard,
          score: task.score,
          scorecardId: task.scorecardId,
          scoreId: task.scoreId,
          hasEvaluation: !!task.evaluation,
          evaluationData: task.evaluation
        });
        return processTask(task);
      })
    );

    console.debug('All processed tasks:', processedTasks.map(task => ({
      id: task.id,
      type: task.type,
      scorecard: task.scorecard,
      score: task.score,
      scorecardId: task.scorecardId,
      scoreId: task.scoreId,
      hasEvaluation: !!task.evaluation,
      evaluationData: task.evaluation
    })));
    return processedTasks;
  } catch (error) {
    console.error('Error listing recent tasks:', error);
    return [];
  }
}

export async function getFromModel<T extends { id: string }>(
  modelName: keyof AmplifyClient['models'],
  id: string
): Promise<{ data: T | null }> {
  try {
    const response = await (client.models[modelName] as any).get({ id });
    return response;
  } catch (error) {
    console.error(`Error getting ${modelName}:`, error);
    return { data: null };
  }
}

export async function createTask(
  command: string,
  type: string = 'command',
  target: string = '',
  metadata: any = {}
): Promise<ProcessedTask | null> {
  try {
    const currentClient = getClient();
    if (!currentClient.models.Task) {
      throw new Error('Task model not found');
    }

    // Get the account ID by key
    const ACCOUNT_KEY = 'call-criteria';
    const accountResponse = await listFromModel<Schema['Account']['type']>(
      'Account',
      { filter: { key: { eq: ACCOUNT_KEY } } }
    );

    if (!accountResponse.data?.length) {
      console.error('No account found with key:', ACCOUNT_KEY);
      return null;
    }

    const accountId = accountResponse.data[0].id;

    type BasicTaskInput = {
      accountId: string;
      command: string;
      type: string;
      target: string;
      metadata: string;
      dispatchStatus: 'PENDING';
      status: 'PENDING';
      createdAt: string;
    };

    const taskInput = {
      accountId,
      command,
      type,
      target,
      metadata: JSON.stringify(metadata),
      dispatchStatus: 'PENDING' as const,
      status: 'PENDING' as const,
      createdAt: new Date().toISOString()
    } as BasicTaskInput;

    // @ts-expect-error Complex union type in generated Amplify types
    const response = await currentClient.models.Task.create(taskInput);

    if (response.data) {
      return processTask(response.data);
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

    // @ts-expect-error Complex union type in generated Amplify types
    const response = await currentClient.models[modelName].update({
      id,
      ...input
    });

    if (response.data) {
      return modelName === 'Task' ? processTask(response.data) : null;
    }

    return null;
  } catch (error) {
    console.error(`Error updating ${modelName}:`, error);
    return null;
  }
}

export async function listRecentEvaluations(limit: number = 100): Promise<Schema['Evaluation']['type'][]> {
  console.warn('listRecentEvaluations called with limit:', limit);
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
        accountId: accountId.trim(),
        sortDirection: 'DESC',
        limit: limit || 100
      }
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

    console.debug('Raw GraphQL response:', {
      evaluationCount: response.data?.listEvaluationByAccountIdAndUpdatedAt?.items?.length,
      firstEvaluation: response.data?.listEvaluationByAccountIdAndUpdatedAt?.items?.[0] ? {
        id: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].id,
        taskId: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].taskId,
        taskStages: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task?.stages?.items
      } : null
    });

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

export function observeRecentEvaluations(limit: number = 100): Observable<{ items: Schema['Evaluation']['type'][], isSynced: boolean }> {
  return new Observable(subscriber => {
    let isSynced = false;
    let evaluations: Schema['Evaluation']['type'][] = [];
    
    async function loadInitialEvaluations() {
      try {
        const response = await listRecentEvaluations(limit);
        console.debug('Initial evaluations load:', {
          count: response.length,
          firstEvaluation: response[0] ? {
            id: response[0].id,
            type: response[0].type,
            metrics: response[0].metrics,
            accuracy: response[0].accuracy,
            scoreResults: response[0].scoreResults,
            task: response[0].task ? {
              id: response[0].task.id,
              status: response[0].task.status,
              stages: response[0].task.stages
            } : null
          } : null
        });
        evaluations = response;
        subscriber.next({ items: evaluations, isSynced: true });
        isSynced = true;
      } catch (error) {
        console.error('Error loading initial evaluations:', error);
        subscriber.error(error);
      }
    }

    async function handleEvaluationUpdate(updatedEvaluation: Schema['Evaluation']['type']) {
      console.debug('Evaluation update received:', {
        id: updatedEvaluation.id,
        type: updatedEvaluation.type,
        metrics: updatedEvaluation.metrics,
        accuracy: updatedEvaluation.accuracy,
        scoreResults: updatedEvaluation.scoreResults,
        task: updatedEvaluation.task ? {
          id: updatedEvaluation.task.id,
          status: updatedEvaluation.task.status,
          stages: updatedEvaluation.task.stages
        } : null
      });

      // If we have IDs but no data, fetch the related data
      if (updatedEvaluation.scorecardId && !updatedEvaluation.scorecard) {
        console.debug('Fetching scorecard data for ID:', updatedEvaluation.scorecardId);
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
            id: updatedEvaluation.scorecardId
          }
        });
        if (isGraphQLResult(scorecardResponse)) {
          updatedEvaluation.scorecard = scorecardResponse.data?.getScorecard;
        }
      }

      if (updatedEvaluation.scoreId && !updatedEvaluation.score) {
        console.debug('Fetching score data for ID:', updatedEvaluation.scoreId);
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
            id: updatedEvaluation.scoreId
          }
        });
        if (isGraphQLResult(scoreResponse)) {
          updatedEvaluation.score = scoreResponse.data?.getScore;
        }
      }

      const evaluationIndex = evaluations.findIndex(e => e.id === updatedEvaluation.id);
      
      if (evaluationIndex !== -1) {
        // Update existing evaluation
        const existingEvaluation = evaluations[evaluationIndex];
        
        // Create the updated evaluation, prioritizing new data
        const updatedEvaluationData = {
          ...existingEvaluation,
          ...updatedEvaluation,
          task: updatedEvaluation.task || existingEvaluation.task
        };

        evaluations[evaluationIndex] = updatedEvaluationData;
      } else {
        // For new evaluations, add to the beginning of the array
        evaluations.unshift(updatedEvaluation);
        console.debug('Added new evaluation:', {
          evaluationId: updatedEvaluation.id,
          totalEvaluations: evaluations.length
        });
      }

      // Sort evaluations by updatedAt
      evaluations.sort((a, b) => 
        new Date(b.updatedAt || b.createdAt || '').getTime() - 
        new Date(a.updatedAt || a.createdAt || '').getTime()
      );

      // Trim to limit if needed
      if (evaluations.length > limit) {
        evaluations = evaluations.slice(0, limit);
      }

      console.debug('Emitting updated evaluation list:', {
        count: evaluations.length,
        evaluationIds: evaluations.map(e => ({
          id: e.id,
          status: e.status,
          taskId: e.taskId
        }))
      });
      subscriber.next({ items: [...evaluations], isSynced: true });
    }

    // Load initial data
    loadInitialEvaluations();

    // Set up subscriptions
    const subscriptions = [
      // Subscribe to evaluation updates
      client.graphql({
        query: `subscription OnUpdateEvaluation {
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
          }
        }`
      }).subscribe({
        next: (data: any) => {
          console.debug('Raw onUpdate data received:', {
            fullData: data,
            evaluationData: data?.data?.onUpdateEvaluation
          });
          
          const evaluationData = data?.data?.onUpdateEvaluation;
          if (!evaluationData?.id) {
            console.debug('Invalid evaluation update data:', data);
            return;
          }

          handleEvaluationUpdate(evaluationData);
        },
        error: (error: Error) => console.error('Error in evaluation onUpdate subscription:', error)
      }),

      // Subscribe to evaluation creates
      client.graphql({
        query: `subscription OnCreateEvaluation {
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
          }
        }`
      }).subscribe({
        next: (data: any) => {
          console.debug('Raw onCreate data received:', {
            fullData: data,
            evaluationData: data?.data?.onCreateEvaluation
          });
          const evaluationData = data?.data?.onCreateEvaluation;
          if (!evaluationData?.id) {
            console.debug('Invalid evaluation create data:', data);
            return;
          }
          console.log('Evaluation onCreate triggered:', { 
            evaluationId: evaluationData.id,
            type: evaluationData.type,
            status: evaluationData.status,
            taskId: evaluationData.taskId
          });
          handleEvaluationUpdate(evaluationData);
        },
        error: (error: Error) => console.error('Error in evaluation onCreate subscription:', error)
      })
    ];

    // Cleanup function
    return () => {
      console.log('Cleaning up evaluation subscriptions');
      subscriptions.forEach(sub => sub.unsubscribe());
    };
  });
} 