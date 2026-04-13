import React, { useCallback, useState, useEffect } from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { BaseTaskData } from '@/types/base'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { Waypoints, MoreHorizontal, Square, X, Trash2, Columns2, Edit, Copy, FileText, ChevronRight, ChevronDown, FileJson, Expand, BookOpenCheck, ExternalLink } from 'lucide-react'
import Link from 'next/link'

import { Timestamp } from './ui/timestamp'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { toast } from 'sonner'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import Editor from "@monaco-editor/react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions, configureYamlLanguage } from "@/lib/monaco-theme"

import ProcedureConversationViewer from "./procedure-conversation-viewer"
import { ParametersDisplay } from "./ui/ParametersDisplay"
import { parseParametersFromYaml } from "@/lib/parameter-parser"
import type { ParameterDefinition, ParameterValue } from "@/types/parameters"
import * as yaml from 'js-yaml'
import OptimizerMetricsChart, { type IterationData } from "./OptimizerMetricsChart"
import { OptimizationDiagnosticBanner, CycleInsightsPanel } from "./OptimizationInsightsPanel"

let amplifyClient: ReturnType<typeof generateClient<Schema>> | null = null
const getAmplifyClient = () => (amplifyClient ??= generateClient<Schema>())

// Minimal fallback for YAML editor - actual templates come from procedure data
const MINIMAL_YAML_FALLBACK = `class: "BeamSearch"
# Loading procedure configuration...`

// Status display helper function
const getStatusDisplay = (status?: string): { text: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' } => {
  if (!status) return { text: 'Pending', variant: 'secondary' }
  
  const statusMap: Record<string, { text: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
    // Task states
    PENDING: { text: 'Pending', variant: 'secondary' },
    RUNNING: { text: 'Running', variant: 'default' },
    COMPLETED: { text: 'Completed', variant: 'outline' },
    FAILED: { text: 'Failed', variant: 'destructive' },
    // Procedure states (state machine)
    START: { text: 'Start', variant: 'secondary' },
    HYPOTHESIS: { text: 'Hypothesis', variant: 'default' },
    CODE: { text: 'Coding', variant: 'default' },
    ERROR: { text: 'Error', variant: 'destructive' },
  }
  
  const upperStatus = status.toUpperCase()
  return statusMap[upperStatus] || { text: status, variant: 'secondary' }
}

// Define the procedure data type
export interface ProcedureTaskData extends BaseTaskData {
  id: string
  featured: boolean
  rootNodeId?: string
  createdAt: string
  updatedAt: string
  scorecardId?: string
  scorecard?: {
    id?: string
    name: string
  } | null
  scoreId?: string
  score?: {
    id?: string
    name: string
  } | null
  taskId?: string
  task?: {
    id: string
    type: string
    status: string
    target: string
    command: string
    description?: string
    dispatchStatus?: string
    metadata?: any
    createdAt?: string
    startedAt?: string
    completedAt?: string
    estimatedCompletionAt?: string
    errorMessage?: string
    errorDetails?: any
    currentStageId?: string
    stages?: {
      items: Array<{
        id: string
        name: string
        order: number
        status: string
        statusMessage?: string
        startedAt?: string
        completedAt?: string
        estimatedCompletionAt?: string
        processedItems?: number
        totalItems?: number
      }>
    }
  } | null
}

export interface ProcedureTaskProps {
  variant: 'grid' | 'detail'
  procedure: ProcedureTaskData
  onClick?: () => void
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  isSelected?: boolean
  onDelete?: (procedureId: string) => void
  onEdit?: (procedureId: string) => void
  onDuplicate?: (procedureId: string) => void
  onConversationFullscreenChange?: (isFullscreen: boolean) => void
}

export default function ProcedureTask({
  variant,
  procedure,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  isSelected,
  onDelete,
  onEdit,
  onDuplicate,
  onConversationFullscreenChange
}: ProcedureTaskProps) {
  const [loadedYaml, setLoadedYaml] = useState<string>('')
  const [isLoadingYaml, setIsLoadingYaml] = useState(false)
  const [sessionCount, setSessionCount] = useState(0)
  const [isConversationFullscreen, setIsConversationFullscreen] = useState(false)
  const [parameters, setParameters] = useState<ParameterDefinition[]>([])
  const [parameterValues, setParameterValues] = useState<ParameterValue>({})
  const [optimizerIterations, setOptimizerIterations] = useState<IterationData[]>([])
  const [optimizerVersions, setOptimizerVersions] = useState<Array<{
    label: string
    versionId?: string
    accepted?: boolean
    isBaseline?: boolean
    feedbackAC1?: number | null
    feedbackDelta?: number | null
    accuracyAC1?: number | null
    accuracyDelta?: number | null
    skipReason?: string
    disqualified?: boolean
  }>>([])
  const [optimizerVersionBaseIds, setOptimizerVersionBaseIds] = useState<{ scorecardId?: string; scoreId?: string }>({})
  const [stateScorecardName, setStateScorecardName] = useState<string>('')
  const [stateScoreName, setStateScoreName] = useState<string>('')
  const [cycleInsights, setCycleInsights] = useState<any[]>([])
  const [optimizationDiagnostic, setOptimizationDiagnostic] = useState<any>(null)
  const [iterationDetails, setIterationDetails] = useState<Map<number, any>>(new Map())
  const [expandedVersionRows, setExpandedVersionRows] = useState<Set<number>>(new Set())

  // Load procedure data when component mounts or procedure changes
  useEffect(() => {
    if (variant === 'detail' && procedure.id) {
      loadProcedureYaml()
    }
  }, [variant, procedure.id])

  // Fetch optimizer metrics from procedure metadata (State.set() now persists via on_set callback)
  useEffect(() => {
    if (variant !== 'detail' || !procedure.id) return

    const fetchMetrics = async () => {
      try {
        const response = await fetch(`/api/procedure-state/${procedure.id}`)
        if (!response.ok) return
        const { state } = await response.json()

        // Always extract identity info from state — used for names and link URLs
        // even when there are no iterations yet (procedure may be starting up)
        const vscId = state.scorecard_id || procedure.scorecardId
        const vscoreId = state.score_id || procedure.scoreId
        if (vscId || vscoreId) {
          setOptimizerVersionBaseIds({ scorecardId: vscId, scoreId: vscoreId })
        }
        if (state.scorecard_name) setStateScorecardName(state.scorecard_name)
        if (state.score_name) setStateScoreName(state.score_name)

        const fbBaseline = state.feedback_baseline_metrics
        const accBaseline = state.accuracy_baseline_metrics
        const cycleIterations: any[] = state.iterations || []

        if (!fbBaseline && cycleIterations.length === 0) return

        const iterations: IterationData[] = []

        // Baseline as first point
        if (fbBaseline || accBaseline) {
          iterations.push({
            iteration: 0,
            label: 'Baseline',
            feedback_metrics: fbBaseline,
            accuracy_metrics: accBaseline,
            accepted: true,
          })
        }

        // Cycle entries from state.iterations
        for (const it of cycleIterations) {
          iterations.push({
            iteration: it.iteration,
            label: `Cycle ${it.iteration}`,
            score_version_id: it.score_version_id,
            feedback_metrics: it.feedback_metrics,
            accuracy_metrics: it.accuracy_metrics,
            feedback_deltas: it.feedback_deltas,
            accuracy_deltas: it.accuracy_deltas,
            accepted: it.accepted,
            skip_reason: it.skip_reason,
            disqualified: it.disqualified,
          })
        }

        setOptimizerIterations(iterations)

        const versionRows: Array<{
          label: string; versionId?: string; accepted?: boolean; isBaseline?: boolean
          feedbackAC1?: number | null; feedbackDelta?: number | null
          accuracyAC1?: number | null; accuracyDelta?: number | null
          skipReason?: string; disqualified?: boolean
        }> = []
        if (state.baseline_version_id) {
          // Prefer the immutable initial-baseline keys (written by newer optimizer runs).
          // For older runs that only have the overwritten keys, infer from the first
          // cycle's stored delta: original_baseline = cycle_ac1 - cycle_delta.
          const firstCycle = cycleIterations[0]
          const inferredFbBaseline =
            firstCycle?.feedback_metrics?.alignment != null && firstCycle?.feedback_deltas?.alignment != null
              ? firstCycle.feedback_metrics.alignment - firstCycle.feedback_deltas.alignment
              : null
          const inferredAccBaseline =
            firstCycle?.accuracy_metrics?.alignment != null && firstCycle?.accuracy_deltas?.alignment != null
              ? firstCycle.accuracy_metrics.alignment - firstCycle.accuracy_deltas.alignment
              : null

          versionRows.push({
            label: 'Baseline',
            versionId: state.baseline_version_id,
            isBaseline: true,
            feedbackAC1: state.feedback_initial_baseline_metrics?.alignment
              ?? inferredFbBaseline
              ?? state.feedback_baseline_metrics?.alignment
              ?? null,
            feedbackDelta: null,
            accuracyAC1: state.accuracy_initial_baseline_metrics?.alignment
              ?? inferredAccBaseline
              ?? state.accuracy_baseline_metrics?.alignment
              ?? null,
            accuracyDelta: null,
            accepted: true,
          })
        }
        for (const it of cycleIterations) {
          versionRows.push({
            label: `Cycle ${it.iteration}`,
            versionId: it.score_version_id,
            accepted: it.accepted,
            feedbackAC1: it.feedback_metrics?.alignment ?? null,
            feedbackDelta: it.feedback_deltas?.alignment ?? null,
            accuracyAC1: it.accuracy_metrics?.alignment ?? null,
            accuracyDelta: it.accuracy_deltas?.alignment ?? null,
            skipReason: it.skip_reason,
            disqualified: it.disqualified,
          })
        }
        if (versionRows.length > 0) setOptimizerVersions(versionRows)

        // Extract cycle insights and optimization diagnostic
        if (state.cycle_insights) setCycleInsights(state.cycle_insights)
        if (state.optimization_diagnostic) setOptimizationDiagnostic(state.optimization_diagnostic)

        // Extract per-iteration details for expandable version rows
        const details = new Map<number, any>()
        for (const it of cycleIterations) {
          if (it.exploration_results || it.done_reason || it.synthesis_reasoning || it.dual_synthesis) {
            details.set(it.iteration, {
              exploration_results: it.exploration_results,
              done_reason: it.done_reason,
              synthesis_reasoning: it.synthesis_reasoning,
              synthesis_strategy: it.synthesis_strategy,
              dual_synthesis: it.dual_synthesis,
            })
          }
        }
        setIterationDetails(details)
      } catch (e) {
        console.error('[ProcedureTask] Failed to fetch optimizer metrics:', e)
      }
    }

    fetchMetrics()

    const isCompleted = procedure.task?.status === 'COMPLETED' || procedure.task?.status === 'FAILED'
    if (!isCompleted) {
      const interval = setInterval(fetchMetrics, 15000)
      return () => clearInterval(interval)
    }
  }, [variant, procedure.id, procedure.task?.status])

  // Parse parameters from YAML whenever it changes
  useEffect(() => {
    if (loadedYaml) {
      try {
        const parsedParams = parseParametersFromYaml(loadedYaml)
        console.log('[ProcedureTask] Parsed parameters:', parsedParams.length, parsedParams)
        setParameters(parsedParams)
        
        // Extract values from the YAML
        const config = yaml.load(loadedYaml) as any
        console.log('[ProcedureTask] YAML config:', config)
        if (config && config.parameters && Array.isArray(config.parameters)) {
          const values: ParameterValue = {}
          config.parameters.forEach((param: any) => {
            if (param.value !== undefined) {
              values[param.name] = param.value
            }
          })
          console.log('[ProcedureTask] Parameter values:', values)
          setParameterValues(values)
        } else if (config && config.params && typeof config.params === 'object') {
          const values: ParameterValue = {}
          Object.entries(config.params).forEach(([name, paramDef]: [string, any]) => {
            if (paramDef && typeof paramDef === 'object' && paramDef.value !== undefined) {
              values[name] = paramDef.value
            }
          })
          console.log('[ProcedureTask] Parameter values from params mapping:', values)
          setParameterValues(values)
        } else {
          console.log('[ProcedureTask] No parameters array found in config')
          setParameterValues({})
        }
      } catch (error) {
        console.error('Error parsing parameters:', error)
        setParameters([])
        setParameterValues({})
      }
    }
  }, [loadedYaml])

  const loadProcedureYaml = async () => {
    if (!procedure.id) return
    
    try {
      setIsLoadingYaml(true)
      const result = await getAmplifyClient().graphql({
        query: `
          query GetProcedure($id: ID!) {
            getProcedure(id: $id) {
              id
              code
            }
          }
        `,
        variables: { id: procedure.id }
      })

      const procedureData = (result as any).data?.getProcedure
      if (procedureData?.code) {
        setLoadedYaml(procedureData.code)
      }
    } catch (error) {
      console.error('Error loading procedure YAML:', error)
      toast.error('Failed to load procedure configuration')
    } finally {
      setIsLoadingYaml(false)
    }
  }

  const handleConversationFullscreenChange = useCallback((isFullscreen: boolean) => {
    setIsConversationFullscreen(isFullscreen)
    if (onConversationFullscreenChange) {
      onConversationFullscreenChange(isFullscreen)
    }
  }, [onConversationFullscreenChange])

  // Convert procedure data to task data format
  const taskData: BaseTaskData = {
    id: procedure.id,
    title: procedure.title,
    description: procedure.description,
    errorMessage: procedure.errorMessage,
    command: procedure.command
  }

  // Create the task object that matches the Task component's expected interface
  // Format stages with proper colors based on status
  const formattedStages = (procedure.task?.stages?.items || []).map((stage: any) => {
    const isCompleted = stage.status === 'COMPLETED';
    const isRunning = stage.status === 'RUNNING';
    const isFailed = stage.status === 'FAILED';
    
    return {
      id: stage.id,
      key: stage.name,
      label: stage.name,
      color: isCompleted ? 'bg-primary' :
             isRunning ? 'bg-secondary' :
             isFailed ? 'bg-false' :
             'bg-neutral',
      name: stage.name,
      order: stage.order,
      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
      statusMessage: stage.statusMessage,
      startedAt: stage.startedAt,
      completedAt: stage.completedAt,
      estimatedCompletionAt: stage.estimatedCompletionAt,
      processedItems: stage.processedItems,
      totalItems: stage.totalItems,
      completed: isCompleted
    };
  });
  
  const taskObject = {
    id: procedure.id,
    type: 'Procedure',
    name: procedure.title,
    description: procedure.description,
    scorecard: procedure.scorecard?.name || stateScorecardName || '',
    score: procedure.score?.name || stateScoreName || '',
    time: procedure.createdAt,
    command: procedure.command,
    output: (procedure as any).output, // May not exist in type definition yet
    data: taskData,
    stages: formattedStages, // Use formatted stages with colors
    currentStageName: procedure.task?.currentStageId
      ? procedure.task.stages?.items?.find(s => s.id === procedure.task?.currentStageId)?.name
      : undefined, // Resolve ID to name
    processedItems: (procedure as any).processedItems, // May not exist in type definition yet
    totalItems: (procedure as any).totalItems, // May not exist in type definition yet
    startedAt: procedure.task?.startedAt, // Get from task
    estimatedCompletionAt: procedure.task?.estimatedCompletionAt, // Get from task
    completedAt: procedure.task?.completedAt, // Get from task
    status: (procedure.task?.status || 'PENDING') as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
    errorMessage: procedure.task?.errorMessage || procedure.errorMessage
  }

  const headerContent = (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
        >
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {onEdit && (
          <DropdownMenuItem onClick={() => onEdit(procedure.id)}>
            <Edit className="mr-2 h-4 w-4" />
            Edit
          </DropdownMenuItem>
        )}
        {onDuplicate && (
          <DropdownMenuItem onClick={() => onDuplicate(procedure.id)}>
            <Copy className="mr-2 h-4 w-4" />
            Duplicate
          </DropdownMenuItem>
        )}
        {onDelete && (
          <DropdownMenuItem 
            onClick={() => onDelete(procedure.id)}
            className="text-destructive focus:text-destructive"
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )

  const renderHeader = (props: any) => {
    if (variant === 'detail') {
      // Custom header for detail view with status badge
      return (
        <div className="space-y-1.5 p-0 flex flex-col items-start w-full max-w-full px-1">
          <div className="flex justify-between items-start w-full max-w-full gap-3 overflow-hidden">
            <div className="flex flex-col pb-1 leading-none min-w-0 flex-1 overflow-hidden">
              <div className="flex items-center gap-2 mb-1">
                <Waypoints className="h-5 w-5 text-muted-foreground" />
                <span className="text-lg font-semibold text-muted-foreground">Procedure</span>
              </div>
              
              {/* Timestamp */}
              <div className="mb-2">
                <Timestamp time={props.task.time} variant="relative" />
              </div>
              
              {props.task.scorecard && props.task.scorecard.trim() !== '' && (
                <div className="flex items-center gap-1.5 font-semibold text-sm min-w-0">
                  <span className="truncate">{props.task.scorecard}</span>
                  {(procedure.scorecardId || optimizerVersionBaseIds.scorecardId) && (
                    <Link
                      href={`/lab/scorecards/${procedure.scorecardId || optimizerVersionBaseIds.scorecardId}`}
                      className="flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </Link>
                  )}
                </div>
              )}
              {props.task.score && props.task.score.trim() !== '' && (
                <div className="flex items-center gap-1.5 font-semibold text-sm min-w-0">
                  <span className="truncate">{props.task.score}</span>
                  {(procedure.scorecardId || optimizerVersionBaseIds.scorecardId) &&
                   (procedure.scoreId || optimizerVersionBaseIds.scoreId) && (
                    <Link
                      href={`/lab/scorecards/${procedure.scorecardId || optimizerVersionBaseIds.scorecardId}/scores/${procedure.scoreId || optimizerVersionBaseIds.scoreId}`}
                      className="flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </Link>
                  )}
                </div>
              )}
            </div>
            <div className="flex flex-col items-end flex-shrink-0 gap-2">
              <div className="flex gap-2">
                {headerContent}
                {onToggleFullWidth && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                    onClick={onToggleFullWidth}
                    aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
                  >
                    {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                  </Button>
                )}
                {onClose && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                    onClick={onClose}
                    aria-label="Close"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )
    } else {
      // Custom header for grid view with bold scorecard/score
      return (
        <div className="space-y-1.5 p-0 flex flex-col items-start w-full max-w-full">
          <div className="flex justify-between items-start w-full max-w-full gap-3 overflow-hidden">
            <div className="flex flex-col pb-1 leading-none min-w-0 flex-1 overflow-hidden">
              {props.task.scorecard && props.task.scorecard.trim() !== '' && (
                <div className="flex items-center gap-1.5 font-semibold text-sm min-w-0">
                  <span className="truncate">{props.task.scorecard}</span>
                </div>
              )}
              {props.task.score && props.task.score.trim() !== '' && (
                <div className="flex items-center gap-1.5 font-semibold text-sm min-w-0">
                  <span className="truncate">{props.task.score}</span>
                </div>
              )}
              {props.task.description && (
                <div className="text-sm text-muted-foreground truncate">
                  {props.task.description}
                </div>
              )}
              <Timestamp time={props.task.time} variant="relative" />
            </div>
            <div className="flex flex-col items-end flex-shrink-0">
              <div className="flex items-center gap-2">
                <div className="text-muted-foreground">
                  <Waypoints className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
                </div>
                {controlButtons}
              </div>
            </div>
          </div>
        </div>
      )
    }
  }

  const renderContent = () => (
    <TaskContent variant={variant} task={taskObject}>
      {variant === 'grid' ? (
        // Empty grid content since all info is now in header
        null
      ) : (
        <div className="p-3">
          {/* Parameters section - collapsed by default */}
          {parameters.length > 0 && (
            <Accordion type="multiple" className="w-full mb-4">
              <AccordionItem value="parameters" className="border-b-0">
                <AccordionTrigger className="hover:no-underline py-2 px-0 justify-start [&>svg]:hidden group">
                  <div className="flex items-center gap-2">
                    <FileText className="h-3 w-3 text-muted-foreground" />
                    <span className="text-sm font-medium leading-none text-muted-foreground">Parameters</span>
                    <ChevronRight className="h-3 w-3 text-muted-foreground transition-transform duration-200 group-data-[state=open]:hidden" />
                    <ChevronDown className="h-3 w-3 text-muted-foreground transition-transform duration-200 hidden group-data-[state=open]:block" />
                  </div>
                </AccordionTrigger>
                <AccordionContent className="pt-0 pb-4">
                  <ParametersDisplay
                    parameters={parameters}
                    values={parameterValues}
                    variant="table"
                  />
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          )}
          
          {/* Configuration section */}
          <Accordion type="multiple" className="w-full">
            <AccordionItem value="configuration" className="border-b-0">
              <AccordionTrigger className="hover:no-underline py-2 px-0 justify-start [&>svg]:hidden group">
                <div className="flex items-center gap-2">
                  <FileJson className="h-3 w-3 text-muted-foreground" />
                  <span className="text-sm font-medium leading-none text-muted-foreground">Code</span>
                  <ChevronRight className="h-3 w-3 text-muted-foreground transition-transform duration-200 group-data-[state=open]:hidden" />
                  <ChevronDown className="h-3 w-3 text-muted-foreground transition-transform duration-200 hidden group-data-[state=open]:block" />
                </div>
              </AccordionTrigger>
              <AccordionContent className="pt-0 pb-4">
                <div className="overflow-hidden">
                  {isLoadingYaml ? (
                    <div className="flex items-center justify-center h-32">
                      <span className="text-sm text-muted-foreground">Loading configuration...</span>
                    </div>
                  ) : (
                    <Editor
                      height="400px"
                      defaultLanguage="yaml"
                      value={loadedYaml || MINIMAL_YAML_FALLBACK}
                      onMount={(_, monaco) => {
                        // Configure Monaco editor for YAML
                        defineCustomMonacoThemes(monaco)
                        applyMonacoTheme(monaco)
                        setupMonacoThemeWatcher(monaco)
                        configureYamlLanguage(monaco)
                      }}
                      options={{
                        ...getCommonMonacoOptions(),
                        readOnly: true,
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        wordWrap: 'on',
                        tabSize: 2,
                        insertSpaces: true,
                      }}
                    />
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>

          {/* Optimization Diagnostic Banner - shown when optimizer is stuck */}
          {optimizationDiagnostic && (
            <OptimizationDiagnosticBanner diagnostic={optimizationDiagnostic} />
          )}

          {/* Optimizer Metrics Chart - only show if iterations exist */}
          {optimizerIterations.length > 0 && (
            <OptimizerMetricsChart iterations={optimizerIterations} />
          )}

          {/* Cycle Insights - synthesis analysis from each cycle */}
          {cycleInsights.length > 0 && (
            <CycleInsightsPanel insights={cycleInsights} />
          )}

          {/* Score Versions table - links to each cycle's version for champion promotion */}
          {optimizerVersions.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-semibold text-muted-foreground mb-2">Score Versions</h3>
              <table className="w-full text-xs border-separate border-spacing-y-0.5">
                <thead>
                  <tr className="text-muted-foreground/60">
                    <th className="px-1 py-0.5 text-left font-normal"></th>
                    <th className="px-1 py-0.5 text-left font-normal"></th>
                    <th className="px-1 py-0.5 text-right font-normal" colSpan={2}>Feedback</th>
                    <th className="px-1 py-0.5 text-right font-normal" colSpan={2}>Accuracy</th>
                    <th className="px-1 py-0.5 font-normal"></th>
                    <th className="px-1 py-0.5 font-normal"></th>
                  </tr>
                </thead>
                <tbody>
                  {optimizerVersions.map((row, i) => {
                    // Extract cycle number from label like "Cycle 1"
                    const cycleMatch = row.label.match(/Cycle\s+(\d+)/)
                    const cycleNum = cycleMatch ? parseInt(cycleMatch[1]) : null
                    const details = cycleNum != null ? iterationDetails.get(cycleNum) : null
                    const isExpanded = cycleNum != null && expandedVersionRows.has(cycleNum)

                    return (
                      <React.Fragment key={i}>
                        <tr
                          className={details ? 'cursor-pointer hover:bg-accent/50' : ''}
                          onClick={() => {
                            if (!details || cycleNum == null) return
                            setExpandedVersionRows(prev => {
                              const next = new Set(prev)
                              if (next.has(cycleNum)) next.delete(cycleNum)
                              else next.add(cycleNum)
                              return next
                            })
                          }}
                        >
                          <td className="px-1 py-0.5 text-muted-foreground whitespace-nowrap">
                            <span className="flex items-center gap-1">
                              {details && (
                                isExpanded
                                  ? <ChevronDown className="h-3 w-3" />
                                  : <ChevronRight className="h-3 w-3" />
                              )}
                              {row.label}
                            </span>
                          </td>
                          <td className="px-1 py-0.5 whitespace-nowrap">
                            {row.isBaseline ? (
                              <Badge variant="outline" className="text-xs px-1 py-0">Baseline</Badge>
                            ) : row.skipReason ? (
                              <Badge variant="secondary" className="text-xs px-1 py-0">Skipped</Badge>
                            ) : row.disqualified ? (
                              <Badge variant="destructive" className="text-xs px-1 py-0">Disqualified</Badge>
                            ) : row.accepted ? (
                              <Badge className="text-xs px-1 py-0">Accepted</Badge>
                            ) : (
                              <Badge variant="secondary" className="text-xs px-1 py-0">Rejected</Badge>
                            )}
                          </td>
                          <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                            {row.feedbackAC1 != null ? row.feedbackAC1.toFixed(3) : '—'}
                          </td>
                          <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right">
                            {row.feedbackDelta != null && (
                              <span className={row.feedbackDelta >= 0 ? 'text-green-500' : 'text-red-500'}>
                                {row.feedbackDelta >= 0 ? '+' : ''}{row.feedbackDelta.toFixed(3)}
                              </span>
                            )}
                          </td>
                          <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                            {row.accuracyAC1 != null ? row.accuracyAC1.toFixed(3) : '—'}
                          </td>
                          <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right">
                            {row.accuracyDelta != null && (
                              <span className={row.accuracyDelta >= 0 ? 'text-green-500' : 'text-red-500'}>
                                {row.accuracyDelta >= 0 ? '+' : ''}{row.accuracyDelta.toFixed(3)}
                              </span>
                            )}
                          </td>
                          <td className="px-1 py-0.5 font-mono text-muted-foreground/60 w-full">
                            {row.versionId ? row.versionId.slice(0, 8) + '…' : '—'}
                          </td>
                          <td className="px-1 py-0.5 text-right whitespace-nowrap">
                            {row.versionId && optimizerVersionBaseIds.scorecardId && optimizerVersionBaseIds.scoreId && (
                              <Link
                                href={`/lab/scorecards/${optimizerVersionBaseIds.scorecardId}/scores/${optimizerVersionBaseIds.scoreId}/versions/${row.versionId}`}
                                className="text-muted-foreground hover:text-foreground transition-colors"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <ExternalLink className="h-3 w-3" />
                              </Link>
                            )}
                          </td>
                        </tr>
                        {isExpanded && details && (
                          <tr>
                            <td colSpan={8} className="px-2 py-2 bg-accent/30 rounded">
                              <div className="space-y-2">
                                {details.done_reason && (
                                  <div>
                                    <span className="text-muted-foreground/70 text-xs">Result: </span>
                                    <span className="text-xs">{details.done_reason}</span>
                                  </div>
                                )}
                                {details.exploration_results && details.exploration_results.length > 0 && (
                                  <div>
                                    <span className="text-muted-foreground/70 text-xs block mb-1">Hypotheses tested:</span>
                                    <div className="space-y-1">
                                      {details.exploration_results.map((er: any, j: number) => {
                                        const hypDesc = er.done_reason || er.hypothesis?.description || er.agent_reasoning || ''
                                        return (
                                          <details key={j} className="border border-border/50 rounded">
                                            <summary className="flex items-center gap-2 text-xs px-2 py-1 cursor-pointer hover:bg-accent/30">
                                              <span className="text-muted-foreground truncate flex-1" title={er.hypothesis?.name || `Hyp ${er.index}`}>
                                                {er.hypothesis?.name || `Hypothesis ${er.index}`}
                                              </span>
                                              {er.succeeded ? (
                                                <Badge className="text-xs px-1 py-0 flex-shrink-0">Pass</Badge>
                                              ) : (
                                                <Badge variant="secondary" className="text-xs px-1 py-0 flex-shrink-0">Fail</Badge>
                                              )}
                                              <span className="whitespace-nowrap flex-shrink-0">
                                                <span className="text-muted-foreground/60 mr-1">FB</span>
                                                {er.fb_deltas?.alignment != null ? (
                                                  <span className={er.fb_deltas.alignment >= 0 ? 'text-green-500' : 'text-red-500'}>
                                                    {er.fb_deltas.alignment >= 0 ? '+' : ''}{er.fb_deltas.alignment.toFixed(3)}
                                                  </span>
                                                ) : '—'}
                                              </span>
                                              <span className="whitespace-nowrap flex-shrink-0">
                                                <span className="text-muted-foreground/60 mr-1">ACC</span>
                                                {er.acc_deltas?.alignment != null ? (
                                                  <span className={er.acc_deltas.alignment >= 0 ? 'text-green-500' : 'text-red-500'}>
                                                    {er.acc_deltas.alignment >= 0 ? '+' : ''}{er.acc_deltas.alignment.toFixed(3)}
                                                  </span>
                                                ) : '—'}
                                              </span>
                                            </summary>
                                            {hypDesc && (
                                              <div className="px-2 py-1.5 border-t border-border/30">
                                                <p className="text-xs text-muted-foreground whitespace-pre-wrap">{
                                                  hypDesc.length > 600 ? hypDesc.slice(0, 600) + '...' : hypDesc
                                                }</p>
                                              </div>
                                            )}
                                          </details>
                                        )
                                      })}
                                    </div>
                                  </div>
                                )}
                                {details.dual_synthesis && (
                                  <div>
                                    <span className="text-muted-foreground/70 text-xs block mb-1">
                                      Dual synthesis{details.synthesis_strategy ? ` — selected Strategy ${details.synthesis_strategy}` : ''}:
                                    </span>
                                    <div className="flex gap-3 text-xs">
                                      {details.dual_synthesis.strategy_a && (
                                        <div className={`border rounded px-2 py-1 ${details.synthesis_strategy === 'A' ? 'border-primary/50 bg-primary/5' : 'border-border/50'}`}>
                                          <span className="font-medium">A (cycle-focused)</span>
                                          <span className="ml-2 text-muted-foreground">
                                            FB <span className={details.dual_synthesis.strategy_a.fb_delta >= 0 ? 'text-green-500' : 'text-red-500'}>
                                              {details.dual_synthesis.strategy_a.fb_delta >= 0 ? '+' : ''}{details.dual_synthesis.strategy_a.fb_delta?.toFixed(3)}
                                            </span>
                                            {' '}ACC <span className={details.dual_synthesis.strategy_a.acc_delta >= 0 ? 'text-green-500' : 'text-red-500'}>
                                              {details.dual_synthesis.strategy_a.acc_delta >= 0 ? '+' : ''}{details.dual_synthesis.strategy_a.acc_delta?.toFixed(3)}
                                            </span>
                                          </span>
                                        </div>
                                      )}
                                      {details.dual_synthesis.strategy_b && (
                                        <div className={`border rounded px-2 py-1 ${details.synthesis_strategy === 'B' ? 'border-primary/50 bg-primary/5' : 'border-border/50'}`}>
                                          <span className="font-medium">B (arc-focused)</span>
                                          <span className="ml-2 text-muted-foreground">
                                            FB <span className={details.dual_synthesis.strategy_b.fb_delta >= 0 ? 'text-green-500' : 'text-red-500'}>
                                              {details.dual_synthesis.strategy_b.fb_delta >= 0 ? '+' : ''}{details.dual_synthesis.strategy_b.fb_delta?.toFixed(3)}
                                            </span>
                                            {' '}ACC <span className={details.dual_synthesis.strategy_b.acc_delta >= 0 ? 'text-green-500' : 'text-red-500'}>
                                              {details.dual_synthesis.strategy_b.acc_delta >= 0 ? '+' : ''}{details.dual_synthesis.strategy_b.acc_delta?.toFixed(3)}
                                            </span>
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                    {details.dual_synthesis.selection_reason && (
                                      <p className="text-xs text-muted-foreground/60 mt-1">{details.dual_synthesis.selection_reason}</p>
                                    )}
                                  </div>
                                )}
                                {details.synthesis_reasoning && (
                                  <div>
                                    <span className="text-muted-foreground/70 text-xs block mb-1">Synthesis reasoning:</span>
                                    <p className="text-xs text-muted-foreground whitespace-pre-wrap">{
                                      details.synthesis_reasoning.length > 500
                                        ? details.synthesis_reasoning.slice(0, 500) + '...'
                                        : details.synthesis_reasoning
                                    }</p>
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Procedure Conversation section */}
          <div className="mt-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold flex items-center gap-2 text-muted-foreground">
                  <BookOpenCheck className="h-5 w-5" />
                  Conversations ({sessionCount})
                </h3>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                  onClick={() => {
                    handleConversationFullscreenChange(true)
                  }}
                  aria-label="Fullscreen conversation"
                >
                  <Expand className="h-4 w-4" />
                </Button>
              </div>
              <div>
                <ProcedureConversationViewer 
                  procedureId={procedure.id} 
                  onSessionCountChange={setSessionCount}
                  onFullscreenChange={handleConversationFullscreenChange}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </TaskContent>
  )

  // Conversation fullscreen is now handled at the parent level
  // No need to render fullscreen view here anymore

  return (
    <Task
      variant={variant}
      task={taskObject}
      onClick={onClick}
      controlButtons={headerContent}
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      isSelected={isSelected}
      renderHeader={renderHeader}
      renderContent={renderContent}
    />
  )
}
