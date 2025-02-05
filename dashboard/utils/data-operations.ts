import { generateClient } from 'aws-amplify/data';
import { Schema } from '@/amplify/data/resource';
import { Observable } from 'rxjs';

// Define the shape of the task data we expect from Amplify
export type AmplifyTask = {
  id: string;
  accountId: string;
  type: string;
  status: string;
  target?: string | null;
  currentStageId?: string | null;
  updatedAt?: string | null;
  createdAt: string;
  scorecardId?: string | null;
  scoreId?: string | null;
  stages: () => Promise<{
    data: Array<{
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
  }>;
}

export type ProcessedTask = {
  id: string;
  type: string;
  status: string;
  target?: string | null;
  currentStageId?: string | null;
  updatedAt?: string | null;
  scorecardId?: string | null;
  scoreId?: string | null;
  createdAt: string;
  stages: Schema['TaskStage']['type'][];
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
  };
}

export type AmplifyListResult<T> = {
  data: T[];
  nextToken?: string | null;
}

let client: AmplifyClient;

export function getClient(): AmplifyClient {
  if (!client) {
    client = generateClient<Schema>() as AmplifyClient;
    console.log('Generated new client:', client);
    console.log('Client models:', client.models);
  }
  return client;
}

export async function listFromModel<T extends { id: string }>(
  modelName: keyof AmplifyClient['models'],
  options?: {
    limit?: number,
    filter?: Record<string, any>,
    nextToken?: string
  }
): Promise<AmplifyListResult<T>> {
  console.log('listFromModel called with:', { modelName, options });
  const currentClient = getClient();
  console.log('client at time of call:', currentClient);
  console.log('client.models at time of call:', currentClient.models);
  try {
    // Collect all results across pages
    let allData: T[] = []
    let currentNextToken = options?.nextToken

    do {
      const response = await (currentClient.models[modelName] as any).list({
        limit: options?.limit,
        filter: options?.filter,
        nextToken: currentNextToken
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

    // Sort by createdAt if available
    if (allData.length > 0 && 'createdAt' in allData[0]) {
      allData.sort((a: any, b: any) =>
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      )
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

async function processTask(task: Schema['Task']['type']): Promise<ProcessedTask> {
  let stages: Schema['TaskStage']['type'][] = [];
  try {
    if (task.stages) {
      const stagesResponse = await task.stages();
      stages = stagesResponse.data || [];
    }
  } catch (error) {
    console.error('Error loading stages for task:', error);
  }
  
  return {
    id: task.id,
    type: task.type,
    status: task.status,
    target: task.target,
    currentStageId: task.currentStageId,
    updatedAt: task.updatedAt,
    scorecardId: task.scorecardId,
    scoreId: task.scoreId,
    createdAt: task.createdAt ?? new Date().toISOString(),
    stages
  };
}

export async function listRecentTasks(limit: number = 10): Promise<ProcessedTask[]> {
  try {
    const currentClient = getClient();
    if (!currentClient.models.Task) {
      throw new Error('Task model not found');
    }

    type TaskListResponse = {
      data: Schema['Task']['type'][];
      nextToken?: string | null;
    };

    // Cast the client.models.Task to a more specific type
    const taskModel = currentClient.models.Task as {
      list: (options: { limit?: number; include?: string[] }) => Promise<TaskListResponse>;
    };

    const response = await taskModel.list({
      limit,
      include: ['stages']
    });

    if (!response.data) {
      return [];
    }

    // Process tasks and load their stages
    const processedTasks = await Promise.all(
      response.data.map(processTask)
    );

    // Sort by createdAt in reverse chronological order
    return processedTasks.sort((a, b) => 
      new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );
  } catch (error) {
    console.error('Error listing recent tasks:', error);
    return [];
  }
}

export function observeRecentTasks(limit: number = 12): Observable<{ items: ProcessedTask[], isSynced: boolean }> {
  return new Observable(handlers => {
    const currentClient = getClient();

    // Initial fetch
    listRecentTasks(limit).then(response => {
      handlers.next({ items: response, isSynced: true });
    }).catch(handlers.error);

    // Define subscription type
    type SubscriptionType = {
      subscribe: (handlers: { 
        next: () => void; 
        error: (error: any) => void 
      }) => { 
        unsubscribe: () => void 
      };
    };

    // Cast subscription methods to specific types
    const taskModel = currentClient.models.Task as {
      onCreate: (options: {}) => SubscriptionType;
      onUpdate: (options: {}) => SubscriptionType;
    };

    const taskStageModel = currentClient.models.TaskStage as {
      onUpdate: (options: {}) => SubscriptionType;
    };

    // Subscribe to changes
    const createSub = taskModel.onCreate({}).subscribe({
      next: async () => {
        const response = await listRecentTasks(limit);
        handlers.next({ items: response, isSynced: true });
      },
      error: handlers.error
    });

    const updateSub = taskModel.onUpdate({}).subscribe({
      next: async () => {
        const response = await listRecentTasks(limit);
        handlers.next({ items: response, isSynced: true });
      },
      error: handlers.error
    });

    const stageSub = taskStageModel.onUpdate({}).subscribe({
      next: async () => {
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