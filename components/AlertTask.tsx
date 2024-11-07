import React from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from './Task'
import { Siren, MessageCircleWarning, Info, LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface AlertTaskProps extends Omit<BaseTaskProps, 'task'> {
  task: BaseTaskProps['task']
  iconType: 'siren' | 'warning' | 'info'
}

const AlertTask: React.FC<AlertTaskProps> = ({
  variant,
  task,
  onClick,
  controlButtons,
  iconType,
  isFullWidth,
  onToggleFullWidth,
  onClose
}) => {
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
