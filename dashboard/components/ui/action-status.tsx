import React from 'react'
import { SegmentedProgressBar, SegmentConfig } from './segmented-progress-bar'
import { ProgressBar } from './progress-bar'
import { ProgressBarTiming } from './progress-bar-timing'

export interface ActionStageConfig {
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
  stageConfigs?: SegmentConfig[]
  errorLabel?: string
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
  errorLabel = 'Failed'
}: ActionStatusProps) {
  const isInProgress = status === 'RUNNING'
  const progress = processedItems && totalItems ? 
    (processedItems / totalItems) * 100 : 0

  return (
    <div className="space-y-4">
      <ProgressBarTiming
        elapsedTime={elapsedTime}
        estimatedTimeRemaining={estimatedTimeRemaining}
        isInProgress={isInProgress}
      />
      {showStages && stages.length > 0 && stageConfigs && (
        <SegmentedProgressBar
          segments={stageConfigs}
          currentSegment={currentStageName || ''}
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