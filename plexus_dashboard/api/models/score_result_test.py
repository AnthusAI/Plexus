import pytest
from unittest.mock import Mock
from ..client import PlexusDashboardClient
from .score_result import ScoreResult

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