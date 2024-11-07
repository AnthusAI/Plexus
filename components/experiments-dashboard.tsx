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

const ACCOUNT_KEY = 'call-criteria'

const renderProgressBar = (progress: number, truePart: number, falsePart: number, isAccuracy: boolean) => {
  const accuracy = Math.round((truePart / (truePart + falsePart)) * 100);
  const trueWidth = (accuracy / 100) * progress;
  const falseWidth = progress - trueWidth;

  return (
    <div className="relative w-full h-6 bg-neutral rounded-full">
      {isAccuracy ? (
        <>
          <div
            className="absolute top-0 left-0 h-full bg-true flex items-center pl-2 text-xs text-primary-foreground font-medium"
            style={{ width: `${trueWidth}%`, borderTopLeftRadius: 'inherit', borderBottomLeftRadius: 'inherit' }}
          >
            {accuracy}%
          </div>
          <div
            className="absolute top-0 h-full bg-false"
            style={{ 
              left: `${trueWidth}%`, 
              width: `${falseWidth}%`,
              borderTopRightRadius: 'inherit',
              borderBottomRightRadius: 'inherit'
            }}
          />
        </>
      ) : (
        <div
          className="absolute top-0 left-0 h-full bg-secondary flex items-center pl-2 text-xs text-primary-foreground font-medium"
          style={{ width: `${progress}%`, borderRadius: 'inherit' }}
        >
          {progress}%
        </div>
      )}
    </div>
  )
}

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

  const getExperimentTaskProps = async (experiment: Schema['Experiment']['type']) => {
    const scorecardName = await experiment.scorecard?.().then(r => r.data?.name) ?? '';
    return {
      id: parseInt(experiment.id),
      type: experiment.type,
      scorecard: scorecardName,
      score: experiment.accuracy?.toString() ?? '',
      time: formatDistanceToNow(new Date(experiment.createdAt), { addSuffix: true }),
      summary: `${experiment.accuracy?.toFixed(1) ?? 0}% accuracy`,
      description: experiment.type,
      data: {
        accuracy: experiment.accuracy ?? 0,
        sensitivity: experiment.sensitivity ?? 0,
        specificity: experiment.specificity ?? 0,
        precision: experiment.precision ?? 0,
        processedItems: experiment.processedItems ?? 0,
        totalItems: experiment.totalItems ?? 0,
        progress: experiment.progress ?? 0,
        inferences: experiment.inferences ?? 0,
        results: experiment.results ?? 0,
        cost: experiment.cost ?? 0,
        status: experiment.status,
        startedAt: experiment.startedAt,
        estimatedEndAt: experiment.estimatedEndAt,
        confusionMatrix: experiment.confusionMatrix as {
          matrix: number[][];
          labels: string[];
        }
      }
    };
  };

  // Effect to update experimentTaskProps when selectedExperiment changes
  useEffect(() => {
    if (selectedExperiment) {
      getExperimentTaskProps(selectedExperiment).then(setExperimentTaskProps);
    } else {
      setExperimentTaskProps(null);
    }
  }, [selectedExperiment]);

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
              const sortedItems = items
                .sort((a, b) => 
                  new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
                )
              setExperiments(sortedItems)
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
        console.error('Error details:', {
          name: error.name,
          message: error.message,
          stack: error.stack
        });
        setError(error as Error);
        setIsLoading(false);
      }
    }

    setupRealTimeSync()

    return () => {
      if (subscription) {
        subscription.unsubscribe()
      }
    }
  }, [client]) // Add client to dependencies

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
                    <TableHead className="w-[10%] @[630px]:table-cell hidden text-right">Inferences</TableHead>
                    <TableHead className="w-[10%] @[630px]:table-cell hidden text-right">Results</TableHead>
                    <TableHead className="w-[10%] @[630px]:table-cell hidden text-right">Cost</TableHead>
                    <TableHead className="w-[15%] @[630px]:table-cell hidden text-left">Progress</TableHead>
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
                        <div className="sm:hidden">
                          <div className="font-semibold">
                            {scorecardNames[experiment.scorecardId ?? '']}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {formatDistanceToNow(new Date(experiment.createdAt), { addSuffix: true })}
                          </div>
                        </div>
                        <div className="hidden sm:block">
                          {scorecardNames[experiment.scorecardId ?? '']}
                          <div className="text-sm text-muted-foreground">
                            {formatDistanceToNow(new Date(experiment.createdAt), { addSuffix: true })}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="bg-neutral text-primary-foreground">
                          {experiment.accuracyType ?? 'Accuracy'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">{experiment.inferences ?? 0}</TableCell>
                      <TableCell className="text-right">{experiment.results ?? 0}</TableCell>
                      <TableCell className="text-right">${experiment.cost?.toFixed(3) ?? '0.000'}</TableCell>
                      <TableCell className="w-[15%]">
                        {renderProgressBar(experiment.progress ?? 0, 
                          experiment.accuracy ?? 0, 
                          100 - (experiment.accuracy ?? 0), 
                          false)}
                      </TableCell>
                      <TableCell className="w-[15%]">
                        {renderProgressBar(experiment.progress ?? 0, 
                          experiment.accuracy ?? 0, 
                          100 - (experiment.accuracy ?? 0), 
                          true)}
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
