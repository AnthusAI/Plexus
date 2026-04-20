import React from 'react'
import { render, screen } from '@testing-library/react'
import { OptimizerProblemItemsPanel } from '@/components/OptimizerProblemItemsPanel'

describe('OptimizerProblemItemsPanel', () => {
  test('renders pattern pills as borderless, theme-correct pills', () => {
    render(
      <OptimizerProblemItemsPanel
        notableItems={{
          'item-1': {
            first_cycle: 1,
            last_cycle: 3,
            wrong_count: 3,
            correct_count: 0,
            segment: 'FP',
            segment_stable: true,
            feedback_label: 'no',
            model_prediction: 'yes',
            pattern: 'PERSISTENT',
            per_cycle: [
              { cycle: 1, segment: 'FP', rationale: 'test' },
              { cycle: 2, segment: 'FP', rationale: 'test' },
              { cycle: 3, segment: 'FP', rationale: 'test' },
            ],
          },
        }}
      />
    )

    const pill = screen
      .getAllByText('Persistent')
      .find((el) => (el as HTMLElement).className.includes('bg-false')) as HTMLElement | undefined

    expect(pill).toBeDefined()
    expect(pill!.className).toContain('border-0')
    expect(pill!.className).toContain('bg-false')
    expect(pill!.className).toContain('text-primary-foreground')
  })
})
