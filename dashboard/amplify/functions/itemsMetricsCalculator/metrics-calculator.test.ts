import axios from 'axios';
import { MetricsCalculator } from './metrics-calculator';
import { SQLiteCache } from './cache';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock the cache
jest.mock('./cache');
const MockedSQLiteCache = SQLiteCache as jest.MockedClass<typeof SQLiteCache>;

describe('MetricsCalculator', () => {
  let calculator: MetricsCalculator;
  const mockEndpoint = 'https://api.example.com/graphql';
  const mockApiKey = 'test-api-key';
  const mockAccountId = 'test-account-id';
  let mockCacheInstance: jest.Mocked<SQLiteCache>;

  beforeEach(() => {
    // Clear all mocks and reset them
    mockedAxios.post.mockClear();
    MockedSQLiteCache.mockClear();

    // Create a new mock instance for the cache before each test
    mockCacheInstance = {
      get: jest.fn(),
      set: jest.fn(),
      createTable: jest.fn(),
      close: jest.fn(),
    } as any;
    MockedSQLiteCache.mockImplementation(() => mockCacheInstance);

    calculator = new MetricsCalculator(mockEndpoint, mockApiKey);
    
    // Mock Date to ensure consistent test results
    jest.useFakeTimers();
    jest.setSystemTime(new Date('2024-01-15T12:00:00Z'));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('constructor', () => {
    it('should initialize with correct properties and default bucket size', () => {
      // Calculator is already initialized in beforeEach
      expect((calculator as any).graphqlEndpoint).toBe(mockEndpoint);
      expect((calculator as any).apiKey).toBe(mockApiKey);
      expect((calculator as any).cacheBucketMinutes).toBe(15);
      expect(mockCacheInstance.createTable).toHaveBeenCalledTimes(1);
    });

    it('should initialize with a custom bucket size', () => {
      calculator = new MetricsCalculator(mockEndpoint, mockApiKey, 5);
      expect((calculator as any).cacheBucketMinutes).toBe(5);
    });
  });

  describe('makeGraphQLRequest', () => {
    it('should make a successful GraphQL request', async () => {
      const mockResponse = {
        data: {
          data: {
            listItemByAccountIdAndCreatedAt: {
              items: [{ id: '1' }, { id: '2' }],
              nextToken: null,
            },
          },
        },
      };

      mockedAxios.post.mockResolvedValueOnce(mockResponse);

      const query = 'query { test }';
      const variables = { test: 'value' };

      const result = await (calculator as any).makeGraphQLRequest(query, variables);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        mockEndpoint,
        { query, variables },
        {
          headers: {
            'x-api-key': mockApiKey,
            'Content-Type': 'application/json',
          },
          timeout: 60000,
        }
      );

      expect(result).toEqual(mockResponse.data.data);
    });

    it('should throw error on GraphQL errors', async () => {
      const mockResponse = {
        data: {
          errors: [{ message: 'GraphQL Error 1' }, { message: 'GraphQL Error 2' }],
        },
      };

      mockedAxios.post.mockResolvedValueOnce(mockResponse);

      const query = 'query { test }';
      const variables = { test: 'value' };

      await expect(
        (calculator as any).makeGraphQLRequest(query, variables)
      ).rejects.toThrow('GraphQL errors: GraphQL Error 1, GraphQL Error 2');
    });

    it('should handle axios specific errors', async () => {
      const axiosError = new Error('Request failed');
      Object.assign(axiosError, {
        isAxiosError: true,
        response: {
          status: 500,
          data: 'Internal Server Error',
        },
      });

      mockedAxios.post.mockRejectedValueOnce(axiosError);
      (axios.isAxiosError as unknown as jest.Mock).mockReturnValue(true);

      await expect(
        (calculator as any).makeGraphQLRequest('query', {})
      ).rejects.toThrow('GraphQL request failed with status 500: Internal Server Error');
    });

    it('should throw error on network failure', async () => {
      mockedAxios.post.mockRejectedValueOnce(new Error('Network error'));
      (axios.isAxiosError as unknown as jest.Mock).mockReturnValue(false);

      const query = 'query { test }';
      const variables = { test: 'value' };

      await expect(
        (calculator as any).makeGraphQLRequest(query, variables)
      ).rejects.toThrow('Network error');
    });
  });
  
  describe('countItemsInTimeframe', () => {
    it('should count items with single page', async () => {
      const mockResponse = {
        data: {
          data: {
            listItemByAccountIdAndCreatedAt: {
              items: [{ id: '1' }, { id: '2' }, { id: '3' }],
              nextToken: null,
            },
          },
        },
      };

      mockedAxios.post.mockResolvedValueOnce(mockResponse);

      const startTime = new Date('2024-01-15T11:00:00Z');
      const endTime = new Date('2024-01-15T12:00:00Z');

      const count = await (calculator as any).countItemsInTimeframe(
        mockAccountId,
        startTime,
        endTime
      );

      expect(count).toBe(3);
      expect(mockedAxios.post).toHaveBeenCalledTimes(1);
    });

    it('should handle pagination', async () => {
      const mockResponses = [
        {
          data: {
            data: {
              listItemByAccountIdAndCreatedAt: {
                items: new Array(1000).fill({ id: '1' }),
                nextToken: 'token1',
              },
            },
          },
        },
        {
          data: {
            data: {
              listItemByAccountIdAndCreatedAt: {
                items: new Array(500).fill({ id: '2' }),
                nextToken: null,
              },
            },
          },
        },
      ];

      mockedAxios.post
        .mockResolvedValueOnce(mockResponses[0])
        .mockResolvedValueOnce(mockResponses[1]);

      const startTime = new Date('2024-01-15T11:00:00Z');
      const endTime = new Date('2024-01-15T12:00:00Z');

      const count = await (calculator as any).countItemsInTimeframe(
        mockAccountId,
        startTime,
        endTime
      );

      expect(count).toBe(1500);
      expect(mockedAxios.post).toHaveBeenCalledTimes(2);
    });

    it('should handle max pages limit', async () => {
      const mockResponse = {
        data: {
          data: {
            listItemByAccountIdAndCreatedAt: {
              items: new Array(1000).fill({ id: '1' }),
              nextToken: 'endless-token',
            },
          },
        },
      };

      // Mock 500 pages all returning nextToken
      for (let i = 0; i < 501; i++) {
        mockedAxios.post.mockResolvedValueOnce(mockResponse);
      }

      const startTime = new Date('2024-01-15T11:00:00Z');
      const endTime = new Date('2024-01-15T12:00:00Z');

      const count = await (calculator as any).countItemsInTimeframe(
        mockAccountId,
        startTime,
        endTime
      );

      expect(count).toBe(500000); // 500 pages * 1000 items
      expect(mockedAxios.post).toHaveBeenCalledTimes(500);
    });
  });

  describe('getClockAlignedBuckets', () => {
    beforeEach(() => {
      calculator = new MetricsCalculator(mockEndpoint, mockApiKey, 15);
    });

    it('should return correctly aligned 15-minute buckets', () => {
      const startTime = new Date('2024-01-15T10:07:00Z');
      const endTime = new Date('2024-01-15T11:20:00Z');
      const buckets = (calculator as any).getClockAlignedBuckets(startTime, endTime);

      expect(buckets).toHaveLength(5);
      // First bucket should start at 10:00
      expect(buckets[0].toISOString()).toBe('2024-01-15T10:00:00.000Z');
      // Last bucket should start at 11:15
      expect(buckets[4].toISOString()).toBe('2024-01-15T11:15:00.000Z');
    });

    it('should handle a start time that is already aligned', () => {
      const startTime = new Date('2024-01-15T10:15:00Z');
      const endTime = new Date('2024-01-15T10:50:00Z');
      const buckets = (calculator as any).getClockAlignedBuckets(startTime, endTime);

      expect(buckets).toHaveLength(3);
      expect(buckets[0].toISOString()).toBe('2024-01-15T10:15:00.000Z');
      expect(buckets[1].toISOString()).toBe('2024-01-15T10:30:00.000Z');
      expect(buckets[2].toISOString()).toBe('2024-01-15T10:45:00.000Z');
    });

    it('should return a single bucket if the range is smaller than the bucket size', () => {
      const startTime = new Date('2024-01-15T10:15:00Z');
      const endTime = new Date('2024-01-15T10:20:00Z');
      const buckets = (calculator as any).getClockAlignedBuckets(startTime, endTime);

      expect(buckets).toHaveLength(1);
      expect(buckets[0].toISOString()).toBe('2024-01-15T10:15:00.000Z');
    });
  });

  describe('getCountWithCaching', () => {
    it('should handle cache hits and misses correctly', async () => {
      const mockCountFunction = jest.fn();
      const startTime = new Date('2024-01-15T10:00:00Z');
      const endTime = new Date('2024-01-15T10:30:00Z');

      // Setup: one bucket is a cache hit, one is a miss
      const bucket1Start = new Date('2024-01-15T10:00:00.000Z');
      const cacheKey1 = (calculator as any)._getCacheKey('items', mockAccountId, bucket1Start);
      (mockCacheInstance.get as jest.Mock).mockImplementation(async (key: string) => key === cacheKey1 ? 100 : null);

      const bucket2Start = new Date('2024-01-15T10:15:00.000Z');
      const cacheKey2 = (calculator as any)._getCacheKey('items', mockAccountId, bucket2Start);
      mockCountFunction.mockResolvedValue(50); // API call result for the miss

      const total = await (calculator as any).getCountWithCaching(
        mockAccountId, startTime, endTime, mockCountFunction, 'items'
      );

      expect(total).toBe(150);
      expect(mockCacheInstance.get).toHaveBeenCalledTimes(2);
      expect(mockCountFunction).toHaveBeenCalledTimes(1); // Only called for the cache miss
      
      const setCall = (mockCacheInstance.set as jest.Mock).mock.calls[0];
      expect(setCall[0]).toBe(cacheKey2); // Correct key for the cache miss
      expect(setCall[1]).toBe(50);       // Correct value
    });
  });

  describe('getItemsSummary', () => {
    it('should calculate items summary for 24 hours with caching', async () => {
      // Mock getCountWithCaching to return a predictable value
      const getCountSpy = jest.spyOn(calculator as any, 'getCountWithCaching').mockResolvedValue(100);
      
      const result = await calculator.getItemsSummary(mockAccountId, 24);

      expect(getCountSpy).toHaveBeenCalledTimes(24); // Called for each hour
      expect(result.chartData).toHaveLength(24);
      expect(result.itemsTotal24h).toBe(2400); // 24 hours * 100 items/hr
      expect(result.itemsAveragePerHour).toBe(100);
      expect(result.itemsPeakHourly).toBe(100);

      // Restore original method
      getCountSpy.mockRestore();
    });
  });

  describe('getScoreResultsSummary', () => {
    it('should calculate score results summary for 24 hours with caching', async () => {
      const getCountSpy = jest.spyOn(calculator as any, 'getCountWithCaching').mockResolvedValue(50);
      
      const result = await calculator.getScoreResultsSummary(mockAccountId, 24);

      expect(getCountSpy).toHaveBeenCalledTimes(24);
      expect(result.chartData).toHaveLength(24);
      expect(result.scoreResultsTotal24h).toBe(1200); // 24 hours * 50 results/hr
      expect(result.scoreResultsAveragePerHour).toBe(50);
      expect(result.scoreResultsPeakHourly).toBe(50);
      
      getCountSpy.mockRestore();
    });
  });
}); 