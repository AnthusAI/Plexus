import React from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from './Task'
import { MessageCircleMore } from 'lucide-react'
import { ProgressBar } from '@/components/ui/progress-bar'

interface FeedbackTaskData {
  progress?: number
  elapsedTime?: string
  processedItems?: number
  totalItems?: number
  estimatedTimeRemaining?: string
}

interface FeedbackTaskProps extends Omit<BaseTaskProps, 'task'> {
  task: BaseTaskProps['task'] & {
    data?: FeedbackTaskData
  }
}

const FeedbackTask: React.FC<FeedbackTaskProps> = ({
  variant,
  task,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}) => {
  const data = task.data as FeedbackTaskData

  const visualization = (
    <div className="flex flex-col h-full">
      <div className="flex-grow">
        {/* Main content goes here */}
      </div>
      {data && (
        <div className="mt-4">
          <ProgressBar 
            progress={data.progress ?? 0}
            elapsedTime={data.elapsedTime}
            processedItems={data.processedItems}
            totalItems={data.totalItems}
            estimatedTimeRemaining={data.estimatedTimeRemaining}
            color="primary"
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
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          <div className="flex justify-end w-full">
            <MessageCircleMore className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization} />
      )}
    />
  )
}

export default FeedbackTask
