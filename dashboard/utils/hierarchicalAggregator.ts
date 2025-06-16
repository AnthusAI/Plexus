/**
 * Hierarchical Aggregation Engine
 * 
 * This module handles the complex logic of aggregating metrics across different time intervals
 * in a hierarchical manner (e.g., 1min -> 5min -> 15min -> 30min -> 60min).
 * 
 * Key principles:
 * 1. Only cache direct aggregations for small buckets (≤15 minutes)
 * 2. Large buckets are computed from smaller cached components
 * 3. No hierarchical cache dependencies to prevent double-counting
 * 4. Validation and automatic recomputation for suspicious values
 */

import { amplifyClient, graphqlRequest } from './amplify-client';

export interface AggregationBucket {
  startTime: string;
  endTime: string;
  intervalMinutes: number;
  count: number;
  sum: number;
  avg: number;
}

/**
 * Request for aggregated metrics
 */
export interface AggregationRequest {
  accountId: string;
  recordType: 'items' | 'scoreResults'; // Type of records to aggregate
  scorecardId?: string;
  scoreId?: string;
  startTime: string;
  endTime: string;
  intervalMinutes: number;
  type?: string; // Filter by score result type: "prediction", "evaluation", etc.
}

export interface CacheEntry {
  key: string;
  bucket: AggregationBucket;
  timestamp: number;
  isDirectAggregation: boolean; // True if computed directly from raw data
}

/**
 * Cache manager for aggregated metrics
 */
class AggregationCache {
  private cache = new Map<string, CacheEntry>();
  private readonly CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
  private readonly MAX_CACHE_SIZE = 1000;

  generateKey(request: AggregationRequest): string {
    const parts = [
      request.accountId,
      request.recordType,
      request.scorecardId || 'all',
      request.scoreId || 'all',
      request.type || 'all',
      request.startTime,
      request.endTime,
      request.intervalMinutes.toString()
    ];
    return parts.join('|');
  }

  get(key: string): AggregationBucket | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    // Check if expired
    if (Date.now() - entry.timestamp > this.CACHE_TTL_MS) {
      this.cache.delete(key);
      return null;
    }

    // Validate cached values
    if (this.isSuspiciousValue(entry.bucket)) {
      console.warn(`Suspicious cached value detected for ${key}:`, entry.bucket);
      this.cache.delete(key);
      return null;
    }

    return entry.bucket;
  }

  set(key: string, bucket: AggregationBucket, isDirectAggregation: boolean): void {
    // Only cache small buckets or direct aggregations
    if (bucket.intervalMinutes > 15 && !isDirectAggregation) {
      return; // Don't cache large computed buckets
    }

    // Validate before caching
    if (this.isSuspiciousValue(bucket)) {
      console.warn(`Refusing to cache suspicious value for ${key}:`, bucket);
      return;
    }

    // Evict old entries if cache is full
    if (this.cache.size >= this.MAX_CACHE_SIZE) {
      const oldestKey = Array.from(this.cache.keys())[0];
      this.cache.delete(oldestKey);
    }

    this.cache.set(key, {
      key,
      bucket,
      timestamp: Date.now(),
      isDirectAggregation
    });
  }

  clear(): void {
    this.cache.clear();
  }

  private isSuspiciousValue(bucket: AggregationBucket): boolean {
    return (
      bucket.count < 0 ||
      bucket.count > 100000 ||
      bucket.sum < 0 ||
      bucket.sum > 1000000 ||
      (bucket.count > 0 && bucket.avg < 0) ||
      (bucket.count > 0 && bucket.avg > 1000)
    );
  }
}

/**
 * Main hierarchical aggregation engine
 */
export class HierarchicalAggregator {
  private cache = new AggregationCache();

  /**
   * Get aggregated metrics for a time range and interval
   */
  async getAggregatedMetrics(request: AggregationRequest): Promise<AggregationBucket> {
    const cacheKey = this.cache.generateKey(request);
    
    // Check cache first
    const cached = this.cache.get(cacheKey);
    if (cached) {
      return cached;
    }

    // Determine aggregation strategy
    if (request.intervalMinutes <= 15) {
      // Small buckets: direct aggregation
      return this.performDirectAggregation(request);
    } else {
      // Large buckets: hierarchical aggregation
      return this.performHierarchicalAggregation(request);
    }
  }

  /**
   * Perform direct aggregation from raw data
   */
  private async performDirectAggregation(request: AggregationRequest): Promise<AggregationBucket> {
    const bucket = await this.queryRawData(request);
    
    // Cache the result as a direct aggregation
    const cacheKey = this.cache.generateKey(request);
    this.cache.set(cacheKey, bucket, true);
    
    return bucket;
  }

  /**
   * Perform hierarchical aggregation by breaking down into smaller cached components
   */
  private async performHierarchicalAggregation(request: AggregationRequest): Promise<AggregationBucket> {
    const subBuckets = await this.getSubBuckets(request);
    
    // Aggregate the sub-buckets
    const aggregated = this.combineSubBuckets(subBuckets, request);
    
    // Don't cache hierarchical aggregations to prevent cache dependencies
    return aggregated;
  }

  /**
   * Break down a large time range into smaller cached components
   */
  private async getSubBuckets(request: AggregationRequest): Promise<AggregationBucket[]> {
    const subBucketSize = this.getOptimalSubBucketSize(request.intervalMinutes);
    const subBucketRequests = this.generateSubBucketRequests(request, subBucketSize);
    
    // Fetch all sub-buckets in parallel
    const subBuckets = await Promise.all(
      subBucketRequests.map(subRequest => this.getAggregatedMetrics(subRequest))
    );
    
    return subBuckets;
  }

  /**
   * Determine the optimal sub-bucket size for hierarchical aggregation
   */
  private getOptimalSubBucketSize(intervalMinutes: number): number {
    if (intervalMinutes >= 60) {
      return 15; // Break 60+ minute buckets into 15-minute components
    } else if (intervalMinutes >= 30) {
      return 15; // Break 30+ minute buckets into 15-minute components
    } else {
      return 5;  // Break 15-30 minute buckets into 5-minute components
    }
  }

  /**
   * Generate sub-bucket requests for a given time range
   */
  private generateSubBucketRequests(request: AggregationRequest, subBucketMinutes: number): AggregationRequest[] {
    const requests: AggregationRequest[] = [];
    const startTime = new Date(request.startTime);
    const endTime = new Date(request.endTime);
    
    let currentTime = new Date(startTime);
    
    while (currentTime < endTime) {
      const bucketEndTime = new Date(currentTime);
      bucketEndTime.setMinutes(bucketEndTime.getMinutes() + subBucketMinutes);
      
      // Don't go beyond the requested end time
      if (bucketEndTime > endTime) {
        bucketEndTime.setTime(endTime.getTime());
      }
      
      requests.push({
        ...request,
        startTime: currentTime.toISOString(),
        endTime: bucketEndTime.toISOString(),
        intervalMinutes: subBucketMinutes
      });
      
      currentTime = new Date(bucketEndTime);
    }
    
    return requests;
  }

  /**
   * Combine multiple sub-buckets into a single aggregated bucket
   */
  private combineSubBuckets(subBuckets: AggregationBucket[], request: AggregationRequest): AggregationBucket {
    const totalCount = subBuckets.reduce((sum, bucket) => sum + bucket.count, 0);
    const totalSum = subBuckets.reduce((sum, bucket) => sum + bucket.sum, 0);
    const avgValue = totalCount > 0 ? totalSum / totalCount : 0;
    
    return {
      startTime: request.startTime,
      endTime: request.endTime,
      intervalMinutes: request.intervalMinutes,
      count: totalCount,
      sum: totalSum,
      avg: avgValue
    };
  }

  /**
   * Query raw data from the database with retry logic for DynamoDB throttling
   */
  private async queryRawData(request: AggregationRequest): Promise<AggregationBucket> {
    const maxRetries = 3;
    const baseDelayMs = 1000; // Start with 1 second delay
    
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await this.executeQuery(request);
      } catch (error: any) {
        const isDynamoThrottling = this.isDynamoDBThrottlingError(error);
        const isLastAttempt = attempt === maxRetries;
        
        if (isDynamoThrottling && !isLastAttempt) {
          // Exponential backoff: 1s, 2s, 4s
          const delayMs = baseDelayMs * Math.pow(2, attempt);
          console.warn(`DynamoDB throttling detected, retrying in ${delayMs}ms (attempt ${attempt + 1}/${maxRetries + 1})`);
          await this.sleep(delayMs);
          continue;
        }
        
        // If not a throttling error or last attempt, log and return empty bucket
        console.error('Error querying raw data:', error);
        return {
          startTime: request.startTime,
          endTime: request.endTime,
          intervalMinutes: request.intervalMinutes,
          count: 0,
          sum: 0,
          avg: 0
        };
      }
    }
    
    // This should never be reached, but TypeScript requires it
    throw new Error('Unexpected error in queryRawData retry logic');
  }

  /**
   * Execute the actual GraphQL query
   */
  private async executeQuery(request: AggregationRequest): Promise<AggregationBucket> {
    let query: string;
    let variables: any;

    if (request.recordType === 'items') {
      // Query items data
      query = `
        query GetItemsForAggregation($accountId: String!, $startTime: String!, $endTime: String!) {
          listItemByAccountIdAndCreatedAt(
            accountId: $accountId,
            createdAt: { between: [$startTime, $endTime] },
            limit: 10000
          ) {
            items {
              id
              createdAt
            }
          }
        }
      `;
      variables = {
        accountId: request.accountId,
        startTime: request.startTime,
        endTime: request.endTime
      };
    } else if (request.recordType === 'scoreResults') {
      // Query score results data
      if (request.scoreId) {
        // Query by specific score
        query = `
          query GetScoreResultsForAggregation($scoreId: String!, $startTime: String!, $endTime: String!) {
            listScoreResultByScoreIdAndUpdatedAt(
              scoreId: $scoreId,
              updatedAt: { between: [$startTime, $endTime] },
              limit: 10000
            ) {
              items {
                value
                updatedAt
                type
              }
            }
          }
        `;
        variables = {
          scoreId: request.scoreId,
          startTime: request.startTime,
          endTime: request.endTime
        };
      } else if (request.scorecardId) {
        // Query by scorecard
        query = `
          query GetScoreResultsForAggregationByScorecard($scorecardId: String!, $startTime: String!, $endTime: String!) {
            listScoreResultByScorecardIdAndUpdatedAt(
              scorecardId: $scorecardId,
              updatedAt: { between: [$startTime, $endTime] },
              limit: 10000
            ) {
              items {
                value
                updatedAt
                type
              }
            }
          }
        `;
        variables = {
          scorecardId: request.scorecardId,
          startTime: request.startTime,
          endTime: request.endTime
        };
      } else {
        // Query by account
        query = `
          query GetScoreResultsForAggregationByAccount($accountId: String!, $startTime: String!, $endTime: String!) {
            listScoreResultByAccountIdAndUpdatedAt(
              accountId: $accountId,
              updatedAt: { between: [$startTime, $endTime] },
              limit: 10000
            ) {
              items {
                value
                updatedAt
                type
              }
            }
          }
        `;
        variables = {
          accountId: request.accountId,
          startTime: request.startTime,
          endTime: request.endTime
        };
      }
    } else {
      throw new Error(`Unsupported record type: ${request.recordType}`);
    }

    const response = await graphqlRequest<any>(query, variables);
    const items = Object.values(response.data)[0] as { items: Array<any> };
    
    // Process the raw data based on record type
    let records = items.items || [];
    
    // Apply type filtering for scoreResults if specified
    if (request.recordType === 'scoreResults' && request.type) {
      records = records.filter(record => record.type === request.type);
    }
    
    const count = records.length;
    
    let sum = 0;
    let avg = 0;
    
    if (request.recordType === 'scoreResults') {
      // Convert values to numbers and calculate sum for score results
      const numericValues = records
        .map(result => this.parseScoreValue(result.value))
        .filter(value => value !== null) as number[];
      
      sum = numericValues.reduce((total, value) => total + value, 0);
      avg = numericValues.length > 0 ? sum / numericValues.length : 0;
    } else {
      // For items, sum and avg are just the count (each item has value 1)
      sum = count;
      avg = count > 0 ? 1 : 0;
    }

    return {
      startTime: request.startTime,
      endTime: request.endTime,
      intervalMinutes: request.intervalMinutes,
      count,
      sum,
      avg
    };
  }

  /**
   * Parse score value to number (handles Yes/No, percentages, etc.)
   */
  private parseScoreValue(value: string): number | null {
    if (!value) return null;
    
    const trimmed = value.trim().toLowerCase();
    
    // Handle Yes/No values
    if (trimmed === 'yes') return 1;
    if (trimmed === 'no') return 0;
    
    // Handle percentage values
    if (trimmed.endsWith('%')) {
      const numStr = trimmed.slice(0, -1);
      const num = parseFloat(numStr);
      return isNaN(num) ? null : num / 100;
    }
    
    // Handle numeric values
    const num = parseFloat(trimmed);
    return isNaN(num) ? null : num;
  }

  /**
   * Check if error is a DynamoDB throttling error
   */
  private isDynamoDBThrottlingError(error: any): boolean {
    if (!error) return false;
    
    const errorMessage = error.message || '';
    const errorString = JSON.stringify(error).toLowerCase();
    
    // Check for various DynamoDB throttling indicators
    return (
      errorMessage.includes('Throughput exceeds the current capacity') ||
      errorMessage.includes('DynamoDB is automatically scaling') ||
      errorString.includes('throttling') ||
      errorString.includes('capacity') ||
      errorString.includes('provisioned throughput')
    );
  }

  /**
   * Sleep for specified milliseconds
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Clear all cached data
   */
  clearCache(): void {
    this.cache.clear();
  }

  /**
   * Get cache statistics for debugging
   */
  getCacheStats(): { size: number; keys: string[] } {
    return {
      size: this.cache['cache'].size,
      keys: Array.from(this.cache['cache'].keys())
    };
  }
}

// Export a singleton instance
export const hierarchicalAggregator = new HierarchicalAggregator(); 