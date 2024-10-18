import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { Siren, MessageCircleWarning, Info, LucideIcon } from 'lucide-react'

interface AlertTaskProps extends Omit<TaskComponentProps, 'renderHeader' | 'renderContent'> {
  iconType: 'siren' | 'warning'
}

const AlertTask: React.FC<AlertTaskProps> = ({
  variant,
  task,
  onClick,
  controlButtons,
  iconType,
}) => {
  let IconComponent: LucideIcon;
  switch (iconType) {
    case 'info':
      IconComponent = Info;
      break;
    case 'warning':
      IconComponent = MessageCircleWarning;
      break;
    default:
      IconComponent = Info; // Fallback to Info if iconType is unknown
  }

  const visualization = (
    <div className="flex items-center justify-center">
      <IconComponent className="h-24 w-24 text-destructive" />
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
            <Siren className="h-6 w-6" />
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
