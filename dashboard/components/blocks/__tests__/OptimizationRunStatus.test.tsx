import React from 'react'
import { TextDecoder } from 'util'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import OptimizationRunStatus from '../OptimizationRunStatus'

Object.assign(global, { TextDecoder })

const mockReadTaskArtifact = jest.fn()

jest.mock('@/lib/artifact-ticket-client', () => ({
  issueTaskArtifactReadTicket: jest.fn(),
}))

jest.mock('@/lib/report-artifacts', () => {
  const actual = jest.requireActual('@/lib/report-artifacts')
  return { ...actual, readTaskArtifact: (...args: unknown[]) => mockReadTaskArtifact(...args) }
})

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
    window.history.replaceState({}, '', '/lab/reports/report-1')
    mockReadTaskArtifact
      .mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
        overview: {
          lifecycle_status: 'running',
          coverage_status: 'complete',
          scorecards_inspected: 4,
          scorecards_in_scope: 1,
          ranked_score_count: 3,
          assessment_progress: '3 of 3 ranked scores complete',
          diagnosis_coverage: '1 of 1 selected diagnoses complete; 0 failed',
          ranking_cutoff: 'none',
          priority_display_limit: 10,
          priority_displayed_count: 1,
          priority_cutoff_rank: 1,
          priority_cutoff_opportunity: 42,
          ranked_below_priority_cutoff: 2,
          diagnosis_top_priority_count: 1,
          diagnosis_monitoring_candidate_count: 0,
          diagnosis_selected_count: 1,
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

  it('shows reconciled aggregate visuals and loads score details only when expanded', async () => {
    const user = userEvent.setup()
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
              milestone: 'diagnosis',
              presentation: presentationDescriptor,
            },
          },
        }}
      />,
    )

    expect(await screen.findByText('3 of 3 ranked scores complete')).toBeInTheDocument()
    expect(screen.getByText('Scorecards inspected')).toBeInTheDocument()
    expect(screen.queryByText('Account inventory inspected')).not.toBeInTheDocument()
    expect(screen.getByText('Scorecards in scope')).toBeInTheDocument()
    expect(screen.getByLabelText('Primary decision mix: 3 scores')).toBeInTheDocument()
    expect(screen.getByText('Optimize: 2')).toBeInTheDocument()
    expect(screen.getByText('Stakeholder clarification: 1')).toBeInTheDocument()
    expect(screen.getByText('Priority Score')).toBeInTheDocument()
    expect(screen.getByText('No ranking cutoff')).toBeInTheDocument()
    expect(screen.getByText(/Top 10 are highlighted/)).toBeInTheDocument()
    expect(screen.getByText(/1 selected for semantic diagnosis/)).toBeInTheDocument()
    expect(screen.getByText(/120 valid feedback/)).toBeInTheDocument()
    expect(screen.getByText('Reviewed errors show a safe opportunity.')).toBeInTheDocument()
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
})
