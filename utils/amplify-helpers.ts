import type { Schema } from "@/amplify/data/resource"
import type { AmplifyListResult, AmplifyGetResult } from "@/types/shared"

export async function listFromModel<T>(
  model: any,
  filter?: any,
  nextToken?: string,
  limit?: number
): Promise<AmplifyListResult<T>> {
  const response = await model.list(filter ? { filter } : undefined)
  return response as AmplifyListResult<T>
}

export function observeQueryFromModel<T>(
  model: any,
  filter?: Record<string, any>
) {
  console.log('Setting up subscription for model:', model?.name);
  console.log('Filter:', filter);

  const subscription = model.observeQuery({
    filter: filter || undefined,
    // Include all fields we want to observe
    fields: [
      'id',
      'type',
      'accuracy',
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
  });

  return {
    subscribe: (handlers: { 
      next: (data: { items: T[] }) => void
      error: (error: Error) => void 
    }) => {
      const wrappedHandlers = {
        next: (data: any) => {
          if (!data?.items) {
            console.error('Missing items in subscription data:', data);
            return;
          }

          // Log the full raw data for each item
          console.log('Raw subscription items:', data.items.map((item: any) => ({
            id: item.id,
            type: item.type,
            processedItems: item.processedItems,
            totalItems: item.totalItems,
            accuracy: item.accuracy,
            allFields: Object.keys(item)
          })));

          handlers.next(data);
        },
        error: (error: Error) => {
          console.error('Subscription error:', error);
          handlers.error(error);
        }
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
    fields: [
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