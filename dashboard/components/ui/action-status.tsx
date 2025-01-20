import React from 'react'
import { SegmentedProgressBar, SegmentConfig } from './segmented-progress-bar'
import { ProgressBar } from './progress-bar'
import { ProgressBarTiming } from './progress-bar-timing'
import { Radio, Triangle } from 'lucide-react'

export interface ActionStageConfig {
  key: string
  label: string
  color: string
  elapsedTime?: string
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
  showStages: boolean
  stages: ActionStageConfig[]
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

  // Create the full stage config list including completion
  const fullStageConfigs = stageConfigs ? [
    ...stageConfigs,
    {
      key: 'completion',
      label: status === 'FAILED' ? 'Failed' : 'Complete',
      color: status === 'FAILED' ? 'bg-false' : 'bg-true'
    }
  ] : []

  const getPreExecutionStatus = () => {
    if (!dispatchStatus) return { 
      message: 'Activity not yet announced...', 
      icon: Radio,
      animation: 'animate-pulse'
    }
    if (!celeryTaskId) return { 
      message: 'Activity announced...', 
      icon: Radio,
      animation: 'animate-pulse'
    }
    if (!workerNodeId) return { 
      message: 'Activity claimed.', 
      icon: Triangle,
      animation: 'animate-bounce'
    }
    return null
  }

  const preExecutionStatus = showPreExecutionStages ? getPreExecutionStatus() : null

  return (
    <div className="space-y-4">
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
      {preExecutionStatus ? (
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
      {showStages && stages.length > 0 && stageConfigs && (
        <SegmentedProgressBar
          segments={fullStageConfigs}
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