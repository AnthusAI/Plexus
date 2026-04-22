import React from 'react'
import { act, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import ProceduresDashboard from '@/components/procedures-dashboard'
import { ProceduresDashboardSkeleton } from '@/components/loading-skeleton'

const mockGraphql = jest.fn()

type Deferred<T> = {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (error: unknown) => void
}

function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

jest.mock('aws-amplify/data', () => ({
  generateClient: jest.fn(() => ({
    graphql: (...args: any[]) => mockGraphql(...args),
    models: {
      Procedure: {
        delete: jest.fn(),
        create: jest.fn(),
      },
    },
  })),
}))

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => '/lab/procedures',
  useParams: () => ({}),
}))

jest.mock('@/app/contexts/AccountContext', () => ({
  useAccount: () => ({
    selectedAccount: { id: 'account-1' },
    accounts: [{ id: 'account-1' }],
    isLoadingAccounts: false,
  }),
}))

jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, layout, layoutId, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => children,
}))

jest.mock('react-intersection-observer', () => ({
  useInView: () => ({ ref: jest.fn(), inView: false }),
}))

jest.mock('@/utils/subscriptions', () => ({
  observeTaskUpdates: () => ({
    subscribe: jest.fn(() => ({ unsubscribe: jest.fn() })),
  }),
  observeTaskStageUpdates: () => ({
    subscribe: jest.fn(() => ({ unsubscribe: jest.fn() })),
  }),
  observeGraphNodeUpdates: () => ({
    subscribe: jest.fn(() => ({ unsubscribe: jest.fn() })),
  }),
}))

jest.mock('@/components/ProcedureTask', () => ({
  __esModule: true,
  default: ({ variant, procedure }: any) => (
    <div data-testid={variant === 'grid' ? `procedure-card-${procedure.id}` : `procedure-detail-${procedure.id}`}>
      task:{procedure.task?.status || 'none'}
    </div>
  ),
}))

jest.mock('@/components/ProcedureTaskEdit', () => ({
  __esModule: true,
  default: () => <div data-testid="procedure-edit-form">edit</div>,
}))

jest.mock('@/components/procedure-conversation-viewer', () => ({
  __esModule: true,
  default: () => <div data-testid="procedure-conversation-viewer">conversation</div>,
}))

jest.mock('@/components/ScorecardContext', () => ({
  __esModule: true,
  default: ({ skeletonMode }: { skeletonMode?: boolean }) => (
    <div data-testid="scorecard-context">{skeletonMode ? 'skeleton' : 'ready'}</div>
  ),
}))

jest.mock('@/components/template-selector', () => ({
  __esModule: true,
  default: () => null,
}))

jest.mock('@/components/ProceduresGauges', () => ({
  ProceduresGauges: () => <div data-testid="procedures-gauges">gauges</div>,
}))

describe('Procedures dashboard loading UX', () => {
  const createSubscriptionResult = () => ({
    subscribe: jest.fn(() => ({ unsubscribe: jest.fn() })),
  })

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('shows the dedicated procedures skeleton on initial load', async () => {
    const deferredProcedures = createDeferred<any>()

    mockGraphql.mockImplementation(({ query }: { query: string }) => {
      const text = String(query)
      if (text.includes('onCreateProcedure') || text.includes('onUpdateProcedure')) {
        return createSubscriptionResult()
      }
      if (text.includes('listProcedureByAccountIdAndUpdatedAt')) {
        return deferredProcedures.promise
      }
      if (text.includes('listTaskByAccountIdAndUpdatedAt')) {
        return Promise.resolve({ data: { listTaskByAccountIdAndUpdatedAt: { items: [] } } })
      }
      return Promise.resolve({ data: {} })
    })

    render(<ProceduresDashboard />)

    expect(screen.getByTestId('procedures-dashboard-skeleton')).toBeInTheDocument()
    expect(screen.queryByText('No procedures found')).not.toBeInTheDocument()
  })

  it('renders cards before task hydration completes, then hydrates statuses', async () => {
    const deferredTasks = createDeferred<any>()

    mockGraphql.mockImplementation(({ query }: { query: string }) => {
      const text = String(query)
      if (text.includes('onCreateProcedure') || text.includes('onUpdateProcedure')) {
        return createSubscriptionResult()
      }
      if (text.includes('listProcedureByAccountIdAndUpdatedAt')) {
        return Promise.resolve({
          data: {
            listProcedureByAccountIdAndUpdatedAt: {
              items: [
                {
                  id: 'proc-1',
                  name: 'Procedure 1',
                  featured: false,
                  code: null,
                  rootNodeId: null,
                  createdAt: '2026-04-20T00:00:00.000Z',
                  updatedAt: '2026-04-20T00:00:00.000Z',
                  accountId: 'account-1',
                  scorecardId: null,
                  scorecard: null,
                  scoreId: null,
                  score: null,
                },
              ],
              nextToken: null,
            },
          },
        })
      }
      if (text.includes('listTaskByAccountIdAndUpdatedAt')) {
        return deferredTasks.promise
      }
      return Promise.resolve({ data: {} })
    })

    render(<ProceduresDashboard />)

    await waitFor(() => {
      expect(screen.getByTestId('procedure-card-proc-1')).toBeInTheDocument()
    })

    expect(screen.getByText('task:none')).toBeInTheDocument()
    expect(screen.queryByTestId('procedures-dashboard-skeleton')).not.toBeInTheDocument()

    await act(async () => {
      deferredTasks.resolve({
        data: {
          listTaskByAccountIdAndUpdatedAt: {
            items: [
              {
                id: 'task-1',
                type: 'Procedure',
                status: 'RUNNING',
                target: 'procedure/run/proc-1',
                command: 'procedure run',
                metadata: JSON.stringify({ procedure_id: 'proc-1' }),
                stages: { items: [] },
              },
            ],
          },
        },
      })
      await Promise.resolve()
    })

    await waitFor(() => {
      expect(screen.getByText('task:RUNNING')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('procedures-dashboard-skeleton')).not.toBeInTheDocument()
  })

  it('shows empty state after initial load when no procedures exist', async () => {
    mockGraphql.mockImplementation(({ query }: { query: string }) => {
      const text = String(query)
      if (text.includes('onCreateProcedure') || text.includes('onUpdateProcedure')) {
        return createSubscriptionResult()
      }
      if (text.includes('listProcedureByAccountIdAndUpdatedAt')) {
        return Promise.resolve({
          data: {
            listProcedureByAccountIdAndUpdatedAt: {
              items: [],
              nextToken: null,
            },
          },
        })
      }
      if (text.includes('listTaskByAccountIdAndUpdatedAt')) {
        return Promise.resolve({ data: { listTaskByAccountIdAndUpdatedAt: { items: [] } } })
      }
      return Promise.resolve({ data: {} })
    })

    render(<ProceduresDashboard />)

    await waitFor(() => {
      expect(screen.getByText('No procedures found')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('procedures-dashboard-skeleton')).not.toBeInTheDocument()
  })

  it('keeps rendered cards and shows non-blocking error banner when task hydration fails', async () => {
    mockGraphql.mockImplementation(({ query }: { query: string }) => {
      const text = String(query)
      if (text.includes('onCreateProcedure') || text.includes('onUpdateProcedure')) {
        return createSubscriptionResult()
      }
      if (text.includes('listProcedureByAccountIdAndUpdatedAt')) {
        return Promise.resolve({
          data: {
            listProcedureByAccountIdAndUpdatedAt: {
              items: [
                {
                  id: 'proc-err',
                  name: 'Procedure Error',
                  featured: false,
                  code: null,
                  rootNodeId: null,
                  createdAt: '2026-04-20T00:00:00.000Z',
                  updatedAt: '2026-04-20T00:00:00.000Z',
                  accountId: 'account-1',
                  scorecardId: null,
                  scorecard: null,
                  scoreId: null,
                  score: null,
                },
              ],
              nextToken: null,
            },
          },
        })
      }
      if (text.includes('listTaskByAccountIdAndUpdatedAt')) {
        return Promise.reject(new Error('task hydration failed'))
      }
      return Promise.resolve({ data: {} })
    })

    render(<ProceduresDashboard />)

    await waitFor(() => {
      expect(screen.getByTestId('procedure-card-proc-err')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText(/Unable to fully refresh procedures:/)).toBeInTheDocument()
      expect(screen.getByText(/task hydration failed/)).toBeInTheDocument()
    })
  })
})

describe('ProceduresDashboardSkeleton styles', () => {
  it('uses themed muted/card classes and avoids bright hardcoded gray blocks', () => {
    const { container } = render(<ProceduresDashboardSkeleton />)
    const root = screen.getByTestId('procedures-dashboard-skeleton')

    expect(root).toBeInTheDocument()
    expect(container.querySelector('.bg-gray-200')).toBeNull()
    expect(container.querySelector('.bg-muted')).not.toBeNull()
    expect(container.querySelector('.bg-card')).not.toBeNull()
  })
})
