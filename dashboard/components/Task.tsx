import React from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Square, RectangleVertical, X, Activity, FlaskConical, FlaskRound, TestTubes } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { CardButton } from '@/components/CardButton'
import { TaskStatus, TaskStageConfig } from './ui/task-status'
import { BaseTaskData } from '@/types/base'
import { cn } from '@/lib/utils'

export interface BaseTaskProps<TData extends BaseTaskData = BaseTaskData> {
  variant: 'grid' | 'detail' | 'nested'
  task: {
    id: string
    type: string
    scorecard: string
    score: string
    time: string
    description?: string
    command?: string
    data?: TData
    stages?: TaskStageConfig[]
    currentStageName?: string
    processedItems?: number
    totalItems?: number
    startedAt?: string
    estimatedCompletionAt?: string
    status?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
    dispatchStatus?: 'DISPATCHED'
    celeryTaskId?: string
    workerNodeId?: string
    completedAt?: string
    errorMessage?: string
  }
  onClick?: () => void
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  isLoading?: boolean
  error?: string
  onRetry?: () => void
  showPreExecutionStages?: boolean
  isSelected?: boolean
  extra?: boolean
}

interface TaskChildProps<TData extends BaseTaskData = BaseTaskData> extends BaseTaskProps<TData> {
  children?: React.ReactNode
  showProgress?: boolean
  hideTaskStatus?: boolean
}

export interface TaskComponentProps<TData extends BaseTaskData = BaseTaskData> extends BaseTaskProps<TData> {
  renderHeader: (props: TaskChildProps<TData>) => React.ReactNode
  renderContent: (props: TaskChildProps<TData>) => React.ReactNode
  showProgress?: boolean
}

// Add the safe date formatting helper
const formatTaskTime = (dateString: string | null | undefined) => {
  if (!dateString) return '';
  
  try {
    const date = new Date(dateString);
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return '';
    }
    return formatDistanceToNow(date, { 
      addSuffix: true,
      includeSeconds: true
    }).replace('about ', '');
  } catch (e) {
    console.warn('Invalid task time format:', dateString);
    return '';
  }
};

// Add helper function to get task icon
const getTaskIcon = (type: string) => {
  // Convert to lowercase for case-insensitive comparison
  const taskType = type.toLowerCase()
  
  if (taskType.includes('evaluation')) {
    if (taskType.includes('accuracy')) {
      return <FlaskConical className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.5} />
    }
    if (taskType.includes('consistency')) {
      return <FlaskRound className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.5} />
    }
    if (taskType.includes('alignment')) {
      return <TestTubes className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.5} />
    }
    return <FlaskConical className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.5} />
  }
  
  return <Activity className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.5} />
}

const Task = <TData extends BaseTaskData = BaseTaskData>({ 
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
  onRetry,
  showPreExecutionStages,
  isSelected = false,
  extra = false
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
    onRetry,
    showPreExecutionStages
  }

  if (variant === 'nested') {
    return (
      <div className="bg-background/50 p-3">
        {renderHeader(childProps)}
        {renderContent(childProps)}
      </div>
    )
  }

  return (
    <div 
      className={`
        transition-colors duration-200 
        flex flex-col h-full p-3 rounded-lg
        ${variant === 'grid' ? 'cursor-pointer hover:bg-accent/50' : ''}
        ${variant === 'grid' ? (isSelected ? 'bg-card' : 'bg-frame') : 'bg-card'}
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
      <div className="flex-1 min-h-0">
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
      </div>
    </div>
  )
}

// Update the TaskHeader component
const TaskHeader = <TData extends BaseTaskData = BaseTaskData>({ 
  task, 
  variant, 
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  isLoading
}: TaskChildProps<TData>) => {
  const formattedTime = formatTaskTime(task.time);
  const taskIcon = getTaskIcon(task.type);

  return (
    <CardHeader className={cn(
      "space-y-1.5 p-0 flex flex-col items-start",
      variant === 'detail' && "px-1"
    )}>
      <div className="flex justify-between items-start w-full">
        <div className="flex flex-col pb-1">
          <div className="text-sm">{task.scorecard || '\u00A0'}</div>
          <div className="text-sm">{task.score || '\u00A0'}</div>
          {variant !== 'grid' && (
            <div className="text-sm">{task.type}</div>
          )}
          <div className="text-xs text-muted-foreground mt-1">{formattedTime}</div>
        </div>
        <div className="flex flex-col items-end">
          {variant === 'grid' ? (
            <>
              <div className="text-sm">{task.type}</div>
              <div className="mt-1">{taskIcon}</div>
            </>
          ) : (
            <>
              <div className="flex gap-2">
                {controlButtons}
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
              </div>
            </>
          )}
        </div>
      </div>
    </CardHeader>
  )
}

const TaskContent = <TData extends BaseTaskData = BaseTaskData>({ 
  task, 
  variant, 
  children, 
  visualization,
  showProgress = true,
  hideTaskStatus = false,
  isLoading,
  showPreExecutionStages
}: TaskChildProps<TData> & {
  visualization?: React.ReactNode
  hideTaskStatus?: boolean
}) => {
  // Get status message from current stage or last completed stage if task is done
  const statusMessage = (() => {
    if (!task.stages?.length) return undefined
    if (task.status === 'FAILED') {
      // For failed tasks, find the failed stage's status message
      const failedStage = task.stages.find(stage => stage.status === 'FAILED')
      return failedStage?.statusMessage
    }
    if (task.status === 'COMPLETED') {
      // Find the last stage with a status message
      return [...task.stages]
        .reverse()
        .find(stage => stage.statusMessage)?.statusMessage
    }
    // If there's a running stage, use its message
    const runningStage = task.stages.find(stage => stage.status === 'RUNNING')
    if (runningStage) {
      return runningStage.statusMessage
    }
    // If all stages are pending, use the first stage's message
    if (task.stages.every(stage => stage.status === 'PENDING')) {
      const firstStage = [...task.stages].sort((a, b) => a.order - b.order)[0]
      return firstStage?.statusMessage
    }
    // Otherwise use current stage's message
    return task.stages.find(stage => stage.name === task.currentStageName)?.statusMessage
  })()

  return (
    <CardContent className="h-full p-0 flex flex-col flex-1">
      {showProgress && !hideTaskStatus && task.stages && (
        <div>
          <TaskStatus
            showStages={true}
            stages={task.stages}
            stageConfigs={task.stages.map(stage => ({
              key: stage.name,
              label: stage.label || stage.name,
              color: stage.color || 'bg-primary',
              name: stage.name,
              order: stage.order,
              status: stage.status,
              processedItems: stage.processedItems,
              totalItems: stage.totalItems,
              statusMessage: stage.statusMessage
            }))}
            currentStageName={task.currentStageName}
            processedItems={task.processedItems}
            totalItems={task.totalItems}
            startedAt={task.startedAt}
            estimatedCompletionAt={task.estimatedCompletionAt}
            status={task.status || 'PENDING'}
            command={task.command || task.data?.command}
            statusMessage={statusMessage}
            errorMessage={task.errorMessage}
            dispatchStatus={task.dispatchStatus}
            celeryTaskId={task.celeryTaskId}
            workerNodeId={task.workerNodeId}
            showPreExecutionStages={showPreExecutionStages}
            completedAt={task.completedAt}
            truncateMessages={variant === 'grid'}
          />
        </div>
      )}
      {children}
    </CardContent>
  )
}

export { Task, TaskHeader, TaskContent }
