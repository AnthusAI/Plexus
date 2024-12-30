import { generateClient } from 'aws-amplify/api';
import { Schema } from '@/amplify/data/resource';

const dataClient = generateClient<Schema>();

export { dataClient }

type ModelName = keyof Schema;

export async function listFromModel<T extends ModelName>(
  modelName: T,
  options?: {
    filter?: Record<string, { eq?: unknown }>,
    limit?: number,
    nextToken?: string
  }
) {
  try {
    // @ts-ignore - Amplify Gen2 typing issue
    const response = await dataClient.models[modelName].list(options);
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

export async function getFromModel<T extends ModelName>(
  modelName: T,
  id: string
) {
  try {
    // @ts-ignore - Amplify Gen2 typing issue
    const response = await dataClient.models[modelName].get({ id });
    return response;
  } catch (error) {
    console.error(`Error getting ${modelName}:`, error);
    return { data: null };
  }
} 