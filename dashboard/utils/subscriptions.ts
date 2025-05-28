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
import type { GraphQLResult, GraphQLSubscription } from '@aws-amplify/api';

// Add type definitions for GraphQL subscription responses
type GraphQLSubscriptionResult<T> = {
  subscribe: (handlers: {
    next: (data: { data?: T }) => void;
    error: (error: any) => void;
  }) => { unsubscribe: () => void };
};

type CreateEvaluationResponse = {
  onCreateEvaluation: Schema['Evaluation']['type'];
};

type UpdateEvaluationResponse = {
  onUpdateEvaluation: Schema['Evaluation']['type'];
};

type DeleteEvaluationResponse = {
  onDeleteEvaluation: Schema['Evaluation']['type'];
};

type GraphQLSubscriptionResponse = { subscribe: Function };

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
    let subscriptions: { unsubscribe: () => void }[] = [];
    let isSubscribed = true;

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
          throw new Error(`No account found with key: ${ACCOUNT_KEY}`);
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
                  universalCode
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
                      trace
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
          }
        }>;

        if (!response.data?.listEvaluationByAccountIdAndUpdatedAt?.items) {
          throw new Error('No evaluations data returned from query');
        }

        evaluations = response.data.listEvaluationByAccountIdAndUpdatedAt.items;
        if (isSubscribed) {
          subscriber.next({ items: evaluations, isSynced: true });
          // Set up subscriptions after initial data is loaded
          setupSubscriptions(accountId);
        }
      } catch (error) {
        console.error('Error loading initial evaluations:', error);
        if (isSubscribed) {
          subscriber.error(error);
        }
      }
    }

    function setupSubscriptions(accountId: string) {
      try {
        const client = getClient();

        // Helper function to handle evaluation changes
        const handleEvaluationChange = (evaluation: Schema['Evaluation']['type'], action: 'create' | 'update' | 'delete') => {
          if (!evaluation || !isSubscribed) return;

          console.debug(`Handling ${action} for evaluation:`, {
            evaluationId: evaluation.id,
            type: evaluation.type,
            status: evaluation.status
          });

          if (action === 'delete') {
            evaluations = evaluations.filter(e => e.id !== evaluation.id);
          } else {
            const existingEvaluation = evaluations.find(e => e.id === evaluation.id);
            
            console.debug('Existing evaluation state:', {
              evaluationId: evaluation.id,
              hasExistingEval: !!existingEvaluation,
              existingTaskData: existingEvaluation?.task,
              existingTaskId: existingEvaluation?.taskId,
              action
            });

            const finalEvaluation = {
              ...evaluation,
              task: evaluation.task || existingEvaluation?.task
            } as Schema['Evaluation']['type'];

            if (action === 'create') {
              evaluations = [finalEvaluation, ...evaluations];
            } else {
              evaluations = evaluations.map(e => 
                e.id === finalEvaluation.id ? finalEvaluation : e
              );
            }
          }
          
          if (isSubscribed) {
            subscriber.next({ items: evaluations, isSynced: true });
          }
        };

        // Set up create subscription
        const createSub = (client.graphql({
          query: `subscription OnCreateEvaluation {
            onCreateEvaluation {
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
                  trace
                  itemId
                  createdAt
                }
              }
            }
          }`
        }) as unknown as GraphQLSubscriptionResult<CreateEvaluationResponse>).subscribe({
          next: (response: { data?: CreateEvaluationResponse }) => {
            console.debug('Create subscription event received:', response.data);
            if (response.data?.onCreateEvaluation) {
              handleEvaluationChange(response.data.onCreateEvaluation, 'create');
            }
          },
          error: (error: Error) => {
            console.error('Create subscription error:', error);
            if (isSubscribed) {
              subscriber.error(error);
            }
          }
        });
        subscriptions.push(createSub);

        // Set up update subscription
        const updateSub = (client.graphql({
          query: `subscription OnUpdateEvaluation {
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
                  trace
                  itemId
                  createdAt
                }
              }
            }
          }`
        }) as unknown as GraphQLSubscriptionResult<UpdateEvaluationResponse>).subscribe({
          next: (response: { data?: UpdateEvaluationResponse }) => {
            console.debug('Update subscription event received:', response.data);
            if (response.data?.onUpdateEvaluation) {
              handleEvaluationChange(response.data.onUpdateEvaluation, 'update');
            }
          },
          error: (error: Error) => {
            console.error('Update subscription error:', error);
            if (isSubscribed) {
              subscriber.error(error);
            }
          }
        });
        subscriptions.push(updateSub);

        // Set up delete subscription
        const deleteSub = (client.graphql({
          query: `subscription OnDeleteEvaluation {
            onDeleteEvaluation {
              id
            }
          }`
        }) as unknown as GraphQLSubscriptionResult<DeleteEvaluationResponse>).subscribe({
          next: (response: { data?: DeleteEvaluationResponse }) => {
            console.debug('Delete subscription event received:', response.data);
            if (response.data?.onDeleteEvaluation) {
              handleEvaluationChange(response.data.onDeleteEvaluation, 'delete');
            }
          },
          error: (error: Error) => {
            console.error('Delete subscription error:', error);
            if (isSubscribed) {
              subscriber.error(error);
            }
          }
        });
        subscriptions.push(deleteSub);

      } catch (error) {
        console.error('Error setting up evaluation subscriptions:', error);
        if (isSubscribed) {
          subscriber.error(error);
        }
      }
    }

    // Start loading initial data
    loadInitialEvaluations();

    // Return cleanup function
    return () => {
      isSubscribed = false;
      console.debug('Cleaning up evaluation subscriptions');
      subscriptions.forEach(sub => {
        try {
          if (sub && typeof sub.unsubscribe === 'function') {
            sub.unsubscribe();
          }
        } catch (error) {
          console.error('Error cleaning up subscription:', error);
        }
      });
      subscriptions = [];
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
                'trace',
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
          const sortedData = [...allData].sort((a, b) => {
            const bDate = b.createdAt ? new Date(b.createdAt).getTime() : 0;
            const aDate = a.createdAt ? new Date(a.createdAt).getTime() : 0;
            return bDate - aDate;
          });

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

// Task subscription queries
const onCreateTaskSubscriptionQuery = /* GraphQL */ `
  subscription OnCreateTask {
    onCreateTask {
      id
      type
      command
      status
      target
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
      celeryTaskId
      workerNodeId
      updatedAt
    }
  }
`;

const onUpdateTaskSubscriptionQuery = /* GraphQL */ `
  subscription OnUpdateTask {
    onUpdateTask {
      id
      type
      command
      status
      target
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
      celeryTaskId
      workerNodeId
      updatedAt
    }
  }
`;

// TaskStage subscription queries
const onCreateTaskStageSubscriptionQuery = /* GraphQL */ `
  subscription OnCreateTaskStage {
    onCreateTaskStage {
      id
      taskId
      name
      order
      status
      processedItems
      totalItems
      startedAt
      completedAt
      estimatedCompletionAt
      statusMessage
    }
  }
`;

const onUpdateTaskStageSubscriptionQuery = /* GraphQL */ `
  subscription OnUpdateTaskStage {
    onUpdateTaskStage {
      id
      taskId
      name
      order
      status
      processedItems
      totalItems
      startedAt
      completedAt
      estimatedCompletionAt
      statusMessage
    }
  }
`;

export function observeTaskUpdates() {
  return new Observable(observer => {
    const client = getClient();
    const subscriptions: { unsubscribe: () => void }[] = [];

    // Subscribe to create events
    const createSub = (client.graphql({ query: onCreateTaskSubscriptionQuery }) as any)
      .subscribe({
        next: ({ data }: { data: any }) => {
          console.log('Task create subscription event:', {
            taskId: data?.onCreateTask?.id,
            type: data?.onCreateTask?.type,
            status: data?.onCreateTask?.status,
            data: data?.onCreateTask
          });
          observer.next({ type: 'create', data: data?.onCreateTask });
        },
        error: (error: any) => {
          console.error('Task create subscription error:', error);
          observer.error(error);
        }
      });
    subscriptions.push(createSub);

    // Subscribe to update events
    const updateSub = (client.graphql({ query: onUpdateTaskSubscriptionQuery }) as any)
      .subscribe({
        next: ({ data }: { data: any }) => {
          console.log('Task update subscription event:', {
            taskId: data?.onUpdateTask?.id,
            type: data?.onUpdateTask?.type,
            status: data?.onUpdateTask?.status,
            data: data?.onUpdateTask
          });
          observer.next({ type: 'update', data: data?.onUpdateTask });
        },
        error: (error: any) => {
          console.error('Task update subscription error:', error);
          observer.error(error);
        }
      });
    subscriptions.push(updateSub);

    return () => {
      subscriptions.forEach(sub => sub.unsubscribe());
    };
  });
}

export function observeTaskStageUpdates() {
  return new Observable(observer => {
    const client = getClient();
    const subscriptions: { unsubscribe: () => void }[] = [];

    // Subscribe to create events
    const createSub = (client.graphql({ query: onCreateTaskStageSubscriptionQuery }) as any)
      .subscribe({
        next: (response: { data?: { onCreateTaskStage?: any }, errors?: any[] }) => {
          // Log the full response first
          console.log('Raw TaskStage create subscription response:', response);
          
          const taskStageData = response?.data?.onCreateTaskStage;
          
          // Check for specific timestamp-related errors but still process the data
          if (response.errors) {
            const nonTimestampErrors = response.errors.filter(error => 
              !error.message.includes('AWSDateTime') && 
              !error.message.includes('createdAt') && 
              !error.message.includes('updatedAt')
            );
            
            // Only log timestamp errors at debug level
            response.errors.forEach(error => {
              if (error.message.includes('AWSDateTime')) {
                console.debug('Ignorable timestamp error:', error);
              }
            });

            // If we have other errors, log them as warnings
            if (nonTimestampErrors.length > 0) {
              console.warn('TaskStage create subscription errors:', nonTimestampErrors);
            }
          }

          // Process the data even if we have timestamp errors
          if (taskStageData?.id && taskStageData?.taskId) {
            console.log('TaskStage create subscription event:', {
              stageId: taskStageData.id,
              taskId: taskStageData.taskId,
              name: taskStageData.name,
              status: taskStageData.status
            });
            observer.next({ type: 'create', data: taskStageData });
          } else if (!response.errors || response.errors.every(e => e.message.includes('AWSDateTime'))) {
            // Only warn if we're missing data and it's not just timestamp errors
            console.warn('Received TaskStage create event but data was invalid:', response);
          }
        },
        error: (error: any) => {
          console.error('TaskStage create subscription error:', error);
          observer.error(error);
        }
      });
    subscriptions.push(createSub);

    // Subscribe to update events
    const updateSub = (client.graphql({ query: onUpdateTaskStageSubscriptionQuery }) as any)
      .subscribe({
        next: (response: { data?: { onUpdateTaskStage?: any }, errors?: any[] }) => {
          // Log the full response first
          console.log('Raw TaskStage update subscription response:', response);
          
          const taskStageData = response?.data?.onUpdateTaskStage;

          // Check for specific timestamp-related errors but still process the data
          if (response.errors) {
            const nonTimestampErrors = response.errors.filter(error => 
              !error.message.includes('AWSDateTime') && 
              !error.message.includes('createdAt') && 
              !error.message.includes('updatedAt')
            );
            
            // Only log timestamp errors at debug level
            response.errors.forEach(error => {
              if (error.message.includes('AWSDateTime')) {
                console.debug('Ignorable timestamp error:', error);
              }
            });

            // If we have other errors, log them as warnings
            if (nonTimestampErrors.length > 0) {
              console.warn('TaskStage update subscription errors:', nonTimestampErrors);
            }
          }

          // Process the data even if we have timestamp errors
          if (taskStageData?.id && taskStageData?.taskId) {
            console.log('TaskStage update subscription event:', {
              stageId: taskStageData.id,
              taskId: taskStageData.taskId,
              name: taskStageData.name,
              status: taskStageData.status
            });
            observer.next({ type: 'update', data: taskStageData });
          } else if (!response.errors || response.errors.every(e => e.message.includes('AWSDateTime'))) {
            // Only warn if we're missing data and it's not just timestamp errors
            console.warn('Received TaskStage update event but data was invalid:', response);
          }
        },
        error: (error: any) => {
          console.error('TaskStage update subscription error:', error);
          observer.error(error);
        }
      });
    subscriptions.push(updateSub);

    return () => {
      subscriptions.forEach(sub => sub.unsubscribe());
    };
  });
}

export function observeItemCreations() {
  const client = getClient();
  
  return {
    subscribe(handler: SubscriptionHandler<any>) {
      const subscription = client.graphql({
        query: `
          subscription OnCreateItem {
            onCreateItem {
              id
              externalId
              description
              accountId
              evaluationId
              updatedAt
              createdAt
              isEvaluation
            }
          }
        `
      }) as unknown as { subscribe: Function };

      return subscription.subscribe({
        next: async ({ data }: { data?: { onCreateItem: Schema['Item']['type'] } }) => {
          if (!data?.onCreateItem) {
            return; // Skip processing for null data
          }
          
          try {
            handler.next({ data: data.onCreateItem });
          } catch (error) {
            console.error('Error processing item creation:', error);
            handler.error(error as Error);
          }
        },
        error: (error: Error) => {
          console.error('Item creation subscription error:', error);
          handler.error(error);
        }
      });
    }
  };
}

export function observeItemUpdates() {
  const client = getClient();
  
  return {
    subscribe(handler: SubscriptionHandler<any>) {
      const subscription = client.graphql({
        query: `
          subscription OnUpdateItem {
            onUpdateItem {
              id
              externalId
              description
              accountId
              evaluationId
              updatedAt
              createdAt
              isEvaluation
            }
          }
        `
      }) as unknown as { subscribe: Function };

      return subscription.subscribe({
        next: async ({ data }: { data?: { onUpdateItem: Schema['Item']['type'] } }) => {
          if (!data?.onUpdateItem) {
            // Amplify Gen2 often sends empty notifications, so we treat this as a signal to refetch
            handler.next({ data: null, needsRefetch: true });
            return;
          }
          
          try {
            handler.next({ data: data.onUpdateItem });
          } catch (error) {
            console.error('Error processing item update:', error);
            handler.error(error as Error);
          }
        },
        error: (error: Error) => {
          console.error('Item update subscription error:', error);
          handler.error(error);
        }
      });
    }
  };
}

export function observeScoreResultChanges() {
  const client = getClient();
  const subscriptions: { unsubscribe: () => void }[] = [];
  
  return {
    subscribe(handler: SubscriptionHandler<{ itemId: string, accountId: string, action: 'create' | 'update' | 'delete' }>) {
      // Subscribe to create events
      const createSub = ((client.models.ScoreResult as any).onCreate() as AmplifySubscription).subscribe({
        next: (response: any) => {
          console.log('📊 ScoreResult onCreate triggered:', response);
          // The actual data structure is nested inside the response
          const scoreResult = response?.data?.onCreateScoreResult || response;
          if (scoreResult?.itemId && scoreResult?.accountId) {
            console.log('📊 Score result created for item:', scoreResult.itemId);
            handler.next({ data: { itemId: scoreResult.itemId, accountId: scoreResult.accountId, action: 'create' } });
          } else {
            console.log('📊 ScoreResult onCreate: missing itemId or accountId in data:', scoreResult);
          }
        },
        error: (error: Error) => {
          console.error('📊 ScoreResult onCreate error:', error);
          handler.error(error);
        }
      });
      subscriptions.push(createSub);

      // Subscribe to update events
      const updateSub = ((client.models.ScoreResult as any).onUpdate() as AmplifySubscription).subscribe({
        next: (response: any) => {
          console.log('📊 ScoreResult onUpdate triggered:', response);
          // The actual data structure is nested inside the response
          const scoreResult = response?.data?.onUpdateScoreResult || response;
          if (scoreResult?.itemId && scoreResult?.accountId) {
            console.log('📊 Score result updated for item:', scoreResult.itemId);
            handler.next({ data: { itemId: scoreResult.itemId, accountId: scoreResult.accountId, action: 'update' } });
          } else {
            console.log('📊 ScoreResult onUpdate: missing itemId or accountId in data:', scoreResult);
          }
        },
        error: (error: Error) => {
          console.error('📊 ScoreResult onUpdate error:', error);
          handler.error(error);
        }
      });
      subscriptions.push(updateSub);

      // Subscribe to delete events
      const deleteSub = ((client.models.ScoreResult as any).onDelete() as AmplifySubscription).subscribe({
        next: (response: any) => {
          console.log('📊 ScoreResult onDelete triggered:', response);
          // The actual data structure is nested inside the response
          const scoreResult = response?.data?.onDeleteScoreResult || response;
          if (scoreResult?.itemId && scoreResult?.accountId) {
            console.log('📊 Score result deleted for item:', scoreResult.itemId);
            handler.next({ data: { itemId: scoreResult.itemId, accountId: scoreResult.accountId, action: 'delete' } });
          } else {
            console.log('📊 ScoreResult onDelete: missing itemId or accountId in data:', scoreResult);
          }
        },
        error: (error: Error) => {
          console.error('📊 ScoreResult onDelete error:', error);
          handler.error(error);
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