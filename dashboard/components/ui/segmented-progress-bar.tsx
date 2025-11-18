import React from 'react'
import { cn } from "@/lib/utils"

export interface SegmentConfig {
  key: string
  label: string
  color?: string
  status?: string
  completed?: boolean
}

interface SegmentedProgressBarProps {
  segments: SegmentConfig[]
  currentSegment: string
  error?: boolean
  errorLabel?: string
  className?: string
  isSelected?: boolean
}

export function SegmentedProgressBar({ 
  segments,
  currentSegment,
  error = false,
  errorLabel = 'Error',
  className = '',
  isSelected = false
}: SegmentedProgressBarProps) {
  const currentIndex = segments.findIndex(s => 
    s.key.toLowerCase() === currentSegment.toLowerCase()
  )
  
  return (
    <div className={cn(
      "w-full h-8 rounded-md overflow-hidden border border-border",
      isSelected ? "bg-progress-background-selected" : "bg-progress-background",
      className
    )}>
      <div role="list" className="h-full w-full flex gap-1">
        {segments.map((segment, index) => {
          const isBeforeCurrent = index < currentIndex
          const isCurrent = index === currentIndex
          const isCompleted = segment.completed || segment.status === 'COMPLETED'
          const isRunning = segment.status === 'RUNNING'

          // Determine color based on completion state first, then position
          const baseColor = isCompleted ? segment.color ?? "bg-primary" :
                         isRunning ? segment.color ?? "bg-secondary" :
                         isBeforeCurrent ? segment.color ?? "bg-secondary" :
                         isCurrent ? error ? "bg-false" : segment.color ?? "bg-secondary" :
                         "bg-progress-background";

          // Add -selected suffix if selected
          const segmentColor = isSelected && baseColor !== "bg-progress-background" ? 
            `${baseColor}-selected` : baseColor;

          return (
            <div
              role="listitem"
              key={segment.key}
              className={cn(
                "flex-1 flex items-center justify-center transition-colors duration-200 min-w-0",
                segmentColor
              )}
            >
              <span className={cn(
                "text-sm truncate px-1 min-w-0 max-w-full",
                isCurrent ? "font-bold text-foreground" : "font-medium text-muted-foreground"
              )}>
                {isCurrent && error ? errorLabel : segment.label}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
} 