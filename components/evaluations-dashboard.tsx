"use client"
import React, { useMemo } from "react"
import { useState, useEffect, useRef } from "react"
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

  console.log('Raw Evaluation data:', {
    id: rawEvaluation.id,
    type: rawEvaluation.type,
    accuracy: rawEvaluation.accuracy,
    metrics: rawEvaluation.metrics,
    allFields: Object.keys(rawEvaluation)
  });

  // Create a strongly typed base object with ALL fields
  const safeEvaluation = {
    id: rawEvaluation.id || '',
    type: rawEvaluation.type || '',
    parameters: rawEvaluation.parameters || {},
    metrics: rawEvaluation.metrics || {},
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
    score: async () => ({
      data: rawEvaluation.score ? {
        ...rawEvaluation.score,
        section: async () => ({ data: null }),
        evaluations: async () => ({ data: [], nextToken: null }),
        batchJobs: async () => ({ data: [], nextToken: null })
      } : null
    })
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

export default function EvaluationsDashboard(): JSX.Element {
  const { authStatus, user } = useAuthenticator(context => [context.authStatus]);
  const router = useRouter();

  useEffect(() => {
    if (authStatus === 'unauthenticated') {
      router.push('/');
      return;
    }
  }, [authStatus, router]);

  if (authStatus !== 'authenticated') {
    return <EvaluationDashboardSkeleton />;
  }

  const [Evaluations, setEvaluations] = useState<NonNullable<Schema['Evaluation']['type']>[]>([])
  const [EvaluationTaskProps, setEvaluationTaskProps] = useState<EvaluationTaskProps['task'] | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [selectedEvaluation, setSelectedEvaluation] = useState<Schema['Evaluation']['type'] | null>(null)
  const selectedEvaluationRef = useRef<Schema['Evaluation']['type'] | null>(null)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [scorecardName, setScorecardName] = useState('Unknown Scorecard')
  const [scorecardNames, setScorecardNames] = useState<Record<string, string>>({})
  const [hasMounted, setHasMounted] = useState(false)
  const isNarrowViewport = useViewportWidth()
  const [scoreResults, setScoreResults] = useState<Schema['ScoreResult']['type'][]>([])

  // Add mounted state check
  useEffect(() => {
    setHasMounted(true);
  }, []);

  // Update ref when selectedEvaluation changes
  useEffect(() => {
    selectedEvaluationRef.current = selectedEvaluation;
  }, [selectedEvaluation]);

  const getEvaluationTaskProps = async (Evaluation: Schema['Evaluation']['type']) => {
    const progress = calculateProgress(Evaluation.processedItems, Evaluation.totalItems);
    
    // Get scorecard name
    const scorecardResult = await Evaluation.scorecard?.();
    const scorecardName = scorecardResult?.data?.name || '';
    
    // Get score name
    const scoreResult = await Evaluation.score?.();
    const scoreName = scoreResult?.data?.name || '';

    // Parse metrics JSON if it exists
    let metrics = [];
    if (Evaluation.metrics) {
        try {
            metrics = typeof Evaluation.metrics === 'string' 
                ? JSON.parse(Evaluation.metrics)
                : Evaluation.metrics;
        } catch (e) {
            console.error('Error parsing metrics:', e);
        }
    }

    // Parse class distributions
    let datasetClassDistribution = null;
    if (Evaluation.datasetClassDistribution) {
        try {
            datasetClassDistribution = typeof Evaluation.datasetClassDistribution === 'string' 
                ? JSON.parse(Evaluation.datasetClassDistribution)
                : Evaluation.datasetClassDistribution;
        } catch (e) {
            console.error('Error parsing dataset class distribution:', e);
        }
    }

    let predictedClassDistribution = null;
    if (Evaluation.predictedClassDistribution) {
        try {
            predictedClassDistribution = typeof Evaluation.predictedClassDistribution === 'string' 
                ? JSON.parse(Evaluation.predictedClassDistribution)
                : Evaluation.predictedClassDistribution;
        } catch (e) {
            console.error('Error parsing predicted class distribution:', e);
        }
    }

    let confusionMatrix = { matrix: [], labels: [] };
    if (Evaluation.confusionMatrix) {
        try {
            confusionMatrix = typeof Evaluation.confusionMatrix === 'string'
                ? JSON.parse(Evaluation.confusionMatrix)
                : Evaluation.confusionMatrix;
        } catch (e) {
            console.error('Error parsing confusion matrix:', e);
        }
    }
    
    return {
        id: Evaluation.id,
        type: Evaluation.type,
        scorecard: scorecardName,
        score: scoreName,
        time: formatDistanceToNow(new Date(Evaluation.createdAt), { addSuffix: true }),
        summary: Evaluation.errorMessage || `${progress}% complete`,
        description: Evaluation.errorDetails ? 
            typeof Evaluation.errorDetails === 'string' ? 
                Evaluation.errorDetails : 
                JSON.stringify(Evaluation.errorDetails) : 
            undefined,
        data: {
            accuracy: Evaluation.accuracy ?? 0,
            metrics: metrics,  // Use the parsed metrics array
            processedItems: Evaluation.processedItems || 0,
            totalItems: Evaluation.totalItems || 0,
            progress,
            inferences: Evaluation.inferences || 0,
            cost: Evaluation.cost ?? null,
            status: Evaluation.status || 'Unknown',
            elapsedSeconds: typeof Evaluation.elapsedSeconds === 'number' ? Evaluation.elapsedSeconds : 0,
            estimatedRemainingSeconds: typeof Evaluation.estimatedRemainingSeconds === 'number' ? 
                Evaluation.estimatedRemainingSeconds : 0,
            startedAt: Evaluation.startedAt || null,
            errorMessage: Evaluation.errorMessage ?? null,
            errorDetails: Evaluation.errorDetails ?? null,
            confusionMatrix,
            scoreGoal: Evaluation.scoreGoal ?? null,
            datasetClassDistribution,
            isDatasetClassDistributionBalanced: Evaluation.isDatasetClassDistributionBalanced ?? null,
            predictedClassDistribution,
            isPredictedClassDistributionBalanced: Evaluation.isPredictedClassDistributionBalanced ?? null,
            metricsExplanation: Evaluation.metricsExplanation,
        },
    };
  }

  // Modify the main subscription handler to be more selective about updates
  useEffect(() => {
    if (!client?.models?.Evaluation) {
      console.error('Client or Evaluation model not initialized')
      return
    }

    let subscription: { unsubscribe: () => void } | null = null

    async function setupRealTimeSync() {
      try {
        const { data: accounts } = await listAccounts()

        if (accounts.length > 0) {
          const foundAccountId = accounts[0].id
          setAccountId(foundAccountId)
          
          // Add error handling for listEvaluations
          try {
            const { data: EvaluationModels } = await listEvaluations(foundAccountId)
            
            const filteredEvaluations = EvaluationModels
              .map(transformEvaluation)
              .sort((a, b) => 
                new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
              )
            
            setEvaluations(filteredEvaluations)
          } catch (error) {
            console.error('Error listing evaluations:', error)
            setEvaluations([])
          }
          
          setIsLoading(false)

          // Update subscription setup with null check
          if (client?.models?.Evaluation) {
            subscription = observeQueryFromModel<Schema['Evaluation']['type']>(
              client.models.Evaluation,
              { accountId: { eq: foundAccountId } }
            ).subscribe({
              next: async ({ items }: { items: Schema['Evaluation']['type'][] }) => {
                try {
                  console.log('Subscription update - Evaluations:', items.map(item => ({
                    id: item.id,
                    type: item.type,
                    accuracy: item.accuracy,
                    processedItems: item.processedItems,
                    totalItems: item.totalItems
                  })))

                  setEvaluations(prevEvaluations => {
                    const updatedEvaluations = [...prevEvaluations]
                    let hasChanges = false

                    items.forEach((newItem: Schema['Evaluation']['type']) => {
                      const index = updatedEvaluations.findIndex(exp => exp.id === newItem.id)
                      if (index === -1) {
                        // New Evaluation - use transform to get full object
                        hasChanges = true
                        updatedEvaluations.push(transformEvaluation(newItem))
                      } else {
                        const existingExp = updatedEvaluations[index]
                        // Only update if relevant fields have changed
                        const relevantFieldsChanged = 
                          existingExp.status !== newItem.status ||
                          existingExp.processedItems !== newItem.processedItems ||
                          existingExp.totalItems !== newItem.totalItems ||
                          existingExp.metrics !== newItem.metrics ||
                          existingExp.errorMessage !== newItem.errorMessage ||
                          existingExp.errorDetails !== newItem.errorDetails ||
                          existingExp.metricsExplanation !== newItem.metricsExplanation ||
                          existingExp.accuracy !== newItem.accuracy ||  // Include accuracy changes
                          existingExp.type !== newItem.type  // Include type changes

                        if (relevantFieldsChanged) {
                          hasChanges = true
                          // Create updated Evaluation preserving existing fields
                          const updatedExp = {
                            ...existingExp,  // Keep all existing fields
                            // Update all fields that can change
                            status: newItem.status ?? existingExp.status,
                            processedItems: newItem.processedItems ?? existingExp.processedItems,
                            totalItems: newItem.totalItems ?? existingExp.totalItems,
                            metrics: newItem.metrics ?? existingExp.metrics,
                            errorMessage: newItem.errorMessage ?? existingExp.errorMessage,
                            errorDetails: newItem.errorDetails ?? existingExp.errorDetails,
                            metricsExplanation: newItem.metricsExplanation ?? existingExp.metricsExplanation,
                            accuracy: newItem.accuracy ?? existingExp.accuracy,  // Update accuracy
                            type: newItem.type ?? existingExp.type  // Update type
                          }
                          updatedEvaluations[index] = transformEvaluation(updatedExp)
                        }
                      }
                    })

                    return hasChanges ? 
                      updatedEvaluations.sort((a, b) => 
                        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
                      ) : 
                      prevEvaluations
                  })

                  // Update selected Evaluation if needed
                  if (selectedEvaluationRef.current) {
                    const updatedItem = items.find(item => item.id === selectedEvaluationRef.current?.id)
                    if (updatedItem) {
                      const relevantFieldsChanged = 
                        selectedEvaluationRef.current.status !== updatedItem.status ||
                        selectedEvaluationRef.current.processedItems !== updatedItem.processedItems ||
                        selectedEvaluationRef.current.totalItems !== updatedItem.totalItems ||
                        selectedEvaluationRef.current.metrics !== updatedItem.metrics ||
                        selectedEvaluationRef.current.errorMessage !== updatedItem.errorMessage ||
                        selectedEvaluationRef.current.errorDetails !== updatedItem.errorDetails ||
                        selectedEvaluationRef.current.metricsExplanation !== updatedItem.metricsExplanation ||
                        selectedEvaluationRef.current.accuracy !== updatedItem.accuracy ||  // Include accuracy changes
                        selectedEvaluationRef.current.type !== updatedItem.type  // Include type changes

                      if (relevantFieldsChanged) {
                        const transformed = transformEvaluation({
                          ...selectedEvaluationRef.current,
                          ...updatedItem,
                          // Explicitly update all fields that can change
                          status: updatedItem.status ?? selectedEvaluationRef.current.status,
                          processedItems: updatedItem.processedItems ?? selectedEvaluationRef.current.processedItems,
                          totalItems: updatedItem.totalItems ?? selectedEvaluationRef.current.totalItems,
                          metrics: updatedItem.metrics ?? selectedEvaluationRef.current.metrics,
                          errorMessage: updatedItem.errorMessage ?? selectedEvaluationRef.current.errorMessage,
                          errorDetails: updatedItem.errorDetails ?? selectedEvaluationRef.current.errorDetails,
                          metricsExplanation: updatedItem.metricsExplanation ?? selectedEvaluationRef.current.metricsExplanation,
                          accuracy: updatedItem.accuracy ?? selectedEvaluationRef.current.accuracy,
                          type: updatedItem.type ?? selectedEvaluationRef.current.type
                        })
                        setSelectedEvaluation(transformed)
                      }
                    }
                  }
                } catch (error) {
                  console.error('Error in subscription handler:', error)
                }
              },
              error: (error: Error) => {
                console.error('Subscription error:', error)
                setError(error)
              }
            })
          }
        } else {
          setIsLoading(false)
        }
      } catch (error) {
        console.error('Error in setupRealTimeSync:', error)
        setIsLoading(false)
        setError(error instanceof Error ? error : new Error('Unknown error occurred'))
      }
    }

    setupRealTimeSync()

    return () => {
      if (subscription) {
        subscription.unsubscribe()
      }
    }
  }, [client])

  // Update the fetchScorecardNames function
  useEffect(() => {
    const fetchScorecardNames = async () => {
      
      const newScorecardNames: Record<string, string> = {};
      
      if (!Evaluations || Evaluations.length === 0) {
        setScorecardNames({});
        return;
      }

      try {
        // Process Evaluations sequentially instead of in parallel
        for (const Evaluation of Evaluations) {
          if (!Evaluation?.id) continue;
          
          try {
            if (Evaluation.scorecard) {
              const result = await Evaluation.scorecard();
              newScorecardNames[Evaluation.id] = result?.data?.name || 'Unknown Scorecard';
            } else {
              newScorecardNames[Evaluation.id] = 'Unknown Scorecard';
            }
          } catch (error) {
            console.error(`Error fetching scorecard name for Evaluation ${Evaluation.id}:`, error);
            newScorecardNames[Evaluation.id] = 'Unknown Scorecard';
          }
        }

        setScorecardNames(newScorecardNames);
      } catch (error) {
        console.error('Error in fetchScorecardNames:', error);
        // Set default names for all Evaluations on error
        const defaultNames = Evaluations.reduce((acc, exp) => {
          if (exp?.id) {
            acc[exp.id] = 'Unknown Scorecard';
          }
          return acc;
        }, {} as Record<string, string>);
        setScorecardNames(defaultNames);
      }
    };

    fetchScorecardNames();
  }, [Evaluations]);

  // Update the score results subscription effect
  useEffect(() => {
    if (!selectedEvaluation?.id) return
    
    let isMounted = true
    console.log('Starting score results subscription for Evaluation:', selectedEvaluation.id)
    
    const subscription = observeScoreResults(client, selectedEvaluation.id).subscribe({
      next: ({ items, isSynced }: { items: Schema['ScoreResult']['type'][], isSynced: boolean }) => {
        console.log('Score results subscription update')

        if (!isMounted) return

        // Defensive type check and null check
        if (!items || !Array.isArray(items)) {
          console.warn('Invalid items received:', items)
          return
        }

        // Additional defensive filtering
        const validItems = items.filter(item => 
          item != null && 
          typeof item === 'object' &&
          'id' in item &&
          'value' in item
        )

        console.log('Score results subscription update:', {
          count: validItems.length,
          isSynced,
          sampleResult: validItems[0] ? {
            id: validItems[0].id,
            value: validItems[0].value,
            allFields: Object.keys(validItems[0])
          } : null
        })

        // Sort and update all results at once
        const sortedItems = [...validItems].sort((a, b) => 
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        )
        
        setScoreResults(prev => {
          // Merge new items with existing ones
          const merged = [...prev]
          for (const item of sortedItems) {
            const existingIndex = merged.findIndex(existing => existing.id === item.id)
            if (existingIndex === -1) {
              merged.push(item)
            } else {
              merged[existingIndex] = item
            }
          }
          return merged.sort((a, b) => 
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          )
        })
      },
      error: (error: Error) => {
        console.error('Score results subscription error:', error)
      }
    })

    return () => {
      isMounted = false
      subscription.unsubscribe()
    }
  }, [selectedEvaluation?.id])

  // Next, let's optimize the EvaluationTaskProps update to avoid unnecessary re-renders
  useEffect(() => {
    const updateEvaluationTaskProps = async () => {
      if (selectedEvaluation) {
        const props = await getEvaluationTaskProps(selectedEvaluation)
        
        setEvaluationTaskProps(prevProps => {
          // Only update if there are actual changes
          if (!prevProps) return { ...props, data: { ...props.data, scoreResults } }
          
          const hasChanges = 
            prevProps.data.accuracy !== props.data.accuracy ||
            prevProps.data.progress !== props.data.progress ||
            prevProps.data.processedItems !== props.data.processedItems ||
            prevProps.data.totalItems !== props.data.totalItems ||
            scoreResults !== prevProps.data.scoreResults
          
          if (!hasChanges) return prevProps
          
          return {
            ...props,
            data: { ...props.data, scoreResults }
          }
        })
      } else {
        setEvaluationTaskProps(null)
      }
    }

    updateEvaluationTaskProps()
  }, [selectedEvaluation, scoreResults])

  // Move these to the top, before any early returns
  const filteredEvaluations = useMemo(() => {
    return Evaluations.filter(Evaluation => {
      if (!selectedScorecard) return true
      return Evaluation.scorecardId === selectedScorecard
    })
  }, [Evaluations, selectedScorecard])

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
              setScoreResults([])  // Clear score results before setting new Evaluation
              setSelectedEvaluation(Evaluation)
            }} 
            className={`cursor-pointer transition-colors duration-200 
              ${Evaluation.id === selectedEvaluation?.id ? 'bg-muted' : 'hover:bg-muted'}`}
          >
            <TableCell className="font-medium sm:pr-4">
              <div className="block @[630px]:hidden">
                <div className="flex justify-between mb-4">
                  {/* Left column - reduce width to ~40% */}
                  <div className="w-[40%] space-y-0.5">
                    <div className="font-semibold truncate">
                      <span className={Evaluation.id === selectedEvaluation?.id ? 'text-focus' : ''}>
                        {scorecardNames[Evaluation.id] || 'Unknown Scorecard'}
                      </span>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {formatDistanceToNow(new Date(Evaluation.createdAt), { addSuffix: true })}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {Evaluation.type || ''}
                    </div>
                  </div>

                  {/* Right column - increase width to ~55% for progress bars */}
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
              {/* Wide variant - visible at 630px and above */}
              <div className="hidden @[630px]:block">
                <div className="font-semibold">
                  <span className={Evaluation.id === selectedEvaluation?.id ? 'text-focus' : ''}>
                    {scorecardNames[Evaluation.id] || 'Unknown Scorecard'}
                  </span>
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
  ), [filteredEvaluations, selectedEvaluation?.id, scorecardNames])

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

  // Now do the early returns
  if (!hasMounted) {
    return <EvaluationDashboardSkeleton />;
  }

  if (isLoading || !hasMounted) {
    return <EvaluationDashboardSkeleton />;
  }

  if (error) {
    return (
      <div className="p-4 text-red-500">
        Error loading Evaluations: {error.message}
      </div>
    )
  }

  // Rest of the component remains the same...
  return (
    <ClientOnly>
      <div className="h-full flex flex-col">
        <div className={`flex ${isNarrowViewport ? 'flex-col' : isFullWidth ? '' : 'space-x-6'} flex-1 h-full`}>
          <div className={`
            flex flex-col
            ${isFullWidth ? 'hidden' : ''} 
            ${(!selectedEvaluation || isNarrowViewport) ? 'w-full' : 'w-1/2'}
          `}>
            <div className="mb-4">
              <ScorecardContext 
                selectedScorecard={selectedScorecard}
                setSelectedScorecard={setSelectedScorecard}
                selectedScore={selectedScore}
                setSelectedScore={setSelectedScore}
                availableFields={[]}
              />
            </div>
            <div className="flex-1 overflow-auto @container">
              {EvaluationList}
            </div>
          </div>

          {selectedEvaluation && EvaluationTaskProps && !isNarrowViewport && (
            <div className={`${isFullWidth ? 'w-full' : 'w-1/2 min-w-[300px]'} flex flex-col flex-1`}>
              <div className="flex-1 flex flex-col">
                {EvaluationTaskComponent}
              </div>
            </div>
          )}
        </div>
      </div>
    </ClientOnly>
  )
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
