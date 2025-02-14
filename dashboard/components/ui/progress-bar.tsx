import React, { useRef } from "react"
import { cn } from "@/lib/utils"
import { ProgressBarTiming } from "./progress-bar-timing"
import NumberFlow from '@number-flow/react'

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
  const highestProgressRef = useRef(0)
  const highestProcessedItemsRef = useRef(0)

  // Update highest values and ensure we never go backwards
  const displayProgress = Math.round(progress)
  const safeProgress = Math.max(displayProgress, highestProgressRef.current)
  highestProgressRef.current = safeProgress
  
  const safeProcessedItems = processedItems !== undefined ? 
    Math.max(processedItems, highestProcessedItemsRef.current) : undefined
  if (safeProcessedItems !== undefined) {
    highestProcessedItemsRef.current = safeProcessedItems
  }

  const clampedProgress = Math.min(Math.max(safeProgress, 0), 100)
  const isInProgress = clampedProgress < 100

  // Common animation config for consistency
  const animationConfig = {
    duration: 400, // Slightly longer duration for smoother number transitions
    easing: 'ease-out' // Use ease-out for number transitions
  }

  // Configure number formatting
  const numberFormat = {
    notation: 'standard' as const,
    maximumFractionDigits: 0
  }

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
      <div className="relative w-full h-8 bg-progress-background rounded-md">
        <div
          role="progressbar"
          className={cn(
            "absolute top-0 left-0 h-full rounded-md",
            `bg-${color}`,
            clampedProgress > 0 ? `bg-${color}` : ''
          )}
          style={{ 
            width: `${clampedProgress}%`,
            transition: `width ${animationConfig.duration}ms ${animationConfig.easing}`
          }}
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
                <NumberFlow 
                  value={safeProcessedItems ?? 0}
                  format={numberFormat}
                  transformTiming={animationConfig}
                  willChange
                />
              </span>
              <span className="text-sm font-medium text-primary-foreground"> / </span>
              <span className={cn(
                "text-sm font-medium",
                isFocused && safeProcessedItems !== totalItems 
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
            <NumberFlow 
              value={clampedProgress}
              format={numberFormat}
              suffix="%"
              transformTiming={animationConfig}
              willChange
            />
          </span>
        </div>
      </div>
    </div>
  )
} 