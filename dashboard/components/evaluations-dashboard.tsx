"use client"
import React, { useMemo, useCallback, useRef } from "react"
import { useState, useEffect } from "react"
import { useInView } from 'react-intersection-observer'
import type { Schema } from "@/amplify/data/resource"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, RectangleVertical, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown, Trash2, MoreHorizontal, Eye, RefreshCw } from "lucide-react"
import { format, formatDistanceToNow, parseISO } from "date-fns"
import { Badge } from "@/components/ui/badge"
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
import { TimeRangeSelector } from "@/components/time-range-selector"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import ReactMarkdown from 'react-markdown'
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import Link from 'next/link'
import { FilterControl, FilterConfig } from "@/components/filter-control"
import { Progress } from "@/components/ui/progress"
import ScorecardContext from "@/components/ScorecardContext"
import { EvaluationDashboardSkeleton } from "@/components/loading-skeleton"
import { ModelListResult, AmplifyListResult, AmplifyGetResult } from '@/types/shared'
import { listFromModel, observeQueryFromModel, getFromModel, observeScoreResults } from "@/utils/amplify-helpers"
import { useAuthenticator } from '@aws-amplify/ui-react'
import { useRouter } from 'next/navigation'
import { Observable } from 'rxjs'
import { client, getClient } from '@/utils/amplify-client'
import type { GraphQLResult, GraphQLSubscription } from '@aws-amplify/api'
import { TaskDispatchButton, evaluationsConfig } from '@/components/task-dispatch'
import { EvaluationCard, EvaluationGrid } from '@/features/evaluations'
import { useEvaluationSubscriptions, useTaskUpdates } from '@/features/evaluations'
import { formatStatus, getBadgeVariant, calculateProgress } from '@/features/evaluations'
import EvaluationTask from '@/components/EvaluationTask'
import { useMediaQuery } from "@/hooks/use-media-query"
import { CardButton } from "@/components/CardButton"
import { GraphQLResult as APIGraphQLResult } from '@aws-amplify/api-graphql'
import type { EvaluationTaskProps } from '@/components/EvaluationTask'
import type { TaskData } from '@/types/evaluation'

const ACCOUNT_KEY = 'call-criteria'

const LIST_ACCOUNTS = `
  query ListAccounts($filter: ModelAccountFilterInput) {
    listAccounts(filter: $filter) {
      items {
        id
        key
      }
    }
  }
`

const LIST_EVALUATIONS = `
  query ListEvaluationByAccountIdAndUpdatedAt(
    $accountId: String!
    $sortDirection: ModelSortDirection
    $limit: Int
  ) {
    listEvaluationByAccountIdAndUpdatedAt(
      accountId: $accountId
      sortDirection: $sortDirection
      limit: $limit
    ) {
      items {
        id
        type
        parameters
        metrics
        metricsExplanation
        inferences
        accuracy
        cost
        createdAt
        updatedAt
        status
        startedAt
        elapsedSeconds
        estimatedRemainingSeconds
        totalItems
        processedItems
        errorMessage
        errorDetails
        accountId
        scorecardId
        scorecard {
          id
          name
        }
        scoreId
        score {
          id
          name
        }
        confusionMatrix
        scoreGoal
        datasetClassDistribution
        isDatasetClassDistributionBalanced
        predictedClassDistribution
        isPredictedClassDistributionBalanced
        taskId
        task {
          id
          type
          status
          target
          command
          description
          dispatchStatus
          metadata
          createdAt
          startedAt
          completedAt
          estimatedCompletionAt
          errorMessage
          errorDetails
          currentStageId
          stages {
            items {
              id
              name
              order
              status
              statusMessage
              startedAt
              completedAt
              estimatedCompletionAt
              processedItems
              totalItems
            }
          }
        }
      }
      nextToken
    }
  }
`

interface GraphQLError {
  message: string;
  path?: string[];
}

interface ListAccountResponse {
  listAccounts: {
    items: Array<{
      id: string;
      key: string;
    }>;
  };
}

interface ListEvaluationResponse {
  listEvaluationByAccountIdAndUpdatedAt: {
    items: Schema['Evaluation']['type'][];
    nextToken: string | null;
  };
}

export default function EvaluationsDashboard() {
  const { user } = useAuthenticator()
  const router = useRouter()
  const [accountId, setAccountId] = useState<string | null>(null)
  const [evaluations, setEvaluations] = useState<Schema['Evaluation']['type'][]>([])
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const isNarrowViewport = useMediaQuery("(max-width: 768px)")
  const { ref, inView } = useInView({
    threshold: 0,
  })

  // Fetch account ID
  useEffect(() => {
    const fetchAccountId = async () => {
      try {
        console.log('Fetching account ID...')
        const client = getClient()
        const accountResponse = await client.graphql<ListAccountResponse>({
          query: LIST_ACCOUNTS,
          variables: {
            filter: { key: { eq: ACCOUNT_KEY } }
          }
        })

        if ('data' in accountResponse && accountResponse.data?.listAccounts?.items?.length) {
          const id = accountResponse.data.listAccounts.items[0].id
          console.log('Found account ID:', id)
          setAccountId(id)
        } else {
          console.warn('No account found with key:', ACCOUNT_KEY)
          setError('No account found')
          setIsLoading(false)
        }
      } catch (error) {
        console.error('Error fetching account:', error)
        setError('Error fetching account')
        setIsLoading(false)
      }
    }
    fetchAccountId()
  }, [])

  // Fetch evaluations
  useEffect(() => {
    if (!accountId) return

    const fetchEvaluations = async () => {
      try {
        console.log('Fetching evaluations for account:', accountId)
        const client = getClient()
        const evaluationsResponse = await client.graphql<ListEvaluationResponse>({
          query: LIST_EVALUATIONS,
          variables: {
            accountId,
            sortDirection: 'DESC',
            limit: 100
          }
        })

        if ('data' in evaluationsResponse) {
          console.log('GraphQL response:', {
            hasData: !!evaluationsResponse.data,
            hasErrors: !!(evaluationsResponse as any).errors,
            errors: (evaluationsResponse as any).errors?.map((e: GraphQLError) => ({
              message: e.message,
              path: e.path
            }))
          })

          if ((evaluationsResponse as any).errors?.length) {
            throw new Error(`GraphQL errors: ${(evaluationsResponse as any).errors.map((e: GraphQLError) => e.message).join(', ')}`)
          }

          if (evaluationsResponse.data) {
            const items = evaluationsResponse.data.listEvaluationByAccountIdAndUpdatedAt.items
            console.log('Found evaluations:', items.length)
            setEvaluations(items)
          }
        }
        setIsLoading(false)
      } catch (error) {
        console.error('Error fetching evaluations:', error)
        setError('Error fetching evaluations')
        setIsLoading(false)
      }
    }

    fetchEvaluations()
  }, [accountId])

  // Subscribe to evaluation updates
  useEvaluationSubscriptions({
    accountId,
    onEvaluationUpdate: (updatedEvaluation) => {
      console.log('Received evaluation update:', updatedEvaluation.id)
      setEvaluations(prev => prev.map(evaluation => 
        evaluation.id === updatedEvaluation.id ? updatedEvaluation : evaluation
      ))
    },
    onEvaluationCreate: (newEvaluation) => {
      console.log('Received new evaluation:', newEvaluation.id)
      setEvaluations(prev => [newEvaluation, ...prev])
    },
    onEvaluationDelete: (evaluationId) => {
      console.log('Received evaluation deletion:', evaluationId)
      setEvaluations(prev => prev.filter(evaluation => evaluation.id !== evaluationId))
    }
  })

  const handleDelete = async (evaluationId: string) => {
    try {
      const currentClient = getClient()
      await currentClient.graphql({
                query: `
          mutation DeleteEvaluation($id: ID!) {
            deleteEvaluation(id: $id) {
              id
            }
          }
        `,
        variables: { id: evaluationId }
      })
      setEvaluations(prev => prev.filter(evaluation => evaluation.id !== evaluationId))
      if (selectedEvaluationId === evaluationId) {
        setSelectedEvaluationId(null)
      }
      return true
            } catch (error) {
      console.error('Error deleting evaluation:', error)
      return false
    }
  }

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.pageX
    const startWidth = leftPanelWidth

    const handleDrag = (e: MouseEvent) => {
      const delta = e.pageX - startX
      const newWidth = Math.min(Math.max(startWidth + (delta / window.innerWidth) * 100, 20), 80)
      setLeftPanelWidth(newWidth)
    }

    const handleDragEnd = () => {
      document.removeEventListener('mousemove', handleDrag)
      document.removeEventListener('mouseup', handleDragEnd)
    }

    document.addEventListener('mousemove', handleDrag)
    document.addEventListener('mouseup', handleDragEnd)
  }

  const renderSelectedTask = () => {
    if (!selectedEvaluationId) return null
    const evaluation = evaluations.find(e => e.id === selectedEvaluationId)
    if (!evaluation) return null

    // Convert task data to the expected format
    const taskData: TaskData | null = evaluation.task ? {
      id: String((evaluation.task as any).id || ''),
      accountId: String((evaluation.task as any).accountId || ''),
      type: String((evaluation.task as any).type || ''),
      status: String((evaluation.task as any).status || ''),
      target: String((evaluation.task as any).target || ''),
      command: String((evaluation.task as any).command || ''),
      description: String((evaluation.task as any).description || ''),
      dispatchStatus: (evaluation.task as any).dispatchStatus,
      metadata: (evaluation.task as any).metadata,
      createdAt: String((evaluation.task as any).createdAt || ''),
      startedAt: (evaluation.task as any).startedAt,
      completedAt: (evaluation.task as any).completedAt,
      estimatedCompletionAt: (evaluation.task as any).estimatedCompletionAt,
      errorMessage: (evaluation.task as any).errorMessage,
      errorDetails: (evaluation.task as any).errorDetails,
      currentStageId: (evaluation.task as any).currentStageId,
      stages: (evaluation.task as any).stages ? {
        items: ((evaluation.task as any).stages.items || []).map((stage: any) => ({
          id: String(stage.id || ''),
          name: String(stage.name || ''),
          order: Number(stage.order || 0),
          status: String(stage.status || ''),
          statusMessage: stage.statusMessage,
          startedAt: stage.startedAt,
          completedAt: stage.completedAt,
          estimatedCompletionAt: stage.estimatedCompletionAt,
          processedItems: Number(stage.processedItems || 0),
          totalItems: Number(stage.totalItems || 0)
        })),
        nextToken: (evaluation.task as any).stages.nextToken
      } : undefined
    } : null

    const task: EvaluationTaskProps['task'] = {
      id: evaluation.id,
      type: evaluation.type || '',
      scorecard: evaluation.scorecard?.name || '-',
      score: evaluation.score?.name || '-',
      time: evaluation.createdAt || '',
      data: {
        id: evaluation.id,
        title: `${evaluation.scorecard?.name || '-'} - ${evaluation.score?.name || '-'}`,
        metrics: typeof evaluation.metrics === 'string' ? JSON.parse(evaluation.metrics) : (evaluation.metrics || []),
        metricsExplanation: evaluation.metricsExplanation || '',
        accuracy: typeof evaluation.accuracy === 'number' ? evaluation.accuracy : null,
        processedItems: Number(evaluation.processedItems || 0),
        totalItems: Number(evaluation.totalItems || 0),
        progress: Number(calculateProgress(evaluation) || 0),
        inferences: Number(evaluation.inferences || 0),
        cost: typeof evaluation.cost === 'number' ? evaluation.cost : null,
        status: evaluation.status || 'PENDING',
        elapsedSeconds: typeof evaluation.elapsedSeconds === 'number' ? evaluation.elapsedSeconds : null,
        estimatedRemainingSeconds: typeof evaluation.estimatedRemainingSeconds === 'number' ? evaluation.estimatedRemainingSeconds : null,
        startedAt: evaluation.startedAt || undefined,
        errorMessage: evaluation.errorMessage || undefined,
        errorDetails: evaluation.errorDetails || undefined,
        confusionMatrix: typeof evaluation.confusionMatrix === 'string' ? JSON.parse(evaluation.confusionMatrix) : evaluation.confusionMatrix,
        scoreGoal: evaluation.scoreGoal ? String(evaluation.scoreGoal) : null,
        datasetClassDistribution: typeof evaluation.datasetClassDistribution === 'string' ? JSON.parse(evaluation.datasetClassDistribution) : evaluation.datasetClassDistribution,
        isDatasetClassDistributionBalanced: Boolean(evaluation.isDatasetClassDistributionBalanced),
        predictedClassDistribution: typeof evaluation.predictedClassDistribution === 'string' ? JSON.parse(evaluation.predictedClassDistribution) : evaluation.predictedClassDistribution,
        predictedClassDistribution: evaluation.predictedClassDistribution ? JSON.parse(evaluation.predictedClassDistribution) : null,
        isPredictedClassDistributionBalanced: Boolean(evaluation.isPredictedClassDistributionBalanced),
        task: taskData
      }
    }

    return (
      <EvaluationTask
        variant="detail"
        task={task}
        controlButtons={
          <DropdownMenu>
            <DropdownMenuTrigger>
              <CardButton
                icon={MoreHorizontal}
                onClick={() => {}}
                aria-label="More options"
              />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleDelete(evaluation.id)}>
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        }
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={() => {
          setSelectedEvaluationId(null)
          setIsFullWidth(false)
        }}
      />
    )
  }

  // Add filtering logic for evaluations based on selected scorecard and score
  const filteredEvaluations = useMemo(() => {
    return evaluations.filter(evaluation => {
      if (!selectedScorecard && !selectedScore) return true;
      if (selectedScorecard && evaluation.scorecard?.name !== selectedScorecard) return false;
      if (selectedScore && evaluation.score?.name !== selectedScore) return false;
      return true;
    });
  }, [evaluations, selectedScorecard, selectedScore]);

  if (isLoading) {
    return (
      <div>
        <div className="mb-4 text-sm text-muted-foreground">
          {error ? `Error: ${error}` : 'Loading evaluations...'}
        </div>
        <EvaluationDashboardSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">Evaluations</h1>
        </div>
        <div className="text-sm text-destructive">Error: {error}</div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full p-1.5">
      <div className="flex justify-between items-start mb-3">
        <ScorecardContext 
          selectedScorecard={selectedScorecard}
          setSelectedScorecard={setSelectedScorecard}
          selectedScore={selectedScore}
          setSelectedScore={setSelectedScore}
        />
        <TaskDispatchButton config={evaluationsConfig} />
      </div>
      
      <div className="flex h-full">
        <div 
          className={`
            ${selectedEvaluationId && !isNarrowViewport && !isFullWidth ? '' : 'w-full'}
            ${selectedEvaluationId && !isNarrowViewport && isFullWidth ? 'hidden' : ''}
            h-full overflow-auto
          `}
          style={selectedEvaluationId && !isNarrowViewport && !isFullWidth ? {
            width: `${leftPanelWidth}%`
          } : undefined}
        >
          {filteredEvaluations.length === 0 ? (
            <div className="text-sm text-muted-foreground">No evaluations found</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredEvaluations.map((evaluation) => (
                <div 
                  key={evaluation.id} 
                  onClick={() => {
                    setSelectedEvaluationId(evaluation.id)
                    if (isNarrowViewport) {
                      setIsFullWidth(true)
                    }
                  }}
                >
                  <EvaluationTask
                    variant="grid"
                    task={{
                      id: evaluation.id,
                      type: evaluation.type,
                      scorecard: evaluation.scorecard?.name || '-',
                      score: evaluation.score?.name || '-',
                      time: evaluation.createdAt,
                      data: {
                        id: evaluation.id,
                        title: `${evaluation.scorecard?.name || '-'} - ${evaluation.score?.name || '-'}`,
                        metrics: evaluation.metrics ? JSON.parse(evaluation.metrics) : [],
                        metricsExplanation: evaluation.metricsExplanation,
                        accuracy: evaluation.accuracy,
                        processedItems: evaluation.processedItems || 0,
                        totalItems: evaluation.totalItems || 0,
                        progress: calculateProgress(evaluation),
                        inferences: evaluation.inferences || 0,
                        cost: evaluation.cost,
                        status: evaluation.status,
                        elapsedSeconds: evaluation.elapsedSeconds,
                        estimatedRemainingSeconds: evaluation.estimatedRemainingSeconds,
                        startedAt: evaluation.startedAt,
                        errorMessage: evaluation.errorMessage,
                        errorDetails: evaluation.errorDetails,
                        confusionMatrix: evaluation.confusionMatrix ? JSON.parse(evaluation.confusionMatrix) : null,
                        scoreGoal: evaluation.scoreGoal,
                        datasetClassDistribution: evaluation.datasetClassDistribution ? JSON.parse(evaluation.datasetClassDistribution) : null,
                        isDatasetClassDistributionBalanced: evaluation.isDatasetClassDistributionBalanced,
                        predictedClassDistribution: evaluation.predictedClassDistribution ? JSON.parse(evaluation.predictedClassDistribution) : null,
                        isPredictedClassDistributionBalanced: evaluation.isPredictedClassDistributionBalanced,
                        task: evaluation.task
                      }
                    }}
                    isSelected={evaluation.id === selectedEvaluationId}
                    onClick={() => {
                      setSelectedEvaluationId(evaluation.id)
                      if (isNarrowViewport) {
                        setIsFullWidth(true)
                      }
                    }}
                    extra={true}
                  />
                </div>
              ))}
              <div ref={ref} />
            </div>
          )}
        </div>

        {selectedEvaluationId && !isNarrowViewport && !isFullWidth && (
          <div
            className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
            onMouseDown={handleDragStart}
          >
            <div className="absolute inset-0 rounded-full transition-colors duration-150 
              group-hover:bg-accent" />
          </div>
        )}

        {selectedEvaluationId && !isNarrowViewport && !isFullWidth && (
          <div 
            className="h-full overflow-hidden"
            style={{ width: `${100 - leftPanelWidth}%` }}
          >
            {renderSelectedTask()}
          </div>
        )}

        {selectedEvaluationId && (isNarrowViewport || isFullWidth) && (
          <div className="fixed inset-0 z-50">
            {renderSelectedTask()}
          </div>
        )}
      </div>
    </div>
  )
}
