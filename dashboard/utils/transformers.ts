/**
 * Data Transformers Module
 * =======================
 * 
 * This module contains functions for transforming data between different formats:
 * - Raw API responses to AmplifyTask objects
 * - AmplifyTask to ProcessedTask objects
 * - Raw evaluation data to processed evaluation objects
 */

import type { Schema } from '../amplify/data/resource';
import type { AmplifyTask, ProcessedTask, ProcessedTaskStage, TaskStageType } from './data-operations';

export function convertToAmplifyTask(rawData: any): AmplifyTask {
  // Create a lazy loader for stages only if stages exist
  const stagesLoader = rawData.stages ? () => Promise.resolve({
    data: {
      items: (rawData.stages?.items ?? []).map((stage: any) => ({
        id: stage.id,
        name: stage.name,
        order: stage.order,
        status: stage.status,
        processedItems: stage.processedItems,
        totalItems: stage.totalItems,
        startedAt: stage.startedAt,
        completedAt: stage.completedAt,
        estimatedCompletionAt: stage.estimatedCompletionAt,
        statusMessage: stage.statusMessage
      }))
    }
  }) : undefined;

  // Create lazy loaders for scorecard and score only if they exist
  const scorecardLoader = rawData.scorecard ? () => Promise.resolve({
    data: {
      id: rawData.scorecard.id,
      name: rawData.scorecard.name
    }
  }) : undefined;

  const scoreLoader = rawData.score ? () => Promise.resolve({
    data: {
      id: rawData.score.id,
      name: rawData.score.name
    }
  }) : undefined;

  // Create lazy loader for evaluation only if it exists
  const evaluationLoader = rawData.evaluation ? () => Promise.resolve({
    data: rawData.evaluation
  }) : undefined;

  return {
    id: rawData.id,
    command: rawData.command,
    type: rawData.type,
    status: rawData.status,
    target: rawData.target,
    description: rawData.description ?? null,
    metadata: rawData.metadata,
    createdAt: rawData.createdAt ?? null,
    startedAt: rawData.startedAt ?? null,
    completedAt: rawData.completedAt ?? null,
    estimatedCompletionAt: rawData.estimatedCompletionAt ?? null,
    errorMessage: rawData.errorMessage ?? null,
    errorDetails: rawData.errorDetails,
    stdout: rawData.stdout ?? null,
    stderr: rawData.stderr ?? null,
    currentStageId: rawData.currentStageId ?? null,
    stages: stagesLoader,
    dispatchStatus: rawData.dispatchStatus ?? null,
    celeryTaskId: rawData.celeryTaskId ?? null,
    workerNodeId: rawData.workerNodeId ?? null,
    updatedAt: rawData.updatedAt ?? null,
    scorecardId: rawData.scorecardId ?? null,
    scoreId: rawData.scoreId ?? null,
    scorecard: scorecardLoader,
    score: scoreLoader,
    evaluation: evaluationLoader
  };
}

export async function processTask(task: AmplifyTask): Promise<ProcessedTask> {
  // Parse metadata if it's a string
  let parsedMetadata: Record<string, unknown> | null = null;
  if (task.metadata) {
    if (typeof task.metadata === 'string') {
      try {
        parsedMetadata = JSON.parse(task.metadata);
      } catch (e) {
        console.warn('Failed to parse task metadata:', e);
      }
    } else if (typeof task.metadata === 'object') {
      parsedMetadata = task.metadata;
    }
  }

  // Handle stages - ensure we handle both function and direct data cases
  const stages: ProcessedTaskStage[] = await (async () => {
    if (typeof task.stages === 'function') {
      try {
        const stagesResult = await task.stages();
        return stagesResult.data?.items?.map((stage: TaskStageType) => ({
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
        })) ?? [];
      } catch (e) {
        console.warn('Failed to fetch stages:', e);
        return [];
      }
    }
    return task.stages?.data?.items?.map((stage: TaskStageType) => ({
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
    })) ?? [];
  })();

  // Transform evaluation data if present
  let evaluation = undefined;
  if (task.evaluation) {
    try {
      const evaluationData = typeof task.evaluation === 'function' ? await task.evaluation() : task.evaluation;

      // Parse metrics if it's a string
      let metrics = evaluationData.data?.metrics;
      try {
        if (typeof metrics === 'string') {
          metrics = JSON.parse(metrics);
        }
      } catch (e) {
        console.error('Error parsing metrics:', e);
      }

      // Parse confusion matrix if it's a string
      let confusionMatrix = evaluationData.data?.confusionMatrix;
      try {
        if (typeof confusionMatrix === 'string') {
          confusionMatrix = JSON.parse(confusionMatrix);
        }
      } catch (e) {
        console.error('Error parsing confusion matrix:', e);
      }

      // Parse dataset class distribution if it's a string
      let datasetClassDistribution = evaluationData.data?.datasetClassDistribution;
      try {
        if (typeof datasetClassDistribution === 'string') {
          datasetClassDistribution = JSON.parse(datasetClassDistribution);
        }
      } catch (e) {
        console.error('Error parsing dataset class distribution:', e);
      }

      // Parse predicted class distribution if it's a string
      let predictedClassDistribution = evaluationData.data?.predictedClassDistribution;
      try {
        if (typeof predictedClassDistribution === 'string') {
          predictedClassDistribution = JSON.parse(predictedClassDistribution);
        }
      } catch (e) {
        console.error('Error parsing predicted class distribution:', e);
      }

      // Get score results data
      let scoreResults = undefined;
      if (evaluationData.data?.scoreResults) {
        const rawScoreResults = typeof evaluationData.data.scoreResults === 'function' 
          ? await evaluationData.data.scoreResults()
          : evaluationData.data.scoreResults;

        if (Array.isArray(rawScoreResults)) {
          scoreResults = rawScoreResults.map((item: {
            id: string;
            value: string | number;
            confidence?: number | null;
            metadata: any;
            explanation?: string | null;
            itemId?: string | null;
            createdAt: string;
            trace?: any | null;
          }) => ({
            id: item.id,
            value: item.value,
            confidence: item.confidence ?? null,
            metadata: item.metadata,
            explanation: item.explanation ?? null,
            itemId: item.itemId ?? null,
            createdAt: item.createdAt,
            trace: item.trace ?? null
          }));
        }
      }

      evaluation = {
        id: evaluationData.data?.id || '',
        type: evaluationData.data?.type || 'unknown',
        metrics,
        metricsExplanation: evaluationData.data?.metricsExplanation,
        inferences: Number(evaluationData.data?.inferences) || 0,
        accuracy: typeof evaluationData.data?.accuracy === 'number' ? evaluationData.data.accuracy : 0,
        cost: evaluationData.data?.cost ?? null,
        status: evaluationData.data?.status || 'PENDING',
        startedAt: evaluationData.data?.startedAt,
        elapsedSeconds: evaluationData.data?.elapsedSeconds ?? null,
        estimatedRemainingSeconds: evaluationData.data?.estimatedRemainingSeconds ?? null,
        totalItems: Number(evaluationData.data?.totalItems) || 0,
        processedItems: Number(evaluationData.data?.processedItems) || 0,
        errorMessage: evaluationData.data?.errorMessage,
        errorDetails: evaluationData.data?.errorDetails,
        confusionMatrix,
        scoreGoal: evaluationData.data?.scoreGoal,
        datasetClassDistribution,
        isDatasetClassDistributionBalanced: evaluationData.data?.isDatasetClassDistributionBalanced,
        predictedClassDistribution,
        isPredictedClassDistributionBalanced: evaluationData.data?.isPredictedClassDistributionBalanced,
        scoreResults,
        accountId: evaluationData.data?.accountId || '',
        items: evaluationData.data?.items || (() => Promise.resolve({ data: [] })),
        scoringJobs: evaluationData.data?.scoringJobs || (() => Promise.resolve({ data: [] })),
        account: evaluationData.data?.account || (() => Promise.resolve({ data: null })),
        createdAt: evaluationData.data?.createdAt || new Date().toISOString(),
        updatedAt: evaluationData.data?.updatedAt || new Date().toISOString(),
        task: null,
        scorecard: null,
        score: null,
        scoreVersion: evaluationData.data?.scoreVersion || (() => Promise.resolve({ data: null }))
      };
    } catch (error) {
      console.error('Error transforming evaluation data:', error);
    }
  }

  const scorecard = task.scorecard ? await (typeof task.scorecard === 'function' ? task.scorecard() : task.scorecard) : undefined;
  const score = task.score ? await (typeof task.score === 'function' ? task.score() : task.score) : undefined;

  return {
    id: task.id,
    command: task.command,
    type: task.type,
    status: task.status,
    target: task.target,
    description: task.description ?? undefined,
    metadata: parsedMetadata,
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
    dispatchStatus: task.dispatchStatus === 'DISPATCHED' ? 'DISPATCHED' : undefined,
    celeryTaskId: task.celeryTaskId ?? undefined,
    workerNodeId: task.workerNodeId ?? undefined,
    updatedAt: task.updatedAt ?? undefined,
    scorecardId: task.scorecardId ?? undefined,
    scoreId: task.scoreId ?? undefined,
    scorecard: scorecard?.data?.id && scorecard.data.name ? {
      id: scorecard.data.id,
      name: scorecard.data.name
    } : undefined,
    score: score?.data?.id && score.data.name ? {
      id: score.data.id,
      name: score.data.name
    } : undefined,
    evaluation
  };
} 