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
  const isEvaluation = model?.constructor?.name === 'EvaluationModel';
  
  try {
    let response;
    
    if (isEvaluation) {
      const accountId = filter?.accountId?.eq;
      
      if (!accountId) {
        console.error('Missing accountId in filter:', filter);
        return { data: [], nextToken: null };
      }

      // Add validation for accountId
      if (typeof accountId !== 'string' || accountId.trim() === '') {
        console.error('Invalid accountId:', {
          accountId,
          type: typeof accountId,
          filter
        });
        return { data: [], nextToken: null };
      }

      console.log('Attempting to query evaluations for account:', {
        accountId,
        accountIdType: typeof accountId,
        accountIdLength: accountId.length,
        filter
      });

      // Try to use the GSI through GraphQL
      try {
        const variables = {
          accountId: accountId.trim(),
          sortDirection: 'DESC' as const,
          limit: limit || 100,
          nextToken
        };

        console.log('Executing GraphQL query with variables:', variables);

        const graphqlResponse = await model.graphql.query({
          query: `
            query ListEvaluationByAccountIdAndUpdatedAt(
              $accountId: String!
              $sortDirection: ModelSortDirection!
              $limit: Int
              $nextToken: String
            ) {
              listEvaluationByAccountIdAndUpdatedAt(
                accountId: $accountId
                sortDirection: $sortDirection
                limit: $limit
                nextToken: $nextToken
              ) {
                items {
                  id
                  type
                  parameters
                  metrics
                  metricsExplanation
                  inferences
                  accuracy
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
                  taskId
                  task {
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
                    currentStageId
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
                  }
                }
                nextToken
              }
            }
          `,
          variables,
          authMode: 'apiKey'
        });

        console.log('Raw GraphQL response:', {
          data: graphqlResponse?.data,
          errors: graphqlResponse?.errors
        });

        if (graphqlResponse?.errors) {
          throw new Error(JSON.stringify(graphqlResponse.errors));
        }

        // Transform the response to match the expected format
        response = {
          data: graphqlResponse?.data?.listEvaluationByAccountIdAndUpdatedAt?.items || [],
          nextToken: graphqlResponse?.data?.listEvaluationByAccountIdAndUpdatedAt?.nextToken
        };

        console.log('GraphQL query results:', {
          dataLength: response?.data?.length,
          hasNextToken: !!response?.nextToken,
          firstItem: response?.data?.[0]?.updatedAt,
          lastItem: response?.data?.[response?.data?.length - 1]?.updatedAt,
          allDates: response?.data?.map((item: { updatedAt: string }) => item.updatedAt).sort((a: string, b: string) => 
            new Date(b).getTime() - new Date(a).getTime()
          )
        });
      } catch (gsiError) {
        console.error('GraphQL query failed:', gsiError);
        
        // Fall back to filtered list with sorting
        console.log('Falling back to regular list query');
        response = await model.list({
          filter: { accountId: { eq: accountId } },
          limit: 100,
          nextToken,
          sort: {
            field: 'updatedAt',
            direction: 'DESC'
          }
        });

        console.log('Fallback query results:', {
          dataLength: response?.data?.length,
          hasNextToken: !!response?.nextToken,
          firstItem: response?.data?.[0]?.updatedAt,
          lastItem: response?.data?.[response?.data?.length - 1]?.updatedAt,
          allDates: response?.data?.map((item: { updatedAt: string }) => item.updatedAt).sort((a: string, b: string) => 
            new Date(b).getTime() - new Date(a).getTime()
          )
        });
      }
    } else {
      const options: any = {}
      if (filter) options.filter = filter
      if (nextToken) options.nextToken = nextToken
      if (limit) options.limit = limit
      
      response = await model.list(options)
    }

    // Sort the results in memory if we have them
    if (response?.data && isEvaluation) {
      response.data.sort((a: any, b: any) => 
        new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
      );
    }

    return {
      data: response?.data || [],
      nextToken: response?.nextToken
    } as AmplifyListResult<T>

  } catch (error: any) {
    console.error('Error listing from model:', {
      error,
      errorMessage: error.message,
      errorStack: error.stack,
      isEvaluation,
      filter
    });
    throw error;
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
              nextToken
              // Removed selectionSet to avoid the 'selectionSet.reduce is not a function' error
              // The default selection should include all the fields we need
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
          const sortedData = [...allData].sort((a, b) => {
            const bDate = b.createdAt ? new Date(b.createdAt).getTime() : 0;
            const aDate = a.createdAt ? new Date(a.createdAt).getTime() : 0;
            return bDate - aDate;
          })

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
