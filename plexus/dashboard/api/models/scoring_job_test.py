import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
from .scoring_job import ScoringJob

@pytest.fixture
def mock_client():
    return Mock()

@pytest.fixture
def sample_scoring_job(mock_client):
    now = datetime.now(timezone.utc)
    return ScoringJob(
        id="test-id",
        accountId="acc-123",
        status="PENDING",
        scorecardId="card-123",
        itemId="item-123",
        createdAt=now,
        updatedAt=now,
        client=mock_client
    )

def test_create_scoring_job(mock_client):
    now = datetime.now(timezone.utc)
    mock_client.execute.return_value = {
        'createScoringJob': {
            'id': 'new-id',
            'accountId': 'acc-123',
            'status': 'PENDING',
            'scorecardId': 'card-123',
            'itemId': 'item-123',
            'createdAt': now.isoformat(),
            'updatedAt': now.isoformat()
        }
    }
    
    job = ScoringJob.create(
        client=mock_client,
        accountId='acc-123',
        scorecardId='card-123',
        itemId='item-123',
        parameters={'temperature': 0.7}
    )
    
    assert job.id == 'new-id'
    assert job.accountId == 'acc-123'
    assert job.status == 'PENDING'
    assert job.scorecardId == 'card-123'
    assert job.itemId == 'item-123'

def test_update_scoring_job(sample_scoring_job):
    now = datetime.now(timezone.utc)
    sample_scoring_job._client.execute.return_value = {
        'updateScoringJob': {
            'id': sample_scoring_job.id,
            'accountId': sample_scoring_job.accountId,
            'status': 'RUNNING',
            'scorecardId': sample_scoring_job.scorecardId,
            'itemId': sample_scoring_job.itemId,
            'createdAt': sample_scoring_job.createdAt.isoformat(),
            'updatedAt': now.isoformat(),
            'startedAt': now.isoformat()
        }
    }
    
    updated = sample_scoring_job.update(
        status='RUNNING',
        startedAt=now
    )
    
    assert updated.status == 'RUNNING'
    assert updated.startedAt == now

def test_get_by_id(mock_client):
    now = datetime.now(timezone.utc)
    mock_client.execute.return_value = {
        'getScoringJob': {
            'id': 'test-id',
            'accountId': 'acc-123',
            'status': 'COMPLETED',
            'scorecardId': 'card-123',
            'itemId': 'item-123',
            'createdAt': now.isoformat(),
            'updatedAt': now.isoformat(),
            'completedAt': now.isoformat()
        }
    }
    
    job = ScoringJob.get_by_id('test-id', mock_client)
    assert job.id == 'test-id'
    assert job.status == 'COMPLETED'
    assert isinstance(job.completedAt, datetime)

def test_update_prevents_modifying_created_at(sample_scoring_job):
    with pytest.raises(ValueError, match="createdAt cannot be modified"):
        sample_scoring_job.update(createdAt=datetime.now(timezone.utc))

def test_from_dict_handles_datetime_fields():
    now = datetime.now(timezone.utc)
    data = {
        'id': 'test-id',
        'accountId': 'acc-123',
        'status': 'RUNNING',
        'scorecardId': 'card-123',
        'itemId': 'item-123',
        'createdAt': now.isoformat(),
        'updatedAt': now.isoformat(),
        'startedAt': now.isoformat(),
        'completedAt': now.isoformat()
    }
    
    job = ScoringJob.from_dict(data, Mock())
    
    assert isinstance(job.createdAt, datetime)
    assert isinstance(job.updatedAt, datetime)
    assert isinstance(job.startedAt, datetime)
    assert isinstance(job.completedAt, datetime) 