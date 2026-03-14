import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, jest, beforeEach } from '@jest/globals'

const mockUseAccount = jest.fn()
const mockUseEvaluationData = jest.fn()
let mockAuthStatus: 'authenticated' | 'configuring' = 'authenticated'

jest.mock('@/app/contexts/AccountContext', () => ({
  useAccount: () => mockUseAccount(),
}))

jest.mock('@/features/evaluations/hooks/useEvaluationData', () => ({
  useEvaluationData: (args: unknown) => mockUseEvaluationData(args),
}))

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  useParams: () => ({}),
  usePathname: () => '/lab/evaluations',
}))

jest.mock('@aws-amplify/ui-react', () => ({
  __esModule: true,
  useAuthenticator: () => ({
    user: mockAuthStatus === 'authenticated' ? { username: 'test-user' } : null,
    authStatus: mockAuthStatus,
  }),
}))

jest.mock('react-intersection-observer', () => ({
  useInView: () => ({ ref: jest.fn(), inView: false }),
}))

jest.mock('framer-motion', () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, layout, ...props }: any) => <div {...props}>{children}</div>,
  },
}))

jest.mock('@/hooks/use-media-query', () => ({
  useMediaQuery: () => false,
}))

jest.mock('@/components/ScorecardContext', () => () => <div data-testid="scorecard-context" />)
jest.mock('@/components/task-dispatch', () => ({
  TaskDispatchButton: () => <button type="button">Dispatch</button>,
  evaluationsConfig: {},
}))
jest.mock('../EvaluationTasksGauges', () => ({
  EvaluationTasksGauges: () => <div data-testid="evaluation-gauges" />,
}))
jest.mock('@/components/TaskDisplay', () => ({
  TaskDisplay: () => <div data-testid="task-display" />,
}))

const EvaluationsDashboard = require('../evaluations-dashboard').default

describe('EvaluationsDashboard account resolution', () => {
  beforeEach(() => {
    mockAuthStatus = 'authenticated'
    mockUseAccount.mockReset()
    mockUseEvaluationData.mockReset()
    mockUseEvaluationData.mockReturnValue({
      evaluations: [],
      isLoading: false,
      isLoadingMore: false,
      hasMore: false,
      error: null,
      refetch: jest.fn(),
      loadMore: jest.fn(),
    })
  })

  it('does not show "No account found" while accounts are still loading', () => {
    mockUseAccount.mockReturnValue({
      accounts: [],
      selectedAccount: null,
      isLoadingAccounts: true,
    })

    render(<EvaluationsDashboard />)

    expect(screen.queryByText('Error: No account found')).not.toBeInTheDocument()
  })

  it('does not show "No account found" before auth is authenticated', () => {
    mockAuthStatus = 'configuring'
    mockUseAccount.mockReturnValue({
      accounts: ['placeholder-account'],
      selectedAccount: null,
      isLoadingAccounts: false,
    })

    render(<EvaluationsDashboard />)

    expect(screen.queryByText('Error: No account found')).not.toBeInTheDocument()
  })

  it('shows "No account found" after account loading completes with no selected account', async () => {
    mockUseAccount.mockReturnValue({
      accounts: [],
      selectedAccount: null,
      isLoadingAccounts: false,
    })

    render(<EvaluationsDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Error: No account found')).toBeInTheDocument()
    })
  })

  it('uses selected account id from AccountContext when loading evaluations', async () => {
    mockUseAccount.mockReturnValue({
      accounts: [{ id: 'account-123', name: 'Primary Account' }],
      selectedAccount: { id: 'account-123', name: 'Primary Account' },
      isLoadingAccounts: false,
    })

    render(<EvaluationsDashboard />)

    await waitFor(() => {
      expect(mockUseEvaluationData).toHaveBeenCalled()
    })

    const firstCallArgs = mockUseEvaluationData.mock.calls[0][0] as { accountId: string | null }
    expect(firstCallArgs.accountId).toBe('account-123')
    expect(screen.queryByText('Error: No account found')).not.toBeInTheDocument()
  })

  it('does not show "No account found" when accounts exist but selected account has not hydrated yet', () => {
    mockUseAccount.mockReturnValue({
      accounts: [{ id: 'account-123', name: 'Primary Account' }],
      selectedAccount: null,
      isLoadingAccounts: false,
    })

    render(<EvaluationsDashboard />)

    expect(screen.queryByText('Error: No account found')).not.toBeInTheDocument()
  })
})
