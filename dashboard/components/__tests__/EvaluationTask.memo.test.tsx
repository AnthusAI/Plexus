import React from 'react'
import { render, screen } from '@testing-library/react'
import EvaluationTask from '@/components/EvaluationTask'

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
})
