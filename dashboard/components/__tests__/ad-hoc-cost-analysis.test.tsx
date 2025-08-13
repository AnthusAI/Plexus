import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { AdHocCostAnalysis } from '../ui/ad-hoc-cost-analysis'

jest.mock('../../utils/cost-analysis', () => ({
  fetchCostAnalysisScoreResults: jest.fn().mockResolvedValue({
    items: [
      { id: '1', scoreId: 'S1', score: { id: 'S1', name: 'Score One' }, cost: { total_cost: 0.01 } },
      { id: '2', scoreId: 'S2', score: { id: 'S2', name: 'Score Two' }, cost: { total_cost: 0.02 } },
    ],
    window: { startTime: '2025-01-01T00:00:00Z', endTime: '2025-01-02T00:00:00Z' }
  }),
  aggregateCostByScore: (items: any[]) => {
    return {
      summary: {
        count: items.length,
        total_cost: items.reduce((s, r) => s + (r.cost?.total_cost ?? 0), 0),
        average_cost: items.reduce((s, r) => s + (r.cost?.total_cost ?? 0), 0) / items.length,
        average_calls: 0,
      },
      groups: [
        { group: { scoreId: 'S1', scoreName: 'Score One' }, count: 1, total_cost: 0.01, average_cost: 0.01, average_calls: 0 },
        { group: { scoreId: 'S2', scoreName: 'Score Two' }, count: 1, total_cost: 0.02, average_cost: 0.02, average_calls: 0 },
      ],
      itemAnalysis: {
        count: 2,
        total_cost: 0.03,
        average_cost: 0.015,
        average_calls: 0,
      },
    }
  }
}))

jest.mock('../../app/contexts/AccountContext', () => ({
  useAccount: () => ({ selectedAccount: { id: 'A1' } })
}))

describe('AdHocCostAnalysis', () => {
  it('renders per-score rows using score names', async () => {
    render(<AdHocCostAnalysis scorecardId="SC1" />)
    await waitFor(() => {
      expect(screen.getByText('Score One')).toBeInTheDocument()
      expect(screen.getByText('Score Two')).toBeInTheDocument()
    })
  })

  it('uses 200 limit by default', async () => {
    const { fetchCostAnalysisScoreResults } = require('../../utils/cost-analysis')
    render(<AdHocCostAnalysis scoreId="S1" />)
    await waitFor(() => expect(fetchCostAnalysisScoreResults).toHaveBeenCalled())
    expect(fetchCostAnalysisScoreResults).toHaveBeenCalledWith(expect.objectContaining({ limit: 200 }))
  })

  it('uses 200 limit for scorecard view', async () => {
    const { fetchCostAnalysisScoreResults } = require('../../utils/cost-analysis')
    render(<AdHocCostAnalysis scorecardId="SC1" />)
    await waitFor(() => expect(fetchCostAnalysisScoreResults).toHaveBeenCalled())
    expect(fetchCostAnalysisScoreResults).toHaveBeenCalledWith(expect.objectContaining({ limit: 200 }))
  })
})


