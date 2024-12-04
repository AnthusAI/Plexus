"use client"

import React, { useEffect, useState } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { Package, Square, X } from 'lucide-react'
import { ProgressBar } from "@/components/ui/progress-bar"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { CardButton } from '@/components/CardButton'
import { formatTimeAgo } from '@/lib/format-time'
import { BatchJobProgressBar, BatchJobStatus } from "@/components/ui/batch-job-progress-bar"
import { dataClient, listFromModel, getFromModel } from '@/utils/data-operations'
import type { Schema } from "@/amplify/data/resource"

interface ScoringJobData {
  id: string
  status: string
  startedAt?: string | null
  completedAt?: string | null
  errorMessage?: string | null
  itemId: string
  accountId: string
  scorecardId: string
  evaluationId?: string | null
  scoreId?: string | null
  batchJobId: string
}

export interface BatchJobTaskData {
  id: string
  modelProvider: string
  modelName: string
  type: string
  status: string
  totalRequests: number
  completedRequests: number
  failedRequests: number
  startedAt: string | null
  estimatedEndAt: string | null
  completedAt: string | null
  errorMessage: string | null
  errorDetails: Record<string, unknown>
  scoringJobs?: ScoringJobData[]
}

export interface BatchJobTaskProps extends BaseTaskProps<BatchJobTaskData> {
  variant: 'grid' | 'detail' | 'nested'
  onToggleFullWidth?: () => void
  onClose?: () => void
}

function getStatusDisplay(status: string): { text: string; variant: string } {
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

// Update the type guard to be more specific
function isValidTaskData(data: unknown): data is Required<BatchJobTaskData> {
  return data !== undefined && data !== null && typeof (data as any).id === 'string';
}

export default function BatchJobTask({
  task,
  variant = 'grid',
  onToggleFullWidth,
  onClose,
}: BatchJobTaskProps) {
  const [scoringJobs, setScoringJobs] = useState<ScoringJobData[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Ensure task.data is valid before using it
  if (!task.data || !isValidTaskData(task.data)) {
    return null;
  }

  // Store task.data in a variable to avoid undefined checks
  const taskData = task.data;

  useEffect(() => {
    let subscriptions: { unsubscribe: () => void }[] = []

    const loadScoringJobs = async () => {
      try {
        console.log('Loading scoring jobs for batch:', taskData.id);
        
        // Use the secondary index to query ScoringJobs directly
        const result = await listFromModel('ScoringJob', {
          filter: {
            batchJobId: { eq: taskData.id }
          }
        })
        
        console.log('Scoring jobs result:', result);
        
        if (result.data) {
          const scoringJobs = result.data.map(job => ({
            id: job.id as string,
            status: job.status as string,
            startedAt: job.startedAt as string | null,
            completedAt: job.completedAt as string | null,
            errorMessage: job.errorMessage as string | null,
            itemId: job.itemId as string,
            accountId: job.accountId as string,
            scorecardId: job.scorecardId as string,
            evaluationId: job.evaluationId as string | null,
            scoreId: job.scoreId as string | null,
            batchJobId: job.batchJobId as string
          }))
          
          setScoringJobs(scoringJobs);
        }
        
        // Set up subscriptions for real-time updates
        if (dataClient.models.BatchJobScoringJob) {
          // Subscribe to onCreate of BatchJobScoringJob
          const createSub = (dataClient.models.BatchJobScoringJob.onCreate() as any)
            .subscribe({
              next: async (data: Schema['BatchJobScoringJob']['type']) => {
                if (data.batchJobId === taskData.id) {
                  const jobResult = await getFromModel('ScoringJob', data.scoringJobId)
                  
                  if (jobResult.data) {
                    setScoringJobs(prev => [
                      ...prev,
                      {
                        id: jobResult.data!.id,
                        status: jobResult.data!.status,
                        startedAt: jobResult.data!.startedAt || null,
                        completedAt: jobResult.data!.completedAt || null,
                        errorMessage: jobResult.data!.errorMessage || null,
                        itemId: jobResult.data!.itemId,
                        accountId: jobResult.data!.accountId,
                        scorecardId: jobResult.data!.scorecardId,
                        evaluationId: jobResult.data!.evaluationId || null,
                        scoreId: jobResult.data!.scoreId || null,
                        batchJobId: taskData.id
                      }
                    ]);
                  }
                }
              },
              error: (error: unknown) => console.error('onCreate subscription error:', error)
            });

          // Subscribe to onUpdate of ScoringJob
          const updateSub = (dataClient.models.ScoringJob.onUpdate() as any)
            .subscribe({
              next: (data: Schema['ScoringJob']['type']) => {
                setScoringJobs(prev => {
                  const isJobInList = prev.some(job => job.id === data.id);
                  if (!isJobInList) return prev;
                  return prev.map(job => 
                    job.id === data.id ? {
                      ...job,
                      ...data,
                      batchJobId: taskData.id
                    } : job
                  );
                });
              },
              error: (error: unknown) => console.error('onUpdate subscription error:', error)
            });

          subscriptions.push(createSub);
          subscriptions.push(updateSub);
        }

        setIsLoading(false);
      } catch (error) {
        console.error('Error loading scoring jobs:', error);
        setIsLoading(false);
      }
    };

    loadScoringJobs();

    return () => {
      subscriptions.forEach(sub => sub.unsubscribe());
    };
  }, [taskData.id]);

  const progress = taskData.totalRequests ? 
    Math.round((taskData.completedRequests / taskData.totalRequests) * 100) : 0;

  const showScoringJobs = variant === 'detail' && scoringJobs.length > 0;

  const taskWithTime = {
    ...task,
    time: taskData.completedAt || taskData.startedAt || task.time || new Date().toISOString()
  };

  const headerContent = (
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
  )

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
            <div className="space-y-4">
              <div className="space-y-0.5">
                <div className="font-semibold">
                  {task.scorecard}
                </div>
                <div className="text-sm text-muted-foreground">
                  {task.score}
                </div>
                <div className="text-sm text-muted-foreground">
                  {formatTimeAgo(taskWithTime.time)}
                </div>
                <div className="text-sm text-muted-foreground">
                  <div>{taskData.type}</div>
                  <div>{taskData.modelProvider}</div>
                  <div>{taskData.modelName}</div>
                </div>
              </div>

              <div className="space-y-2">
                <BatchJobProgressBar 
                  status={taskData.status as BatchJobStatus}
                />
                <ProgressBar 
                  progress={progress}
                  processedItems={taskData.completedRequests}
                  totalItems={taskData.totalRequests}
                  color="secondary"
                />
              </div>

              {taskData.errorMessage && (
                <div className="mt-2 text-sm text-destructive whitespace-pre-wrap">
                  Error: {taskData.errorMessage}
                </div>
              )}
            </div>

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
                            Scoring Job {job.id}
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
                            getStatusDisplay(job.status).variant === 'success' && 
                              "bg-green-600",
                            getStatusDisplay(job.status).variant === 'warning' && 
                              "bg-yellow-600",
                            getStatusDisplay(job.status).variant === 'destructive' && 
                              "bg-red-600",
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