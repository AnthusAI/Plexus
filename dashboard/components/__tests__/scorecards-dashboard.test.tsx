import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import ScorecardsComponent from '../scorecards-dashboard'

// Mock amplify client with jest.mock
jest.mock('@/utils/amplify-client', () => ({
  amplifyClient: {
    Account: {
      list: jest.fn().mockResolvedValue({
        data: [{ id: 'account-1', key: 'call-criteria' }]
      })
    },
    Scorecard: {
      get: jest.fn(),
      list: jest.fn().mockResolvedValue({ data: [] })
    },
    ScorecardExampleItem: {
      listByScorecard: jest.fn().mockResolvedValue({
        data: []
      })
    }
  },
  getClient: () => ({
    models: {
      Task: {
        list: jest.fn().mockResolvedValue({ data: [] })
      },
      Item: {
        create: jest.fn(),
        update: jest.fn()
      }
    }
  }),
  graphqlRequest: jest.fn().mockResolvedValue({
    data: {
      listScorecardExampleItemByScorecardId: {
        items: []
      }
    }
  })
}))

// Get references to the mocked functions for our tests
const mockAmplifyClient = jest.mocked(require('@/utils/amplify-client'))

// Mock next/navigation
const mockPush = jest.fn()
const mockReplace = jest.fn()
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    prefetch: jest.fn()
  }),
  usePathname: () => '/lab/scorecards',
  useParams: () => ({})
}))

// Mock framer-motion to avoid animation issues in tests
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>
  },
  AnimatePresence: ({ children }: any) => children
}))

// Mock the subscriptions
jest.mock('@/utils/subscriptions', () => ({
  observeTaskUpdates: () => ({
    subscribe: jest.fn(() => ({
      unsubscribe: jest.fn()
    }))
  }),
  observeTaskStageUpdates: () => ({
    subscribe: jest.fn(() => ({
      unsubscribe: jest.fn()
    }))
  })
}))

// Mock child components to avoid complex rendering
jest.mock('../scorecards/ScorecardComponent', () => {
  return function MockScorecardComponent({ variant, onClick, score, onEdit }: any) {
    if (variant === 'grid') {
      return (
        <div data-testid={`scorecard-${score.id}`} onClick={onClick}>
          <h3>{score.name || 'New Scorecard'}</h3>
          <button onClick={onEdit}>Edit</button>
        </div>
      )
    }
    if (variant === 'detail') {
      return (
        <div data-testid="scorecard-detail">
          <h2>{score.name || 'New Scorecard'}</h2>
          <div>Detail view for {score.id || 'new scorecard'}</div>
        </div>
      )
    }
    return null
  }
})

jest.mock('../scorecards/ScorecardDetailView', () => {
  return function MockScorecardDetailView() {
    return <div data-testid="scorecard-detail-view">Detail View</div>
  }
})

jest.mock('../loading-skeleton', () => ({
  ScorecardDashboardSkeleton: () => <div data-testid="loading-skeleton">Loading...</div>
}))

describe('ScorecardsComponent', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    // Reset window.history
    delete (window as any).history
    window.history = {
      pushState: jest.fn(),
      replaceState: jest.fn(),
      back: jest.fn(),
      forward: jest.fn(),
      go: jest.fn(),
      length: 1,
      scrollRestoration: 'auto',
      state: null
    } as any
  })

  describe('Initial Loading', () => {
    it('should show loading skeleton while fetching data', () => {
      render(<ScorecardsComponent />)
      expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument()
    })

    it('should render empty state when no scorecards exist', async () => {
      render(<ScorecardsComponent />)
      
      await waitFor(() => {
        expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument()
      })

      expect(screen.getByRole('button', { name: /new scorecard/i })).toBeInTheDocument()
    })
  })

  describe('New Scorecard Creation', () => {
    it('should handle new scorecard button click without API errors', async () => {
      const user = userEvent.setup()
      render(<ScorecardsComponent />)
      
      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument()
      })

      // Find and click the "New Scorecard" button
      const newButton = screen.getByRole('button', { name: /new scorecard/i })
      await user.click(newButton)

      // Should show scorecard detail view for new scorecard
      await waitFor(() => {
        expect(screen.getByTestId('scorecard-detail')).toBeInTheDocument()
      })

      // Verify no API call was made with empty ID (the bug we fixed)
      expect(mockAmplifyClient.amplifyClient.Scorecard.get).not.toHaveBeenCalledWith({ id: '' })
    })

    it('should create blank scorecard with proper default values', async () => {
      const user = userEvent.setup()
      render(<ScorecardsComponent />)
      
      await waitFor(() => {
        expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument()
      })

      const newButton = screen.getByRole('button', { name: /new scorecard/i })
      await user.click(newButton)

      // Should show detail view with appropriate content for new scorecard
      await waitFor(() => {
        const detailView = screen.getByTestId('scorecard-detail')
        expect(detailView).toBeInTheDocument()
        expect(detailView).toHaveTextContent('new scorecard')
      })
    })

    it('should not make any API calls for blank scorecard creation', async () => {
      const user = userEvent.setup()
      render(<ScorecardsComponent />)
      
      await waitFor(() => {
        expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument()
      })

      // Clear any calls made during initial load
      mockAmplifyClient.amplifyClient.Scorecard.get.mockClear()

      const newButton = screen.getByRole('button', { name: /new scorecard/i })
      await user.click(newButton)

      await waitFor(() => {
        expect(screen.getByTestId('scorecard-detail')).toBeInTheDocument()
      })

      // Verify no additional API calls were made
      expect(mockAmplifyClient.amplifyClient.Scorecard.get).not.toHaveBeenCalled()
    })
  })

  describe('Existing Scorecard Selection', () => {
    beforeEach(() => {
      // Mock existing scorecards
      mockAmplifyClient.amplifyClient.Scorecard.list.mockResolvedValue({
        data: [
          {
            id: 'scorecard-1',
            name: 'Test Scorecard',
            key: 'test-scorecard',
            description: 'A test scorecard',
            accountId: 'account-1',
            sections: jest.fn().mockResolvedValue({ data: [] })
          }
        ]
      })

      mockAmplifyClient.amplifyClient.Scorecard.get.mockResolvedValue({
        data: {
          id: 'scorecard-1',
          name: 'Test Scorecard',
          sections: jest.fn().mockResolvedValue({ data: [] })
        }
      })
    })

    it('should make API call when selecting existing scorecard', async () => {
      const user = userEvent.setup()
      render(<ScorecardsComponent />)
      
      await waitFor(() => {
        expect(screen.getByTestId('scorecard-scorecard-1')).toBeInTheDocument()
      })

      const scorecardCard = screen.getByTestId('scorecard-scorecard-1')
      await user.click(scorecardCard)

      await waitFor(() => {
        expect(mockAmplifyClient.amplifyClient.Scorecard.get).toHaveBeenCalledWith({ id: 'scorecard-1' })
      })
    })

    it('should handle API errors gracefully when loading existing scorecard', async () => {
      const user = userEvent.setup()
      
      // Mock API error
      mockAmplifyClient.amplifyClient.Scorecard.get.mockRejectedValue(new Error('API Error'))
      
      render(<ScorecardsComponent />)
      
      await waitFor(() => {
        expect(screen.getByTestId('scorecard-scorecard-1')).toBeInTheDocument()
      })

      const scorecardCard = screen.getByTestId('scorecard-scorecard-1')
      await user.click(scorecardCard)

      // Should still attempt the API call but handle the error
      await waitFor(() => {
        expect(mockAmplifyClient.amplifyClient.Scorecard.get).toHaveBeenCalledWith({ id: 'scorecard-1' })
      })
    })
  })

  describe('URL Management', () => {
    it('should update URL when creating new scorecard', async () => {
      const user = userEvent.setup()
      render(<ScorecardsComponent />)
      
      await waitFor(() => {
        expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument()
      })

      const newButton = screen.getByRole('button', { name: /new scorecard/i })
      await user.click(newButton)

      await waitFor(() => {
        expect(screen.getByTestId('scorecard-detail')).toBeInTheDocument()
      })

      // URL should be updated when creating new scorecard
      expect(window.history.pushState).toHaveBeenCalledWith(null, '', '/lab/scorecards/')
    })
  })

  describe('Error Handling', () => {
    it('should display error message when initial data fetch fails', async () => {
      mockAmplifyClient.amplifyClient.Account.list.mockRejectedValue(new Error('Failed to fetch accounts'))
      
      render(<ScorecardsComponent />)
      
      await waitFor(() => {
        expect(screen.getByText(/error loading scorecards/i)).toBeInTheDocument()
      })
    })
  })
})