import React from 'react'
import { Progress } from '@/components/ui/progress'

export interface TaskProgressProps {
  progress: number
  elapsedTime: string
  processedItems: number
  totalItems: number
  estimatedTimeRemaining: string
  processingRate: number
}

const TaskProgress: React.FC<TaskProgressProps> = ({
  progress,
  elapsedTime,
  processedItems,
  totalItems,
  estimatedTimeRemaining,
  processingRate
}) => {
  return (
    <div className="space-y-2">
      <Progress value={progress} className="w-full" />
      <div className="flex justify-between text-sm text-muted-foreground">
        <span>{processedItems} / {totalItems}</span>
        <span>{progress.toFixed(0)}%</span>
      </div>
      <div className="flex justify-between text-sm text-muted-foreground">
        <span>Elapsed: {elapsedTime}</span>
        <span>ETA: {estimatedTimeRemaining}</span>
      </div>
      <div className="text-sm text-muted-foreground">
        Processing rate: {processingRate.toFixed(2)} items/second
      </div>
    </div>
  )
}

export default TaskProgress
