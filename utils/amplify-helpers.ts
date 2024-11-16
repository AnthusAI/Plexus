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
          metricsExplanation
          inferences
          cost
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
  const isScoreResult = model.name === 'ScoreResult'
  const selectionSet = isScoreResult ? [
    'id',
    'value',
    'confidence',
    'metadata',
    'correct',
    'itemId',
    'accountId',
    'scoringJobId',
    'experimentId',
    'scorecardId'
  ] : [
    'id',
    'type',
    'parameters',
    'metrics',
    'metricsExplanation',
    'inferences',
    'cost',
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

  console.log('Setting up subscription for model:', model.name);
  console.log('Selection set:', selectionSet);
  console.log('Filter:', filter);

  const subscription = model.observeQuery({
    filter: filter ? filter : undefined,
    selectionSet
  });

  return {
    subscribe: (handlers: { 
      next: (data: { items: T[] }) => void
      error: (error: Error) => void 
    }) => {
      const wrappedHandlers = {
        next: (data: { items: T[] }) => {
          console.log('Raw subscription data received:', 
            data.items.map(item => ({
              id: (item as any).id,
              metricsExplanation: (item as any).metricsExplanation,
              metrics: (item as any).metrics
            }))
          );
          handlers.next(data);
        },
        error: handlers.error
      };
      
      return subscription.subscribe(wrappedHandlers);
    }
  } as any;
}

export async function getFromModel<T>(
  model: any,
  id: string
): Promise<AmplifyGetResult<T>> {
  const response = await model.get({ id })
  return response as AmplifyGetResult<T>
}

export function observeScoreResults(client: any, experimentId: string) {
  return client.models.ScoreResult.observeQuery({
    filter: { experimentId: { eq: experimentId } },
    limit: 1000,
    sort: {
      field: 'createdAt',
      direction: 'desc'
    },
    selectionSet: [
      'id',
      'value',
      'confidence',
      'metadata',
      'correct',
      'itemId',
      'accountId',
      'scoringJobId',
      'experimentId',
      'scorecardId',
      'createdAt'
    ]
  })
} 