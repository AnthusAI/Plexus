"use client"
import React, { useMemo, useCallback, useRef } from "react"
import { useState, useEffect } from "react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, RectangleVertical, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown, Trash2, MoreHorizontal, Eye } from "lucide-react"
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
import EvaluationTask, { type EvaluationTaskProps } from "@/components/EvaluationTask"
import { EvaluationListProgressBar } from "@/components/EvaluationListProgressBar"
import { EvaluationListAccuracyBar } from "@/components/EvaluationListAccuracyBar"
import { CardButton } from '@/components/CardButton'
import { formatDuration } from '@/utils/format-duration'
import { EvaluationDashboardSkeleton } from "@/components/loading-skeleton"
import { ModelListResult, AmplifyListResult, AmplifyGetResult } from '@/types/shared'
import { listFromModel, observeQueryFromModel, getFromModel, observeScoreResults } from "@/utils/amplify-helpers"
import { useAuthenticator } from '@aws-amplify/ui-react';
import { useRouter } from 'next/navigation';
import { Observable } from 'rxjs';

const ACCOUNT_KEY = 'call-criteria'

const formatStatus = (status: string) => {
  return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
};

const getBadgeVariant = (status: string) => {
  const formattedStatus = status.toLowerCase();
  if (formattedStatus === 'done') {
    return 'bg-true text-primary-foreground';
  }
  return 'bg-neutral text-primary-foreground';
};

const calculateProgress = (processedItems?: number | null, totalItems?: number | null): number => {
  if (!processedItems || !totalItems || totalItems === 0) return 0;
  return Math.round((processedItems / totalItems) * 100);
};

// Update the transformEvaluation function
const transformEvaluation = (rawEvaluation: any): Schema['Evaluation']['type'] => {
  if (!rawEvaluation) {
    throw new Error('Cannot transform null Evaluation')
  }

  // Create a strongly typed base object with ALL fields
  const safeEvaluation = {
    id: rawEvaluation.id || '',
    type: rawEvaluation.type || '',
    parameters: rawEvaluation.parameters || {},
    metrics: (() => {
      try {
        if (!rawEvaluation.metrics) return []
        if (Array.isArray(rawEvaluation.metrics)) return rawEvaluation.metrics
        if (typeof rawEvaluation.metrics === 'string') {
          const parsed = JSON.parse(rawEvaluation.metrics)
          return Array.isArray(parsed) ? parsed : []
        }
        return []
      } catch (e) {
        console.warn('Error parsing metrics:', e)
        return []
      }
    })(),
    inferences: rawEvaluation.inferences || 0,
    cost: rawEvaluation.cost || 0,
    createdAt: rawEvaluation.createdAt || new Date().toISOString(),
    updatedAt: rawEvaluation.updatedAt || new Date().toISOString(),
    status: rawEvaluation.status || '',
    startedAt: rawEvaluation.startedAt || null,
    totalItems: rawEvaluation.totalItems || 0,
    processedItems: rawEvaluation.processedItems || 0,
    errorMessage: rawEvaluation.errorMessage || null,
    errorDetails: rawEvaluation.errorDetails || null,
    accountId: rawEvaluation.accountId || '',
    scorecardId: rawEvaluation.scorecardId || null,
    scoreId: rawEvaluation.scoreId || null,
    confusionMatrix: rawEvaluation.confusionMatrix || null,
    elapsedSeconds: rawEvaluation.elapsedSeconds || 0,
    estimatedRemainingSeconds: rawEvaluation.estimatedRemainingSeconds || 0,
    scoreGoal: rawEvaluation.scoreGoal || null,
    datasetClassDistribution: rawEvaluation.datasetClassDistribution || null,
    isDatasetClassDistributionBalanced: rawEvaluation.isDatasetClassDistributionBalanced ?? null,
    predictedClassDistribution: rawEvaluation.predictedClassDistribution || null,
    isPredictedClassDistributionBalanced: rawEvaluation.isPredictedClassDistributionBalanced || null,
    metricsExplanation: rawEvaluation.metricsExplanation || null,
    accuracy: typeof rawEvaluation.accuracy === 'number' ? rawEvaluation.accuracy : null,
    items: async (options?: any) => ({ data: [], nextToken: null }),
    scoreResults: async (options?: any) => ({ data: [], nextToken: null }),
    scoringJobs: async (options?: any) => ({ data: [], nextToken: null }),
    resultTests: async (options?: any) => ({ data: [], nextToken: null })
  };

  return {
    ...safeEvaluation,
    account: async () => ({
      data: {
        id: rawEvaluation.account?.id || '',
        name: rawEvaluation.account?.name || '',
        key: rawEvaluation.account?.key || '',
        scorecards: async (options?: any) => ({ data: [], nextToken: null }),
        evaluations: async (options?: any) => ({ data: [], nextToken: null }),
        batchJobs: async (options?: any) => ({ data: [], nextToken: null }),
        items: async (options?: any) => ({ data: [], nextToken: null }),
        scoringJobs: async (options?: any) => ({ data: [], nextToken: null }),
        scoreResults: async (options?: any) => ({ data: [], nextToken: null }),
        actions: async (options?: any) => ({ data: [], nextToken: null }),
        tasks: async (options?: any) => ({ data: [], nextToken: null }),
        createdAt: rawEvaluation.account?.createdAt || new Date().toISOString(),
        updatedAt: rawEvaluation.account?.updatedAt || new Date().toISOString(),
        description: rawEvaluation.account?.description || ''
      }
    }),
    scorecard: async () => {
      if (rawEvaluation.scorecard?.data) {
        return { data: rawEvaluation.scorecard.data }
      }
      if (rawEvaluation.scorecardId) {
        const { data: scorecard } = await getFromModel<Schema['Scorecard']['type']>(
          client.models.Scorecard,
          rawEvaluation.scorecardId
        )
        return { data: scorecard }
      }
      return { data: null }
    },
    score: async () => {
      console.log('Transform - raw score data:', {
        rawScore: rawEvaluation.score,
        scoreId: rawEvaluation.scoreId,
        fullEvaluation: rawEvaluation
      });
      
      // If we have the score data already, use it
      if (rawEvaluation.score?.data) {
        return { data: rawEvaluation.score.data }
      }
      
      // If we have a scoreId, fetch the score
      if (rawEvaluation.scoreId) {
        const { data: score } = await getFromModel<Schema['Score']['type']>(
          client.models.Score,
          rawEvaluation.scoreId
        )
        console.log('Fetched score:', score);
        return { data: score }
      }
      
      return { data: null }
    }
  };
};

// Add missing interfaces
interface ConfusionMatrix {
  matrix: number[][]
  labels: string[]
}

interface EvaluationRowProps {
  evaluation: Schema['Evaluation']['type']
  selectedEvaluationId: string | undefined | null
  scorecardNames: Record<string, string>
  scoreNames: Record<string, string>
  onSelect: (evaluation: Schema['Evaluation']['type']) => void
  onDelete: (evaluationId: string) => Promise<boolean>
}

const EvaluationRow = React.memo(({ 
  evaluation, 
  selectedEvaluationId, 
  scorecardNames, 
  scoreNames,
  onSelect,
  onDelete
}: EvaluationRowProps) => {
  return (
    <TableRow 
      onClick={() => onSelect(evaluation)} 
      className="group cursor-pointer transition-colors duration-200 relative hover:bg-muted"
    >
      <TableCell className="font-medium">
        <div className="block @[630px]:hidden">
          <div className="flex justify-between">
            <div className="w-[40%] space-y-0.5">
              <div className="font-semibold truncate">
                <span className={evaluation.id === selectedEvaluationId ? 'text-focus' : ''}>
                  {scorecardNames[evaluation.id] || 'Unknown Scorecard'}
                </span>
              </div>
              <div className="text-sm text-muted-foreground">
                {scoreNames[evaluation.id] || 'Unknown Score'}
              </div>
              <div className="text-sm text-muted-foreground">
                {formatDistanceToNow(new Date(evaluation.createdAt), { addSuffix: true })}
              </div>
              <div className="text-sm text-muted-foreground">
                {evaluation.type || ''}
              </div>
            </div>
            <div className="w-[55%] space-y-2">
              <EvaluationListProgressBar 
                progress={calculateProgress(evaluation.processedItems, evaluation.totalItems)}
                totalSamples={evaluation.totalItems ?? 0}
                isFocused={evaluation.id === selectedEvaluationId}
              />
              <EvaluationListAccuracyBar 
                progress={calculateProgress(evaluation.processedItems, evaluation.totalItems)}
                accuracy={evaluation.accuracy ?? 0}
                isFocused={evaluation.id === selectedEvaluationId}
              />
            </div>
          </div>
          <div className="mt-2 flex justify-end space-x-2">
            <CardButton 
              icon={Eye}
              onClick={() => onSelect(evaluation)}
            />
            <DropdownMenu>
              <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                <Button 
                  variant="ghost" 
                  size="icon"
                  className="h-8 w-8 p-0"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={async (e) => {
                  e.stopPropagation();
                  if (window.confirm('Are you sure you want to delete this evaluation?')) {
                    await onDelete(evaluation.id);
                  }
                }}>
                  <Trash2 className="h-4 w-4 mr-2" /> Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        <div className="hidden @[630px]:block">
          <div className="font-semibold">
            <span className={evaluation.id === selectedEvaluationId ? 'text-focus' : ''}>
              {scorecardNames[evaluation.id] || 'Unknown Scorecard'}
            </span>
          </div>
          <div className="text-sm text-muted-foreground">
            {scoreNames[evaluation.id] || 'Unknown Score'}
          </div>
          <div className="text-sm text-muted-foreground">
            {formatDistanceToNow(new Date(evaluation.createdAt), { addSuffix: true })}
          </div>
        </div>
      </TableCell>
      <TableCell className="hidden @[630px]:table-cell text-sm text-muted-foreground">
        {evaluation.type || ''}
      </TableCell>
      <TableCell className="hidden @[630px]:table-cell w-[15%] text-right">
        <EvaluationListProgressBar 
          progress={calculateProgress(evaluation.processedItems, evaluation.totalItems)}
          totalSamples={evaluation.totalItems ?? 0}
          isFocused={evaluation.id === selectedEvaluationId}
        />
      </TableCell>
      <TableCell className="hidden @[630px]:table-cell w-[15%]">
        <EvaluationListAccuracyBar 
          progress={calculateProgress(evaluation.processedItems, evaluation.totalItems)}
          accuracy={evaluation.accuracy ?? 0}
          isFocused={evaluation.id === selectedEvaluationId}
        />
      </TableCell>
      <TableCell className="hidden @[630px]:table-cell w-[10%] text-right">
        <div className="flex items-center justify-end space-x-2">
          <CardButton 
            icon={Eye}
            onClick={() => onSelect(evaluation)}
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button 
                variant="ghost" 
                size="icon"
                className="h-8 w-8 p-0"
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={async (e) => {
                e.stopPropagation();
                if (window.confirm('Are you sure you want to delete this evaluation?')) {
                  await onDelete(evaluation.id);
                }
              }}>
                <Trash2 className="h-4 w-4 mr-2" /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </TableCell>
    </TableRow>
  );
});

EvaluationRow.displayName = 'EvaluationRow';

// Add viewport hook
function useViewportWidth() {
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)

  useEffect(() => {
    const checkWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640)
    }
    
    checkWidth()
    window.addEventListener('resize', checkWidth)
    return () => window.removeEventListener('resize', checkWidth)
  }, [])

  return isNarrowViewport
}

// Add these helper functions at the top
async function listAccounts(): ModelListResult<Schema['Account']['type']> {
  return listFromModel<Schema['Account']['type']>(
    client.models.Account,
    { key: { eq: ACCOUNT_KEY } }
  )
}

async function listEvaluations(accountId: string): ModelListResult<Schema['Evaluation']['type']> {
  if (!client?.models?.Evaluation) {
    throw new Error('Evaluation model not found in client')
  }
  
  return listFromModel<Schema['Evaluation']['type']>(
    client.models.Evaluation,
    { accountId: { eq: accountId } }
  )
}

// Add this interface near the top of the file
interface EvaluationParameters {
  scoreType?: string
  dataBalance?: string
  scoreGoal?: string
  [key: string]: any  // Allow other parameters
}

// Keep the client definition
const client = generateClient<Schema>()

// Add this type at the top with other interfaces
interface SubscriptionResponse {
  items: Schema['ScoreResult']['type'][]
}

// Add this type to help with the state update
type EvaluationTaskPropsType = EvaluationTaskProps['task']

interface EvaluationWithResults {
  id: string
  scoreResults: Array<{
    id: string
    value: number
    confidence: number | null
    metadata: any
    correct: boolean | null
    createdAt: string
    itemId: string
    EvaluationId: string
    scorecardId: string
  }>
}

interface EvaluationQueryResponse {
  data: {
    id: string
    scoreResults: Array<{
      id: string
      value: number
      confidence: number | null
      metadata: any
      correct: boolean | null
      createdAt: string
      itemId: string
      EvaluationId: string
      scorecardId: string
    }>
  }
}

// Define the structure of scoreResults
interface ScoreResult {
  id: string
  value: number
  confidence: number | null
  metadata: any
  correct: boolean | null
  createdAt: string
  itemId: string
  EvaluationId: string
  scorecardId: string
}

// Define the structure of the Evaluation with scoreResults
interface EvaluationWithResults {
  id: string
  scoreResults: ScoreResult[]
}

// Add this helper function near the top with other helpers
async function getEvaluationScoreResults(client: any, EvaluationId: string, nextToken?: string) {
  console.log('Fetching score results for Evaluation:', {
    EvaluationId,
    nextToken,
    usingNextToken: !!nextToken
  })

  // Remove sortDirection from initial query
  const params: any = {
    EvaluationId,
    limit: 10000
  }
  
  if (nextToken) {
    params.nextToken = nextToken
  }

  const response = await client.models.ScoreResult.listScoreResultByEvaluationId(params)

  // Sort the results in memory instead
  const sortedData = response.data ? 
    [...response.data].sort((a, b) => 
      new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    ) : []

  return {
    data: sortedData,
    nextToken: response.nextToken
  }
}

// Add this type near other interfaces
interface DragState {
  isDragging: boolean
  startX: number
  startWidth: number
}

// Add this new function near the top with other helper functions
async function loadRelatedData(
  evaluations: Schema['Evaluation']['type'][],
  setScorecardNames: (names: Record<string, string>) => void,
  setScoreNames: (names: Record<string, string>) => void
): Promise<Schema['Evaluation']['type'][]> {
  // Get unique IDs
  const scorecardIds = [...new Set(evaluations
    .filter(e => e.scorecardId)
    .map(e => e.scorecardId as string))]
  const scoreIds = [...new Set(evaluations
    .filter(e => e.scoreId)
    .map(e => e.scoreId as string))]

  console.log('Loading related data:', {
    evaluationCount: evaluations.length,
    scorecardIds,
    scoreIds,
    evaluationsWithoutScoreId: evaluations.filter(e => !e.scoreId).map(e => ({
      id: e.id,
      type: e.type,
      createdAt: e.createdAt
    }))
  })

  // Load all scorecards and scores in parallel with error handling
  const [scorecards, scores] = await Promise.all([
    Promise.all(
      scorecardIds.map(async id => {
        try {
          return await getFromModel<Schema['Scorecard']['type']>(
            client.models.Scorecard, 
            id
          )
        } catch (error) {
          console.error('Error loading scorecard:', { id, error })
          return { data: null }
        }
      })
    ),
    Promise.all(
      scoreIds.map(async id => {
        try {
          console.log('Attempting to load score:', { id })
          const result = await getFromModel<Schema['Score']['type']>(
            client.models.Score,
            id
          )
          if (!result.data) {
            console.warn('Score not found:', { id })
          }
          return result
        } catch (error) {
          console.error('Error loading score:', { id, error })
          return { data: null }
        }
      })
    )
  ])

  // Log score loading results with more detail
  console.log('Score loading results:', scores.map((result, index) => ({
    id: result.data?.id,
    requestedId: scoreIds[index],
    name: result.data?.name,
    success: !!result.data,
    found: result.data !== null && result.data !== undefined
  })))

  // Create maps for quick lookups
  const scorecardMap = new Map(
    scorecards.map(result => [result.data?.id, result.data])
  )
  const scoreMap = new Map(
    scores.map((result, index) => [scoreIds[index], result.data])
  )

  // Create name mappings
  const newScorecardNames: Record<string, string> = {}
  const newScoreNames: Record<string, string> = {}

  evaluations.forEach(evaluation => {
    const scorecard = scorecardMap.get(evaluation.scorecardId || '')
    const score = scoreMap.get(evaluation.scoreId || '')
    if (scorecard) {
      newScorecardNames[evaluation.id] = scorecard.name
    }
    if (score) {
      newScoreNames[evaluation.id] = score.name
    } else if (evaluation.scoreId) {
      console.log('Missing score data for evaluation:', {
        evaluationId: evaluation.id,
        scoreId: evaluation.scoreId,
        type: evaluation.type,
        createdAt: evaluation.createdAt,
        scoreMapKeys: Array.from(scoreMap.keys())
      })
    }
  })

  // Log final name mappings with more detail
  console.log('Final name mappings:', {
    scoreNames: newScoreNames,
    unmappedEvaluations: evaluations
      .filter(e => !newScoreNames[e.id])
      .map(e => ({
        id: e.id,
        scoreId: e.scoreId,
        type: e.type,
        createdAt: e.createdAt,
        scoreFound: e.scoreId ? scoreMap.has(e.scoreId) : false
      }))
  })

  // Update the state with the new names
  setScorecardNames(newScorecardNames)
  setScoreNames(newScoreNames)

  // Transform evaluations with pre-loaded data and explicitly return the result
  return evaluations.map(evaluation => ({
    ...evaluation,
    scorecard: async () => ({
      data: scorecardMap.get(evaluation.scorecardId || '') || null
    }),
    score: async () => ({
      data: scoreMap.get(evaluation.scoreId || '') || null
    })
  }))
}

// Add type for metrics
interface EvaluationMetric {
  name: string
  value: number
  unit?: string
  maximum?: number
  priority: boolean
}

interface ParsedScoreResult {
  id: string
  value: string
  confidence: number | null
  explanation: string | null
  metadata: {
    human_label: string | null
    correct: boolean
    human_explanation?: string | null
    text?: string | null
  }
  itemId: string | null
}

interface ScoreResultMetadata {
  item_id?: number | string
  results?: {
    [key: string]: {
      value?: string | number
      confidence?: number
      explanation?: string
      metadata?: {
        human_label?: string
        correct?: boolean
        human_explanation?: string
        text?: string
      }
    }
  }
}

function parseScoreResult(result: Schema['ScoreResult']['type']): ParsedScoreResult {
  // Handle double-stringified JSON
  const parsedMetadata = (() => {
    try {
      let metadata = result.metadata
      if (typeof metadata === 'string') {
        metadata = JSON.parse(metadata)
        if (typeof metadata === 'string') {
          metadata = JSON.parse(metadata)
        }
      }
      return metadata as ScoreResultMetadata
    } catch (e) {
      console.error('Error parsing metadata:', e)
      return {} as ScoreResultMetadata
    }
  })()

  console.log('Raw score result:', {
    id: result.id,
    metadata: result.metadata,
    parsedMetadata
  })

  const firstResultKey = parsedMetadata?.results ? 
    Object.keys(parsedMetadata.results)[0] : null
  const scoreResult = firstResultKey && parsedMetadata.results ? 
    parsedMetadata.results[firstResultKey] : null

  console.log('Parsed score result:', {
    firstResultKey,
    scoreResult,
    value: scoreResult?.value,
    confidence: scoreResult?.confidence,
    explanation: scoreResult?.explanation,
    metadata: scoreResult?.metadata
  })

  return {
    id: result.id,
    value: String(scoreResult?.value ?? ''),
    confidence: result.confidence ?? scoreResult?.confidence ?? null,
    explanation: scoreResult?.explanation ?? null,
    metadata: {
      human_label: scoreResult?.metadata?.human_label ?? null,
      correct: Boolean(scoreResult?.metadata?.correct),
      human_explanation: scoreResult?.metadata?.human_explanation ?? null,
      text: scoreResult?.metadata?.text ?? null
    },
    itemId: parsedMetadata?.item_id?.toString() ?? null
  }
}

// Handle delete evaluation
const handleDeleteEvaluation = async (client: any, evaluationId: string) => {
  try {
    // First, get all score results for this evaluation
    const scoreResultsResponse = await client.models.ScoreResult.list({
      filter: { evaluationId: { eq: evaluationId } },
      limit: 10000,
      fields: ['id']
    });

    // Delete all score results first
    if (scoreResultsResponse.data && scoreResultsResponse.data.length > 0) {
      console.log(`Deleting ${scoreResultsResponse.data.length} score results for evaluation ${evaluationId}`);
      await Promise.all(
        scoreResultsResponse.data.map((result: { id: string }) => 
          client.models.ScoreResult.delete({ id: result.id })
        )
      );
    }

    // Get and delete all scoring jobs for this evaluation
    const scoringJobsResponse = await client.models.ScoringJob.list({
      filter: { evaluationId: { eq: evaluationId } },
      limit: 10000,
      fields: ['id']
    });

    if (scoringJobsResponse.data && scoringJobsResponse.data.length > 0) {
      console.log(`Deleting ${scoringJobsResponse.data.length} scoring jobs for evaluation ${evaluationId}`);
      await Promise.all(
        scoringJobsResponse.data.map((job: { id: string }) => 
          client.models.ScoringJob.delete({ id: job.id })
        )
      );
    }

    // Then delete the evaluation itself
    await client.models.Evaluation.delete({ id: evaluationId });
    return true;
  } catch (error) {
    console.error('Error deleting evaluation:', error);
    return false;
  }
};

// Add type for confusion matrix
interface ConfusionMatrix {
  matrix: number[][]
  labels: string[]
}

// Add type for class distribution
interface ClassDistribution {
  label: string
  count: number
}

interface TaskProps {
  variant: 'grid' | 'detail'
  task: {
    id: string
    type: string
    scorecard: string
    score: string
    time: string
    summary?: string
    description?: string
    data: {
      id: string
      title: string
      accuracy: number | null
      metrics: {
        name: string
        value: number
        unit: string
        maximum: number
        priority: boolean
      }[]
      metricsExplanation: string | null
      processedItems: number
      totalItems: number
      progress: number
      inferences: number
      cost: number | null
      status: string
      elapsedSeconds: number | null
      estimatedRemainingSeconds: number | null
      startedAt: string | null
      errorMessage?: string
      errorDetails: any | null
      confusionMatrix: ConfusionMatrix | null
      scoreGoal: string | null
      datasetClassDistribution?: ClassDistribution[]
      isDatasetClassDistributionBalanced: boolean | null
      predictedClassDistribution?: ClassDistribution[]
      isPredictedClassDistributionBalanced: boolean | null
      scoreResults: {
        id: string
        value: string
        confidence: number | null
        explanation: string | null
        metadata: {
          human_label: string | null
          correct: boolean
          human_explanation?: string | null
          text?: string | null
        }
        itemId: string
        createdAt: string
        updatedAt: string
      }[]
    }
  }
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  selectedScoreResultId?: string | null
  onSelectScoreResult?: (id: string | null) => void
}

export default function EvaluationsDashboard(): JSX.Element {
  const { user } = useAuthenticator();
  const router = useRouter();
  
  // State hooks
  const [evaluations, setEvaluations] = useState<NonNullable<Schema['Evaluation']['type']>[]>([]);
  const [evaluationTaskProps, setEvaluationTaskProps] = useState<EvaluationTaskProps | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedEvaluation, setSelectedEvaluation] = useState<Schema['Evaluation']['type'] | null>(null);
  const [scorecardNames, setScorecardNames] = useState<Record<string, string>>({});
  const [scoreNames, setScoreNames] = useState<Record<string, string>>({});
  const [scoreResults, setScoreResults] = useState<Schema['ScoreResult']['type'][]>([]);
  const [isFullWidth, setIsFullWidth] = useState(false);
  const [selectedScoreResultId, setSelectedScoreResultId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedEvaluation) {
      setEvaluationTaskProps(null);
      return;
    }

    const scorecardName = selectedEvaluation.scorecardId && scorecardNames[selectedEvaluation.scorecardId] 
      ? scorecardNames[selectedEvaluation.scorecardId] 
      : selectedEvaluation.scorecardId || 'Unknown Scorecard';

    const scoreName = selectedEvaluation.scoreId && scoreNames[selectedEvaluation.scoreId]
      ? scoreNames[selectedEvaluation.scoreId]
      : selectedEvaluation.scoreId || 'Unknown Score';

    const parsedMetrics = Array.isArray(selectedEvaluation.metrics) 
      ? selectedEvaluation.metrics.map((metric: any) => ({
          name: String(metric?.name || ''),
          value: Number(metric?.value || 0),
          unit: String(metric?.unit || '%'),
          maximum: Number(metric?.maximum || 100),
          priority: Boolean(metric?.priority)
        }))
      : [];

    const parsedScoreResults = (scoreResults || []).map((result: any) => ({
      id: String(result?.id || ''),
      value: String(result?.value || ''),
      confidence: result?.confidence !== undefined ? Number(result.confidence) : null,
      explanation: result?.explanation || null,
      metadata: {
        human_label: result?.metadata?.human_label || null,
        correct: Boolean(result?.metadata?.correct),
        human_explanation: result?.metadata?.human_explanation || null,
        text: result?.metadata?.text || null
      },
      itemId: String(result?.itemId || ''),
      createdAt: result?.createdAt || new Date().toISOString(),
      updatedAt: result?.updatedAt || new Date().toISOString()
    }));

    const parsedConfusionMatrix = selectedEvaluation.confusionMatrix 
      ? (typeof selectedEvaluation.confusionMatrix === 'string' 
          ? JSON.parse(selectedEvaluation.confusionMatrix) 
          : selectedEvaluation.confusionMatrix) as ConfusionMatrix
      : null;

    const parsedDatasetClassDistribution = selectedEvaluation.datasetClassDistribution 
      ? (typeof selectedEvaluation.datasetClassDistribution === 'string'
          ? JSON.parse(selectedEvaluation.datasetClassDistribution)
          : selectedEvaluation.datasetClassDistribution) as ClassDistribution[]
      : undefined;

    const parsedPredictedClassDistribution = selectedEvaluation.predictedClassDistribution
      ? (typeof selectedEvaluation.predictedClassDistribution === 'string'
          ? JSON.parse(selectedEvaluation.predictedClassDistribution)
          : selectedEvaluation.predictedClassDistribution) as ClassDistribution[]
      : undefined;

    const taskProps: EvaluationTaskProps = {
      variant: 'detail',
      task: {
        id: selectedEvaluation.id,
        type: selectedEvaluation.type,
        scorecard: scorecardName,
        score: scoreName,
        time: selectedEvaluation.createdAt,
        summary: undefined,
        description: undefined,
        data: {
          id: selectedEvaluation.id,
          title: selectedEvaluation.type,
          accuracy: selectedEvaluation.accuracy !== null ? Number(selectedEvaluation.accuracy) : null,
          metrics: parsedMetrics,
          metricsExplanation: selectedEvaluation.metricsExplanation || null,
          processedItems: Number(selectedEvaluation.processedItems || 0),
          totalItems: Number(selectedEvaluation.totalItems || 0),
          progress: selectedEvaluation.processedItems && selectedEvaluation.totalItems ?
            (Number(selectedEvaluation.processedItems) / Number(selectedEvaluation.totalItems)) * 100 : 0,
          inferences: Number(selectedEvaluation.inferences || 0),
          cost: selectedEvaluation.cost !== null ? Number(selectedEvaluation.cost) : null,
          status: String(selectedEvaluation.status || ''),
          elapsedSeconds: selectedEvaluation.elapsedSeconds !== null ? Number(selectedEvaluation.elapsedSeconds) : null,
          estimatedRemainingSeconds: selectedEvaluation.estimatedRemainingSeconds !== null ? 
            Number(selectedEvaluation.estimatedRemainingSeconds) : null,
          startedAt: selectedEvaluation.startedAt || null,
          errorMessage: selectedEvaluation.errorMessage || undefined,
          errorDetails: selectedEvaluation.errorDetails || null,
          confusionMatrix: parsedConfusionMatrix,
          scoreGoal: selectedEvaluation.scoreGoal || null,
          datasetClassDistribution: parsedDatasetClassDistribution,
          isDatasetClassDistributionBalanced: selectedEvaluation.isDatasetClassDistributionBalanced || null,
          predictedClassDistribution: parsedPredictedClassDistribution,
          isPredictedClassDistributionBalanced: selectedEvaluation.isPredictedClassDistributionBalanced || null,
          scoreResults: parsedScoreResults
        }
      },
      isFullWidth,
      onToggleFullWidth: () => setIsFullWidth(!isFullWidth),
      selectedScoreResultId,
      onSelectScoreResult: setSelectedScoreResultId
    };

    setEvaluationTaskProps(taskProps);
  }, [selectedEvaluation, scorecardNames, scoreNames, scoreResults, isFullWidth, selectedScoreResultId]);

  return (
    <div className="flex flex-col h-full">
      {isLoading ? (
        <EvaluationDashboardSkeleton />
      ) : (
        <div className="flex flex-col h-full">
          {evaluationTaskProps && (
            <EvaluationTask {...evaluationTaskProps} />
          )}
        </div>
      )}
    </div>
  );
}
