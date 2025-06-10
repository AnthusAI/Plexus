# Caching Strategy for Item Count Metrics

This document outlines a caching strategy to optimize the calculation of item and score result count metrics. The goal is to reduce the number of queries to the backend by caching counts in small, time-aligned buckets.

## Implementation Strategy Update (2025-06-10)

Due to cyclic dependency issues with Python Lambda deployment in AWS Amplify, we have implemented a dual-language strategy:
- **TypeScript**: Lambda function implementation (COMPLETED)
- **Python**: For CLI tools and MCP server (existing implementation maintained)

## 1. Caching Mechanism

- **Cache Granularity:** The core of the caching mechanism will be 5-minute, clock-aligned time buckets.
- **Bucket Alignment:** These buckets will align with the clock, starting at `:00`, `:05`, `:10`, etc., for every hour. For example, `10:00:00 - 10:04:59`.
- **Cached Data:** The cache will store the total count of items and score results for each 5-minute bucket. We will not cache the individual item IDs, only the aggregate counts.
- **Cache Storage:** 
  - **TypeScript Lambda**: Currently using direct GraphQL queries without caching (future enhancement: DynamoDB cache)
  - **Python CLI**: SQLite for local persistence

## 2. Configurable Bucket Width
The width of the cache buckets will be configurable.
- **Default Width:** The default width will be 5 minutes.
- **Configuration:** This will be a parameter in the `MetricsCalculator` class, making it easy to adjust for different performance needs (e.g., switching to 1-minute buckets).

## 3. Cache Storage

### Python Implementation (CLI Tools)
To provide persistence for local development and CLI tools, the caching mechanism will use a local SQLite database.

- **Database File:** The cache will be stored in a local SQLite file (e.g., `tmp/metrics_cache.db`).
- **Cache Table:** A simple table will be created to store the cache keys and their corresponding counts.

### TypeScript Implementation (Lambda) - Future Enhancement
For the Lambda function, we'll use DynamoDB for distributed caching:

- **DynamoDB Table**: A dedicated cache table with TTL for automatic cleanup
- **Key Structure**: Composite key of account ID, metric type, and time bucket
- **TTL**: Set to expire cached entries after 24 hours

## 4. Querying and Caching Logic

The primary analysis will continue to be performed on hourly buckets relative to the current time (e.g., the last hour, the hour before that). However, the data for these hourly buckets will be assembled using the cached buckets.

### Algorithm

For each hourly analysis bucket:

1.  **Identify Sub-Buckets:** Determine the set of 5-minute, clock-aligned buckets that are fully contained within the hourly bucket's time range.

2.  **Handle Overlaps:** The start and end times of the hourly bucket will likely not align perfectly with the 5-minute clock buckets. This creates two "partial" or "overlap" periods:
    *   One at the beginning of the hourly bucket.
    *   One at the end of the hourly bucket.

3.  **Fetch from Cache:**
    *   For each of the fully-contained 5-minute buckets, check if its count is already in the cache.
    *   If a bucket's count is **not** in the cache, perform a GraphQL query to fetch the count for that 5-minute interval.
    *   Store the newly fetched count in the cache for future use.

4.  **Query Overlaps:**
    *   Perform two separate, precise GraphQL queries for the small, non-aligned overlap periods at the start and end of the hourly bucket. These overlap periods will always be less than 5 minutes long. The results of these queries will not be cached.

5.  **Calculate Total:** The total count for the hourly analysis bucket is the sum of:
    *   The counts from all the fully-contained 5-minute buckets (retrieved from the cache or newly fetched).
    *   The counts from the two overlap queries.

## 5. Implementation Status

### Phase 1: TypeScript Lambda Implementation ✅ COMPLETED
1. **Location**: `dashboard/amplify/functions/itemsMetricsCalculator/`
2. **Components Implemented**:
   - ✅ MetricsCalculator class ported from Python to TypeScript
   - ✅ Lambda handler function (`index.ts`)
   - ✅ GraphQL queries using axios
   - ✅ Package configuration (`package.json`, `tsconfig.json`)
   - ✅ CDK resource configuration updated for Node.js runtime
   - ✅ Direct AppSync resolver integration in `backend.ts`
   - ✅ In-memory caching layer with TTL (suitable for Lambda environment)
   - ✅ Cache cleanup on Lambda execution completion
   
3. **Architecture Notes**:
   - Replaced SQLite dependency with in-memory cache (better for Lambda)
   - Cache persists only for single Lambda execution (stateless)
   - 5-minute TTL for cache entries within execution
   
4. **Future Enhancements**:
   - Add DynamoDB distributed caching layer
   - Add comprehensive unit tests

### Phase 2: Python CLI Implementation (Existing)
1. **Location**: `plexus/metrics/calculator.py`
2. **Components**:
   - ✅ Existing implementation maintained
   - ✅ SQLite caching layer
   - ✅ Backward compatibility
   - ✅ Tests in `test_metrics_calculator.py`

### Phase 3: Testing and Validation
1. **Cross-validation**: Ensure TypeScript and Python implementations produce identical results
2. **Performance testing**: Measure query performance in Lambda environment
3. **Integration testing**: Test AppSync resolver integration

## 6. Current Status & Next Steps

### ✅ Deployment Ready (2025-06-10)
The TypeScript Lambda implementation is now deployment-ready with:
- Removed SQLite dependency (replaced with in-memory cache)
- Fixed package.json dependencies 
- Updated cache implementation for Lambda environment
- Added cache cleanup on execution completion

### Immediate Actions
1. **Deploy and Test**:
   - Deploy the updated TypeScript Lambda function
   - Test the AppSync resolver integration
   - Monitor performance and error rates
   - Validate metrics accuracy against Python implementation

### Future Enhancements
2. **Add Distributed Caching**:
   - Create DynamoDB cache table
   - Implement distributed cache read/write logic
   - Add cache hit/miss metrics and monitoring

3. **Performance Optimization**:
   - Implement parallel query execution for multiple time buckets
   - Add request batching for GraphQL queries
   - Optimize memory usage for large result sets
   - Add comprehensive unit and integration tests