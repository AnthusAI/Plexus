import { useState, useEffect, useCallback, useRef } from 'react';
import { getClient } from '@/utils/amplify-client';
import { Observable } from 'rxjs';
import { 
  EVALUATION_UPDATE_SUBSCRIPTION, 
  TASK_UPDATE_SUBSCRIPTION, 
  TASK_STAGE_UPDATE_SUBSCRIPTION 
} from '../graphql/queries';
import type { Schema } from '@/amplify/data/resource';
import type { 
  BaseEvaluation,
  ProcessedEvaluation,
  TaskStageType, 
  AmplifyTask,
  Evaluation
} from '@/utils/data-operations';
import { 
  transformEvaluation, 
  getValueFromLazyLoader, 
  transformAmplifyTask, 
  processTask,
  listRecentEvaluations
} from '@/utils/data-operations';
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
  trace: any | null;
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
  selectedScorecard?: string | null;
  selectedScore?: string | null;
};

type UseEvaluationDataReturn = {
  evaluations: ProcessedEvaluation[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
};

export function useEvaluationData({ 
  accountId, 
  limit = 24,
  selectedScorecard = null,
  selectedScore = null
}: UseEvaluationDataProps): UseEvaluationDataReturn {
  const [evaluations, setEvaluations] = useState<ProcessedEvaluation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [evaluationMap, setEvaluationMap] = useState<Map<string, ProcessedEvaluation>>(new Map());
  const taskMapRef = useRef<Map<string, AmplifyTask>>(new Map());
  const stageMapRef = useRef<Map<string, Map<string, TaskStageType>>>(new Map());
  const activeSubscriptionRef = useRef<{ unsubscribe: () => void } | null>(null);
  
  // Store the current filter values in refs to use in the refetch function
  const filterValuesRef = useRef({
    accountId,
    limit,
    selectedScorecard,
    selectedScore
  });
  
  // Update the ref when filter values change
  useEffect(() => {
    filterValuesRef.current = {
      accountId,
      limit,
      selectedScorecard,
      selectedScore
    };
  }, [accountId, limit, selectedScorecard, selectedScore]);

  // Helper function to get task stages
  const getTaskStages = useCallback((taskId: string | null | undefined) => {
    if (!taskId) return new Map<string, TaskStageType>();
    
    let taskStages = stageMapRef.current.get(taskId);
    if (!taskStages) {
      taskStages = new Map<string, TaskStageType>();
      stageMapRef.current.set(taskId, taskStages);
    }
    return taskStages;
  }, []);

  // Helper function to get task stages items
  const getTaskStageItems = useCallback((taskId: string | null | undefined) => {
    const taskStages = getTaskStages(taskId);
    return Array.from(taskStages.values());
  }, [getTaskStages]);

  // Helper function to update task stages
  const updateTaskStages = useCallback((taskId: string | null | undefined, stageData: TaskStageType) => {
    if (!taskId || !stageData?.id) return;
    
    const taskStages = getTaskStages(taskId);
    taskStages.set(stageData.id, stageData);
  }, [getTaskStages]);

  // Helper function to get task stages size
  const getTaskStagesSize = useCallback((taskId: string | null | undefined) => {
    const taskStages = getTaskStages(taskId);
    return taskStages.size;
  }, [getTaskStages]);

  // Handle task updates
  const handleTaskUpdate = useCallback((taskData: any) => {
    if (!taskData?.id) {
      console.warn('Received task update without ID:', taskData);
      return;
    }

    const updateTaskId = taskData.id;

    // Store task data in map
    const taskToStore: AmplifyTask = {
      id: updateTaskId,
      type: taskData.type || '',
      status: taskData.status || '',
      target: taskData.target || '',
      command: taskData.command || '',
      ...('startedAt' in taskData && { startedAt: taskData.startedAt }),
      ...('completedAt' in taskData && { completedAt: taskData.completedAt }),
      ...('stages' in taskData && { stages: taskData.stages }),
      ...('description' in taskData && { description: taskData.description }),
      ...('metadata' in taskData && { metadata: taskData.metadata }),
      ...('errorMessage' in taskData && { errorMessage: taskData.errorMessage }),
      ...('errorDetails' in taskData && { errorDetails: taskData.errorDetails }),
      ...('currentStageId' in taskData && { currentStageId: taskData.currentStageId }),
    };
    
    // If we already have this task in the map, merge with existing data
    const existingTask = taskMapRef.current.get(updateTaskId);
    if (existingTask) {
      // Get existing stages from stageMap
      const stageItems = getTaskStageItems(updateTaskId);
      
      const mergedTask: AmplifyTask = { 
        ...existingTask, 
        ...taskToStore,
        // Ensure we keep existing stages if not provided in update
        stages: taskToStore.stages || { 
          data: { 
            items: stageItems 
          } 
        }
      };
      
      taskMapRef.current.set(updateTaskId, mergedTask);
    } else {
      taskMapRef.current.set(updateTaskId, taskToStore);
    }
    
    console.log('Updated taskMap:', {
      taskId: updateTaskId,
      taskInMap: taskMapRef.current.has(updateTaskId),
      taskData: taskMapRef.current.get(updateTaskId)
    });

    // Update any evaluations that reference this task
    setEvaluations(prevEvaluations => {
      let hasUpdates = false;
      const updatedEvaluations = prevEvaluations.map(evaluation => {
        const task = evaluation.task;
        if (!task?.id) return evaluation;

        if (task.id === updateTaskId) {
          hasUpdates = true;
          // Get all stages for this task
          const stageItems = getTaskStageItems(task.id);

          // Update the task with new data
          const updatedTask: AmplifyTask = {
            ...task,
            ...taskToStore,
            stages: {
              data: {
                items: stageItems
              }
            }
          };

          return {
            ...evaluation,
            task: updatedTask
          };
        }
        return evaluation;
      });

      return hasUpdates ? updatedEvaluations : prevEvaluations;
    });
  }, [getTaskStages, getTaskStageItems]);

  // Handle stage updates
  const handleStageUpdate = useCallback((stageData: TaskStageType) => {
    if (!stageData?.id || !stageData.taskId) {
      console.warn('Received stage update without ID or taskId:', stageData);
      return;
    }

    const taskId = stageData.taskId;

    // Update stage in map
    updateTaskStages(taskId, stageData);

    console.log('Updated stageMap:', {
      taskId,
      stageId: stageData.id,
      stageCount: getTaskStagesSize(taskId),
      stageData
    });

    // Update any evaluations that reference this task
    setEvaluations(prevEvaluations => {
      let hasUpdates = false;
      const updatedEvaluations = prevEvaluations.map(evaluation => {
        const task = evaluation.task;
        if (!task?.id) return evaluation;

        if (task.id === taskId) {
          hasUpdates = true;
          // Get all stages for this task
          const stageItems = getTaskStageItems(task.id);

          // Update existing task with new stages
          const updatedTask: AmplifyTask = {
            ...task,
            stages: {
              data: {
                items: stageItems
              }
            }
          };

          return {
            ...evaluation,
            task: updatedTask
          };
        }
        return evaluation;
      });

      return hasUpdates ? updatedEvaluations : prevEvaluations;
    });
  }, [getTaskStages, getTaskStageItems, updateTaskStages, getTaskStagesSize]);

  // Setup subscriptions and initial data load
  useEffect(() => {
    if (!accountId) return;
    
    // Clean up any existing subscription
    if (activeSubscriptionRef.current) {
      activeSubscriptionRef.current.unsubscribe();
      activeSubscriptionRef.current = null;
    }
    
    setIsLoading(true);
    
    let subscriptions: { unsubscribe: () => void }[] = [];
    const client = getClient();

    // Initial data load and evaluation subscription
    const evaluationSubscription = observeRecentEvaluations(
      limit, 
      accountId, 
      selectedScorecard, 
      selectedScore
    ).subscribe({
      next: async ({ items, isSynced }) => {
        console.log('Received evaluations:', {
          count: items.length,
          firstItem: items[0] ? {
            id: items[0].id,
            type: items[0].type,
            task: items[0].task
          } : null,
          filters: {
            selectedScorecard,
            selectedScore
          }
        });

        // Transform items and filter out nulls
        const transformedItems = items
          .map(item => {
            // Check if we have task data in our map
            if (item.taskId) {
              const taskData = taskMapRef.current.get(item.taskId);
              if (taskData) {
                // Get stages from stageMap
                const taskStages = stageMapRef.current.get(item.taskId);
                const stageItems = taskStages ? Array.from(taskStages.values()) : [];
                
                // Add stages to task data
                taskData.stages = {
                  data: {
                    items: stageItems
                  }
                };
                
                // Update the item with our task data
                item.task = taskData;
              }
            }
            
            return transformEvaluation(item);
          })
          .filter((item): item is ProcessedEvaluation => item !== null);

        setEvaluations(transformedItems);
        setIsLoading(false);
      },
      error: async (error) => {
        console.error('Error in evaluation subscription:', error);
        
        // Even if subscription fails, try to load data directly
        try {
          const response = await listRecentEvaluations(
            limit,
            accountId,
            selectedScorecard,
            selectedScore
          );
          
          console.log('Loaded evaluations directly after subscription error:', {
            count: response.length,
            filters: {
              selectedScorecard,
              selectedScore
            }
          });
          
          // Transform items and filter out nulls
          const transformedItems = response
            .map(item => transformEvaluation(item))
            .filter((item): item is ProcessedEvaluation => item !== null);
            
          setEvaluations(transformedItems);
        } catch (directError) {
          console.error('Error loading evaluations directly:', directError);
          setError('Failed to load evaluations');
        } finally {
          setIsLoading(false);
        }
      }
    });
    
    activeSubscriptionRef.current = evaluationSubscription;
    subscriptions.push(evaluationSubscription);

    // Subscribe to evaluation creates
    const evaluationCreateSubscription = (client.graphql({
      query: EVALUATION_UPDATE_SUBSCRIPTION.replace('onUpdateEvaluation', 'onCreateEvaluation')
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onCreateEvaluation: Schema['Evaluation']['type'] } }) => {
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
            const taskData = taskMapRef.current.get(evaluationWithTask.taskId);
            if (taskData) {
              // Get stages from stageMap
              const taskStages = evaluationWithTask.taskId ? 
                stageMapRef.current.get(evaluationWithTask.taskId) : 
                new Map<string, TaskStageType>();
              const stageItems = taskStages ? Array.from(taskStages.values()) : [];
              
              // Create a Schema-compliant task
              const schemaTask: Schema['Task']['type'] = {
                id: taskData.id,
                accountId: accountId!,
                type: taskData.type,
                status: taskData.status,
                target: taskData.target,
                command: taskData.command,
                description: taskData.description,
                metadata: taskData.metadata,
                createdAt: taskData.createdAt || new Date().toISOString(),
                startedAt: taskData.startedAt,
                completedAt: taskData.completedAt,
                estimatedCompletionAt: taskData.estimatedCompletionAt,
                errorMessage: taskData.errorMessage,
                errorDetails: taskData.errorDetails,
                currentStageId: taskData.currentStageId,
                // Add required lazy loaders
                account: () => Promise.resolve({ data: null }),
                currentStage: () => Promise.resolve({ data: null }),
                stages: () => {
                  // Get stages from stageMap
                  const taskStages = evaluationWithTask.taskId ? 
                    stageMapRef.current.get(evaluationWithTask.taskId) : 
                    new Map<string, TaskStageType>();
                  const stageItems = taskStages ? Array.from(taskStages.values()) : [];
                  return Promise.resolve({ 
                    data: stageItems.map(stage => ({
                      id: stage.id,
                      taskId: stage.taskId,
                      name: stage.name,
                      order: stage.order,
                      status: stage.status,
                      processedItems: stage.processedItems,
                      totalItems: stage.totalItems,
                      startedAt: stage.startedAt,
                      completedAt: stage.completedAt,
                      estimatedCompletionAt: stage.estimatedCompletionAt,
                      statusMessage: stage.statusMessage,
                      createdAt: stage.createdAt || new Date().toISOString(),
                      updatedAt: stage.updatedAt || new Date().toISOString(),
                      task: () => Promise.resolve({ data: schemaTask }),
                      tasksAsCurrentStage: () => Promise.resolve({ data: [], nextToken: null })
                    })) as Schema['TaskStage']['type'][],
                    nextToken: null
                  });
                },
                evaluation: () => Promise.resolve({ data: evaluationWithTask }),
                scorecard: () => Promise.resolve({ data: null }),
                score: () => Promise.resolve({ data: null }),
                report: () => Promise.resolve({ data: null }),
                updatedAt: new Date().toISOString()
              };
              
              // Create a function that returns the task data
              evaluationWithTask = {
                ...evaluationWithTask,
                task: () => Promise.resolve({ data: schemaTask })
              };
            }
          }

          const transformedEvaluation = transformEvaluation(evaluationWithTask);
          if (transformedEvaluation) {
            setEvaluations(prev => [transformedEvaluation, ...prev]);
          }
        }
      },
      error: (error: Error) => {
        console.error('Error in evaluation create subscription:', error);
      }
    });
    subscriptions.push(evaluationCreateSubscription);

    // Subscribe to evaluation updates
    const evaluationUpdateSubscription = (client.graphql({
      query: EVALUATION_UPDATE_SUBSCRIPTION
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onUpdateEvaluation: Schema['Evaluation']['type'] } }) => {
        if (data?.onUpdateEvaluation) {
          console.log('Evaluation update received:', {
            evaluationId: data.onUpdateEvaluation.id,
            type: data.onUpdateEvaluation.type,
            taskId: data.onUpdateEvaluation.taskId,
            hasTask: !!data.onUpdateEvaluation.task
          });

          // If the evaluation doesn't have a task but has a taskId, check our taskMap
          let evaluationWithTask = data.onUpdateEvaluation;
          if (!evaluationWithTask.task && evaluationWithTask.taskId) {
            const taskData = taskMapRef.current.get(evaluationWithTask.taskId);
            if (taskData) {
              // Get stages from stageMap
              const taskStages = evaluationWithTask.taskId ? 
                stageMapRef.current.get(evaluationWithTask.taskId) : 
                new Map<string, TaskStageType>();
              const stageItems = taskStages ? Array.from(taskStages.values()) : [];
              
              // Create a Schema-compliant task
              const schemaTask: Schema['Task']['type'] = {
                id: taskData.id,
                accountId: accountId!,
                type: taskData.type,
                status: taskData.status,
                target: taskData.target,
                command: taskData.command,
                description: taskData.description,
                metadata: taskData.metadata,
                createdAt: taskData.createdAt || new Date().toISOString(),
                startedAt: taskData.startedAt,
                completedAt: taskData.completedAt,
                estimatedCompletionAt: taskData.estimatedCompletionAt,
                errorMessage: taskData.errorMessage,
                errorDetails: taskData.errorDetails,
                currentStageId: taskData.currentStageId,
                // Add required lazy loaders
                account: () => Promise.resolve({ data: null }),
                currentStage: () => Promise.resolve({ data: null }),
                stages: () => {
                  // Get stages from stageMap
                  const taskStages = evaluationWithTask.taskId ? 
                    stageMapRef.current.get(evaluationWithTask.taskId) : 
                    new Map<string, TaskStageType>();
                  const stageItems = taskStages ? Array.from(taskStages.values()) : [];
                  return Promise.resolve({ 
                    data: stageItems.map(stage => ({
                      id: stage.id,
                      taskId: stage.taskId,
                      name: stage.name,
                      order: stage.order,
                      status: stage.status,
                      processedItems: stage.processedItems,
                      totalItems: stage.totalItems,
                      startedAt: stage.startedAt,
                      completedAt: stage.completedAt,
                      estimatedCompletionAt: stage.estimatedCompletionAt,
                      statusMessage: stage.statusMessage,
                      createdAt: stage.createdAt || new Date().toISOString(),
                      updatedAt: stage.updatedAt || new Date().toISOString(),
                      task: () => Promise.resolve({ data: schemaTask }),
                      tasksAsCurrentStage: () => Promise.resolve({ data: [], nextToken: null })
                    })) as Schema['TaskStage']['type'][],
                    nextToken: null
                  });
                },
                evaluation: () => Promise.resolve({ data: evaluationWithTask }),
                scorecard: () => Promise.resolve({ data: null }),
                score: () => Promise.resolve({ data: null }),
                report: () => Promise.resolve({ data: null }),
                updatedAt: new Date().toISOString()
              };
              
              // Create a function that returns the task data
              evaluationWithTask = {
                ...evaluationWithTask,
                task: () => Promise.resolve({ data: schemaTask })
              };
            }
          }

          const transformedEvaluation = transformEvaluation(evaluationWithTask);
          if (transformedEvaluation) {
            // Check if this evaluation is now running and should be subscribed to
            const isNowRunning = 
              transformedEvaluation.status === 'RUNNING' || 
              transformedEvaluation.task?.status === 'RUNNING';

            // Check if this is the most recent running evaluation
            const isMostRecent = (prevEvaluations: ProcessedEvaluation[]) => {
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
                            human_label: scoreResult?.metadata?.human_label ?? parsedMetadata.human_label ?? (typeof item.metadata === 'object' ? (item.metadata as any).human_label : null) ?? null,
                            correct: Boolean(scoreResult?.metadata?.correct ?? parsedMetadata.correct ?? (typeof item.metadata === 'object' ? (item.metadata as any).correct : null)),
                            human_explanation: scoreResult?.metadata?.human_explanation ?? parsedMetadata.human_explanation ?? (typeof item.metadata === 'object' ? (item.metadata as any).human_explanation : null) ?? null,
                            text: scoreResult?.metadata?.text ?? parsedMetadata.text ?? (typeof item.metadata === 'object' ? (item.metadata as any).text : null) ?? null
                          },
                          itemId: item.itemId ?? parsedMetadata.item_id?.toString() ?? null,
                          createdAt: item.createdAt || new Date().toISOString(),
                          trace: item.trace ?? null,
                          feedbackItem: item.feedbackItem ?? null  // Preserve feedbackItem relationship
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
                        scoreResults: transformedItems
                      };

                      // Only create new array if evaluation actually changed
                      if (Object.is(evalToUpdate.scoreResults, updatedEval.scoreResults)) {
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
            hasScoreResults: !!data.onUpdateEvaluation.scoreResults,
            timestamp: new Date().toISOString()
          });
        }
      },
      error: (error: Error) => {
        console.error('Error in evaluation update subscription:', error);
      }
    });
    subscriptions.push(evaluationUpdateSubscription);

    // Subscribe to task updates
    const taskSubscription = (client.graphql({
      query: TASK_UPDATE_SUBSCRIPTION
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onUpdateTask: any } }) => {
        if (data?.onUpdateTask) {
          handleTaskUpdate(data.onUpdateTask);
        }
      },
      error: (error: Error) => {
        console.error('Error in task update subscription:', error);
      }
    });
    subscriptions.push(taskSubscription);

    // Subscribe to task stage updates
    const stageSubscription = (client.graphql({
      query: TASK_STAGE_UPDATE_SUBSCRIPTION
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onUpdateTaskStage: any } }) => {
        if (data?.onUpdateTaskStage) {
          handleStageUpdate(data.onUpdateTaskStage);
        }
      },
      error: (error: Error) => {
        console.error('Error in task stage update subscription:', error);
      }
    });
    subscriptions.push(stageSubscription);

    return () => {
      subscriptions.forEach(sub => sub.unsubscribe());
      if (activeSubscriptionRef.current) {
        activeSubscriptionRef.current.unsubscribe();
        activeSubscriptionRef.current = null;
      }
    };
  }, [accountId, limit, selectedScorecard, selectedScore, handleTaskUpdate, handleStageUpdate]);

  // Define refetch function to reload data with current filters
  const refetch = useCallback(() => {
    if (!filterValuesRef.current.accountId) return;
    
    // Clean up existing subscription
    if (activeSubscriptionRef.current) {
      activeSubscriptionRef.current.unsubscribe();
      activeSubscriptionRef.current = null;
    }
    
    setIsLoading(true);
    
    // Create new subscription with current filter values
    const newSubscription = observeRecentEvaluations(
      filterValuesRef.current.limit,
      filterValuesRef.current.accountId,
      filterValuesRef.current.selectedScorecard,
      filterValuesRef.current.selectedScore
    ).subscribe({
      next: async ({ items, isSynced }) => {
        console.log('Refetched evaluations:', {
          count: items.length,
          filters: {
            selectedScorecard: filterValuesRef.current.selectedScorecard,
            selectedScore: filterValuesRef.current.selectedScore
          }
        });

        // Transform items and filter out nulls
        const transformedItems = items
          .map(item => {
            // Check if we have task data in our map
            if (item.taskId) {
              const taskData = taskMapRef.current.get(item.taskId);
              if (taskData) {
                // Get stages from stageMap
                const taskStages = stageMapRef.current.get(item.taskId);
                const stageItems = taskStages ? Array.from(taskStages.values()) : [];
                
                // Add stages to task data
                taskData.stages = {
                  data: {
                    items: stageItems
                  }
                };
                
                // Update the item with our task data
                item.task = taskData;
              }
            }
            
            return transformEvaluation(item);
          })
          .filter((item): item is ProcessedEvaluation => item !== null);

        setEvaluations(transformedItems);
        setIsLoading(false);
      },
      error: (error) => {
        console.error('Error in evaluation refetch:', error);
        
        // Even if subscription fails, try to load data directly
        async function loadDataDirectly() {
          try {
            const response = await listRecentEvaluations(
              filterValuesRef.current.limit,
              filterValuesRef.current.accountId,
              filterValuesRef.current.selectedScorecard,
              filterValuesRef.current.selectedScore
            );
            
            console.log('Loaded evaluations directly after subscription error:', {
              count: response.length,
              filters: {
                selectedScorecard: filterValuesRef.current.selectedScorecard,
                selectedScore: filterValuesRef.current.selectedScore
              }
            });
            
            // Transform items and filter out nulls
            const transformedItems = response
              .map(item => transformEvaluation(item))
              .filter((item): item is ProcessedEvaluation => item !== null);
              
            setEvaluations(transformedItems);
          } catch (directError) {
            console.error('Error loading evaluations directly:', directError);
            setError('Failed to load evaluations');
          } finally {
            setIsLoading(false);
          }
        }
        
        loadDataDirectly();
      }
    });
    
    activeSubscriptionRef.current = newSubscription;
  }, []);

  return { evaluations, isLoading, error, refetch };
} 