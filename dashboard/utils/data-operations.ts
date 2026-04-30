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
  procedureId?: string | null;
  baseline_evaluation_id?: string | null;
  current_baseline_evaluation_id?: string | null;
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

export type NormalizedIdentifierItem = {
  name: string;
  value: string;
  url?: string;
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
  scoreVersionId
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
  selectedScore: string | null = null,
  nextToken: string | null = null
): Promise<{ items: any[], nextToken: string | null }> {
  try {
    const client = getClient();
    
    // Get the account ID if not provided
    if (!accountId) {
      const ACCOUNT_KEY = process.env.NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY || '';
      if (!ACCOUNT_KEY) {
        throw new Error('NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY environment variable not set');
      }
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
      limit: limit || 100,
      nextToken: nextToken
    };
    
    // Determine which GSI to use based on the filters
    if (selectedScorecard && selectedScore) {
      // If both scorecard and score are selected, use the scoreId GSI directly
      query = `
        query ListEvaluationByScoreIdAndUpdatedAt(
          $scoreId: String!
          $sortDirection: ModelSortDirection!
          $limit: Int
          $nextToken: String
        ) {
          listEvaluationByScoreIdAndUpdatedAt(
            scoreId: $scoreId
            sortDirection: $sortDirection
            limit: $limit
            nextToken: $nextToken
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
          $nextToken: String
        ) {
          listEvaluationByScorecardIdAndUpdatedAt(
            scorecardId: $scorecardId
            sortDirection: $sortDirection
            limit: $limit
            nextToken: $nextToken
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
          $nextToken: String
        ) {
          listEvaluationByAccountIdAndUpdatedAt(
            accountId: $accountId
            sortDirection: $sortDirection
            limit: $limit
            nextToken: $nextToken
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
    
    // Extract items from the response based on which query was used
    const result = 
      responseData?.listEvaluationByAccountIdAndUpdatedAt || 
      responseData?.listEvaluationByScorecardIdAndUpdatedAt || 
      responseData?.listEvaluationByScoreIdAndUpdatedAt;
    
    if (!result?.items) {
      return { items: [], nextToken: null };
    }
    
    return { items: result.items, nextToken: result.nextToken || null };
  } catch (error) {
    console.error('Error in listRecentEvaluations:', error);
    return { items: [], nextToken: null };
  }
}

export async function fetchEvaluationById(
  evaluationId: string
): Promise<ProcessedEvaluation | null> {
  try {
    const client = getClient();
    const query = `
      query GetEvaluation($id: ID!) {
        getEvaluation(id: $id) {
          ${EVALUATION_FIELDS}
        }
      }
    `;
    const response = await client.graphql({ query, variables: { id: evaluationId } }) as GraphQLResult<any>;
    const raw = response?.data?.getEvaluation;
    if (!raw) return null;
    return transformEvaluation(raw);
  } catch (error) {
    console.error('Error in fetchEvaluationById:', error);
    return null;
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
        const response = await listRecentEvaluations(limit, accountId, selectedScorecard, selectedScore, null);
        
        // Merge: preserve any items already received via create events during loading
        const loadedIds = new Set(response.items.map((e: any) => e.id));
        const pendingCreates = evaluations.filter((e: any) => !loadedIds.has(e.id));
        evaluations = [...pendingCreates, ...response.items];
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
        if (accountId && evaluation.accountId && evaluation.accountId !== accountId) return;
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
            scoreVersionId
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
            scoreVersionId
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

type ParsedScoreResultMetadata = {
  processedMetadata: {
    human_label: string | null;
    correct: boolean;
    human_explanation: string | null;
    text: string | null;
  };
  nestedScoreResult: any | null;
  parsedMetadata: any;
};

export function extractScoreResultItemIdentifiers(result: any): NormalizedIdentifierItem[] | null {
  if (!result?.item) {
    return null;
  }

  const relationshipIdentifiers = result.item?.itemIdentifiers?.items;
  if (Array.isArray(relationshipIdentifiers) && relationshipIdentifiers.length > 0) {
    return relationshipIdentifiers
      .slice()
      .sort((a: any, b: any) => (a.position || 0) - (b.position || 0))
      .map((identifier: any) => ({
        name: identifier.name,
        value: identifier.value,
        url: identifier.url || undefined
      }));
  }

  const legacyIdentifiers = result.item?.identifiers;
  if (!legacyIdentifiers) {
    return null;
  }

  const normalizeIdentifierEntry = (entry: any): NormalizedIdentifierItem | null => {
    if (!entry || typeof entry !== 'object') return null;
    if (typeof entry.name !== 'string' || !entry.name) return null;

    const rawValue = entry.value ?? entry.id;
    if (rawValue === undefined || rawValue === null) return null;

    return {
      name: entry.name,
      value: String(rawValue),
      url: typeof entry.url === 'string' ? entry.url : undefined
    };
  };

  if (Array.isArray(legacyIdentifiers)) {
    const normalized = legacyIdentifiers
      .map((entry: any) => normalizeIdentifierEntry(entry))
      .filter((entry: NormalizedIdentifierItem | null): entry is NormalizedIdentifierItem => entry !== null);
    return normalized.length > 0 ? normalized : null;
  }

  if (typeof legacyIdentifiers === 'string') {
    try {
      const parsed = JSON.parse(legacyIdentifiers);
      const normalized = Array.isArray(parsed)
        ? parsed
            .map((entry: any) => normalizeIdentifierEntry(entry))
            .filter((entry: NormalizedIdentifierItem | null): entry is NormalizedIdentifierItem => entry !== null)
        : [];
      return normalized.length > 0 ? normalized : null;
    } catch {
      return null;
    }
  }

  if (typeof legacyIdentifiers === 'object') {
    const normalized = Object.entries(legacyIdentifiers as Record<string, unknown>)
      .map(([name, value]) => {
        if (!name || value === undefined || value === null) return null;
        return { name, value: String(value) };
      })
      .filter((entry: NormalizedIdentifierItem | null): entry is NormalizedIdentifierItem => entry !== null);
    return normalized.length > 0 ? normalized : null;
  }

  return null;
}

function parseScoreResultMetadata(rawMetadata: unknown): ParsedScoreResultMetadata {
  let parsedMetadata: any;
  try {
    if (typeof rawMetadata === 'string') {
      parsedMetadata = JSON.parse(rawMetadata);
      if (typeof parsedMetadata === 'string') {
        parsedMetadata = JSON.parse(parsedMetadata);
      }
    } else {
      parsedMetadata = rawMetadata || {};
    }
  } catch {
    parsedMetadata = {};
  }

  const firstResultKey = parsedMetadata?.results ? Object.keys(parsedMetadata.results)[0] : null;
  const nestedScoreResult = firstResultKey && parsedMetadata.results ? parsedMetadata.results[firstResultKey] : null;

  return {
    processedMetadata: {
      human_label: nestedScoreResult?.metadata?.human_label ?? parsedMetadata.human_label ?? null,
      correct: Boolean(nestedScoreResult?.metadata?.correct ?? parsedMetadata.correct),
      human_explanation: nestedScoreResult?.metadata?.human_explanation ?? parsedMetadata.human_explanation ?? null,
      text: nestedScoreResult?.metadata?.text ?? parsedMetadata.text ?? null
    },
    nestedScoreResult,
    parsedMetadata
  };
}

export function transformScoreResultForDisplay(result: any) {
  const { processedMetadata, nestedScoreResult, parsedMetadata } = parseScoreResultMetadata(result?.metadata);

  return {
    id: result?.id,
    value: result?.value,
    confidence: result?.confidence ?? null,
    metadata: processedMetadata,
    explanation: result?.explanation ?? nestedScoreResult?.explanation ?? null,
    trace: result?.trace ?? nestedScoreResult?.trace ?? null,
    itemId: result?.itemId ?? parsedMetadata?.item_id?.toString() ?? null,
    itemIdentifiers: extractScoreResultItemIdentifiers(result),
    createdAt: result?.createdAt || new Date().toISOString(),
    feedbackItem: result?.feedbackItem ?? null
  };
}

export function parseTaskMetadata(rawMetadata: unknown): Record<string, unknown> | null {
  if (!rawMetadata) return null;

  if (typeof rawMetadata === 'string') {
    try {
      const parsed = JSON.parse(rawMetadata);
      return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : null;
    } catch {
      return null;
    }
  }

  if (typeof rawMetadata === 'object') {
    return rawMetadata as Record<string, unknown>;
  }

  return null;
}

export function getTaskProcedureId(task: AmplifyTask | null | undefined): string | null {
  const metadata = parseTaskMetadata(task?.metadata);
  if (!metadata) return null;

  const procedureId = metadata.procedure_id ?? metadata.procedureId;
  return typeof procedureId === 'string' && procedureId.trim() ? procedureId : null;
}

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



  // Get scorecard and score data
  const scorecardData = evaluation.scorecard ? 
    (typeof evaluation.scorecard === 'function' ? 
      getValueFromLazyLoader(evaluation.scorecard)?.data : 
      evaluation.scorecard) : null;

  const scoreData = evaluation.score ?
    (typeof evaluation.score === 'function' ?
      getValueFromLazyLoader(evaluation.score)?.data :
      evaluation.score) : null;

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
  const transformedScoreResults = standardizedScoreResults.map((result: any) =>
    transformScoreResultForDisplay(result)
  );

  const procedureId = getTaskProcedureId(taskData);
  const parsedParameters = parseJsonMaybeDeep(evaluation.parameters);
  const parsedMetadata = parsedParameters && typeof parsedParameters === 'object'
    ? parseJsonMaybeDeep((parsedParameters as Record<string, unknown>).metadata)
    : null;
  const baselineEvaluationId = parsedMetadata && typeof parsedMetadata === 'object' && typeof (parsedMetadata as Record<string, unknown>).baseline === 'string'
    ? (parsedMetadata as Record<string, unknown>).baseline as string
    : null;
  const currentBaselineEvaluationId = parsedMetadata && typeof parsedMetadata === 'object' && typeof (parsedMetadata as Record<string, unknown>).current_baseline === 'string'
    ? (parsedMetadata as Record<string, unknown>).current_baseline as string
    : null;

  // Transform the evaluation into the format expected by components
  const transformedEvaluation: ProcessedEvaluation = {
    ...evaluation, // Include all base evaluation fields
    task: taskData,
    scorecard: scorecardData ? { name: scorecardData.name } : null,
    score: scoreData ? { name: scoreData.name } : null,
    procedureId,
    baseline_evaluation_id: baselineEvaluationId,
    current_baseline_evaluation_id: currentBaselineEvaluationId,
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

function parseJsonMaybeDeep(value: unknown): unknown {
  let current = value;

  for (let i = 0; i < 2; i += 1) {
    if (typeof current !== 'string') {
      return current;
    }

    try {
      current = JSON.parse(current);
    } catch {
      return current;
    }
  }

  return current;
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
  costDetails?: any;
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
  scorecardId?: string | null;
  scoreId?: string | null;
  scoreVersionId?: string | null;
  parameters?: string | null;
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
