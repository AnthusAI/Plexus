import React from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { ClipboardCheck, Package, PackageCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { ProgressBar } from "@/components/ui/progress-bar"
import { Separator } from "@/components/ui/separator"
import BatchJobTask from '@/components/BatchJobTask'

export interface RelatedBatchJob {
  id: string
  provider: string
  type: string
  status: string
  totalRequests: number
  completedRequests: number
  failedRequests: number
  errorMessage?: string
}

export interface ScoringJobTaskData {
  status: string
  startedAt?: string
  completedAt?: string
  errorMessage?: string
  errorDetails?: any
  itemName?: string
  scorecardName?: string
  totalItems: number
  completedItems: number
  batchJobs?: RelatedBatchJob[]
}

export type ScoringJobTaskProps = {
  variant?: 'grid' | 'detail'
  task: {
    id: number
    type: string
    scorecard: string
    score: string
    time: string
    summary: string
    description?: string
    data: ScoringJobTaskData
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

const transformScoringJobData = (task: ScoringJobTaskProps['task']) => ({
  ...task,
  data: {
    progress: (task.data.completedItems / task.data.totalItems) * 100,
    processedItems: task.data.completedItems,
    totalItems: task.data.totalItems,
    numberComplete: task.data.completedItems,
    numberTotal: task.data.totalItems,
    eta: task.data.startedAt,
    elapsedTime: task.data.completedAt
  }
})

export default function ScoringJobTask({ 
  variant = "grid",
  task,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}: ScoringJobTaskProps) {
  const transformedTask = transformScoringJobData(task)
  const statusDisplay = getStatusDisplay(task.data.status)

  const visualization = (
    <div className="flex flex-col h-full">
      <div>
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
      </div>
      <div className="flex-1" />
      <ProgressBar 
        progress={(task.data.completedItems / task.data.totalItems) * 100}
        processedItems={task.data.completedItems}
        totalItems={task.data.totalItems}
        color="secondary"
      />
      
      {variant === 'detail' && task.data.batchJobs && (
        <>
          <Separator className="my-4" />
          <div>
            <div className="text-sm font-semibold mb-4">Batch Jobs</div>
            <div className="space-y-2">
              {task.data.batchJobs.map((batchJob) => (
                <BatchJobTask
                  key={batchJob.id}
                  variant="nested"
                  task={{
                    id: parseInt(batchJob.id),
                    type: 'Batch Job',
                    scorecard: task.scorecard,
                    score: task.score,
                    time: task.time,
                    summary: `${batchJob.provider} ${batchJob.type}`,
                    data: batchJob,
                  }}
                />
              ))}
            </div>
          </div>
        </>
      )}
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
            <ClipboardCheck className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization} />
      )}
    />
  )
} 