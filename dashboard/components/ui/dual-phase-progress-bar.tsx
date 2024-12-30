import React from "react"
import { cn } from "@/lib/utils"

export interface DualPhaseProgressBarProps {
  isFirstPhase: boolean
  firstPhaseProgress: number
  firstPhaseProcessedItems?: number
  firstPhaseTotalItems?: number
  secondPhaseProgress: number
  secondPhaseProcessedItems?: number
  secondPhaseTotalItems?: number
  className?: string
  isFocused?: boolean
}

export function DualPhaseProgressBar({
  isFirstPhase,
  firstPhaseProgress,
  firstPhaseProcessedItems,
  firstPhaseTotalItems,
  secondPhaseProgress,
  secondPhaseProcessedItems,
  secondPhaseTotalItems,
  className,
  isFocused = false
}: DualPhaseProgressBarProps) {
  const clampedFirstPhase = Math.min(Math.max(Math.round(firstPhaseProgress), 0), 100)
  const clampedSecondPhase = Math.min(Math.max(Math.round(secondPhaseProgress), 0), 100)

  // Get the current phase's values
  const currentProgress = isFirstPhase ? clampedFirstPhase : clampedSecondPhase
  const currentProcessedItems = isFirstPhase ? firstPhaseProcessedItems : secondPhaseProcessedItems
  const currentTotalItems = isFirstPhase ? firstPhaseTotalItems : secondPhaseTotalItems

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="relative w-full h-8 bg-neutral rounded-md overflow-hidden">
        {/* Second phase progress bar */}
        {!isFirstPhase && (
          <div
            className={cn(
              "absolute top-0 left-0 h-full transition-all bg-secondary z-20",
              clampedSecondPhase === 100 ? "rounded-md" : "rounded-l-md"
            )}
            style={{ width: clampedSecondPhase > 0 ? `${clampedSecondPhase}%` : "0%" }}
          />
        )}
        {/* First phase progress bar */}
        <div
          className={cn(
            "absolute top-0 left-0 h-full transition-all z-10",
            isFirstPhase ? "bg-secondary" : "bg-primary",
            clampedFirstPhase === 100 ? "rounded-md" : "rounded-l-md"
          )}
          style={{ width: clampedFirstPhase > 0 ? `${clampedFirstPhase}%` : "0%" }}
        />
        {/* Content overlay */}
        <div className="absolute top-0 left-0 right-0 h-full flex justify-between items-center px-2 z-30">
          <div>
            {currentProcessedItems !== undefined && currentTotalItems !== undefined && (
              <span className="flex items-center gap-1">
                <span className={cn(
                  "text-sm font-medium",
                  isFocused ? "text-focus" : "text-primary-foreground"
                )}>
                  {currentProcessedItems}
                </span>
                <span className="text-sm font-medium text-primary-foreground">/</span>
                <span className={cn(
                  "text-sm font-medium",
                  isFocused && currentProcessedItems !== currentTotalItems
                    ? "text-focus"
                    : "text-primary-foreground"
                )}>
                  {currentTotalItems}
                </span>
              </span>
            )}
          </div>
          <span className={cn(
            "text-sm font-medium",
            isFocused ? "text-focus" : "text-primary-foreground"
          )}>
            {currentProgress}%
          </span>
        </div>
      </div>
    </div>
  )
} 