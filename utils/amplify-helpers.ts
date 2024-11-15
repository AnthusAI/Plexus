import type { Schema } from "@/amplify/data/resource"
import type { AmplifyListResult, AmplifyGetResult } from "@/types/shared"

export async function listFromModel<T>(
  model: any,
  filter?: any,
  nextToken?: string,
  limit?: number
): Promise<AmplifyListResult<T>> {
  const query = `
    query List${model.name}($filter: Model${model.name}FilterInput, $nextToken: String, $limit: Int) {
      list${model.name}s(filter: $filter, nextToken: $nextToken, limit: $limit) {
        items {
          id
          type
          parameters
          metrics
          inferences
          cost
          accuracy
          accuracyType
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
          scoreId
          confusionMatrix
          scoreGoal
          datasetClassDistribution
          isDatasetClassDistributionBalanced
          predictedClassDistribution
          isPredictedClassDistributionBalanced
        }
        nextToken
      }
    }
  `
  const response = await model.list(filter ? { filter } : undefined)
  return response as AmplifyListResult<T>
}

export function observeQueryFromModel<T>(
  model: any,
  filter?: Record<string, any>
) {
  return (model.observeQuery({
    filter: filter ? filter : undefined,
    selectionSet: [
      'id',
      'type',
      'parameters',
      'metrics',
      'inferences',
      'cost',
      'accuracy',
      'accuracyType',
      'createdAt',
      'updatedAt',
      'status',
      'startedAt',
      'totalItems',
      'processedItems',
      'errorMessage',
      'errorDetails',
      'accountId',
      'scorecardId',
      'scoreId',
      'confusionMatrix',
      'elapsedSeconds',
      'estimatedRemainingSeconds',
      'scoreGoal',
      'datasetClassDistribution',
      'isDatasetClassDistributionBalanced',
      'predictedClassDistribution',
      'isPredictedClassDistributionBalanced'
    ]
  }) as any) as { subscribe: (handlers: { 
    next: (data: { items: T[] }) => void
    error: (error: Error) => void 
  }) => { unsubscribe: () => void } }
}

export async function getFromModel<T>(
  model: any,
  id: string
): Promise<AmplifyGetResult<T>> {
  const response = await model.get({ id })
  return response as AmplifyGetResult<T>
} 