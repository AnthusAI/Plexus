import React from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { Siren, MessageCircleWarning, Info, LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { AlertTaskData } from '@/types/tasks'
import { BaseTaskProps } from '@/components/Task'

export interface AlertTaskProps extends BaseTaskProps<AlertTaskData> {}

const AlertTask: React.FC<AlertTaskProps> = ({
  variant,
  task,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}) => {
  const { iconType } = task.data || {}
  let IconComponent: LucideIcon;
  
  switch (iconType) {
    case 'info':
      IconComponent = Info;
      break;
    case 'warning':
      IconComponent = MessageCircleWarning;
      break;
    case 'siren':
      IconComponent = Siren;
      break;
    default:
      IconComponent = Info;
  }

  const visualization = (
    <div className={cn(
      "flex flex-col items-center w-full",
      variant === 'detail' ? 'grid grid-cols-2 gap-2' : 'flex justify-center'
    )}>
      <div className="relative w-full aspect-square flex items-center justify-center max-w-[20em]">
        <IconComponent 
          className="text-destructive absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" 
          style={{ width: '70%', height: '70%' }}
          strokeWidth={2.5} 
        />
      </div>
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
            <IconComponent className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization} />
      )}
    />
  )
}

export default AlertTask
