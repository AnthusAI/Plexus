import { render, screen, waitFor } from '@testing-library/react'
import PublicEvaluation from '../page'
import { generateClient } from 'aws-amplify/api'

// Mock the next/navigation module
jest.mock('next/navigation', () => ({
  useParams: () => ({ id: 'test-id' }),
}))

// Mock the aws-amplify/api module
jest.mock('aws-amplify/api', () => ({
  generateClient: jest.fn(),
}))

// Mock the components
jest.mock('@/components/landing/Layout', () => ({
  Layout: ({ children }: { children: React.ReactNode }) => <div data-testid="mock-layout">{children}</div>,
}))

jest.mock('@/components/landing/Footer', () => ({
  Footer: () => <div data-testid="mock-footer">Footer</div>,
}))

jest.mock('@/components/EvaluationTask', () => ({
  EvaluationTask: ({ task }: { task: any }) => (
    <div data-testid="mock-evaluation-task">
      Evaluation Task: {task.id}
    </div>
  ),
}))

describe('PublicEvaluation', () => {
  const mockClient = {
    models: {
      Evaluation: {
        get: jest.fn(),
      },
    },
  }

  beforeEach(() => {
    ;(generateClient as jest.Mock).mockReturnValue(mockClient)
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it('shows loading state initially', () => {
    render(<PublicEvaluation />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('displays evaluation when loaded successfully', async () => {
    const mockEvaluation = {
      id: 'test-id',
      type: 'test-type',
      scorecard: 'test-scorecard',
      score: 'test-score',
      createdAt: '2024-02-21T00:00:00.000Z',
      title: 'Test Evaluation',
      accuracy: 0.95,
      metrics: [],
      processedItems: 100,
      totalItems: 100,
      progress: 100,
      inferences: 100,
      cost: 0,
      status: 'COMPLETED',
      elapsedSeconds: 60,
      estimatedRemainingSeconds: 0,
    }

    mockClient.models.Evaluation.get.mockResolvedValueOnce(mockEvaluation)

    render(<PublicEvaluation />)

    await waitFor(() => {
      expect(screen.getByText(/Test Evaluation/)).toBeInTheDocument()
    })

    expect(screen.getByTestId('mock-evaluation-task')).toBeInTheDocument()
    expect(screen.getByTestId('mock-footer')).toBeInTheDocument()
  })

  it('displays error message when fetch fails', async () => {
    mockClient.models.Evaluation.get.mockRejectedValueOnce(new Error('Failed to fetch'))

    render(<PublicEvaluation />)

    await waitFor(() => {
      expect(screen.getByText('Failed to load evaluation')).toBeInTheDocument()
    })
  })

  it('displays not found message when evaluation is null', async () => {
    mockClient.models.Evaluation.get.mockResolvedValueOnce(null)

    render(<PublicEvaluation />)

    await waitFor(() => {
      expect(screen.getByText('No evaluation found')).toBeInTheDocument()
    })
  })
}) 