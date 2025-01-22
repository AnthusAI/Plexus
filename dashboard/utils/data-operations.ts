import { generateClient } from 'aws-amplify/data';
import { Schema } from '@/amplify/data/resource';
import { Observable } from 'rxjs';

let client: ReturnType<typeof generateClient<Schema>>;

export function getClient(): ReturnType<typeof generateClient<Schema>> {
  if (!client) {
    client = generateClient<Schema>();
    console.log('Generated new client:', client);
    console.log('Client models:', client.models);
  }
  return client;
}

export async function listFromModel<T extends keyof Schema>(
  modelName: T,
  options?: {
    limit?: number,
    filter?: Record<string, any>
  }
) {
  console.log('listFromModel called with:', { modelName, options });
  const currentClient = getClient();
  console.log('client at time of call:', currentClient);
  console.log('client.models at time of call:', currentClient.models);
  try {
    const response = await (currentClient.models[modelName] as any).list({
      limit: options?.limit,
      filter: options?.filter
    });
    return {
      data: [...response.data].sort((a, b) =>
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      )
    };
  } catch (error) {
    console.error(`Error listing ${modelName}:`, error);
    return { data: [] };
  }
}

export async function listRecentTasks(limit: number = 12) {
  const currentClient = getClient();
  console.log('client at time of call:', currentClient);
  console.log('client.models at time of call:', currentClient.models);
  try {
    const response = await (currentClient.models.Task as any).list({
      limit,
      include: ['stages']
    });
    
    // Fetch stages for each task
    const tasksWithStages = await Promise.all(
      response.data.map(async (task: any) => {
        const stagesResponse = await task.stages();
        return {
          ...task,
          stages: stagesResponse.data
        };
      })
    );
    
    // Sort by createdAt in reverse chronological order
    const sortedTasks = [...tasksWithStages].sort((a, b) => 
      new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );
    
    console.log('Task list response:', {
      data: sortedTasks,
      count: sortedTasks.length,
      firstRecord: sortedTasks[0],
      nextToken: response.nextToken
    });
    return { data: sortedTasks };
  } catch (error) {
    console.error('Error listing tasks:', error);
    return { data: [] };
  }
}

export function observeRecentTasks(limit: number = 12): Observable<{ items: Schema['Task']['type'][], isSynced: boolean }> {
  return new Observable(handlers => {
    const currentClient = getClient();

    // Initial fetch
    listRecentTasks(limit).then(response => {
      handlers.next({ items: response.data, isSynced: true });
    }).catch(handlers.error);

    // Subscribe to changes
    const createSub = (currentClient.models.Task as any).onCreate({}).subscribe({
      next: async () => {
        const response = await listRecentTasks(limit);
        handlers.next({ items: response.data, isSynced: true });
      },
      error: handlers.error
    });

    const updateSub = (currentClient.models.Task as any).onUpdate({}).subscribe({
      next: async () => {
        const response = await listRecentTasks(limit);
        handlers.next({ items: response.data, isSynced: true });
      },
      error: handlers.error
    });

    const stageSub = (currentClient.models.TaskStage as any).onUpdate({}).subscribe({
      next: async () => {
        const response = await listRecentTasks(limit);
        handlers.next({ items: response.data, isSynced: true });
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

export async function getFromModel<T extends keyof Schema>(
  modelName: T,
  id: string
) {
  try {
    const response = await (client.models[modelName] as any).get({ id });
    return response;
  } catch (error) {
    console.error(`Error getting ${modelName}:`, error);
    return { data: null };
  }
} 