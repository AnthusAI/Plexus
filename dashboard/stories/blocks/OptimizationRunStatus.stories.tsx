import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { expect, userEvent, within } from '@storybook/test'

import {
  OptimizationRunStatusPresentation,
  type ScorecardDetailsByReference,
  type StakeholderPresentation,
} from '@/components/blocks/OptimizationRunStatus'

const meta = {
  title: 'Reports/Blocks/Optimization Run Status',
  component: OptimizationRunStatusPresentation,
  parameters: { layout: 'fullscreen' },
  decorators: [(Story) => <div className="min-h-screen bg-background p-6"><Story /></div>],
  tags: ['autodocs', 'optimization-run-status-acceptance'],
} satisfies Meta<typeof OptimizationRunStatusPresentation>

export default meta
type Story = StoryObj<typeof meta>

const genericPortfolio = 'Example portfolio'

const presentation = {
  overview: {
    lifecycle_status: 'incomplete',
    inventory_coverage_status: 'complete',
    analysis_coverage_status: 'incomplete',
    scorecards_inspected: 3,
    scorecards_in_scope: 2,
    evidence_ranked_score_count: 12,
    ranked_score_count: 8,
    cooldown_excluded_count: 1,
    assessment_progress: '12 of 12 scores assessed',
    diagnosis_coverage: '6 of 7 scheduled diagnoses completed',
    diagnosis_selected_count: 7,
    diagnosis_scheduled_count: 7,
    diagnosis_incomplete_count: 1,
    diagnosis_deferred_count: 1,
    diagnosis_max_count: 12,
    priority_display_limit: 6,
    priority_displayed_count: 6,
    priority_cutoff_rank: 6,
    priority_cutoff_opportunity: 9,
    ranked_below_priority_cutoff: 2,
    pending_approval_count: 2,
    current_activity: 'The run ended with incomplete analysis and still has stakeholder decisions to resolve.',
    notes: 'One selected review did not complete; the remaining inventory is reconciled.',
    next_checkpoint: 'Retry the incomplete diagnosis with complete evidence before relying on the run.',
  },
  score_count: 12,
  scorecard_count: 2,
  primary_disposition_counts: {
    promotion_ready: 1,
    continue_optimization: 2,
    stakeholder_decision_required: 1,
    no_safe_improvement: 1,
    failed_or_incomplete: 1,
    awaiting_optimizer_review: 1,
    optimization_in_progress: 1,
    optimizer_launching: 1,
    awaiting_optimization_approval: 1,
    cooldown: 1,
    not_selected: 1,
  },
  primary_decision_mix: {},
  secondary_issue_counts: {
    policy_contradiction: 2,
    stakeholder_question: 2,
    incomplete_evidence: 1,
  },
  attention_queue: Array.from({ length: 6 }, (_, index) => ({
    scorecard_name: genericPortfolio,
    score_name: `Attention item ${index + 1}`,
    primary_disposition: index === 0 ? 'stakeholder_decision_required' : 'awaiting_optimization_approval',
    secondary_issue_flags: index === 0 ? ['policy_contradiction'] : ['stakeholder_question'],
    evidence_count: 18 - index,
    severity: index === 0 ? 'critical' : 'high',
    rationale: index === 0
      ? 'A policy rule and the observed feedback point to different next actions.'
      : `A stakeholder decision is needed for item ${index + 1}.`,
    next_action: 'review_with_stakeholder',
  })),
  questions_and_issues: Array.from({ length: 6 }, (_, index) => ({
    scorecard_name: genericPortfolio,
    score_name: `Question item ${index + 1}`,
    issue_flag: index === 0 ? 'policy_contradiction' : 'stakeholder_question',
    issue_severity: index === 0 ? 0 : 1,
    affected_evidence_count: 14 - index,
    finding: index === 0
      ? 'The configured policy and the available evidence require a stakeholder decision.'
      : `Stakeholder clarification is needed for question ${index + 1}.`,
    next_action: 'clarify_policy',
  })),
  optimization_outcomes: [
    {
      scorecard_name: genericPortfolio,
      score_name: 'Promotion candidate',
      primary_disposition: 'promotion_ready',
      evidence_count: 31,
      outcome: 'improved_with_zero_regressions',
      promotion_readiness: 'ready_for_human_approval',
      trend: 'Matched evaluation improved while protected cases stayed stable.',
      rationale: 'The candidate is ready for a separate human promotion decision.',
      next_action: 'request_promotion_approval',
    },
    {
      scorecard_name: genericPortfolio,
      score_name: 'Incomplete candidate',
      primary_disposition: 'failed_or_incomplete',
      evidence_count: 11,
      outcome: 'evaluation_incomplete',
      rationale: 'The evaluation ended before a safe comparison could be completed.',
      next_action: 'retry_with_complete_evidence',
    },
    ...Array.from({ length: 4 }, (_, index) => ({
      scorecard_name: genericPortfolio,
      score_name: `Outcome item ${index + 3}`,
      primary_disposition: 'continue_optimization',
      evidence_count: 10 - index,
      outcome: 'iteration_in_progress',
      rationale: `Evidence review continues for outcome ${index + 3}.`,
      next_action: 'continue_optimization',
    })),
  ],
  opportunity_distribution: [
    {
      evidence_rank: 1,
      opportunity: 31,
      disposition: 'selected_for_review',
      scorecard_name: genericPortfolio,
      score_name: 'Promotion candidate',
      disagreement_rate: 0.24,
      valid_feedback_count: 128,
    },
    {
      evidence_rank: 4,
      opportunity: 14,
      disposition: 'cooldown',
      scorecard_name: genericPortfolio,
      score_name: 'Policy-deferred signal',
      reason: 'Recent score activity',
      eligibility_timestamp: '2026-08-15T00:00:00Z',
      disagreement_rate: 0.15,
      valid_feedback_count: 96,
    },
  ],
  top_priorities: [
    {
      rank: 1,
      evidence_rank: 1,
      candidate_rank: 1,
      scorecard_name: genericPortfolio,
      score_name: 'Promotion candidate',
      opportunity: 31,
      evidence_count: 128,
      readiness: 'promotion_ready',
      policy_disposition: 'eligible',
      policy_reason: 'meets_rank_policy',
      review_disposition: 'complete',
      next_action: 'request_promotion_approval',
    },
    {
      rank: 4,
      evidence_rank: 4,
      candidate_rank: 3,
      scorecard_name: genericPortfolio,
      score_name: 'Policy-deferred signal',
      opportunity: 14,
      evidence_count: 96,
      readiness: 'cooldown',
      policy_disposition: 'cooldown',
      policy_reason: 'recent_score_activity',
      review_disposition: 'blocked',
      eligibility_timestamp: '2026-08-15T00:00:00Z',
      next_action: 'wait_for_cooldown',
      rationale: 'The evidence rank remains visible while policy defers further work.',
    },
  ],
  scorecards: [
    { scorecard_ref: 'group-a', scorecard_name: 'Example group A', score_count: 6, reviewed_error_opportunity: 45, artifacts: [] },
    { scorecard_ref: 'group-b', scorecard_name: 'Example group B', score_count: 6, reviewed_error_opportunity: 29, artifacts: [] },
  ],
} satisfies StakeholderPresentation

const scorecardDetails: ScorecardDetailsByReference = {
  'group-a': {
    scorecard_name: 'Example group A',
    questions_and_issues: [],
    scores: [
      {
        score_name: 'Promotion candidate', primary_disposition: 'promotion_ready',
        valid_feedback_count: 128, reviewed_disagreements: 31,
        outcome: 'improved_with_zero_regressions', promotion_readiness: 'ready_for_human_approval',
        rationale: 'Ready for a separate human promotion decision.', next_action: 'request_promotion_approval',
        artifacts: [],
      },
      {
        score_name: 'Policy-deferred signal', evidence_rank: 4, candidate_rank: 3,
        primary_disposition: 'cooldown', policy_disposition: 'cooldown', policy_reason: 'recent_score_activity',
        review_disposition: 'blocked', eligibility_timestamp: '2026-08-15T00:00:00Z',
        valid_feedback_count: 96, reviewed_disagreements: 14,
        rationale: 'Policy defers the next optimization attempt until the cooldown ends.', next_action: 'wait_for_cooldown',
        artifacts: [],
      },
    ],
  },
  'group-b': {
    scorecard_name: 'Example group B',
    questions_and_issues: [],
    scores: [
      {
        score_name: 'Incomplete candidate', primary_disposition: 'failed_or_incomplete',
        valid_feedback_count: 51, reviewed_disagreements: 11, outcome: 'evaluation_incomplete',
        rationale: 'The comparison is incomplete and must not be promoted.', next_action: 'retry_with_complete_evidence',
        artifacts: [],
      },
    ],
  },
}

export const StakeholderAcceptance: Story = {
  args: { presentation, scorecardDetails },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    await expect(canvas.getByText('Incomplete · Inventory complete · Analysis incomplete')).toBeInTheDocument()
    await expect(canvas.getByRole('heading', { name: 'Why this run is incomplete' })).toBeInTheDocument()
    await expect(canvas.getByText(/1 diagnosis result was incomplete/)).toBeInTheDocument()
    await expect(canvas.getByText((_, element) => (
      element?.tagName.toLowerCase() === 'p'
      && element.textContent === 'Next: Retry the incomplete diagnosis with complete evidence before relying on the run.'
    ))).toBeInTheDocument()
    await expect(canvas.getByTestId('lifecycle-total')).toHaveTextContent('12 of 12 scores')
    await expect(canvas.getByText('Promotion ready: 1')).toBeInTheDocument()
    await expect(canvas.getByText('Failed or incomplete: 1')).toBeInTheDocument()
    await expect(canvas.getByText('Policy: Cooldown · Recent score activity')).toBeInTheDocument()
    await expect(canvas.getByText('Eligible after: 2026-08-15T00:00:00Z')).toBeInTheDocument()

    await userEvent.click(canvas.getByRole('button', { name: 'Show all attention queue entries (6)' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Show all issues (6)' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Show all outcomes (6)' }))
    await expect(canvas.getByText('Attention item 6')).toBeInTheDocument()
    await expect(canvas.getByText('Stakeholder clarification is needed for question 6.')).toBeInTheDocument()
    await expect(canvas.getByText('Evidence review continues for outcome 6.')).toBeInTheDocument()

    await userEvent.click(canvas.getByRole('button', { name: 'Collapse attention queue entries' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Collapse issues' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Collapse outcomes' }))
    await expect(canvas.queryByText('Attention item 6')).not.toBeInTheDocument()
    await expect(canvas.queryByText('Stakeholder clarification is needed for question 6.')).not.toBeInTheDocument()
    await expect(canvas.queryByText('Evidence review continues for outcome 6.')).not.toBeInTheDocument()

    await userEvent.click(canvas.getByRole('button', { name: /Example group A/ }))
    await userEvent.click(canvas.getByRole('button', { name: /Example group B/ }))
    await expect(canvas.getAllByText('Policy-deferred signal')).toHaveLength(2)
    await expect(canvas.getAllByText('Incomplete candidate')).toHaveLength(2)

    const policySummary = canvas.getAllByText('Policy-deferred signal')
      .map(element => element.closest('summary'))
      .find((summary): summary is HTMLElement => summary !== null)
    await expect(policySummary).toBeDefined()
    await userEvent.click(policySummary!)
    const policyDetails = policySummary!.closest('details')
    await expect(policyDetails).not.toBeNull()
    const scoreContext = within(policyDetails!)
    await expect(scoreContext.getByText('Evidence rank #4')).toBeInTheDocument()
    await expect(scoreContext.getByText('Eligible candidate #3')).toBeInTheDocument()
    await expect(scoreContext.getByText('Policy: Cooldown · Recent score activity')).toBeInTheDocument()
    await expect(scoreContext.getByText('Review: Blocked')).toBeInTheDocument()
    await expect(scoreContext.getByText('Eligible after: 2026-08-15T00:00:00Z')).toBeInTheDocument()
  },
}
