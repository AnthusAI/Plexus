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
      <div data-testid={`procedure-task-status-${procedure.id}`}>{procedure.task?.status ?? ''}</div>
      <div data-testid={`procedure-task-stages-${procedure.id}`}>
        {(procedure.task?.stages?.items ?? []).map((stage: any) => `${stage.name}:${stage.status}:${stage.statusMessage}`).join('|')}
      </div>
      {controlButtons}
    </div>
  ),
}))

describe('ScoreProcedureList', () => {
  beforeEach(() => {
    jest.clearAllMocks()

    mockGraphql.mockImplementation(async ({ query }: { query: string }) => {
      if (query.includes('listTaskByScoreId')) {
        return {
          data: {
            listTaskByScoreId: {
              items: [
                {
                  id: 'task-1',
                  type: 'Procedure',
                  status: 'COMPLETED',
                  target: 'procedure/run/proc-1',
                  command: '',
                  description: 'Task description that should not be treated as procedure note',
                  dispatchStatus: null,
                  metadata: null,
                  createdAt: '2026-04-25T00:00:00Z',
                  startedAt: '2026-04-25T00:01:00Z',
                  completedAt: '2026-04-25T00:05:00Z',
                  estimatedCompletionAt: null,
                  errorMessage: null,
                  errorDetails: null,
                  currentStageId: 'stage-final',
                  stages: {
                    items: [
                      {
                        id: 'stage-start',
                        name: 'Start',
                        order: 1,
                        status: 'COMPLETED',
                        statusMessage: 'Initialized optimizer',
                      },
                      {
                        id: 'stage-final',
                        name: 'Finalizing',
                        order: 2,
                        status: 'COMPLETED',
                        statusMessage: 'Saved optimizer result',
                      },
                    ],
                  },
                },
              ],
            },
          },
        }
      }

      return {
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
      }
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
                    winning_feedback_metrics: { alignment: 0.83, accuracy: 0.91, precision: 0.72, recall: 0.81, cost: 0.32 },
                    winning_accuracy_metrics: { alignment: 0.88, accuracy: 0.93, precision: 0.77, recall: 0.84, cost: 0.41 },
                  },
                  cycles: [
                    {
                      version_id: 'version-1',
                      feedback_evaluation_id: 'eval-feedback-cycle-1',
                      accuracy_evaluation_id: 'eval-accuracy-cycle-1',
                      feedback_metrics: { alignment: 0.80, precision: 0.79, recall: 0.70, cost: 0.21 },
                      accuracy_metrics: { alignment: 0.82, precision: 0.82, recall: 0.71, cost: 0.30 },
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
        scorecardId="scorecard-1"
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
    expect(screen.getByTestId('procedure-task-status-proc-1')).toHaveTextContent('COMPLETED')
    expect(screen.getByTestId('procedure-task-stages-proc-1')).toHaveTextContent('Start:COMPLETED:Initialized optimizer')
    expect(screen.getByTestId('procedure-task-stages-proc-1')).toHaveTextContent('Finalizing:COMPLETED:Saved optimizer result')
    expect(screen.getByRole('option', { name: /best feedback precision/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /best regression recall/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /best feedback cost/i })).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: /more options/i })[0])
    expect(screen.getByRole('menuitem', { name: /runtime log/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /event stream/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /find best evaluation/i })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /open best feedback alignment evaluation/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /open best feedback precision evaluation/i })).not.toBeInTheDocument()
    await user.click(screen.getByRole('menuitem', { name: /find best evaluation/i }))
    expect(screen.getByRole('dialog', { name: /find best evaluation/i })).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText(/^Metric$/i), 'precision')
    expect(screen.getByRole('link', { name: /open evaluation/i })).toHaveAttribute(
      'href',
      '/lab/evaluations/eval-feedback-cycle-1'
    )
    await user.selectOptions(screen.getByLabelText(/^Metric$/i), 'cost')
    expect(screen.getByRole('link', { name: /open version/i })).toHaveAttribute(
      'href',
      '/lab/scorecards/scorecard-1/scores/score-1/versions/version-1'
    )
  })

  it('filters version-scoped procedures to runs that touched the selected version', async () => {
    render(
      <ScoreProcedureList
        scoreId="score-1"
        scorecardId="scorecard-1"
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
