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
import { 
  createBatchJobScoringJobSubscription,
  createScoringJobSubscription,
  BatchJobScoringJobSubscriptionData,
  ScoringJobSubscriptionData
} from '@/utils/subscriptions'

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
  createdAt: string
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
    RUNNING: { text: 'Running', variant: 'secondary' },
    COMPLETED: { text: 'success', variant: 'success' },
    FAILED: { text: 'Failed', variant: 'destructive' },
    CANCELED: { text: 'Canceled', variant: 'secondary' },
  }
  return statusMap[normalizedStatus] || { text: status, variant: 'secondary' }
}

// Update the type guard to be more specific
function isValidTaskData(data: unknown): data is Required<BatchJobTaskData> {
  return data !== undefined && data !== null && typeof (data as any).id === 'string';
}

// First, let's add some type helpers
type ScoringJobModel = Schema['ScoringJob']['type'];
type BatchJobScoringJobModel = Schema['BatchJobScoringJob']['type'];

// First, add a type for the job result
type ScoringJobResult = {
  data: ScoringJobModel | null;
};

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
        
        // First get the links from BatchJobScoringJob
        const linksResult = await listFromModel(
          'BatchJobScoringJob',
          { 
            filter: {
              batchJobId: { eq: taskData.id }
            },
            limit: 1000
          }
        );
        
        console.log('BatchJobScoringJob links:', linksResult);
        
        if (linksResult.data) {
          // Get all scoring job IDs
          const scoringJobIds = linksResult.data.map(link => link.scoringJobId);
          
          // Then update the Promise.all section
          const jobsResult = await Promise.all(
            scoringJobIds.map(async id => {
              const result = await getFromModel('ScoringJob', id);
              return result as ScoringJobResult;
            })
          );
          
          // Filter out nulls and map to our format
          const validJobs = jobsResult
            .filter(result => result.data)
            .map(result => {
              const job = result.data!;
              return {
                id: job.id,
                status: job.status,
                startedAt: job.startedAt || null,
                completedAt: job.completedAt || null,
                errorMessage: job.errorMessage || null,
                itemId: job.itemId,
                accountId: job.accountId,
                scorecardId: job.scorecardId,
                evaluationId: job.evaluationId || null,
                scoreId: job.scoreId || null,
                batchJobId: taskData.id,
                createdAt: job.createdAt
              };
            });
          
          setScoringJobs(validJobs);
        }
        
        // Set up subscriptions with proper types
        if (dataClient.models.BatchJobScoringJob) {
          // Use the subscription helper for BatchJobScoringJob
          const handleBatchJobData = async (data: BatchJobScoringJobSubscriptionData) => {
            if (!data?.batchJobId || !data?.scoringJobId) return;
            
            if (data.batchJobId === taskData.id) {
              const jobResult = await getFromModel('ScoringJob', data.scoringJobId);
              const scoringJob = jobResult?.data;
              
              if (scoringJob) {
                setScoringJobs((prev) => [
                  ...prev,
                  {
                    id: scoringJob.id,
                    status: scoringJob.status,
                    startedAt: scoringJob.startedAt || null,
                    completedAt: scoringJob.completedAt || null,
                    errorMessage: scoringJob.errorMessage || null,
                    itemId: scoringJob.itemId,
                    accountId: scoringJob.accountId,
                    scorecardId: scoringJob.scorecardId,
                    evaluationId: scoringJob.evaluationId || null,
                    scoreId: scoringJob.scoreId || null,
                    batchJobId: taskData.id,
                    createdAt: scoringJob.createdAt,
                  },
                ]);
              }
            }
          };

          const handleBatchJobError = (error: unknown) => {
            console.error('onCreate subscription error:', error);
          };

          const createSub = createBatchJobScoringJobSubscription(
            handleBatchJobData,
            handleBatchJobError
          );

          // Use the subscription helper for ScoringJob updates
          const handleScoringJobData = (data: ScoringJobSubscriptionData) => {
            if (!data?.id) return;
            
            setScoringJobs((prev) => {
              const isJobInList = prev.some((job) => job.id === data.id);
              if (!isJobInList) return prev;
              
              return prev.map((job) => 
                job.id === data.id 
                  ? {
                      ...job,
                      ...data,
                      batchJobId: taskData.id,
                    }
                  : job
              );
            });
          };

          const handleScoringJobError = (error: unknown) => {
            console.error('onUpdate subscription error:', error);
          };

          const updateSub = createScoringJobSubscription(
            handleScoringJobData,
            handleScoringJobError
          );

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
                        <div className="space-y-1">
                          <div className="text-sm text-muted-foreground">
                            Item: {job.itemId}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {formatTimeAgo(job.createdAt)}
                          </div>
                        </div>
                        <Badge 
                          variant={getStatusDisplay(job.status).variant as any}
                          className={cn(
                            "capitalize",
                            job.status.toUpperCase() === 'COMPLETED' && "bg-true",
                            job.status.toUpperCase() === 'FAILED' && "bg-false",
                            !['COMPLETED', 'FAILED'].includes(job.status.toUpperCase()) && 
                              "bg-neutral-600"
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