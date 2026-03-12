# Metrics Count Verification Tool

This directory contains a standalone verification tool for checking and correcting aggregated metrics counts in the `AggregatedMetrics` table.

## Purpose

The tool uses the same counting logic as the Lambda function to:
1. Query records from the current and previous calendar hours
2. Count them into hierarchical time buckets (1/5/15/60 minutes)
3. Compare with existing `AggregatedMetrics` records
4. Optionally fix any incorrect or missing counts

## Files

- **`counting_core.py`**: Shared counting logic used by both Lambda and CLI
- **`verify_counts.py`**: Standalone verification script
- **`test_verify_counts.py`**: Unit tests for the counting logic

## Setup

1. Ensure you have the required environment variables set in `infrastructure/.env`:

```bash
# Plexus API Configuration
PLEXUS_API_URL=https://your-appsync-endpoint.appsync-api.us-west-2.amazonaws.com/graphql
PLEXUS_API_KEY=da2-xxxxxxxxxxxxxxxxxxxxxxxxxx

# Account Configuration
PLEXUS_ACCOUNT_KEY=call-criteria
```

2. Load the environment variables:

```bash
cd /path/to/Plexus
export $(cat infrastructure/.env | grep -v '^#' | xargs)
```

## Usage

### Dry Run (Check Only)

Check counts without making any changes:

```bash
cd plexus/cli/metrics
python verify_counts.py --dry-run
```

This will:
- Query all records in the current + previous hour
- Count them into buckets
- Compare with existing `AggregatedMetrics`
- Report any differences
- **NOT update** the database

### Fix Incorrect Counts

Actually update incorrect counts:

```bash
python verify_counts.py --no-dry-run
```

This will:
- Do everything the dry run does
- **Update** any incorrect or missing `AggregatedMetrics` records

### Check Specific Record Type

Check only one type of record:

```bash
python verify_counts.py --dry-run --record-type items
python verify_counts.py --dry-run --record-type scoreResults
python verify_counts.py --dry-run --record-type tasks
python verify_counts.py --dry-run --record-type evaluations
```

## Example Output

```
Initializing client...
Checking metrics for account: Call Criteria (acc-abc123...)
Time window: 2024-01-19 13:00 to 2024-01-19 15:00

[DRY RUN MODE] - Will not update any records

Processing items...
  Querying items from 13:00 to 15:00...
  Retrieved 1,234 records
  Counting into buckets...
  Counted into 154 buckets
  Comparing with existing metrics...
  Differences found:
    14:35-14:40 (5min): DB has 230, should be 234 (off by +4)
    14:00-15:00 (60min): DB has 1200, should be 1234 (off by +34)
  Summary: 152 correct, 2 incorrect, 0 missing (of 154 total)
  [DRY RUN] Would update 2 buckets

Processing scoreResults...
  Querying scoreResults from 13:00 to 15:00...
  Retrieved 456 records
  Counting into buckets...
  Counted into 154 buckets
  Comparing with existing metrics...
  Summary: 154 correct, 0 incorrect, 0 missing (of 154 total)

============================================================
Found 2 incorrect/missing counts (out of 308 checked)
Run without --dry-run to fix them
============================================================
```

## Running Tests

```bash
cd plexus/cli/metrics
python -m pytest test_verify_counts.py -v
```

Or with the standard unittest runner:

```bash
python test_verify_counts.py
```

## How It Works

1. **Account Lookup**: Uses `PLEXUS_ACCOUNT_KEY` to find the account via `Account.get_by_key()`
2. **Time Window**: Calculates current + previous calendar hour (same as Lambda)
3. **Query Records**: Fetches all records in the 2-hour window via GraphQL
4. **Count Efficiently**: Uses O(n) algorithm to assign each record to all relevant buckets
5. **Compare**: Queries existing `AggregatedMetrics` and compares counts
6. **Update**: If not dry-run, updates or creates `AggregatedMetrics` records

## Technical Notes

- **Same Logic as Lambda**: Uses identical counting logic to ensure consistency
- **Read-Only by Default**: Dry-run mode is the default to prevent accidental updates
- **Handles Pagination**: Automatically pages through GraphQL results
- **Cross-Checks**: Verifies that sum of 1-min buckets equals total records
- **Error Handling**: Continues processing even if individual updates fail

## Troubleshooting

### "PLEXUS_ACCOUNT_KEY environment variable not set"

Make sure you've loaded the environment variables:

```bash
export $(cat infrastructure/.env | grep -v '^#' | xargs)
```

### "Account not found for key: xxx"

Check that the account key in your `.env` file matches an existing account in the database.

### Import Errors

Make sure you're running from the correct directory and have the Plexus package in your Python path:

```bash
cd plexus/cli/metrics
python verify_counts.py
```

The script automatically adds the parent directories to the Python path.

