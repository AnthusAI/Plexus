import React from 'react'
import { render, waitFor } from '@testing-library/react'
import ProcedureTask from '@/components/ProcedureTask'

const mockGraphql = jest.fn()
const mockDownloadData = jest.fn()

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
jest.mock('@/components/OptimizerMetricsChart', () => () => <div data-testid="optimizer-chart" />)
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

  it('loads metadata without apiKey auth mode and does not call the proxy route', async () => {
    const metadataState = {
      state: {
        iterations: [
          {
            iteration: 1,
            feedback_metrics: { alignment: 0.7, accuracy: 82, precision: 81, recall: 80 },
            feedback_deltas: { alignment: 0.1, accuracy: 2, precision: 2, recall: 2 },
            accuracy_metrics: { alignment: 0.68, accuracy: 78, precision: 77, recall: 76 },
            accuracy_deltas: { alignment: 0.08, accuracy: 1, precision: 1, recall: 1 },
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

  it('hydrates offloaded optimizer state from Amplify Storage procedures path', async () => {
    const metadataState = {
      state: {
        _s3_key: 'procedures/proc-1/state.json',
      },
    }

    const hydratedState = {
      iterations: [
        {
          iteration: 1,
          feedback_metrics: { alignment: 0.75, accuracy: 84, precision: 83, recall: 82 },
          feedback_deltas: { alignment: 0.05, accuracy: 1, precision: 1, recall: 1 },
          accuracy_metrics: { alignment: 0.7, accuracy: 80, precision: 79, recall: 78 },
          accuracy_deltas: { alignment: 0.03, accuracy: 1, precision: 1, recall: 1 },
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
})
