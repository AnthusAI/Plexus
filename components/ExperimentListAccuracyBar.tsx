import React from "react"
import { cn } from "@/lib/utils"

interface ExperimentListAccuracyBarProps {
  progress: number
  accuracy: number
  isFocused?: boolean
}

export function ExperimentListAccuracyBar({ 
  progress, 
  accuracy,
  isFocused = false 
}: ExperimentListAccuracyBarProps) {
  const roundedAccuracy = Math.round(accuracy)
  const clampedAccuracy = Math.min(Math.max(roundedAccuracy, 0), 100)
  const clampedProgress = Math.min(Math.max(progress, 0), 100)
  const opacity = clampedProgress / 100
  const trueWidth = clampedAccuracy
  const falseWidth = 100 - trueWidth
  
  return (
    <div className="relative w-full h-8 bg-neutral rounded-md">
      {clampedProgress > 0 && (
        <>
          <div
            className={cn(
              "absolute top-0 left-0 h-full flex items-center pl-2 text-sm font-medium rounded-md",
              isFocused ? "text-focus" : "text-primary-foreground"
            )}
            style={{ width: 'auto' }}
          >
            {clampedAccuracy}%
          </div>
          {trueWidth > 0 && (
            <div
              className={cn(
                "absolute top-0 left-0 h-full bg-true flex items-center pl-2 text-sm font-medium",
                isFocused ? "text-focus" : "text-primary-foreground"
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
              className="absolute top-0 h-full bg-false"
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
        </>
      )}
    </div>
  )
} 