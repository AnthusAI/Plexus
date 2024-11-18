import type { Schema } from "@/amplify/data/resource"
import type { AmplifyListResult, AmplifyGetResult } from "@/types/shared"

export async function listFromModel<T extends { id: string }>(
  model: any,
  filter?: any,
  nextToken?: string,
  limit?: number
): Promise<AmplifyListResult<T>> {
  console.log('Listing from model:', {
    modelName: model?.name,
    filter,
    nextToken,
    limit
  })

  const options: any = {}
  if (filter) options.filter = filter
  if (nextToken) options.nextToken = nextToken
  if (limit) options.limit = limit

  try {
    // Collect all results across pages
    let allData: T[] = []
    let currentNextToken = nextToken

    do {
      if (currentNextToken) options.nextToken = currentNextToken
      
      const response = await model.list(options)
      console.log('List page response:', {
        count: response.data?.length,
        nextToken: response.nextToken,
        sampleItem: response.data?.[0] ? {
          id: response.data[0].id,
          allFields: Object.keys(response.data[0])
        } : null
      })

      if (response.data?.length) {
        allData = [...allData, ...response.data]
      }

      currentNextToken = response.nextToken
    } while (currentNextToken)

    console.log('All pages fetched:', {
      totalCount: allData.length,
      firstId: allData[0]?.id,
      lastId: allData[allData.length - 1]?.id
    })

    return {
      data: allData,
      nextToken: null  // No more pages
    } as AmplifyListResult<T>

  } catch (error) {
    console.error('Error listing from model:', error)
    throw error
  }
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
  console.log('Setting up score results subscription for experiment:', experimentId)
  
  return client.models.ScoreResult.observeQuery({
    filter: { experimentId: { eq: experimentId } },
    selectionSet: [
      'id',
      'value',
      'confidence',
      'metadata',
      'correct',
      'createdAt',
      'itemId',
      'experimentId',
      'scorecardId'
    ]
  })
} 