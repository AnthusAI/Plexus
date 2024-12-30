import React from "react"
import { cn } from "@/lib/utils"
import { ThumbsUp, ThumbsDown } from "lucide-react"

export interface AccuracyBarProps {
  accuracy: number | null
  className?: string
  onSegmentClick?: (isCorrect: boolean) => void
}

export function AccuracyBar({ accuracy, className, onSegmentClick }: AccuracyBarProps) {
  if (accuracy === null) {
    return (
      <div className={cn("relative w-full h-8 bg-neutral rounded-md", className)} />
    )
  }

  const clampedAccuracy = Math.min(Math.max(accuracy, 0), 100)
  const showThumbsUp = clampedAccuracy > 0
  const showThumbsDown = clampedAccuracy < 100
  
  return (
    <div className={cn("relative w-full h-8 bg-false rounded-md", className)}>
      <div
        className={cn(
          "absolute top-0 left-0 h-full bg-true cursor-pointer hover:opacity-90",
          "rounded-l-md",
          clampedAccuracy === 100 && "rounded-r-md"
        )}
        style={{ width: `${clampedAccuracy}%` }}
        onClick={() => onSegmentClick?.(true)}
      />
      <div 
        className={cn(
          "absolute top-0 right-0 h-full cursor-pointer hover:opacity-90",
          "bg-false rounded-r-md",
          clampedAccuracy === 0 && "rounded-l-md"
        )}
        style={{ width: `${100 - clampedAccuracy}%` }}
        onClick={() => onSegmentClick?.(false)}
      />
      <div className="absolute top-0 left-0 right-0 h-full flex justify-between items-center px-2 pointer-events-none">
        <div className="flex items-center gap-2">
          {showThumbsUp && (
            <ThumbsUp className="w-4 h-4 text-primary-foreground" />
          )}
          <span className="text-sm font-medium text-primary-foreground">
            {Math.round(accuracy)}%
          </span>
        </div>
        {showThumbsDown && (
          <ThumbsDown className="w-4 h-4 text-primary-foreground" />
        )}
      </div>
    </div>
  )
} 