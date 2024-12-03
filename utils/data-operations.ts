import { generateClient } from 'aws-amplify/data'
import type { Schema } from '@/amplify/data/resource'
import type { AmplifyListResult, AmplifyGetResult } from '@/types/shared'

const client = generateClient<Schema>()

interface BatchJobType {
  createdAt: string
  [key: string]: any
}

export async function listFromModel<T>(
  modelName: keyof Schema,
  filter?: any,
  nextToken?: string,
  limit?: number
): Promise<{ data: T[] }> {
  const options: any = {}
  if (filter) options.filter = filter
  if (nextToken) options.nextToken = nextToken
  if (limit) options.limit = limit
  
  try {
    const response = await client.models[modelName].list(options)
    
    if (modelName === 'BatchJob' && Array.isArray(response.data)) {
      return {
        data: [...response.data].sort((a: any, b: any) => 
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        )
      }
    }
    
    return response
  } catch (error) {
    console.error(`Error listing from ${modelName}:`, error)
    throw error
  }
}

export async function getFromModel<T>(
  modelName: keyof Schema,
  id: string
): Promise<AmplifyGetResult<T>> {
  const response = await client.models[modelName].get({ id })
  return response as AmplifyGetResult<T>
}

export const dataClient = client 