/**
 * Generalized Metrics Aggregation System
 * 
 * This module provides a unified interface for aggregating metrics from different data sources:
 * - ScoreResults (with optional type filtering: prediction, evaluation, etc.)
 * - FeedbackItems (different table structure)
 * - Future data sources can be easily added
 * 
 * Features:
 * - Session storage caching to avoid duplicate downloads
 * - Flexible filtering options
 * - Backward compatibility with existing systems
 * - Parallel data fetching for efficiency
 */

import { graphqlRequest } from './amplify-client'

// Base interfaces
export interface MetricsDataSource {
  type: 'items' | 'scoreResults' | 'feedbackItems'
  accountId: string
  startTime?: Date
  endTime?: Date
  // Optional filters
  scorecardId?: string
  scoreId?: string
  scoreResultType?: string // For scoreResults: "prediction", "evaluation", etc.
  createdByType?: string // For items: "evaluation", "prediction", etc.
  // Cache configuration
  cacheKey?: string
  cacheTTL?: number // TTL in milliseconds, default 5 minutes
}

export interface AggregatedData {
  count: number
  sum: number
  avg: number
  items: Array<any> // Raw items for further processing
}

export interface MetricsResult {
  hourly: AggregatedData
  total24h: AggregatedData
  chartData: Array<{
    time: string
    value: number
    bucketStart: string
    bucketEnd: string
  }>
  lastUpdated: Date
}

// Session storage cache manager
class SessionStorageCache {
  private readonly DEFAULT_TTL = 5 * 60 * 1000 // 5 minutes

  generateKey(source: MetricsDataSource): string {
    const parts = [
      source.type,
      source.accountId,
      source.scorecardId || 'all',
      source.scoreId || 'all',
      source.scoreResultType || 'all',
      source.createdByType || 'all',
      source.startTime?.toISOString() || 'all',
      source.endTime?.toISOString() || 'all'
    ]
    return `metrics_${parts.join('|')}`
  }

  get(key: string): AggregatedData | null {
    try {
      const cached = sessionStorage.getItem(key)
      if (!cached) return null

      const parsed = JSON.parse(cached)
      const now = Date.now()
      
      // Check if expired
      if (now - parsed.timestamp > (parsed.ttl || this.DEFAULT_TTL)) {
        sessionStorage.removeItem(key)
        return null
      }

      return parsed.data
    } catch (error) {
      console.warn('Error reading from session storage cache:', error)
      return null
    }
  }

  set(key: string, data: AggregatedData, ttl?: number): void {
    try {
      const cacheEntry = {
        data,
        timestamp: Date.now(),
        ttl: ttl || this.DEFAULT_TTL
      }
      sessionStorage.setItem(key, JSON.stringify(cacheEntry))
    } catch (error) {
      console.warn('Error writing to session storage cache:', error)
    }
  }

  clear(): void {
    try {
      // Clear only metrics cache entries
      const keys = Object.keys(sessionStorage)
      keys.forEach(key => {
        if (key.startsWith('metrics_')) {
          sessionStorage.removeItem(key)
        }
      })
    } catch (error) {
      console.warn('Error clearing session storage cache:', error)
    }
  }
}

// Main aggregator class
export class GeneralizedMetricsAggregator {
  private cache = new SessionStorageCache()

  /**
   * Get aggregated metrics for a data source
   */
  async getMetrics(source: MetricsDataSource): Promise<AggregatedData> {
    const cacheKey = this.cache.generateKey(source)
    
    // Check cache first
    const cached = this.cache.get(cacheKey)
    if (cached) {
      return cached
    }

    // Fetch fresh data
    const data = await this.fetchRawData(source)
    
    // Cache the result
    this.cache.set(cacheKey, data, source.cacheTTL)
    
    return data
  }

  /**
   * Get comprehensive metrics (hourly + 24h + chart data)
   */
  async getComprehensiveMetrics(source: MetricsDataSource): Promise<MetricsResult> {
    const now = new Date()
    
    // Calculate rolling 60-minute window for hourly metrics
    const nowAligned = new Date(now)
    nowAligned.setSeconds(0, 0)
    const currentHourMinutes = nowAligned.getMinutes()
    const windowMinutes = 60 + currentHourMinutes
    const lastHour = new Date(nowAligned.getTime() - windowMinutes * 60 * 1000)

    // Create sources for different time ranges
    const hourlySource: MetricsDataSource = {
      ...source,
      startTime: lastHour,
      endTime: now
    }

    const total24hSource: MetricsDataSource = {
      ...source,
      startTime: new Date(now.getTime() - 24 * 60 * 60 * 1000),
      endTime: now
    }

    // Fetch both in parallel
    const [hourlyData, total24hData] = await Promise.all([
      this.getMetrics(hourlySource),
      this.getMetrics(total24hSource)
    ])

    // Generate chart data from the 24h raw data to avoid extra API calls
    const chartData = this.generateChartDataFromRecords(total24hData.items, source)

    // Normalize hourly metrics
    const actualWindowMinutes = (now.getTime() - lastHour.getTime()) / (60 * 1000)
    const normalizationFactor = actualWindowMinutes > 0 ? 60 / actualWindowMinutes : 1

    const normalizedHourlyData: AggregatedData = {
      ...hourlyData,
      count: Math.round(hourlyData.count * normalizationFactor),
      sum: hourlyData.sum * normalizationFactor,
      avg: hourlyData.avg // Average doesn't need normalization
    }

    return {
      hourly: normalizedHourlyData,
      total24h: total24hData,
      chartData,
      lastUpdated: now
    }
  }

  /**
   * Fetch raw data based on data source type
   */
  private async fetchRawData(source: MetricsDataSource): Promise<AggregatedData> {
    let allRecords: any[] = [];
    let nextToken: string | null = null;
    let pageCount = 0;
    const MAX_PAGES = 50; // Safety break for large datasets

    do {
      // Add a delay between paged requests to prevent throttling DynamoDB
      if (pageCount > 0) {
        await new Promise(resolve => setTimeout(resolve, 250));
      }

      const page = await this.fetchRawDataPage(source, nextToken);
      allRecords = allRecords.concat(page.records);
      nextToken = page.nextToken;
      pageCount++;

    } while (nextToken && pageCount < MAX_PAGES);

    if (pageCount >= MAX_PAGES) {
      console.warn(`Metrics aggregation reached max pages (${MAX_PAGES}). Data might be incomplete.`);
    }

    return this.processRecords(source, allRecords);
  }

  private async fetchRawDataPage(source: MetricsDataSource, nextToken: string | null): Promise<{ records: any[], nextToken: string | null }> {
    switch (source.type) {
      case 'items':
        return this.fetchItemsData(source, nextToken);
      case 'scoreResults':
        return this.fetchScoreResultsData(source, nextToken);
      case 'feedbackItems':
        return this.fetchFeedbackItemsData(source, nextToken);
      default:
        // Ensure this is unreachable, but satisfies TypeScript
        const exhaustiveCheck: never = source.type;
        throw new Error(`Unsupported data source type: ${exhaustiveCheck}`);
    }
  }

  private processRecords(source: MetricsDataSource, records: any[]): AggregatedData {
    let processedRecords = records;
    if (source.type === 'scoreResults' && source.scoreResultType) {
        processedRecords = records.filter(record => record.type === source.scoreResultType);
    }

    const count = processedRecords.length;
    let sum = 0;
    let avg = 0;

    if (source.type === 'scoreResults') {
        const numericValues = processedRecords
            .map(result => this.parseScoreValue(result.value))
            .filter(value => value !== null) as number[];
        
        sum = numericValues.reduce((total, value) => total + value, 0);
        avg = numericValues.length > 0 ? sum / numericValues.length : 0;
    } else if (source.type === 'feedbackItems') {
        const agreementItems = processedRecords.filter(item => item.isAgreement === true);
        sum = agreementItems.length;
        avg = count > 0 ? sum / count : 0;
    } else if (source.type === 'items') {
      // For items, sum and avg are just the count (each item has value 1)
      sum = count;
      avg = count > 0 ? 1 : 0;
    }

    return {
        count,
        sum,
        avg,
        items: processedRecords,
    };
  }

  /**
   * Fetch Items data
   */
  private async fetchItemsData(source: MetricsDataSource, nextToken: string | null): Promise<{ records: any[], nextToken: string | null }> {
    const startTime = source.startTime?.toISOString()
    const endTime = source.endTime?.toISOString()

    let query: string
    let variables: any

    if (source.createdByType) {
      // Use the new GSI to filter by createdByType
      query = `
        query GetItemsForMetricsByCreatedByType($accountId: String!, $createdByType: String!, $startTime: String!, $endTime: String!, $nextToken: String) {
          listItemByAccountCreatedByTypeAndCreatedAt(
            accountId: $accountId,
            createdByTypeCreatedAt: {
              createdByType: { eq: $createdByType },
              createdAt: { between: [$startTime, $endTime] }
            },
            limit: 1000,
            nextToken: $nextToken
          ) {
            items {
              id
              createdAt
              createdByType
            }
            nextToken
          }
        }
      `;
      
      variables = {
        accountId: source.accountId,
        createdByType: source.createdByType,
        startTime,
        endTime,
        nextToken
      };
    } else {
      // Use the original query for all items
      query = `
        query GetItemsForMetrics($accountId: String!, $startTime: String!, $endTime: String!, $nextToken: String) {
          listItemByAccountIdAndCreatedAt(
            accountId: $accountId,
            createdAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
          ) {
            items {
              id
              createdAt
              createdByType
            }
            nextToken
          }
        }
      `;
      
      variables = {
        accountId: source.accountId,
        startTime,
        endTime,
        nextToken
      };
    }

    const response = await this.performRequestWithRetry(query, variables);
    const result = Object.values(response.data)[0] as { items: Array<any>; nextToken?: string };
    const records = result.items || [];
    
    return { records, nextToken: result.nextToken || null };
  }

  /**
   * Fetch ScoreResults data with optional type filtering
   */
  private async fetchScoreResultsData(source: MetricsDataSource, nextToken: string | null): Promise<{ records: any[], nextToken: string | null }> {
    let query: string
    let variables: any

    const startTime = source.startTime?.toISOString()
    const endTime = source.endTime?.toISOString()

    if (source.scoreId) {
      // Query by specific score
      query = `
        query GetScoreResultsForMetrics($scoreId: String!, $startTime: String!, $endTime: String!) {
          listScoreResultByScoreIdAndUpdatedAt(
            scoreId: $scoreId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 10000
          ) {
            items {
              id
              value
              updatedAt
              type
              scoreId
              scorecardId
            }
          }
        }
      `
      variables = {
        scoreId: source.scoreId,
        startTime,
        endTime
      }
    } else if (source.scorecardId) {
      // Query by scorecard
      query = `
        query GetScoreResultsForMetricsByScorecard($scorecardId: String!, $startTime: String!, $endTime: String!) {
          listScoreResultByScorecardIdAndUpdatedAt(
            scorecardId: $scorecardId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 10000
          ) {
            items {
              id
              value
              updatedAt
              type
              scoreId
              scorecardId
            }
          }
        }
      `
      variables = {
        scorecardId: source.scorecardId,
        startTime,
        endTime
      }
    } else {
      // Query by account
      query = `
        query GetScoreResultsForMetricsByAccount($accountId: String!, $startTime: String!, $endTime: String!, $nextToken: String) {
          listScoreResultByAccountIdAndUpdatedAt(
            accountId: $accountId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
          ) {
            items {
              id
              value
              updatedAt
              type
              scoreId
              scorecardId
            }
            nextToken
          }
        }
      `
      variables = {
        accountId: source.accountId,
        startTime,
        endTime,
        nextToken
      }
    }

    const response = await this.performRequestWithRetry(query, variables);
    const result = Object.values(response.data)[0] as { items: Array<any>; nextToken?: string };
    const records = result.items || [];
    
    return { records, nextToken: result.nextToken || null };
  }

  /**
   * Fetch FeedbackItems data
   */
  private async fetchFeedbackItemsData(source: MetricsDataSource, nextToken: string | null): Promise<{ records: any[], nextToken: string | null }> {
    let query: string
    let variables: any

    const startTime = source.startTime?.toISOString()
    const endTime = source.endTime?.toISOString()

    if (source.scoreId && source.scorecardId) {
      // Query by specific scorecard and score
      query = `
        query GetFeedbackItemsForMetrics($accountId: String!, $scorecardId: String!, $scoreId: String!, $startTime: String!, $endTime: String!) {
          listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt(
            accountId: $accountId,
            scorecardIdScoreIdUpdatedAt: {
              scorecardId: { eq: $scorecardId },
              scoreId: { eq: $scoreId },
              updatedAt: { between: [$startTime, $endTime] }
            },
            limit: 10000
          ) {
            items {
              id
              updatedAt
              editedAt
              isAgreement
              initialAnswerValue
              finalAnswerValue
              scorecardId
              scoreId
            }
          }
        }
      `
      variables = {
        accountId: source.accountId,
        scorecardId: source.scorecardId,
        scoreId: source.scoreId,
        startTime,
        endTime
      }
    } else {
      // Query by account with date range
      query = `
        query GetFeedbackItemsForMetricsByAccount($accountId: String!, $startTime: String!, $endTime: String!, $nextToken: String) {
          listFeedbackItemByAccountIdAndUpdatedAt(
            accountId: $accountId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
          ) {
            items {
              id
              updatedAt
              editedAt
              isAgreement
              initialAnswerValue
              finalAnswerValue
              scorecardId
              scoreId
            }
            nextToken
          }
        }
      `
      variables = {
        accountId: source.accountId,
        startTime,
        endTime,
        nextToken
      }
    }

    const response = await this.performRequestWithRetry(query, variables);
    const result = Object.values(response.data)[0] as { items: Array<any>; nextToken?: string };
    const records = result.items || [];

    return { records, nextToken: result.nextToken || null };
  }

  /**
   * Generate chart data from a pre-fetched list of records.
   * This avoids making 24 extra API calls for the chart.
   */
  private generateChartDataFromRecords(records: any[], source: MetricsDataSource): Array<{
    time: string
    value: number
    bucketStart: string
    bucketEnd: string
  }> {
    const now = new Date();
    const hourlyBuckets = Array.from({ length: 24 }, () => 0);
    const timestampField = source.type === 'items' ? 'createdAt' : 'updatedAt';

    // Apply the same filtering logic as processRecords to ensure consistency
    let filteredRecords = records;
    if (source.type === 'scoreResults' && source.scoreResultType) {
        filteredRecords = records.filter(record => record.type === source.scoreResultType);
    }

    filteredRecords.forEach(record => {
        const recordDate = new Date(record[timestampField]);
        const hoursAgo = Math.floor((now.getTime() - recordDate.getTime()) / (1000 * 60 * 60));
        if (hoursAgo >= 0 && hoursAgo < 24) {
            const bucketIndex = 23 - hoursAgo;
            hourlyBuckets[bucketIndex]++;
        }
    });

    const chartData: Array<{ time: string; value: number; bucketStart: string; bucketEnd: string }> = [];
    for (let i = 0; i < 24; i++) {
        const date = new Date(now);
        date.setHours(date.getHours() - (23 - i));
        date.setMinutes(0,0,0);

        const bucketStart = date;
        const bucketEnd = new Date(bucketStart.getTime() + 60 * 60 * 1000);

        chartData.push({
            time: bucketStart.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
            value: hourlyBuckets[i],
            bucketStart: bucketStart.toISOString(),
            bucketEnd: (bucketEnd > now ? now : bucketEnd).toISOString(),
        });
    }

    return chartData;
  }

  /**
   * Parse score value to number (handles Yes/No, percentages, etc.)
   */
  private parseScoreValue(value: string): number | null {
    if (!value) return null
    
    const trimmed = value.trim().toLowerCase()
    
    // Handle Yes/No values
    if (trimmed === 'yes') return 1
    if (trimmed === 'no') return 0
    
    // Handle percentage values
    if (trimmed.endsWith('%')) {
      const numStr = trimmed.slice(0, -1)
      const num = parseFloat(numStr)
      return isNaN(num) ? null : num / 100
    }
    
    // Handle numeric values
    const num = parseFloat(trimmed)
    return isNaN(num) ? null : num
  }

  /**
   * Clear all cached data
   */
  clearCache(): void {
    this.cache.clear()
  }

  /**
   * Helper to perform a GraphQL request with a retry mechanism for throttling.
   */
  private async performRequestWithRetry(query: string, variables: any, maxRetries = 3, initialDelay = 300): Promise<any> {
    let attempt = 0;
    while (attempt < maxRetries) {
        try {
            const response = await graphqlRequest<any>(query, variables);
            // Also check for GraphQL-level errors that don't throw an exception
            if (response.errors && response.errors.some((e: any) => this.isDynamoDBThrottlingError(e))) {
                 throw response.errors.find((e: any) => this.isDynamoDBThrottlingError(e));
            }
            return response;
        } catch (error: any) {
            attempt++;
            if (attempt >= maxRetries || !this.isDynamoDBThrottlingError(error)) {
                console.error(`Final attempt failed or non-retriable error for query: ${query.substring(0, 100)}...`, error);
                throw error;
            }
            const delay = initialDelay * Math.pow(2, attempt - 1);
            console.warn(`Throttling detected. Retrying in ${delay}ms... (Attempt ${attempt}/${maxRetries})`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
  }

  /**
   * Check if an error object indicates DynamoDB throttling.
   */
  private isDynamoDBThrottlingError(error: any): boolean {
    if (!error) return false;
    
    const errorMessage = error.message || '';
    const errorType = error.errorType || '';
    const errorString = JSON.stringify(error).toLowerCase();
    
    return (
      errorMessage.includes('Throughput exceeds the current capacity') ||
      errorType.includes('DynamoDbException') ||
      errorString.includes('throttling')
    );
  }
}

// Export singleton instance
export const generalizedMetricsAggregator = new GeneralizedMetricsAggregator() 