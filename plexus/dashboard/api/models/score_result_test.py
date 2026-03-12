import pytest
from unittest.mock import Mock
from typing import TYPE_CHECKING
from .score_result import ScoreResult
from datetime import datetime, timezone
import json

if TYPE_CHECKING:
    from ..client import PlexusDashboardClient

@pytest.fixture
def mock_client():
    return Mock()

@pytest.fixture
def sample_score_result(mock_client):
    return ScoreResult(
        id="test-id",
        value=0.95,
        itemId="test-item",
        accountId="test-account",
        scoringJobId="test-job",
        scorecardId="test-scorecard",
        client=mock_client
    )

def test_create_score_result(mock_client):
    """Test creating a score result"""
    mock_client.execute.return_value = {
        'createScoreResult': {
            'id': 'new-id',
            'value': 0.85,
            'itemId': 'item-1',
            'accountId': 'account-1',
            'scoringJobId': 'job-1',
            'scorecardId': 'scorecard-1',
            'confidence': 0.92,
            'metadata': {'source': 'test'}
        }
    }
    
    result = ScoreResult.create(
        client=mock_client,
        value=0.85,
        itemId='item-1',
        accountId='account-1',
        scoringJobId='job-1',
        scorecardId='scorecard-1',
        confidence=0.92,
        metadata={'source': 'test'}
    )
    
    assert result.value == 0.85
    assert result.confidence == 0.92
    assert result.metadata == {'source': 'test'}

def test_from_dict_handles_optional_fields(mock_client):
    """Test that from_dict properly handles missing optional fields"""
    data = {
        'id': 'test-id',
        'value': 0.75,
        'itemId': 'item-1',
        'accountId': 'account-1',
        'scoringJobId': 'job-1',
        'scorecardId': 'scorecard-1'
    }
    
    result = ScoreResult.from_dict(data, mock_client)
    
    assert result.value == 0.75
    assert result.confidence is None
    assert result.metadata is None 

def test_update_score_result(sample_score_result):
    """Test updating a score result"""
    sample_score_result._client.execute.return_value = {
        'updateScoreResult': {
            'id': sample_score_result.id,
            'value': sample_score_result.value,
            'itemId': sample_score_result.itemId,
            'accountId': sample_score_result.accountId,
            'scoringJobId': sample_score_result.scoringJobId,
            'scorecardId': sample_score_result.scorecardId,
            'confidence': 0.98,
            'metadata': {'updated': True}
        }
    }
    
    updated = sample_score_result.update(
        confidence=0.98,
        metadata={'updated': True}
    )
    
    assert updated.confidence == 0.98
    assert updated.metadata == {'updated': True}
    # Verify unchanged fields remain the same
    assert updated.value == sample_score_result.value
    assert updated.itemId == sample_score_result.itemId

def test_batch_create_score_results(mock_client):
    """Test creating multiple score results in a batch"""
    mock_client.execute.return_value = {
        'batchCreateScoreResults': {
            'items': [
                {
                    'id': 'id-1',
                    'value': 0.85,
                    'itemId': 'item-1',
                    'accountId': 'account-1',
                    'scoringJobId': 'job-1',
                    'scorecardId': 'card-1',
                    'confidence': 0.92,
                    'metadata': '{"source": "test1"}'
                },
                {
                    'id': 'id-2',
                    'value': 0.78,
                    'itemId': 'item-2',
                    'accountId': 'account-1',
                    'scoringJobId': 'job-1',
                    'scorecardId': 'card-1',
                    'confidence': 0.88,
                    'metadata': '{"source": "test2"}'
                }
            ]
        }
    }
    
    items = [
        {
            'value': 0.85,
            'itemId': 'item-1',
            'accountId': 'account-1',
            'scoringJobId': 'job-1',
            'scorecardId': 'card-1',
            'confidence': 0.92,
            'metadata': {'source': 'test1'}
        },
        {
            'value': 0.78,
            'itemId': 'item-2',
            'accountId': 'account-1',
            'scoringJobId': 'job-1',
            'scorecardId': 'card-1',
            'confidence': 0.88,
            'metadata': {'source': 'test2'}
        }
    ]
    
    results = ScoreResult.batch_create(mock_client, items)
    
    assert len(results) == 2
    assert results[0].value == 0.85
    assert results[0].metadata == {'source': 'test1'}
    assert results[1].value == 0.78
    assert results[1].metadata == {'source': 'test2'}
    
    # Verify the mutation was called with correct inputs
    mock_client.execute.assert_called_once()
    call_args = mock_client.execute.call_args[0]
    assert 'batchCreateScoreResults' in call_args[0]
    assert len(call_args[1]['inputs']) == 2


# Tests for find_by_cache_key method
class TestFindByCacheKey:
    """Test suite for ScoreResult.find_by_cache_key method"""
    
    @pytest.fixture
    def sample_score_result_data(self):
        """Sample ScoreResult data for mocking responses"""
        return {
            'id': 'score-result-123',
            'value': 'Yes',
            'explanation': 'Test explanation',
            'itemId': 'item-123',
            'scorecardId': 'scorecard-456', 
            'scoreId': 'score-789',
            'accountId': 'account-abc',
            'updatedAt': '2025-07-13T18:55:07.290773+00:00',
            'createdAt': '2025-07-13T18:55:07.290773+00:00',
            'metadata': '{"test": "data"}',
            'confidence': 0.95
        }
    
    @pytest.fixture
    def mock_gsi_response(self, sample_score_result_data):
        """Mock GSI query response"""
        return {
            'listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt': {
                'items': [sample_score_result_data]
            }
        }
    
    @pytest.fixture
    def mock_empty_gsi_response(self):
        """Mock empty GSI query response (cache miss)"""
        return {
            'listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt': {
                'items': []
            }
        }
    
    def test_find_by_cache_key_success(self, mock_client, mock_gsi_response, sample_score_result_data):
        """Test successful cache key lookup"""
        mock_client.execute.return_value = mock_gsi_response
        
        result = ScoreResult.find_by_cache_key(
            client=mock_client,
            item_id="item-123",
            type="prediction",
            score_id="score-789"
        )
        
        # Verify we got a ScoreResult object back
        assert result is not None
        assert isinstance(result, ScoreResult)
        assert result.id == sample_score_result_data['id']
        assert result.value == sample_score_result_data['value']
        assert result.itemId == sample_score_result_data['itemId']
        assert result.scorecardId == sample_score_result_data['scorecardId']
        assert result.scoreId == sample_score_result_data['scoreId']
        
        # Verify the GSI query was executed correctly
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        variables = call_args[0][1]
        
        assert 'listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt' in query
        assert 'sortDirection: DESC' in query
        assert 'limit: 1' in query
        assert variables == {
            "itemId": "item-123",
            "type": "prediction", 
            "scoreId": "score-789"
        }
    
    def test_find_by_cache_key_not_found(self, mock_client, mock_empty_gsi_response):
        """Test cache miss scenario"""
        mock_client.execute.return_value = mock_empty_gsi_response
        
        result = ScoreResult.find_by_cache_key(
            client=mock_client,
            item_id="item-nonexistent",
            type="prediction",
            score_id="score-nonexistent"
        )
        
        # Should return None for cache miss
        assert result is None
        
        # Verify query was still executed
        mock_client.execute.assert_called_once()
    
    def test_find_by_cache_key_with_account_id(self, mock_client, mock_gsi_response):
        """Test cache lookup with optional account_id parameter"""
        mock_client.execute.return_value = mock_gsi_response
        
        result = ScoreResult.find_by_cache_key(
            client=mock_client,
            item_id="item-123",
            type="prediction",
            score_id="score-789",
            account_id="account-abc"  # Optional parameter
        )
        
        assert result is not None
        
        # account_id is currently not used in the query, but method should still work
        mock_client.execute.assert_called_once()
    
    def test_find_by_cache_key_exception_handling(self, mock_client):
        """Test exception handling in find_by_cache_key"""
        # Mock client to raise an exception
        mock_client.execute.side_effect = Exception("GraphQL error")
        
        # Should not raise exception, should return None
        result = ScoreResult.find_by_cache_key(
            client=mock_client,
            item_id="item-123",
            type="prediction",
            score_id="score-789"
        )
        
        assert result is None
        mock_client.execute.assert_called_once()
    
    def test_find_by_cache_key_multiple_results_returns_most_recent(self, mock_client, sample_score_result_data):
        """Test that find_by_cache_key returns the most recent result when multiple exist"""
        # Create multiple results with different timestamps
        older_result = sample_score_result_data.copy()
        older_result['id'] = 'older-result'
        older_result['updatedAt'] = '2025-07-13T17:00:00.000000+00:00'
        
        newer_result = sample_score_result_data.copy()
        newer_result['id'] = 'newer-result'
        newer_result['updatedAt'] = '2025-07-13T19:00:00.000000+00:00'
        
        # Mock response with multiple items (should be sorted DESC by updatedAt)
        mock_response = {
            'listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt': {
                'items': [newer_result]  # GSI should return most recent first due to DESC sort + limit 1
            }
        }
        mock_client.execute.return_value = mock_response
        
        result = ScoreResult.find_by_cache_key(
            client=mock_client,
            item_id="item-123",
            type="prediction",
            score_id="score-789"
        )
        
        # Should get the newer result
        assert result is not None
        assert result.id == 'newer-result'
    
    def test_find_by_cache_key_gsi_query_structure(self, mock_client, mock_gsi_response):
        """Test that the GSI query is structured correctly"""
        mock_client.execute.return_value = mock_gsi_response
        
        ScoreResult.find_by_cache_key(
            client=mock_client,
            item_id="test-item",
            type="prediction", 
            score_id="test-score"
        )
        
        # Examine the generated query
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        
        # Verify key parts of the GSI query
        assert 'query GetMostRecentScoreResult' in query
        assert '$itemId: String!' in query
        assert '$type: String!' in query
        assert '$scoreId: String!' in query
        assert 'itemId: $itemId' in query
        assert 'beginsWith:' in query
        assert 'type: $type' in query
        assert 'scoreId: $scoreId' in query
        assert 'sortDirection: DESC' in query
        assert 'limit: 1' in query
    
    def test_find_by_cache_key_fields_inclusion(self, mock_client, mock_gsi_response):
        """Test that all ScoreResult fields are included in the query"""
        mock_client.execute.return_value = mock_gsi_response
        
        ScoreResult.find_by_cache_key(
            client=mock_client,
            item_id="test-item",
            type="prediction",
            score_id="test-score"
        )
        
        # Check that ScoreResult.fields() output is included in query
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        
        # Should include key fields that ScoreResult.fields() returns
        expected_fields = ['id', 'value', 'itemId', 'scorecardId', 'scoreId', 'updatedAt', 'createdAt']
        for field in expected_fields:
            assert field in query, f"Field {field} should be in the query"

def test_score_result_update_with_datetime_createdAt():
    """Test that update() properly handles datetime objects passed as createdAt"""
    mock_client = Mock()
    
    # Mock the initial ScoreResult with actual datetime objects (like real GraphQL returns)
    score_result = ScoreResult(
        id="test-id",
        value="0.95",
        itemId="test-item",
        accountId="test-account",
        scorecardId="test-scorecard",
        createdAt=datetime.now(timezone.utc),  # Real datetime object
        updatedAt=datetime.now(timezone.utc),  # Real datetime object
        client=mock_client
    )
    
    # Mock the response with datetime objects (simulating real GraphQL behavior)
    mock_client.execute.return_value = {
        'updateScoreResult': {
            'id': 'test-id',
            'value': '0.95',
            'itemId': 'test-item',
            'accountId': 'test-account',
            'scorecardId': 'test-scorecard',
            'attachments': ['file1.txt'],
            'createdAt': datetime.now(timezone.utc).isoformat(),  # GraphQL returns ISO string
            'updatedAt': datetime.now(timezone.utc).isoformat(),  # GraphQL returns ISO string
        }
    }
    
    # This should NOT raise TypeError about datetime serialization
    try:
        updated = score_result.update(
            attachments=['file1.txt'],
            createdAt=datetime.now(timezone.utc)  # Passing a datetime object
        )
        
        # Should succeed
        assert updated.attachments == ['file1.txt']
    except TypeError as e:
        if "datetime" in str(e):
            pytest.fail(f"update() should handle datetime objects: {e}")
        raise


def test_score_result_updatedAt_is_json_serializable():
    """Test that updatedAt can be serialized to JSON for logging"""
    mock_client = Mock()
    
    score_result = ScoreResult(
        id="test-id",
        value="0.95",
        itemId="test-item",
        accountId="test-account",
        scorecardId="test-scorecard",
        updatedAt=datetime.now(timezone.utc),
        client=mock_client
    )
    
    # This is what happens in our logging code - should not raise
    try:
        json.dumps({
            "updated_at": str(score_result.updatedAt) if score_result.updatedAt else None
        })
    except TypeError as e:
        pytest.fail(f"updatedAt should be JSON serializable after str(): {e}")


def test_get_by_id_returns_datetime_objects():
    """Test that get_by_id properly parses datetime strings into datetime objects"""
    mock_client = Mock()
    
    now = datetime.now(timezone.utc)
    iso_string = now.isoformat()
    
    mock_client.execute.return_value = {
        'getScoreResult': {
            'id': 'test-id',
            'value': '0.95',
            'itemId': 'test-item',
            'accountId': 'test-account',
            'scorecardId': 'test-scorecard',
            'createdAt': iso_string,
            'updatedAt': iso_string,
        }
    }
    
    result = ScoreResult.get_by_id('test-id', mock_client)
    
    # Should have datetime objects, not strings
    assert isinstance(result.createdAt, datetime), f"createdAt should be datetime, got {type(result.createdAt)}"
    assert isinstance(result.updatedAt, datetime), f"updatedAt should be datetime, got {type(result.updatedAt)}"