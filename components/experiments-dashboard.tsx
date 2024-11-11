"use client"
import React from "react"
import { useState, useEffect, useRef, useMemo } from "react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown } from "lucide-react"
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

// Add this function to transform the raw experiment data
const transformExperiment = (rawExperiment: any): Schema['Experiment']['type'] => {
  return {
    ...rawExperiment,
    account: async () => ({
      data: {
        id: rawExperiment.account?.id,
        name: rawExperiment.account?.name,
        key: rawExperiment.account?.key,
        scorecards: async () => ({ data: [], nextToken: null }),
        experiments: async () => ({ data: [], nextToken: null }),
        batchJobs: async () => ({ data: [], nextToken: null }),
        createdAt: rawExperiment.createdAt,
        updatedAt: rawExperiment.updatedAt,
        description: ''
      }
    }),
    scorecard: async () => ({
      data: rawExperiment.scorecard ? {
        id: rawExperiment.scorecard.id,
        name: rawExperiment.scorecard.name,
        key: rawExperiment.scorecard.key,
        description: rawExperiment.scorecard.description,
      } : null
    }),
    score: async () => ({
      data: rawExperiment.score ? {
        ...rawExperiment.score,
        section: async () => ({ data: null }),
        experiments: async () => ({ data: [], nextToken: null }),
        batchJobs: async () => ({ data: [], nextToken: null })
      } : null
    }),
    samples: async () => ({
      data: rawExperiment.samples || [],
      nextToken: null
    })
  }
}

// Move client initialization into a custom hook
function useAmplifyClient() {
  const [client] = useState(() => {
    if (typeof window === 'undefined') return null; // Return null during SSR
    console.log('Initializing client...');
    const c = generateClient<Schema>();
    console.log('Client initialized:', c);
    return c;
  });
  return client;
}

export default function ExperimentsDashboard() {
  const client = useAmplifyClient();
  const [experiments, setExperiments] = useState<Schema['Experiment']['type'][]>([])
  const [experimentTaskProps, setExperimentTaskProps] = useState<ExperimentTaskProps['task'] | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [selectedExperiment, setSelectedExperiment] = useState<Schema['Experiment']['type'] | null>(null)
  const selectedExperimentRef = useRef<Schema['Experiment']['type'] | null>(null)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const [scorecardName, setScorecardName] = useState('Unknown Scorecard')
  const [scorecardNames, setScorecardNames] = useState<Record<string, string>>({})

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
    
    // Parse confusion matrix from JSON string
    let confusionMatrix;
    if (experiment.confusionMatrix && typeof experiment.confusionMatrix === 'string') {
        try {
            confusionMatrix = JSON.parse(experiment.confusionMatrix);
        } catch (e) {
            console.error('Error parsing confusion matrix:', e);
            confusionMatrix = { matrix: [], labels: [] };
        }
    } else {
        confusionMatrix = { matrix: [], labels: [] };
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
            sensitivity: experiment.sensitivity ?? null,
            specificity: experiment.specificity ?? null,
            precision: experiment.precision ?? null,
            processedItems: experiment.processedItems || 0,
            totalItems: experiment.totalItems || 0,
            progress,
            inferences: experiment.inferences || 0,
            cost: experiment.cost ?? null,
            status: experiment.status || 'Unknown',
            elapsedSeconds: experiment.elapsedSeconds ?? 0,
            estimatedRemainingSeconds: experiment.estimatedRemainingSeconds ?? 0,
            startedAt: experiment.startedAt || null,
            errorMessage: experiment.errorMessage ?? null,
            errorDetails: experiment.errorDetails ?? null,
            confusionMatrix, // Use the parsed confusion matrix
        },
    }
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
    if (!client) return; // Skip if client isn't initialized yet

    let subscription: { unsubscribe: () => void } | null = null

    async function setupRealTimeSync() {
      try {
        console.log('Fetching account...');
        const accountResult = await client!.models.Account.list({
          filter: { key: { eq: ACCOUNT_KEY } }
        });

        if (accountResult.data.length > 0) {
          const foundAccountId = accountResult.data[0].id;
          setAccountId(foundAccountId);
          
          // Update the selection set to include scorecard fields
          const initialExperiments = await client!.models.Experiment.list({
            filter: { accountId: { eq: foundAccountId } },
            selectionSet: [
              'id', 'type', 'parameters', 'metrics', 'inferences', 
              'cost', 'accuracy', 'accuracyType', 'sensitivity', 'specificity', 
              'precision', 'createdAt', 'updatedAt', 'status', 'startedAt', 
              'totalItems', 'processedItems', 'errorMessage', 
              'errorDetails', 'accountId', 'scorecardId', 'scoreId', 'confusionMatrix',
              // Include these fields for the scorecard relationship
              'scorecard.id',
              'scorecard.name',
              'scorecard.key',
              'scorecard.description'
            ]
          });
          
          const filteredExperiments = initialExperiments.data
            .map(transformExperiment)
            .sort((a: Schema['Experiment']['type'], b: Schema['Experiment']['type']) => 
              new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
            );
          
          setExperiments(filteredExperiments);
          setIsLoading(false);

          // Use the same selection set for the subscription
          subscription = client!.models.Experiment.observeQuery({
            filter: { accountId: { eq: foundAccountId } },
            selectionSet: [
              'id', 'type', 'parameters', 'metrics', 'inferences', 
              'cost', 'accuracy', 'accuracyType', 'sensitivity', 'specificity', 
              'precision', 'createdAt', 'updatedAt', 'status', 'startedAt', 
              'totalItems', 'processedItems', 'errorMessage', 
              'errorDetails', 'accountId', 'scorecardId', 'scoreId', 'confusionMatrix',
              // Include these fields for the scorecard relationship
              'scorecard.id',
              'scorecard.name',
              'scorecard.key',
              'scorecard.description'
            ]
          }).subscribe({
            next: async ({ items }) => {
              console.log('Raw subscription update:', items);
              
              // Fetch scorecards for experiments that need them
              const itemsWithScorecard = await Promise.all(items.map(async (item) => {
                if (item.scorecardId && !item.scorecard) {
                  const scorecardResult = await client!.models.Scorecard.get({
                    id: item.scorecardId
                  });
                  return {
                    ...item,
                    scorecard: scorecardResult.data
                  };
                }
                return item;
              }));
              
              const transformedItems = itemsWithScorecard.map(transformExperiment);
              console.log('Transformed items:', transformedItems);
              
              const sortedItems = transformedItems.sort((a, b) => 
                new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
              );
              setExperiments(sortedItems);
              
              const currentSelectedExperiment = selectedExperimentRef.current;
              if (currentSelectedExperiment) {
                const updatedExperiment = sortedItems.find(exp => exp.id === currentSelectedExperiment.id);
                if (updatedExperiment) {
                  setSelectedExperiment(updatedExperiment);
                  const updatedProps = await getExperimentTaskProps(updatedExperiment);
                  setExperimentTaskProps(updatedProps);
                }
              }
            },
            error: (error: Error) => {
              console.error('Subscription error:', error);
              setError(error);
            }
          });
        } else {
          setIsLoading(false);
        }
      } catch (error) {
        if (error instanceof Error) {
          console.error('Error details:', error);
          setError(error);
        } else {
          setError(new Error('An unexpected error occurred'));
        }
        setIsLoading(false);
      }
    }

    setupRealTimeSync();

    return () => {
      if (subscription) {
        subscription.unsubscribe();
      }
    }
  }, [client])

  // Add viewport check effect
  useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640)
    }

    checkViewportWidth()
    window.addEventListener('resize', checkViewportWidth)

    return () => window.removeEventListener('resize', checkViewportWidth)
  }, [])

  // Add debug logging
  useEffect(() => {
    console.log('Client-side experiments:', experiments)
    console.log('Client-side selectedExperiment:', selectedExperiment)
    console.log('Client-side experimentTaskProps:', experimentTaskProps)
  }, [experiments, selectedExperiment, experimentTaskProps])

  // Add server-side logging
  console.log('Server-side render state:', {
    experiments,
    selectedExperiment,
    experimentTaskProps
  })

  useEffect(() => {
    const fetchScorecardNames = async () => {
      const newScorecardNames: Record<string, string> = {}
      
      await Promise.all(experiments.map(async (experiment) => {
        if (experiment.scorecard) {
          try {
            const result = await experiment.scorecard()
            if (result?.data?.name) {
              newScorecardNames[experiment.id] = result.data.name
            }
          } catch (error) {
            console.error('Error fetching scorecard name:', error)
            newScorecardNames[experiment.id] = 'Unknown Scorecard'
          }
        }
      }))
      
      setScorecardNames(newScorecardNames)
    }

    fetchScorecardNames()
  }, [experiments]) // Depend on experiments array

  if (isLoading) {
    return <div>Loading experiments...</div>
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

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div className="flex-shrink-0">
          <ScorecardContext 
            selectedScorecard={selectedScorecard}
            setSelectedScorecard={setSelectedScorecard}
            selectedScore={selectedScore}
            setSelectedScore={setSelectedScore}
            availableFields={[]}
          />
        </div>
      </div>
      <div className="flex-grow flex flex-col overflow-hidden pb-2">
        {selectedExperiment && experimentTaskProps && (isNarrowViewport || isFullWidth) ? (
          <div className="flex-grow overflow-y-auto">
            <ExperimentTask
              variant="detail"
              task={experimentTaskProps}
              isFullWidth={isFullWidth}
              onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
              onClose={() => {
                setSelectedExperiment(null);
                setIsFullWidth(false);
              }}
            />
          </div>
        ) : (
          <div className={`flex ${isNarrowViewport ? 'flex-col' : 'space-x-6'} flex-1 h-full`}>
            <div className={`${isFullWidth ? 'hidden' : 'flex-1'} @container overflow-auto`}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[30%]">Experiment</TableHead>
                    <TableHead className="w-[10%] @[630px]:table-cell hidden">Type</TableHead>
                    <TableHead className="w-[10%] @[630px]:table-cell hidden text-right">Cost</TableHead>
                    <TableHead className="w-[15%] @[630px]:table-cell hidden text-right">Progress</TableHead>
                    <TableHead className="w-[15%] @[630px]:table-cell hidden text-right">Accuracy</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredExperiments.map((experiment) => (
                    <TableRow 
                      key={experiment.id} 
                      onClick={() => setSelectedExperiment(experiment)} 
                      className="cursor-pointer transition-colors duration-200 hover:bg-muted"
                    >
                      <TableCell className="font-medium sm:pr-4">
                        <div className="block @[630px]:hidden">
                          <div className="flex justify-between mb-4">
                            {/* Left column */}
                            <div className="space-y-1">
                              <div className="font-semibold">
                                {scorecardNames[experiment.id] || 'Unknown Scorecard'}
                              </div>
                              <div className="text-sm text-muted-foreground">
                                {formatDistanceToNow(new Date(experiment.createdAt), { addSuffix: true })}
                              </div>
                              <div className="text-sm text-muted-foreground">{experiment.accuracyType ?? 'Accuracy'}</div>
                            </div>

                            {/* Center column */}
                            <div className="space-y-1 ml-4">
                              <div className="text-sm text-muted-foreground">
                                {experiment.totalItems ?? 0} samples
                              </div>
                              <div className="text-sm text-muted-foreground">
                                ${experiment.cost?.toFixed(3) ?? '0.000'}
                              </div>
                            </div>

                            {/* Right column */}
                            <div className="w-[140px] space-y-2">
                              <ExperimentListProgressBar 
                                progress={calculateProgress(experiment.processedItems, experiment.totalItems)}
                                totalSamples={experiment.totalItems ?? 0}
                              />
                              <ExperimentListAccuracyBar 
                                progress={calculateProgress(experiment.processedItems, experiment.totalItems)}
                                accuracy={experiment.accuracy ?? 0}
                              />
                            </div>
                          </div>
                        </div>
                        {/* Wide variant - visible at 630px and above */}
                        <div className="hidden @[630px]:block">
                          <div className="font-semibold">
                            {scorecardNames[experiment.id] || 'Unknown Scorecard'}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {formatDistanceToNow(new Date(experiment.createdAt), { addSuffix: true })}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="hidden @[630px]:table-cell text-sm text-muted-foreground">
                        {experiment.accuracyType ?? 'Accuracy'}
                      </TableCell>
                      <TableCell className="hidden @[630px]:table-cell text-right">
                        ${experiment.cost?.toFixed(3) ?? '0.000'}
                      </TableCell>
                      <TableCell className="hidden @[630px]:table-cell w-[15%] text-right">
                        <ExperimentListProgressBar 
                          progress={calculateProgress(experiment.processedItems, experiment.totalItems)}
                          totalSamples={experiment.totalItems ?? 0}
                        />
                      </TableCell>
                      <TableCell className="hidden @[630px]:table-cell w-[15%]">
                        <ExperimentListAccuracyBar 
                          progress={calculateProgress(experiment.processedItems, experiment.totalItems)}
                          accuracy={experiment.accuracy ?? 0}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {selectedExperiment && experimentTaskProps && !isNarrowViewport && !isFullWidth && (
              <div className={`${isFullWidth ? 'w-full' : 'w-1/2 min-w-[300px]'} flex flex-col flex-1 overflow-y-auto`}>
                <div className="flex-1 flex flex-col">
                  <ExperimentTask
                    variant="detail"
                    task={experimentTaskProps}
                    isFullWidth={isFullWidth}
                    onToggleFullWidth={() => {
                      console.log('Toggle fullwidth clicked');
                      setIsFullWidth(!isFullWidth);
                    }}
                    onClose={() => {
                      console.log('Close clicked');
                      setSelectedExperiment(null);
                      setIsFullWidth(false);
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
