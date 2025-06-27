# Caching Strategy for Item Count Metrics - Simplified Client-Side Approach

This document outlines a simplified caching strategy to optimize the calculation of item and score result count metrics. The new approach moves aggregation to the client side and uses GraphQL API records for caching instead of Lambda functions and SQLite.

## Implementation Strategy Update (2025-01-XX)

**Major Simplification**: Moving from server-side Lambda aggregation to client-side aggregation with GraphQL caching:
- **Remove**: Complex Lambda function with SQLite caching
- **Add**: Simple AggregatedMetrics GraphQL model for caching
- **Move**: All aggregation logic to TypeScript client-side code
- **Benefit**: Simpler architecture, better maintainability, leverages existing GraphQL infrastructure

## 1. AggregatedMetrics Model

A new GraphQL model will store cached aggregation results:

```typescript
AggregatedMetrics: {
  accountId: string (required)           // Account segmentation
  scorecardId?: string (optional)        // Optional scorecard segmentation  
  scoreId?: string (optional)            // Optional score segmentation
  recordType: string (required)          // "items" or "scoreResults"
  timeRangeStart: datetime (required)    // Start of time bucket (aligned)
  timeRangeEnd: datetime (required)      // End of time bucket (aligned)
  numberOfMinutes: integer (required)   // Duration: 1, 5, 15, or 60 minutes
  count: integer (required)              // Aggregated count for this bucket
  cost?: integer (optional)              // Fixed-point currency values
  decisionCount?: integer (optional)     // Number of decisions made
  externalAiApiCount?: integer (optional) // External AI API calls
  cachedAiApiCount?: integer (optional)  // Cached AI API calls  
  errorCount?: integer (optional)        // Number of errors
  metadata: json (optional)              // Additional metrics data
  complete: boolean (required, default: false) // Whether aggregation is complete
  createdAt: datetime (required)
  updatedAt: datetime (required)
}
```

### GSI Indexing Strategy

Primary access patterns require these GSIs:
1. **byAccountTimeRangeRecord**: `accountId` + `timeRangeStart` + `recordType` (most common)
2. **byScorecardTimeRangeRecord**: `scorecardId` + `timeRangeStart` + `recordType` (scorecard-specific)
3. **byScoreTimeRangeRecord**: `scoreId` + `timeRangeStart` + `recordType` (score-specific)
4. **byAccountRecordType**: `accountId` + `recordType` + `timeRangeStart` (for cleanup/maintenance)

## 2. Client-Side Aggregation Algorithm

### Hierarchical Time Bucket Strategy

For any requested time range, the algorithm processes data in this hierarchy:
1. **60-minute buckets**: For whole hours fully contained in the target range
2. **15-minute buckets**: For remaining time segments ≥15 minutes
3. **5-minute buckets**: For remaining time segments ≥5 minutes  
4. **1-minute buckets**: For remaining time segments <5 minutes

### Algorithm Steps

```typescript
async function getAggregatedMetrics(
  accountId: string,
  recordType: 'items' | 'scoreResults',
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string
): Promise<AggregatedMetricsData> {
  
  let totalMetrics: AggregatedMetricsData = { count: 0 };
  let currentTime = startTime;
  
  while (currentTime < endTime) {
    // Determine the largest bucket size that fits
    const remainingMinutes = (endTime.getTime() - currentTime.getTime()) / (1000 * 60);
    
    let bucketMinutes: number;
    let bucketEnd: Date;
    
    if (remainingMinutes >= 60 && isHourAligned(currentTime)) {
      bucketMinutes = 60;
      bucketEnd = new Date(currentTime.getTime() + 60 * 60 * 1000);
    } else if (remainingMinutes >= 15 && is15MinuteAligned(currentTime)) {
      bucketMinutes = 15;
      bucketEnd = new Date(currentTime.getTime() + 15 * 60 * 1000);
    } else if (remainingMinutes >= 5 && is5MinuteAligned(currentTime)) {
      bucketMinutes = 5;
      bucketEnd = new Date(currentTime.getTime() + 5 * 60 * 1000);
    } else {
      bucketMinutes = 1;
      bucketEnd = new Date(currentTime.getTime() + 1 * 60 * 1000);
    }
    
    // Ensure we don't exceed the target end time
    if (bucketEnd > endTime) {
      bucketEnd = endTime;
      bucketMinutes = Math.ceil((bucketEnd.getTime() - currentTime.getTime()) / (1000 * 60));
    }
    
    // Try to get cached result
    const cachedResult = await getCachedAggregation(
      accountId, recordType, currentTime, bucketEnd, bucketMinutes, scorecardId, scoreId
    );
    
    if (cachedResult) {
      // Aggregate cached metrics
      totalMetrics.count += cachedResult.count;
      totalMetrics.cost = (totalMetrics.cost || 0) + (cachedResult.cost || 0);
      totalMetrics.decisionCount = (totalMetrics.decisionCount || 0) + (cachedResult.decisionCount || 0);
      totalMetrics.externalAiApiCount = (totalMetrics.externalAiApiCount || 0) + (cachedResult.externalAiApiCount || 0);
      totalMetrics.cachedAiApiCount = (totalMetrics.cachedAiApiCount || 0) + (cachedResult.cachedAiApiCount || 0);
      totalMetrics.errorCount = (totalMetrics.errorCount || 0) + (cachedResult.errorCount || 0);
    } else {
      // Perform JIT aggregation and cache result
      const metrics = await performJITAggregation(
        accountId, recordType, currentTime, bucketEnd, scorecardId, scoreId
      );
      
      await cacheAggregationResult(
        accountId, recordType, currentTime, bucketEnd, bucketMinutes, metrics, scorecardId, scoreId
      );
      
      // Aggregate JIT metrics
      totalMetrics.count += metrics.count;
      totalMetrics.cost = (totalMetrics.cost || 0) + (metrics.cost || 0);
      totalMetrics.decisionCount = (totalMetrics.decisionCount || 0) + (metrics.decisionCount || 0);
      totalMetrics.externalAiApiCount = (totalMetrics.externalAiApiCount || 0) + (metrics.externalAiApiCount || 0);
      totalMetrics.cachedAiApiCount = (totalMetrics.cachedAiApiCount || 0) + (metrics.cachedAiApiCount || 0);
      totalMetrics.errorCount = (totalMetrics.errorCount || 0) + (metrics.errorCount || 0);
    }
    
    currentTime = bucketEnd;
  }
  
  return totalMetrics;
}
```

## 3. Just-In-Time (JIT) Aggregation

When cached data is not available, perform direct GraphQL queries:

```typescript
async function performJITAggregation(
  accountId: string,
  recordType: 'items' | 'scoreResults',
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string
): Promise<AggregatedMetricsData> {
  
  if (recordType === 'items') {
    return await aggregateItemMetrics(accountId, startTime, endTime, scorecardId, scoreId);
  } else {
    return await aggregateScoreResultMetrics(accountId, startTime, endTime, scorecardId, scoreId);
  }
}

async function aggregateItemMetrics(
  accountId: string,
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string
): Promise<AggregatedMetricsData> {
  // Use existing GraphQL queries with time range filters
  // Leverage GSIs: byAccountAndCreatedAt, byScorecardAndCreatedAt, byScoreAndCreatedAt
  
  const items = await queryItems(accountId, startTime, endTime, scorecardId, scoreId);
  
  return {
    count: items.length,
    // Additional metrics would be calculated from item data
    // cost, decisionCount, etc. would come from related ScoreResults
  };
}

async function aggregateScoreResultMetrics(
  accountId: string,
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string
): Promise<AggregatedMetricsData> {
  const scoreResults = await queryScoreResults(accountId, startTime, endTime, scorecardId, scoreId);
  
  let metrics: AggregatedMetricsData = { count: scoreResults.length };
  
  // Aggregate metrics from score results
  for (const result of scoreResults) {
    if (result.cost) {
      metrics.cost = (metrics.cost || 0) + (result.cost.totalCost || 0);
      metrics.externalAiApiCount = (metrics.externalAiApiCount || 0) + (result.cost.apiCalls || 0);
    }
    // Add other metric calculations based on ScoreResult data
  }
  
  return metrics;
}
```

## 4. Cache Management

### Cache Lookup Strategy
1. Query appropriate GSI based on segmentation (account/scorecard/score)
2. Filter by `timeRangeStart` and `recordType`
3. Find exact match for `numberOfMinutes` and time range
4. Verify `complete: true` before using cached result

### Cache Storage Strategy
```typescript
interface AggregatedMetricsData {
  count: number;
  cost?: number;
  decisionCount?: number;
  externalAiApiCount?: number;
  cachedAiApiCount?: number;
  errorCount?: number;
}

async function cacheAggregationResult(
  accountId: string,
  recordType: string,
  startTime: Date,
  endTime: Date,
  numberOfMinutes: number,
  metrics: AggregatedMetricsData,
  scorecardId?: string,
  scoreId?: string
): Promise<void> {
  
  await createAggregatedMetrics({
    accountId,
    scorecardId,
    scoreId,
    recordType,
    timeRangeStart: startTime,
    timeRangeEnd: endTime,
    numberOfMinutes,
    count: metrics.count,
    cost: metrics.cost,
    decisionCount: metrics.decisionCount,
    externalAiApiCount: metrics.externalAiApiCount,
    cachedAiApiCount: metrics.cachedAiApiCount,
    errorCount: metrics.errorCount,
    complete: true,
    metadata: {
      generatedAt: new Date().toISOString(),
      bucketType: getBucketType(numberOfMinutes)
    }
  });
}
```

## 5. Integration with ItemsGauges

Update the `useItemsMetrics` hook to use the new client-side aggregation:

```typescript
export function useItemsMetrics(): UseItemsMetricsResult {
  const fetchMetrics = useCallback(async () => {
    if (!selectedAccount) return;
    
    const now = new Date();
    const last24Hours = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const lastHour = new Date(now.getTime() - 60 * 60 * 1000);
    
    // Get aggregated metrics using new client-side algorithm
    const [
      itemsMetrics24h,
      scoreResultsMetrics24h,
      itemsMetricsLastHour,
      scoreResultsMetricsLastHour,
      chartData
    ] = await Promise.all([
      getAggregatedMetrics(selectedAccount.id, 'items', last24Hours, now),
      getAggregatedMetrics(selectedAccount.id, 'scoreResults', last24Hours, now),
      getAggregatedMetrics(selectedAccount.id, 'items', lastHour, now),
      getAggregatedMetrics(selectedAccount.id, 'scoreResults', lastHour, now),
      generateChartData(selectedAccount.id, last24Hours, now)
    ]);
    
    // Calculate derived metrics
    const itemsAveragePerHour = itemsMetrics24h.count / 24;
    const scoreResultsAveragePerHour = scoreResultsMetrics24h.count / 24;
    
    return {
      itemsPerHour: itemsMetricsLastHour.count,
      scoreResultsPerHour: scoreResultsMetricsLastHour.count,
      itemsTotal24h: itemsMetrics24h.count,
      scoreResultsTotal24h: scoreResultsMetrics24h.count,
      itemsAveragePerHour,
      scoreResultsAveragePerHour,
      // New comprehensive metrics
      totalCost24h: scoreResultsMetrics24h.cost || 0,
      totalDecisions24h: scoreResultsMetrics24h.decisionCount || 0,
      totalExternalApiCalls24h: scoreResultsMetrics24h.externalAiApiCount || 0,
      totalCachedApiCalls24h: scoreResultsMetrics24h.cachedAiApiCount || 0,
      totalErrors24h: scoreResultsMetrics24h.errorCount || 0,
      costPerHour: (scoreResultsMetricsLastHour.cost || 0),
      chartData
    };
  }, [selectedAccount]);
}
```

## 6. Implementation Plan

### Phase 1: GraphQL Model Setup
1. ✅ Add AggregatedMetrics model to `amplify/data/resource.ts`
2. ✅ Configure GSI indexes for efficient querying
3. ✅ Deploy schema changes

### Phase 2: Client-Side Aggregation
1. ✅ Create `utils/metricsAggregator.ts` with core algorithm
2. ✅ Implement time bucket alignment functions
3. ✅ Add cache lookup and storage functions
4. ✅ Create JIT aggregation functions

### Phase 3: Integration
1. ✅ Update `useItemsMetrics` hook to use new aggregation
2. ✅ Remove Lambda function dependencies
3. ✅ Update ItemsGauges component if needed
4. ✅ Add error handling and loading states

### Phase 4: Cleanup
1. ✅ Remove old Lambda function code
2. ✅ Remove SQLite dependencies
3. ✅ Update documentation
4. ✅ Add unit tests for aggregation logic

## 7. Benefits of New Approach

### Simplified Architecture
- **Removed**: Complex Lambda function with SQLite caching
- **Removed**: Server-side aggregation complexity
- **Added**: Simple GraphQL model for caching
- **Added**: Client-side aggregation with clear logic

### Better Performance
- **Leverages existing GSIs**: Uses optimized DynamoDB indexes
- **Hierarchical caching**: Efficient time bucket strategy
- **Client-side control**: Better error handling and retry logic

### Improved Maintainability
- **Single language**: All logic in TypeScript
- **GraphQL consistency**: Uses same patterns as rest of app
- **Testable**: Client-side logic easier to unit test
- **Debuggable**: Client-side execution easier to debug

## 8. Migration Strategy

1. **Parallel Implementation**: Build new system alongside existing
2. **Feature Flag**: Use environment variable to switch between systems
3. **Validation**: Compare results between old and new systems
4. **Gradual Rollout**: Enable for subset of accounts first
5. **Full Migration**: Remove old system after validation complete

## 9. Current Status

### ✅ Phase 1: GraphQL Model Setup - COMPLETED
- ✅ Added AggregatedMetrics model to `amplify/data/resource.ts`
- ✅ Configured GSI indexes for efficient querying
- ✅ Deployed schema changes

### ✅ Phase 2: Client-Side Aggregation - COMPLETED
- ✅ Created `utils/metricsAggregator.ts` with core algorithm
- ✅ Implemented time bucket alignment functions
- ✅ Added cache lookup and storage functions
- ✅ Created JIT aggregation functions
- ✅ Created `utils/chartDataGenerator.ts` for chart data

### 🔄 Phase 3: Integration - IN PROGRESS
- ✅ Updated `useItemsMetrics` hook to use new aggregation
- ✅ Removed Lambda function dependencies
- ⏳ Testing integration with ItemsGauges component
- ⏳ Add error handling and loading states

### ⏳ Phase 4: Cleanup - PENDING
- ⏳ Remove old Lambda function code
- ⏳ Remove SQLite dependencies
- ⏳ Update documentation
- ⏳ Add unit tests for aggregation logic

### Ready for Testing
The new client-side aggregation system is now implemented and ready for testing:
1. **AggregatedMetrics model** deployed and available
2. **Core aggregation logic** implemented with hierarchical time buckets
3. **Chart data generation** using new system
4. **Hook integration** completed

### Next Steps
1. **Test the new system** with real data
2. **Validate caching behavior** and performance
3. **Compare results** with old Lambda system (if available)
4. **Fine-tune** based on initial testing results