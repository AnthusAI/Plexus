import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'

import { ScoreProcedureList } from '../score-procedure-list'

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

jest.mock('@/components/ProcedureTask', () => ({
  __esModule: true,
  default: ({ procedure, controlButtons }: any) => (
    <div>
      <div>{procedure.title}</div>
      <div>{procedure.description}</div>
      {controlButtons}
    </div>
  ),
}))

describe('ScoreProcedureList', () => {
  beforeEach(() => {
    jest.clearAllMocks()

    mockGraphql.mockResolvedValue({
      data: {
        listProcedureByScoreIdAndUpdatedAt: {
          items: [
            {
              id: 'proc-1',
              name: 'Optimizer Run 1',
              status: 'COMPLETED',
              metadata: JSON.stringify({
                optimizer_artifacts: {
                  manifest: 'tasks/task-1/optimizer/manifest.json',
                  events: 'tasks/task-1/optimizer/events.jsonl',
                  runtime_log: 'tasks/task-1/optimizer/runtime.log',
                },
              }),
              updatedAt: '2026-04-25T00:00:00Z',
              scoreVersionId: 'version-0',
            },
            {
              id: 'proc-2',
              name: 'Other Run',
              status: 'FAILED',
              metadata: null,
              updatedAt: '2026-04-24T00:00:00Z',
              scoreVersionId: 'version-x',
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
                  baseline: { version_id: 'version-0' },
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
                  cycles: [
                    {
                      version_id: 'version-1',
                      candidates: [{ version_id: 'version-2' }],
                    },
                  ],
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

  it('renders score-scoped procedures with indexed optimizer actions', async () => {
    render(
      <ScoreProcedureList
        scoreId="score-1"
        scoreName="Medication Review: Prescriber"
        scorecardName="SelectQuote HCS Medium-Risk"
        scope="score"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Optimizer Run 1')).toBeInTheDocument()
    })

    expect(screen.getByText(/Winning: version-1/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Log$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Events$/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /^FB$/i })).toHaveAttribute('href', '/lab/evaluations/eval-feedback-1')
  })

  it('filters version-scoped procedures to runs that touched the selected version', async () => {
    render(
      <ScoreProcedureList
        scoreId="score-1"
        scoreName="Medication Review: Prescriber"
        scorecardName="SelectQuote HCS Medium-Risk"
        scope="version"
        versionId="version-2"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Optimizer Run 1')).toBeInTheDocument()
    })

    expect(screen.queryByText('Other Run')).not.toBeInTheDocument()
  })
})
