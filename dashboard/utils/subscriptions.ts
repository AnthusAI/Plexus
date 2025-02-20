/**
 * Subscriptions Module
 * ===================
 * 
 * This module consolidates all subscription-related functionality:
 * - Task subscriptions (observeRecentTasks)
 * - Evaluation subscriptions (observeRecentEvaluations)
 * - Score result subscriptions (observeScoreResults)
 * - Batch job scoring subscriptions
 */

import { Observable } from 'rxjs';
import type { Schema } from '../amplify/data/resource';
import { getClient } from './amplify-client';
import { TASK_UPDATE_SUBSCRIPTION } from '../graphql/evaluation-queries';
import type { SubscriptionHandler, GraphQLResponse } from './types';
import { convertToAmplifyTask, processTask } from './transformers';
import type { ProcessedTask } from './data-operations';
import type { GraphQLResult } from '@aws-amplify/api';

export type SubscriptionCallback<T> = (data: T) => void;
export type ErrorCallback = (error: unknown) => void;

export interface BatchJobScoringJobSubscriptionData {
  batchJobId: string;
  scoringJobId: string;
}

export interface ScoringJobSubscriptionData {
  id: string;
  status: string;
  startedAt?: string | null;
  completedAt?: string | null;
  errorMessage?: string | null;
  itemId: string;
  accountId: string;
  scorecardId: string;
  evaluationId?: string | null;
  scoreId?: string | null;
}

type AmplifySubscription = {
  subscribe: (handlers: {
    next: (data: any) => void;
    error: (error: any) => void;
  }) => { unsubscribe: () => void };
};

export function createBatchJobScoringJobSubscription(
  onData: SubscriptionCallback<BatchJobScoringJobSubscriptionData>,
  onError: ErrorCallback
) {
  const client = getClient();
  const subscription = (client.models.BatchJobScoringJob as any).onCreate() as AmplifySubscription;
  return subscription.subscribe({
    next: onData,
    error: onError
  });
}

export function createScoringJobSubscription(
  onData: SubscriptionCallback<ScoringJobSubscriptionData>,
  onError: ErrorCallback
) {
  const client = getClient();
  const subscription = (client.models.ScoringJob as any).onUpdate() as AmplifySubscription;
  return subscription.subscribe({
    next: onData,
    error: onError
  });
}

export function observeRecentTasks(limit: number = 10) {
  const client = getClient();
  
  return {
    subscribe(handler: SubscriptionHandler<any>) {
      const subscription = client.graphql({
        query: TASK_UPDATE_SUBSCRIPTION
      }) as unknown as { subscribe: Function };

      return subscription.subscribe({
        next: async ({ data }: { data?: { onUpdateTask: Schema['Task']['type'] } }) => {
          if (data?.onUpdateTask) {
            try {
              const updatedTask = data.onUpdateTask;
              const convertedTask = convertToAmplifyTask(updatedTask);
              const processedTask = await processTask(convertedTask);
              handler.next({ data: processedTask });
            } catch (error) {
              console.error('Error processing task update:', error);
              handler.error(error as Error);
            }
          }
        },
        error: (error: Error) => {
          handler.error(error);
          console.error('Error in task subscription:', error);
        }
      });
    }
  };
}

interface AmplifyListResult<T> {
  data: T[];
  nextToken: string | null;
}

export function observeRecentEvaluations(limit: number = 100): Observable<{ items: Schema['Evaluation']['type'][], isSynced: boolean }> {
  return new Observable(subscriber => {
    let evaluations: Schema['Evaluation']['type'][] = [];
    let subscriptionCleanup: { unsubscribe: () => void } | null = null;

    // Load initial data
    async function loadInitialEvaluations() {
      try {
        const currentClient = getClient();

        // Get the account ID by key
        const ACCOUNT_KEY = 'call-criteria';
        const accountResponse = await (currentClient.models.Account as any).list({ 
          filter: { key: { eq: ACCOUNT_KEY } } 
        }) as AmplifyListResult<Schema['Account']['type']>;

        if (!accountResponse.data?.length) {
          console.error('No account found with key:', ACCOUNT_KEY);
          return [];
        }

        const accountId = accountResponse.data[0].id;
        console.debug('Fetching evaluations for account:', accountId);

        const response = await currentClient.graphql({
          query: `
            query ListEvaluationByAccountIdAndUpdatedAt(
              $accountId: String!
              $sortDirection: ModelSortDirection!
              $limit: Int
            ) {
              listEvaluationByAccountIdAndUpdatedAt(
                accountId: $accountId
                sortDirection: $sortDirection
                limit: $limit
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
                  scorecard {
                    id
                    name
                  }
                  scoreId
                  score {
                    id
                    name
                  }
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
                  scoreResults {
                    items {
                      id
                      value
                      confidence
                      metadata
                      explanation
                      itemId
                      createdAt
                      scoringJob {
                        id
                        status
                        metadata
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
            limit: limit || 100
          }
        }) as GraphQLResult<{
          listEvaluationByAccountIdAndUpdatedAt: {
            items: Schema['Evaluation']['type'][];
            nextToken?: string | null;
          };
        }>;

        if (!response.data) {
          console.error('No data returned from GraphQL query');
          return [];
        }

        const result = response.data;
        if (!result?.listEvaluationByAccountIdAndUpdatedAt?.items) {
          console.error('No items found in GraphQL response');
          return [];
        }

        evaluations = result.listEvaluationByAccountIdAndUpdatedAt.items;
        subscriber.next({ items: evaluations, isSynced: true });
      } catch (error) {
        console.error('Error loading initial evaluations:', error);
        subscriber.error(error);
      }
    }

    // Set up subscription
    try {
      console.debug('Setting up evaluation subscription...');
      const client = getClient();
      subscriptionCleanup = (client.graphql({
        query: `
          subscription OnUpdateEvaluation {
            onUpdateEvaluation {
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
              scoreResults {
                items {
                  id
                  value
                  confidence
                  metadata
                  explanation
                  itemId
                  createdAt
                  scoringJob {
                    id
                    status
                    metadata
                  }
                }
              }
            }
          }
        `
      }) as unknown as { subscribe: Function }).subscribe({
        next: ({ data }: { data?: { onUpdateEvaluation: any } }) => {
          if (data?.onUpdateEvaluation) {
            const updatedEvaluation = data.onUpdateEvaluation;
            evaluations = evaluations.map(evaluation => 
              evaluation.id === updatedEvaluation.id ? updatedEvaluation : evaluation
            );
            subscriber.next({ items: evaluations, isSynced: true });
          }
        },
        error: (error: Error) => {
          console.error('Error in evaluation subscription:', error);
          subscriber.error(error);
        }
      });
    } catch (error) {
      console.error('Error setting up evaluation subscription:', error);
      subscriber.error(error);
    }

    // Load initial data
    loadInitialEvaluations();

    // Cleanup function
    return () => {
      console.debug('Cleaning up evaluation subscription');
      if (subscriptionCleanup) {
        subscriptionCleanup.unsubscribe();
      }
    };
  });
}

export function observeScoreResults(evaluationId: string) {
  console.log('Setting up score results subscription for evaluation:', evaluationId);
  
  const client = getClient();
  const subscriptions: { unsubscribe: () => void }[] = [];

  return {
    subscribe: (handlers: {
      next: (data: { items: Schema['ScoreResult']['type'][], isSynced: boolean }) => void,
      error: (error: Error) => void
    }) => {
      // Function to fetch latest data using the GSI with pagination
      const fetchLatestData = async () => {
        try {
          console.log('Starting to fetch ScoreResults for evaluation:', evaluationId);
          
          let allData: Schema['ScoreResult']['type'][] = [];
          let nextToken: string | null = null;
          let pageCount = 0;
          
          do {
            pageCount++;
            console.log('Fetching ScoreResult page:', {
              pageNumber: pageCount,
              nextToken,
              evaluationId
            });

            const response = await (client.models.ScoreResult as any).listScoreResultByEvaluationId({
              evaluationId,
              limit: 10000,
              nextToken,
              fields: [
                'id',
                'value',
                'confidence',
                'metadata',
                'explanation',
                'correct',
                'itemId',
                'accountId',
                'scoringJobId',
                'evaluationId',
                'scorecardId',
                'createdAt'
              ]
            }) as AmplifyListResult<Schema['ScoreResult']['type']>;
            
            if (response?.data) {
              allData = [...allData, ...response.data];
            }
            
            nextToken = response.nextToken;
          } while (nextToken);

          // Sort all results in memory
          const sortedData = [...allData].sort((a, b) => 
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          );

          handlers.next({
            items: sortedData,
            isSynced: true
          });
        } catch (error: unknown) {
          const err = error as Error;
          console.error('Error fetching ScoreResults:', {
            error: err,
            evaluationId,
            errorMessage: err.message,
            errorStack: err.stack
          });
          handlers.error(err);
        }
      };

      // Get initial data
      fetchLatestData();

      // Subscribe to create events
      const createSub = ((client.models.ScoreResult as any).onCreate() as AmplifySubscription).subscribe({
        next: () => {
          console.log('ScoreResult onCreate triggered, fetching latest data');
          fetchLatestData();
        },
        error: (error: Error) => {
          console.error('ScoreResult onCreate error:', error);
          handlers.error(error);
        }
      });
      subscriptions.push(createSub);

      // Subscribe to update events
      const updateSub = ((client.models.ScoreResult as any).onUpdate() as AmplifySubscription).subscribe({
        next: () => {
          console.log('ScoreResult onUpdate triggered, fetching latest data');
          fetchLatestData();
        },
        error: (error: Error) => {
          console.error('ScoreResult onUpdate error:', error);
          handlers.error(error);
        }
      });
      subscriptions.push(updateSub);

      // Subscribe to delete events
      const deleteSub = ((client.models.ScoreResult as any).onDelete() as AmplifySubscription).subscribe({
        next: () => {
          console.log('ScoreResult onDelete triggered, fetching latest data');
          fetchLatestData();
        },
        error: (error: Error) => {
          console.error('ScoreResult onDelete error:', error);
          handlers.error(error);
        }
      });
      subscriptions.push(deleteSub);

      return {
        unsubscribe: () => {
          subscriptions.forEach(sub => sub.unsubscribe());
        }
      };
    }
  };
} 