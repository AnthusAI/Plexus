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
  stages: ProcessedTaskStage[];
  dispatchStatus?: 'DISPATCHED' | string;  // Allow both literal and string
  celeryTaskId?: string;
  workerNodeId?: string;
  updatedAt?: string;  // Add updatedAt field
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
    command: task.command,
    type: task.type,
    status: task.status,
    target: task.target,
    description: task.description ?? undefined,
    metadata: task.metadata ?? undefined,
    createdAt: task.createdAt ?? undefined,
    startedAt: task.startedAt ?? undefined,
    completedAt: task.completedAt ?? undefined,
    estimatedCompletionAt: task.estimatedCompletionAt ?? undefined,
    errorMessage: task.errorMessage ?? undefined,
    errorDetails: task.errorDetails ?? undefined,
    stdout: task.stdout ?? undefined,
    stderr: task.stderr ?? undefined,
    currentStageId: task.currentStageId ?? undefined,
    stages: task.stages?.map(stage => ({
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
    })) ?? [],
    dispatchStatus: task.dispatchStatus ?? undefined,
    celeryTaskId: task.celeryTaskId ?? undefined,
    workerNodeId: task.workerNodeId ?? undefined,
    updatedAt: task.updatedAt ?? undefined
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
    description: task.description,
    metadata: task.metadata,
    createdAt: task.createdAt,
    startedAt: task.startedAt,
    completedAt: task.completedAt,
    estimatedCompletionAt: task.estimatedCompletionAt,
    errorMessage: task.errorMessage,
    errorDetails: task.errorDetails,
    stdout: task.stdout,
    stderr: task.stderr,
    currentStageId: task.currentStageId,
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
    })),
    dispatchStatus: task.dispatchStatus,
    celeryTaskId: task.celeryTaskId,
    workerNodeId: task.workerNodeId,
    updatedAt: task.updatedAt
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
  console.log('Setting up task subscription...');
  return new Observable(handlers => {
    const currentClient = getClient();
    let accountId: string | null = null;

    // Get the account ID first
    const ACCOUNT_KEY = 'call-criteria';
    console.log('Fetching account ID for subscription...');
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
      console.log('Account ID found:', accountId);

      // Initial fetch
      console.log('Performing initial task fetch...');
      listRecentTasks(limit).then(response => {
        console.log('Initial tasks loaded:', {
          count: response.length,
          tasks: response.map(t => ({
            id: t.id,
            celeryTaskId: t.celeryTaskId,
            workerNodeId: t.workerNodeId,
            dispatchStatus: t.dispatchStatus
          }))
        });
        handlers.next({ items: response, isSynced: true });
      }).catch(handlers.error);

      console.log('Setting up subscriptions...');
      // Subscribe to changes with more frequent updates for claiming
      const createSub = (currentClient.models.Task as any).onCreate().subscribe({
        next: async () => {
          console.log('Task created event received');
          if (!accountId) return;
          const response = await listRecentTasks(limit);
          handlers.next({ items: response, isSynced: true });
        },
        error: (error) => {
          console.error('Error in task create subscription:', error);
          handlers.error(error);
        }
      });

      const updateSub = (currentClient.models.Task as any).onUpdate().subscribe({
        next: async (event: any) => {
          // Log the full event to see its structure
          console.log('Full Update Event:', event);

          // In Amplify Gen2, fields are methods that need to be called
          const updatedTask = event?.element;
          if (updatedTask) {
            console.log('Task Update Event:', {
              id: updatedTask.id(),
              celeryTaskId: updatedTask.celeryTaskId(),
              workerNodeId: updatedTask.workerNodeId(),
              dispatchStatus: updatedTask.dispatchStatus(),
              status: updatedTask.status()
            });
          }

          // Always trigger an update for task updates to ensure we catch claiming
          if (!accountId) return;
          try {
            const response = await listRecentTasks(limit);
            console.log('Task List Response:', {
              count: response.length,
              tasks: response.map(t => ({
                id: t.id,
                celeryTaskId: t.celeryTaskId,
                workerNodeId: t.workerNodeId,
                dispatchStatus: t.dispatchStatus,
                status: t.status
              }))
            });
            handlers.next({ items: response, isSynced: true });
          } catch (error) {
            console.error('Error fetching tasks after update:', error);
          }
        },
        error: (error: Error) => {
          console.error('Error in task update subscription:', error);
          handlers.error(error);
        }
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
      console.log('Subscriptions set up successfully');
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