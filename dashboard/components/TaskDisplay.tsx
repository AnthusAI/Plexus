import React, { useEffect, useState, useMemo } from 'react'
import type { AmplifyTask, ProcessedTask } from '@/utils/data-operations'
import { transformAmplifyTask, processTask, standardizeScoreResults } from '@/utils/data-operations'
import type { EvaluationTaskProps } from '@/types/tasks/evaluation'
import type { TaskStatus } from '@/types/shared'
import EvaluationTask from '@/components/EvaluationTask'
import { Task, TaskHeader, TaskContent } from '@/components/Task'

interface ProcessedTaskStage {
  id: string;
  name: string;
  order: number;
  status: string;
  statusMessage?: string;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  processedItems?: number;
  totalItems?: number;
}

interface TaskDisplayProps {
  task: AmplifyTask | null
  variant?: 'grid' | 'detail'
  isSelected?: boolean
  onClick?: () => void
  extra?: boolean
  evaluationData: {
    id: string
    type: string
    scorecard?: { name: string } | null
    score?: { name: string } | null
    createdAt: string
    metrics?: any
    metricsExplanation?: string | null
    accuracy?: number | null
    processedItems?: number | null
    totalItems?: number | null
    inferences?: number | null
    cost?: number | null
    status?: string | null
    elapsedSeconds?: number | null
    estimatedRemainingSeconds?: number | null
    startedAt?: string | null
    errorMessage?: string | null
    errorDetails?: any
    confusionMatrix?: any
    scoreGoal?: string | null
    datasetClassDistribution?: any
    isDatasetClassDistributionBalanced?: boolean | null
    predictedClassDistribution?: any
    isPredictedClassDistributionBalanced?: boolean | null
    scoreResults?: any // Accept any type for score results - we'll standardize it internally
  }
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  selectedScoreResultId?: string | null
  onSelectScoreResult?: (id: string | null) => void
  commandDisplay?: 'show' | 'hide'
}

function calculateProgress(processedItems?: number | null, totalItems?: number | null): number {
  if (!processedItems || !totalItems || totalItems === 0) return 0
  return Math.round((processedItems / totalItems) * 100)
}

export function TaskDisplay({
  variant = 'grid',
  task,
  evaluationData,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  selectedScoreResultId,
  onSelectScoreResult,
  extra,
  isSelected,
  commandDisplay: initialCommandDisplay = 'show'
}: TaskDisplayProps) {

  const [processedTask, setProcessedTask] = useState<ProcessedTask | null>(null)

  // Add detailed logging for evaluationData
  console.log('TaskDisplay received evaluationData:', {
    id: evaluationData.id,
    hasScoreResults: !!evaluationData.scoreResults,
    scoreResultsType: evaluationData.scoreResults ? typeof evaluationData.scoreResults : 'undefined',
    scoreResultsItemsType: evaluationData.scoreResults?.items ? typeof evaluationData.scoreResults.items : 'undefined',
    scoreResultsItemsLength: evaluationData.scoreResults?.items?.length ?? 0,
    scoreResultsItemsIsArray: Array.isArray(evaluationData.scoreResults?.items),
    firstScoreResult: evaluationData.scoreResults?.items?.[0],
    variant
  });

  useEffect(() => {
    async function processTaskData() {
      if (!task) {
        console.debug('TaskDisplay: No task data provided', {
          evaluationId: evaluationData.id,
          evaluationStatus: evaluationData.status
        });
        setProcessedTask(null);
        return;
      }
      try {
        const convertedTask = await transformAmplifyTask(task);
        const result = await processTask(convertedTask);
        setProcessedTask(result);
      } catch (error) {
        console.error('Error processing task:', error);
        setProcessedTask(null);
      }
    }
    processTaskData();
  }, [task]);

  // Memoize score results transformation
  const transformedScoreResults = useMemo(() => {
    console.log('TaskDisplay transforming score results:', {
      hasResults: !!evaluationData.scoreResults,
      scoreResultsType: evaluationData.scoreResults ? typeof evaluationData.scoreResults : 'undefined',
      hasItems: evaluationData.scoreResults && 'items' in evaluationData.scoreResults
    });

    // Standardize score results to ensure consistent format
    const standardizedResults = standardizeScoreResults(evaluationData.scoreResults);
    
    console.log('TaskDisplay standardized score results:', {
      count: standardizedResults.length,
      firstResult: standardizedResults[0],
      isArray: Array.isArray(standardizedResults)
    });

    if (!standardizedResults.length) {
      console.log('No score results to transform');
      return [];
    }

    const transformed = standardizedResults.map((result: any) => {
      // Parse metadata if it's a string
      let parsedMetadata;
      try {
        if (typeof result.metadata === 'string') {
          parsedMetadata = JSON.parse(result.metadata);
          if (typeof parsedMetadata === 'string') {
            parsedMetadata = JSON.parse(parsedMetadata);
          }
        } else {
          parsedMetadata = result.metadata || {};
        }

        console.log('Score result metadata in TaskDisplay:', {
          resultId: result.id,
          rawMetadata: result.metadata,
          parsedMetadata,
          metadataType: typeof result.metadata,
          hasResults: !!parsedMetadata?.results,
          resultsKeys: parsedMetadata?.results ? Object.keys(parsedMetadata.results) : [],
          humanLabel: parsedMetadata?.human_label,
          nestedHumanLabel: parsedMetadata?.results?.[Object.keys(parsedMetadata.results)[0]]?.metadata?.human_label
        });

      } catch (e) {
        console.error('Error parsing metadata:', e);
        parsedMetadata = {};
      }

      // Extract results from nested structure if present
      const firstResultKey = parsedMetadata?.results ? Object.keys(parsedMetadata.results)[0] : null;
      const scoreResult = firstResultKey && parsedMetadata.results ? parsedMetadata.results[firstResultKey] : null;

      const transformedResult = {
        id: result.id,
        value: result.value,
        confidence: result.confidence ?? null,
        explanation: result.explanation ?? scoreResult?.explanation ?? null,
        metadata: {
          human_label: scoreResult?.metadata?.human_label ?? parsedMetadata.human_label ?? result.metadata?.human_label ?? null,
          correct: Boolean(scoreResult?.metadata?.correct ?? parsedMetadata.correct ?? result.metadata?.correct),
          human_explanation: scoreResult?.metadata?.human_explanation ?? parsedMetadata.human_explanation ?? result.metadata?.human_explanation ?? null,
          text: scoreResult?.metadata?.text ?? parsedMetadata.text ?? result.metadata?.text ?? null
        },
        itemId: result.itemId ?? parsedMetadata.item_id?.toString() ?? null,
        createdAt: result.createdAt
      };

      console.log('Transformed score result in TaskDisplay:', {
        id: transformedResult.id,
        value: transformedResult.value,
        humanLabel: transformedResult.metadata.human_label,
        correct: transformedResult.metadata.correct,
        explanation: transformedResult.explanation
      });

      return transformedResult;
    });

    console.log('TaskDisplay final transformed score results:', {
      inputCount: standardizedResults.length,
      transformedCount: transformed.length,
      firstTransformed: transformed[0]
    });

    return transformed;
  }, [evaluationData.scoreResults]);

  const taskProps = {
    task: {
      id: evaluationData.id,
      type: evaluationData.type,
      scorecard: evaluationData.scorecard?.name || '-',
      score: evaluationData.score?.name || '-',
      time: evaluationData.createdAt || new Date().toISOString(),
      startedAt: processedTask?.startedAt || task?.startedAt || evaluationData.startedAt,
      completedAt: processedTask?.completedAt || task?.completedAt,
      estimatedCompletionAt: processedTask?.estimatedCompletionAt || task?.estimatedCompletionAt,
      status: (processedTask?.status || task?.status || evaluationData.status || 'PENDING') as TaskStatus,
      data: {
        id: evaluationData.id,
        title: `${evaluationData.scorecard?.name || '-'} - ${evaluationData.score?.name || '-'}`,
        metrics: typeof evaluationData.metrics === 'string' ? 
          JSON.parse(evaluationData.metrics).map((m: any) => ({
            name: m.name || 'Unknown',
            value: m.value || 0,
            unit: m.unit,
            maximum: m.maximum,
            priority: m.priority || false
          })) : (evaluationData.metrics || []).map((m: any) => ({
            name: m.name || 'Unknown',
            value: m.value || 0,
            unit: m.unit,
            maximum: m.maximum,
            priority: m.priority || false
          })),
        accuracy: evaluationData.accuracy || null,
        processedItems: Number(evaluationData.processedItems || 0),
        totalItems: Number(evaluationData.totalItems || 0),
        progress: calculateProgress(evaluationData.processedItems, evaluationData.totalItems),
        inferences: Number(evaluationData.inferences || 0),
        cost: evaluationData.cost ?? null,
        status: (processedTask?.status || task?.status || evaluationData.status || 'PENDING') as TaskStatus,
        elapsedSeconds: evaluationData.elapsedSeconds ?? null,
        estimatedRemainingSeconds: evaluationData.estimatedRemainingSeconds ?? null,
        startedAt: processedTask?.startedAt || task?.startedAt || evaluationData.startedAt,
        completedAt: processedTask?.completedAt || task?.completedAt,
        estimatedCompletionAt: processedTask?.estimatedCompletionAt || task?.estimatedCompletionAt,
        errorMessage: evaluationData.errorMessage || undefined,
        errorDetails: evaluationData.errorDetails || undefined,
        confusionMatrix: typeof evaluationData.confusionMatrix === 'string' ? 
          JSON.parse(evaluationData.confusionMatrix) : evaluationData.confusionMatrix,
        metricsExplanation: evaluationData.metricsExplanation || null,
        scoreGoal: evaluationData.scoreGoal || null,
        datasetClassDistribution: typeof evaluationData.datasetClassDistribution === 'string' ? 
          JSON.parse(evaluationData.datasetClassDistribution) : evaluationData.datasetClassDistribution,
        isDatasetClassDistributionBalanced: evaluationData.isDatasetClassDistributionBalanced ?? null,
        predictedClassDistribution: typeof evaluationData.predictedClassDistribution === 'string' ? 
          JSON.parse(evaluationData.predictedClassDistribution) : evaluationData.predictedClassDistribution,
        isPredictedClassDistributionBalanced: evaluationData.isPredictedClassDistributionBalanced ?? null,
        scoreResults: transformedScoreResults,
        task: processedTask ? {
          ...processedTask,
          accountId: evaluationData.id,
          stages: {
            items: processedTask.stages.map((stage: ProcessedTaskStage) => ({
              id: stage.id,
              name: stage.name,
              order: stage.order,
              status: stage.status,
              statusMessage: stage.statusMessage,
              startedAt: stage.startedAt,
              completedAt: stage.completedAt,
              estimatedCompletionAt: stage.estimatedCompletionAt,
              processedItems: stage.processedItems,
              totalItems: stage.totalItems
            }))
          }
        } : null
      }
    },
    onClick,
    controlButtons,
    isFullWidth,
    onToggleFullWidth,
    onClose,
    isSelected,
    extra,
    selectedScoreResultId,
    onSelectScoreResult
  } as EvaluationTaskProps

  return <EvaluationTask {...taskProps} variant={variant} />
} 