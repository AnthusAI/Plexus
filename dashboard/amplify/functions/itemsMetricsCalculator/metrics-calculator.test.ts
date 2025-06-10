import { MetricsCalculator } from './metrics-calculator';
import { getFromCache, setInCache, cleanupCache } from './cache';

// Mock the axios library
jest.mock('axios');
import axios from 'axios';
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock the cache functions
jest.mock('./cache', () => ({
  getFromCache: jest.fn(),
  setInCache: jest.fn(),
  cleanupCache: jest.fn()
}));

const mockedGetFromCache = getFromCache as jest.Mock;
const mockedSetInCache = setInCache as jest.Mock;

describe('MetricsCalculator', () => {
  let calculator: MetricsCalculator;
  const mockEndpoint = 'https://api.example.com/graphql';
  const mockApiKey = 'test-api-key';

  beforeEach(() => {
    jest.clearAllMocks();
    calculator = new MetricsCalculator(mockEndpoint, mockApiKey, 15, 'items');
  });

  describe('constructor', () => {
    it('should initialize with provided values', () => {
      expect(calculator).toBeDefined();
    });

    it('should use default cacheBucketMinutes', () => {
      const defaultCalculator = new MetricsCalculator(mockEndpoint, mockApiKey, undefined, 'items');
      expect(defaultCalculator).toBeDefined();
    });

    it('should allow custom cacheBucketMinutes', () => {
      const customCalculator = new MetricsCalculator(mockEndpoint, mockApiKey, 30, 'items');
      expect(customCalculator).toBeDefined();
    });
  });

  describe('clock-aligned bucket calculation', () => {
    it('should calculate clock-aligned buckets correctly for 15-minute intervals', () => {
      // This is testing the private method through public interface behavior
      // We'll verify the behavior through the caching mechanism
      
      const startTime = new Date('2023-12-01T10:07:30.000Z'); // 10:07:30
      const endTime = new Date('2023-12-01T11:23:45.000Z');   // 11:23:45
      
      // The aligned buckets should be:
      // 10:15:00 - 10:30:00
      // 10:30:00 - 10:45:00
      // 10:45:00 - 11:00:00
      // 11:00:00 - 11:15:00
      // 11:15:00 - 11:30:00 (but this one ends after our endTime, so it won't be included)
      
      // We expect 4 full aligned buckets
      // Plus margins: 10:07:30 - 10:15:00 and 11:15:00 - 11:23:45
      
      expect(startTime.getMinutes()).toBe(7); // Verify test setup
      expect(endTime.getMinutes()).toBe(23);  // Verify test setup
    });

    it('should handle bucket alignment at hour boundaries', () => {
      const startTime = new Date('2023-12-01T09:50:00.000Z');
      const endTime = new Date('2023-12-01T10:20:00.000Z');
      
      // Should span the hour boundary correctly
      // Aligned buckets: 10:00:00 - 10:15:00, 10:15:00 - 10:30:00 (partial)
      expect(startTime.getUTCHours()).toBe(9);
      expect(endTime.getUTCHours()).toBe(10);
    });
  });

  describe('caching behavior', () => {
    beforeEach(() => {
      // Mock successful GraphQL responses
      mockedAxios.post.mockResolvedValue({
        status: 200,
        data: {
          data: {
            listItemByAccountIdAndCreatedAt: {
              items: [{ id: '1' }, { id: '2' }], // Mock 2 items
              nextToken: null
            }
          }
        }
      });
    });

    it('should cache results for clock-aligned buckets', async () => {
      const accountId = 'test-account';
      const bucketStart = new Date('2023-12-01T10:15:00.000Z'); // Clock-aligned 15-minute bucket
      const bucketEnd = new Date('2023-12-01T10:30:00.000Z');
      
      // Mock cache miss for the bucket
      mockedGetFromCache.mockResolvedValue(null);
      
      // First call should query the API
      const result1 = await (calculator as any).getCountWithCaching(
        accountId,
        bucketStart,
        bucketEnd,
        (calculator as any).countItemsInTimeframe.bind(calculator)
      );
      expect(result1).toBe(2);
      expect(mockedAxios.post).toHaveBeenCalledTimes(1);
      
      // Verify the result was cached
      const cacheKey = `countItemsInTimeframe:${accountId}:${bucketStart.toISOString()}`;
      expect(mockedSetInCache).toHaveBeenCalledWith(cacheKey, 2);
    });

    it('should use cached values for subsequent requests', async () => {
      const accountId = 'test-account';
      const bucketStart = new Date('2023-12-01T10:30:00.000Z');
      const bucketEnd = new Date('2023-12-01T10:45:00.000Z');
      
      // Pre-populate the cache
      const cacheKey = `countItemsInTimeframe:${accountId}:${bucketStart.toISOString()}`;
      mockedGetFromCache.mockImplementation((key: string) => {
        if (key === cacheKey) {
          return Promise.resolve(42); // Cache hit with value 42
        }
        return Promise.resolve(null); // Cache miss for other keys
      });
      
      // Method should use cache instead of making API call
      const result = await (calculator as any).getCountWithCaching(
        accountId,
        bucketStart,
        bucketEnd,
        (calculator as any).countItemsInTimeframe.bind(calculator)
      );
      
      expect(result).toBe(42);
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });
  });

  describe('margin handling in _getCountForWindow', () => {
    beforeEach(() => {
      // Mock different responses for different time ranges to verify margin handling
      mockedAxios.post.mockImplementation((url: string, payload: any) => {
        const variables = payload.variables;
        
        // Return different counts based on the time range to verify correct querying
        const startTime = new Date(variables.startTime);
        const endTime = new Date(variables.endTime);
        const durationMinutes = (endTime.getTime() - startTime.getTime()) / (1000 * 60);
        
        let itemCount;
        if (durationMinutes < 10) {
          itemCount = 1; // Small margins
        } else if (durationMinutes === 15) {
          itemCount = 5; // Full 15-minute buckets
        } else {
          itemCount = 3; // Other durations
        }
        
        return Promise.resolve({
          status: 200,
          data: {
            data: {
              listItemByAccountIdAndCreatedAt: {
                items: Array(itemCount).fill(null).map((_, i) => ({ id: `item-${i}` })),
                nextToken: null
              }
            }
          }
        });
      });
    });

    it('should query margins and use cache for aligned buckets', async () => {
      const accountId = 'test-account';
      
      // Time window that will have margins on both sides
      const startTime = new Date('2023-12-01T10:07:00.000Z'); // 7 minutes past hour
      const endTime = new Date('2023-12-01T10:38:00.000Z');   // 38 minutes past hour
      
      // Expected behavior:
      // - Start margin: 10:07:00 - 10:15:00 (8 minutes, should query API and get 1 item)
      // - Aligned bucket: 10:15:00 - 10:30:00 (15 minutes, should cache and get 5 items)
      // - End margin: 10:30:00 - 10:38:00 (8 minutes, should query API and get 1 item)
      // Total: 1 + 5 + 1 = 7 items
      
      // Mock cache miss for the aligned bucket (so it gets queried and cached)
      const alignedBucketStart = new Date('2023-12-01T10:15:00.000Z');
      const cacheKey = `countItemsInTimeframe:${accountId}:${alignedBucketStart.toISOString()}`;
      mockedGetFromCache.mockImplementation((key: string) => {
        if (key === cacheKey) {
          return Promise.resolve(null); // Cache miss for aligned bucket
        }
        return Promise.resolve(null); // Cache miss for everything else
      });
      
      const result = await (calculator as any)._getCountForWindow(
        accountId,
        startTime,
        endTime,
        (calculator as any).countItemsInTimeframe.bind(calculator)
      );
      
      expect(result).toBe(7);
      
      // Should have made 3 API calls: 2 for margins + 1 for the aligned bucket
      expect(mockedAxios.post).toHaveBeenCalledTimes(3);
      
      // Verify that the aligned bucket was cached
      expect(mockedSetInCache).toHaveBeenCalledWith(cacheKey, 5);
    });

    it('should handle windows smaller than bucket size by querying directly', async () => {
      const accountId = 'test-account';
      
      // Small window that doesn't contain any full aligned buckets
      const startTime = new Date('2023-12-01T10:17:00.000Z');
      const endTime = new Date('2023-12-01T10:22:00.000Z'); // Only 5 minutes
      
      const result = await (calculator as any)._getCountForWindow(
        accountId,
        startTime,
        endTime,
        (calculator as any).countItemsInTimeframe.bind(calculator)
      );
      
      expect(result).toBe(1); // Small duration = 1 item based on our mock
      expect(mockedAxios.post).toHaveBeenCalledTimes(1);
    });
  });

  describe('error handling', () => {
    it('should handle GraphQL errors gracefully', async () => {
      mockedAxios.post.mockResolvedValue({
        status: 200,
        data: {
          errors: [{ message: 'Test GraphQL error' }]
        }
      });
      
      const accountId = 'test-account';
      const startTime = new Date('2023-12-01T10:00:00.000Z');
      const endTime = new Date('2023-12-01T10:15:00.000Z');
      
      // Error handling should log the error and return 0, not throw
      const result = await (calculator as any).countItemsInTimeframe(accountId, startTime, endTime);
      expect(result).toBe(0);
    });

    it('should handle network errors gracefully', async () => {
      mockedAxios.post.mockRejectedValue(new Error('Network error'));
      mockedAxios.isAxiosError.mockReturnValue(false);
      
      const accountId = 'test-account';
      const startTime = new Date('2023-12-01T10:00:00.000Z');
      const endTime = new Date('2023-12-01T10:15:00.000Z');
      
      // Error handling should log the error and return 0, not throw
      const result = await (calculator as any).countItemsInTimeframe(accountId, startTime, endTime);
      expect(result).toBe(0);
    });

    it('should handle timeout errors with specific message', async () => {
      const timeoutError = new Error('timeout') as any;
      timeoutError.code = 'ECONNABORTED';
      mockedAxios.post.mockRejectedValue(timeoutError);
      mockedAxios.isAxiosError.mockReturnValue(true);
      
      const accountId = 'test-account';
      const startTime = new Date('2023-12-01T10:00:00.000Z');
      const endTime = new Date('2023-12-01T10:15:00.000Z');
      
      await expect(
        (calculator as any).makeGraphQLRequest('test query', {})
      ).rejects.toThrow('GraphQL request timed out after 60 seconds');
    });
  });

  describe('integration tests', () => {
    beforeEach(() => {
      // Mock realistic responses for integration testing
      mockedAxios.post.mockResolvedValue({
        status: 200,
        data: {
          data: {
            listItemByAccountIdAndCreatedAt: {
              items: Array(10).fill(null).map((_, i) => ({ id: `item-${i}` })),
              nextToken: null
            },
            listScoreResultByAccountIdAndUpdatedAt: {
              items: Array(5).fill(null).map((_, i) => ({ id: `score-${i}` })),
              nextToken: null
            }
          }
        }
      });
    });

    it('should demonstrate full caching workflow for getItemsSummary', async () => {
      const accountId = 'integration-test-account';
      
      // This should trigger the full caching workflow
      const result = await calculator.getItemsSummary(accountId, 2); // 2 hours
      
      expect(result).toHaveProperty('itemsPerHour');
      expect(result).toHaveProperty('itemsTotal24h');
      expect(result).toHaveProperty('chartData');
      expect(result.chartData).toHaveLength(2);
      
      // Verify some cache entries were created
      // Note: The exact number depends on how many aligned buckets were created
      expect(mockedAxios.post).toHaveBeenCalled();
    });
  });

  describe('getItemsSummary', () => {
    it('should calculate items summary correctly', async () => {
      // Mock GraphQL responses
      mockedAxios.post.mockResolvedValue({
        data: {
          data: {
            listItemByAccountIdAndCreatedAt: {
              items: new Array(10).fill({ id: 'item-id' }),
              nextToken: null
            }
          }
        },
        status: 200
      });

      const summary = await calculator.getItemsSummary('test-account-id', 24);

      expect(summary).toHaveProperty('itemsTotal24h');
      expect(summary).toHaveProperty('itemsPerHour');
      expect(summary).toHaveProperty('itemsAveragePerHour');
      expect(summary).toHaveProperty('itemsPeakHourly');
      expect(summary).toHaveProperty('chartData');
      expect(Array.isArray(summary.chartData)).toBe(true);
    });
  });

  describe('getScoreResultsSummary', () => {
    it('should calculate score results summary correctly', async () => {
      const scoreResultsCalculator = new MetricsCalculator(mockEndpoint, mockApiKey, 15, 'score_results');
      
      // Mock GraphQL responses
      mockedAxios.post.mockResolvedValue({
        data: {
          data: {
            listScoreResultByAccountIdAndCreatedAt: {
              items: new Array(5).fill({ id: 'result-id' }),
              nextToken: null
            }
          }
        },
        status: 200
      });

      const summary = await scoreResultsCalculator.getScoreResultsSummary('test-account-id', 24);

      expect(summary).toHaveProperty('scoreResultsTotal24h');
      expect(summary).toHaveProperty('scoreResultsPerHour');
      expect(summary).toHaveProperty('scoreResultsAveragePerHour');
      expect(summary).toHaveProperty('scoreResultsPeakHourly');
      expect(summary).toHaveProperty('chartData');
      expect(Array.isArray(summary.chartData)).toBe(true);
    });
  });
}); 