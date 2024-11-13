"use client"
import React from "react"
import { useState, useEffect, useRef, useMemo } from "react"
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

// Update the transformExperiment function to ensure consistent output
const transformExperiment = (rawExperiment: any): Schema['Experiment']['type'] => {
  if (!rawExperiment) {
    throw new Error('Cannot transform null experiment');
  }
  
  // Ensure all required fields exist with default values
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
    ...rawExperiment
  };

  return {
    ...safeExperiment,
    account: async () => ({
      data: {
        id: rawExperiment.account?.id || '',
        name: rawExperiment.account?.name || '',
        key: rawExperiment.account?.key || '',
        scorecards: async () => ({ data: [], nextToken: null }),
        experiments: async () => ({ data: [], nextToken: null }),
        batchJobs: async () => ({ data: [], nextToken: null }),
        createdAt: rawExperiment.createdAt || new Date().toISOString(),
        updatedAt: rawExperiment.updatedAt || new Date().toISOString(),
        description: ''
      }
    }),
    scorecard: async () => ({
      data: rawExperiment.scorecard ? {
        id: rawExperiment.scorecard.id || '',
        name: rawExperiment.scorecard.name || '',
        key: rawExperiment.scorecard.key || '',
        description: rawExperiment.scorecard.description || '',
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
  };
};

// Move client initialization into a custom hook
function useAmplifyClient() {
  const [client] = useState(() => {
    if (typeof window === 'undefined') return null; // Return null during SSR
    const c = generateClient<Schema>();
    return c;
  });
  return client;
}

// 1. Move viewport state to a custom hook with proper SSR handling
function useViewportWidth() {
  const [isNarrowViewport, setIsNarrowViewport] = useState(false);

  useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640);
    };

    checkViewportWidth();
    window.addEventListener('resize', checkViewportWidth);
    return () => window.removeEventListener('resize', checkViewportWidth);
  }, []);

  // Return a default value during SSR
  return typeof window === 'undefined' ? false : isNarrowViewport;
}

// Update the debug function to use console.log instead of console.error
function debugLog(phase: string, data: any) {
  console.log(`[Debug ${phase}]`, {
    type: typeof data,
    isArray: Array.isArray(data),
    length: Array.isArray(data) ? data.length : null,
    keys: typeof data === 'object' ? Object.keys(data) : null,
    data
  });
}

// Update the confusionMatrix interface
interface ConfusionMatrix {
    matrix: number[][];
    labels: string[];
}

export default function ExperimentsDashboard() {
  const client = useAmplifyClient();
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

  // Replace isNarrowViewport state with the hook
  const isNarrowViewport = useViewportWidth();

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
    
    // Parse confusion matrix safely
    let confusionMatrix: ConfusionMatrix = { matrix: [], labels: [] };
    if (experiment.confusionMatrix) {
        if (typeof experiment.confusionMatrix === 'string') {
            try {
                confusionMatrix = JSON.parse(experiment.confusionMatrix);
            } catch (e) {
                console.error('Error parsing confusion matrix:', e);
            }
        } else if (typeof experiment.confusionMatrix === 'object' && 
                   'matrix' in experiment.confusionMatrix && 
                   'labels' in experiment.confusionMatrix) {
            confusionMatrix = experiment.confusionMatrix as ConfusionMatrix;
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
            sensitivity: experiment.sensitivity ?? null,
            specificity: experiment.specificity ?? null,
            precision: experiment.precision ?? null,
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
            confusionMatrix, // Use the safely parsed confusion matrix
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
    if (!client) {
      return;
    }

    let subscription: { unsubscribe: () => void } | null = null

    async function setupRealTimeSync() {
      try {

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
              'elapsedSeconds',
              'estimatedRemainingSeconds',
              // Include these fields for the scorecard relationship
              'scorecard.id',
              'scorecard.name',
              'scorecard.key',
              'scorecard.description'
            ]
          });
          
          const filteredExperiments = initialExperiments.data
            .map(transformExperiment)
            .sort((a, b) => 
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
              'elapsedSeconds',
              'estimatedRemainingSeconds',
              // Include these fields for the scorecard relationship
              'scorecard.id',
              'scorecard.name',
              'scorecard.key',
              'scorecard.description'
            ]
          }).subscribe({
            next: async ({ items }) => {
              try {
                debugLog('Raw Items', items);

                // Fetch scorecards for experiments that need them
                const itemsWithScorecard = await Promise.all(items.map(async (item) => {
                  try {
                    if (item.scorecardId && !item.scorecard) {
                      const scorecardResult = await client!.models.Scorecard.get({
                        id: item.scorecardId
                      });
                      debugLog('Scorecard Result', scorecardResult);
                      return {
                        ...item,
                        scorecard: scorecardResult.data
                      };
                    }
                    return item;
                  } catch (error) {
                    console.error('Error fetching scorecard for item:', item.id, error);
                    return item;
                  }
                }));
                
                debugLog('Items With Scorecard', itemsWithScorecard);
                
                const transformedItems = itemsWithScorecard.map(item => {
                  try {
                    return transformExperiment(item);
                  } catch (error) {
                    console.error('Error transforming item:', item.id, error);
                    return null;
                  }
                }).filter(Boolean);
                
                debugLog('Transformed Items', transformedItems);
                
                const sortedItems = transformedItems
                    .filter((item): item is NonNullable<typeof item> => item !== null)
                    .sort((a, b) => 
                        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
                    );
                
                debugLog('Sorted Items', sortedItems);
                
                const validSortedItems = sortedItems.filter((item): 
                    item is NonNullable<Schema['Experiment']['type']> => item !== null);
                setExperiments(validSortedItems);
                
                const currentSelectedExperiment = selectedExperimentRef.current;
                if (currentSelectedExperiment) {
                  const updatedExperiment = sortedItems.find(exp => 
                    exp && exp.id === currentSelectedExperiment.id
                  );
                  if (updatedExperiment) {
                    debugLog('Updated Experiment', updatedExperiment);
                    setSelectedExperiment(updatedExperiment);
                    const updatedProps = await getExperimentTaskProps(updatedExperiment);
                    debugLog('Updated Props', updatedProps);
                    setExperimentTaskProps(updatedProps);
                  }
                }
              } catch (error) {
                // Keep console.error for actual errors
                console.error('Error in subscription handler:', error);
                if (error instanceof Error) {
                  console.error('Error details:', {
                    message: error.message,
                    stack: error.stack
                  });
                }
              }
            },
            error: (error: Error) => {
              // Keep console.error for actual errors
              console.error('Subscription error:', {
                message: error.message,
                stack: error.stack
              });
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
                              {/* Left column - reduce width to ~40% */}
                              <div className="w-[40%] space-y-0.5">
                                <div className="font-semibold truncate">
                                  {scorecardNames[experiment.id] || 'Unknown Scorecard'}
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
