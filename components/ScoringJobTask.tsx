import React from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { ClipboardCheck, Package, PackageCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { ProgressBar } from "@/components/ui/progress-bar"
import { Separator } from "@/components/ui/separator"
import BatchJobTask from '@/components/BatchJobTask'
import { RelatedBatchJob } from '@/types/tasks'

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

export interface ScoringJobTaskProps extends BaseTaskProps<ScoringJobTaskData> {}

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

const transformScoringJobData = (task: ScoringJobTaskProps['task']) => {
  if (!task.data) return task
  return {
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
  }
}

export default function ScoringJobTask({ 
  variant = "grid",
  task,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}: ScoringJobTaskProps) {
  const data = task.data ?? {} as ScoringJobTaskData
  const statusDisplay = getStatusDisplay(data.status)

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
        {data.errorMessage && (
          <div className="mt-2 text-sm text-destructive whitespace-pre-wrap">
            Error: {data.errorMessage}
          </div>
        )}
      </div>
      <div className="flex-1" />
      <ProgressBar 
        progress={(data.completedItems / data.totalItems) * 100}
        processedItems={data.completedItems}
        totalItems={data.totalItems}
        color="secondary"
      />
      
      {variant === 'detail' && data.batchJobs && (
        <div className="mt-8">
          <div className="text-sm text-muted-foreground tracking-wider mb-2">
            Batch jobs
          </div>
          <hr className="mb-4 border-border" />
          <div className="space-y-2">
            {data.batchJobs.map((batchJob) => (
              <BatchJobTask
                key={batchJob.id}
                variant="grid"
                task={{
                  id: batchJob.id,
                  type: 'Batch Job',
                  scorecard: task.scorecard,
                  score: task.score,
                  time: task.time,
                  summary: `${batchJob.type} job`,
                  data: {
                    type: batchJob.type,
                    status: batchJob.status,
                    totalRequests: batchJob.totalRequests || 0,
                    completedRequests: batchJob.completedRequests || 0,
                    failedRequests: batchJob.failedRequests || 0,
                    startedAt: batchJob.startedAt || undefined,
                    completedAt: batchJob.completedAt || undefined,
                    errorMessage: batchJob.errorMessage || undefined,
                    errorDetails: batchJob.errorDetails || undefined,
                    modelProvider: batchJob.modelProvider,
                    modelName: batchJob.modelName,
                    scoringJobs: []
                  }
                }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )

  return (
    <Task
      variant={variant}
      task={{
        ...task,
        data: {
          ...data,
          progress: (data.completedItems / data.totalItems) * 100
        }
      }}
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