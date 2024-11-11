import React, { useRef, useState, useEffect } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { FlaskConical, Square, X } from 'lucide-react'
import MetricsGauges from '@/components/MetricsGauges'
import { ProgressBar } from "@/components/ui/progress-bar"
import { ResponsiveWaffle } from '@nivo/waffle'
import { ConfusionMatrix } from '@/components/confusion-matrix'
import { intervalToDuration } from 'date-fns'
import { CardButton } from '@/components/CardButton'

export interface ExperimentTaskData {
  accuracy: number | null
  sensitivity: number | null
  specificity: number | null
  precision: number | null
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
}

export interface ExperimentTaskProps extends BaseTaskProps<ExperimentTaskData> {
  onToggleFullWidth: () => void
  onClose: () => void
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

  const metrics = variant === 'detail' ? [
    {
      value: data.accuracy ?? undefined,
      label: 'Accuracy',
      backgroundColor: 'var(--gauge-background)',
    },
    {
      value: data.sensitivity ?? undefined,
      label: 'Sensitivity',
      backgroundColor: 'var(--gauge-background)',
    },
    {
      value: data.specificity ?? undefined,
      label: 'Specificity',
      backgroundColor: 'var(--gauge-background)',
    },
    {
      value: data.precision ?? undefined,
      label: 'Precision',
      backgroundColor: 'var(--gauge-background)',
    }
  ] : [
    {
      value: data.accuracy ?? undefined,
      label: 'Accuracy',
      backgroundColor: 'var(--gauge-background)',
    }
  ]

  const metricsVariant = variant === 'grid' ? 'grid' : 'detail'

  const visualization = (
    <div className="w-full">
      <MetricsGauges gauges={metrics} variant={metricsVariant} />
      <div className="mt-4">
        <ProgressBar 
          progress={data.progress}
          elapsedTime={data.elapsedSeconds ? 
            formatDuration(data.elapsedSeconds) : undefined}
          processedItems={data.processedItems}
          totalItems={data.totalItems}
          estimatedTimeRemaining={data.estimatedRemainingSeconds ? 
            formatDuration(data.estimatedRemainingSeconds) : undefined}
          color="secondary"
        />
      </div>
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
    </div>
  )

  return (
    <Task
      variant={variant}
      task={{
        ...task,
        type: computedType
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
