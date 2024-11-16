import React, { useRef, useState, useEffect } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { FlaskConical, Square, X } from 'lucide-react'
import MetricsGauges from '@/components/MetricsGauges'
import { ProgressBar } from "@/components/ui/progress-bar"
import { ResponsiveWaffle } from '@nivo/waffle'
import { ConfusionMatrix } from '@/components/confusion-matrix'
import { intervalToDuration } from 'date-fns'
import { CardButton } from '@/components/CardButton'
import ScoreTypesHeader from '@/components/ScoreTypesHeader'
import ClassDistributionVisualizer from '@/components/ClassDistributionVisualizer'
import PredictedClassDistributionVisualizer from '@/components/PredictedClassDistributionVisualizer'

export interface ExperimentMetric {
  name: string
  value: number
  unit?: string
  maximum?: number
  priority: boolean
}

export interface ExperimentTaskData {
  accuracy: number | null
  metrics: ExperimentMetric[]
  metricsExplanation?: string | null
  processedItems: number
  totalItems: number
  progress: number
  inferences: number
  cost: number | null
  status: string
  elapsedSeconds: number | null
  estimatedRemainingSeconds: number | null
  startedAt?: string | null
  errorMessage?: string | null
  errorDetails?: any | null
  confusionMatrix?: {
    matrix: number[][]
    labels: string[]
  }
  scoreGoal?: string | null
  datasetClassDistribution?: { label: string, count: number }[]
  isDatasetClassDistributionBalanced?: boolean | null
  predictedClassDistribution?: { label: string, count: number }[]
  isPredictedClassDistributionBalanced?: boolean | null
  scoreResults?: Schema['ScoreResult']['type'][]
}

export interface ExperimentTaskProps {
  variant?: 'grid' | 'detail'
  task: {
    id: string
    type: string
    scorecard: string
    score: string
    time: string
    summary?: string
    description?: string
    data?: ExperimentTaskData
  }
  onClick?: () => void
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
}

function computeExperimentType(data: ExperimentTaskData): string {
  if (data.errorMessage || data.errorDetails) {
    return "Error in experiment"
  }
  
  if (data.progress === 100) {
    return "Experiment done"
  }
  
  if (data.progress >= 90) {
    return "Experiment finishing"
  }
  
  if (data.progress >= 10) {
    return "Experiment running"
  }
  
  if (data.progress > 0) {
    return "Experiment started"
  }
  
  return "Experiment pending"
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

export default function ExperimentTask({ 
  variant = 'grid',
  task,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}: ExperimentTaskProps) {
  const data = task.data ?? {} as ExperimentTaskData
  
  useEffect(() => {
    if (variant === 'detail') {
      console.log('ExperimentTask data:', {
        metricsExplanation: data.metricsExplanation,
        metrics: data.metrics,
        variant
      })
    }
  }, [variant, data])

  const computedType = computeExperimentType(data)
  const waffleContainerRef = useRef<HTMLDivElement>(null)
  const [waffleHeight, setWaffleHeight] = useState(20)

  useEffect(() => {
    const updateWaffleHeight = () => {
      if (waffleContainerRef.current) {
        const width = waffleContainerRef.current.offsetWidth
        setWaffleHeight(width / 4)
      }
    }

    updateWaffleHeight()
    window.addEventListener('resize', updateWaffleHeight)
    return () => window.removeEventListener('resize', updateWaffleHeight)
  }, [])

  const metrics = variant === 'detail' ? 
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

  const metricsVariant = variant === 'grid' ? 'grid' : 'detail'

  const visualization = (
    <div className="w-full">
      {variant === 'detail' && (
        <>
          <div className="mb-4">
            <ProgressBar 
              progress={data.progress}
              elapsedTime={data.elapsedSeconds !== null ? 
                formatDuration(data.elapsedSeconds) : undefined}
              processedItems={data.processedItems}
              totalItems={data.totalItems}
              estimatedTimeRemaining={data.estimatedRemainingSeconds !== null ? 
                formatDuration(data.estimatedRemainingSeconds) : undefined}
              color="secondary"
              isFocused={variant === 'detail'}
            />
          </div>

          <div className="mb-4">
            <ClassDistributionVisualizer
              data={data.datasetClassDistribution}
              isBalanced={data.isDatasetClassDistributionBalanced}
            />
          </div>

          <div className="mb-4">
            <PredictedClassDistributionVisualizer
              data={data.predictedClassDistribution}
            />
          </div>
        </>
      )}
      
      <MetricsGauges 
        gauges={metrics} 
        variant={metricsVariant} 
        metricsExplanation={data.metricsExplanation}
      />
      
      {variant !== 'detail' && (
        <div className="mt-4">
          <ProgressBar 
            progress={data.progress}
            elapsedTime={data.elapsedSeconds !== null ? 
              formatDuration(data.elapsedSeconds) : undefined}
            processedItems={data.processedItems}
            totalItems={data.totalItems}
            estimatedTimeRemaining={data.estimatedRemainingSeconds !== null ? 
              formatDuration(data.estimatedRemainingSeconds) : undefined}
            color="secondary"
            isFocused={false}
          />
        </div>
      )}

      {variant === 'detail' && (
        <>
          <div 
            ref={waffleContainerRef}
            className="mt-4 w-full" 
            style={{ height: `${waffleHeight}px` }}
          >
            <ResponsiveWaffle
              data={[
                { 
                  id: 'correct', 
                  label: 'Correct', 
                  value: Math.round(data.processedItems * (data.accuracy ?? 0) / 100) 
                },
                { 
                  id: 'incorrect', 
                  label: 'Incorrect', 
                  value: data.processedItems - Math.round(data.processedItems * (data.accuracy ?? 0) / 100) 
                },
                { 
                  id: 'unprocessed', 
                  label: 'Unprocessed', 
                  value: data.totalItems - data.processedItems 
                }
              ]}
              total={data.totalItems}
              rows={5}
              columns={20}
              padding={1}
              valueFormat=".0f"
              colors={({ id }) => {
                const colorMap: Record<string, string> = {
                  correct: 'var(--true)',
                  incorrect: 'var(--false)',
                  unprocessed: 'var(--neutral)'
                }
                return colorMap[id] || 'var(--neutral)'
              }}
              borderRadius={2}
              fillDirection="right"
              margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
              legends={[{
                anchor: 'bottom',
                direction: 'row',
                justify: false,
                translateX: 0,
                translateY: 30,
                itemsSpacing: 4,
                itemWidth: 100,
                itemHeight: 20,
                itemDirection: 'left-to-right',
                itemOpacity: 1,
                itemTextColor: 'var(--text-muted)',
                symbolSize: 20
              }]}
            />
          </div>
          {data.confusionMatrix && (
            <div className="mt-8">
              <ConfusionMatrix data={data.confusionMatrix} />
            </div>
          )}
        </>
      )}

      {data.scoreResults && data.scoreResults.length > 0 && (
        <div className="mt-8">
          <h3 className="text-lg font-semibold mb-4">
            {data.scoreResults.length} Predictions
          </h3>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {data.scoreResults.map((result) => (
              <ExperimentTaskScoreResult
                key={result.id}
                id={result.id}
                value={result.value}
                confidence={result.confidence}
                metadata={result.metadata}
                correct={result.correct}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )

  return (
    <Task
      variant={variant}
      task={{
        ...task,
        type: computedType,
        summary: variant === 'detail' ? undefined : task.summary
      }}
      onClick={onClick}
      controlButtons={controlButtons}
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          <div className="flex justify-end w-full">
            {variant === 'detail' ? (
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
            ) : (
              <FlaskConical className="h-6 w-6" />
            )}
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props}>
          {visualization}
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
