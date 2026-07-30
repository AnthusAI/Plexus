'use client'

import React, { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FileDown,
  Loader2,
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
import type { BlockComponent, ReportBlockProps } from './ReportBlock'

type PresentationOverview = {
  lifecycle_status?: string
  coverage_status?: string
  scorecards_inspected?: number
  scorecards_in_scope?: number
  evidence_ranked_score_count?: number
  ranked_score_count?: number
  unranked_score_count?: number
  cooldown_excluded_count?: number
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
  diagnosis_max_count?: number
  pending_approval_count?: number
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
  dashboard_url?: string | null
}

type ScorecardCard = {
  scorecard_ref: string
  scorecard_name: string
  score_count: number
  primary_decision_mix: Record<string, number>
  reviewed_error_opportunity: number
  artifacts: ArtifactDescriptor[]
}

type StakeholderPresentation = {
  overview: PresentationOverview
  score_count: number
  scorecard_count: number
  primary_decision_mix: Record<string, number>
  secondary_issue_counts: Record<string, number>
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
  rationale?: string
  next_action?: string
  policy_disposition?: string
  policy_reason?: string
  review_disposition?: string
  eligibility_timestamp?: string | null
  dashboard_url?: string | null
  artifacts?: ArtifactDescriptor[]
}

type ScoreQuestion = {
  kind?: string
  score_name?: string
  finding?: string
  rationale?: string
  next_action?: string
}

type ScorecardPresentation = {
  scorecard_name: string
  scores: ScoreDetail[]
  questions_and_issues: ScoreQuestion[]
}

type LiveProgress = {
  phase: string
  current: number
  total: number
  message?: string
  updatedAt?: string
}

type CompactStatus = {
  presentation: ArtifactDescriptor | null
  liveProgress: LiveProgress | null
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

function record(value: unknown): Record<string, any> | null {
  return value && typeof value === 'object' ? value as Record<string, any> : null
}

function label(value: string): string {
  const text = value.replaceAll('_', ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
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
      return { presentation: null, liveProgress: null }
    }
  }
  const envelope = record(parsed)
  const preview = record(envelope?.preview)
  const summary = record(preview?.summary)
  const rawProgress = record(summary?.live_progress)
  const current = Number(rawProgress?.current)
  const total = Number(rawProgress?.total)
  const phase = typeof rawProgress?.phase === 'string' ? rawProgress.phase.trim() : ''
  const isValidProgress = phase.length > 0
    && Number.isFinite(current)
    && current >= 0
    && Number.isFinite(total)
    && total > 0

  return {
    presentation: parseArtifactDescriptor(summary?.presentation),
    liveProgress: isValidProgress
      ? {
          phase,
          current: Math.min(current, total),
          total,
          message: typeof rawProgress?.message === 'string' ? rawProgress.message : undefined,
          updatedAt: typeof rawProgress?.updated_at === 'string' ? rawProgress.updated_at : undefined,
        }
      : null,
  }
}

function presentationKey(descriptor: ArtifactDescriptor | null): string | null {
  if (!descriptor) return null
  return [descriptor.task_id, descriptor.object_key, descriptor.sha256, descriptor.source_revision].join(':')
}

function progressLabel(progress: LiveProgress): string {
  const unit = progress.phase === 'assessment' ? 'scores assessed' :
    progress.phase === 'diagnosis' ? 'analysis steps complete' : 'scores processed'
  return `${progress.current} of ${progress.total} ${unit}`
}

function LiveProgressCard({ progress }: { progress: LiveProgress }) {
  const phaseLabel = label(progress.phase)
  const percentage = Math.round(progress.current / progress.total * 100)

  return (
    <div className="rounded-md bg-primary/5 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">{phaseLabel} in progress</div>
        <div className="text-sm font-medium">{progressLabel(progress)}</div>
      </div>
      <div
        className="mt-3 h-2 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={`${phaseLabel} progress`}
        aria-valuemin={0}
        aria-valuemax={progress.total}
        aria-valuenow={progress.current}
        aria-valuetext={progressLabel(progress)}
      >
        <div className="h-full bg-primary transition-[width]" style={{ width: `${percentage}%` }} />
      </div>
      {progress.message && <p className="mt-3 text-sm text-muted-foreground">{progress.message}</p>}
    </div>
  )
}

function parsePresentation(value: unknown): StakeholderPresentation {
  const parsed = typeof value === 'string' ? JSON.parse(value) : value
  const data = record(parsed)
  if (
    !data ||
    !record(data.overview) ||
    typeof data.score_count !== 'number' ||
    typeof data.scorecard_count !== 'number' ||
    !record(data.primary_decision_mix) ||
    !record(data.secondary_issue_counts) ||
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
    return {
      scorecard_ref: String(item.scorecard_ref || item.scorecard_name),
      scorecard_name: item.scorecard_name,
      score_count: Number(item.score_count || 0),
      primary_decision_mix: record(item.primary_decision_mix) as Record<string, number> || {},
      reviewed_error_opportunity: Number(item.reviewed_error_opportunity || 0),
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

  return {
    overview: data.overview as PresentationOverview,
    score_count: data.score_count,
    scorecard_count: data.scorecard_count,
    primary_decision_mix: data.primary_decision_mix,
    secondary_issue_counts: data.secondary_issue_counts,
    opportunity_distribution: opportunityDistribution,
    top_priorities: data.top_priorities,
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

function ScorecardSection({ scorecard, reportId }: { scorecard: ScorecardCard; reportId: string | null }) {
  const [expanded, setExpanded] = useState(false)
  const [details, setDetails] = useState<ScorecardPresentation | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const detailArtifact = scorecard.artifacts.find(artifact => artifact.kind === 'scorecard_presentation')
  const summaryArtifact = scorecard.artifacts.find(artifact => artifact.kind === 'scorecard_summary')
  const csvArtifact = scorecard.artifacts.find(artifact => artifact.kind === 'scorecard_portfolio_csv')

  const toggle = async () => {
    const opening = !expanded
    setExpanded(opening)
    if (!opening || details || loading || !detailArtifact) return
    setLoading(true)
    setError(null)
    try {
      const value = record(await loadJsonArtifact(detailArtifact))
      if (!value || !Array.isArray(value.scores) || !Array.isArray(value.questions_and_issues)) {
        throw new Error('Scorecard details artifact is malformed.')
      }
      setDetails({
        scorecard_name: String(value.scorecard_name || scorecard.scorecard_name),
        scores: value.scores.map((rawScore: unknown) => {
          const score = record(rawScore)
          if (!score) throw new Error('Scorecard details contain a malformed score.')
          const artifacts = Array.isArray(score.artifacts)
            ? score.artifacts.map(parseArtifactDescriptor)
            : []
          if (artifacts.some((artifact: ArtifactDescriptor | null) => artifact === null)) {
            throw new Error('Scorecard details contain a malformed score artifact.')
          }
          return { ...score, artifacts: artifacts as ArtifactDescriptor[] }
        }),
        questions_and_issues: value.questions_and_issues.map((rawIssue: unknown) => {
          const issue = record(rawIssue)
          if (!issue) throw new Error('Scorecard details contain a malformed question or issue.')
          return issue
        }),
      })
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
            return (
              <details key={`${score.score_name || 'score'}-${index}`} className="rounded-md bg-card p-3">
                <summary className="cursor-pointer font-medium">
                  {score.score_name || 'Unlabeled score'}
                  {score.readiness && <span className="ml-2 text-xs font-normal text-muted-foreground">{label(score.readiness)}</span>}
                </summary>
                <div className="mt-3 space-y-2 text-sm">
                  <p>{score.rationale || 'No rationale available.'}</p>
                  <p className="text-muted-foreground">
                    {score.valid_feedback_count ?? 0} valid feedback · {score.reviewed_disagreements ?? 0} reviewed disagreements
                  </p>
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

  const overview = presentation.overview
  const liveProgress = compactStatus.liveProgress
  const decisions = Object.entries(presentation.primary_decision_mix)
    .filter(([, count]) => count > 0)
    .sort((left, right) => right[1] - left[1])
  const decisionTotal = decisions.reduce((total, [, count]) => total + count, 0)

  return (
    <div className="space-y-6">
      <section className="rounded-lg bg-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm text-muted-foreground">{label(overview.lifecycle_status || 'running')} · {label(overview.coverage_status || 'pending')} coverage</p>
            <h2 className="mt-1 text-2xl font-semibold">Optimization portfolio overview</h2>
            {overview.current_activity && <p className="mt-2 max-w-3xl text-muted-foreground">{overview.current_activity}</p>}
          </div>
          <div className="rounded-md bg-primary/10 px-3 py-2 text-sm font-medium text-primary">
            {overview.pending_approval_count ?? 0} pending actions
          </div>
        </div>

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

        <div className="mt-6 grid gap-3 md:grid-cols-2">
          {liveProgress?.phase === 'assessment'
            ? <LiveProgressCard progress={liveProgress} />
            : <div className="rounded-md bg-muted/30 p-4"><div className="text-xs uppercase tracking-wide text-muted-foreground">Assessment</div><div className="mt-1 text-sm">{overview.assessment_progress || 'Pending'}</div></div>}
          {liveProgress?.phase === 'diagnosis'
            ? <LiveProgressCard progress={liveProgress} />
            : <div className="rounded-md bg-muted/30 p-4"><div className="text-xs uppercase tracking-wide text-muted-foreground">Diagnosis</div><div className="mt-1 text-sm">{overview.diagnosis_coverage || 'Pending'}</div></div>}
        </div>
      </section>

      {overview.coverage_status === 'incomplete' && (
        <section className="rounded-lg bg-amber-500/10 p-5">
          <h3 className="font-semibold">Why this run is incomplete</h3>
          <p className="mt-1 text-sm">{overview.notes || 'The available evidence was not complete enough for exact conclusions.'}</p>
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
        <h3 className="text-lg font-semibold">Primary decision mix</h3>
        <p className="text-sm text-muted-foreground">Each score appears exactly once according to its primary next action.</p>
        <div className="mt-4 flex h-8 overflow-hidden rounded-md bg-muted" aria-label={`Primary decision mix: ${decisionTotal} scores`}>
          {decisions.map(([key, count], index) => (
            <div
              key={key}
              className={`${DECISION_COLORS[index % DECISION_COLORS.length]} min-w-1`}
              style={{ width: `${decisionTotal ? count / decisionTotal * 100 : 0}%` }}
              title={`${label(key)}: ${count}`}
            />
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm">
          {decisions.map(([key, count], index) => (
            <span key={key} className="inline-flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-sm ${DECISION_COLORS[index % DECISION_COLORS.length]}`} />
              {label(key)}: {count}
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

      <section className="rounded-lg bg-card p-6">
        <h3 className="text-lg font-semibold">Top priorities</h3>
        <p className="text-sm text-muted-foreground">Shown in original evidence order. Cooldown and other policy gates remain visible and do not renumber the list.</p>
        <div className="mt-3 space-y-2">
          {presentation.top_priorities.map((priority, index) => (
            <div key={`${priority.scorecard_name}-${priority.score_name}-${index}`} className="rounded-md bg-muted/30 p-4 text-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <span className="rounded bg-muted px-2 py-1 text-xs font-medium">#{priority.rank ?? index + 1}</span>
                  <div>
                    <div><span className="font-medium">{priority.score_name || 'Unlabeled score'}</span><span className="text-muted-foreground"> · {priority.scorecard_name || 'Unlabeled scorecard'}</span></div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {priority.evidence_count ?? 0} valid feedback · {typeof priority.disagreement_rate === 'number' ? `${(priority.disagreement_rate * 100).toFixed(1)}% disagreement` : 'disagreement rate unavailable'} · {label(priority.readiness || 'inconclusive')}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {label(priority.review_disposition || priority.policy_disposition || 'eligible')}
                      {priority.policy_reason && priority.policy_reason !== 'meets_rank_policy' ? ` · ${label(priority.policy_reason)}` : ''}
                      {priority.candidate_rank ? ` · eligible candidate #${priority.candidate_rank}` : ''}
                    </div>
                  </div>
                </div>
                <div className="text-right text-muted-foreground">{priority.opportunity ?? 0} reviewed disagreements<br />{label(priority.next_action || 'review')}</div>
              </div>
              {priority.rationale && <p className="mt-3 text-muted-foreground">{priority.rationale}</p>}
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg bg-card p-6">
        <h3 className="text-lg font-semibold">Scorecards</h3>
        <p className="text-sm text-muted-foreground">Expand any number of scorecards to compare score-level evidence and actions.</p>
        <div className="mt-4 space-y-2">
          {presentation.scorecards.map(scorecard => (
            <ScorecardSection key={scorecard.scorecard_ref} scorecard={scorecard} reportId={reportId} />
          ))}
        </div>
      </section>
    </div>
  )
}

OptimizationRunStatus.blockClass = 'OptimizationRunStatus'

export default OptimizationRunStatus
