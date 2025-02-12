"use client"
import React, { useMemo, useCallback, useRef } from "react"
import { useState, useEffect } from "react"
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
        scoreId
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

const LIST_SCORECARDS = `
  query ListScorecards($filter: ModelScorecardFilterInput) {
    listScorecards(filter: $filter) {
      items {
        id
        name
        sections {
          items {
            id
            scores {
              items {
                id
                name
              }
            }
          }
        }
      }
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

interface ListScorecardResponse {
  listScorecards: {
    items: Array<{
      id: string;
      name: string;
      sections: {
        items: Array<{
          id: string;
          scores: {
            items: Array<{
              id: string;
              name: string;
            }>;
          };
        }>;
      };
    }>;
  };
}

export default function EvaluationsDashboard() {
  const { user } = useAuthenticator()
  const router = useRouter()
  const [accountId, setAccountId] = useState<string | null>(null)
  const [evaluations, setEvaluations] = useState<Schema['Evaluation']['type'][]>([])
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<string | null>(null)
  const [scorecardNames, setScorecardNames] = useState<Record<string, string>>({})
  const [scoreNames, setScoreNames] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  // Fetch scorecard and score names
  useEffect(() => {
    if (!accountId) return

    const fetchNames = async () => {
      try {
        console.log('Fetching scorecard names for account:', accountId)
        const client = getClient()
        const scorecardsResponse = await client.graphql<ListScorecardResponse>({
          query: LIST_SCORECARDS,
          variables: {
            filter: { accountId: { eq: accountId } }
          }
        })
        console.log('Scorecards response:', scorecardsResponse)
        const newScorecardNames: Record<string, string> = {}
        const newScoreNames: Record<string, string> = {}

        const scorecards = scorecardsResponse.data?.listScorecards?.items || []
        for (const scorecard of scorecards) {
          newScorecardNames[scorecard.id] = scorecard.name
          for (const section of scorecard.sections?.items || []) {
            for (const score of section.scores?.items || []) {
              newScoreNames[score.id] = score.name
            }
          }
        }

        console.log('Found scorecard names:', Object.keys(newScorecardNames).length)
        console.log('Found score names:', Object.keys(newScoreNames).length)
        setScorecardNames(newScorecardNames)
        setScoreNames(newScoreNames)
      } catch (error) {
        console.error('Error fetching names:', error)
        setError('Error fetching scorecard names')
      }
    }

    fetchNames()
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
        
      {evaluations.length === 0 ? (
        <div className="text-sm text-muted-foreground">No evaluations found</div>
      ) : (
        <EvaluationGrid
          evaluations={evaluations}
          selectedEvaluationId={selectedEvaluationId}
          scorecardNames={scorecardNames}
          scoreNames={scoreNames}
          onSelect={(evaluation) => setSelectedEvaluationId(evaluation.id)}
          onDelete={handleDelete}
        />
      )}
          </div>
  )
}
