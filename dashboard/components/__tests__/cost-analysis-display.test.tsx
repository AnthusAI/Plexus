import React from 'react'
import { render, screen } from '@testing-library/react'
import { CostAnalysisDisplay, type CostAnalysisDisplayData } from '../ui/cost-analysis-display'

describe('CostAnalysisDisplay', () => {
  const baseSummary = { count: 2, total_cost: '0.03', average_cost: '0.015', average_calls: 1 }

  it('renders scorecard view with box plot heading only', () => {
    const data: CostAnalysisDisplayData = {
      summary: baseSummary,
      groups: [
        { group: { scoreId: 'S1', scoreName: 'Score One' }, min_cost: 0.01, q1_cost: 0.01, median_cost: 0.015, q3_cost: 0.02, max_cost: 0.02 },
        { group: { scoreId: 'S2', scoreName: 'Score Two' }, min_cost: 0.005, q1_cost: 0.01, median_cost: 0.02, q3_cost: 0.03, max_cost: 0.04 },
      ]
    }
    render(<CostAnalysisDisplay data={data} />)
    expect(screen.getByText('Cost distribution per score')).toBeInTheDocument()
    expect(screen.queryByText('Histogram')).not.toBeInTheDocument()
  })

  it('renders single-score view with Box Plot and Histogram headings', () => {
    const data: CostAnalysisDisplayData = {
      summary: baseSummary,
      groups: [
        { group: { scoreId: 'S1', scoreName: 'Score One' }, min_cost: 0.01, q1_cost: 0.01, median_cost: 0.015, q3_cost: 0.02, max_cost: 0.02, },
      ],
      filters: { scoreId: 'S1' }
    }
    render(<CostAnalysisDisplay data={data} />)
    expect(screen.getByText('Box Plot')).toBeInTheDocument()
    expect(screen.getByText('Histogram')).toBeInTheDocument()
  })
})


