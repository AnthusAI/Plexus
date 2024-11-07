"use client"
import React from "react"
import { useState, useEffect } from "react"
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

const calculateProgress = (processedItems?: number, totalItems?: number): number => {
  if (!processedItems || !totalItems || totalItems === 0) return 0;
  return Math.round((processedItems / totalItems) * 100);
};

export default function ExperimentsDashboard() {
  const [client] = useState(() => {
    console.log('Initializing client...');
    const c = generateClient<Schema>();
    console.log('Client initialized:', c);
    return c;
  });
  const [experiments, setExperiments] = useState<Schema['Experiment']['type'][]>([])
  const [experimentTaskProps, setExperimentTaskProps] = useState<ExperimentTaskProps['task'] | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [selectedExperiment, setSelectedExperiment] = useState<Schema['Experiment']['type'] | null>(null)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const [scorecardNames, setScorecardNames] = useState<Record<string, string>>({})

  const getExperimentTaskProps = async (experiment: any) => {
    const progress = calculateProgress(experiment.processedItems, experiment.totalItems);
    return {
      id: experiment.id,
      type: experiment.type,
      scorecard: experiment.scorecardId,
      score: experiment.scoreId,
      time: experiment.createdAt,
      summary: 'Experiment Summary',
      description: 'Experiment Description',
      data: {
        accuracy: experiment.accuracy || 0,
        sensitivity: experiment.sensitivity || 0,
        specificity: experiment.specificity || 0,
        precision: experiment.precision || 0,
        processedItems: experiment.processedItems || 0,
        totalItems: experiment.totalItems || 0,
        progress,
        inferences: experiment.inferences || 0,
        cost: experiment.cost || 0,
        status: experiment.status || 'Unknown',
        elapsedTime: '00:00:00',
        estimatedTimeRemaining: '00:00:00',
        confusionMatrix: experiment.confusionMatrix || { matrix: [], labels: [] },
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

  // Add effect to load scorecard names
  useEffect(() => {
    const loadScorecardNames = async () => {
      const names: Record<string, string> = {};
      for (const experiment of experiments) {
        if (experiment.scorecardId) {
          const name = await experiment.scorecard?.().then(r => r.data?.name);
          if (name) {
            names[experiment.scorecardId] = name;
          }
        }
      }
      setScorecardNames(names);
    };
    loadScorecardNames();
  }, [experiments]);

  // Move all client usage into useEffect to avoid server/client mismatch
  useEffect(() => {
    let subscription: { unsubscribe: () => void } | null = null

    async function setupRealTimeSync() {
      try {
        console.log('Fetching account...');
        const accountResult = await client.models.Account.list({
          filter: { key: { eq: ACCOUNT_KEY } }
        });
        console.log('Account result:', accountResult);

        if (accountResult.data.length > 0) {
          const foundAccountId = accountResult.data[0].id;
          console.log('Found account ID:', foundAccountId);
          setAccountId(foundAccountId);
          
          console.log('Fetching experiments...');
          const initialExperiments = await client.models.Experiment.list({
            filter: { accountId: { eq: foundAccountId } }
          });
          console.log('Experiments result:', initialExperiments);
          
          // Filter and sort experiments
          const filteredExperiments = initialExperiments.data
            .sort((a, b) => 
              new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
            )
          
          setExperiments(filteredExperiments)
          setIsLoading(false)

          // Set up real-time subscription
          subscription = client.models.Experiment.observeQuery({
            filter: { accountId: { eq: foundAccountId } }
          }).subscribe({
            next: ({ items }) => {
              const sortedItems = items.sort((a, b) => 
                new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
              )
              setExperiments(sortedItems)
              
              // Update selectedExperiment if it exists in the new items
              if (selectedExperiment) {
                const updatedExperiment = items.find(item => 
                  item.id === selectedExperiment.id
                )
                if (updatedExperiment && 
                    JSON.stringify(updatedExperiment) !== 
                    JSON.stringify(selectedExperiment)) {
                  setSelectedExperiment(updatedExperiment)
                }
              }
            },
            error: (error: Error) => {
              console.error('Subscription error:', error)
              setError(error)
            }
          })
        } else {
          console.log('No account found with key:', ACCOUNT_KEY);
          setIsLoading(false)
        }
      } catch (error) {
        if (error instanceof Error) {
          console.error('Error details:', {
            name: error.name,
            message: error.message,
            stack: error.stack
          });
          setError(error);
        } else {
          console.error('Unexpected error:', error);
          setError(new Error('An unexpected error occurred'));
        }
        setIsLoading(false);
      }
    }

    setupRealTimeSync()

    return () => {
      if (subscription) {
        subscription.unsubscribe()
      }
    }
  }, [client, selectedExperiment?.id]) // Add selectedExperiment.id to dependencies

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
    console.log('Client-side scorecardNames:', scorecardNames)
  }, [experiments, selectedExperiment, experimentTaskProps, scorecardNames])

  // Add server-side logging
  console.log('Server-side render state:', {
    experiments,
    selectedExperiment,
    experimentTaskProps,
    scorecardNames
  })

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
            availableFields={[]} // We'll need to populate this from real data
            timeRangeOptions={[
              { value: 'Accuracy', label: 'Accuracy' },
              { value: 'Consistency', label: 'Consistency' },
            ]}
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
          <div className={`flex ${isNarrowViewport ? 'flex-col' : 'space-x-6'} h-full`}>
            <div className={`${isFullWidth ? 'hidden' : 'flex-1'} @container overflow-auto`}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[30%]">Experiment</TableHead>
                    <TableHead className="w-[10%] @[630px]:table-cell hidden">Type</TableHead>
                    <TableHead className="w-[10%] @[630px]:table-cell hidden text-right">Samples</TableHead>
                    <TableHead className="w-[10%] @[630px]:table-cell hidden text-right">Inferences</TableHead>
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
                              <div className="font-semibold">{scorecardNames[experiment.scorecardId ?? '']}</div>
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
                                {experiment.inferences ?? 0} inferences
                              </div>
                              <div className="text-sm text-muted-foreground">
                                ${experiment.cost?.toFixed(3) ?? '0.000'}
                              </div>
                            </div>

                            {/* Right column */}
                            <div className="w-[140px] space-y-2">
                              <ExperimentListProgressBar 
                                progress={calculateProgress(experiment.processedItems, experiment.totalItems)}
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
                          {scorecardNames[experiment.scorecardId ?? '']}
                          <div className="text-sm text-muted-foreground">
                            {formatDistanceToNow(new Date(experiment.createdAt), { addSuffix: true })}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="hidden @[630px]:table-cell text-sm text-muted-foreground">
                        {experiment.accuracyType ?? 'Accuracy'}
                      </TableCell>
                      <TableCell className="hidden @[630px]:table-cell text-right">
                        {experiment.totalItems ?? 0}
                      </TableCell>
                      <TableCell className="hidden @[630px]:table-cell text-right">
                        {experiment.inferences ?? 0}
                      </TableCell>
                      <TableCell className="hidden @[630px]:table-cell text-right">
                        ${experiment.cost?.toFixed(3) ?? '0.000'}
                      </TableCell>
                      <TableCell className="hidden @[630px]:table-cell w-[15%] text-right">
                        <ExperimentListProgressBar 
                          progress={calculateProgress(experiment.processedItems, experiment.totalItems)}
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
              <div className="flex-1 overflow-y-auto">
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
            )}
          </div>
        )}
      </div>
    </div>
  )
}
