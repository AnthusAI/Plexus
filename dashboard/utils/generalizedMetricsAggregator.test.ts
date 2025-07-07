import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { generalizedMetricsAggregator, MetricsDataSource } from './generalizedMetricsAggregator';

// Mock the entire amplify-client module
jest.mock('./amplify-client', () => {
  const mockGraphqlMethod = jest.fn();
  const mockClient = {
    graphql: mockGraphqlMethod
  };
  
  return {
    graphqlRequest: jest.fn(),
    getClient: jest.fn(() => mockClient),
    handleGraphQLErrors: jest.fn(),
    amplifyClient: {
      Account: { list: jest.fn() },
      ScoreResult: { list: jest.fn() },
      FeedbackItem: { list: jest.fn() }
    }
  };
});

// Import the mocked functions
import { graphqlRequest, getClient } from './amplify-client';

const mockGraphqlRequest = graphqlRequest as jest.MockedFunction<typeof graphqlRequest>;
const mockGetClient = getClient as jest.MockedFunction<typeof getClient>;

// We'll control the client's graphql method through this reference
let mockGraphqlClientMethod: jest.MockedFunction<any>;

// Mock sessionStorage
const sessionStorageMock = (() => {
  let store: { [key: string]: string } = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, 'sessionStorage', {
  value: sessionStorageMock,
});

describe('GeneralizedMetricsAggregator', () => {
  beforeEach(() => {
    // Clear mocks and session storage before each test
    jest.clearAllMocks();
    sessionStorageMock.clear();
    
    // Get the reference to the mocked graphql method
    const mockClient = mockGetClient();
    mockGraphqlClientMethod = mockClient.graphql as jest.MockedFunction<any>;
  });

  const accountId = 'test-account';
  const now = new Date();
  const last24Hours = new Date(now.getTime() - 24 * 60 * 60 * 1000);

  const mockScoreResults = (count: number, type?: string) => ({
    data: {
      listScoreResultByAccountIdAndUpdatedAt: {
        items: Array.from({ length: count }, (_, i) => ({
          id: `sr-${i}`,
          value: 'Yes',
          updatedAt: new Date().toISOString(),
          type: type || (i % 2 === 0 ? 'prediction' : 'evaluation'),
        })),
      },
    },
  });

  const mockFeedbackItems = (count: number) => ({
    data: {
      listFeedbackItemByAccountIdAndUpdatedAt: {
        items: Array.from({ length: count }, (_, i) => ({
          id: `fi-${i}`,
          isAgreement: i % 2 === 0,
          updatedAt: new Date().toISOString(),
        })),
      },
    },
  });

  describe('fetchScoreResultsData', () => {
    it('should fetch and process score results data correctly', async () => {
      mockGraphqlClientMethod.mockResolvedValue(mockScoreResults(10));

      const source: MetricsDataSource = {
        type: 'scoreResults',
        accountId,
        startTime: last24Hours,
        endTime: now,
      };

      const result = await generalizedMetricsAggregator.getMetrics(source);

      expect(result.count).toBe(10);
      expect(result.sum).toBe(10); // All 'Yes' -> 1
      expect(result.avg).toBe(1);
      expect(mockGraphqlClientMethod).toHaveBeenCalledTimes(1);
    });

    it('should filter score results by type', async () => {
      mockGraphqlClientMethod.mockResolvedValue(mockScoreResults(10));

      const source: MetricsDataSource = {
        type: 'scoreResults',
        accountId,
        startTime: last24Hours,
        endTime: now,
        scoreResultType: 'prediction',
      };

      const result = await generalizedMetricsAggregator.getMetrics(source);

      expect(result.count).toBe(5); // Half are 'prediction'
      expect(result.sum).toBe(5);
      expect(result.avg).toBe(1);
      expect(mockGraphqlClientMethod).toHaveBeenCalledTimes(1);
    });
  });

  describe('fetchFeedbackItemsData', () => {
    it('should fetch and process feedback items data correctly', async () => {
      mockGraphqlClientMethod.mockResolvedValue(mockFeedbackItems(20));

      const source: MetricsDataSource = {
        type: 'feedbackItems',
        accountId,
        startTime: last24Hours,
        endTime: now,
      };

      const result = await generalizedMetricsAggregator.getMetrics(source);

      expect(result.count).toBe(20);
      expect(result.sum).toBe(10); // Half have isAgreement: true
      expect(result.avg).toBe(0.5); // Agreement rate
      expect(mockGraphqlClientMethod).toHaveBeenCalledTimes(1);
    });
  });

  describe('Caching', () => {
    it('should cache results in session storage', async () => {
      mockGraphqlClientMethod.mockResolvedValue(mockScoreResults(5));

      const source: MetricsDataSource = {
        type: 'scoreResults',
        accountId,
        startTime: last24Hours,
        endTime: now,
      };

      // First call - should fetch from API
      await generalizedMetricsAggregator.getMetrics(source);
      expect(mockGraphqlClientMethod).toHaveBeenCalledTimes(1);

      // Second call - should use cache
      await generalizedMetricsAggregator.getMetrics(source);
      expect(mockGraphqlClientMethod).toHaveBeenCalledTimes(1); // No new API call
    });

    it('should not use cache if TTL has expired', async () => {
        mockGraphqlClientMethod.mockResolvedValue(mockScoreResults(5));
      
        const source: MetricsDataSource = {
          type: 'scoreResults',
          accountId,
          startTime: last24Hours,
          endTime: now,
          cacheTTL: 10, // 10 ms TTL
        };
      
        // First call
        await generalizedMetricsAggregator.getMetrics(source);
        expect(mockGraphqlClientMethod).toHaveBeenCalledTimes(1);
      
        // Wait for TTL to expire
        await new Promise(resolve => setTimeout(resolve, 20));
      
        // Second call - should fetch again
        await generalizedMetricsAggregator.getMetrics(source);
        expect(mockGraphqlClientMethod).toHaveBeenCalledTimes(2);
      });
  });

  describe('getComprehensiveMetrics', () => {
    it('should fetch hourly and 24h data and generate chart data', async () => {
        mockGraphqlClientMethod
        .mockResolvedValueOnce(mockScoreResults(2)) // Hourly
        .mockResolvedValueOnce(mockScoreResults(50)) // 24h total
        .mockResolvedValue(mockScoreResults(1)); // Chart buckets

      const source: MetricsDataSource = {
        type: 'scoreResults',
        accountId,
        startTime: last24Hours,
        endTime: now,
      };

      const result = await generalizedMetricsAggregator.getComprehensiveMetrics(source);

      // It will make more calls for the chart data generation
      expect(mockGraphqlClientMethod).toHaveBeenCalled();
      
      expect(result.hourly.count).toBeGreaterThan(0);
      expect(result.total24h.count).toBe(50);
      expect(result.chartData.length).toBeGreaterThan(0);
      expect(result.chartData.length).toBeLessThanOrEqual(24);
    });
  });
}); 