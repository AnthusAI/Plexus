import React from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from './Task'
import { Siren, MessageCircleWarning } from 'lucide-react'

const AlertTask: React.FC<BaseTaskProps> = ({ variant, task, onClick, controlButtons }) => {
  const visualization = (
    <div className="flex items-center justify-center">
      <MessageCircleWarning className="h-24 w-24 text-destructive" />
    </div>
  )

  return (
    <Task variant={variant} task={task} onClick={onClick} controlButtons={controlButtons}>
      <TaskHeader task={task} variant={variant}>
        <div className="flex flex-col items-end">
          <div className="w-7 flex-shrink-0 mb-1">
            <Siren className="h-5 w-5" />
          </div>
        </div>
      </TaskHeader>
      <TaskContent task={task} variant={variant} visualization={visualization}>
        {/* Additional content can be added here if needed */}
      </TaskContent>
    </Task>
  )
}

export default AlertTask
