import React from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ProcedureTask from '@/components/ProcedureTask'

const mockGraphql = jest.fn()
const mockDownloadData = jest.fn()

jest.setTimeout(10000)

jest.mock('aws-amplify/data', () => ({
  generateClient: jest.fn(() => ({
    graphql: mockGraphql,
  })),
}))

jest.mock('aws-amplify/storage', () => ({
  downloadData: (...args: any[]) => mockDownloadData(...args),
}))

jest.mock('@monaco-editor/react', () => () => null)
jest.mock('@/components/procedure-conversation-viewer', () => () => null)
jest.mock('@/components/ui/ParametersDisplay', () => ({ ParametersDisplay: () => null }))
jest.mock('@/components/OptimizerMetricsChart', () => ({
  __esModule: true,
  default: ({ onDatasetViewChange }: any) => (
    <div data-testid="optimizer-chart">
      <button type="button" onClick={() => onDatasetViewChange?.('overall')}>set-overall</button>
      <button type="button" onClick={() => onDatasetViewChange?.('recent')}>set-recent</button>
      <button type="button" onClick={() => onDatasetViewChange?.('regression')}>set-regression</button>
    </div>
  ),
}))
jest.mock('@/components/OptimizationInsightsPanel', () => ({
  EndOfRunReport: () => null,
  ReportSection: () => null,
}))
jest.mock('@/components/loading-skeleton', () => ({
  OptimizerMetricsChartSkeleton: () => null,
  CycleHistoryTableSkeleton: () => null,
}))
jest.mock('@/lib/monaco-theme', () => ({
  defineCustomMonacoThemes: jest.fn(),
  applyMonacoTheme: jest.fn(),
  setupMonacoThemeWatcher: jest.fn(),
  getCommonMonacoOptions: jest.fn(() => ({})),
  configureYamlLanguage: jest.fn(),
}))

describe('ProcedureTask optimizer auth flow', () => {
  const baseProcedure: any = {
    id: 'proc-1',
    title: 'Optimizer Procedure',
    description: 'test',
    featured: false,
    createdAt: '2026-01-01T00:00:00.000Z',
    updatedAt: '2026-01-01T00:00:00.000Z',
    scorecardId: 'sc-1',
    scoreId: 's-1',
    task: {
      id: 'task-1',
      type: 'Procedure Run',
      status: 'COMPLETED',
      target: 'procedure/run/proc-1',
      command: 'procedure run',
      stages: { items: [] },
    },
  }

  beforeEach(() => {
    jest.clearAllMocks()
    ;(global as any).fetch = jest.fn()
  })

  it('renders local dispatch mode before stale dispatcher fields', () => {
    render(
      <ProcedureTask
        variant="grid"
        procedure={{
          ...baseProcedure,
          task: {
            ...baseProcedure.task,
            status: 'RUNNING',
            dispatchStatus: 'ANNOUNCED',
            workerNodeId: 'BlackbookM3-15348',
            metadata: JSON.stringify({ procedure_id: 'proc-1', dispatch_mode: 'local' }),
          },
        }}
      />
    )

    expect(screen.getByText('Local')).toBeInTheDocument()
    expect(screen.queryByText('Claimed...')).not.toBeInTheDocument()
    expect(screen.queryByText('Announced...')).not.toBeInTheDocument()
  })

  it('renders pending when no task has been attached yet', () => {
    render(
      <ProcedureTask
        variant="grid"
        procedure={{
          ...baseProcedure,
          task: null,
        }}
      />
    )

    expect(screen.getByText('Pending...')).toBeInTheDocument()
    expect(screen.queryByText('Announced...')).not.toBeInTheDocument()
  })

  it('still renders claimed for true dispatcher-owned tasks', () => {
    render(
      <ProcedureTask
        variant="grid"
        procedure={{
          ...baseProcedure,
          task: {
            ...baseProcedure.task,
            status: 'RUNNING',
            dispatchStatus: 'CLAIMED',
            workerNodeId: 'dispatcher-1',
            metadata: JSON.stringify({ procedure_id: 'proc-1' }),
          },
        }}
      />
    )

    expect(screen.getByText('Claimed...')).toBeInTheDocument()
    expect(screen.queryByText('Local')).not.toBeInTheDocument()
  })

  it('loads metadata without apiKey auth mode and does not call the proxy route', async () => {
    const metadataState = {
      state: {
        baseline_version_id: 'v0',
        iterations: [
          {
            iteration: 1,
            recent_metrics: { alignment: 0.7, accuracy: 82, precision: 81, recall: 80 },
            recent_deltas: { alignment: 0.1, accuracy: 2, precision: 2, recall: 2 },
            regression_metrics: { alignment: 0.68, accuracy: 78, precision: 77, recall: 76 },
            regression_deltas: { alignment: 0.08, accuracy: 1, precision: 1, recall: 1 },
            recent_cost_per_item: 0.011,
            regression_cost_per_item: 0.022,
          },
        ],
      },
    }

    mockGraphql.mockImplementation(async ({ query }: any) => {
      const queryText = String(query)
      if (queryText.includes('GetProcedureMetadata')) {
        return { data: { getProcedure: { metadata: JSON.stringify(metadataState) } } }
      }
      if (queryText.includes('query GetProcedure($id: ID!)')) {
        return { data: { getProcedure: { id: 'proc-1', code: 'class: BeamSearch' } } }
      }
      return { data: {} }
    })

    render(<ProcedureTask variant="detail" procedure={baseProcedure} />)

    await waitFor(() => {
      const metadataCall = mockGraphql.mock.calls
        .map(call => call[0])
        .find(args => String(args.query).includes('GetProcedureMetadata'))

      expect(metadataCall).toBeDefined()
      expect(metadataCall.authMode).toBeUndefined()
      expect((global as any).fetch).not.toHaveBeenCalled()
    })
  })

  it('renders grid notes above status and shows feedback accuracy performance', () => {
    render(
      <ProcedureTask
        variant="grid"
        procedure={{
          ...baseProcedure,
          description: 'Procedure note for the operator',
          task: {
            ...baseProcedure.task,
            status: 'COMPLETED',
            startedAt: '2026-01-01T00:00:00.000Z',
            completedAt: '2026-01-01T00:05:00.000Z',
            currentStageId: 'stage-final',
            stages: {
              items: [
                {
                  id: 'stage-start',
                  name: 'Start',
                  order: 1,
                  status: 'COMPLETED',
                  statusMessage: 'Started procedure',
                },
                {
                  id: 'stage-final',
                  name: 'Finalizing',
                  order: 2,
                  status: 'COMPLETED',
                  statusMessage: 'Final stage complete',
                },
              ],
            },
          },
          feedbackEvaluationSummary: {
            id: 'eval-feedback-1',
            status: 'COMPLETED',
            accuracy: 87,
            processedItems: 87,
            totalItems: 100,
          },
        } as any}
      />
    )

    const card = screen.getAllByRole('button')[0]
    expect(screen.getByText('Procedure note for the operator')).toBeInTheDocument()
    expect(screen.getByText('Final stage complete')).toBeInTheDocument()
    expect(screen.getAllByText('87%').length).toBeGreaterThan(0)
    expect(card).toHaveTextContent('Elapsed:')
    expect(card.textContent?.indexOf('Procedure note for the operator')).toBeLessThan(
      card.textContent?.indexOf('Final stage complete') ?? 0
    )
  })

  it('shows compact left icon/title in grid header when action controls are present', () => {
    render(
      <ProcedureTask
        variant="grid"
        procedure={{
          ...baseProcedure,
          description: 'Procedure note for action layout',
        } as any}
        controlButtons={<button type="button" aria-label="Procedure actions">actions</button>}
      />
    )

    expect(screen.getByLabelText('Procedure actions')).toBeInTheDocument()
    expect(screen.getByText(/^Procedure$/)).toBeInTheDocument()
  })

  it('hydrates offloaded optimizer state from Amplify Storage procedures path', async () => {
    const metadataState = {
      state: {
        _s3_key: 'procedures/proc-1/state.json',
      },
    }

    const hydratedState = {
      baseline_version_id: 'v0',
      iterations: [
        {
          iteration: 1,
          recent_metrics: { alignment: 0.75, accuracy: 84, precision: 83, recall: 82 },
          recent_deltas: { alignment: 0.05, accuracy: 1, precision: 1, recall: 1 },
          regression_metrics: { alignment: 0.7, accuracy: 80, precision: 79, recall: 78 },
          regression_deltas: { alignment: 0.03, accuracy: 1, precision: 1, recall: 1 },
          recent_cost_per_item: 0.019,
          regression_cost_per_item: 0.031,
        },
      ],
    }

    mockGraphql.mockImplementation(async ({ query }: any) => {
      const queryText = String(query)
      if (queryText.includes('GetProcedureMetadata')) {
        return { data: { getProcedure: { metadata: JSON.stringify(metadataState) } } }
      }
      if (queryText.includes('query GetProcedure($id: ID!)')) {
        return { data: { getProcedure: { id: 'proc-1', code: 'class: BeamSearch' } } }
      }
      return { data: {} }
    })

    mockDownloadData.mockReturnValue({
      result: Promise.resolve({
        body: {
          text: async () => JSON.stringify(hydratedState),
        },
      }),
    })

    render(<ProcedureTask variant="detail" procedure={baseProcedure} />)

    await waitFor(() => {
      expect(mockDownloadData).toHaveBeenCalledWith({
        path: 'procedures/proc-1/state.json',
        options: { bucket: 'reportBlockDetails' },
      })
      expect((global as any).fetch).not.toHaveBeenCalled()
    })
  })

  it('shows overall cycles columns by default and switches column sets with chart mode', async () => {
    const metadataState = {
      state: {
        baseline_version_id: 'v0',
        recent_baseline_metrics: { alignment: 0.6, accuracy: 80, precision: 79, recall: 78 },
        regression_baseline_metrics: { alignment: 0.58, accuracy: 77, precision: 76, recall: 75 },
        recent_baseline_cost_per_item: 0.01,
        regression_baseline_cost_per_item: 0.02,
        iterations: [
          {
            iteration: 1,
            score_version_id: 'v1',
            accepted: true,
            recent_metrics: { alignment: 0.7, accuracy: 82, precision: 81, recall: 80 },
            recent_deltas: { alignment: 0.1, accuracy: 2, precision: 2, recall: 2 },
            regression_metrics: { alignment: 0.68, accuracy: 78, precision: 77, recall: 76 },
            regression_deltas: { alignment: 0.1, accuracy: 1, precision: 1, recall: 1 },
            recent_cost_per_item: 0.011,
            regression_cost_per_item: 0.022,
          },
        ],
      },
    }

    mockGraphql.mockImplementation(async ({ query }: any) => {
      const queryText = String(query)
      if (queryText.includes('GetProcedureMetadata')) {
        return { data: { getProcedure: { metadata: JSON.stringify(metadataState) } } }
      }
      if (queryText.includes('query GetProcedure($id: ID!)')) {
        return { data: { getProcedure: { id: 'proc-1', code: 'class: BeamSearch' } } }
      }
      return { data: {} }
    })

    render(<ProcedureTask variant="detail" procedure={baseProcedure} />)

    await waitFor(() => {
      expect(screen.getByText('Cycles')).toBeInTheDocument()
    })

    const table = screen.getByRole('table')
    expect(within(table).getByText('Recent')).toBeInTheDocument()
    expect(within(table).getByText('Regression')).toBeInTheDocument()
    expect(within(table).getAllByText('Cost/item')).toHaveLength(2)
    expect(within(table).getAllByText('Δ')).toHaveLength(4)
    expect(within(table).queryByRole('columnheader', { name: 'P' })).not.toBeInTheDocument()
    expect(within(table).queryByRole('columnheader', { name: 'R' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'set-recent' }))
    expect(within(table).getByText('Recent')).toBeInTheDocument()
    expect(within(table).queryByText('Regression')).not.toBeInTheDocument()
    expect(within(table).queryByText('Cost/item')).not.toBeInTheDocument()
    expect(within(table).queryByText('Δ')).not.toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: 'P' })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: 'R' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'set-regression' }))
    expect(within(table).getByText('Regression')).toBeInTheDocument()
    expect(within(table).queryByText('Recent')).not.toBeInTheDocument()
    expect(within(table).queryByText('Cost/item')).not.toBeInTheDocument()
    expect(within(table).queryByText('Δ')).not.toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: 'P' })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: 'R' })).toBeInTheDocument()
  })

  it('ignores legacy feedback/accuracy metric keys', async () => {
    const legacyProcedure = {
      ...baseProcedure,
      id: 'proc-legacy',
      task: { ...baseProcedure.task, id: 'task-legacy' },
    }

    const metadataState = {
      state: {
        baseline_version_id: 'v0',
        iterations: [
          {
            iteration: 1,
            feedback_metrics: { alignment: 0.7, accuracy: 82, precision: 81, recall: 80 },
            feedback_deltas: { alignment: 0.1, accuracy: 2, precision: 2, recall: 2 },
            accuracy_metrics: { alignment: 0.68, accuracy: 78, precision: 77, recall: 76 },
            accuracy_deltas: { alignment: 0.1, accuracy: 1, precision: 1, recall: 1 },
          },
        ],
      },
    }

    mockGraphql.mockImplementation(async ({ query }: any) => {
      const queryText = String(query)
      if (queryText.includes('GetProcedureMetadata')) {
        return { data: { getProcedure: { metadata: JSON.stringify(metadataState) } } }
      }
      if (queryText.includes('query GetProcedure($id: ID!)')) {
        return { data: { getProcedure: { id: 'proc-legacy', code: 'class: BeamSearch' } } }
      }
      return { data: {} }
    })

    render(<ProcedureTask variant="detail" procedure={legacyProcedure as any} />)

    await waitFor(() => {
      expect(screen.getByText('Cycles')).toBeInTheDocument()
    })
    expect(screen.queryByText('0.700')).not.toBeInTheDocument()
    expect(screen.queryByText('0.680')).not.toBeInTheDocument()
  })
})
