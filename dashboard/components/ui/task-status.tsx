import React, { useEffect, useState, useMemo } from 'react'
import { SegmentedProgressBar, SegmentConfig } from './segmented-progress-bar'
import { ProgressBar } from './progress-bar'
import { ProgressBarTiming } from './progress-bar-timing'
import { Radio, Hand, ConciergeBell, Square, RectangleVertical, X, AlertTriangle, MessageSquareText, SquareChevronRight } from 'lucide-react'
import { cn } from "@/lib/utils"
import { StyleTag } from './style-tag'
import { CardButton } from '@/components/CardButton'

// Add custom animation styles
const animations = `
@keyframes jiggle {
  0%, 100% { transform: rotate(0deg); }
  5% { transform: rotate(15deg); }
  10% { transform: rotate(-13deg); }
  15% { transform: rotate(10deg); }
  20% { transform: rotate(0deg); }
}

.animate-jiggle {
  animation: jiggle 2s ease-in-out;
  animation-iteration-count: infinite;
  transform-origin: bottom center;
}

@keyframes wave {
  0%, 100% { transform: rotate(0deg); }
  5% { transform: rotate(-15deg); }
  10% { transform: rotate(13deg); }
  15% { transform: rotate(-10deg); }
  20% { transform: rotate(0deg); }
}

.animate-wave {
  animation: wave 2s ease-in-out;
  animation-iteration-count: infinite;
  transform-origin: bottom center;
}
`

export interface TaskStageConfig {
  key: string
  label: string
  color: string
  name: string
  order: number
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  processedItems?: number
  totalItems?: number
  startedAt?: string
  completedAt?: string
  estimatedCompletionAt?: string
  statusMessage?: string
  completed?: boolean
}

export interface TaskStatusProps {
  showStages?: boolean
  stages?: TaskStageConfig[]
  currentStageName?: string
  processedItems?: number
  totalItems?: number
  startedAt?: string
  estimatedCompletionAt?: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  command?: string
  statusMessage?: string
  errorMessage?: string
  stageConfigs?: TaskStageConfig[]
  isLoading?: boolean
  errorLabel?: string
  dispatchStatus?: string
  celeryTaskId?: string
  workerNodeId?: string
  showPreExecutionStages?: boolean
  completedAt?: string
  truncateMessages?: boolean
  variant?: 'grid' | 'detail' | 'nested' | 'list'
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  extra?: boolean
  isSelected?: boolean
  commandDisplay?: 'hide' | 'show' | 'full'
  statusMessageDisplay?: 'always' | 'never' | 'error-only'
  onCommandDisplayChange?: (display: 'show' | 'full') => void
}

function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${Math.floor(seconds)}s`
  }
  if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = Math.floor(seconds % 60)
    return `${minutes}m ${remainingSeconds}s`
  }
  const hours = Math.floor(seconds / 3600)
  const remainingMinutes = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${remainingMinutes}m`
}

export const TaskStatus: React.FC<TaskStatusProps> = ({
  showStages = false,
  stages = [],
  currentStageName,
  processedItems,
  totalItems,
  startedAt,
  estimatedCompletionAt,
  status,
  command,
  statusMessage,
  errorMessage,
  stageConfigs = [],
  isLoading,
  errorLabel,
  dispatchStatus,
  celeryTaskId,
  workerNodeId,
  showPreExecutionStages = false,
  completedAt,
  truncateMessages = false,
  variant = 'grid',
  isFullWidth = false,
  onToggleFullWidth,
  onClose,
  extra = false,
  isSelected = false,
  commandDisplay = 'show',
  statusMessageDisplay = 'always',
  onCommandDisplayChange
}) => {
  console.debug('TaskStatus render:', {
    command,
    commandDisplay,
    variant,
    truncateMessages
  });

  const [isMessageExpanded, setIsMessageExpanded] = useState(false);
  const isInProgress = status === 'RUNNING'
  const isFinished = status === 'COMPLETED' || status === 'FAILED'
  const isError = status === 'FAILED'

  // State for computed timing values
  const [elapsedTime, setElapsedTime] = useState<string>('')
  const [estimatedTimeRemaining, setEstimatedTimeRemaining] = useState<string>('')

  // Update timing values every second while not completed
  useEffect(() => {
    const updateTiming = () => {
      // If no task start time, show 0s
      if (!startedAt) {
        setElapsedTime('0s')
        return
      }

      const taskStartTime = new Date(startedAt)
      const endTime = completedAt ? new Date(completedAt) : new Date()

      // Calculate elapsed time from task start to end time
      const elapsedSeconds = Math.floor(
        (endTime.getTime() - taskStartTime.getTime()) / 1000
      )

      const formattedTime = formatDuration(elapsedSeconds)

      setElapsedTime(formattedTime)

      // Only show ETA if in progress and we have an estimate
      if (isInProgress && estimatedCompletionAt) {
        const estimated = new Date(estimatedCompletionAt)
        const remainingSeconds = Math.floor(
          (estimated.getTime() - endTime.getTime()) / 1000
        )
        if (remainingSeconds > 0) {
          setEstimatedTimeRemaining(formatDuration(remainingSeconds))
        } else {
          setEstimatedTimeRemaining('')
        }
      } else {
        setEstimatedTimeRemaining('')
      }
    }

    // Initial update
    updateTiming()

    // Update every second until completed
    const interval = !completedAt ? setInterval(updateTiming, 1000) : null

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [startedAt, estimatedCompletionAt, completedAt, isInProgress])

  // Find first running stage if currentStageName is undefined
  const effectiveCurrentStage = useMemo(() => {
    // If we have an explicit currentStageName, use it
    if (currentStageName) return currentStageName;

    // If task is completed or failed, use completion
    if (status === 'FAILED' || status === 'COMPLETED') return 'completion';

    // Find the first RUNNING stage from the stage configs
    const runningStage = stageConfigs.find(s => s.status === 'RUNNING');
    if (runningStage) return runningStage.name;

    // If no running stage, find the first PENDING stage
    const pendingStage = stageConfigs.find(s => s.status === 'PENDING');
    if (pendingStage) return pendingStage.name;

    // Default to empty string if no stages found
    return '';
  }, [currentStageName, status, stageConfigs]);

  // Convert TaskStageConfig to SegmentConfig for the progress bar
  const segments = useMemo(() => {
    const orderedStages = stageConfigs
      .sort((a, b) => a.order - b.order)  // Ensure stages are ordered
      .map(stage => {
        const isRunning = stage.status === 'RUNNING';
        const isCompleted = stage.status === 'COMPLETED';
        
        return {
          key: stage.name,
          label: stage.label || stage.name,
          color: stage.color || (
            isCompleted ? 'bg-primary' :
            isRunning ? 'bg-secondary' :
            stage.status === 'FAILED' ? 'bg-false' :
            'bg-neutral'
          ),
          status: stage.status,
          completed: isCompleted
        };
      });

    // Always add completion segment with appropriate color based on status
    orderedStages.push({
      key: 'completion',
      label: 'Complete',
      color: status === 'COMPLETED' ? 'bg-true' :
             status === 'FAILED' ? 'bg-false' :
             'bg-neutral',
      status: status === 'COMPLETED' ? 'COMPLETED' :
              status === 'FAILED' ? 'FAILED' :
              'PENDING',
      completed: status === 'COMPLETED'
    });

    return orderedStages;
  }, [stageConfigs, status]);

  // Update the progress calculation logic
  const { processedItems: effectiveProcessedItems, totalItems: effectiveTotalItems } = useMemo(() => {
    // First try to get progress from stages
    if (stages?.length > 0) {
      // First try to find a RUNNING stage with progress info
      const runningStage = stages.find(stage => {
        return stage.status === 'RUNNING';
      });

      if (runningStage) {
        const proc = Number(runningStage.processedItems);
        const tot = Number(runningStage.totalItems);
        // Only use the stage's progress if it has valid numbers
        if (!isNaN(proc) && !isNaN(tot) && tot > 0) {
          return {
            processedItems: proc,
            totalItems: tot
          };
        }
      }

      // If no running stage found with progress, fall back to the last stage with progress
      const sortedStages = [...stages].sort((a, b) => (b.order || 0) - (a.order || 0));
      const stageWithProgress = sortedStages.find(stage => {
        const proc = Number(stage.processedItems);
        const tot = Number(stage.totalItems);
        return !isNaN(proc) && !isNaN(tot) && tot > 0;
      });

      if (stageWithProgress) {
        const proc = Number(stageWithProgress.processedItems);
        const tot = Number(stageWithProgress.totalItems);
        return {
          processedItems: proc,
          totalItems: tot
        };
      }
    }
    
    // If no stages have progress info, fall back to direct processedItems/totalItems
    const directProcessed = Number(processedItems);
    const directTotal = Number(totalItems);
    
    if (!isNaN(directProcessed) && !isNaN(directTotal) && directTotal > 0) {
      return {
        processedItems: directProcessed,
        totalItems: directTotal
      };
    }
    
    // If no valid progress info found anywhere, return zeros
    return {
      processedItems: 0,
      totalItems: 0
    };
  }, [stages, processedItems, totalItems]);

  // Calculate progress percentage
  const progress = useMemo(() => 
    effectiveTotalItems > 0 ? 
      Math.round((effectiveProcessedItems / effectiveTotalItems) * 100) : 
      0
  , [effectiveProcessedItems, effectiveTotalItems]);

  // Update the progress bar color based on status
  const progressBarColor = useMemo(() => 
    status === 'COMPLETED' ? 'primary' :
    status === 'FAILED' ? 'false' :
    'secondary'
  , [status]);

  const getPreExecutionStatus = () => {
    if (workerNodeId && workerNodeId.trim() !== '') {
      return { 
        message: 'Claimed...', 
        icon: Hand,
        animation: 'animate-wave'
      }
    }
    if (!celeryTaskId) {
      return { 
        message: 'Announced...', 
        icon: ConciergeBell,
        animation: 'animate-jiggle'
      }
    }
    return { 
      message: 'Announced...', 
      icon: Radio,
      animation: 'animate-pulse'
    }
  }

  // Show pre-execution status when:
  // 1. Task is in PENDING state
  // 2. Has no stages (not started processing yet)
  // 3. Either has a worker node ID or showPreExecutionStages is true
  const shouldShowPreExecution = status === 'PENDING' && 
    (!stages || stages.length === 0) && 
    ((workerNodeId && workerNodeId.trim() !== '') || showPreExecutionStages)

  const preExecutionStatus = shouldShowPreExecution ? getPreExecutionStatus() : null
  const showEmptyState = !stages.length && !preExecutionStatus && status === 'PENDING'

  const displayMessage = isError && errorMessage ? errorMessage : statusMessage

  const handleCommandClick = () => {
    if (commandDisplay === 'hide' || !onCommandDisplayChange) return;
    onCommandDisplayChange(commandDisplay === 'show' ? 'full' : 'show');
  };

  const handleMessageClick = () => {
    setIsMessageExpanded(prev => !prev);
  };

  // If the variant is 'list', render only a simple progress bar
  if (variant === 'list') {
    return (
      <div className="[&>*+*]:mt-2">
        <StyleTag />
        <div className="rounded-lg bg-background px-1 py-1 space-y-1 -mx-1">
          {command && commandDisplay !== 'hide' && (
            <div 
              className={cn(
                "font-mono text-sm text-muted-foreground leading-6 flex items-start gap-1",
                {
                  "overflow-hidden": commandDisplay === 'show',
                  "cursor-pointer hover:text-foreground": !!onCommandDisplayChange
                }
              )}
              onClick={handleCommandClick}
              role={onCommandDisplayChange ? "button" : undefined}
              tabIndex={onCommandDisplayChange ? 0 : undefined}
              onKeyDown={onCommandDisplayChange ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleCommandClick();
                }
              } : undefined}
            >
              <SquareChevronRight 
                className={cn(
                  "w-4 h-4 flex-shrink-0 mt-1",
                  onCommandDisplayChange && "cursor-pointer"
                )} 
              />
              <span className={cn({
                "truncate": commandDisplay === 'show',
                "whitespace-pre-wrap break-all": commandDisplay === 'full'
              })}>{command}</span>
            </div>
          )}
          {(statusMessageDisplay === 'always' || 
            (statusMessageDisplay === 'error-only' && isError) ||
            (statusMessageDisplay === 'never' && isError && errorMessage)) && (
            <div 
              className={cn(
                "text-sm flex items-center gap-1 cursor-pointer hover:text-foreground",
                !isMessageExpanded && "truncate",
                isMessageExpanded && "whitespace-pre-wrap",
                isError ? 'text-destructive font-medium' : ''
              )}
              onClick={handleMessageClick}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleMessageClick();
                }
              }}
            >
              {isError ? (
                <AlertTriangle className="w-4 h-4 animate-pulse flex-shrink-0" />
              ) : displayMessage && (
                <MessageSquareText className="w-4 h-4 flex-shrink-0" />
              )}
              {displayMessage || '\u00A0'}
            </div>
          )}
        </div>
        {showEmptyState ? (
          <div className="flex items-center gap-1 text-sm text-muted-foreground">
            <Radio className="w-4 h-4 animate-pulse" />
            <span>Announced...</span>
          </div>
        ) : preExecutionStatus ? (
          <div className="flex items-center gap-1 text-sm text-muted-foreground">
            <preExecutionStatus.icon className={`w-4 h-4 ${preExecutionStatus.animation}`} />
            <span>{preExecutionStatus.message}</span>
          </div>
        ) : (
          <ProgressBarTiming
            elapsedTime={elapsedTime}
            estimatedTimeRemaining={estimatedTimeRemaining}
            isInProgress={isInProgress}
            className="text-muted-foreground"
          />
        )}
        {showStages && (
          <ProgressBar
            progress={progress}
            processedItems={effectiveProcessedItems}
            totalItems={effectiveTotalItems}
            color={progressBarColor}
            showTiming={false}
            isSelected={isSelected}
          />
        )}
      </div>
    );
  }

  return (
    <div className="[&>*+*]:mt-2">
      <StyleTag />
      <div className="rounded-lg bg-background px-1 py-1 space-y-1 -mx-1">
        {command && commandDisplay !== 'hide' && (
          <div 
            className={cn(
              "font-mono text-sm text-muted-foreground leading-6 flex items-start gap-1",
              {
                "overflow-hidden": commandDisplay === 'show',
                "cursor-pointer hover:text-foreground": !!onCommandDisplayChange
              }
            )}
            onClick={handleCommandClick}
            role={onCommandDisplayChange ? "button" : undefined}
            tabIndex={onCommandDisplayChange ? 0 : undefined}
            onKeyDown={onCommandDisplayChange ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleCommandClick();
              }
            } : undefined}
          >
            <SquareChevronRight 
              className={cn(
                "w-4 h-4 flex-shrink-0 mt-1",
                onCommandDisplayChange && "cursor-pointer"
              )} 
            />
            <span className={cn({
              "truncate": commandDisplay === 'show',
              "whitespace-pre-wrap break-all": commandDisplay === 'full'
            })}>{command}</span>
          </div>
        )}
        {(statusMessageDisplay === 'always' || 
          (statusMessageDisplay === 'error-only' && isError) ||
          (statusMessageDisplay === 'never' && isError && errorMessage)) && (
          <div 
            className={cn(
              "text-sm flex items-center gap-1 cursor-pointer hover:text-foreground",
              !isMessageExpanded && "truncate",
              isMessageExpanded && "whitespace-pre-wrap",
              isError ? 'text-destructive font-medium' : ''
            )}
            onClick={handleMessageClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleMessageClick();
              }
            }}
          >
            {isError ? (
              <AlertTriangle className="w-4 h-4 animate-pulse flex-shrink-0" />
            ) : displayMessage && (
              <MessageSquareText className="w-4 h-4 flex-shrink-0" />
            )}
            {displayMessage || '\u00A0'}
          </div>
        )}
      </div>
      {showEmptyState ? (
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <Radio className="w-4 h-4 animate-pulse" />
          <span>Announced...</span>
        </div>
      ) : preExecutionStatus ? (
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <preExecutionStatus.icon className={`w-4 h-4 ${preExecutionStatus.animation}`} />
          <span>{preExecutionStatus.message}</span>
        </div>
      ) : (
        <ProgressBarTiming
          elapsedTime={elapsedTime}
          estimatedTimeRemaining={estimatedTimeRemaining}
          isInProgress={isInProgress}
          className="text-muted-foreground"
        />
      )}
      {showStages && (
        <SegmentedProgressBar
          segments={segments}
          currentSegment={effectiveCurrentStage}
          error={status === 'FAILED'}
          errorLabel={errorLabel}
          isSelected={isSelected}
        />
      )}
      <ProgressBar
        progress={progress}
        processedItems={effectiveProcessedItems}
        totalItems={effectiveTotalItems}
        color={progressBarColor}
        showTiming={false}
        isSelected={isSelected}
      />
    </div>
  )
} 