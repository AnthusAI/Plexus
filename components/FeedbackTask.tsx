import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { MessageCircleMore } from 'lucide-react'
import { Progress } from '@/components/ui/progress'
import TaskProgress from './TaskProgress'

interface FeedbackTaskData {
  progress?: number
  elapsedTime?: string
  numberComplete?: number
  numberTotal?: number
  eta?: string
  processedItems: number
  totalItems: number
  estimatedTimeRemaining: string
}

const FeedbackTask: React.FC<Omit<TaskComponentProps, 'renderHeader' | 'renderContent'>> = ({
  variant,
  task,
  onClick,
  controlButtons,
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
      renderHeader={(props) => (
        <TaskHeader {...props}>
          <div className="flex justify-end w-full">
            <MessageCircleMore className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization}>
          {data && data.progress !== undefined && (
            <TaskProgress 
              progress={data.progress} 
              elapsedTime={data.elapsedTime} 
              processedItems={data.processedItems} 
              totalItems={data.totalItems} 
              estimatedTimeRemaining={data.estimatedTimeRemaining} 
            />
          )}
        </TaskContent>
      )}
    />
  )
}

export default FeedbackTask
