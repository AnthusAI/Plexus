import React from "react"
import { cn } from "@/lib/utils"

interface EvaluationListAccuracyBarProps {
  progress: number
  accuracy: number
  isFocused?: boolean
  isSelected?: boolean
  baselineAccuracy?: number
  currentBaselineAccuracy?: number
}

export function EvaluationListAccuracyBar({
  progress,
  accuracy,
  isFocused = false,
  isSelected = false,
  baselineAccuracy,
  currentBaselineAccuracy
}: EvaluationListAccuracyBarProps) {
  const formattedAccuracy = accuracy >= 98
    ? Math.round(accuracy * 10) / 10
    : Math.round(accuracy)
  const clampedAccuracy = Math.min(Math.max(formattedAccuracy, 0), 100)
  const clampedProgress = Math.min(Math.max(progress, 0), 100)
  const opacity = clampedProgress / 100
  const trueWidth = clampedAccuracy
  const falseWidth = 100 - trueWidth
  const clampedBaseline = baselineAccuracy != null
    ? Math.min(Math.max(baselineAccuracy, 0), 100)
    : null
  const clampedCurrentBaseline = currentBaselineAccuracy != null
    ? Math.min(Math.max(currentBaselineAccuracy, 0), 100)
    : null

  return (
    <div className={cn(
      "relative w-full h-8 rounded-md",
      isSelected ? "bg-progress-background-selected" : "bg-progress-background"
    )}>
      {clampedProgress > 0 && (
        <>
          <div
            className={cn(
              "absolute top-0 left-0 h-full flex items-center pl-2 text-sm font-medium rounded-md",
              isFocused ? "text-focus" : isSelected ? "text-primary-selected-foreground" : "text-primary-foreground"
            )}
            style={{ width: 'auto' }}
          >
            {clampedAccuracy}%
          </div>
          {trueWidth > 0 && (
            <div
              className={cn(
                "absolute top-0 left-0 h-full flex items-center pl-2 text-sm font-medium",
                isSelected ? "bg-true-selected" : "bg-true",
                isFocused ? "text-focus" : isSelected ? "text-foreground-true" : "text-primary-foreground"
              )}
              style={{
                width: `${trueWidth}%`,
                borderTopLeftRadius: 'inherit',
                borderBottomLeftRadius: 'inherit',
                borderTopRightRadius: falseWidth === 0 ? 'inherit' : 0,
                borderBottomRightRadius: falseWidth === 0 ? 'inherit' : 0,
                opacity
              }}
            >
              {clampedAccuracy}%
            </div>
          )}
          {falseWidth > 0 && (
            <div
              className={cn(
                "absolute top-0 h-full",
                isSelected ? "bg-false-selected" : "bg-false"
              )}
              style={{
                left: `${trueWidth}%`,
                width: `${falseWidth}%`,
                borderTopLeftRadius: trueWidth === 0 ? 'inherit' : 0,
                borderBottomLeftRadius: trueWidth === 0 ? 'inherit' : 0,
                borderTopRightRadius: 'inherit',
                borderBottomRightRadius: 'inherit',
                opacity
              }}
            />
          )}
          {clampedBaseline != null && (
            <div
              className="absolute top-0 h-full w-[2px] bg-muted-foreground/50"
              style={{ left: `${clampedBaseline}%` }}
            />
          )}
          {clampedCurrentBaseline != null && (
            <div
              className="absolute top-0 h-full w-[2px] bg-muted-foreground"
              style={{ left: `${clampedCurrentBaseline}%` }}
            />
          )}
        </>
      )}
    </div>
  )
}
