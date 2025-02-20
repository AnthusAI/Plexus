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
import { convertToAmplifyTask, processTask } from './transformers';

// Re-export the transformation functions for backward compatibility
export { convertToAmplifyTask as transformAmplifyTask, processTask };

// Define base types for nested objects
export type TaskStageType = {
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
}

interface RawStages {
  data?: {
    items: TaskStageType[];
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
        taskCompletedAt: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task?.completedAt,
        taskStartedAt: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task?.startedAt,
        taskStatus: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task?.status,
        rawTask: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task,
        taskKeys: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task ? Object.keys(response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task) : [],
        taskType: typeof response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task,
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
    let subscriptionCleanup: { unsubscribe: () => void }[] = [];

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
            taskCompletedAt: response[0].task?.completedAt,
            taskStartedAt: response[0].task?.startedAt,
            taskStatus: response[0].task?.status,
            rawTask: response[0].task,
            taskKeys: response[0].task ? Object.keys(response[0].task) : [],
            taskType: typeof response[0].task,
            scoreResults: response[0].scoreResults
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
      console.debug('Setting up evaluation subscriptions...');
      const client = getClient();

      // Helper function to handle evaluation changes
      const handleEvaluationChange = (evaluation: any, action: 'create' | 'update') => {
        console.debug(`Handling ${action} for evaluation:`, {
          evaluationId: evaluation.id,
          type: evaluation.type,
          taskData: evaluation.task,
          taskId: evaluation.task?.id,
          taskStatus: evaluation.task?.status,
          taskType: typeof evaluation.task,
          taskKeys: evaluation.task ? Object.keys(evaluation.task) : []
        });

        if (action === 'create') {
          evaluations = [evaluation, ...evaluations];
        } else {
          evaluations = evaluations.map(e => 
            e.id === evaluation.id ? evaluation : e
          );
        }
        
        subscriber.next({ items: evaluations, isSynced: true });
      };

      // Set up create subscription
      const createSub = (client.graphql({
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
          }
        `
      }) as unknown as { subscribe: Function }).subscribe({
        next: ({ data }: { data?: { onCreateEvaluation: any } }) => {
          console.debug('Create subscription event received:', {
            hasData: !!data,
            evaluation: data?.onCreateEvaluation ? {
              id: data.onCreateEvaluation.id,
              type: data.onCreateEvaluation.type,
              taskData: data.onCreateEvaluation.task,
              taskId: data.onCreateEvaluation.task?.id
            } : null
          });
          if (data?.onCreateEvaluation) {
            handleEvaluationChange(data.onCreateEvaluation, 'create');
          }
        },
        error: (error: Error) => {
          console.error('Error in create subscription:', error);
          subscriber.error(error);
        }
      });
      subscriptionCleanup.push(createSub);

      // Set up update subscription
      const updateSub = (client.graphql({
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
          }
        `
      }) as unknown as { subscribe: Function }).subscribe({
        next: ({ data }: { data?: { onUpdateEvaluation: any } }) => {
          console.debug('Update subscription event received:', {
            hasData: !!data,
            evaluation: data?.onUpdateEvaluation ? {
              id: data.onUpdateEvaluation.id,
              type: data.onUpdateEvaluation.type,
              taskData: data.onUpdateEvaluation.task,
              taskId: data.onUpdateEvaluation.task?.id
            } : null
          });
          if (data?.onUpdateEvaluation) {
            handleEvaluationChange(data.onUpdateEvaluation, 'update');
          }
        },
        error: (error: Error) => {
          console.error('Error in update subscription:', error);
          subscriber.error(error);
        }
      });
      subscriptionCleanup.push(updateSub);

    } catch (error) {
      console.error('Error setting up evaluation subscriptions:', error);
      subscriber.error(error);
    }

    // Load initial data
    loadInitialEvaluations();

    // Cleanup function
    return () => {
      console.debug('Cleaning up evaluation subscriptions');
      subscriptionCleanup.forEach(sub => {
        try {
          if (sub && typeof sub.unsubscribe === 'function') {
            sub.unsubscribe();
          }
        } catch (error) {
          console.error('Error cleaning up subscription:', error);
        }
      });
      subscriptionCleanup = [];
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
  console.debug('transformEvaluation entry point:', {
    evaluationId: evaluation?.id,
    hasTask: !!evaluation?.task,
    taskType: typeof evaluation?.task,
    rawTask: evaluation?.task,
    taskKeys: evaluation?.task ? Object.keys(evaluation.task) : []
  });

  if (!evaluation) return null;

  const rawTaskResponse = getValueFromLazyLoader(evaluation.task);
  console.debug('Raw task response:', {
    taskId: rawTaskResponse?.data?.id,
    hasData: !!rawTaskResponse?.data,
    completedAt: rawTaskResponse?.data?.completedAt,
    status: rawTaskResponse?.data?.status,
    rawResponse: rawTaskResponse
  });

  const rawTask = rawTaskResponse?.data;
  const rawStages = getValueFromLazyLoader(rawTask?.stages) as { data?: { items: TaskStageType[] } } | undefined;
  
  console.debug('Raw task and stages:', {
    taskId: rawTask?.id,
    taskStatus: rawTask?.status,
    taskCompletedAt: rawTask?.completedAt,
    taskStartedAt: rawTask?.startedAt,
    stagesData: rawStages?.data?.items?.map((s: TaskStageType) => ({
      id: s.id,
      name: s.name,
      order: s.order,
      status: s.status,
      processedItems: s.processedItems,
      totalItems: s.totalItems,
      startedAt: s.startedAt,
      completedAt: s.completedAt,
      estimatedCompletionAt: s.estimatedCompletionAt,
      statusMessage: s.statusMessage
    })) || []
  });

  // ... rest of the function remains the same ...
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