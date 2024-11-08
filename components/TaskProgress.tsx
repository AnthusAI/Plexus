import React from "react"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

export interface TaskData {
  accuracy?: number
  progress?: number
  elapsedTime?: string
  estimatedTimeRemaining?: string
  processedItems?: number
  totalItems?: number
  numberComplete?: number
  numberTrue?: number
  numberFalse?: number
  numberTotal?: number
  before?: {
    outerRing: Array<{ category: string; value: number; fill: string }>
    innerRing: Array<{ category: string; value: number; fill: string }>
  }
  after?: {
    outerRing: Array<{ category: string; value: number; fill: string }>
    innerRing: Array<{ category: string; value: number; fill: string }>
  }
  outerRing?: Array<{ category: string; value: number; fill: string }>
  innerRing?: Array<{ category: string; value: number; fill: string }>
}

export interface TaskProps {
  variant: "grid" | "detail"
  task: {
    id: number
    type: string
    scorecard: string
    score: string
    time: string
    summary: string
    description?: string
    data?: TaskData
  }
  onClick?: () => void
  controlButtons?: React.ReactNode
  iconType?: "warning" | "info"
}

export interface TaskProgressProps {
  progress: number
  className?: string
  elapsedTime?: string
  processedItems?: number
  totalItems?: number
  estimatedTimeRemaining?: string
  color?: 'primary' | 'secondary' | 'true' | 'false'
}

export function TaskProgress({ 
  progress, 
  className,
  elapsedTime,
  processedItems,
  totalItems,
  estimatedTimeRemaining,
  color = 'secondary'
}: TaskProgressProps) {
  const displayProgress = Math.round(progress)
  const clampedProgress = Math.min(Math.max(displayProgress, 0), 100)

  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-sm text-muted-foreground h-5">
        {processedItems !== undefined && totalItems !== undefined ? (
          <>
            <span>{displayProgress}%</span>
            <span>{processedItems} / {totalItems}</span>
          </>
        ) : (
          <span>&nbsp;</span>
        )}
      </div>
      <div className="relative w-full h-6 bg-neutral rounded-md">
        <div
          className={`absolute top-0 left-0 h-full bg-${color} rounded-md ${
            clampedProgress > 0 ? `bg-${color}` : ''
          }`}
          style={{ width: clampedProgress > 0 ? `${clampedProgress}%` : 'auto' }}
        />
      </div>
      <div className="flex justify-between text-sm text-muted-foreground h-5">
        {elapsedTime || estimatedTimeRemaining ? (
          <>
            {elapsedTime && <span>Elapsed: {elapsedTime}</span>}
            {estimatedTimeRemaining && <span>ETA: {estimatedTimeRemaining}</span>}
          </>
        ) : (
          <span>&nbsp;</span>
        )}
      </div>
    </div>
  )
}

export default TaskProgress
