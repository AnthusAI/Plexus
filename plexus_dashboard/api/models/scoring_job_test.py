import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
from .scoring_job import ScoringJob

@pytest.fixture
def mock_client():
    return Mock()

@pytest.fixture
def sample_parameters():
    return {
        'model': 'gpt-4',
        'temperature': 0.7,
        'maxTokens': 1000
    }

@pytest.fixture
def sample_scoring_job(mock_client, sample_parameters):
    return ScoringJob(
        id="test-id",
        accountId="acc-123",
        status="PENDING",
        scorecardId="card-123",
        parameters=sample_parameters,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
        client=mock_client
    )

def test_create_scoring_job(mock_client, sample_parameters):
    now = datetime.now(timezone.utc)
    mock_client.execute.return_value = {
        'createScoringJob': {
            'id': 'new-id',
            'accountId': 'acc-123',
            'status': 'PENDING',
            'scorecardId': 'card-123',
            'parameters': sample_parameters,
            'createdAt': now.isoformat(),
            'updatedAt': now.isoformat(),
            'batchSize': 100,
            'concurrency': 5
        }
    }
    
    job = ScoringJob.create(
        client=mock_client,
        accountId='acc-123',
        scorecardId='card-123',
        parameters=sample_parameters,
        batchSize=100,
        concurrency=5
    )
    
    assert job.id == 'new-id'
    assert job.accountId == 'acc-123'
    assert job.status == 'PENDING'
    assert job.parameters == sample_parameters
    assert job.batchSize == 100
    assert job.concurrency == 5

def test_update_scoring_job(sample_scoring_job):
    now = datetime.now(timezone.utc)
    sample_scoring_job._client.execute.return_value = {
        'updateScoringJob': {
            'id': sample_scoring_job.id,
            'accountId': sample_scoring_job.accountId,
            'status': 'RUNNING',
            'scorecardId': sample_scoring_job.scorecardId,
            'parameters': sample_scoring_job.parameters,
            'createdAt': sample_scoring_job.createdAt.isoformat(),
            'updatedAt': now.isoformat(),
            'processedItems': 50,
            'totalItems': 100,
            'cost': 0.15
        }
    }
    
    updated = sample_scoring_job.update(
        status='RUNNING',
        processedItems=50,
        totalItems=100,
        cost=0.15
    )
    
    assert updated.status == 'RUNNING'
    assert updated.processedItems == 50
    assert updated.totalItems == 100
    assert updated.cost == 0.15

def test_get_by_id(mock_client):
    now = datetime.now(timezone.utc)
    mock_client.execute.return_value = {
        'getScoringJob': {
            'id': 'test-id',
            'accountId': 'acc-123',
            'status': 'COMPLETED',
            'scorecardId': 'card-123',
            'parameters': {'model': 'gpt-4'},
            'createdAt': now.isoformat(),
            'updatedAt': now.isoformat(),
            'completedAt': now.isoformat(),
            'cost': 1.25
        }
    }
    
    job = ScoringJob.get_by_id('test-id', mock_client)
    assert job.id == 'test-id'
    assert job.status == 'COMPLETED'
    assert isinstance(job.completedAt, datetime)
    assert job.cost == 1.25

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
        'parameters': {'model': 'gpt-4'},
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

def test_create_with_optional_parameters(mock_client, sample_parameters):
    now = datetime.now(timezone.utc)
    mock_client.execute.return_value = {
        'createScoringJob': {
            'id': 'new-id',
            'accountId': 'acc-123',
            'status': 'PENDING',
            'scorecardId': 'card-123',
            'parameters': sample_parameters,
            'createdAt': now.isoformat(),
            'updatedAt': now.isoformat()
        }
    }
    
    job = ScoringJob.create(
        client=mock_client,
        accountId='acc-123',
        scorecardId='card-123',
        parameters=sample_parameters
    )
    
    assert job.id == 'new-id'
    assert job.batchSize is None
    assert job.concurrency is None 