import React from "react"
import { cn } from "@/lib/utils"
import { ThumbsUp, ThumbsDown } from "lucide-react"

export interface AccuracyBarProps {
  accuracy: number
  className?: string
}

export function AccuracyBar({ accuracy, className }: AccuracyBarProps) {
  const clampedAccuracy = Math.min(Math.max(accuracy, 0), 100)
  
  return (
    <div className={cn("relative w-full h-8 bg-false rounded-md", className)}>
      <div
        className="absolute top-0 left-0 h-full bg-true rounded-l-md"
        style={{ width: `${clampedAccuracy}%` }}
      />
      <div className="absolute top-0 left-0 right-0 h-full flex justify-between items-center px-2">
        <ThumbsUp className="w-4 h-4 text-primary-foreground" />
        <ThumbsDown className="w-4 h-4 text-primary-foreground" />
      </div>
    </div>
  )
} 