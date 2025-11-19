# Metrics Aggregation Lambda

## Overview

This Lambda function replaces the client-side metrics aggregation system with a serverless cloud-based solution. It provides **real-time** aggregation of counts for Items, Score Results, Tasks, and Evaluations with minimal latency.

## Architecture

```
DynamoDB Tables (Amplify)
    ↓ (DynamoDB Streams)
Lambda Event Source Mapping (with batching)
    ↓
Metrics Aggregation Lambda
    ↓ (GraphQL queries)
Query full 2-hour window
    ↓ (O(n) counting)
Count into all bucket sizes
    ↓ (GraphQL mutations)
Update AggregatedMetrics table
```

## Key Features

### 1. **Stream-Triggered, Query-Based Counting**
- **Trigger**: DynamoDB Streams tell us when something changed
- **Strategy**: Query the full 2-hour window (current + previous hour) and recount everything
- **Why**: Ensures accuracy, handles late-arriving data, simpler than incremental updates

### 2. **Efficient O(n) Counting**
- Single pass through all records
- Each record assigned to exactly one bucket at each level (1/5/15/60 min)
- Cross-checks verify correctness

### 3. **Throttled Invocation**
- Batching configured per table type:
  - Items: 10 records or 15 seconds
  - Score Results: 100 records or 15 seconds
  - Tasks: 1 record or 15 seconds
  - Evaluations: 1 record or 15 seconds

### 4. **Hierarchical Buckets**
- **1-minute**: Most granular, directly counted
- **5-minute**: Directly counted (not computed from 1-min)
- **15-minute**: Directly counted (not computed from 5-min)
- **60-minute**: Directly counted (not computed from 15-min)

This matches the existing client-side system's behavior.

## Files

### Core Logic
- **`handler.py`**: Lambda entry point, orchestrates the process
- **`bucket_counter.py`**: Efficient O(n) counting into hierarchical buckets
- **`graphql_queries.py`**: Queries for fetching records with pagination
- **`graphql_client.py`**: GraphQL client for API interactions

### Tests
- **`test_handler.py`**: Tests for handler utilities
- **`test_graphql_client.py`**: Tests for GraphQL operations
- **`test_bucket_counter.py`**: Tests for counting logic

### Configuration
- **`requirements.txt`**: Python dependencies
- **`LOGGING_STRATEGY.md`**: Documentation of logging approach

## Environment Variables

Required in Lambda environment:
- `PLEXUS_API_URL` or `GRAPHQL_ENDPOINT`: AppSync GraphQL endpoint
- `PLEXUS_API_KEY` or `GRAPHQL_API_KEY`: API key for authentication

For local testing, create `.env` file in `infrastructure/` directory:
```bash
PLEXUS_API_URL=https://your-appsync-endpoint.com/graphql
PLEXUS_API_KEY=da2-xxxxxxxxxxxxx
AMPLIFY_STACK_PATTERN=amplify-xxxxx-main-branch
```

## Testing Locally

```bash
cd infrastructure/lambda_functions/metrics_aggregator

# Load environment variables
export $(cat ../../.env | grep -v '^#' | xargs)

# Run tests
python test_handler.py
python test_graphql_client.py
python test_bucket_counter.py
```

## Deployment

See `infrastructure/METRICS_AGGREGATION_SETUP.md` for deployment instructions.

## How It Works

### 1. Stream Event Arrives
```python
{
  'Records': [
    {
      'eventSourceARN': 'arn:aws:dynamodb:.../table/Item-xxx/stream/...',
      'dynamodb': {
        'NewImage': {
          'accountId': {'S': 'acc-123'},
          'id': {'S': 'item-456'}
        }
      }
    }
  ]
}
```

### 2. Extract Affected Tables
Lambda identifies: `('items', 'acc-123')`

### 3. Query 2-Hour Window
```
Current time: 2:15 PM
Previous hour: 1:00 PM - 2:00 PM
Current hour: 2:00 PM - 3:00 PM
Query window: 1:00 PM - 3:00 PM
```

### 4. Count Records (O(n))
For each record:
- Parse timestamp: `2024-01-19T14:37:23Z`
- Assign to 1-min bucket: `14:37:00 - 14:38:00`
- Assign to 5-min bucket: `14:35:00 - 14:40:00`
- Assign to 15-min bucket: `14:30:00 - 14:45:00`
- Assign to 60-min bucket: `14:00:00 - 15:00:00`

### 5. Update AggregatedMetrics
Upsert all bucket counts to DynamoDB via GraphQL.

## Logging

See `LOGGING_STRATEGY.md` for details. Key points:

- **Minimal but complete**: Only log what's needed for verification
- **Cross-checks**: Verify sum of 1-min buckets equals processed records
- **Visual markers**: ✓, ✗, ⚠ for quick scanning
- **Token-efficient**: No noise from successful common cases

Example output:
```
============================================================
METRICS AGGREGATION LAMBDA
============================================================
Stream records: 15
Affected: 1 table/account pairs
  - items / acc-abc123...
Time window: 2024-01-19 13:00 to 2024-01-19 15:00

============================================================
Processing items for account acc-abc123...
============================================================
[1/3] Querying items...
[1/3] Retrieved 1,234 items records
[2/3] Counting into buckets...
  Processed: 1,234 records (0 skipped - no timestamp)
  Cross-check: 1,234 in 1-min buckets vs 1,234 records ✓
     1min:  120 buckets,  1234 total records
     5min:   24 buckets,  1234 total records
    15min:    8 buckets,  1234 total records
    60min:    2 buckets,  1234 total records
[2/3] Generated 154 bucket updates
[3/3] Updating AggregatedMetrics...
[3/3] ✓ Updated 154 buckets successfully

============================================================
✓ SUCCESS: 154 buckets updated
============================================================
```

## Performance Characteristics

### Time Complexity
- **Query**: O(n) where n = records in 2-hour window
- **Count**: O(n) single pass through records
- **Update**: O(b) where b = number of buckets (~150-200)
- **Total**: O(n) - linear in number of records

### Space Complexity
- **Records**: O(n) - all records in memory
- **Buckets**: O(b) - ~150-200 bucket counters
- **Total**: O(n) - dominated by records

### Expected Performance
- **1,000 records**: ~2-3 seconds
- **10,000 records**: ~10-15 seconds
- **100,000 records**: ~60-90 seconds

## Comparison to Client-Side System

| Aspect | Client-Side | Lambda-Based |
|--------|-------------|--------------|
| **Latency** | 10-30 seconds after page load | 1-5 seconds after record creation |
| **Accuracy** | Prone to bugs, hard to debug | Single source of truth, testable |
| **Cost** | Client compute, many API calls | Lambda invocations, fewer API calls |
| **Maintenance** | Complex distributed logic | Centralized, easier to debug |
| **Scalability** | Limited by client resources | Scales with AWS Lambda |

## Next Steps

1. **Deploy**: Follow deployment guide in `infrastructure/METRICS_AGGREGATION_SETUP.md`
2. **Monitor**: Check CloudWatch logs for the logging output described above
3. **Verify**: Compare counts with client-side system during transition period
4. **Disable**: Once verified, remove client-side aggregation code
5. **Optimize**: If needed, add caching or reduce query window based on actual usage patterns

