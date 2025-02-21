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
  AmplifyTask 
} from '@/utils/data-operations';
import { transformEvaluation, getValueFromLazyLoader, transformAmplifyTask, processTask } from '@/utils/data-operations';
import { observeRecentEvaluations } from '@/utils/data-operations';

type UseEvaluationDataProps = {
  accountId: string | null;
  limit?: number;
};

type UseEvaluationDataReturn = {
  evaluations: ProcessedEvaluation[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
};

export function useEvaluationData({ accountId, limit = 24 }: UseEvaluationDataProps): UseEvaluationDataReturn {
  const [evaluations, setEvaluations] = useState<ProcessedEvaluation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [evaluationMap, setEvaluationMap] = useState<Map<string, ProcessedEvaluation>>(new Map());
  const taskMapRef = useRef<Map<string, AmplifyTask>>(new Map());
  const stageMapRef = useRef<Map<string, Map<string, TaskStageType>>>(new Map());

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
        console.error('Error in evaluation subscription:', error);
        setError('Failed to load evaluations');
        setIsLoading(false);
      }
    });
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
            setEvaluations(prev => 
              prev.map(e => e.id === transformedEvaluation.id ? transformedEvaluation : e)
            );
          }
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
    };
  }, [accountId, limit, handleTaskUpdate, handleStageUpdate]);

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