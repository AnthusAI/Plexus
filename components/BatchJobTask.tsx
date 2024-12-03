"use client"

import React, { useMemo } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { Package, Square, X } from 'lucide-react'
import { ProgressBar } from "@/components/ui/progress-bar"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { CardButton } from '@/components/CardButton'
import { formatTimeAgo } from '@/lib/format-time'

export interface BatchJobTaskData {
  modelProvider: string
  modelName: string
  type: string
  status: string
  totalRequests: number
  completedRequests: number
  failedRequests: number
  startedAt?: string
  estimatedEndAt?: string
  completedAt?: string
  errorMessage?: string
  errorDetails?: any
  scoringJobs?: {
    id: string
    status: string
    startedAt?: string | null
    completedAt?: string | null
    errorMessage?: string | null
    scoringJobId: string
    batchJobId: string
  }[]
}

export interface BatchJobTaskProps extends BaseTaskProps<BatchJobTaskData> {
  variant: 'grid' | 'detail' | 'nested'
  onToggleFullWidth?: () => void
  onClose?: () => void
}

const getStatusDisplay = (status: string): { text: string; variant: string } => {
  const normalizedStatus = status?.toUpperCase() || 'PENDING'
  const statusMap: Record<string, { text: string; variant: string }> = {
    PENDING: { text: 'Pending', variant: 'secondary' },
    RUNNING: { text: 'Running', variant: 'default' },
    COMPLETED: { text: 'Completed', variant: 'success' },
    FAILED: { text: 'Failed', variant: 'destructive' },
    CANCELED: { text: 'Canceled', variant: 'warning' },
  }
  return statusMap[normalizedStatus] || { text: status, variant: 'default' }
}

export default function BatchJobTask({
  task,
  variant = 'grid',
  onToggleFullWidth,
  onClose,
}: BatchJobTaskProps) {
  const data = task.data ?? {} as BatchJobTaskData
  const statusDisplay = getStatusDisplay(data.status)
  const progress = data.totalRequests ? 
    Math.round((data.completedRequests / data.totalRequests) * 100) : 0

  const scoringJobs = data.scoringJobs || []
  const showScoringJobs = variant === 'detail' && scoringJobs.length > 0

  const taskWithTime = {
    ...task,
    time: data.completedAt || data.startedAt || task.time || new Date().toISOString()
  }

  const headerContent = useMemo(() => (
    <div className="flex justify-end w-full">
      {variant === 'detail' ? (
        <div className="flex items-center space-x-2">
          {typeof onToggleFullWidth === 'function' && (
            <CardButton
              icon={Square}
              onClick={onToggleFullWidth}
            />
          )}
          {typeof onClose === 'function' && (
            <CardButton
              icon={X}
              onClick={onClose}
            />
          )}
        </div>
      ) : (
        <Package className="h-6 w-6" />
      )}
    </div>
  ), [variant, onToggleFullWidth, onClose])

  return (
    <Task
      variant={variant}
      task={taskWithTime}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          {headerContent}
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props}>
          <div className="flex flex-col h-full">
            <div>
              <div className="flex justify-start mb-4">
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
              <div className="flex items-center gap-2 mb-4">
                <Badge variant="outline" className="capitalize">
                  {data.modelProvider}
                </Badge>
                <span className="text-sm text-muted-foreground">/</span>
                <Badge variant="outline" className="capitalize">
                  {data.modelName}
                </Badge>
              </div>
              {data.errorMessage && (
                <div className="mt-2 text-sm text-destructive whitespace-pre-wrap">
                  Error: {data.errorMessage}
                </div>
              )}
            </div>
            <ProgressBar 
              progress={progress}
              processedItems={data.completedRequests}
              totalItems={data.totalRequests}
              color="secondary"
            />
            {showScoringJobs && (
              <div className="mt-8">
                <div className="text-sm text-muted-foreground tracking-wider mb-2">
                  Scoring Jobs ({scoringJobs.length})
                </div>
                <hr className="mb-4 border-border" />
                <div className="space-y-2">
                  {scoringJobs.map((job) => (
                    <div 
                      key={job.id} 
                      className="p-4 bg-card-light rounded-lg"
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <div className="font-medium">
                            Scoring Job {job.scoringJobId}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            Status: {job.status}
                          </div>
                          {job.startedAt && (
                            <div className="text-sm text-muted-foreground">
                              Started: {formatTimeAgo(job.startedAt)}
                            </div>
                          )}
                          {job.completedAt && (
                            <div className="text-sm text-muted-foreground">
                              Completed: {formatTimeAgo(job.completedAt)}
                            </div>
                          )}
                          {job.errorMessage && (
                            <div className="text-sm text-destructive mt-2">
                              Error: {job.errorMessage}
                            </div>
                          )}
                        </div>
                        <Badge 
                          variant={getStatusDisplay(job.status).variant as any}
                          className={cn(
                            "capitalize",
                            getStatusDisplay(job.status).variant === 'success' && "bg-green-600",
                            getStatusDisplay(job.status).variant === 'warning' && "bg-yellow-600",
                            getStatusDisplay(job.status).variant === 'destructive' && "bg-red-600",
                          )}
                        >
                          {getStatusDisplay(job.status).text}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </TaskContent>
      )}
    />
  )
} 