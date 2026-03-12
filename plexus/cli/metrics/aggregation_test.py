"""
Tests for aggregation and counting logic.

These tests verify:
1. BucketCounter with sample data
2. Bucket assignment logic
3. O(n) iteration correctness
4. Cross-check validation
"""

import pytest
from datetime import datetime, timezone, timedelta
from .aggregation import (
    BucketCounter,
    parse_iso_datetime,
    count_records_efficiently,
    BUCKET_SIZES
)


def test_bucket_counter_basic():
    """Test basic bucket counting"""
    counter = BucketCounter('acc-123', 'items')
    
    # Add a record
    timestamp = datetime(2024, 11, 19, 14, 30, 0, tzinfo=timezone.utc)
    counter.add_record(timestamp)
    
    # Should have buckets for all sizes
    assert len(counter.buckets) == len(BUCKET_SIZES)
    
    # Each bucket should have count of 1
    for bucket_size in BUCKET_SIZES:
        matching_buckets = [
            (start, size) for (start, size) in counter.buckets.keys()
            if size == bucket_size
        ]
        assert len(matching_buckets) == 1
        assert counter.buckets[matching_buckets[0]] == 1


def test_bucket_counter_multiple_records():
    """Test counting multiple records"""
    counter = BucketCounter('acc-123', 'items')
    
    # Add 3 records in the same minute
    base_time = datetime(2024, 11, 19, 14, 30, 0, tzinfo=timezone.utc)
    for i in range(3):
        timestamp = base_time + timedelta(seconds=i*10)
        counter.add_record(timestamp)
    
    # 1-minute bucket should have count of 3
    one_min_buckets = [
        (start, size) for (start, size) in counter.buckets.keys()
        if size == 1
    ]
    assert len(one_min_buckets) == 1
    assert counter.buckets[one_min_buckets[0]] == 3


def test_bucket_counter_alignment():
    """Test that timestamps are properly aligned to bucket boundaries"""
    counter = BucketCounter('acc-123', 'items')
    
    # Add record at 14:32:45
    timestamp = datetime(2024, 11, 19, 14, 32, 45, tzinfo=timezone.utc)
    counter.add_record(timestamp)
    
    counts = counter.get_bucket_counts()
    
    # Find the 1-minute bucket
    one_min_bucket = [c for c in counts if c['number_of_minutes'] == 1][0]
    
    # Should be aligned to 14:32:00
    assert one_min_bucket['time_range_start'].minute == 32
    assert one_min_bucket['time_range_start'].second == 0
    
    # Find the 5-minute bucket
    five_min_bucket = [c for c in counts if c['number_of_minutes'] == 5][0]
    
    # Should be aligned to 14:30:00 (32 minutes is in the 30-35 bucket)
    assert five_min_bucket['time_range_start'].minute == 30
    assert five_min_bucket['time_range_start'].second == 0


def test_bucket_counter_get_bucket_counts():
    """Test getting bucket counts as list"""
    counter = BucketCounter('acc-123', 'items')
    
    timestamp = datetime(2024, 11, 19, 14, 30, 0, tzinfo=timezone.utc)
    counter.add_record(timestamp)
    
    counts = counter.get_bucket_counts()
    
    # Should have one bucket for each size
    assert len(counts) == len(BUCKET_SIZES)
    
    # Each should have the required fields
    for count in counts:
        assert 'account_id' in count
        assert 'record_type' in count
        assert 'time_range_start' in count
        assert 'time_range_end' in count
        assert 'number_of_minutes' in count
        assert 'count' in count
        assert 'complete' in count
        
        assert count['account_id'] == 'acc-123'
        assert count['record_type'] == 'items'
        assert count['count'] == 1


def test_bucket_counter_complete_flag():
    """Test that complete flag is set correctly"""
    counter = BucketCounter('acc-123', 'items')
    
    # Add a record from 2 hours ago (definitely complete)
    past_timestamp = datetime.now(timezone.utc) - timedelta(hours=2)
    counter.add_record(past_timestamp)
    
    counts = counter.get_bucket_counts()
    
    # All buckets should be complete
    for count in counts:
        assert count['complete'] is True
    
    # Now add a record from the future (incomplete)
    counter2 = BucketCounter('acc-123', 'items')
    future_timestamp = datetime.now(timezone.utc) + timedelta(minutes=5)
    counter2.add_record(future_timestamp)
    
    counts2 = counter2.get_bucket_counts()
    
    # All buckets should be incomplete
    for count in counts2:
        assert count['complete'] is False


def test_parse_iso_datetime_with_z():
    """Test parsing ISO datetime with Z suffix"""
    result = parse_iso_datetime("2024-11-19T14:30:00Z")
    
    assert result.year == 2024
    assert result.month == 11
    assert result.day == 19
    assert result.hour == 14
    assert result.minute == 30
    assert result.second == 0
    assert result.tzinfo == timezone.utc


def test_parse_iso_datetime_with_offset():
    """Test parsing ISO datetime with timezone offset"""
    result = parse_iso_datetime("2024-11-19T14:30:00+00:00")
    
    assert result.year == 2024
    assert result.month == 11
    assert result.day == 19
    assert result.hour == 14
    assert result.minute == 30
    assert result.tzinfo is not None


def test_parse_iso_datetime_invalid():
    """Test that invalid datetime falls back to now"""
    result = parse_iso_datetime("not a valid datetime")
    
    # Should return something close to now
    now = datetime.now(timezone.utc)
    assert abs((result - now).total_seconds()) < 60


def test_count_records_efficiently():
    """Test efficient counting of records"""
    # Create sample records
    base_time = datetime(2024, 11, 19, 14, 0, 0, tzinfo=timezone.utc)
    records = []
    
    # Add 10 records in first minute
    for i in range(10):
        records.append({
            'id': f'item-{i}',
            'createdAt': (base_time + timedelta(seconds=i*5)).isoformat().replace('+00:00', 'Z')
        })
    
    # Add 5 records in second minute
    for i in range(5):
        records.append({
            'id': f'item-{i+10}',
            'createdAt': (base_time + timedelta(minutes=1, seconds=i*10)).isoformat().replace('+00:00', 'Z')
        })
    
    # Count them
    counts = count_records_efficiently(records, 'acc-123', 'items', verbose=False)
    
    # Should have buckets
    assert len(counts) > 0
    
    # Sum of 1-minute buckets should equal total records
    one_min_total = sum(c['count'] for c in counts if c['number_of_minutes'] == 1)
    assert one_min_total == 15


def test_count_records_efficiently_cross_check():
    """Test that cross-check validation works"""
    # Create records across different time buckets
    base_time = datetime(2024, 11, 19, 14, 0, 0, tzinfo=timezone.utc)
    records = []
    
    # Add records across 10 minutes
    for minute in range(10):
        for second in range(0, 60, 10):  # 6 records per minute
            records.append({
                'id': f'item-{minute}-{second}',
                'createdAt': (base_time + timedelta(minutes=minute, seconds=second)).isoformat().replace('+00:00', 'Z')
            })
    
    # Total: 10 minutes * 6 records = 60 records
    counts = count_records_efficiently(records, 'acc-123', 'items', verbose=False)
    
    # Cross-check: sum of 1-min buckets should equal total records
    one_min_total = sum(c['count'] for c in counts if c['number_of_minutes'] == 1)
    assert one_min_total == 60
    
    # 5-minute buckets should also sum correctly
    five_min_total = sum(c['count'] for c in counts if c['number_of_minutes'] == 5)
    assert five_min_total == 60  # Same records, just grouped differently


def test_count_records_efficiently_skips_no_timestamp():
    """Test that records without timestamps are skipped"""
    records = [
        {'id': 'item-1', 'createdAt': '2024-11-19T14:00:00Z'},
        {'id': 'item-2'},  # No timestamp
        {'id': 'item-3', 'createdAt': '2024-11-19T14:01:00Z'},
    ]
    
    counts = count_records_efficiently(records, 'acc-123', 'items', verbose=False)
    
    # Should only count 2 records
    one_min_total = sum(c['count'] for c in counts if c['number_of_minutes'] == 1)
    assert one_min_total == 2


def test_count_records_efficiently_uses_updated_at():
    """Test that updatedAt is used if createdAt is missing"""
    records = [
        {'id': 'item-1', 'updatedAt': '2024-11-19T14:00:00Z'},
        {'id': 'item-2', 'createdAt': '2024-11-19T14:01:00Z'},
    ]
    
    counts = count_records_efficiently(records, 'acc-123', 'scoreResults', verbose=False)
    
    # Should count both records
    one_min_total = sum(c['count'] for c in counts if c['number_of_minutes'] == 1)
    assert one_min_total == 2


def test_bucket_sizes_constant():
    """Test that BUCKET_SIZES has expected values"""
    assert BUCKET_SIZES == [1, 5, 15, 60]


def test_count_records_hierarchical_consistency():
    """Test that hierarchical bucket counts are consistent"""
    # Create 30 records evenly distributed across 30 minutes
    base_time = datetime(2024, 11, 19, 14, 0, 0, tzinfo=timezone.utc)
    records = []
    
    for minute in range(30):
        records.append({
            'id': f'item-{minute}',
            'createdAt': (base_time + timedelta(minutes=minute)).isoformat().replace('+00:00', 'Z')
        })
    
    counts = count_records_efficiently(records, 'acc-123', 'items', verbose=False)
    
    # 1-minute buckets: 30 buckets with 1 record each
    one_min_buckets = [c for c in counts if c['number_of_minutes'] == 1]
    assert len(one_min_buckets) == 30
    assert all(c['count'] == 1 for c in one_min_buckets)
    
    # 5-minute buckets: 6 buckets with 5 records each
    five_min_buckets = [c for c in counts if c['number_of_minutes'] == 5]
    assert len(five_min_buckets) == 6
    assert all(c['count'] == 5 for c in five_min_buckets)
    
    # 15-minute buckets: 2 buckets with 15 records each
    fifteen_min_buckets = [c for c in counts if c['number_of_minutes'] == 15]
    assert len(fifteen_min_buckets) == 2
    assert all(c['count'] == 15 for c in fifteen_min_buckets)
    
    # 60-minute bucket: 1 bucket with 30 records
    sixty_min_buckets = [c for c in counts if c['number_of_minutes'] == 60]
    assert len(sixty_min_buckets) == 1
    assert sixty_min_buckets[0]['count'] == 30
