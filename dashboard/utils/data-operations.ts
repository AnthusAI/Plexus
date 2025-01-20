import { generateClient } from 'aws-amplify/data';
import { Schema } from '@/amplify/data/resource';

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
  }
) {
  console.log('listFromModel called with:', { modelName, options });
  const currentClient = getClient();
  console.log('client at time of call:', currentClient);
  console.log('client.models at time of call:', currentClient.models);
  try {
    const response = await (currentClient.models[modelName] as any).list({
      limit: options?.limit
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

export async function listRecentActions(limit: number = 12) {
  const currentClient = getClient();
  console.log('client at time of call:', currentClient);
  console.log('client.models at time of call:', currentClient.models);
  try {
    const response = await (currentClient.models.Action as any).list({
      limit,
      include: ['stages']
    });
    
    // Fetch stages for each action
    const actionsWithStages = await Promise.all(
      response.data.map(async (action: any) => {
        const stagesResponse = await action.stages();
        return {
          ...action,
          stages: stagesResponse.data
        };
      })
    );
    
    // Sort by createdAt in reverse chronological order
    const sortedActions = [...actionsWithStages].sort((a, b) => 
      new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );
    
    console.log('Action list response:', {
      data: sortedActions,
      count: sortedActions.length,
      firstRecord: sortedActions[0],
      nextToken: response.nextToken
    });
    return { data: sortedActions };
  } catch (error) {
    console.error('Error listing actions:', error);
    return { data: [] };
  }
}

export function observeRecentActions(limit: number = 12) {
  console.log('observeRecentActions called with:', { limit });
  const currentClient = getClient();
  console.log('client at time of call:', currentClient);
  console.log('client.models at time of call:', currentClient.models);
  const subscription = {
    subscribe: (handlers: { 
      next: (data: { items: Schema['Action']['type'][], isSynced: boolean }) => void,
      error: (error: Error) => void 
    }) => {
      // Initial fetch
      listRecentActions(limit).then(response => {
        handlers.next({ items: response.data, isSynced: true });
      }).catch(handlers.error);

      // Subscribe to Action updates
      const actionSubs = [
        // Subscribe to new actions
        (currentClient.models.Action as any).onCreate({}).subscribe({
          next: async () => {
            const response = await listRecentActions(limit);
            handlers.next({ items: response.data, isSynced: true });
          },
          error: handlers.error
        }),
        // Subscribe to action updates
        (currentClient.models.Action as any).onUpdate({}).subscribe({
          next: async () => {
            const response = await listRecentActions(limit);
            handlers.next({ items: response.data, isSynced: true });
          },
          error: handlers.error
        })
      ];

      // Subscribe to stage updates
      const stageSub = (currentClient.models.ActionStage as any).onUpdate({}).subscribe({
        next: async () => {
          const response = await listRecentActions(limit);
          handlers.next({ items: response.data, isSynced: true });
        },
        error: handlers.error
      });

      return {
        unsubscribe: () => {
          actionSubs.forEach(sub => sub.unsubscribe());
          stageSub.unsubscribe();
        }
      };
    }
  };

  return subscription;
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