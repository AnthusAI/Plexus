import React from 'react'
import { cn } from "@/lib/utils"

type BatchState = 'open' | 'closed' | 'processing' | 'complete' | 'error'

interface BatchStageProgressBarProps {
  state: BatchState
  className?: string
}

const states: BatchState[] = ['open', 'closed', 'processing', 'complete']

const stateToIndex: Record<BatchState, number> = {
  open: 0,
  closed: 1,
  processing: 2,
  complete: 3,
  error: 3
}

const stateColors: Record<BatchState, string> = {
  open: 'bg-primary',
  closed: 'bg-primary',
  processing: 'bg-secondary',
  complete: 'bg-true',
  error: 'bg-false'
}

const defaultLabels = ['Open', 'Closed', 'Processing', 'Complete']
const stateLabels: Record<BatchState, string[]> = {
  open: defaultLabels,
  closed: defaultLabels,
  processing: defaultLabels,
  complete: defaultLabels,
  error: ['Open', 'Closed', 'Processing', 'Error']
}

export function BatchStageProgressBar({ 
  state = 'open', 
  className = ''
}: BatchStageProgressBarProps) {
  const normalizedState = state.toLowerCase() as BatchState
  // Ensure state is valid, default to 'open' if not
  const validState = Object.keys(stateLabels).includes(normalizedState) 
    ? normalizedState 
    : 'open'
  const labels = stateLabels[validState]
  const activeIndex = validState === 'error' 
    ? 3  // Show all segments as active up to the error point
    : stateToIndex[validState]

  return (
    <div className={cn(
      "w-full h-8 bg-neutral rounded-md overflow-hidden border border-border", 
      className
    )}>
      <div className="h-full w-full flex gap-1">
        {labels.map((label, index) => {
          const segmentState = states[index].toLowerCase() as BatchState
          const isActive = index <= activeIndex
          const isError = validState === 'error' && index === labels.length - 1

          return (
            <div
              key={index}
              className={cn(
                "flex-1 flex items-center justify-center transition-colors duration-200",
                isActive 
                  ? stateColors[isError ? 'error' : segmentState] 
                  : "bg-neutral"
              )}
            >
              <span className={cn(
                "text-sm font-medium truncate px-1 text-primary-foreground"
              )}>
                {label}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
} 