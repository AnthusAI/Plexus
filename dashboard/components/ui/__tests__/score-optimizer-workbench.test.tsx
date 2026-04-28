import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'

import { ScoreOptimizerWorkbench } from '../score-optimizer-workbench'

const mockGraphql = jest.fn()
const mockDownloadData = jest.fn()

jest.mock('aws-amplify/api', () => ({
  generateClient: () => ({
    graphql: mockGraphql,
  }),
}))

jest.mock('aws-amplify/storage', () => ({
  downloadData: (...args: any[]) => mockDownloadData(...args),
}))

describe('ScoreOptimizerWorkbench', () => {
  beforeEach(() => {
    jest.clearAllMocks()

    mockGraphql.mockResolvedValue({
      data: {
        listProcedureByScoreIdAndUpdatedAt: {
          items: [
            {
              id: 'proc-1',
              name: 'Feedback Alignment Optimizer',
              status: 'COMPLETED',
              metadata: JSON.stringify({
                optimizer_artifacts: {
                  manifest: 'tasks/task-1/optimizer/manifest.json',
                  events: 'tasks/task-1/optimizer/events.jsonl',
                  runtime_log: 'tasks/task-1/optimizer/runtime.log',
                },
              }),
              updatedAt: '2026-04-25T00:00:00Z',
              scoreVersionId: 'version-1',
            },
          ],
        },
      },
    })

    mockDownloadData.mockImplementation(({ path }: { path: string }) => {
      if (path === 'tasks/task-1/optimizer/manifest.json') {
        return {
          result: Promise.resolve({
            body: {
              text: async () =>
                JSON.stringify({
                  summary: {
                    completed_cycles: 6,
                    configured_max_iterations: 10,
                    stop_reason: 'max_iterations',
                  },
                  best: {
                    winning_version_id: 'version-1',
                    best_feedback_evaluation_id: 'eval-feedback-1',
                    best_accuracy_evaluation_id: 'eval-accuracy-1',
                    winning_feedback_metrics: { alignment: 0.83 },
                    winning_accuracy_metrics: { alignment: 0.88 },
                  },
                  cycles: [],
                }),
            },
          }),
        }
      }

      return {
        result: Promise.resolve({
          body: {
            text: async () => 'artifact body',
          },
        }),
      }
    })
  })

  it('renders indexed optimizer runs and candidate versions', async () => {
    render(
      <ScoreOptimizerWorkbench
        scoreId="score-1"
        scoreName="Medication Review: Prescriber"
        scorecardName="SelectQuote HCS Medium-Risk"
        championVersionId="version-1"
        versions={[
          {
            id: 'version-1',
            isFeatured: 'true',
            note: 'Best candidate',
            branch: 'optimizer',
            parentVersionId: 'version-0',
          },
        ]}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Feedback Alignment Optimizer')).toBeInTheDocument()
    })

    expect(screen.getByText('Winning version: version-1')).toBeInTheDocument()
    expect(screen.getByText('Feedback AC1: 0.8300')).toBeInTheDocument()
    expect(screen.getByText('Regression AC1: 0.8800')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Runtime log/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Event stream/i })).toBeInTheDocument()
    expect(screen.getByText('Champion')).toBeInTheDocument()
    expect(screen.getByText('Pinned')).toBeInTheDocument()
  })
})
