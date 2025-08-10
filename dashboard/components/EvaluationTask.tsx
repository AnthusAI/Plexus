import React, { useRef, useState, useEffect, useMemo, useCallback } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { FlaskConical, Square, X, Split, ChevronLeft, MoreHorizontal, MessageSquareCode, Share, Trash2 } from 'lucide-react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { CardButton } from '@/components/CardButton'
import { toast } from '@/components/ui/use-toast'
import MetricsGauges from '@/components/MetricsGauges'
import { TaskStatus, type TaskStageConfig } from '@/components/ui/task-status'
import { ConfusionMatrix, type ConfusionMatrixData, type ConfusionMatrixRow } from '@/components/confusion-matrix'
import ClassDistributionVisualizer from '@/components/ClassDistributionVisualizer'
import PredictedClassDistributionVisualizer from '@/components/PredictedClassDistributionVisualizer'
import { EvaluationTaskScoreResults } from './EvaluationTaskScoreResults'
import type { Schema } from "@/amplify/data/resource"
import MetricsGaugesExplanation from '@/components/MetricsGaugesExplanation'
import { useResizeObserver } from '@/hooks/use-resize-observer'
import { BaseTaskData } from '@/types/base'
import { EvaluationListAccuracyBar } from '@/components/EvaluationListAccuracyBar'
import isEqual from 'lodash/isEqual'
import { ScoreResultComponent, ScoreResultData } from '@/components/ui/score-result'
import { cn } from '@/lib/utils'
import { Timestamp } from '@/components/ui/timestamp'

export interface EvaluationMetric {
  name: string
  value: number
  unit?: string
  maximum?: number
  priority: boolean
}

interface Distribution {
  label: string
  count: number
}

interface ScoreResult {
  id: string
  value: string | number
  confidence: number | null
  explanation: string | null
  metadata: {
    human_label: string | null
    correct: boolean
    human_explanation: string | null
    text: string | null
  }
  trace: any | null
  itemId: string | null
  itemIdentifiers?: Array<{
    name: string
    value: string
    url?: string
  }> | null
  feedbackItem: {
    editCommentValue: string | null
  } | null
}

interface TaskStage {
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

interface TaskData {
  id: string;
  accountId: string;
  type: string;
  status: string;
  target: string;
  command: string;
  completedAt?: string;
  startedAt?: string;
  dispatchStatus?: 'DISPATCHED';
  celeryTaskId?: string;
  workerNodeId?: string;
  description?: string;
  metadata?: any;
  createdAt?: string;
  estimatedCompletionAt?: string;
  errorMessage?: string;
  errorDetails?: string;
  currentStageId?: string;
  stages?: {
    items: TaskStage[];
    nextToken?: string | null;
  };
}

export interface EvaluationTaskData extends BaseTaskData {
  id: string
  title: string
  command?: string
  accuracy: number | null
  metrics: EvaluationMetric[]
  metricsExplanation?: string | null
  processedItems: number
  totalItems: number
  progress: number
  inferences: number
  cost: number | null
  status: string
  elapsedSeconds: number | null
  estimatedRemainingSeconds: number | null
  startedAt?: string | undefined
  errorMessage?: string
  errorDetails?: any | null
  confusionMatrix?: {
    matrix: number[][] | null
    labels: string[] | null
  } | null
  scoreGoal?: string | null
  datasetClassDistribution?: Array<Distribution>
  isDatasetClassDistributionBalanced?: boolean | null
  predictedClassDistribution?: Array<Distribution>
  isPredictedClassDistributionBalanced?: boolean | null
  scoreResults?: ScoreResult[]
  selectedScoreResult?: Schema['ScoreResult']['type'] | null
  task?: TaskData | null
  universalCode?: string | null
}

export interface EvaluationTaskProps extends Omit<BaseTaskProps<EvaluationTaskData>, 'variant'> {
  variant?: 'grid' | 'detail'
  // Added task output display support
  task: {
    id: string
    type: string
    scorecard: string
    score: string
    time: string
    summary?: string
    description?: string
    command?: string
    output?: string // Universal Code YAML output
    attachedFiles?: string[] // Array of S3 file keys for attachments
    stdout?: string // Task stdout output
    stderr?: string // Task stderr output
    data: EvaluationTaskData
    stages?: TaskStageConfig[]
    currentStageName?: string
    processedItems?: number
    totalItems?: number
    startedAt?: string
    estimatedCompletionAt?: string
    status?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
    dispatchStatus?: 'DISPATCHED'
    celeryTaskId?: string
    workerNodeId?: string
    completedAt?: string
    errorMessage?: string
    statusMessage?: string
  }
  selectedScoreResultId?: string | null
  onSelectScoreResult?: (id: string | null) => void
  extra?: boolean
  isSelected?: boolean
  commandDisplay?: 'hide' | 'show' | 'full'
  onShare?: () => void
  onDelete?: (evaluationId: string) => void
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = seconds % 60
  
  if (hours > 0) {
    return `${hours}h ${minutes}m ${remainingSeconds}s`
  }
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`
  }
  return `${remainingSeconds}s`
}

function computeIsBalanced(distribution: { label: string, count: number }[] | null | undefined): boolean | null {
  if (!distribution || distribution.length <= 1) return null
  
  const total = distribution.reduce((sum, item) => sum + item.count, 0)
  const expectedCount = total / distribution.length
  const tolerance = 0.2 // 20% tolerance
  
  return distribution.every(item => 
    Math.abs(item.count - expectedCount) <= expectedCount * tolerance
  )
}

const mapTaskStatus = (status: string | undefined | null): 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' => {
  if (!status) return 'PENDING';
  const upperStatus = status.toUpperCase();
  switch (upperStatus) {
    case 'PENDING':
    case 'RUNNING':
    case 'COMPLETED':
    case 'FAILED':
      return upperStatus;
    case 'DONE':
      return 'COMPLETED';
    case 'ERROR':
      return 'FAILED';
    default:
      return 'PENDING';
  }
}

const getStatusMessage = (data: EvaluationTaskData) => {
  // If we have task data with stages, use that
  if (data.task?.stages?.items?.length) {
    // If task failed, show the failed stage's message
    if (data.task.status === 'FAILED') {
      const failedStage = data.task.stages.items.find(stage => stage.status === 'FAILED')
      return failedStage?.statusMessage;
    }

    // If task completed, show the last stage's message
    if (data.task.status === 'COMPLETED') {
      return [...data.task.stages.items]
        .reverse()
        .find(stage => stage.statusMessage)?.statusMessage;
    }

    // If there's a running stage, use its message
    const runningStage = data.task.stages.items.find(stage => stage.status === 'RUNNING');
    if (runningStage?.statusMessage) {
      return runningStage.statusMessage;
    }

    // If no running stage message, find the last non-pending stage with a message
    const lastActiveStage = [...data.task.stages.items]
      .sort((a, b) => b.order - a.order)
      .find(stage => stage.status !== 'PENDING' && stage.statusMessage);
    if (lastActiveStage?.statusMessage) {
      return lastActiveStage.statusMessage;
    }

    // If all stages are pending, use the first stage's message
    if (data.task.stages.items.every(stage => stage.status === 'PENDING')) {
      const firstStage = [...data.task.stages.items].sort((a, b) => a.order - b.order)[0];
      return firstStage?.statusMessage;
    }
  }
  
  // Otherwise, construct a status message from the evaluation data
  if (data.status === 'COMPLETED') {
    return `Processed ${data.processedItems} of ${data.totalItems} items`;
  }
  if (data.status === 'FAILED') {
    return data.errorMessage || 'Task failed';
  }
  if (data.status === 'RUNNING') {
    return `Processing ${data.processedItems} of ${data.totalItems} items...`;
  }
  return undefined;
}

const GridContent = React.memo(({ data, extra, isSelected }: { 
  data: EvaluationTaskData; 
  extra?: boolean;
  isSelected?: boolean;
}) => {

  console.log(`🔍 TRACE_STAGES: GridContent render - ${data.id} - stages: ${data.task?.stages?.items?.map(s => `${s.name}:${s.status}`).join(',') || 'none'}`);

  const progress = useMemo(() => 
    data.processedItems && data.totalItems ? 
      Math.round((data.processedItems / data.totalItems) * 100) : 0
  , [data.processedItems, data.totalItems]);
  
  const accuracy = data.accuracy ?? 0;

  // Use already-transformed score results directly
  const parsedScoreResults = useMemo(() => {
    // data.scoreResults is already transformed by transformEvaluation
    const scoreResults = data.scoreResults || [];
    
    if (!scoreResults.length) {
      return [];
    }
    
    // The results are already transformed, just map them to ScoreResultData format
    return scoreResults.map((result: any) => ({
      id: result.id,
      value: result.value,
      confidence: result.confidence,
      explanation: result.explanation,
      metadata: result.metadata || {
        human_label: null,
        correct: false,
        human_explanation: null,
        text: null
      },
      trace: result.trace,
      itemId: result.itemId,
      itemIdentifiers: result.itemIdentifiers,
      feedbackItem: result.feedbackItem
    }));
  }, [data.scoreResults]);


  const stages = useMemo(() => {
    const stageItems = data.task?.stages?.items || [];
    
    console.log(`🔍 TRACE_STAGES: GridContent useMemo stages - ${data.id} - creating TaskStatus configs for: ${stageItems.map(s => `${s.name}:${s.status}`).join(',')}`);
    
    return stageItems.map(stage => ({
      key: stage.name,
      label: stage.name,
      color: stage.name === 'Processing' ? 'bg-secondary' : (
        stage.status === 'COMPLETED' || stage.status === 'RUNNING' ? 'bg-primary' :
        stage.status === 'FAILED' ? 'bg-false' :
        'bg-neutral'
      ),
      name: stage.name,
      order: stage.order,
      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
      processedItems: stage.processedItems,
      totalItems: stage.totalItems,
      statusMessage: stage.statusMessage,
      startedAt: stage.startedAt || undefined,
      completedAt: stage.completedAt || undefined,
      estimatedCompletionAt: stage.estimatedCompletionAt || undefined
    }));
  }, [
    data.task?.stages?.items, 
    data.id,
    // Force recomputation when any stage object changes by including a hash of stage data
    JSON.stringify(data.task?.stages?.items?.map(s => ({ 
      name: s.name, 
      status: s.status, 
      processedItems: s.processedItems, 
      totalItems: s.totalItems,
      statusMessage: s.statusMessage,
      startedAt: s.startedAt,
      completedAt: s.completedAt
    })))
  ]);

  const taskStatus = useMemo(() => {
    const statusObj = {
      showStages: true,
      status: mapTaskStatus(data.task?.status || data.status),
      stageConfigs: stages,
      stages,
      processedItems: data.processedItems,
      totalItems: data.totalItems,
      startedAt: data.task?.startedAt || data.startedAt || undefined,
      completedAt: data.task?.completedAt || undefined,
      estimatedCompletionAt: data.task?.estimatedCompletionAt || undefined,
      errorMessage: data.task?.errorMessage || data.errorMessage || undefined,
      command: data.task?.command || data.command,
      statusMessage: getStatusMessage(data),
      variant: 'grid' as const,
      extra,
      isSelected,
      commandDisplay: 'hide' as const,
      elapsedSeconds: data.elapsedSeconds,
      estimatedRemainingSeconds: data.estimatedRemainingSeconds
    };
    
    console.log(`🔍 TRACE_STAGES: GridContent useMemo taskStatus - ${data.id} - final TaskStatus props stages: ${statusObj.stages.map(s => `${s.name}:${s.status}`).join(',')}`);
    
    return statusObj;
  }, [
    data.task?.status,
    data.status,
    stages,
    data.processedItems,
    data.totalItems,
    data.task?.startedAt,
    data.startedAt,
    data.task?.completedAt,
    data.task?.estimatedCompletionAt,
    data.task?.errorMessage,
    data.errorMessage,
    data.task?.command,
    data.command,
    extra,
    isSelected,
    data.elapsedSeconds,
    data.estimatedRemainingSeconds,
    data.id
  ]);

  return (
    <div className="space-y-2">
      <TaskStatus 
        {...taskStatus} 
        key={`${data.id}-${JSON.stringify(stages.map(s => ({ name: s.name, status: s.status, processedItems: s.processedItems })))}`}
      />
      {extra && (
        <EvaluationListAccuracyBar 
          progress={progress}
          accuracy={accuracy}
          isSelected={isSelected}
        />
      )}
    </div>
  )
}, (prevProps, nextProps) => {
  const prevStagesList = prevProps.data.task?.stages?.items || [];
  const nextStagesList = nextProps.data.task?.stages?.items || [];
  const stagesChanged = (
    prevStagesList.length !== nextStagesList.length ||
    prevStagesList.some((s, i) => {
      const ns = nextStagesList[i];
      return !ns || s.name !== ns.name || s.status !== ns.status || s.processedItems !== ns.processedItems || s.totalItems !== ns.totalItems;
    })
  );

  const progressChanged = (
    prevProps.data.processedItems !== nextProps.data.processedItems ||
    prevProps.data.totalItems !== nextProps.data.totalItems ||
    prevProps.data.accuracy !== nextProps.data.accuracy ||
    prevProps.data.status !== nextProps.data.status ||
    prevProps.data.elapsedSeconds !== nextProps.data.elapsedSeconds ||
    prevProps.data.estimatedRemainingSeconds !== nextProps.data.estimatedRemainingSeconds
  );

  const otherChanged = (
    prevProps.extra !== nextProps.extra ||
    prevProps.isSelected !== nextProps.isSelected ||
    !isEqual(prevProps.data.scoreResults, nextProps.data.scoreResults)
  );

  const allow = stagesChanged || progressChanged || otherChanged;
  if (allow) {
    console.log(`🔍 TRACE_STAGES: GridContent memo ALLOWING re-render - ${nextProps.data.id} - stagesChanged=${stagesChanged} progressChanged=${progressChanged} otherChanged=${otherChanged}`);
    return false;
  }
  console.log(`🔍 TRACE_STAGES: GridContent memo BLOCKING re-render - ${nextProps.data.id} - no changes`);
  return true;
});

interface ParsedScoreResult extends ScoreResultData {}

function parseScoreResult(result: any): ParsedScoreResult {

  if (!result) {
    console.warn('Received null or undefined score result');
    return {
      id: '',
      value: '',
      confidence: null,
      explanation: null,
      metadata: {
        human_label: null,
        correct: false,
        human_explanation: null,
        text: null
      },
      trace: null,
      itemId: null,
      itemIdentifiers: null,
      feedbackItem: null
    };
  }

  // Cache parsed metadata to prevent repeated parsing
  let parsedMetadata = result._parsedMetadata;
  if (!parsedMetadata) {
    try {
      let metadata = result.metadata;
      if (typeof metadata === 'string') {
        try {
          metadata = JSON.parse(metadata);
          if (typeof metadata === 'string') {
            metadata = JSON.parse(metadata);
          }
        } catch (e) {
          console.error('Error parsing metadata string:', e);
          metadata = {};
        }
      }
      parsedMetadata = metadata || {};
      // Cache the parsed result
      result._parsedMetadata = parsedMetadata;
    } catch (e) {
      console.error('Error processing metadata:', e);
      parsedMetadata = {};
    }
  }


  // Extract results from nested structure if present
  const firstResultKey = parsedMetadata?.results ? 
    Object.keys(parsedMetadata.results)[0] : null
  const scoreResult = firstResultKey && parsedMetadata.results ? 
    parsedMetadata.results[firstResultKey] : null

  // Ensure we have valid values for all fields
  const id = result.id || '';
  const value = String(result.value || scoreResult?.value || '');
  const confidence = result.confidence ?? scoreResult?.confidence ?? null;
  const explanation = result.explanation ?? scoreResult?.explanation ?? null;
  const trace = result.trace ?? scoreResult?.trace ?? null;
  const humanLabel = scoreResult?.metadata?.human_label ?? parsedMetadata.human_label ?? null;
  const correct = Boolean(scoreResult?.metadata?.correct ?? parsedMetadata.correct);
  const humanExplanation = scoreResult?.metadata?.human_explanation ?? parsedMetadata.human_explanation ?? null;
  const text = scoreResult?.metadata?.text ?? parsedMetadata.text ?? null;
  const itemId = result.itemId || parsedMetadata.item_id?.toString() || null;

  // Parse feedbackItem data
  const feedbackItem = result.feedbackItem ? {
    editCommentValue: result.feedbackItem.editCommentValue || null
  } : null;



  return {
    id,
    value,
    confidence,
    explanation,
    metadata: {
      human_label: humanLabel,
      correct,
      human_explanation: humanExplanation,
      text
    },
    trace,
    itemId,
    itemIdentifiers: result.itemIdentifiers || null,
    feedbackItem
  };
}

const DetailContent = React.memo(({ 
  data, 
  isFullWidth,
  metrics,
  metricsVariant,
  selectedScoreResultId,
  onSelectScoreResult,
  extra,
  isSelected,
  commandDisplay = 'show',
  onCommandDisplayChange
}: { 
  data: EvaluationTaskData
  isFullWidth: boolean
  metrics: any[]
  metricsVariant: 'grid' | 'detail'
  selectedScoreResultId?: string | null
  onSelectScoreResult?: (id: string | null) => void
  extra?: boolean
  isSelected?: boolean
  commandDisplay?: 'hide' | 'show' | 'full'
  onCommandDisplayChange?: (display: 'show' | 'full') => void
}) => {
  // Force isSelected to true in detail mode
  const effectiveIsSelected = true;


  const [containerWidth, setContainerWidth] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const [selectedPredictedActual, setSelectedPredictedActual] = useState<{
    predicted: string | null
    actual: string | null
  }>({ predicted: null, actual: null })

  // Find the selected score result from the already-transformed results
  const selectedScoreResult = useMemo(() => {
    const scoreResults = data.scoreResults || [];
    return selectedScoreResultId ? scoreResults.find((r: any) => r.id === selectedScoreResultId) : null;
  }, [data.scoreResults, selectedScoreResultId]);


  // Use already-transformed score results directly
  const parsedScoreResults = useMemo(() => {
    // data.scoreResults is already transformed by transformEvaluation
    const scoreResults = data.scoreResults || [];
    
    if (!scoreResults.length) {
      return [];
    }
    
    // The results are already transformed, just map them to ScoreResultData format
    return scoreResults.map((result: any) => ({
      id: result.id,
      value: result.value,
      confidence: result.confidence,
      explanation: result.explanation,
      metadata: result.metadata || {
        human_label: null,
        correct: false,
        human_explanation: null,
        text: null
      },
      trace: result.trace,
      itemId: result.itemId,
      itemIdentifiers: result.itemIdentifiers,
      feedbackItem: result.feedbackItem
    }));
  }, [data.scoreResults]);

  useResizeObserver(containerRef, (entry) => {
    setContainerWidth(entry.contentRect.width)
  })

  const handleActualLabelSelect = (label: string) => {
    setSelectedPredictedActual(prev => ({
      ...prev,
      actual: prev.actual === label ? null : label,
      predicted: null
    }))
  }

  const handlePredictedLabelSelect = (label: string) => {
    setSelectedPredictedActual(prev => ({
      ...prev,
      predicted: prev.predicted === label ? null : label,
      actual: null
    }))
  }

  // Add logging for display conditions
  const isWideEnoughForTwo = containerWidth >= 800
  const isWideEnoughForThree = containerWidth >= 1180 && isFullWidth
  const showAsColumns = isWideEnoughForTwo
  
  // Modify the panel visibility logic to prioritize the selected score result
  const showResultDetail = selectedScoreResult !== null
  const showResultsList = parsedScoreResults.length > 0
  
  // In narrow view with a selected result, ONLY show the score result detail
  const showScoreResultInNarrowView = !isWideEnoughForTwo && showResultDetail
  
  // Only show main panel if we're not in narrow view with a selected result
  const showMainPanel = isWideEnoughForThree || 
                        (isWideEnoughForTwo && (!showResultDetail || !showResultsList)) || 
                        (!isWideEnoughForTwo && !showResultDetail) // Only show main panel in narrow view if no result selected

  console.log('DetailContent render conditions:', {
    containerWidth,
    isWideEnoughForTwo,
    isWideEnoughForThree,
    hasScoreResults: !!data.scoreResults?.length,
    parsedResultCount: parsedScoreResults.length,
    showMainPanel,
    showResultsList,
    showResultDetail,
    showScoreResultInNarrowView,
    showAsColumns,
    selectedScoreResult: selectedScoreResult?.id
  });

  const handleScoreResultSelect = (result: Schema['ScoreResult']['type']) => {
    console.log('Score result selected:', result.id);
    onSelectScoreResult?.(result.id)
  }

  const handleScoreResultClose = () => {
    console.log('Score result detail closed');
    onSelectScoreResult?.(null)
  }

  const transformedConfusionMatrixData = useMemo((): ConfusionMatrixData | null => {
    const cmInput = data.confusionMatrix;
    if (!cmInput || !cmInput.matrix || !cmInput.labels || cmInput.matrix.length === 0 || cmInput.labels.length === 0) {
      return null;
    }
    // Basic check: matrix rows should match labels length for a square matrix using labels for both axes
    if (cmInput.matrix.length !== cmInput.labels.length) {
        console.warn('Confusion matrix: matrix rows length does not match labels length.');
        // This might indicate an issue, but ConfusionMatrix component itself has more robust validation.
        // For now, we let it pass to the component for its validation.
    }
    if (cmInput.labels.some(l => l === '')) {
        console.warn('EvaluationTask: Input confusion matrix labels contain empty strings. This can lead to errors.');
    }

    try {
      const newMatrix: ConfusionMatrixRow[] = cmInput.matrix.map((row, actualIndex) => {
        const actualClassLabel = cmInput.labels![actualIndex];
        if (actualClassLabel === undefined) {
          // Should not happen if matrix.length === labels.length and labels is not sparse
          throw new Error(`Label not found for actual index ${actualIndex}`);
        }
        const predictedClassCounts: { [predictedClassLabel: string]: number } = {};
        row.forEach((count, predictedIndex) => {
          const predictedClassLabel = cmInput.labels![predictedIndex];
          if (predictedClassLabel === undefined) {
            throw new Error(`Label not found for predicted index ${predictedIndex}`);
          }
          // It's important that predictedClassLabel is a valid key (non-empty string)
          // The ConfusionMatrix component will validate if these labels exist in its main `labels` prop.
          predictedClassCounts[predictedClassLabel] = count;
        });
        return {
          actualClassLabel: actualClassLabel, // Use the label as is, even if it's ""
          predictedClassCounts,
        };
      });
      return {
        matrix: newMatrix,
        labels: cmInput.labels, // Pass original labels, ConfusionMatrix will validate them
      };
    } catch (error) {
      console.error("Error transforming confusion matrix data:", error);
      return null; // Or a specific error structure if ConfusionMatrix can handle it
    }
  }, [data.confusionMatrix]);

  return (
    <div 
      ref={containerRef}
      className="w-full p-3 min-w-[300px] h-full overflow-y-auto"
    >
      <div className={`overflow-visible ${showAsColumns ? 'grid gap-4' : 'space-y-4'} ${showAsColumns ? 'h-full' : 'h-auto'}`} 
        style={{
          gridTemplateColumns: isWideEnoughForThree 
            ? selectedScoreResult ? '1fr 1fr 1fr' : '1fr 1fr'
            : isWideEnoughForTwo
              ? '1fr 1fr'    // Always equal width for two panels
              : '1fr'          // Show only one panel
        }}
      >
        {/* When in narrow view and a score result is selected, ONLY show the score result detail */}
        {showScoreResultInNarrowView && selectedScoreResult && (
          <div className="w-full h-full flex flex-col overflow-hidden">
            <div className="flex-1 overflow-hidden">
              <ScoreResultComponent
                result={{
                  id: selectedScoreResult.id,
                  value: String(selectedScoreResult.value),
                  confidence: selectedScoreResult.confidence,
                  explanation: selectedScoreResult.explanation,
                  metadata: selectedScoreResult.metadata || {
                    human_label: null,
                    correct: false,
                    human_explanation: null,
                    text: null
                  },
                  trace: selectedScoreResult.trace,
                  itemId: selectedScoreResult.itemId,
                  itemIdentifiers: (selectedScoreResult as any).itemIdentifiers,
                  feedbackItem: (selectedScoreResult as any).feedbackItem || null
                }}
                variant="detail"
                onClose={handleScoreResultClose}
              />
            </div>
          </div>
        )}

        {/* Only show main panel if not showing score result in narrow view */}
        {showMainPanel && (
          <div 
            className={`w-full ${showAsColumns ? 'h-full' : 'h-auto'} flex flex-col overflow-visible`}
          >
            <div className={`${showAsColumns ? 'flex-1' : ''} overflow-visible max-h-full`}>
              <div className="space-y-3 p-1 overflow-visible">
                <div className="mb-3">
                  <TaskStatus
                    key={`detail-${data.id}-${JSON.stringify(data.task?.stages?.items?.map(s => ({ name: s.name, status: s.status, processedItems: s.processedItems })))}`}
                    variant="detail"
                    showStages={true}
                    status={mapTaskStatus(data.task?.status || data.status)}
                    stageConfigs={data.task?.stages?.items?.map(stage => ({
                      key: stage.name,
                      label: stage.name,
                      color: stage.name === 'Processing' ? 'bg-secondary' : (
                        stage.status === 'COMPLETED' || stage.status === 'RUNNING' ? 'bg-primary' :
                        stage.status === 'FAILED' ? 'bg-false' :
                        'bg-neutral'
                      ),
                      name: stage.name,
                      order: stage.order,
                      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
                      processedItems: stage.processedItems,
                      totalItems: stage.totalItems,
                      statusMessage: stage.statusMessage,
                      completed: stage.status === 'COMPLETED',
                      startedAt: stage.startedAt || undefined,
                      completedAt: stage.completedAt || undefined,
                      estimatedCompletionAt: stage.estimatedCompletionAt || undefined
                    })) || []}
                    stages={data.task?.stages?.items?.map(stage => ({
                      key: stage.name,
                      label: stage.name,
                      color: stage.name === 'Processing' ? 'bg-secondary' : (
                        stage.status === 'COMPLETED' || stage.status === 'RUNNING' ? 'bg-primary' :
                        stage.status === 'FAILED' ? 'bg-false' :
                        'bg-neutral'
                      ),
                      name: stage.name,
                      order: stage.order,
                      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
                      processedItems: stage.processedItems,
                      totalItems: stage.totalItems,
                      statusMessage: stage.statusMessage,
                      startedAt: stage.startedAt || undefined,
                      completedAt: stage.completedAt || undefined,
                      estimatedCompletionAt: stage.estimatedCompletionAt || undefined
                    })) || []}
                    processedItems={data.processedItems}
                    totalItems={data.totalItems}
                    startedAt={data.task?.startedAt || data.startedAt || undefined}
                    completedAt={data.task?.completedAt || undefined}
                    estimatedCompletionAt={data.task?.estimatedCompletionAt || undefined}
                    errorMessage={data.task?.errorMessage || data.errorMessage || undefined}
                    command={data.task?.command || data.command}
                    statusMessage={getStatusMessage(data)}
                    truncateMessages={true}
                    extra={extra}
                    isSelected={effectiveIsSelected}
                    commandDisplay={commandDisplay}
                    onCommandDisplayChange={onCommandDisplayChange}
                    elapsedSeconds={data.elapsedSeconds}
                    estimatedRemainingSeconds={data.estimatedRemainingSeconds}
                  />
                </div>

                <div className="mb-3">
                  <ClassDistributionVisualizer
                    data={data.datasetClassDistribution}
                    isBalanced={data.isDatasetClassDistributionBalanced}
                    onLabelSelect={handleActualLabelSelect}
                  />
                </div>

                <div className="mb-3">
                  <PredictedClassDistributionVisualizer
                    data={data.predictedClassDistribution}
                    onLabelSelect={handlePredictedLabelSelect}
                  />
                </div>

                <div className="mb-3">
                  <MetricsGaugesExplanation
                    explanation={data.metricsExplanation}
                    goal={data.scoreGoal}
                  />
                </div>

                <MetricsGauges 
                  gauges={metrics} 
                  variant="detail"
                />

                {/* Confusion Matrix Section */}
                {transformedConfusionMatrixData && (
                  <div className="mt-4 rounded-md bg-background/30 w-full" style={{ overflow: 'visible' }}>
                    <ConfusionMatrix
                      data={transformedConfusionMatrixData} // Pass the transformed data object
                      onSelectionChange={setSelectedPredictedActual} // Reverted to original handler
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Only show score results list if not showing score result in narrow view */}
        {showResultsList && !showScoreResultInNarrowView && (
          <div className={`w-full ${showAsColumns ? 'h-full' : 'h-[500px] mt-6'} flex flex-col overflow-hidden`}>
            <div className="h-full overflow-y-auto">
              <EvaluationTaskScoreResults 
                results={parsedScoreResults} 
                accuracy={data.accuracy ?? 0}
                selectedPredictedValue={selectedPredictedActual.predicted}
                selectedActualValue={selectedPredictedActual.actual}
                onResultSelect={handleScoreResultSelect}
                selectedScoreResult={selectedScoreResult}
              />
            </div>
          </div>
        )}

        {/* Only show the score result detail in column layout if not already showing it in narrow view */}
        {showResultDetail && !showScoreResultInNarrowView && selectedScoreResult && (
          <div className={`w-full ${showAsColumns ? 'h-full' : 'h-full'} flex flex-col overflow-hidden`}>
            <div className="flex-1 overflow-hidden">
              <ScoreResultComponent
                result={{
                  id: selectedScoreResult.id,
                  value: String(selectedScoreResult.value),
                  confidence: selectedScoreResult.confidence,
                  explanation: selectedScoreResult.explanation,
                  metadata: selectedScoreResult.metadata || {
                    human_label: null,
                    correct: false,
                    human_explanation: null,
                    text: null
                  },
                  trace: selectedScoreResult.trace,
                  itemId: selectedScoreResult.itemId,
                  itemIdentifiers: (selectedScoreResult as any).itemIdentifiers,
                  feedbackItem: (selectedScoreResult as any).feedbackItem || null
                }}
                variant="detail"
                onClose={handleScoreResultClose}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}, (prevProps, nextProps) => {
  // Add logging for memo comparison
  const stagesChanged = (() => {
    const prevStages = prevProps.data.task?.stages?.items || [];
    const nextStages = nextProps.data.task?.stages?.items || [];
    if (prevStages.length !== nextStages.length) return true;
    return prevStages.some((s, i) => {
      const ns = nextStages[i];
      return !ns || s.name !== ns.name || s.status !== ns.status || s.processedItems !== ns.processedItems || s.totalItems !== ns.totalItems;
    });
  })();

  const shouldUpdate = 
    prevProps.extra !== nextProps.extra || 
    prevProps.isSelected !== nextProps.isSelected ||
    prevProps.selectedScoreResultId !== nextProps.selectedScoreResultId ||
    prevProps.isFullWidth !== nextProps.isFullWidth ||
    prevProps.commandDisplay !== nextProps.commandDisplay ||
    // progress / metrics / status changes
    prevProps.data.processedItems !== nextProps.data.processedItems ||
    prevProps.data.totalItems !== nextProps.data.totalItems ||
    prevProps.data.accuracy !== nextProps.data.accuracy ||
    prevProps.data.status !== nextProps.data.status ||
    prevProps.data.elapsedSeconds !== nextProps.data.elapsedSeconds ||
    prevProps.data.estimatedRemainingSeconds !== nextProps.data.estimatedRemainingSeconds ||
    stagesChanged ||
    // score results list changes
    prevProps.data.scoreResults?.length !== nextProps.data.scoreResults?.length ||
    !isEqual(prevProps.data.scoreResults, nextProps.data.scoreResults);

  console.log('DetailContent memo comparison:', {
    shouldUpdate,
    prevScoreResultCount: prevProps.data.scoreResults?.length ?? 0,
    nextScoreResultCount: nextProps.data.scoreResults?.length ?? 0,
    scoreResultsChanged: !isEqual(prevProps.data.scoreResults, nextProps.data.scoreResults),
    prevFirstResult: prevProps.data.scoreResults?.[0],
    nextFirstResult: nextProps.data.scoreResults?.[0]
  });

  return !shouldUpdate;
});

// Wrap the component with React.memo to prevent unnecessary re-renders
const EvaluationTask = React.memo(function EvaluationTaskComponent({ 
  variant = 'grid',
  task,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  selectedScoreResultId,
  onSelectScoreResult,
  extra,
  isSelected,
  commandDisplay: initialCommandDisplay = 'hide',
  onShare,
  onDelete,
  ...restProps
}: EvaluationTaskProps) {
  const [commandDisplay, setCommandDisplay] = useState(initialCommandDisplay);

  const data = task.data ?? {} as EvaluationTaskData
  
  console.log(`🔍 TRACE_STAGES: EvaluationTask render - ${data.id} - stages: ${data.task?.stages?.items?.map(s => `${s.name}:${s.status}`).join(',') || 'none'}`);
  

  // Add more detailed logging for incoming data

  // Function to generate universal YAML code for evaluation
  const generateUniversalCode = useCallback((evaluationData: EvaluationTaskData) => {
    const yamlContent = `# Universal Code Snippet - Evaluation Results
# Generated for: ${evaluationData.title || 'Evaluation'}
# Type: Accuracy Evaluation
# Date: ${new Date().toISOString()}

evaluation:
  id: "${evaluationData.id}"
  type: "${task.type || 'Accuracy Evaluation'}"
  scorecard: "${task.scorecard || ''}"
  score: "${task.score || ''}"
  status: "${evaluationData.status}"
  
  # Performance Metrics
  accuracy: ${evaluationData.accuracy || 0}
  processed_items: ${evaluationData.processedItems || 0}
  total_items: ${evaluationData.totalItems || 0}
  inferences: ${evaluationData.inferences || 0}
  cost: ${evaluationData.cost || 0}
  
  # Timing Information
  started_at: "${evaluationData.startedAt || ''}"
  elapsed_seconds: ${evaluationData.elapsedSeconds || 0}
  estimated_remaining_seconds: ${evaluationData.estimatedRemainingSeconds || 0}
  
  # Additional Metrics
  metrics:${evaluationData.metrics?.map(metric => `
    - name: "${metric.name}"
      value: ${metric.value}
      unit: "${metric.unit || ''}"
      priority: ${metric.priority || false}`).join('') || ''}
  
  # Error Information
  error_message: "${evaluationData.errorMessage || ''}"
  
  # Score Results Summary
  score_results_count: ${evaluationData.scoreResults?.length || 0}
  
  # Class Distribution
  dataset_balanced: ${evaluationData.isDatasetClassDistributionBalanced || false}
  predicted_balanced: ${evaluationData.isPredictedClassDistributionBalanced || false}

# Context: This YAML contains evaluation results and metrics for analysis by humans, AI models, and other systems.
# Usage: Can be used for reporting, monitoring, or further automated analysis.
`;
    return yamlContent;
  }, [task.type, task.scorecard, task.score]);

  // Function to handle copying universal code to clipboard
  const handleGetCode = useCallback(async () => {
    try {
      const universalCode = data.universalCode || generateUniversalCode(data);
      await navigator.clipboard.writeText(universalCode);
      toast({
        description: "Copied Universal Code to clipboard",
        duration: 2000,
      });
    } catch (error) {
      console.error('Failed to copy universal code:', error);
      toast({
        variant: "destructive",
        description: "Failed to copy code to clipboard",
        duration: 2000,
      });
    }
  }, [data, generateUniversalCode]);

  const metrics = useMemo(() => 
    variant === 'detail' ? 
      (data.metrics ?? []).map(metric => ({
        value: metric.value,
        label: metric.name,
        information: getMetricInformation(metric.name),
        maximum: metric.maximum ?? 100,
        unit: metric.unit ?? '%',
        priority: metric.priority
      }))
      : [
        {
          value: data.accuracy ?? undefined,
          label: 'Accuracy',
          backgroundColor: 'var(--gauge-background)',
          priority: true
        }
      ]
  , [variant, data.metrics, data.accuracy])

  const headerContent = useMemo(() => (
    variant === 'detail' ? (
      <div className="flex items-center space-x-2">
        <DropdownMenu>
          <DropdownMenuTrigger>
            <CardButton
              icon={MoreHorizontal}
              onClick={() => {
                console.log('MoreHorizontal button clicked - dropdown should open');
              }}
            />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => {
              console.log('Get Code menu item selected');
              handleGetCode();
            }}>
              <MessageSquareCode className="mr-2 h-4 w-4" />
              Get Code
            </DropdownMenuItem>
            {onShare && (
              <DropdownMenuItem onSelect={() => {
                console.log('Share menu item selected');
                onShare();
              }}>
                <Share className="mr-2 h-4 w-4" />
                Share
              </DropdownMenuItem>
            )}
            {onDelete && (
              <DropdownMenuItem onSelect={() => {
                console.log('Delete menu item selected');
                onDelete(data.id);
              }}>
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
        {typeof onToggleFullWidth === 'function' && (
          <CardButton
            icon={Square}
            onClick={onToggleFullWidth}
          />
        )}
        {typeof onClose === 'function' && (
          <CardButton
            icon={X}
            onClick={() => {
              console.log('EvaluationTask: X button clicked, calling onClose function');
              onClose();
            }}
          />
        )}
      </div>
    ) : null
  ), [variant, onToggleFullWidth, onClose, handleGetCode])

  const taskData = task.data?.task as TaskData | undefined;

  const taskWithDefaults = useMemo(() => ({
    id: task.id,
    type: task.type ? task.type.split(' ').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    ).join(' ') : 'Unknown',
    scorecard: task.scorecard,
    score: task.score,
    time: task.time,
    description: variant === 'detail' ? undefined : task.summary,
    data: task.data,
    command: taskData?.command,
    stages: taskData?.stages?.items?.map(stage => ({
      key: stage.name,
      label: stage.name,
      color: stage.name === 'Processing' ? 'bg-secondary' : (
        stage.status === 'COMPLETED' || stage.status === 'RUNNING' ? 'bg-primary' :
        stage.status === 'FAILED' ? 'bg-false' :
        'bg-neutral'
      ),
      name: stage.name,
      order: stage.order,
      status: mapTaskStatus(stage.status),
      processedItems: stage.processedItems,
      totalItems: stage.totalItems,
      statusMessage: stage.statusMessage
    })) || [],
    currentStageName: taskData?.currentStageId || undefined,
    processedItems: task.data?.processedItems,
    totalItems: task.data?.totalItems,
    startedAt: taskData?.startedAt || task.data?.startedAt || undefined,
    estimatedCompletionAt: taskData?.estimatedCompletionAt || undefined,
    status: mapTaskStatus(taskData?.status || task.data?.status),
    dispatchStatus: taskData?.dispatchStatus,
    celeryTaskId: taskData?.celeryTaskId,
    workerNodeId: taskData?.workerNodeId,
    completedAt: taskData?.completedAt || undefined,
    errorMessage: taskData?.errorMessage || task.data?.errorMessage || undefined
  }), [task, taskData, variant]);

  // Type assertion to ensure all properties match BaseTaskProps
  const typedTask = {
    ...taskWithDefaults,
    startedAt: taskWithDefaults.startedAt || undefined,
    completedAt: taskWithDefaults.completedAt || undefined,
    estimatedCompletionAt: taskWithDefaults.estimatedCompletionAt || undefined,
    errorMessage: taskWithDefaults.errorMessage || undefined,
    status: taskWithDefaults.status,
    dispatchStatus: taskWithDefaults.dispatchStatus,
    celeryTaskId: taskWithDefaults.celeryTaskId,
    workerNodeId: taskWithDefaults.workerNodeId,
    currentStageName: taskWithDefaults.currentStageName,
    stages: taskWithDefaults.stages
  } as unknown as BaseTaskProps['task']

  // Update TaskStatus components to handle null values
  const renderTaskStatus = (data: EvaluationTaskData) => {
    const taskStages = data.task?.stages?.items?.map(stage => ({
      key: stage.name,
      label: stage.name,
      color: stage.name === 'Processing' ? 'bg-secondary' : (
        stage.status === 'COMPLETED' || stage.status === 'RUNNING' ? 'bg-primary' :
        stage.status === 'FAILED' ? 'bg-false' :
        'bg-neutral'
      ),
      name: stage.name,
      order: stage.order,
      status: mapTaskStatus(stage.status),
      processedItems: stage.processedItems,
      totalItems: stage.totalItems,
      statusMessage: stage.statusMessage,
      startedAt: stage.startedAt || undefined,
      completedAt: stage.completedAt || undefined,
      estimatedCompletionAt: stage.estimatedCompletionAt || undefined
    })) || []

    const taskStatus = {
      showStages: true,
      status: mapTaskStatus(data.task?.status || data.status),
      stageConfigs: taskStages,
      stages: taskStages,
      processedItems: data.processedItems,
      totalItems: data.totalItems,
      startedAt: data.task?.startedAt || data.startedAt || undefined,
      completedAt: data.task?.completedAt || undefined,
      estimatedCompletionAt: data.task?.estimatedCompletionAt || undefined,
      errorMessage: data.task?.errorMessage || data.errorMessage || undefined,
      command: data.task?.command || data.command,
      statusMessage: data.task?.stages?.items?.find(s => s.status === 'RUNNING')?.statusMessage || undefined,
      isSelected,
      elapsedSeconds: data.elapsedSeconds,
      estimatedRemainingSeconds: data.estimatedRemainingSeconds
    } as const

    return <TaskStatus {...taskStatus} />
  }

  return (
    <Task
      variant={variant}
      task={typedTask}
      onClick={onClick}
      controlButtons={controlButtons}
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      extra={extra}
      isSelected={isSelected}
      commandDisplay={commandDisplay}
      {...restProps}
      renderHeader={(props) => (
        <div className={cn(
          "space-y-1.5 p-0 flex flex-col items-start w-full max-w-full",
          variant === 'detail' && "px-1"
        )}>
          <div className="flex justify-between items-start w-full max-w-full gap-3 overflow-hidden">
            <div className="flex flex-col pb-1 leading-none min-w-0 flex-1 overflow-hidden">
              {variant === 'detail' && (
                <div className="flex items-center gap-2 mb-3">
                  <FlaskConical className="h-5 w-5 text-muted-foreground" />
                  <span className="text-lg font-semibold text-muted-foreground">{props.task.type}</span>
                </div>
              )}
              {props.task.name && (
                <div className="font-semibold text-sm truncate">{props.task.name}</div>
              )}
              {props.task.description && (
                <div className={`text-sm text-muted-foreground ${variant === 'detail' ? '' : 'truncate'}`}>
                  {props.task.description}
                </div>
              )}
              {props.task.scorecard && props.task.scorecard.trim() !== '' && (
                <div className="font-semibold text-sm truncate">{props.task.scorecard}</div>
              )}
              {props.task.score && props.task.score.trim() !== '' && (
                <div className="font-semibold text-sm truncate">{props.task.score}</div>
              )}
              <Timestamp time={props.task.time} variant="relative" />
            </div>
            <div className="flex flex-col items-end flex-shrink-0">
              {variant === 'grid' ? (
                <div className="flex flex-col items-center gap-1">
                  <div className="text-muted-foreground">
                    <FlaskConical className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
                  </div>
                  <div className="text-xs text-muted-foreground text-center">
                    {(() => {
                      const [firstWord, ...restWords] = props.task.type.split(/\s+/);
                      return (
                        <>
                          {firstWord}<br />
                          {restWords.join(' ')}
                        </>
                      );
                    })()}
                  </div>
                </div>
              ) : (
                <div className="flex gap-2">
                  {headerContent}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      renderContent={(props) => {
        // Add logging for content rendering decision

        return (
          <TaskContent {...props} hideTaskStatus={true}>
            {variant === 'grid' ? (
              <GridContent data={data} extra={extra} isSelected={isSelected} />
            ) : (
              <DetailContent 
                data={data}
                isFullWidth={isFullWidth ?? false}
                metrics={metrics}
                metricsVariant="detail"
                selectedScoreResultId={selectedScoreResultId}
                onSelectScoreResult={onSelectScoreResult}
                extra={extra}
                isSelected={isSelected}
                commandDisplay={commandDisplay}
                onCommandDisplayChange={setCommandDisplay}
              />
            )}
          </TaskContent>
        );
      }}
    />
  )
}, (prevProps, nextProps) => {
  // Custom comparison function to prevent unnecessary re-renders
  // Only re-render if these specific props change
  const stageComparison = isEqual(
    prevProps.task.data?.task?.stages?.items,
    nextProps.task.data?.task?.stages?.items
  );
  
  // Check for task data changes more comprehensively
  const taskDataChanged = !isEqual(prevProps.task.data, nextProps.task.data);
  
  const shouldNotRerender = (
    prevProps.variant === nextProps.variant &&
    prevProps.task.id === nextProps.task.id &&
    prevProps.task.status === nextProps.task.status &&
    prevProps.isSelected === nextProps.isSelected &&
    prevProps.selectedScoreResultId === nextProps.selectedScoreResultId &&
    prevProps.isFullWidth === nextProps.isFullWidth &&
    // CHECK FOR SCORECARD/SCORE CHANGES - CRITICAL FOR REALTIME UPDATES
    prevProps.task.scorecard === nextProps.task.scorecard &&
    prevProps.task.score === nextProps.task.score &&
    // CHECK FOR TASK STAGE CHANGES - CRITICAL FOR REALTIME STAGE UPDATES
    stageComparison &&
    // CHECK FOR ANY TASK DATA CHANGES
    !taskDataChanged
  );
  
  const prevStages = prevProps.task.data?.task?.stages?.items?.map(s => `${s.name}:${s.status}`).join(',') || 'none';
  const nextStages = nextProps.task.data?.task?.stages?.items?.map(s => `${s.name}:${s.status}`).join(',') || 'none';
  
  if (shouldNotRerender) {
    console.log(`🔍 TRACE_STAGES: EvaluationTask memo BLOCKING re-render - ${nextProps.task.id} - stages: [${nextStages}]`);
  } else {
    console.log(`🔍 TRACE_STAGES: EvaluationTask memo ALLOWING re-render - ${nextProps.task.id} - stage change: [${prevStages}] → [${nextStages}]`);
  }
  
  return shouldNotRerender;
});

export default EvaluationTask;

function getMetricInformation(metricName: string): string {
  const descriptions: Record<string, string> = {
    "Accuracy": "Accuracy measures the overall correctness of predictions, showing the " +
      "percentage of all cases (both positive and negative) that were " +
      "correctly classified.\n\n" +
      "While accuracy is a good general metric, it can be misleading when classes " +
      "are imbalanced. For example, if only 1% of cases are positive, a model " +
      "that always predicts negative would have 99% accuracy but be useless for " +
      "detecting positive cases.",
    "Precision": "Precision measures the accuracy of positive predictions, showing " +
      "the percentage of predicted positive cases that were actually positive.\n\n" +
      "High precision is crucial when false positives are costly - for example, " +
      "when flagging content that will be removed or when identifying cases that " +
      "will trigger penalties. In these cases, we want to be very confident in " +
      "our positive predictions.",
    "Sensitivity": "Sensitivity (also called Recall) measures the ability to correctly " +
      "identify positive cases, showing the percentage of actual positive " +
      "cases that were correctly identified.\n\n" +
      "High sensitivity is essential when missing positive cases is costly - for " +
      "example, when detecting regulated content that must be caught, or when " +
      "screening for high-risk conditions. In these cases, we prefer false " +
      "positives over missing actual positives.",
    "Specificity": "Specificity measures the ability to correctly identify negative " +
      "cases, showing the percentage of actual negative cases that were " +
      "correctly identified.\n\n" +
      "High specificity indicates the model is good at ruling out false " +
      "positives. This is important in scenarios where we want to avoid " +
      "overwhelming review systems with false alarms, or when we need to " +
      "confidently clear cases as negative."
  }
  return descriptions[metricName] || ""
}
