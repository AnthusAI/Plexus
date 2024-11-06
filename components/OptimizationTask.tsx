import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { Sparkles } from 'lucide-react'
import BeforeAfterGauges from './BeforeAfterGauges'
import TaskProgress from './TaskProgress'

interface OptimizationTaskData {
  progress?: number
  elapsedTime?: string
  numberComplete?: number
  numberTotal?: number
  eta?: string
  before?: {
    innerRing: Array<{ value: number }>
  }
  after?: {
    innerRing: Array<{ value: number }>
  }
}

const OptimizationTask: React.FC<
  Omit<TaskComponentProps, 'renderHeader' | 'renderContent'>
> = ({ variant, task, onClick, controlButtons }) => {
  const data = task.data as OptimizationTaskData

  const visualization = (
    <div className="flex flex-col items-center w-full">
      <BeforeAfterGauges
        title={task.description || 'Metric'}
        before={data.before?.innerRing[0]?.value ?? 0}
        after={data.after?.innerRing[0]?.value ?? 0}
        variant={variant}
        backgroundColor="var(--gauge-background)"
      />
      {data && (
        <div className="mt-4 w-full">
          <TaskProgress 
            progress={data.progress ?? 0}
            elapsedTime={data.elapsedTime ?? ''}
            processedItems={data.numberComplete ?? 0}
            totalItems={data.numberTotal ?? 0}
            estimatedTimeRemaining={data.eta ?? ''}
          />
        </div>
      )}
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
            <Sparkles className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization} />
      )}
    />
  )
}

export default OptimizationTask
