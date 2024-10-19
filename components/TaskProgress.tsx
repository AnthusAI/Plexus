import React from 'react'
import { Progress } from '@/components/ui/progress'

export interface TaskProgressProps {
  progress: number
  elapsedTime: string
  processedItems: number
  totalItems: number
  estimatedTimeRemaining: string
}

const TaskProgress: React.FC<TaskProgressProps> = ({
  progress,
  elapsedTime,
  processedItems,
  totalItems,
  estimatedTimeRemaining,
}) => {
  return (
    <div className="space-y-2 mt-4">
      <div className="flex justify-between text-sm text-muted-foreground">
        <span>{progress.toFixed(0)}%</span>
        <span>{processedItems} / {totalItems}</span>
      </div>
      <Progress value={progress} className="w-full" />
      <div className="flex justify-between text-sm text-muted-foreground">
        <span>Elapsed: {elapsedTime}</span>
        <span>ETA: {estimatedTimeRemaining}</span>
      </div>
    </div>
  )
}

export default TaskProgress
