import React, { useEffect, useState } from 'react'
import { SegmentedProgressBar, SegmentConfig } from './segmented-progress-bar'
import { ProgressBar } from './progress-bar'
import { ProgressBarTiming } from './progress-bar-timing'
import { Radio, Hand, ConciergeBell, Square, RectangleVertical, X } from 'lucide-react'
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
  completedAt,
  truncateMessages = true,
  variant,
  isFullWidth,
  onToggleFullWidth,
  onClose
}: TaskStatusProps) {
  const isInProgress = status === 'RUNNING'
  const isFinished = status === 'COMPLETED' || status === 'FAILED'

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

      console.log('Timing Debug:', {
        startedAt,
        completedAt,
        rawStartTime: new Date(startedAt),
        rawEndTime: completedAt ? new Date(completedAt) : new Date(),
      })

      const taskStartTime = new Date(startedAt)
      const endTime = completedAt ? new Date(completedAt) : new Date()

      // Log the actual timestamps we're using
      console.log('Timestamps:', {
        startTimeMs: taskStartTime.getTime(),
        endTimeMs: endTime.getTime(),
        difference: endTime.getTime() - taskStartTime.getTime(),
        calculatedSeconds: Math.floor((endTime.getTime() - taskStartTime.getTime()) / 1000)
      })

      // Calculate elapsed time from task start to end time
      const elapsedSeconds = Math.floor(
        (endTime.getTime() - taskStartTime.getTime()) / 1000
      )

      const formattedTime = formatDuration(elapsedSeconds)
      console.log('Final time:', {
        elapsedSeconds,
        formattedTime
      })

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

    // Start from the current stage and work backwards
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
    if (!dispatchStatus) return { 
      message: 'Starting...', 
      icon: Radio,
      animation: 'animate-pulse'
    }
    if (!celeryTaskId) return { 
      message: 'Task announced...', 
      icon: ConciergeBell,
      animation: 'animate-jiggle'
    }
    if (!workerNodeId) return { 
      message: 'Task claimed.', 
      icon: Hand,
      animation: 'animate-wave'
    }
    return null
  }

  const preExecutionStatus = showPreExecutionStages ? getPreExecutionStatus() : null
  const showEmptyState = !stages.length && !preExecutionStatus

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
      {(command || statusMessage || isFinished) && (
        <div className="rounded-lg bg-background px-2 py-1 space-y-1 -mx-2">
          {command && (
            <div className={`font-mono text-sm text-muted-foreground ${truncateMessages ? 'truncate' : 'whitespace-pre-wrap'}`}>
              $ {command}
            </div>
          )}
          <div className={`text-sm ${truncateMessages ? 'truncate' : 'whitespace-pre-wrap'}`}>
            {statusMessage || '\u00A0'}
          </div>
        </div>
      )}
      {showEmptyState ? (
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <Radio className="w-4 h-4 animate-pulse" />
          <span>Starting...</span>
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