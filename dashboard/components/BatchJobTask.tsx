"use client"

import React, { useEffect, useState } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { Package, Square, X } from 'lucide-react'
import { DualPhaseProgressBar } from "@/components/ui/dual-phase-progress-bar"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { CardButton } from '@/components/CardButton'
import { formatTimeAgo } from '@/lib/format-time'
import { BatchJobProgressBar, BatchJobStatus } from "@/components/ui/batch-job-progress-bar"
import { getClient, listFromModel, getFromModel } from '@/utils/data-operations'
import type { Schema } from "@/amplify/data/resource"
import { 
  createBatchJobScoringJobSubscription,
  createScoringJobSubscription,
  BatchJobScoringJobSubscriptionData,
  ScoringJobSubscriptionData
} from '@/utils/subscriptions'
import { BaseTaskData } from '@/types/base'

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
  title: string
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
  errorMessage?: string
  errorDetails: Record<string, unknown>
  scoringJobs?: ScoringJobData[]
  scoringJobCountCache?: number
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

function isValidTaskData(data: unknown): data is Required<BatchJobTaskData> {
  return data !== undefined && data !== null && typeof (data as any).id === 'string';
}

// Configuration constants
const BATCH_JOB_CONFIG = {
  MAX_SCORING_JOBS: 20
} as const;

// First phase includes both OPEN and CLOSED states
const FIRST_PHASE_STATES = ['OPEN', 'CLOSED'] as const;

export default function BatchJobTask({
  task,
  variant = 'grid',
  onToggleFullWidth,
  onClose,
}: BatchJobTaskProps) {
  const [scoringJobs, setScoringJobs] = useState<ScoringJobData[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!task.data || !isValidTaskData(task.data)) {
      return;
    }

    const taskData = task.data;
    let subscriptions: { unsubscribe: () => void }[] = []

    const loadScoringJobs = async () => {
      try {
        console.log('Loading scoring jobs for batch:', taskData.id);
        
        // Use listFromModel helper instead of direct dataClient access
        const linksResult = await listFromModel<Schema['BatchJobScoringJob']['type']>('BatchJobScoringJob', {
          filter: {
            batchJobId: { eq: taskData.id }
          }
        });
        
        console.log('BatchJobScoringJob links loaded:', {
          count: linksResult.data?.length || 0,
          expectedCount: taskData.scoringJobCountCache,
          sampleLinks: linksResult.data?.slice(0, 3).map(link => ({
            batchJobId: link.batchJobId,
            scoringJobId: link.scoringJobId
          }))
        });

        if (!linksResult.data) {
          console.log('No BatchJobScoringJob links found');
          setScoringJobs([]);
          setIsLoading(false);
          return;
        }

        // Get all scoring jobs in one query using IN filter
        const scoringJobIds = linksResult.data.map(link => link.scoringJobId);
        
        console.log('Fetching scoring jobs:', {
          ids: scoringJobIds
        });

        // Fetch each scoring job individually
        const jobResults = await Promise.all(
          scoringJobIds.map(id => getFromModel('ScoringJob', id))
        );

        type ScoringJobResult = Awaited<ReturnType<typeof getFromModel<'ScoringJob'>>>;
        
        const validJobs = jobResults
          .filter((result: ScoringJobResult): result is ScoringJobResult & { data: NonNullable<ScoringJobResult['data']> } => 
            result.data !== null
          )
          .map((result: ScoringJobResult & { data: NonNullable<ScoringJobResult['data']> }) => {
            const job = result.data;
            return {
              id: job.id as string,
              status: job.status as string,
              startedAt: (job.startedAt as string) || null,
              completedAt: (job.completedAt as string) || null,
              errorMessage: (job.errorMessage as string) || null,
              itemId: job.itemId as string,
              accountId: job.accountId as string,
              scorecardId: job.scorecardId as string,
              evaluationId: (job.evaluationId as string) || null,
              scoreId: (job.scoreId as string) || null,
              batchJobId: taskData.id,
              createdAt: job.createdAt as string
            } satisfies ScoringJobData;
          });

        console.log('ScoringJobs loaded:', {
          count: validJobs.length,
          expectedCount: scoringJobIds.length,
          sampleJobs: validJobs.slice(0, 3).map((job: ScoringJobData) => ({
            id: job.id,
            status: job.status,
            itemId: job.itemId
          }))
        });

        setScoringJobs(validJobs);
        
        // Set up subscriptions with proper types
        const client = getClient();
        if (client.models.BatchJobScoringJob) {
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

    // Only load scoring jobs if we're in detail view
    if (variant === 'detail') {
      loadScoringJobs();
    } else {
      setIsLoading(false);
    }

    return () => {
      subscriptions.forEach(sub => sub.unsubscribe());
    };
  }, [task.data, variant, task.data?.scoringJobCountCache]);

  if (!task.data || !isValidTaskData(task.data)) {
    return null;
  }

  const taskData = task.data;

  const isFirstPhase = FIRST_PHASE_STATES.includes(taskData.status as typeof FIRST_PHASE_STATES[number]);
  const firstPhaseProgress = Math.round((taskData.scoringJobCountCache || 0) / BATCH_JOB_CONFIG.MAX_SCORING_JOBS * 100);

  const secondPhaseProgress = taskData.totalRequests ? 
    Math.round((taskData.completedRequests / taskData.totalRequests) * 100) : 0;

  const showScoringJobs = variant === 'detail' && (taskData.scoringJobCountCache || 0) > 0;

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
                <DualPhaseProgressBar 
                  isFirstPhase={isFirstPhase}
                  firstPhaseProgress={firstPhaseProgress}
                  firstPhaseProcessedItems={taskData.scoringJobCountCache || 0}
                  firstPhaseTotalItems={BATCH_JOB_CONFIG.MAX_SCORING_JOBS}
                  secondPhaseProgress={secondPhaseProgress}
                  secondPhaseProcessedItems={taskData.completedRequests}
                  secondPhaseTotalItems={taskData.totalRequests}
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
                  Scoring Jobs ({taskData.scoringJobCountCache || 0})
                </div>
                <hr className="mb-4 border-border" />
                <div className="space-y-2">
                  {isLoading ? (
                    <div className="text-sm text-muted-foreground">
                      Loading scoring jobs...
                    </div>
                  ) : scoringJobs.length === 0 ? (
                    <div className="text-sm text-muted-foreground">
                      No scoring jobs loaded yet
                    </div>
                  ) : (
                    scoringJobs.map((job) => (
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
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </TaskContent>
      )}
    />
  )
} 