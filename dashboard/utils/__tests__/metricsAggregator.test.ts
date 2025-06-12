/**
 * Test suite for MetricsAggregatorV2
 * 
 * This test suite validates the V2 metrics aggregator integration with
 * the hierarchical aggregator.
 */

import { getAggregatedMetrics, clearAggregationCache, getCacheStats } from '../metricsAggregator';

// Mock the hierarchical aggregator
jest.mock('../hierarchicalAggregator', () => ({
  hierarchicalAggregator: {
    getAggregatedMetrics: jest.fn(),
    clearCache: jest.fn(),
    getCacheStats: jest.fn()
  }
}));

import { hierarchicalAggregator } from '../hierarchicalAggregator';
const mockHierarchicalAggregator = hierarchicalAggregator as jest.Mocked<typeof hierarchicalAggregator>;

describe('MetricsAggregatorV2', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('getAggregatedMetrics', () => {
    it('should aggregate scoreResults successfully', async () => {
      // Mock the hierarchical aggregator response
      mockHierarchicalAggregator.getAggregatedMetrics.mockResolvedValue({
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T11:00:00Z',
        intervalMinutes: 60,
        count: 100,
        sum: 85.5,
        avg: 0.855
      });

      const startTime = new Date('2024-01-01T10:00:00Z');
      const endTime = new Date('2024-01-01T11:00:00Z');

      const result = await getAggregatedMetrics(
        'test-account',
        'scoreResults',
        startTime,
        endTime,
        'scorecard-123',
        'score-456'
      );

      expect(result).toEqual({
        count: 100,
        cost: 0,
        decisionCount: 0,
        externalAiApiCount: 0,
        cachedAiApiCount: 0,
        errorCount: 0
      });

      expect(mockHierarchicalAggregator.getAggregatedMetrics).toHaveBeenCalledWith({
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:00:00.000Z',
        endTime: '2024-01-01T11:00:00.000Z',
        intervalMinutes: 60,
        scorecardId: 'scorecard-123',
        scoreId: 'score-456'
      });
    });

    it('should aggregate items successfully', async () => {
      // Mock the hierarchical aggregator response
      mockHierarchicalAggregator.getAggregatedMetrics.mockResolvedValue({
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T11:00:00Z',
        intervalMinutes: 60,
        count: 50,
        sum: 50,
        avg: 1
      });

      const startTime = new Date('2024-01-01T10:00:00Z');
      const endTime = new Date('2024-01-01T11:00:00Z');

      const result = await getAggregatedMetrics(
        'test-account',
        'items',
        startTime,
        endTime
      );

      expect(result).toEqual({
        count: 50,
        cost: 0,
        decisionCount: 0,
        externalAiApiCount: 0,
        cachedAiApiCount: 0,
        errorCount: 0
      });

      expect(mockHierarchicalAggregator.getAggregatedMetrics).toHaveBeenCalledWith({
        accountId: 'test-account',
        recordType: 'items',
        startTime: '2024-01-01T10:00:00.000Z',
        endTime: '2024-01-01T11:00:00.000Z',
        intervalMinutes: 60
      });
    });

    it('should handle errors gracefully', async () => {
      mockHierarchicalAggregator.getAggregatedMetrics.mockRejectedValue(
        new Error('GraphQL error')
      );

      const startTime = new Date('2024-01-01T10:00:00Z');
      const endTime = new Date('2024-01-01T11:00:00Z');

      const result = await getAggregatedMetrics(
        'test-account',
        'scoreResults',
        startTime,
        endTime
      );

      expect(result).toEqual({
        count: 0,
        cost: 0,
        decisionCount: 0,
        externalAiApiCount: 0,
        cachedAiApiCount: 0,
        errorCount: 0
      });
    });

    it('should call progress callback', async () => {
      mockHierarchicalAggregator.getAggregatedMetrics.mockResolvedValue({
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T11:00:00Z',
        intervalMinutes: 60,
        count: 50,
        sum: 42.5,
        avg: 0.85
      });

      const startTime = new Date('2024-01-01T10:00:00Z');
      const endTime = new Date('2024-01-01T11:00:00Z');
      const onProgress = jest.fn();

      await getAggregatedMetrics(
        'test-account',
        'scoreResults',
        startTime,
        endTime,
        undefined,
        undefined,
        onProgress
      );

      expect(onProgress).toHaveBeenCalledWith({
        bucketStart: startTime,
        bucketEnd: endTime,
        bucketMetrics: {
          count: 50,
          cost: 0,
          decisionCount: 0,
          externalAiApiCount: 0,
          cachedAiApiCount: 0,
          errorCount: 0
        },
        totalMetrics: {
          count: 50,
          cost: 0,
          decisionCount: 0,
          externalAiApiCount: 0,
          cachedAiApiCount: 0,
          errorCount: 0
        },
        bucketNumber: 1,
        totalBuckets: 1
      });
    });
  });

  describe('clearAggregationCache', () => {
    it('should clear the hierarchical aggregator cache', () => {
      clearAggregationCache();
      expect(mockHierarchicalAggregator.clearCache).toHaveBeenCalled();
    });
  });

  describe('getCacheStats', () => {
    it('should return cache statistics', () => {
      mockHierarchicalAggregator.getCacheStats.mockReturnValue({
        size: 5,
        keys: ['key1', 'key2', 'key3', 'key4', 'key5']
      });

      const stats = getCacheStats();
      
      expect(stats).toEqual({
        size: 5,
        keys: ['key1', 'key2', 'key3', 'key4', 'key5']
      });
      expect(mockHierarchicalAggregator.getCacheStats).toHaveBeenCalled();
    });
  });
}); 