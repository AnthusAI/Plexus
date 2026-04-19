import React from 'react'
import { render, screen } from '@testing-library/react'

import AcceptanceRate from '../AcceptanceRate'

describe('AcceptanceRate block', () => {
  const baseProps = {
    config: {},
    name: 'Acceptance Rate',
    position: 0,
    type: 'AcceptanceRate',
    id: 'rb-acceptance-rate',
  }

  it('renders hidden-row controls without outline styling', () => {
    const items = Array.from({ length: 201 }, (_, index) => ({
      item_id: `item-${index}`,
      item_accepted: true,
      total_score_results: 1,
      accepted_score_results: 1,
      corrected_score_results: 0,
      score_result_acceptance_rate: 1,
    }))

    render(
      <AcceptanceRate
        {...baseProps}
        output={{
          items,
          summary: {
            total_items: 201,
            accepted_items: 201,
            corrected_items: 0,
            item_acceptance_rate: 1,
            total_score_results: 201,
            accepted_score_results: 201,
            corrected_score_results: 0,
            score_result_acceptance_rate: 1,
            feedback_items_total: 0,
            feedback_items_valid: 0,
            feedback_items_changed: 0,
            score_results_with_feedback: 0,
          },
        }}
      />
    )

    const hiddenRowsNote = screen.getByText('Item rows are hidden by default for large results.')
    expect(hiddenRowsNote.closest('div')?.className).not.toContain('border')

    const showRowsButton = screen.getByRole('button', { name: /show item rows/i })
    expect(showRowsButton.className).not.toContain('border')
    expect(showRowsButton.className).toContain('text-primary')
  })
})
