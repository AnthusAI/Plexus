import React from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Square, Columns2, X } from 'lucide-react'

export interface BaseTaskProps {
  variant: 'grid' | 'detail'
  task: {
    id: number
    type: string
    scorecard: string
    score: string
    time: string
    summary: string
    description?: string
    data?: {
      eta?: string
      numberComplete?: number
      numberTrue?: number
      numberFalse?: number
      numberTotal?: number
      accuracy?: number
      f1Score?: number
      progress?: number
      elapsedTime?: string
      processedItems?: number
      totalItems?: number
      estimatedTimeRemaining?: string
      before?: {
        innerRing: Array<{ value: number }>
      }
      after?: {
        innerRing: Array<{ value: number }>
      }
    }
  }
  onClick?: () => void
  customSummary?: React.ReactNode
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
}

interface TaskChildProps extends BaseTaskProps {
  children?: React.ReactNode
}

export interface TaskComponentProps extends BaseTaskProps {
  renderHeader: (props: TaskChildProps) => React.ReactNode
  renderContent: (props: TaskChildProps) => React.ReactNode
}

const Task: React.FC<TaskComponentProps> = ({ 
  variant, 
  task, 
  onClick, 
  controlButtons,
  renderHeader,
  renderContent,
  isFullWidth,
  onToggleFullWidth,
  onClose
}) => {
  const childProps: TaskChildProps = {
    variant,
    task,
    controlButtons,
    isFullWidth,
    onToggleFullWidth,
    onClose
  }

  return (
    <Card 
      className={`bg-card-light shadow-none border-none rounded-lg transition-colors duration-200 hover:bg-muted flex flex-col h-full
        ${variant === 'grid' ? 'cursor-pointer' : ''}`}
      onClick={variant === 'grid' ? onClick : undefined}
    >
      {renderHeader(childProps)}
      {renderContent(childProps)}
    </Card>
  )
}

const TaskHeader: React.FC<TaskChildProps> = ({ 
  task, 
  variant, 
  children, 
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose 
}) => (
  <CardHeader className="space-y-1.5 p-4 pr-4 flex flex-col items-start">
    <div className="flex justify-between items-start w-full">
      <div className="flex flex-col">
        <div className="text-lg font-bold">{task.type}</div>
        <div className="text-xs text-muted-foreground">{task.scorecard}</div>
        <div className="text-xs text-muted-foreground">{task.score}</div>
        {variant === 'detail' && (
          <div className="text-xs text-muted-foreground mt-1">{task.time}</div>
        )}
      </div>
      <div className="flex flex-col items-end">
        {variant === 'grid' ? (
          children
        ) : (
          <div className="flex gap-2">
            {onToggleFullWidth && (
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={onToggleFullWidth}
                className="bg-background hover:bg-background/90"
              >
                {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
              </Button>
            )}
            {onClose && (
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={onClose}
                className="bg-background hover:bg-background/90"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
            {controlButtons}
          </div>
        )}
        {variant === 'grid' && (
          <div className="text-xs text-muted-foreground flex items-center mt-1">
            {task.time}
          </div>
        )}
      </div>
    </div>
  </CardHeader>
)

const TaskContent: React.FC<TaskChildProps & {
  visualization?: React.ReactNode,
  customSummary?: React.ReactNode
}> = ({ task, variant, children, visualization, customSummary }) => (
  <CardContent className="p-4 pt-0 pb-4 flex flex-col flex-grow">
    <div className="flex flex-col justify-start items-start w-full">
      <div className="space-y-1 w-full">
        <div className="text-lg font-bold">
          {task.description && (
            <div className="text-sm text-muted-foreground">
              {task.description}
            </div>
          )}
          {customSummary ? customSummary : <div>{task.summary}</div>}
        </div>
      </div>
      {visualization && (
        <div className="w-full mt-4">{visualization}</div>
      )}
    </div>
    {children}
  </CardContent>
)

export { Task, TaskHeader, TaskContent }
