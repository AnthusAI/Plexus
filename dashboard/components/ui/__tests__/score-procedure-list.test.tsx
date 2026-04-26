import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

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

    mockGraphql.mockImplementationOnce(async () => ({
      data: {
        listProcedureByScoreIdAndUpdatedAt: {
          items: [
            {
              id: 'proc-1',
              name: 'Optimizer Run 1',
              description: 'Procedure note 1',
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
              description: 'Procedure note 2',
              status: 'FAILED',
              metadata: null,
              updatedAt: '2026-04-24T00:00:00Z',
              scoreVersionId: 'version-x',
            },
          ],
        },
      },
    }))
    mockGraphql.mockImplementationOnce(async () => ({
      data: {
        listTaskByScoreId: {
          items: [
            {
              id: 'task-1',
              type: 'Procedure',
              status: 'COMPLETED',
              target: 'proc-1',
              command: '',
              description: 'Task description that should not be treated as procedure note',
              dispatchStatus: null,
              metadata: null,
              createdAt: '2026-04-25T00:00:00Z',
              startedAt: null,
              completedAt: null,
              estimatedCompletionAt: null,
              errorMessage: null,
              errorDetails: null,
              currentStageId: null,
              stages: { items: [] },
            },
          ],
        },
      },
    }))

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
    const user = userEvent.setup()
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

    expect(screen.getByText('Procedure note 1')).toBeInTheDocument()
    expect(screen.queryByText(/Task description that should not be treated as procedure note/)).not.toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: /more options/i })[0])
    expect(screen.getByRole('menuitem', { name: /runtime log/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /event stream/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /open best feedback alignment evaluation/i })).toHaveAttribute(
      'href',
      '/lab/evaluations/eval-feedback-1'
    )
    expect(screen.getByRole('menuitem', { name: /open best regression alignment evaluation/i })).toHaveAttribute(
      'href',
      '/lab/evaluations/eval-accuracy-1'
    )
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
