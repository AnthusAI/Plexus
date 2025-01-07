"use client"
import React, { useMemo, useCallback, useRef } from "react"
import { useState, useEffect } from "react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, RectangleVertical, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown } from "lucide-react"
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
import type { EvaluationTaskData } from '@/components/EvaluationTask'
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
    scoreIds
  })

  // Load all scorecards and scores in parallel
  const [scorecards, scores] = await Promise.all([
    Promise.all(scorecardIds.map(id => getFromModel<Schema['Scorecard']['type']>(
      client.models.Scorecard, 
      id
    ))),
    Promise.all(scoreIds.map(id => getFromModel<Schema['Score']['type']>(
      client.models.Score,
      id
    )))
  ])

  // Create maps for quick lookups
  const scorecardMap = new Map(
    scorecards.map(result => [result.data?.id, result.data])
  )
  const scoreMap = new Map(
    scores.map(result => [result.data?.id, result.data])
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
    }
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

interface EvaluationMetric {
  name?: string;
  value?: number;
  unit?: string;
  maximum?: number;
  priority?: boolean;
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

// Add sorting helper at the top
const sortByCreatedAt = (evaluations: Schema['Evaluation']['type'][]) => {
  return [...evaluations].sort((a, b) => {
    const aTime = new Date(a.createdAt).getTime();
    const bTime = new Date(b.createdAt).getTime();
    console.log('Comparing dates:', {
      a: { id: a.id, time: a.createdAt, timestamp: aTime },
      b: { id: b.id, time: b.createdAt, timestamp: bTime }
    });
    return bTime - aTime;
  });
};

export default function EvaluationsDashboard(): JSX.Element {
  const { authStatus, user } = useAuthenticator(context => [context.authStatus]);
  const router = useRouter();
  
  // State hooks
  const [Evaluations, setEvaluations] = useState<NonNullable<Schema['Evaluation']['type']>[]>([])
  const [EvaluationTaskProps, setEvaluationTaskProps] = useState<EvaluationTaskProps['task'] | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [selectedEvaluation, setSelectedEvaluation] = useState<Schema['Evaluation']['type'] | null>(null)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [scorecardName, setScorecardName] = useState('Unknown Scorecard')
  const [scorecardNames, setScorecardNames] = useState<Record<string, string>>({})
  const [hasMounted, setHasMounted] = useState(false)
  const [scoreResults, setScoreResults] = useState<Schema['ScoreResult']['type'][]>([])
  const [leftPanelWidth, setLeftPanelWidth] = useState<number>(50)
  const [scoreNames, setScoreNames] = useState<Record<string, string>>({})

  // Ref hooks
  const selectedEvaluationRef = useRef<Schema['Evaluation']['type'] | null>(null)
  const dragStateRef = useRef<DragState>({
    isDragging: false,
    startX: 0,
    startWidth: 50
  })
  const containerRef = useRef<HTMLDivElement>(null)

  // Custom hooks
  const isNarrowViewport = useViewportWidth()

  // Memoized values
  const filteredEvaluations = useMemo(() => {
    return Evaluations.filter(Evaluation => {
      if (!selectedScorecard) return true
      return Evaluation.scorecardId === selectedScorecard
    })
  }, [Evaluations, selectedScorecard])

  // Memoized components
  const EvaluationList = useMemo(() => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[30%]">Evaluation</TableHead>
          <TableHead className="w-[10%] @[630px]:table-cell hidden">Type</TableHead>
          <TableHead className="w-[15%] @[630px]:table-cell hidden text-right">Progress</TableHead>
          <TableHead className="w-[15%] @[630px]:table-cell hidden text-right">Accuracy</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {filteredEvaluations.map((Evaluation) => (
          <TableRow 
            key={Evaluation.id} 
            onClick={() => {
              setScoreResults([])
              setSelectedEvaluation(Evaluation)
            }} 
            className={`cursor-pointer transition-colors duration-200 
              ${Evaluation.id === selectedEvaluation?.id ? 'bg-muted' : 'hover:bg-muted'}`}
          >
            <TableCell className="font-medium">
              <div className="block @[630px]:hidden">
                <div className="flex justify-between">
                  <div className="w-[40%] space-y-0.5">
                    <div className="font-semibold truncate">
                      <span className={Evaluation.id === selectedEvaluation?.id ? 'text-focus' : ''}>
                        {scorecardNames[Evaluation.id] || 'Unknown Scorecard'}
                      </span>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {scoreNames[Evaluation.id] || 'Unknown Score'}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {formatDistanceToNow(new Date(Evaluation.createdAt), { addSuffix: true })}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {Evaluation.type || ''}
                    </div>
                  </div>
                  <div className="w-[55%] space-y-2">
                    <EvaluationListProgressBar 
                      progress={calculateProgress(Evaluation.processedItems, Evaluation.totalItems)}
                      totalSamples={Evaluation.totalItems ?? 0}
                      isFocused={Evaluation.id === selectedEvaluation?.id}
                    />
                    <EvaluationListAccuracyBar 
                      progress={calculateProgress(Evaluation.processedItems, Evaluation.totalItems)}
                      accuracy={Evaluation.accuracy ?? 0}
                      isFocused={Evaluation.id === selectedEvaluation?.id}
                    />
                  </div>
                </div>
              </div>
              <div className="hidden @[630px]:block">
                <div className="font-semibold">
                  <span className={Evaluation.id === selectedEvaluation?.id ? 'text-focus' : ''}>
                    {scorecardNames[Evaluation.id] || 'Unknown Scorecard'}
                  </span>
                </div>
                <div className="text-sm text-muted-foreground">
                  {scoreNames[Evaluation.id] || 'Unknown Score'}
                </div>
                <div className="text-sm text-muted-foreground">
                  {formatDistanceToNow(new Date(Evaluation.createdAt), { addSuffix: true })}
                </div>
              </div>
            </TableCell>
            <TableCell className="hidden @[630px]:table-cell text-sm text-muted-foreground">
              {Evaluation.type || ''}
            </TableCell>
            <TableCell className="hidden @[630px]:table-cell w-[15%] text-right">
              <EvaluationListProgressBar 
                progress={calculateProgress(Evaluation.processedItems, Evaluation.totalItems)}
                totalSamples={Evaluation.totalItems ?? 0}
                isFocused={Evaluation.id === selectedEvaluation?.id}
              />
            </TableCell>
            <TableCell className="hidden @[630px]:table-cell w-[15%]">
              <EvaluationListAccuracyBar 
                progress={calculateProgress(Evaluation.processedItems, Evaluation.totalItems)}
                accuracy={Evaluation.accuracy ?? 0}
                isFocused={Evaluation.id === selectedEvaluation?.id}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  ), [filteredEvaluations, selectedEvaluation?.id, scorecardNames, scoreNames])

  const EvaluationTaskComponent = useMemo(() => {
    if (!selectedEvaluation || !EvaluationTaskProps) return null
    
    return (
      <EvaluationTask
        variant="detail"
        task={EvaluationTaskProps}
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={() => {
          setSelectedEvaluation(null)
          setIsFullWidth(false)
        }}
      />
    )
  }, [selectedEvaluation?.id, EvaluationTaskProps, isFullWidth])

  // Event handlers
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    if (!containerRef.current) return
    
    dragStateRef.current = {
      isDragging: true,
      startX: e.clientX,
      startWidth: leftPanelWidth
    }
  }, [leftPanelWidth])

  const handleDragMove = useCallback((e: MouseEvent) => {
    if (!dragStateRef.current.isDragging || !containerRef.current) return

    const containerWidth = containerRef.current.offsetWidth
    const delta = e.clientX - dragStateRef.current.startX
    const newWidth = Math.max(20, Math.min(80, 
      dragStateRef.current.startWidth + (delta / containerWidth * 100)
    ))
    
    setLeftPanelWidth(newWidth)
  }, [])

  const handleDragEnd = useCallback(() => {
    dragStateRef.current.isDragging = false
  }, [])

  // Effects
  useEffect(() => {
    if (authStatus === 'unauthenticated') {
      router.push('/');
      return;
    }
  }, [authStatus, router]);

  useEffect(() => {
    setHasMounted(true);
  }, []);

  useEffect(() => {
    selectedEvaluationRef.current = selectedEvaluation;

    if (selectedEvaluation) {
      const subscription = observeScoreResults(client, selectedEvaluation.id).subscribe({
        next: (data) => {
          const parsedResults = data.items.map(parseScoreResult)
          setScoreResults(parsedResults)
        },
        error: (error) => {
          console.error('Error observing score results:', error)
        }
      })

      return () => {
        subscription.unsubscribe()
      }
    }
  }, [selectedEvaluation])

  // Add effect to update EvaluationTaskProps when selectedEvaluation changes
  useEffect(() => {
    if (!selectedEvaluation) {
      setEvaluationTaskProps(null);
      return;
    }

    console.log('Selected evaluation data:', {
      id: selectedEvaluation.id,
      rawConfusionMatrix: selectedEvaluation.confusionMatrix,
      confusionMatrixType: typeof selectedEvaluation.confusionMatrix,
      isObject: selectedEvaluation.confusionMatrix && typeof selectedEvaluation.confusionMatrix === 'object',
      hasMatrixProp: selectedEvaluation.confusionMatrix && 
        typeof selectedEvaluation.confusionMatrix === 'object' && 
        'matrix' in selectedEvaluation.confusionMatrix,
      hasLabelsProp: selectedEvaluation.confusionMatrix && 
        typeof selectedEvaluation.confusionMatrix === 'object' && 
        'labels' in selectedEvaluation.confusionMatrix
    });

    const rawMetrics = (() => {
      try {
        if (typeof selectedEvaluation.metrics === 'string') {
          return JSON.parse(selectedEvaluation.metrics);
        }
        if (Array.isArray(selectedEvaluation.metrics)) {
          return selectedEvaluation.metrics;
        }
        return [];
      } catch (e) {
        console.error('Error parsing metrics:', e);
        return [];
      }
    })();

    const metrics = rawMetrics.map((metric: EvaluationMetric) => ({
      name: String(metric?.name || ''),
      value: Number(metric?.value || 0),
      unit: String(metric?.unit || '%'),
      maximum: Number(metric?.maximum || 100),
      priority: Boolean(metric?.priority)
    }));

    const confusionMatrix = (() => {
      try {
        const rawMatrix = typeof selectedEvaluation.confusionMatrix === 'string' 
          ? JSON.parse(selectedEvaluation.confusionMatrix)
          : selectedEvaluation.confusionMatrix;

        if (rawMatrix && typeof rawMatrix === 'object' &&
            Array.isArray(rawMatrix.matrix) && Array.isArray(rawMatrix.labels)) {
          return {
            matrix: rawMatrix.matrix,
            labels: rawMatrix.labels
          };
        }
        return null;
      } catch (e) {
        console.error('Error parsing confusion matrix:', e);
        return null;
      }
    })();

    const datasetClassDistribution = (() => {
      try {
        const rawDist = typeof selectedEvaluation.datasetClassDistribution === 'string' 
          ? JSON.parse(selectedEvaluation.datasetClassDistribution)
          : selectedEvaluation.datasetClassDistribution;

        if (Array.isArray(rawDist)) {
          return rawDist.map(item => ({
            label: String(item?.label || ''),
            count: Number(item?.count || 0)
          }));
        }
        return undefined;
      } catch (e) {
        console.error('Error parsing dataset distribution:', e);
        return undefined;
      }
    })();

    const predictedClassDistribution = (() => {
      try {
        const rawDist = typeof selectedEvaluation.predictedClassDistribution === 'string' 
          ? JSON.parse(selectedEvaluation.predictedClassDistribution)
          : selectedEvaluation.predictedClassDistribution;

        if (Array.isArray(rawDist)) {
          return rawDist.map(item => ({
            label: String(item?.label || ''),
            count: Number(item?.count || 0)
          }));
        }
        return undefined;
      } catch (e) {
        console.error('Error parsing predicted distribution:', e);
        return undefined;
      }
    })();

    const taskProps = {
      id: selectedEvaluation.id,
      type: selectedEvaluation.type,
      scorecard: scorecardNames[selectedEvaluation.id] || 'Unknown Scorecard',
      score: scoreNames[selectedEvaluation.id] || 'Unknown Score',
      time: selectedEvaluation.createdAt,
      data: {
        accuracy: selectedEvaluation.accuracy ?? null,
        metrics,
        metricsExplanation: selectedEvaluation.metricsExplanation ?? null,
        processedItems: selectedEvaluation.processedItems ?? 0,
        totalItems: selectedEvaluation.totalItems ?? 0,
        progress: calculateProgress(selectedEvaluation.processedItems, selectedEvaluation.totalItems),
        inferences: selectedEvaluation.inferences ?? 0,
        cost: selectedEvaluation.cost ?? null,
        status: selectedEvaluation.status || '',
        elapsedSeconds: selectedEvaluation.elapsedSeconds ?? null,
        estimatedRemainingSeconds: selectedEvaluation.estimatedRemainingSeconds ?? null,
        startedAt: selectedEvaluation.startedAt ?? null,
        errorMessage: selectedEvaluation.errorMessage ?? null,
        errorDetails: selectedEvaluation.errorDetails ?? null,
        confusionMatrix,
        scoreGoal: selectedEvaluation.scoreGoal ?? null,
        datasetClassDistribution,
        isDatasetClassDistributionBalanced: selectedEvaluation.isDatasetClassDistributionBalanced ?? null,
        predictedClassDistribution,
        isPredictedClassDistributionBalanced: selectedEvaluation.isPredictedClassDistributionBalanced ?? null,
        scoreResults: scoreResults
      }
    };

    setEvaluationTaskProps(taskProps);
  }, [selectedEvaluation, scorecardNames, scoreNames, scoreResults]);

  // Add initial data loading effect
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

        const { data: evaluations } = await listEvaluations(foundAccountId);
        if (!evaluations) {
          setIsLoading(false);
          return;
        }

        console.log('Raw evaluations from listEvaluations:', evaluations.map(e => ({
          id: e.id,
          createdAt: e.createdAt,
          type: e.type
        })));

        const transformedEvaluations = await loadRelatedData(
          evaluations,
          setScorecardNames,
          setScoreNames
        );

        console.log('Transformed evaluations before sort:', transformedEvaluations.map(e => ({
          id: e.id,
          createdAt: e.createdAt,
          type: e.type
        })));

        const sortedEvaluations = sortByCreatedAt(transformedEvaluations);

        console.log('Transformed evaluations after sort:', sortedEvaluations.map(e => ({
          id: e.id,
          createdAt: e.createdAt,
          type: e.type
        })));

        setEvaluations(sortedEvaluations);
        setIsLoading(false);

        // Set up subscriptions for real-time updates
        const handleEvaluationUpdate = async (data: Schema['Evaluation']['type']) => {
          console.log('Evaluation update received:', {
            id: data.id,
            type: data.type,
            status: data.status,
            processedItems: data.processedItems,
            totalItems: data.totalItems,
            accuracy: data.accuracy,
            createdAt: data.createdAt
          });

          if (!foundAccountId) return;
          
          // For onCreate, we can just add the new evaluation to the list
          const isCreate = !Evaluations.some(e => e.id === data.id);
          if (isCreate) {
            console.log('Handling onCreate for evaluation:', {
              id: data.id,
              createdAt: data.createdAt,
              existingIds: Evaluations.map(e => e.id)
            });

            // Transform the evaluation before setState to avoid async issues
            const transformedEvaluation = await loadRelatedData(
              [data],
              setScorecardNames,
              setScoreNames
            );

            setEvaluations(prev => {
              // Double-check we haven't already added this evaluation
              if (prev.some(e => e.id === data.id)) {
                console.log('Evaluation already exists in list, skipping:', data.id);
                return prev;
              }

              const newList = sortByCreatedAt([transformedEvaluation[0], ...prev]);
              console.log('New evaluation list order:', newList.map(e => ({
                id: e.id,
                createdAt: e.createdAt,
                type: e.type
              })));
              return newList;
            });
          } else {
            // For updates, we'll update the specific evaluation in place
            setEvaluations(prev => {
              const updatedList = prev.map(e => e.id === data.id ? {
                ...e,
                ...data,
                // Preserve the async functions
                account: e.account,
                scorecard: e.scorecard,
                score: e.score
              } : e);

              // Re-sort after update in case createdAt changed
              const sortedList = sortByCreatedAt(updatedList);
              console.log('Updated evaluation list order:', sortedList.map(e => ({
                id: e.id,
                createdAt: e.createdAt,
                type: e.type
              })));

              return sortedList;
            });
          }

          // Update selectedEvaluation if it matches
          if (selectedEvaluation && data.id === selectedEvaluation.id) {
            setSelectedEvaluation(prev => ({
              ...prev!,
              ...data,
              // Preserve the async functions
              account: prev!.account,
              scorecard: prev!.scorecard,
              score: prev!.score
            }));
          }
        };

        const handleError = (error: unknown) => {
          console.error('Subscription error:', error);
          setError(error instanceof Error ? error : new Error(String(error)));
        };

        type EvaluationObservable = Observable<Schema['Evaluation']['type']>;
        
        // Subscribe to create events
        const createSub = (client.models.Evaluation as any).onCreate().subscribe({
          next: handleEvaluationUpdate,
          error: handleError
        });

        // Subscribe to update events
        const updateSub = (client.models.Evaluation as any).onUpdate().subscribe({
          next: handleEvaluationUpdate,
          error: handleError
        });

        return () => {
          createSub.unsubscribe();
          updateSub.unsubscribe();
        };

      } catch (error) {
        console.error('Error loading initial data:', error);
        setError(error instanceof Error ? error : new Error('Failed to load initial data'));
        setIsLoading(false);
      }
    };

    loadInitialData();

    // No cleanup needed here as it's handled in the async function
    return undefined;
  }, [selectedEvaluation]); // Add selectedEvaluation to dependencies since we use it in handleEvaluationUpdate

  // Early return for unauthenticated state
  if (authStatus !== 'authenticated') {
    return <EvaluationDashboardSkeleton />;
  }

  // Early return for loading state
  if (!hasMounted) {
    return <EvaluationDashboardSkeleton />;
  }

  // Early return for error state
  if (error) {
    return (
      <div className="p-4 text-red-500">
        Error loading Evaluations: {error.message}
      </div>
    );
  }

  return (
    <ClientOnly>
      <div className="h-full flex flex-col" ref={containerRef}>
        <div className={`flex ${isNarrowViewport ? 'flex-col' : ''} flex-1 h-full w-full`}>
          <div className={`
            flex flex-col
            ${isFullWidth ? 'hidden' : ''} 
            ${(!selectedEvaluation || !isNarrowViewport) ? 'flex h-full' : 'hidden'}
            ${(!selectedEvaluation || isNarrowViewport) ? 'w-full' : ''}
          `}
          style={!isNarrowViewport && selectedEvaluation ? {
            width: `${leftPanelWidth}%`
          } : undefined}>
            <div className="mb-4 flex-shrink-0">
              <ScorecardContext 
                selectedScorecard={selectedScorecard}
                setSelectedScorecard={setSelectedScorecard}
                selectedScore={selectedScore}
                setSelectedScore={setSelectedScore}
                availableFields={[]}
              />
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto @container">
              {EvaluationList}
            </div>
          </div>

          {selectedEvaluation && !isNarrowViewport && !isFullWidth && (
            <div
              className="w-2 relative cursor-col-resize flex-shrink-0 group"
              onMouseDown={handleDragStart}
            >
              <div className="absolute inset-0 rounded-full transition-colors duration-150 
                group-hover:bg-accent" />
            </div>
          )}

          {selectedEvaluation && EvaluationTaskProps && (
            <div 
              className={`
                flex flex-col flex-1 
                ${isNarrowViewport || isFullWidth ? 'w-full' : ''}
                h-full
              `}
              style={!isNarrowViewport && !isFullWidth ? {
                width: `${100 - leftPanelWidth}%`
              } : undefined}
            >
              {EvaluationTaskComponent}
            </div>
          )}
        </div>
      </div>
    </ClientOnly>
  );
}

// Create a ClientOnly wrapper component
function ClientOnly({ children }: { children: React.ReactNode }) {
  const [hasMounted, setHasMounted] = useState(false);

  useEffect(() => {
    setHasMounted(true);
  }, []);

  if (!hasMounted) {
    return null; // Or a loading skeleton that matches server render
  }

  return <>{children}</>;
}
