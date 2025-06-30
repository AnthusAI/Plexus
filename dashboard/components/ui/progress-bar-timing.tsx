import React from "react"
import { cn } from "@/lib/utils"
import { Timer, AlarmClock, AlarmClockCheck } from "lucide-react"
import { Timestamp } from "./timestamp"

export interface ProgressBarTimingProps {
  elapsedTime?: string
  estimatedTimeRemaining?: string
  isInProgress?: boolean
  isFocused?: boolean
  className?: string
  startedAt?: string
  completedAt?: string
}

export function ProgressBarTiming({
  elapsedTime,
  estimatedTimeRemaining,
  isInProgress = true,
  isFocused = false,
  className,
  startedAt,
  completedAt
}: ProgressBarTimingProps) {
  return (
    <div className={cn("flex justify-between text-sm text-muted-foreground h-5", className)}>
      <div className="flex items-center gap-1">
        <Timer 
          data-testid="timer-icon"
          className={cn(
            "w-4 h-4 shrink-0",
            isInProgress && "animate-pulse"
          )}
        />
        {elapsedTime ? (
          <span>Elapsed: {elapsedTime}</span>
        ) : startedAt ? (
          <div className="flex items-center gap-1">
            <span>Elapsed:</span>
            <Timestamp 
              time={startedAt} 
              completionTime={completedAt} 
              variant="elapsed" 
              showIcon={false}
            />
          </div>
        ) : (
          <span>Elapsed: 0s</span>
        )}
      </div>
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
              className="w-4 h-4 shrink-0" 
            />
          ) : (
            <AlarmClockCheck 
              data-testid="alarm-check-icon"
              className="w-4 h-4 shrink-0" 
            />
          )}
        </div>
      )}
    </div>
  )
} 