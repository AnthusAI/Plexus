import React from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { Package, PackageCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { ProgressBar } from "@/components/ui/progress-bar"

export interface BatchJobTaskData {
  provider: string
  type: string
  status: string
  totalRequests: number
  completedRequests: number
  failedRequests: number
  startedAt?: string
  completedAt?: string
  errorMessage?: string
}

export type BatchJobTaskProps = {
  variant?: 'grid' | 'detail' | 'nested'
  task: {
    id: number
    type: string
    scorecard: string
    score: string
    time: string
    summary: string
    description?: string
    data: BatchJobTaskData
  }
  onClick?: () => void
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
}

const getStatusDisplay = (status: string): { text: string; variant: string } => {
  const statusMap: Record<string, { text: string; variant: string }> = {
    pending: { text: 'Pending', variant: 'secondary' },
    in_progress: { text: 'In Progress', variant: 'default' },
    done: { text: 'Done', variant: 'success' },
    failed: { text: 'Failed', variant: 'destructive' },
    canceled: { text: 'Canceled', variant: 'warning' },
  }
  return statusMap[status.toLowerCase()] || { text: status, variant: 'default' }
}

const transformBatchJobData = (task: BatchJobTaskProps['task']) => ({
  ...task,
  data: {
    progress: (task.data.completedRequests / task.data.totalRequests) * 100,
    processedItems: task.data.completedRequests,
    totalItems: task.data.totalRequests,
    numberComplete: task.data.completedRequests,
    numberTotal: task.data.totalRequests,
    eta: task.data.startedAt,
    elapsedTime: task.data.completedAt
  }
})

export default function BatchJobTask({ 
  variant = "grid",
  task,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}: BatchJobTaskProps) {
  const statusDisplay = getStatusDisplay(task.data.status)
  const transformedTask = transformBatchJobData(task)

  if (variant === 'nested') {
    return (
      <div className="bg-background/50 py-3 rounded-md space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {task.data.status === 'done' ? (
              <PackageCheck className="h-4 w-4" />
            ) : (
              <Package className="h-4 w-4" />
            )}
            <span className="text-sm font-medium">
              {task.data.provider}
            </span>
          </div>
          <Badge 
            variant={statusDisplay.variant as any}
            className={cn(
              "capitalize text-xs w-24 flex justify-center",
              statusDisplay.variant === 'success' && "bg-green-600",
              statusDisplay.variant === 'warning' && "bg-yellow-600",
              statusDisplay.variant === 'destructive' && "bg-red-600",
            )}
          >
            {statusDisplay.text}
          </Badge>
        </div>
        <ProgressBar 
          progress={(task.data.completedRequests / task.data.totalRequests) * 100}
          processedItems={task.data.completedRequests}
          totalItems={task.data.totalRequests}
          color="secondary"
        />
        {task.data.errorMessage && (
          <div className="text-xs text-destructive">
            Error: {task.data.errorMessage}
          </div>
        )}
      </div>
    )
  }

  const visualization = (
    <div className="flex flex-col h-full">
      <div className="flex justify-end mb-4">
        <Badge 
          variant={statusDisplay.variant as any}
          className={cn(
            "capitalize w-24 flex justify-center",
            statusDisplay.variant === 'success' && "bg-green-600",
            statusDisplay.variant === 'warning' && "bg-yellow-600",
            statusDisplay.variant === 'destructive' && "bg-red-600",
          )}
        >
          {statusDisplay.text}
        </Badge>
      </div>
      {task.data.errorMessage && (
        <div className="mt-2 text-sm text-destructive whitespace-pre-wrap">
          Error: {task.data.errorMessage}
        </div>
      )}
      <div className="flex-1" />
      <ProgressBar 
        progress={(task.data.completedRequests / task.data.totalRequests) * 100}
        processedItems={task.data.completedRequests}
        totalItems={task.data.totalRequests}
        color="secondary"
      />
    </div>
  )

  return (
    <Task
      variant={variant}
      task={transformedTask}
      onClick={onClick}
      controlButtons={controlButtons}
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          <div className="flex justify-end w-full">
            {task.data.status === 'done' ? (
              <PackageCheck className="h-6 w-6" />
            ) : (
              <Package className="h-6 w-6" />
            )}
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization} />
      )}
    />
  )
} 