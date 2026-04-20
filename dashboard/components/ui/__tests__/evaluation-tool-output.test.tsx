import * as React from 'react'
import { render, screen, waitFor } from '@testing-library/react'

import EvaluationToolOutput from '../evaluation-tool-output'

const mockGenerateClient = jest.fn()
const mockTransformEvaluation = jest.fn()

jest.mock('aws-amplify/api', () => ({
  generateClient: (...args: any[]) => mockGenerateClient(...args),
}))

jest.mock('@/utils/data-operations', () => ({
  transformEvaluation: (...args: any[]) => mockTransformEvaluation(...args),
}))

jest.mock('@/components/TaskDisplay', () => ({
  TaskDisplay: ({ extra, evaluationData }: any) => (
    <div
      data-testid="task-display"
      data-extra={String(Boolean(extra))}
      data-score-results={Array.isArray(evaluationData?.scoreResults) ? evaluationData.scoreResults.length : -1}
    >
      Task
    </div>
  ),
}))

describe('EvaluationToolOutput progressive rendering', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  test('renders quickly from light payload, then hydrates score results, and always enables extra', async () => {
    let resolveScores: ((value: any) => void) | null = null

    const graphql = jest.fn(({ query }: { query: string }) => {
      if (query.includes('GetEvaluationLight')) {
        return Promise.resolve({
          data: {
            getEvaluation: {
              id: 'eval-123',
              type: 'accuracy',
              createdAt: '2026-04-19T00:00:00.000Z',
              accuracy: 75,
              processedItems: 3,
              totalItems: 10,
              status: 'RUNNING',
              task: {
                id: 'task-1',
                status: 'RUNNING',
                command: 'plexus_evaluation_run',
                stages: {
                  items: [
                    {
                      id: 'stage-1',
                      taskId: 'task-1',
                      name: 'Processing',
                      order: 1,
                      status: 'RUNNING',
                      processedItems: 3,
                      totalItems: 10,
                    },
                  ],
                },
              },
              scorecard: { name: 'Scorecard A' },
              score: { name: 'Score X' },
            },
          },
        })
      }

      if (query.includes('listScoreResultByEvaluationId')) {
        return new Promise((resolve) => {
          resolveScores = resolve
        })
      }

      return Promise.resolve({ data: {} })
    })

    mockGenerateClient.mockReturnValue({ graphql })

    mockTransformEvaluation.mockImplementation((raw: any) => ({
      id: raw.id,
      type: raw.type || 'accuracy',
      scorecard: raw.scorecard || { name: 'Scorecard A' },
      score: raw.score || { name: 'Score X' },
      createdAt: raw.createdAt || '2026-04-19T00:00:00.000Z',
      metrics: null,
      metricsExplanation: null,
      accuracy: raw.accuracy ?? null,
      processedItems: raw.processedItems ?? 0,
      totalItems: raw.totalItems ?? 0,
      inferences: 0,
      cost: null,
      status: raw.status ?? 'RUNNING',
      elapsedSeconds: null,
      estimatedRemainingSeconds: null,
      startedAt: null,
      errorMessage: null,
      errorDetails: null,
      confusionMatrix: null,
      scoreGoal: null,
      datasetClassDistribution: null,
      isDatasetClassDistributionBalanced: null,
      predictedClassDistribution: null,
      isPredictedClassDistributionBalanced: null,
      scoreResults: raw.scoreResults?.items ?? [],
      scorecardId: null,
      scoreId: null,
      scoreVersionId: null,
      parameters: null,
      task: raw.task ?? null,
    }))

    render(<EvaluationToolOutput toolOutput={JSON.stringify({ evaluation_id: 'eval-123' })} />)

    await waitFor(() => expect(screen.getByTestId('task-display')).toBeInTheDocument())

    const initialTaskDisplay = screen.getByTestId('task-display')
    expect(initialTaskDisplay.getAttribute('data-extra')).toBe('true')
    expect(initialTaskDisplay.getAttribute('data-score-results')).toBe('0')

    expect(screen.getByText('Hydrating score results…')).toBeInTheDocument()

    resolveScores?.({
      data: {
        listScoreResultByEvaluationId: {
          items: [{ id: 'sr-1', value: 'yes' }],
          nextToken: null,
        },
      },
    })

    await waitFor(() => {
      const hydratedTaskDisplay = screen.getByTestId('task-display')
      expect(hydratedTaskDisplay.getAttribute('data-score-results')).toBe('1')
    })
  })
})
