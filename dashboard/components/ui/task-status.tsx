import React, { useEffect, useState } from 'react'
import { SegmentedProgressBar, SegmentConfig } from './segmented-progress-bar'
import { ProgressBar } from './progress-bar'
import { ProgressBarTiming } from './progress-bar-timing'
import { Radio, Hand, ConciergeBell, Square, RectangleVertical, X, AlertTriangle } from 'lucide-react'
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
  variant?: 'grid' | 'detail' | 'nested'
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
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

export function TaskStatus({
  showStages = true,
  stages = [],
  currentStageName,
  processedItems,
  totalItems,
  startedAt,
  estimatedCompletionAt,
  status,
  stageConfigs,
  errorLabel = 'Failed',
  dispatchStatus,
  celeryTaskId,
  workerNodeId,
  showPreExecutionStages = false,
  command,
  statusMessage,
  errorMessage,
  completedAt,
  truncateMessages = true,
  variant,
  isFullWidth,
  onToggleFullWidth,
  onClose
}: TaskStatusProps) {
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

  // Get progress information from stages if available, otherwise use props
  const getProgressFromStages = () => {
    if (!stages || stages.length === 0) {
      return { processedItems, totalItems }
    }

    // For completed tasks, find the stage with the most progress
    if (status === 'COMPLETED') {
      const stageWithProgress = stages
        .filter(s => s.totalItems !== undefined && s.totalItems > 0)
        .sort((a, b) => (b.totalItems || 0) - (a.totalItems || 0))[0]
      
      if (stageWithProgress) {
        return {
          processedItems: stageWithProgress.processedItems,
          totalItems: stageWithProgress.totalItems
        }
      }
    }

    // For running tasks, start from current stage and work backwards
    const currentStageIndex = stages.findIndex(s => s.name === currentStageName)
    if (currentStageIndex === -1) {
      return { processedItems, totalItems }
    }

    // Check current stage first
    const currentStage = stages[currentStageIndex]
    if (currentStage.totalItems !== undefined && currentStage.totalItems !== null) {
      return {
        processedItems: currentStage.processedItems,
        totalItems: currentStage.totalItems
      }
    }

    // Look backwards through previous stages for progress info
    for (let i = currentStageIndex - 1; i >= 0; i--) {
      const stage = stages[i]
      if (stage.totalItems !== undefined && stage.totalItems !== null) {
        return {
          processedItems: stage.processedItems,
          totalItems: stage.totalItems
        }
      }
    }

    // Fallback to props if no stage has progress info
    return { processedItems, totalItems }
  }

  const { processedItems: effectiveProcessedItems, totalItems: effectiveTotalItems } = 
    getProgressFromStages()
  
  const progress = effectiveProcessedItems && effectiveTotalItems ? 
    (effectiveProcessedItems / effectiveTotalItems) * 100 : 0

  // Convert TaskStageConfig to SegmentConfig for the progress bar
  const segmentConfigs: SegmentConfig[] = stageConfigs ? [
    ...stageConfigs.map(stage => ({
      key: stage.name,
      label: stage.label,
      color: stage.status === 'PENDING' ? 'bg-neutral' : 
             stage.status === 'FAILED' ? 'bg-false' : 
             stage.color,
      status: stage.status
    })),
    // Only add completion segment if we have other stages
    ...(stageConfigs.length > 0 ? [{
      key: 'completion',
      label: status === 'FAILED' ? 'Failed' : 'Complete',
      color: status === 'FAILED' ? 'bg-false' : 'bg-true',
      status: status
    }] : [])
  ] : []

  const getPreExecutionStatus = () => {
    if (workerNodeId && workerNodeId.trim() !== '') {
      console.debug('Task claimed by worker:', workerNodeId);
      return { 
        message: 'Claimed...', 
        icon: Hand,
        animation: 'animate-wave'
      }
    }
    if (!celeryTaskId) {
      console.debug('Task announced, no celery ID yet');
      return { 
        message: 'Announced...', 
        icon: ConciergeBell,
        animation: 'animate-jiggle'
      }
    }
    console.debug('Task has celery ID:', celeryTaskId);
    return { 
      message: 'Announced...', 
      icon: Radio,
      animation: 'animate-pulse'
    }
  }

  // Only show pre-execution status when:
  // 1. Task is in PENDING state
  // 2. Has no stages (not started processing yet)
  // 3. Either has a worker node ID or showPreExecutionStages is true
  const shouldShowPreExecution = status === 'PENDING' && 
    (!stages || stages.length === 0) && 
    ((workerNodeId && workerNodeId.trim() !== '') || showPreExecutionStages)

  const preExecutionStatus = shouldShowPreExecution ? getPreExecutionStatus() : null
  const showEmptyState = !stages.length && !preExecutionStatus && status === 'PENDING'

  const displayMessage = isError && errorMessage ? errorMessage : statusMessage

  return (
    <div className="[&>*+*]:mt-2">
      <StyleTag />
      {variant === 'detail' && (
        <div className="flex justify-between items-center mb-4">
          <div className="flex-grow" />
          <div className="flex items-center space-x-2">
            {onToggleFullWidth && (
              <CardButton
                icon={isFullWidth ? RectangleVertical : Square}
                onClick={onToggleFullWidth}
              />
            )}
            {onClose && (
              <CardButton
                icon={X}
                onClick={onClose}
              />
            )}
          </div>
        </div>
      )}
      {(command || displayMessage || isFinished) && (
        <div className="rounded-lg bg-background px-1 py-1 space-y-1 -mx-1">
          {command && (
            <div className={`font-mono text-sm text-muted-foreground ${truncateMessages ? 'truncate' : 'whitespace-pre-wrap'}`}>
              $ {command}
            </div>
          )}
          <div className={cn(
            "text-sm flex items-center gap-2",
            truncateMessages ? 'truncate' : 'whitespace-pre-wrap',
            isError ? 'text-destructive font-medium' : ''
          )}>
            {isError && <AlertTriangle className="w-4 h-4 animate-pulse" />}
            {displayMessage || '\u00A0'}
          </div>
        </div>
      )}
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
        />
      )}
      {showStages && (
        <SegmentedProgressBar
          segments={segmentConfigs}
          currentSegment={status === 'FAILED' || status === 'COMPLETED' ? 'completion' : currentStageName || ''}
          error={status === 'FAILED'}
          errorLabel={errorLabel}
        />
      )}
      <ProgressBar
        progress={progress}
        processedItems={effectiveProcessedItems}
        totalItems={effectiveTotalItems}
        color={status === 'FAILED' ? 'false' : 'secondary'}
        showTiming={false}
      />
    </div>
  )
} 