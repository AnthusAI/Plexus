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
    
    console.log(`STAGE_TRACE: handleTaskUpdate received task ${updateTaskId} status=${taskData.status} hasStages=${!!taskData.stages}`);

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

          // Only update if we have meaningful changes
          // Don't override stage data if the task update doesn't have stages
          const hasIncomingStages = !!taskToStore.stages && taskToStore.stages.data?.items?.length > 0;
          const hasExistingTaskStages = !!task.stages && (task.stages.data?.items?.length > 0 || task.stages.items?.length > 0);
          const hasStageMapData = stageItems.length > 0;
          
          // Preserve existing task stages if:
          // 1. The incoming task update has no stages AND
          // 2. We have existing task stages OR we have stage map data
          const shouldPreserveExistingTaskStages = !hasIncomingStages && hasExistingTaskStages;
          const shouldUseStageMapData = !hasIncomingStages && !hasExistingTaskStages && hasStageMapData;
          
          console.log(`STAGE_TRACE: handleTaskUpdate eval ${evaluation.id} preserve=${shouldPreserveExistingTaskStages} useMap=${shouldUseStageMapData} existing=${hasExistingTaskStages ? (task.stages?.data?.items?.length || task.stages?.items?.length || 0) : 0} stageMap=${hasStageMapData ? stageItems.length : 0}`);

          // Update the task with new data, but preserve stages intelligently
          const updatedTask: AmplifyTask = {
            ...task,
            ...taskToStore,
            stages: shouldPreserveExistingTaskStages ? task.stages : 
                   shouldUseStageMapData ? { data: { items: stageItems } } :
                   hasIncomingStages ? taskToStore.stages : 
                   task.stages // Fallback to existing
          };

          const finalStageCount = updatedTask.stages?.data?.items?.length || updatedTask.stages?.items?.length || 0;
          console.log(`STAGE_TRACE: handleTaskUpdate created updatedTask for ${updateTaskId} with ${finalStageCount} stages`);

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
    
    console.log(`STAGE_TRACE: handleStageUpdate received ${stageData.name}:${stageData.status} for task ${taskId} at ${new Date().toLocaleTimeString()}`);

    // Update stage in map
    updateTaskStages(taskId, stageData);

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
          
          console.log(`STAGE_TRACE: handleStageUpdate updating eval ${evaluation.id} (taskId: ${task.id}) with stages: ${stageItems.map(s => `${s.name}:${s.status}`).join(',')} at ${new Date().toLocaleTimeString()}`);

          // Update existing task with new stages - FORCE NEW OBJECT REFERENCES
          const updatedTask: AmplifyTask = {
            ...task,
            stages: {
              data: {
                items: [...stageItems] // Create new array reference
              }
            }
          };

          const updatedEvaluation = {
            ...evaluation,
            task: updatedTask
          };

          return updatedEvaluation;
        }
        return evaluation;
      });

      if (hasUpdates) {
        console.log(`STAGE_TRACE: handleStageUpdate setting ${updatedEvaluations.length} evaluations`);
      }

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
        // Process evaluations from subscription

        // Transform items and filter out nulls
        const transformedItems = items
          .map((item, index) => {
            // CRITICAL FIX: Preserve existing stage data instead of overwriting it
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
                console.log(`🔍 TRACE_STAGES: Found task data for item ${index} - using taskMap data with ${stageItems.length} stages`);
              } else {
                // PRESERVE existing task data if we don't have fresh data
                if (item.task && typeof item.task === 'object') {
                  console.log(`🔍 TRACE_STAGES: No taskMap data for item ${index} - preserving existing task data`);
                  // Keep the existing task data as-is, don't overwrite it
                } else {
                  console.log(`🔍 TRACE_STAGES: No task data found for item ${index} - will use transformEvaluation fallback`);
                }
              }
            } else {
              // Check if we can find task data using the evaluation ID as the task ID
              // This might happen if the evaluation's taskId is null but the task exists
              const taskDataByEvalId = taskMapRef.current.get(item.id);
              if (taskDataByEvalId) {
                // Get stages from stageMap - check both the evaluation ID and the actual task ID
                let taskStages = stageMapRef.current.get(item.id);
                if (!taskStages) {
                  taskStages = stageMapRef.current.get(taskDataByEvalId.id);
                }
                const stageItems = taskStages ? Array.from(taskStages.values()) : [];
                
                // Add stages to task data
                taskDataByEvalId.stages = {
                  data: {
                    items: stageItems
                  }
                };
                
                // Update the item with the fallback task data
                item.task = taskDataByEvalId;
                
                // Also update the item's taskId to maintain consistency
                item.taskId = taskDataByEvalId.id;
              }
            }
            
            const transformed = transformEvaluation(item);
            return transformed;
          })
          .filter((item): item is ProcessedEvaluation => item !== null);

        console.log(`STAGE_TRACE: setEvaluations with ${transformedItems.length} items`);
        
        // CRITICAL FIX: Merge with existing evaluations to preserve stage data and names
        setEvaluations(prevEvaluations => {
          const merged = transformedItems.map(newEval => {
            const existingEval = prevEvaluations.find(e => e.id === newEval.id);
            
            // If we have an existing evaluation with good stage data, preserve it
            if (existingEval && existingEval.task?.stages?.data?.items?.length > 0) {
              // Keep the existing stage data, but update other fields
              const preservedStageData = existingEval.task.stages;
              console.log(`🔍 TRACE_STAGES: Preserving existing stage data for ${newEval.id}: ${preservedStageData.data.items.map(s => `${s.name}:${s.status}`).join(',')}`);
              
              return {
                ...newEval,
                // Preserve scorecard/score names to avoid flicker if missing in new payload
                scorecard: newEval.scorecard || existingEval.scorecard,
                score: newEval.score || existingEval.score,
                task: newEval.task ? {
                  ...newEval.task,
                  stages: preservedStageData
                } : newEval.task
              };
            }
            
            return {
              ...newEval,
              // Preserve scorecard/score names to avoid flicker if missing in new payload
              scorecard: newEval.scorecard || existingEval?.scorecard || newEval.scorecard,
              score: newEval.score || existingEval?.score || newEval.score
            };
          });
          
          return merged;
        });
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
            
          // CRITICAL FIX: Merge with existing evaluations to preserve stage data and names (direct load version)
          setEvaluations(prevEvaluations => {
            const merged = transformedItems.map(newEval => {
              const existingEval = prevEvaluations.find(e => e.id === newEval.id);
              
              // If we have an existing evaluation with good stage data, preserve it
              if (existingEval && existingEval.task?.stages?.data?.items?.length > 0) {
                // Keep the existing stage data, but update other fields
                const preservedStageData = existingEval.task.stages;
                console.log(`🔍 TRACE_STAGES: Preserving existing stage data (direct load) for ${newEval.id}: ${preservedStageData.data.items.map(s => `${s.name}:${s.status}`).join(',')}`);
                
                return {
                  ...newEval,
                  scorecard: newEval.scorecard || existingEval.scorecard,
                  score: newEval.score || existingEval.score,
                  task: newEval.task ? {
                    ...newEval.task,
                    stages: preservedStageData
                  } : newEval.task
                };
              }
              
              return {
                ...newEval,
                scorecard: newEval.scorecard || existingEval?.scorecard || newEval.scorecard,
                score: newEval.score || existingEval?.score || newEval.score
              };
            });
            
            return merged;
          });
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

    // Removed onCreateEvaluation subscription to avoid transient duplicates.

    // Subscribe to evaluation updates - TEMPORARILY RE-ENABLED FOR DEBUGGING
    const evaluationUpdateSubscription = (client.graphql({
      query: EVALUATION_UPDATE_SUBSCRIPTION
    }) as unknown as { subscribe: Function }).subscribe({
      next: async ({ data }: { data?: { onUpdateEvaluation: Schema['Evaluation']['type'] } }) => {
        if (data?.onUpdateEvaluation) {

          // If we have scorecard/score IDs but no scorecard/score data, fetch them
          const needsScorecard = data.onUpdateEvaluation.scorecardId && !data.onUpdateEvaluation.scorecard;
          const needsScore = data.onUpdateEvaluation.scoreId && !data.onUpdateEvaluation.score;
          
          
          if (needsScorecard || needsScore) {
            
            try {
              // Fetch scorecard data if needed
              if (needsScorecard) {
                (client.graphql({
                query: `query GetScorecard($id: ID!) {
                  getScorecard(id: $id) {
                    id
                    name
                  }
                }`,
                variables: { id: data.onUpdateEvaluation.scorecardId }
              }) as Promise<any>).then((result: any) => {
                if (result.data?.getScorecard) {
                  // Update the evaluation with the scorecard data
                  setEvaluations(prev => {
                    const updated = prev.map(e => {
                      if (e.id === data.onUpdateEvaluation.id) {
                        const updatedEval = {
                          ...e,
                          scorecard: { 
                            id: result.data.getScorecard.id, 
                            name: result.data.getScorecard.name 
                          }
                        };
                        return updatedEval;
                      }
                      return e;
                    });
                    return [...updated]; // Force new array reference
                  });
                }
              }).catch((error: any) => {
                console.error('Error fetching scorecard:', error);
              });
            }
            
            // Fetch score data if needed
            if (needsScore) {
              (client.graphql({
                query: `query GetScore($id: ID!) {
                  getScore(id: $id) {
                    id
                    name
                  }
                }`,
                variables: { id: data.onUpdateEvaluation.scoreId }
              }) as Promise<any>).then((result: any) => {
                if (result.data?.getScore) {
                  // Update the evaluation with the score data
                  setEvaluations(prev => {
                    const updated = prev.map(e => {
                      if (e.id === data.onUpdateEvaluation.id) {
                        const updatedEval = {
                          ...e,
                          score: { 
                            id: result.data.getScore.id, 
                            name: result.data.getScore.name 
                          }
                        };
                        return updatedEval;
                      }
                      return e;
                    });
                    return [...updated]; // Force new array reference
                  });
                }
              }).catch((error: any) => {
                console.error('Error fetching score:', error);
              });
            }
            } catch (fetchError) {
              console.error('Error in scorecard/score fetching:', fetchError);
            }
          }

          // Always fetch the complete Task record with nested TaskStage information
          let evaluationWithTask = data.onUpdateEvaluation;
          if (evaluationWithTask.taskId) {
            console.log('📋 DEBUG: Fetching complete Task record with stages for taskId:', evaluationWithTask.taskId);
            
            // Fetch the complete task record
            try {
              const taskResponse = await (client.models.Task.get as any)({ 
                id: evaluationWithTask.taskId
              });
              
              if (taskResponse?.data) {
                console.log('📋 DEBUG: Retrieved complete Task record:', {
                  taskId: taskResponse.data.id,
                  taskStatus: taskResponse.data.status,
                  rawStages: taskResponse.data.stages,
                  stagesIsFunction: typeof taskResponse.data.stages === 'function'
                });
                
                // Use the Task -> stages relationship approach that the user proved works
                console.log('📋 DEBUG: Querying TaskStages via Task relationship for update - taskId:', taskResponse.data.id);
                let stageItems: any[] = [];
                
                try {
                  // Use the approach that works: get Task with stages relationship
                  const taskWithStagesResponse = await client.graphql({
                    query: `
                      query GetTaskWithStages($id: ID!) {
                        getTask(id: $id) {
                          id
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
                              taskId
                              createdAt
                              updatedAt
                            }
                          }
                        }
                      }
                    `,
                    variables: { id: taskResponse.data!.id }
                  }) as any;
                  
                  console.log('🔍 TRACE_STAGES: Task->stages relationship query result for update:', {
                    taskId: taskResponse.data.id,
                    response: taskWithStagesResponse,
                    hasData: !!taskWithStagesResponse?.data?.getTask,
                    stageCount: taskWithStagesResponse?.data?.getTask?.stages?.items?.length || 0,
                    stages: taskWithStagesResponse?.data?.getTask?.stages?.items?.map((s: any) => ({ 
                      id: s.id,
                      name: s.name, 
                      status: s.status,
                      processedItems: s.processedItems,
                      totalItems: s.totalItems
                    })) || []
                  });
                  
                  if (taskWithStagesResponse?.data?.getTask?.stages?.items && taskWithStagesResponse.data.getTask.stages.items.length > 0) {
                    stageItems = taskWithStagesResponse.data.getTask.stages.items;
                    console.log('📋 DEBUG: Successfully retrieved stages via Task relationship for update!');
                  }
                } catch (taskStagesError) {
                  console.warn('Failed to query TaskStages via Task relationship for update:', taskStagesError);
                }
                
                // Fallback: Try the LazyLoader approach if direct query didn't work
                if (stageItems.length === 0 && taskResponse.data.stages && typeof taskResponse.data.stages === 'function') {
                  try {
                    console.log('📋 DEBUG: Fallback - Resolving stages LazyLoader for update...');
                    const stagesResponse = await taskResponse.data.stages();
                    console.log('📋 DEBUG: Raw stagesResponse for update:', stagesResponse);
                    
                    if (stagesResponse?.data && stagesResponse.data.length > 0) {
                      // If data is a direct array (not {items: []})
                      stageItems = stagesResponse.data;
                      console.log('📋 DEBUG: Resolved stages for update:', {
                        stageCount: stageItems.length,
                        stages: stageItems.map(s => ({ 
                          name: s.name, 
                          status: s.status,
                          processedItems: s.processedItems,
                          totalItems: s.totalItems
                        }))
                      });
                    } else if ((stagesResponse?.data as any)?.items && (stagesResponse.data as any).items.length > 0) {
                      // If data is wrapped in {items: []}
                      stageItems = (stagesResponse.data as any).items;
                      console.log('📋 DEBUG: Resolved stages for update (items format):', {
                        stageCount: stageItems.length,
                        stages: stageItems.map(s => ({ 
                          name: s.name, 
                          status: s.status,
                          processedItems: s.processedItems,
                          totalItems: s.totalItems
                        }))
                      });
                    } else {
                      console.log('📋 DEBUG: No stages found yet for update - likely timing issue. Will retry in 1 second...', {
                        taskId: taskResponse.data.id,
                        taskStatus: taskResponse.data.status,
                        responseData: stagesResponse?.data
                      });
                      
                      // Retry after a short delay in case stages are created after the task
                      setTimeout(async () => {
                        try {
                          console.log('📋 DEBUG: Retrying stages fetch for update...');
                          const retryStagesResponse = taskResponse.data ? await (taskResponse.data as any).stages() : null;
                          if (retryStagesResponse?.data && retryStagesResponse.data.length > 0) {
                            const retryStageItems = retryStagesResponse.data;
                            console.log('📋 DEBUG: Retry successful - found stages for update:', {
                              stageCount: retryStageItems.length,
                              stages: retryStageItems.map((s: any) => ({ 
                                name: s.name, 
                                status: s.status 
                              }))
                            });
                            
                            // Update the stage maps if we have task data
                            if (taskResponse.data) {
                              const taskStages = getTaskStages(taskResponse.data.id);
                              taskStages.clear();
                              retryStageItems.forEach((stage: any) => {
                                taskStages.set(stage.id, {
                                  id: stage.id,
                                  taskId: stage.taskId || taskResponse.data!.id,
                                  name: stage.name,
                                  order: stage.order,
                                  status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
                                  processedItems: stage.processedItems || undefined,
                                  totalItems: stage.totalItems || undefined,
                                  startedAt: stage.startedAt || undefined,
                                  completedAt: stage.completedAt || undefined,
                                  estimatedCompletionAt: stage.estimatedCompletionAt || undefined,
                                  statusMessage: stage.statusMessage || undefined,
                                  createdAt: stage.createdAt,
                                  updatedAt: stage.updatedAt
                                });
                              });
                              
                              // Trigger handleTaskUpdate to refresh the UI
                              handleTaskUpdate({
                                id: taskResponse.data.id,
                                status: taskResponse.data.status,
                                stages: { items: retryStageItems }
                              });
                            }
                          } else {
                            console.log('📋 DEBUG: Retry still found no stages for update');
                          }
                        } catch (retryError) {
                          console.warn('📋 DEBUG: Retry failed for stages fetch:', retryError);
                        }
                      }, 1000);
                    }
                  } catch (stagesError) {
                    console.warn('Failed to resolve stages LazyLoader for update:', stagesError);
                    console.log('📋 DEBUG: stages function details:', {
                      stagesType: typeof taskResponse.data.stages,
                      stagesFunction: taskResponse.data.stages.toString().substring(0, 200)
                    });
                  }
                }
                
                // Update our task and stage maps with the fresh data
                const taskToStore: AmplifyTask = {
                  id: taskResponse.data.id,
                  type: taskResponse.data.type,
                  status: taskResponse.data.status,
                  target: taskResponse.data.target,
                  command: taskResponse.data.command,
                  description: taskResponse.data.description,
                  metadata: taskResponse.data.metadata,
                  createdAt: taskResponse.data.createdAt,
                  startedAt: taskResponse.data.startedAt,
                  completedAt: taskResponse.data.completedAt,
                  estimatedCompletionAt: taskResponse.data.estimatedCompletionAt,
                  errorMessage: taskResponse.data.errorMessage,
                  errorDetails: taskResponse.data.errorDetails,
                  currentStageId: taskResponse.data.currentStageId,
                  stages: {
                    data: {
                      items: stageItems
                    }
                  }
                };
                
                // Store in taskMap
                taskMapRef.current.set(taskResponse.data.id, taskToStore);
                
                // Update stage map with the latest stage data
                if (stageItems.length > 0 && taskResponse.data) {
                  const taskStages = getTaskStages(taskResponse.data.id);
                  taskStages.clear(); // Clear old stages
                  stageItems.forEach(stage => {
                    taskStages.set(stage.id, {
                      id: stage.id,
                      taskId: stage.taskId || taskResponse.data!.id,
                      name: stage.name,
                      order: stage.order,
                      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
                      processedItems: stage.processedItems || undefined,
                      totalItems: stage.totalItems || undefined,
                      startedAt: stage.startedAt || undefined,
                      completedAt: stage.completedAt || undefined,
                      estimatedCompletionAt: stage.estimatedCompletionAt || undefined,
                      statusMessage: stage.statusMessage || undefined,
                      createdAt: stage.createdAt,
                      updatedAt: stage.updatedAt
                    });
                  });
                }
                
                // Create a direct task object with stages for EvaluationCard compatibility
                const directTaskWithStages = {
                  ...taskToStore,
                  stages: {
                    data: {
                      items: stageItems.map(stage => ({
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
                        createdAt: stage.createdAt,
                        updatedAt: stage.updatedAt
                      }))
                    }
                  }
                };
                
                // Assign the direct task object to evaluation (cast to satisfy TypeScript)
                evaluationWithTask = {
                  ...evaluationWithTask,
                  task: directTaskWithStages as any
                };
                
                console.log('🔍 TRACE_STAGES: About to transform evaluation with fetched task (UPDATE):', {
                  evaluationId: evaluationWithTask.id,
                  hasTask: !!evaluationWithTask.task,
                  taskId: (evaluationWithTask.task as any)?.id,
                  taskStages: (evaluationWithTask.task as any)?.stages,
                  taskStageCount: (evaluationWithTask.task as any)?.stages?.data?.items?.length || 0
                });
              }
            } catch (taskFetchError) {
              console.warn('Failed to fetch complete Task record, falling back to taskMap:', taskFetchError);
              // Fall back to existing logic if task fetch fails
            }
          }
          
          // Fallback: If the evaluation doesn't have a task but has a taskId, check our taskMap
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
              
              // Create a direct task object with stages for EvaluationCard compatibility  
              const directTaskWithStages = {
                ...taskData,
                stages: {
                  data: {
                    items: stageItems.map(stage => ({
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
                      createdAt: stage.createdAt,
                      updatedAt: stage.updatedAt
                    }))
                  }
                }
              };
              
              // Assign the direct task object to evaluation (cast to satisfy TypeScript)
              evaluationWithTask = {
                ...evaluationWithTask,
                task: directTaskWithStages as any
              };
            }
          }

          console.log('📋 DEBUG: Before transformEvaluation (UPDATE) - evaluationWithTask.task details:', {
            evaluationId: evaluationWithTask.id,
            taskId: (evaluationWithTask.task as any)?.id,
            taskStages: (evaluationWithTask.task as any)?.stages,
            taskStagesData: (evaluationWithTask.task as any)?.stages?.data,
            taskStagesItems: (evaluationWithTask.task as any)?.stages?.data?.items,
            stageCount: (evaluationWithTask.task as any)?.stages?.data?.items?.length || 0,
            firstStage: (evaluationWithTask.task as any)?.stages?.data?.items?.[0]
          });

          const transformedEvaluation = transformEvaluation(evaluationWithTask);
          
          console.log('📋 DEBUG: After transformEvaluation (UPDATE):', {
            evaluationId: evaluationWithTask.id,
            hadTask: !!evaluationWithTask.task,
            hasTransformedTask: !!transformedEvaluation?.task,
            transformedTaskId: transformedEvaluation?.task?.id,
            transformedTaskStages: transformedEvaluation?.task?.stages,
            transformedStageCount: getValueFromLazyLoader(transformedEvaluation?.task?.stages)?.data?.items?.length || 0,
            transformedStageItems: getValueFromLazyLoader(transformedEvaluation?.task?.stages)?.data?.items?.map((s: any) => ({ name: s.name, status: s.status })) || []
          });
          
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
              // Find existing evaluation
              const existingEval = prev.find(e => e.id === transformedEvaluation.id);
              if (!existingEval) {
                console.log(`STAGE_TRACE: Evaluation update for non-existent eval ${transformedEvaluation.id}`);
                return prev;
              }

              // Check if this is a meaningful update by comparing key fields
              const isMeaningfulUpdate = 
                existingEval.status !== transformedEvaluation.status ||
                existingEval.accuracy !== transformedEvaluation.accuracy ||
                existingEval.processedItems !== transformedEvaluation.processedItems ||
                existingEval.totalItems !== transformedEvaluation.totalItems;

              if (!isMeaningfulUpdate) {
                console.log(`STAGE_TRACE: Skipping non-meaningful update for eval ${transformedEvaluation.id}`);
                return prev;
              }

              console.log(`STAGE_TRACE: Processing meaningful update for eval ${transformedEvaluation.id}`);

              const updatedEvaluations = prev.map(e => {
                if (e.id === transformedEvaluation.id) {
                  // Preserve existing task data if the update doesn't contain good task information
                  const shouldPreserveExistingTask = !transformedEvaluation.task && !!e.task;
                  const shouldPreserveExistingTaskStages = transformedEvaluation.task && 
                    e.task && 
                    (!transformedEvaluation.task.stages?.data?.items || transformedEvaluation.task.stages.data.items.length === 0) &&
                    (e.task.stages?.data?.items && e.task.stages.data.items.length > 0);

                  console.log(`STAGE_TRACE: Evaluation update preserve=${shouldPreserveExistingTask} preserveStages=${shouldPreserveExistingTaskStages} for ${transformedEvaluation.id}`);

                  // Preserve existing score results and scorecard/score names when updating evaluation
                  const updatedEval = {
                    ...transformedEvaluation,
                    scoreResults: e.scoreResults || transformedEvaluation.scoreResults,
                    scorecard: transformedEvaluation.scorecard || e.scorecard,
                    score: transformedEvaluation.score || e.score,
                    // Preserve task data if needed
                    task: shouldPreserveExistingTask ? e.task :
                          shouldPreserveExistingTaskStages ? {
                            ...transformedEvaluation.task,
                            stages: e.task.stages
                          } : transformedEvaluation.task
                  };

                  if (updatedEval.task?.stages?.data?.items?.length > 0) {
                    console.log(`STAGE_TRACE: Evaluation update preserved ${updatedEval.id} with ${updatedEval.task.stages.data.items.length} stages: ${updatedEval.task.stages.data.items.map(s => `${s.name}:${s.status}`).join(',')}`);
                  } else {
                    console.log(`STAGE_TRACE: Evaluation update ${updatedEval.id} has no stages after preservation`);
                  }

                  return updatedEval;
                }
                return e;
              });

              // If this evaluation is now running and is the most recent, set up subscription
              if (isNowRunning && isMostRecent(updatedEvaluations)) {
                const scoreResults = getValueFromLazyLoader(transformedEvaluation.scoreResults);

                // Clean up existing subscription if any
                if (activeSubscriptionRef.current) {
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

              const finalEval = updatedEvaluations.find(e => e.id === transformedEvaluation.id);
              if (finalEval?.task?.stages?.data?.items?.length > 0) {
                console.log(`STAGE_TRACE: setEvaluations final eval ${transformedEvaluation.id} has ${finalEval.task.stages.data.items.length} stages`);
              } else {
                console.log(`STAGE_TRACE: setEvaluations final eval ${transformedEvaluation.id} has no stages`);
              }

              return updatedEvaluations;
            });
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
          const stage = data.onUpdateTaskStage;
          console.log(`STAGE_TRACE: Stage subscription received ${stage.name}:${stage.status} for task ${stage.taskId} at ${new Date().toLocaleTimeString()}`);
        } else {
          console.log(`STAGE_TRACE: Stage subscription received no data at ${new Date().toLocaleTimeString()}`);
        }
        
        if (data?.onUpdateTaskStage) {
          handleStageUpdate(data.onUpdateTaskStage);
        } else {
          console.warn('Stage subscription received but no onUpdateTaskStage data:', data);
        }
      },
      error: (error: Error) => {
console.error('STAGE_TRACE: Error in task stage update subscription:', error.message);
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

        // Transform items and filter out nulls
        const transformedItems = items
          .map((item, index) => {
            console.log(`🔍 TRACE_STAGES: Processing item ${index} (${item.id}):`, {
              hasTaskId: !!item.taskId,
              taskId: item.taskId,
              hasTaskInMap: !!taskMapRef.current.get(item.taskId || ''),
              itemTaskBefore: item.task,
              mapSize: taskMapRef.current.size,
              availableTaskIds: Array.from(taskMapRef.current.keys()),
              requestedTaskId: item.taskId
            });
            
            // Check if we have task data in our map
            if (item.taskId) {
              const taskData = taskMapRef.current.get(item.taskId);
              if (taskData) {
                // Get stages from stageMap
                const taskStages = stageMapRef.current.get(item.taskId);
                const stageItems = taskStages ? Array.from(taskStages.values()) : [];
                
                console.log(`🔍 TRACE_STAGES: Found task data for item ${index}:`, {
                  taskId: item.taskId,
                  stageCount: stageItems.length,
                  taskDataId: taskData.id
                });
                
                // Add stages to task data
                taskData.stages = {
                  data: {
                    items: stageItems
                  }
                };
                
                // Update the item with our task data
                item.task = taskData;
              } else {
                console.log(`🔍 TRACE_STAGES: No task data found for item ${index}:`, {
                  taskId: item.taskId,
                  availableTaskIds: Array.from(taskMapRef.current.keys())
                });
              }
            } else {
              console.log(`🔍 TRACE_STAGES: Item ${index} has no taskId`);
              
              // Check if we can find task data using the evaluation ID as the task ID
              // This might happen if the evaluation's taskId is null but the task exists
              const taskDataByEvalId = taskMapRef.current.get(item.id);
              if (taskDataByEvalId) {
                console.log(`🔍 TRACE_STAGES: Found task data using evaluation ID for item ${index}:`, {
                  evaluationId: item.id,
                  taskDataId: taskDataByEvalId.id,
                  stageMapHasEvalId: !!stageMapRef.current.get(item.id),
                  stageMapHasTaskId: !!stageMapRef.current.get(taskDataByEvalId.id)
                });
                
                // Get stages from stageMap - check both the evaluation ID and the actual task ID
                let taskStages = stageMapRef.current.get(item.id);
                if (!taskStages) {
                  taskStages = stageMapRef.current.get(taskDataByEvalId.id);
                }
                const stageItems = taskStages ? Array.from(taskStages.values()) : [];
                
                console.log(`🔍 TRACE_STAGES: Using fallback task data for item ${index}:`, {
                  evaluationId: item.id,
                  taskId: taskDataByEvalId.id,
                  stageCount: stageItems.length
                });
                
                // Add stages to task data
                taskDataByEvalId.stages = {
                  data: {
                    items: stageItems
                  }
                };
                
                // Update the item with the fallback task data
                item.task = taskDataByEvalId;
                
                // Also update the item's taskId to maintain consistency
                item.taskId = taskDataByEvalId.id;
              }
            }
            
            const transformed = transformEvaluation(item);
            
            console.log(`🔍 TRACE_STAGES: After transformEvaluation for item ${index}:`, {
              hasTask: !!transformed?.task,
              taskId: transformed?.task?.id,
              taskStageCount: transformed?.task?.stages?.data?.items?.length || 0
            });
            
            return transformed;
          })
          .filter((item): item is ProcessedEvaluation => item !== null);

        console.log('🔍 TRACE_STAGES: About to setEvaluations with transformedItems:', {
          itemCount: transformedItems.length,
          firstItemId: transformedItems[0]?.id,
          firstItemTask: transformedItems[0]?.task,
          firstItemTaskId: transformedItems[0]?.task?.id,
          firstItemTaskStages: transformedItems[0]?.task?.stages?.data?.items?.length || 0
        });
        
          // CRITICAL FIX: Merge with existing evaluations to preserve stage data and names (refetch version)
        setEvaluations(prevEvaluations => {
          const merged = transformedItems.map(newEval => {
            const existingEval = prevEvaluations.find(e => e.id === newEval.id);
            
            // If we have an existing evaluation with good stage data, preserve it
            if (existingEval && existingEval.task?.stages?.data?.items?.length > 0) {
              // Keep the existing stage data, but update other fields
              const preservedStageData = existingEval.task.stages;
              console.log(`🔍 TRACE_STAGES: Preserving existing stage data (refetch) for ${newEval.id}: ${preservedStageData.data.items.map(s => `${s.name}:${s.status}`).join(',')}`);
              
              return {
                ...newEval,
                  scorecard: newEval.scorecard || existingEval.scorecard,
                  score: newEval.score || existingEval.score,
                task: newEval.task ? {
                  ...newEval.task,
                  stages: preservedStageData
                } : newEval.task
              };
            }
            
              return {
                ...newEval,
                scorecard: newEval.scorecard || existingEval?.scorecard || newEval.scorecard,
                score: newEval.score || existingEval?.score || newEval.score
              };
          });
          
          return merged;
        });
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
              
          // CRITICAL FIX: Merge with existing evaluations to preserve stage data and names (refetch fallback version)
            setEvaluations(prevEvaluations => {
              const merged = transformedItems.map(newEval => {
                const existingEval = prevEvaluations.find(e => e.id === newEval.id);
                
                // If we have an existing evaluation with good stage data, preserve it
                if (existingEval && existingEval.task?.stages?.data?.items?.length > 0) {
                  // Keep the existing stage data, but update other fields
                  const preservedStageData = existingEval.task.stages;
                  console.log(`🔍 TRACE_STAGES: Preserving existing stage data (refetch fallback) for ${newEval.id}: ${preservedStageData.data.items.map(s => `${s.name}:${s.status}`).join(',')}`);
                  
                  return {
                    ...newEval,
                  scorecard: newEval.scorecard || existingEval.scorecard,
                  score: newEval.score || existingEval.score,
                    task: newEval.task ? {
                      ...newEval.task,
                      stages: preservedStageData
                    } : newEval.task
                  };
                }
                
              return {
                ...newEval,
                scorecard: newEval.scorecard || existingEval?.scorecard || newEval.scorecard,
                score: newEval.score || existingEval?.score || newEval.score
              };
              });
              
              return merged;
            });
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