import React, { useEffect, useState, useMemo } from 'react'
import type { AmplifyTask, ProcessedTask } from '@/utils/data-operations'
import { transformAmplifyTask, processTask } from '@/utils/data-operations'
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

  const [processedTask, setProcessedTask] = useState<ProcessedTask | null>(null)
  const [commandDisplay, setCommandDisplay] = useState(initialCommandDisplay)


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

  const transformedScoreResults = useMemo(() => {
    if (!evaluationData?.scoreResults) return [];

    // All score results come pre-transformed with itemIdentifiers included
    return Array.isArray(evaluationData.scoreResults) ? 
      evaluationData.scoreResults : 
      (evaluationData.scoreResults && typeof evaluationData.scoreResults === 'object' && 'items' in evaluationData.scoreResults ? 
        evaluationData.scoreResults.items : 
        []);
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
                
                // Handle different possible structures for stages
                let stageItems: any[] = [];
                if (task?.stages) {
                  if (Array.isArray(task.stages)) {
                    stageItems = task.stages;
                  } else if (typeof task.stages === 'function') {
                    // This is a lazy loader, we can't process it synchronously
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