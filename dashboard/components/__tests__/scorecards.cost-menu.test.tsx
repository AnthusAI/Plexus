import React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ScorecardComponent from '../scorecards/ScorecardComponent'
jest.mock('../../app/contexts/AccountContext', () => ({
  useAccount: () => ({ selectedAccount: { id: 'A1' } })
}))

describe('ScorecardComponent cost menu', () => {
  const baseScorecard = {
    id: 'sc1',
    name: 'My Scorecard',
    key: 'my-scorecard',
    description: '',
    type: 'scorecard',
    order: 0,
    externalId: 'ext-1',
    sections: { items: [] },
  }

  it('shows Analyze Cost when onCostAnalysis is provided', async () => {
    const user = userEvent.setup()
    const onCostAnalysis = jest.fn()
    render(
      <ScorecardComponent
        score={baseScorecard as any}
        variant="detail"
        onCostAnalysis={onCostAnalysis}
      />
    )

    // Open kebab menu
    const menuButton = screen.getAllByRole('button', { name: /more options/i })[0]
    await user.click(menuButton)

    // Verify Analyze Cost present
    expect(await screen.findByText(/Analyze Cost/i)).toBeInTheDocument()
  })
})


