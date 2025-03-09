import React, { useRef, useState, useEffect, useMemo, useCallback } from 'react'
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
import isEqual from 'lodash/isEqual'
import { standardizeScoreResults } from '@/utils/data-operations'

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
  trace: any | null
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
  datasetClassDistribution?: Array<Distribution>
  isDatasetClassDistributionBalanced?: boolean | null
  predictedClassDistribution?: Array<Distribution>
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
  commandDisplay?: 'hide' | 'show' | 'full'
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
  console.log('GridContent received data:', {
    dataId: data.id,
    hasScoreResults: !!data.scoreResults,
    scoreResultsType: data.scoreResults ? typeof data.scoreResults : 'undefined',
    scoreResultsIsArray: Array.isArray(data.scoreResults),
    scoreResultsCount: Array.isArray(data.scoreResults) ? data.scoreResults.length : 
                      (typeof data.scoreResults === 'object' && data.scoreResults !== null && 'length' in data.scoreResults ? 
                       (data.scoreResults as any).length : 0),
    firstScoreResult: Array.isArray(data.scoreResults) ? data.scoreResults[0] : 
                     (typeof data.scoreResults === 'object' && data.scoreResults !== null && 
                      Array.isArray((data.scoreResults as any).items) ? (data.scoreResults as any).items[0] : undefined)
  });

  const progress = useMemo(() => 
    data.processedItems && data.totalItems ? 
      Math.round((data.processedItems / data.totalItems) * 100) : 0
  , [data.processedItems, data.totalItems]);
  
  const accuracy = data.accuracy ?? 0;

  // Parse score results
  const parsedScoreResults = useMemo(() => {
    // Standardize score results to ensure consistent format
    const standardizedResults = standardizeScoreResults(data.scoreResults);
    
    console.log('GridContent standardized score results:', {
      count: standardizedResults.length,
      firstResult: standardizedResults[0],
      isArray: Array.isArray(standardizedResults)
    });
    
    if (!standardizedResults.length) {
      console.log('No score results to parse in GridContent');
      return [];
    }
    
    console.log('Parsing score results in GridContent:', {
      count: standardizedResults.length,
      firstResult: standardizedResults[0]
    });
    
    return standardizedResults.map((result: any) => {
      return parseScoreResult(result);
    });
  }, [data.scoreResults]);

  console.log('GridContent render:', {
    scoreResults: {
      raw: data.scoreResults,
      parsed: parsedScoreResults,
      count: parsedScoreResults.length
    }
  });

  const stages = useMemo(() => 
    data.task?.stages?.items?.map(stage => ({
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
    })) || []
  , [data.task?.stages?.items]);

  const taskStatus = useMemo(() => ({
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
    commandDisplay: 'hide' as const
  }), [
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
    isSelected
  ]);

  return (
    <div className="space-y-2">
      <TaskStatus {...taskStatus} />
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
  // Custom comparison function to prevent unnecessary re-renders
  if (prevProps.extra !== nextProps.extra || prevProps.isSelected !== nextProps.isSelected) {
    return false;
  }

  const prevData = prevProps.data;
  const nextData = nextProps.data;

  // Compare task stages
  const prevStages = prevData.task?.stages?.items;
  const nextStages = nextData.task?.stages?.items;
  if (!isEqual(prevStages, nextStages)) {
    return false;
  }

  // Compare score results directly without parsing
  if (!isEqual(prevData.scoreResults, nextData.scoreResults)) {
    console.log('Score results changed:', {
      prevCount: prevData.scoreResults?.length ?? 0,
      nextCount: nextData.scoreResults?.length ?? 0
    });
    return false;
  }

  // Compare essential task data
  if (
    prevData.processedItems !== nextData.processedItems ||
    prevData.totalItems !== nextData.totalItems ||
    prevData.accuracy !== nextData.accuracy ||
    prevData.status !== nextData.status ||
    prevData.task?.status !== nextData.task?.status ||
    prevData.task?.command !== nextData.task?.command ||
    prevData.command !== nextData.command ||
    prevData.errorMessage !== nextData.errorMessage ||
    prevData.task?.errorMessage !== nextData.task?.errorMessage ||
    prevData.startedAt !== nextData.startedAt ||
    prevData.task?.startedAt !== nextData.task?.startedAt ||
    prevData.task?.completedAt !== nextData.task?.completedAt ||
    prevData.task?.estimatedCompletionAt !== nextData.task?.estimatedCompletionAt
  ) {
    return false;
  }

  return true;
});

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
  trace: any | null
  itemId: string | null
}

function parseScoreResult(result: any): ParsedScoreResult {
  console.log('parseScoreResult called with:', {
    resultType: typeof result,
    resultIsNull: result === null,
    resultIsUndefined: result === undefined,
    resultId: result?.id,
    resultValue: result?.value,
    resultMetadataType: result?.metadata ? typeof result.metadata : 'undefined',
    resultExplanation: result?.explanation,
    resultTrace: result?.trace ? typeof result.trace : 'undefined'
  });

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
      itemId: null
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

  console.log('parseScoreResult processed result:', {
    id,
    value,
    confidence,
    explanation,
    humanLabel,
    correct
  });

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
    itemId
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

  console.log('DetailContent render:', {
    scoreResults: {
      raw: data.scoreResults,
      count: data.scoreResults?.length ?? 0,
      firstResult: data.scoreResults?.[0],
      lastResult: data.scoreResults?.[data.scoreResults?.length - 1],
      allResults: data.scoreResults // Log all results to see the full data
    },
    selectedScoreResultId,
    hasSelectedResult: !!selectedScoreResultId
  });

  const [containerWidth, setContainerWidth] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const [selectedPredictedActual, setSelectedPredictedActual] = useState<{
    predicted: string | null
    actual: string | null
  }>({ predicted: null, actual: null })

  // Find the selected score result from the standardized results
  const standardizedResults = useMemo(() => standardizeScoreResults(data.scoreResults), [data.scoreResults]);
  const selectedScoreResult = selectedScoreResultId ? standardizedResults.find(r => r.id === selectedScoreResultId) : null;

  console.log('DetailContent selected score result:', {
    selectedScoreResultId,
    hasSelectedResult: !!selectedScoreResult,
    selectedResult: selectedScoreResult
  });

  // Parse score results with more detailed logging
  const parsedScoreResults = useMemo(() => {
    // Standardize score results to ensure consistent format
    const standardizedResults = standardizeScoreResults(data.scoreResults);
    
    console.log('DetailContent standardized score results:', {
      count: standardizedResults.length,
      firstResult: standardizedResults[0],
      isArray: Array.isArray(standardizedResults)
    });
    
    if (!standardizedResults.length) {
      console.log('No score results to parse in DetailContent');
      return [];
    }
    
    console.log('Parsing score results in DetailContent:', {
      count: standardizedResults.length,
      firstResult: standardizedResults[0]
    });
    
    const results = standardizedResults.map((result: any) => parseScoreResult(result));
    
    console.log('Parsed score results in DetailContent:', {
      count: results.length,
      firstResult: results[0]
    });
    
    return results;
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
  const showMainPanel = true
  const showResultsList = parsedScoreResults.length > 0
  const showResultDetail = selectedScoreResult !== null

  console.log('DetailContent render conditions:', {
    hasScoreResults: !!data.scoreResults?.length,
    parsedResultCount: parsedScoreResults.length,
    showMainPanel,
    showResultsList,
    showResultDetail,
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

  return (
    <div 
      ref={containerRef}
      className="w-full min-w-[300px] h-full"
    >
      <div className={`${showAsColumns ? 'grid gap-4' : 'space-y-4'} h-full`} 
        style={{
          gridTemplateColumns: isWideEnoughForThree && selectedScoreResult 
            ? '1fr 1fr 1fr' 
            : isWideEnoughForTwo && parsedScoreResults.length > 0
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
                    isSelected={effectiveIsSelected}
                    commandDisplay={commandDisplay}
                    onCommandDisplayChange={onCommandDisplayChange}
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

                {!showAsColumns && parsedScoreResults.length > 0 && (
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

        {showAsColumns && parsedScoreResults.length > 0 && (
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
}, (prevProps, nextProps) => {
  // Add logging for memo comparison
  const shouldUpdate = 
    prevProps.extra !== nextProps.extra || 
    prevProps.isSelected !== nextProps.isSelected ||
    prevProps.selectedScoreResultId !== nextProps.selectedScoreResultId ||
    prevProps.isFullWidth !== nextProps.isFullWidth ||
    prevProps.commandDisplay !== nextProps.commandDisplay ||
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
  commandDisplay: initialCommandDisplay = 'show',
  ...restProps
}: EvaluationTaskProps) {
  const [commandDisplay, setCommandDisplay] = useState(initialCommandDisplay);

  const data = task.data ?? {} as EvaluationTaskData

  // Add more detailed logging for incoming data
  console.log('EvaluationTask received data:', {
    taskId: task.id,
    variant,
    scoreResults: {
      isDefined: !!data.scoreResults,
      type: data.scoreResults ? typeof data.scoreResults : 'undefined',
      isArray: Array.isArray(data.scoreResults),
      count: Array.isArray(data.scoreResults) ? data.scoreResults.length : 
             (typeof data.scoreResults === 'object' && data.scoreResults !== null && 'length' in data.scoreResults ? 
              (data.scoreResults as any).length : 0),
      firstResult: Array.isArray(data.scoreResults) ? data.scoreResults[0] : 
                  (typeof data.scoreResults === 'object' && data.scoreResults !== null && 
                   Array.isArray((data.scoreResults as any).items) ? (data.scoreResults as any).items[0] : undefined),
      allResults: data.scoreResults // Log all results to see the full data
    },
    status: data.status,
    taskStatus: data.task?.status
  });

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

  const taskWithDefaults = useMemo(() => ({
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
      commandDisplay={commandDisplay}
      {...restProps}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          {headerContent}
        </TaskHeader>
      )}
      renderContent={(props) => {
        // Add logging for content rendering decision
        console.log('EvaluationTask renderContent:', {
          variant,
          hasScoreResults: !!data.scoreResults,
          scoreResultsType: typeof data.scoreResults,
          scoreResultsIsArray: Array.isArray(data.scoreResults),
          scoreResultsCount: Array.isArray(data.scoreResults) ? data.scoreResults.length : 
                            (typeof data.scoreResults === 'object' && data.scoreResults !== null && 'length' in data.scoreResults ? 
                             (data.scoreResults as any).length : 0),
          isDetailView: variant === 'detail'
        });

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
  return (
    prevProps.variant === nextProps.variant &&
    prevProps.task.id === nextProps.task.id &&
    prevProps.task.status === nextProps.task.status &&
    prevProps.isSelected === nextProps.isSelected &&
    prevProps.selectedScoreResultId === nextProps.selectedScoreResultId &&
    prevProps.isFullWidth === nextProps.isFullWidth
  );
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
