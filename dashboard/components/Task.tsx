import React from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Square, Columns2, X, Activity, FlaskConical, FlaskRound, TestTubes, FileText, FileBarChart } from 'lucide-react'
import { CardButton } from '@/components/CardButton'
import { TaskStatus, TaskStageConfig } from './ui/task-status'
import { BaseTaskData } from '@/types/base'
import { cn } from '@/lib/utils'
import { Timestamp } from './ui/timestamp'

export interface BaseTaskProps<TData extends BaseTaskData = BaseTaskData> {
  variant: 'grid' | 'detail' | 'nested' | 'bare'
  task: {
    id: string
    type: string
    name?: string
    description?: string
    scorecard: string
    score: string
    time: string
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
  commandDisplay?: 'hide' | 'show' | 'full'
  statusMessageDisplay?: 'always' | 'never' | 'error-only'
}

interface TaskChildProps<TData extends BaseTaskData = BaseTaskData> extends BaseTaskProps<TData> {
  children?: React.ReactNode
  showProgress?: boolean
  hideTaskStatus?: boolean
  isSelected?: boolean
}

export interface TaskComponentProps<TData extends BaseTaskData = BaseTaskData> extends BaseTaskProps<TData> {
  renderHeader: (props: TaskChildProps<TData>) => React.ReactNode
  renderContent: (props: TaskChildProps<TData>) => React.ReactNode
  showProgress?: boolean
  isSelected?: boolean
}

// Add helper function to get task icon
const getTaskIcon = (type: string) => {
  // Convert to lowercase for case-insensitive comparison
  const taskType = type.toLowerCase()
  
  // Add check for Report type
  if (taskType.includes('report')) {
    return <FileBarChart className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
  }
  
  if (taskType.includes('evaluation')) {
    if (taskType.includes('accuracy')) {
      return <FlaskConical className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
    }
    if (taskType.includes('consistency')) {
      return <FlaskRound className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
    }
    if (taskType.includes('alignment')) {
      return <TestTubes className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
    }
    return <FlaskConical className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
  }
  
  return <Activity className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
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
  extra = false,
  commandDisplay = 'show',
  statusMessageDisplay = 'always'
}: TaskComponentProps<TData>) => {
  // Force isSelected to true in detail mode
  const effectiveIsSelected = variant === 'detail' ? true : isSelected;

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
    showPreExecutionStages,
    isSelected: effectiveIsSelected,
    commandDisplay,
    statusMessageDisplay,
    extra
  }

  if (variant === 'nested') {
    return (
      <div className="bg-background/50 p-3">
        {renderHeader(childProps)}
        {renderContent(childProps)}
      </div>
    )
  }

  // Add a check for the 'bare' variant to render only content
  if (variant === 'bare') {
    return <>{renderContent(childProps)}</>;
  }

  return (
    <div 
      className={cn(
        "transition-colors duration-200 flex flex-col h-full rounded-lg w-full max-w-full relative",
        variant === 'grid' ? 'cursor-pointer' : '',
        effectiveIsSelected ? 'bg-card-selected' : variant === 'grid' ? 'bg-card hover:bg-accent' : 'bg-card',
        (effectiveIsSelected && variant === 'grid') && "selected-border-rounded"
      )}
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
      <div className="flex-none p-3 w-full max-w-full overflow-hidden relative z-10">
        {renderHeader(childProps)}
      </div>
      <div className="flex-1 min-h-0 relative z-10">
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
  const taskIcon = getTaskIcon(task.type);

  // Add a console log to debug the onClose function
  const handleClose = () => {
    console.log('TaskHeader: Close button clicked, onClose function:', !!onClose);
    if (onClose) {
      onClose();
    }
  };

  return (
    <CardHeader className={cn(
      "space-y-1.5 p-0 flex flex-col items-start w-full max-w-full",
      variant === 'detail' && "px-1"
    )}>
      <div className="flex justify-between items-start w-full max-w-full gap-3 overflow-hidden">
        <div className="flex flex-col pb-1 leading-none min-w-0 flex-1 overflow-hidden">
          {variant === 'detail' && (
            <div className="flex items-center gap-2 mb-3">
              <Activity className="h-5 w-5 text-muted-foreground" />
              <span className="text-lg font-semibold text-muted-foreground">Task</span>
            </div>
          )}
          {task.name && (
            <div className="font-semibold text-sm truncate">{task.name}</div>
          )}
          {task.scorecard && task.scorecard.trim() !== '' && (
            <div className="font-semibold text-sm truncate">{task.scorecard}</div>
          )}
          {task.score && task.score.trim() !== '' && (
            <div className="font-semibold text-sm truncate">{task.score}</div>
          )}
          <Timestamp time={task.time} variant="relative" />
        </div>
        <div className="flex flex-col items-end flex-shrink-0">
          {variant === 'grid' ? (
            <div className="flex flex-col items-center gap-1">
              <div className="text-muted-foreground">{taskIcon}</div>
              <div className="text-xs text-muted-foreground text-center">
                {(() => {
                  const [firstWord, ...restWords] = task.type.split(/\s+/);
                  return (
                    <>
                      {firstWord}<br />
                      {restWords.join(' ')}
                    </>
                  );
                })()}
              </div>
            </div>
          ) : (
            <>
              <div className="flex gap-2">
                {controlButtons}
                {onToggleFullWidth && (
                  <CardButton
                    icon={isFullWidth ? Columns2 : Square}
                    onClick={onToggleFullWidth}
                    disabled={isLoading}
                    aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
                  />
                )}
                {onClose && (
                  <CardButton
                    icon={X}
                    onClick={handleClose}
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
  showPreExecutionStages,
  isSelected = false,
  commandDisplay = 'show',
  statusMessageDisplay = 'always',
  extra = false
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
    <CardContent className={cn(
      "h-full p-0 flex flex-col flex-1",
      variant === 'grid' ? 'px-3 pb-3' : ''
    )}>
      {!hideTaskStatus && (
        <div className={variant === 'detail' ? 'px-3' : ''}>
          <TaskStatus
            showStages={showProgress}
            stages={task.stages || []}
            currentStageName={task.currentStageName}
            processedItems={task.processedItems}
            totalItems={task.totalItems}
            startedAt={task.startedAt}
            estimatedCompletionAt={task.estimatedCompletionAt}
            status={task.status || 'PENDING'}
            command={task.command || task.description}
            statusMessage={statusMessage}
            errorMessage={task.errorMessage}
            dispatchStatus={task.dispatchStatus}
            celeryTaskId={task.celeryTaskId}
            workerNodeId={task.workerNodeId}
            showPreExecutionStages={showPreExecutionStages}
            completedAt={task.completedAt}
            truncateMessages={variant === 'grid'}
            isSelected={isSelected}
            variant={variant}
            commandDisplay={commandDisplay}
            statusMessageDisplay={statusMessageDisplay}
            extra={extra}
          />
        </div>
      )}
      {children}
    </CardContent>
  )
}

export { Task, TaskHeader, TaskContent }
