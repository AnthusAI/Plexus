import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

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
              cost: 0.4,
              metrics: JSON.stringify({ alignment: 0.88, precision: 0.72, recall: 0.81 }),
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
              cost: 0.2,
              metrics: JSON.stringify({ alignment: 0.51, precision: 0.91, recall: 0.62 }),
            },
            {
              id: 'eval-3',
              type: 'feedback',
              status: 'COMPLETED',
              updatedAt: '2026-04-23T00:00:00Z',
              createdAt: '2026-04-23T00:00:00Z',
              scoreVersionId: 'version-3',
              parameters: JSON.stringify({ notes: 'Evaluation note 3' }),
              accuracy: 80.0,
              cost: null,
              metrics: JSON.stringify({ alignment: 0.70, recall: 0.93 }),
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

    expect(screen.getAllByText(/Feedback · COMPLETED/i).length).toBeGreaterThan(0)
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

  it('sorts by precision, recall, and cost with missing values after present values', async () => {
    const user = userEvent.setup()
    render(<ScoreEvaluationList scoreId="score-1" scope="score" />)

    await waitFor(() => {
      expect(screen.getByText('eval-1')).toBeInTheDocument()
    })

    const idsInOrder = () => screen.getAllByText(/^eval-[123]$/).map((node) => node.textContent)
    const sortSelect = screen.getByLabelText(/^Sort$/i)

    await user.selectOptions(sortSelect, 'precision')
    expect(idsInOrder()).toEqual(['eval-2', 'eval-1', 'eval-3'])

    await user.selectOptions(sortSelect, 'recall')
    expect(idsInOrder()).toEqual(['eval-3', 'eval-1', 'eval-2'])

    await user.selectOptions(sortSelect, 'cost')
    expect(idsInOrder()).toEqual(['eval-2', 'eval-1', 'eval-3'])
  })
})
