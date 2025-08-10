import React, { useEffect, useState, useMemo, useRef } from 'react'
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
  const normalizeStatus = (value?: string | null): TaskStatus => {
    if (!value) return 'pending';
    const s = String(value).toLowerCase();
    if (s === 'done') return 'completed';
    if (s === 'error') return 'failed';
    if (s === 'pending' || s === 'running' || s === 'completed' || s === 'failed') return s as TaskStatus;
    return 'pending';
  };

  // Log for ALL evaluations to see what TaskDisplay is receiving
  if (evaluationData && evaluationData.id === '6ee38d94-63b4-40ee-b53b-8131ab340a00') {
    const stageArr = ((task as any)?.stages?.items || (task as any)?.stages?.data?.items || []) as any[];
    console.log(`STAGE_TRACE: TaskDisplay render ${evaluationData.id} received task with stages: ${stageArr.map((s: any) => `${s.name}:${s.status}`).join(',') || 'none'}`);
  }

  const [processedTask, setProcessedTask] = useState<ProcessedTask | null>(null)
  const [commandDisplay, setCommandDisplay] = useState(initialCommandDisplay)
  const lastStageItemsRef = useRef<any[]>([])
  const getStageItemsFromTask = (t: any): any[] => {
    if (!t) return [];
    const s: any = (t as any).stages;
    if (!s) return [];
    if (Array.isArray(s)) return s;
    const fromData = (s as any)?.data?.items;
    if (Array.isArray(fromData)) return fromData;
    const fromItems = (s as any)?.items;
    if (Array.isArray(fromItems)) return fromItems;
    return [];
  };


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
      
      // Removed excessive logging
      
      // Check if task already has well-structured stage data (from subscription)
      const hasDirectStageData = (task as any)?.stages && 
        typeof (task as any).stages === 'object' && 
        (((task as any).stages.data?.items?.length ?? 0) > 0 || ((task as any).stages.items?.length ?? 0) > 0);
      
      if (hasDirectStageData) {
        // Skip the transformAmplifyTask/processTask pipeline that strips stages
        // Create a ProcessedTask directly from the good data we already have
        // Using direct stage data - bypass transform pipeline
        
        const stageItems = ((task as any).stages?.data?.items || (task as any).stages?.items || []) as any[];
        const processedTask: ProcessedTask = {
          id: task.id,
          command: task.command || '',
          type: task.type || 'evaluation',
          status: task.status || 'PENDING',
          target: task.target || '',
          stages: stageItems.map((stage: any) => ({
            id: stage.id || '',
            name: stage.name || '',
            order: stage.order || 0,
            status: (stage.status || 'PENDING') as any,
            statusMessage: stage.statusMessage,
            startedAt: stage.startedAt,
            completedAt: stage.completedAt,
            estimatedCompletionAt: stage.estimatedCompletionAt,
            processedItems: stage.processedItems,
            totalItems: stage.totalItems
          })),
          startedAt: task.startedAt || undefined,
          completedAt: task.completedAt || undefined,
          estimatedCompletionAt: task.estimatedCompletionAt || undefined,
          errorMessage: task.errorMessage || undefined,
          errorDetails: task.errorDetails || undefined,
          currentStageId: task.currentStageId || undefined
        };
        if (stageItems.length > 0) {
          lastStageItemsRef.current = stageItems;
        }
        
        // Created ProcessedTask with stage data preserved
        if (processedTask.stages?.length > 0) {
          console.log(`STAGE_TRACE: TaskDisplay processTaskData direct path created ProcessedTask ${processedTask.id} with ${processedTask.stages.length} stages: ${processedTask.stages.map(s => `${s.name}:${s.status}`).join(',')}`);
        } else {
          console.log(`STAGE_TRACE: TaskDisplay processTaskData direct path created ProcessedTask ${processedTask.id} with NO stages - hasDirectStageData=${hasDirectStageData}`);
        }
        
        if (evaluationData.id === '6ee38d94-63b4-40ee-b53b-8131ab340a00') {
          console.log(`STAGE_TRACE: TaskDisplay setProcessedTask for ${evaluationData.id} with ${processedTask.stages?.length || 0} stages`);
        }
        
        setProcessedTask(processedTask);
        return;
      }
      
      // Fallback to original processing for tasks without stage data
      try {
        const convertedTask = await transformAmplifyTask(task);
        
        const result = await processTask(convertedTask);
        if (result.stages?.length > 0) {
          console.log(`STAGE_TRACE: TaskDisplay processTaskData fallback path created ProcessedTask ${result.id} with ${result.stages.length} stages: ${result.stages.map(s => `${s.name}:${s.status}`).join(',')}`);
        } else {
          console.log(`STAGE_TRACE: TaskDisplay processTaskData fallback path lost stages for task ${task.id} - transformAmplifyTask/processTask stripped them`);
        }
        
        setProcessedTask(result);
      } catch (error) {
        console.error('Error processing task:', error);
        setProcessedTask(null);
      }
    }
    processTaskData();
  }, [task, evaluationData?.id]);

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
  // Determine status with a fallback: if all stages completed, mark as COMPLETED
  const rawStatus = normalizeStatus(evaluationData?.status || task?.status || processedTask?.status || 'PENDING');
  const stageSourceRaw: any[] = processedTask?.stages?.length ? processedTask.stages : getStageItemsFromTask(task);
  const stageSource: any[] = stageSourceRaw.length > 0 ? stageSourceRaw : lastStageItemsRef.current;
  const allStagesCompleted = stageSource.length > 0 && stageSource.every((s: any) => (String(s?.status || '').toUpperCase()) === 'COMPLETED');
  const effectiveStatus = (rawStatus === 'completed' || (rawStatus !== 'failed' && allStagesCompleted)) ? 'completed' : rawStatus;
  const displayStatusUC = (effectiveStatus === 'pending') ? 'PENDING'
    : (effectiveStatus === 'running') ? 'RUNNING'
    : (effectiveStatus === 'completed') ? 'COMPLETED'
    : (effectiveStatus === 'failed') ? 'FAILED'
    : 'PENDING';

  const rawStageItemsForDisplay: any[] = stageSourceRaw.length > 0 ? stageSourceRaw : lastStageItemsRef.current;
  if (rawStageItemsForDisplay.length > 0) {
    lastStageItemsRef.current = rawStageItemsForDisplay;
  }

  const commonTaskProps = {
    id: displayId,
    type: displayType,
    time: displayTime,
    startedAt: (processedTask?.startedAt || task?.startedAt || evaluationData?.startedAt) ?? undefined,
    completedAt: (processedTask?.completedAt || task?.completedAt) ?? undefined,
    estimatedCompletionAt: (processedTask?.estimatedCompletionAt || task?.estimatedCompletionAt) ?? undefined,
    status: displayStatusUC as any,
    stages: rawStageItemsForDisplay.map((stage: any) => {
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
    }),
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
              status: displayStatusUC as any,
              target: processedTask.target,
              description: processedTask.description,
              dispatchStatus: processedTask.dispatchStatus,
              startedAt: processedTask.startedAt,
              completedAt: processedTask.completedAt,
              estimatedCompletionAt: processedTask.estimatedCompletionAt,
              celeryTaskId: processedTask.celeryTaskId,
              workerNodeId: processedTask.workerNodeId,
              stages: { items: (commonTaskProps.stages && commonTaskProps.stages.length > 0) ? commonTaskProps.stages : lastStageItemsRef.current.map((stage: any) => {
                const isCompleted = (stage.status || '').toUpperCase() === 'COMPLETED';
                const isRunning = (stage.status || '').toUpperCase() === 'RUNNING';
                const isFailed = (stage.status || '').toUpperCase() === 'FAILED';
                return {
                  id: stage.id || stage.name,
                  key: stage.name,
                  label: stage.name,
                  color: isCompleted ? 'bg-primary' : (
                    isRunning ? 'bg-secondary' : (
                      isFailed ? 'bg-false' : 'bg-neutral'
                    )
                  ),
                  name: stage.name,
                  order: stage.order || 0,
                  status: (stage.status || 'PENDING') as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
                  processedItems: stage.processedItems,
                  totalItems: stage.totalItems,
                  statusMessage: stage.statusMessage,
                  startedAt: stage.startedAt,
                  completedAt: stage.completedAt,
                  estimatedCompletionAt: stage.estimatedCompletionAt,
                  completed: isCompleted
                };
              }) },
              errorMessage: commonTaskProps.errorMessage,
              errorDetails: commonTaskProps.errorDetails
          } : {
              id: displayId,
              accountId: '',
              type: displayType,
              command: task?.command,
              status: displayStatusUC as any,
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
                const stageItems: any[] = getStageItemsFromTask(task);
                
                
                const items = stageItems.map((stage: any) => ({
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
                  }));
                return { items: items.length > 0 ? items : (commonTaskProps.stages || []) };
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

  if (evaluationData.id === '6ee38d94-63b4-40ee-b53b-8131ab340a00') {
    console.log(`STAGE_TRACE: TaskDisplay about to render EvaluationTask for ${evaluationData.id}`);
  }

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
  
  // DEBUG: Log all memo calls for the evaluation that should be getting stage updates
  if (nextProps.evaluationData.id === 'ff9cecfb-b568-4715-bc7a-8be6c763028c') {
    console.log(`STAGE_TRACE: TaskDisplay memo called for ${nextProps.evaluationData.id} variant=${nextProps.variant} - checking for changes`);
    console.log(`STAGE_TRACE: TaskDisplay memo - task object changed: ${prevProps.task !== nextProps.task}, evaluationData object changed: ${prevProps.evaluationData !== nextProps.evaluationData}`);
  }
  
  // CRITICAL: Check if task stages have changed
  const prevStages = (prevProps.task as any)?.stages?.data?.items || (prevProps.task as any)?.stages?.items || [];
  const nextStages = (nextProps.task as any)?.stages?.data?.items || (nextProps.task as any)?.stages?.items || [];
  const stagesChanged = prevStages.length !== nextStages.length || 
    prevStages.some((stage: any, index: number) => {
      const nextStage: any = nextStages[index];
      return !nextStage || stage.name !== nextStage.name || stage.status !== nextStage.status;
    });
  
  if (stagesChanged) {
    console.log(`STAGE_TRACE: TaskDisplay memo ALLOWING re-render for ${nextProps.evaluationData.id} - stages changed`);
    console.log(`STAGE_TRACE: TaskDisplay memo stage details - prev: ${prevStages.map((s: any) => `${s.name}:${s.status}`).join(',')} next: ${nextStages.map((s: any) => `${s.name}:${s.status}`).join(',')}`);
    return false; // Allow re-render
  }
  
  // FORCE UPDATE for our problem evaluation to debug what's happening
  if (nextProps.evaluationData.id === 'ff9cecfb-b568-4715-bc7a-8be6c763028c') {
    console.log(`STAGE_TRACE: TaskDisplay memo FORCING re-render for ${nextProps.evaluationData.id} to debug`);
    return false; // Allow re-render
  }
  
  const shouldRerender = !(
    prevProps.variant === nextProps.variant &&
    prevProps.task?.id === nextProps.task?.id &&
    prevProps.evaluationData.status === nextProps.evaluationData.status &&
    prevProps.evaluationData.id === nextProps.evaluationData.id &&
    prevProps.evaluationData.processedItems === nextProps.evaluationData.processedItems &&
    prevProps.evaluationData.totalItems === nextProps.evaluationData.totalItems &&
    prevProps.evaluationData.accuracy === nextProps.evaluationData.accuracy &&
    prevProps.evaluationData.elapsedSeconds === nextProps.evaluationData.elapsedSeconds &&
    prevProps.evaluationData.estimatedRemainingSeconds === nextProps.evaluationData.estimatedRemainingSeconds &&
    prevProps.isSelected === nextProps.isSelected &&
    prevProps.selectedScoreResultId === nextProps.selectedScoreResultId &&
    prevProps.isFullWidth === nextProps.isFullWidth &&
    // CHECK FOR SCORECARD/SCORE CHANGES - CRITICAL FOR REALTIME UPDATES
    prevProps.evaluationData.scorecard?.name === nextProps.evaluationData.scorecard?.name &&
    prevProps.evaluationData.score?.name === nextProps.evaluationData.score?.name
  );
  
  if (shouldRerender) {
    console.log(`STAGE_TRACE: TaskDisplay memo ALLOWING re-render for ${nextProps.evaluationData.id} - other props changed`);
  }
  
  return !shouldRerender; // Return true to BLOCK re-render, false to ALLOW
}); 