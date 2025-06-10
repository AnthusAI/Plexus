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

/**
 * A utility class for calculating items and score results metrics over time periods.
 * Uses API key authentication to connect to the Plexus GraphQL API and provides
 * methods to count items and score results within specific timeframes,
 * generate time buckets, and calculate hourly rates and statistics.
 *
 * This implementation includes a SQLite-based caching layer to reduce redundant
 * API calls for overlapping time periods.
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

  private _getCacheKey(metricType: 'items' | 'scoreResults', accountId: string, startTime: Date): string {
    return `${accountId}:${metricType}:${startTime.toISOString()}`;
  }

  /**
   * Make a GraphQL request to the API using API key authentication.
   */
  private async makeGraphQLRequest(query: string, variables: Record<string, any>): Promise<any> {
    const payload = { query, variables };

    console.log('Making GraphQL request:', { 
      queryType: this.getQueryType(query),
      variables: { ...variables, _page_number: undefined }
    });

    try {
      const response = await axios.post(
        this.graphqlEndpoint,
        payload,
        {
          headers: {
            'x-api-key': this.apiKey,
            'Content-Type': 'application/json'
          },
          timeout: 60000 // 60 seconds
        }
      );

      const data = response.data as GraphQLResponse;

      if (data.errors) {
        const errorMessages = data.errors.map(e => e.message).join(', ');
        throw new Error(`GraphQL errors: ${errorMessages}`);
      }

      return data.data || {};
    } catch (error) {
      if (axios.isAxiosError(error)) {
        if (error.response) {
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
    const maxPages = 500;

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
      currentVariables._page_number = pageCount + 1;

      try {
        const data = await this.makeGraphQLRequest(query, currentVariables);
        const items = data.listItemByAccountIdAndCreatedAt?.items || [];
        const itemCount = items.length;
        totalCount += itemCount;
        pageCount++;

        console.log(`Fetched ${itemCount} items on page ${pageCount}, total so far: ${totalCount}`);

        nextToken = data.listItemByAccountIdAndCreatedAt?.nextToken;
        if (!nextToken) break;
      } catch (error) {
        console.error(`Failed to fetch items page ${pageCount + 1}:`, error);
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
    const maxPages = 500;

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
      currentVariables._page_number = pageCount + 1;

      try {
        const data = await this.makeGraphQLRequest(query, currentVariables);
        const items = data.listScoreResultByAccountIdAndUpdatedAt?.items || [];
        const itemCount = items.length;
        totalCount += itemCount;
        pageCount++;

        console.log(`Fetched ${itemCount} score results on page ${pageCount}, total so far: ${totalCount}`);

        nextToken = data.listScoreResultByAccountIdAndUpdatedAt?.nextToken;
        if (!nextToken) break;
      } catch (error) {
        console.error(`Failed to fetch score results page ${pageCount + 1}:`, error);
        break;
      }
    }

    console.log(`Found ${totalCount} score results between ${startTime.toISOString()} and ${endTime.toISOString()} (processed ${pageCount} pages)`);
    return totalCount;
  }

  /**
   * Generates a list of clock-aligned time buckets within a given time range.
   * For example, with 15-minute buckets, it will generate buckets like
   * 10:00-10:15, 10:15-10:30, etc.
   *
   * @param startTime The start of the overall time range.
   * @param endTime The end of the overall time range.
   * @param bucketSizeMinutes The size of each bucket in minutes.
   * @returns A list of tuples, where each tuple is a [start, end] Date pair for a bucket.
   */
  private getClockAlignedBuckets(startTime: Date, endTime: Date, bucketSizeMinutes: number): Array<[Date, Date]> {
    const buckets: Array<[Date, Date]> = [];
    let current = new Date(startTime);

    // Find the first aligned bucket start time
    const minutes = current.getMinutes();
    const remainder = minutes % bucketSizeMinutes;
    if (remainder !== 0) {
      current.setMinutes(minutes - remainder);
      current.setSeconds(0);
      current.setMilliseconds(0);
    }
    // If the first alignment is before the start time, move to the next one
    if (current < startTime) {
        current = new Date(current.getTime() + bucketSizeMinutes * 60 * 1000);
    }

    while (current < endTime) {
      const bucketStartTime = new Date(current);
      const bucketEndTime = new Date(bucketStartTime.getTime() + bucketSizeMinutes * 60 * 1000);

      if (bucketEndTime <= endTime) {
        buckets.push([bucketStartTime, bucketEndTime]);
      }
      current = bucketEndTime;
    }
    return buckets;
  }

  /**
   * Retrieves a count for a given time window, utilizing a cache to avoid
   * redundant queries for the same time buckets.
   *
   * @param accountId The account ID.
   * @param startTime The start of the time window.
   * @param endTime The end of the time window.
   * @param countFunction The function to call to get the count for a time range (if not cached).
   * @param metricType The type of metric being counted ('items' or 'scoreResults'), for the cache key.
   * @returns The total count for the window.
   */
  private async getCountWithCaching(
    accountId: string,
    startTime: Date,
    endTime: Date,
    countFunction: (accountId: string, startTime: Date, endTime: Date) => Promise<number>,
    metricType: 'items' | 'scoreResults'
  ): Promise<number> {
    let totalCount = 0;
    const alignedBuckets = this.getClockAlignedBuckets(startTime, endTime, this.cacheBucketMinutes);

    if (alignedBuckets.length === 0) {
      // The window is smaller than a single bucket, query directly
      return await countFunction(accountId, startTime, endTime);
    }

    let lastAlignedTime = startTime;

    // 1. Handle the initial partial bucket (if any)
    const firstBucketStartTime = alignedBuckets[0][0];
    if (firstBucketStartTime > startTime) {
      console.log(`Querying initial partial bucket: ${startTime.toISOString()} - ${firstBucketStartTime.toISOString()}`);
      totalCount += await countFunction(accountId, startTime, firstBucketStartTime);
    }

    // 2. Process the full, aligned buckets using the cache
    for (const [bucketStart, bucketEnd] of alignedBuckets) {
      const cacheKey = this._getCacheKey(metricType, accountId, bucketStart);
      let count = await cache.get(cacheKey);

      if (count === null) {
        console.log(`Cache MISS for ${metricType}. Querying bucket: ${bucketStart.toISOString()} - ${bucketEnd.toISOString()}`);
        count = await countFunction(accountId, bucketStart, bucketEnd);
        await cache.set(cacheKey, count);
      } else {
        console.log(`Cache HIT for ${metricType}. Bucket: ${bucketStart.toISOString()} - ${bucketEnd.toISOString()}`);
      }
      totalCount += count;
      lastAlignedTime = bucketEnd;
    }

    // 3. Handle the final partial bucket (if any)
    if (endTime > lastAlignedTime) {
      console.log(`Querying final partial bucket: ${lastAlignedTime.toISOString()} - ${endTime.toISOString()}`);
      totalCount += await countFunction(accountId, lastAlignedTime, endTime);
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

      // Count score results in this hourly window
      const scoreResultsCount = await this.getCountWithCaching(
        accountId,
        bucketStart,
        bucketEnd,
        this.countScoreResultsInTimeframe.bind(this),
        'scoreResults'
      );

      // Format the time label
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
    const currentHourScoreResults = chartData[chartData.length - 1].scoreResults || 0;
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

      // Count items in this hourly window
      const itemsCount = await this.getCountWithCaching(
        accountId,
        bucketStart,
        bucketEnd,
        this.countItemsInTimeframe.bind(this),
        'items'
      );

      // Format the time label
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