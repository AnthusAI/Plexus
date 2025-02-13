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
        sortDirection: options?.sortDirection,
        // Include stages when listing tasks
        include: modelName === 'Task' ? ['stages'] : undefined
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
  // Handle stages - if it's a LazyLoader, we'll return an empty array
  // The stages will be loaded later by the processTask function
  const stages: ProcessedTaskStage[] = Array.isArray(task.stages) 
    ? task.stages.map((stage: any) => ({
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
      }))
    : []

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
    dispatchStatus: task.dispatchStatus ?? undefined,
    celeryTaskId: task.celeryTaskId ?? undefined,
    workerNodeId: task.workerNodeId ?? undefined,
    updatedAt: task.updatedAt ?? undefined
  }
}

// Add this type at the top with other types
type ErrorHandler = (error: Error) => void;

export function observeRecentTasks(limit: number = 12): Observable<{ items: ProcessedTask[], isSynced: boolean }> {
  return new Observable(subscriber => {
    let isSynced = false
    const client = getClient()

    // Subscribe to task updates
    const taskSubscriptions = [
      client.models.Task.onCreate({}).subscribe({
        next: () => {
          refreshTasks()
        },
        error: (error: Error) => {
          console.error('Error in task onCreate subscription:', error)
        }
      }),
      client.models.Task.onUpdate({}).subscribe({
        next: () => {
          refreshTasks()
        },
        error: (error: Error) => {
          console.error('Error in task onUpdate subscription:', error)
        }
      })
    ]

    // Subscribe to stage updates
    const stageSubscription = (client.models.TaskStage as any).onUpdate({}).subscribe({
      next: () => {
        refreshTasks()
      },
      error: (error: Error) => {
        console.error('Error in stage onUpdate subscription:', error)
      }
    })

    // Initial load
    refreshTasks()

    async function refreshTasks() {
      try {
        const tasks = await listRecentTasks(limit)
        subscriber.next({ items: tasks, isSynced: true })
        isSynced = true
      } catch (error) {
        console.error('Error refreshing tasks:', error)
        if (!isSynced) {
          subscriber.next({ items: [], isSynced: false })
        }
      }
    }

    // Cleanup function
    return () => {
      taskSubscriptions.forEach(sub => sub.unsubscribe())
      stageSubscription.unsubscribe()
    }
  })
}

type TaskStageData = Schema['TaskStage']['type'];

async function processTask(task: AmplifyTask): Promise<ProcessedTask> {
  console.debug(`Starting to process task ${task.id}`);
  let stages: ProcessedTaskStage[] = [];

  try {
    if (!task.stages) {
      console.debug(`Task ${task.id} has no stages`);
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
        stages: [],
        dispatchStatus: task.dispatchStatus ?? undefined,
        celeryTaskId: task.celeryTaskId ?? undefined,
        workerNodeId: task.workerNodeId ?? undefined,
        updatedAt: task.updatedAt ?? undefined
      };
    }

    if (typeof task.stages === 'function') {
      console.debug(`Task ${task.id} has stages as function`);
      // Handle LazyLoader
      const stagesData = await task.stages();
      console.debug(`Loaded stages data for task ${task.id}:`, stagesData);
      if (stagesData?.data) {
        stages = stagesData.data.map((stage: TaskStageData) => ({
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
        }));
      }
    } else if (typeof task.stages === 'object' && task.stages !== null) {
      const stagesObj = task.stages as { items?: TaskStageData[] };
      if (stagesObj.items && Array.isArray(stagesObj.items)) {
        // Handle nested stages.items structure from GraphQL
        console.debug(`Task ${task.id} has stages.items array:`, stagesObj.items);
        stages = stagesObj.items.map((stage: TaskStageData) => ({
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
        }));
      } else if (Array.isArray(task.stages)) {
        console.debug(`Task ${task.id} has stages as array:`, task.stages);
        const stagesArray = task.stages as TaskStageData[];
        stages = stagesArray.map((stage: TaskStageData) => ({
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
        }));
      }
    } else {
      console.debug(`Task ${task.id} has unknown stages format:`, task.stages);
    }
  } catch (error: unknown) {
    console.error('Error loading stages for task:', error)
  }

  console.debug(`Finished processing task ${task.id}, stages:`, stages);

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
    dispatchStatus: task.dispatchStatus ?? undefined,
    celeryTaskId: task.celeryTaskId ?? undefined,
    workerNodeId: task.workerNodeId ?? undefined,
    updatedAt: task.updatedAt ?? undefined
  }
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

    console.debug('Raw GraphQL response:', JSON.stringify(response.data, null, 2));

    const result = response.data;
    if (!result?.listTaskByAccountIdAndUpdatedAt?.items) {
      return [];
    }

    // Process tasks and load their stages
    const processedTasks = await Promise.all(
      result.listTaskByAccountIdAndUpdatedAt.items.map(async (task) => {
        console.debug(`Processing task ${task.id}, stages:`, task.stages);
        const processed = await processTask(task);
        console.debug(`Processed task ${task.id}, final stages:`, processed.stages);
        return processed;
      })
    );

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