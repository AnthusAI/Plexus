import React from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Square, Columns2, X } from 'lucide-react'
import { formatTimeAgo } from '@/utils/format-time'
import { CardButton } from '@/components/CardButton'

export interface BaseTaskProps<TData = unknown> {
  variant: 'grid' | 'detail' | 'nested'
  task: {
    id: string
    type: string
    scorecard: string
    score: string
    time: string
    summary: string
    description?: string
    data?: TData
  }
  onClick?: () => void
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
}

interface TaskChildProps<TData = unknown> extends BaseTaskProps<TData> {
  children?: React.ReactNode
}

export interface TaskComponentProps<TData = unknown> extends BaseTaskProps<TData> {
  renderHeader: (props: TaskChildProps<TData>) => React.ReactNode
  renderContent: (props: TaskChildProps<TData>) => React.ReactNode
}

const Task = <TData = unknown>({ 
  variant, 
  task, 
  onClick, 
  controlButtons,
  renderHeader,
  renderContent,
  isFullWidth,
  onToggleFullWidth,
  onClose
}: TaskComponentProps<TData>) => {
  const childProps: TaskChildProps<TData> = {
    variant,
    task,
    controlButtons,
    isFullWidth,
    onToggleFullWidth,
    onClose
  }

  if (variant === 'nested') {
    return (
      <div className="bg-background/50 p-3 rounded-md">
        {renderHeader(childProps)}
        {renderContent(childProps)}
      </div>
    )
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

const TaskHeader = <TData = unknown>({ 
  task, 
  variant, 
  children, 
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose 
}: TaskChildProps<TData>) => {
  const formattedTime = formatTimeAgo(task.time, variant === 'grid')

  return (
    <CardHeader className="space-y-1.5 p-4 pr-4 flex flex-col items-start">
      <div className="flex justify-between items-start w-full">
        <div className="flex flex-col">
          <div className="text-lg font-bold">{task.type}</div>
          <div className="text-xs text-muted-foreground">{task.scorecard}</div>
          <div className="text-xs text-muted-foreground">{task.score}</div>
          {variant === 'detail' && (
            <div className="text-xs text-muted-foreground mt-1">{formattedTime}</div>
          )}
        </div>
        <div className="flex flex-col items-end">
          {variant === 'grid' ? (
            children
          ) : (
            <div className="flex gap-2">
              {onToggleFullWidth && (
                <CardButton
                  icon={isFullWidth ? Columns2 : Square}
                  onClick={onToggleFullWidth}
                />
              )}
              {onClose && (
                <CardButton
                  icon={X}
                  onClick={onClose}
                />
              )}
              {controlButtons}
            </div>
          )}
          {variant === 'grid' && (
            <div className="text-xs text-muted-foreground flex items-center mt-1">
              {formattedTime}
            </div>
          )}
        </div>
      </div>
    </CardHeader>
  )
}

const TaskContent = <TData = unknown>({ 
  task, 
  variant, 
  children, 
  visualization, 
  customSummary 
}: TaskChildProps<TData> & {
  visualization?: React.ReactNode,
  customSummary?: React.ReactNode
}) => (
  <CardContent className="p-4 pt-0 pb-4 flex flex-col flex-1">
    <div className="flex flex-col h-full">
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
        <div className="flex-1 w-full mt-4">{visualization}</div>
      )}
    </div>
    {children}
  </CardContent>
)

export { Task, TaskHeader, TaskContent }
