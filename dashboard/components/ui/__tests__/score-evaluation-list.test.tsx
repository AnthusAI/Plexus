import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'

import { ScoreEvaluationList } from '../score-evaluation-list'

const mockGraphql = jest.fn()

jest.mock('aws-amplify/api', () => ({
  generateClient: () => ({
    graphql: mockGraphql,
  }),
}))

jest.mock('@/components/EvaluationTask', () => ({
  __esModule: true,
  default: ({ task, controlButtons }: any) => (
    <div>
      <div>{task.id}</div>
      <div>{task.description}</div>
      <div data-testid={`notes-${task.id}`}>{task?.data?.parameters ?? ''}</div>
      {controlButtons}
    </div>
  ),
}))

describe('ScoreEvaluationList', () => {
  beforeEach(() => {
    jest.clearAllMocks()

    mockGraphql.mockResolvedValue({
      data: {
        listEvaluationByScoreIdAndUpdatedAt: {
          items: [
            {
              id: 'eval-1',
              type: 'feedback',
              status: 'COMPLETED',
              updatedAt: '2026-04-25T00:00:00Z',
              createdAt: '2026-04-25T00:00:00Z',
              scoreVersionId: 'version-1',
              parameters: JSON.stringify({ notes: 'Evaluation note 1' }),
              accuracy: 92.5,
              metrics: JSON.stringify({ alignment: 0.88 }),
            },
            {
              id: 'eval-2',
              type: 'accuracy',
              status: 'FAILED',
              updatedAt: '2026-04-24T00:00:00Z',
              createdAt: '2026-04-24T00:00:00Z',
              scoreVersionId: 'version-2',
              parameters: JSON.stringify({ notes: 'Evaluation note 2' }),
              accuracy: 75.0,
              metrics: JSON.stringify({ alignment: 0.51 }),
            },
          ],
        },
      },
    })
  })

  it('renders score-scoped evaluations with metrics and actions', async () => {
    render(<ScoreEvaluationList scoreId="score-1" scope="score" />)

    await waitFor(() => {
      expect(screen.getByText('eval-1')).toBeInTheDocument()
    })

    expect(screen.getByText(/Feedback · COMPLETED/i)).toBeInTheDocument()
    expect(screen.getByTestId('notes-eval-1')).toHaveTextContent('Evaluation note 1')
    expect(screen.getAllByRole('link', { name: /^Open$/i })[0]).toHaveAttribute('href', '/lab/evaluations/eval-1')
  })

  it('filters version-scoped evaluations to the selected version', async () => {
    render(<ScoreEvaluationList scoreId="score-1" scope="version" versionId="version-2" />)

    await waitFor(() => {
      expect(screen.getByText('eval-2')).toBeInTheDocument()
    })

    expect(screen.queryByText('eval-1')).not.toBeInTheDocument()
  })
})
