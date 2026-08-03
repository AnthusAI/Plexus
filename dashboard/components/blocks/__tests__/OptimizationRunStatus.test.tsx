import React from 'react'
import { TextDecoder } from 'util'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import OptimizationRunStatus, { OptimizationRunStatusPresentation } from '../OptimizationRunStatus'

Object.assign(global, { TextDecoder })

const mockReadTaskArtifact = jest.fn()

jest.mock('@/lib/artifact-ticket-client', () => ({
  issueTaskArtifactReadTicket: jest.fn(),
}))

jest.mock('@/lib/report-artifacts', () => {
  const actual = jest.requireActual('@/lib/report-artifacts')
  return { ...actual, readTaskArtifact: (...args: unknown[]) => mockReadTaskArtifact(...args) }
})

jest.mock('@/components/OptimizationOpportunityDistribution', () => ({
  __esModule: true,
  default: ({ rows }: { rows: Array<{
    disposition: string
    disagreement_rate?: number | null
    valid_feedback_count?: number | null
  }> }) => (
    <div>
      <span>Opportunity distribution</span>
      <span>Cooling down ({rows.filter(row => row.disposition === 'cooldown').length})</span>
      <span>First disagreement {rows[0]?.disagreement_rate}</span>
      <span>First feedback volume {rows[0]?.valid_feedback_count}</span>
    </div>
  ),
}))

const presentationDescriptor = {
  logical_id: 'stakeholder_presentation',
  kind: 'stakeholder_presentation',
  display_name: 'Stakeholder presentation data',
  scope: 'run',
  content_type: 'application/json',
  size_bytes: 10,
  sha256: 'a'.repeat(64),
  task_id: 'task-1',
  object_key: 'tasks/task-1/optimization-presentation-r0002.json',
  source_revision: 2,
}

const detailDescriptor = {
  ...presentationDescriptor,
  logical_id: 'scorecard_presentation:abc123',
  kind: 'scorecard_presentation',
  display_name: 'Interactive score details',
  scope: 'scorecard',
  object_key: 'tasks/task-1/scorecard-presentation-r0002.json',
  scorecard_name: 'Example Portfolio',
}

const summaryDescriptor = {
  ...detailDescriptor,
  logical_id: 'scorecard_summary:abc123',
  kind: 'scorecard_summary',
  display_name: 'Summary',
  content_type: 'text/markdown',
  object_key: 'tasks/task-1/scorecard-summary-r0002.md',
}

const scoreBriefDescriptor = {
  ...detailDescriptor,
  logical_id: 'score_brief:def456',
  kind: 'score_brief',
  display_name: 'Score brief',
  scope: 'score' as const,
  content_type: 'text/markdown',
  object_key: 'tasks/task-1/score-brief-r0002.md',
  score_name: 'Priority Score',
}

describe('OptimizationRunStatus', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockReadTaskArtifact.mockReset()
    window.history.replaceState({}, '', '/lab/reports/report-1')
    mockReadTaskArtifact
      .mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
        overview: {
          lifecycle_status: 'running',
          coverage_status: 'complete',
          scorecards_inspected: 4,
          scorecards_in_scope: 1,
          evidence_ranked_score_count: 4,
          ranked_score_count: 3,
          cooldown_excluded_count: 1,
          assessment_progress: '3 of 3 ranked scores complete',
          diagnosis_coverage: '1 of 1 scheduled diagnoses complete; 0 failed; 0 deferred by the safety cap',
          ranking_cutoff: 'none',
          priority_display_limit: 10,
          priority_displayed_count: 1,
          priority_cutoff_rank: 1,
          priority_cutoff_opportunity: 42,
          ranked_below_priority_cutoff: 2,
          diagnosis_top_priority_count: 1,
          diagnosis_monitoring_candidate_count: 0,
          diagnosis_selected_count: 1,
          diagnosis_scheduled_count: 1,
          diagnosis_deferred_count: 0,
          diagnosis_skipped_count: 2,
          diagnosis_max_count: 25,
          pending_approval_count: 1,
          current_activity: 'Preparing human decisions.',
          next_checkpoint: 'Approved work will be freshness checked.',
        },
        score_count: 3,
        scorecard_count: 1,
        primary_decision_mix: { optimize: 2, stakeholder_clarification: 1 },
        secondary_issue_counts: { 'stakeholder question': 2 },
        opportunity_distribution: [{
          evidence_rank: 1,
          scorecard_name: 'Example Portfolio',
          score_name: 'Recently changed score',
          opportunity: 60,
          disagreement_rate: 0.25,
          valid_feedback_count: 240,
          review_disposition: 'cooldown',
          policy_disposition: 'cooldown',
          policy_reason: 'recent_score_activity',
          eligibility_timestamp: '2026-08-05T00:00:00Z',
        }, {
          evidence_rank: 2,
          scorecard_name: 'Example Portfolio',
          score_name: 'Priority Score',
          opportunity: 42,
          review_disposition: 'selected_for_review',
          policy_disposition: 'eligible',
          policy_reason: 'meets_rank_policy',
        }],
        top_priorities: [{
          scorecard_name: 'Example Portfolio',
          score_name: 'Priority Score',
          opportunity: 42,
          rank: 1,
          evidence_count: 120,
          disagreement_rate: 0.35,
          readiness: 'ready_to_optimize',
          collection_state: 'continue_broad_collection',
          rationale: 'Reviewed errors show a safe opportunity.',
          next_action: 'request_optimization_approval',
        }, {
          scorecard_name: 'Example Portfolio',
          score_name: 'Secondary Score',
          opportunity: 6,
          rank: 2,
          evidence_count: 60,
          disagreement_rate: 0.10,
          readiness: 'insufficient_evidence',
          collection_state: 'continue_broad_collection',
          rationale: 'More feedback is needed.',
          next_action: 'collect_more_feedback',
        }, {
          scorecard_name: 'Example Portfolio',
          score_name: 'Unavailable Evidence Score',
          rank: 3,
          readiness: 'incomplete',
          collection_state: 'inconclusive',
          next_action: 'review_evidence',
        }],
        scorecards: [{
          scorecard_ref: 'safe-ref',
          scorecard_name: 'Example Portfolio',
          score_count: 3,
          primary_decision_mix: { optimize: 2, stakeholder_clarification: 1 },
          reviewed_error_opportunity: 42,
          artifacts: [summaryDescriptor, detailDescriptor],
        }],
      }))))
      .mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
        scorecard_name: 'Example Portfolio',
        scores: [{
          score_name: 'Priority Score',
          valid_feedback_count: 120,
          reviewed_disagreements: 42,
          readiness: 'ready_to_optimize',
          rationale: 'Reviewed errors show a safe opportunity.',
          next_action: 'request_optimization_approval',
          artifacts: [scoreBriefDescriptor],
        }],
        questions_and_issues: [{
          kind: 'stakeholder_question',
          score_name: 'Priority Score',
          finding: 'Should this exception be treated as acceptable?',
          next_action: 'request_stakeholder_clarification',
        }],
      }))))
  })

  it('shows safe aggregate artifact publication progress without storage identifiers', async () => {
    render(
      <OptimizationRunStatus
        id="block-1"
        type="OptimizationRunStatus"
        name="Run Status"
        position={0}
        config={{}}
        output={{
          output_compacted: true,
          preview: {
            type: 'optimization_run_status',
            status: 'published',
            summary: {
              revision: 2,
              milestone: 'assessment',
              presentation: presentationDescriptor,
              live_progress: {
                phase: 'publication',
                current: 3,
                total: 8,
                unit: 'artifacts',
                message: 'Publishing assessment milestone artifacts: scorecard spreadsheets.',
                next_checkpoint: 'Publishing the assessment milestone.',
                artifact_counts: {
                  decision_evidence: { completed: 1, total: 1 },
                  stakeholder_workbook: { completed: 1, total: 1 },
                  score_briefs: { completed: 1, total: 1 },
                  scorecard_summaries: { completed: 0, total: 1 },
                  scorecard_spreadsheets: { completed: 0, total: 1 },
                  scorecard_presentations: { completed: 0, total: 1 },
                  stakeholder_presentation: { completed: 0, total: 1 },
                  revision_manifest: { completed: 0, total: 1 },
                  object_key: { completed: 99, total: 99 },
                },
              },
            },
          },
        }}
      />,
    )

    expect(await screen.findByText('3 of 8 artifacts')).toBeInTheDocument()
    expect(screen.getByText('Scorecard spreadsheets')).toBeInTheDocument()
    expect(screen.getAllByText('1 / 1')).toHaveLength(3)
    expect(screen.queryByText('Object key')).not.toBeInTheDocument()
  })

  it('shows reconciled aggregate visuals and loads score details only when expanded', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <OptimizationRunStatus
        id="block-1"
        type="OptimizationRunStatus"
        name="Run Status"
        position={0}
        config={{}}
        output={{
          output_compacted: true,
          preview: {
            type: 'optimization_run_status',
            status: 'published',
            summary: {
              revision: 2,
              milestone: 'diagnosis',
              presentation: presentationDescriptor,
              live_progress: {
                phase: 'assessment',
                current: 10,
                total: 100,
                message: 'Assessing 10 of 100 scores.',
                updated_at: '2026-07-30T18:00:00Z',
              },
            },
          },
        }}
      />,
    )

    expect(await screen.findByText('10 of 100 scores assessed')).toBeInTheDocument()
    expect(screen.getByText('Assessing 10 of 100 scores.')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Assessment progress' })).toHaveAttribute('aria-valuenow', '10')
    expect(screen.getByText('Scorecards inspected')).toBeInTheDocument()
    expect(screen.queryByText('Account inventory inspected')).not.toBeInTheDocument()
    expect(screen.getByText('Scorecards in scope')).toBeInTheDocument()
    expect(screen.getByText('Evidence-ranked scores')).toBeInTheDocument()
    expect(screen.getByText('Eligible candidates')).toBeInTheDocument()
    expect(screen.getByText('Cooldown deferrals')).toBeInTheDocument()
    expect(screen.getByText('Opportunity distribution')).toBeInTheDocument()
    expect(screen.getByText('Cooling down (1)')).toBeInTheDocument()
    expect(screen.getByText('First disagreement 0.25')).toBeInTheDocument()
    expect(screen.getByText('First feedback volume 240')).toBeInTheDocument()
    expect(screen.getByLabelText('Primary decision mix: 3 scores')).toBeInTheDocument()
    expect(screen.getByText('Optimize: 2')).toBeInTheDocument()
    expect(screen.getByText('Stakeholder clarification: 1')).toBeInTheDocument()
    expect(screen.getByText('Priority Score')).toBeInTheDocument()
    expect(screen.getByText('Evidence rank before policy gates')).toBeInTheDocument()
    expect(screen.getByText(/Top 10 evidence ranks are highlighted/)).toBeInTheDocument()
    expect(screen.getByText(/1 selected for deeper review/)).toBeInTheDocument()
    expect(screen.getByText(/1 are scheduled in this run; 0 are deferred by the safety cap/)).toBeInTheDocument()
    expect(screen.getByText(/120 valid feedback/)).toBeInTheDocument()
    expect(screen.getByText('Reviewed errors show a safe opportunity.')).toBeInTheDocument()
    expect(screen.getByText('78 agreements')).toBeInTheDocument()
    expect(screen.getByText('42 disagreements')).toBeInTheDocument()
    expect(screen.getByText('35.0% disagreement')).toBeInTheDocument()
    expect(screen.getByRole('meter', { name: 'Feedback outcomes for Priority Score' })).toHaveStyle({ width: '100%' })
    expect(screen.getByRole('meter', { name: 'Feedback outcomes for Priority Score' })).toHaveAttribute(
      'aria-valuetext',
      '78 agreements, 42 disagreements, 120 valid feedback, 35.0% disagreement',
    )
    expect(screen.getByLabelText('Agreements for Priority Score')).toHaveStyle({ width: '65%' })
    expect(screen.getByLabelText('Disagreements for Priority Score')).toHaveStyle({ width: '35%' })
    expect(screen.getByRole('meter', { name: 'Feedback outcomes for Secondary Score' })).toHaveStyle({ width: '50%' })
    expect(screen.getByRole('meter', { name: 'Feedback outcomes for Unavailable Evidence Score' })).toHaveStyle({ width: '0%' })
    expect(screen.getByRole('meter', { name: 'Feedback outcomes for Unavailable Evidence Score' })).toHaveAttribute('aria-valuetext', 'Unavailable')
    expect(mockReadTaskArtifact).toHaveBeenCalledTimes(1)

    rerender(
      <OptimizationRunStatus
        id="block-1"
        type="OptimizationRunStatus"
        name="Run Status"
        position={0}
        config={{}}
        output={{
          output_compacted: true,
          preview: {
            type: 'optimization_run_status',
            status: 'published',
            summary: {
              revision: 2,
              milestone: 'diagnosis',
              presentation: presentationDescriptor,
              live_progress: {
                phase: 'assessment',
                current: 11,
                total: 100,
                message: 'Assessing 11 of 100 scores.',
                updated_at: '2026-07-30T18:01:00Z',
              },
            },
          },
        }}
      />,
    )

    expect(screen.getByText('11 of 100 scores assessed')).toBeInTheDocument()
    expect(screen.getByText('Assessing 11 of 100 scores.')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Assessment progress' })).toHaveAttribute('aria-valuenow', '11')
    expect(mockReadTaskArtifact).toHaveBeenCalledTimes(1)

    rerender(
      <OptimizationRunStatus
        id="block-1"
        type="OptimizationRunStatus"
        name="Run Status"
        position={0}
        config={{}}
        output={{
          output_compacted: true,
          preview: {
            type: 'optimization_run_status',
            status: 'published',
            summary: {
              revision: 2,
              milestone: 'diagnosis',
              presentation: presentationDescriptor,
              live_progress: {
                phase: 'diagnosis',
                current: 73,
                total: 125,
                message: 'Diagnosing 73 of 125 selected scores.',
                updated_at: '2026-07-30T18:02:00Z',
              },
            },
          },
        }}
      />,
    )

    expect(screen.getByText('73 of 125 analysis steps complete')).toBeInTheDocument()
    expect(screen.getByText('Diagnosing 73 of 125 selected scores.')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Diagnosis progress' })).toHaveAttribute('aria-valuenow', '73')
    expect(mockReadTaskArtifact).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('button', { name: /Example Portfolio/ }))

    expect(await screen.findAllByText('Reviewed errors show a safe opportunity.')).toHaveLength(2)
    expect(screen.getAllByText(/120 valid feedback/)).toHaveLength(2)
    expect(screen.getByText('Should this exception be treated as acceptable?')).toBeInTheDocument()
    expect(mockReadTaskArtifact).toHaveBeenCalledTimes(2)
    expect(screen.getByRole('link', { name: 'Summary artifact' })).toHaveAttribute(
      'href',
      '/lab/reports/report-1?revision=2&artifact=scorecard_summary%3Aabc123',
    )
    expect(screen.getByRole('link', { name: 'Open score brief' })).toHaveAttribute(
      'href',
      '/lab/reports/report-1?revision=2&artifact=score_brief%3Adef456',
    )
  })

  it('distinguishes complete inventory coverage from incomplete semantic analysis', async () => {
    mockReadTaskArtifact.mockReset().mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
      overview: {
        lifecycle_status: 'incomplete',
        coverage_status: 'complete',
        inventory_coverage_status: 'complete',
        analysis_coverage_status: 'incomplete',
        diagnosis_incomplete_count: 2,
        diagnosis_deferred_count: 8,
        diagnosis_coverage: '2 of 2 scheduled diagnoses returned; 2 incomplete results; 0 execution failures; 8 deferred by the safety cap',
        next_checkpoint: 'Review incomplete semantic findings.',
      },
      score_count: 0,
      scorecard_count: 0,
      primary_decision_mix: {},
      secondary_issue_counts: {},
      opportunity_distribution: [],
      top_priorities: [],
      scorecards: [],
    }))))

    render(
      <OptimizationRunStatus
        id="block-1"
        type="OptimizationRunStatus"
        name="Run Status"
        position={0}
        config={{}}
        output={{
          output_compacted: true,
          preview: {
            type: 'optimization_run_status',
            status: 'published',
            summary: {
              revision: 3,
              milestone: 'finalization',
              presentation: presentationDescriptor,
            },
          },
        }}
      />,
    )

    expect(await screen.findByText('Incomplete · Inventory complete · Analysis incomplete')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Why this run is incomplete' })).toBeInTheDocument()
    expect(screen.getByText(/2 diagnosis results were incomplete/)).toBeInTheDocument()
    expect(screen.getByText(/8 selected diagnoses were deferred by the safety cap/)).toBeInTheDocument()
  })

  it('uses a newer live assessment count without rendering the stale durable count as current progress', async () => {
    mockReadTaskArtifact.mockReset().mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
      overview: {
        lifecycle_status: 'running',
        coverage_status: 'complete',
        assessment_progress: '0 of 100 eligible candidates assessed',
      },
      score_count: 0,
      scorecard_count: 0,
      primary_decision_mix: {},
      secondary_issue_counts: {},
      attention_queue: [],
      questions_and_issues: [],
      optimization_outcomes: [],
      opportunity_distribution: [],
      top_priorities: [],
      scorecards: [],
    }))))

    render(
      <OptimizationRunStatus
        id="block-1"
        type="OptimizationRunStatus"
        name="Run Status"
        position={0}
        config={{}}
        output={{
          output_compacted: true,
          preview: {
            type: 'optimization_run_status',
            status: 'published',
            summary: {
              revision: 2,
              milestone: 'assessment',
              presentation: presentationDescriptor,
              live_progress: {
                phase: 'assessment',
                current: 37,
                total: 100,
                message: 'Assessing 37 of 100 candidates.',
                updated_at: '2026-07-31T13:00:00Z',
              },
            },
          },
        }}
      />,
    )

    expect(await screen.findByText('37 of 100 scores assessed')).toBeInTheDocument()
    expect(screen.queryByText('0 of 100 eligible candidates assessed')).not.toBeInTheDocument()
  })

  it('keeps a newer durable assessment milestone visible when live progress is stale', async () => {
    mockReadTaskArtifact.mockReset().mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
      overview: {
        lifecycle_status: 'running',
        coverage_status: 'complete',
        assessment_progress: '72 of 100 eligible candidates assessed',
      },
      score_count: 0,
      scorecard_count: 0,
      primary_decision_mix: {},
      secondary_issue_counts: {},
      attention_queue: [],
      questions_and_issues: [],
      optimization_outcomes: [],
      opportunity_distribution: [],
      top_priorities: [],
      scorecards: [],
    }))))

    render(
      <OptimizationRunStatus
        id="block-1"
        type="OptimizationRunStatus"
        name="Run Status"
        position={0}
        config={{}}
        output={{
          output_compacted: true,
          preview: {
            type: 'optimization_run_status',
            status: 'published',
            summary: {
              revision: 3,
              milestone: 'assessment',
              presentation: presentationDescriptor,
              live_progress: {
                phase: 'assessment',
                current: 71,
                total: 100,
                message: 'Assessing 71 of 100 candidates.',
                updated_at: '2026-07-31T12:59:00Z',
              },
            },
          },
        }}
      />,
    )

    expect(await screen.findByText('72 of 100 eligible candidates assessed')).toBeInTheDocument()
    expect(screen.queryByText('71 of 100 scores assessed')).not.toBeInTheDocument()
    expect(screen.queryByText('Assessing 71 of 100 candidates.')).not.toBeInTheDocument()
  })

  it('does not overlay live assessment progress from a different cohort total', async () => {
    mockReadTaskArtifact.mockReset().mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
      overview: {
        lifecycle_status: 'running',
        coverage_status: 'complete',
        assessment_progress: '72 of 100 eligible candidates assessed',
      },
      score_count: 0,
      scorecard_count: 0,
      primary_decision_mix: {},
      secondary_issue_counts: {},
      attention_queue: [],
      questions_and_issues: [],
      optimization_outcomes: [],
      opportunity_distribution: [],
      top_priorities: [],
      scorecards: [],
    }))))

    render(
      <OptimizationRunStatus
        id="block-1"
        type="OptimizationRunStatus"
        name="Run Status"
        position={0}
        config={{}}
        output={{
          output_compacted: true,
          preview: {
            type: 'optimization_run_status',
            status: 'published',
            summary: {
              revision: 3,
              milestone: 'assessment',
              presentation: presentationDescriptor,
              live_progress: {
                phase: 'assessment',
                current: 73,
                total: 101,
                message: 'Assessing 73 of 101 candidates.',
                updated_at: '2026-07-31T13:01:00Z',
              },
            },
          },
        }}
      />,
    )

    expect(await screen.findByText('72 of 100 eligible candidates assessed')).toBeInTheDocument()
    expect(screen.queryByText('73 of 101 scores assessed')).not.toBeInTheDocument()
    expect(screen.queryByText('Assessing 73 of 101 candidates.')).not.toBeInTheDocument()
  })

  it('shows aggregate ranking progress, retry status, and an unknown inventory total', async () => {
    render(
      <OptimizationRunStatus
        id="block-1"
        type="OptimizationRunStatus"
        name="Run Status"
        position={0}
        config={{}}
        output={{
          output_compacted: true,
          preview: {
            type: 'optimization_run_status',
            status: 'published',
            summary: {
              revision: 2,
              milestone: 'started',
              presentation: presentationDescriptor,
              live_progress: {
                phase: 'ranking',
                subphase: 'feedback_analysis',
                current: 12,
                total: null,
                unit: 'scorecards',
                state: 'retrying',
                elapsed_seconds: 63,
                next_checkpoint: 'Retrying the inventory page.',
                message: 'Inventory has inspected 12 scorecards; retrying a page.',
                updated_at: '2026-07-31T12:00:00Z',
              },
            },
          },
        }}
      />,
    )

    expect(await screen.findByText('12 scorecards inspected')).toBeInTheDocument()
    expect(screen.getByText('Ranking / Feedback analysis status')).toBeInTheDocument()
    expect(screen.getByText('Retrying')).toBeInTheDocument()
    expect(screen.getByText('Elapsed: 1m 3s')).toBeInTheDocument()
    expect(screen.getByText('Next: Retrying the inventory page.')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar', { name: 'Ranking progress' })).not.toBeInTheDocument()
  })

  it('does not render stale ranking progress over a durable ranking milestone', async () => {
    render(
      <OptimizationRunStatus
        id="block-1"
        type="OptimizationRunStatus"
        name="Run Status"
        position={0}
        config={{}}
        output={{
          output_compacted: true,
          preview: {
            type: 'optimization_run_status',
            status: 'published',
            summary: {
              revision: 2,
              milestone: 'assessment',
              presentation: presentationDescriptor,
              live_progress: {
                phase: 'ranking',
                subphase: 'inventory',
                current: 12,
                total: null,
                unit: 'scorecards',
                message: 'This delayed ranking callback must not overlay assessment.',
                updated_at: '2026-07-31T12:00:00Z',
              },
            },
          },
        }}
      />,
    )

    await screen.findByText('Optimization opportunity survey')
    expect(screen.queryByText('12 scorecards inspected')).not.toBeInTheDocument()
  })

  it('presents the canonical optimizer lifecycle, attention, outcomes, and score detail contract', async () => {
    const user = userEvent.setup()
    mockReadTaskArtifact.mockReset()
      .mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
        overview: {
          lifecycle_status: 'running',
          coverage_status: 'complete',
          scorecards_inspected: 2,
          scorecards_in_scope: 2,
          evidence_ranked_score_count: 7,
          ranked_score_count: 7,
          pending_approval_count: 1,
          current_activity: 'Approved optimizations are running and completed evidence is being reviewed.',
        },
        score_count: 7,
        scorecard_count: 2,
        primary_disposition_counts: {
          awaiting_optimization_approval: 1,
          optimizer_launching: 1,
          optimization_in_progress: 1,
          awaiting_optimizer_review: 1,
          promotion_ready: 1,
          continue_optimization: 1,
          failed_or_incomplete: 1,
        },
        primary_decision_mix: { optimize: 7 },
        secondary_issue_counts: {
          feedback_rubric_contradiction: 2,
          stakeholder_question: 1,
        },
        attention_queue: [{
          scorecard_name: 'Example Portfolio',
          score_name: 'Priority Score',
          primary_disposition: 'optimization_in_progress',
          secondary_issue_flags: ['feedback_rubric_contradiction', 'stakeholder_question'],
          evidence_count: 120,
          severity: 1,
          rationale: 'Recent feedback conflicts with the current rubric on an important class.',
          next_action: 'answer_stakeholder_question',
          dashboard_url: 'https://dashboard.example.test/scores/priority',
        }],
        questions_and_issues: [{
          issue_flag: 'feedback_rubric_contradiction',
          issue_severity: 1,
          scorecard_name: 'Example Portfolio',
          score_name: 'Priority Score',
          affected_evidence_count: 48,
          finding: 'Recent feedback and the written rubric disagree.',
          next_action: 'answer_stakeholder_question',
          dashboard_url: 'https://dashboard.example.test/scores/priority',
        }, {
          issue_flag: 'stakeholder_question',
          issue_severity: 2,
          scorecard_name: 'Second Portfolio',
          score_name: 'Policy Score',
          affected_evidence_count: 12,
          finding: 'Stakeholders need to decide how an exception should be handled.',
          next_action: 'answer_question',
        }],
        optimization_outcomes: [{
          scorecard_name: 'Example Portfolio',
          score_name: 'Priority Score',
          primary_disposition: 'optimization_in_progress',
          secondary_issue_flags: ['feedback_rubric_contradiction'],
          outcome: 'optimization_in_progress',
          readiness: 'optimization_in_progress',
          promotion_readiness: 'not_evaluated',
          evidence_count: 120,
          trend: 'Disagreement increased in the latest four complete weeks.',
          rationale: 'The approved optimizer is running under the published limits.',
          next_action: 'wait_for_optimizer_completion',
          dashboard_url: 'https://dashboard.example.test/scores/priority',
        }, {
          scorecard_name: 'Second Portfolio',
          score_name: 'Promotion Candidate',
          primary_disposition: 'promotion_ready',
          secondary_issue_flags: [],
          outcome: 'promotion_ready',
          readiness: 'promotion_ready',
          promotion_readiness: 'promotion_ready',
          evidence_count: 80,
          trend: 'Stable across the latest complete weeks.',
          rationale: 'The candidate improved safely across recent and historical evidence.',
          next_action: 'request_promotion_approval',
        }],
        opportunity_distribution: [],
        top_priorities: [],
        scorecards: [{
          scorecard_ref: 'safe-ref',
          scorecard_name: 'Example Portfolio',
          score_count: 1,
          primary_disposition_counts: { optimization_in_progress: 1 },
          primary_decision_mix: { optimize: 1 },
          reviewed_error_opportunity: 42,
          artifacts: [summaryDescriptor, detailDescriptor],
        }, {
          scorecard_ref: 'second-safe-ref',
          scorecard_name: 'Second Portfolio',
          score_count: 1,
          primary_disposition_counts: { promotion_ready: 1 },
          primary_decision_mix: { promotion_review: 1 },
          reviewed_error_opportunity: 8,
          artifacts: [],
        }],
      }))))
      .mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
        scorecard_name: 'Example Portfolio',
        scores: [{
          score_name: 'Priority Score',
          primary_disposition: 'optimization_in_progress',
          secondary_issue_flags: ['feedback_rubric_contradiction', 'stakeholder_question'],
          valid_feedback_count: 120,
          reviewed_disagreements: 42,
          disagreement_rate: 0.35,
          readiness: 'optimization_in_progress',
          outcome: 'optimization_in_progress',
          promotion_readiness: 'not_evaluated',
          trend: 'Disagreement increased in the latest four complete weeks.',
          rationale: 'The approved optimizer is running under the published limits.',
          next_action: 'wait_for_optimizer_completion',
          dashboard_url: 'https://dashboard.example.test/scores/priority',
          artifacts: [scoreBriefDescriptor],
        }],
        questions_and_issues: [],
      }))))

    render(
      <OptimizationRunStatus
        id="block-1"
        type="OptimizationRunStatus"
        name="Run Status"
        position={0}
        config={{}}
        output={{
          output_compacted: true,
          preview: {
            type: 'optimization_run_status',
            status: 'published',
            summary: {
              revision: 4,
              milestone: 'optimization',
              presentation: presentationDescriptor,
            },
          },
        }}
      />,
    )

    expect(await screen.findByRole('heading', { name: 'Optimization lifecycle' })).toBeInTheDocument()
    expect(screen.getByText('Awaiting approval')).toBeInTheDocument()
    expect(screen.getByTestId('lifecycle-awaiting-approval')).toHaveTextContent('1')
    expect(screen.getByTestId('lifecycle-launching-running')).toHaveTextContent('2')
    expect(screen.getByTestId('lifecycle-review-pending')).toHaveTextContent('1')
    expect(screen.getByTestId('lifecycle-promotion-ready')).toHaveTextContent('1')
    expect(screen.getByTestId('lifecycle-continue-or-no-safe-improvement')).toHaveTextContent('1')
    expect(screen.getByTestId('lifecycle-failed-incomplete')).toHaveTextContent('1')
    expect(screen.getByLabelText('Primary disposition mix: 7 scores')).toBeInTheDocument()
    expect(screen.getByText('Optimization in progress: 1')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Contradictions and stakeholder questions' })).toBeInTheDocument()
    expect(screen.getByText('Recent feedback and the written rubric disagree.')).toBeInTheDocument()
    expect(screen.getByText('48 affected feedback items')).toBeInTheDocument()
    expect(screen.getAllByText('Answer stakeholder question').length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: 'Optimization progress and outcomes' })).toBeInTheDocument()
    expect(screen.getByText('The candidate improved safely across recent and historical evidence.')).toBeInTheDocument()
    expect(screen.getByText('Request promotion approval')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Example Portfolio/ }))

    expect(await screen.findByText('Primary disposition')).toBeInTheDocument()
    expect(screen.getAllByText('Optimization in progress').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Feedback rubric contradiction').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Stakeholder question').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Disagreement increased in the latest four complete weeks.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('The approved optimizer is running under the published limits.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Wait for optimizer completion').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'Open score in dashboard' })).toHaveAttribute(
      'href',
      'https://dashboard.example.test/scores/priority',
    )
    expect(screen.getByRole('link', { name: 'Open score brief' })).toBeInTheDocument()
    expect(screen.queryByText('task-1')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Second Portfolio/ }))
    expect(screen.getByRole('button', { name: /Example Portfolio/ })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: /Second Portfolio/ })).toHaveAttribute('aria-expanded', 'true')
  })

  it('renders canonical-only disposition counts, producer policy fields, and progressively disclosed report lists', async () => {
    const user = userEvent.setup()
    mockReadTaskArtifact.mockReset()
      .mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
        overview: { lifecycle_status: 'running', coverage_status: 'complete' },
        score_count: 17,
        scorecard_count: 1,
        primary_disposition_counts: {
          promotion_ready: 1,
          continue_optimization: 1,
          stakeholder_decision_required: 1,
          no_safe_improvement: 1,
          failed_or_incomplete: 1,
          awaiting_optimizer_review: 1,
          optimization_in_progress: 1,
          optimizer_launching: 1,
          awaiting_optimization_approval: 1,
          stakeholder_clarification_required: 1,
          guideline_or_code_repair: 1,
          feedback_curation_review: 1,
          monitoring_or_diminishing_returns: 1,
          targeted_feedback_collection: 1,
          cooldown: 1,
          insufficient_evidence: 1,
          not_selected: 1,
        },
        secondary_issue_counts: {},
        attention_queue: Array.from({ length: 6 }, (_, index) => ({
          scorecard_name: 'Example Portfolio', score_name: `Attention ${index + 1}`,
          primary_disposition: 'stakeholder_decision_required', evidence_count: 10 - index,
        })),
        questions_and_issues: Array.from({ length: 6 }, (_, index) => ({
          scorecard_name: 'Example Portfolio', score_name: `Issue ${index + 1}`,
          issue_flag: 'stakeholder_question', finding: `Issue finding ${index + 1}`,
        })),
        optimization_outcomes: Array.from({ length: 6 }, (_, index) => ({
          scorecard_name: 'Example Portfolio', score_name: `Outcome ${index + 1}`,
          primary_disposition: 'promotion_ready', outcome: 'promotion_ready',
          rationale: `Outcome rationale ${index + 1}`,
        })),
        opportunity_distribution: [],
        top_priorities: [{
          scorecard_name: 'Example Portfolio', score_name: 'Ranked score',
          evidence_rank: 4, candidate_rank: 2, policy_disposition: 'cooldown',
          policy_reason: 'recent_score_activity', review_disposition: 'blocked',
          eligibility_timestamp: '2026-08-05T00:00:00Z',
        }],
        scorecards: [{
          scorecard_ref: 'safe-ref', scorecard_name: 'Example Portfolio', score_count: 1,
          reviewed_error_opportunity: 1, artifacts: [detailDescriptor],
        }],
      }))))
      .mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
        scorecard_name: 'Example Portfolio', questions_and_issues: [], scores: [{
          score_name: 'Ranked score', evidence_rank: 4, candidate_rank: 2,
          primary_disposition: 'cooldown', policy_disposition: 'cooldown',
          policy_reason: 'recent_score_activity', review_disposition: 'blocked',
          eligibility_timestamp: '2026-08-05T00:00:00Z', artifacts: [],
        }],
      }))))

    render(<OptimizationRunStatus id="block-1" type="OptimizationRunStatus" name="Run Status" position={0} config={{}}
      output={{ output_compacted: true, preview: { summary: { presentation: presentationDescriptor } } }} />)

    expect(await screen.findByLabelText('Primary disposition mix: 17 scores')).toBeInTheDocument()
    expect(screen.getByTestId('lifecycle-total')).toHaveTextContent('17 of 17 scores')
    expect(screen.getByText('Stakeholder decision required: 1')).toBeInTheDocument()
    expect(screen.getByText('Evidence rank #4')).toBeInTheDocument()
    expect(screen.getByText('Eligible candidate #2')).toBeInTheDocument()
    expect(screen.getByText('Policy: Cooldown · Recent score activity')).toBeInTheDocument()
    expect(screen.getByText('Review: Blocked')).toBeInTheDocument()
    expect(screen.getByText('Eligible after: 2026-08-05T00:00:00Z')).toBeInTheDocument()
    expect(screen.queryByText('Attention 6')).not.toBeInTheDocument()
    expect(screen.queryByText('Issue finding 6')).not.toBeInTheDocument()
    expect(screen.queryByText('Outcome rationale 6')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Show up to 25 examples (of 6)' }))
    await user.click(screen.getByRole('button', { name: 'Show all issues (6)' }))
    await user.click(screen.getByRole('button', { name: 'Show all outcomes (6)' }))
    expect(screen.getByText('Attention 6')).toBeInTheDocument()
    expect(screen.getByText('Issue finding 6')).toBeInTheDocument()
    expect(screen.getByText('Outcome rationale 6')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Collapse examples' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Example Portfolio/ }))
    await user.click(screen.getAllByText('Ranked score').at(-1)!)
    expect(await screen.findAllByText('Evidence rank #4')).toHaveLength(2)
    expect(screen.getAllByText('Eligible candidate #2')).toHaveLength(2)
    expect(screen.getAllByText('Policy: Cooldown · Recent score activity')).toHaveLength(2)
    expect(screen.getAllByText('Review: Blocked')).toHaveLength(2)
    expect(screen.getAllByText('Eligible after: 2026-08-05T00:00:00Z')).toHaveLength(2)
  })

  it.each([
    ['an array used as the artifact record', []],
    ['an invalid count map', { primary_decision_mix: { optimize: -1 } }],
    ['a malformed issue row', { questions_and_issues: [[]] }],
    ['a malformed outcome row', { optimization_outcomes: [[]] }],
    ['malformed attention flags', { attention_queue: [{ secondary_issue_flags: { not: 'a list' } }] }],
    ['a malformed nested issue action', { questions_and_issues: [{ next_action: { not: 'text' } }] }],
    ['a malformed nested outcome disposition', { optimization_outcomes: [{ primary_disposition: [] }] }],
    ['an unknown attention disposition', { attention_queue: [{ primary_disposition: 'unaccounted_attention_state' }] }],
    ['an unknown outcome disposition', { optimization_outcomes: [{ primary_disposition: 'unaccounted_outcome_state' }] }],
    ['a malformed nested priority action', { top_priorities: [{ next_action: [] }] }],
    ['an unknown canonical disposition', { primary_disposition_counts: { unaccounted_state: 1 } }],
  ])('shows a visible error for %s', async (_description, override) => {
    const artifact = {
      overview: {}, score_count: 0, scorecard_count: 0,
      primary_decision_mix: {}, secondary_issue_counts: {},
      attention_queue: [], questions_and_issues: [], optimization_outcomes: [],
      opportunity_distribution: [], top_priorities: [], scorecards: [],
      ...(Array.isArray(override) ? {} : override),
    }
    mockReadTaskArtifact.mockReset().mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify(override))))
    if (!Array.isArray(override)) {
      mockReadTaskArtifact.mockReset().mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify(artifact))))
    }

    render(<OptimizationRunStatus id="block-1" type="OptimizationRunStatus" name="Run Status" position={0} config={{}}
      output={{ output_compacted: true, preview: { summary: { presentation: presentationDescriptor } } }} />)

    expect(await screen.findByText(/malformed|invalid count/i)).toBeInTheDocument()
  })

  it.each([
    ['score', [{ score_name: 'Malformed score', primary_disposition: [] }], []],
    ['score disposition', [{ score_name: 'Readable score name', primary_disposition: 'unaccounted_detail_state' }], []],
    ['question', [{ score_name: 'Valid score', artifacts: [] }], [{ score_name: 'Valid score', next_action: {} }]],
  ])('shows a visible artifact error for a malformed scorecard-detail %s row', async (_kind, scores, questions) => {
    const user = userEvent.setup()
    mockReadTaskArtifact
      .mockReset()
      .mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
        overview: {}, score_count: 1, scorecard_count: 1,
        primary_disposition_counts: { not_selected: 1 }, primary_decision_mix: {}, secondary_issue_counts: {},
        attention_queue: [], questions_and_issues: [], optimization_outcomes: [],
        opportunity_distribution: [], top_priorities: [],
        scorecards: [{
          scorecard_ref: 'detail-fixture', scorecard_name: 'Detail fixture', score_count: 1,
          reviewed_error_opportunity: 0, artifacts: [detailDescriptor],
        }],
      }))))
      .mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
        scorecard_name: 'Detail fixture', scores, questions_and_issues: questions,
      }))))

    render(<OptimizationRunStatus id="block-1" type="OptimizationRunStatus" name="Run Status" position={0} config={{}}
      output={{ output_compacted: true, preview: { summary: { presentation: presentationDescriptor } } }} />)

    await user.click(await screen.findByRole('button', { name: /Detail fixture/ }))

    expect(await screen.findByText(/scorecard details contain a malformed/i)).toBeInTheDocument()
  })

  it('renders injected stakeholder data without reading an artifact and keeps scorecards independently expandable', async () => {
    const user = userEvent.setup()
    mockReadTaskArtifact.mockReset()
    const presentation = {
      overview: { lifecycle_status: 'complete' },
      score_count: 2,
      scorecard_count: 2,
      primary_disposition_counts: { promotion_ready: 1, cooldown: 1 },
      primary_decision_mix: {},
      secondary_issue_counts: {},
      attention_queue: [],
      questions_and_issues: [],
      optimization_outcomes: [],
      opportunity_distribution: [],
      top_priorities: [],
      scorecards: [
        { scorecard_ref: 'fixture-one', scorecard_name: 'Fixture group one', score_count: 1, reviewed_error_opportunity: 0, artifacts: [] },
        { scorecard_ref: 'fixture-two', scorecard_name: 'Fixture group two', score_count: 1, reviewed_error_opportunity: 0, artifacts: [] },
      ],
    }

    const { rerender } = render(
      <OptimizationRunStatusPresentation
        presentation={presentation}
        scorecardDetails={{
          'fixture-one': { scorecard_name: 'Fixture group one', questions_and_issues: [], scores: [{ score_name: 'Fixture score one', artifacts: [] }] },
          'fixture-two': { scorecard_name: 'Fixture group two', questions_and_issues: [], scores: [{ score_name: 'Fixture score two', artifacts: [] }] },
        }}
      />,
    )

    await user.click(screen.getByRole('button', { name: /Fixture group one/ }))
    await user.click(screen.getByRole('button', { name: /Fixture group two/ }))

    expect(screen.getByText('Fixture score one')).toBeInTheDocument()
    expect(screen.getByText('Fixture score two')).toBeInTheDocument()
    expect(mockReadTaskArtifact).not.toHaveBeenCalled()

    rerender(
      <OptimizationRunStatusPresentation
        presentation={{
          ...presentation,
          overview: { ...presentation.overview, current_activity: 'A compatible realtime update arrived.' },
        }}
        scorecardDetails={{
          'fixture-one': { scorecard_name: 'Fixture group one', questions_and_issues: [], scores: [{ score_name: 'Fixture score one', artifacts: [] }] },
          'fixture-two': { scorecard_name: 'Fixture group two', questions_and_issues: [], scores: [{ score_name: 'Fixture score two', artifacts: [] }] },
        }}
      />,
    )

    expect(screen.getByText('A compatible realtime update arrived.')).toBeInTheDocument()
    expect(screen.getByText('Fixture score one')).toBeInTheDocument()
    expect(screen.getByText('Fixture score two')).toBeInTheDocument()
  })

  it('shows automatic execution counts and score decisions without an approval-pending message', async () => {
    const user = userEvent.setup()
    render(
      <OptimizationRunStatusPresentation
        presentation={{
          overview: {
            lifecycle_status: 'running',
            execution_mode: 'automatic',
            execution_selected_count: 2,
            execution_launched_count: 1,
            execution_rejected_count: 1,
            execution_named_selected_count: 1,
            execution_named_launched_count: 1,
            execution_named_rejected_count: 1,
            execution_detail_coverage: 'incomplete',
            execution_detail_limitation: 'Named detail is available for 1 of 2 selected targets.',
            pending_approval_count: 0,
          },
          score_count: 2,
          scorecard_count: 1,
          primary_disposition_counts: { optimization_in_progress: 1, no_safe_improvement: 1 },
          primary_decision_mix: {}, secondary_issue_counts: {}, attention_queue: [],
          questions_and_issues: [], optimization_outcomes: [], opportunity_distribution: [], top_priorities: [],
          scorecards: [{
            scorecard_ref: 'automatic-fixture', scorecard_name: 'Automatic fixture', score_count: 2,
            reviewed_error_opportunity: 0, artifacts: [],
          }],
        }}
        scorecardDetails={{
          'automatic-fixture': {
            scorecard_name: 'Automatic fixture', questions_and_issues: [], scores: [{
              score_name: 'Launched score', execution_status: 'automatic_launched',
              execution_reason: 'Meets the automatic policy.',
              execution_authorization_source: 'published_policy', artifacts: [],
            }, {
              score_name: 'Policy-excluded score', execution_status: 'automatic_rejected',
              execution_reason: 'Outside the safety cap.', artifacts: [],
            }],
          },
        }}
      />,
    )

    expect(screen.getByText('Automatic execution')).toBeInTheDocument()
    expect(screen.getAllByText(/policy-selected/).length).toBeGreaterThan(0)
    expect(screen.getByText(/safe, policy-selected targets may launch automatically/i)).toBeInTheDocument()
    expect(screen.getByText(/champion promotion remains manual/i)).toBeInTheDocument()
    expect(screen.getAllByText(/launched/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/not selected/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/rejected/i)).not.toBeInTheDocument()
    expect(screen.getByText('Automatic execution detail is incomplete')).toBeInTheDocument()
    expect(screen.getByText('Named detail is available for 1 of 2 selected targets.')).toBeInTheDocument()
    expect(screen.queryByText(/pending approval/i)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Automatic fixture/ }))
    expect(screen.getByText('Automatic launched')).toBeInTheDocument()
    expect(screen.getByText('Not selected automatically')).toBeInTheDocument()
    expect(screen.getByText('Meets the automatic policy.')).toBeInTheDocument()
    expect(screen.getByText('Outside the safety cap.')).toBeInTheDocument()
  })

  it('leads an incomplete automatic run with its decision and grouped next actions', () => {
    render(
      <OptimizationRunStatusPresentation
        presentation={{
          overview: {
            lifecycle_status: 'incomplete',
            inventory_coverage_status: 'complete',
            analysis_coverage_status: 'incomplete',
            execution_mode: 'automatic',
            evidence_ranked_score_count: 1105,
            assessed_score_count: 699,
            diagnosis_selected_count: 4,
            diagnosis_scheduled_count: 1,
            diagnosis_completed_count: 1,
            diagnosis_deferred_count: 3,
            execution_selected_count: 0,
            execution_launched_count: 0,
            execution_rejected_count: 699,
          },
          score_count: 1105,
          scorecard_count: 51,
          primary_disposition_counts: {
            guideline_or_code_repair: 960,
            insufficient_evidence: 82,
            targeted_feedback_collection: 13,
            cooldown: 47,
            not_selected: 3,
          },
          primary_decision_mix: {},
          secondary_issue_counts: { potential_code_conflict: 1 },
          attention_queue: [{
            scorecard_name: 'Example Portfolio',
            score_name: 'Deferred Score',
            primary_disposition: 'not_selected',
            evidence_count: 200,
            severity: 1,
            rationale: 'Semantic diagnosis is required.',
            next_action: 'await_semantic_diagnosis',
          }],
          questions_and_issues: [], optimization_outcomes: [], opportunity_distribution: [], top_priorities: [],
          scorecards: [],
        }}
      />,
    )

    expect(screen.getByRole('heading', { name: 'No automatic optimizations launched' })).toBeInTheDocument()
    expect(screen.getByText(/found work, but did not prove a safe automatic optimization/i)).toBeInTheDocument()
    expect(screen.getAllByText(/complete 3 deferred diagnoses/i).length).toBeGreaterThan(0)
    expect(screen.getByText('Finish analysis')).toBeInTheDocument()
    expect(screen.getByText('Repair score definitions')).toBeInTheDocument()
    expect(screen.queryByText(/699 not selected/i)).not.toBeInTheDocument()
  })

  it('does not announce a zero-launch decision before diagnosis evidence exists', () => {
    render(
      <OptimizationRunStatusPresentation
        presentation={{
          overview: {
            lifecycle_status: 'running',
            execution_mode: 'automatic',
            execution_selected_count: 0,
            execution_launched_count: 0,
          },
          score_count: 0, scorecard_count: 0,
          primary_disposition_counts: {}, primary_decision_mix: {}, secondary_issue_counts: {},
          attention_queue: [], questions_and_issues: [], optimization_outcomes: [],
          opportunity_distribution: [], top_priorities: [], scorecards: [],
        }}
      />,
    )

    expect(screen.queryByRole('heading', { name: 'No automatic optimizations launched' })).not.toBeInTheDocument()
  })

  it('shows the full opportunity-survey funnel without implying that completion means improvement', () => {
    render(
      <OptimizationRunStatusPresentation
        presentation={{
          overview: {
            lifecycle_status: 'complete',
            execution_mode: 'automatic',
            evidence_ranked_score_count: 1105,
            assessed_score_count: 696,
            diagnosis_completed_count: 1,
            execution_selected_count: 0,
            execution_launched_count: 0,
            optimizer_review_count: 0,
          },
          score_count: 1105,
          scorecard_count: 56,
          primary_disposition_counts: { guideline_or_code_repair: 958 },
          primary_decision_mix: {}, secondary_issue_counts: {}, attention_queue: [],
          questions_and_issues: [], optimization_outcomes: [], opportunity_distribution: [], top_priorities: [],
          scorecards: [],
        }}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Optimization opportunity survey' })).toBeInTheDocument()
    expect(screen.getByLabelText('Optimization execution funnel')).toHaveTextContent(
      '1105Surveyed696Assessed1Diagnosed0Selected0Launched0Evaluated0Improved',
    )
    expect(screen.getByText('No score optimizer launched')).toBeInTheDocument()
    expect(screen.getByText(/completed survey does not mean that a score was optimized/i)).toBeInTheDocument()
  })

  it('shows launched, evaluated, and safely improved scores as distinct funnel stages', () => {
    render(
      <OptimizationRunStatusPresentation
        presentation={{
          overview: {
            lifecycle_status: 'complete',
            execution_mode: 'automatic',
            evidence_ranked_score_count: 40,
            assessed_score_count: 12,
            diagnosis_completed_count: 5,
            execution_selected_count: 3,
            execution_launched_count: 2,
            optimizer_review_count: 2,
          },
          score_count: 40,
          scorecard_count: 4,
          primary_disposition_counts: { promotion_ready: 1, no_safe_improvement: 1 },
          primary_decision_mix: {}, secondary_issue_counts: {}, attention_queue: [],
          questions_and_issues: [], optimization_outcomes: [], opportunity_distribution: [], top_priorities: [],
          scorecards: [],
        }}
      />,
    )

    expect(screen.getByLabelText('Optimization execution funnel')).toHaveTextContent(
      '40Surveyed12Assessed5Diagnosed3Selected2Launched2Evaluated1Improved',
    )
    expect(screen.getByText('1 validated safe improvement')).toBeInTheDocument()
  })

  it('keeps the human optimization-approval checkpoint visible for approval-required runs', () => {
    render(
      <OptimizationRunStatusPresentation
        presentation={{
          overview: { lifecycle_status: 'running', execution_mode: 'approval_required', pending_approval_count: 1 },
          score_count: 0, scorecard_count: 0, primary_decision_mix: {}, secondary_issue_counts: {},
          attention_queue: [], questions_and_issues: [], optimization_outcomes: [],
          opportunity_distribution: [], top_priorities: [], scorecards: [],
        }}
      />,
    )

    expect(screen.getByText('Human optimization approval')).toBeInTheDocument()
    expect(screen.getByText(/human optimization-approval checkpoint/i)).toBeInTheDocument()
    expect(screen.getByText(/champion promotion remains manual/i)).toBeInTheDocument()
    expect(screen.queryByText('Automatic execution')).not.toBeInTheDocument()
  })

  it('leads with the backend conclusion and groups four open workstreams by next action', () => {
    render(
      <OptimizationRunStatusPresentation
        presentation={{
          overview: { lifecycle_status: 'complete' },
          decision_summary: {
            state: 'repair_required',
            headline: 'Repair score definitions before optimization',
            explanation: 'The evidence found repair work but no target that is safe to optimize automatically.',
            next_action: 'repair_score_definition',
          },
          action_counts: {
            repair_score_definition: 8,
            collect_targeted_feedback: 4,
            monitor_recent_activity: 2,
            resolve_stakeholder_question: 1,
          },
          action_workstreams: [
            { id: 'repair', next_action: 'repair_score_definition', score_count: 8, rationale: 'Resolve guideline and code conflicts.' },
            { id: 'feedback', next_action: 'collect_targeted_feedback', score_count: 4, rationale: 'Collect the missing terminal classes.' },
            { id: 'monitor', queue_state: 'monitor', next_action: 'monitor_recent_activity', score_count: 2, rationale: 'Wait for the activity cooldown.' },
            { id: 'question', next_action: 'resolve_stakeholder_question', score_count: 1, rationale: 'Clarify the policy boundary.' },
          ],
          score_count: 15,
          scorecard_count: 3,
          primary_decision_mix: {}, secondary_issue_counts: {}, attention_queue: [],
          questions_and_issues: [], optimization_outcomes: [], opportunity_distribution: [], top_priorities: [], scorecards: [],
        }}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Repair score definitions before optimization' })).toBeInTheDocument()
    expect(screen.getByText(/no target that is safe to optimize automatically/i)).toBeInTheDocument()
    expect(screen.getAllByTestId('optimization-action-card')).toHaveLength(4)
    expect(screen.getAllByText('Repairs and evidence').length).toBeGreaterThan(0)
    expect(screen.getByText('Resolve guideline and code conflicts.')).toBeInTheDocument()
  })

  it('surfaces a run failure above the last durable pre-failure presentation', async () => {
    mockReadTaskArtifact.mockReset().mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
      overview: { lifecycle_status: 'running', analysis_coverage_status: 'complete' },
      decision_summary: {
        state: 'analysis_pending', headline: 'No optimization decision yet',
        explanation: 'The execution policy is still being evaluated.', next_action: 'Continue.',
      },
      action_counts: { automatic_work: 0, human_decisions: 0, repairs_and_evidence: 1, monitor_later: 0, no_action: 0 },
      action_workstreams: [], score_count: 1, scorecard_count: 1,
      primary_disposition_counts: { guideline_or_code_repair: 1 }, primary_decision_mix: {},
      secondary_issue_counts: {}, attention_queue: [], questions_and_issues: [],
      optimization_outcomes: [], opportunity_distribution: [], top_priorities: [], scorecards: [],
    }))))

    render(<OptimizationRunStatus id="block-1" type="OptimizationRunStatus" name="Run Status" position={0} config={{}}
      output={{ output_compacted: true, preview: { summary: {
        milestone: 'diagnosis', presentation: presentationDescriptor,
        run_failure: {
          state: 'failure', headline: 'The optimization run could not complete',
          explanation: 'Core milestone publication failed.',
        },
      } } }} />)

    expect(await screen.findByRole('heading', { name: 'The optimization run could not complete' })).toBeInTheDocument()
    expect(screen.getByText('Core milestone publication failed.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'No optimization decision yet' })).not.toBeInTheDocument()
  })

  it('defaults to open work and lets operators inspect monitor and history queues', async () => {
    const user = userEvent.setup()
    mockReadTaskArtifact.mockReset().mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
      overview: { lifecycle_status: 'complete' },
      decision_summary: {
        state: 'repair_required',
        headline: 'Resolve the current definition repairs',
        explanation: 'The report is ready for repair work, not optimizer launch.',
        next_action: 'repair_score_definition',
      },
      action_counts: {
        automatic_work: 0, human_decisions: 1, repairs_and_evidence: 3, monitor_later: 2, no_action: 9,
      },
      action_workstreams: [
        {
          id: 'open-repair', action_group: 'repairs_and_evidence', title: 'Definition repair', owner_role: 'score_author',
          queue_state: 'open', score_count: 3, scorecard_count: 1, evidence_count: 27,
          next_action: 'repair_score_definition', dominant_issue: 'guideline_or_code_repair',
          rationale: 'Repair the conflicting definition.', consequence_of_inaction: 'The portfolio remains blocked.',
          representative_rows: [{
            scorecard_name: 'Representative portfolio', score_name: 'Representative score',
            primary_disposition: 'guideline_or_code_repair', evidence_count: 27,
            rationale: 'The score needs the definition repaired.', next_action: 'repair_score_definition',
          }],
        },
        {
          id: 'monitor-later', action_group: 'monitor_later', title: 'Cooldown monitor', owner_role: 'operator',
          queue_state: 'monitor', score_count: 2, scorecard_count: 1, evidence_count: 18,
          next_action: 'wait_for_cooldown', dominant_issue: 'recent_score_activity',
          rationale: 'Wait for recent score activity to age out.', consequence_of_inaction: 'The cooldown remains active.', representative_rows: [],
        },
        {
          id: 'old-history', action_group: 'no_action', title: 'Completed history', owner_role: 'operator',
          queue_state: 'history', score_count: 9, scorecard_count: 2, evidence_count: 0,
          next_action: 'none', dominant_issue: 'none', rationale: 'Already resolved.', consequence_of_inaction: 'None.', representative_rows: [],
        },
      ],
      score_count: 12, scorecard_count: 2,
      primary_disposition_counts: { guideline_or_code_repair: 3 }, primary_decision_mix: {}, secondary_issue_counts: {},
      attention_queue: [{
        scorecard_name: 'Representative portfolio', score_name: 'Legacy attention row',
        primary_disposition: 'guideline_or_code_repair', evidence_count: 27,
        rationale: 'This must not duplicate the backend workstream queue.', next_action: 'repair_score_definition',
      }],
      questions_and_issues: [], optimization_outcomes: [{
        scorecard_name: 'Representative portfolio', score_name: 'Not-run score',
        primary_disposition: 'not_selected', outcome: 'not_run', rationale: 'No execution evidence exists.',
      }], opportunity_distribution: [], top_priorities: [],
      scorecards: [{
        scorecard_ref: 'detail-revision', scorecard_name: 'Detail revision fixture', score_count: 1,
        detail_status: 'ready', detail_source_revision: 4, reviewed_error_opportunity: 0, artifacts: [],
      }],
    }))))

    render(<OptimizationRunStatus id="block-1" type="OptimizationRunStatus" name="Run Status" position={0} config={{}}
      output={{ output_compacted: true, preview: { summary: { presentation: presentationDescriptor } } }} />)

    expect(await screen.findByRole('heading', { name: 'Resolve the current definition repairs' })).toBeInTheDocument()
    expect(screen.getAllByTestId('optimization-action-card')).toHaveLength(4)
    expect(screen.getByText('Definition repair')).toBeInTheDocument()
    expect(screen.queryByText('Completed history')).not.toBeInTheDocument()
    expect(screen.queryByText('Cooldown monitor')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Human attention queue' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Optimization progress and outcomes' })).not.toBeInTheDocument()
    expect(screen.getByTestId('lifecycle-review-pending').closest('details')).toBeInTheDocument()
    expect(screen.getByText('Definition repair').closest('details')).not.toHaveAttribute('open')

    await user.click(screen.getByText('Definition repair'))
    expect(screen.getByText('Definition repair').closest('details')).toHaveAttribute('open')
    expect(screen.getByText((_, element) => element?.textContent === 'Owner: Score author')).toBeInTheDocument()
    expect(screen.getByText('The portfolio remains blocked.')).toBeInTheDocument()
    expect(screen.getByText('Representative score')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Monitor (1)' }))
    expect(screen.getByText('Cooldown monitor')).toBeInTheDocument()
    expect(screen.queryByText('Definition repair')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'History (1)' }))
    expect(screen.getByText('Completed history')).toBeInTheDocument()
    expect(screen.queryByText('Cooldown monitor')).not.toBeInTheDocument()
  })
})
