import React, { useRef, useState, useEffect, useMemo, useCallback } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { FlaskConical, Square, X, Split, ChevronLeft, MoreHorizontal, MessageSquareCode, Share, Trash2, ExternalLink, AlertTriangle } from 'lucide-react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { CardButton } from '@/components/CardButton'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { toast } from '@/components/ui/use-toast'
import MetricsGauges from '@/components/MetricsGauges'
import { TaskStatus, type TaskStageConfig } from '@/components/ui/task-status'
import { ProgressBarTiming } from '@/components/ui/progress-bar-timing'
import { ConfusionMatrix, type ConfusionMatrixData, type ConfusionMatrixRow } from '@/components/confusion-matrix'
import ClassDistributionVisualizer from '@/components/ClassDistributionVisualizer'
import PredictedClassDistributionVisualizer from '@/components/PredictedClassDistributionVisualizer'
import { EvaluationTaskScoreResults } from './EvaluationTaskScoreResults'
import { TopicList, type Topic } from '@/components/ui/topic-list'
import type { Schema } from "@/amplify/data/resource"
import MetricsGaugesExplanation from '@/components/MetricsGaugesExplanation'
import { useResizeObserver } from '@/hooks/use-resize-observer'
import { BaseTaskData } from '@/types/base'
import { EvaluationListAccuracyBar } from '@/components/EvaluationListAccuracyBar'
import isEqual from 'lodash/isEqual'
import { ScoreResultComponent, ScoreResultData } from '@/components/ui/score-result'
import { cn } from '@/lib/utils'
import { Timestamp } from '@/components/ui/timestamp'
import Link from 'next/link'
import { getClient } from '@/utils/amplify-client'
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import remarkBreaks from "remark-breaks"

const parseJsonDeep = (value: unknown): unknown => {
  let current = value
  for (let i = 0; i < 3; i += 1) {
    if (typeof current !== 'string') return current
    const trimmed = current.trim()
    if (!trimmed) return current
    try {
      current = JSON.parse(trimmed)
    } catch {
      return current
    }
  }
  return current
}

export interface EvaluationMetric {
  name: string
  value: number
  unit?: string
  maximum?: number
  priority: boolean
}

interface Distribution {
  label: string
  count: number
}

interface ScoreResult {
  id: string
  value: string | number
  confidence: number | null
  explanation: string | null
  metadata: {
    human_label: string | null
    correct: boolean
    human_explanation: string | null
    text: string | null
  }
  trace: any | null
  itemId: string | null
  itemIdentifiers?: Array<{
    name: string
    value: string
    url?: string
  }> | null
  feedbackItem: {
    editCommentValue: string | null
  } | null
}

interface TaskStage {
  id: string;
  name: string;
  order: number;
  status: string;
  statusMessage?: string;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  processedItems?: number;
  totalItems?: number;
}

interface TaskData {
  id: string;
  accountId: string;
  type: string;
  status: string;
  target: string;
  command: string;
  completedAt?: string;
  startedAt?: string;
  dispatchStatus?: 'DISPATCHED';
  celeryTaskId?: string;
  workerNodeId?: string;
  description?: string;
  metadata?: any;
  createdAt?: string;
  estimatedCompletionAt?: string;
  errorMessage?: string;
  errorDetails?: string;
  currentStageId?: string;
  stages?: {
    items: TaskStage[];
    nextToken?: string | null;
  };
}

export interface EvaluationTaskData extends BaseTaskData {
  id: string
  title: string
  command?: string
  accuracy: number | null
  metrics: EvaluationMetric[]
  metricsExplanation?: string | null
  processedItems: number
  totalItems: number
  progress: number
  inferences: number
  cost: number | null
  status: string
  elapsedSeconds: number | null
  estimatedRemainingSeconds: number | null
  startedAt?: string | undefined
  errorMessage?: string
  errorDetails?: any | null
  confusionMatrix?: {
    matrix: number[][] | null
    labels: string[] | null
  } | null
  scoreGoal?: string | null
  datasetClassDistribution?: Array<Distribution>
  isDatasetClassDistributionBalanced?: boolean | null
  predictedClassDistribution?: Array<Distribution>
  isPredictedClassDistributionBalanced?: boolean | null
  scoreResults?: ScoreResult[]
  selectedScoreResult?: Schema['ScoreResult']['type'] | null
  task?: TaskData | null
  universalCode?: string | null
  parameters?: string | null
  dataSetId?: string | null
}

export interface EvaluationTaskProps extends Omit<BaseTaskProps<EvaluationTaskData>, 'variant'> {
  variant?: 'grid' | 'detail'
  // Added task output display support
  task: {
    id: string
    type: string
    scorecard: string
    score: string
    time: string
    summary?: string
    description?: string
    command?: string
    output?: string // Universal Code YAML output
    attachedFiles?: string[] // Array of S3 file keys for attachments
    stdout?: string // Task stdout output
    stderr?: string // Task stderr output
    data: EvaluationTaskData
    stages?: TaskStageConfig[]
    currentStageName?: string
    processedItems?: number
    totalItems?: number
    startedAt?: string
    estimatedCompletionAt?: string
    status?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
    dispatchStatus?: 'DISPATCHED'
    celeryTaskId?: string
    workerNodeId?: string
    completedAt?: string
    errorMessage?: string
    statusMessage?: string
    scorecardId?: string
    scoreId?: string
    scoreVersionId?: string
    dataSetId?: string
  }
  selectedScoreResultId?: string | null
  onSelectScoreResult?: (id: string | null) => void
  extra?: boolean
  isSelected?: boolean
  commandDisplay?: 'hide' | 'show' | 'full'
  onShare?: () => void
  onDelete?: (evaluationId: string) => void
}

type MisclassificationCategory =
  | 'score_configuration_problem'
  | 'information_gap'
  | 'guideline_gap_requires_sme'
  | 'mechanical_malfunction'

type MisclassificationRedFlag = {
  flag?: string
  severity?: 'high' | 'medium' | 'low' | string
  message?: string
}

type MisclassificationCategorySummary = {
  category_summary_text?: string
  top_patterns?: Array<{ pattern?: string; count?: number }>
  representative_evidence?: Array<{
    feedback_item_id?: string
    item_id?: string
    source?: string
    quote_or_fact?: string
  }>
  item_count?: number
}

type MisclassificationPrimaryNextAction = {
  action?: 'bug_investigation' | 'data_remediation' | 'sme_guideline_clarification' | 'score_configuration_optimization' | string
  confidence?: 'high' | 'medium' | 'low' | string
  reasons?: string[]
}

type OptimizationApplicability = {
  status?: 'applicable' | 'limited' | 'blocked' | string
  reason?: string
}

type CandidateAssessmentStageReference = {
  stage_key?: string
  baseline_evaluation_id?: string
  candidate_evaluation_id?: string
  baseline_status?: string
  candidate_status?: string
  delta_ac1?: number
  delta_value_score?: number
}

type CandidateAssessmentCompactSummary = {
  schema_version?: string
  attachment_key?: string
  scorecard_id?: string
  score_id?: string
  baseline_score_version_id?: string
  candidate_score_version_id?: string
  decision?: string
  decision_reason?: string
  decision_confidence?: string
  baseline_generalization_gap?: number
  candidate_generalization_gap?: number
  generalization_gap_delta?: number
  random_delta_mean?: number
  random_delta_stddev?: number
  primary_next_action?: string
  stage_references?: CandidateAssessmentStageReference[]
}

type MisclassificationAnalysis = {
  item_classifications_all?: Array<{
    topic_id?: number | string
    topic_label?: string
    feedback_item_id?: string
    item_id?: string
    timestamp?: string
    predicted_value?: string
    correct_value?: string
    primary_category?: MisclassificationCategory | string
    confidence?: string
    rationale_short?: string
    rationale_full?: string
    rationale_paragraph?: string
    evidence_quote?: string
    config_fixability?: string
    evidence_snippets?: Array<{ source?: string; quote_or_fact?: string }>
    mechanical_subtype?: string | null
    mechanical_details?: string | null
    information_gap_subtype?: string | null
    detailed_cause?: string
    suggested_fix?: string
  }>
  analysis_scope?: {
    candidate_items_total?: number
    classified_items_total?: number
    texts_analyzed_total?: number
    topics_found?: number
    topic_assignment_scope?: string
    topic_assignment_unavailable_count?: number
  }
  category_diagnostics?: {
    information_gap?: {
      item_count?: number
      missing_or_degraded_primary_input_count?: number
      missing_or_degraded_primary_input_share?: number
      missing_required_context_count?: number
      missing_required_context_share?: number
      diagnostic_summary?: string
    }
  }
  category_totals?: Partial<Record<MisclassificationCategory, number>>
  category_summaries?: Partial<Record<MisclassificationCategory, MisclassificationCategorySummary>>
  mechanical_subtype_totals?: Record<string, number>
  primary_next_action?: MisclassificationPrimaryNextAction
  optimization_applicability?: OptimizationApplicability
  topic_category_breakdown?: Array<{
    topic_id?: number | string
    topic_label?: string
    topic_primary_category?: string
    topic_category_purity?: number
    member_count?: number
    category_counts?: Record<string, number>
  }>
  max_category_summary_items_used?: number
  overall_assessment?: {
    total_items?: number
    predominant_category?: MisclassificationCategory | string
    score_fix_candidate_items?: number
  }
  evaluation_red_flags?: MisclassificationRedFlag[]
}

type RootCauseData = {
  topics?: Topic[] | null
  misclassification_analysis?: MisclassificationAnalysis | null
  overall_explanation?: string | null
  overall_improvement_suggestion?: string | null
}

const MISCLASSIFICATION_CATEGORY_CONFIG: Array<{
  key: MisclassificationCategory
  label: string
  shortLabel: string
  colorClass: string
}> = [
  {
    key: 'score_configuration_problem',
    label: 'Score configuration',
    shortLabel: 'Score',
    colorClass: 'bg-chart-1',
  },
  {
    key: 'information_gap',
    label: 'Information gap',
    shortLabel: 'Info',
    colorClass: 'bg-chart-2',
  },
  {
    key: 'guideline_gap_requires_sme',
    label: 'SME guideline gap',
    shortLabel: 'SME',
    colorClass: 'bg-chart-3',
  },
  {
    key: 'mechanical_malfunction',
    label: 'Mechanical malfunction',
    shortLabel: 'System',
    colorClass: 'bg-chart-4',
  },
]

const getMisclassificationCategoryLabel = (category?: string | null): string => {
  if (!category) return 'Unavailable'
  return (
    MISCLASSIFICATION_CATEGORY_CONFIG.find(config => config.key === category)?.label ??
    category.replace(/_/g, ' ')
  )
}

const getMisclassificationAssessment = (category?: string | null): string => {
  switch (category) {
    case 'score_configuration_problem':
      return 'Optimization likely to help'
    case 'information_gap':
      return 'Upstream data remediation likely needed'
    case 'guideline_gap_requires_sme':
      return 'SME guideline clarification likely needed'
    case 'mechanical_malfunction':
      return 'System malfunction investigation needed'
    default:
      return 'Insufficient evidence for a clear recommendation'
  }
}

const getPrimaryNextActionLabel = (action?: string | null): string => {
  switch (action) {
    case 'bug_investigation':
      return 'Bug investigation'
    case 'data_remediation':
      return 'Data remediation'
    case 'sme_guideline_clarification':
      return 'SME guideline clarification'
    case 'score_configuration_optimization':
      return 'Score-configuration optimization'
    default:
      return 'Unavailable'
  }
}

const getAssessmentDecisionLabel = (decision?: string | null): string => {
  switch ((decision ?? '').toLowerCase()) {
    case 'accept':
      return 'Accept'
    case 'reject':
      return 'Reject'
    case 'inconclusive':
      return 'Inconclusive'
    default:
      return 'Unavailable'
  }
}

const getAssessmentStageLabel = (stageKey?: string | null): string => {
  switch ((stageKey ?? '').toLowerCase()) {
    case 'deterministic_reference':
      return 'Deterministic reference'
    case 'random_iteration':
      return 'Random iteration (n=50)'
    case 'random_gate':
      return 'Random gate (n=200)'
    default:
      return stageKey ? stageKey.replace(/_/g, ' ') : 'Unknown stage'
  }
}

const formatSignedMetric = (value?: number | null, digits = 3): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'N/A'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(digits)}`
}

const formatMetric = (value?: number | null, digits = 3): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'N/A'
  return value.toFixed(digits)
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = seconds % 60
  
  if (hours > 0) {
    return `${hours}h ${minutes}m ${remainingSeconds}s`
  }
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`
  }
  return `${remainingSeconds}s`
}

function computeIsBalanced(distribution: { label: string, count: number }[] | null | undefined): boolean | null {
  if (!distribution || distribution.length <= 1) return null
  
  const total = distribution.reduce((sum, item) => sum + item.count, 0)
  const expectedCount = total / distribution.length
  const tolerance = 0.2 // 20% tolerance
  
  return distribution.every(item => 
    Math.abs(item.count - expectedCount) <= expectedCount * tolerance
  )
}

const mapTaskStatus = (status: string | undefined | null): 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' => {
  if (!status) return 'PENDING';
  const upperStatus = status.toUpperCase();
  switch (upperStatus) {
    case 'PENDING':
    case 'RUNNING':
    case 'COMPLETED':
    case 'FAILED':
      return upperStatus;
    case 'DONE':
      return 'COMPLETED';
    case 'ERROR':
      return 'FAILED';
    default:
      return 'PENDING';
  }
}

const getStatusMessage = (data: EvaluationTaskData) => {
  // If we have task data with stages, use that
  if (data.task?.stages?.items?.length) {
    // If task failed, show the failed stage's message
    if (data.task.status === 'FAILED') {
      const failedStage = data.task.stages.items.find(stage => stage.status === 'FAILED')
      return failedStage?.statusMessage;
    }

    // If task completed, show the last stage's message
    if (data.task.status === 'COMPLETED') {
      return [...data.task.stages.items]
        .reverse()
        .find(stage => stage.statusMessage)?.statusMessage;
    }

    // If there's a running stage, use its message
    const runningStage = data.task.stages.items.find(stage => stage.status === 'RUNNING');
    if (runningStage?.statusMessage) {
      return runningStage.statusMessage;
    }

    // If no running stage message, find the last non-pending stage with a message
    const lastActiveStage = [...data.task.stages.items]
      .sort((a, b) => b.order - a.order)
      .find(stage => stage.status !== 'PENDING' && stage.statusMessage);
    if (lastActiveStage?.statusMessage) {
      return lastActiveStage.statusMessage;
    }

    // If all stages are pending, use the first stage's message
    if (data.task.stages.items.every(stage => stage.status === 'PENDING')) {
      const firstStage = [...data.task.stages.items].sort((a, b) => a.order - b.order)[0];
      return firstStage?.statusMessage;
    }
  }
  
  // Otherwise, construct a status message from the evaluation data
  if (data.status === 'COMPLETED') {
    return `Processed ${data.processedItems} of ${data.totalItems} items`;
  }
  if (data.status === 'FAILED') {
    return data.errorMessage || 'Task failed';
  }
  if (data.status === 'RUNNING') {
    return `Processing ${data.processedItems} of ${data.totalItems} items...`;
  }
  return undefined;
}

const GridContent = React.memo(({ data, extra, isSelected }: { 
  data: EvaluationTaskData; 
  extra?: boolean;
  isSelected?: boolean;
}) => {


  const progress = useMemo(() => 
    data.processedItems && data.totalItems ? 
      Math.round((data.processedItems / data.totalItems) * 100) : 0
  , [data.processedItems, data.totalItems]);
  
  const accuracy = data.accuracy ?? 0;

  // Use already-transformed score results directly
  const parsedScoreResults = useMemo(() => {
    // data.scoreResults is already transformed by transformEvaluation
    const rawResults = Array.isArray(data.scoreResults) ? data.scoreResults : [];
    // Dedupe by id to avoid duplicates and ensure stable list when re-rendering
    const uniqueMap = new Map<string, any>();
    for (const r of rawResults) {
      if (r && r.id && !uniqueMap.has(r.id)) uniqueMap.set(r.id, r);
    }
    // Maintain stable descending time ordering (if present)
    const scoreResults = Array.from(uniqueMap.values()).sort((a: any, b: any) => {
      const at = a.createdAt ? new Date(a.createdAt).getTime() : 0;
      const bt = b.createdAt ? new Date(b.createdAt).getTime() : 0;
      return bt - at;
    });
    
    if (!scoreResults.length) {
      return [];
    }
    
    // The results are already transformed, just map them to ScoreResultData format
    return scoreResults.map((result: any) => ({
      id: result.id,
      value: String(result.value ?? ''),
      confidence: result.confidence,
      explanation: result.explanation,
      metadata: result.metadata || {
        human_label: null,
        correct: false,
        human_explanation: null,
        text: null
      },
      trace: result.trace,
      itemId: result.itemId,
      itemIdentifiers: result.itemIdentifiers,
      feedbackItem: result.feedbackItem
    }));
  }, [data.scoreResults]);

  // Determine loading state for score results
  const isResultsLoading = useMemo(() => !Array.isArray(data.scoreResults), [data.scoreResults])


  const stages = useMemo(() => {
    const stageItems = data.task?.stages?.items || [];
    
    
    return stageItems.map(stage => ({
      key: stage.name,
      label: stage.name,
      color: stage.name === 'Processing' ? 'bg-secondary' : (
        stage.status === 'COMPLETED' || stage.status === 'RUNNING' ? 'bg-primary' :
        stage.status === 'FAILED' ? 'bg-false' :
        'bg-neutral'
      ),
      name: stage.name,
      order: stage.order,
      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
      processedItems: stage.processedItems,
      totalItems: stage.totalItems,
      statusMessage: stage.statusMessage,
      startedAt: stage.startedAt || undefined,
      completedAt: stage.completedAt || undefined,
      estimatedCompletionAt: stage.estimatedCompletionAt || undefined
    }));
  }, [
    data.task?.stages?.items, 
    data.id,
    // Force recomputation when any stage object changes by including a hash of stage data
    JSON.stringify(data.task?.stages?.items?.map(s => ({ 
      name: s.name, 
      status: s.status, 
      processedItems: s.processedItems, 
      totalItems: s.totalItems,
      statusMessage: s.statusMessage,
      startedAt: s.startedAt,
      completedAt: s.completedAt
    })))
  ]);

  const taskStatus = useMemo(() => {
    const statusObj = {
      showStages: true,
      status: mapTaskStatus(data.task?.status || data.status),
      stageConfigs: stages,
      stages,
      processedItems: data.processedItems,
      totalItems: data.totalItems,
      startedAt: data.task?.startedAt || data.startedAt || undefined,
      completedAt: data.task?.completedAt || undefined,
      estimatedCompletionAt: data.task?.estimatedCompletionAt || undefined,
      errorMessage: data.task?.errorMessage || data.errorMessage || undefined,
      command: data.task?.command || data.command,
      statusMessage: getStatusMessage(data),
      variant: 'grid' as const,
      extra,
      isSelected,
      commandDisplay: 'hide' as const,
    };
    
    
    return statusObj;
  }, [
    data.task?.status,
    data.status,
    stages,
    data.processedItems,
    data.totalItems,
    data.task?.startedAt,
    data.startedAt,
    data.task?.completedAt,
    data.task?.estimatedCompletionAt,
    data.task?.errorMessage,
    data.errorMessage,
    data.task?.command,
    data.command,
    extra,
    isSelected,
    data.id
  ]);

  return (
    <div className="space-y-2 mt-auto">
      <TaskStatus
        {...taskStatus}
        hideElapsedTime
        key={`${data.id}-${JSON.stringify(stages.map(s => ({ name: s.name, status: s.status, processedItems: s.processedItems })))}`}
      />
      {extra && (
        <EvaluationListAccuracyBar
          progress={progress}
          accuracy={accuracy}
          isSelected={isSelected}
        />
      )}
    </div>
  )
}, (prevProps, nextProps) => {
  const prevStagesList = prevProps.data.task?.stages?.items || [];
  const nextStagesList = nextProps.data.task?.stages?.items || [];
  const stagesChanged = (
    prevStagesList.length !== nextStagesList.length ||
    prevStagesList.some((s, i) => {
      const ns = nextStagesList[i];
      return !ns || s.name !== ns.name || s.status !== ns.status || s.processedItems !== ns.processedItems || s.totalItems !== ns.totalItems;
    })
  );

  const progressChanged = (
    prevProps.data.processedItems !== nextProps.data.processedItems ||
    prevProps.data.totalItems !== nextProps.data.totalItems ||
    prevProps.data.accuracy !== nextProps.data.accuracy ||
    prevProps.data.status !== nextProps.data.status ||
    prevProps.data.elapsedSeconds !== nextProps.data.elapsedSeconds ||
    prevProps.data.estimatedRemainingSeconds !== nextProps.data.estimatedRemainingSeconds
  );

  const otherChanged = (
    prevProps.extra !== nextProps.extra ||
    prevProps.isSelected !== nextProps.isSelected ||
    !isEqual(prevProps.data.scoreResults, nextProps.data.scoreResults)
  );

  const allow = stagesChanged || progressChanged || otherChanged;
  if (allow) {
    return false;
  }
  return true;
});

interface ParsedScoreResult extends ScoreResultData {}

function parseScoreResult(result: any): ParsedScoreResult {

  if (!result) {
    console.warn('Received null or undefined score result');
    return {
      id: '',
      value: '',
      confidence: null,
      explanation: null,
      metadata: {
        human_label: null,
        correct: false,
        human_explanation: null,
        text: null
      },
      trace: null,
      itemId: null,
      itemIdentifiers: null,
      feedbackItem: null
    };
  }

  // Cache parsed metadata to prevent repeated parsing
  let parsedMetadata = result._parsedMetadata;
  if (!parsedMetadata) {
    try {
      let metadata = result.metadata;
      if (typeof metadata === 'string') {
        try {
          metadata = JSON.parse(metadata);
          if (typeof metadata === 'string') {
            metadata = JSON.parse(metadata);
          }
        } catch (e) {
          console.error('Error parsing metadata string:', e);
          metadata = {};
        }
      }
      parsedMetadata = metadata || {};
      // Cache the parsed result
      result._parsedMetadata = parsedMetadata;
    } catch (e) {
      console.error('Error processing metadata:', e);
      parsedMetadata = {};
    }
  }


  // Extract results from nested structure if present
  const firstResultKey = parsedMetadata?.results ? 
    Object.keys(parsedMetadata.results)[0] : null
  const scoreResult = firstResultKey && parsedMetadata.results ? 
    parsedMetadata.results[firstResultKey] : null

  // Ensure we have valid values for all fields
  const id = result.id || '';
  const value = String(result.value || scoreResult?.value || '');
  const confidence = result.confidence ?? scoreResult?.confidence ?? null;
  const explanation = result.explanation ?? scoreResult?.explanation ?? null;
  const trace = result.trace ?? scoreResult?.trace ?? null;
  const humanLabel = scoreResult?.metadata?.human_label ?? parsedMetadata.human_label ?? null;
  const correct = Boolean(scoreResult?.metadata?.correct ?? parsedMetadata.correct);
  const humanExplanation = scoreResult?.metadata?.human_explanation ?? parsedMetadata.human_explanation ?? null;
  const text = scoreResult?.metadata?.text ?? parsedMetadata.text ?? null;
  const itemId = result.itemId || parsedMetadata.item_id?.toString() || null;

  // Parse feedbackItem data
  const originalScoreResult = result.feedbackItem?.scoreResults?.items?.find(
    (sr: any) => sr.type === 'prediction'
  ) || null;
  const feedbackItem = result.feedbackItem ? {
    editCommentValue: result.feedbackItem.editCommentValue || null,
    initialAnswerValue: result.feedbackItem.initialAnswerValue || originalScoreResult?.value || null,
    initialCommentValue: result.feedbackItem.initialCommentValue || originalScoreResult?.explanation || null,
    finalAnswerValue: result.feedbackItem.finalAnswerValue || null,
    editorName: result.feedbackItem.editorName || null,
    editedAt: result.feedbackItem.editedAt || null,
    createdAt: result.feedbackItem.createdAt || null,
  } : null;



  return {
    id,
    value,
    confidence,
    explanation,
    metadata: {
      human_label: humanLabel,
      correct,
      human_explanation: humanExplanation,
      text
    },
    trace,
    itemId,
    itemIdentifiers: result.itemIdentifiers || null,
    feedbackItem
  };
}

const DetailContent = React.memo(({ 
  data, 
  isFullWidth,
  metrics,
  metricsVariant,
  selectedScoreResultId,
  onSelectScoreResult,
  extra,
  isSelected,
  commandDisplay = 'show',
  onCommandDisplayChange
}: { 
  data: EvaluationTaskData
  isFullWidth: boolean
  metrics: any[]
  metricsVariant: 'grid' | 'detail'
  selectedScoreResultId?: string | null
  onSelectScoreResult?: (id: string | null) => void
  extra?: boolean
  isSelected?: boolean
  commandDisplay?: 'hide' | 'show' | 'full'
  onCommandDisplayChange?: (display: 'show' | 'full') => void
}) => {
  // Force isSelected to true in detail mode
  const effectiveIsSelected = true;


  const [containerWidth, setContainerWidth] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const [selectedPredictedActual, setSelectedPredictedActual] = useState<{
    predicted: string | null
    actual: string | null
  }>({ predicted: null, actual: null })

  // Find the selected score result from the already-transformed results
  const selectedScoreResult = useMemo(() => {
    const scoreResults = data.scoreResults || [];
    return selectedScoreResultId ? scoreResults.find((r: any) => r.id === selectedScoreResultId) : null;
  }, [data.scoreResults, selectedScoreResultId]);


  // Use already-transformed score results directly
  const parsedScoreResults = useMemo(() => {
    // data.scoreResults is already transformed by transformEvaluation
    const scoreResults = data.scoreResults || [];
    
    if (!scoreResults.length) {
      return [];
    }
    
    // The results are already transformed, just map them to ScoreResultData format
    return scoreResults.map((result: any) => ({
      id: result.id,
      value: result.value,
      confidence: result.confidence,
      explanation: result.explanation,
      metadata: result.metadata || {
        human_label: null,
        correct: false,
        human_explanation: null,
        text: null
      },
      trace: result.trace,
      itemId: result.itemId,
      itemIdentifiers: result.itemIdentifiers,
      feedbackItem: result.feedbackItem
    }));
  }, [data.scoreResults]);

  // Local loading flag for this detail panel scope
  const isResultsLoading = useMemo(() => !Array.isArray(data.scoreResults), [data.scoreResults])

  useResizeObserver(containerRef, (entry) => {
    setContainerWidth(entry.contentRect.width)
  })

  const handleActualLabelSelect = (label: string) => {
    setSelectedPredictedActual(prev => ({
      ...prev,
      actual: prev.actual === label ? null : label,
      predicted: null
    }))
  }

  const handlePredictedLabelSelect = (label: string) => {
    setSelectedPredictedActual(prev => ({
      ...prev,
      predicted: prev.predicted === label ? null : label,
      actual: null
    }))
  }

  // Add logging for display conditions
  const isWideEnoughForTwo = containerWidth >= 800
  const isWideEnoughForThree = containerWidth >= 1180 && isFullWidth
  const showAsColumns = isWideEnoughForTwo
  
  // Modify the panel visibility logic to prioritize the selected score result
  const showResultDetail = selectedScoreResult !== null
  const showResultsList = parsedScoreResults.length > 0
  
  // In narrow view with a selected result, ONLY show the score result detail
  const showScoreResultInNarrowView = !isWideEnoughForTwo && showResultDetail
  
  // Only show main panel if we're not in narrow view with a selected result
  const showMainPanel = isWideEnoughForThree ||
                        (isWideEnoughForTwo && (!showResultDetail || !showResultsList)) || 
                        (!isWideEnoughForTwo && !showResultDetail); // Only show main panel in narrow view if no result selected

  const handleScoreResultSelect = (result: Schema['ScoreResult']['type']) => {
    onSelectScoreResult?.(result.id)
  }

  const selectFirstFilteredScoreResult = (itemIds: string[]) => {
    const firstItemId = itemIds.find(Boolean)
    if (!firstItemId) return
    const matching = parsedScoreResults.find(result => result.itemId === firstItemId)
    if (matching) {
      onSelectScoreResult?.(matching.id)
    }
  }

  const handleTopicFilter = (
    itemIds: string[] | null,
    topicLabel?: string | null
  ) => {
    setSelectedCategoryKey(null)
    setSelectedCategoryLabel(null)
    setSelectedCategoryItemIds(null)
    setCategoryMissingItemIdCount(0)
    setSelectedTopicItemIds(itemIds)
    setSelectedTopicLabel(itemIds ? (topicLabel ?? null) : null)
    if (itemIds && itemIds.length > 0) {
      setSelectedPredictedActual({ predicted: null, actual: null })
      selectFirstFilteredScoreResult(itemIds)
    }
  }

  const handleCategoryFilter = (
    categoryKey: MisclassificationCategory,
    categoryLabel: string
  ) => {
    const classifications = misclassificationCategoryBreakdown.itemClassifications ?? []
    const filteredClassifications = classifications.filter(
      classification => classification.primary_category === categoryKey
    )

    const itemIds: string[] = []
    let missingCount = 0

    filteredClassifications.forEach(classification => {
      if (!classification.item_id) {
        missingCount += 1
        return
      }

      itemIds.push(classification.item_id)
    })

    setSelectedTopicItemIds(null)
    setSelectedTopicLabel(null)
    setSelectedCategoryKey(categoryKey)
    setSelectedCategoryLabel(categoryLabel)
    setSelectedCategoryItemIds(Array.from(new Set(itemIds)))
    setCategoryMissingItemIdCount(missingCount)
    setSelectedPredictedActual({ predicted: null, actual: null })
    selectFirstFilteredScoreResult(itemIds)
  }

  const clearCategoryFilter = () => {
    setSelectedCategoryKey(null)
    setSelectedCategoryLabel(null)
    setSelectedCategoryItemIds(null)
    setCategoryMissingItemIdCount(0)
  }

  const handleScoreResultClose = () => {
    onSelectScoreResult?.(null)
  }

  const transformedConfusionMatrixData = useMemo((): ConfusionMatrixData | null => {
    const cmInput = data.confusionMatrix;
    if (!cmInput || !cmInput.matrix || !cmInput.labels || cmInput.matrix.length === 0 || cmInput.labels.length === 0) {
      return null;
    }
    // Basic check: matrix rows should match labels length for a square matrix using labels for both axes
    if (cmInput.matrix.length !== cmInput.labels.length) {
        console.warn('Confusion matrix: matrix rows length does not match labels length.');
        // This might indicate an issue, but ConfusionMatrix component itself has more robust validation.
        // For now, we let it pass to the component for its validation.
    }
    if (cmInput.labels.some(l => l === '')) {
        console.warn('EvaluationTask: Input confusion matrix labels contain empty strings. This can lead to errors.');
    }

    try {
      const newMatrix: ConfusionMatrixRow[] = cmInput.matrix.map((row, actualIndex) => {
        const actualClassLabel = cmInput.labels![actualIndex];
        if (actualClassLabel === undefined) {
          // Should not happen if matrix.length === labels.length and labels is not sparse
          throw new Error(`Label not found for actual index ${actualIndex}`);
        }
        const predictedClassCounts: { [predictedClassLabel: string]: number } = {};
        row.forEach((count, predictedIndex) => {
          const predictedClassLabel = cmInput.labels![predictedIndex];
          if (predictedClassLabel === undefined) {
            throw new Error(`Label not found for predicted index ${predictedIndex}`);
          }
          // It's important that predictedClassLabel is a valid key (non-empty string)
          // The ConfusionMatrix component will validate if these labels exist in its main `labels` prop.
          predictedClassCounts[predictedClassLabel] = count;
        });
        return {
          actualClassLabel: actualClassLabel, // Use the label as is, even if it's ""
          predictedClassCounts,
        };
      });
      return {
        matrix: newMatrix,
        labels: cmInput.labels, // Pass original labels, ConfusionMatrix will validate them
      };
    } catch (error) {
      console.error("Error transforming confusion matrix data:", error);
      return null; // Or a specific error structure if ConfusionMatrix can handle it
    }
  }, [data.confusionMatrix]);

  const rootCauseData = useMemo((): RootCauseData | null => {
    try {
      const params = parseJsonDeep(data.parameters) as Record<string, unknown> | null
      const rootCause = params?.root_cause
      return (rootCause && typeof rootCause === 'object') ? (rootCause as RootCauseData) : null
    } catch {
      return null
    }
  }, [data.parameters])

  const rootCauseTopics = rootCauseData?.topics ?? null
  const misclassificationAnalysis = rootCauseData?.misclassification_analysis ?? null
  const rcaCoverage = useMemo(() => {
    try {
      const params = parseJsonDeep(data.parameters) as Record<string, unknown> | null
      if (!params || typeof params !== 'object') return null
      return {
        status: typeof params.rca_coverage_status === 'string' ? params.rca_coverage_status : null,
        incorrectItemsTotal: typeof params.incorrect_items_total === 'number' ? params.incorrect_items_total : 0,
        incorrectItemsWithFeedbackLink: typeof params.incorrect_items_with_feedback_link === 'number'
          ? params.incorrect_items_with_feedback_link
          : 0,
        incorrectItemsWithoutFeedbackLink: typeof params.incorrect_items_without_feedback_link === 'number'
          ? params.incorrect_items_without_feedback_link
          : 0,
      }
    } catch {
      return null
    }
  }, [data.parameters])
  const rcaCoverageNote = useMemo(() => {
    if (!rcaCoverage || !rcaCoverage.status) return null
    if (rcaCoverage.status === 'partial') {
      return `RCA analyzed ${rcaCoverage.incorrectItemsWithFeedbackLink}/${rcaCoverage.incorrectItemsTotal} incorrect item(s); ${rcaCoverage.incorrectItemsWithoutFeedbackLink} missing feedback linkage.`
    }
    if (rcaCoverage.status === 'none' && rcaCoverage.incorrectItemsTotal > 0) {
      return `RCA unavailable: 0/${rcaCoverage.incorrectItemsTotal} incorrect item(s) had feedback linkage.`
    }
    if (rcaCoverage.status === 'full' && rcaCoverage.incorrectItemsTotal > 0) {
      return `RCA analyzed ${rcaCoverage.incorrectItemsWithFeedbackLink}/${rcaCoverage.incorrectItemsTotal} incorrect item(s).`
    }
    return null
  }, [rcaCoverage])
  const misclassificationCategoryBreakdown = useMemo(() => {
    const totals = misclassificationAnalysis?.category_totals ?? {}
    const itemClassifications = Array.isArray(misclassificationAnalysis?.item_classifications_all)
      ? misclassificationAnalysis.item_classifications_all
      : []
    const rows = MISCLASSIFICATION_CATEGORY_CONFIG.map(config => {
      const rawCount = totals[config.key]
      const count = typeof rawCount === 'number' && Number.isFinite(rawCount) ? rawCount : 0
      return { ...config, count }
    })
    const totalItems = rows.reduce((sum, row) => sum + row.count, 0)
    const informationGapItems = itemClassifications.filter(
      classification => classification.primary_category === 'information_gap'
    )
    const missingOrDegradedPrimaryInputSignals = informationGapItems.filter(classification =>
      (classification.evidence_snippets ?? []).some(snippet => {
        const source = (snippet.source ?? '').toLowerCase()
        if (source !== 'primary_input') return false
        const text = (snippet.quote_or_fact ?? '').toLowerCase()
        return (
          text.includes('unavailable')
          || text.includes('missing')
          || text.includes('not available')
          || text.includes('insufficient')
          || text.includes('degraded')
          || text.includes('redacted')
        )
      })
    ).length
    const missingRequiredContextSignals = informationGapItems.filter(
      classification => classification.information_gap_subtype === 'missing_required_context'
    ).length
    const derivedInfoGapDiagnostics = {
      item_count: informationGapItems.length,
      missing_or_degraded_primary_input_count: missingOrDegradedPrimaryInputSignals,
      missing_or_degraded_primary_input_share: informationGapItems.length > 0
        ? missingOrDegradedPrimaryInputSignals / informationGapItems.length
        : 0,
      missing_required_context_count: missingRequiredContextSignals,
      missing_required_context_share: informationGapItems.length > 0
        ? missingRequiredContextSignals / informationGapItems.length
        : 0,
      diagnostic_summary: informationGapItems.length > 0
        ? `${missingOrDegradedPrimaryInputSignals}/${informationGapItems.length} information-gap item(s) include missing/degraded primary-input evidence.`
        : 'No information-gap items in this run.',
    }

    return {
      rows,
      totalItems,
      redFlags: Array.isArray(misclassificationAnalysis?.evaluation_red_flags)
        ? misclassificationAnalysis.evaluation_red_flags
        : [],
      overall: misclassificationAnalysis?.overall_assessment ?? null,
      categorySummaries: misclassificationAnalysis?.category_summaries ?? {},
      topicCategoryBreakdown: Array.isArray(misclassificationAnalysis?.topic_category_breakdown)
        ? misclassificationAnalysis.topic_category_breakdown
        : [],
      primaryNextAction: misclassificationAnalysis?.primary_next_action ?? null,
      optimizationApplicability: misclassificationAnalysis?.optimization_applicability ?? null,
      mechanicalSubtypeTotals: misclassificationAnalysis?.mechanical_subtype_totals ?? {},
      categoryDiagnostics: {
        information_gap:
          misclassificationAnalysis?.category_diagnostics?.information_gap
          ?? derivedInfoGapDiagnostics,
      },
      maxCategorySummaryItemsUsed: misclassificationAnalysis?.max_category_summary_items_used,
      itemClassifications,
    }
  }, [misclassificationAnalysis])

  const [showRootCauseCode, setShowRootCauseCode] = useState(false)
  const [selectedTopicItemIds, setSelectedTopicItemIds] = useState<string[] | null>(null)
  const [selectedTopicLabel, setSelectedTopicLabel] = useState<string | null>(null)
  const [selectedCategoryKey, setSelectedCategoryKey] = useState<MisclassificationCategory | null>(null)
  const [selectedCategoryLabel, setSelectedCategoryLabel] = useState<string | null>(null)
  const [selectedCategoryItemIds, setSelectedCategoryItemIds] = useState<string[] | null>(null)
  const [categoryMissingItemIdCount, setCategoryMissingItemIdCount] = useState(0)
  const rcaDataByItemId = useMemo<
    Record<string, {
      detailed_cause?: string
      suggested_fix?: string
      misclassification_category?: string
      misclassification_confidence?: string
      misclassification_rationale?: string
      misclassification_evidence_quote?: string
      misclassification_config_fixability?: string
      misclassification_evidence?: Array<{ source?: string; quote_or_fact?: string }>
      misclassification_mechanical_subtype?: string
      misclassification_mechanical_details?: string
    }>
  >(() => {
    const map: Record<string, {
      detailed_cause?: string
      suggested_fix?: string
      misclassification_category?: string
      misclassification_confidence?: string
      misclassification_rationale?: string
      misclassification_evidence_quote?: string
      misclassification_config_fixability?: string
      misclassification_evidence?: Array<{ source?: string; quote_or_fact?: string }>
      misclassification_mechanical_subtype?: string
      misclassification_mechanical_details?: string
    }> = {}

    ;(misclassificationCategoryBreakdown.itemClassifications ?? []).forEach(classification => {
      if (!classification.item_id) return
      map[classification.item_id] = {
        misclassification_category: classification.primary_category ?? undefined,
        misclassification_confidence: classification.confidence ?? undefined,
        misclassification_rationale: (
          classification.rationale_paragraph
          ?? classification.rationale_full
          ?? classification.rationale_short
          ?? undefined
        ),
        misclassification_evidence_quote: classification.evidence_quote ?? undefined,
        misclassification_config_fixability: classification.config_fixability ?? undefined,
        misclassification_evidence: classification.evidence_snippets ?? undefined,
        misclassification_mechanical_subtype: classification.mechanical_subtype ?? undefined,
        misclassification_mechanical_details: classification.mechanical_details ?? undefined,
        detailed_cause: classification.detailed_cause ?? undefined,
        suggested_fix: classification.suggested_fix ?? undefined,
      }
    })

    ;(rootCauseTopics ?? []).forEach((topic: any) => {
      ;(topic.exemplars ?? []).forEach((exemplar: any) => {
        const itemId = exemplar?.item_id
        if (!itemId) return
        map[itemId] = {
          ...(map[itemId] ?? {}),
          detailed_cause: exemplar?.detailed_cause ?? map[itemId]?.detailed_cause,
          suggested_fix: exemplar?.suggested_fix ?? map[itemId]?.suggested_fix,
        }
      })
    })
    return map
  }, [misclassificationCategoryBreakdown.itemClassifications, rootCauseTopics])

  const activeFilteredItemIds = selectedCategoryItemIds ?? selectedTopicItemIds
  const activeFilterChipLabel = selectedCategoryLabel
    ? `Filtered by category: ${selectedCategoryLabel}`
    : selectedTopicLabel
      ? `Filtered by topic: ${selectedTopicLabel}`
      : null

  const selectedItemRcaContext = selectedScoreResult?.itemId
    ? rcaDataByItemId[selectedScoreResult.itemId]
    : undefined
  const topicCategoryInfoByKey = useMemo(() => {
    const map: Record<string, { primaryCategory?: string; purity?: number; categoryCounts?: Record<string, number> }> = {}
    ;(misclassificationCategoryBreakdown.topicCategoryBreakdown ?? []).forEach(topic => {
      const primaryCategory = typeof topic.topic_primary_category === 'string'
        ? topic.topic_primary_category
        : undefined
      const purity = typeof topic.topic_category_purity === 'number'
        ? topic.topic_category_purity
        : undefined
      const categoryCounts =
        topic.category_counts && typeof topic.category_counts === 'object'
          ? (topic.category_counts as Record<string, number>)
          : undefined
      if (topic.topic_id !== undefined && topic.topic_id !== null) {
        map[String(topic.topic_id)] = { primaryCategory, purity, categoryCounts }
      }
      if (topic.topic_label) {
        map[String(topic.topic_label)] = { primaryCategory, purity, categoryCounts }
      }
    })
    return map
  }, [misclassificationCategoryBreakdown.topicCategoryBreakdown])

  const candidateAssessmentSummary = useMemo<CandidateAssessmentCompactSummary | null>(() => {
    const parsedTaskMetadata = parseJsonDeep(data.task?.metadata)
    if (!parsedTaskMetadata || typeof parsedTaskMetadata !== 'object') return null
    const metadataObject = parsedTaskMetadata as Record<string, unknown>
    const rawCompactSummary = parseJsonDeep(metadataObject.candidate_assessment_compact_summary)
    if (!rawCompactSummary || typeof rawCompactSummary !== 'object') return null
    const compactSummary = rawCompactSummary as CandidateAssessmentCompactSummary
    if (compactSummary.schema_version !== 'candidate_assessment_bundle.v1') return null
    return compactSummary
  }, [data.task?.metadata])

  const candidateAssessmentStageRefs = useMemo(() => {
    const stageRefs = candidateAssessmentSummary?.stage_references
    if (!Array.isArray(stageRefs)) return []
    return stageRefs.filter(ref => ref && typeof ref === 'object')
  }, [candidateAssessmentSummary])

  return (
    <div
      ref={containerRef}
      className="w-full px-3 pb-3 min-w-[300px]"
    >
      <div className={`overflow-visible ${showAsColumns ? 'grid gap-4' : 'space-y-4'} ${showAsColumns ? 'h-full' : 'h-auto'}`} 
        style={{
          gridTemplateColumns: isWideEnoughForThree 
            ? selectedScoreResult ? '1fr 1fr 1fr' : '1fr 1fr'
            : isWideEnoughForTwo
              ? '1fr 1fr'    // Always equal width for two panels
              : '1fr'          // Show only one panel
        }}
      >
        {/* When in narrow view and a score result is selected, ONLY show the score result detail */}
        {showScoreResultInNarrowView && selectedScoreResult && (
          <div className="w-full h-full flex flex-col overflow-hidden">
            <ScoreResultComponent
              result={{
                id: selectedScoreResult.id,
                value: String(selectedScoreResult.value),
                confidence: selectedScoreResult.confidence,
                explanation: selectedScoreResult.explanation,
                metadata: selectedScoreResult.metadata || {
                  human_label: null,
                  correct: false,
                  human_explanation: null,
                  text: null
                },
                trace: selectedScoreResult.trace,
                itemId: selectedScoreResult.itemId,
                itemIdentifiers: (selectedScoreResult as any).itemIdentifiers,
                feedbackItem: (selectedScoreResult as any).feedbackItem || null
              }}
              variant="detail"
              onClose={handleScoreResultClose}
              rcaDetailedCause={selectedItemRcaContext?.detailed_cause}
              rcaSuggestedFix={selectedItemRcaContext?.suggested_fix}
              misclassificationCategory={selectedItemRcaContext?.misclassification_category}
              misclassificationConfidence={selectedItemRcaContext?.misclassification_confidence}
              misclassificationRationale={selectedItemRcaContext?.misclassification_rationale}
              misclassificationEvidenceQuote={selectedItemRcaContext?.misclassification_evidence_quote}
              misclassificationConfigFixability={selectedItemRcaContext?.misclassification_config_fixability}
              misclassificationEvidence={selectedItemRcaContext?.misclassification_evidence}
              misclassificationMechanicalSubtype={selectedItemRcaContext?.misclassification_mechanical_subtype}
              misclassificationMechanicalDetails={selectedItemRcaContext?.misclassification_mechanical_details}
            />
          </div>
        )}

        {/* Only show main panel if not showing score result in narrow view */}
        {showMainPanel && (
          <div 
            className={`w-full ${showAsColumns ? 'h-full' : 'h-auto'} flex flex-col overflow-visible`}
          >
            <div className={`${showAsColumns ? 'flex-1' : ''} overflow-visible max-h-full`}>
              <div className="space-y-3 p-1 overflow-visible">
                <div className="mb-3">
                  <TaskStatus
                    key={`detail-${data.id}-${JSON.stringify(data.task?.stages?.items?.map(s => ({ name: s.name, status: s.status, processedItems: s.processedItems })))}`}
                    variant="detail"
                    showStages={true}
                    status={mapTaskStatus(data.task?.status || data.status)}
                    stageConfigs={data.task?.stages?.items?.map(stage => ({
                      key: stage.name,
                      label: stage.name,
                      color: stage.name === 'Processing' ? 'bg-secondary' : (
                        stage.status === 'COMPLETED' || stage.status === 'RUNNING' ? 'bg-primary' :
                        stage.status === 'FAILED' ? 'bg-false' :
                        'bg-neutral'
                      ),
                      name: stage.name,
                      order: stage.order,
                      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
                      processedItems: stage.processedItems,
                      totalItems: stage.totalItems,
                      statusMessage: stage.statusMessage,
                      completed: stage.status === 'COMPLETED',
                      startedAt: stage.startedAt || undefined,
                      completedAt: stage.completedAt || undefined,
                      estimatedCompletionAt: stage.estimatedCompletionAt || undefined
                    })) || []}
                    stages={data.task?.stages?.items?.map(stage => ({
                      key: stage.name,
                      label: stage.name,
                      color: stage.name === 'Processing' ? 'bg-secondary' : (
                        stage.status === 'COMPLETED' || stage.status === 'RUNNING' ? 'bg-primary' :
                        stage.status === 'FAILED' ? 'bg-false' :
                        'bg-neutral'
                      ),
                      name: stage.name,
                      order: stage.order,
                      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
                      processedItems: stage.processedItems,
                      totalItems: stage.totalItems,
                      statusMessage: stage.statusMessage,
                      startedAt: stage.startedAt || undefined,
                      completedAt: stage.completedAt || undefined,
                      estimatedCompletionAt: stage.estimatedCompletionAt || undefined
                    })) || []}
                    processedItems={data.processedItems}
                    totalItems={data.totalItems}
                    startedAt={data.task?.startedAt || data.startedAt || undefined}
                    completedAt={data.task?.completedAt || undefined}
                    estimatedCompletionAt={data.task?.estimatedCompletionAt || undefined}
                    errorMessage={data.task?.errorMessage || data.errorMessage || undefined}
                    command={data.task?.command || data.command}
                    statusMessage={getStatusMessage(data)}
                    truncateMessages={true}
                    extra={extra}
                    isSelected={effectiveIsSelected}
                    commandDisplay={commandDisplay}
                    onCommandDisplayChange={onCommandDisplayChange}
                    hideElapsedTime
                  />
                </div>

                {candidateAssessmentSummary && (
                  <div className="mb-3">
                    <div className="font-medium text-muted-foreground text-sm mb-1">
                      Candidate assessment
                    </div>
                    <div className="rounded-md bg-card p-2 space-y-2">
                      <div className="text-sm text-foreground">
                        {getAssessmentDecisionLabel(candidateAssessmentSummary.decision)}
                      </div>
                      {candidateAssessmentSummary.decision_reason && (
                        <div className="text-xs text-muted-foreground">
                          Reason: {candidateAssessmentSummary.decision_reason}
                        </div>
                      )}
                      {candidateAssessmentSummary.decision_confidence && (
                        <div className="text-xs text-muted-foreground">
                          Confidence: {candidateAssessmentSummary.decision_confidence}
                        </div>
                      )}
                      {candidateAssessmentSummary.primary_next_action && (
                        <div className="text-xs text-muted-foreground">
                          Primary route action: {getPrimaryNextActionLabel(candidateAssessmentSummary.primary_next_action)}
                        </div>
                      )}

                      {candidateAssessmentStageRefs.length > 0 && (
                        <div className="space-y-1.5">
                          <div className="text-xs font-medium text-muted-foreground">
                            Stage evidence
                          </div>
                          {candidateAssessmentStageRefs.map((stageRef, index) => (
                            <div key={`assessment-stage-${stageRef.stage_key ?? 'unknown'}-${index}`} className="rounded bg-muted/40 p-2 space-y-1">
                              <div className="text-xs text-foreground font-medium">
                                {getAssessmentStageLabel(stageRef.stage_key)}
                              </div>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground">
                                <div>
                                  Baseline: {stageRef.baseline_evaluation_id ?? 'Unavailable'} ({stageRef.baseline_status ?? 'Unknown'})
                                </div>
                                <div>
                                  Candidate: {stageRef.candidate_evaluation_id ?? 'Unavailable'} ({stageRef.candidate_status ?? 'Unknown'})
                                </div>
                                <div>
                                  Delta AC1: {formatSignedMetric(stageRef.delta_ac1)}
                                </div>
                                <div>
                                  Delta value: {formatSignedMetric(stageRef.delta_value_score)}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="space-y-1.5">
                        <div className="text-xs font-medium text-muted-foreground">
                          Generalization gap KPIs
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground">
                          <div>
                            Baseline gap: {formatMetric(candidateAssessmentSummary.baseline_generalization_gap)}
                          </div>
                          <div>
                            Candidate gap: {formatMetric(candidateAssessmentSummary.candidate_generalization_gap)}
                          </div>
                          <div>
                            Gap delta: {formatSignedMetric(candidateAssessmentSummary.generalization_gap_delta)}
                          </div>
                          <div>
                            Random delta mean/stddev: {formatSignedMetric(candidateAssessmentSummary.random_delta_mean)} / {formatMetric(candidateAssessmentSummary.random_delta_stddev)}
                          </div>
                        </div>
                      </div>

                      {candidateAssessmentSummary.attachment_key && (
                        <div className="text-xs text-muted-foreground">
                          Bundle attachment key:{' '}
                          <span className="font-mono break-all text-foreground">
                            {candidateAssessmentSummary.attachment_key}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                <div className="mb-3">
                  <ClassDistributionVisualizer
                    data={data.datasetClassDistribution}
                    isBalanced={data.isDatasetClassDistributionBalanced}
                    onLabelSelect={handleActualLabelSelect}
                  />
                </div>

                <div className="mb-3">
                  <PredictedClassDistributionVisualizer
                    data={data.predictedClassDistribution}
                    onLabelSelect={handlePredictedLabelSelect}
                  />
                </div>

                <div className="mb-3">
                  <MetricsGaugesExplanation
                    explanation={data.metricsExplanation}
                    goal={data.scoreGoal}
                  />
                </div>

                <MetricsGauges 
                  gauges={metrics} 
                  variant="detail"
                />

                {/* Confusion Matrix Section */}
                {transformedConfusionMatrixData && (
                  <div className="mt-4 rounded-md bg-background/30 w-full" style={{ overflow: 'visible' }}>
                    <ConfusionMatrix
                      data={transformedConfusionMatrixData} // Pass the transformed data object
                      onSelectionChange={setSelectedPredictedActual} // Reverted to original handler
                    />
                  </div>
                )}

                {/* Score-Configuration RCA */}
                {(rootCauseData && (
                  (rootCauseTopics && rootCauseTopics.length > 0) ||
                  misclassificationCategoryBreakdown.totalItems > 0 ||
                  misclassificationCategoryBreakdown.redFlags.length > 0
                )) && (
                  <div className="mt-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium text-sm text-muted-foreground">Score-Configuration RCA</h4>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() => setShowRootCauseCode(v => !v)}
                        title="Show JSON"
                      >
                        <MessageSquareCode className="w-3.5 h-3.5 text-muted-foreground" />
                      </Button>
                    </div>
                    {rcaCoverageNote && (
                      <div className="mb-2 text-xs text-muted-foreground">
                        {rcaCoverageNote}
                      </div>
                    )}
                    {showRootCauseCode ? (
                      <pre className="whitespace-pre-wrap text-xs font-mono text-foreground bg-background rounded-md p-3 overflow-y-auto max-h-96 overflow-x-auto">
                        {JSON.stringify(rootCauseData, null, 2)}
                      </pre>
                    ) : (
                      <>
                        {misclassificationCategoryBreakdown.totalItems > 0 && (
                          <div className="mb-3">
                            <div className="font-medium text-muted-foreground text-sm mb-1">
                              Misclassification categories
                            </div>
                            <div className="space-y-2 bg-card rounded-md p-2">
                              <div className="h-7 rounded-md overflow-hidden bg-muted/70 flex">
                                {misclassificationCategoryBreakdown.rows
                                  .filter(row => row.count > 0)
                                  .map(row => {
                                    const percentage = misclassificationCategoryBreakdown.totalItems > 0
                                      ? (row.count / misclassificationCategoryBreakdown.totalItems) * 100
                                      : 0
                                    const showLabel = percentage >= 15
                                    return (
                                      <div
                                        key={row.key}
                                        className={cn('h-full flex items-center justify-center text-xs text-foreground', row.colorClass)}
                                        style={{ width: `${percentage}%` }}
                                        title={`${row.label}: ${row.count} (${percentage.toFixed(1)}%)`}
                                      >
                                        {showLabel ? row.shortLabel : null}
                                      </div>
                                    )
                                  })}
                              </div>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-1">
                                {misclassificationCategoryBreakdown.rows.map(row => {
                                  const percentage = misclassificationCategoryBreakdown.totalItems > 0
                                    ? (row.count / misclassificationCategoryBreakdown.totalItems) * 100
                                    : 0
                                  return (
                                    <div key={`summary-${row.key}`} className="flex items-center justify-between gap-2 text-xs">
                                      <div className="flex items-center gap-1.5 min-w-0">
                                        <span className={cn('w-2 h-2 rounded-full shrink-0', row.colorClass)} />
                                        <span className="truncate text-foreground">{row.label}</span>
                                      </div>
                                      <span className="text-muted-foreground shrink-0">
                                        {row.count} ({percentage.toFixed(1)}%)
                                      </span>
                                    </div>
                                  )
                                })}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                Overall: {getMisclassificationAssessment(
                                  misclassificationCategoryBreakdown.overall?.predominant_category
                                )}{' '}
                                ({getMisclassificationCategoryLabel(
                                  misclassificationCategoryBreakdown.overall?.predominant_category
                                )})
                              </div>
                            </div>
                          </div>
                        )}
                        {misclassificationCategoryBreakdown.totalItems > 0 &&
                          (
                            misclassificationCategoryBreakdown.overall?.predominant_category === 'information_gap'
                            || (
                              (misclassificationCategoryBreakdown.rows.find(row => row.key === 'information_gap')?.count ?? 0)
                              / Math.max(1, misclassificationCategoryBreakdown.totalItems)
                            ) >= 0.5
                          ) && (
                            <Alert className="mb-3 py-2 px-3 border-chart-2/40 text-chart-2 [&>svg]:text-chart-2">
                              <AlertTriangle className="h-4 w-4" />
                              <div className="min-w-0 text-xs">
                                <AlertTitle className="mb-0.5 text-xs">Information-gap is dominating this run</AlertTitle>
                                <AlertDescription className="text-xs text-foreground">
                                  {misclassificationCategoryBreakdown.categoryDiagnostics?.information_gap?.diagnostic_summary}
                                  {' '}({misclassificationCategoryBreakdown.categoryDiagnostics?.information_gap?.item_count ?? 0} item(s),{' '}
                                  {(((misclassificationCategoryBreakdown.categoryDiagnostics?.information_gap?.missing_or_degraded_primary_input_share ?? 0) * 100)).toFixed(1)}% with missing/degraded primary-input evidence).
                                  {' '}This can limit score-configuration-only optimization.
                                </AlertDescription>
                              </div>
                            </Alert>
                          )}
                        {misclassificationCategoryBreakdown.totalItems > 0 && (
                          <div className="mb-3">
                            <div className="flex items-center justify-between gap-2 mb-1">
                              <div className="font-medium text-muted-foreground text-sm">
                                Category summaries
                              </div>
                              {selectedCategoryKey && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 px-2 text-xs"
                                  onClick={clearCategoryFilter}
                                >
                                  Clear category filter
                                </Button>
                              )}
                            </div>
                            <div className="space-y-2 bg-card rounded-md p-2">
                              {MISCLASSIFICATION_CATEGORY_CONFIG.map(row => {
                                const summary = misclassificationCategoryBreakdown.categorySummaries?.[row.key]
                                const summaryText = summary?.category_summary_text
                                const patterns = Array.isArray(summary?.top_patterns) ? summary?.top_patterns : []
                                const itemCount = summary?.item_count ?? 0
                                const categoryClassifications = (misclassificationCategoryBreakdown.itemClassifications ?? [])
                                  .filter(classification => classification.primary_category === row.key)
                                const itemsWithMissingId = categoryClassifications
                                  .filter(classification => !classification.item_id)
                                  .length
                                return (
                                  <div key={`category-summary-${row.key}`} className="rounded-md bg-muted/40 p-2 space-y-1.5">
                                    <div className="flex items-center justify-between gap-2 mb-1">
                                      <div className="flex items-center gap-1.5 min-w-0">
                                        <span className={cn('w-2 h-2 rounded-full shrink-0', row.colorClass)} />
                                        <span className="text-xs font-medium text-foreground truncate">{row.label}</span>
                                      </div>
                                      <span className="text-xs text-muted-foreground shrink-0">{itemCount} item(s)</span>
                                    </div>
                                    <div className="text-xs text-foreground">
                                      {summaryText || 'No items in this category for this run.'}
                                    </div>
                                    {patterns.length > 0 && (
                                      <div className="mt-1 text-xs text-muted-foreground">
                                        Top patterns: {patterns
                                          .map(pattern => `${pattern.pattern ?? 'unknown'} (${pattern.count ?? 0})`)
                                          .join(', ')}
                                      </div>
                                    )}
                                    {itemCount > 0 && (
                                      <div className="flex items-center justify-between gap-2">
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          className={cn(
                                            'h-7 text-xs border-0 shadow-none px-2',
                                            selectedCategoryKey === row.key
                                              ? 'bg-secondary text-secondary-foreground hover:bg-secondary/90'
                                              : 'bg-muted text-foreground hover:bg-muted/80'
                                          )}
                                          onClick={() => handleCategoryFilter(row.key, row.label)}
                                        >
                                          View items ({itemCount})
                                        </Button>
                                        {selectedCategoryKey === row.key && categoryMissingItemIdCount > 0 && (
                                          <span className="text-[11px] text-muted-foreground">
                                            {categoryMissingItemIdCount} item(s) missing item_id not shown
                                          </span>
                                        )}
                                      </div>
                                    )}
                                    {itemsWithMissingId > 0 && selectedCategoryKey !== row.key && (
                                      <div className="text-[11px] text-muted-foreground">
                                        {itemsWithMissingId} item(s) in this category are missing item_id and cannot appear in score results.
                                      </div>
                                    )}
                                  </div>
                                )
                              })}
                              <div className="text-xs text-muted-foreground">
                                Summary budget per category: {misclassificationCategoryBreakdown.maxCategorySummaryItemsUsed ?? 'N/A'}
                              </div>
                            </div>
                          </div>
                        )}
                        {Object.entries(misclassificationCategoryBreakdown.mechanicalSubtypeTotals ?? {}).some(([, value]) => (value ?? 0) > 0) && (
                          <div className="mb-3">
                            <div className="font-medium text-muted-foreground text-sm mb-1">
                              Mechanical subtype breakdown
                            </div>
                            <div className="rounded-md bg-card p-2 space-y-1">
                              {Object.entries(misclassificationCategoryBreakdown.mechanicalSubtypeTotals ?? {})
                                .filter(([, value]) => (value ?? 0) > 0)
                                .map(([subtype, value]) => (
                                  <div key={`mechanical-subtype-${subtype}`} className="flex items-center justify-between text-xs">
                                    <span className="text-foreground">{subtype.replace(/_/g, ' ')}</span>
                                    <span className="text-muted-foreground">{value}</span>
                                  </div>
                                ))}
                            </div>
                          </div>
                        )}
                        {misclassificationCategoryBreakdown.redFlags.length > 0 && (
                          <div className="mb-3">
                            <div className="font-medium text-muted-foreground text-sm mb-1">
                              Evaluation red flags
                            </div>
                            <div className="space-y-1">
                              {misclassificationCategoryBreakdown.redFlags.map((flag, index) => {
                                const severity = (flag.severity ?? 'low').toLowerCase()
                                return (
                                  <Alert
                                    key={`${flag.flag ?? 'flag'}-${index}`}
                                    variant={severity === 'high' ? 'destructive' : 'default'}
                                    className={cn(
                                      'py-2 px-3',
                                      severity === 'medium' && 'border-chart-3/40 text-chart-3 [&>svg]:text-chart-3',
                                      severity === 'low' && 'border-muted text-muted-foreground'
                                    )}
                                  >
                                    <AlertTriangle className="h-4 w-4" />
                                    <div className="min-w-0">
                                      <AlertTitle className="mb-0.5 text-xs">
                                        <span className="uppercase tracking-wide">{severity}</span>
                                        {flag.flag && (
                                          <span className="ml-2 font-mono normal-case text-muted-foreground">{flag.flag}</span>
                                        )}
                                      </AlertTitle>
                                      <AlertDescription className="text-xs text-foreground">
                                        {flag.message ?? 'No details provided.'}
                                      </AlertDescription>
                                    </div>
                                  </Alert>
                                )
                              })}
                            </div>
                          </div>
                        )}
                        {misclassificationCategoryBreakdown.primaryNextAction && (
                          <div className="mb-3">
                            <div className="font-medium text-muted-foreground text-sm mb-1">
                              Primary next action
                            </div>
                            <div className="rounded-md bg-card p-2 space-y-1">
                              <div className="text-sm text-foreground">
                                {getPrimaryNextActionLabel(
                                  misclassificationCategoryBreakdown.primaryNextAction.action
                                )}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                Confidence: {misclassificationCategoryBreakdown.primaryNextAction.confidence ?? 'N/A'}
                              </div>
                              {Array.isArray(misclassificationCategoryBreakdown.primaryNextAction.reasons) &&
                                misclassificationCategoryBreakdown.primaryNextAction.reasons.length > 0 && (
                                  <div className="text-xs text-muted-foreground">
                                    {misclassificationCategoryBreakdown.primaryNextAction.reasons.join(' ')}
                                  </div>
                                )}
                              <div className="text-xs text-muted-foreground">
                                Optimization applicability: {misclassificationCategoryBreakdown.optimizationApplicability?.status ?? 'N/A'}
                                {misclassificationCategoryBreakdown.optimizationApplicability?.reason
                                  ? ` - ${misclassificationCategoryBreakdown.optimizationApplicability.reason}`
                                  : ''}
                              </div>
                            </div>
                          </div>
                        )}
                        {rootCauseData?.overall_explanation && (
                          <div className="mb-3">
                            <div className="font-medium text-muted-foreground text-sm mb-1">Overall root cause</div>
                            <div className="prose prose-sm max-w-none prose-p:text-foreground prose-strong:text-foreground prose-headings:text-foreground prose-li:text-foreground">
                              <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={{
                                p: ({children}) => <p className="mb-2 last:mb-0 text-sm">{children}</p>,
                                strong: ({children}) => <strong className="font-semibold">{children}</strong>,
                              }}>
                                {rootCauseData.overall_explanation}
                              </ReactMarkdown>
                            </div>
                          </div>
                        )}
                        {rootCauseData?.overall_improvement_suggestion && (
                          <div className="mb-3">
                            <div className="font-medium text-muted-foreground text-sm mb-1">Score-configuration improvement</div>
                            {misclassificationCategoryBreakdown.optimizationApplicability?.status &&
                              misclassificationCategoryBreakdown.optimizationApplicability.status !== 'applicable' && (
                                <Alert className="mb-2 py-2 px-3">
                                  <AlertTriangle className="h-4 w-4" />
                                  <div className="text-xs text-foreground">
                                    RCA recommendations are limited because optimization applicability is{' '}
                                    <strong>{misclassificationCategoryBreakdown.optimizationApplicability.status}</strong>.
                                    {' '}Follow primary next action first.
                                  </div>
                                </Alert>
                              )}
                            <div className="prose prose-sm max-w-none prose-p:text-foreground prose-strong:text-foreground prose-headings:text-foreground prose-li:text-foreground">
                              <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={{
                                p: ({children}) => <p className="mb-2 last:mb-0 text-sm">{children}</p>,
                                strong: ({children}) => <strong className="font-semibold">{children}</strong>,
                              }}>
                                {rootCauseData.overall_improvement_suggestion}
                              </ReactMarkdown>
                            </div>
                          </div>
                        )}
                        {rootCauseTopics && rootCauseTopics.length > 0 && (
                          <TopicList
                            topics={rootCauseTopics}
                            topicCategoryInfoByKey={topicCategoryInfoByKey}
                            onTopicFilter={handleTopicFilter}
                            activeTopicLabel={selectedTopicLabel}
                          />
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Show score results panel during loading or when results exist, hidden only in narrow detail mode */}
        {(!showScoreResultInNarrowView) && (isResultsLoading || showResultsList) && (
          <div className={`w-full ${showAsColumns ? 'h-full' : 'h-[500px] mt-6'} flex flex-col overflow-hidden`}>
            {activeFilterChipLabel && (
              <div className="mb-2">
                <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-foreground">
                  {activeFilterChipLabel}
                </span>
              </div>
            )}
            <div className="h-full overflow-y-auto">
              <EvaluationTaskScoreResults
                results={parsedScoreResults}
                accuracy={data.accuracy ?? 0}
                selectedPredictedValue={selectedPredictedActual.predicted}
                selectedActualValue={selectedPredictedActual.actual}
                selectedItemIds={activeFilteredItemIds}
                onResultSelect={handleScoreResultSelect}
                selectedScoreResult={selectedScoreResult}
                isLoading={isResultsLoading}
              />
            </div>
          </div>
        )}

        {/* Only show the score result detail in column layout if not already showing it in narrow view */}
        {showResultDetail && !showScoreResultInNarrowView && selectedScoreResult && (
          <div className={`w-full ${showAsColumns ? 'h-full' : 'h-full'} flex flex-col overflow-hidden`}>
            <ScoreResultComponent
              result={{
                id: selectedScoreResult.id,
                value: String(selectedScoreResult.value),
                confidence: selectedScoreResult.confidence,
                explanation: selectedScoreResult.explanation,
                metadata: selectedScoreResult.metadata || {
                  human_label: null,
                  correct: false,
                  human_explanation: null,
                  text: null
                },
                trace: selectedScoreResult.trace,
                itemId: selectedScoreResult.itemId,
                itemIdentifiers: (selectedScoreResult as any).itemIdentifiers,
                feedbackItem: (selectedScoreResult as any).feedbackItem || null
              }}
              variant="detail"
              onClose={handleScoreResultClose}
              rcaDetailedCause={selectedItemRcaContext?.detailed_cause}
              rcaSuggestedFix={selectedItemRcaContext?.suggested_fix}
              misclassificationCategory={selectedItemRcaContext?.misclassification_category}
              misclassificationConfidence={selectedItemRcaContext?.misclassification_confidence}
              misclassificationRationale={selectedItemRcaContext?.misclassification_rationale}
              misclassificationEvidenceQuote={selectedItemRcaContext?.misclassification_evidence_quote}
              misclassificationConfigFixability={selectedItemRcaContext?.misclassification_config_fixability}
              misclassificationEvidence={selectedItemRcaContext?.misclassification_evidence}
              misclassificationMechanicalSubtype={selectedItemRcaContext?.misclassification_mechanical_subtype}
              misclassificationMechanicalDetails={selectedItemRcaContext?.misclassification_mechanical_details}
            />
          </div>
        )}
      </div>
    </div>
  )
}, (prevProps, nextProps) => {
  // Add logging for memo comparison
  const stagesChanged = (() => {
    const prevStages = prevProps.data.task?.stages?.items || [];
    const nextStages = nextProps.data.task?.stages?.items || [];
    if (prevStages.length !== nextStages.length) return true;
    return prevStages.some((s, i) => {
      const ns = nextStages[i];
      return !ns || s.name !== ns.name || s.status !== ns.status || s.processedItems !== ns.processedItems || s.totalItems !== ns.totalItems;
    });
  })();

  const shouldUpdate = 
    prevProps.extra !== nextProps.extra || 
    prevProps.isSelected !== nextProps.isSelected ||
    prevProps.selectedScoreResultId !== nextProps.selectedScoreResultId ||
    prevProps.isFullWidth !== nextProps.isFullWidth ||
    prevProps.commandDisplay !== nextProps.commandDisplay ||
    // evaluation identity changed
    prevProps.data.id !== nextProps.data.id ||
    // progress / metrics / status changes
    prevProps.data.processedItems !== nextProps.data.processedItems ||
    prevProps.data.totalItems !== nextProps.data.totalItems ||
    prevProps.data.accuracy !== nextProps.data.accuracy ||
    prevProps.data.status !== nextProps.data.status ||
    prevProps.data.elapsedSeconds !== nextProps.data.elapsedSeconds ||
    prevProps.data.estimatedRemainingSeconds !== nextProps.data.estimatedRemainingSeconds ||
    stagesChanged ||
    // score results list changes
    prevProps.data.scoreResults?.length !== nextProps.data.scoreResults?.length ||
    !isEqual(prevProps.data.scoreResults, nextProps.data.scoreResults);

  // Reduced logging

  return !shouldUpdate;
});

// Wrap the component with React.memo to prevent unnecessary re-renders
const EvaluationTask = React.memo(function EvaluationTaskComponent({ 
  variant = 'grid',
  task,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  selectedScoreResultId,
  onSelectScoreResult,
  extra,
  isSelected,
  commandDisplay: initialCommandDisplay = 'hide',
  onShare,
  onDelete,
  ...restProps
}: EvaluationTaskProps) {
  const [commandDisplay, setCommandDisplay] = useState(initialCommandDisplay);
  const [scoreVersionInfo, setScoreVersionInfo] = useState<{
    createdAt: string;
    isChampion: boolean;
  } | null>(null);
  const [baselineMetrics, setBaselineMetrics] = useState<EvaluationMetric[] | null>(null);

  const data = task.data ?? {} as EvaluationTaskData

  const evaluationNotes = useMemo(() => {
    try {
      const params = parseJsonDeep(data.parameters) as Record<string, unknown> | null
      if (params && typeof params.notes === 'string' && params.notes.trim()) {
        // Normalize Markdown: remove spaces before closing bold/italic delimiters so that
        // AI-generated text like "**label: **" renders correctly (CommonMark rejects a
        // closing delimiter that is preceded by whitespace).
        return params.notes.trim().replace(/ (\*+)/g, '$1')
      }
    } catch { /* ignore */ }
    return null
  }, [data.parameters])

  // Add more detailed logging for incoming data

  // Fetch score version information when scoreVersionId is available
  useEffect(() => {
    if (!task.scoreVersionId || variant !== 'detail') {
      setScoreVersionInfo(null);
      return;
    }

    const fetchScoreVersion = async () => {
      try {
        const client = getClient();
        const result = await client.graphql({
          query: `
            query GetScoreVersion($id: ID!) {
              getScoreVersion(id: $id) {
                id
                createdAt
                score {
                  championVersionId
                }
              }
            }
          `,
          variables: { id: task.scoreVersionId }
        });

        const scoreVersion = (result as any).data?.getScoreVersion;
        if (scoreVersion) {
          setScoreVersionInfo({
            createdAt: scoreVersion.createdAt,
            isChampion: scoreVersion.score?.championVersionId === task.scoreVersionId
          });
        }
      } catch (error) {
        console.error('Error fetching score version:', error);
        setScoreVersionInfo(null);
      }
    };

    fetchScoreVersion();
  }, [task.scoreVersionId, variant]);

  // Fetch baseline metrics when a baseline evaluation ID is stored in parameters.metadata
  const baselineEvaluationId = useMemo(() => {
    try {
      const params = parseJsonDeep(data.parameters) as Record<string, unknown> | null
      const metadata = parseJsonDeep(params?.metadata) as Record<string, unknown> | null
      return typeof metadata?.baseline === 'string' ? metadata.baseline : null
    } catch {
      return null
    }
  }, [data.parameters])

  const dataSetIdFromParameters = useMemo(() => {
    try {
      const params = parseJsonDeep(data.parameters) as Record<string, unknown> | null
      return typeof params?.dataset_id === 'string' ? params.dataset_id : null
    } catch {
      return null
    }
  }, [data.parameters])

  useEffect(() => {
    if (!baselineEvaluationId || variant !== 'detail') {
      setBaselineMetrics(null);
      return;
    }

    const fetchBaselineMetrics = async () => {
      try {
        const client = getClient();
        const result = await client.graphql({
          query: `
            query GetBaselineEvaluation($id: ID!) {
              getEvaluation(id: $id) {
                id
                metrics
              }
            }
          `,
          variables: { id: baselineEvaluationId }
        });

        const baselineEval = (result as any).data?.getEvaluation;
        if (baselineEval?.metrics) {
          try {
            const parsed = parseJsonDeep(baselineEval.metrics);
            if (Array.isArray(parsed)) {
              setBaselineMetrics(parsed as EvaluationMetric[]);
            } else if (parsed && typeof parsed === 'object') {
              const metrics = Object.entries(parsed as Record<string, unknown>)
                .map(([name, value]) => ({
                  name,
                  value: typeof value === 'number' ? value : Number(value),
                  priority: false
                }))
                .filter(metric => Number.isFinite(metric.value));
              setBaselineMetrics(metrics.length > 0 ? metrics : null);
            } else {
              setBaselineMetrics(null);
            }
          } catch {
            setBaselineMetrics(null);
          }
        } else {
          setBaselineMetrics(null);
        }
      } catch (error) {
        console.error('Error fetching baseline evaluation metrics:', error);
        setBaselineMetrics(null);
      }
    };

    fetchBaselineMetrics();
  }, [baselineEvaluationId, variant]);

  // Function to generate universal YAML code for evaluation
  const generateUniversalCode = useCallback((evaluationData: EvaluationTaskData) => {
    const yamlContent = `# Universal Code Snippet - Evaluation Results
# Generated for: ${evaluationData.title || 'Evaluation'}
# Type: Accuracy Evaluation
# Date: ${new Date().toISOString()}

evaluation:
  id: "${evaluationData.id}"
  type: "${task.type || 'Accuracy Evaluation'}"
  scorecard: "${task.scorecard || ''}"
  score: "${task.score || ''}"
  status: "${evaluationData.status}"
  
  # Performance Metrics
  accuracy: ${evaluationData.accuracy || 0}
  processed_items: ${evaluationData.processedItems || 0}
  total_items: ${evaluationData.totalItems || 0}
  inferences: ${evaluationData.inferences || 0}
  cost: ${evaluationData.cost || 0}
  
  # Timing Information
  started_at: "${evaluationData.startedAt || ''}"
  elapsed_seconds: ${evaluationData.elapsedSeconds || 0}
  estimated_remaining_seconds: ${evaluationData.estimatedRemainingSeconds || 0}
  
  # Additional Metrics
  metrics:${(() => {
    try {
      let metricsData = evaluationData.metrics;
      
      // Parse if string
      if (typeof metricsData === 'string') {
        metricsData = JSON.parse(metricsData);
      }
      
      // Ensure it's an array
      if (!Array.isArray(metricsData)) {
        if (metricsData && typeof metricsData === 'object') {
          metricsData = Object.entries(metricsData).map(([key, value]) => ({
            name: key,
            value: value as number,
            priority: false
          }));
        } else {
          return '';
        }
      }
      
      return metricsData.map(metric => `
    - name: "${metric.name}"
      value: ${metric.value}
      unit: "${metric.unit || ''}"
      priority: ${metric.priority || false}`).join('');
    } catch (e) {
      console.error('Error parsing metrics:', e);
      return '';
    }
  })()}
  
  # Error Information
  error_message: "${evaluationData.errorMessage || ''}"
  
  # Score Results Summary
  score_results_count: ${evaluationData.scoreResults?.length || 0}
  
  # Class Distribution
  dataset_balanced: ${evaluationData.isDatasetClassDistributionBalanced || false}
  predicted_balanced: ${evaluationData.isPredictedClassDistributionBalanced || false}

# Context: This YAML contains evaluation results and metrics for analysis by humans, AI models, and other systems.
# Usage: Can be used for reporting, monitoring, or further automated analysis.
`;
    return yamlContent;
  }, [task.type, task.scorecard, task.score]);

  // Function to handle copying universal code to clipboard
  const handleGetCode = useCallback(async () => {
    try {
      const universalCode = data.universalCode || generateUniversalCode(data);
      await navigator.clipboard.writeText(universalCode);
      toast({
        description: "Copied Universal Code to clipboard",
        duration: 2000,
      });
    } catch (error) {
      console.error('Failed to copy universal code:', error);
      toast({
        variant: "destructive",
        description: "Failed to copy code to clipboard",
        duration: 2000,
      });
    }
  }, [data, generateUniversalCode]);

  const metrics = useMemo(() => {
    if (variant === 'detail') {
      return (data.metrics ?? []).map(metric => {
        const normalizeMetricName = (name?: string) => (name ?? '').trim().toLowerCase()
        const baselineMetric = baselineMetrics?.find(
          bm => normalizeMetricName(bm.name) === normalizeMetricName(metric.name)
        )
        const beforeValue = baselineMetric !== undefined ? baselineMetric.value : undefined

        // Special handling for Alignment (Gwet's AC1)
        if (metric.name === 'Alignment') {
          return {
            value: metric.value,
            beforeValue,
            showComparisonLabel: beforeValue !== undefined,
            label: metric.name,
            information: getMetricInformation(metric.name),
            min: -1,           // AC1 ranges from -1 to 1
            max: 1,
            valueUnit: '',     // No percentage sign
            decimalPlaces: 2,  // Show 2 decimal places
            priority: metric.priority,
            segments: [
              { start: 0, end: 50, color: 'var(--gauge-inviable)' },      // -1 to 0
              { start: 50, end: 60, color: 'var(--gauge-converging)' },   // 0 to 0.2
              { start: 60, end: 75, color: 'var(--gauge-almost)' },       // 0.2 to 0.5
              { start: 75, end: 90, color: 'var(--gauge-viable)' },       // 0.5 to 0.8
              { start: 90, end: 100, color: 'var(--gauge-great)' }        // 0.8 to 1.0
            ]
          }
        }

        // Default handling for other metrics
        return {
          value: metric.value,
          beforeValue,
          showComparisonLabel: beforeValue !== undefined,
          label: metric.name,
          information: getMetricInformation(metric.name),
          max: metric.maximum ?? 100,        // Fixed: was 'maximum', should be 'max'
          valueUnit: metric.unit ?? '%',     // Fixed: was 'unit', should be 'valueUnit'
          priority: metric.priority
        }
      })
    }
    return [
      {
        value: data.accuracy ?? undefined,
        label: 'Accuracy',
        backgroundColor: 'var(--gauge-background)',
        priority: true
      }
    ]
  }, [variant, data.metrics, data.accuracy, baselineMetrics])

  const headerContent = useMemo(() => (
    variant === 'detail' ? (
      <div className="flex items-center space-x-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
             <Button 
               variant="ghost" 
               size="icon" 
               className="h-8 w-8 rounded-md bg-border"
               aria-label="More options"
             >
               <MoreHorizontal className="h-4 w-4" />
             </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => {
              handleGetCode();
            }}>
              <MessageSquareCode className="mr-2 h-4 w-4" />
              Get Code
            </DropdownMenuItem>
            {onShare && (
              <DropdownMenuItem onSelect={() => {
                onShare();
              }}>
                <Share className="mr-2 h-4 w-4" />
                Share
              </DropdownMenuItem>
            )}
            {onDelete && (
              <DropdownMenuItem onSelect={() => {
                onDelete(data.id);
              }}>
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
        {typeof onToggleFullWidth === 'function' && (
          <CardButton
            icon={Square}
            onClick={onToggleFullWidth}
          />
        )}
        {typeof onClose === 'function' && (
          <CardButton
            icon={X}
            onClick={() => {
              onClose();
            }}
          />
        )}
      </div>
    ) : null
  ), [variant, onToggleFullWidth, onClose, handleGetCode])

  const taskData = task.data?.task as TaskData | undefined;

  const taskWithDefaults = useMemo(() => {
    // Debug: Log what we're receiving in EvaluationTask
    
    return {
      id: task.id,
      type: task.type ? task.type.split(' ').map(word => 
        word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
      ).join(' ') : 'Unknown',
      scorecard: task.scorecard,
      score: task.score,
      time: task.time,
      description: variant === 'detail' ? undefined : task.summary,
      data: task.data,
      command: taskData?.command,
      stages: taskData?.stages?.items?.map(stage => ({
        key: stage.name,
        label: stage.name,
        color: stage.name === 'Processing' ? 'bg-secondary' : (
          stage.status === 'COMPLETED' || stage.status === 'RUNNING' ? 'bg-primary' :
          stage.status === 'FAILED' ? 'bg-false' :
          'bg-neutral'
        ),
        name: stage.name,
        order: stage.order,
        status: mapTaskStatus(stage.status),
        processedItems: stage.processedItems,
        totalItems: stage.totalItems,
        statusMessage: stage.statusMessage
      })) || [],
      currentStageName: taskData?.currentStageId || undefined,
      processedItems: task.data?.processedItems,
      totalItems: task.data?.totalItems,
      startedAt: taskData?.startedAt || task.data?.startedAt || undefined,
      estimatedCompletionAt: taskData?.estimatedCompletionAt || undefined,
      status: mapTaskStatus(taskData?.status || task.data?.status),
      dispatchStatus: taskData?.dispatchStatus,
      celeryTaskId: taskData?.celeryTaskId,
      workerNodeId: taskData?.workerNodeId,
      completedAt: taskData?.completedAt || undefined,
      errorMessage: taskData?.errorMessage || task.data?.errorMessage || undefined,
      scorecardId: task.scorecardId,
      scoreId: task.scoreId,
      scoreVersionId: task.scoreVersionId,
      dataSetId: task.data?.dataSetId ?? task.dataSetId ?? dataSetIdFromParameters ?? undefined
    };
  }, [task, taskData, variant, dataSetIdFromParameters]);

  // Type assertion to ensure all properties match BaseTaskProps
  const typedTask = {
    ...taskWithDefaults,
    startedAt: taskWithDefaults.startedAt || undefined,
    completedAt: taskWithDefaults.completedAt || undefined,
    estimatedCompletionAt: taskWithDefaults.estimatedCompletionAt || undefined,
    errorMessage: taskWithDefaults.errorMessage || undefined,
    status: taskWithDefaults.status,
    dispatchStatus: taskWithDefaults.dispatchStatus,
    celeryTaskId: taskWithDefaults.celeryTaskId,
    workerNodeId: taskWithDefaults.workerNodeId,
    currentStageName: taskWithDefaults.currentStageName,
    stages: taskWithDefaults.stages
  } as unknown as BaseTaskProps['task']

  // Update TaskStatus components to handle null values
  const renderTaskStatus = (data: EvaluationTaskData) => {
    const taskStages = data.task?.stages?.items?.map(stage => ({
      key: stage.name,
      label: stage.name,
      color: stage.name === 'Processing' ? 'bg-secondary' : (
        stage.status === 'COMPLETED' || stage.status === 'RUNNING' ? 'bg-primary' :
        stage.status === 'FAILED' ? 'bg-false' :
        'bg-neutral'
      ),
      name: stage.name,
      order: stage.order,
      status: mapTaskStatus(stage.status),
      processedItems: stage.processedItems,
      totalItems: stage.totalItems,
      statusMessage: stage.statusMessage,
      startedAt: stage.startedAt || undefined,
      completedAt: stage.completedAt || undefined,
      estimatedCompletionAt: stage.estimatedCompletionAt || undefined
    })) || []

    const taskStatus = {
      showStages: true,
      status: mapTaskStatus(data.task?.status || data.status),
      stageConfigs: taskStages,
      stages: taskStages,
      processedItems: data.processedItems,
      totalItems: data.totalItems,
      startedAt: data.task?.startedAt || data.startedAt || undefined,
      completedAt: data.task?.completedAt || undefined,
      estimatedCompletionAt: data.task?.estimatedCompletionAt || undefined,
      errorMessage: data.task?.errorMessage || data.errorMessage || undefined,
      command: data.task?.command || data.command,
      statusMessage: data.task?.stages?.items?.find(s => s.status === 'RUNNING')?.statusMessage || undefined,
      isSelected,
      elapsedSeconds: data.elapsedSeconds,
      estimatedRemainingSeconds: data.estimatedRemainingSeconds
    } as const

    return <TaskStatus {...taskStatus} />
  }

  return (
    <Task
      variant={variant}
      task={typedTask}
      onClick={onClick}
      controlButtons={controlButtons}
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      extra={extra}
      isSelected={isSelected}
      commandDisplay={commandDisplay}
      {...restProps}
      renderHeader={(props) => (
        <div className={cn(
          "space-y-1.5 p-0 flex flex-col items-start w-full max-w-full",
          variant === 'detail' && "px-1"
        )}>
          <div className="flex justify-between items-start w-full max-w-full gap-3 overflow-hidden">
            <div className="flex flex-col pb-1 leading-none min-w-0 flex-1 overflow-hidden">
              {variant === 'detail' && (
                <div className="flex items-center gap-2">
                  <FlaskConical className="h-5 w-5 text-muted-foreground" />
                  <span className="text-lg font-semibold text-muted-foreground">{props.task.type}</span>
                </div>
              )}
              {/* Grid variant: show all metadata inline in header */}
              {variant !== 'detail' && (
                <>
                  {props.task.name && (
                    <div className="font-semibold text-sm truncate">{props.task.name}</div>
                  )}
                  {props.task.description && (
                    <div className="text-sm text-muted-foreground truncate">
                      {props.task.description}
                    </div>
                  )}
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
                  <Timestamp time={props.task.time} variant="relative" />
                  <ProgressBarTiming
                    startedAt={data.startedAt || (data.task as any)?.startedAt}
                    completedAt={(data.task as any)?.completedAt}
                    isInProgress={data.status?.toUpperCase() === 'RUNNING'}
                    className="text-muted-foreground"
                  />
                  {evaluationNotes && (
                    <div className="mt-3 mb-0 prose prose-sm max-w-none text-muted-foreground prose-p:text-muted-foreground prose-strong:text-muted-foreground prose-headings:text-muted-foreground prose-li:text-muted-foreground">
                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={{
                        p: ({children}) => <p className="mb-1 last:mb-0 text-sm">{children}</p>,
                        strong: ({children}) => <strong className="font-semibold">{children}</strong>,
                      }}>
                        {evaluationNotes}
                      </ReactMarkdown>
                    </div>
                  )}
                </>
              )}
            </div>
            <div className="flex flex-col items-end flex-shrink-0">
              {variant === 'grid' ? (
                <div className="flex flex-col items-center gap-1">
                  <div className="flex items-center gap-2">
                    <div className="text-muted-foreground">
                      <FlaskConical className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
                    </div>
                    {(onShare || onDelete) && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <CardButton
                            icon={MoreHorizontal}
                            onClick={() => {}}
                          />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onSelect={() => {
                            handleGetCode();
                          }}>
                            <MessageSquareCode className="mr-2 h-4 w-4" />
                            Get Code
                          </DropdownMenuItem>
                          {onShare && (
                            <DropdownMenuItem onSelect={() => {
                              onShare();
                            }}>
                              <Share className="mr-2 h-4 w-4" />
                              Share
                            </DropdownMenuItem>
                          )}
                          {onDelete && (
                            <DropdownMenuItem onSelect={() => {
                              onDelete(data.id);
                            }}>
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground text-center">
                    {(() => {
                      const [firstWord, ...restWords] = props.task.type.split(/\s+/);
                      return (
                        <>
                          {firstWord}<br />
                          {restWords.join(' ')}
                        </>
                      );
                    })()}
                  </div>
                </div>
              ) : (
                <div className="flex gap-2">
                  {headerContent}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      renderContent={(props) => {
        // Detail variant: metadata section that scrolls with content
        const detailMetadata = variant === 'detail' ? (
          <div className="px-4 flex flex-col leading-none">
            {props.task.name && (
              <div className="font-semibold text-sm">{props.task.name}</div>
            )}
            {props.task.description && (
              <div className="text-sm text-muted-foreground">
                {props.task.description}
              </div>
            )}
            {props.task.scorecard && props.task.scorecard.trim() !== '' && (
              <div className="flex items-center gap-1.5 font-semibold text-sm min-w-0">
                <span className="truncate">{props.task.scorecard}</span>
                {taskWithDefaults.scorecardId && (
                  <Link
                    href={`/lab/scorecards/${taskWithDefaults.scorecardId}`}
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
                {taskWithDefaults.scorecardId &&
                  taskWithDefaults.scoreId &&
                  taskWithDefaults.scoreVersionId && (
                    <Link
                      href={`/lab/scorecards/${taskWithDefaults.scorecardId}/scores/${taskWithDefaults.scoreId}/versions/${taskWithDefaults.scoreVersionId}`}
                      className="flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </Link>
                  )}
              </div>
            )}
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>Score Version:</span>
              {scoreVersionInfo ? (
                <>
                  <Timestamp time={scoreVersionInfo.createdAt} variant="relative" />
                  {scoreVersionInfo.isChampion && (
                    <span className="px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium">
                      Champion
                    </span>
                  )}
                </>
              ) : (
                <span>Unavailable</span>
              )}
            </div>
            {taskWithDefaults.dataSetId && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>Dataset:</span>
                <span className="font-mono truncate max-w-[22rem]">{taskWithDefaults.dataSetId}</span>
                <Link
                  href={`/lab/datasets/${taskWithDefaults.dataSetId}`}
                  className="flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                </Link>
              </div>
            )}
            {task.data?.cost != null && task.data.cost > 0 && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>Cost:</span>
                <span>
                  ${task.data.cost.toFixed(4)} total
                  {task.data.processedItems > 0 && (
                    <> &middot; ${(task.data.cost / task.data.processedItems).toFixed(6)}/item</>
                  )}
                </span>
              </div>
            )}
            <Timestamp time={props.task.time} variant="relative" />
            <ProgressBarTiming
              startedAt={data.startedAt || (data.task as any)?.startedAt}
              completedAt={(data.task as any)?.completedAt}
              isInProgress={data.status?.toUpperCase() === 'RUNNING'}
              className="text-muted-foreground"
            />
            {evaluationNotes && (
              <div className="mt-3 mb-0 prose prose-sm max-w-none text-muted-foreground prose-p:text-muted-foreground prose-strong:text-muted-foreground prose-headings:text-muted-foreground prose-li:text-muted-foreground">
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={{
                  p: ({children}) => <p className="mb-1 last:mb-0 text-sm">{children}</p>,
                  strong: ({children}) => <strong className="font-semibold">{children}</strong>,
                }}>
                  {evaluationNotes}
                </ReactMarkdown>
              </div>
            )}
          </div>
        ) : null;

        return (
          <>
            {detailMetadata}
            <TaskContent {...props} hideTaskStatus={true}>
              {variant === 'grid' ? (
                <GridContent data={data} extra={extra} isSelected={isSelected} />
              ) : (
                <DetailContent
                  data={data}
                  isFullWidth={isFullWidth ?? false}
                  metrics={metrics}
                  metricsVariant="detail"
                  selectedScoreResultId={selectedScoreResultId}
                  onSelectScoreResult={onSelectScoreResult}
                  extra={extra}
                  isSelected={isSelected}
                  commandDisplay={commandDisplay}
                  onCommandDisplayChange={setCommandDisplay}
                />
              )}
            </TaskContent>
          </>
        );
      }}
    />
  )
}, (prevProps, nextProps) => {
  // Custom comparison function to prevent unnecessary re-renders
  // Only re-render if these specific props change
  const stageComparison = isEqual(
    prevProps.task.data?.task?.stages?.items,
    nextProps.task.data?.task?.stages?.items
  );
  
  // Check for task data changes more comprehensively
  const taskDataChanged = !isEqual(prevProps.task.data, nextProps.task.data);
  
  const shouldNotRerender = (
    prevProps.variant === nextProps.variant &&
    prevProps.task.id === nextProps.task.id &&
    prevProps.task.status === nextProps.task.status &&
    prevProps.isSelected === nextProps.isSelected &&
    prevProps.selectedScoreResultId === nextProps.selectedScoreResultId &&
    prevProps.isFullWidth === nextProps.isFullWidth &&
    // CHECK FOR SCORECARD/SCORE CHANGES - CRITICAL FOR REALTIME UPDATES
    prevProps.task.scorecard === nextProps.task.scorecard &&
    prevProps.task.score === nextProps.task.score &&
    // CHECK FOR TASK STAGE CHANGES - CRITICAL FOR REALTIME STAGE UPDATES
    stageComparison &&
    // CHECK FOR ANY TASK DATA CHANGES
    !taskDataChanged
  );
  
  const prevStages = prevProps.task.data?.task?.stages?.items?.map(s => `${s.name}:${s.status}`).join(',') || 'none';
  const nextStages = nextProps.task.data?.task?.stages?.items?.map(s => `${s.name}:${s.status}`).join(',') || 'none';
  
  if (shouldNotRerender) {
  } else {
  }
  
  return shouldNotRerender;
});

export default EvaluationTask;

function getMetricInformation(metricName: string): string {
  const descriptions: Record<string, string> = {
    "Accuracy": "Accuracy measures the overall correctness of predictions, showing the " +
      "percentage of all cases (both positive and negative) that were " +
      "correctly classified.\n\n" +
      "While accuracy is a good general metric, it can be misleading when classes " +
      "are imbalanced. For example, if only 1% of cases are positive, a model " +
      "that always predicts negative would have 99% accuracy but be useless for " +
      "detecting positive cases.",
    "Precision": "Precision measures the accuracy of positive predictions, showing " +
      "the percentage of predicted positive cases that were actually positive.\n\n" +
      "High precision is crucial when false positives are costly - for example, " +
      "when flagging content that will be removed or when identifying cases that " +
      "will trigger penalties. In these cases, we want to be very confident in " +
      "our positive predictions.",
    "Sensitivity": "Sensitivity (also called Recall) measures the ability to correctly " +
      "identify positive cases, showing the percentage of actual positive " +
      "cases that were correctly identified.\n\n" +
      "High sensitivity is essential when missing positive cases is costly - for " +
      "example, when detecting regulated content that must be caught, or when " +
      "screening for high-risk conditions. In these cases, we prefer false " +
      "positives over missing actual positives.",
    "Specificity": "Specificity measures the ability to correctly identify negative " +
      "cases, showing the percentage of actual negative cases that were " +
      "correctly identified.\n\n" +
      "High specificity indicates the model is good at ruling out false " +
      "positives. This is important in scenarios where we want to avoid " +
      "overwhelming review systems with false alarms, or when we need to " +
      "confidently clear cases as negative."
  }
  return descriptions[metricName] || ""
}
