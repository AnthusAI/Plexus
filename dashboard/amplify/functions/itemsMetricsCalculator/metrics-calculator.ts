import axios from 'axios';
import { cache } from './cache';

interface GraphQLResponse {
  data?: any;
  errors?: Array<{ message: string }>;
}

interface TimeBucket {
  time: string;
  items?: number;
  scoreResults?: number;
  bucketStart: string;
  bucketEnd: string;
}

interface ItemsMetrics {
  itemsPerHour: number;
  itemsAveragePerHour: number;
  itemsPeakHourly: number;
  itemsTotal24h: number;
  chartData: TimeBucket[];
}

interface ScoreResultsMetrics {
  scoreResultsPerHour: number;
  scoreResultsAveragePerHour: number;
  scoreResultsPeakHourly: number;
  scoreResultsTotal24h: number;
  chartData: TimeBucket[];
}

type CountFunction = (accountId: string, startTime: Date, endTime: Date) => Promise<number>;

/**
 * A utility class for calculating items and score results metrics over time periods.
 * Uses API key authentication to connect to the Plexus GraphQL API and provides
 * methods to count items and score results within specific timeframes,
 * generate time buckets, and calculate hourly rates and statistics.
 *
 * This implementation mirrors the Python MetricsCalculator exactly, including
 * the SQLite-based caching mechanism with clock-aligned buckets and margin handling.
 */
export class MetricsCalculator {
  private graphqlEndpoint: string;
  private apiKey: string;
  private cacheBucketMinutes: number;

  /**
   * Initialize the MetricsCalculator.
   *
   * @param graphqlEndpoint The GraphQL API endpoint URL
   * @param apiKey The API key for authentication
   * @param cacheBucketMinutes The width of the cache buckets in minutes. Defaults to 15.
   */
  constructor(graphqlEndpoint: string, apiKey: string, cacheBucketMinutes = 15) {
    this.graphqlEndpoint = graphqlEndpoint;
    this.apiKey = apiKey;
    this.cacheBucketMinutes = cacheBucketMinutes;
  }

  /**
   * Make a GraphQL request to the API using API key authentication.
   */
  private async makeGraphQLRequest(query: string, variables: Record<string, any>): Promise<any> {
    const payload = { query, variables };

    // Log the request with a brief description
    const queryType = this.getQueryType(query);
    const pageInfo = variables.nextToken ? ` (page ${variables._page_number || '?'})` : '';
    
    console.log(`GraphQL request: ${queryType}${pageInfo}`);
    console.debug(`Making GraphQL request to ${this.graphqlEndpoint}`);
    console.debug(`Query: ${query}`);
    console.debug(`Variables: ${JSON.stringify(variables)}`);

    const headers = {
      'x-api-key': this.apiKey,
      'Content-Type': 'application/json'
    };

    try {
      const response = await axios.post(
        this.graphqlEndpoint,
        payload,
        {
          headers,
          timeout: 60000 // 60 seconds - increased timeout as in Python
        }
      );

      if (response.status !== 200) {
        throw new Error(`GraphQL request failed with status ${response.status}: ${response.data}`);
      }

      const data = response.data as GraphQLResponse;

      if (data.errors) {
        const errorMessages = data.errors.map(e => e.message).join(', ');
        throw new Error(`GraphQL errors: ${errorMessages}`);
      }

      return data.data || {};

    } catch (error) {
      if (axios.isAxiosError(error)) {
        if (error.code === 'ECONNABORTED') {
          throw new Error('GraphQL request timed out after 60 seconds');
        } else if (error.response) {
          throw new Error(`GraphQL request failed with status ${error.response.status}: ${error.response.data}`);
        } else if (error.request) {
          throw new Error('GraphQL request failed: No response received');
        }
      }
      throw error;
    }
  }

  private getQueryType(query: string): string {
    if (query.includes('listItemByAccountIdAndCreatedAt')) return 'items';
    if (query.includes('listScoreResultByAccountIdAndCreatedAt')) return 'score_results';
    if (query.includes('listScoreResultByAccountIdAndUpdatedAt')) return 'score_results';
    if (query.includes('listItems')) return 'items';
    if (query.includes('listScoreResults')) return 'score_results';
    return 'unknown';
  }

  /**
   * Count items created within a specific timeframe using the GSI.
   */
  private async countItemsInTimeframe(accountId: string, startTime: Date, endTime: Date): Promise<number> {
    const query = `
      query ListItemByAccountIdAndCreatedAt($accountId: String!, $startTime: String!, $endTime: String!, $nextToken: String, $limit: Int) {
        listItemByAccountIdAndCreatedAt(
          accountId: $accountId, 
          createdAt: { between: [$startTime, $endTime] },
          nextToken: $nextToken,
          limit: $limit
        ) {
          items {
            id
          }
          nextToken
        }
      }
    `;

    const variables: Record<string, any> = {
      accountId,
      startTime: startTime.toISOString(),
      endTime: endTime.toISOString(),
      limit: 1000
    };

    let totalCount = 0;
    let nextToken: string | null = null;
    let pageCount = 0;
    const maxPages = 500; // Increased page limit as in Python

    console.log(`Counting items for account ${accountId} between ${startTime.toISOString()} and ${endTime.toISOString()}`);

    while (true) {
      if (pageCount >= maxPages) {
        console.warn(`Reached maximum page limit (${maxPages}) while counting items. Partial count: ${totalCount}`);
        break;
      }

      const currentVariables = { ...variables };
      if (nextToken) {
        currentVariables.nextToken = nextToken;
      }
      
      // Add page number to variables for logging
      currentVariables._page_number = pageCount + 1;

      console.debug(`Fetching items page ${pageCount + 1}`);

      try {
        const data = await this.makeGraphQLRequest(query, currentVariables);
        const items = data.listItemByAccountIdAndCreatedAt?.items || [];
        const itemCount = items.length;
        totalCount += itemCount;
        pageCount++;

        console.debug(`Fetched ${itemCount} items on page ${pageCount}, total so far: ${totalCount}`);

        nextToken = data.listItemByAccountIdAndCreatedAt?.nextToken;
        if (!nextToken) break;
      } catch (error) {
        console.error(`Failed to fetch items page ${pageCount + 1}: ${error}`);
        break;
      }
    }

    console.log(`Found ${totalCount} items between ${startTime.toISOString()} and ${endTime.toISOString()} (processed ${pageCount} pages)`);
    return totalCount;
  }

  /**
   * Count score results updated within a specific timeframe using the GSI.
   */
  private async countScoreResultsInTimeframe(accountId: string, startTime: Date, endTime: Date): Promise<number> {
    const query = `
      query ListScoreResultByAccountIdAndUpdatedAt($accountId: String!, $startTime: String!, $endTime: String!, $nextToken: String, $limit: Int) {
        listScoreResultByAccountIdAndUpdatedAt(
          accountId: $accountId, 
          updatedAt: { between: [$startTime, $endTime] },
          nextToken: $nextToken,
          limit: $limit
        ) {
          items {
            id
          }
          nextToken
        }
      }
    `;

    const variables: Record<string, any> = {
      accountId,
      startTime: startTime.toISOString(),
      endTime: endTime.toISOString(),
      limit: 1000
    };

    let totalCount = 0;
    let nextToken: string | null = null;
    let pageCount = 0;
    const maxPages = 500; // Increased page limit as in Python

    console.log(`Counting score results for account ${accountId} between ${startTime.toISOString()} and ${endTime.toISOString()}`);

    while (true) {
      if (pageCount >= maxPages) {
        console.warn(`Reached maximum page limit (${maxPages}) while counting score results. Partial count: ${totalCount}`);
        break;
      }

      const currentVariables = { ...variables };
      if (nextToken) {
        currentVariables.nextToken = nextToken;
      }
      
      // Add page number to variables for logging
      currentVariables._page_number = pageCount + 1;

      console.debug(`Fetching score results page ${pageCount + 1}`);

      try {
        const data = await this.makeGraphQLRequest(query, currentVariables);
        const items = data.listScoreResultByAccountIdAndUpdatedAt?.items || [];
        const itemCount = items.length;
        totalCount += itemCount;
        pageCount++;

        console.debug(`Fetched ${itemCount} score results on page ${pageCount}, total so far: ${totalCount}`);

        nextToken = data.listScoreResultByAccountIdAndUpdatedAt?.nextToken;
        if (!nextToken) break;
      } catch (error) {
        console.error(`Failed to fetch score results page ${pageCount + 1}: ${error}`);
        break;
      }
    }

    console.log(`Found ${totalCount} score results between ${startTime.toISOString()} and ${endTime.toISOString()} (processed ${pageCount} pages)`);
    return totalCount;
  }

  /**
   * Generate time buckets of a specific size between a start and end time.
   */
  private getTimeBuckets(startTime: Date, endTime: Date, bucketSizeMinutes: number): Array<[Date, Date]> {
    const buckets: Array<[Date, Date]> = [];
    let currentTime = new Date(startTime);
    
    while (currentTime < endTime) {
      const bucketEndTime = new Date(currentTime.getTime() + bucketSizeMinutes * 60 * 1000);
      buckets.push([currentTime, new Date(Math.min(bucketEndTime.getTime(), endTime.getTime()))]);
      currentTime = bucketEndTime;
    }
    
    return buckets;
  }

  /**
   * Calculates the clock-aligned buckets that are fully contained within the given time range.
   * This mirrors the Python implementation exactly.
   */
  private getClockAlignedBuckets(startTime: Date, endTime: Date, bucketSizeMinutes: number): Array<[Date, Date]> {
    const buckets: Array<[Date, Date]> = [];
    
    // Find the start of the first full bucket
    let firstBucketStart = new Date(startTime);
    if (startTime.getMinutes() % bucketSizeMinutes !== 0 || startTime.getSeconds() !== 0 || startTime.getMilliseconds() !== 0) {
      const minutesToAdd = bucketSizeMinutes - (startTime.getMinutes() % bucketSizeMinutes);
      firstBucketStart = new Date(startTime.getTime() + minutesToAdd * 60 * 1000);
      firstBucketStart.setMinutes((startTime.getMinutes() + minutesToAdd) % 60);
      firstBucketStart.setSeconds(0);
      firstBucketStart.setMilliseconds(0);
    }

    // Iterate through buckets and add the ones that are fully contained
    let currentTime = new Date(firstBucketStart);
    while (currentTime.getTime() + bucketSizeMinutes * 60 * 1000 <= endTime.getTime()) {
      const bucketEnd = new Date(currentTime.getTime() + bucketSizeMinutes * 60 * 1000);
      buckets.push([new Date(currentTime), bucketEnd]);
      currentTime = bucketEnd;
    }
    
    return buckets;
  }

  /**
   * Get count for a time range, using clock-aligned cache buckets.
   * This is a simpler version used within the more complex _getCountForWindow method.
   */
  private async getCountWithCaching(
    accountId: string, 
    startTime: Date, 
    endTime: Date, 
    countFunction: CountFunction
  ): Promise<number> {
    // Extract the actual function name, removing "bound " prefix if present
    const cacheKeyPrefix = countFunction.name.replace(/^bound /, '');
    let totalCount = 0;
    
    // Get the clock-aligned buckets that are fully contained in the time range
    const alignedBuckets = this.getClockAlignedBuckets(startTime, endTime, this.cacheBucketMinutes);

    if (alignedBuckets.length === 0) {
      // If no full buckets, just query the whole range
      return await countFunction(accountId, startTime, endTime);
    }

    // 1. Count items in the first partial bucket (if any)
    const firstBucketStart = alignedBuckets[0][0];
    if (startTime < firstBucketStart) {
      totalCount += await countFunction(accountId, startTime, firstBucketStart);
    }

    // 2. Count items in the full buckets (using cache)
    for (const [bucketStart, bucketEnd] of alignedBuckets) {
      const cacheKey = `${cacheKeyPrefix}:${accountId}:${bucketStart.toISOString()}`;
      let cachedValue = await cache.get(cacheKey);
      let count: number;
      
      if (cachedValue !== null) {
        count = cachedValue;
        console.debug(`Cache hit for ${cacheKey}: ${count} items`);
      } else {
        count = await countFunction(accountId, bucketStart, bucketEnd);
        await cache.set(cacheKey, count);
        console.debug(`Cache miss for ${cacheKey}. Fetched and cached ${count} items`);
      }
      totalCount += count;
    }

    // 3. Count items in the last partial bucket (if any)
    const lastBucketEnd = alignedBuckets[alignedBuckets.length - 1][1];
    if (endTime > lastBucketEnd) {
      totalCount += await countFunction(accountId, lastBucketEnd, endTime);
    }

    return totalCount;
  }

  /**
   * Gets the count for an arbitrary time window, using cached buckets and querying for margins.
   * Implements the logic from the caching plan - this is the core method that mirrors the Python implementation exactly.
   */
  private async _getCountForWindow(
    accountId: string, 
    startTime: Date, 
    endTime: Date, 
    countFunction: CountFunction
  ): Promise<number> {
    const bucketMinutes = this.cacheBucketMinutes;
    let totalCount = 0;

    // 1. Calculate the boundaries of the fully cached portion of the window
    
    // Round start_time UP to the next bucket boundary
    // If start_time is already on a boundary, it will be moved to the next one, so we handle that.
    let cachePeriodStart: Date;
    if (startTime.getMinutes() % bucketMinutes === 0 && startTime.getSeconds() === 0 && startTime.getMilliseconds() === 0) {
      cachePeriodStart = new Date(startTime);
    } else {
      const cachePeriodStartMinute = ((Math.floor(startTime.getMinutes() / bucketMinutes)) + 1) * bucketMinutes;
      cachePeriodStart = new Date(startTime);
      cachePeriodStart.setSeconds(0);
      cachePeriodStart.setMilliseconds(0);
      
      if (cachePeriodStartMinute >= 60) {
        cachePeriodStart = new Date(cachePeriodStart.getTime() + 60 * 60 * 1000);
        cachePeriodStart.setMinutes(0);
      } else {
        cachePeriodStart.setMinutes(cachePeriodStartMinute);
      }
    }

    // Round end_time DOWN to the previous bucket boundary
    const cachePeriodEndMinute = Math.floor(endTime.getMinutes() / bucketMinutes) * bucketMinutes;
    const cachePeriodEnd = new Date(endTime);
    cachePeriodEnd.setMinutes(cachePeriodEndMinute);
    cachePeriodEnd.setSeconds(0);
    cachePeriodEnd.setMilliseconds(0);

    // 2. Check if the window is too small to contain any full buckets
    if (cachePeriodStart >= cachePeriodEnd || cachePeriodStart > endTime || cachePeriodEnd < startTime) {
      // The entire window is a margin, query it directly
      console.debug(`Window ${startTime.toISOString()} to ${endTime.toISOString()} has no full cache buckets. Querying directly.`);
      return await countFunction(accountId, startTime, endTime);
    }

    // 3. Query the start margin (if it exists)
    const startMarginEnd = new Date(Math.min(cachePeriodStart.getTime(), endTime.getTime()));
    if (startTime < startMarginEnd) {
      console.debug(`Querying start margin: ${startTime.toISOString()} to ${startMarginEnd.toISOString()}`);
      totalCount += await countFunction(accountId, startTime, startMarginEnd);
    }

    // 4. Get counts from the fully enclosed, cached buckets
    const cachedBuckets = this.getClockAlignedBuckets(cachePeriodStart, cachePeriodEnd, bucketMinutes);
    for (const [subStart, subEnd] of cachedBuckets) {
      totalCount += await this.getCountWithCaching(accountId, subStart, subEnd, countFunction);
    }

    // 5. Query the end margin (if it exists)
    if (endTime > cachePeriodEnd) {
      console.debug(`Querying end margin: ${cachePeriodEnd.toISOString()} to ${endTime.toISOString()}`);
      totalCount += await countFunction(accountId, cachePeriodEnd, endTime);
    }

    return totalCount;
  }

  /**
   * Calculate key metrics for score results over the last N hours.
   */
  async getScoreResultsSummary(accountId: string, hours: number = 24): Promise<ScoreResultsMetrics> {
    const endTimeUTC = new Date();
    console.log(`Calculating score results metrics for account ${accountId} over ${hours} hours`);

    const chartData: TimeBucket[] = [];

    // Create ROLLING hourly buckets, going back from the current time
    for (let i = 0; i < hours; i++) {
      const bucketEnd = new Date(endTimeUTC.getTime() - i * 60 * 60 * 1000);
      const bucketStart = new Date(endTimeUTC.getTime() - (i + 1) * 60 * 60 * 1000);

      // This is the hourly window we want to analyze.
      // It is NOT clock-aligned.
      const scoreResultsCount = await this._getCountForWindow(
        accountId, 
        bucketStart, 
        bucketEnd, 
        this.countScoreResultsInTimeframe.bind(this)
      );

      // The label should reflect the clock hour it ends in.
      const timeLabel = bucketEnd.toLocaleTimeString('en-US', { 
        hour: 'numeric', 
        hour12: true,
        timeZone: 'UTC'
      });

      chartData.push({
        time: timeLabel,
        scoreResults: scoreResultsCount,
        bucketStart: bucketStart.toISOString(),
        bucketEnd: bucketEnd.toISOString()
      });
    }

    // Reverse the data to be chronological
    chartData.reverse();

    if (chartData.length === 0) {
      return {
        scoreResultsPerHour: 0,
        scoreResultsAveragePerHour: 0,
        scoreResultsPeakHourly: 0,
        scoreResultsTotal24h: 0,
        chartData: []
      };
    }

    const totalScoreResults = chartData.reduce((sum, bucket) => sum + (bucket.scoreResults || 0), 0);
    const currentHourScoreResults = chartData[chartData.length - 1].scoreResults || 0; // The most recent hour
    const averageScoreResults = totalScoreResults / chartData.length;
    const peakScoreResults = Math.max(...chartData.map(bucket => bucket.scoreResults || 0));

    return {
      scoreResultsPerHour: currentHourScoreResults,
      scoreResultsAveragePerHour: Math.round(averageScoreResults),
      scoreResultsPeakHourly: peakScoreResults,
      scoreResultsTotal24h: totalScoreResults,
      chartData
    };
  }

  /**
   * Calculate key metrics for items over the last N hours.
   */
  async getItemsSummary(accountId: string, hours: number = 24): Promise<ItemsMetrics> {
    const endTimeUTC = new Date();
    console.log(`Calculating item metrics for account ${accountId} over ${hours} hours`);

    const chartData: TimeBucket[] = [];

    // Create ROLLING hourly buckets, going back from the current time
    for (let i = 0; i < hours; i++) {
      const bucketEnd = new Date(endTimeUTC.getTime() - i * 60 * 60 * 1000);
      const bucketStart = new Date(endTimeUTC.getTime() - (i + 1) * 60 * 60 * 1000);

      const itemsCount = await this._getCountForWindow(
        accountId, 
        bucketStart, 
        bucketEnd, 
        this.countItemsInTimeframe.bind(this)
      );

      const timeLabel = bucketEnd.toLocaleTimeString('en-US', { 
        hour: 'numeric', 
        hour12: true,
        timeZone: 'UTC'
      });

      chartData.push({
        time: timeLabel,
        items: itemsCount,
        bucketStart: bucketStart.toISOString(),
        bucketEnd: bucketEnd.toISOString()
      });
    }

    // Reverse the data to be chronological
    chartData.reverse();

    if (chartData.length === 0) {
      return {
        itemsPerHour: 0,
        itemsAveragePerHour: 0,
        itemsPeakHourly: 0,
        itemsTotal24h: 0,
        chartData: []
      };
    }

    const totalItems = chartData.reduce((sum, bucket) => sum + (bucket.items || 0), 0);
    const currentHourItems = chartData[chartData.length - 1].items || 0;
    const averageItems = totalItems / chartData.length;
    const peakItems = Math.max(...chartData.map(bucket => bucket.items || 0));

    return {
      itemsPerHour: currentHourItems,
      itemsAveragePerHour: Math.round(averageItems),
      itemsPeakHourly: peakItems,
      itemsTotal24h: totalItems,
      chartData
    };
  }
} 