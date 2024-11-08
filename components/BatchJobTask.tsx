import React from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { Package } from 'lucide-react'
import { TaskProgress } from '@/components/TaskProgress'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

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
  variant?: 'grid' | 'detail'
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
    validating: { text: 'Validating', variant: 'secondary' },
    in_progress: { text: 'In Progress', variant: 'default' },
    finalizing: { text: 'Finalizing', variant: 'secondary' },
    completed: { text: 'Completed', variant: 'success' },
    failed: { text: 'Failed', variant: 'destructive' },
    expired: { text: 'Expired', variant: 'destructive' },
    canceling: { text: 'Canceling', variant: 'warning' },
    canceled: { text: 'Canceled', variant: 'warning' },
  }
  return statusMap[status.toLowerCase()] || { text: status, variant: 'default' }
}

export default function BatchJobTask({ 
  variant = "grid",
  task,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}: BatchJobTaskProps) {
  const data = task.data
  const statusDisplay = getStatusDisplay(data.status)

  const visualization = (
    <div className="flex flex-col h-full">
      <div>
        <Badge 
          variant={statusDisplay.variant as any}
          className={cn(
            "capitalize w-fit mb-4",
            statusDisplay.variant === 'success' && "bg-green-600",
            statusDisplay.variant === 'warning' && "bg-yellow-600",
            statusDisplay.variant === 'destructive' && "bg-red-600",
          )}
        >
          {statusDisplay.text}
        </Badge>
        {data.errorMessage && (
          <div className="mt-2 text-sm text-destructive whitespace-pre-wrap">
            Error: {data.errorMessage}
          </div>
        )}
      </div>
      <div className="flex-1" />
      <TaskProgress 
        progress={(data.completedRequests / data.totalRequests) * 100}
        processedItems={data.completedRequests}
        totalItems={data.totalRequests}
      />
    </div>
  )

  return (
    <Task
      variant={variant}
      task={task}
      onClick={onClick}
      controlButtons={controlButtons}
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          <div className="flex justify-end w-full">
            <Package className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization} />
      )}
    />
  )
} 