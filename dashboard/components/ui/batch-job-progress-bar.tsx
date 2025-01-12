import React from 'react'
import { SegmentedProgressBar, SegmentConfig } from './segmented-progress-bar'
import { cn } from "@/lib/utils"

export type BatchJobStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'OPEN' | 'CLOSED'

interface BatchJobProgressBarProps {
  status: BatchJobStatus
  className?: string
}

const normalStageConfigs: SegmentConfig[] = [
  { key: 'open', label: 'Open', color: 'bg-primary' },
  { key: 'closed', label: 'Closed', color: 'bg-primary' },
  { key: 'processing', label: 'Processing', color: 'bg-secondary' },
  { key: 'complete', label: 'Complete', color: 'bg-true' }
]

const errorStageConfigs: SegmentConfig[] = [
  { key: 'open', label: 'Open', color: 'bg-primary' },
  { key: 'closed', label: 'Closed', color: 'bg-primary' },
  { key: 'processing', label: 'Processing', color: 'bg-secondary' },
  { key: 'failed', label: 'Failed', color: 'bg-false' }
]

const statusToSegmentKey = (status: BatchJobStatus): string => {
  switch (status.toLowerCase()) {
    case 'open':
      return 'open'
    case 'closed':
      return 'closed'
    case 'running':
    case 'processing':
    case 'processed':
    case 'created':
      return 'processing'
    case 'completed':
      return 'complete'
    case 'failed':
      return 'failed'
    default:
      return 'open'
  }
}

export function BatchJobProgressBar({ 
  status, 
  className 
}: BatchJobProgressBarProps) {
  const isFailed = status === 'FAILED'
  const segments = isFailed ? errorStageConfigs : normalStageConfigs

  return (
    <SegmentedProgressBar
      segments={segments}
      currentSegment={statusToSegmentKey(status)}
      className={className}
    />
  )
} 