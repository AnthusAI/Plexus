import React from 'react'
import { SegmentedProgressBar, SegmentConfig } from './segmented-progress-bar'
import { ProgressBar } from './progress-bar'
import { ProgressBarTiming } from './progress-bar-timing'
import { Radio, Hand, ConciergeBell } from 'lucide-react'
import { cn } from "@/lib/utils"

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

// Add style tag to inject the animation
const StyleTag = () => (
  <style>{animations}</style>
)

export interface ActionStageConfig {
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

export interface ActionStatusProps {
  showStages?: boolean
  stages?: ActionStageConfig[]
  currentStageName?: string
  processedItems?: number
  totalItems?: number
  elapsedTime?: string
  estimatedTimeRemaining?: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  command?: string
  statusMessage?: string
  stageConfigs?: ActionStageConfig[]
  isLoading?: boolean
  errorLabel?: string
  dispatchStatus?: string
  celeryTaskId?: string
  workerNodeId?: string
  showPreExecutionStages?: boolean
}

export function ActionStatus({
  showStages = true,
  stages = [],
  currentStageName,
  processedItems,
  totalItems,
  elapsedTime,
  estimatedTimeRemaining,
  status,
  stageConfigs,
  errorLabel = 'Failed',
  dispatchStatus,
  celeryTaskId,
  workerNodeId,
  showPreExecutionStages = false,
  command,
  statusMessage
}: ActionStatusProps) {
  const isInProgress = status === 'RUNNING'
  const progress = processedItems && totalItems ? 
    (processedItems / totalItems) * 100 : 0

  // Convert ActionStageConfig to SegmentConfig for the progress bar
  const segmentConfigs: SegmentConfig[] = stageConfigs ? [
    ...stageConfigs.map(stage => ({
      key: stage.name,
      label: stage.label,
      color: stage.color
    })),
    // Only add completion segment if we have other stages
    ...(stageConfigs.length > 0 ? [{
      key: 'completion',
      label: status === 'FAILED' ? 'Failed' : 'Complete',
      color: status === 'FAILED' ? 'bg-false' : 'bg-true'
    }] : [])
  ] : []

  const getPreExecutionStatus = () => {
    if (!dispatchStatus) return { 
      message: 'Starting...', 
      icon: Radio,
      animation: 'animate-pulse'
    }
    if (!celeryTaskId) return { 
      message: 'Activity announced...', 
      icon: ConciergeBell,
      animation: 'animate-jiggle'
    }
    if (!workerNodeId) return { 
      message: 'Activity claimed.', 
      icon: Hand,
      animation: 'animate-wave'
    }
    return null
  }

  const preExecutionStatus = showPreExecutionStages ? getPreExecutionStatus() : null
  const showEmptyState = !stages.length && !preExecutionStatus

  return (
    <div className="space-y-4">
      <StyleTag />
      {(command || statusMessage) && (
        <div className="rounded-lg bg-card-light p-3 space-y-2">
          {command && (
            <div className="font-mono text-sm text-muted-foreground">
              {command}
            </div>
          )}
          {statusMessage && (
            <div className="font-mono text-sm">
              {statusMessage}
            </div>
          )}
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
        processedItems={processedItems}
        totalItems={totalItems}
        color={status === 'FAILED' ? 'false' : 'secondary'}
        showTiming={false}
      />
    </div>
  )
} 