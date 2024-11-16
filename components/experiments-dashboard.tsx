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
import ExperimentTask, { type ExperimentTaskProps } from "@/components/ExperimentTask"
import { ExperimentListProgressBar } from "@/components/ExperimentListProgressBar"
import { ExperimentListAccuracyBar } from "@/components/ExperimentListAccuracyBar"
import { CardButton } from '@/components/CardButton'
import { formatDuration } from '@/utils/format-duration'
import { ExperimentDashboardSkeleton } from "@/components/loading-skeleton"
import { ModelListResult, AmplifyListResult, AmplifyGetResult } from '@/types/shared'
import { listFromModel, observeQueryFromModel, getFromModel } from "@/utils/amplify-helpers"
import type { ExperimentTaskData } from '@/components/ExperimentTask'

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

// Update the transformExperiment function
const transformExperiment = (rawExperiment: any): Schema['Experiment']['type'] => {
  if (!rawExperiment) {
    throw new Error('Cannot transform null experiment')
  }

  // Create a strongly typed base object with ALL fields
  const safeExperiment = {
    id: rawExperiment.id || '',
    type: rawExperiment.type || '',
    parameters: rawExperiment.parameters || {},
    metrics: rawExperiment.metrics || {},
    inferences: rawExperiment.inferences || 0,
    cost: rawExperiment.cost || 0,
    createdAt: rawExperiment.createdAt || new Date().toISOString(),
    updatedAt: rawExperiment.updatedAt || new Date().toISOString(),
    status: rawExperiment.status || '',
    startedAt: rawExperiment.startedAt || null,
    totalItems: rawExperiment.totalItems || 0,
    processedItems: rawExperiment.processedItems || 0,
    errorMessage: rawExperiment.errorMessage || null,
    errorDetails: rawExperiment.errorDetails || null,
    accountId: rawExperiment.accountId || '',
    scorecardId: rawExperiment.scorecardId || null,
    scoreId: rawExperiment.scoreId || null,
    confusionMatrix: rawExperiment.confusionMatrix || null,
    elapsedSeconds: rawExperiment.elapsedSeconds || 0,
    estimatedRemainingSeconds: rawExperiment.estimatedRemainingSeconds || 0,
    scoreGoal: rawExperiment.scoreGoal || null,
    datasetClassDistribution: rawExperiment.datasetClassDistribution || null,
    isDatasetClassDistributionBalanced: rawExperiment.isDatasetClassDistributionBalanced ?? null,
    predictedClassDistribution: rawExperiment.predictedClassDistribution || null,
    isPredictedClassDistributionBalanced: rawExperiment.isPredictedClassDistributionBalanced || null,
    metricsExplanation: rawExperiment.metricsExplanation || null,
    items: async (options?: any) => ({ data: [], nextToken: null }),
    scoreResults: async (options?: any) => ({ data: [], nextToken: null }),
    scoringJobs: async (options?: any) => ({ data: [], nextToken: null })
  };

  return {
    ...safeExperiment,
    account: async () => ({
      data: {
        id: rawExperiment.account?.id || '',
        name: rawExperiment.account?.name || '',
        key: rawExperiment.account?.key || '',
        scorecards: async (options?: any) => ({ data: [], nextToken: null }),
        experiments: async (options?: any) => ({ data: [], nextToken: null }),
        batchJobs: async (options?: any) => ({ data: [], nextToken: null }),
        items: async (options?: any) => ({ data: [], nextToken: null }),
        scoringJobs: async (options?: any) => ({ data: [], nextToken: null }),
        scoreResults: async (options?: any) => ({ data: [], nextToken: null }),
        createdAt: rawExperiment.account?.createdAt || new Date().toISOString(),
        updatedAt: rawExperiment.account?.updatedAt || new Date().toISOString(),
        description: rawExperiment.account?.description || ''
      }
    }),
    scorecard: async () => {
      if (rawExperiment.scorecard?.data) {
        return { data: rawExperiment.scorecard.data }
      }
      if (rawExperiment.scorecardId) {
        const { data: scorecard } = await getFromModel<Schema['Scorecard']['type']>(
          client.models.Scorecard,
          rawExperiment.scorecardId
        )
        return { data: scorecard }
      }
      return { data: null }
    },
    score: async () => ({
      data: rawExperiment.score ? {
        ...rawExperiment.score,
        section: async () => ({ data: null }),
        experiments: async () => ({ data: [], nextToken: null }),
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

async function listExperiments(accountId: string): ModelListResult<Schema['Experiment']['type']> {
  return listFromModel<Schema['Experiment']['type']>(
    client.models.Experiment,
    { accountId: { eq: accountId } }
  )
}

// Add this interface near the top of the file
interface ExperimentParameters {
  scoreType?: string
  dataBalance?: string
  scoreGoal?: string
  [key: string]: any  // Allow other parameters
}

// Update the helper function to handle any type
const getAccuracyFromMetrics = (metrics: any): number => {
  if (!metrics) return 0;
  try {
    const metricsArray = typeof metrics === 'string' 
      ? JSON.parse(metrics) 
      : Array.isArray(metrics) 
        ? metrics 
        : typeof metrics === 'object' 
          ? [metrics] 
          : [];
    const accuracyMetric = metricsArray.find((m: any) => m.name === 'Accuracy');
    return accuracyMetric?.value ?? 0;
  } catch (e) {
    console.error('Error parsing metrics:', e);
    return 0;
  }
};

// Keep the client definition
const client = generateClient<Schema>()

// Add this helper function at the top of the file
function observeScoreResults(client: any, experimentId: string) {
  return client.models.ScoreResult.observeQuery({
    filter: { experimentId: { eq: experimentId } },
    selectionSet: [
      'id',
      'value',
      'confidence',
      'metadata',
      'correct',
      'itemId',
      'accountId',
      'scoringJobId',
      'experimentId',
      'scorecardId'
    ]
  })
}

// Add this type at the top with other interfaces
interface SubscriptionResponse {
  items: Schema['ScoreResult']['type'][]
}

// Add this type to help with the state update
type ExperimentTaskPropsType = ExperimentTaskProps['task']

export default function ExperimentsDashboard(): JSX.Element {
  const [experiments, setExperiments] = useState<NonNullable<Schema['Experiment']['type']>[]>([])
  const [experimentTaskProps, setExperimentTaskProps] = useState<ExperimentTaskProps['task'] | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [selectedExperiment, setSelectedExperiment] = useState<Schema['Experiment']['type'] | null>(null)
  const selectedExperimentRef = useRef<Schema['Experiment']['type'] | null>(null)
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

  // Update ref when selectedExperiment changes
  useEffect(() => {
    selectedExperimentRef.current = selectedExperiment;
  }, [selectedExperiment]);

  const getExperimentTaskProps = async (experiment: Schema['Experiment']['type']) => {
    const progress = calculateProgress(experiment.processedItems, experiment.totalItems);
    
    // Get scorecard name
    const scorecardResult = await experiment.scorecard?.();
    const scorecardName = scorecardResult?.data?.name || '';
    
    // Get score name
    const scoreResult = await experiment.score?.();
    const scoreName = scoreResult?.data?.name || '';

    // Parse metrics JSON if it exists
    let metrics = [];
    if (experiment.metrics) {
        try {
            metrics = typeof experiment.metrics === 'string' 
                ? JSON.parse(experiment.metrics)
                : experiment.metrics;
        } catch (e) {
            console.error('Error parsing metrics:', e);
        }
    }

    // Parse class distributions
    let datasetClassDistribution = null;
    if (experiment.datasetClassDistribution) {
        try {
            datasetClassDistribution = typeof experiment.datasetClassDistribution === 'string' 
                ? JSON.parse(experiment.datasetClassDistribution)
                : experiment.datasetClassDistribution;
        } catch (e) {
            console.error('Error parsing dataset class distribution:', e);
        }
    }

    let predictedClassDistribution = null;
    if (experiment.predictedClassDistribution) {
        try {
            predictedClassDistribution = typeof experiment.predictedClassDistribution === 'string' 
                ? JSON.parse(experiment.predictedClassDistribution)
                : experiment.predictedClassDistribution;
        } catch (e) {
            console.error('Error parsing predicted class distribution:', e);
        }
    }

    let confusionMatrix = { matrix: [], labels: [] };
    if (experiment.confusionMatrix) {
        try {
            confusionMatrix = typeof experiment.confusionMatrix === 'string'
                ? JSON.parse(experiment.confusionMatrix)
                : experiment.confusionMatrix;
        } catch (e) {
            console.error('Error parsing confusion matrix:', e);
        }
    }
    
    return {
        id: experiment.id,
        type: experiment.type,
        scorecard: scorecardName,
        score: scoreName,
        time: formatDistanceToNow(new Date(experiment.createdAt), { addSuffix: true }),
        summary: experiment.errorMessage || `${progress}% complete`,
        description: experiment.errorDetails ? 
            typeof experiment.errorDetails === 'string' ? 
                experiment.errorDetails : 
                JSON.stringify(experiment.errorDetails) : 
            undefined,
        data: {
            accuracy: getAccuracyFromMetrics(experiment.metrics),
            metrics: metrics,  // Use the parsed metrics array
            processedItems: experiment.processedItems || 0,
            totalItems: experiment.totalItems || 0,
            progress,
            inferences: experiment.inferences || 0,
            cost: experiment.cost ?? null,
            status: experiment.status || 'Unknown',
            elapsedSeconds: typeof experiment.elapsedSeconds === 'number' ? experiment.elapsedSeconds : 0,
            estimatedRemainingSeconds: typeof experiment.estimatedRemainingSeconds === 'number' ? 
                experiment.estimatedRemainingSeconds : 0,
            startedAt: experiment.startedAt || null,
            errorMessage: experiment.errorMessage ?? null,
            errorDetails: experiment.errorDetails ?? null,
            confusionMatrix,
            scoreGoal: experiment.scoreGoal ?? null,
            datasetClassDistribution,
            isDatasetClassDistributionBalanced: experiment.isDatasetClassDistributionBalanced ?? null,
            predictedClassDistribution,
            isPredictedClassDistributionBalanced: experiment.isPredictedClassDistributionBalanced ?? null,
            metricsExplanation: experiment.metricsExplanation,
        },
    };
  }

  // Modify the main subscription handler to be more selective about updates
  useEffect(() => {
    if (!client) return

    let subscription: { unsubscribe: () => void } | null = null

    async function setupRealTimeSync() {
      try {
        const { data: accounts } = await listAccounts()

        if (accounts.length > 0) {
          const foundAccountId = accounts[0].id
          setAccountId(foundAccountId)
          
          const { data: experimentModels } = await listExperiments(foundAccountId)
          
          const filteredExperiments = experimentModels
            .map(transformExperiment)
            .sort((a, b) => 
              new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
            )
          
          setExperiments(filteredExperiments)
          setIsLoading(false)

          // Set up subscription with more selective updates
          subscription = observeQueryFromModel<Schema['Experiment']['type']>(
            client.models.Experiment,
            { accountId: { eq: foundAccountId } }
          ).subscribe({
            next: async ({ items }: { items: Schema['Experiment']['type'][] }) => {
              try {
                setExperiments(prevExperiments => {
                  const updatedExperiments = [...prevExperiments]
                  let hasChanges = false

                  items.forEach((newItem: Schema['Experiment']['type']) => {
                    const index = updatedExperiments.findIndex(exp => exp.id === newItem.id)
                    if (index === -1) {
                      // New experiment
                      hasChanges = true
                      updatedExperiments.push(transformExperiment(newItem))
                    } else {
                      const existingExp = updatedExperiments[index]
                      // Only update if relevant fields have changed
                      const relevantFieldsChanged = 
                        existingExp.status !== newItem.status ||
                        existingExp.processedItems !== newItem.processedItems ||
                        existingExp.totalItems !== newItem.totalItems ||
                        existingExp.metrics !== newItem.metrics ||
                        existingExp.errorMessage !== newItem.errorMessage ||
                        existingExp.errorDetails !== newItem.errorDetails

                      if (relevantFieldsChanged) {
                        hasChanges = true
                        updatedExperiments[index] = transformExperiment({
                          ...existingExp,
                          ...newItem,
                          // Preserve fields that might be missing in the update
                          metricsExplanation: newItem.metricsExplanation || existingExp.metricsExplanation,
                          metrics: newItem.metrics || existingExp.metrics,
                          scoreGoal: newItem.scoreGoal || existingExp.scoreGoal,
                        })
                      }
                    }
                  })

                  // Only trigger re-render if we actually made changes
                  return hasChanges ? 
                    updatedExperiments.sort((a, b) => 
                      new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
                    ) : 
                    prevExperiments
                })

                // Update selected experiment if needed
                if (selectedExperimentRef.current) {
                  const updatedItem = items.find((item: Schema['Experiment']['type']) => 
                    item.id === selectedExperimentRef.current?.id
                  )
                  if (updatedItem) {
                    const relevantFieldsChanged = 
                      selectedExperimentRef.current.status !== updatedItem.status ||
                      selectedExperimentRef.current.processedItems !== updatedItem.processedItems ||
                      selectedExperimentRef.current.totalItems !== updatedItem.totalItems ||
                      selectedExperimentRef.current.metrics !== updatedItem.metrics ||
                      selectedExperimentRef.current.errorMessage !== updatedItem.errorMessage ||
                      selectedExperimentRef.current.errorDetails !== updatedItem.errorDetails

                    if (relevantFieldsChanged) {
                      const transformed = transformExperiment({
                        ...selectedExperimentRef.current,
                        ...updatedItem,
                        metricsExplanation: updatedItem.metricsExplanation || 
                          selectedExperimentRef.current.metricsExplanation,
                        metrics: updatedItem.metrics || selectedExperimentRef.current.metrics,
                        scoreGoal: updatedItem.scoreGoal || selectedExperimentRef.current.scoreGoal,
                      })
                      setSelectedExperiment(transformed)
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
        } else {
          setIsLoading(false)
        }
      } catch (error) {
        console.error('Error in setupRealTimeSync:', error)
        setIsLoading(false)
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
      
      if (!experiments || experiments.length === 0) {
        setScorecardNames({});
        return;
      }

      try {
        // Process experiments sequentially instead of in parallel
        for (const experiment of experiments) {
          if (!experiment?.id) continue;
          
          try {
            if (experiment.scorecard) {
              const result = await experiment.scorecard();
              newScorecardNames[experiment.id] = result?.data?.name || 'Unknown Scorecard';
            } else {
              newScorecardNames[experiment.id] = 'Unknown Scorecard';
            }
          } catch (error) {
            console.error(`Error fetching scorecard name for experiment ${experiment.id}:`, error);
            newScorecardNames[experiment.id] = 'Unknown Scorecard';
          }
        }

        setScorecardNames(newScorecardNames);
      } catch (error) {
        console.error('Error in fetchScorecardNames:', error);
        // Set default names for all experiments on error
        const defaultNames = experiments.reduce((acc, exp) => {
          if (exp?.id) {
            acc[exp.id] = 'Unknown Scorecard';
          }
          return acc;
        }, {} as Record<string, string>);
        setScorecardNames(defaultNames);
      }
    };

    fetchScorecardNames();
  }, [experiments]);

  // Update the score results subscription effect
  useEffect(() => {
    if (!selectedExperiment?.id) {
      setScoreResults([])
      return
    }

    console.log('Starting subscription for experiment:', selectedExperiment.id)
    
    // First, get initial results
    const fetchInitialResults = async () => {
      try {
        const response = await client.models.ScoreResult.list({
          filter: { experimentId: { eq: selectedExperiment.id } },
          limit: 1000
        })
        console.log('Initial score results:', response.data.length)
        setScoreResults(response.data.sort((a, b) => 
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        ))
      } catch (error) {
        console.error('Error fetching initial results:', error)
      }
    }
    
    fetchInitialResults()
    
    // Then set up subscription for updates
    const sub = observeScoreResults(client, selectedExperiment.id).subscribe({
      next: ({ items }: { items: Schema['ScoreResult']['type'][] }) => {
        console.log('Subscription update - score results:', items.length)
        setScoreResults(prevResults => {
          const allResults = [...prevResults]
          let hasChanges = false
          
          items.forEach((newItem: Schema['ScoreResult']['type']) => {
            const existingIndex = allResults.findIndex(r => r.id === newItem.id)
            if (existingIndex === -1) {
              hasChanges = true
              allResults.push(newItem)
            } else if (JSON.stringify(allResults[existingIndex]) !== JSON.stringify(newItem)) {
              hasChanges = true
              allResults[existingIndex] = newItem
            }
          })
          
          if (!hasChanges) return prevResults
          
          return allResults.sort((a, b) => 
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          )
        })
      },
      error: (error: Error) => {
        console.error('Subscription error:', error)
      }
    })

    return () => {
      console.log('Cleaning up subscription')
      sub.unsubscribe()
    }
  }, [selectedExperiment?.id])

  // Next, let's optimize the experimentTaskProps update to avoid unnecessary re-renders
  useEffect(() => {
    const updateExperimentTaskProps = async () => {
      if (selectedExperiment) {
        const props = await getExperimentTaskProps(selectedExperiment)
        
        setExperimentTaskProps(prevProps => {
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
        setExperimentTaskProps(null)
      }
    }

    updateExperimentTaskProps()
  }, [selectedExperiment, scoreResults])

  // Move these to the top, before any early returns
  const filteredExperiments = useMemo(() => {
    return experiments.filter(experiment => {
      if (!selectedScorecard) return true
      return experiment.scorecardId === selectedScorecard
    })
  }, [experiments, selectedScorecard])

  const ExperimentList = useMemo(() => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[30%]">Experiment</TableHead>
          <TableHead className="w-[10%] @[630px]:table-cell hidden">Type</TableHead>
          <TableHead className="w-[15%] @[630px]:table-cell hidden text-right">Progress</TableHead>
          <TableHead className="w-[15%] @[630px]:table-cell hidden text-right">Accuracy</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {filteredExperiments.map((experiment) => (
          <TableRow 
            key={experiment.id} 
            onClick={() => setSelectedExperiment(experiment)} 
            className={`cursor-pointer transition-colors duration-200 
              ${experiment.id === selectedExperiment?.id ? 'bg-muted' : 'hover:bg-muted'}`}
          >
            <TableCell className="font-medium sm:pr-4">
              <div className="block @[630px]:hidden">
                <div className="flex justify-between mb-4">
                  {/* Left column - reduce width to ~40% */}
                  <div className="w-[40%] space-y-0.5">
                    <div className="font-semibold truncate">
                      <span className={experiment.id === selectedExperiment?.id ? 'text-focus' : ''}>
                        {scorecardNames[experiment.id] || 'Unknown Scorecard'}
                      </span>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {formatDistanceToNow(new Date(experiment.createdAt), { addSuffix: true })}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {getAccuracyFromMetrics(experiment.metrics) > 0 ? 'Accuracy' : ''}
                    </div>
                  </div>

                  {/* Right column - increase width to ~55% for progress bars */}
                  <div className="w-[55%] space-y-2">
                    <ExperimentListProgressBar 
                      progress={calculateProgress(experiment.processedItems, experiment.totalItems)}
                      totalSamples={experiment.totalItems ?? 0}
                      isFocused={experiment.id === selectedExperiment?.id}
                    />
                    <ExperimentListAccuracyBar 
                      progress={calculateProgress(experiment.processedItems, experiment.totalItems)}
                      accuracy={getAccuracyFromMetrics(experiment.metrics)}
                      isFocused={experiment.id === selectedExperiment?.id}
                    />
                  </div>
                </div>
              </div>
              {/* Wide variant - visible at 630px and above */}
              <div className="hidden @[630px]:block">
                <div className="font-semibold">
                  <span className={experiment.id === selectedExperiment?.id ? 'text-focus' : ''}>
                    {scorecardNames[experiment.id] || 'Unknown Scorecard'}
                  </span>
                </div>
                <div className="text-sm text-muted-foreground">
                  {formatDistanceToNow(new Date(experiment.createdAt), { addSuffix: true })}
                </div>
              </div>
            </TableCell>
            <TableCell className="hidden @[630px]:table-cell text-sm text-muted-foreground">
              {getAccuracyFromMetrics(experiment.metrics) > 0 ? 'Accuracy' : ''}
            </TableCell>
            <TableCell className="hidden @[630px]:table-cell w-[15%] text-right">
              <ExperimentListProgressBar 
                progress={calculateProgress(experiment.processedItems, experiment.totalItems)}
                totalSamples={experiment.totalItems ?? 0}
                isFocused={experiment.id === selectedExperiment?.id}
              />
            </TableCell>
            <TableCell className="hidden @[630px]:table-cell w-[15%]">
              <ExperimentListAccuracyBar 
                progress={calculateProgress(experiment.processedItems, experiment.totalItems)}
                accuracy={getAccuracyFromMetrics(experiment.metrics)}
                isFocused={experiment.id === selectedExperiment?.id}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  ), [filteredExperiments, selectedExperiment?.id, scorecardNames])

  const experimentTaskComponent = useMemo(() => {
    if (!selectedExperiment || !experimentTaskProps) return null
    
    return (
      <ExperimentTask
        variant="detail"
        task={experimentTaskProps}
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={() => {
          setSelectedExperiment(null)
          setIsFullWidth(false)
        }}
      />
    )
  }, [selectedExperiment?.id, experimentTaskProps, isFullWidth])

  // Now do the early returns
  if (!hasMounted) {
    return <ExperimentDashboardSkeleton />;
  }

  if (isLoading || !hasMounted) {
    return <ExperimentDashboardSkeleton />;
  }

  if (error) {
    return (
      <div className="p-4 text-red-500">
        Error loading experiments: {error.message}
      </div>
    )
  }

  // Rest of the component remains the same...
  return (
    <ClientOnly>
      <div className="space-y-4 h-full flex flex-col">
        <div className={`flex ${isNarrowViewport ? 'flex-col' : isFullWidth ? '' : 'space-x-6'} flex-1 h-full`}>
          <div className={`
            flex flex-col
            ${isFullWidth ? 'hidden' : ''} 
            ${(!selectedExperiment || isNarrowViewport) ? 'w-full' : 'w-1/2'}
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
              {ExperimentList}
            </div>
          </div>

          {selectedExperiment && experimentTaskProps && !isNarrowViewport && (
            <div className={`${isFullWidth ? 'w-full' : 'w-1/2 min-w-[300px]'} flex flex-col flex-1`}>
              <div className="flex-1 flex flex-col">
                {experimentTaskComponent}
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
