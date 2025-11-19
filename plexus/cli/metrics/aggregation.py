"""
Core counting and aggregation logic for metrics.

This module provides the shared counting logic used by both the Lambda function
and the CLI commands. It queries records in a time window and counts them into
hierarchical time buckets (1/5/15/60 minutes).

The logic is designed to be O(n) - each record is processed once and assigned
to all relevant bucket sizes simultaneously.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Any, Optional, TYPE_CHECKING
from collections import defaultdict

if TYPE_CHECKING:
    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.dashboard.api.models.aggregated_metrics import AggregatedMetrics


# Bucket sizes we track (in minutes)
BUCKET_SIZES = [1, 5, 15, 60]


class BucketCounter:
    """
    Efficiently counts records into multiple hierarchical time buckets.
    
    For each record, determines which 1min, 5min, 15min, and 60min buckets
    it belongs to and increments the appropriate counters.
    """
    
    def __init__(self, account_id: str, record_type: str):
        """
        Initialize bucket counter.
        
        Args:
            account_id: Account ID for these metrics
            record_type: Type of records ('items', 'scoreResults', 'tasks', 'evaluations')
        """
        self.account_id = account_id
        self.record_type = record_type
        
        # Counters: (bucket_start_time, bucket_minutes) -> count
        self.buckets: Dict[Tuple[datetime, int], int] = defaultdict(int)
    
    def add_record(self, timestamp: datetime) -> None:
        """
        Add a record to all relevant buckets.
        
        Args:
            timestamp: When the record was created/updated
        """
        # Add to each bucket size
        for bucket_minutes in BUCKET_SIZES:
            bucket_start = self._align_to_bucket(timestamp, bucket_minutes)
            key = (bucket_start, bucket_minutes)
            self.buckets[key] += 1
    
    def get_bucket_counts(self) -> List[Dict[str, Any]]:
        """
        Get all bucket counts as a list ready for ORM updates.
        
        Returns:
            List of dicts with bucket info and counts
        """
        now = datetime.now(timezone.utc)
        results = []
        
        for (bucket_start, bucket_minutes), count in self.buckets.items():
            bucket_end = bucket_start + timedelta(minutes=bucket_minutes)
            
            # Determine if bucket is complete (entirely in the past)
            is_complete = bucket_end <= now
            
            results.append({
                'account_id': self.account_id,
                'record_type': self.record_type,
                'time_range_start': bucket_start,
                'time_range_end': bucket_end,
                'number_of_minutes': bucket_minutes,
                'count': count,
                'complete': is_complete
            })
        
        return results
    
    def _align_to_bucket(self, timestamp: datetime, bucket_minutes: int) -> datetime:
        """
        Align a timestamp to the start of its bucket.
        
        Args:
            timestamp: Datetime to align
            bucket_minutes: Bucket size in minutes
            
        Returns:
            Aligned datetime at bucket start
        """
        # Get minutes since epoch
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        minutes_since_epoch = int((timestamp - epoch).total_seconds() / 60)
        
        # Round down to bucket boundary
        bucket_start_minutes = (minutes_since_epoch // bucket_minutes) * bucket_minutes
        
        # Convert back to datetime
        return epoch + timedelta(minutes=bucket_start_minutes)


def parse_iso_datetime(timestamp_str: str) -> datetime:
    """
    Parse ISO 8601 datetime string.
    
    Args:
        timestamp_str: ISO datetime string (e.g., "2024-01-01T12:00:00Z")
        
    Returns:
        Datetime object with UTC timezone
    """
    try:
        # Remove 'Z' suffix if present and add UTC timezone
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str[:-1] + '+00:00'
        
        # Parse with timezone
        dt = datetime.fromisoformat(timestamp_str)
        
        # Ensure UTC timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        return dt
    except (ValueError, AttributeError):
        # Fall back to current time if parsing fails
        return datetime.now(timezone.utc)


def count_records_efficiently(
    records: List[Dict[str, Any]], 
    account_id: str, 
    record_type: str,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    Efficiently count records into all relevant buckets.
    
    This is an O(n) operation that processes each record once and assigns
    it to all relevant bucket sizes (1min, 5min, 15min, 60min).
    
    Args:
        records: List of records with 'createdAt' or 'updatedAt' timestamps
        account_id: Account ID
        record_type: Type of records
        verbose: If True, print detailed counting statistics
        
    Returns:
        List of bucket counts ready for ORM updates
    """
    counter = BucketCounter(account_id, record_type)
    
    processed = 0
    skipped = 0
    
    for record in records:
        # Extract timestamp (try createdAt first, then updatedAt)
        timestamp_str = record.get('createdAt') or record.get('updatedAt')
        if not timestamp_str:
            skipped += 1
            continue
        
        # Parse timestamp
        timestamp = parse_iso_datetime(timestamp_str)
        
        # Add to all relevant buckets
        counter.add_record(timestamp)
        processed += 1
    
    # Get bucket counts
    bucket_counts = counter.get_bucket_counts()
    
    if verbose:
        # Log counting summary with cross-checks
        print(f"  Processed: {processed} records ({skipped} skipped - no timestamp)")
        
        # Cross-check: sum of 1-min buckets should equal processed records
        one_min_total = sum(b['count'] for b in bucket_counts if b['number_of_minutes'] == 1)
        match = "✓" if one_min_total == processed else "✗ MISMATCH"
        print(f"  Cross-check: {one_min_total} in 1-min buckets vs {processed} records {match}")
        
        # Show distribution by bucket size
        for size in BUCKET_SIZES:
            size_buckets = [b for b in bucket_counts if b['number_of_minutes'] == size]
            size_total = sum(b['count'] for b in size_buckets)
            print(f"    {size:2d}min: {len(size_buckets):3d} buckets, {size_total:5d} total records")
    
    return bucket_counts


def query_records_for_counting(
    client: 'PlexusDashboardClient',
    account_id: str,
    record_type: str,
    start_time: datetime,
    end_time: datetime,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    Query records from the API for counting.
    
    Uses the appropriate GraphQL query based on record type and handles pagination.
    
    Args:
        client: The API client
        account_id: Account ID to filter by
        record_type: Type of records ('items', 'scoreResults', 'tasks', 'evaluations')
        start_time: Start of time range
        end_time: End of time range
        verbose: If True, print query progress
        
    Returns:
        List of record dictionaries with timestamps
    """
    if record_type == 'items':
        return _query_items(client, account_id, start_time, end_time, verbose)
    elif record_type == 'scoreResults':
        return _query_score_results(client, account_id, start_time, end_time, verbose)
    elif record_type == 'tasks':
        return _query_tasks(client, account_id, start_time, end_time, verbose)
    elif record_type == 'evaluations':
        return _query_evaluations(client, account_id, start_time, end_time, verbose)
    else:
        raise ValueError(f"Unknown record type: {record_type}")


def _paginated_query(
    client: 'PlexusDashboardClient',
    query: str,
    variables: Dict[str, Any],
    result_key: str,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    Execute a paginated GraphQL query.
    
    Args:
        client: The API client
        query: GraphQL query string
        variables: Query variables
        result_key: Key in result to extract items from
        verbose: If True, print pagination progress
        
    Returns:
        List of all items across all pages
    """
    all_items = []
    next_token = None
    page_count = 0
    
    while True:
        page_count += 1
        if next_token:
            variables['nextToken'] = next_token
        
        result = client.execute(query, variables)
        items = result.get(result_key, {}).get('items', [])
        all_items.extend(items)
        
        next_token = result.get(result_key, {}).get('nextToken')
        
        # Only log if multiple pages or if there's more to come
        if verbose and (page_count > 1 or next_token):
            print(f"  Page {page_count}: +{len(items)} records (total: {len(all_items)})")
        
        if not next_token:
            break
    
    if verbose and page_count > 1:
        print(f"  Fetched {len(all_items)} records across {page_count} pages")
    
    return all_items


def _query_items(
    client: 'PlexusDashboardClient',
    account_id: str,
    start_time: datetime,
    end_time: datetime,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """Query Items in time window."""
    query = """
    query ListItemsByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listItemByAccountIdAndCreatedAt(
            accountId: $accountId,
            createdAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                createdAt
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listItemByAccountIdAndCreatedAt',
        verbose
    )


def _query_score_results(
    client: 'PlexusDashboardClient',
    account_id: str,
    start_time: datetime,
    end_time: datetime,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """Query ScoreResults in time window."""
    query = """
    query ListScoreResultsByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listScoreResultByAccountIdAndUpdatedAt(
            accountId: $accountId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                updatedAt
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listScoreResultByAccountIdAndUpdatedAt',
        verbose
    )


def _query_tasks(
    client: 'PlexusDashboardClient',
    account_id: str,
    start_time: datetime,
    end_time: datetime,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """Query Tasks in time window."""
    query = """
    query ListTasksByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listTaskByAccountIdAndUpdatedAt(
            accountId: $accountId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                createdAt
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listTaskByAccountIdAndUpdatedAt',
        verbose
    )


def _query_evaluations(
    client: 'PlexusDashboardClient',
    account_id: str,
    start_time: datetime,
    end_time: datetime,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """Query Evaluations in time window."""
    query = """
    query ListEvaluationsByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listEvaluationByAccountIdAndUpdatedAt(
            accountId: $accountId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                updatedAt
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listEvaluationByAccountIdAndUpdatedAt',
        verbose
    )
