"""
Aggregation logic for processing DynamoDB stream records.

This module handles retroactive counting of records in time buckets.
When triggered by stream events, it:
1. Identifies affected time buckets (current + previous hour)
2. Queries DynamoDB to count ALL records in those buckets
3. Updates AggregatedMetrics with actual counts

This replaces the client-side aggregation entirely.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict


class MetricsAggregator:
    """
    Aggregates counts from DynamoDB stream records into time buckets.
    """
    
    # Bucket sizes in minutes
    BUCKET_SIZES = [1, 5, 15, 60]
    
    def __init__(self):
        """Initialize the aggregator."""
        self.counts = defaultdict(lambda: defaultdict(int))
    
    def process_stream_records(self, records: List[Dict[str, Any]]) -> Dict[str, List[Tuple[str, str, int, int]]]:
        """
        Process DynamoDB stream records and aggregate counts.
        
        Args:
            records: List of DynamoDB stream records
            
        Returns:
            Dict mapping record types to list of (start_time, end_time, count, bucket_minutes) tuples
        """
        # Group records by type and time bucket
        for record in records:
            event_name = record.get('eventName')
            
            # Only count INSERT events (new records)
            if event_name != 'INSERT':
                continue
            
            # Extract the new image
            new_image = record.get('dynamodb', {}).get('NewImage', {})
            if not new_image:
                continue
            
            # Determine record type from the stream ARN
            event_source_arn = record.get('eventSourceARN', '')
            record_type = self._determine_record_type(event_source_arn)
            
            if not record_type:
                continue
            
            # Extract timestamp
            timestamp = self._extract_timestamp(new_image, record_type)
            if not timestamp:
                continue
            
            # Extract account ID
            account_id = self._extract_account_id(new_image)
            if not account_id:
                continue
            
            # Increment counts for all bucket sizes
            for bucket_minutes in self.BUCKET_SIZES:
                bucket_start = self._align_to_bucket(timestamp, bucket_minutes)
                bucket_key = (record_type, account_id, bucket_start, bucket_minutes)
                self.counts[bucket_key]['count'] += 1
        
        # Convert to output format
        return self._format_results()
    
    def _determine_record_type(self, event_source_arn: str) -> str:
        """
        Determine the record type from the DynamoDB stream ARN.
        
        Args:
            event_source_arn: DynamoDB stream ARN
            
        Returns:
            Record type string ('items', 'scoreResults', 'tasks', 'evaluations')
        """
        arn_lower = event_source_arn.lower()
        
        if 'item' in arn_lower and 'feedback' not in arn_lower:
            return 'items'
        elif 'scoreresult' in arn_lower:
            return 'scoreResults'
        elif 'task' in arn_lower:
            return 'tasks'
        elif 'evaluation' in arn_lower:
            return 'evaluations'
        
        return ''
    
    def _extract_timestamp(self, dynamo_item: Dict[str, Any], record_type: str) -> datetime:
        """
        Extract timestamp from DynamoDB item.
        
        Args:
            dynamo_item: DynamoDB item in stream format
            record_type: Type of record
            
        Returns:
            Datetime object
        """
        # Try createdAt first (most common)
        if 'createdAt' in dynamo_item:
            timestamp_str = dynamo_item['createdAt'].get('S', '')
            if timestamp_str:
                return self._parse_iso_datetime(timestamp_str)
        
        # Fall back to updatedAt
        if 'updatedAt' in dynamo_item:
            timestamp_str = dynamo_item['updatedAt'].get('S', '')
            if timestamp_str:
                return self._parse_iso_datetime(timestamp_str)
        
        # Use current time as fallback
        return datetime.now(timezone.utc)
    
    def _extract_account_id(self, dynamo_item: Dict[str, Any]) -> str:
        """
        Extract account ID from DynamoDB item.
        
        Args:
            dynamo_item: DynamoDB item in stream format
            
        Returns:
            Account ID string
        """
        if 'accountId' in dynamo_item:
            return dynamo_item['accountId'].get('S', '')
        return ''
    
    def _parse_iso_datetime(self, timestamp_str: str) -> datetime:
        """
        Parse ISO 8601 datetime string.
        
        Args:
            timestamp_str: ISO datetime string
            
        Returns:
            Datetime object
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
            # Fall back to current time
            return datetime.now(timezone.utc)
    
    def _align_to_bucket(self, timestamp: datetime, bucket_minutes: int) -> datetime:
        """
        Align a timestamp to the start of a time bucket.
        
        Args:
            timestamp: Datetime to align
            bucket_minutes: Bucket size in minutes
            
        Returns:
            Aligned datetime
        """
        # Get minutes since epoch
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        minutes_since_epoch = int((timestamp - epoch).total_seconds() / 60)
        
        # Round down to bucket boundary
        bucket_start_minutes = (minutes_since_epoch // bucket_minutes) * bucket_minutes
        
        # Convert back to datetime
        return epoch + timedelta(minutes=bucket_start_minutes)
    
    def _format_results(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Format aggregated results for output.
        
        Returns:
            Dict mapping record types to list of aggregation dicts
        """
        results = defaultdict(list)
        
        for (record_type, account_id, bucket_start, bucket_minutes), data in self.counts.items():
            bucket_end = bucket_start + timedelta(minutes=bucket_minutes)
            
            # Determine if bucket is complete (in the past)
            now = datetime.now(timezone.utc)
            is_complete = bucket_end <= now
            
            results[record_type].append({
                'account_id': account_id,
                'time_range_start': bucket_start.isoformat().replace('+00:00', 'Z'),
                'time_range_end': bucket_end.isoformat().replace('+00:00', 'Z'),
                'number_of_minutes': bucket_minutes,
                'count': data['count'],
                'complete': is_complete
            })
        
        return dict(results)


def process_stream_batch(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process a batch of DynamoDB stream records.
    
    Args:
        records: List of DynamoDB stream records from Lambda event
        
    Returns:
        Dict mapping record types to aggregation results
    """
    aggregator = MetricsAggregator()
    return aggregator.process_stream_records(records)

