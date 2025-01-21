import type { Schema } from "@/amplify/data/resource"
import type { AmplifyListResult, AmplifyGetResult } from "@/types/shared"
import { tap } from "node:test/reporters"
import { Observable } from "rxjs"

interface ScoringJobsSubscriptionData {
  items: Schema['ScoringJob']['type'][]
  isSynced: boolean
}

interface BatchJobScoringJobLink {
  id: string
  scoringJob: Schema['ScoringJob']['type']
  batchJobId: string
  scoringJobId: string
}

export async function listFromModel<T extends { id: string }>(
  model: any,
  filter?: any,
  nextToken?: string,
  limit?: number
): Promise<AmplifyListResult<T>> {
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

      if (response.data?.length) {
        allData = [...allData, ...response.data]
      }

      currentNextToken = response.nextToken
    } while (currentNextToken)

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
  filter?: Record<string, any>,
  modelName?: string
) {
  // Use provided modelName first, then try to detect it
  const detectedModelName = modelName || 
                          model?.constructor?.name?.replace('Model', '') || 
                          Object.keys(model || {}).find(key => key.endsWith('Model'))?.replace('Model', '') ||
                          'Unknown';
  
  console.log('Setting up subscription for model:', {
    providedModelName: modelName,
    detectedModelName,
    modelConstructor: model?.constructor?.name,
    modelKeys: Object.keys(model || {})
  });
  console.log('Filter:', filter);

  // Define fields based on model name
  let fields: any[];
  switch (detectedModelName) {
    case 'BatchJob':
      fields = [
        'id',
        'type',
        'status',
        'startedAt',
        'estimatedEndAt',
        'completedAt',
        'totalRequests',
        'completedRequests',
        'failedRequests',
        'errorMessage',
        'errorDetails',
        'accountId',
        'scorecardId',
        'scoreId',
        'modelProvider',
        'modelName',
        'scoringJobCountCache',
        'createdAt',
        'updatedAt'
      ];
      break;
    case 'Evaluation':
      fields = [
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
        {
          name: 'score',
          fields: [
            'id',
            'name',
            'type',
            'description',
            'createdAt',
            'updatedAt'
          ]
        },
        'confusionMatrix',
        'elapsedSeconds',
        'estimatedRemainingSeconds',
        'scoreGoal',
        'datasetClassDistribution',
        'isDatasetClassDistributionBalanced',
        'predictedClassDistribution',
        'isPredictedClassDistributionBalanced'
      ];
      break;
    default:
      console.warn('Unknown model type:', detectedModelName);
      fields = ['id', 'createdAt', 'updatedAt'];
      break;
  }

  console.log('Using fields for subscription:', fields);

  const subscription = model.observeQuery({
    filter: filter || undefined,
    fields
  });

  return subscription;
}

export async function getFromModel<T>(
  model: any,
  id: string
): Promise<AmplifyGetResult<T>> {
  const response = await model.get({ id })
  return response as AmplifyGetResult<T>
}

export function observeScoreResults(client: any, evaluationId: string) {
  console.log('Setting up score results subscription for evaluation:', evaluationId)
  
  const subscriptions: { unsubscribe: () => void }[] = []

  return {
    subscribe: (handlers: {
      next: (data: any) => void,
      error: (error: Error) => void
    }) => {
      // Function to fetch latest data using the GSI with pagination
      const fetchLatestData = async () => {
        try {
          console.log('Starting to fetch ScoreResults for evaluation:', evaluationId)
          
          let allData: Schema['ScoreResult']['type'][] = []
          let nextToken: string | null = null
          let pageCount = 0
          
          do {
            pageCount++
            console.log('Fetching ScoreResult page:', {
              pageNumber: pageCount,
              nextToken,
              evaluationId
            })

            const response: {
              data: Schema['ScoreResult']['type'][]
              nextToken: string | null
            } = await client.models.ScoreResult.listScoreResultByEvaluationId({
              evaluationId,
              limit: 10000,
              nextToken,
              fields: [
                'id',
                'value',
                'confidence',
                'metadata',
                'correct',
                'itemId',
                'accountId',
                'scoringJobId',
                'evaluationId',
                'scorecardId',
                'createdAt'
              ]
            })
            
            const pageSize = response?.data?.length || 0
            console.log('Received page response:', {
              pageNumber: pageCount,
              pageSize,
              hasNextToken: !!response.nextToken,
              nextToken: response.nextToken,
              firstId: response.data?.[0]?.id,
              lastId: response.data?.[pageSize - 1]?.id
            })
            
            if (response?.data) {
              allData = [...allData, ...response.data]
            }
            
            nextToken = response.nextToken
            
            console.log('Pagination status:', {
              pageNumber: pageCount,
              newRecordsInPage: pageSize,
              totalRecordsSoFar: allData.length,
              hasMorePages: !!nextToken
            })
          } while (nextToken)

          // Sort all results in memory
          const sortedData = [...allData].sort((a, b) => 
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          )

          console.log('Completed fetching all ScoreResults:', {
            totalPages: pageCount,
            totalRecords: sortedData.length,
            evaluationId,
            firstRecordId: sortedData[0]?.id,
            lastRecordId: sortedData[sortedData.length - 1]?.id
          })

          handlers.next({
            items: sortedData,
            isSynced: true
          })
        } catch (error: unknown) {
          const err = error as Error
          console.error('Error fetching ScoreResults:', {
            error: err,
            evaluationId,
            errorMessage: err.message,
            errorStack: err.stack
          })
        }
      }

      // Get initial data
      fetchLatestData()

      // Subscribe to create events
      const createSub = client.models.ScoreResult.onCreate().subscribe({
        next: () => {
          console.log('ScoreResult onCreate triggered, fetching latest data')
          fetchLatestData()
        },
        error: (error: Error) => {
          console.error('ScoreResult onCreate error:', error)
          handlers.error(error)
        }
      })
      subscriptions.push(createSub)

      // Subscribe to update events
      const updateSub = client.models.ScoreResult.onUpdate().subscribe({
        next: () => {
          console.log('ScoreResult onUpdate triggered, fetching latest data')
          fetchLatestData()
        },
        error: (error: Error) => {
          console.error('ScoreResult onUpdate error:', error)
          handlers.error(error)
        }
      })
      subscriptions.push(updateSub)

      // Subscribe to delete events
      const deleteSub = client.models.ScoreResult.onDelete().subscribe({
        next: () => {
          console.log('ScoreResult onDelete triggered, fetching latest data')
          fetchLatestData()
        },
        error: (error: Error) => {
          console.error('ScoreResult onDelete error:', error)
          handlers.error(error)
        }
      })
      subscriptions.push(deleteSub)

      return {
        unsubscribe: () => {
          subscriptions.forEach(sub => sub.unsubscribe())
        }
      }
    }
  }
} 
