import { handler } from './index';
import { MetricsCalculator } from './metrics-calculator';
import { Context } from 'aws-lambda';

// Mock the MetricsCalculator module
jest.mock('./metrics-calculator');
const MockedMetricsCalculator = MetricsCalculator as jest.MockedClass<typeof MetricsCalculator>;

// Mock console methods
const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation();
const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

describe('Lambda Handler', () => {
  const mockContext: Context = {
    callbackWaitsForEmptyEventLoop: false,
    functionName: 'test-function',
    functionVersion: '1',
    invokedFunctionArn: 'arn:aws:lambda:us-east-1:123456789012:function:test-function',
    memoryLimitInMB: '128',
    awsRequestId: 'test-request-id',
    logGroupName: 'test-log-group',
    logStreamName: 'test-log-stream',
    getRemainingTimeInMillis: () => 30000,
    done: jest.fn(),
    fail: jest.fn(),
    succeed: jest.fn()
  };

  beforeEach(() => {
    jest.clearAllMocks();
    // Set up environment variables
    process.env.PLEXUS_API_URL = 'https://api.example.com/graphql';
    process.env.PLEXUS_API_KEY = 'test-api-key';
  });

  afterEach(() => {
    // Clean up environment variables
    delete process.env.PLEXUS_API_URL;
    delete process.env.PLEXUS_API_KEY;
  });

  it('should successfully calculate metrics for valid input', async () => {
    const mockItemsMetrics = {
      itemsTotal24h: 2280,
      itemsPerHour: 100,
      chartData: [{ time: '2023-01-01T00:00:00.000Z', items: 100 }]
    };

    const mockScoreResultsMetrics = {
      scoreResultsTotal24h: 4560,
      scoreResultsPerHour: 200,
      chartData: [{ time: '2023-01-01T00:00:00.000Z', scoreResults: 200 }]
    };

    // Mock implementation for getItemsSummary and getScoreResultsSummary
    const mockGetItemsSummary = jest.fn().mockResolvedValue(mockItemsMetrics);
    const mockGetScoreResultsSummary = jest.fn().mockResolvedValue(mockScoreResultsMetrics);

    MockedMetricsCalculator.mockImplementation((endpoint, apiKey, cacheMinutes, metricType) => {
      if (metricType === 'items') {
        return { getItemsSummary: mockGetItemsSummary } as any;
      }
      if (metricType === 'score_results') {
        return { getScoreResultsSummary: mockGetScoreResultsSummary } as any;
      }
      return {} as any;
    });

    const event = {
      arguments: {
        accountId: 'test-account-id',
        hours: 24
      }
    };

    const result = await handler(event, mockContext, jest.fn());

    expect(MockedMetricsCalculator).toHaveBeenCalledWith(
      'https://api.example.com/graphql',
      'test-api-key',
      15,
      'items'
    );
    
    expect(MockedMetricsCalculator).toHaveBeenCalledWith(
      'https://api.example.com/graphql',
      'test-api-key',
      15,
      'score_results'
    );

    expect(mockGetItemsSummary).toHaveBeenCalledWith('test-account-id', 24);
    expect(mockGetScoreResultsSummary).toHaveBeenCalledWith('test-account-id', 24);

    expect(result).toEqual({
      accountId: 'test-account-id',
      hours: 24,
      timestamp: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/),
      totalItems: mockItemsMetrics.itemsTotal24h,
      itemsLast24Hours: mockItemsMetrics.itemsTotal24h,
      itemsLastHour: mockItemsMetrics.itemsPerHour,
      itemsHourlyBreakdown: mockItemsMetrics.chartData,
      totalScoreResults: mockScoreResultsMetrics.scoreResultsTotal24h,
      scoreResultsLast24Hours: mockScoreResultsMetrics.scoreResultsTotal24h,
      scoreResultsLastHour: mockScoreResultsMetrics.scoreResultsPerHour,
      scoreResultsHourlyBreakdown: mockScoreResultsMetrics.chartData
    });

    expect(consoleLogSpy).toHaveBeenCalledWith('Event:', expect.any(String));
    expect(consoleLogSpy).toHaveBeenCalledWith('Result:', expect.any(String));
  });

  it('should use default hours when not provided', async () => {
    const mockGetItemsSummary = jest.fn().mockResolvedValue({
      itemsTotal24h: 0,
      itemsPerHour: 0,
      chartData: []
    });
    const mockGetScoreResultsSummary = jest.fn().mockResolvedValue({
      scoreResultsTotal24h: 0,
      scoreResultsPerHour: 0,
      chartData: []
    });

    MockedMetricsCalculator.mockImplementation((endpoint, apiKey, cacheMinutes, metricType) => {
      if (metricType === 'items') {
        return { getItemsSummary: mockGetItemsSummary } as any;
      }
      if (metricType === 'score_results') {
        return { getScoreResultsSummary: mockGetScoreResultsSummary } as any;
      }
      return {} as any;
    });

    const event = {
      arguments: {
        accountId: 'test-account-id'
        // hours not provided
      }
    };

    await handler(event, mockContext, jest.fn());

    expect(mockGetItemsSummary).toHaveBeenCalledWith('test-account-id', 24);
    expect(mockGetScoreResultsSummary).toHaveBeenCalledWith('test-account-id', 24);
  });

  it('should throw error when accountId is missing', async () => {
    const event = {
      arguments: {
        // accountId missing
        hours: 24
      }
    };

    await expect(handler(event, mockContext, jest.fn())).rejects.toThrow('accountId is required');
    expect(consoleErrorSpy).toHaveBeenCalledWith('Error calculating metrics:', expect.any(Error));
  });

  it('should throw error when environment variables are missing', async () => {
    delete process.env.PLEXUS_API_URL;
    delete process.env.PLEXUS_API_KEY;

    const event = {
      arguments: {
        accountId: 'test-account-id',
        hours: 24
      }
    };

    await expect(handler(event, mockContext, jest.fn())).rejects.toThrow(
      'PLEXUS_API_URL and PLEXUS_API_KEY environment variables must be set.'
    );
  });
  
  it('should handle MetricsCalculator errors', async () => {
    const mockGetItemsSummary = jest.fn().mockRejectedValue(new Error('GraphQL error'));
    const mockGetScoreResultsSummary = jest.fn().mockResolvedValue({
      scoreResultsTotal24h: 0,
      scoreResultsPerHour: 0,
      chartData: [],
    });

    MockedMetricsCalculator.mockImplementation((endpoint, apiKey, cacheMinutes, metricType) => {
      if (metricType === 'items') {
        return { getItemsSummary: mockGetItemsSummary } as any;
      }
      if (metricType === 'score_results') {
        return { getScoreResultsSummary: mockGetScoreResultsSummary } as any;
      }
      return {} as any;
    });

    const event = {
      arguments: {
        accountId: 'test-account-id',
        hours: 24
      }
    };

    await expect(handler(event, mockContext, jest.fn())).rejects.toThrow('GraphQL error');
    expect(consoleErrorSpy).toHaveBeenCalledWith('Error calculating metrics:', expect.any(Error));
  });
}); 