"use client"

import React, { useState, useEffect, useRef, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { dataClient, listFromModel, getFromModel } from '@/utils/data-operations'
import type { Schema } from "@/amplify/data/resource"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { 
  Activity,
  MoreHorizontal,
  PlayCircle,
  StopCircle,
  AlertCircle
} from "lucide-react"
import { CardButton } from "@/components/CardButton"
import { format, formatDistanceToNow } from "date-fns"
import { observeQueryFromModel } from "@/utils/amplify-helpers"
import { useMediaQuery } from "../hooks/use-media-query"
import BatchJobTask from "@/components/BatchJobTask"
import { Subscription } from 'rxjs'
import { ProgressBar } from "@/components/ui/progress-bar"
import { Badge } from "@/components/ui/badge"
import { SegmentedProgressBar } from "@/components/ui/segmented-progress-bar"
import { BatchJobProgressBar, BatchJobStatus } from "@/components/ui/batch-job-progress-bar"
import { DualPhaseProgressBar } from "@/components/ui/dual-phase-progress-bar"

const ACCOUNT_KEY = 'call-criteria'

type ScorecardType = Schema['Scorecard']['type']
type ScoreType = Schema['Score']['type']
type BatchJobType = Schema['BatchJob']['type']

interface SimpleResponse<T> {
  data: T | null
}

interface SimpleAccount {
  id: string
  name: string
  key: string
}

interface SimpleBatchJob {
  id: string
  type: string
  status: string
  startedAt: string | null
  estimatedEndAt: string | null
  completedAt: string | null
  completedRequests: number | null
  failedRequests: number | null
  errorMessage: string | null
  errorDetails: Record<string, unknown>
  accountId: string
  scorecardId: string | null
  scoreId: string | null
  modelProvider: string
  modelName: string
  scoringJobCountCache: number | null
  createdAt: string
  updatedAt: string
}

async function listAccounts(): Promise<SimpleResponse<SimpleAccount[]>> {
  try {
    const result = await listFromModel('Account', {
      filter: {
        key: { eq: ACCOUNT_KEY }
      }
    });
    return { 
      data: result.data?.map(account => ({
        id: account.id as string,
        name: account.name as string,
        key: account.key as string
      })) || null 
    };
  } catch (error) {
    console.error('Error listing accounts:', error);
    return { data: null };
  }
}

async function listBatchJobs(accountId: string): Promise<SimpleResponse<SimpleBatchJob[]>> {
  try {
    const result = await listFromModel('BatchJob', {
      filter: {
        accountId: { eq: accountId }
      }
    });
    return { 
      data: result.data?.map(job => ({
        ...job,
        startedAt: (job.startedAt as string) || null,
        estimatedEndAt: (job.estimatedEndAt as string) || null,
        completedAt: (job.completedAt as string) || null,
        errorMessage: (job.errorMessage as string) || null,
        errorDetails: typeof job.errorDetails === 'object' && job.errorDetails !== null
          ? job.errorDetails as Record<string, unknown>
          : {} as Record<string, unknown>,
        completedRequests: (job.completedRequests as number) || 0,
        failedRequests: (job.failedRequests as number) || null,
        scorecardId: (job.scorecardId as string) || null,
        scoreId: (job.scoreId as string) || null,
        scoringJobCountCache: (job.scoringJobCountCache as number) || null
      })) || null 
    };
  } catch (error) {
    console.error('Error listing batch jobs:', error);
    return { data: null };
  }
}

type ScoreCardData = {
  id: string
  name: string
  key: string
  accountId: string
}

type ScoreData = {
  id: string
  name: string
  type: string
  sectionId: string
}

async function getScorecard(id: string): Promise<SimpleResponse<ScorecardType>> {
  const result = await getFromModel('Scorecard', id);
  return result;
}

async function getScore(id: string): Promise<SimpleResponse<ScoreType>> {
  const result = await getFromModel('Score', id);
  return result;
}

interface SimpleScoringJob {
  id: string
  status: string
  startedAt: string | null
  completedAt: string | null
  errorMessage: string | null
  itemId: string
  accountId: string
  scorecardId: string
  evaluationId: string | null
  scoreId: string | null
}

interface BatchJobWithCount {
  id: string
  type: string
  status: string
  startedAt: string | null
  estimatedEndAt: string | null
  completedAt: string | null
  completedRequests: number
  failedRequests: number | null
  errorMessage: string | null
  errorDetails: Record<string, unknown>
  accountId: string
  scorecardId: string | null
  scoreId: string | null
  modelProvider: string
  modelName: string
  scoringJobCountCache: number | null
  createdAt: string
  updatedAt: string
  scorecard: ScorecardType | null
  score: ScoreType | null
  scoringJobsCount: number
  scoringJobs: Schema['ScoringJob']['type'][]
  account: Schema['Account']['type']
  batchId: string
}

interface BatchJobListResponse {
  data: SimpleBatchJob[];
}

interface ScoringJobListResponse {
  data: SimpleScoringJob[];
}

function getProgressPercentage(job: BatchJobWithCount): number {
  const total = job.scoringJobCountCache || 0;
  const completed = job.completedRequests || 0;
  if (!total) return 0;
  return Math.round((completed / total) * 100);
}

type BatchStatus = 'RUNNING' | 'COMPLETED' | 'FAILED' | 'PENDING'

function getStatusIcon(status: string): JSX.Element {
  const normalizedStatus = (status?.toUpperCase() || 'PENDING') as BatchStatus;
  switch (normalizedStatus) {
    case 'RUNNING':
      return <PlayCircle className="h-4 w-4 text-primary animate-pulse" />;
    case 'COMPLETED':
      return <StopCircle className="h-4 w-4 text-success" />;
    case 'FAILED':
      return <AlertCircle className="h-4 w-4 text-destructive" />;
    default:
      return <Activity className="h-4 w-4 text-muted-foreground" />;
  }
}

function formatTimeAgo(dateStr?: string | null): string {
  if (!dateStr) return 'Not started';
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return 'Invalid date';
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return 'Invalid date';
  }
}

const mapBatchJob = async (job: BatchJobType): Promise<BatchJobWithCount> => {
  let scorecardData: ScorecardType | null = null;
  let scoreData: ScoreType | null = null;

  if (job.scorecardId) {
    try {
      const scorecardResult = await getScorecard(job.scorecardId);
      if (scorecardResult?.data) {
        scorecardData = scorecardResult.data;
      }
    } catch (err) {
      console.error('Error fetching scorecard:', err);
    }
  }

  if (job.scoreId) {
    try {
      const scoreResult = await getScore(job.scoreId);
      if (scoreResult?.data) {
        scoreData = scoreResult.data;
      }
    } catch (err) {
      console.error('Error fetching score:', err);
    }
  }

  return {
    id: job.id,
    type: job.type,
    status: job.status,
    startedAt: job.startedAt || null,
    estimatedEndAt: job.estimatedEndAt || null,
    completedAt: job.completedAt || null,
    completedRequests: job.completedRequests || 0,
    failedRequests: job.failedRequests || null,
    errorMessage: job.errorMessage || null,
    errorDetails: typeof job.errorDetails === 'object' ? 
      job.errorDetails as Record<string, unknown> : 
      {},
    accountId: job.accountId,
    scorecardId: job.scorecardId || null,
    scoreId: job.scoreId || null,
    modelProvider: job.modelProvider,
    modelName: job.modelName,
    scoringJobCountCache: job.scoringJobCountCache || null,
    createdAt: job.createdAt,
    updatedAt: job.updatedAt,
    scorecard: scorecardData,
    score: scoreData,
    scoringJobsCount: job.scoringJobCountCache || 0,
    scoringJobs: [],
    account: {} as Schema['Account']['type'],
    batchId: job.id
  };
};

const BATCH_JOB_SUBSCRIPTION = `
  subscription OnBatchJobChange($accountId: String!) {
    onBatchJobChange(accountId: $accountId) {
      id
      type
      status
      startedAt
      estimatedEndAt
      completedAt
      totalRequests
      completedRequests
      failedRequests
      errorMessage
      errorDetails
      accountId
      scorecardId
      scoreId
      modelProvider
      modelName
      scoringJobCountCache
      createdAt
      updatedAt
    }
  }
`;

interface SubscriptionResponse {
  items: Schema['BatchJob']['type'][];
}

interface BatchJobWithRelatedData extends BatchJobWithCount {
  scorecard: Schema['Scorecard']['type'] | null
  score: Schema['Score']['type'] | null
  scoringJobs: Schema['ScoringJob']['type'][]
  account: Schema['Account']['type']
}

async function loadRelatedData(batchJobs: SimpleBatchJob[]): Promise<BatchJobWithRelatedData[]> {
  const scorecardIds = [...new Set(batchJobs
    .filter(j => j.scorecardId)
    .map(j => j.scorecardId as string))]
  const scoreIds = [...new Set(batchJobs
    .filter(j => j.scoreId)
    .map(j => j.scoreId as string))]

  console.log('Loading related data:', {
    batchJobCount: batchJobs.length,
    scorecardIds,
    scoreIds
  });

  const [scorecards, scores] = await Promise.all([
    Promise.all(scorecardIds.map(id => getFromModel('Scorecard', id))),
    Promise.all(scoreIds.map(id => getFromModel('Score', id)))
  ])

  console.log('Loaded related data:', {
    scorecards: scorecards.map((s: SimpleResponse<ScorecardType>) => ({ 
      id: s.data?.id, 
      name: s.data?.name 
    })),
    scores: scores.map((s: SimpleResponse<ScoreType>) => ({ 
      id: s.data?.id, 
      name: s.data?.name 
    }))
  });

  const scorecardMap = new Map(
    scorecards.map((result: SimpleResponse<ScorecardType>) => {
      const data = result.data as ScorecardType
      return [data.id, data]
    })
  )
  const scoreMap = new Map(
    scores.map((result: SimpleResponse<ScoreType>) => {
      const data = result.data as ScoreType
      return [data.id, data]
    })
  )

  const transformedJobs = batchJobs.map((job): BatchJobWithRelatedData => ({
    ...job,
    completedRequests: job.completedRequests ?? 0,
    scorecard: (scorecardMap.get(job.scorecardId || '') || null) as Schema['Scorecard']['type'] | null,
    score: (scoreMap.get(job.scoreId || '') || null) as Schema['Score']['type'] | null,
    scoringJobs: [],
    account: {} as Schema['Account']['type'],
    scoringJobsCount: job.scoringJobCountCache || 0,
    batchId: job.id
  }));

  return transformedJobs;
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

function handleError(error: unknown) {
  console.error('An error occurred:', error);
}

const BATCH_JOB_CONFIG = {
  MAX_SCORING_JOBS: 20
} as const;

const FIRST_PHASE_STATES = ['OPEN', 'CLOSED'] as const;

export default function BatchesDashboard() {
  const [batchJobs, setBatchJobs] = useState<BatchJobWithCount[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [selectedBatchJob, setSelectedBatchJob] = useState<BatchJobWithCount | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const isNarrowViewport = useMediaQuery('(max-width: 768px)')
  const subscriptionsRef = useRef<{ unsubscribe: () => void }[]>([])
  const containerRef = useRef<HTMLDivElement>(null)
  const dragStateRef = useRef<{
    isDragging: boolean
    startX: number
    startWidth: number
  }>({
    isDragging: false,
    startX: 0,
    startWidth: 50
  })

  const handleDragStart = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault()
    dragStateRef.current = {
      isDragging: true,
      startX: e.clientX,
      startWidth: leftPanelWidth
    }
    document.addEventListener('mousemove', handleDragMove)
    document.addEventListener('mouseup', handleDragEnd)
  }, [leftPanelWidth])

  const handleDragMove = useCallback((e: MouseEvent) => {
    if (!dragStateRef.current.isDragging || !containerRef.current) return

    const element = containerRef.current
    const containerWidth = element.getBoundingClientRect().width
    const deltaX = e.clientX - dragStateRef.current.startX
    const newWidthPercent = (dragStateRef.current.startWidth * 
      containerWidth / 100 + deltaX) / containerWidth * 100

    const constrainedWidth = Math.min(Math.max(newWidthPercent, 20), 80)
    setLeftPanelWidth(constrainedWidth)
  }, [])

  const handleDragEnd = useCallback(() => {
    dragStateRef.current.isDragging = false
    document.removeEventListener('mousemove', handleDragMove)
    document.removeEventListener('mouseup', handleDragEnd)
  }, [])

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (selectedBatchJob && event.key === 'Escape') {
      setSelectedBatchJob(null)
      setIsFullWidth(false)
    }
  }, [selectedBatchJob])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  const handleActionClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
  }

  useEffect(() => {
    if (!accountId) return;

    try {
      if (dataClient.models.BatchJob) {
        const handleBatchUpdate = async (data: Schema['BatchJob']['type']) => {
          if (!accountId) return;
          
          const { data: updatedBatchJobs } = await listBatchJobs(accountId);
          if (!updatedBatchJobs) return;

          const transformedBatchJobs = updatedBatchJobs.map(job => ({
            ...job,
            completedRequests: job.completedRequests ?? 0
          }));
          
          const transformedJobs = await loadRelatedData(transformedBatchJobs);
          setBatchJobs(transformedJobs);

          // Update selectedBatchJob if it matches the updated job
          if (selectedBatchJob && data.id === selectedBatchJob.id) {
            const updatedJob = transformedJobs.find(job => job.id === selectedBatchJob.id);
            if (updatedJob) {
              setSelectedBatchJob(updatedJob);
            }
          }
        };

        const handleError = (error: unknown) => {
          console.error('Error:', error);
          setError(error instanceof Error ? error : new Error(String(error)));
        };

        // @ts-ignore - Amplify Gen2 typing issue
        const createSub = dataClient.models.BatchJob.onCreate().subscribe({
          next: handleBatchUpdate,
          error: handleError
        });

        // @ts-ignore - Amplify Gen2 typing issue
        const updateSub = dataClient.models.BatchJob.onUpdate().subscribe({
          next: handleBatchUpdate,
          error: handleError
        });

        subscriptionsRef.current = [createSub, updateSub];
      }
    } catch (error) {
      handleError(error);
    }

    return () => {
      subscriptionsRef.current.forEach(sub => sub.unsubscribe());
      subscriptionsRef.current = [];
    };
  }, [accountId]); // Keep only accountId in dependencies

  const handleBatchJobClick = (job: BatchJobWithCount) => {
    setSelectedBatchJob(job)
  }

  const handleBatchJobClose = () => {
    setSelectedBatchJob(null)
    setIsFullWidth(false)
  }

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const { data: accounts } = await listAccounts();
        if (!accounts?.length) {
          setIsLoading(false);
          return;
        }

        const foundAccountId = accounts[0].id;
        setAccountId(foundAccountId);

        const { data: batchJobs } = await listBatchJobs(foundAccountId);
        if (!batchJobs) {
          setIsLoading(false);
          return;
        }

        const transformedBatchJobs = batchJobs.map(job => ({
          ...job,
          completedRequests: typeof job.completedRequests === 'number' ? 
            job.completedRequests : 0
        }));

        const transformedJobs = await loadRelatedData(transformedBatchJobs);
        setBatchJobs(transformedJobs);
        setIsLoading(false);

      } catch (error) {
        console.error('Error loading initial data:', error);
        setError(error instanceof Error ? error : new Error('Failed to load initial data'));
        setIsLoading(false);
      }
    };

    loadInitialData();
  }, []); // Run once on mount

  useEffect(() => {
    if (selectedBatchJob) {
      const updatedJob = batchJobs.find(job => job.id === selectedBatchJob.id);
      if (updatedJob && JSON.stringify(updatedJob) !== JSON.stringify(selectedBatchJob)) {
        setSelectedBatchJob(updatedJob);
      }
    }
  }, [batchJobs, selectedBatchJob]);

  if (isLoading) {
    return <div>Loading...</div>
  }

  if (error) {
    return <div>Error: {error.message}</div>
  }

  return (
    <div className="h-full flex flex-col" ref={containerRef}>
      <div className={`flex ${isNarrowViewport ? 'flex-col' : ''} flex-1 h-full w-full`}>
        <div 
          className={`
            flex flex-col
            ${isFullWidth ? 'hidden' : ''} 
            ${(!selectedBatchJob || !isNarrowViewport) ? 'flex h-full' : 'hidden'}
            ${(!selectedBatchJob || isNarrowViewport) ? 'w-full' : ''}
          `}
          style={!isNarrowViewport && selectedBatchJob && !isFullWidth ? {
            width: `${leftPanelWidth}%`
          } : undefined}
        >
          <div className="p-2">
            <div className="space-y-4">
              <div className="@container">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[40%]">Batch</TableHead>
                      <TableHead className="w-[30%] hidden @[800px]:table-cell">Type</TableHead>
                      <TableHead className="w-[30%] hidden @[500px]:table-cell">Progress</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {batchJobs.map((job) => (
                      <TableRow 
                        key={job.id}
                        onClick={() => handleBatchJobClick(job)}
                        className={`cursor-pointer transition-colors duration-200 
                          ${job.id === selectedBatchJob?.id ? 'bg-muted' : 'hover:bg-muted'}`}
                      >
                        <TableCell>
                          {/* Mobile variant - visible when container is narrow */}
                          <div className="block @[500px]:hidden">
                            <div className="flex flex-col space-y-2">
                              <div className="space-y-0.5">
                                <div className="font-semibold truncate">
                                  <span className={job.id === selectedBatchJob?.id ? 'text-focus' : ''}>
                                    {job.scorecard?.name || 'Unknown Scorecard'}
                                  </span>
                                </div>
                                <div className="text-sm text-muted-foreground">
                                  {job.score?.name || 'Unknown Score'}
                                </div>
                                <div className="text-sm text-muted-foreground">
                                  {formatTimeAgo(job.createdAt)}
                                </div>
                                <div className="text-sm text-muted-foreground">
                                  <div>{job.type}</div>
                                  <div>{job.modelProvider}</div>
                                  <div>{job.modelName}</div>
                                </div>
                              </div>
                              <div className="space-y-2">
                                <BatchJobProgressBar 
                                  status={job.status as BatchJobStatus}
                                />
                                <DualPhaseProgressBar 
                                  isFirstPhase={FIRST_PHASE_STATES.includes(job.status as typeof FIRST_PHASE_STATES[number])}
                                  firstPhaseProgress={Math.round((job.scoringJobsCount / BATCH_JOB_CONFIG.MAX_SCORING_JOBS) * 100)}
                                  firstPhaseProcessedItems={job.scoringJobsCount}
                                  firstPhaseTotalItems={BATCH_JOB_CONFIG.MAX_SCORING_JOBS}
                                  secondPhaseProgress={getProgressPercentage(job)}
                                  secondPhaseProcessedItems={job.completedRequests}
                                  secondPhaseTotalItems={job.scoringJobCountCache || 0}
                                  isFocused={job.id === selectedBatchJob?.id}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Tablet variant - visible at medium container widths */}
                          <div className="hidden @[500px]:block @[800px]:hidden">
                            <div className="font-semibold">
                              <span className={job.id === selectedBatchJob?.id ? 'text-focus' : ''}>
                                {job.scorecard?.name || 'Unknown Scorecard'}
                              </span>
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {job.score?.name || 'Unknown Score'}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {formatTimeAgo(job.createdAt)}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              <div>{job.type}</div>
                              <div>{job.modelProvider}</div>
                              <div>{job.modelName}</div>
                            </div>
                          </div>

                          {/* Desktop variant - visible at wide container widths */}
                          <div className="hidden @[800px]:block">
                            <div className="font-semibold">
                              <span className={job.id === selectedBatchJob?.id ? 'text-focus' : ''}>
                                {job.scorecard?.name || 'Unknown Scorecard'}
                              </span>
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {job.score?.name || 'Unknown Score'}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {formatTimeAgo(job.createdAt)}
                            </div>
                          </div>
                        </TableCell>

                        {/* Type column - visible at wide container widths */}
                        <TableCell className="hidden @[800px]:table-cell">
                          <div className="flex flex-col text-sm text-muted-foreground">
                            <div>{job.type}</div>
                            <div>{job.modelProvider}</div>
                            <div>{job.modelName}</div>
                          </div>
                        </TableCell>

                        {/* Progress column - visible at medium and wide container widths */}
                        <TableCell className="hidden @[500px]:table-cell">
                          <div className="space-y-2">
                            <BatchJobProgressBar 
                              status={job.status as BatchJobStatus}
                            />
                            <DualPhaseProgressBar 
                              isFirstPhase={FIRST_PHASE_STATES.includes(job.status as typeof FIRST_PHASE_STATES[number])}
                              firstPhaseProgress={Math.round((job.scoringJobsCount / BATCH_JOB_CONFIG.MAX_SCORING_JOBS) * 100)}
                              firstPhaseProcessedItems={job.scoringJobsCount}
                              firstPhaseTotalItems={BATCH_JOB_CONFIG.MAX_SCORING_JOBS}
                              secondPhaseProgress={getProgressPercentage(job)}
                              secondPhaseProcessedItems={job.completedRequests}
                              secondPhaseTotalItems={job.scoringJobCountCache || 0}
                              isFocused={job.id === selectedBatchJob?.id}
                            />
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          </div>
        </div>

        {selectedBatchJob && !isNarrowViewport && !isFullWidth && (
          <div
            className="w-2 relative cursor-col-resize flex-shrink-0 group"
            onMouseDown={handleDragStart}
          >
            <div className="absolute inset-0 rounded-full transition-colors duration-150 
              group-hover:bg-accent" />
          </div>
        )}

        {selectedBatchJob && (
          <div className={`
            flex flex-col flex-1 
            ${isNarrowViewport || isFullWidth ? 'w-full' : ''}
            h-full
          `}
          style={!isNarrowViewport && !isFullWidth ? {
            width: `${100 - leftPanelWidth}%`
          } : undefined}>
            <BatchJobTask
              variant="detail"
              task={{
                id: selectedBatchJob.id,
                type: selectedBatchJob.type,
                scorecard: '',
                score: '',
                time: selectedBatchJob.completedAt || selectedBatchJob.startedAt || new Date().toISOString(),
                summary: `${getProgressPercentage(selectedBatchJob)}% complete`,
                description: selectedBatchJob.errorMessage || undefined,
                data: {
                  id: selectedBatchJob.id,
                  modelProvider: selectedBatchJob.modelProvider,
                  modelName: selectedBatchJob.modelName,
                  type: selectedBatchJob.type,
                  status: selectedBatchJob.status,
                  totalRequests: selectedBatchJob.scoringJobCountCache || 0,
                  completedRequests: selectedBatchJob.completedRequests || 0,
                  failedRequests: selectedBatchJob.failedRequests || 0,
                  startedAt: selectedBatchJob.startedAt || null,
                  estimatedEndAt: selectedBatchJob.estimatedEndAt || null,
                  completedAt: selectedBatchJob.completedAt || null,
                  errorMessage: selectedBatchJob.errorMessage || null,
                  errorDetails: selectedBatchJob.errorDetails as Record<string, unknown> || {},
                  scoringJobs: [],
                  scoringJobCountCache: selectedBatchJob.scoringJobCountCache || 0
                }
              }}
              isFullWidth={isFullWidth}
              onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
              onClose={handleBatchJobClose}
            />
          </div>
        )}
      </div>
    </div>
  )
} 