import React from 'react'
import { Progress } from '@/components/ui/progress'

interface TaskProgressProps {
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
  estimatedTimeRemaining
}) => (
  <div className="mt-4">
    <div className="flex justify-between text-xs mb-1">
      <div className="font-semibold">Progress: {progress}%</div>
      <div>{elapsedTime}</div>
    </div>
    <Progress value={progress} className="w-full h-4" />
    <div className="flex justify-between text-xs mt-1">
      <div>{processedItems}/{totalItems}</div>
      <div>ETA: {estimatedTimeRemaining}</div>
    </div>
  </div>
)

export default TaskProgress
