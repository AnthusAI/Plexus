import React from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { Package, PackageCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { ProgressBar } from "@/components/ui/progress-bar"
import { BatchJobTaskData, RelatedBatchJob } from '@/types/tasks'
import { BaseTaskProps } from '@/components/Task'

interface BatchJobTaskProps extends BaseTaskProps<BatchJobTaskData> {}

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

const transformBatchJobData = (task: BatchJobTaskProps['task']) => {
  if (!task.data) return task
  const data = task.data
  return {
    ...task,
    data: {
      ...data,
      progress: (data.completedRequests / data.totalRequests) * 100,
      processedItems: data.completedRequests,
      totalItems: data.totalRequests,
      numberComplete: data.completedRequests,
      numberTotal: data.totalRequests,
      eta: data.startedAt,
      elapsedTime: data.completedAt
    }
  }
}

export default class BatchJobTask extends React.Component<BatchJobTaskProps> {
  renderBatchJob = (batchJob: RelatedBatchJob) => (
    <BatchJobTask
      key={batchJob.id}
      variant="nested"
      task={{
        id: batchJob.id,
        type: 'Batch Job',
        scorecard: this.props.task.scorecard,
        score: this.props.task.score,
        time: this.props.task.time,
        summary: `${batchJob.provider} ${batchJob.type}`,
        data: batchJob,
      }}
    />
  )

  render() {
    const { variant = "grid", task, onClick, controlButtons, isFullWidth, onToggleFullWidth, onClose } = this.props
    const data = task.data ?? {} as BatchJobTaskData
    const statusDisplay = getStatusDisplay(data.status || 'pending')
    const transformedTask = transformBatchJobData(task)

    if (variant === 'nested') {
      return (
        <div className="bg-background/50 py-3 rounded-md space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {data.status === 'done' ? (
                <PackageCheck className="h-4 w-4" />
              ) : (
                <Package className="h-4 w-4" />
              )}
              <span className="text-sm font-medium">
                {data.provider}
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
            progress={(data.completedRequests / data.totalRequests) * 100}
            processedItems={data.completedRequests}
            totalItems={data.totalRequests}
            color="secondary"
          />
          {data.errorMessage && (
            <div className="text-xs text-destructive">
              Error: {data.errorMessage}
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
        {data.errorMessage && (
          <div className="mt-2 text-sm text-destructive whitespace-pre-wrap">
            Error: {data.errorMessage}
          </div>
        )}
        <div className="flex-1" />
        <ProgressBar 
          progress={(data.completedRequests / data.totalRequests) * 100}
          processedItems={data.completedRequests}
          totalItems={data.totalRequests}
          color="secondary"
        />
        
        {variant === 'detail' && data.batchJobs && (
          <div className="mt-8">
            <div className="text-sm text-muted-foreground tracking-wider mb-2">
              Batch jobs
            </div>
            <hr className="mb-4 border-border" />
            <div className="space-y-2">
              {data.batchJobs.map(this.renderBatchJob)}
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
            progress: (data.completedRequests / data.totalRequests) * 100
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
              {data.status === 'done' ? (
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
} 