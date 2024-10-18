import React from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from './Task'
import { MessageCircleMore } from 'lucide-react'
import { Progress } from '@/components/ui/progress'

const FeedbackTask: React.FC<BaseTaskProps> = ({ variant, task, onClick, controlButtons }) => {
  const { data } = task

  const visualization = (
    <div className="flex items-center justify-center h-[120px] w-[120px]">
    </div>
  )

  return (
    <Task variant={variant} task={task} onClick={onClick} controlButtons={controlButtons}>
      <TaskHeader task={task} variant={variant}>
        <div className="flex flex-col items-end">
          <div className="w-7 flex-shrink-0 mb-1">
            <MessageCircleMore className="h-5 w-5" />
          </div>
        </div>
      </TaskHeader>
      <TaskContent task={task} variant={variant} visualization={visualization}>
        {data && data.progress !== undefined && (
          <div className="mt-4">
            <div className="flex justify-between text-xs mb-1">
              <div className="font-semibold">Progress: {data.progress}%</div>
              <div>{data.elapsedTime}</div>
            </div>
            <Progress value={data.progress} className="w-full h-4" />
            <div className="flex justify-between text-xs mt-1">
              <div>{data.processedItems}/{data.totalItems}</div>
              <div>
                {task.type === "Feedback queue completed" 
                  ? `Completed in ${data.elapsedTime}`
                  : `ETA: ${data.estimatedTimeRemaining}`
                }
              </div>
            </div>
          </div>
        )}
      </TaskContent>
    </Task>
  )
}

export default FeedbackTask
