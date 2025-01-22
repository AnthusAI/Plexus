import React from "react"
import { cn } from "@/lib/utils"
import { ProgressBarTiming } from "./progress-bar-timing"

export interface ProgressBarProps {
  progress: number
  className?: string
  elapsedTime?: string
  processedItems?: number
  totalItems?: number
  estimatedTimeRemaining?: string
  color?: 'primary' | 'secondary' | 'true' | 'false' | 'neutral'
  isFocused?: boolean
  showTiming?: boolean
}

export function ProgressBar({ 
  progress, 
  className,
  elapsedTime,
  processedItems,
  totalItems,
  estimatedTimeRemaining,
  color = 'secondary',
  isFocused = false,
  showTiming = true
}: ProgressBarProps) {
  const displayProgress = Math.round(progress)
  const clampedProgress = Math.min(Math.max(displayProgress, 0), 100)
  const isInProgress = clampedProgress < 100

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {showTiming && (
        <ProgressBarTiming
          elapsedTime={elapsedTime}
          estimatedTimeRemaining={estimatedTimeRemaining}
          isInProgress={isInProgress}
          isFocused={isFocused}
        />
      )}
      <div className="relative w-full h-8 bg-neutral rounded-md">
        <div
          role="progressbar"
          className={cn(
            "absolute top-0 left-0 h-full rounded-md transition-all",
            `bg-${color}`,
            clampedProgress > 0 ? `bg-${color}` : ''
          )}
          style={{ width: `${clampedProgress}%` }}
        />
        <div className="absolute top-0 left-0 right-0 h-full flex justify-between items-center px-2">
          {processedItems !== undefined && totalItems !== undefined && (
            <span>
              <span className={cn(
                "text-sm font-medium",
                isFocused
                  ? "text-focus" 
                  : "text-primary-foreground"
              )}>
                {processedItems}
              </span>
              <span className="text-sm font-medium text-primary-foreground"> / </span>
              <span className={cn(
                "text-sm font-medium",
                isFocused && processedItems !== totalItems 
                  ? "text-focus" 
                  : "text-primary-foreground" 
              )}>
                {totalItems}
              </span>
            </span>
          )}
          <span className={cn(
            "text-sm font-medium",
            isFocused && isInProgress ? "text-focus" : "text-primary-foreground"
          )}>
            {displayProgress}%
          </span>
        </div>
      </div>
    </div>
  )
} 