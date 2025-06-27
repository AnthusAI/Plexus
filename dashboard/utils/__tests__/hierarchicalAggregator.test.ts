/**
 * Test suite for HierarchicalAggregator
 * 
 * This test suite validates the hierarchical aggregation logic to ensure:
 * 1. No double-counting occurs
 * 2. Cache behavior is correct
 * 3. Different time intervals work properly
 * 4. Edge cases are handled
 */

import { HierarchicalAggregator, AggregationRequest, AggregationBucket } from '../hierarchicalAggregator';

// Mock the amplify-client module
jest.mock('../amplify-client', () => ({
  graphqlRequest: jest.fn(),
  amplifyClient: {}
}));

import { graphqlRequest } from '../amplify-client';
const mockGraphqlRequest = graphqlRequest as jest.MockedFunction<typeof graphqlRequest>;

describe('HierarchicalAggregator', () => {
  let aggregator: HierarchicalAggregator;

  beforeEach(() => {
    aggregator = new HierarchicalAggregator();
    jest.clearAllMocks();
  });

  afterEach(() => {
    aggregator.clearCache();
  });

  describe('Time Period Deconstruction Tests', () => {
    describe('Last Hour Scenarios (60 minutes)', () => {
      it('should break down 60-minute request into four 15-minute sub-buckets', async () => {
        // Mock responses for 4 sub-buckets (15 minutes each)
        const mockResponses = [
          { data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }] } } },
          { data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'No', updatedAt: '2024-01-01T10:15:00Z' }] } } },
          { data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-01T10:30:00Z' }] } } },
          { data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-01T10:45:00Z' }] } } }
        ];

        mockGraphqlRequest
          .mockResolvedValueOnce(mockResponses[0])
          .mockResolvedValueOnce(mockResponses[1])
          .mockResolvedValueOnce(mockResponses[2])
          .mockResolvedValueOnce(mockResponses[3]);

        const request: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T10:00:00Z',
          endTime: '2024-01-01T11:00:00Z',
          intervalMinutes: 60
        };

        const result = await aggregator.getAggregatedMetrics(request);

        // Verify correct aggregation
        expect(result.count).toBe(4);
        expect(result.sum).toBe(3); // Yes=1, No=0, Yes=1, Yes=1
        expect(result.avg).toBe(3/4);

        // Verify exactly 4 GraphQL calls (one per 15-minute sub-bucket)
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(4);

        // Verify the sub-bucket time ranges are correct
        const calls = mockGraphqlRequest.mock.calls;
        expect(calls[0][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T10:00:00.000Z',
          endTime: '2024-01-01T10:15:00.000Z'
        });
        expect(calls[1][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T10:15:00.000Z',
          endTime: '2024-01-01T10:30:00.000Z'
        });
        expect(calls[2][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T10:30:00.000Z',
          endTime: '2024-01-01T10:45:00.000Z'
        });
        expect(calls[3][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T10:45:00.000Z',
          endTime: '2024-01-01T11:00:00.000Z'
        });
      });

      it('should cache 15-minute sub-buckets but not the 60-minute parent', async () => {
        // Mock sub-bucket responses
        mockGraphqlRequest.mockResolvedValue({
          data: {
            listScoreResultByAccountIdAndUpdatedAt: {
              items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }]
            }
          }
        });

        const request: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T10:00:00Z',
          endTime: '2024-01-01T11:00:00Z',
          intervalMinutes: 60
        };

        // First call - should make 4 GraphQL calls
        await aggregator.getAggregatedMetrics(request);
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(4);

        // Clear mock and make second call
        mockGraphqlRequest.mockClear();
        await aggregator.getAggregatedMetrics(request);

        // Second call should use cached sub-buckets (no GraphQL calls)
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(0);

        // Verify cache contains 4 entries (the 15-minute sub-buckets)
        const stats = aggregator.getCacheStats();
        expect(stats.size).toBe(4);
      });
    });

    describe('Last Day Scenarios (1440 minutes)', () => {
      it('should break down 24-hour request into 96 fifteen-minute sub-buckets', async () => {
        // Mock response for all sub-buckets
        mockGraphqlRequest.mockResolvedValue({
          data: {
            listScoreResultByAccountIdAndUpdatedAt: {
              items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }]
            }
          }
        });

        const request: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T00:00:00Z',
          endTime: '2024-01-02T00:00:00Z',
          intervalMinutes: 1440 // 24 hours
        };

        const result = await aggregator.getAggregatedMetrics(request);

        // Should make 96 GraphQL calls (24 hours * 4 fifteen-minute buckets per hour)
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(96);

        // Verify aggregation
        expect(result.count).toBe(96); // One item per sub-bucket
        expect(result.sum).toBe(96);   // All Yes values
        expect(result.intervalMinutes).toBe(1440);
      });

      it('should handle partial day requests correctly', async () => {
        // Mock response
        mockGraphqlRequest.mockResolvedValue({
          data: {
            listScoreResultByAccountIdAndUpdatedAt: {
              items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }]
            }
          }
        });

        // Request 6 hours (360 minutes)
        const request: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T08:00:00Z',
          endTime: '2024-01-01T14:00:00Z',
          intervalMinutes: 360
        };

        await aggregator.getAggregatedMetrics(request);

        // Should make 24 GraphQL calls (6 hours * 4 fifteen-minute buckets per hour)
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(24);

        // Verify first and last sub-bucket time ranges
        const calls = mockGraphqlRequest.mock.calls;
        expect(calls[0][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T08:00:00.000Z',
          endTime: '2024-01-01T08:15:00.000Z'
        });
        expect(calls[23][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T13:45:00.000Z',
          endTime: '2024-01-01T14:00:00.000Z'
        });
      });
    });

    describe('Medium Duration Scenarios (30-60 minutes)', () => {
      it('should break down 45-minute request into three 15-minute sub-buckets', async () => {
        // Mock responses for 3 sub-buckets
        const mockResponses = [
          { data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }] } } },
          { data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'No', updatedAt: '2024-01-01T10:15:00Z' }] } } },
          { data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-01T10:30:00Z' }] } } }
        ];

        mockGraphqlRequest
          .mockResolvedValueOnce(mockResponses[0])
          .mockResolvedValueOnce(mockResponses[1])
          .mockResolvedValueOnce(mockResponses[2]);

        const request: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T10:00:00Z',
          endTime: '2024-01-01T10:45:00Z',
          intervalMinutes: 45
        };

        const result = await aggregator.getAggregatedMetrics(request);

        expect(result.count).toBe(3);
        expect(result.sum).toBe(2); // Yes=1, No=0, Yes=1
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(3);
      });

      it('should break down 30-minute request into two 15-minute sub-buckets', async () => {
        mockGraphqlRequest
          .mockResolvedValueOnce({
            data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }] } }
          })
          .mockResolvedValueOnce({
            data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'No', updatedAt: '2024-01-01T10:15:00Z' }] } }
          });

        const request: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T10:00:00Z',
          endTime: '2024-01-01T10:30:00Z',
          intervalMinutes: 30
        };

        const result = await aggregator.getAggregatedMetrics(request);

        expect(result.count).toBe(2);
        expect(result.sum).toBe(1); // Yes=1, No=0
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(2);
      });
    });

    describe('Small Duration Scenarios (≤15 minutes)', () => {
      it('should perform direct aggregation for 15-minute request', async () => {
        mockGraphqlRequest.mockResolvedValueOnce({
          data: {
            listScoreResultByAccountIdAndUpdatedAt: {
              items: [
                { value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' },
                { value: 'No', updatedAt: '2024-01-01T10:05:00Z' },
                { value: 'Yes', updatedAt: '2024-01-01T10:10:00Z' }
              ]
            }
          }
        });

        const request: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T10:00:00Z',
          endTime: '2024-01-01T10:15:00Z',
          intervalMinutes: 15
        };

        const result = await aggregator.getAggregatedMetrics(request);

        expect(result.count).toBe(3);
        expect(result.sum).toBe(2);
        // Should make only 1 GraphQL call (direct aggregation)
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(1);
      });

      it('should perform direct aggregation for 5-minute request', async () => {
        mockGraphqlRequest.mockResolvedValueOnce({
          data: {
            listScoreResultByAccountIdAndUpdatedAt: {
              items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }]
            }
          }
        });

        const request: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T10:00:00Z',
          endTime: '2024-01-01T10:05:00Z',
          intervalMinutes: 5
        };

        const result = await aggregator.getAggregatedMetrics(request);

        expect(result.count).toBe(1);
        expect(result.sum).toBe(1);
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(1);
      });
    });

    describe('Edge Cases in Time Period Deconstruction', () => {
      it('should handle non-aligned time boundaries correctly', async () => {
        // Request that doesn't align with 15-minute boundaries
        mockGraphqlRequest
          .mockResolvedValueOnce({
            data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-01T10:07:00Z' }] } }
          })
          .mockResolvedValueOnce({
            data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'No', updatedAt: '2024-01-01T10:22:00Z' }] } }
          })
          .mockResolvedValueOnce({
            data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-01T10:37:00Z' }] } }
          });

        const request: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T10:07:00Z', // Non-aligned start
          endTime: '2024-01-01T10:52:00Z',   // Non-aligned end
          intervalMinutes: 45
        };

        const result = await aggregator.getAggregatedMetrics(request);

        expect(result.count).toBe(3);
        expect(result.sum).toBe(2);
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(3);

        // Verify the sub-bucket boundaries are correct
        const calls = mockGraphqlRequest.mock.calls;
        expect(calls[0][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T10:07:00.000Z',
          endTime: '2024-01-01T10:22:00.000Z' // 15 minutes from start
        });
        expect(calls[1][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T10:22:00.000Z',
          endTime: '2024-01-01T10:37:00.000Z' // Next 15 minutes
        });
        expect(calls[2][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T10:37:00.000Z',
          endTime: '2024-01-01T10:52:00.000Z' // Final segment (15 minutes)
        });
      });

      it('should handle requests that span midnight correctly', async () => {
        // Mock responses for buckets spanning midnight
        mockGraphqlRequest
          .mockResolvedValueOnce({
            data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-01T23:45:00Z' }] } }
          })
          .mockResolvedValueOnce({
            data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'No', updatedAt: '2024-01-02T00:00:00Z' }] } }
          })
          .mockResolvedValueOnce({
            data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-02T00:15:00Z' }] } }
          })
          .mockResolvedValueOnce({
            data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-02T00:30:00Z' }] } }
          });

        const request: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T23:45:00Z',
          endTime: '2024-01-02T00:45:00Z',
          intervalMinutes: 60
        };

        const result = await aggregator.getAggregatedMetrics(request);

        expect(result.count).toBe(4);
        expect(result.sum).toBe(3); // Yes=1, No=0, Yes=1, Yes=1
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(4);

        // Verify midnight boundary is handled correctly
        const calls = mockGraphqlRequest.mock.calls;
        expect(calls[0][1].startTime).toBe('2024-01-01T23:45:00.000Z');
        expect(calls[0][1].endTime).toBe('2024-01-02T00:00:00.000Z');
        expect(calls[1][1].startTime).toBe('2024-01-02T00:00:00.000Z');
        expect(calls[1][1].endTime).toBe('2024-01-02T00:15:00.000Z');
      });
    });

    describe('Cache Efficiency in Time Period Deconstruction', () => {
      it('should reuse cached sub-buckets across overlapping requests', async () => {
        // Mock response for sub-buckets
        mockGraphqlRequest.mockResolvedValue({
          data: {
            listScoreResultByAccountIdAndUpdatedAt: {
              items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }]
            }
          }
        });

        // First request: 10:00-11:00 (60 minutes)
        const request1: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T10:00:00Z',
          endTime: '2024-01-01T11:00:00Z',
          intervalMinutes: 60
        };

        await aggregator.getAggregatedMetrics(request1);
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(4); // 4 sub-buckets

        // Clear mock for second request
        mockGraphqlRequest.mockClear();

        // Second request: 10:30-11:30 (60 minutes, overlaps with first)
        const request2: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T10:30:00Z',
          endTime: '2024-01-01T11:30:00Z',
          intervalMinutes: 60
        };

        await aggregator.getAggregatedMetrics(request2);

        // Should only make 2 new GraphQL calls for the non-overlapping sub-buckets
        // (11:00-11:15 and 11:15-11:30), while reusing cached buckets for 10:30-11:00
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(2);

        // Verify cache contains 6 entries total (4 from first + 2 new from second)
        const stats = aggregator.getCacheStats();
        expect(stats.size).toBe(6);
      });
    });

    describe('Complex Multi-Level Bucket Breakdown', () => {
      it('should use every bucket size in a complex hierarchical scenario', async () => {
        // This test creates a scenario that forces the system to use:
        // 1. 15-minute sub-buckets (for the main 98-minute request)
        // 2. 5-minute sub-buckets (for some 16-29 minute intermediate buckets)  
        // 3. Direct aggregation (for ≤15 minute buckets)
        
        // Request: 1 hour 38 minutes starting 2 minutes past the hour
        // 10:02:00 to 11:40:00 = 98 minutes
        // This will break down as follows:
        // - Main request (98 min) → 15-minute sub-buckets
        // - Some sub-buckets will be partial (< 15 min) → direct aggregation
        // - We'll create a scenario where some intermediate requests are 16-29 min → 5-minute sub-buckets

        const mockData = {
          data: {
            listScoreResultByAccountIdAndUpdatedAt: {
              items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }]
            }
          }
        };

        // Mock all GraphQL calls to return consistent data
        mockGraphqlRequest.mockResolvedValue(mockData);

        // Main request: 10:02:00 to 11:40:00 (98 minutes)
        const mainRequest: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T10:02:00Z',
          endTime: '2024-01-01T11:40:00Z',
          intervalMinutes: 98
        };

        const result = await aggregator.getAggregatedMetrics(mainRequest);

        // The 98-minute request should break down into 15-minute sub-buckets:
        // 10:02-10:17 (15 min), 10:17-10:32 (15 min), 10:32-10:47 (15 min), 
        // 10:47-11:02 (15 min), 11:02-11:17 (15 min), 11:17-11:32 (15 min), 
        // 11:32-11:40 (8 min - partial)
        
        // Expected: 7 GraphQL calls for the 15-minute breakdown
        const initialCallCount = mockGraphqlRequest.mock.calls.length;
        expect(initialCallCount).toBe(7);

        // Verify the breakdown includes both full 15-minute buckets and a partial bucket
        const calls = mockGraphqlRequest.mock.calls;
        
        // First bucket: 10:02-10:17 (15 minutes)
        expect(calls[0][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T10:02:00.000Z',
          endTime: '2024-01-01T10:17:00.000Z'
        });

        // Last bucket: 11:32-11:40 (8 minutes - partial, direct aggregation)
        expect(calls[6][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T11:32:00.000Z',
          endTime: '2024-01-01T11:40:00.000Z'
        });

        // Clear mock and create a request that will force 5-minute sub-buckets
        mockGraphqlRequest.mockClear();
        mockGraphqlRequest.mockResolvedValue(mockData);

        // Request a 23-minute window that will use 5-minute sub-buckets
        // 10:05:00 to 10:28:00 (23 minutes)
        const mediumRequest: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T10:05:00Z',
          endTime: '2024-01-01T10:28:00Z',
          intervalMinutes: 23
        };

        await aggregator.getAggregatedMetrics(mediumRequest);

        // The 23-minute request should break down into 5-minute sub-buckets:
        // 10:05-10:10 (5 min), 10:10-10:15 (5 min), 10:15-10:20 (5 min),
        // 10:20-10:25 (5 min), 10:25-10:28 (3 min - partial)
        
        const mediumCallCount = mockGraphqlRequest.mock.calls.length;
        expect(mediumCallCount).toBe(5);

        // Verify 5-minute breakdown
        const mediumCalls = mockGraphqlRequest.mock.calls;
        expect(mediumCalls[0][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T10:05:00.000Z',
          endTime: '2024-01-01T10:10:00.000Z'
        });
        expect(mediumCalls[1][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T10:10:00.000Z',
          endTime: '2024-01-01T10:15:00.000Z'
        });

        // Last bucket should be partial (3 minutes - direct aggregation)
        expect(mediumCalls[4][1]).toEqual({
          accountId: 'test-account',
          startTime: '2024-01-01T10:25:00.000Z',
          endTime: '2024-01-01T10:28:00.000Z'
        });

        // Clear mock and test direct aggregation (≤15 minutes)
        mockGraphqlRequest.mockClear();
        mockGraphqlRequest.mockResolvedValue(mockData);

        // Request a 12-minute window (direct aggregation)
        const smallRequest: AggregationRequest = {
          accountId: 'test-account',
          recordType: 'scoreResults',
          startTime: '2024-01-01T10:15:00Z',
          endTime: '2024-01-01T10:27:00Z',
          intervalMinutes: 12
        };

        await aggregator.getAggregatedMetrics(smallRequest);

        // Should make exactly 1 GraphQL call (direct aggregation)
        expect(mockGraphqlRequest).toHaveBeenCalledTimes(1);

        // Verify all results are properly aggregated
        expect(result.count).toBe(7); // 7 sub-buckets from main request
        expect(result.intervalMinutes).toBe(98);

        // Verify cache contains entries for all the different bucket sizes
        const finalStats = aggregator.getCacheStats();
        expect(finalStats.size).toBeGreaterThan(10); // Should have many cached entries
      });

      it('should demonstrate bucket size decision logic with precise intervals', async () => {
        // This test explicitly demonstrates the bucket size decision points
        const mockData = {
          data: {
            listScoreResultByAccountIdAndUpdatedAt: {
              items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }]
            }
          }
        };

        mockGraphqlRequest.mockResolvedValue(mockData);

        // Test each bucket size threshold
        const testCases = [
          { minutes: 15, expectedCalls: 1, description: '15 minutes - direct aggregation' },
          { minutes: 16, expectedCalls: 4, description: '16 minutes - 5-minute sub-buckets (16/5 = 3.2 → 4 buckets)' },
          { minutes: 25, expectedCalls: 5, description: '25 minutes - 5-minute sub-buckets (25/5 = 5 buckets)' },
          { minutes: 29, expectedCalls: 6, description: '29 minutes - 5-minute sub-buckets (29/5 = 5.8 → 6 buckets)' },
          { minutes: 30, expectedCalls: 2, description: '30 minutes - 15-minute sub-buckets (30/15 = 2 buckets)' },
          { minutes: 45, expectedCalls: 3, description: '45 minutes - 15-minute sub-buckets (45/15 = 3 buckets)' },
          { minutes: 60, expectedCalls: 4, description: '60 minutes - 15-minute sub-buckets (60/15 = 4 buckets)' },
          { minutes: 90, expectedCalls: 6, description: '90 minutes - 15-minute sub-buckets (90/15 = 6 buckets)' }
        ];

        for (const testCase of testCases) {
          // Clear cache and mock between test cases to ensure independence
          aggregator.clearCache();
          mockGraphqlRequest.mockClear();

          const request: AggregationRequest = {
            accountId: 'test-account',
            recordType: 'scoreResults',
            startTime: '2024-01-01T10:00:00Z',
            endTime: new Date(new Date('2024-01-01T10:00:00Z').getTime() + testCase.minutes * 60 * 1000).toISOString(),
            intervalMinutes: testCase.minutes
          };

          await aggregator.getAggregatedMetrics(request);

          // Debug output to understand what's happening
          if (mockGraphqlRequest.mock.calls.length !== testCase.expectedCalls) {
            console.log(`DEBUG: ${testCase.minutes} minutes - Expected: ${testCase.expectedCalls}, Actual: ${mockGraphqlRequest.mock.calls.length}`);
            console.log('GraphQL calls made:', mockGraphqlRequest.mock.calls.map(call => ({
              startTime: call[1].startTime,
              endTime: call[1].endTime
            })));
          }

          expect(mockGraphqlRequest).toHaveBeenCalledTimes(testCase.expectedCalls);
          console.log(`✓ ${testCase.description}: ${mockGraphqlRequest.mock.calls.length} calls`);
        }
      });
    });
  });

  describe('Direct Aggregation (≤15 minutes)', () => {
    it('should perform direct aggregation for small intervals', async () => {
      // Mock raw data response
      mockGraphqlRequest.mockResolvedValueOnce({
        data: {
          listScoreResultByAccountIdAndUpdatedAt: {
            items: [
              { value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' },
              { value: 'No', updatedAt: '2024-01-01T10:05:00Z' },
              { value: 'Yes', updatedAt: '2024-01-01T10:10:00Z' }
            ]
          }
        }
      });

      const request: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T10:15:00Z',
        intervalMinutes: 15
      };

      const result = await aggregator.getAggregatedMetrics(request);

      expect(result).toEqual({
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T10:15:00Z',
        intervalMinutes: 15,
        count: 3,
        sum: 2, // Yes=1, No=0, Yes=1
        avg: 2/3
      });

      expect(mockGraphqlRequest).toHaveBeenCalledTimes(1);
    });

    it('should cache direct aggregation results', async () => {
      mockGraphqlRequest.mockResolvedValueOnce({
        data: {
          listScoreResultByAccountIdAndUpdatedAt: {
            items: [
              { value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }
            ]
          }
        }
      });

      const request: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T10:05:00Z',
        intervalMinutes: 5
      };

      // First call
      await aggregator.getAggregatedMetrics(request);
      
      // Second call should use cache
      await aggregator.getAggregatedMetrics(request);

      expect(mockGraphqlRequest).toHaveBeenCalledTimes(1);
    });
  });

  describe('Hierarchical Aggregation (>15 minutes)', () => {
    it('should break down 60-minute intervals into 15-minute sub-buckets', async () => {
      // Mock responses for 4 sub-buckets (15 minutes each)
      const mockResponses = [
        { data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }] } } },
        { data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'No', updatedAt: '2024-01-01T10:15:00Z' }, { value: 'Yes', updatedAt: '2024-01-01T10:20:00Z' }] } } },
        { data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'Yes', updatedAt: '2024-01-01T10:30:00Z' }] } } },
        { data: { listScoreResultByAccountIdAndUpdatedAt: { items: [{ value: 'No', updatedAt: '2024-01-01T10:45:00Z' }] } } }
      ];

      mockGraphqlRequest
        .mockResolvedValueOnce(mockResponses[0])
        .mockResolvedValueOnce(mockResponses[1])
        .mockResolvedValueOnce(mockResponses[2])
        .mockResolvedValueOnce(mockResponses[3]);

      const request: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T11:00:00Z',
        intervalMinutes: 60
      };

      const result = await aggregator.getAggregatedMetrics(request);

      expect(result).toEqual({
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T11:00:00Z',
        intervalMinutes: 60,
        count: 5, // Total items across all sub-buckets
        sum: 3,   // Yes=1, No=0, Yes=1, Yes=1, No=0
        avg: 3/5
      });

      // Should call GraphQL 4 times (once for each 15-minute sub-bucket)
      expect(mockGraphqlRequest).toHaveBeenCalledTimes(4);
    });

    it('should not cache hierarchical aggregation results', async () => {
      // Mock sub-bucket responses
      mockGraphqlRequest
        .mockResolvedValue({
          data: {
            listScoreResultByAccountIdAndUpdatedAt: {
              items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }]
            }
          }
        });

      const request: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T11:00:00Z',
        intervalMinutes: 60
      };

      // First call
      await aggregator.getAggregatedMetrics(request);
      
      // Reset mock call count
      mockGraphqlRequest.mockClear();
      
      // Second call should NOT use cache for the 60-minute bucket
      // but SHOULD use cache for the 15-minute sub-buckets
      await aggregator.getAggregatedMetrics(request);

      // Should not call GraphQL again because sub-buckets are cached
      expect(mockGraphqlRequest).toHaveBeenCalledTimes(0);
    });
  });

  describe('Cache Validation', () => {
    it('should reject suspicious cached values', async () => {
      // Mock a response that would create a suspicious value
      mockGraphqlRequest.mockResolvedValueOnce({
        data: {
          listScoreResultByAccountIdAndUpdatedAt: {
            items: Array(200000).fill({ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' })
          }
        }
      });

      const request: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T10:05:00Z',
        intervalMinutes: 5
      };

      const result = await aggregator.getAggregatedMetrics(request);

      // Should still return the result but not cache it
      expect(result.count).toBe(200000);
      
      // Clear the mock and try again - should call GraphQL again (not cached)
      mockGraphqlRequest.mockClear();
      mockGraphqlRequest.mockResolvedValueOnce({
        data: {
          listScoreResultByAccountIdAndUpdatedAt: {
            items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }]
          }
        }
      });

      await aggregator.getAggregatedMetrics(request);
      expect(mockGraphqlRequest).toHaveBeenCalledTimes(1);
    });
  });

  describe('Score Value Parsing', () => {
    it('should correctly parse different score value formats', async () => {
      mockGraphqlRequest.mockResolvedValueOnce({
        data: {
          listScoreResultByAccountIdAndUpdatedAt: {
            items: [
              { value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' },
              { value: 'No', updatedAt: '2024-01-01T10:01:00Z' },
              { value: '85%', updatedAt: '2024-01-01T10:02:00Z' },
              { value: '0.75', updatedAt: '2024-01-01T10:03:00Z' },
              { value: 'invalid', updatedAt: '2024-01-01T10:04:00Z' }
            ]
          }
        }
      });

      const request: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T10:05:00Z',
        intervalMinutes: 5
      };

      const result = await aggregator.getAggregatedMetrics(request);

      expect(result.count).toBe(5); // All items counted
      expect(result.sum).toBe(1 + 0 + 0.85 + 0.75); // Yes=1, No=0, 85%=0.85, 0.75=0.75, invalid=null (excluded from sum)
      expect(result.avg).toBe((1 + 0 + 0.85 + 0.75) / 4); // Average of valid numeric values only
    });
  });

  describe('Error Handling', () => {
    it('should return empty bucket on GraphQL error', async () => {
      mockGraphqlRequest.mockRejectedValueOnce(new Error('GraphQL error'));

      const request: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T10:05:00Z',
        intervalMinutes: 5
      };

      const result = await aggregator.getAggregatedMetrics(request);

      expect(result).toEqual({
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T10:05:00Z',
        intervalMinutes: 5,
        count: 0,
        sum: 0,
        avg: 0
      });
    });
  });

  describe('No Double-Counting Scenarios', () => {
    it('should not double-count when same data is requested multiple times', async () => {
      // Mock the same data for multiple calls
      const mockData = {
        data: {
          listScoreResultByAccountIdAndUpdatedAt: {
            items: [
              { value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' },
              { value: 'No', updatedAt: '2024-01-01T10:05:00Z' }
            ]
          }
        }
      };

      mockGraphqlRequest.mockResolvedValue(mockData);

      const request: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T10:15:00Z',
        intervalMinutes: 15
      };

      // Call multiple times
      const result1 = await aggregator.getAggregatedMetrics(request);
      const result2 = await aggregator.getAggregatedMetrics(request);
      const result3 = await aggregator.getAggregatedMetrics(request);

      // All results should be identical
      expect(result1).toEqual(result2);
      expect(result2).toEqual(result3);
      
      // Should only call GraphQL once (cached after first call)
      expect(mockGraphqlRequest).toHaveBeenCalledTimes(1);
    });

    it('should handle overlapping time ranges correctly', async () => {
      // Mock different data for different time ranges
      mockGraphqlRequest
        .mockResolvedValueOnce({
          data: {
            listScoreResultByAccountIdAndUpdatedAt: {
              items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }]
            }
          }
        })
        .mockResolvedValueOnce({
          data: {
            listScoreResultByAccountIdAndUpdatedAt: {
              items: [
                { value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' },
                { value: 'No', updatedAt: '2024-01-01T10:10:00Z' }
              ]
            }
          }
        });

      // First request: 10:00-10:05
      const request1: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T10:05:00Z',
        intervalMinutes: 5
      };

      // Second request: 10:00-10:15 (overlaps with first)
      const request2: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T10:15:00Z',
        intervalMinutes: 15
      };

      const result1 = await aggregator.getAggregatedMetrics(request1);
      const result2 = await aggregator.getAggregatedMetrics(request2);

      expect(result1.count).toBe(1);
      expect(result1.sum).toBe(1);
      
      expect(result2.count).toBe(2);
      expect(result2.sum).toBe(1); // Yes=1, No=0
    });
  });

  describe('Cache Statistics', () => {
    it('should provide accurate cache statistics', async () => {
      mockGraphqlRequest.mockResolvedValue({
        data: {
          listScoreResultByAccountIdAndUpdatedAt: {
            items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }]
          }
        }
      });

      // Make a few requests to populate cache
      await aggregator.getAggregatedMetrics({
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:00:00Z',
        endTime: '2024-01-01T10:05:00Z',
        intervalMinutes: 5
      });

      await aggregator.getAggregatedMetrics({
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: '2024-01-01T10:05:00Z',
        endTime: '2024-01-01T10:10:00Z',
        intervalMinutes: 5
      });

      const stats = aggregator.getCacheStats();
      expect(stats.size).toBe(2);
      expect(stats.keys).toHaveLength(2);
    });
  });

  describe('DynamoDB Throttling Handling', () => {
    it('should retry on DynamoDB throttling errors with exponential backoff', async () => {
      const startTime = new Date('2024-01-01T10:00:00Z');
      const endTime = new Date('2024-01-01T10:15:00Z');
      
      const request: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: startTime.toISOString(),
        endTime: endTime.toISOString(),
        intervalMinutes: 15
      };

      // Mock a DynamoDB throttling error
      const throttlingError = {
        message: 'Throughput exceeds the current capacity for one or more global secondary indexes. DynamoDB is automatically scaling your index so please try again shortly.',
        errors: [{
          errorType: 'DynamoDB:DynamoDbException',
          message: 'Throughput exceeds the current capacity'
        }]
      };

      let callCount = 0;
      
      // Mock to fail twice with throttling, then succeed
      mockGraphqlRequest.mockImplementation(() => {
        callCount++;
        if (callCount <= 2) {
          throw throttlingError;
        }
        return Promise.resolve({
          data: {
            listScoreResultByAccountIdAndUpdatedAt: {
              items: [
                { value: '85', updatedAt: '2024-01-01T10:05:00Z' },
                { value: '92', updatedAt: '2024-01-01T10:10:00Z' }
              ]
            }
          }
        });
      });

      // Mock the sleep function to avoid actual delays
      const originalSleep = (aggregator as any).sleep;
      (aggregator as any).sleep = jest.fn().mockResolvedValue(undefined);

      const result = await aggregator.getAggregatedMetrics(request);
      
      // Should have succeeded after retries
      expect(result.count).toBe(2);
      expect(result.sum).toBe(177); // 85 + 92
      expect(callCount).toBe(3); // Failed twice, succeeded on third attempt

      // Restore original functions
      (aggregator as any).sleep = originalSleep;
      // Clear mock
      mockGraphqlRequest.mockClear();
    });

    it('should return empty bucket after max retries on persistent throttling', async () => {
      const startTime = new Date('2024-01-01T10:00:00Z');
      const endTime = new Date('2024-01-01T10:15:00Z');
      
      const request: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: startTime.toISOString(),
        endTime: endTime.toISOString(),
        intervalMinutes: 15
      };

      // Mock persistent DynamoDB throttling error
      const throttlingError = {
        message: 'Throughput exceeds the current capacity for one or more global secondary indexes. DynamoDB is automatically scaling your index so please try again shortly.',
        errors: [{
          errorType: 'DynamoDB:DynamoDbException',
          message: 'Throughput exceeds the current capacity'
        }]
      };

      let callCount = 0;
      
      // Mock to always fail with throttling
      mockGraphqlRequest.mockImplementation(() => {
        callCount++;
        throw throttlingError;
      });

      // Mock the sleep function to avoid actual delays
      const originalSleep = (aggregator as any).sleep;
      (aggregator as any).sleep = jest.fn().mockResolvedValue(undefined);

      const result = await aggregator.getAggregatedMetrics(request);
       
      // Should return empty bucket after all retries exhausted
      expect(result.count).toBe(0);
      expect(result.sum).toBe(0);
      expect(callCount).toBe(4); // Initial attempt + 3 retries

      // Restore original functions
      (aggregator as any).sleep = originalSleep;
      // Clear mock
      mockGraphqlRequest.mockClear();
    }, 10000);

    it('should not retry on non-throttling errors', async () => {
      const startTime = new Date('2024-01-01T10:00:00Z');
      const endTime = new Date('2024-01-01T10:15:00Z');
      
      const request: AggregationRequest = {
        accountId: 'test-account',
        recordType: 'scoreResults',
        startTime: startTime.toISOString(),
        endTime: endTime.toISOString(),
        intervalMinutes: 15
      };

      // Mock a non-throttling error
      const nonThrottlingError = {
        message: 'Access denied',
        errors: [{
          errorType: 'Unauthorized',
          message: 'Access denied'
        }]
      };

      let callCount = 0;
      
      // Mock to always fail with non-throttling error
      mockGraphqlRequest.mockImplementation(() => {
        callCount++;
        throw nonThrottlingError;
      });

      // Mock the sleep function to avoid actual delays
      const originalSleep = (aggregator as any).sleep;
      (aggregator as any).sleep = jest.fn().mockResolvedValue(undefined);

      const result = await aggregator.getAggregatedMetrics(request);
       
      // Should return empty bucket immediately without retries
      expect(result.count).toBe(0);
      expect(result.sum).toBe(0);
      expect(callCount).toBe(1); // Only one attempt, no retries

      // Restore original functions
      (aggregator as any).sleep = originalSleep;
      // Clear mock
      mockGraphqlRequest.mockClear();
    }, 10000);
  });
});

describe('Integration Tests', () => {
  let aggregator: HierarchicalAggregator;

  beforeEach(() => {
    aggregator = new HierarchicalAggregator();
    jest.clearAllMocks();
  });

  afterEach(() => {
    aggregator.clearCache();
  });

  it('should handle complex hierarchical scenario without double-counting', async () => {
    // Simulate a 2-hour request broken into 15-minute sub-buckets
    const subBucketData = [
      [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }], // 10:00-10:15
      [{ value: 'No', updatedAt: '2024-01-01T10:15:00Z' }],  // 10:15-10:30
      [{ value: 'Yes', updatedAt: '2024-01-01T10:30:00Z' }], // 10:30-10:45
      [{ value: 'Yes', updatedAt: '2024-01-01T10:45:00Z' }], // 10:45-11:00
      [{ value: 'No', updatedAt: '2024-01-01T11:00:00Z' }],  // 11:00-11:15
      [{ value: 'Yes', updatedAt: '2024-01-01T11:15:00Z' }], // 11:15-11:30
      [{ value: 'No', updatedAt: '2024-01-01T11:30:00Z' }],  // 11:30-11:45
      [{ value: 'Yes', updatedAt: '2024-01-01T11:45:00Z' }]  // 11:45-12:00
    ];

    // Mock all sub-bucket responses
    subBucketData.forEach(items => {
      mockGraphqlRequest.mockResolvedValueOnce({
        data: {
          listScoreResultByAccountIdAndUpdatedAt: { items }
        }
      });
    });

    const request: AggregationRequest = {
      accountId: 'test-account',
      recordType: 'scoreResults',
      startTime: '2024-01-01T10:00:00Z',
      endTime: '2024-01-01T12:00:00Z',
      intervalMinutes: 120
    };

    const result = await aggregator.getAggregatedMetrics(request);

    expect(result.count).toBe(8); // Total items
    expect(result.sum).toBe(5);   // 5 Yes values (1 each) + 3 No values (0 each)
    expect(result.avg).toBe(5/8); // Average

    // Should call GraphQL 8 times (once for each 15-minute sub-bucket)
    expect(mockGraphqlRequest).toHaveBeenCalledTimes(8);

    // Now request a sub-range that should use cached data
    mockGraphqlRequest.mockClear();

    // Mock the response for the sub-request
    mockGraphqlRequest.mockResolvedValueOnce({
      data: {
        listScoreResultByAccountIdAndUpdatedAt: {
          items: [{ value: 'Yes', updatedAt: '2024-01-01T10:00:00Z' }]
        }
      }
    });

    const subRequest: AggregationRequest = {
      accountId: 'test-account',
      recordType: 'scoreResults',
      startTime: '2024-01-01T10:00:00Z',
      endTime: '2024-01-01T10:15:00Z',
      intervalMinutes: 15
    };

    const subResult = await aggregator.getAggregatedMetrics(subRequest);

    expect(subResult.count).toBe(1);
    expect(subResult.sum).toBe(1);
    
    // Should call GraphQL once since this is a different time range than the sub-buckets
    // The 15-minute request (10:00-10:15) is different from the 15-minute sub-buckets 
    // that were created during the 2-hour aggregation
    expect(mockGraphqlRequest).toHaveBeenCalledTimes(1);
  }, 10000);
}); 