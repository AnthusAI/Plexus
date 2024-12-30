import React from 'react'
import { SegmentedProgressBar } from './segmented-progress-bar'
import { cn } from "@/lib/utils"

export type BatchJobStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'OPEN' | 'CLOSED'

interface BatchJobProgressBarProps {
  status: BatchJobStatus
  className?: string
}

const statusToProgressState = (status: BatchJobStatus) => {
  switch (status.toLowerCase()) {
    case 'open':
      return 'open'
    case 'closed':
      return 'closed'
    case 'processing':
    case 'processed':
    case 'created':
      return 'processing'
    case 'completed':
      return 'complete'
    case 'error':
      return 'error'
    default:
      return 'open'
  }
}

export function BatchJobProgressBar({ 
  status, 
  className 
}: BatchJobProgressBarProps) {
  return (
    <SegmentedProgressBar
      state={statusToProgressState(status)}
      className={className}
    />
  )
} 