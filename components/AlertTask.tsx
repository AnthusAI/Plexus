import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { Siren, MessageCircleWarning } from 'lucide-react'

const AlertTask: React.FC<Omit<TaskComponentProps, 'renderHeader' | 'renderContent'>> = ({ variant, task, onClick, controlButtons }) => {
  const visualization = (
    <div className="flex items-center justify-center">
      <MessageCircleWarning className="h-24 w-24 text-destructive" />
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
          <div className="flex flex-col items-end">
            <div className="w-7 flex-shrink-0 mb-1">
              <Siren className="h-5 w-5" />
            </div>
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization}>
          {/* Additional content can be added here if needed */}
        </TaskContent>
      )}
    />
  )
}

export default AlertTask
