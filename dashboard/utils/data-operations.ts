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
  taskId: string;
  name: string;
  order: number;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  processedItems?: number;
  totalItems?: number;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  statusMessage?: string;
  createdAt?: string;
  updatedAt?: string;
}

interface RawStages {
  data?: {
    items: TaskStageType[];
  };
}

// Define base evaluation type from Schema
type BaseEvaluation = Schema['Evaluation']['type'];

// Define processed evaluation type that extends base evaluation
export type ProcessedEvaluation = Omit<BaseEvaluation, 'task' | 'scorecard' | 'score' | 'metrics' | 'confusionMatrix' | 'datasetClassDistribution' | 'predictedClassDistribution' | 'scoreResults'> & {
  // Override fields that need processing
  task: AmplifyTask | null;
  scorecard: { name: string } | null;
  score: { name: string } | null;
  metrics: any;  // Allow any for processed metrics since we parse JSON
  confusionMatrix: any;  // Allow any for processed matrix since we parse JSON
  datasetClassDistribution: any;  // Allow any for processed distribution since we parse JSON
  predictedClassDistribution: any;  // Allow any for processed distribution since we parse JSON
  scoreResults?: Array<{
    id: string;
    value: string | number;
    confidence: number | null;
    metadata: any;
    explanation: string | null;
    trace: any | null;
    itemId: string | null;
    itemIdentifiers?: Array<{
      name: string;
      value: string;
      url?: string;
    }> | null;
    createdAt: string;
  }>;
};

// Update AmplifyTask type to use BaseEvaluation
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
  output?: string | null; // Universal Code YAML output
  attachedFiles?: string[] | null; // Array of S3 file keys for attachments
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
    data?: BaseEvaluation | null;
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
  output?: string; // Universal Code YAML output
  attachedFiles?: string[]; // Array of S3 file keys for attachments
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
  evaluation?: ProcessedEvaluation;
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
function isGraphQLResult(response: any): response is GraphQLResult<any> {
  return response && typeof response === 'object' && ('data' in response || 'errors' in response);
}

// Define the evaluation fields to use in GraphQL queries
const EVALUATION_FIELDS = `
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
  # scoreResults intentionally omitted; will be lazy-loaded per selected evaluation
`;

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

export async function listRecentEvaluations(
  limit: number = 100,
  accountId: string | null = null,
  selectedScorecard: string | null = null,
  selectedScore: string | null = null
): Promise<any[]> {
  console.debug('listRecentEvaluations called with limit:', limit, 'filters:', { accountId, selectedScorecard, selectedScore });
  try {
    const client = getClient();
    
    // Get the account ID if not provided
    if (!accountId) {
      const ACCOUNT_KEY = 'call-criteria';
      const accountResponse = await (client.models.Account as any).list({ 
        filter: { key: { eq: ACCOUNT_KEY } } 
      });
      
      if (!accountResponse.data?.length) {
        throw new Error(`No account found with key: ${ACCOUNT_KEY}`);
      }
      
      accountId = accountResponse.data[0].id;
    }
    
    let query = '';
    let variables: any = {
      sortDirection: 'DESC',
      limit: limit || 100
    };
    
    // Determine which GSI to use based on the filters
    if (selectedScorecard && selectedScore) {
      // If both scorecard and score are selected, use the scoreId GSI directly
      query = `
        query ListEvaluationByScoreIdAndUpdatedAt(
          $scoreId: String!
          $sortDirection: ModelSortDirection!
          $limit: Int
        ) {
          listEvaluationByScoreIdAndUpdatedAt(
            scoreId: $scoreId
            sortDirection: $sortDirection
            limit: $limit
          ) {
            items {
              ${EVALUATION_FIELDS}
            }
            nextToken
          }
        }
      `;
      variables.scoreId = selectedScore;
    } else if (selectedScorecard) {
      // If only scorecard is selected, use the scorecardId GSI
      query = `
        query ListEvaluationByScorecardIdAndUpdatedAt(
          $scorecardId: String!
          $sortDirection: ModelSortDirection!
          $limit: Int
        ) {
          listEvaluationByScorecardIdAndUpdatedAt(
            scorecardId: $scorecardId
            sortDirection: $sortDirection
            limit: $limit
          ) {
            items {
              ${EVALUATION_FIELDS}
            }
            nextToken
          }
        }
      `;
      variables.scorecardId = selectedScorecard;
    } else {
      // Default to accountId GSI
      query = `
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
              ${EVALUATION_FIELDS}
            }
            nextToken
          }
        }
      `;
      variables.accountId = accountId;
    }
    
    const response = await client.graphql({
      query,
      variables
    }) as GraphQLResult<any>;
    
    // Extract data from the response
    const responseData = response?.data || {};
    
    console.debug('Evaluations response:', {
      itemCount: 
        responseData?.listEvaluationByAccountIdAndUpdatedAt?.items?.length || 
        responseData?.listEvaluationByScorecardIdAndUpdatedAt?.items?.length || 
        responseData?.listEvaluationByScoreIdAndUpdatedAt?.items?.length || 0,
      filters: { accountId, selectedScorecard, selectedScore }
    });
    
    // Extract items from the response based on which query was used
    const result = 
      responseData?.listEvaluationByAccountIdAndUpdatedAt || 
      responseData?.listEvaluationByScorecardIdAndUpdatedAt || 
      responseData?.listEvaluationByScoreIdAndUpdatedAt;
    
    if (!result?.items) {
      console.warn('No items found in evaluation response');
      return [];
    }
    
    return result.items;
  } catch (error) {
    console.error('Error in listRecentEvaluations:', error);
    return [];
  }
}

export function observeRecentEvaluations(
  limit: number = 100,
  accountId: string | null = null,
  selectedScorecard: string | null = null,
  selectedScore: string | null = null
): Observable<{ items: any[], isSynced: boolean }> {
  return new Observable(subscriber => {
    let evaluations: any[] = [];
    let subscriptionCleanup: { unsubscribe: () => void }[] = [];

    // Load initial data
    async function loadInitialEvaluations() {
      try {
        const response = await listRecentEvaluations(limit, accountId, selectedScorecard, selectedScore);
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
          } : null,
          filters: {
            accountId,
            selectedScorecard,
            selectedScore
          }
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
      const client = getClient();

      // Helper function to handle evaluation changes
      const handleEvaluationChange = (evaluation: any, action: 'create' | 'update') => {
        console.debug(`Handling ${action} for evaluation:`, {
          evaluationId: evaluation.id,
          type: evaluation.type,
          scorecardId: evaluation.scorecardId,
          scorecard: evaluation.scorecard,
          scorecardName: evaluation.scorecard?.name,
          scoreId: evaluation.scoreId,
          score: evaluation.score,
          scoreName: evaluation.score?.name,
          taskData: evaluation.task,
          taskId: evaluation.task?.id,
          taskStatus: evaluation.task?.status,
          taskType: typeof evaluation.task,
          taskKeys: evaluation.task ? Object.keys(evaluation.task) : []
        });

        if (action === 'create') {
          evaluations = [evaluation, ...evaluations];
        } else {
          evaluations = evaluations.map(e => {
            if (e.id === evaluation.id) {
              // Preserve scorecard/score data from existing evaluation if missing in update
              const updatedEvaluation = {
                ...evaluation,
                scorecard: evaluation.scorecard || e.scorecard,
                score: evaluation.score || e.score
              };
              console.debug('Updated evaluation with preserved scorecard/score:', {
                evaluationId: updatedEvaluation.id,
                originalScorecard: evaluation.scorecard,
                originalScore: evaluation.score,
                existingScorecard: e.scorecard,
                existingScore: e.score,
                finalScorecard: updatedEvaluation.scorecard,
                finalScore: updatedEvaluation.score
              });
              return updatedEvaluation;
            }
            return e;
          });
        }
        
        subscriber.next({ items: evaluations, isSynced: true });
      };

      // Add the TaskFields fragment, for example before the subscription queries
      const TASK_FIELDS_FRAGMENT = `
        fragment TaskFields on Task {
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
      `;

      // Update the OnCreateEvaluation subscription query to use the TaskFields fragment
      const createEvaluationSubscriptionQuery = `
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
              ...TaskFields
            }
            # scoreResults intentionally omitted; will be lazy-loaded per selected evaluation
          }
        }
        ${TASK_FIELDS_FRAGMENT}
      `;

      // Similarly, update the OnUpdateEvaluation subscription query
      const updateEvaluationSubscriptionQuery = `
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
              ...TaskFields
            }
            # scoreResults intentionally omitted; will be lazy-loaded per selected evaluation
          }
        }
        ${TASK_FIELDS_FRAGMENT}
      `;

      // Then, replace the subscription queries in the subscription setup with these updated queries
      // For create subscription
      const createSub = (client.graphql({ query: createEvaluationSubscriptionQuery }) as unknown as { subscribe: (observer: { next: ({ data }: { data: any }) => void, error: (error: any) => void }) => any }).subscribe({
        next: ({ data }: { data: any }) => {
          // Handle the subscription event
          console.debug('Create subscription event received:', { data });
          if (data?.onCreateEvaluation) {
            handleEvaluationChange(data.onCreateEvaluation, 'create');
          }
        },
        error: (error: any) => {
          console.error('Error in create subscription:', error);
        }
      });
      subscriptionCleanup.push(createSub);

      // For update subscription
      const updateSub = (client.graphql({ query: updateEvaluationSubscriptionQuery }) as unknown as { subscribe: (observer: { next: ({ data }: { data: any }) => void, error: (error: any) => void }) => any }).subscribe({
        next: ({ data }: { data: any }) => {
          console.debug('Update subscription event received:', { data });
          if (data?.onUpdateEvaluation) {
            handleEvaluationChange(data.onUpdateEvaluation, 'update');
          }
        },
        error: (error: any) => {
          console.error('Error in update subscription:', error);
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
  itemIdentifiers?: Array<{
    name: string;
    value: string;
    url?: string;
  }> | null;
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
  itemIdentifiers?: Array<{
    name: string;
    value: string;
    url?: string;
  }> | null;
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

export function transformEvaluation(evaluation: BaseEvaluation): ProcessedEvaluation | null {

  if (!evaluation) return null;

  // Handle task data - properly handle both function and object cases
  let taskData: AmplifyTask | null = null;
  if (evaluation.task) {
    if (typeof evaluation.task === 'function') {
      // If it's a function (LazyLoader), we need to get the raw value
      // Note: Since this is synchronous, we can only use the value if it's already loaded
      const rawTaskResponse = getValueFromLazyLoader(evaluation.task);
      if (rawTaskResponse?.data) {
        taskData = rawTaskResponse.data as unknown as AmplifyTask;
      }
    } else {
      // If it's already an object, use it directly
      taskData = evaluation.task as AmplifyTask;
    }
  }
  
  // Get stage items - handle both LazyLoader and direct object formats
  let stageItems: any[] = [];
  if (taskData?.stages) {
    // Check if stages is a LazyLoader function
    if (typeof taskData.stages === 'function') {
      const stageResponse = getValueFromLazyLoader(taskData.stages);
      stageItems = stageResponse?.data?.items || [];
  } else {
      // Handle direct object format (new structure)
      const direct: any = taskData.stages as unknown as { data?: { items?: any[] }, items?: any[] };
      stageItems = direct?.data?.items || direct?.items || [];
    }
  }

  // Only log when we actually have stage changes to reduce noise
  if (stageItems.length > 0) {
    console.log('🔍 TRACE_STAGES: transformEvaluation found stage data:', {
      evaluationId: evaluation.id,
      taskDataId: taskData?.id,
      stageCount: stageItems.length,
      stageStatuses: stageItems.map((s: any) => ({ name: s.name, status: s.status }))
    });
  }


  // Get scorecard and score data
  const scorecardData = evaluation.scorecard ? 
    (typeof evaluation.scorecard === 'function' ? 
      getValueFromLazyLoader(evaluation.scorecard)?.data : 
      evaluation.scorecard) : null;

  const scoreData = evaluation.score ?
    (typeof evaluation.score === 'function' ?
      getValueFromLazyLoader(evaluation.score)?.data :
      evaluation.score) : null;

  console.debug('transformEvaluation scorecard/score processing:', {
    evaluationId: evaluation.id,
    rawScorecard: evaluation.scorecard,
    rawScore: evaluation.score,
    scorecardType: typeof evaluation.scorecard,
    scoreType: typeof evaluation.score,
    scorecardData,
    scoreData,
    finalScorecardName: scorecardData?.name,
    finalScoreName: scoreData?.name
  });

  // Get score results data - handle both function and object cases
  let rawScoreResults: any = null;
  if (evaluation.scoreResults) {
    if (typeof evaluation.scoreResults === 'function') {
      // If it's a function (LazyLoader), we need to get the raw value
      const scoreResultsResponse = getValueFromLazyLoader(evaluation.scoreResults);
      rawScoreResults = scoreResultsResponse?.data || scoreResultsResponse;
    } else {
      // If it's already an object, use it directly
      rawScoreResults = evaluation.scoreResults;
    }
  }


  // Extract score results array
  let standardizedScoreResults: any[] = [];
  if (rawScoreResults) {
    if (Array.isArray(rawScoreResults)) {
      standardizedScoreResults = rawScoreResults;
    } else if (typeof rawScoreResults === 'object' && 'items' in rawScoreResults && Array.isArray(rawScoreResults.items)) {
      standardizedScoreResults = rawScoreResults.items;
    }
  }


  // Transform score results into the expected format
  const transformedScoreResults = standardizedScoreResults.map((result: any) => {
    // Extract item identifier data if available
    let itemIdentifiers = null;
    
    if (result.item?.itemIdentifiers?.items) {
      itemIdentifiers = result.item.itemIdentifiers.items
        .sort((a: any, b: any) => (a.position || 0) - (b.position || 0)) // Sort by position
        .map((identifier: any) => ({
          name: identifier.name,
          value: identifier.value,
          url: identifier.url || undefined
        }));
    } else if (result.item?.identifiers) {
      // Handle legacy JSON identifiers format
      try {
        const parsed = JSON.parse(result.item.identifiers);
        if (Array.isArray(parsed)) {
          itemIdentifiers = parsed.map((identifier: any) => ({
            name: identifier.name,
            value: identifier.value || identifier.id, // Support both value and id fields
            url: identifier.url || undefined
          }));
        }
      } catch (error) {
        console.warn('Failed to parse legacy identifiers JSON:', error);
      }
    }

    // Parse metadata (which might be JSON string, sometimes double-encoded)
    let parsedMetadata;
    try {
      if (typeof result.metadata === 'string') {
        parsedMetadata = JSON.parse(result.metadata);
        if (typeof parsedMetadata === 'string') {
          parsedMetadata = JSON.parse(parsedMetadata);
        }
      } else {
        parsedMetadata = result.metadata || {};
      }
    } catch (e) {
      console.warn('Error parsing metadata:', e);
      parsedMetadata = {};
    }

    // Extract results from nested structure if present
    const firstResultKey = parsedMetadata?.results ? Object.keys(parsedMetadata.results)[0] : null;
    const scoreResult = firstResultKey && parsedMetadata.results ? parsedMetadata.results[firstResultKey] : null;

    // Construct properly formatted metadata object
    const processedMetadata = {
      human_label: scoreResult?.metadata?.human_label ?? parsedMetadata.human_label ?? null,
      correct: Boolean(scoreResult?.metadata?.correct ?? parsedMetadata.correct),
      human_explanation: scoreResult?.metadata?.human_explanation ?? parsedMetadata.human_explanation ?? null,
      text: scoreResult?.metadata?.text ?? parsedMetadata.text ?? null
    };

    return {
      id: result.id,
      value: result.value,
      confidence: result.confidence ?? null,
      metadata: processedMetadata,
      explanation: result.explanation ?? scoreResult?.explanation ?? null,
      trace: result.trace ?? scoreResult?.trace ?? null,
      itemId: result.itemId ?? parsedMetadata.item_id?.toString() ?? null,
      itemIdentifiers,
      createdAt: result.createdAt || new Date().toISOString(),
      feedbackItem: result.feedbackItem ?? null  // Preserve feedbackItem relationship
    };
  });

  // Transform the evaluation into the format expected by components
  const transformedEvaluation: ProcessedEvaluation = {
    ...evaluation, // Include all base evaluation fields
    task: taskData,
    scorecard: scorecardData ? { name: scorecardData.name } : null,
    score: scoreData ? { name: scoreData.name } : null,
    metrics: typeof evaluation.metrics === 'string' ? 
      JSON.parse(evaluation.metrics) : evaluation.metrics,
    confusionMatrix: typeof evaluation.confusionMatrix === 'string' ? 
      JSON.parse(evaluation.confusionMatrix) : evaluation.confusionMatrix,
    datasetClassDistribution: typeof evaluation.datasetClassDistribution === 'string' ?
      JSON.parse(evaluation.datasetClassDistribution) : evaluation.datasetClassDistribution,
    predictedClassDistribution: typeof evaluation.predictedClassDistribution === 'string' ?
      JSON.parse(evaluation.predictedClassDistribution) : evaluation.predictedClassDistribution,
    scoreResults: transformedScoreResults
  };


  return transformedEvaluation;
}

// Add to the existing types at the top
export type Evaluation = {
  id: string;
  type: string;
  scorecard?: { name: string } | null;
  score?: { name: string } | null;
  createdAt: string;
  metrics?: any;
  metricsExplanation?: string | null;
  accuracy?: number | null;
  processedItems?: number | null;
  totalItems?: number | null;
  inferences?: number | null;
  cost?: number | null;
  status?: string | null;
  elapsedSeconds?: number | null;
  estimatedRemainingSeconds?: number | null;
  startedAt?: string | null;
  errorMessage?: string | null;
  errorDetails?: any;
  confusionMatrix?: any;
  scoreGoal?: string | null;
  datasetClassDistribution?: any;
  isDatasetClassDistributionBalanced?: boolean | null;
  predictedClassDistribution?: any;
  isPredictedClassDistributionBalanced?: boolean | null;
  task: AmplifyTask | null;
  scoreResults?: {
    items?: Array<{
      id: string;
      value: string | number;
      confidence: number | null;
      metadata: any;
      trace: any | null;
      itemId: string | null;
      itemIdentifiers?: Array<{
        name: string;
        value: string;
        url?: string;
      }> | null;
    }>;
  } | null;
};

// Add type definitions for subscription events
export type TaskSubscriptionEvent = {
  type: 'create' | 'update';
  data: {
    id: string;
    status: string;
    startedAt?: string;
    completedAt?: string;
    stages?: {
      data?: {
        items: TaskStageType[];
      };
    };
  };
};

export type TaskStageSubscriptionEvent = {
  type: 'create' | 'update';
  data: TaskStageType;
};

// Export the base evaluation type for use in other files
export type { BaseEvaluation };

// Add a standardization function for score results
