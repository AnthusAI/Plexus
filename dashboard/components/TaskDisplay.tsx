import React, { useEffect, useState, useMemo } from 'react'
import type { AmplifyTask, ProcessedTask } from '@/utils/data-operations'
import { transformAmplifyTask, processTask, standardizeScoreResults } from '@/utils/data-operations'
import type { EvaluationTaskProps } from '@/types/tasks/evaluation'
import type { TaskStatus } from '@/types/shared'
import EvaluationTask from '@/components/EvaluationTask'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import ReportTask from '@/components/ReportTask'

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
  reportData?: {
    id: string
    name: string
    createdAt: string
    updatedAt?: string
  }
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  selectedScoreResultId?: string | null
  onSelectScoreResult?: (id: string | null) => void
  commandDisplay?: 'show' | 'hide'
  onShare?: () => void
  onDelete?: (evaluationId: string) => void
}

function calculateProgress(processedItems?: number | null, totalItems?: number | null): number {
  if (!processedItems || !totalItems || totalItems === 0) return 0
  return Math.round((processedItems / totalItems) * 100)
}

// Wrap the component with React.memo to prevent unnecessary re-renders
export const TaskDisplay = React.memo(function TaskDisplayComponent({
  variant = 'grid',
  task,
  evaluationData,
  reportData,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  selectedScoreResultId,
  onSelectScoreResult,
  extra,
  isSelected,
  commandDisplay: initialCommandDisplay = 'show',
  onShare,
  onDelete
}: TaskDisplayProps) {
  // Add debug logging for onClose prop
  console.log('TaskDisplay component received props:', {
    variant,
    taskId: reportData?.id || evaluationData?.id,
    hasOnClose: !!onClose,
    hasOnToggleFullWidth: !!onToggleFullWidth
  });

  const [processedTask, setProcessedTask] = useState<ProcessedTask | null>(null)
  const [commandDisplay, setCommandDisplay] = useState(initialCommandDisplay)

  // Add detailed logging for evaluationData or reportData
  console.log('TaskDisplay received data:', {
    id: reportData?.id || evaluationData?.id,
    type: reportData ? 'Report' : evaluationData?.type,
    hasTask: !!task,
    taskId: task?.id,
    taskType: typeof task,
    taskKeys: task ? Object.keys(task) : [],
    taskStages: task?.stages,
    taskStagesType: task?.stages ? typeof task.stages : 'undefined',
    taskStagesData: (task?.stages as any)?.data,
    taskStagesItems: (task?.stages as any)?.items,
    hasScoreResults: !!evaluationData?.scoreResults,
    variant
  });

  useEffect(() => {
    async function processTaskData() {
      if (!task) {
        console.debug('TaskDisplay: No task data provided', {
          dataId: reportData?.id || evaluationData?.id,
          evaluationStatus: evaluationData?.status
        });
        setProcessedTask(null);
        return;
      }
      try {
        console.log('TaskDisplay: Processing task data:', {
          taskId: task.id,
          taskStages: task.stages,
          taskStagesType: typeof task.stages
        });
        const convertedTask = await transformAmplifyTask(task);
        console.log('TaskDisplay: Converted task:', {
          taskId: convertedTask.id,
          stages: convertedTask.stages
        });
        const result = await processTask(convertedTask);
        console.log('TaskDisplay: Processed task result:', {
          taskId: result.id,
          stages: result.stages,
          stagesCount: result.stages?.length
        });
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
    if (!evaluationData) return [];

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
        trace: result.trace ?? scoreResult?.trace ?? null,
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
  }, [evaluationData]);

  // Define base properties, prefer reportData if available
  const displayId = reportData?.id || evaluationData?.id || 'unknown-id';
  const displayType = reportData ? 'Report' : (evaluationData ? `${evaluationData.type} Evaluation` : 'Unknown');
  const displayTime = reportData?.createdAt || evaluationData?.createdAt || new Date().toISOString();
  const displayTitle = reportData?.name || (evaluationData ? `${evaluationData.scorecard?.name || '-'} - ${evaluationData.score?.name || '-'}` : 'Report');

  // Construct props common to both EvaluationTask and ReportTask
  const commonTaskProps = {
    id: displayId,
    type: displayType,
    time: displayTime,
    startedAt: (processedTask?.startedAt || task?.startedAt || evaluationData?.startedAt) ?? undefined,
    completedAt: (processedTask?.completedAt || task?.completedAt) ?? undefined,
    estimatedCompletionAt: (processedTask?.estimatedCompletionAt || task?.estimatedCompletionAt) ?? undefined,
    status: (processedTask?.status || task?.status || evaluationData?.status || 'PENDING') as TaskStatus,
    stages: processedTask ? processedTask.stages.map((stage: ProcessedTaskStage) => {
      const isCompleted = stage.status === 'COMPLETED';
      const isRunning = stage.status === 'RUNNING';
      const isFailed = stage.status === 'FAILED';

      return {
        id: stage.id,
        key: stage.name,
        label: stage.name,
        color: isCompleted ? 'bg-primary' :
               isRunning ? 'bg-secondary' :
               isFailed ? 'bg-false' :
               'bg-neutral',
        name: stage.name,
        order: stage.order,
        status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
        statusMessage: stage.statusMessage,
        startedAt: stage.startedAt,
        completedAt: stage.completedAt,
        estimatedCompletionAt: stage.estimatedCompletionAt,
        processedItems: stage.processedItems,
        totalItems: stage.totalItems,
        completed: isCompleted
      };
    }) : undefined,
    title: displayTitle,
    command: processedTask?.command,
    description: processedTask?.description,
    dispatchStatus: processedTask?.dispatchStatus,
    metadata: processedTask?.metadata,
    errorMessage: processedTask?.errorMessage || (task ? (task.errorMessage || evaluationData?.errorMessage) : evaluationData?.errorMessage) || undefined,
    errorDetails: processedTask?.errorDetails || (task ? (task.errorDetails || evaluationData?.errorDetails) : evaluationData?.errorDetails) || undefined,
    celeryTaskId: (processedTask?.celeryTaskId || task?.celeryTaskId) ?? undefined,
    workerNodeId: (processedTask?.workerNodeId || task?.workerNodeId) ?? undefined,
    output: processedTask?.output || task?.output || undefined, // Universal Code YAML output
    attachedFiles: processedTask?.attachedFiles || task?.attachedFiles || undefined, // File attachments
    stdout: processedTask?.stdout || task?.stdout || undefined, // Task stdout
    stderr: processedTask?.stderr || task?.stderr || undefined, // Task stderr
  };

  // Conditionally render EvaluationTask or ReportTask
  if (evaluationData) {
    // Construct props specific to EvaluationTask
    const evaluationTaskProps = {
      task: {
        ...commonTaskProps,
        scorecard: evaluationData.scorecard?.name || '-',
        score: evaluationData.score?.name || '-',
        data: {
          id: displayId,
          title: displayTitle,
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
          status: commonTaskProps.status,
          elapsedSeconds: evaluationData.elapsedSeconds ?? null,
          estimatedRemainingSeconds: evaluationData.estimatedRemainingSeconds ?? null,
          startedAt: commonTaskProps.startedAt,
          completedAt: commonTaskProps.completedAt,
          estimatedCompletionAt: commonTaskProps.estimatedCompletionAt,
          errorMessage: commonTaskProps.errorMessage,
          errorDetails: commonTaskProps.errorDetails,
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
              id: processedTask.id,
              accountId: '',
              type: processedTask.type || displayType,
              command: processedTask.command,
              status: processedTask.status,
              target: processedTask.target,
              description: processedTask.description,
              dispatchStatus: processedTask.dispatchStatus,
              startedAt: processedTask.startedAt,
              completedAt: processedTask.completedAt,
              estimatedCompletionAt: processedTask.estimatedCompletionAt,
              celeryTaskId: processedTask.celeryTaskId,
              workerNodeId: processedTask.workerNodeId,
              stages: commonTaskProps.stages ? {
                items: commonTaskProps.stages
              } : { items: [] },
              errorMessage: commonTaskProps.errorMessage,
              errorDetails: commonTaskProps.errorDetails
          } : {
              id: displayId,
              accountId: '',
              type: displayType,
              command: task?.command,
              status: task?.status || evaluationData?.status || 'PENDING',
              target: task?.target,
              description: task?.description,
              dispatchStatus: task?.dispatchStatus,
              startedAt: task?.startedAt || evaluationData?.startedAt,
              completedAt: task?.completedAt,
              estimatedCompletionAt: task?.estimatedCompletionAt,
              celeryTaskId: task?.celeryTaskId,
              workerNodeId: task?.workerNodeId,
              stages: (() => {
                // Try to extract stages from the original task data
                console.log('TaskDisplay: Extracting stages from task in fallback case:', {
                  taskId: task?.id,
                  taskStages: task?.stages,
                  taskStagesType: typeof task?.stages
                });
                
                // Handle different possible structures for stages
                let stageItems: any[] = [];
                if (task?.stages) {
                  if (Array.isArray(task.stages)) {
                    stageItems = task.stages;
                  } else if (typeof task.stages === 'function') {
                    // This is a lazy loader, we can't process it synchronously
                    console.log('TaskDisplay: Task stages is a lazy loader, cannot process synchronously');
                  } else {
                    // Try to access data or items properties safely
                    const stagesData = (task.stages as any);
                    if (stagesData?.data?.items) {
                      stageItems = stagesData.data.items;
                    } else if (stagesData?.items) {
                      stageItems = stagesData.items;
                    }
                  }
                }
                
                console.log('TaskDisplay: Extracted stage items:', {
                  count: stageItems.length,
                  items: stageItems
                });
                
                return {
                  items: stageItems.map((stage: any) => ({
                    id: stage.id || stage.name,
                    key: stage.name,
                    label: stage.name,
                    color: stage.status === 'COMPLETED' ? 'bg-primary' :
                           stage.status === 'RUNNING' ? 'bg-secondary' :
                           stage.status === 'FAILED' ? 'bg-false' :
                           'bg-neutral',
                    name: stage.name,
                    order: stage.order || 0,
                    status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
                    statusMessage: stage.statusMessage,
                    startedAt: stage.startedAt,
                    completedAt: stage.completedAt,
                    estimatedCompletionAt: stage.estimatedCompletionAt,
                    processedItems: stage.processedItems,
                    totalItems: stage.totalItems,
                    completed: stage.status === 'COMPLETED'
                  }))
                };
              })(),
              errorMessage: task?.errorMessage || evaluationData?.errorMessage,
              errorDetails: task?.errorDetails || evaluationData?.errorDetails,
          }
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
      onSelectScoreResult,
      onShare,
      onDelete
    } as EvaluationTaskProps;

    return <EvaluationTask {...evaluationTaskProps} variant={variant} />;

  } else if (reportData) {
    // Construct props for ReportTask
    const reportStatusRaw = commonTaskProps.status;
    const reportStatusValue = reportStatusRaw ? reportStatusRaw.toUpperCase() : 'PENDING';
    const reportStatusFinal = ['PENDING', 'RUNNING', 'COMPLETED', 'FAILED'].includes(reportStatusValue)
      ? reportStatusValue as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
      : undefined;
      
    const reportTaskProps = {
      task: {
        ...commonTaskProps,
        status: reportStatusFinal, // Override status with the validated/refined one
        scorecard: '-',
        score: '-',
        data: {
            id: reportData.id,
            title: displayTitle,
            name: reportData.name,
            createdAt: reportData.createdAt,
            updatedAt: reportData.updatedAt
        }
      },
      variant,
      isSelected,
      onClick,
      controlButtons,
      isFullWidth,
      onToggleFullWidth,
      onClose,
      extra
    };
    return <ReportTask {...reportTaskProps} />;
  }

  // Fallback or loading state if neither data type is provided
  console.warn("TaskDisplay rendered without evaluationData or reportData");
  return <div>Loading...</div>;
}, (prevProps, nextProps) => {
  // Custom comparison function to prevent unnecessary re-renders
  // Only re-render if these specific props change
  return (
    prevProps.variant === nextProps.variant &&
    prevProps.task?.id === nextProps.task?.id &&
    prevProps.task?.status === nextProps.task?.status &&
    prevProps.evaluationData.id === nextProps.evaluationData.id &&
    prevProps.evaluationData.status === nextProps.evaluationData.status &&
    prevProps.isSelected === nextProps.isSelected &&
    prevProps.selectedScoreResultId === nextProps.selectedScoreResultId &&
    prevProps.isFullWidth === nextProps.isFullWidth
  );
}); 