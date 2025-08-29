import React from 'react'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import ScorecardsComponent from '../scorecards-dashboard'

// Mock scrollIntoView which doesn't exist in JSDOM
Element.prototype.scrollIntoView = jest.fn()

// Mock amplify client with jest.mock
jest.mock('@/utils/amplify-client', () => ({
  amplifyClient: {
    Account: {
      list: jest.fn().mockResolvedValue({
        data: [{ id: 'account-1', key: 'call-criteria' }]
      })
    },
    Scorecard: {
      get: jest.fn().mockResolvedValue({
        data: {
          id: 'new-scorecard-id',
          name: 'New Scorecard',
          key: 'scorecard_123456789',
          accountId: 'account-1',
          sections: jest.fn().mockResolvedValue({ data: [] })
        }
      }),
      list: jest.fn().mockResolvedValue({ data: [] }),
      create: jest.fn().mockResolvedValue({
        data: {
          id: 'new-scorecard-id',
          name: 'New Scorecard',
          key: 'scorecard_123456789',
          accountId: 'account-1'
        }
      })
    },
    ScorecardExampleItem: {
      listByScorecard: jest.fn().mockResolvedValue({
        data: []
      })
    },
    ScorecardSection: {
      list: jest.fn().mockResolvedValue({
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
jest.mock('../scorecards/ScorecardGrid', () => {
  return function MockScorecardGrid({ scorecards, onSelectScorecard, onEdit }: any) {
    return (
      <div className="grid grid-cols-1 @[400px]:grid-cols-1 @[600px]:grid-cols-2 @[900px]:grid-cols-3 gap-4">
        {scorecards.map((scorecard: any) => (
          <div key={scorecard.id}>
            <div data-testid={`scorecard-${scorecard.id}`} onClick={() => onSelectScorecard(scorecard)}>
              <h3>{scorecard.name || 'New Scorecard'}</h3>
              <button onClick={() => onEdit(scorecard)}>Edit</button>
            </div>
          </div>
        ))}
      </div>
    )
  }
})

jest.mock('../scorecards/ScorecardComponent', () => {
  return function MockScorecardComponent({ variant, onClick, score, onEdit }: any) {
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
    // Reset mocks before each test
    jest.clearAllMocks()
    
    // Reset account mocks for each test
    mockAmplifyClient.amplifyClient.Account.list.mockResolvedValue({
      data: [{ id: 'account-1', key: 'call-criteria' }]
    })
    
    // Reset default scorecard list to empty
    mockAmplifyClient.amplifyClient.Scorecard.list.mockResolvedValue({
      data: []
    })
    mockAmplifyClient.amplifyClient.Scorecard.get.mockResolvedValue({
      data: {
        id: 'new-scorecard-id',
        name: 'New Scorecard',
        key: 'scorecard_123456789',
        accountId: 'account-1',
        sections: jest.fn().mockResolvedValue({ data: [] })
      }
    })
    mockAmplifyClient.amplifyClient.Scorecard.create.mockResolvedValue({
      data: {
        id: 'new-scorecard-id',
        name: 'New Scorecard',
        key: 'scorecard_123456789',
        accountId: 'account-1'
      }
    })
    mockAmplifyClient.amplifyClient.ScorecardExampleItem.listByScorecard.mockResolvedValue({
      data: []
    })
    
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
      act(() => {
        render(<ScorecardsComponent />)
      })
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
      
      // Mock the creation flow - after creation, list should include the new scorecard
      mockAmplifyClient.amplifyClient.Scorecard.list
        .mockResolvedValueOnce({ data: [] }) // Initial empty list
        .mockResolvedValue({ 
          data: [{
            id: 'new-scorecard-id',
            name: 'New Scorecard',
            key: 'scorecard_123456789',
            accountId: 'account-1',
            sections: jest.fn().mockResolvedValue({ data: [] })
          }]
        }) // After creation, include the new scorecard with sections method
      
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
      
      // Mock the creation flow
      mockAmplifyClient.amplifyClient.Scorecard.list
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValue({ 
          data: [{
            id: 'new-scorecard-id',
            name: 'New Scorecard',
            key: 'scorecard_123456789',
            accountId: 'account-1',
            sections: jest.fn().mockResolvedValue({ data: [] })
          }]
        })
      
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
        expect(detailView).toHaveTextContent('New Scorecard')
      })
    })

    it('should verify new scorecard appears in the list after creation', async () => {
      const user = userEvent.setup()
      
      // Mock the creation flow - first empty, then with new scorecard after creation
      mockAmplifyClient.amplifyClient.Scorecard.list
        .mockResolvedValueOnce({ data: [] }) // Initial load (empty)
        .mockResolvedValue({ 
          data: [{
            id: 'new-scorecard-id',
            name: 'New Scorecard',
            key: 'scorecard_123456789',
            accountId: 'account-1',
            sections: jest.fn().mockResolvedValue({ data: [] })
          }]
        }) // After creation, always return the new scorecard
      
      render(<ScorecardsComponent />)
      
      await waitFor(() => {
        expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument()
      })

      const newButton = screen.getByRole('button', { name: /new scorecard/i })
      await user.click(newButton)

      await waitFor(() => {
        expect(screen.getByTestId('scorecard-detail')).toBeInTheDocument()
      })

      // The scorecard should appear in the grid after creation
      await waitFor(() => {
        expect(screen.getByTestId('scorecard-new-scorecard-id')).toBeInTheDocument()
      })
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

    it('should select scorecard and show detail view when clicking existing scorecard', async () => {
      const user = userEvent.setup()
      render(<ScorecardsComponent />)
      
      await waitFor(() => {
        expect(screen.getByTestId('scorecard-scorecard-1')).toBeInTheDocument()
      })

      const scorecardCard = screen.getByTestId('scorecard-scorecard-1')
      await user.click(scorecardCard)

      // Should show the detail view for the selected scorecard
      await waitFor(() => {
        expect(screen.getByTestId('scorecard-detail')).toBeInTheDocument()
        expect(screen.getByText('Detail view for scorecard-1')).toBeInTheDocument()
      })
      
      // Verify the detail view specifically contains the scorecard name
      const detailView = screen.getByTestId('scorecard-detail')
      expect(detailView).toHaveTextContent('Test Scorecard')
      
      // Should NOT call get() for just selecting - only for editing
      expect(mockAmplifyClient.amplifyClient.Scorecard.get).not.toHaveBeenCalled()
    })

    it('should handle edit button click and call API with proper error handling', async () => {
      const user = userEvent.setup()
      
      // Mock API error for get() call
      mockAmplifyClient.amplifyClient.Scorecard.get.mockRejectedValue(new Error('API Error'))
      
      render(<ScorecardsComponent />)
      
      await waitFor(() => {
        expect(screen.getByTestId('scorecard-scorecard-1')).toBeInTheDocument()
      })

      // Click the edit button (not the scorecard itself)
      const editButton = screen.getByRole('button', { name: 'Edit' })
      await user.click(editButton)

      // Should call get() when editing (not just selecting)
      await waitFor(() => {
        expect(mockAmplifyClient.amplifyClient.Scorecard.get).toHaveBeenCalledWith({ id: 'scorecard-1' })
      })
    })
  })

  describe('URL Management', () => {
    it('should update URL when creating new scorecard', async () => {
      const user = userEvent.setup()
      
      // Mock the creation flow
      mockAmplifyClient.amplifyClient.Scorecard.list
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValue({ 
          data: [{
            id: 'new-scorecard-id',
            name: 'New Scorecard',
            key: 'scorecard_123456789',
            accountId: 'account-1',
            sections: jest.fn().mockResolvedValue({ data: [] })
          }]
        })
      
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
      expect(window.history.pushState).toHaveBeenCalledWith(null, '', '/lab/scorecards/new-scorecard-id')
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