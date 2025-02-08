import { generateClient } from 'aws-amplify/data';
import { Schema } from '@/amplify/data/resource';
import { Observable } from 'rxjs';

// Define the shape of the task data we expect from Amplify
export type AmplifyTask = Schema['Task']['type'];

export type ProcessedTask = {
  id: string;
  command: string;
  type: string;
  status: string;
  target: string;
  metadata?: any;
  currentStageId?: string | null;
  updatedAt?: string | null;
  scorecardId?: string | null;
  scoreId?: string | null;
  createdAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
  estimatedCompletionAt?: string | null;
  stages: Array<{
    id: string;
    name: string;
    order: number;
    status: string;
    processedItems?: number | null;
    totalItems?: number | null;
    startedAt?: string | null;
    completedAt?: string | null;
    estimatedCompletionAt?: string | null;
    statusMessage?: string | null;
  }>;
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

interface GraphQLResult<T> {
  data?: T;
  errors?: GraphQLError[];
}

type ListTaskResponse = {
  listTaskByAccountIdAndUpdatedAt: {
    items: Schema['Task']['type'][];
    nextToken: string | null;
  };
};

export function getClient(): AmplifyClient {
  if (!client) {
    client = generateClient<Schema>() as AmplifyClient;
  }
  return client;
}

export async function listFromModel<T extends { id: string }>(
  modelName: keyof AmplifyClient['models'],
  options?: {
    limit?: number,
    filter?: Record<string, any>,
    nextToken?: string,
    sortDirection?: 'ASC' | 'DESC'
  }
): Promise<AmplifyListResult<T>> {
  const currentClient = getClient();
  
  try {
    // Collect all results across pages
    let allData: T[] = []
    let currentNextToken = options?.nextToken

    do {
      const response = await (currentClient.models[modelName] as any).list({
        limit: options?.limit,
        filter: options?.filter,
        nextToken: currentNextToken,
        sortDirection: options?.sortDirection
      });

      if (response.data?.length) {
        allData = [...allData, ...response.data]
      }

      currentNextToken = response.nextToken
    } while (currentNextToken && (!options?.limit || allData.length < options.limit))

    // If we have a limit, respect it exactly
    if (options?.limit && allData.length > options.limit) {
      allData = allData.slice(0, options.limit)
    }

    // Sort by updatedAt if available, otherwise by createdAt
    if (allData.length > 0) {
      if ('updatedAt' in allData[0]) {
        allData.sort((a: any, b: any) =>
          new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        )
      } else if ('createdAt' in allData[0]) {
        allData.sort((a: any, b: any) =>
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        )
      }
    }

    return {
      data: allData,
      nextToken: currentNextToken
    };
  } catch (error) {
    console.error(`Error listing ${modelName}:`, error);
    return { data: [], nextToken: null };
  }
}

export function transformAmplifyTask(task: AmplifyTask): ProcessedTask {
  return {
    id: task.id,
    command: task.command || '',
    type: task.type,
    status: task.status,
    target: task.target,
    metadata: task.metadata,
    currentStageId: task.currentStageId,
    updatedAt: task.updatedAt,
    scorecardId: task.scorecardId,
    scoreId: task.scoreId,
    createdAt: task.createdAt || new Date().toISOString(),
    startedAt: task.startedAt,
    completedAt: task.completedAt,
    estimatedCompletionAt: task.estimatedCompletionAt,
    stages: []  // Stages are loaded separately by processTask
  }
}

// Add this type at the top with other types
interface GraphQLTaskStages {
  items: Schema['TaskStage']['type'][];
}

async function processTask(task: AmplifyTask): Promise<ProcessedTask> {
  let stages: Schema['TaskStage']['type'][] = [];
  try {
    // Handle both GraphQL response format and Amplify client format
    if (typeof task.stages === 'function') {
      // Amplify client format
      const stagesData = await task.stages();
      if (stagesData?.data) {
        stages = stagesData.data;
      }
    } else if (task.stages && 'items' in task.stages) {
      // GraphQL response format
      const graphqlStages = task.stages as GraphQLTaskStages;
      stages = graphqlStages.items;
    }
  } catch (error) {
    console.error('Error loading stages for task:', error);
  }
  
  return {
    id: task.id,
    command: task.command || '',
    type: task.type,
    status: task.status,
    target: task.target,
    metadata: task.metadata,
    currentStageId: task.currentStageId,
    updatedAt: task.updatedAt,
    scorecardId: task.scorecardId,
    scoreId: task.scoreId,
    createdAt: task.createdAt || new Date().toISOString(),
    startedAt: task.startedAt,
    completedAt: task.completedAt,
    estimatedCompletionAt: task.estimatedCompletionAt,
    stages: stages.map(stage => ({
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
}

export async function listRecentTasks(limit: number = 10): Promise<ProcessedTask[]> {
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
      throw new Error(`GraphQL errors: ${response.errors.map(e => e.message).join(', ')}`);
    }

    const result = response.data;
    if (!result?.listTaskByAccountIdAndUpdatedAt?.items) {
      return [];
    }

    // Process tasks and load their stages
    const processedTasks = await Promise.all(
      result.listTaskByAccountIdAndUpdatedAt.items.map(processTask)
    );

    return processedTasks;
  } catch (error) {
    console.error('Error listing recent tasks:', error);
    return [];
  }
}

export function observeRecentTasks(limit: number = 12): Observable<{ items: ProcessedTask[], isSynced: boolean }> {
  return new Observable(handlers => {
    const currentClient = getClient();
    let accountId: string | null = null;

    // Get the account ID first
    const ACCOUNT_KEY = 'call-criteria';
    listFromModel<Schema['Account']['type']>(
      'Account',
      { filter: { key: { eq: ACCOUNT_KEY } } }
    ).then(response => {
      if (!response.data?.length) {
        console.error('No account found with key:', ACCOUNT_KEY);
        handlers.error(new Error('No account found'));
        return;
      }

      accountId = response.data[0].id;

      // Initial fetch
      listRecentTasks(limit).then(response => {
        handlers.next({ items: response, isSynced: true });
      }).catch(handlers.error);

      // Subscribe to changes
      const createSub = (currentClient.models.Task as any).onCreate().subscribe({
        next: async () => {
          if (!accountId) return;
          const response = await listRecentTasks(limit);
          handlers.next({ items: response, isSynced: true });
        },
        error: handlers.error
      });

      const updateSub = (currentClient.models.Task as any).onUpdate().subscribe({
        next: async () => {
          if (!accountId) return;
          const response = await listRecentTasks(limit);
          handlers.next({ items: response, isSynced: true });
        },
        error: handlers.error
      });

      const stageSub = (currentClient.models.TaskStage as any).onUpdate().subscribe({
        next: async () => {
          if (!accountId) return;
          const response = await listRecentTasks(limit);
          handlers.next({ items: response, isSynced: true });
        },
        error: handlers.error
      });

      // Cleanup subscriptions
      return () => {
        createSub.unsubscribe();
        updateSub.unsubscribe();
        stageSub.unsubscribe();
      };
    }).catch(error => {
      console.error('Error getting account:', error);
      handlers.error(error);
    });
  });
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