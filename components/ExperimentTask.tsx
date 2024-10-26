import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { FlaskConical } from 'lucide-react'
import MetricsGauges from './MetricsGauges'
import TaskProgress from './TaskProgress'

interface ExperimentTaskData {
  accuracy: number
  progress: number
  elapsedTime: string
  processedItems: number
  totalItems: number
  estimatedTimeRemaining: string
}

export interface ExperimentTaskProps extends 
  Omit<TaskComponentProps, 'renderHeader' | 'renderContent'> {}

const ExperimentTask: React.FC<ExperimentTaskProps> = ({ 
  variant, 
  task, 
  onClick, 
  controlButtons 
}) => {
  const data = task.data as ExperimentTaskData

  const accuracyConfig = {
    value: data.accuracy,
    label: 'Accuracy',
    segments: [
      { start: 0, end: 60, color: 'var(--gauge-inviable)' },
      { start: 60, end: 85, color: 'var(--gauge-converging)' },
      { start: 85, end: 100, color: 'var(--gauge-great)' }
    ],
    backgroundColor: 'var(--background)',
    showTicks: variant === 'detail'
  }

  const progressConfig = {
    value: data.progress,
    label: 'Progress',
    backgroundColor: 'var(--background)',
    showTicks: variant === 'detail'
  }

  const visualization = (
    <div className="w-full">
      <MetricsGauges 
        gauges={[accuracyConfig, progressConfig]}
      />
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
        <TaskContent {...props}>
          <div className="flex flex-col w-full gap-4">
            {visualization}
            <TaskProgress 
              progress={data.progress}
              elapsedTime={data.elapsedTime}
              processedItems={data.processedItems}
              totalItems={data.totalItems}
              estimatedTimeRemaining={data.estimatedTimeRemaining}
            />
          </div>
        </TaskContent>
      )}
    />
  )
}

export default ExperimentTask
