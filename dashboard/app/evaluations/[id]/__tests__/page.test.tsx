import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { resizeWindow, mockMatchMedia } from '@/utils/test-utils';

// Mock all the imports before importing the component
jest.mock('next/navigation', () => ({
  useParams: jest.fn(() => ({ id: 'test-evaluation-id' }))
}));

jest.mock('@/components/landing/Layout', () => ({
  Layout: ({ children }: { children: React.ReactNode }) => <div data-testid="mock-layout">{children}</div>
}));

jest.mock('@/components/landing/Footer', () => ({
  Footer: () => <div data-testid="mock-footer">Footer</div>
}));

jest.mock('@/components/EvaluationTask', () => ({
  __esModule: true,
  default: jest.fn(() => <div data-testid="mock-evaluation-task">Evaluation Task</div>)
}));

// Mock the evaluations-dashboard module
jest.mock('@/components/evaluations-dashboard', () => ({
  transformEvaluation: jest.fn(data => data)
}));

// Mock the utils/data-operations module
jest.mock('@/utils/data-operations', () => ({
  getValueFromLazyLoader: jest.fn(() => ({ data: { items: [] } }))
}));

// Mock console methods to reduce noise in test output
const originalConsoleError = console.error;
const originalConsoleLog = console.log;

// Now import the component and its dependencies
import PublicEvaluation, { EvaluationService } from '../page';

describe('PublicEvaluation Component', () => {
  // Create mock evaluation service
  const mockFetchEvaluation = jest.fn();
  const mockEvaluationService = {
    fetchEvaluation: mockFetchEvaluation
  } as unknown as EvaluationService;
  
  beforeEach(() => {
    jest.clearAllMocks();
    mockMatchMedia(); // Set up mock media query for responsive tests
    
    // Silence console logs during tests
    console.error = jest.fn();
    console.log = jest.fn();
  });
  
  afterEach(() => {
    // Restore console methods
    console.error = originalConsoleError;
    console.log = originalConsoleLog;
  });

  test('should show loading state initially', () => {
    // Setup the mock to delay response
    mockFetchEvaluation.mockImplementation(() => new Promise(() => {}));
    
    render(<PublicEvaluation evaluationService={mockEvaluationService} />);
    
    // Check if loading state is shown
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  test('should show error message when API call fails', async () => {
    // Setup the mock to reject with an error
    mockFetchEvaluation.mockRejectedValue(new Error('API Error'));
    
    render(<PublicEvaluation evaluationService={mockEvaluationService} />);
    
    // Wait for the loading state to be replaced with error
    await waitFor(() => {
      expect(screen.getByText('Failed to load evaluation')).toBeInTheDocument();
    });
  });

  test('should show error message when API returns null data', async () => {
    // Setup the mock to reject with an error
    mockFetchEvaluation.mockRejectedValue(new Error('No evaluation found'));
    
    render(<PublicEvaluation evaluationService={mockEvaluationService} />);
    
    // Wait for the loading state to be replaced with error message
    await waitFor(() => {
      expect(screen.getByText('Failed to load evaluation')).toBeInTheDocument();
    });
  });

  test('should render evaluation when API call succeeds', async () => {
    // Mock evaluation data
    const mockEvaluationData = {
      id: 'test-id',
      type: 'TEST',
      accuracy: 85,
      metrics: {
        precision: 80,
        sensitivity: 75,
        specificity: 90
      },
      scorecard: { name: 'Test Scorecard', id: 'scorecard-id' },
      score: { name: 'Test Score', id: 'score-id' },
      processedItems: 80,
      totalItems: 100,
      inferences: 100,
      cost: 0.25,
      status: 'COMPLETED',
      elapsedSeconds: 120,
      estimatedRemainingSeconds: 0,
      startedAt: '2023-01-01T00:00:00.000Z',
      createdAt: '2023-01-01T00:00:00.000Z',
      task: {
        id: 'task-id',
        type: 'EVALUATION',
        status: 'COMPLETED',
        target: 'target',
        command: 'command',
        metadata: {},
        stages: { items: [] }
      }
    };
    
    // Setup the mock to resolve with data
    mockFetchEvaluation.mockResolvedValue(mockEvaluationData);
    
    // Render the component
    render(<PublicEvaluation evaluationService={mockEvaluationService} />);
    
    // Wait for the evaluation to be rendered
    await waitFor(() => {
      // First check that loading is gone
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });
    
    // Check for the heading that appears when evaluation is loaded
    expect(screen.getByText('Evaluation Results')).toBeInTheDocument();
    
    // Check that the evaluation task component is rendered
    expect(screen.getByTestId('mock-evaluation-task')).toBeInTheDocument();
    
    // Verify fetchEvaluation was called with the correct ID
    expect(mockFetchEvaluation).toHaveBeenCalledWith('test-evaluation-id');
  });

  test('should be responsive across different screen sizes', async () => {
    // Mock evaluation data
    const mockEvaluationData = {
      id: 'test-id',
      type: 'TEST',
      accuracy: 85,
      metrics: {
        precision: 80,
        sensitivity: 75,
        specificity: 90
      },
      scorecard: { name: 'Test Scorecard', id: 'scorecard-id' },
      score: { name: 'Test Score', id: 'score-id' },
      processedItems: 80,
      totalItems: 100,
      inferences: 100,
      cost: 0.25,
      status: 'COMPLETED',
      elapsedSeconds: 120,
      estimatedRemainingSeconds: 0,
      startedAt: '2023-01-01T00:00:00.000Z',
      createdAt: '2023-01-01T00:00:00.000Z',
      task: {
        id: 'task-id',
        type: 'EVALUATION',
        status: 'COMPLETED',
        target: 'target',
        command: 'command',
        metadata: {},
        stages: { items: [] }
      }
    };
    
    // Setup the mock to resolve with data
    mockFetchEvaluation.mockResolvedValue(mockEvaluationData);
    
    // Render the component
    render(<PublicEvaluation evaluationService={mockEvaluationService} />);
    
    // Wait for the evaluation to be rendered
    await waitFor(() => {
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });
    
    // Test mobile view
    resizeWindow(375, 812); // iPhone X dimensions
    expect(screen.getByText('Evaluation Results')).toBeInTheDocument();
    
    // Test tablet view
    resizeWindow(768, 1024); // iPad dimensions
    expect(screen.getByText('Evaluation Results')).toBeInTheDocument();
    
    // Test desktop view
    resizeWindow(1920, 1080);
    expect(screen.getByText('Evaluation Results')).toBeInTheDocument();
  });
});
