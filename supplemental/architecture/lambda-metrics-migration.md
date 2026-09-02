# Items Metrics Lambda Function Migration

This document describes how we've migrated the GraphQL queries and time bucket logic from the React frontend to a Python-based AWS Lambda function.

## Overview

Previously, the `useItemsMetrics` hook in the React frontend made direct GraphQL queries to calculate metrics like:
- Items per hour (current and average)
- Score results per hour (current and average)
- Peak hourly rates for dynamic gauge scaling
- 24-hour activity chart data with hourly buckets

Now, this logic has been moved to a dedicated Lambda function that can be invoked to calculate these metrics server-side.

## Files Created

### 1. Core Metrics Calculator Module
- **File**: `plexus/utils/metrics_calculator.py`
- **Purpose**: Reusable metrics calculation logic that can be used by both Lambda functions and CLI commands
- **Key Features**:
  - GraphQL API integration using requests library
  - Time bucket generation for rolling hourly metrics
  - Pagination handling for large datasets
  - Environment variable configuration
  - Comprehensive error handling and logging

### 2. Lambda Function Code
- **File**: `dashboard/amplify/functions/itemsMetricsCalculator/index.py`
- **Purpose**: AWS Lambda function that uses the factored-out metrics calculator
- **Key Features**:
  - Imports the reusable MetricsCalculator class
  - Simple event handler interface
  - Error handling and JSON response formatting
  - CORS headers for frontend integration

### 3. Lambda Dependencies
- **File**: `dashboard/amplify/functions/itemsMetricsCalculator/requirements.txt`
- **Contents**: `requests==2.31.0` and note about bundled plexus module

### 4. CDK Resource Definition
- **File**: `dashboard/amplify/functions/itemsMetricsCalculator/resource.ts`
- **Purpose**: AWS CDK stack definition for the Lambda function
- **Configuration**:
  - Runtime: Python 3.11
  - Timeout: 5 minutes (for large dataset processing)
  - Memory: 512MB
  - Environment variables for GraphQL endpoint and API key

### 5. Backend Integration
- **File**: `dashboard/amplify/backend.ts` (updated)
- **Changes**: Added ItemsMetricsCalculator stack to the Amplify backend

### 6. CLI Commands
- **File**: `plexus/cli/RecordCountCommands.py`
- **Purpose**: CLI commands for manually testing the same metrics calculation logic
- **Commands**:
  - `plexus count items` - Count items with time-based filtering
  - `plexus count scoreresults` - Count score results with time-based filtering  
  - `plexus count results` - Alias for scoreresults
- **Features**:
  - Account ID from environment or command line
  - Configurable time ranges (hours)
  - JSON output option
  - Verbose logging
  - Rich console output with tables

### 7. Main CLI Integration
- **File**: `plexus/cli/CommandLineInterface.py` (updated)
- **Purpose**: Registers the new count commands with the main Plexus CLI
- **Changes**: Added import and registration for the count command group

### 8. Unit Tests for Metrics Calculator
- **File**: `plexus/utils/test_metrics_calculator.py`
- **Purpose**: Comprehensive unit tests for the core metrics calculation logic
- **Coverage**:
  - MetricsCalculator class initialization and methods
  - GraphQL request handling (success and error cases)
  - Pagination handling
  - Time bucket generation
  - Metrics calculation with mocked data
  - Environment variable configuration

### 9. Unit Tests for CLI Commands  
- **File**: `plexus/cli/test_record_count_commands.py`
- **Purpose**: Unit tests for the CLI record count commands
- **Coverage**:
  - All CLI commands (items, scoreresults, results)
  - Command line argument parsing
  - JSON output formatting
  - Error handling and help messages

## Lambda Function Architecture

### Input
```json
{
  "accountId": "account-id-here"
}
```

### Output
```json
{
  "statusCode": 200,
  "body": {
    "scoreResultsPerHour": 42,
    "itemsPerHour": 18,
    "scoreResultsAveragePerHour": 35,
    "itemsAveragePerHour": 15,
    "itemsPeakHourly": 60,
    "scoreResultsPeakHourly": 120,
    "itemsTotal24h": 360,
    "scoreResultsTotal24h": 840,
    "chartData": [
      {
        "time": "00:00",
        "items": 10,
        "scoreResults": 15,
        "bucketStart": "2024-01-01T00:00:00Z",
        "bucketEnd": "2024-01-01T01:00:00Z"
      }
    ]
  }
}
```

## Logic Migration Details

### 1. GraphQL Queries
The following GraphQL queries were migrated from TypeScript to Python:

- `listItemByAccountIdAndCreatedAt` - for items in last hour and 24 hours
- `listScoreResultByAccountIdAndUpdatedAt` - for score results in last hour and 24 hours

### 2. Pagination Handling
- Implements the same pagination logic as the React hook
- Uses `nextToken` to fetch all pages of data
- Limits each page to 10,000 items

### 3. Time Bucket Calculation
- Generates 24 hourly buckets from 23 hours ago to now
- Filters items and score results into appropriate time buckets
- Calculates counts for each bucket

### 4. Metrics Calculation
- **Current hourly rates**: Count of items/score results in last hour
- **Average hourly rates**: Total 24h count divided by 24
- **Peak hourly rates**: Maximum count in any single hour (for gauge scaling)
- **24h totals**: Total counts over the entire 24-hour period

## Environment Variables Required

The Lambda function requires these environment variables to be set:

- `GRAPHQL_ENDPOINT`: The AppSync GraphQL API endpoint
- `GRAPHQL_API_KEY`: The API key for authentication

## Deployment Steps

1. **Deploy the Lambda function**:
   ```bash
   # From dashboard directory
   npx ampx deploy
   ```

2. **Configure environment variables**:
   After deployment, update the Lambda function's environment variables with the actual GraphQL endpoint and API key.

3. **Set up API Gateway** (optional):
   Create an API Gateway endpoint to invoke the Lambda function from the frontend.

4. **Update React components**:
   Modify the ItemsGauges component to use the new Lambda-based hook.

## Benefits of Migration

1. **Reduced Frontend Load**: Complex GraphQL queries and data processing moved to server-side
2. **Better Performance**: Lambda can handle larger datasets without blocking the UI
3. **Caching Opportunities**: Lambda results can be cached for improved performance
4. **Scalability**: Lambda scales automatically based on demand
5. **Security**: Direct database access moved to server-side, reducing client-side exposure

## Future Enhancements

1. **Caching**: Implement Redis or DynamoDB caching for frequently requested metrics
2. **Scheduled Execution**: Run metrics calculation on a schedule and store results
3. **Real-time Updates**: Use WebSockets or Server-Sent Events for real-time metric updates
4. **Additional Metrics**: Expand to calculate more complex metrics and analytics

## Testing

### Unit Tests

Run the comprehensive unit tests to verify the functionality:

```bash
# Test the core metrics calculator
python -m pytest plexus/utils/test_metrics_calculator.py -v

# Test the CLI commands
python -m pytest plexus/cli/test_record_count_commands.py -v

# Run all tests
python -m pytest plexus/utils/test_metrics_calculator.py plexus/cli/test_record_count_commands.py -v
```

### Manual CLI Testing

You can manually test the same logic that will run in Lambda using these CLI commands:

```bash
# Count items for the last 24 hours (uses PLEXUS_ACCOUNT_KEY env var)
plexus count items

# Count items with specific account ID and time range
plexus count items --account-id your-account-id --hours 12

# Count score results with JSON output
plexus count scoreresults --json-output

# Count results (alias for scoreresults) with verbose logging  
plexus count results --verbose --hours 6

# Get help for any command
plexus count --help
plexus count items --help
```

### Environment Setup for Manual Testing

Before running CLI commands, set up your environment:

```bash
# Source the .env file to load environment variables
source .env

# Or set them manually
export GRAPHQL_ENDPOINT="your-graphql-endpoint"
export GRAPHQL_API_KEY="your-api-key"
export PLEXUS_ACCOUNT_KEY="your-account-id"
```

### Lambda Function Local Testing

To test the Lambda function locally:

1. Install dependencies:
   ```bash
   cd dashboard/amplify/functions/itemsMetricsCalculator
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```bash
   export GRAPHQL_ENDPOINT="your-graphql-endpoint"
   export GRAPHQL_API_KEY="your-api-key"
   ```

3. Run the function:
   ```python
   import index
   
   event = {"accountId": "your-account-id", "hours": 24}
   context = type('Context', (), {'aws_request_id': 'test-request-id'})()
   
   result = index.lambda_handler(event, context)
   print(result)
   ```

## Migration Checklist

- [x] Create Lambda function with GraphQL query logic
- [x] Add Python dependencies (requests)
- [x] Create CDK resource definition
- [x] Integrate with Amplify backend
- [x] Create template React hook for Lambda invocation
- [ ] Configure actual GraphQL endpoint and API key
- [ ] Set up API Gateway endpoint (if needed)
- [ ] Test Lambda function with real data
- [ ] Update ItemsGauges component to use Lambda hook
- [ ] Deploy to staging environment
- [ ] Performance testing and optimization
- [ ] Deploy to production

## Troubleshooting

### Common Issues

1. **GraphQL Authentication Errors**:
   - Verify `GRAPHQL_API_KEY` is correct
   - Check API key permissions and expiration

2. **Timeout Errors**:
   - Increase Lambda timeout if processing large datasets
   - Consider implementing data pagination or filtering

3. **Memory Errors**:
   - Increase Lambda memory allocation
   - Optimize data processing to use less memory

4. **CORS Issues** (if using API Gateway):
   - Configure proper CORS headers in Lambda response
   - Set up API Gateway CORS configuration 