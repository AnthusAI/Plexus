import { generateClient } from 'aws-amplify/data';
import { Schema } from '@/amplify/data/resource';
import { Observable } from 'rxjs';

// Define the shape of the task data we expect from Amplify
export type AmplifyTask = Schema['Task']['type'];

export type ProcessedTask = {
  id: string;
  command: string;
  type: string;
  status: string;
  target: string;
  description?: string;
  metadata?: string;
  createdAt?: string;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  errorMessage?: string;
  errorDetails?: string;
  stdout?: string;
  stderr?: string;
  currentStageId?: string;
  stages: ProcessedTaskStage[];
  dispatchStatus?: 'DISPATCHED' | string;  // Allow both literal and string
  celeryTaskId?: string;
  workerNodeId?: string;
  updatedAt?: string;  // Add updatedAt field
  scorecardId?: string;
  scoreId?: string;
  scorecard?: {
    id: string;
    name: string;
  };
  score?: {
    id: string;
    name: string;
  };
  evaluation?: {
    id: string;
    type: string;
    metrics: any;
    metricsExplanation?: string | null;
    inferences: number;
    accuracy: number | null;
    cost: number | null;
    status: string;
    startedAt?: string;
    elapsedSeconds: number | null;
    estimatedRemainingSeconds: number | null;
    totalItems: number;
    processedItems: number;
    errorMessage?: string;
    errorDetails?: any;
    confusionMatrix?: any;
    scoreGoal?: string;
    datasetClassDistribution?: any;
    isDatasetClassDistributionBalanced?: boolean;
    predictedClassDistribution?: any;
    isPredictedClassDistributionBalanced?: boolean;
    scoreResults?: {
      items?: Array<{
        id: string;
        value: string | number;
        confidence: number | null;
        metadata: any;
        explanation: string | null;
        itemId: string | null;
        createdAt: string;
      }>;
    };
  };
};

export type ProcessedTaskStage = {
  id: string;
  name: string;
  order: number;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  processedItems?: number;
  totalItems?: number;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  statusMessage?: string;
};

type AmplifyClient = ReturnType<typeof generateClient<Schema>> & {
  models: {
    Task: {
      list: (options: { 
        limit?: number; 
        include?: string[];
      }) => Promise<{
        data: Array<Schema['Task']['type']>;
        nextToken?: string | null;
      }>;
      onCreate: (options: {}) => { subscribe: (handlers: { next: () => void; error: (error: any) => void }) => { unsubscribe: () => void } };
      onUpdate: (options: {}) => { subscribe: (handlers: { next: () => void; error: (error: any) => void }) => { unsubscribe: () => void } };
    };
    TaskStage: {
      onUpdate: (options: {}) => { subscribe: (handlers: { next: () => void; error: (error: any) => void }) => { unsubscribe: () => void } };
    };
    Evaluation: {
      list: (options: any) => Promise<AmplifyListResult<Schema['Evaluation']['type']>>;
      listEvaluationByAccountIdAndUpdatedAt: (options: {
        accountId: string;
        sortDirection?: 'ASC' | 'DESC';
        limit?: number;
        nextToken?: string;
      }) => Promise<AmplifyListResult<Schema['Evaluation']['type']>>;
    };
  };
}

export type AmplifyListResult<T> = {
  data: T[];
  nextToken?: string | null;
}

let client: AmplifyClient;

// Add back the type definitions at the top
interface GraphQLError {
  message: string;
  path?: string[];
}

interface GraphQLResult<T> {
  data?: T;
  errors?: GraphQLError[];
}

type ListTaskResponse = {
  listTaskByAccountIdAndUpdatedAt: {
    items: Schema['Task']['type'][];
    nextToken: string | null;
  };
};

export function getClient(): AmplifyClient {
  if (!client) {
    client = generateClient<Schema>() as AmplifyClient;
  }
  return client;
}

export async function listFromModel<T extends { id: string }>(
  modelName: keyof AmplifyClient['models'],
  options?: {
    limit?: number,
    filter?: Record<string, any>,
    nextToken?: string,
    sortDirection?: 'ASC' | 'DESC'
  }
): Promise<AmplifyListResult<T>> {
  console.warn('listFromModel called:', {
    modelName,
    options
  });
  const currentClient = getClient();
  
  try {
    // Collect all results across pages
    let allData: T[] = []
    let currentNextToken = options?.nextToken

    do {
      console.debug('Making list request:', {
        modelName,
        limit: options?.limit,
        filter: options?.filter,
        nextToken: currentNextToken,
        include: modelName === 'Task' ? ['stages', 'scorecard', 'score'] : undefined
      });

      const response = await (currentClient.models[modelName] as any).list({
        limit: options?.limit,
        filter: options?.filter,
        nextToken: currentNextToken,
        sortDirection: options?.sortDirection,
        // Include stages when listing tasks
        include: modelName === 'Task' ? ['stages', 'scorecard', 'score'] : undefined
      });

      console.debug('List response:', {
        modelName,
        dataLength: response.data?.length,
        firstItem: response.data?.[0] ? {
          id: response.data[0].id,
          scorecard: response.data[0].scorecard,
          score: response.data[0].score
        } : null
      });

      if (response.data?.length) {
        allData = [...allData, ...response.data]
      }

      currentNextToken = response.nextToken
    } while (currentNextToken && (!options?.limit || allData.length < options.limit))

    // If we have a limit, respect it exactly
    if (options?.limit && allData.length > options.limit) {
      allData = allData.slice(0, options.limit)
    }

    // Sort by updatedAt if available, otherwise by createdAt
    if (allData.length > 0) {
      if ('updatedAt' in allData[0]) {
        allData.sort((a: any, b: any) =>
          new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        )
      } else if ('createdAt' in allData[0]) {
        allData.sort((a: any, b: any) =>
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        )
      }
    }

    console.debug('listFromModel result:', {
      modelName,
      dataLength: allData.length,
      firstItem: allData[0] ? {
        id: allData[0].id,
        scorecard: (allData[0] as any).scorecard,
        score: (allData[0] as any).score
      } : null
    });

    return {
      data: allData,
      nextToken: currentNextToken
    };
  } catch (error) {
    console.error(`Error listing ${modelName}:`, error);
    return { data: [], nextToken: null };
  }
}

export function transformAmplifyTask(task: AmplifyTask): ProcessedTask {
  console.debug('transformAmplifyTask input:', {
    taskId: task.id,
    hasStages: !!task.stages,
    stagesType: task.stages ? typeof task.stages : 'undefined',
    rawStages: task.stages,
    hasEvaluation: !!task.evaluation,
    evaluationData: task.evaluation
  });

  // Handle stages - if it's a LazyLoader, we'll return an empty array
  // The stages will be loaded later by the processTask function
  const stages: ProcessedTaskStage[] = task.stages?.items ? 
    task.stages.items.map((stage: any) => ({
      id: stage.id,
      name: stage.name,
      order: stage.order,
      status: (stage.status ?? 'PENDING') as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
      processedItems: stage.processedItems ?? undefined,
      totalItems: stage.totalItems ?? undefined,
      startedAt: stage.startedAt ?? undefined,
      completedAt: stage.completedAt ?? undefined,
      estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
      statusMessage: stage.statusMessage ?? undefined
    }))
    : [];

  console.debug('Transformed stages:', {
    taskId: task.id,
    stagesCount: stages.length,
    stages
  });

  // Transform evaluation data if present
  let evaluation = undefined;
  if (task.evaluation) {
    try {
      // Parse metrics if it's a string
      let metrics = task.evaluation.metrics;
      try {
        if (typeof metrics === 'string') {
          metrics = JSON.parse(metrics);
        }
      } catch (e) {
        console.error('Error parsing metrics:', e);
      }

      // Parse confusion matrix if it's a string
      let confusionMatrix = task.evaluation.confusionMatrix;
      try {
        if (typeof confusionMatrix === 'string') {
          confusionMatrix = JSON.parse(confusionMatrix);
        }
      } catch (e) {
        console.error('Error parsing confusion matrix:', e);
      }

      // Parse dataset class distribution if it's a string
      let datasetClassDistribution = task.evaluation.datasetClassDistribution;
      try {
        if (typeof datasetClassDistribution === 'string') {
          datasetClassDistribution = JSON.parse(datasetClassDistribution);
        }
      } catch (e) {
        console.error('Error parsing dataset class distribution:', e);
      }

      // Parse predicted class distribution if it's a string
      let predictedClassDistribution = task.evaluation.predictedClassDistribution;
      try {
        if (typeof predictedClassDistribution === 'string') {
          predictedClassDistribution = JSON.parse(predictedClassDistribution);
        }
      } catch (e) {
        console.error('Error parsing predicted class distribution:', e);
      }

      evaluation = {
        id: task.evaluation.id,
        type: task.evaluation.type,
        metrics,
        metricsExplanation: task.evaluation.metricsExplanation,
        inferences: Number(task.evaluation.inferences) || 0,
        accuracy: typeof task.evaluation.accuracy === 'number' ? task.evaluation.accuracy : null,
        cost: task.evaluation.cost ?? null,
        status: task.evaluation.status,
        startedAt: task.evaluation.startedAt,
        elapsedSeconds: task.evaluation.elapsedSeconds ?? null,
        estimatedRemainingSeconds: task.evaluation.estimatedRemainingSeconds ?? null,
        totalItems: Number(task.evaluation.totalItems) || 0,
        processedItems: Number(task.evaluation.processedItems) || 0,
        errorMessage: task.evaluation.errorMessage,
        errorDetails: task.evaluation.errorDetails,
        confusionMatrix,
        scoreGoal: task.evaluation.scoreGoal,
        datasetClassDistribution,
        isDatasetClassDistributionBalanced: task.evaluation.isDatasetClassDistributionBalanced,
        predictedClassDistribution,
        isPredictedClassDistributionBalanced: task.evaluation.isPredictedClassDistributionBalanced,
        scoreResults: task.evaluation.scoreResults
      };
    } catch (error) {
      console.error('Error transforming evaluation data:', error);
    }
  }

  return {
    id: task.id,
    command: task.command,
    type: task.type,
    status: task.status,
    target: task.target,
    description: task.description ?? undefined,
    metadata: typeof task.metadata === 'string' ? task.metadata : JSON.stringify(task.metadata ?? null),
    createdAt: task.createdAt ?? undefined,
    startedAt: task.startedAt ?? undefined,
    completedAt: task.completedAt ?? undefined,
    estimatedCompletionAt: task.estimatedCompletionAt ?? undefined,
    errorMessage: task.errorMessage ?? undefined,
    errorDetails: typeof task.errorDetails === 'string' ? task.errorDetails : JSON.stringify(task.errorDetails ?? null),
    stdout: task.stdout ?? undefined,
    stderr: task.stderr ?? undefined,
    currentStageId: task.currentStageId ?? undefined,
    stages,
    dispatchStatus: task.dispatchStatus ?? undefined,
    celeryTaskId: task.celeryTaskId ?? undefined,
    workerNodeId: task.workerNodeId ?? undefined,
    updatedAt: task.updatedAt ?? undefined,
    scorecardId: task.scorecardId ?? undefined,
    scoreId: task.scoreId ?? undefined,
    scorecard: task.scorecard ? {
      id: task.scorecard.id,
      name: task.scorecard.name
    } : undefined,
    score: task.score ? {
      id: task.score.id,
      name: task.score.name
    } : undefined,
    evaluation
  }
}

// Add this type at the top with other types
type ErrorHandler = (error: Error) => void;

export function observeRecentTasks(limit: number = 12): Observable<{ items: ProcessedTask[], isSynced: boolean }> {
  console.warn('observeRecentTasks called with limit:', limit);
  return new Observable(subscriber => {
    let isSynced = false;
    let currentTasks: ProcessedTask[] = [];
    const client = getClient();

    // Initial load
    async function loadInitialTasks() {
      try {
        const tasks = await listRecentTasks(limit);
        currentTasks = tasks;
        subscriber.next({ items: currentTasks, isSynced: true });
        isSynced = true;
      } catch (error) {
        console.error('Error in initial task load:', error);
        subscriber.next({ items: [], isSynced: false });
      }
    }

    // Handle task updates in-memory
    async function handleTaskUpdate(updatedTask: AmplifyTask) {
      try {
        console.debug('Processing task update/create - Raw Input:', {
          taskId: updatedTask.id,
          type: updatedTask.type,
          status: updatedTask.status,
          hasStages: !!updatedTask.stages,
          scorecardId: updatedTask.scorecardId,
          scoreId: updatedTask.scoreId,
          rawScorecard: updatedTask.scorecard,
          rawScore: updatedTask.score
        });

        // If we have IDs but no data, fetch the related data
        if (updatedTask.scorecardId && !updatedTask.scorecard) {
          console.debug('Fetching scorecard data for ID:', updatedTask.scorecardId);
          const scorecardResponse = await client.graphql({
            query: `
              query GetScorecard($id: ID!) {
                getScorecard(id: $id) {
                  id
                  name
                  key
                }
              }
            `,
            variables: {
              id: updatedTask.scorecardId
            }
          });
          updatedTask.scorecard = scorecardResponse.data?.getScorecard;
          console.debug('Fetched scorecard:', updatedTask.scorecard);
        }

        if (updatedTask.scoreId && !updatedTask.score) {
          console.debug('Fetching score data for ID:', updatedTask.scoreId);
          const scoreResponse = await client.graphql({
            query: `
              query GetScore($id: ID!) {
                getScore(id: $id) {
                  id
                  name
                  key
                }
              }
            `,
            variables: {
              id: updatedTask.scoreId
            }
          });
          updatedTask.score = scoreResponse.data?.getScore;
          console.debug('Fetched score:', updatedTask.score);
        }

        const processedTask = await processTask(updatedTask);
        console.debug('Task after processing:', {
          taskId: processedTask.id,
          hasStages: processedTask.stages?.length,
          scorecardId: processedTask.scorecardId,
          scoreId: processedTask.scoreId,
          processedScorecard: processedTask.scorecard,
          processedScore: processedTask.score
        });

        const taskIndex = currentTasks.findIndex(t => t.id === processedTask.id);
        
        if (taskIndex !== -1) {
          const existingTask = currentTasks[taskIndex];
          console.debug('Existing task state:', {
            taskId: existingTask.id,
            existingScorecard: existingTask.scorecard,
            existingScore: existingTask.score,
            existingScorecardId: existingTask.scorecardId,
            existingScoreId: existingTask.scoreId
          });
          
          // Create the updated task, prioritizing new data
          const updatedTaskData = {
            ...existingTask,
            ...processedTask,
            stages: processedTask.stages?.length ? processedTask.stages : existingTask.stages,
          };

          // Handle scorecard updates with tracing
          if (updatedTask.scorecardId) {
            console.debug('Updating scorecard:', {
              taskId: updatedTask.id,
              newScorecardId: updatedTask.scorecardId,
              oldScorecardId: existingTask.scorecardId,
              newScorecard: updatedTask.scorecard,
              oldScorecard: existingTask.scorecard
            });
            updatedTaskData.scorecardId = updatedTask.scorecardId;
            if (updatedTask.scorecard) {
              updatedTaskData.scorecard = {
                id: updatedTask.scorecard.id,
                name: updatedTask.scorecard.name
              };
            }
          }

          // Handle score updates with tracing
          if (updatedTask.scoreId) {
            console.debug('Updating score:', {
              taskId: updatedTask.id,
              newScoreId: updatedTask.scoreId,
              oldScoreId: existingTask.scoreId,
              newScore: updatedTask.score,
              oldScore: existingTask.score
            });
            updatedTaskData.scoreId = updatedTask.scoreId;
            if (updatedTask.score) {
              updatedTaskData.score = {
                id: updatedTask.score.id,
                name: updatedTask.score.name
              };
            }
          }

          currentTasks[taskIndex] = updatedTaskData;

          console.debug('Final updated task state:', {
            taskId: currentTasks[taskIndex].id,
            scorecardId: currentTasks[taskIndex].scorecardId,
            scoreId: currentTasks[taskIndex].scoreId,
            finalScorecard: currentTasks[taskIndex].scorecard,
            finalScore: currentTasks[taskIndex].score
          });
        } else {
          // For new tasks, add to the beginning of the array
          currentTasks.unshift(processedTask);
          console.debug('Added new task:', {
            taskId: processedTask.id,
            totalTasks: currentTasks.length,
            scorecardId: processedTask.scorecardId,
            scoreId: processedTask.scoreId,
            scorecard: processedTask.scorecard,
            score: processedTask.score
          });
        }

        // Sort tasks
        currentTasks.sort((a, b) => {
          if ((a.status === 'COMPLETED' || a.status === 'FAILED') && 
              (b.status === 'COMPLETED' || b.status === 'FAILED')) {
            return new Date(b.updatedAt || b.createdAt || '').getTime() - 
                   new Date(a.updatedAt || a.createdAt || '').getTime();
          }
          return new Date(b.createdAt || '').getTime() - new Date(a.createdAt || '').getTime();
        });

        // Trim to limit if needed
        if (currentTasks.length > limit) {
          currentTasks = currentTasks.slice(0, limit);
        }

        console.debug('Emitting updated task list:', {
          count: currentTasks.length,
          taskIds: currentTasks.map(t => ({
            id: t.id,
            scorecardId: t.scorecardId,
            scoreId: t.scoreId,
            scorecard: t.scorecard?.name,
            score: t.score?.name
          }))
        });
        subscriber.next({ items: [...currentTasks], isSynced: true });
      } catch (error) {
        console.error('Error processing task update:', error);
      }
    }

    // Handle stage updates in-memory
    async function handleStageUpdate(updatedStage: any) {
      try {
        console.debug('Stage update received:', updatedStage);
        
        // Extract taskId from the stage data - handle both possible structures
        const taskId = updatedStage?.taskId || updatedStage?.data?.taskId;
        if (!taskId) {
          console.warn('No taskId found in stage update:', updatedStage);
          return;
        }

        const taskIndex = currentTasks.findIndex(t => t.id === taskId);
        if (taskIndex === -1) {
          console.debug(`Task ${taskId} not found in current tasks`);
          return;
        }

        const task = currentTasks[taskIndex];
        if (!task.stages) {
          console.debug(`Task ${taskId} has no stages array`);
          return;
        }

        // Get the actual stage data, handling both possible structures
        const stageData = updatedStage?.data || updatedStage;
        const stageIndex = task.stages.findIndex(s => s.id === stageData.id);
        
        if (stageIndex === -1) {
          console.debug(`Stage ${stageData.id} not found in task ${taskId}`);
          return;
        }

        // Update the specific stage
        task.stages[stageIndex] = {
          ...task.stages[stageIndex],
          status: stageData.status ?? task.stages[stageIndex].status,
          processedItems: stageData.processedItems ?? task.stages[stageIndex].processedItems,
          totalItems: stageData.totalItems ?? task.stages[stageIndex].totalItems,
          startedAt: stageData.startedAt ?? task.stages[stageIndex].startedAt,
          completedAt: stageData.completedAt ?? task.stages[stageIndex].completedAt,
          estimatedCompletionAt: stageData.estimatedCompletionAt ?? task.stages[stageIndex].estimatedCompletionAt,
          statusMessage: stageData.statusMessage ?? task.stages[stageIndex].statusMessage
        };
        
        // Update task status if needed
        if (stageData.status === 'FAILED') {
          task.status = 'FAILED';
        } else if (stageData.status === 'COMPLETED' && 
                  task.stages.every(s => s.status === 'COMPLETED')) {
          task.status = 'COMPLETED';
        }
        
        subscriber.next({ items: [...currentTasks], isSynced: true });
      } catch (error) {
        console.error('Error processing stage update:', error);
      }
    }

    // Load initial data
    loadInitialTasks();

    // Set up subscriptions
    const taskSubscriptions = [
      client.graphql({
        query: `subscription OnCreateTask {
          onCreateTask {
            id
            accountId
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
            stdout
            stderr
            currentStageId
            scorecardId
            scoreId
            celeryTaskId
            workerNodeId
            updatedAt
            scorecard {
              id
              name
              key
            }
            score {
              id
              name
              key
            }
            stages {
              items {
                id
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
            evaluation {
              id
              type
              metrics
              metricsExplanation
              inferences
              accuracy
              cost
              status
              startedAt
              elapsedSeconds
              estimatedRemainingSeconds
              totalItems
              processedItems
              errorMessage
              errorDetails
              confusionMatrix
              scoreGoal
              datasetClassDistribution
              isDatasetClassDistributionBalanced
              predictedClassDistribution
              isPredictedClassDistributionBalanced
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
        }`
      }).subscribe({
        next: (data: any) => {
          console.debug('Raw onCreate data received:', data);
          const taskData = data?.data?.onCreateTask;
          if (!taskData?.id) {
            console.debug('Invalid task create data:', data);
            return;
          }
          console.log('Task onCreate triggered:', { 
            taskId: taskData.id,
            type: taskData.type,
            status: taskData.status,
            scorecard: taskData.scorecard?.name,
            score: taskData.score?.name
          });
          handleTaskUpdate(taskData);
        },
        error: (error: Error) => console.error('Error in task onCreate subscription:', error)
      }),
      
      client.graphql({
        query: `subscription OnUpdateTask {
          onUpdateTask {
            id
            accountId
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
            stdout
            stderr
            currentStageId
            scorecardId
            scoreId
            celeryTaskId
            workerNodeId
            updatedAt
            scorecard {
              id
              name
              key
            }
            score {
              id
              name
              key
            }
            stages {
              items {
                id
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
            evaluation {
              id
              type
              metrics
              metricsExplanation
              inferences
              accuracy
              cost
              status
              startedAt
              elapsedSeconds
              estimatedRemainingSeconds
              totalItems
              processedItems
              errorMessage
              errorDetails
              confusionMatrix
              scoreGoal
              datasetClassDistribution
              isDatasetClassDistributionBalanced
              predictedClassDistribution
              isPredictedClassDistributionBalanced
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
        }`
      }).subscribe({
        next: (data: any) => {
          console.debug('Raw onUpdate data received:', {
            fullData: data,
            taskData: data?.data?.onUpdateTask,
            scorecardData: {
              id: data?.data?.onUpdateTask?.scorecardId,
              scorecard: data?.data?.onUpdateTask?.scorecard
            },
            scoreData: {
              id: data?.data?.onUpdateTask?.scoreId,
              score: data?.data?.onUpdateTask?.score
            }
          });
          
          const taskData = data?.data?.onUpdateTask;
          if (!taskData?.id) {
            console.debug('Invalid task update data:', data);
            return;
          }

          handleTaskUpdate(taskData);
        },
        error: (error: Error) => console.error('Error in task onUpdate subscription:', error)
      })
    ];

    // Subscribe to stage updates
    const stageSubscription = (client.models.TaskStage as any).onUpdate({}).subscribe({
      next: (data: any) => {
        console.debug('Raw stage update data received:', data);
        // Handle both direct data and wrapped data cases
        const stageData = data?.data?.onUpdateTaskStage || data;
        if (!stageData?.id) {
          console.debug('Invalid stage update data:', data);
          return;
        }

        console.log('Stage onUpdate triggered:', { 
          stageId: stageData.id,
          taskId: stageData.taskId,
          status: stageData.status,
          processedItems: stageData.processedItems,
          totalItems: stageData.totalItems
        });
        handleStageUpdate(stageData);
      },
      error: (error: Error) => console.error('Error in stage onUpdate subscription:', error)
    });

    // Cleanup function
    return () => {
      console.log('Cleaning up task subscriptions');
      taskSubscriptions.forEach(sub => sub.unsubscribe());
      stageSubscription.unsubscribe();
    };
  });
}

type TaskStageData = Schema['TaskStage']['type'];

async function processTask(task: AmplifyTask): Promise<ProcessedTask> {
  console.debug(`Starting to process task ${task.id}`, {
    taskId: task.id,
    type: task.type,
    hasStages: !!task.stages,
    stagesType: task.stages ? typeof task.stages : 'undefined',
    rawStages: task.stages,
    hasEvaluation: !!task.evaluation,
    evaluationData: task.evaluation
  });

  try {
    if (!task.stages) {
      // If stages is missing, try to load them
      const stagesResponse = await listFromModel<Schema['TaskStage']['type']>(
        'TaskStage',
        { filter: { taskId: { eq: task.id } } }
      );
      task.stages = { items: stagesResponse.data || [] };
    }

    // Sort stages by order
    const stages: ProcessedTaskStage[] = (task.stages?.items || [])
      .sort((a: any, b: any) => a.order - b.order)
      .map((stage: any) => ({
        id: stage.id,
        name: stage.name,
        order: stage.order,
        status: (stage.status ?? 'PENDING') as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
        processedItems: stage.processedItems ?? undefined,
        totalItems: stage.totalItems ?? undefined,
        startedAt: stage.startedAt ?? undefined,
        completedAt: stage.completedAt ?? undefined,
        estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
        statusMessage: stage.statusMessage ?? undefined
      }));

    const processed: ProcessedTask = {
      id: task.id,
      command: task.command,
      type: task.type,
      status: task.status,
      target: task.target,
      description: task.description ?? undefined,
      metadata: typeof task.metadata === 'string' ? task.metadata : JSON.stringify(task.metadata ?? null),
      createdAt: task.createdAt ?? undefined,
      startedAt: task.startedAt ?? undefined,
      completedAt: task.completedAt ?? undefined,
      estimatedCompletionAt: task.estimatedCompletionAt ?? undefined,
      errorMessage: task.errorMessage ?? undefined,
      errorDetails: typeof task.errorDetails === 'string' ? task.errorDetails : JSON.stringify(task.errorDetails ?? null),
      stdout: task.stdout ?? undefined,
      stderr: task.stderr ?? undefined,
      currentStageId: task.currentStageId ?? undefined,
      stages,
      dispatchStatus: task.dispatchStatus ?? undefined,
      celeryTaskId: task.celeryTaskId ?? undefined,
      workerNodeId: task.workerNodeId ?? undefined,
      updatedAt: task.updatedAt ?? undefined,
      scorecardId: task.scorecardId ?? undefined,
      scoreId: task.scoreId ?? undefined,
      scorecard: task.scorecard ? {
        id: task.scorecard.id,
        name: task.scorecard.name
      } : undefined,
      score: task.score ? {
        id: task.score.id,
        name: task.score.name
      } : undefined,
      evaluation: task.evaluation ? {
        id: task.evaluation.id,
        type: task.evaluation.type,
        metrics: task.evaluation.metrics,
        metricsExplanation: task.evaluation.metricsExplanation,
        inferences: task.evaluation.inferences,
        accuracy: task.evaluation.accuracy,
        cost: task.evaluation.cost,
        status: task.evaluation.status,
        startedAt: task.evaluation.startedAt,
        elapsedSeconds: task.evaluation.elapsedSeconds,
        estimatedRemainingSeconds: task.evaluation.estimatedRemainingSeconds,
        totalItems: task.evaluation.totalItems,
        processedItems: task.evaluation.processedItems,
        errorMessage: task.evaluation.errorMessage,
        errorDetails: task.evaluation.errorDetails,
        confusionMatrix: task.evaluation.confusionMatrix,
        scoreGoal: task.evaluation.scoreGoal,
        datasetClassDistribution: task.evaluation.datasetClassDistribution,
        isDatasetClassDistributionBalanced: task.evaluation.isDatasetClassDistributionBalanced,
        predictedClassDistribution: task.evaluation.predictedClassDistribution,
        isPredictedClassDistributionBalanced: task.evaluation.isPredictedClassDistributionBalanced,
        scoreResults: task.evaluation.scoreResults
      } : undefined
    };

    console.debug(`Finished processing task ${task.id}`, {
      id: processed.id,
      type: processed.type,
      scorecard: processed.scorecard,
      score: processed.score,
      scorecardId: processed.scorecardId,
      scoreId: processed.scoreId,
      hasEvaluation: !!processed.evaluation,
      evaluationData: processed.evaluation
    });

    return processed;
  } catch (error: unknown) {
    console.error('Error processing task:', error);
    throw error;
  }
}

export async function listRecentTasks(limit: number = 10): Promise<ProcessedTask[]> {
  console.warn('listRecentTasks called with limit:', limit);
  try {
    const currentClient = getClient();
    if (!currentClient.models.Task) {
      throw new Error('Task model not found');
    }

    // Get the account ID by key
    const ACCOUNT_KEY = 'call-criteria';
    const accountResponse = await listFromModel<Schema['Account']['type']>(
      'Account',
      { filter: { key: { eq: ACCOUNT_KEY } } }
    );

    if (!accountResponse.data?.length) {
      console.error('No account found with key:', ACCOUNT_KEY);
      return [];
    }

    const accountId = accountResponse.data[0].id;
    console.debug('Fetching tasks for account:', accountId);

    const response = await currentClient.graphql({
      query: `
        query ListTaskByAccountIdAndUpdatedAt(
          $accountId: String!
          $sortDirection: ModelSortDirection!
          $limit: Int
        ) {
          listTaskByAccountIdAndUpdatedAt(
            accountId: $accountId
            sortDirection: $sortDirection
            limit: $limit
          ) {
            items {
              id
              accountId
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
              stdout
              stderr
              currentStageId
              scorecardId
              scoreId
              celeryTaskId
              workerNodeId
              updatedAt
              scorecard {
                id
                name
              }
              score {
                id
                name
              }
              stages {
                items {
                  id
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
              evaluation {
                id
                type
                metrics
                metricsExplanation
                inferences
                accuracy
                cost
                status
                startedAt
                elapsedSeconds
                estimatedRemainingSeconds
                totalItems
                processedItems
                errorMessage
                errorDetails
                confusionMatrix
                scoreGoal
                datasetClassDistribution
                isDatasetClassDistributionBalanced
                predictedClassDistribution
                isPredictedClassDistributionBalanced
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
            nextToken
          }
        }
      `,
      variables: {
        accountId: accountId.trim(),
        sortDirection: 'DESC',
        limit: limit || 100
      },
      authMode: 'userPool'
    }) as unknown as GraphQLResult<ListTaskResponse>;

    if (response.errors?.length) {
      console.error('GraphQL errors:', response.errors);
      throw new Error(`GraphQL errors: ${response.errors.map(e => e.message).join(', ')}`);
    }

    if (!response.data) {
      console.error('No data returned from GraphQL query');
      return [];
    }

    console.debug('Raw GraphQL response - Task with evaluation:', {
      taskCount: response.data?.listTaskByAccountIdAndUpdatedAt?.items?.length,
      firstTask: response.data?.listTaskByAccountIdAndUpdatedAt?.items?.[0] ? {
        id: response.data.listTaskByAccountIdAndUpdatedAt.items[0].id,
        type: response.data.listTaskByAccountIdAndUpdatedAt.items[0].type,
        hasEvaluation: !!response.data.listTaskByAccountIdAndUpdatedAt.items[0].evaluation,
        evaluation: response.data.listTaskByAccountIdAndUpdatedAt.items[0].evaluation ? {
          id: response.data.listTaskByAccountIdAndUpdatedAt.items[0].evaluation.id,
          type: response.data.listTaskByAccountIdAndUpdatedAt.items[0].evaluation.type,
          metrics: response.data.listTaskByAccountIdAndUpdatedAt.items[0].evaluation.metrics,
          accuracy: response.data.listTaskByAccountIdAndUpdatedAt.items[0].evaluation.accuracy,
          processedItems: response.data.listTaskByAccountIdAndUpdatedAt.items[0].evaluation.processedItems,
          totalItems: response.data.listTaskByAccountIdAndUpdatedAt.items[0].evaluation.totalItems,
          scoreResults: response.data.listTaskByAccountIdAndUpdatedAt.items[0].evaluation.scoreResults
        } : null
      } : null
    });

    const result = response.data;
    if (!result?.listTaskByAccountIdAndUpdatedAt?.items) {
      console.error('No items found in GraphQL response');
      return [];
    }

    // Process tasks and load their stages
    const processedTasks = await Promise.all(
      result.listTaskByAccountIdAndUpdatedAt.items.map(async (task) => {
        console.debug(`Processing task ${task.id}, raw data:`, {
          id: task.id,
          type: task.type,
          scorecard: task.scorecard,
          score: task.score,
          scorecardId: task.scorecardId,
          scoreId: task.scoreId,
          hasEvaluation: !!task.evaluation,
          evaluationData: task.evaluation
        });
        return processTask(task);
      })
    );

    console.debug('All processed tasks:', processedTasks.map(task => ({
      id: task.id,
      type: task.type,
      scorecard: task.scorecard,
      score: task.score,
      scorecardId: task.scorecardId,
      scoreId: task.scoreId,
      hasEvaluation: !!task.evaluation,
      evaluationData: task.evaluation
    })));
    return processedTasks;
  } catch (error) {
    console.error('Error listing recent tasks:', error);
    return [];
  }
}

export async function getFromModel<T extends { id: string }>(
  modelName: keyof AmplifyClient['models'],
  id: string
): Promise<{ data: T | null }> {
  try {
    const response = await (client.models[modelName] as any).get({ id });
    return response;
  } catch (error) {
    console.error(`Error getting ${modelName}:`, error);
    return { data: null };
  }
}

export async function createTask(
  command: string,
  type: string = 'command',
  target: string = '',
  metadata: any = {}
): Promise<ProcessedTask | null> {
  try {
    const currentClient = getClient();
    if (!currentClient.models.Task) {
      throw new Error('Task model not found');
    }

    // Get the account ID by key
    const ACCOUNT_KEY = 'call-criteria';
    const accountResponse = await listFromModel<Schema['Account']['type']>(
      'Account',
      { filter: { key: { eq: ACCOUNT_KEY } } }
    );

    if (!accountResponse.data?.length) {
      console.error('No account found with key:', ACCOUNT_KEY);
      return null;
    }

    const accountId = accountResponse.data[0].id;

    type BasicTaskInput = {
      accountId: string;
      command: string;
      type: string;
      target: string;
      metadata: string;
      dispatchStatus: 'PENDING';
      status: 'PENDING';
      createdAt: string;
    };

    const taskInput = {
      accountId,
      command,
      type,
      target,
      metadata: JSON.stringify(metadata),
      dispatchStatus: 'PENDING' as const,
      status: 'PENDING' as const,
      createdAt: new Date().toISOString()
    } as BasicTaskInput;

    // @ts-expect-error Complex union type in generated Amplify types
    const response = await currentClient.models.Task.create(taskInput);

    if (response.data) {
      return processTask(response.data);
    }

    return null;
  } catch (error) {
    console.error('Error creating task:', error);
    return null;
  }
}

export async function updateTask(
  id: string,
  input: Partial<AmplifyTask> | Partial<Schema['TaskStage']['type']>,
  modelName: 'Task' | 'TaskStage' = 'Task'
): Promise<ProcessedTask | null> {
  try {
    const currentClient = getClient();
    if (!currentClient.models[modelName]) {
      throw new Error(`${modelName} model not found`);
    }

    // @ts-expect-error Complex union type in generated Amplify types
    const response = await currentClient.models[modelName].update({
      id,
      ...input
    });

    if (response.data) {
      return modelName === 'Task' ? processTask(response.data) : null;
    }

    return null;
  } catch (error) {
    console.error(`Error updating ${modelName}:`, error);
    return null;
  }
}

export async function listRecentEvaluations(limit: number = 100): Promise<Schema['Evaluation']['type'][]> {
  console.warn('listRecentEvaluations called with limit:', limit);
  try {
    const currentClient = getClient();

    // Get the account ID by key
    const ACCOUNT_KEY = 'call-criteria';
    const accountResponse = await listFromModel<Schema['Account']['type']>(
      'Account',
      { filter: { key: { eq: ACCOUNT_KEY } } }
    );

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
                }
                nextToken
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
    });

    if (response.errors?.length) {
      console.error('GraphQL errors:', response.errors);
      throw new Error(`GraphQL errors: ${response.errors.map(e => e.message).join(', ')}`);
    }

    if (!response.data) {
      console.error('No data returned from GraphQL query');
      return [];
    }

    console.debug('Raw GraphQL response:', {
      evaluationCount: response.data?.listEvaluationByAccountIdAndUpdatedAt?.items?.length,
      firstEvaluation: response.data?.listEvaluationByAccountIdAndUpdatedAt?.items?.[0] ? {
        id: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].id,
        taskId: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].taskId,
        taskStages: response.data.listEvaluationByAccountIdAndUpdatedAt.items[0].task?.stages?.items
      } : null
    });

    const result = response.data;
    if (!result?.listEvaluationByAccountIdAndUpdatedAt?.items) {
      console.error('No items found in GraphQL response');
      return [];
    }

    return result.listEvaluationByAccountIdAndUpdatedAt.items;
  } catch (error) {
    console.error('Error listing recent evaluations:', error);
    return [];
  }
}

export function observeRecentEvaluations(limit: number = 100): Observable<{ items: Schema['Evaluation']['type'][], isSynced: boolean }> {
  return new Observable(subscriber => {
    let isSynced = false;
    let evaluations: Schema['Evaluation']['type'][] = [];
    
    async function loadInitialEvaluations() {
      try {
        const response = await listRecentEvaluations(limit);
        console.debug('Initial evaluations load:', {
          count: response.length,
          firstEvaluation: response[0] ? {
            id: response[0].id,
            type: response[0].type,
            metrics: response[0].metrics,
            accuracy: response[0].accuracy,
            scoreResults: response[0].scoreResults,
            task: response[0].task ? {
              id: response[0].task.id,
              status: response[0].task.status,
              stages: response[0].task.stages
            } : null
          } : null
        });
        evaluations = response;
        subscriber.next({ items: evaluations, isSynced: true });
        isSynced = true;
      } catch (error) {
        console.error('Error loading initial evaluations:', error);
        subscriber.error(error);
      }
    }

    async function handleEvaluationUpdate(updatedEvaluation: Schema['Evaluation']['type']) {
      console.debug('Evaluation update received:', {
        id: updatedEvaluation.id,
        type: updatedEvaluation.type,
        metrics: updatedEvaluation.metrics,
        accuracy: updatedEvaluation.accuracy,
        scoreResults: updatedEvaluation.scoreResults,
        task: updatedEvaluation.task ? {
          id: updatedEvaluation.task.id,
          status: updatedEvaluation.task.status,
          stages: updatedEvaluation.task.stages
        } : null
      });

      // If we have IDs but no data, fetch the related data
      if (updatedEvaluation.scorecardId && !updatedEvaluation.scorecard) {
        console.debug('Fetching scorecard data for ID:', updatedEvaluation.scorecardId);
        const scorecardResponse = await client.graphql({
          query: `
            query GetScorecard($id: ID!) {
              getScorecard(id: $id) {
                id
                name
                key
              }
            }
          `,
          variables: {
            id: updatedEvaluation.scorecardId
          }
        });
        updatedEvaluation.scorecard = scorecardResponse.data?.getScorecard;
      }

      if (updatedEvaluation.scoreId && !updatedEvaluation.score) {
        console.debug('Fetching score data for ID:', updatedEvaluation.scoreId);
        const scoreResponse = await client.graphql({
          query: `
            query GetScore($id: ID!) {
              getScore(id: $id) {
                id
                name
                key
              }
            }
          `,
          variables: {
            id: updatedEvaluation.scoreId
          }
        });
        updatedEvaluation.score = scoreResponse.data?.getScore;
      }

      const evaluationIndex = evaluations.findIndex(e => e.id === updatedEvaluation.id);
      
      if (evaluationIndex !== -1) {
        // Update existing evaluation
        const existingEvaluation = evaluations[evaluationIndex];
        
        // Create the updated evaluation, prioritizing new data
        const updatedEvaluationData = {
          ...existingEvaluation,
          ...updatedEvaluation,
          task: updatedEvaluation.task || existingEvaluation.task
        };

        evaluations[evaluationIndex] = updatedEvaluationData;
      } else {
        // For new evaluations, add to the beginning of the array
        evaluations.unshift(updatedEvaluation);
        console.debug('Added new evaluation:', {
          evaluationId: updatedEvaluation.id,
          totalEvaluations: evaluations.length
        });
      }

      // Sort evaluations by updatedAt
      evaluations.sort((a, b) => 
        new Date(b.updatedAt || b.createdAt || '').getTime() - 
        new Date(a.updatedAt || a.createdAt || '').getTime()
      );

      // Trim to limit if needed
      if (evaluations.length > limit) {
        evaluations = evaluations.slice(0, limit);
      }

      console.debug('Emitting updated evaluation list:', {
        count: evaluations.length,
        evaluationIds: evaluations.map(e => ({
          id: e.id,
          status: e.status,
          taskId: e.taskId
        }))
      });
      subscriber.next({ items: [...evaluations], isSynced: true });
    }

    // Load initial data
    loadInitialEvaluations();

    // Set up subscriptions
    const subscriptions = [
      // Subscribe to evaluation updates
      client.graphql({
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
          }
        }`
      }).subscribe({
        next: (data: any) => {
          console.debug('Raw onUpdate data received:', {
            fullData: data,
            evaluationData: data?.data?.onUpdateEvaluation
          });
          
          const evaluationData = data?.data?.onUpdateEvaluation;
          if (!evaluationData?.id) {
            console.debug('Invalid evaluation update data:', data);
            return;
          }

          handleEvaluationUpdate(evaluationData);
        },
        error: (error: Error) => console.error('Error in evaluation onUpdate subscription:', error)
      }),

      // Subscribe to evaluation creates
      client.graphql({
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
          }
        }`
      }).subscribe({
        next: (data: any) => {
          console.debug('Raw onCreate data received:', {
            fullData: data,
            evaluationData: data?.data?.onCreateEvaluation
          });
          const evaluationData = data?.data?.onCreateEvaluation;
          if (!evaluationData?.id) {
            console.debug('Invalid evaluation create data:', data);
            return;
          }
          console.log('Evaluation onCreate triggered:', { 
            evaluationId: evaluationData.id,
            type: evaluationData.type,
            status: evaluationData.status,
            taskId: evaluationData.taskId
          });
          handleEvaluationUpdate(evaluationData);
        },
        error: (error: Error) => console.error('Error in evaluation onCreate subscription:', error)
      })
    ];

    // Cleanup function
    return () => {
      console.log('Cleaning up evaluation subscriptions');
      subscriptions.forEach(sub => sub.unsubscribe());
    };
  });
} 