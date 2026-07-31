'use client'

import React, { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileDown,
  Loader2,
  PlayCircle,
  ShieldCheck,
  XCircle,
} from 'lucide-react'

import OptimizationOpportunityDistribution, {
  type OptimizationOpportunityDisposition,
  type OptimizationOpportunityRow,
} from '@/components/OptimizationOpportunityDistribution'
import { issueTaskArtifactReadTicket } from '@/lib/artifact-ticket-client'
import {
  buildReportArtifactHref,
  parseArtifactDescriptor,
  readTaskArtifact,
  type ArtifactDescriptor,
} from '@/lib/report-artifacts'
import { cn } from '@/lib/utils'
import type { BlockComponent, ReportBlockProps } from './ReportBlock'

type PresentationOverview = {
  lifecycle_status?: string
  coverage_status?: string
  inventory_coverage_status?: string
  analysis_coverage_status?: string
  scorecards_inspected?: number
  scorecards_in_scope?: number
  evidence_ranked_score_count?: number
  ranked_score_count?: number
  unranked_score_count?: number
  cooldown_excluded_count?: number
  assessed_score_count?: number
  assessment_progress?: string
  diagnosis_coverage?: string
  ranking_cutoff?: string
  ranking_policy?: string
  priority_display_limit?: number
  priority_displayed_count?: number
  priority_cutoff_rank?: number
  priority_cutoff_opportunity?: number
  ranked_below_priority_cutoff?: number
  diagnosis_selection_policy?: string
  diagnosis_top_priority_count?: number
  diagnosis_monitoring_candidate_count?: number
  diagnosis_selected_count?: number
  diagnosis_scheduled_count?: number
  diagnosis_deferred_count?: number
  diagnosis_skipped_count?: number
  diagnosis_incomplete_count?: number
  diagnosis_completed_count?: number
  diagnosis_max_count?: number
  pending_approval_count?: number
  execution_mode?: string
  execution_selected_count?: number
  execution_launched_count?: number
  execution_rejected_count?: number
  execution_named_selected_count?: number
  execution_named_launched_count?: number
  execution_named_rejected_count?: number
  execution_detail_coverage?: string
  execution_detail_limitation?: string
  optimizer_review_count?: number
  current_activity?: string
  next_checkpoint?: string
  notes?: string
}

type PriorityRow = {
  rank?: number
  evidence_rank?: number
  candidate_rank?: number | null
  scorecard_name?: string
  score_name?: string
  opportunity?: number
  evidence_count?: number
  disagreement_rate?: number
  readiness?: string
  collection_state?: string
  rationale?: string
  next_action?: string
  policy_disposition?: string
  policy_reason?: string
  review_disposition?: string
  eligibility_timestamp?: string | null
  execution_status?: string
  execution_reason?: string
  execution_authorization_source?: string
  dashboard_url?: string | null
}

type ScorecardCard = {
  scorecard_ref: string
  scorecard_name: string
  score_count: number
  primary_disposition_counts?: Record<string, number>
  primary_decision_mix: Record<string, number>
  reviewed_error_opportunity: number
  artifacts: ArtifactDescriptor[]
}

type PrimaryDisposition =
  | 'promotion_ready'
  | 'continue_optimization'
  | 'stakeholder_decision_required'
  | 'no_safe_improvement'
  | 'failed_or_incomplete'
  | 'awaiting_optimizer_review'
  | 'optimization_in_progress'
  | 'optimizer_launching'
  | 'awaiting_optimization_approval'
  | 'stakeholder_clarification_required'
  | 'guideline_or_code_repair'
  | 'feedback_curation_review'
  | 'monitoring_or_diminishing_returns'
  | 'targeted_feedback_collection'
  | 'cooldown'
  | 'insufficient_evidence'
  | 'not_selected'

type AttentionRow = {
  scorecard_name?: string
  score_name?: string
  primary_disposition?: PrimaryDisposition | string
  secondary_issue_flags?: string[]
  evidence_count?: number
  severity?: number | string
  rationale?: string
  next_action?: string
  dashboard_url?: string | null
}

type OptimizationOutcome = {
  scorecard_name?: string
  score_name?: string
  primary_disposition?: PrimaryDisposition | string
  secondary_issue_flags?: string[]
  evidence_count?: number
  outcome?: string
  readiness?: string
  promotion_readiness?: string
  trend?: string
  rationale?: string
  next_action?: string
  dashboard_url?: string | null
}

export type StakeholderPresentation = {
  overview: PresentationOverview
  score_count: number
  scorecard_count: number
  primary_disposition_counts?: Record<string, number>
  primary_decision_mix: Record<string, number>
  secondary_issue_counts: Record<string, number>
  attention_queue: AttentionRow[]
  questions_and_issues: ScoreQuestion[]
  optimization_outcomes: OptimizationOutcome[]
  opportunity_distribution: OptimizationOpportunityRow[]
  top_priorities: PriorityRow[]
  scorecards: ScorecardCard[]
}

type ScoreDetail = {
  score_name?: string
  evidence_rank?: number
  candidate_rank?: number | null
  valid_feedback_count?: number
  reviewed_disagreements?: number
  disagreement_rate?: number
  readiness?: string
  primary_disposition?: PrimaryDisposition | string
  secondary_issue_flags?: string[]
  outcome?: string
  promotion_readiness?: string
  trend?: string
  rationale?: string
  next_action?: string
  policy_disposition?: string
  policy_reason?: string
  review_disposition?: string
  eligibility_timestamp?: string | null
  execution_status?: string
  execution_reason?: string
  execution_authorization_source?: string
  dashboard_url?: string | null
  artifacts?: ArtifactDescriptor[]
}

type ScoreQuestion = {
  kind?: string
  issue_flag?: string
  issue_severity?: number
  score_name?: string
  scorecard_name?: string
  affected_evidence_count?: number
  evidence_count?: number
  finding?: string
  rationale?: string
  next_action?: string
  dashboard_url?: string | null
}

export type ScorecardPresentation = {
  scorecard_name: string
  scores: ScoreDetail[]
  questions_and_issues: ScoreQuestion[]
}

export type ScorecardDetailsByReference = Record<string, ScorecardPresentation>

type LiveProgress = {
  phase: string
  subphase?: 'inventory' | 'activity_evidence' | 'feedback_analysis'
  current: number
  total: number | null
  message?: string
  updatedAt?: string
  unit?: string
  state?: 'active' | 'retrying' | 'incomplete' | 'failed'
  elapsedSeconds?: number
  nextCheckpoint?: string
  heartbeatIntervalSeconds?: number
  artifactCounts?: Record<string, { completed: number, total: number }>
}

type CompactStatus = {
  presentation: ArtifactDescriptor | null
  liveProgress: LiveProgress | null
  durableMilestone: string | null
}

const DECISION_COLORS = [
  'bg-blue-500',
  'bg-amber-500',
  'bg-violet-500',
  'bg-emerald-500',
  'bg-slate-500',
  'bg-rose-500',
  'bg-cyan-500',
]

const PRIMARY_DISPOSITION_LABELS: Record<PrimaryDisposition, string> = {
  promotion_ready: 'Promotion ready',
  continue_optimization: 'Continue optimization',
  stakeholder_decision_required: 'Stakeholder decision required',
  no_safe_improvement: 'No safe improvement',
  failed_or_incomplete: 'Failed or incomplete',
  awaiting_optimizer_review: 'Awaiting optimizer review',
  optimization_in_progress: 'Optimization in progress',
  optimizer_launching: 'Optimizer launching',
  awaiting_optimization_approval: 'Awaiting optimization approval',
  stakeholder_clarification_required: 'Stakeholder clarification required',
  guideline_or_code_repair: 'Guideline or code repair',
  feedback_curation_review: 'Feedback curation review',
  monitoring_or_diminishing_returns: 'Monitoring or diminishing returns',
  targeted_feedback_collection: 'Targeted feedback collection',
  cooldown: 'Cooldown',
  insufficient_evidence: 'Insufficient evidence',
  not_selected: 'Not selected',
}

const PRIMARY_DISPOSITION_KEYS: ReadonlySet<string> = new Set(Object.keys(PRIMARY_DISPOSITION_LABELS))

const PRIMARY_DISPOSITION_COLORS: Partial<Record<PrimaryDisposition, string>> = {
  promotion_ready: 'bg-emerald-500',
  continue_optimization: 'bg-blue-500',
  stakeholder_decision_required: 'bg-amber-500',
  no_safe_improvement: 'bg-slate-500',
  failed_or_incomplete: 'bg-rose-500',
  awaiting_optimizer_review: 'bg-violet-500',
  optimization_in_progress: 'bg-cyan-500',
  optimizer_launching: 'bg-sky-500',
  awaiting_optimization_approval: 'bg-amber-400',
  stakeholder_clarification_required: 'bg-orange-500',
  guideline_or_code_repair: 'bg-rose-400',
  feedback_curation_review: 'bg-fuchsia-500',
  monitoring_or_diminishing_returns: 'bg-teal-500',
  targeted_feedback_collection: 'bg-indigo-500',
  cooldown: 'bg-slate-400',
  insufficient_evidence: 'bg-zinc-400',
  not_selected: 'bg-zinc-300',
}

const LIFECYCLE_GROUPS = [
  {
    key: 'awaiting-approval',
    label: 'Awaiting approval',
    dispositions: [
      'awaiting_optimization_approval',
      'stakeholder_decision_required',
      'stakeholder_clarification_required',
    ],
    icon: Clock3,
    tone: 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
  },
  {
    key: 'launching-running',
    label: 'Launching or running',
    dispositions: ['optimizer_launching', 'optimization_in_progress'],
    icon: PlayCircle,
    tone: 'bg-cyan-500/10 text-cyan-700 dark:text-cyan-300',
  },
  {
    key: 'review-pending',
    label: 'Review pending',
    dispositions: [
      'awaiting_optimizer_review',
      'guideline_or_code_repair',
      'feedback_curation_review',
    ],
    icon: CircleHelp,
    tone: 'bg-violet-500/10 text-violet-700 dark:text-violet-300',
  },
  {
    key: 'promotion-ready',
    label: 'Promotion ready',
    dispositions: ['promotion_ready'],
    icon: ShieldCheck,
    tone: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  },
  {
    key: 'continue-or-no-safe-improvement',
    label: 'Continue or monitor',
    dispositions: [
      'continue_optimization',
      'no_safe_improvement',
      'monitoring_or_diminishing_returns',
      'targeted_feedback_collection',
      'cooldown',
      'insufficient_evidence',
      'not_selected',
    ],
    icon: CheckCircle2,
    tone: 'bg-blue-500/10 text-blue-700 dark:text-blue-300',
  },
  {
    key: 'failed-incomplete',
    label: 'Failed or incomplete',
    dispositions: ['failed_or_incomplete'],
    icon: XCircle,
    tone: 'bg-rose-500/10 text-rose-700 dark:text-rose-300',
  },
] as const

function record(value: unknown): Record<string, any> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const prototype = Object.getPrototypeOf(value)
  return prototype === Object.prototype || prototype === null ? value as Record<string, any> : null
}

function countMap(
  value: unknown,
  name: string,
  allowedKeys?: ReadonlySet<string>,
): Record<string, number> | null {
  if (value === undefined) return null
  const map = record(value)
  if (
    !map
    || Object.values(map).some(count => typeof count !== 'number' || !Number.isFinite(count) || count < 0)
    || (allowedKeys && Object.keys(map).some(key => !allowedKeys.has(key)))
  ) {
    throw new Error(`Stakeholder presentation contains an invalid count map for ${name}.`)
  }
  return map as Record<string, number>
}

function finiteNonNegativeNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
}

function malformedRow(value: unknown, context: string): Record<string, any> {
  const row = record(value)
  if (!row) throw new Error(`${context}.`)
  return row
}

function validateOptionalStrings(
  row: Record<string, any>,
  fields: readonly string[],
  context: string,
): void {
  for (const field of fields) {
    if (row[field] != null && typeof row[field] !== 'string') {
      throw new Error(`${context}: ${field} must be text.`)
    }
  }
}

function validateOptionalNumbers(
  row: Record<string, any>,
  fields: readonly string[],
  context: string,
): void {
  for (const field of fields) {
    if (row[field] != null && finiteNonNegativeNumber(row[field]) === null) {
      throw new Error(`${context}: ${field} must be a non-negative number.`)
    }
  }
}

function validateOptionalStringList(
  row: Record<string, any>,
  field: string,
  context: string,
): void {
  const value = row[field]
  if (value != null && (!Array.isArray(value) || value.some(item => typeof item !== 'string'))) {
    throw new Error(`${context}: ${field} must be a list of text values.`)
  }
}

function validateOptionalPrimaryDisposition(
  row: Record<string, any>,
  context: string,
): void {
  const value = row.primary_disposition
  if (value != null && (typeof value !== 'string' || !PRIMARY_DISPOSITION_KEYS.has(value))) {
    throw new Error(`${context}: primary_disposition must be a canonical disposition.`)
  }
}

function parseAttentionRow(value: unknown): AttentionRow {
  const context = 'Stakeholder presentation contains a malformed attention queue row'
  const row = malformedRow(value, context)
  validateOptionalStrings(row, [
    'scorecard_name', 'score_name', 'primary_disposition', 'rationale', 'next_action', 'dashboard_url',
  ], context)
  validateOptionalPrimaryDisposition(row, context)
  validateOptionalNumbers(row, ['evidence_count'], context)
  validateOptionalStringList(row, 'secondary_issue_flags', context)
  if (
    row.severity != null
    && typeof row.severity !== 'string'
    && finiteNonNegativeNumber(row.severity) === null
  ) {
    throw new Error(`${context}: severity must be text or a non-negative number.`)
  }
  return row as AttentionRow
}

function parseQuestionRow(value: unknown, container = 'Stakeholder presentation'): ScoreQuestion {
  const context = container === 'Scorecard details'
    ? 'Scorecard details contain a malformed question or issue row'
    : 'Stakeholder presentation contains a malformed question or issue row'
  const row = malformedRow(value, context)
  validateOptionalStrings(row, [
    'kind', 'issue_flag', 'score_name', 'scorecard_name', 'finding', 'rationale', 'next_action', 'dashboard_url',
  ], context)
  validateOptionalNumbers(row, ['issue_severity', 'affected_evidence_count', 'evidence_count'], context)
  return row as ScoreQuestion
}

function parseOutcomeRow(value: unknown): OptimizationOutcome {
  const context = 'Stakeholder presentation contains a malformed outcome row'
  const row = malformedRow(value, context)
  validateOptionalStrings(row, [
    'scorecard_name', 'score_name', 'primary_disposition', 'outcome', 'readiness',
    'promotion_readiness', 'trend', 'rationale', 'next_action', 'dashboard_url',
  ], context)
  validateOptionalPrimaryDisposition(row, context)
  validateOptionalNumbers(row, ['evidence_count'], context)
  validateOptionalStringList(row, 'secondary_issue_flags', context)
  return row as OptimizationOutcome
}

function parsePriorityRow(value: unknown): PriorityRow {
  const context = 'Stakeholder presentation contains a malformed priority row'
  const row = malformedRow(value, context)
  validateOptionalStrings(row, [
    'scorecard_name', 'score_name', 'readiness', 'collection_state', 'rationale', 'next_action',
    'policy_disposition', 'policy_reason', 'review_disposition', 'eligibility_timestamp',
    'execution_status', 'execution_reason', 'execution_authorization_source', 'dashboard_url',
  ], context)
  validateOptionalNumbers(row, [
    'rank', 'evidence_rank', 'candidate_rank', 'opportunity', 'evidence_count', 'disagreement_rate',
  ], context)
  return row as PriorityRow
}

function parseScoreDetailRow(value: unknown): ScoreDetail {
  const context = 'Scorecard details contain a malformed score row'
  const row = malformedRow(value, context)
  validateOptionalStrings(row, [
    'score_name', 'readiness', 'primary_disposition', 'outcome', 'promotion_readiness', 'trend',
    'rationale', 'next_action', 'policy_disposition', 'policy_reason', 'review_disposition',
    'eligibility_timestamp', 'execution_status', 'execution_reason',
    'execution_authorization_source', 'dashboard_url',
  ], context)
  validateOptionalPrimaryDisposition(row, context)
  validateOptionalNumbers(row, [
    'evidence_rank', 'candidate_rank', 'valid_feedback_count', 'reviewed_disagreements', 'disagreement_rate',
  ], context)
  validateOptionalStringList(row, 'secondary_issue_flags', context)
  if (row.artifacts != null && !Array.isArray(row.artifacts)) {
    throw new Error(`${context}: artifacts must be a list.`)
  }
  return row as ScoreDetail
}

function label(value: string): string {
  const text = value.replaceAll('_', ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function primaryDispositionLabel(value: string | undefined): string {
  if (!value) return 'Not selected'
  return PRIMARY_DISPOSITION_LABELS[value as PrimaryDisposition] || label(value)
}

function primaryDispositionColor(value: string | undefined, index = 0): string {
  if (!value) return 'bg-zinc-300'
  return PRIMARY_DISPOSITION_COLORS[value as PrimaryDisposition]
    || DECISION_COLORS[index % DECISION_COLORS.length]
}

function executionStatusLabel(value: string | undefined): string {
  switch (value) {
    case 'automatic_selected': return 'Automatic selected'
    case 'automatic_launched': return 'Automatic launched'
    case 'automatic_rejected': return 'Not selected automatically'
    default: return value ? label(value) : ''
  }
}

function numericCount(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : 0
}

function lifecycleCount(
  counts: Record<string, number>,
  dispositions: readonly string[],
): number {
  return dispositions.reduce((total, disposition) => total + numericCount(counts[disposition]), 0)
}

function affectedEvidenceLabel(value: unknown): string {
  const count = numericCount(value)
  return `${count} affected feedback item${count === 1 ? '' : 's'}`
}

function severityRank(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value) && value >= 0) return value
  const normalized = typeof value === 'string' ? value.toLowerCase() : ''
  return ({ critical: 0, high: 1, medium: 2, low: 3 } as Record<string, number>)[normalized] ?? 99
}

function opportunityDisposition(value: unknown): OptimizationOpportunityDisposition {
  switch (value) {
    case 'selected_for_review': return 'selected_for_review'
    case 'cooldown': return 'cooldown'
    case 'blocked': return 'blocked'
    case 'incomplete': return 'incomplete'
    default: return 'eligible'
  }
}

function reportIdFromLocation(): string | null {
  if (typeof window === 'undefined') return null
  const match = window.location.pathname.match(/^\/lab\/reports\/([^/]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

function parseCompactStatus(output: ReportBlockProps['output']): CompactStatus {
  let parsed: unknown = output
  if (typeof output === 'string') {
    try {
      parsed = JSON.parse(output)
    } catch {
      return { presentation: null, liveProgress: null, durableMilestone: null }
    }
  }
  const envelope = record(parsed)
  const preview = record(envelope?.preview)
  const summary = record(preview?.summary)
  const rawProgress = record(summary?.live_progress)
  const durableMilestone = typeof summary?.milestone === 'string'
    ? summary.milestone.trim().toLowerCase()
    : null
  const current = Number(rawProgress?.current)
  const rawTotal = rawProgress?.total
  const total = rawTotal === null || rawTotal === undefined ? null : Number(rawTotal)
  const phase = typeof rawProgress?.phase === 'string' ? rawProgress.phase.trim() : ''
  const rawState = typeof rawProgress?.state === 'string' ? rawProgress.state.trim().toLowerCase() : 'active'
  const rawSubphase = typeof rawProgress?.subphase === 'string'
    ? rawProgress.subphase.trim().toLowerCase()
    : ''
  const validSubphase = !rawSubphase || (
    phase === 'ranking'
    && ['inventory', 'activity_evidence', 'feedback_analysis'].includes(rawSubphase)
  )
  const rawArtifactCounts = record(rawProgress?.artifact_counts)
  const artifactCounts = Object.fromEntries([
    'decision_evidence',
    'stakeholder_workbook',
    'score_briefs',
    'scorecard_summaries',
    'scorecard_spreadsheets',
    'scorecard_presentations',
    'stakeholder_presentation',
    'revision_manifest',
  ].flatMap(kind => {
    const counts = record(rawArtifactCounts?.[kind])
    const completed = Number(counts?.completed)
    const countTotal = Number(counts?.total)
    return Number.isSafeInteger(completed)
      && Number.isSafeInteger(countTotal)
      && completed >= 0
      && countTotal >= 0
      && completed <= countTotal
      ? [[kind, { completed, total: countTotal }]]
      : []
  }))
  const validState = ['active', 'retrying', 'incomplete', 'failed'].includes(rawState)
  const isValidProgress = phase.length > 0
    && Number.isFinite(current)
    && current >= 0
    && (total === null || (Number.isFinite(total) && total > 0))
    && validState
    && validSubphase

  return {
    presentation: parseArtifactDescriptor(summary?.presentation),
    durableMilestone,
    liveProgress: isValidProgress
      ? {
          phase,
          subphase: rawSubphase as LiveProgress['subphase'],
          current: total === null ? current : Math.min(current, total),
          total,
          message: typeof rawProgress?.message === 'string' ? rawProgress.message : undefined,
          updatedAt: typeof rawProgress?.updated_at === 'string' ? rawProgress.updated_at : undefined,
          unit: typeof rawProgress?.unit === 'string' ? rawProgress.unit : undefined,
          state: rawState as LiveProgress['state'],
          elapsedSeconds: Number.isFinite(Number(rawProgress?.elapsed_seconds))
            ? Number(rawProgress?.elapsed_seconds)
            : undefined,
          nextCheckpoint: typeof rawProgress?.next_checkpoint === 'string'
            ? rawProgress.next_checkpoint
            : undefined,
          heartbeatIntervalSeconds: Number.isFinite(Number(rawProgress?.heartbeat_interval_seconds))
            ? Number(rawProgress?.heartbeat_interval_seconds)
            : undefined,
          artifactCounts: Object.keys(artifactCounts).length > 0 ? artifactCounts : undefined,
        }
      : null,
  }
}

function presentationKey(descriptor: ArtifactDescriptor | null): string | null {
  if (!descriptor) return null
  return [descriptor.task_id, descriptor.object_key, descriptor.sha256, descriptor.source_revision].join(':')
}

function progressLabel(progress: LiveProgress): string {
  const unit = progress.unit || (progress.phase === 'assessment' ? 'scores assessed' :
    progress.phase === 'diagnosis' ? 'analysis steps complete' : 'scorecards')
  if (progress.total === null) {
    return progress.phase === 'ranking'
      ? `${progress.current} ${unit} inspected`
      : `${progress.current} ${unit} complete`
  }
  return `${progress.current} of ${progress.total} ${unit}`
}

function assessmentProgressCounts(value: string | undefined): { current: number, total: number } | null {
  if (!value) return null
  const match = value.match(/^\s*(\d+)\s+of\s+(\d+)\s+(?:eligible candidates|ranked scores)\s+assessed\b/i)
  if (!match) return null
  const current = Number(match[1])
  const total = Number(match[2])
  if (!Number.isSafeInteger(current) || !Number.isSafeInteger(total) || current < 0 || total <= 0) {
    return null
  }
  return { current, total }
}

/**
 * Live progress is an overlay, not durable evidence. Show it only when it
 * advances the same assessment cohort beyond the immutable milestone. This
 * prevents a delayed subscription update from making the current status move
 * backwards while retaining the milestone artifact unchanged.
 */
function reconcileLiveProgress(
  liveProgress: LiveProgress | null | undefined,
  overview: PresentationOverview,
  durableMilestone: string | null | undefined,
): LiveProgress | null | undefined {
  if (
    liveProgress?.phase === 'ranking'
    && durableMilestone
    && durableMilestone !== 'started'
  ) {
    return null
  }
  if (liveProgress?.phase !== 'assessment') return liveProgress
  const durable = assessmentProgressCounts(overview.assessment_progress)
  if (!durable) return liveProgress
  if (liveProgress.total !== durable.total || liveProgress.current <= durable.current) return null
  return liveProgress
}

function LiveProgressCard({ progress }: { progress: LiveProgress }) {
  const phaseLabel = progress.subphase
    ? `${label(progress.phase)} / ${label(progress.subphase)}`
    : label(progress.phase)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 15_000)
    return () => window.clearInterval(timer)
  }, [])
  const heartbeatMs = Math.max(1, progress.heartbeatIntervalSeconds || 90) * 1000
  const updatedAt = progress.updatedAt ? Date.parse(progress.updatedAt) : Number.NaN
  const delayed = progress.state === 'active'
    && Number.isFinite(updatedAt)
    && now - updatedAt > heartbeatMs
  const status = delayed ? 'delayed' : (progress.state || 'active')
  const percentage = progress.total === null
    ? null
    : Math.round(progress.current / progress.total * 100)
  const statusLabel = label(status)
  const elapsed = typeof progress.elapsedSeconds === 'number'
    ? `${Math.floor(progress.elapsedSeconds / 60)}m ${progress.elapsedSeconds % 60}s`
    : null

  return (
    <div className="rounded-md bg-primary/5 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">{phaseLabel} {status === 'active' ? 'in progress' : 'status'}</div>
        <div className="text-sm font-medium">{progressLabel(progress)}</div>
      </div>
      {status !== 'active' && <div className="mt-2 text-sm font-medium">{statusLabel}</div>}
      {percentage !== null && <div
        className="mt-3 h-2 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={`${phaseLabel} progress`}
        aria-valuemin={0}
        aria-valuemax={progress.total ?? 0}
        aria-valuenow={progress.current}
        aria-valuetext={progressLabel(progress)}
      >
        <div className="h-full bg-primary transition-[width]" style={{ width: `${percentage}%` }} />
      </div>}
      {progress.message && <p className="mt-3 text-sm text-muted-foreground">{progress.message}</p>}
      {progress.artifactCounts && Object.keys(progress.artifactCounts).length > 0 && (
        <dl className="mt-3 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
          {Object.entries(progress.artifactCounts).map(([kind, counts]) => (
            <div key={kind} className="flex items-center justify-between gap-2">
              <dt className="text-muted-foreground">{label(kind)}</dt>
              <dd className="font-medium tabular-nums">{counts.completed} / {counts.total}</dd>
            </div>
          ))}
        </dl>
      )}
      {elapsed && <p className="mt-2 text-sm text-muted-foreground">Elapsed: {elapsed}</p>}
      {progress.nextCheckpoint && <p className="mt-2 text-sm text-muted-foreground">Next: {progress.nextCheckpoint}</p>}
    </div>
  )
}

function finiteNonNegative(value: number | undefined): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : 0
}

function countLabel(value: number, singular: string): string {
  return `${value} ${singular}${value === 1 ? '' : 's'}`
}

function FeedbackCompositionSignal({
  scoreName,
  feedbackTotal,
  disagreements,
  maximum,
}: {
  scoreName: string
  feedbackTotal: number
  disagreements: number
  maximum: number
}) {
  const safeTotal = finiteNonNegative(feedbackTotal)
  const safeDisagreements = Math.min(safeTotal, finiteNonNegative(disagreements))
  const agreements = Math.max(0, safeTotal - safeDisagreements)
  const safeMaximum = Math.max(finiteNonNegative(maximum), safeTotal, 1)
  const totalPercentage = Math.min(100, safeTotal / safeMaximum * 100)
  const disagreementPercentage = safeTotal ? safeDisagreements / safeTotal * 100 : 0
  const agreementPercentage = safeTotal ? 100 - disagreementPercentage : 0
  const valueText = safeTotal
    ? `${countLabel(agreements, 'agreement')}, ${countLabel(safeDisagreements, 'disagreement')}, ${safeTotal} valid feedback, ${disagreementPercentage.toFixed(1)}% disagreement`
    : 'Unavailable'

  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs">
        <span className="font-medium text-foreground">Feedback outcomes</span>
        {safeTotal > 0 ? (
          <span className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 tabular-nums">
            <span className="inline-flex items-center gap-1.5">
              <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm bg-emerald-500" />
              {countLabel(agreements, 'agreement')}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm bg-rose-500" />
              {countLabel(safeDisagreements, 'disagreement')}
            </span>
            <span className="text-muted-foreground">{safeTotal} valid feedback</span>
            <span className="text-muted-foreground">{disagreementPercentage.toFixed(1)}% disagreement</span>
          </span>
        ) : (
          <span className="text-muted-foreground">Unavailable</span>
        )}
      </div>
      <div className="mt-2 h-3 overflow-hidden rounded-full bg-muted">
        <div
          role="meter"
          aria-label={`Feedback outcomes for ${scoreName}`}
          aria-valuemin={0}
          aria-valuemax={safeMaximum}
          aria-valuenow={safeTotal}
          aria-valuetext={valueText}
          className="flex h-full min-w-0 overflow-hidden rounded-full"
          style={{ width: `${totalPercentage}%` }}
        >
          <div
            aria-label={`Agreements for ${scoreName}`}
            className="h-full bg-emerald-500"
            style={{ width: `${agreementPercentage}%` }}
          />
          <div
            aria-label={`Disagreements for ${scoreName}`}
            className="h-full bg-rose-500"
            style={{ width: `${disagreementPercentage}%` }}
          />
        </div>
      </div>
    </div>
  )
}

function parsePresentation(value: unknown): StakeholderPresentation {
  const parsed = typeof value === 'string' ? JSON.parse(value) : value
  const data = record(parsed)
  const primaryDispositionCounts = countMap(
    data?.primary_disposition_counts,
    'primary_disposition_counts',
    PRIMARY_DISPOSITION_KEYS,
  )
  const primaryDecisionMix = countMap(data?.primary_decision_mix, 'primary_decision_mix')
  const secondaryIssueCounts = countMap(data?.secondary_issue_counts, 'secondary_issue_counts')
  if (
    !data ||
    !record(data.overview) ||
    finiteNonNegativeNumber(data.score_count) === null ||
    finiteNonNegativeNumber(data.scorecard_count) === null ||
    (!primaryDispositionCounts && !primaryDecisionMix) ||
    !secondaryIssueCounts ||
    !Array.isArray(data.top_priorities) ||
    !Array.isArray(data.scorecards)
  ) {
    throw new Error('Stakeholder presentation artifact is malformed.')
  }

  const scorecards = data.scorecards.map((value: unknown) => {
    const item = record(value)
    if (!item || typeof item.scorecard_name !== 'string' || !Array.isArray(item.artifacts)) {
      throw new Error('Stakeholder presentation contains a malformed scorecard.')
    }
    const artifacts = item.artifacts.map(parseArtifactDescriptor)
    if (artifacts.some((artifact: ArtifactDescriptor | null) => artifact === null)) {
      throw new Error('Stakeholder presentation contains a malformed artifact link.')
    }
    const scorecardDispositionCounts = countMap(
      item.primary_disposition_counts,
      'scorecard primary_disposition_counts',
      PRIMARY_DISPOSITION_KEYS,
    )
    const scorecardDecisionMix = countMap(item.primary_decision_mix, 'scorecard primary_decision_mix')
    if (finiteNonNegativeNumber(item.score_count) === null || finiteNonNegativeNumber(item.reviewed_error_opportunity) === null) {
      throw new Error('Stakeholder presentation contains an invalid scorecard count.')
    }
    return {
      scorecard_ref: String(item.scorecard_ref || item.scorecard_name),
      scorecard_name: item.scorecard_name,
      score_count: item.score_count,
      primary_disposition_counts: scorecardDispositionCounts || undefined,
      primary_decision_mix: scorecardDecisionMix || {},
      reviewed_error_opportunity: item.reviewed_error_opportunity,
      artifacts: artifacts as ArtifactDescriptor[],
    }
  })
  const opportunityDistribution = (Array.isArray(data.opportunity_distribution)
    ? data.opportunity_distribution
    : []).map((value: unknown) => {
      const row = record(value)
      if (!row) throw new Error('Stakeholder presentation contains a malformed opportunity row.')
      const evidenceRank = Number(row.evidence_rank)
      const opportunity = Number(row.opportunity)
      if (!Number.isFinite(evidenceRank) || !Number.isFinite(opportunity)) {
        throw new Error('Stakeholder presentation contains an invalid opportunity rank or value.')
      }
      return {
        evidence_rank: evidenceRank,
        opportunity,
        disposition: opportunityDisposition(row.review_disposition || row.policy_disposition),
        scorecard_name: String(row.scorecard_name || 'Unlabeled scorecard'),
        score_name: String(row.score_name || 'Unlabeled score'),
        disagreement_rate: typeof row.disagreement_rate === 'number'
          ? row.disagreement_rate
          : null,
        valid_feedback_count: typeof row.valid_feedback_count === 'number'
          ? row.valid_feedback_count
          : null,
        reason: row.policy_reason && row.policy_reason !== 'meets_rank_policy'
          ? label(String(row.policy_reason))
          : null,
        eligibility_timestamp: row.eligibility_timestamp
          ? String(row.eligibility_timestamp)
          : null,
        dashboard_url: row.dashboard_url ? String(row.dashboard_url) : null,
      }
    })

  const parseRows = <T,>(value: unknown, field: string, parseRow: (row: unknown) => T): T[] => {
    if (value === undefined) return []
    if (!Array.isArray(value)) throw new Error(`Stakeholder presentation contains a malformed ${field} list.`)
    return value.map(parseRow)
  }

  return {
    overview: data.overview as PresentationOverview,
    score_count: data.score_count,
    scorecard_count: data.scorecard_count,
    primary_disposition_counts: primaryDispositionCounts || undefined,
    primary_decision_mix: primaryDecisionMix || {},
    secondary_issue_counts: secondaryIssueCounts,
    attention_queue: parseRows(data.attention_queue, 'attention queue', parseAttentionRow),
    questions_and_issues: parseRows(data.questions_and_issues, 'issue', parseQuestionRow),
    optimization_outcomes: parseRows(data.optimization_outcomes, 'outcome', parseOutcomeRow),
    opportunity_distribution: opportunityDistribution,
    top_priorities: parseRows(data.top_priorities, 'priority', parsePriorityRow),
    scorecards,
  }
}

async function loadJsonArtifact(descriptor: ArtifactDescriptor): Promise<unknown> {
  const bytes = await readTaskArtifact(descriptor, {
    issueTicket: issueTaskArtifactReadTicket,
  })
  return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes))
}

function ArtifactLink({
  descriptor,
  reportId,
  children,
}: {
  descriptor: ArtifactDescriptor
  reportId: string | null
  children: React.ReactNode
}) {
  if (!reportId) return null
  return (
    <Link
      href={buildReportArtifactHref({
        reportId,
        revision: descriptor.source_revision,
        logicalId: descriptor.logical_id,
      })}
      className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
    >
      <FileDown className="h-3.5 w-3.5" />
      {children}
    </Link>
  )
}

function DispositionBadge({ disposition }: { disposition?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-medium">
      <span aria-hidden="true" className={`h-2 w-2 rounded-full ${primaryDispositionColor(disposition)}`} />
      {primaryDispositionLabel(disposition)}
    </span>
  )
}

function OptimizationLifecycle({ counts }: { counts: Record<string, number> }) {
  const lifecycleTotal = LIFECYCLE_GROUPS.reduce(
    (total, group) => total + lifecycleCount(counts, group.dispositions),
    0,
  )
  const dispositionTotal = Object.values(counts).reduce((total, count) => total + numericCount(count), 0)
  return (
    <section className="rounded-lg bg-card p-6">
      <h3 className="text-lg font-semibold">Optimization lifecycle</h3>
      <p className="text-sm text-muted-foreground">
        At-a-glance status for optimization work after portfolio selection. Every score has one primary disposition.
      </p>
      <p data-testid="lifecycle-total" className="mt-2 text-xs text-muted-foreground">
        Lifecycle total: {lifecycleTotal} of {dispositionTotal} scores
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {LIFECYCLE_GROUPS.map(group => {
          const Icon = group.icon
          const count = lifecycleCount(counts, group.dispositions)
          return (
            <div
              key={group.key}
              data-testid={`lifecycle-${group.key}`}
              className={`rounded-md p-3 ${group.tone}`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="text-2xl font-semibold tabular-nums">{count}</div>
                <Icon aria-hidden="true" className="h-4 w-4" />
              </div>
              <div className="mt-1 text-xs font-medium">{group.label}</div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function AttentionQueue({ rows }: { rows: AttentionRow[] }) {
  const [showAll, setShowAll] = useState(false)
  if (rows.length === 0) return null
  const ranked = [...rows].sort((left, right) => {
    const severity = severityRank(left.severity) - severityRank(right.severity)
    if (severity !== 0) return severity
    return numericCount(right.evidence_count) - numericCount(left.evidence_count)
  })
  return (
    <section className="rounded-lg bg-card p-6">
      <h3 className="text-lg font-semibold">Human attention queue</h3>
      <p className="text-sm text-muted-foreground">
        The most important open decisions and issues, ordered by severity and supporting feedback volume.
      </p>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {(showAll ? ranked : ranked.slice(0, 5)).map((row, index) => (
          <article key={`${row.scorecard_name}-${row.score_name}-${index}`} className="rounded-md bg-muted/30 p-4 text-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div><span className="font-medium">{row.score_name || 'Unlabeled score'}</span><span className="text-muted-foreground"> · {row.scorecard_name || 'Unlabeled scorecard'}</span></div>
                <div className="mt-2"><DispositionBadge disposition={row.primary_disposition} /></div>
              </div>
              <div className="text-xs text-muted-foreground">{numericCount(row.evidence_count)} feedback items</div>
            </div>
            <p className="mt-3">{row.rationale || 'Human review is required.'}</p>
            {Array.isArray(row.secondary_issue_flags) && row.secondary_issue_flags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {row.secondary_issue_flags.map(flag => (
                  <span key={flag} className="rounded-full bg-amber-500/10 px-2.5 py-1 text-xs">{label(flag)}</span>
                ))}
              </div>
            )}
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <span className="text-muted-foreground">{label(row.next_action || 'review')}</span>
              {row.dashboard_url && <Link href={row.dashboard_url} className="text-primary hover:underline">Open score</Link>}
            </div>
          </article>
        ))}
      </div>
      {ranked.length > 5 && (
        <button
          type="button"
          className="mt-4 text-sm text-primary hover:underline"
          onClick={() => setShowAll(value => !value)}
        >
          {showAll ? 'Collapse attention queue entries' : `Show all attention queue entries (${ranked.length})`}
        </button>
      )}
    </section>
  )
}

function IssuesSummary({ issues }: { issues: ScoreQuestion[] }) {
  const [showAll, setShowAll] = useState(false)
  if (issues.length === 0) return null
  const ranked = [...issues].sort((left, right) => {
    const severity = severityRank(left.issue_severity) - severityRank(right.issue_severity)
    if (severity !== 0) return severity
    return numericCount(right.affected_evidence_count ?? right.evidence_count)
      - numericCount(left.affected_evidence_count ?? left.evidence_count)
  })
  return (
    <section className="rounded-lg bg-card p-6">
      <h3 className="text-lg font-semibold">Contradictions and stakeholder questions</h3>
      <p className="text-sm text-muted-foreground">
        Highest-priority policy and evidence issues, ranked by severity and affected feedback volume.
      </p>
      <ol className="mt-4 space-y-2">
        {(showAll ? ranked : ranked.slice(0, 5)).map((issue, index) => (
          <li key={`${issue.scorecard_name}-${issue.score_name}-${issue.issue_flag}-${index}`} className="rounded-md bg-amber-500/10 p-4 text-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-amber-500/15 px-2 py-1 text-xs font-medium">#{index + 1}</span>
                  <span className="font-medium">{issue.score_name || 'Unlabeled score'}</span>
                  <span className="text-muted-foreground">· {issue.scorecard_name || 'Unlabeled scorecard'}</span>
                </div>
                <div className="mt-2 text-xs font-medium text-amber-800 dark:text-amber-200">
                  {label(issue.issue_flag || issue.kind || 'issue')}
                </div>
              </div>
              <div className="text-xs text-muted-foreground">
                {affectedEvidenceLabel(issue.affected_evidence_count ?? issue.evidence_count)}
              </div>
            </div>
            <p className="mt-2">{issue.finding || issue.rationale || 'Review required.'}</p>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <span className="text-muted-foreground">{label(issue.next_action || 'review')}</span>
              {issue.dashboard_url && (
                <Link href={issue.dashboard_url} className="text-primary hover:underline">Open score</Link>
              )}
            </div>
          </li>
        ))}
      </ol>
      {ranked.length > 5 && (
        <button
          type="button"
          className="mt-4 text-sm text-primary hover:underline"
          onClick={() => setShowAll(value => !value)}
        >
          {showAll ? 'Collapse issues' : `Show all issues (${ranked.length})`}
        </button>
      )}
    </section>
  )
}

function OptimizationOutcomes({ outcomes }: { outcomes: OptimizationOutcome[] }) {
  const [showAll, setShowAll] = useState(false)
  if (outcomes.length === 0) return null
  return (
    <section className="rounded-lg bg-card p-6">
      <h3 className="text-lg font-semibold">Optimization progress and outcomes</h3>
      <p className="text-sm text-muted-foreground">
        Approved optimizer work, evidence review, and terminal decisions. Promotion always requires a separate human approval.
      </p>
      <div className="mt-4 space-y-2">
        {(showAll ? outcomes : outcomes.slice(0, 5)).map((outcome, index) => (
          <article key={`${outcome.scorecard_name}-${outcome.score_name}-${index}`} className="rounded-md bg-muted/30 p-4 text-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div><span className="font-medium">{outcome.score_name || 'Unlabeled score'}</span><span className="text-muted-foreground"> · {outcome.scorecard_name || 'Unlabeled scorecard'}</span></div>
                <div className="mt-2"><DispositionBadge disposition={outcome.primary_disposition} /></div>
              </div>
              <div className="text-right text-xs text-muted-foreground">
                <div>{numericCount(outcome.evidence_count)} feedback items</div>
                <div className="mt-1">{label(outcome.outcome || 'not_run')}</div>
              </div>
            </div>
            <p className="mt-3">{outcome.rationale || 'No outcome rationale is available yet.'}</p>
            {outcome.trend && <p className="mt-2 text-xs text-muted-foreground">{outcome.trend}</p>}
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <span className="text-muted-foreground">{label(outcome.next_action || 'review')}</span>
              {outcome.dashboard_url && (
                <Link href={outcome.dashboard_url} className="text-primary hover:underline">Open score</Link>
              )}
            </div>
          </article>
        ))}
      </div>
      {outcomes.length > 5 && (
        <button
          type="button"
          className="mt-4 text-sm text-primary hover:underline"
          onClick={() => setShowAll(value => !value)}
        >
          {showAll ? 'Collapse outcomes' : `Show all outcomes (${outcomes.length})`}
        </button>
      )}
    </section>
  )
}

function RankAndPolicyDetails({
  evidenceRank,
  candidateRank,
  policyDisposition,
  policyReason,
  reviewDisposition,
  eligibilityTimestamp,
}: {
  evidenceRank?: number
  candidateRank?: number | null
  policyDisposition?: string
  policyReason?: string
  reviewDisposition?: string
  eligibilityTimestamp?: string | null
}) {
  const policy = [policyDisposition && label(policyDisposition), policyReason && label(policyReason)]
    .filter((value): value is string => Boolean(value))
    .join(' · ')
  return (
    <div className="space-y-1 text-xs text-muted-foreground">
      {finiteNonNegativeNumber(evidenceRank) !== null && <div>Evidence rank #{evidenceRank}</div>}
      {finiteNonNegativeNumber(candidateRank) !== null && <div>Eligible candidate #{candidateRank}</div>}
      {policy && <div>Policy: {policy}</div>}
      {reviewDisposition && <div>Review: {label(reviewDisposition)}</div>}
      {eligibilityTimestamp && <div>Eligible after: {eligibilityTimestamp}</div>}
    </div>
  )
}

async function loadScorecardPresentationArtifact(
  scorecard: ScorecardCard,
): Promise<ScorecardPresentation | null> {
  const detailArtifact = scorecard.artifacts.find(artifact => artifact.kind === 'scorecard_presentation')
  if (!detailArtifact) return null

  const value = record(await loadJsonArtifact(detailArtifact))
  if (!value || !Array.isArray(value.scores) || !Array.isArray(value.questions_and_issues)) {
    throw new Error('Scorecard details artifact is malformed.')
  }
  return {
    scorecard_name: String(value.scorecard_name || scorecard.scorecard_name),
    scores: value.scores.map((rawScore: unknown) => {
      const score = parseScoreDetailRow(rawScore)
      const artifacts = Array.isArray(score.artifacts)
        ? score.artifacts.map(parseArtifactDescriptor)
        : []
      if (artifacts.some((artifact: ArtifactDescriptor | null) => artifact === null)) {
        throw new Error('Scorecard details contain a malformed score artifact.')
      }
      return { ...score, artifacts: artifacts as ArtifactDescriptor[] }
    }),
    questions_and_issues: value.questions_and_issues.map(
      (rawIssue: unknown) => parseQuestionRow(rawIssue, 'Scorecard details'),
    ),
  }
}

function ScorecardSection({
  scorecard,
  reportId,
  loadDetails,
}: {
  scorecard: ScorecardCard
  reportId: string | null
  loadDetails?: (scorecard: ScorecardCard) => Promise<ScorecardPresentation | null>
}) {
  const [expanded, setExpanded] = useState(false)
  const [details, setDetails] = useState<ScorecardPresentation | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const summaryArtifact = scorecard.artifacts.find(artifact => artifact.kind === 'scorecard_summary')
  const csvArtifact = scorecard.artifacts.find(artifact => artifact.kind === 'scorecard_portfolio_csv')

  const toggle = async () => {
    const opening = !expanded
    setExpanded(opening)
    if (!opening || details || loading || !loadDetails) return
    setLoading(true)
    setError(null)
    try {
      setDetails(await loadDetails(scorecard))
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="rounded-lg bg-muted/30">
      <button
        type="button"
        onClick={() => void toggle()}
        className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left"
        aria-expanded={expanded}
      >
        <span className="flex min-w-0 items-center gap-2">
          {expanded ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" />}
          <span className="truncate font-medium">{scorecard.scorecard_name}</span>
        </span>
        <span className="shrink-0 text-sm text-muted-foreground">
          {scorecard.score_count} scores · {scorecard.reviewed_error_opportunity} reviewed disagreements
        </span>
      </button>

      {expanded && (
        <div className="space-y-4 px-4 pb-4">
          <div className="flex flex-wrap gap-4">
            {summaryArtifact && <ArtifactLink descriptor={summaryArtifact} reportId={reportId}>Summary artifact</ArtifactLink>}
            {csvArtifact && <ArtifactLink descriptor={csvArtifact} reportId={reportId}>Quantitative CSV</ArtifactLink>}
          </div>
          {loading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading score details…
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          {details?.scores.map((score, index) => {
            const scoreQuestions = details.questions_and_issues.filter(
              issue => issue.score_name === score.score_name,
            )
            const scoreBrief = score.artifacts?.find(artifact => artifact.kind === 'score_brief')
            const secondaryFlags = Array.isArray(score.secondary_issue_flags)
              ? score.secondary_issue_flags
              : []
            return (
              <details key={`${score.score_name || 'score'}-${index}`} className="rounded-md bg-card p-3">
                <summary className="cursor-pointer">
                  <span className="font-medium">{score.score_name || 'Unlabeled score'}</span>
                  <span className="ml-2 inline-flex align-middle">
                    <DispositionBadge disposition={score.primary_disposition || score.readiness} />
                  </span>
                </summary>
                <div className="mt-3 space-y-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-muted-foreground">Primary disposition</span>
                    <DispositionBadge disposition={score.primary_disposition || score.readiness} />
                  </div>
                  {score.execution_status && (
                    <div className="rounded-md bg-emerald-500/10 p-3">
                      <div className="font-medium">{executionStatusLabel(score.execution_status)}</div>
                      {score.execution_reason && <p className="mt-1 text-muted-foreground">{score.execution_reason}</p>}
                      {score.execution_authorization_source && (
                        <p className="mt-1 text-xs text-muted-foreground">Authorized by: {label(score.execution_authorization_source)}</p>
                      )}
                    </div>
                  )}
                  <RankAndPolicyDetails
                    evidenceRank={score.evidence_rank}
                    candidateRank={score.candidate_rank}
                    policyDisposition={score.policy_disposition}
                    policyReason={score.policy_reason}
                    reviewDisposition={score.review_disposition}
                    eligibilityTimestamp={score.eligibility_timestamp}
                  />
                  {secondaryFlags.length > 0 && (
                    <div>
                      <div className="text-xs font-medium text-muted-foreground">Secondary issues</div>
                      <div className="mt-1 flex flex-wrap gap-2">
                        {secondaryFlags.map(flag => (
                          <span key={flag} className="rounded-full bg-amber-500/10 px-2.5 py-1 text-xs">
                            {label(flag)}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <p>{score.rationale || 'No rationale available.'}</p>
                  <FeedbackCompositionSignal
                    scoreName={score.score_name || 'Unlabeled score'}
                    feedbackTotal={score.valid_feedback_count ?? 0}
                    disagreements={score.reviewed_disagreements ?? 0}
                    maximum={score.valid_feedback_count ?? 0}
                  />
                  {score.trend && (
                    <p><span className="text-muted-foreground">Recent trend:</span> {score.trend}</p>
                  )}
                  {score.outcome && (
                    <p><span className="text-muted-foreground">Optimizer outcome:</span> {label(score.outcome)}</p>
                  )}
                  {score.promotion_readiness && (
                    <p><span className="text-muted-foreground">Promotion readiness:</span> {label(score.promotion_readiness)}</p>
                  )}
                  <p><span className="text-muted-foreground">Next action:</span> {label(score.next_action || 'review')}</p>
                  {score.dashboard_url && (
                    <Link href={score.dashboard_url} className="inline-flex text-primary hover:underline">
                      Open score in dashboard
                    </Link>
                  )}
                  {scoreQuestions.length > 0 && (
                    <div className="rounded-md bg-amber-500/10 p-3">
                      <div className="font-medium">Questions and issues</div>
                      <ul className="mt-2 list-disc space-y-2 pl-5">
                        {scoreQuestions.map((issue, issueIndex) => (
                          <li key={`${issue.kind || 'issue'}-${issueIndex}`}>
                            {issue.finding || issue.rationale || 'Review required.'}
                            {issue.next_action && (
                              <span className="text-muted-foreground"> Next: {label(issue.next_action)}.</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {scoreBrief && (
                    <ArtifactLink descriptor={scoreBrief} reportId={reportId}>Open score brief</ArtifactLink>
                  )}
                </div>
              </details>
            )
          })}
          {details && details.questions_and_issues.length > 0 && (
            <div className="rounded-md bg-amber-500/10 p-3 text-sm">
              {details.questions_and_issues.length} stakeholder question or structural issue{details.questions_and_issues.length === 1 ? '' : 's'}.
            </div>
          )}
        </div>
      )}
    </section>
  )
}

const OptimizationRunStatus: BlockComponent = ({ output, name }: ReportBlockProps) => {
  const compactStatus = useMemo(() => parseCompactStatus(output), [output])
  const descriptor = compactStatus.presentation
  // A progress-only ReportBlock update has the same immutable presentation.
  // Keep this object stable so it updates the visible progress immediately
  // without downloading that artifact again.
  const descriptorKey = presentationKey(descriptor)
  const stableDescriptor = useMemo(() => descriptor, [descriptorKey])
  const [presentation, setPresentation] = useState<StakeholderPresentation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const reportId = reportIdFromLocation()

  useEffect(() => {
    let cancelled = false
    if (!stableDescriptor) {
      setError('The latest optimization presentation is not available yet.')
      return
    }
    setError(null)
    setPresentation(null)
    void loadJsonArtifact(stableDescriptor)
      .then(value => {
        if (!cancelled) setPresentation(parsePresentation(value))
      })
      .catch(loadError => {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : String(loadError))
      })
    return () => {
      cancelled = true
    }
  }, [stableDescriptor])

  if (error) {
    return (
      <section className="rounded-lg bg-destructive/10 p-5 text-destructive">
        <div className="flex gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5" />
          <div><h2 className="font-semibold">{name || 'Optimization run status'}</h2><p className="text-sm">{error}</p></div>
        </div>
      </section>
    )
  }

  if (!presentation) {
    return (
      <section className="flex min-h-40 items-center justify-center rounded-lg bg-card text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading optimization overview…
      </section>
    )
  }

  return (
    <OptimizationRunStatusPresentation
      presentation={presentation}
      liveProgress={compactStatus.liveProgress}
      durableMilestone={compactStatus.durableMilestone}
      reportId={reportId}
      loadScorecardDetails={loadScorecardPresentationArtifact}
    />
  )
}

export function OptimizationRunStatusPresentation({
  presentation,
  liveProgress,
  durableMilestone = null,
  reportId = null,
  scorecardDetails,
  loadScorecardDetails,
}: {
  presentation: StakeholderPresentation
  liveProgress?: LiveProgress | null
  durableMilestone?: string | null
  reportId?: string | null
  scorecardDetails?: ScorecardDetailsByReference
  loadScorecardDetails?: (scorecard: ScorecardCard) => Promise<ScorecardPresentation | null>
}) {
  const overview = presentation.overview
  const usesCanonicalDispositions = presentation.primary_disposition_counts !== undefined
  const dispositionCounts = presentation.primary_disposition_counts || presentation.primary_decision_mix
  const decisions = Object.entries(dispositionCounts)
    .filter(([, count]) => count > 0)
    .sort((left, right) => right[1] - left[1])
  const decisionTotal = decisions.reduce((total, [, count]) => total + count, 0)
  const lifecycleStatus = overview.lifecycle_status || 'running'
  const inventoryCoverageStatus = overview.inventory_coverage_status || overview.coverage_status || 'pending'
  const analysisCoverageStatus = overview.analysis_coverage_status || (
    ['incomplete', 'failed'].includes(lifecycleStatus.toLowerCase())
      ? 'incomplete'
      : overview.coverage_status || 'pending'
  )
  const incompleteDiagnosisCount = Math.max(0, Number(overview.diagnosis_incomplete_count || 0))
  const deferredDiagnosisCount = Math.max(0, Number(overview.diagnosis_deferred_count || 0))
  const automaticExecution = overview.execution_mode === 'automatic'
  const countAtStart = (value?: string): number => {
    const match = String(value || '').match(/^\s*(\d+)\b/)
    return match ? Number(match[1]) : 0
  }
  const surveyedCount = finiteNonNegative(overview.evidence_ranked_score_count ?? presentation.score_count)
  const assessedCount = finiteNonNegative(
    overview.assessed_score_count ?? countAtStart(overview.assessment_progress),
  )
  const diagnosedCount = finiteNonNegative(
    overview.diagnosis_completed_count ?? countAtStart(overview.diagnosis_coverage),
  )
  const selectedCount = finiteNonNegative(overview.execution_selected_count)
  const launchedCount = finiteNonNegative(overview.execution_launched_count)
  const evaluatedCount = finiteNonNegative(overview.optimizer_review_count)
  const improvedCount = finiteNonNegative(dispositionCounts.promotion_ready)
  const executionFunnel = [
    ['Surveyed', surveyedCount],
    ['Assessed', assessedCount],
    ['Diagnosed', diagnosedCount],
    ['Selected', selectedCount],
    ['Launched', launchedCount],
    ['Evaluated', evaluatedCount],
    ['Improved', improvedCount],
  ] as const
  const runHasIncompleteCoverage = inventoryCoverageStatus === 'incomplete' || analysisCoverageStatus === 'incomplete'
  const reconciledLiveProgress = reconcileLiveProgress(liveProgress, overview, durableMilestone)
  const maximumPriorityFeedback = Math.max(
    0,
    ...presentation.top_priorities.map(priority => finiteNonNegative(priority.evidence_count)),
  )

  return (
    <div className="space-y-6">
      <section className="rounded-lg bg-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm text-muted-foreground">
              {label(lifecycleStatus)} · Inventory {label(inventoryCoverageStatus).toLowerCase()} · Analysis {label(analysisCoverageStatus).toLowerCase()}
            </p>
            <h2 className="mt-1 text-2xl font-semibold">Optimization opportunity survey</h2>
            {overview.current_activity && <p className="mt-2 max-w-3xl text-muted-foreground">{overview.current_activity}</p>}
          </div>
          <div className="rounded-md bg-primary/10 px-3 py-2 text-sm font-medium text-primary">
            {automaticExecution
              ? 'Automatic policy active'
              : overview.execution_mode === 'approval_required'
                ? `${overview.pending_approval_count ?? 0} pending actions · Approval required`
                : `${overview.pending_approval_count ?? 0} pending actions`}
          </div>
        </div>

        <div className="mt-5">
          <div className="text-sm font-medium">From opportunity survey to validated improvement</div>
          <div
            className="mt-2 grid gap-2"
            style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(5.5rem, 1fr))' }}
            aria-label="Optimization execution funnel"
          >
            {executionFunnel.map(([stage, count], index) => (
              <div
                key={stage}
                className={cn(
                  'rounded-md p-3',
                  index === executionFunnel.length - 1 && count > 0
                    ? 'bg-emerald-500/15'
                    : 'bg-muted/40',
                )}
              >
                <div className="text-2xl font-semibold tabular-nums">{count}</div>
                <div className="text-xs text-muted-foreground">{stage}</div>
              </div>
            ))}
          </div>
          <div className={cn(
            'mt-2 rounded-md px-3 py-2 text-sm',
            improvedCount > 0 ? 'bg-emerald-500/10' : 'bg-muted/30',
          )}>
            {improvedCount > 0 ? (
              <span className="font-medium">
                {improvedCount} validated safe {improvedCount === 1 ? 'improvement' : 'improvements'}
              </span>
            ) : launchedCount === 0 ? (
              <>
                <span className="font-medium">No score optimizer launched</span>
                <span className="text-muted-foreground"> · A completed survey does not mean that a score was optimized.</span>
              </>
            ) : (
              <>
                <span className="font-medium">No validated safe improvement yet</span>
                <span className="text-muted-foreground"> · {launchedCount} score {launchedCount === 1 ? 'optimizer is' : 'optimizers are'} still awaiting or did not pass evaluation and review.</span>
              </>
            )}
          </div>
        </div>

        {automaticExecution && (
          <div className={cn('mt-4 rounded-md p-4 text-sm', launchedCount > 0 ? 'bg-emerald-500/10' : 'bg-muted/30')}>
            <div className="font-medium">Automatic execution</div>
            <p className="mt-1 text-muted-foreground">
              {overview.execution_selected_count ?? 0} policy-selected · {overview.execution_launched_count ?? 0} launched · {overview.execution_rejected_count ?? 0} not selected
            </p>
            <p className="mt-2 text-muted-foreground">
              Safe, policy-selected targets may launch automatically. Champion promotion remains manual.
            </p>
            {overview.execution_detail_coverage === 'incomplete' && (
              <div className="mt-3 rounded-md bg-amber-500/10 p-3">
                <div className="font-medium text-amber-700 dark:text-amber-300">Automatic execution detail is incomplete</div>
                <p className="mt-1 text-muted-foreground">
                  {overview.execution_detail_limitation || 'Some automatic decisions cannot be shown by safe score name.'}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Visible named detail: {overview.execution_named_selected_count ?? 0} selected, {overview.execution_named_launched_count ?? 0} launched, {overview.execution_named_rejected_count ?? 0} not selected by policy.
                </p>
              </div>
            )}
          </div>
        )}

        {overview.execution_mode === 'approval_required' && (
          <div className="mt-4 rounded-md bg-primary/10 p-4 text-sm">
            <div className="font-medium">Human optimization approval</div>
            <p className="mt-1 text-muted-foreground">
              Optimization launch waits for the human optimization-approval checkpoint. Champion promotion remains manual.
            </p>
          </div>
        )}

        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {[
            ['Scorecards inspected', overview.scorecards_inspected ?? presentation.scorecard_count],
            ['Scorecards in scope', overview.scorecards_in_scope ?? presentation.scorecard_count],
            ['Scores in portfolio', presentation.score_count],
            ['Evidence-ranked scores', overview.evidence_ranked_score_count ?? presentation.score_count],
            ['Eligible candidates', overview.ranked_score_count ?? 0],
            ['Cooldown deferrals', overview.cooldown_excluded_count ?? 0],
          ].map(([metric, value]) => (
            <div key={String(metric)} className="rounded-md bg-muted/40 p-3">
              <div className="text-2xl font-semibold">{value}</div>
              <div className="text-sm text-muted-foreground">{metric}</div>
            </div>
          ))}
        </div>

        {reconciledLiveProgress?.phase === 'ranking' && (
          <div className="mt-6">
            <LiveProgressCard progress={reconciledLiveProgress} />
          </div>
        )}

        {reconciledLiveProgress?.phase === 'publication' && (
          <div className="mt-6">
            <LiveProgressCard progress={reconciledLiveProgress} />
          </div>
        )}

        <div className="mt-6 grid gap-3 md:grid-cols-2">
          {reconciledLiveProgress?.phase === 'assessment'
            ? <LiveProgressCard progress={reconciledLiveProgress} />
            : <div className="rounded-md bg-muted/30 p-4"><div className="text-xs uppercase tracking-wide text-muted-foreground">Assessment</div><div className="mt-1 text-sm">{overview.assessment_progress || 'Pending'}</div></div>}
          {reconciledLiveProgress?.phase === 'diagnosis'
            ? <LiveProgressCard progress={reconciledLiveProgress} />
            : <div className="rounded-md bg-muted/30 p-4"><div className="text-xs uppercase tracking-wide text-muted-foreground">Diagnosis</div><div className="mt-1 text-sm">{overview.diagnosis_coverage || 'Pending'}</div></div>}
        </div>
      </section>

      {usesCanonicalDispositions && <OptimizationLifecycle counts={dispositionCounts} />}

      <AttentionQueue rows={presentation.attention_queue} />

      {runHasIncompleteCoverage && (
        <section className="rounded-lg bg-amber-500/10 p-5">
          <h3 className="font-semibold">Why this run is incomplete</h3>
          <div className="mt-1 space-y-1 text-sm">
            <p>
              {inventoryCoverageStatus === 'incomplete'
                ? 'Portfolio inventory coverage is incomplete, so the ranking is partial.'
                : 'Portfolio inventory coverage is complete.'}
            </p>
            {analysisCoverageStatus === 'incomplete' && (
              <p>
                {incompleteDiagnosisCount > 0
                  ? `${incompleteDiagnosisCount} diagnosis ${incompleteDiagnosisCount === 1 ? 'result was' : 'results were'} incomplete.`
                  : 'Semantic analysis did not complete.'}
                {deferredDiagnosisCount > 0
                  ? ` ${deferredDiagnosisCount} selected ${deferredDiagnosisCount === 1 ? 'diagnosis was' : 'diagnoses were'} deferred by the safety cap.`
                  : ''}
              </p>
            )}
            {overview.notes && <p className="text-muted-foreground">{overview.notes}</p>}
          </div>
          {overview.next_checkpoint && <p className="mt-2 text-sm"><span className="font-medium">Next:</span> {overview.next_checkpoint}</p>}
        </section>
      )}

      <section className="rounded-lg bg-card p-6">
        <h3 className="text-lg font-semibold">How priorities were selected</h3>
        <p className="text-sm text-muted-foreground">The ranking and the deeper semantic review use related but different boundaries.</p>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <div className="rounded-md bg-muted/30 p-4">
            <div className="font-medium">Evidence rank before policy gates</div>
            <p className="mt-1 text-sm text-muted-foreground">
              All {overview.evidence_ranked_score_count ?? presentation.score_count} scores retain their original reviewed-disagreement rank. Policy gates change disposition, not rank.
            </p>
          </div>
          <div className="rounded-md bg-muted/30 p-4">
            <div className="font-medium">Top {overview.priority_display_limit ?? 10} evidence ranks are highlighted</div>
            <p className="mt-1 text-sm text-muted-foreground">
              {Number(overview.ranked_below_priority_cutoff || 0) > 0
                ? `The highlighted list ends at evidence rank ${overview.priority_cutoff_rank ?? overview.priority_displayed_count ?? 0}, at ${overview.priority_cutoff_opportunity ?? 0} reviewed disagreements. ${overview.ranked_below_priority_cutoff} evidence-ranked scores remain below this display cutoff.`
                : `All ${overview.priority_displayed_count ?? presentation.top_priorities.length} evidence-ranked scores fit in the highlighted list.`}
            </p>
          </div>
          <div className="rounded-md bg-muted/30 p-4">
            <div className="font-medium">{overview.diagnosis_selected_count ?? 0} selected for deeper review</div>
            <p className="mt-1 text-sm text-muted-foreground">
              The top {overview.diagnosis_top_priority_count ?? 0} eligible candidates plus {overview.diagnosis_monitoring_candidate_count ?? 0} monitoring candidates are selected, with overlap counted once. {overview.diagnosis_scheduled_count ?? overview.diagnosis_selected_count ?? 0} are scheduled in this run; {overview.diagnosis_deferred_count ?? 0} are deferred by the safety cap. {overview.diagnosis_skipped_count ?? 0} eligible candidates fall outside the diagnosis policy. Safety cap: {overview.diagnosis_max_count ?? 25}.
            </p>
          </div>
        </div>
      </section>

      <OptimizationOpportunityDistribution rows={presentation.opportunity_distribution} />

      <section className="rounded-lg bg-card p-6">
        <h3 className="text-lg font-semibold">{usesCanonicalDispositions ? 'Primary disposition mix' : 'Primary decision mix'}</h3>
        <p className="text-sm text-muted-foreground">Each score appears exactly once according to its primary disposition.</p>
        <div
          className="mt-4 flex h-8 overflow-hidden rounded-md bg-muted"
          aria-label={`${usesCanonicalDispositions ? 'Primary disposition' : 'Primary decision'} mix: ${decisionTotal} scores`}
        >
          {decisions.map(([key, count], index) => (
            <div
              key={key}
              className={`${usesCanonicalDispositions ? primaryDispositionColor(key, index) : DECISION_COLORS[index % DECISION_COLORS.length]} min-w-1`}
              style={{ width: `${decisionTotal ? count / decisionTotal * 100 : 0}%` }}
              title={`${usesCanonicalDispositions ? primaryDispositionLabel(key) : label(key)}: ${count}`}
            />
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm">
          {decisions.map(([key, count], index) => (
            <span key={key} className="inline-flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-sm ${usesCanonicalDispositions ? primaryDispositionColor(key, index) : DECISION_COLORS[index % DECISION_COLORS.length]}`} />
              {usesCanonicalDispositions ? primaryDispositionLabel(key) : label(key)}: {count}
            </span>
          ))}
        </div>
        {Object.keys(presentation.secondary_issue_counts).length > 0 && (
          <div className="mt-5">
            <div className="flex items-center gap-2 text-sm font-medium"><CircleHelp className="h-4 w-4" /> Overlapping questions and issues</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(presentation.secondary_issue_counts).map(([key, count]) => (
                <span key={key} className="rounded-full bg-muted px-3 py-1 text-xs">{label(key)}: {count}</span>
              ))}
            </div>
          </div>
        )}
      </section>

      <IssuesSummary issues={presentation.questions_and_issues} />

      <OptimizationOutcomes outcomes={presentation.optimization_outcomes} />

      <section className="rounded-lg bg-card p-6">
        <h3 className="text-lg font-semibold">Top priorities</h3>
        <p className="text-sm text-muted-foreground">Shown in original evidence order. Every feedback bar uses the largest visible feedback total as the same maximum: bar length shows reviewed volume, green shows agreements, and red shows disagreements. Cooldown and other policy gates remain visible and do not renumber the list.</p>
        <div className="mt-3 space-y-2">
          {presentation.top_priorities.map((priority, index) => {
            const scoreName = priority.score_name || 'Unlabeled score'
            const opportunity = finiteNonNegative(priority.opportunity)
            const feedbackVolume = finiteNonNegative(priority.evidence_count)
            return (
            <div key={`${priority.scorecard_name}-${priority.score_name}-${index}`} className="rounded-md bg-muted/30 p-4 text-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <span className="rounded bg-muted px-2 py-1 text-xs font-medium">#{priority.rank ?? index + 1}</span>
                  <div>
                    <div><span className="font-medium">{scoreName}</span><span className="text-muted-foreground"> · {priority.scorecard_name || 'Unlabeled scorecard'}</span></div>
                    <div className="mt-1 text-xs text-muted-foreground">{label(priority.readiness || 'inconclusive')}</div>
                    <div className="mt-2">
                      <RankAndPolicyDetails
                        evidenceRank={priority.evidence_rank}
                        candidateRank={priority.candidate_rank}
                        policyDisposition={priority.policy_disposition}
                        policyReason={priority.policy_reason}
                        reviewDisposition={priority.review_disposition}
                        eligibilityTimestamp={priority.eligibility_timestamp}
                      />
                    </div>
                  </div>
                </div>
                <div className="text-right text-muted-foreground">{label(priority.next_action || 'review')}</div>
              </div>
              <div className="mt-4">
                <FeedbackCompositionSignal
                  scoreName={scoreName}
                  feedbackTotal={feedbackVolume}
                  disagreements={opportunity}
                  maximum={maximumPriorityFeedback}
                />
              </div>
              {priority.rationale && <p className="mt-3 text-muted-foreground">{priority.rationale}</p>}
            </div>
          )})}
        </div>
      </section>

      <section className="rounded-lg bg-card p-6">
        <h3 className="text-lg font-semibold">Scorecards</h3>
        <p className="text-sm text-muted-foreground">Expand any number of scorecards to compare score-level evidence and actions.</p>
        <div className="mt-4 space-y-2">
          {presentation.scorecards.map(scorecard => (
            <ScorecardSection
              key={scorecard.scorecard_ref}
              scorecard={scorecard}
              reportId={reportId}
              loadDetails={async card => scorecardDetails?.[card.scorecard_ref]
                ?? await loadScorecardDetails?.(card)
                ?? null}
            />
          ))}
        </div>
      </section>
    </div>
  )
}

OptimizationRunStatus.blockClass = 'OptimizationRunStatus'

export default OptimizationRunStatus
