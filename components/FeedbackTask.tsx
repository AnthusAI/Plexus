import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { MessageCircleMore } from 'lucide-react'
import { Progress } from '@/components/ui/progress'

interface FeedbackTaskData {
  progress?: number
  elapsedTime?: string
  numberComplete?: number
  numberTotal?: number
  eta?: string
}

const FeedbackTask: React.FC<Omit<TaskComponentProps, 'renderHeader' | 'renderContent'>> = ({ variant, task, onClick, controlButtons }) => {
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
            <MessageCircleMore className="h-5 w-5" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization}>
          {data && data.progress !== undefined && (
            <div className="mt-4">
              <div className="flex justify-between text-xs mb-1">
                <div className="font-semibold">Progress: {data.progress}%</div>
                <div>{data.elapsedTime}</div>
              </div>
              <Progress value={data.progress} className="w-full h-4" />
              <div className="flex justify-between text-xs mt-1">
                <div>{data.numberComplete}/{data.numberTotal}</div>
                <div>
                  {task.type === "Feedback queue completed" 
                    ? `Completed in ${data.elapsedTime}`
                    : `ETA: ${data.eta}`
                  }
                </div>
              </div>
            </div>
          )}
        </TaskContent>
      )}
    />
  )
}

export default FeedbackTask
