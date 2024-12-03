"use client"

import React, { useState, useEffect, useRef, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { dataClient, listFromModel, getFromModel } from '@/utils/data-operations'
import type { Schema } from "@/amplify/data/resource"
import type { ModelListResult, AmplifyGetResult } from "@/types/shared"
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

const ACCOUNT_KEY = 'call-criteria'

async function listAccounts(): Promise<ModelListResult<Schema['Account']['type']>> {
  return listFromModel<Schema['Account']['type']>(
    'Account',
    { key: { eq: ACCOUNT_KEY } }
  )
}

async function listBatchJobs(accountId: string): Promise<ModelListResult<Schema['BatchJob']['type']>> {
  return listFromModel<Schema['BatchJob']['type']>(
    'BatchJob',
    { accountId: { eq: accountId } }
  )
}

interface ScorecardData {
  id: string;
  name: string;
}

interface ScoreData {
  id: string;
  name: string;
}

interface BatchJobType {
  id: string
  type: string
  status: string
  startedAt?: string | null
  estimatedEndAt?: string | null
  completedAt?: string | null
  completedRequests?: number
  failedRequests?: number
  errorMessage?: string
  errorDetails?: any
  accountId: string
  scorecardId?: string
  scoreId?: string
  modelProvider: string
  modelName: string
  scoringJobCountCache?: number
  createdAt: string
  updatedAt: string
  scoringJobs?: any[]
  account?: any
  batchId?: string
}

interface BatchJobWithCount extends BatchJobType {
  scorecard: { id: string; name: string } | null
  score: { id: string; name: string } | null
  scoringJobsCount: number
  scoringJobs: any[]
  account: any
  batchId: string
}

interface BatchJobListResponse {
  data: BatchJobType[];
}

interface ScoringJobListResponse {
  data: Schema['ScoringJob']['type'][];
}

function getProgressPercentage(job: BatchJobWithCount): number {
  if (!job.scoringJobCountCache) return 0
  return Math.round((job.completedRequests || 0) / job.scoringJobCountCache * 100)
}

function getStatusIcon(status: string): JSX.Element {
  switch (status.toUpperCase()) {
    case 'RUNNING':
      return <PlayCircle className="h-4 w-4 text-primary animate-pulse" />
    case 'COMPLETED':
      return <StopCircle className="h-4 w-4 text-success" />
    case 'FAILED':
      return <AlertCircle className="h-4 w-4 text-destructive" />
    default:
      return <Activity className="h-4 w-4 text-muted-foreground" />
  }
}

function formatTimeAgo(dateStr?: string | null): string {
  if (!dateStr) return 'Not started'
  try {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return 'Invalid date'
    return formatDistanceToNow(date, { addSuffix: true })
  } catch (error) {
    console.error('Error formatting date:', error)
    return 'Invalid date'
  }
}

async function getScorecard(id: string): Promise<AmplifyGetResult<Schema['Scorecard']['type']>> {
  if (!dataClient.models.Scorecard) {
    throw new Error('Scorecard model not found in client')
  }
  return dataClient.models.Scorecard.get({ id })
}

async function getScore(id: string): Promise<AmplifyGetResult<Schema['Score']['type']>> {
  if (!dataClient.models.Score) {
    throw new Error('Score model not found in client')
  }
  return dataClient.models.Score.get({ id })
}

const mapBatchJob = async (job: BatchJobType): Promise<BatchJobWithCount> => {
  let scorecardData: ScorecardData | null = null;
  let scoreData: ScoreData | null = null;

  if (job.scorecardId) {
    try {
      const scorecardResult = await getScorecard(job.scorecardId);
      if (scorecardResult?.data) {
        scorecardData = {
          id: scorecardResult.data.id,
          name: scorecardResult.data.name
        };
      }
    } catch (err) {
      console.error('Error fetching scorecard:', err);
    }
  }

  if (job.scoreId) {
    try {
      const scoreResult = await getScore(job.scoreId);
      if (scoreResult?.data) {
        scoreData = {
          id: scoreResult.data.id,
          name: scoreResult.data.name
        };
      }
    } catch (err) {
      console.error('Error fetching score:', err);
    }
  }

  return {
    id: job.id,
    type: job.type,
    status: job.status,
    startedAt: job.startedAt,
    estimatedEndAt: job.estimatedEndAt,
    completedAt: job.completedAt,
    completedRequests: job.completedRequests,
    failedRequests: job.failedRequests,
    errorMessage: job.errorMessage,
    errorDetails: job.errorDetails,
    accountId: job.accountId,
    scorecardId: job.scorecardId,
    scoreId: job.scoreId,
    modelProvider: job.modelProvider,
    modelName: job.modelName,
    scoringJobCountCache: job.scoringJobCountCache,
    createdAt: job.createdAt,
    updatedAt: job.updatedAt,
    scoringJobsCount: job.scoringJobCountCache || 0,
    scorecard: scorecardData,
    score: scoreData
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

async function loadRelatedData(batchJobs: BatchJobType[]): Promise<BatchJobWithCount[]> {
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
    Promise.all(scorecardIds.map(id => getFromModel<Schema['Scorecard']['type']>('Scorecard', id))),
    Promise.all(scoreIds.map(id => getFromModel<Schema['Score']['type']>('Score', id)))
  ])

  console.log('Loaded related data:', {
    scorecards: scorecards.map(s => ({ id: s.data?.id, name: s.data?.name })),
    scores: scores.map(s => ({ id: s.data?.id, name: s.data?.name }))
  });

  const scorecardMap = new Map(
    scorecards.map(result => [result.data?.id, result.data])
  )
  const scoreMap = new Map(
    scores.map(result => [result.data?.id, result.data])
  )

  return batchJobs.map(job => ({
    ...job,
    scorecard: job.scorecardId ? {
      id: job.scorecardId,
      name: scorecardMap.get(job.scorecardId)?.name || 'Unknown Scorecard'
    } : null,
    score: job.scoreId ? {
      id: job.scoreId,
      name: scoreMap.get(job.scoreId)?.name || 'Unknown Score'
    } : null,
    scoringJobsCount: job.scoringJobCountCache || 0,
    scoringJobs: [],
    account: {},
    batchId: job.id
  })) as BatchJobWithCount[]
}

export default function BatchesDashboard() {
  const [batchJobs, setBatchJobs] = useState<BatchJobWithCount[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [selectedBatchJob, setSelectedBatchJob] = useState<BatchJobWithCount | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const isNarrowViewport = useMediaQuery('(max-width: 768px)')
  const [subscription, setSubscription] = useState<{ unsubscribe: () => void } | null>(null)
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
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);

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

    const containerWidth = containerRef.current.offsetWidth
    const deltaX = e.clientX - dragStateRef.current.startX
    const newWidthPercent = (dragStateRef.current.startWidth * 
      containerWidth / 100 + deltaX) / containerWidth * 100

    // Constrain width between 20% and 80%
    const constrainedWidth = Math.min(Math.max(newWidthPercent, 20), 80)
    setLeftPanelWidth(constrainedWidth)
  }, [])

  const handleDragEnd = useCallback(() => {
    dragStateRef.current.isDragging = false
    document.removeEventListener('mousemove', handleDragMove)
    document.removeEventListener('mouseup', handleDragEnd)
  }, [])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (selectedBatchJob && event.key === 'Escape') {
        setSelectedBatchJob(null)
        setIsFullWidth(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedBatchJob])

  const handleActionClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
  }

  useEffect(() => {
    let subscriptions: { unsubscribe: () => void }[] = [];

    const setupRealTimeSync = async () => {
      try {
        const { data: accounts } = await listAccounts();
        if (accounts.length === 0) {
          setIsLoading(false);
          return;
        }

        const foundAccountId = accounts[0].id;
        setAccountId(foundAccountId);

        // Initial data fetch
        const { data: batchJobModels } = await listBatchJobs(foundAccountId);
        
        // Transform the batch jobs and load related data
        const transformedJobs = await loadRelatedData(batchJobModels);
        setBatchJobs(transformedJobs);
        setIsLoading(false);

        console.log('Setting up subscriptions for BatchJobs with filter:', {
          accountId: foundAccountId
        });

        const handleBatchUpdate = (data: any) => {
          console.log('Received batch update:', data);
          // Refresh the full list when we get an update
          listBatchJobs(foundAccountId).then(async result => {
            if (!result.data) return;
            const transformedJobs = await loadRelatedData(result.data);
            setBatchJobs(transformedJobs);
          });
        };

        if (dataClient.models.BatchJob) {
          // Subscribe to onCreate
          const createSub = dataClient.models.BatchJob.onCreate().subscribe({
            next: handleBatchUpdate,
            error: (error: Error) => {
              console.error('onCreate subscription error:', error);
              setError(error);
            }
          });

          // Subscribe to onUpdate
          const updateSub = dataClient.models.BatchJob.onUpdate().subscribe({
            next: handleBatchUpdate,
            error: (error: Error) => {
              console.error('onUpdate subscription error:', error);
              setError(error);
            }
          });

          // Subscribe to onDelete
          const deleteSub = dataClient.models.BatchJob.onDelete().subscribe({
            next: handleBatchUpdate,
            error: (error: Error) => {
              console.error('onDelete subscription error:', error);
              setError(error);
            }
          });

          subscriptions.push(createSub);
          subscriptions.push(updateSub);
          subscriptions.push(deleteSub);

          console.log('Subscriptions setup complete');
        }

      } catch (error) {
        console.error('Error in setupRealTimeSync:', error);
        setIsLoading(false);
        setError(error instanceof Error ? error : new Error('Unknown error'));
      }
    };

    setupRealTimeSync();

    return () => {
      console.log('Cleaning up subscriptions');
      subscriptions.forEach(sub => sub.unsubscribe());
    };
  }, []);

  const handleBatchJobClick = (job: BatchJobWithCount) => {
    setSelectedBatchJob(job)
  }

  const handleBatchJobClose = () => {
    setSelectedBatchJob(null)
    setIsFullWidth(false)
  }

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
            <div className="flex items-center justify-between mb-4">
              <h1 className="text-2xl font-semibold">Batch Jobs</h1>
            </div>
            <div className="space-y-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[50%]">Job</TableHead>
                    <TableHead className="w-[15%] @[630px]:table-cell hidden">Status</TableHead>
                    <TableHead className="w-[35%] @[630px]:table-cell hidden">Progress</TableHead>
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
                        {/* Narrow variant - visible below 630px */}
                        <div className="block @[630px]:hidden">
                          <div className="flex justify-between">
                            <div className="w-[40%] space-y-0.5">
                              <div className="font-semibold truncate">
                                <span className={job.id === selectedBatchJob?.id ? 'text-focus' : ''}>
                                  {job.scorecard?.name || 'Unknown Scorecard'}
                                </span>
                              </div>
                              <div className="text-sm text-muted-foreground">
                                {job.score?.name || 'Unknown Score'}
                              </div>
                              <div className="text-sm text-muted-foreground">
                                {job.type}
                              </div>
                              <div className="text-sm text-muted-foreground">
                                {job.modelProvider} / {job.modelName}
                              </div>
                            </div>
                            <div className="w-[55%] space-y-2">
                              <div className="flex items-center gap-2 justify-end">
                                <Badge 
                                  variant={
                                    job.status === 'COMPLETED' ? 'success' :
                                    job.status === 'FAILED' ? 'destructive' :
                                    'default'
                                  }
                                >
                                  {job.status}
                                </Badge>
                              </div>
                              <ProgressBar 
                                progress={getProgressPercentage(job)}
                                processedItems={job.completedRequests ?? 0}
                                totalItems={job.scoringJobCountCache ?? 0}
                                color="secondary"
                                isFocused={job.id === selectedBatchJob?.id}
                              />
                            </div>
                          </div>
                        </div>

                        {/* Wide variant - visible at 630px and above */}
                        <div className="hidden @[630px]:block">
                          <div className="font-semibold">
                            <span className={job.id === selectedBatchJob?.id ? 'text-focus' : ''}>
                              {job.scorecard?.name || 'Unknown Scorecard'}
                            </span>
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {job.score?.name || 'Unknown Score'}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {job.type}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {job.modelProvider} / {job.modelName}
                          </div>
                        </div>
                      </TableCell>

                      <TableCell className="hidden @[630px]:table-cell w-[15%] text-right">
                        <ProgressBar 
                          progress={getProgressPercentage(job)}
                          processedItems={job.completedRequests ?? 0}
                          totalItems={job.scoringJobCountCache ?? 0}
                          color="secondary"
                          isFocused={job.id === selectedBatchJob?.id}
                        />
                      </TableCell>

                      <TableCell className="hidden @[630px]:table-cell">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(job.status)}
                          <Badge 
                            variant={
                              job.status === 'COMPLETED' ? 'success' :
                              job.status === 'FAILED' ? 'destructive' :
                              'default'
                            }
                          >
                            {job.status}
                          </Badge>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
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
                  type: selectedBatchJob.type,
                  status: selectedBatchJob.status,
                  totalRequests: selectedBatchJob.scoringJobCountCache || 0,
                  completedRequests: selectedBatchJob.completedRequests || 0,
                  failedRequests: selectedBatchJob.failedRequests || 0,
                  startedAt: selectedBatchJob.startedAt || undefined,
                  estimatedEndAt: selectedBatchJob.estimatedEndAt || undefined,
                  completedAt: selectedBatchJob.completedAt || undefined,
                  errorMessage: selectedBatchJob.errorMessage || undefined,
                  errorDetails: selectedBatchJob.errorDetails || undefined,
                  modelProvider: selectedBatchJob.modelProvider,
                  modelName: selectedBatchJob.modelName,
                  scoringJobs: []
                }
              }}
              isFullWidth={isFullWidth}
              onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
              onClose={() => {
                setSelectedBatchJob(null)
                setIsFullWidth(false)
              }}
            />
          </div>
        )}
      </div>
    </div>
  )
} 