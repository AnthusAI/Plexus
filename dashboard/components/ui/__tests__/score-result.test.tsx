import React from 'react'
import { render, screen } from '@testing-library/react'
import { ScoreResultComponent } from '@/components/ui/score-result'

describe('ScoreResultComponent misclassification triage', () => {
  test('renders misclassification category, confidence, rationale, and evidence', () => {
    render(
      <ScoreResultComponent
        variant="detail"
        result={{
          id: 'sr-1',
          value: 'Yes',
          confidence: 0.88,
          explanation: 'Predicted Yes because guarantee language was present.',
          metadata: {
            human_label: 'No',
            correct: false,
          },
          itemId: 'item-1',
        }}
        misclassificationCategory="information_gap"
        misclassificationConfidence="medium"
        misclassificationRationale="Critical phrase appears to be missing from the transcript."
        misclassificationEvidence={[
          {
            source: 'edit_comment',
            quote_or_fact: 'Reviewer noted missing transcript phrase from audio.',
          },
        ]}
      />
    )

    expect(screen.getByText('Misclassification triage')).toBeInTheDocument()
    expect(screen.getByText('Information gap')).toBeInTheDocument()
    expect(screen.getByText('Confidence: medium')).toBeInTheDocument()
    expect(screen.getByText(/Critical phrase appears to be missing/i)).toBeInTheDocument()
    expect(screen.getByText(/Reviewer noted missing transcript phrase/i)).toBeInTheDocument()
  })
})
