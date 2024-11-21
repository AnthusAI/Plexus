import React from "react"
import { cn } from "@/lib/utils"
import { Loader2, AlarmClock, AlarmClockCheck, CircleCheck } from "lucide-react"

export interface ProgressBarProps {
  progress: number
  className?: string
  elapsedTime?: string
  processedItems?: number
  totalItems?: number
  estimatedTimeRemaining?: string
  color?: 'primary' | 'secondary' | 'true' | 'false' | 'neutral'
  isFocused?: boolean
}

export function ProgressBar({ 
  progress, 
  className,
  elapsedTime,
  processedItems,
  totalItems,
  estimatedTimeRemaining,
  color = 'secondary',
  isFocused = false
}: ProgressBarProps) {
  const displayProgress = Math.round(progress)
  const clampedProgress = Math.min(Math.max(displayProgress, 0), 100)
  const isInProgress = clampedProgress < 100

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {(elapsedTime || estimatedTimeRemaining) && (
        <div className="flex justify-between text-sm text-foreground h-5">
          {elapsedTime && (
            <div className="flex items-center gap-1">
              {isInProgress ? (
                <Loader2 className="w-4 h-4 text-foreground animate-spin shrink-0" />
              ) : (
                <CircleCheck className="w-4 h-4 text-foreground shrink-0" />
              )}
              <span>Elapsed: {elapsedTime}</span>
            </div>
          )}
          {estimatedTimeRemaining && (
            <div className="flex items-center gap-1">
              {isInProgress ? (
                <span>
                  ETA:{' '}
                  <span className={cn(isFocused && "text-focus")}>
                    {estimatedTimeRemaining}
                  </span>
                </span>
              ) : (
                <span>Done</span>
              )}
              {isInProgress ? (
                <AlarmClock className="w-4 h-4 text-foreground shrink-0" />
              ) : (
                <AlarmClockCheck className="w-4 h-4 text-foreground shrink-0" />
              )}
            </div>
          )}
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
          <span className={cn(
            "text-sm font-medium",
            isFocused && isInProgress ? "text-focus" : "text-primary-foreground"
          )}>
            {displayProgress}%
          </span>
          {processedItems !== undefined && totalItems !== undefined && (
            <span className={cn(
              "text-sm font-medium",
              isFocused ? "text-focus" : "text-primary-foreground"
            )}>
              {processedItems} / {totalItems}
            </span>
          )}
        </div>
      </div>
    </div>
  )
} 