import React from 'react'
import { render, screen } from '@testing-library/react'
import { TaskDisplay } from '@/components/TaskDisplay'
import userEvent from '@testing-library/user-event'

const baseEval = {
  id: 'e1',
  type: 'Accuracy',
  createdAt: new Date().toISOString(),
  scorecard: { name: 'SC' },
  score: { name: 'Score' },
  status: 'RUNNING',
  processedItems: 0,
  totalItems: 4,
} as any

const makeTask = (stages?: any) => ({
  id: 't1',
  type: 'evaluation',
  status: 'RUNNING',
  stages,
}) as any

describe('TaskDisplay', () => {
  test('normalizes DONE→COMPLETED but respects last stage completion for Complete indicator', () => {
    const stages = { items: [
      { id:'s1', name:'Setup', order:1, status:'COMPLETED' },
      { id:'s2', name:'Processing', order:2, status:'RUNNING' },
      { id:'s3', name:'Finalizing', order:3, status:'PENDING' },
    ]}

    const { container, rerender } = render(
      <TaskDisplay
        variant="grid"
        task={makeTask(stages)}
        evaluationData={{ ...baseEval, status: 'DONE' }}
      />
    )

    const list = container.querySelector('[role="list"]') as HTMLElement
    const items = list.querySelectorAll('[role="listitem"]')
    const complete = items[items.length - 1]
    expect(complete.className).toContain('bg-neutral')

    const stages2 = { items: [
      { id:'s1', name:'Setup', order:1, status:'COMPLETED' },
      { id:'s2', name:'Processing', order:2, status:'COMPLETED' },
      { id:'s3', name:'Finalizing', order:3, status:'COMPLETED' },
    ]}

    rerender(
      <TaskDisplay
        variant="grid"
        task={makeTask(stages2)}
        evaluationData={{ ...baseEval, status: 'DONE' }}
      />
    )

    const list2 = container.querySelector('[role="list"]') as HTMLElement
    const items2 = list2.querySelectorAll('[role="listitem"]')
    const complete2 = items2[items2.length - 1]
    expect(complete2.className).toContain('bg-true')
  })

  test('stage-source fallback: stages persist if later update omits them', () => {
    const stages = { items: [
      { id:'s1', name:'Setup', order:1, status:'COMPLETED' },
      { id:'s2', name:'Processing', order:2, status:'RUNNING' },
    ]}

    const { rerender } = render(
      <TaskDisplay
        variant="grid"
        task={makeTask(stages)}
        evaluationData={{ ...baseEval }}
      />
    )

    rerender(
      <TaskDisplay
        variant="grid"
        task={makeTask(undefined)}
        evaluationData={{ ...baseEval }}
      />
    )

    expect(screen.getByText('Setup')).toBeInTheDocument()
    expect(screen.getByText('Processing')).toBeInTheDocument()
  })

  test('no premature completion when counts equal but last stage not completed', () => {
    const stages = { items: [
      { id:'s1', name:'Setup', order:1, status:'COMPLETED' },
      { id:'s2', name:'Processing', order:2, status:'RUNNING' },
      { id:'s3', name:'Finalizing', order:3, status:'PENDING' },
    ]}

    const { container } = render(
      <TaskDisplay
        variant="grid"
        task={makeTask(stages)}
        evaluationData={{ ...baseEval, processedItems: 4, totalItems: 4 }}
      />
    )

    const list = container.querySelector('[role="list"]') as HTMLElement
    const items = list.querySelectorAll('[role="listitem"]')
    const complete = items[items.length - 1]
    // In selected/detail contexts, neutral background may be themed; accept either neutral or progress background
    expect(complete.className).toMatch(/bg-neutral|bg-progress-background/)
  })

  test('score results loading skeleton appears when scoreResults=null and hides when array arrives', async () => {
    const user = userEvent.setup()
    const evalLoading = { ...baseEval, scoreResults: null } as any

    const { rerender } = render(
      <TaskDisplay
        variant="detail"
        task={makeTask({ items: [] })}
        evaluationData={evalLoading}
      />
    )

    // Loading skeletons should render
    // Look for multiple skeleton rows by their pulse class container
    const skeletons = document.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)

    const resultsHeader = screen.getByText('Score Results')
    expect(resultsHeader).toBeInTheDocument()

    // Now provide results
    const results = [
      { id: 'r1', value: 'yes', confidence: 0.9, metadata: { correct: true, human_label: 'yes' } },
      { id: 'r2', value: 'no', confidence: 0.2, metadata: { correct: false, human_label: 'no' } },
    ]

    rerender(
      <TaskDisplay
        variant="detail"
        task={makeTask({ items: [] })}
        evaluationData={{ ...baseEval, scoreResults: results } as any}
      />
    )

    // Skeletons should disappear, and two results should render
    const afterSkeletons = document.querySelectorAll('.animate-pulse')
    expect(afterSkeletons.length).toBe(0)
    // ScoreResultComponent renders result values; assert presence via text
    expect(screen.getByText('yes')).toBeInTheDocument()
    expect(screen.getByText('no')).toBeInTheDocument()
  })

  test('result list updates when scoreResults reference changes', () => {
    const first = [{ id: 'r1', value: 'yes', metadata: { correct: true, human_label: 'yes' } }]
    const second = [
      { id: 'r1', value: 'yes', metadata: { correct: true, human_label: 'yes' } },
      { id: 'r2', value: 'no', metadata: { correct: false, human_label: 'no' } },
    ]

    const { rerender } = render(
      <TaskDisplay
        variant="detail"
        task={makeTask({ items: [] })}
        evaluationData={{ ...baseEval, scoreResults: first } as any}
      />
    )

    expect(screen.getByText('yes')).toBeInTheDocument()
    expect(screen.queryByText('no')).toBeNull()

    rerender(
      <TaskDisplay
        variant="detail"
        task={makeTask({ items: [] })}
        evaluationData={{ ...baseEval, scoreResults: second } as any}
      />
    )

    expect(screen.getByText('yes')).toBeInTheDocument()
    expect(screen.getByText('no')).toBeInTheDocument()
  })
})
