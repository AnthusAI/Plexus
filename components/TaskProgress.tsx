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
}

export function TaskProgress({ 
  progress, 
  className,
  elapsedTime,
  processedItems,
  totalItems,
  estimatedTimeRemaining 
}: TaskProgressProps) {
  const showTopRow = processedItems !== undefined && totalItems !== undefined
  const showBottomRow = elapsedTime || estimatedTimeRemaining

  return (
    <div className="flex flex-col gap-1">
      {showTopRow && (
        <div className="flex justify-between text-sm text-muted-foreground">
          <span>{progress}%</span>
          <span>{processedItems} / {totalItems}</span>
        </div>
      )}
      <Progress
        value={progress}
        className={cn("h-4", className)}
      />
      {showBottomRow && (
        <div className="flex justify-between text-sm text-muted-foreground">
          {elapsedTime && <span>Elapsed: {elapsedTime}</span>}
          {estimatedTimeRemaining && <span>ETA: {estimatedTimeRemaining}</span>}
        </div>
      )}
    </div>
  )
}

export default TaskProgress
