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
      itemsPerHour: 100,
      itemsAveragePerHour: 95,
      itemsPeakHourly: 150,
      itemsTotal24h: 2280,
      chartData: []
    };

    const mockScoreResultsMetrics = {
      scoreResultsPerHour: 200,
      scoreResultsAveragePerHour: 190,
      scoreResultsPeakHourly: 250,
      scoreResultsTotal24h: 4560,
      chartData: []
    };

    const mockCalculatorInstance = {
      getItemsSummary: jest.fn().mockResolvedValue(mockItemsMetrics),
      getScoreResultsSummary: jest.fn().mockResolvedValue(mockScoreResultsMetrics)
    };

    MockedMetricsCalculator.mockImplementation(() => mockCalculatorInstance as any);

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
      15
    );

    expect(mockCalculatorInstance.getItemsSummary).toHaveBeenCalledWith('test-account-id', 24);
    expect(mockCalculatorInstance.getScoreResultsSummary).toHaveBeenCalledWith('test-account-id', 24);

    expect(result).toEqual({
      ...mockItemsMetrics,
      ...mockScoreResultsMetrics,
      accountId: 'test-account-id',
      hours: 24,
      timestamp: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
    });

    expect(consoleLogSpy).toHaveBeenCalledWith('Event:', expect.any(String));
    expect(consoleLogSpy).toHaveBeenCalledWith('Result:', expect.any(String));
  });

  it('should use default hours when not provided', async () => {
    const mockCalculatorInstance = {
      getItemsSummary: jest.fn().mockResolvedValue({
        itemsPerHour: 0,
        itemsAveragePerHour: 0,
        itemsPeakHourly: 0,
        itemsTotal24h: 0,
        chartData: []
      }),
      getScoreResultsSummary: jest.fn().mockResolvedValue({
        scoreResultsPerHour: 0,
        scoreResultsAveragePerHour: 0,
        scoreResultsPeakHourly: 0,
        scoreResultsTotal24h: 0,
        chartData: []
      })
    };

    MockedMetricsCalculator.mockImplementation(() => mockCalculatorInstance as any);

    const event = {
      arguments: {
        accountId: 'test-account-id'
        // hours not provided
      }
    };

    await handler(event, mockContext, jest.fn());

    expect(mockCalculatorInstance.getItemsSummary).toHaveBeenCalledWith('test-account-id', 24);
    expect(mockCalculatorInstance.getScoreResultsSummary).toHaveBeenCalledWith('test-account-id', 24);
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
      'GraphQL endpoint and API key environment variables must be set'
    );
  });

  it('should handle missing PLEXUS_API_URL', async () => {
    delete process.env.PLEXUS_API_URL;

    const event = {
      arguments: {
        accountId: 'test-account-id'
      }
    };

    await expect(handler(event, mockContext, jest.fn())).rejects.toThrow(
      'GraphQL endpoint and API key environment variables must be set'
    );
  });

  it('should handle missing PLEXUS_API_KEY', async () => {
    delete process.env.PLEXUS_API_KEY;

    const event = {
      arguments: {
        accountId: 'test-account-id'
      }
    };

    await expect(handler(event, mockContext, jest.fn())).rejects.toThrow(
      'GraphQL endpoint and API key environment variables must be set'
    );
  });

  it('should handle empty arguments', async () => {
    const event = {
      // arguments not provided
    };

    await expect(handler(event, mockContext, jest.fn())).rejects.toThrow('accountId is required');
  });

  it('should handle MetricsCalculator errors', async () => {
    const mockCalculatorInstance = {
      getItemsSummary: jest.fn().mockRejectedValue(new Error('GraphQL error')),
      getScoreResultsSummary: jest.fn().mockResolvedValue({})
    };

    MockedMetricsCalculator.mockImplementation(() => mockCalculatorInstance as any);

    const event = {
      arguments: {
        accountId: 'test-account-id',
        hours: 24
      }
    };

    await expect(handler(event, mockContext, jest.fn())).rejects.toThrow('GraphQL error');
    expect(consoleErrorSpy).toHaveBeenCalledWith('Error calculating metrics:', expect.any(Error));
  });

  it('should execute both metric calculations in parallel', async () => {
    let itemsResolve: any;
    let scoreResultsResolve: any;

    const itemsPromise = new Promise((resolve) => {
      itemsResolve = resolve;
    });

    const scoreResultsPromise = new Promise((resolve) => {
      scoreResultsResolve = resolve;
    });

    const mockCalculatorInstance = {
      getItemsSummary: jest.fn().mockReturnValue(itemsPromise),
      getScoreResultsSummary: jest.fn().mockReturnValue(scoreResultsPromise)
    };

    MockedMetricsCalculator.mockImplementation(() => mockCalculatorInstance as any);

    const event = {
      arguments: {
        accountId: 'test-account-id',
        hours: 24
      }
    };

    // Start the handler but don't await it yet
    const handlerPromise = handler(event, mockContext, jest.fn());

    // Both methods should have been called
    expect(mockCalculatorInstance.getItemsSummary).toHaveBeenCalled();
    expect(mockCalculatorInstance.getScoreResultsSummary).toHaveBeenCalled();

    // Resolve both promises
    itemsResolve({
      itemsPerHour: 100,
      itemsAveragePerHour: 95,
      itemsPeakHourly: 150,
      itemsTotal24h: 2280,
      chartData: []
    });

    scoreResultsResolve({
      scoreResultsPerHour: 200,
      scoreResultsAveragePerHour: 190,
      scoreResultsPeakHourly: 250,
      scoreResultsTotal24h: 4560,
      chartData: []
    });

    // Now await the handler
    const result = await handlerPromise;

    expect(result).toHaveProperty('itemsPerHour', 100);
    expect(result).toHaveProperty('scoreResultsPerHour', 200);
  });

  it('should include timestamp in ISO format', async () => {
    const mockCalculatorInstance = {
      getItemsSummary: jest.fn().mockResolvedValue({
        itemsPerHour: 0,
        itemsAveragePerHour: 0,
        itemsPeakHourly: 0,
        itemsTotal24h: 0,
        chartData: []
      }),
      getScoreResultsSummary: jest.fn().mockResolvedValue({
        scoreResultsPerHour: 0,
        scoreResultsAveragePerHour: 0,
        scoreResultsPeakHourly: 0,
        scoreResultsTotal24h: 0,
        chartData: []
      })
    };

    MockedMetricsCalculator.mockImplementation(() => mockCalculatorInstance as any);

    const event = {
      arguments: {
        accountId: 'test-account-id'
      }
    };

    const beforeTime = new Date().toISOString();
    const result = await handler(event, mockContext, jest.fn());
    const afterTime = new Date().toISOString();

    expect(result.timestamp).toBeDefined();
    expect(new Date(result.timestamp).toISOString()).toBe(result.timestamp);
    expect(result.timestamp >= beforeTime).toBe(true);
    expect(result.timestamp <= afterTime).toBe(true);
  });
}); 