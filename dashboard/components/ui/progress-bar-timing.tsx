import React from "react"
import { cn } from "@/lib/utils"
import { Loader2, AlarmClock, AlarmClockCheck, CircleCheck } from "lucide-react"

export interface ProgressBarTimingProps {
  elapsedTime?: string
  estimatedTimeRemaining?: string
  isInProgress?: boolean
  isFocused?: boolean
  className?: string
}

export function ProgressBarTiming({
  elapsedTime,
  estimatedTimeRemaining,
  isInProgress = true,
  isFocused = false,
  className
}: ProgressBarTimingProps) {
  if (!elapsedTime && !estimatedTimeRemaining) return null

  return (
    <div className={cn("flex justify-between text-sm text-foreground h-5", className)}>
      {elapsedTime && (
        <div className="flex items-center gap-1">
          {isInProgress ? (
            <Loader2 
              data-testid="loader-icon"
              className="w-4 h-4 text-foreground animate-spin shrink-0" 
            />
          ) : (
            <CircleCheck 
              data-testid="check-icon"
              className="w-4 h-4 text-foreground shrink-0" 
            />
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
            <AlarmClock 
              data-testid="alarm-icon"
              className="w-4 h-4 text-foreground shrink-0" 
            />
          ) : (
            <AlarmClockCheck 
              data-testid="alarm-check-icon"
              className="w-4 h-4 text-foreground shrink-0" 
            />
          )}
        </div>
      )}
    </div>
  )
} 