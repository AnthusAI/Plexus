"use client"
import React from "react"
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
    accuracy: rawExperiment.accuracy || null,
    accuracyType: rawExperiment.accuracyType || null,
    sensitivity: rawExperiment.sensitivity || null,
    specificity: rawExperiment.specificity || null,
    precision: rawExperiment.precision || null,
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
        scorecards: async (options?: any) => ({ 
          data: [], 
          nextToken: null 
        }),
        experiments: async (options?: any) => ({ 
          data: [], 
          nextToken: null 
        }),
        batchJobs: async (options?: any) => ({ 
          data: [], 
          nextToken: null 
        }),
        items: async (options?: any) => ({ 
          data: [], 
          nextToken: null 
        }),
        scoringJobs: async (options?: any) => ({ 
          data: [], 
          nextToken: null 
        }),
        scoreResults: async (options?: any) => ({ 
          data: [], 
          nextToken: null 
        }),
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

export const client = generateClient<Schema>()

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
            accuracy: experiment.accuracy ?? null,
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
        },
    };
  }

  // Effect to update experimentTaskProps when selectedExperiment changes
  useEffect(() => {
    const updateExperimentTaskProps = async () => {
      if (selectedExperiment) {
        const props = await getExperimentTaskProps(selectedExperiment)
        setExperimentTaskProps(props)
      } else {
        setExperimentTaskProps(null)
      }
    }

    updateExperimentTaskProps()
  }, [selectedExperiment]) // Only depend on selectedExperiment

  // Move all client usage into useEffect to avoid server/client mismatch
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
            .sort((a: Schema['Experiment']['type'], b: Schema['Experiment']['type']) => 
              new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
            )
          
          setExperiments(filteredExperiments)
          setIsLoading(false)

          // Set up subscription
          subscription = observeQueryFromModel<Schema['Experiment']['type']>(
            client.models.Experiment,
            { accountId: { eq: foundAccountId } }
          ).subscribe({
            next: async ({ items }) => {
              try {

                const transformedItems = await Promise.all(
                  items.map(async (item: Schema['Experiment']['type']) => {
                    // Find existing experiment BEFORE transformation
                    const existingExperiment = experiments.find(exp => exp.id === item.id);
                    
                    // Create merged item preserving the existing values
                    const mergedItem = {
                      ...item,
                      scoreGoal: existingExperiment?.scoreGoal || item.scoreGoal
                    };
                    
                    // Transform and log the result
                    const transformed = transformExperiment(mergedItem);

                    return transformed;
                  })
                );

                // Create a new array with all properties preserved
                const validItems = [...transformedItems]
                  .sort((a, b) => 
                    new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
                  );

                setExperiments(validItems);
                
                // Update selected experiment if needed
                if (selectedExperimentRef.current) {
                  const updatedExperiment = validItems.find(exp => 
                    exp.id === selectedExperimentRef.current?.id
                  );
                  if (updatedExperiment) {
                    setSelectedExperiment(updatedExperiment);
                    const updatedProps = await getExperimentTaskProps(updatedExperiment);
                    setExperimentTaskProps(updatedProps);
                  }
                }
              } catch (error) {
                console.error('Error in subscription handler:', error);
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
        if (error instanceof Error) {
          console.error('Error details:', error)
          setError(error)
        } else {
          setError(new Error('An unexpected error occurred'))
        }
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

  // Ensure consistent initial state
  if (!hasMounted) {
    return <ExperimentDashboardSkeleton />;
  }

  // Early return for loading state
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

  const filteredExperiments = experiments.filter(experiment => {
    if (!selectedScorecard) return true
    return experiment.scorecardId === selectedScorecard
  })

  // Wrap the main content in ClientOnly
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
                              <div className="text-sm text-muted-foreground">{experiment.accuracyType ?? 'Accuracy'}</div>
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
                                accuracy={experiment.accuracy ?? 0}
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
                        {experiment.accuracyType ?? 'Accuracy'}
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
                          accuracy={experiment.accuracy ?? 0}
                          isFocused={experiment.id === selectedExperiment?.id}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>

          {selectedExperiment && experimentTaskProps && !isNarrowViewport && (
            <div className={`${isFullWidth ? 'w-full' : 'w-1/2 min-w-[300px]'} flex flex-col flex-1`}>
              <div className="flex-1 flex flex-col">
                <ExperimentTask
                  variant="detail"
                  task={experimentTaskProps}
                  isFullWidth={isFullWidth}
                  onToggleFullWidth={() => {
                    setIsFullWidth(!isFullWidth);
                  }}
                  onClose={() => {
                    setSelectedExperiment(null);
                    setIsFullWidth(false);
                  }}
                />
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
