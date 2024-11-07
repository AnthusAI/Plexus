import React, { useRef, useState, useEffect } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { FlaskConical } from 'lucide-react'
import MetricsGauges from '@/components/MetricsGauges'
import { TaskProgress } from '@/components/TaskProgress'
import { ResponsiveWaffle } from '@nivo/waffle'
import { ConfusionMatrix } from '@/components/confusion-matrix'
import { formatDuration, intervalToDuration, formatDistanceToNow } from 'date-fns'

export interface ExperimentTaskData {
  accuracy: number
  sensitivity: number
  specificity: number
  precision: number
  processedItems: number
  totalItems: number
  progress: number
  inferences: number
  results: number
  cost: number
  status: string
  startedAt?: string
  estimatedEndAt?: string
  confusionMatrix?: {
    matrix: number[][]
    labels: string[]
  }
}

export type ExperimentTaskProps = {
  variant?: 'grid' | 'detail'
  task: {
    id: number
    type: string
    scorecard: string
    score: string
    time: string
    summary: string
    description?: string
    data: ExperimentTaskData
  }
  onClick?: () => void
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
}

export default function ExperimentTask({ 
  variant = "grid",
  task,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}: ExperimentTaskProps) {
  const data = task.data
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

  const getElapsedTime = () => {
    if (!data.startedAt) return "00:00:00"
    const start = new Date(data.startedAt)
    const now = new Date()
    const duration = intervalToDuration({ start, end: now })
    return formatDuration(duration, { format: ['hours', 'minutes', 'seconds'] })
  }

  const getEstimatedTimeRemaining = () => {
    if (!data.estimatedEndAt) return "00:00:00"
    const now = new Date()
    const end = new Date(data.estimatedEndAt)
    if (end < now) return "00:00:00"
    const duration = intervalToDuration({ start: now, end })
    return formatDuration(duration, { format: ['hours', 'minutes', 'seconds'] })
  }

  const metrics = variant === 'detail' ? [
    {
      value: data.accuracy,
      label: 'Accuracy',
      backgroundColor: 'var(--gauge-background)',
    },
    {
      value: data.sensitivity,
      label: 'Sensitivity',
      backgroundColor: 'var(--gauge-background)',
    },
    {
      value: data.specificity,
      label: 'Specificity',
      backgroundColor: 'var(--gauge-background)',
    },
    {
      value: data.precision,
      label: 'Precision',
      backgroundColor: 'var(--gauge-background)',
    }
  ] : [
    {
      value: data.accuracy,
      label: 'Accuracy',
      backgroundColor: 'var(--gauge-background)',
    }
  ]

  const visualization = variant === 'detail' ? (
    <div className="w-full">
      <MetricsGauges gauges={metrics} variant={variant} />
      <div className="mt-4">
        <TaskProgress 
          progress={(data.processedItems / data.totalItems) * 100}
          elapsedTime={getElapsedTime()}
          processedItems={data.processedItems}
          totalItems={data.totalItems}
          estimatedTimeRemaining={getEstimatedTimeRemaining()}
        />
      </div>
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
              value: Math.round(data.processedItems * data.accuracy / 100) 
            },
            { 
              id: 'incorrect', 
              label: 'Incorrect', 
              value: data.processedItems - Math.round(data.processedItems * data.accuracy / 100) 
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
    </div>
  ) : (
    <div className="w-full">
      <MetricsGauges gauges={metrics} variant={variant} />
      <div className="mt-4">
        <TaskProgress 
          progress={(data.processedItems / data.totalItems) * 100}
          elapsedTime={getElapsedTime()}
          processedItems={data.processedItems}
          totalItems={data.totalItems}
          estimatedTimeRemaining={getEstimatedTimeRemaining()}
        />
      </div>
    </div>
  )

  return (
    <Task
      variant={variant}
      task={task}
      onClick={onClick}
      controlButtons={controlButtons}
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          <div className="flex justify-end w-full">
            <FlaskConical className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization}>
        </TaskContent>
      )}
    />
  )
}
