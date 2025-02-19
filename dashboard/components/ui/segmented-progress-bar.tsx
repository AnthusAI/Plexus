import React from 'react'
import { cn } from "@/lib/utils"

export interface SegmentConfig {
  key: string
  label: string
  color?: string
}

interface SegmentedProgressBarProps {
  segments: SegmentConfig[]
  currentSegment: string
  error?: boolean
  errorLabel?: string
  className?: string
}

export function SegmentedProgressBar({ 
  segments,
  currentSegment,
  error = false,
  errorLabel = 'Error',
  className = ''
}: SegmentedProgressBarProps) {
  const currentIndex = segments.findIndex(s => 
    s.key.toLowerCase() === currentSegment.toLowerCase()
  )
  
  return (
    <div className={cn(
      "w-full h-8 bg-neutral rounded-md overflow-hidden border border-border", 
      className
    )}>
      <div role="list" className="h-full w-full flex gap-1">
        {segments.map((segment, index) => {
          const isBeforeCurrent = index < currentIndex
          const isCurrent = index === currentIndex

          return (
            <div
              role="listitem"
              key={segment.key}
              className={cn(
                "flex-1 flex items-center justify-center transition-colors duration-200 min-w-0",
                isBeforeCurrent ? segment.color ?? "bg-secondary" :
                isCurrent ? error ? "bg-false" : segment.color ?? "bg-secondary" :
                "bg-neutral"
              )}
            >
              <span className={cn(
                "text-sm font-medium truncate px-1 text-primary-foreground min-w-0 max-w-full"
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