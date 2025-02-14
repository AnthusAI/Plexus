import React, { useRef, useState, useEffect, useMemo } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { FlaskConical, Square, X, Split, ChevronLeft } from 'lucide-react'
import MetricsGauges from '@/components/MetricsGauges'
import { TaskStatus, type TaskStageConfig } from '@/components/ui/task-status'
import { ConfusionMatrix } from '@/components/confusion-matrix'
import { CardButton } from '@/components/CardButton'
import ClassDistributionVisualizer from '@/components/ClassDistributionVisualizer'
import PredictedClassDistributionVisualizer from '@/components/PredictedClassDistributionVisualizer'
import { EvaluationTaskScoreResult } from '@/components/EvaluationTaskScoreResult'
import type { Schema } from "@/amplify/data/resource"
import MetricsGaugesExplanation from '@/components/MetricsGaugesExplanation'
import { EvaluationTaskScoreResults } from '@/components/EvaluationTaskScoreResults'
import { EvaluationTaskScoreResultDetail } from '@/components/EvaluationTaskScoreResultDetail'
import { useResizeObserver } from '@/hooks/use-resize-observer'
import { BaseTaskData } from '@/types/base'
import { EvaluationListAccuracyBar } from '@/components/EvaluationListAccuracyBar'

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
  }
  itemId: string | null
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
  datasetClassDistribution?: Array<{ label: string; count: number }>
  isDatasetClassDistributionBalanced?: boolean | null
  predictedClassDistribution?: Array<{ label: string; count: number }>
  isPredictedClassDistributionBalanced?: boolean | null
  scoreResults?: ScoreResult[]
  selectedScoreResult?: Schema['ScoreResult']['type'] | null
  task?: TaskData | null
}

export interface EvaluationTaskProps extends Omit<BaseTaskProps<EvaluationTaskData>, 'variant'> {
  variant?: 'grid' | 'detail'
  task: {
    id: string
    type: string
    scorecard: string
    score: string
    time: string
    summary?: string
    description?: string
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
  const progress = data.processedItems && data.totalItems ? 
    Math.round((data.processedItems / data.totalItems) * 100) : 0
  const accuracy = data.accuracy ?? 0

  return (
    <div className="space-y-2">
      <TaskStatus
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
        command={data.task?.command || data.command || undefined}
        statusMessage={getStatusMessage(data)}
        variant="grid"
        extra={extra}
        isSelected={isSelected}
      />
      {extra && (
        <EvaluationListAccuracyBar 
          progress={progress}
          accuracy={accuracy}
        />
      )}
    </div>
  )
})

interface ParsedScoreResult {
  id: string
  value: string
  confidence: number | null
  explanation: string | null
  metadata: {
    human_label: string | null
    correct: boolean
    human_explanation: string | null
    text: string | null
  }
  itemId: string | null
}

function parseScoreResult(result: any): ParsedScoreResult {
  if (!result) {
    console.warn('Received null or undefined score result')
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
      itemId: null
    }
  }

  // Handle metadata parsing with better error handling
  const parsedMetadata = (() => {
    try {
      let metadata = result.metadata
      if (typeof metadata === 'string') {
        metadata = JSON.parse(metadata)
        if (typeof metadata === 'string') {
          metadata = JSON.parse(metadata)
        }
      }
      return metadata || {}
    } catch (e) {
      console.error('Error parsing metadata:', e)
      return {}
    }
  })()

  // Extract results from nested structure if present
  const firstResultKey = parsedMetadata?.results ? 
    Object.keys(parsedMetadata.results)[0] : null
  const scoreResult = firstResultKey && parsedMetadata.results ? 
    parsedMetadata.results[firstResultKey] : null

  // Log the parsing process for debugging
  console.debug('Score result parsing:', {
    originalResult: result,
    parsedMetadata,
    firstResultKey,
    scoreResult
  })

  return {
    id: result.id || '',
    value: String(result.value || scoreResult?.value || ''),
    confidence: result.confidence ?? scoreResult?.confidence ?? null,
    explanation: result.explanation ?? scoreResult?.explanation ?? null,
    metadata: {
      human_label: scoreResult?.metadata?.human_label ?? parsedMetadata.human_label ?? null,
      correct: Boolean(scoreResult?.metadata?.correct ?? parsedMetadata.correct),
      human_explanation: scoreResult?.metadata?.human_explanation ?? parsedMetadata.human_explanation ?? null,
      text: scoreResult?.metadata?.text ?? parsedMetadata.text ?? null
    },
    itemId: result.itemId || parsedMetadata.item_id?.toString() || null
  }
}

const DetailContent = React.memo(({ 
  data, 
  isFullWidth,
  metrics,
  metricsVariant,
  selectedScoreResultId,
  onSelectScoreResult,
  extra,
  isSelected
}: { 
  data: EvaluationTaskData
  isFullWidth: boolean
  metrics: any[]
  metricsVariant: 'grid' | 'detail'
  selectedScoreResultId?: string | null
  onSelectScoreResult?: (id: string | null) => void
  extra?: boolean
  isSelected?: boolean
}) => {
  console.log('DetailContent render:', {
    hasTaskData: !!data.task,
    taskStatus: data.task?.status,
    evaluationStatus: data.status,
    processedItems: data.processedItems,
    totalItems: data.totalItems,
    stageCount: data.task?.stages?.items?.length,
    stages: data.task?.stages?.items?.map(s => ({
      name: s.name,
      status: s.status,
      processedItems: s.processedItems,
      totalItems: s.totalItems
    }))
  });

  const [containerWidth, setContainerWidth] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const [selectedPredictedActual, setSelectedPredictedActual] = useState<{
    predicted: string | null
    actual: string | null
  }>({ predicted: null, actual: null })

  const selectedScoreResult = data.scoreResults?.find(r => r.id === selectedScoreResultId) ?? null

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

  const isWideEnoughForTwo = containerWidth >= 800
  const isWideEnoughForThree = containerWidth >= 1180 && isFullWidth
  
  const showAsColumns = isWideEnoughForTwo
  const showMainPanel = !selectedScoreResult || isWideEnoughForThree
  const showResultsList = !selectedScoreResult || showAsColumns
  const showResultDetail = selectedScoreResult

  const handleScoreResultSelect = (result: Schema['ScoreResult']['type']) => {
    onSelectScoreResult?.(result.id)
  }

  const handleScoreResultClose = () => {
    onSelectScoreResult?.(null)
  }

  const parsedScoreResults = useMemo(() => {
    return data.scoreResults?.map(parseScoreResult) ?? []
  }, [data.scoreResults])

  return (
    <div 
      ref={containerRef}
      className="w-full min-w-[300px] h-full"
    >
      <div className={`${showAsColumns ? 'grid gap-4' : 'space-y-4'} h-full`} 
        style={{
          gridTemplateColumns: isWideEnoughForThree && selectedScoreResult 
            ? '1fr 1fr 1fr' 
            : isWideEnoughForTwo
              ? selectedScoreResult 
                ? '1fr 1fr'  // Show results list and detail only
                : '1fr 1fr'  // Show main and results list
              : '1fr'
        }}
      >
        {showMainPanel && (
          <div className="w-full h-full flex flex-col">
            <div className="flex-1 overflow-y-auto">
              <div className="px-1">
                <div className="mb-3">
                  <TaskStatus
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
                    isSelected={true}
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

                {data.confusionMatrix?.matrix && 
                 data.confusionMatrix.matrix.length > 0 && 
                 data.confusionMatrix.labels && (
                  <div className="mt-3">
                    <ConfusionMatrix 
                      data={{
                        matrix: data.confusionMatrix.matrix,
                        labels: data.confusionMatrix.labels
                      }}
                      onSelectionChange={setSelectedPredictedActual}
                    />
                  </div>
                )}

                {!showAsColumns && data.scoreResults && data.scoreResults.length > 0 && (
                  <div className="mt-6">
                    <EvaluationTaskScoreResults 
                      results={parsedScoreResults} 
                      accuracy={data.accuracy ?? 0}
                      selectedPredictedValue={selectedPredictedActual.predicted}
                      selectedActualValue={selectedPredictedActual.actual}
                      onResultSelect={handleScoreResultSelect}
                      selectedScoreResult={selectedScoreResult}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {showAsColumns && showResultsList && data.scoreResults && data.scoreResults.length > 0 && (
          <div className="w-full h-full relative">
            <div className="absolute inset-0 pr-0">
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

        {showResultDetail && selectedScoreResult && (
          <div className="w-full h-full relative">
            <div className="absolute inset-0 pr-0">
              <EvaluationTaskScoreResultDetail
                result={parseScoreResult(selectedScoreResult)}
                onClose={handleScoreResultClose}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
})

export default function EvaluationTask({ 
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
  ...restProps
}: EvaluationTaskProps) {
  const data = task.data ?? {} as EvaluationTaskData

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
        {typeof onToggleFullWidth === 'function' && (
          <CardButton
            icon={Square}
            onClick={onToggleFullWidth}
          />
        )}
        {typeof onClose === 'function' && (
          <CardButton
            icon={X}
            onClick={onClose}
          />
        )}
      </div>
    ) : null
  ), [variant, onToggleFullWidth, onClose])

  const taskData = task.data?.task as TaskData | undefined;

  const taskWithDefaults = {
    id: task.id,
    type: (() => {
      // If we have a task record, use its type directly (just capitalize it)
      if (taskData?.type) {
        return taskData.type.split(' ')
          .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
          .join(' ')
      }
      // Otherwise, this is from an Evaluation record, so append "Evaluation"
      return `${(task.type || '').split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ')} Evaluation`.trim()
    })(),
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
  }

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
      isSelected
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
      {...restProps}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          {headerContent}
        </TaskHeader>
      )}
      renderContent={(props) => (
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
            />
          )}
        </TaskContent>
      )}
    />
  )
}

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
