import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { Sparkles } from 'lucide-react'
import BeforeAfterPieCharts from './BeforeAfterPieCharts'
import TaskProgress from './TaskProgress'

interface OptimizationTaskData {
  progress?: number
  elapsedTime?: string
  numberComplete?: number
  numberTotal?: number
  estimatedTimeRemaining?: string
  processingRate?: number
  before?: {
    innerRing: Array<{ value: number }>
  }
  after?: {
    innerRing: Array<{ value: number }>
  }
}

const OptimizationTask: React.FC<Omit<TaskComponentProps, 'renderHeader' | 'renderContent'>> = ({
  variant,
  task,
  onClick,
  controlButtons,
}) => {
  const data = task.data as OptimizationTaskData

  const visualization = (
    <BeforeAfterPieCharts
      before={data.before || { innerRing: [{ value: 0 }] }}
      after={data.after || { innerRing: [{ value: 0 }] }}
    />
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
            <Sparkles className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization}>
          {data && (
            <TaskProgress 
              progress={data.progress ?? 0}
              elapsedTime={data.elapsedTime ?? ''}
              processedItems={data.numberComplete ?? 0}
              totalItems={data.numberTotal ?? 0}
              estimatedTimeRemaining={data.estimatedTimeRemaining ?? ''}
              processingRate={data.processingRate ?? 0}
            />
          )}
        </TaskContent>
      )}
    />
  )
}

export default OptimizationTask
