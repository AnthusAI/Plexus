"""
Efficient bucket counting for metrics aggregation.

This module handles counting records into multiple time buckets efficiently
by iterating through the data once and assigning each record to all relevant buckets.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Set
from collections import defaultdict


class BucketCounter:
    """
    Efficiently counts records into multiple hierarchical time buckets.
    
    For each record, determines which 1min, 5min, 15min, and 60min buckets
    it belongs to and increments the appropriate counters.
    """
    
    # Bucket sizes we track (in minutes)
    BUCKET_SIZES = [1, 5, 15, 60]
    
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
            timestamp: When the record was created
        """
        # Add to each bucket size
        for bucket_minutes in self.BUCKET_SIZES:
            bucket_start = self._align_to_bucket(timestamp, bucket_minutes)
            key = (bucket_start, bucket_minutes)
            self.buckets[key] += 1
    
    def get_bucket_counts(self) -> List[Dict[str, any]]:
        """
        Get all bucket counts as a list ready for GraphQL updates.
        
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
                'time_range_start': bucket_start.isoformat().replace('+00:00', 'Z'),
                'time_range_end': bucket_end.isoformat().replace('+00:00', 'Z'),
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


def get_time_window() -> Tuple[datetime, datetime]:
    """
    Get the time window to query (current hour + previous hour).
    
    Returns:
        Tuple of (start_time, end_time) for the 2-hour window
    """
    now = datetime.now(timezone.utc)
    
    # Current hour start (e.g., if it's 2:15, this is 2:00)
    current_hour_start = now.replace(minute=0, second=0, microsecond=0)
    
    # Previous hour start (e.g., if it's 2:15, this is 1:00)
    previous_hour_start = current_hour_start - timedelta(hours=1)
    
    # End time is the start of the next hour (e.g., if it's 2:15, this is 3:00)
    end_time = current_hour_start + timedelta(hours=1)
    
    return previous_hour_start, end_time


def count_records_efficiently(records: List[Dict[str, any]], 
                              account_id: str, 
                              record_type: str,
                              filter_field: str = None,
                              filter_value: str = None) -> List[Dict[str, any]]:
    """
    Efficiently count records into all relevant buckets.
    
    This is an O(n) operation that processes each record once and assigns
    it to all relevant bucket sizes (1min, 5min, 15min, 60min).
    
    Args:
        records: List of records with 'createdAt' or 'updatedAt' timestamps
        account_id: Account ID
        record_type: Type of records
        filter_field: Optional field name to filter by (e.g., 'type')
        filter_value: Optional value to filter for (e.g., 'prediction')
        
    Returns:
        List of bucket counts ready for GraphQL updates
    """
    counter = BucketCounter(account_id, record_type)
    
    processed = 0
    skipped = 0
    filtered_out = 0
    
    for record in records:
        # Apply filter if specified
        if filter_field and filter_value:
            if record.get(filter_field) != filter_value:
                filtered_out += 1
                continue
        
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
    
    # Log counting summary with cross-checks
    filter_msg = f", {filtered_out} filtered out" if filter_field else ""
    print(f"  Processed: {processed} records ({skipped} skipped - no timestamp{filter_msg})")
    
    # Cross-check: sum of 1-min buckets should equal processed records
    one_min_total = sum(b['count'] for b in bucket_counts if b['number_of_minutes'] == 1)
    match = "✓" if one_min_total == processed else "✗ MISMATCH"
    print(f"  Cross-check: {one_min_total} in 1-min buckets vs {processed} records {match}")
    
    # Show distribution by bucket size
    for size in BucketCounter.BUCKET_SIZES:
        size_buckets = [b for b in bucket_counts if b['number_of_minutes'] == size]
        size_total = sum(b['count'] for b in size_buckets)
        print(f"    {size:2d}min: {len(size_buckets):3d} buckets, {size_total:5d} total records")
    
    return bucket_counts


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

