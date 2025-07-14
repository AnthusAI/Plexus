/**
 * Amplify API Module
 * ==================
 *
 * This module consolidates functions for interacting with the Amplify client for CRUD operations.
 * It includes functions such as listFromModel, getFromModel, createTask, and updateTask.
 *
 * Note: Transformation functions (convertToAmplifyTask, processTask) are still imported from data-operations.ts
 * and will eventually be moved into a dedicated transformers module.
 */

import { getClient } from './amplify-client';
import type { Schema } from '../amplify/data/resource';
import type { AmplifyListResult } from '@/types/shared';
import type { AmplifyTask, ProcessedTask } from './data-operations';
import { convertToAmplifyTask, processTask } from './transformers';
import { GraphQLResult, GraphQLSubscription } from '@aws-amplify/api';

// Add a type guard for GraphQL results
function isGraphQLResult<T>(response: GraphQLResult<T> | GraphQLSubscription<T>): response is GraphQLResult<T> {
  return !('subscribe' in response);
}

export async function listFromModel<T>(
  modelName: keyof (ReturnType<typeof getClient>)['models'],
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
      // Include extra fields for Task model
      include: modelName === 'Task' ? ['stages', 'scorecard', 'score'] : undefined
    });
    return {
      data: response.data,
      nextToken: response.nextToken || undefined
    };
  } catch (error) {
    console.error(`Error in listFromModel for ${modelName}:`, error);
    return { data: [] };
  }
}

export async function getFromModel<T extends { id: string }>(
  modelName: keyof (ReturnType<typeof getClient>)['models'],
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

export async function listRecentTasks(limit: number = 12): Promise<{ tasks: ProcessedTask[] }> {
  try {
    const currentClient = getClient();

    // Get the account ID by key
    ;
    const accountResponse = await listFromModel<Schema['Account']['type']>(
      'Account',
      { filter: { key: { eq: ACCOUNT_KEY } } }
    );

    if (!accountResponse.data?.length) {
      console.error('No account found with key:', ACCOUNT_KEY);
      return { tasks: [] };
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
              output
              attachedFiles
              currentStageId
              scorecardId
              scoreId
              celeryTaskId
              workerNodeId
              scorecard {
                id
                name
              }
              score {
                id
                name
              }
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
              evaluation {
                id
                type
                metrics
                metricsExplanation
                inferences
                accuracy
                cost
                status
                startedAt
                elapsedSeconds
                estimatedRemainingSeconds
                totalItems
                processedItems
                errorMessage
                errorDetails
                confusionMatrix
                scoreGoal
                datasetClassDistribution
                isDatasetClassDistributionBalanced
                predictedClassDistribution
                isPredictedClassDistributionBalanced
                scoreResults {
                  items {
                    id
                    value
                    confidence
                    metadata
                    explanation
                    itemId
                    createdAt
                  }
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
        limit: limit || 12
      }
    }) as GraphQLResult<{
      listTaskByAccountIdAndUpdatedAt: {
        items: Schema['Task']['type'][];
        nextToken?: string | null;
      };
    }>;

    if (response.errors?.length) {
      console.error('GraphQL errors:', response.errors);
      throw new Error(`GraphQL errors: ${response.errors.map((e: Error) => e.message).join(', ')}`);
    }

    if (!response.data) {
      console.error('No data returned from GraphQL query');
      return { tasks: [] };
    }

    const result = response.data;
    if (!result?.listTaskByAccountIdAndUpdatedAt?.items) {
      console.error('No items found in GraphQL response');
      return { tasks: [] };
    }


    const tasks = await Promise.all(
      result.listTaskByAccountIdAndUpdatedAt.items.map(async (item: any) => {
        const amplifyTask = convertToAmplifyTask(item);
        return processTask(amplifyTask);
      })
    );

    return { tasks };
  } catch (error) {
    console.error('Error listing recent tasks:', error);
    return { tasks: [] };
  }
} 