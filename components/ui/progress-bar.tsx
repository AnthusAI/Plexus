import React from "react"
import { cn } from "@/lib/utils"

export interface ProgressBarProps {
  progress: number
  className?: string
  elapsedTime?: string
  processedItems?: number
  totalItems?: number
  estimatedTimeRemaining?: string
  color?: 'primary' | 'secondary' | 'true' | 'false' | 'neutral'
}

export function ProgressBar({ 
  progress, 
  className,
  elapsedTime,
  processedItems,
  totalItems,
  estimatedTimeRemaining,
  color = 'secondary'
}: ProgressBarProps) {
  const displayProgress = Math.round(progress)
  const clampedProgress = Math.min(Math.max(displayProgress, 0), 100)

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {(elapsedTime || estimatedTimeRemaining) && (
        <div className="flex justify-between text-sm text-muted-foreground h-5">
          {elapsedTime && <span>Elapsed: {elapsedTime}</span>}
          {estimatedTimeRemaining && <span>ETA: {estimatedTimeRemaining}</span>}
        </div>
      )}
      <div className="relative w-full h-8 bg-neutral rounded-md">
        <div
          className={cn(
            "absolute top-0 left-0 h-full rounded-md transition-all",
            `bg-${color}`,
            clampedProgress > 0 ? `bg-${color}` : ''
          )}
          style={{ width: clampedProgress > 0 ? `${clampedProgress}%` : 'auto' }}
        />
        <div className="absolute top-0 left-0 right-0 h-full flex justify-between items-center px-2">
          <span className="text-sm text-primary-foreground font-medium">
            {displayProgress}%
          </span>
          {processedItems !== undefined && totalItems !== undefined && (
            <span className="text-sm text-primary-foreground font-medium">
              {processedItems} / {totalItems}
            </span>
          )}
        </div>
      </div>
    </div>
  )
} 