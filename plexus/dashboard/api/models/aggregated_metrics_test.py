"""
Tests for the AggregatedMetrics model.

These tests verify:
1. from_dict() with datetime parsing
2. list_by_time_range() with mocked client
3. create_or_update() upsert logic
4. Field handling and validation
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock
from .aggregated_metrics import AggregatedMetrics


@pytest.fixture
def mock_client():
    """Create a mock client with required execute method"""
    client = Mock()
    return client


@pytest.fixture
def sample_metrics_data():
    """Sample AggregatedMetrics data"""
    now = datetime.now(timezone.utc)
    start = now.replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(minutes=60)
    
    return {
        'id': 'test-id-123',
        'accountId': 'acc-123',
        'recordType': 'items',
        'timeRangeStart': start.isoformat().replace('+00:00', 'Z'),
        'timeRangeEnd': end.isoformat().replace('+00:00', 'Z'),
        'numberOfMinutes': 60,
        'count': 100,
        'complete': True,
        'createdAt': now.isoformat().replace('+00:00', 'Z'),
        'updatedAt': now.isoformat().replace('+00:00', 'Z'),
        'scorecardId': None,
        'scoreId': None,
        'cost': 1000,
        'decisionCount': 50,
        'externalAiApiCount': 25,
        'cachedAiApiCount': 25,
        'errorCount': 0,
        'metadata': {'source': 'test'}
    }


def test_from_dict_basic(mock_client, sample_metrics_data):
    """Test creating AggregatedMetrics from dictionary"""
    metric = AggregatedMetrics.from_dict(sample_metrics_data, mock_client)
    
    assert metric.id == 'test-id-123'
    assert metric.accountId == 'acc-123'
    assert metric.recordType == 'items'
    assert metric.numberOfMinutes == 60
    assert metric.count == 100
    assert metric.complete is True
    assert metric.cost == 1000
    assert metric.decisionCount == 50
    assert metric.externalAiApiCount == 25
    assert metric.cachedAiApiCount == 25
    assert metric.errorCount == 0
    assert metric.metadata == {'source': 'test'}


def test_from_dict_datetime_parsing(mock_client, sample_metrics_data):
    """Test that datetime fields are properly parsed"""
    metric = AggregatedMetrics.from_dict(sample_metrics_data, mock_client)
    
    # All datetime fields should be datetime objects
    assert isinstance(metric.timeRangeStart, datetime)
    assert isinstance(metric.timeRangeEnd, datetime)
    assert isinstance(metric.createdAt, datetime)
    assert isinstance(metric.updatedAt, datetime)
    
    # All should have UTC timezone
    assert metric.timeRangeStart.tzinfo is not None
    assert metric.timeRangeEnd.tzinfo is not None
    assert metric.createdAt.tzinfo is not None
    assert metric.updatedAt.tzinfo is not None


def test_repr(mock_client, sample_metrics_data):
    """Test __repr__ method"""
    metric = AggregatedMetrics.from_dict(sample_metrics_data, mock_client)
    repr_str = repr(metric)
    
    assert 'AggregatedMetrics' in repr_str
    assert 'test-id-123' in repr_str
    assert 'items' in repr_str
    assert '60min' in repr_str
    assert 'count=100' in repr_str


def test_list_by_time_range(mock_client, sample_metrics_data):
    """Test querying metrics by time range"""
    # Setup mock response
    mock_client.execute.return_value = {
        'listAggregatedMetricsByAccountIdAndTimeRangeStartAndRecordType': {
            'items': [sample_metrics_data],
            'nextToken': None
        }
    }
    
    start_time = datetime.now(timezone.utc) - timedelta(hours=1)
    end_time = datetime.now(timezone.utc)
    
    metrics = AggregatedMetrics.list_by_time_range(
        mock_client,
        'acc-123',
        start_time,
        end_time
    )
    
    # Should have called execute once
    assert mock_client.execute.call_count == 1
    
    # Should return one metric
    assert len(metrics) == 1
    assert metrics[0].id == 'test-id-123'
    assert metrics[0].count == 100


def test_list_by_time_range_with_record_type_filter(mock_client, sample_metrics_data):
    """Test querying metrics with record type filter"""
    # Setup mock response with multiple record types
    data_items = dict(sample_metrics_data)
    data_items['recordType'] = 'items'
    
    data_scores = dict(sample_metrics_data)
    data_scores['id'] = 'test-id-456'
    data_scores['recordType'] = 'scoreResults'
    
    mock_client.execute.return_value = {
        'listAggregatedMetricsByAccountIdAndTimeRangeStartAndRecordType': {
            'items': [data_items, data_scores],
            'nextToken': None
        }
    }
    
    start_time = datetime.now(timezone.utc) - timedelta(hours=1)
    end_time = datetime.now(timezone.utc)
    
    # Query with filter
    metrics = AggregatedMetrics.list_by_time_range(
        mock_client,
        'acc-123',
        start_time,
        end_time,
        record_type='items'
    )
    
    # Should only return items
    assert len(metrics) == 1
    assert metrics[0].recordType == 'items'


def test_list_by_time_range_pagination(mock_client, sample_metrics_data):
    """Test that pagination is handled correctly"""
    # First page
    data1 = dict(sample_metrics_data)
    data1['id'] = 'test-id-1'
    
    # Second page
    data2 = dict(sample_metrics_data)
    data2['id'] = 'test-id-2'
    
    # Setup mock to return two pages
    mock_client.execute.side_effect = [
        {
            'listAggregatedMetricsByAccountIdAndTimeRangeStartAndRecordType': {
                'items': [data1],
                'nextToken': 'token-123'
            }
        },
        {
            'listAggregatedMetricsByAccountIdAndTimeRangeStartAndRecordType': {
                'items': [data2],
                'nextToken': None
            }
        }
    ]
    
    start_time = datetime.now(timezone.utc) - timedelta(hours=1)
    end_time = datetime.now(timezone.utc)
    
    metrics = AggregatedMetrics.list_by_time_range(
        mock_client,
        'acc-123',
        start_time,
        end_time
    )
    
    # Should have called execute twice
    assert mock_client.execute.call_count == 2
    
    # Should return both metrics
    assert len(metrics) == 2
    assert metrics[0].id == 'test-id-1'
    assert metrics[1].id == 'test-id-2'


def test_create_or_update_creates_new(mock_client, sample_metrics_data):
    """Test create_or_update creates new record when none exists"""
    # Mock list_by_time_range to return empty (no existing record)
    mock_client.execute.side_effect = [
        # First call: list_by_time_range query
        {
            'listAggregatedMetricsByAccountIdAndTimeRangeStartAndRecordType': {
                'items': [],
                'nextToken': None
            }
        },
        # Second call: create mutation
        {
            'createAggregatedMetrics': sample_metrics_data
        }
    ]
    
    start_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=60)
    
    metric = AggregatedMetrics.create_or_update(
        mock_client,
        account_id='acc-123',
        record_type='items',
        time_range_start=start_time,
        time_range_end=end_time,
        number_of_minutes=60,
        count=100,
        complete=True
    )
    
    # Should have called execute twice (query + create)
    assert mock_client.execute.call_count == 2
    
    # Second call should be create mutation
    second_call_args = mock_client.execute.call_args_list[1]
    assert 'createAggregatedMetrics' in second_call_args[0][0]
    
    assert metric.id == 'test-id-123'
    assert metric.count == 100


def test_create_or_update_updates_existing(mock_client, sample_metrics_data):
    """Test create_or_update updates existing record"""
    # Mock list_by_time_range to return existing record
    mock_client.execute.side_effect = [
        # First call: list_by_time_range query
        {
            'listAggregatedMetricsByAccountIdAndTimeRangeStartAndRecordType': {
                'items': [sample_metrics_data],
                'nextToken': None
            }
        },
        # Second call: update mutation
        {
            'updateAggregatedMetrics': {
                **sample_metrics_data,
                'count': 150  # Updated count
            }
        }
    ]
    
    start_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=60)
    
    metric = AggregatedMetrics.create_or_update(
        mock_client,
        account_id='acc-123',
        record_type='items',
        time_range_start=start_time,
        time_range_end=end_time,
        number_of_minutes=60,
        count=150,  # New count
        complete=True
    )
    
    # Should have called execute twice (query + update)
    assert mock_client.execute.call_count == 2
    
    # Second call should be update mutation
    second_call_args = mock_client.execute.call_args_list[1]
    assert 'updateAggregatedMetrics' in second_call_args[0][0]
    
    assert metric.count == 150


def test_fields_method():
    """Test that fields() returns all expected fields"""
    fields = AggregatedMetrics.fields()
    
    required_fields = [
        'id', 'accountId', 'recordType', 'timeRangeStart', 'timeRangeEnd',
        'numberOfMinutes', 'count', 'complete', 'createdAt', 'updatedAt'
    ]
    
    for field in required_fields:
        assert field in fields
    
    optional_fields = [
        'scorecardId', 'scoreId', 'cost', 'decisionCount',
        'externalAiApiCount', 'cachedAiApiCount', 'errorCount', 'metadata'
    ]
    
    for field in optional_fields:
        assert field in fields
