# Metrics Aggregation System V2

## Overview

The V2 Metrics Aggregation System is a complete rewrite of the hierarchical aggregation logic designed to eliminate double-counting issues that were present in the original system. The new system is built with testing as a first-class citizen and uses a clean separation of concerns.

## Problem Solved

The original metrics aggregation system had a critical double-counting issue where:
1. **Hierarchical Cache Dependencies**: Large buckets were cached after being computed from smaller sub-buckets
2. **Cache Pollution**: Both aggregated results and individual sub-bucket results were cached separately
3. **Inconsistent Cache States**: This led to overlapping cached data and potential double-counting

## Architecture

### Core Components

1. **`hierarchicalAggregator.ts`** - The core aggregation engine
   - Handles all hierarchical aggregation logic
   - Manages caching strategy to prevent double-counting
   - Includes validation and automatic cache cleanup

2. **`metricsAggregatorV2.ts`** - Backward-compatible interface
   - Provides the same API as the original system
   - Uses the new hierarchical aggregator under the hood
   - Maintains compatibility with existing code

3. **Comprehensive Test Suite**
   - `hierarchicalAggregator.test.ts` - Tests core aggregation logic
   - `metricsAggregatorV2.test.ts` - Tests the compatibility layer
   - 17 total tests covering all scenarios

## Key Features

### 1. No Double-Counting
- **Limited Caching Strategy**: Only small buckets (≤15 minutes) are cached directly
- **Fresh Computation**: Large buckets are always computed from smaller cached components
- **No Hierarchical Dependencies**: Prevents cache pollution and inconsistencies

### 2. Cache Validation
- **Suspicious Value Detection**: Automatically detects unreasonable cached values
- **Automatic Recomputation**: Invalid cache entries are discarded and recomputed
- **Bounds Checking**: Values outside reasonable ranges (< 0 or > 100,000) are rejected

### 3. Simplified Breakdown Strategy
- **Fixed Patterns**: Large buckets → 15min sub-buckets, medium buckets → 5min sub-buckets
- **Consistent Alignment**: All time buckets are properly aligned to their intervals
- **Predictable Behavior**: No complex recursive breakdown logic

### 4. Comprehensive Testing
- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test complex hierarchical scenarios
- **Error Handling**: Test graceful degradation on failures
- **Cache Behavior**: Validate caching strategy works correctly

## Usage

### Basic Usage
```typescript
import { getAggregatedMetrics } from './utils/metricsAggregatorV2';

const result = await getAggregatedMetrics(
  'account-id',
  'scoreResults',
  startTime,
  endTime,
  'scorecard-id',
  'score-id'
);

console.log(`Count: ${result.count}`);
```

### With Progress Callback
```typescript
const result = await getAggregatedMetrics(
  'account-id',
  'scoreResults',
  startTime,
  endTime,
  'scorecard-id',
  'score-id',
  (progress) => {
    console.log(`Progress: ${progress.bucketNumber}/${progress.totalBuckets}`);
  }
);
```

### Cache Management
```typescript
import { clearAggregationCache, getCacheStats } from './utils/metricsAggregatorV2';

// Clear cache
clearAggregationCache();

// Get cache statistics
const stats = getCacheStats();
console.log(`Cache size: ${stats.size} entries`);
```

## Testing

Run the test suite:
```bash
npm test -- --testPathPattern="hierarchicalAggregator|metricsAggregatorV2"
```

Run the integration test:
```bash
npx ts-node dashboard/utils/testAggregationV2.ts
```

## Migration Strategy

The V2 system is designed for gradual migration:

1. **Phase 1**: Use V2 for scoreResults aggregation only
2. **Phase 2**: Extend to support items aggregation
3. **Phase 3**: Replace original system entirely

### Current Limitations
- Only supports `scoreResults` record type
- Some legacy metrics (cost, decisionCount, etc.) return 0
- Requires GraphQL endpoint to be properly configured

## Debugging

### Cache Statistics
```typescript
const stats = getCacheStats();
console.log('Cache entries:', stats.keys);
```

### Validation Warnings
The system logs warnings when suspicious values are detected:
```
Refusing to cache suspicious value for key: { count: 200000, ... }
```

### Error Handling
All errors are logged and the system returns empty results rather than failing:
```typescript
// Returns { count: 0, cost: 0, ... } on error
const result = await getAggregatedMetrics(...);
```

## Benefits

1. **Reliability**: Comprehensive test coverage ensures correctness
2. **Performance**: Efficient caching strategy reduces redundant computations
3. **Maintainability**: Clean separation of concerns and well-documented code
4. **Debuggability**: Extensive logging and validation for troubleshooting
5. **Compatibility**: Drop-in replacement for existing aggregation calls

## Future Enhancements

1. **Items Support**: Extend to support items record type aggregation
2. **Additional Metrics**: Add support for cost, decision count, etc.
3. **Performance Optimization**: Further optimize cache hit rates
4. **Real-time Updates**: Support for streaming aggregation updates 