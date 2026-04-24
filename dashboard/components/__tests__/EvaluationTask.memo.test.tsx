import React from 'react'
import { render, screen } from '@testing-library/react'
import EvaluationTask from '@/components/EvaluationTask'

jest.mock('@/utils/amplify-client', () => ({
  getClient: jest.fn(() => ({
    graphql: jest.fn(() => new Promise(() => {})),
  })),
}))

const makeData = (overrides: Partial<any> = {}) => ({
  id: 'e1',
  title: 'Eval',
  accuracy: 0,
  metrics: [],
  processedItems: 0,
  totalItems: 4,
  progress: 0,
  inferences: 0,
  cost: 0,
  status: 'RUNNING',
  elapsedSeconds: 0,
  estimatedRemainingSeconds: 0,
  scoreResults: [],
  task: {
    status: 'RUNNING',
    stages: {
      items: [
        { id:'s1', name:'Setup', order:1, status:'COMPLETED' },
        { id:'s2', name:'Processing', order:2, status:'RUNNING', processedItems: 0, totalItems: 4 },
      ]
    }
  },
  ...overrides
})

const makeTaskProps = (data: any) => ({
  id: 't1', type: 'Accuracy Evaluation', time: new Date().toISOString(), data,
})

describe('EvaluationTask memo behavior', () => {
  test('GridContent re-renders when processedItems changes', () => {
    const data = makeData()
    const { rerender } = render(
      <EvaluationTask
        variant="grid"
        task={{ id:'id', type:'Accuracy Evaluation', scorecard:'', score:'', time:new Date().toISOString(), data }}
      />
    )

    // Update processedItems → 1
    const data2 = makeData({ processedItems: 1 })
    rerender(
      <EvaluationTask
        variant="grid"
        task={{ id:'id', type:'Accuracy Evaluation', scorecard:'', score:'', time:new Date().toISOString(), data: data2 }}
      />
    )

    // Verify progress text appears without being ambiguous
    expect(screen.getByText(/Processing 1 of 4 items/)).toBeInTheDocument()
  })

  test('DetailContent re-renders on stage change', () => {
    const stages = {
      items: [
        { id:'s1', name:'Setup', order:1, status:'COMPLETED' },
        { id:'s2', name:'Processing', order:2, status:'RUNNING', processedItems: 2, totalItems: 4 },
      ]
    }
    const data = makeData({ task: { status:'RUNNING', stages } })
    const { rerender } = render(
      <EvaluationTask
        variant="detail"
        task={{ id:'id', type:'Accuracy Evaluation', scorecard:'', score:'', time:new Date().toISOString(), data }}
      />
    )

    // Flip second stage to COMPLETED
    const stages2 = {
      items: [
        { id:'s1', name:'Setup', order:1, status:'COMPLETED' },
        { id:'s2', name:'Processing', order:2, status:'COMPLETED', processedItems: 4, totalItems: 4 },
      ]
    }
    const data2 = makeData({ task: { status:'RUNNING', stages: stages2 } })
    rerender(
      <EvaluationTask
        variant="detail"
        task={{ id:'id', type:'Accuracy Evaluation', scorecard:'', score:'', time:new Date().toISOString(), data: data2 }}
      />
    )

    // Ensure segments show three completed stages
    const listItems = screen.getAllByRole('listitem')
    expect(listItems).toHaveLength(3)
  })

  test('DetailContent renders candidate assessment compact summary KPIs', () => {
    const data = makeData({
      status: 'COMPLETED',
      baseline_evaluation_id: 'eval-original-base',
      current_baseline_evaluation_id: 'eval-current-best',
      task: {
        status: 'COMPLETED',
        stages: {
          items: [
            { id:'s1', name:'Setup', order:1, status:'COMPLETED' },
            { id:'s2', name:'Processing', order:2, status:'COMPLETED', processedItems: 4, totalItems: 4 },
          ]
        },
        metadata: {
          candidate_assessment_compact_summary: {
            schema_version: 'candidate_assessment_bundle.v1',
            decision: 'accept',
            decision_reason: 'meets_reference_and_generalization_policy',
            decision_confidence: 'high',
            primary_next_action: 'score_configuration_optimization',
            baseline_generalization_gap: 0.055,
            candidate_generalization_gap: 0.085,
            generalization_gap_delta: 0.03,
            random_delta_mean: -0.01,
            random_delta_stddev: 0.02,
            attachment_key: 'candidate-assessments/task-1/base__vs__cand.json',
            stage_references: [
              {
                stage_key: 'deterministic_reference',
                baseline_evaluation_id: 'eval-base',
                candidate_evaluation_id: 'eval-cand',
                baseline_status: 'COMPLETED',
                candidate_status: 'COMPLETED',
                delta_ac1: 0.02,
                delta_value_score: 0.015,
              },
            ],
          },
        },
      },
    })

    render(
      <EvaluationTask
        variant="detail"
        task={{ id:'id', type:'Accuracy Evaluation', scorecard:'', score:'', time:new Date().toISOString(), data }}
      />
    )

    expect(screen.getByText('Candidate assessment')).toBeInTheDocument()
    expect(screen.getByText('Accept')).toBeInTheDocument()
    expect(screen.getByText(/Deterministic reference/)).toBeInTheDocument()
    expect(screen.getByText(/Original baseline:\s*eval-base/i)).toBeInTheDocument()
    expect(screen.getByText(/Current best baseline:\s*eval-current-best/i)).toBeInTheDocument()
    expect(screen.getByText(/Gap delta:\s*\+0.030/)).toBeInTheDocument()
    expect(screen.getByText(/Bundle attachment key:/)).toBeInTheDocument()
  })

  test('DetailContent renders original and current best baseline references', () => {
    const data = makeData({
      status: 'COMPLETED',
      baseline_evaluation_id: 'eval-original',
      current_baseline_evaluation_id: 'eval-current',
      task: {
        status: 'COMPLETED',
        stages: {
          items: [
            { id:'s1', name:'Setup', order:1, status:'COMPLETED' },
            { id:'s2', name:'Processing', order:2, status:'COMPLETED', processedItems: 4, totalItems: 4 },
          ]
        },
      },
    })

    render(
      <EvaluationTask
        variant="detail"
        task={{ id:'id', type:'Accuracy Evaluation', scorecard:'', score:'', time:new Date().toISOString(), data }}
      />
    )

    expect(screen.getByText('Original baseline:')).toBeInTheDocument()
    expect(screen.getByText('eval-original')).toBeInTheDocument()
    expect(screen.getByText('Current best baseline:')).toBeInTheDocument()
    expect(screen.getByText('eval-current')).toBeInTheDocument()
  })
})
