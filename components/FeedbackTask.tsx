import React from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from './Task'
import { MessageCircleMore } from 'lucide-react'
import TaskProgress from './TaskProgress'

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
    <div className="flex items-center justify-center h-[120px] w-[120px]">
      {/* Add any specific visualization for FeedbackTask here if needed */}
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
        <TaskContent {...props} visualization={visualization}>
          {data && (
            <TaskProgress 
              progress={data.progress ?? 0}
              elapsedTime={data.elapsedTime ?? ''}
              processedItems={data.processedItems ?? 0}
              totalItems={data.totalItems ?? 0}
              estimatedTimeRemaining={data.estimatedTimeRemaining ?? ''}
            />
          )}
        </TaskContent>
      )}
    />
  )
}

export default FeedbackTask
