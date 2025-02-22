import { useState, useEffect, useCallback, useRef } from 'react';
import { getClient } from '@/utils/amplify-client';
import { Observable } from 'rxjs';
import { 
  EVALUATION_UPDATE_SUBSCRIPTION, 
  TASK_UPDATE_SUBSCRIPTION, 
  TASK_STAGE_UPDATE_SUBSCRIPTION 
} from '../graphql/queries';
import type { Schema } from '@/amplify/data/resource';
import type { Evaluation, TaskStageType, AmplifyTask } from '@/utils/data-operations';
import { transformEvaluation, getValueFromLazyLoader, transformAmplifyTask, processTask } from '@/utils/data-operations';
import { observeRecentEvaluations } from '@/utils/data-operations';
import { observeScoreResults } from '@/utils/amplify-helpers';
import { isEqual } from 'lodash';

// Add type for score result
type ScoreResult = {
  id: string;
  value: string | number;
  confidence: number | null;
  metadata: any;
  itemId: string | null;
};

// Add type for subscription
type Subscription = {
  unsubscribe: () => void;
};

// Add type for subscription response
type ScoreResultsSubscriptionResponse = {
  items: Schema['ScoreResult']['type'][];
  isSynced: boolean;
};

// Add type for subscription handler
type ScoreResultsSubscriptionHandler = {
  next: (data: ScoreResultsSubscriptionResponse) => void;
  error: (error: Error) => void;
};

// Add type for subscription
type ScoreResultsSubscription = {
  subscribe: (handlers: ScoreResultsSubscriptionHandler) => { unsubscribe: () => void };
};

type UseEvaluationDataProps = {
  accountId: string | null;
  limit?: number;
};

type UseEvaluationDataReturn = {
  evaluations: Evaluation[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
};

export function useEvaluationData({ accountId, limit = 24 }: UseEvaluationDataProps): UseEvaluationDataReturn {
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [evaluationMap, setEvaluationMap] = useState<Map<string, Evaluation>>(new Map());
  const taskMapRef = useRef<Map<string, AmplifyTask>>(new Map());
  const activeSubscriptionRef = useRef<Subscription | null>(null);

  // Helper function to update maps
  const updateMaps = useCallback((newEvaluations: Evaluation[]) => {
    const newEvalMap = new Map<string, Evaluation>();
    const newTaskMap = new Map<string, AmplifyTask>();
    
    newEvaluations.forEach(evaluation => {
      newEvalMap.set(evaluation.id, evaluation);
      if (evaluation.task) {
        newTaskMap.set(evaluation.task.id, evaluation.task);
      }
    });
    
    setEvaluationMap(newEvalMap);
    taskMapRef.current = newTaskMap;
  }, []);

  // Merge task update into evaluations
  const mergeTaskUpdate = useCallback((taskData: AmplifyTask | { taskId: string; status: string }) => {
    // Get the task ID from either format
    const updateTaskId = 'id' in taskData ? taskData.id : taskData.taskId;
    
    console.log('Merging task update:', {
      taskId: updateTaskId,
      status: taskData.status,
      hasStages: 'stages' in taskData ? !!taskData.stages : false,
      rawTaskData: taskData
    });

    // Update taskMap - create a proper AmplifyTask structure
    const taskToStore: AmplifyTask = {
      id: updateTaskId,
      status: taskData.status,
      type: 'id' in taskData ? taskData.type : 'unknown',
      command: 'id' in taskData ? taskData.command : '',
      target: 'id' in taskData ? taskData.target : '',
      ...(('startedAt' in taskData) && { startedAt: taskData.startedAt }),
      ...(('completedAt' in taskData) && { completedAt: taskData.completedAt }),
      ...(('stages' in taskData) && { stages: taskData.stages }),
      ...(('description' in taskData) && { description: taskData.description }),
      ...(('metadata' in taskData) && { metadata: taskData.metadata }),
      ...(('errorMessage' in taskData) && { errorMessage: taskData.errorMessage }),
      ...(('errorDetails' in taskData) && { errorDetails: taskData.errorDetails }),
      ...(('currentStageId' in taskData) && { currentStageId: taskData.currentStageId }),
    };
    
    // If we already have this task in the map, merge with existing data
    const existingTask = taskMapRef.current.get(updateTaskId);
    if (existingTask) {
      taskMapRef.current.set(updateTaskId, { ...existingTask, ...taskToStore });
    } else {
      taskMapRef.current.set(updateTaskId, taskToStore);
    }
    
    console.log('Updated taskMap:', {
      taskId: updateTaskId,
      taskInMap: taskMapRef.current.has(updateTaskId),
      taskData: taskMapRef.current.get(updateTaskId)
    });

    setEvaluations(prevEvaluations => {
      const updatedEvaluations = prevEvaluations.map(evaluation => {
        if (!evaluation.task || evaluation.task.id !== updateTaskId) {
          return evaluation;
        }

        console.log('Updating evaluation task:', {
          evaluationId: evaluation.id,
          taskId: evaluation.task.id,
          oldStatus: evaluation.task.status,
          newStatus: taskData.status,
          oldStages: evaluation.task.stages,
          newStages: 'stages' in taskData ? taskData.stages : undefined
        });

        // Create updated task with new data
        const updatedTask = {
          ...evaluation.task,
          status: taskData.status, // Always update status
          // Only update other fields if they exist in the update and it's an AmplifyTask
          ...('startedAt' in taskData && { startedAt: taskData.startedAt }),
          ...('completedAt' in taskData && { completedAt: taskData.completedAt }),
          ...('stages' in taskData && { stages: taskData.stages })
        };

        return {
          ...evaluation,
          task: updatedTask
        };
      });

      const wasUpdated = updatedEvaluations.some(e => 
        e.task?.id === updateTaskId && e.task.status === taskData.status
      );

      console.log('Task update complete:', {
        evaluationsUpdated: wasUpdated,
        updateTaskId,
        evaluationCount: updatedEvaluations.length,
        taskIds: updatedEvaluations.map(e => e.task?.id).filter(Boolean)
      });

      return updatedEvaluations;
    });
  }, []);

  // Merge task stage update into evaluations
  const mergeTaskStageUpdate = useCallback((stageData: TaskStageType & { taskId: string }) => {
    const { taskId, ...stage } = stageData;

    console.log('Merging stage update:', {
      taskId,
      stageId: stage.id,
      status: stage.status
    });

    setEvaluations(prevEvaluations => {
      const updatedEvaluations = prevEvaluations.map(evaluation => {
        if (!evaluation.task || evaluation.task.id !== taskId) {
          return evaluation;
        }

        // Get current stages, handling both direct and lazy-loaded data
        const currentStages = getValueFromLazyLoader(evaluation.task.stages);
        const stageItems = currentStages?.data?.items || [];
        
        console.log('Current stage state:', {
          evaluationId: evaluation.id,
          taskId: evaluation.task.id,
          currentStageCount: stageItems.length,
          updatingStageId: stage.id
        });

        // Find if stage already exists
        const stageIndex = stageItems.findIndex(s => s.id === stage.id);
        
        // Create new stages array
        const updatedStages = {
          data: {
            items: stageIndex === -1 
              ? [...stageItems, stage]  // Add new stage
              : stageItems.map((s, i) => i === stageIndex ? { ...s, ...stage } : s)  // Update existing stage
          }
        };

        console.log('Updated stage state:', {
          evaluationId: evaluation.id,
          taskId: evaluation.task.id,
          updatedStageCount: updatedStages.data.items.length,
          wasStageFound: stageIndex !== -1
        });

        // Create updated task with new stages
        const updatedTask = {
          ...evaluation.task,
          stages: updatedStages
        };

        return {
          ...evaluation,
          task: updatedTask
        };
      });

      console.log('Stage update complete:', {
        evaluationsUpdated: updatedEvaluations.some(e => e.task?.id === taskId)
      });

      return updatedEvaluations;
    });
  }, []);

  // Setup subscriptions and initial data load
  useEffect(() => {
    if (!accountId) return;

    let subscriptions: { unsubscribe: () => void }[] = [];
    const client = getClient();

    // Initial data load and evaluation subscription
    const evaluationSubscription = observeRecentEvaluations(limit).subscribe({
      next: async ({ items, isSynced }) => {
        console.log('Received evaluations:', {
          count: items.length,
          firstItem: items[0] ? {
            id: items[0].id,
            type: items[0].type,
            task: items[0].task
          } : null
        });

        // Transform items and filter out nulls
        const transformedItems = items
          .map(item => {
            console.log('Processing item:', {
              id: item.id,
              type: item.type,
              hasTask: !!item.task,
              taskData: item.task
            });
            
            // If the item has a task, ensure we use the task data directly
            if (item.task && typeof item.task === 'object') {
              const transformedItem = {
                ...item,
                task: item.task
              };
              return transformEvaluation(transformedItem);
            }
            return transformEvaluation(item);
          })
          .reduce<Evaluation[]>((acc, item) => {
            if (item !== null && item !== undefined) {
              acc.push(item);
            }
            return acc;
          }, []);

        console.log('Transformed evaluations:', {
          count: transformedItems.length,
          firstItem: transformedItems[0] ? {
            id: transformedItems[0].id,
            type: transformedItems[0].type,
            task: transformedItems[0].task
          } : null
        });
        
        setEvaluations(transformedItems);
        updateMaps(transformedItems);
        
        if (isSynced) {
          setIsLoading(false);
        }

        // Find the active evaluation that needs score results
        const activeEvaluation = transformedItems
          .sort((a, b) => {
            const aStarted = a.startedAt ? new Date(a.startedAt).getTime() : 0;
            const bStarted = b.startedAt ? new Date(b.startedAt).getTime() : 0;
            return bStarted - aStarted;
          })
          .find(e => {
            const taskStatus = typeof e.task === 'function' ? null : e.task?.status;
            return (e.status === 'RUNNING' || e.status === 'COMPLETED') && 
                   (taskStatus === 'RUNNING' || taskStatus === 'COMPLETED');
          });

        if (activeEvaluation?.id && !activeSubscriptionRef.current) {
          // Clean up any existing subscription
          if (activeSubscriptionRef.current) {
            activeSubscriptionRef.current.unsubscribe();
            activeSubscriptionRef.current = null;
          }

          // Set up subscription for the active evaluation
          const subscription = observeScoreResults(client, activeEvaluation.id);
          activeSubscriptionRef.current = subscription.subscribe({
            next: ({ items: scoreResults }) => {
              setEvaluations(prevEvaluations => {
                return prevEvaluations.map(e => {
                  if (e.id === activeEvaluation.id) {
                    return {
                      ...e,
                      scoreResults: {
                        ...e.scoreResults,
                        items: scoreResults
                      }
                    };
                  }
                  return e;
                });
              });
            }
          });

          subscriptions.push(activeSubscriptionRef.current);
        }
      },
      error: (error: Error) => {
        console.error('Evaluations subscription error:', error);
        setError('Error fetching evaluations');
        setIsLoading(false);
      }
    });
    subscriptions.push(evaluationSubscription);

    // Add evaluation create/update subscriptions
    const evaluationCreateSubscription = (client.graphql({
      query: `
        subscription OnCreateEvaluation {
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
                itemId
                createdAt
              }
            }
          }
        }
      `
    }) as unknown as { subscribe: Function }).subscribe({
      next: async ({ data }: { data?: { onCreateEvaluation: Schema['Evaluation']['type'] } }) => {
        if (data?.onCreateEvaluation) {
          console.log('Evaluation create received:', {
            evaluationId: data.onCreateEvaluation.id,
            type: data.onCreateEvaluation.type,
            taskId: data.onCreateEvaluation.taskId,
            hasTask: !!data.onCreateEvaluation.task
          });

          // If the evaluation doesn't have a task but has a taskId, check our taskMap
          let evaluationWithTask = data.onCreateEvaluation;
          
          if (!evaluationWithTask.task && evaluationWithTask.taskId) {
            const task = taskMapRef.current.get(evaluationWithTask.taskId);
            if (task) {
              console.log('Found matching task in taskMap:', {
                taskId: task.id,
                status: task.status,
                taskData: task
              });
              
              // Create a task with the required Schema fields
              const schemaTask: Schema['Task']['type'] = {
                id: task.id,
                accountId: evaluationWithTask.accountId,
                type: task.type,
                status: task.status,
                target: task.target,
                command: task.command,
                account: () => Promise.resolve({ data: null }),
                currentStage: () => Promise.resolve({ data: null }),
                stages: () => Promise.resolve({ data: [], nextToken: null }),
                evaluation: () => Promise.resolve({ data: evaluationWithTask }),
                scorecard: () => Promise.resolve({ data: null }),
                score: () => Promise.resolve({ data: null }),
                createdAt: task.createdAt || new Date().toISOString(),
                updatedAt: task.updatedAt || new Date().toISOString()
              };
              
              evaluationWithTask = {
                ...evaluationWithTask,
                task: () => Promise.resolve({ data: schemaTask })
              };

              console.log('Created evaluation with task:', {
                evaluationId: evaluationWithTask.id,
                taskId: schemaTask.id,
                taskStatus: schemaTask.status,
                hasStages: !!schemaTask.stages
              });
            } else {
              console.warn('Task not found in taskMap:', evaluationWithTask.taskId, 'Current taskMap keys:', Array.from(taskMapRef.current.keys()));
            }
          }

          const transformedEvaluation = transformEvaluation(evaluationWithTask);
          if (transformedEvaluation) {
            setEvaluations(prev => [transformedEvaluation, ...prev]);
          }
        }
      },
      error: (error: Error) => {
        console.error('Evaluation create subscription error:', error);
      }
    });
    subscriptions.push(evaluationCreateSubscription);

    const evaluationUpdateSubscription = (client.graphql({
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
              }
            }
          }
        }
      `
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onUpdateEvaluation: Schema['Evaluation']['type'] } }) => {
        if (data?.onUpdateEvaluation) {
          console.log('Evaluation update received:', {
            evaluationId: data.onUpdateEvaluation.id,
            type: data.onUpdateEvaluation.type,
            status: data.onUpdateEvaluation.status,
            taskStatus: typeof data.onUpdateEvaluation.task === 'function' 
              ? null 
              : (data.onUpdateEvaluation.task as any)?.status, // Type assertion to bypass strict typing
            startedAt: data.onUpdateEvaluation.startedAt
          });

          const transformedEvaluation = transformEvaluation(data.onUpdateEvaluation);
          if (transformedEvaluation) {
            // Check if this evaluation is now running and should be subscribed to
            const isNowRunning = 
              transformedEvaluation.status === 'RUNNING' || 
              transformedEvaluation.task?.status === 'RUNNING';

            // Check if this is the most recent running evaluation
            const isMostRecent = (prevEvaluations: Evaluation[]) => {
              const runningEvals = prevEvaluations
                .filter(e => e.status === 'RUNNING' || e.task?.status === 'RUNNING')
                .sort((a, b) => {
                  const aStarted = a.startedAt ? new Date(a.startedAt).getTime() : 0;
                  const bStarted = b.startedAt ? new Date(b.startedAt).getTime() : 0;
                  return bStarted - aStarted;
                });
              return runningEvals[0]?.id === transformedEvaluation.id;
            };

            setEvaluations(prev => {
              const updatedEvaluations = prev.map(e => 
                e.id === transformedEvaluation.id ? transformedEvaluation : e
              );

              // If this evaluation is now running and is the most recent, set up subscription
              if (isNowRunning && isMostRecent(updatedEvaluations)) {
                const scoreResults = getValueFromLazyLoader(transformedEvaluation.scoreResults);
                console.log('Setting up score results subscription for evaluation:', {
                  evaluationId: transformedEvaluation.id,
                  currentScoreResultsCount: scoreResults?.length ?? 0,
                  taskStatus: getValueFromLazyLoader(transformedEvaluation.task)?.status,
                  evaluationStatus: transformedEvaluation.status,
                  isNewestEvaluation: transformedEvaluation === updatedEvaluations[0]
                });

                // Clean up existing subscription if any
                if (activeSubscriptionRef.current) {
                  console.log('Cleaning up existing subscription');
                  activeSubscriptionRef.current.unsubscribe();
                  activeSubscriptionRef.current = null;
                }

                // Set up new subscription
                const subscription = observeScoreResults(client, transformedEvaluation.id);
                const sub = subscription.subscribe({
                  next: (data: ScoreResultsSubscriptionResponse) => {
                    console.log('Received score results update:', {
                      evaluationId: transformedEvaluation.id,
                      scoreResultCount: data.items.length,
                      firstResult: data.items[0],
                      lastResult: data.items[data.items.length - 1],
                      timestamp: new Date().toISOString()
                    });
                    
                    setEvaluations(prevEvals => {
                      // Only create a new array if we actually update an evaluation
                      const evalToUpdate = prevEvals.find(e => e.id === transformedEvaluation.id);
                      if (!evalToUpdate) return prevEvals;

                      // Transform items to match expected type
                      const transformedItems = data.items.map(item => {
                        // Parse metadata if it's a string
                        let parsedMetadata;
                        try {
                          if (typeof item.metadata === 'string') {
                            parsedMetadata = JSON.parse(item.metadata);
                            if (typeof parsedMetadata === 'string') {
                              parsedMetadata = JSON.parse(parsedMetadata);
                            }
                          } else {
                            parsedMetadata = item.metadata || {};
                          }

                          console.log('Score result metadata in useEvaluationData:', {
                            rawMetadata: item.metadata,
                            parsedMetadata,
                            metadataType: typeof item.metadata,
                            hasResults: !!parsedMetadata?.results,
                            resultsKeys: parsedMetadata?.results ? Object.keys(parsedMetadata.results) : [],
                            humanLabel: parsedMetadata?.human_label,
                            nestedHumanLabel: parsedMetadata?.results?.[Object.keys(parsedMetadata.results)[0]]?.metadata?.human_label
                          });

                        } catch (e) {
                          console.error('Error parsing score result metadata:', e);
                          parsedMetadata = {};
                        }

                        // Extract results from nested structure if present
                        const firstResultKey = parsedMetadata?.results ? Object.keys(parsedMetadata.results)[0] : null;
                        const scoreResult = firstResultKey && parsedMetadata.results ? parsedMetadata.results[firstResultKey] : null;

                        const result = {
                          id: item.id,
                          value: item.value,
                          confidence: item.confidence ?? null,
                          explanation: item.explanation ?? scoreResult?.explanation ?? null,
                          metadata: {
                            human_label: scoreResult?.metadata?.human_label ?? parsedMetadata.human_label ?? item.metadata?.human_label ?? null,
                            correct: Boolean(scoreResult?.metadata?.correct ?? parsedMetadata.correct ?? item.metadata?.correct),
                            human_explanation: scoreResult?.metadata?.human_explanation ?? parsedMetadata.human_explanation ?? item.metadata?.human_explanation ?? null,
                            text: scoreResult?.metadata?.text ?? parsedMetadata.text ?? item.metadata?.text ?? null
                          },
                          itemId: item.itemId ?? parsedMetadata.item_id?.toString() ?? null,
                          createdAt: item.createdAt
                        };

                        console.log('Transformed score result in useEvaluationData:', {
                          id: result.id,
                          value: result.value,
                          humanLabel: result.metadata.human_label,
                          correct: result.metadata.correct,
                          rawMetadata: item.metadata,
                          parsedMetadata,
                          scoreResult,
                          nestedHumanLabel: scoreResult?.metadata?.human_label
                        });

                        return result;
                      });

                      // Create updated evaluation with new score results
                      const updatedEval = {
                        ...evalToUpdate,
                        scoreResults: {
                          items: transformedItems
                        }
                      };

                      // Only create new array if evaluation actually changed
                      if (Object.is(evalToUpdate.scoreResults?.items, updatedEval.scoreResults.items)) {
                        return prevEvals;
                      }

                      // Return new array with only the updated evaluation changed
                      return prevEvals.map(e => 
                        e.id === transformedEvaluation.id ? updatedEval : e
                      );
                    });
                  },
                  error: (error: Error) => {
                    console.error('Error in score results subscription:', error);
                  }
                });

                const unsubscribe = sub.unsubscribe;
                activeSubscriptionRef.current = { unsubscribe };
                subscriptions.push({ unsubscribe });
              }

              return updatedEvaluations;
            });
          }

          console.log('Checking if should subscribe to score results:', {
            evaluationId: data.onUpdateEvaluation.id,
            status: data.onUpdateEvaluation.status,
            taskStatus: typeof data.onUpdateEvaluation.task === 'function' 
              ? null 
              : (data.onUpdateEvaluation.task as any)?.status,
            hasExistingSubscription: !!activeSubscriptionRef.current
          });

          // After setting up new subscription
          console.log('Score results subscription set up:', {
            evaluationId: data.onUpdateEvaluation.id,
            subscriptionTime: new Date().toISOString()
          });

          // When receiving score results
          console.log('Score results received:', {
            evaluationId: data.onUpdateEvaluation.id,
            count: data.onUpdateEvaluation.scoreResults?.items?.length,
            firstResult: data.onUpdateEvaluation.scoreResults?.items?.[0],
            lastResult: data.onUpdateEvaluation.scoreResults?.items?.[data.onUpdateEvaluation.scoreResults.items.length - 1],
            timestamp: new Date().toISOString()
          });
        }
      },
      error: (error: Error) => {
        console.error('Evaluation update subscription error:', error);
      }
    });
    subscriptions.push(evaluationUpdateSubscription);

    // Task update subscription
    const taskSubscription = (client.graphql({
      query: TASK_UPDATE_SUBSCRIPTION
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onUpdateTask: AmplifyTask } }) => {
        if (data?.onUpdateTask) {
          console.log('Task update received:', {
            taskId: data.onUpdateTask.id,
            status: data.onUpdateTask.status
          });
          mergeTaskUpdate(data.onUpdateTask);
        }
      },
      error: (error: Error) => {
        console.error('Task subscription error:', error);
      }
    });
    subscriptions.push(taskSubscription);

    // Add task create subscription
    const taskCreateSubscription = (client.graphql({
      query: `
        subscription OnCreateTask {
          onCreateTask {
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
      `
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onCreateTask: AmplifyTask } }) => {
        if (data?.onCreateTask) {
          console.log('Task create received:', {
            taskId: data.onCreateTask.id,
            status: data.onCreateTask.status,
            type: data.onCreateTask.type
          });
          mergeTaskUpdate(data.onCreateTask);
        }
      },
      error: (error: Error) => {
        console.error('Task create subscription error:', error);
      }
    });
    subscriptions.push(taskCreateSubscription);

    // Task stage update subscription
    const stageSubscription = (client.graphql({
      query: TASK_STAGE_UPDATE_SUBSCRIPTION
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onUpdateTaskStage: TaskStageType & { taskId: string } } }) => {
        if (data?.onUpdateTaskStage) {
          console.log('Stage update received:', {
            stageId: data.onUpdateTaskStage.id,
            taskId: data.onUpdateTaskStage.taskId,
            status: data.onUpdateTaskStage.status
          });
          mergeTaskStageUpdate(data.onUpdateTaskStage);
        }
      },
      error: (error: Error) => {
        console.error('Task stage subscription error:', error);
      }
    });
    subscriptions.push(stageSubscription);

    return () => {
      console.log('Cleaning up all subscriptions');
      subscriptions.forEach(sub => sub.unsubscribe());
      if (activeSubscriptionRef.current) {
        activeSubscriptionRef.current.unsubscribe();
        activeSubscriptionRef.current = null;
      }
    };
  }, [accountId, limit, mergeTaskUpdate, mergeTaskStageUpdate, updateMaps]);

  const refetch = useCallback(() => {
    if (!accountId) return;
    setIsLoading(true);
    // The subscription will automatically refetch and update the data
  }, [accountId]);

  return {
    evaluations,
    isLoading,
    error,
    refetch
  };
} 