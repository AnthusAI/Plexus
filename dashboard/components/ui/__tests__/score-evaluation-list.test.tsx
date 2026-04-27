import React from 'react'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ScoreEvaluationList } from '../score-evaluation-list'

const mockGraphql = jest.fn()
const subscriptionHandlers: Record<string, Array<(payload: any) => void>> = {}

function subscriptionResult(key: string) {
  return {
    subscribe: ({ next }: { next: (payload: any) => void }) => {
      subscriptionHandlers[key] = subscriptionHandlers[key] ?? []
      subscriptionHandlers[key].push(next)
      return { unsubscribe: jest.fn() }
    },
  }
}

function emitSubscription(key: string, data: any) {
  for (const handler of subscriptionHandlers[key] ?? []) {
    handler({ data })
  }
}

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
      <div data-testid={`status-${task.id}`}>{task?.data?.task?.status ?? ''}</div>
      <div data-testid={`stages-${task.id}`}>
        {(task?.data?.task?.stages?.items ?? []).map((stage: any) => `${stage.name}:${stage.status}`).join('|')}
      </div>
      {controlButtons}
    </div>
  ),
}))

describe('ScoreEvaluationList', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    for (const key of Object.keys(subscriptionHandlers)) delete subscriptionHandlers[key]

    mockGraphql.mockImplementation(({ query }: { query: string }) => {
      const text = String(query)
      if (text.includes('onCreateEvaluation')) return subscriptionResult('createEvaluation')
      if (text.includes('onUpdateEvaluation')) return subscriptionResult('updateEvaluation')
      if (text.includes('onDeleteEvaluation')) return subscriptionResult('deleteEvaluation')
      if (text.includes('onUpdateTaskStage')) return subscriptionResult('updateTaskStage')
      if (text.includes('onUpdateTask')) return subscriptionResult('updateTask')

      return Promise.resolve({
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
              taskId: 'task-eval-1',
              task: {
                id: 'task-eval-1',
                status: 'COMPLETED',
                stages: { items: [] },
              },
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
    expect(screen.getByLabelText('Loading evaluations')).toBeInTheDocument()
    await waitFor(() => {
      expect(idsInOrder()).toEqual(['eval-2', 'eval-1', 'eval-3'])
    })

    await user.selectOptions(sortSelect, 'recall')
    await waitFor(() => {
      expect(idsInOrder()).toEqual(['eval-3', 'eval-1', 'eval-2'])
    })

    await user.selectOptions(sortSelect, 'cost')
    await waitFor(() => {
      expect(idsInOrder()).toEqual(['eval-2', 'eval-1', 'eval-3'])
    })
  })

  it('inserts matching realtime evaluations and ignores other scores', async () => {
    render(<ScoreEvaluationList scoreId="score-1" scope="score" />)

    await waitFor(() => {
      expect(screen.getByText('eval-1')).toBeInTheDocument()
    })

    act(() => {
      emitSubscription('createEvaluation', {
        onCreateEvaluation: {
          id: 'eval-other-score',
          type: 'feedback',
          status: 'COMPLETED',
          scoreId: 'score-other',
          scoreVersionId: 'version-x',
          createdAt: '2026-04-26T00:00:00Z',
          updatedAt: '2026-04-26T00:00:00Z',
          metrics: JSON.stringify({ alignment: 0.99 }),
        },
      })
      emitSubscription('createEvaluation', {
        onCreateEvaluation: {
          id: 'eval-live',
          type: 'feedback',
          status: 'RUNNING',
          scoreId: 'score-1',
          scoreVersionId: 'version-live',
          createdAt: '2026-04-26T00:00:00Z',
          updatedAt: '2026-04-26T00:00:00Z',
          metrics: JSON.stringify({ alignment: 0.65 }),
        },
      })
    })

    await waitFor(() => {
      expect(screen.getByText('eval-live')).toBeInTheDocument()
    })
    expect(screen.queryByText('eval-other-score')).not.toBeInTheDocument()
  })

  it('updates visible evaluation task and stage data from realtime task subscriptions', async () => {
    render(<ScoreEvaluationList scoreId="score-1" scope="score" />)

    await waitFor(() => {
      expect(screen.getByText('eval-1')).toBeInTheDocument()
    })

    act(() => {
      emitSubscription('updateTask', {
        onUpdateTask: {
          id: 'task-eval-1',
          status: 'RUNNING',
          target: 'evaluation/feedback/test',
          stages: { items: [] },
        },
      })
      emitSubscription('updateTaskStage', {
        onUpdateTaskStage: {
          id: 'stage-live',
          taskId: 'task-eval-1',
          name: 'Score items',
          order: 2,
          status: 'RUNNING',
        },
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('status-eval-1')).toHaveTextContent('RUNNING')
    })
    expect(screen.getByTestId('stages-eval-1')).toHaveTextContent('Score items:RUNNING')
  })
})
