import React, { useRef, useState, useEffect } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { FlaskConical } from 'lucide-react'
import MetricsGauges from '@/components/MetricsGauges'
import { TaskProgress } from '@/components/TaskProgress'
import { ResponsiveWaffle } from '@nivo/waffle'

interface ExperimentTaskData {
  accuracy: number
  f1Score: number
  elapsedTime: string
  processedItems: number
  totalItems: number
  estimatedTimeRemaining: string
}

export interface ExperimentTaskProps extends BaseTaskProps {}

export default function ExperimentTask({ 
  variant = "grid",
  task,
  onClick,
  controlButtons
}: ExperimentTaskProps) {
  const data = task.data as ExperimentTaskData
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

  const accuracyConfig = {
    value: data.accuracy,
    label: 'Accuracy',
    segments: [
      { start: 0, end: 60, color: 'var(--gauge-inviable)' },
      { start: 60, end: 85, color: 'var(--gauge-converging)' },
      { start: 85, end: 100, color: 'var(--gauge-great)' }
    ],
    backgroundColor: 'var(--gauge-background)',
    showTicks: variant === 'detail'
  }

  const f1ScoreConfig = {
    value: data.f1Score,
    label: 'F1 Score',
    segments: [
      { start: 0, end: 60, color: 'var(--gauge-inviable)' },
      { start: 60, end: 85, color: 'var(--gauge-converging)' },
      { start: 85, end: 100, color: 'var(--gauge-great)' }
    ],
    backgroundColor: 'var(--gauge-background)',
    showTicks: variant === 'detail'
  }

  const visualization = variant === 'detail' ? (
    <div className="w-full">
      <MetricsGauges gauges={[accuracyConfig, f1ScoreConfig]} />
      <div className="mt-4">
        <TaskProgress 
          progress={(data.processedItems / data.totalItems) * 100}
          elapsedTime={data.elapsedTime}
          processedItems={data.processedItems}
          totalItems={data.totalItems}
          estimatedTimeRemaining={data.estimatedTimeRemaining}
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
    </div>
  ) : (
    <div className="w-full">
      <MetricsGauges 
        gauges={[{
          ...accuracyConfig,
          showTicks: false
        }, {
          ...f1ScoreConfig,
          showTicks: false
        }]}
      />
      <div className="mt-4">
        <TaskProgress 
          progress={(data.processedItems / data.totalItems) * 100}
          elapsedTime={data.elapsedTime}
          processedItems={data.processedItems}
          totalItems={data.totalItems}
          estimatedTimeRemaining={data.estimatedTimeRemaining}
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
