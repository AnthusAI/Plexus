import React from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Square, RectangleVertical, X } from 'lucide-react'
import { formatTimeAgo } from '@/utils/format-time'
import { CardButton } from '@/components/CardButton'
import { ActionStatus, ActionStageConfig } from './ui/action-status'

export interface BaseTaskProps<TData = unknown> {
  variant: 'grid' | 'detail' | 'nested'
  task: {
    id: string
    type: string
    scorecard: string
    score: string
    time: string
    summary?: string
    description?: string
    data?: TData
    stages?: ActionStageConfig[]
    currentStageName?: string
    processedItems?: number
    totalItems?: number
    elapsedTime?: string
    estimatedTimeRemaining?: string
    status?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  }
  onClick?: () => void
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  isLoading?: boolean
  error?: string
  onRetry?: () => void
}

interface TaskChildProps<TData = unknown> extends BaseTaskProps<TData> {
  children?: React.ReactNode
  showProgress?: boolean
}

export interface TaskComponentProps<TData = unknown> extends BaseTaskProps<TData> {
  renderHeader: (props: TaskChildProps<TData>) => React.ReactNode
  renderContent: (props: TaskChildProps<TData>) => React.ReactNode
  showProgress?: boolean
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
  onClose,
  showProgress = true,
  isLoading = false,
  error,
  onRetry
}: TaskComponentProps<TData>) => {
  const childProps: TaskChildProps<TData> = {
    variant,
    task,
    controlButtons,
    isFullWidth,
    onToggleFullWidth,
    onClose,
    showProgress,
    isLoading,
    error,
    onRetry
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
      className={`
        bg-card shadow-none border-none rounded-lg transition-colors duration-200 
        flex flex-col h-full min-w-[300px]
        ${variant === 'grid' ? 'cursor-pointer' : ''}
        ${isLoading ? 'opacity-70' : ''}
      `}
      onClick={variant === 'grid' && !isLoading ? onClick : undefined}
      role={variant === 'grid' ? 'button' : 'article'}
      tabIndex={variant === 'grid' ? 0 : undefined}
      onKeyDown={variant === 'grid' ? (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick?.()
        }
      } : undefined}
      aria-busy={isLoading}
      aria-disabled={isLoading}
    >
      <div className="flex-none">
        {renderHeader(childProps)}
      </div>
      <CardContent className="flex-1 min-h-0 p-4">
        {error ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-4">
            <div className="text-destructive mb-2">{error}</div>
            {onRetry && (
              <Button 
                variant="outline" 
                size="sm" 
                onClick={onRetry}
                className="mt-2"
              >
                Retry
              </Button>
            )}
          </div>
        ) : (
          renderContent(childProps)
        )}
      </CardContent>
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
  onClose,
  isLoading
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
                  icon={isFullWidth ? RectangleVertical : Square}
                  onClick={onToggleFullWidth}
                  disabled={isLoading}
                  aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
                />
              )}
              {onClose && (
                <CardButton
                  icon={X}
                  onClick={onClose}
                  disabled={isLoading}
                  aria-label="Close"
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
  customSummary,
  showProgress = true,
  isLoading
}: TaskChildProps<TData> & {
  visualization?: React.ReactNode,
  customSummary?: React.ReactNode
}) => {
  // Find the current stage's status message
  const currentStage = task.stages?.find(stage => stage.name === task.currentStageName)
  const statusMessage = currentStage?.statusMessage

  return (
    <CardContent className="h-full p-0 flex flex-col flex-1">
      {variant === 'grid' ? (
        <div className="flex flex-col h-full">
          <div className="space-y-1 w-full">
            <div className="text-lg font-bold">
              {customSummary ? customSummary : <div>{task.summary}</div>}
            </div>
          </div>
          {showProgress && task.stages && (
            <div className="mt-4">
              <ActionStatus
                showStages={true}
                stages={task.stages || []}
                currentStageName={task.currentStageName}
                processedItems={task.processedItems}
                totalItems={task.totalItems}
                elapsedTime={task.elapsedTime}
                estimatedTimeRemaining={task.estimatedTimeRemaining}
                status={task.status || 'PENDING'}
                command={task.description}
                statusMessage={statusMessage}
                stageConfigs={task.stages?.map(stage => {
                  const stageName = stage.name.toLowerCase()
                  let color = 'bg-primary'
                  
                  // Only the middle processing stage should be secondary
                  if (stageName === 'processing') {
                    color = 'bg-secondary'
                  }
                  
                  return {
                    key: stage.name,
                    label: stage.name,
                    color,
                    tooltip: `${stage.name} - ${stage.status}${
                      stage.processedItems !== undefined && stage.totalItems 
                        ? ` (${stage.processedItems}/${stage.totalItems})`
                        : ''
                    }${
                      stage.elapsedTime
                        ? `\nElapsed: ${stage.elapsedTime}`
                        : ''
                    }`
                  }
                })}
                isLoading={isLoading}
              />
            </div>
          )}
        </div>
      ) : (
        <div className="flex flex-col h-full">
          {children}
          {showProgress && task.stages && (
            <div className="mt-4">
              <ActionStatus
                showStages={true}
                stages={task.stages || []}
                currentStageName={task.currentStageName}
                processedItems={task.processedItems}
                totalItems={task.totalItems}
                elapsedTime={task.elapsedTime}
                estimatedTimeRemaining={task.estimatedTimeRemaining}
                status={task.status || 'PENDING'}
                command={task.description}
                statusMessage={statusMessage}
                stageConfigs={task.stages?.map(stage => {
                  const stageName = stage.name.toLowerCase()
                  let color = 'bg-primary'
                  
                  // Only the middle processing stage should be secondary
                  if (stageName === 'processing') {
                    color = 'bg-secondary'
                  }
                  
                  return {
                    key: stage.name,
                    label: stage.name,
                    color,
                    tooltip: `${stage.name} - ${stage.status}${
                      stage.processedItems !== undefined && stage.totalItems 
                        ? ` (${stage.processedItems}/${stage.totalItems})`
                        : ''
                    }${
                      stage.elapsedTime
                        ? `\nElapsed: ${stage.elapsedTime}`
                        : ''
                    }`
                  }
                })}
                isLoading={isLoading}
              />
            </div>
          )}
        </div>
      )}
    </CardContent>
  )
}

export { Task, TaskHeader, TaskContent }
