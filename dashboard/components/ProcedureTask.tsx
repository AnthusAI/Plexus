import React, { useCallback, useState, useEffect, useTransition } from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { BaseTaskData } from '@/types/base'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { Waypoints, MoreHorizontal, Square, X, Trash2, Columns2, Edit, Copy, FileText, ChevronRight, ChevronDown, FileJson, Expand, BookOpenCheck, ExternalLink, Stethoscope, ClipboardList, PlayCircle, FlaskConical, Users } from 'lucide-react'
import Link from 'next/link'

import { Timestamp } from './ui/timestamp'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
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
import { formatAmplifyError } from "@/utils/amplify-client"
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions, configureYamlLanguage } from "@/lib/monaco-theme"

import ProcedureConversationViewer from "./procedure-conversation-viewer"
import { ParametersDisplay } from "./ui/ParametersDisplay"
import { parseParametersFromYaml } from "@/lib/parameter-parser"
import type { ParameterDefinition, ParameterValue } from "@/types/parameters"
import * as yaml from 'js-yaml'
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import remarkBreaks from "remark-breaks"
import { downloadData } from "aws-amplify/storage"
import OptimizerMetricsChart, { type DatasetView, type IterationData } from "./OptimizerMetricsChart"
import { EndOfRunReport, ReportSection } from "./OptimizationInsightsPanel"
import { OptimizerProblemItemsPanel, type NotableItemRecurrence } from "./OptimizerProblemItemsPanel"
import { CollapsibleText } from "./ui/message-utils"
import { OptimizerMetricsChartSkeleton, CycleHistoryTableSkeleton } from "./loading-skeleton"

let amplifyClient: ReturnType<typeof generateClient<Schema>> | null = null
const getAmplifyClient = () => (amplifyClient ??= generateClient<Schema>())

// Module-level stale-while-revalidate cache for procedure state
// Keyed by procedure ID; allows instant display when navigating back to a procedure
const procedureStateCache = new Map<string, { state: any; timestamp: number }>()

// Minimal fallback for YAML editor - actual templates come from procedure data
const MINIMAL_YAML_FALLBACK = `class: "BeamSearch"
# Loading procedure configuration...`

const RECENT_SERIES_COLOR = "var(--chart-1)"
const REGRESSION_SERIES_COLOR = "var(--chart-2)"

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
  const [, startTransition] = useTransition()
  const [loadedYaml, setLoadedYaml] = useState<string>('')
  const [isLoadingYaml, setIsLoadingYaml] = useState(false)
  const [sessionCount, setSessionCount] = useState(0)
  const [isConversationFullscreen, setIsConversationFullscreen] = useState(false)
  const [parameters, setParameters] = useState<ParameterDefinition[]>([])
  const [parameterValues, setParameterValues] = useState<ParameterValue>({})
  const [isLoadingProcedureState, setIsLoadingProcedureState] = useState(true)
  // Continue dialog state
  const [showContinueDialog, setShowContinueDialog] = useState(false)
  const [continueAdditionalCycles, setContinueAdditionalCycles] = useState('3')
  const [continueHint, setContinueHint] = useState('')
  const [isContinuing, setIsContinuing] = useState(false)
  // Branch dialog state
  const [showBranchDialog, setShowBranchDialog] = useState(false)
  const [branchFromCycle, setBranchFromCycle] = useState<number | null>(null)
  const [branchAdditionalCycles, setBranchAdditionalCycles] = useState('3')
  const [branchHint, setBranchHint] = useState('')
  const [isBranching, setIsBranching] = useState(false)
  const [optimizerIterations, setOptimizerIterations] = useState<IterationData[]>([])
  const [optimizerVersions, setOptimizerVersions] = useState<Array<{
    label: string
    versionId?: string
    accepted?: boolean
    isBaseline?: boolean
    recentAC1?: number | null
    recentAlignmentDelta?: number | null
    recentAccuracy?: number | null
    recentAccuracyDelta?: number | null
    recentPrecision?: number | null
    recentRecall?: number | null
    recentCostPerItem?: number | null
    regressionAC1?: number | null
    regressionAlignmentDelta?: number | null
    regressionAccuracy?: number | null
    regressionAccuracyDelta?: number | null
    regressionPrecision?: number | null
    regressionRecall?: number | null
    regressionCostPerItem?: number | null
    skipReason?: string
    disqualified?: boolean
  }>>([])
  const [cyclesTableView, setCyclesTableView] = useState<DatasetView>('overall')
  const [optimizerVersionBaseIds, setOptimizerVersionBaseIds] = useState<{ scorecardId?: string; scoreId?: string }>({})
  const [stateScorecardName, setStateScorecardName] = useState<string>('')
  const [stateScoreName, setStateScoreName] = useState<string>('')
  const [cycleInsights, setCycleInsights] = useState<any[]>([])
  const [optimizationDiagnostic, setOptimizationDiagnostic] = useState<any>(null)
  const [endOfRunReport, setEndOfRunReport] = useState<any>(null)
  const [procedureSummary, setProcedureSummary] = useState<{ progress?: string; next_steps?: string; diagnosis?: string; prescription?: string; cycle?: number } | null>(null)
  const [procedureCosts, setProcedureCosts] = useState<any | null>(null)
  const [notableItemRecurrence, setNotableItemRecurrence] = useState<NotableItemRecurrence | null>(null)
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

    // Apply cached state immediately if fresh enough (< 30s), then fetch in background
    const cached = procedureStateCache.get(procedure.id)

    const applyState = (state: any) => {
      // Identity info is critical — apply immediately
      const vscId = state.scorecard_id || procedure.scorecardId
      const vscoreId = state.score_id || procedure.scoreId
      if (vscId || vscoreId) {
        setOptimizerVersionBaseIds({ scorecardId: vscId, scoreId: vscoreId })
      }
      if (state.scorecard_name) setStateScorecardName(state.scorecard_name)
      if (state.score_name) setStateScoreName(state.score_name)
      // Costs should stream even before baseline metrics exist.
      setProcedureCosts(state.costs ?? null)

      const cycleIterations: any[] = state.iterations || []

      const firstCycle = cycleIterations[0]
      const inferredRecentBaseline = firstCycle?.recent_metrics != null && firstCycle?.recent_deltas != null
        ? {
            alignment: firstCycle.recent_metrics.alignment - firstCycle.recent_deltas.alignment,
            accuracy:  firstCycle.recent_metrics.accuracy  - firstCycle.recent_deltas.accuracy,
            precision: firstCycle.recent_metrics.precision - firstCycle.recent_deltas.precision,
            recall:    firstCycle.recent_metrics.recall    - firstCycle.recent_deltas.recall,
          }
        : null
      const inferredRegressionBaseline = firstCycle?.regression_metrics != null && firstCycle?.regression_deltas != null
        ? {
            alignment: firstCycle.regression_metrics.alignment - firstCycle.regression_deltas.alignment,
            accuracy:  firstCycle.regression_metrics.accuracy  - firstCycle.regression_deltas.accuracy,
            precision: firstCycle.regression_metrics.precision - firstCycle.regression_deltas.precision,
            recall:    firstCycle.regression_metrics.recall    - firstCycle.regression_deltas.recall,
          }
        : null
      const recentBaseline = state.recent_initial_baseline_metrics ?? inferredRecentBaseline ?? state.recent_baseline_metrics
      const regressionBaseline = state.regression_initial_baseline_metrics ?? inferredRegressionBaseline ?? state.regression_baseline_metrics
      const recentBaselineCost = state.recent_initial_baseline_cost_per_item ?? state.recent_baseline_cost_per_item ?? null
      const regressionBaselineCost = state.regression_initial_baseline_cost_per_item ?? state.regression_baseline_cost_per_item ?? null
      if (!recentBaseline && !regressionBaseline && cycleIterations.length === 0) return

      // Heavy chart/table updates — include setIsLoadingProcedureState so the skeleton
      // only disappears once the chart data is ready in the same render pass.
      startTransition(() => {
        setIsLoadingProcedureState(false)
        const iterations: IterationData[] = []
        if (recentBaseline || regressionBaseline) {
          iterations.push({
            iteration: 0,
            label: 'Baseline',
            recent_metrics: recentBaseline,
            regression_metrics: regressionBaseline,
            accepted: true,
            recent_cost_per_item: recentBaselineCost,
            regression_cost_per_item: regressionBaselineCost,
          })
        }
        for (const it of cycleIterations) {
          iterations.push({
            iteration: it.iteration, label: `Cycle ${it.iteration}`,
            score_version_id: it.score_version_id,
            recent_metrics: it.recent_metrics,
            regression_metrics: it.regression_metrics,
            recent_deltas: it.recent_deltas,
            regression_deltas: it.regression_deltas,
            recent_cost_per_item: it.recent_cost_per_item,
            regression_cost_per_item: it.regression_cost_per_item,
            accepted: it.accepted, skip_reason: it.skip_reason, disqualified: it.disqualified,
          })
        }
        setOptimizerIterations(iterations)

        // Version rows for cycles table
        const versionRows: Array<{
          label: string; versionId?: string; accepted?: boolean; isBaseline?: boolean
          recentAC1?: number | null; recentAlignmentDelta?: number | null
          recentAccuracy?: number | null; recentAccuracyDelta?: number | null
          recentPrecision?: number | null; recentRecall?: number | null
          recentCostPerItem?: number | null
          regressionAC1?: number | null; regressionAlignmentDelta?: number | null
          regressionAccuracy?: number | null; regressionAccuracyDelta?: number | null
          regressionPrecision?: number | null; regressionRecall?: number | null
          regressionCostPerItem?: number | null
          skipReason?: string; disqualified?: boolean
        }> = []
        if (state.baseline_version_id) {
          versionRows.push({
            label: 'Baseline', versionId: state.baseline_version_id, isBaseline: true,
            recentAC1: recentBaseline?.alignment ?? null,
            recentAlignmentDelta: null,
            recentAccuracy: recentBaseline?.accuracy ?? null,
            recentAccuracyDelta: null,
            recentPrecision: recentBaseline?.precision ?? null,
            recentRecall: recentBaseline?.recall ?? null,
            recentCostPerItem: recentBaselineCost,
            regressionAC1: regressionBaseline?.alignment ?? null,
            regressionAlignmentDelta: null,
            regressionAccuracy: regressionBaseline?.accuracy ?? null,
            regressionAccuracyDelta: null,
            regressionPrecision: regressionBaseline?.precision ?? null,
            regressionRecall: regressionBaseline?.recall ?? null,
            regressionCostPerItem: regressionBaselineCost,
            accepted: true,
          })
        }
        for (const it of cycleIterations) {
          versionRows.push({
            label: `Cycle ${it.iteration}`, versionId: it.score_version_id, accepted: it.accepted,
            recentAC1: it.recent_metrics?.alignment ?? null,
            recentAlignmentDelta: it.recent_deltas?.alignment ?? null,
            recentAccuracy: it.recent_metrics?.accuracy ?? null,
            recentAccuracyDelta: it.recent_deltas?.accuracy ?? null,
            recentPrecision: it.recent_metrics?.precision ?? null,
            recentRecall: it.recent_metrics?.recall ?? null,
            recentCostPerItem: it.recent_cost_per_item ?? null,
            regressionAC1: it.regression_metrics?.alignment ?? null,
            regressionAlignmentDelta: it.regression_deltas?.alignment ?? null,
            regressionAccuracy: it.regression_metrics?.accuracy ?? null,
            regressionAccuracyDelta: it.regression_deltas?.accuracy ?? null,
            regressionPrecision: it.regression_metrics?.precision ?? null,
            regressionRecall: it.regression_metrics?.recall ?? null,
            regressionCostPerItem: it.regression_cost_per_item ?? null,
            skipReason: it.skip_reason, disqualified: it.disqualified,
          })
        }
        if (versionRows.length > 0) setOptimizerVersions(versionRows)

        if (state.cycle_insights) setCycleInsights(state.cycle_insights)
        if (state.optimization_diagnostic) setOptimizationDiagnostic(state.optimization_diagnostic)
        if (state.end_of_run_report) setEndOfRunReport(state.end_of_run_report)
        if (state.procedure_summary) setProcedureSummary(state.procedure_summary)
        if (state.notable_item_recurrence) setNotableItemRecurrence(state.notable_item_recurrence)
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
      })
    }

    // Apply cached state right away for instant display
    if (cached) applyState(cached.state)

    const fetchMetrics = async () => {
      try {
        // Step 1: fetch metadata via authenticated Amplify GraphQL
        const result = await (getAmplifyClient() as any).graphql({
          query: `query GetProcedureMetadata($id: ID!) {
            getProcedure(id: $id) { metadata }
          }`,
          variables: { id: procedure.id },
        })
        const raw = result?.data?.getProcedure?.metadata
        if (!raw) return

        const metadata = typeof raw === 'string' ? JSON.parse(raw) : raw
        // Prefer the lightweight dashboard projection (tens of KB) over the
        // full runtime state (can exceed 10 MB due to exploration_results/RCA).
        let stateRef = metadata?.dashboard_state || metadata?.state || {}

        // Step 2: if state was offloaded to S3, fetch directly with authenticated Amplify Storage
        let state: any = stateRef
        if (stateRef._s3_key) {
          const stateKey = String(stateRef._s3_key)
          if (!stateKey.startsWith('procedures/') && !stateKey.startsWith('reportblocks/')) {
            throw new Error(`Unexpected optimizer state key path: ${stateKey}`)
          }
          const downloadResult = await downloadData({
            path: stateKey,
            options: { bucket: 'reportBlockDetails' as any },
          }).result
          const fullStateRaw = await downloadResult.body.text()
          state = JSON.parse(fullStateRaw)
        }

        // Cache the raw state for stale-while-revalidate on next open
        procedureStateCache.set(procedure.id, { state, timestamp: Date.now() })

        applyState(state)
      } catch (e) {
        console.error('[ProcedureTask] Failed to fetch optimizer metrics:', formatAmplifyError(e))
      } finally {
        setIsLoadingProcedureState(false)
      }
    }

    fetchMetrics()

    const isCompleted = procedure.task?.status === 'COMPLETED' || procedure.task?.status === 'FAILED'
    if (!isCompleted) {
      const interval = setInterval(fetchMetrics, 15000)
      return () => clearInterval(interval)
    }
  }, [variant, procedure.id, procedure.task?.status])

  const getRunParametersFromTaskMetadata = useCallback((): ParameterValue => {
    try {
      const rawMetadata = procedure.task?.metadata
      if (!rawMetadata) return {}
      const metadata = typeof rawMetadata === 'string' ? JSON.parse(rawMetadata) : rawMetadata
      const runParameters = metadata?.run_parameters
      if (runParameters && typeof runParameters === 'object' && !Array.isArray(runParameters)) {
        return runParameters as ParameterValue
      }
    } catch {
      // Ignore malformed metadata and fall back to YAML-derived values.
    }
    return {}
  }, [procedure.task?.metadata])

  const extractRunParametersFromYaml = useCallback((yamlContent: string): ParameterValue => {
    try {
      const parsed = yaml.load(yamlContent) as any
      const values: ParameterValue = {}

      if (parsed?.parameters && Array.isArray(parsed.parameters)) {
        parsed.parameters.forEach((param: any) => {
          if (!param || typeof param !== 'object' || !param.name) return
          if (param.value !== undefined) values[param.name] = param.value
          else if (param.default !== undefined) values[param.name] = param.default
        })
      }

      if (parsed?.params && typeof parsed.params === 'object') {
        Object.entries(parsed.params).forEach(([name, paramDef]: [string, any]) => {
          if (!paramDef || typeof paramDef !== 'object') return
          if (paramDef.value !== undefined) values[name] = paramDef.value
          else if (paramDef.default !== undefined) values[name] = paramDef.default
        })
      }

      return values
    } catch {
      return {}
    }
  }, [])

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
        const values: ParameterValue = {}
        if (config && config.parameters && Array.isArray(config.parameters)) {
          config.parameters.forEach((param: any) => {
            if (param.value !== undefined) {
              values[param.name] = param.value
            } else if (param.default !== undefined) {
              values[param.name] = param.default
            }
          })
        } else if (config && config.params && typeof config.params === 'object') {
          Object.entries(config.params).forEach(([name, paramDef]: [string, any]) => {
            if (paramDef && typeof paramDef === 'object' && paramDef.value !== undefined) {
              values[name] = paramDef.value
            } else if (paramDef && typeof paramDef === 'object' && paramDef.default !== undefined) {
              values[name] = paramDef.default
            }
          })
        }

        // Ensure parser defaults are present when no explicit value exists.
        parsedParams.forEach((param) => {
          if (values[param.name] === undefined && param.default !== undefined) {
            values[param.name] = param.default
          }
        })

        const runParameters = getRunParametersFromTaskMetadata()
        const mergedValues = { ...values, ...runParameters }
        console.log('[ProcedureTask] Parameter values (YAML + run metadata):', mergedValues)
        setParameterValues(mergedValues)
      } catch (error) {
        console.error('Error parsing parameters:', error)
        setParameters([])
        setParameterValues({})
      }
    }
  }, [loadedYaml, getRunParametersFromTaskMetadata])

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
      console.error('Error loading procedure YAML:', formatAmplifyError(error))
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

  // How many completed optimizer cycles the procedure has run
  const completedCycleCount = optimizerIterations.filter(it => it.iteration > 0).length
  const canContinueOptimization =
    completedCycleCount > 0 && procedure.task?.status !== 'RUNNING'

  const formatMetricValue = (value?: number | null) =>
    value != null ? value.toFixed(3) : '—'

  const formatDeltaValue = (value?: number | null) =>
    value != null ? (
      <span className={value >= 0 ? 'text-green-500' : 'text-red-500'}>
        {value >= 0 ? '+' : ''}{value.toFixed(3)}
      </span>
    ) : null

  const formatCostPerItem = (value?: number | null) =>
    value != null ? `$${value.toFixed(4)}` : '—'
  const formatCurrency = (value?: number | null) =>
    value != null ? `$${value.toFixed(4)}` : '—'
  const formatDiscountCurrency = (value?: number | null) =>
    value != null ? `-${formatCurrency(value)}` : '—'

  const MetricHeaderLabel = ({ label, shape, color }: { label: string; shape: 'circle' | 'square'; color: string }) => (
    <span className="inline-flex items-center gap-1">
      <svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true" className="shrink-0">
        {shape === 'circle' ? (
          <circle cx="4" cy="4" r="3" fill={color} />
        ) : (
          <rect x="1" y="1" width="6" height="6" fill={color} />
        )}
      </svg>
      <span>{label}</span>
    </span>
  )

  const isOverallCyclesView = cyclesTableView === 'overall'
  const cyclesSelectedDatasetLabel = cyclesTableView === 'recent' ? 'Recent' : 'Regression'
  const cyclesSelectedDatasetColor = cyclesTableView === 'recent' ? RECENT_SERIES_COLOR : REGRESSION_SERIES_COLOR
  const cyclesExpandedColSpan = isOverallCyclesView ? 14 : 8

  const evaluationCosts = procedureCosts?.evaluation ?? {}
  const inferenceCosts = procedureCosts?.inference ?? {}
  const costTotals = procedureCosts?.totals ?? {}
  const evaluationIncurred = Number(costTotals?.evaluation?.incurred ?? evaluationCosts?.incurred_total ?? 0)
  const evaluationReused = Number(costTotals?.evaluation?.reused ?? evaluationCosts?.reused_total ?? 0)
  const evaluationTotal = Number(costTotals?.evaluation?.total ?? evaluationCosts?.total ?? (evaluationIncurred + evaluationReused))
  const inferenceTotal = Number(costTotals?.inference?.total ?? inferenceCosts?.total ?? 0)
  const overallIncurred = Number(costTotals?.overall?.incurred ?? (evaluationIncurred + inferenceTotal))
  const overallTotal = Number(costTotals?.overall?.total ?? (evaluationTotal + inferenceTotal))
  const evaluationEntryCount = Array.isArray(evaluationCosts?.entries) ? evaluationCosts.entries.length : 0
  const inferenceEntryCount = Array.isArray(inferenceCosts?.entries) ? inferenceCosts.entries.length : 0

  // ---- Shared helpers for creating a Task and dispatching a procedure run ----
  const createTaskWithStages = async (procedureId: string, runParameters?: ParameterValue) => {
    const accountId = (procedure as any).accountId
    if (!accountId) throw new Error('No accountId on procedure')
    const metadata: Record<string, any> = {
      type: 'Procedure',
      procedure_id: procedureId,
    }
    if (runParameters && Object.keys(runParameters).length > 0) {
      metadata.run_parameters = runParameters
    }
    const taskResult = await getAmplifyClient().graphql({
      query: `
        mutation CreateTask($input: CreateTaskInput!) {
          createTask(input: $input) { id accountId type status }
        }
      `,
      variables: {
        input: {
          accountId,
          type: 'Procedure',
          status: 'PENDING',
          target: `procedure/run/${procedureId}`,
          command: `procedure run ${procedureId}`,
          description: `Procedure workflow for ${procedureId}`,
          dispatchStatus: 'PENDING',
          metadata: JSON.stringify(metadata)
        }
      }
    })
    const task = (taskResult as any).data?.createTask
    if (!task) throw new Error('Failed to create Task')
    const stages = [
      { name: 'Start', order: 1, statusMessage: 'Initializing...' },
      { name: 'Evaluation', order: 2, statusMessage: 'Running evaluation...' },
      { name: 'Hypothesis', order: 3, statusMessage: 'Generating hypotheses...' },
      { name: 'Test', order: 4, statusMessage: 'Testing...' },
      { name: 'Insights', order: 5, statusMessage: 'Generating insights...' },
    ]
    for (const stage of stages) {
      await getAmplifyClient().graphql({
        query: `
          mutation CreateTaskStage($input: CreateTaskStageInput!) {
            createTaskStage(input: $input) { id }
          }
        `,
        variables: { input: { taskId: task.id, name: stage.name, order: stage.order, status: 'PENDING', statusMessage: stage.statusMessage } }
      })
    }
    return task
  }

  const updateProcedureYaml = async (procedureId: string, newYaml: string) => {
    await getAmplifyClient().graphql({
      query: `
        mutation UpdateProcedure($input: UpdateProcedureInput!) {
          updateProcedure(input: $input) { id }
        }
      `,
      variables: { input: { id: procedureId, code: newYaml } }
    })
  }

  // ---- Continue (same procedure, more cycles) ----
  const handleContinue = async () => {
    if (!loadedYaml) {
      toast.error('Procedure configuration not loaded yet')
      return
    }
    setIsContinuing(true)
    try {
      const parsed = yaml.load(loadedYaml) as any
      const additionalCycles = parseInt(continueAdditionalCycles, 10) || 3
      const newMaxIterations = completedCycleCount + additionalCycles

      // Update params in YAML
      if (parsed.params && typeof parsed.params === 'object') {
        if (parsed.params.max_iterations) parsed.params.max_iterations.value = newMaxIterations
        if (continueHint.trim()) {
          if (!parsed.params.hint) parsed.params.hint = { type: 'string', required: false }
          parsed.params.hint.value = continueHint.trim()
        }
      }
      const updatedYaml = yaml.dump(parsed, { lineWidth: -1 })
      await updateProcedureYaml(procedure.id, updatedYaml)
      setLoadedYaml(updatedYaml)

      const runParameters = extractRunParametersFromYaml(updatedYaml)
      const task = await createTaskWithStages(procedure.id, runParameters)
      const resp = await fetch('/api/console/procedure-continue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ procedureId: procedure.id, taskId: task.id }),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error((err as any).error || `HTTP ${resp.status}`)
      }
      setShowContinueDialog(false)
      setContinueHint('')
      toast.success(`Continuing optimization for ${additionalCycles} more cycle${additionalCycles !== 1 ? 's' : ''}`)
    } catch (err) {
      console.error('Continue failed:', err)
      toast.error(`Failed to continue: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setIsContinuing(false)
    }
  }

  // ---- Branch from a specific cycle ----
  const handleBranchFromCycle = async () => {
    if (branchFromCycle == null) return
    setIsBranching(true)
    try {
      const additionalCycles = parseInt(branchAdditionalCycles, 10) || 3

      // Create a new procedure with the same YAML but reset max_iterations
      const parsed = loadedYaml ? yaml.load(loadedYaml) as any : {}
      const newMaxIterations = branchFromCycle + additionalCycles
      if (parsed.params && typeof parsed.params === 'object') {
        if (parsed.params.max_iterations) parsed.params.max_iterations.value = newMaxIterations
        if (branchHint.trim()) {
          if (!parsed.params.hint) parsed.params.hint = { type: 'string', required: false }
          parsed.params.hint.value = branchHint.trim()
        }
      }
      const branchYaml = yaml.dump(parsed, { lineWidth: -1 })

      // Create new procedure record
      const accountId = (procedure as any).accountId
      if (!accountId) throw new Error('No accountId on procedure')
      const createResult = await getAmplifyClient().graphql({
        query: `
          mutation CreateProcedure($input: CreateProcedureInput!) {
            createProcedure(input: $input) { id }
          }
        `,
        variables: {
          input: {
            accountId,
            name: (procedure as any).name ? `${(procedure as any).name} (branch from cycle ${branchFromCycle})` : `Branch from cycle ${branchFromCycle}`,
            code: branchYaml,
            featured: false,
          }
        }
      })
      const newProcedure = (createResult as any).data?.createProcedure
      if (!newProcedure) throw new Error('Failed to create branch procedure')

      // Clone state via CLI
      const cloneResp = await fetch('/api/console/procedure-clone-state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sourceProcedureId: procedure.id,
          targetProcedureId: newProcedure.id,
          truncateToCycle: branchFromCycle,
        }),
      })
      if (!cloneResp.ok) {
        const err = await cloneResp.json().catch(() => ({}))
        throw new Error((err as any).error || `State clone HTTP ${cloneResp.status}`)
      }

      // Create task and dispatch
      const runParameters = extractRunParametersFromYaml(branchYaml)
      const task = await createTaskWithStages(newProcedure.id, runParameters)
      const runResp = await fetch('/api/console/procedure-run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ procedureId: newProcedure.id, taskId: task.id }),
      })
      if (!runResp.ok) {
        const err = await runResp.json().catch(() => ({}))
        throw new Error((err as any).error || `Dispatch HTTP ${runResp.status}`)
      }

      setShowBranchDialog(false)
      setBranchHint('')
      toast.success(`Branch created from cycle ${branchFromCycle} — running ${additionalCycles} more cycle${additionalCycles !== 1 ? 's' : ''}`)
    } catch (err) {
      console.error('Branch failed:', err)
      toast.error(`Failed to branch: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setIsBranching(false)
    }
  }

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
        {/* Continue — available after any completed cycle unless a run is currently active */}
        {canContinueOptimization && (
          <>
            <DropdownMenuItem onClick={() => setShowContinueDialog(true)}>
              <PlayCircle className="mr-2 h-4 w-4" />
              Continue ({completedCycleCount} cycle{completedCycleCount !== 1 ? 's' : ''} done)
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
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


          {/* Optimizer Metrics Chart - skeleton while loading, chart when data arrives */}
          {isLoadingProcedureState ? (
            <OptimizerMetricsChartSkeleton />
          ) : optimizerIterations.length > 0 ? (
            <OptimizerMetricsChart
              iterations={optimizerIterations}
              datasetView={cyclesTableView}
              onDatasetViewChange={setCyclesTableView}
            />
          ) : null}

          {/* Procedure-level summary — updated after each cycle */}
          {procedureSummary && (() => {
            const progressText = procedureSummary.progress || procedureSummary.diagnosis || ''
            const nextText = procedureSummary.next_steps || procedureSummary.prescription || ''
            if (!progressText && !nextText) return null
            return (
              <div className="mt-4 @container">
                <div className="grid grid-cols-1 gap-3 @lg:grid-cols-2">
                  {progressText.trim() && (
                    <div className="rounded-lg border border-border/50 bg-card p-3">
                      <ReportSection
                        icon={<FileText className="h-3.5 w-3.5" />}
                        title="Progress"
                        summary={progressText}
                      />
                    </div>
                  )}
                  {nextText.trim() && (
                    <div className="rounded-lg border border-border/50 bg-card p-3">
                      <ReportSection
                        icon={<ClipboardList className="h-3.5 w-3.5" />}
                        title="Next Steps"
                        summary={nextText}
                      />
                    </div>
                  )}
                </div>
              </div>
            )
          })()}

          {procedureCosts && (
            <div className="mt-4 rounded-lg bg-card p-3">
              <h3 className="text-sm font-semibold text-muted-foreground mb-2">Cost Breakdown</h3>
              <div className="grid grid-cols-1 gap-2 @lg:grid-cols-3 text-xs">
                <div className="rounded p-2 bg-background">
                  <div className="mb-1 flex items-start justify-between gap-2">
                    <div className="text-muted-foreground/70">Evaluation</div>
                    <div className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/80">
                      {evaluationEntryCount} runs
                    </div>
                  </div>
                  <div className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5">
                    <div className="text-muted-foreground">Referenced total</div>
                    <div className="text-right tabular-nums">{formatCurrency(evaluationTotal)}</div>
                    <div className="text-emerald-700 dark:text-emerald-400">Reuse discount</div>
                    <div className="text-right tabular-nums text-emerald-700 dark:text-emerald-400">{formatDiscountCurrency(evaluationReused)}</div>
                    <div className="text-muted-foreground">Spent this run</div>
                    <div className="text-right font-medium tabular-nums">{formatCurrency(evaluationIncurred)}</div>
                  </div>
                </div>
                <div className="rounded p-2 bg-background">
                  <div className="mb-1 flex items-start justify-between gap-2">
                    <div className="text-muted-foreground/70">Optimization Inference</div>
                    <div className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/80">
                      {inferenceEntryCount} LLM calls
                    </div>
                  </div>
                  <div className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5">
                    <div className="text-muted-foreground">Spent this run</div>
                    <div className="text-right font-medium tabular-nums">{formatCurrency(inferenceTotal)}</div>
                  </div>
                </div>
                <div className="rounded p-2 bg-background">
                  <div className="text-muted-foreground/70 mb-1">Procedure Total</div>
                  <div className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5">
                    <div className="text-muted-foreground">Referenced total</div>
                    <div className="text-right tabular-nums">{formatCurrency(overallTotal)}</div>
                    <div className="text-emerald-700 dark:text-emerald-400">Reuse discount</div>
                    <div className="text-right tabular-nums text-emerald-700 dark:text-emerald-400">{formatDiscountCurrency(evaluationReused)}</div>
                    <div className="text-muted-foreground">Spent this run</div>
                    <div className="text-right font-medium tabular-nums">{formatCurrency(overallIncurred)}</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Cycles table - skeleton while loading, table when data arrives */}
          {isLoadingProcedureState ? (
            <CycleHistoryTableSkeleton />
          ) : optimizerVersions.length > 0 ? (
            <div className="mt-4 rounded-lg bg-card p-3">
              <h3 className="text-sm font-semibold text-muted-foreground mb-2">Cycles</h3>
              <table className="w-full text-xs border-separate border-spacing-y-1">
                <thead>
                  {isOverallCyclesView ? (
                    <>
                      <tr className="text-muted-foreground/60">
                        <th className="px-1 py-0.5 text-left font-normal"></th>
                        <th className="px-1 py-0.5 text-left font-normal"></th>
                        <th className="px-1 py-0.5 text-left font-normal" colSpan={5} style={{ color: RECENT_SERIES_COLOR }}>Recent</th>
                        <th className="px-1 py-0.5 text-left font-normal" colSpan={5} style={{ color: REGRESSION_SERIES_COLOR }}>Regression</th>
                        <th className="px-1 py-0.5 font-normal"></th>
                        <th className="px-1 py-0.5 font-normal"></th>
                      </tr>
                      <tr className="text-muted-foreground/40">
                        <th className="px-1 py-0 font-normal"></th>
                        <th className="px-1 py-0 font-normal"></th>
                        <th className="px-1 py-0 text-left font-normal">
                          <MetricHeaderLabel label="AC1" shape="circle" color={RECENT_SERIES_COLOR} />
                        </th>
                        <th className="px-1 py-0 text-left font-normal">Δ</th>
                        <th className="px-1 py-0 text-left font-normal">
                          <MetricHeaderLabel label="Acc" shape="square" color={RECENT_SERIES_COLOR} />
                        </th>
                        <th className="px-1 py-0 text-left font-normal">Δ</th>
                        <th className="px-1 py-0 text-left font-normal">Cost/item</th>
                        <th className="px-1 py-0 text-left font-normal">
                          <MetricHeaderLabel label="AC1" shape="circle" color={REGRESSION_SERIES_COLOR} />
                        </th>
                        <th className="px-1 py-0 text-left font-normal">Δ</th>
                        <th className="px-1 py-0 text-left font-normal">
                          <MetricHeaderLabel label="Acc" shape="square" color={REGRESSION_SERIES_COLOR} />
                        </th>
                        <th className="px-1 py-0 text-left font-normal">Δ</th>
                        <th className="px-1 py-0 text-left font-normal">Cost/item</th>
                        <th className="px-1 py-0 font-normal"></th>
                        <th className="px-1 py-0 font-normal"></th>
                      </tr>
                    </>
                  ) : (
                    <>
                      <tr className="text-muted-foreground/60">
                        <th className="px-1 py-0.5 text-left font-normal"></th>
                        <th className="px-1 py-0.5 text-left font-normal"></th>
                        <th className="px-1 py-0.5 text-left font-normal" colSpan={4} style={{ color: cyclesSelectedDatasetColor }}>{cyclesSelectedDatasetLabel}</th>
                        <th className="px-1 py-0.5 font-normal"></th>
                        <th className="px-1 py-0.5 font-normal"></th>
                      </tr>
                      <tr className="text-muted-foreground/40">
                        <th className="px-1 py-0 font-normal"></th>
                        <th className="px-1 py-0 font-normal"></th>
                        <th className="px-1 py-0 text-left font-normal">
                          <MetricHeaderLabel label="AC1" shape="circle" color={cyclesSelectedDatasetColor} />
                        </th>
                        <th className="px-1 py-0 text-left font-normal">
                          <MetricHeaderLabel label="Acc" shape="square" color={cyclesSelectedDatasetColor} />
                        </th>
                        <th className="px-1 py-0 text-left font-normal">P</th>
                        <th className="px-1 py-0 text-left font-normal">R</th>
                        <th className="px-1 py-0 font-normal"></th>
                        <th className="px-1 py-0 font-normal"></th>
                      </tr>
                    </>
                  )}
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
                          className={cn('bg-background', details ? 'cursor-pointer hover:bg-accent/50' : '')}
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
                              {details?.exploration_results?.length > 0 && (
                                <span className="text-muted-foreground/40 text-xs">
                                  {details.exploration_results.filter((er: any) => er.succeeded).length}/{details.exploration_results.length}
                                </span>
                              )}
                            </span>
                          </td>
                          <td className="px-1 py-0.5 whitespace-nowrap">
                            {row.isBaseline ? (
                              <Badge variant="pill" className="text-xs px-1 py-0 font-normal bg-neutral text-primary-foreground">Baseline</Badge>
                            ) : row.skipReason ? (
                              <Badge variant="pill" className="text-xs px-1 py-0 font-normal bg-warning text-primary-foreground">Skipped</Badge>
                            ) : row.disqualified ? (
                              <Badge variant="pill" className="text-xs px-1 py-0 font-normal bg-false text-primary-foreground">Disqualified</Badge>
                            ) : row.accepted ? (
                              <Badge variant="pill" className="text-xs px-1 py-0 font-normal bg-true text-primary-foreground">Accepted</Badge>
                            ) : (
                              <Badge variant="pill" className="text-xs px-1 py-0 font-normal bg-false text-primary-foreground">Rejected</Badge>
                            )}
                          </td>
                          {isOverallCyclesView ? (
                            <>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatMetricValue(row.recentAC1)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right">
                                {formatDeltaValue(row.recentAlignmentDelta)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatMetricValue(row.recentAccuracy)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right">
                                {formatDeltaValue(row.recentAccuracyDelta)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatCostPerItem(row.recentCostPerItem)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatMetricValue(row.regressionAC1)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right">
                                {formatDeltaValue(row.regressionAlignmentDelta)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatMetricValue(row.regressionAccuracy)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right">
                                {formatDeltaValue(row.regressionAccuracyDelta)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatCostPerItem(row.regressionCostPerItem)}
                              </td>
                            </>
                          ) : cyclesTableView === 'recent' ? (
                            <>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatMetricValue(row.recentAC1)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatMetricValue(row.recentAccuracy)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatMetricValue(row.recentPrecision)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatMetricValue(row.recentRecall)}
                              </td>
                            </>
                          ) : (
                            <>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatMetricValue(row.regressionAC1)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatMetricValue(row.regressionAccuracy)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatMetricValue(row.regressionPrecision)}
                              </td>
                              <td className="px-1 py-0.5 whitespace-nowrap tabular-nums text-right text-muted-foreground">
                                {formatMetricValue(row.regressionRecall)}
                              </td>
                            </>
                          )}
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
                            <td colSpan={cyclesExpandedColSpan} className="px-2 py-2 bg-accent/30 rounded">
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
                                          <details key={j} className="rounded bg-background">
                                            <summary className="flex items-center gap-2 text-xs px-2 py-1 cursor-pointer hover:bg-accent/30">
                                              <span className="text-muted-foreground truncate flex-1" title={er.hypothesis?.name || `Hyp ${er.index}`}>
                                                {er.hypothesis?.name || `Hypothesis ${er.index}`}
                                              </span>
                                              {er.succeeded ? (
                                                <Badge variant="pill" className="text-xs px-1 py-0 font-normal flex-shrink-0 bg-true text-primary-foreground">Pass</Badge>
                                              ) : (
                                                <Badge variant="pill" className="text-xs px-1 py-0 font-normal flex-shrink-0 bg-false text-primary-foreground">Fail</Badge>
                                              )}
                                              <span className="whitespace-nowrap flex-shrink-0">
                                                <span className="text-muted-foreground/60 mr-1">Recent</span>
                                                {er.fb_deltas?.alignment != null ? (
                                                  <span className={er.fb_deltas.alignment >= 0 ? 'text-green-500' : 'text-red-500'}>
                                                    {er.fb_deltas.alignment >= 0 ? '+' : ''}{er.fb_deltas.alignment.toFixed(3)}
                                                  </span>
                                                ) : '—'}
                                              </span>
                                              <span className="whitespace-nowrap flex-shrink-0">
                                                <span className="text-muted-foreground/60 mr-1">Regression</span>
                                                {er.acc_deltas?.alignment != null ? (
                                                  <span className={er.acc_deltas.alignment >= 0 ? 'text-green-500' : 'text-red-500'}>
                                                    {er.acc_deltas.alignment >= 0 ? '+' : ''}{er.acc_deltas.alignment.toFixed(3)}
                                                  </span>
                                                ) : '—'}
                                              </span>
                                            </summary>
                                            {hypDesc && (
                                              <div className="px-2 py-1.5 border-t border-border/30">
                                                <div className="prose prose-sm max-w-none text-muted-foreground prose-p:text-muted-foreground prose-strong:text-muted-foreground prose-headings:text-muted-foreground prose-li:text-muted-foreground [&_p]:text-xs [&_li]:text-xs">
                                                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{hypDesc}</ReactMarkdown>
                                                </div>
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
                                            Recent <span className={details.dual_synthesis.strategy_a.recent_delta >= 0 ? 'text-green-500' : 'text-red-500'}>
                                              {details.dual_synthesis.strategy_a.recent_delta >= 0 ? '+' : ''}{details.dual_synthesis.strategy_a.recent_delta?.toFixed(3)}
                                            </span>
                                            {' '}Regression <span className={details.dual_synthesis.strategy_a.regression_delta >= 0 ? 'text-green-500' : 'text-red-500'}>
                                              {details.dual_synthesis.strategy_a.regression_delta >= 0 ? '+' : ''}{details.dual_synthesis.strategy_a.regression_delta?.toFixed(3)}
                                            </span>
                                          </span>
                                        </div>
                                      )}
                                      {details.dual_synthesis.strategy_b && (
                                        <div className={`border rounded px-2 py-1 ${details.synthesis_strategy === 'B' ? 'border-primary/50 bg-primary/5' : 'border-border/50'}`}>
                                          <span className="font-medium">B (arc-focused)</span>
                                          <span className="ml-2 text-muted-foreground">
                                            Recent <span className={details.dual_synthesis.strategy_b.recent_delta >= 0 ? 'text-green-500' : 'text-red-500'}>
                                              {details.dual_synthesis.strategy_b.recent_delta >= 0 ? '+' : ''}{details.dual_synthesis.strategy_b.recent_delta?.toFixed(3)}
                                            </span>
                                            {' '}Regression <span className={details.dual_synthesis.strategy_b.regression_delta >= 0 ? 'text-green-500' : 'text-red-500'}>
                                              {details.dual_synthesis.strategy_b.regression_delta >= 0 ? '+' : ''}{details.dual_synthesis.strategy_b.regression_delta?.toFixed(3)}
                                            </span>
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                    {details.dual_synthesis.selection_reason && (
                                      <div className="prose prose-sm max-w-none mt-1 text-muted-foreground/60 prose-p:text-muted-foreground/60 [&_p]:text-xs">
                                        <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{details.dual_synthesis.selection_reason}</ReactMarkdown>
                                      </div>
                                    )}
                                  </div>
                                )}
                                {details.synthesis_reasoning && !details.synthesis_reasoning.includes('UsageStats') && (
                                  <div>
                                    <span className="text-muted-foreground/70 text-xs block mb-1">Synthesis reasoning:</span>
                                    <div className="prose prose-sm max-w-none text-muted-foreground prose-p:text-muted-foreground prose-strong:text-muted-foreground prose-headings:text-muted-foreground prose-li:text-muted-foreground [&_p]:text-xs [&_li]:text-xs">
                                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{details.synthesis_reasoning}</ReactMarkdown>
                                    </div>
                                  </div>
                                )}
                                {(() => {
                                  const insight = cycleInsights.find((ci: any) => ci.cycle === cycleNum)
                                  if (!insight) return null

                                  // Prefer new three-audience format fields
                                  const execSummary = insight.executive_summary || ''
                                  const labReport = insight.lab_report || ''
                                  const smeAgenda = insight.sme_agenda || ''
                                  const useNewFormat = execSummary || labReport || smeAgenda

                                  if (useNewFormat) {
                                    return (
                                      <div className="mt-1 space-y-2">
                                        {execSummary && (
                                          <div className="rounded-lg border border-border/50 bg-card p-3">
                                            <ReportSection
                                              icon={<FileText className="h-3.5 w-3.5" />}
                                              title="Executive Summary"
                                              summary={execSummary}
                                            />
                                          </div>
                                        )}
                                        <div className="@container">
                                        <div className="grid grid-cols-1 gap-2 @lg:grid-cols-2">
                                          {labReport && (
                                            <div className="rounded-lg border border-border/50 bg-card p-3">
                                              <ReportSection
                                                icon={<FlaskConical className="h-3.5 w-3.5" />}
                                                title="Lab Report"
                                                summary={labReport}
                                              />
                                            </div>
                                          )}
                                          {smeAgenda && (
                                            <div className="rounded-lg border border-border/50 bg-card p-3">
                                              <ReportSection
                                                icon={<Users className="h-3.5 w-3.5" />}
                                                title="SME Agenda"
                                                summary={smeAgenda}
                                              />
                                            </div>
                                          )}
                                        </div>
                                        </div>
                                      </div>
                                    )
                                  }

                                  // Legacy format: parse diagnosis/prescription from stored fields or analysis text
                                  let diagSummary = insight.diagnosis_summary || ''
                                  let prescSummary = insight.prescription_summary || ''
                                  let diagDetail = ''
                                  let prescDetail = ''
                                  if (insight.analysis) {
                                    const diagSummaryMatch = insight.analysis.match(/## DIAGNOSIS SUMMARY\n([\s\S]*?)(?=\n## DIAGNOSIS DETAIL|\n## PRESCRIPTION|\s*$)/)
                                    if (diagSummaryMatch && !diagSummary.trim()) diagSummary = diagSummaryMatch[1].trim()
                                    const prescSummaryMatch = insight.analysis.match(/## PRESCRIPTION SUMMARY\n([\s\S]*?)(?=\n## PRESCRIPTION DETAIL|\n===|\s*$)/)
                                    if (prescSummaryMatch && !prescSummary.trim()) prescSummary = prescSummaryMatch[1].trim()
                                    const diagDetailMatch = insight.analysis.match(/## DIAGNOSIS DETAIL\n([\s\S]*?)(?=\n## PRESCRIPTION|\s*$)/)
                                    if (diagDetailMatch) diagDetail = diagDetailMatch[1].trim()
                                    const prescDetailMatch = insight.analysis.match(/## PRESCRIPTION DETAIL\n([\s\S]*?)(?=\n===|\s*$)/)
                                    if (prescDetailMatch) prescDetail = prescDetailMatch[1].trim()
                                  }
                                  const hasDiag = diagSummary.trim().length > 0
                                  const hasPresc = prescSummary.trim().length > 0
                                  if (hasDiag || hasPresc) {
                                    return (
                                      <div className="@container mt-1">
                                        <div className="grid grid-cols-1 gap-3 @lg:grid-cols-2">
                                          {hasDiag && (
                                            <div className="rounded-lg border border-border/50 bg-card p-3">
                                              <ReportSection
                                                icon={<Stethoscope className="h-3.5 w-3.5" />}
                                                title="Diagnosis"
                                                summary={diagSummary}
                                                detail={diagDetail}
                                              />
                                            </div>
                                          )}
                                          {hasPresc && (
                                            <div className="rounded-lg border border-border/50 bg-card p-3">
                                              <ReportSection
                                                icon={<ClipboardList className="h-3.5 w-3.5" />}
                                                title="Prescription"
                                                summary={prescSummary}
                                                detail={prescDetail}
                                              />
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    )
                                  }
                                  // Fallback: show full analysis text when structured fields not available
                                  return insight.analysis ? (
                                    <div>
                                      <span className="text-muted-foreground/70 text-xs block mb-1">Cycle analysis:</span>
                                      <div className="text-xs text-muted-foreground">
                                        <CollapsibleText
                                          content={insight.analysis}
                                          maxLines={40}
                                          className="whitespace-pre-wrap break-words text-xs text-muted-foreground"
                                        />
                                      </div>
                                    </div>
                                  ) : null
                                })()}
                                {/* Branch button — hidden inside expanded details */}
                                {cycleNum != null && (
                                  <div className="pt-1 border-t border-border/30">
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-6 text-xs text-muted-foreground/60 hover:text-muted-foreground px-2"
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        setBranchFromCycle(cycleNum)
                                        setBranchAdditionalCycles('3')
                                        setBranchHint('')
                                        setShowBranchDialog(true)
                                      }}
                                    >
                                      Branch from cycle {cycleNum}…
                                    </Button>
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
          ) : null}

          {/* Problem item tracker — items with recurrent misclassifications */}
          {notableItemRecurrence && (
            <OptimizerProblemItemsPanel notableItems={notableItemRecurrence} />
          )}

          {/* End-of-run diagnosis and prescription */}
          {endOfRunReport && <EndOfRunReport report={endOfRunReport} />}

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
              <div className="h-[600px]">
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
    <>
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

      {/* Continue dialog */}
      <Dialog open={showContinueDialog} onOpenChange={setShowContinueDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Continue Optimization</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="text-sm text-muted-foreground">
              {completedCycleCount} cycle{completedCycleCount !== 1 ? 's' : ''} completed.
              The optimizer will resume from where it left off — no re-running of baselines or dataset build.
            </p>
            <div className="space-y-2">
              <Label htmlFor="continue-cycles">Additional cycles</Label>
              <Select value={continueAdditionalCycles} onValueChange={setContinueAdditionalCycles}>
                <SelectTrigger id="continue-cycles">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 5, 10].map(n => (
                    <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="continue-hint">Instructions (optional)</Label>
              <Textarea
                id="continue-hint"
                placeholder="e.g. Focus on reducing false positives in the 'Yes' class"
                value={continueHint}
                onChange={e => setContinueHint(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowContinueDialog(false)} disabled={isContinuing}>
              Cancel
            </Button>
            <Button onClick={handleContinue} disabled={isContinuing}>
              {isContinuing ? 'Starting...' : 'Continue Optimization'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Branch dialog */}
      <Dialog open={showBranchDialog} onOpenChange={setShowBranchDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Branch from Cycle {branchFromCycle}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="text-sm text-muted-foreground">
              Creates a new procedure starting from cycle {branchFromCycle}, with a copy of
              the accumulated state up to that point.
            </p>
            <div className="space-y-2">
              <Label htmlFor="branch-cycles">Additional cycles to run</Label>
              <Select value={branchAdditionalCycles} onValueChange={setBranchAdditionalCycles}>
                <SelectTrigger id="branch-cycles">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 5, 10].map(n => (
                    <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="branch-hint">Instructions (optional)</Label>
              <Textarea
                id="branch-hint"
                placeholder="e.g. Try structural changes to the prompt"
                value={branchHint}
                onChange={e => setBranchHint(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowBranchDialog(false)} disabled={isBranching}>
              Cancel
            </Button>
            <Button onClick={handleBranchFromCycle} disabled={isBranching}>
              {isBranching ? 'Creating branch...' : 'Create Branch'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
