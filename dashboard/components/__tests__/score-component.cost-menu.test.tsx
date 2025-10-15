import React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ScoreComponent } from '../ui/score-component'
jest.mock('../../app/contexts/AccountContext', () => ({
  useAccount: () => ({ selectedAccount: { id: 'A1' } })
}))

describe('ScoreComponent cost menu', () => {
  const baseScore = {
    id: 's1',
    name: 'My Score',
    description: '',
    type: 'Classifier',
    order: 1,
  }

  it('shows Analyze Cost when onCostAnalysis is provided', async () => {
    const user = userEvent.setup()
    const onCostAnalysis = jest.fn()
    render(
      <ScoreComponent
        score={baseScore as any}
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


