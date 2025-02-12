"use client"
import React, { useMemo, useCallback, useRef } from "react"
import { useState, useEffect } from "react"
import { useInView } from 'react-intersection-observer'
import type { Schema } from "@/amplify/data/resource"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, RectangleVertical, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown, Trash2, MoreHorizontal, Eye, Activity, FlaskConical, FlaskRound, TestTubes, RefreshCw } from "lucide-react"
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
        console.log('Account response:', accountResponse)
        if (accountResponse.data?.listAccounts?.items?.length) {
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

        console.log('GraphQL response:', {
          hasData: !!evaluationsResponse.data,
          hasErrors: !!evaluationsResponse.errors,
          errors: evaluationsResponse.errors?.map(e => ({
            message: e.message,
            path: e.path
          }))
        })

        if (evaluationsResponse.errors?.length) {
          throw new Error(`GraphQL errors: ${evaluationsResponse.errors.map(e => e.message).join(', ')}`)
        }

        if (evaluationsResponse.data) {
          const items = evaluationsResponse.data.listEvaluationByAccountIdAndUpdatedAt.items
          console.log('Found evaluations:', items.length)
          setEvaluations(items)
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

    const task: EvaluationTaskProps['task'] = {
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
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Evaluations</h1>
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
          {evaluations.length === 0 ? (
            <div className="text-sm text-muted-foreground">No evaluations found</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {evaluations.map((evaluation) => (
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
