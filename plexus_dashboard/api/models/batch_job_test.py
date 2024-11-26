import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
from .batch_job import BatchJob

@pytest.fixture
def mock_client():
    return Mock()

@pytest.fixture
def sample_parameters():
    return {
        'model': 'gpt-4',
        'temperature': 0.7
    }

@pytest.fixture
def sample_batch_job(mock_client, sample_parameters):
    return BatchJob(
        id="test-id",
        accountId="acc-123",
        status="PENDING",
        type="inference",
        parameters=sample_parameters,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
        client=mock_client
    )

def test_create_batch_job(mock_client, sample_parameters):
    now = datetime.now(timezone.utc)
    mock_client.execute.return_value = {
        'createBatchJob': {
            'id': 'new-id',
            'accountId': 'acc-123',
            'status': 'PENDING',
            'type': 'inference',
            'parameters': sample_parameters,
            'createdAt': now.isoformat(),
            'updatedAt': now.isoformat()
        }
    }
    
    job = BatchJob.create(
        client=mock_client,
        accountId='acc-123',
        type='inference',
        parameters=sample_parameters
    )
    
    assert job.id == 'new-id'
    assert job.accountId == 'acc-123'
    assert job.status == 'PENDING'
    assert job.parameters == sample_parameters

def test_update_batch_job(sample_batch_job):
    now = datetime.now(timezone.utc)
    sample_batch_job._client.execute.return_value = {
        'updateBatchJob': {
            'id': sample_batch_job.id,
            'accountId': sample_batch_job.accountId,
            'status': 'RUNNING',
            'type': sample_batch_job.type,
            'parameters': sample_batch_job.parameters,
            'createdAt': sample_batch_job.createdAt.isoformat(),
            'updatedAt': now.isoformat(),
            'processedItems': 50,
            'totalItems': 100
        }
    }
    
    updated = sample_batch_job.update(
        status='RUNNING',
        processedItems=50,
        totalItems=100
    )
    
    assert updated.status == 'RUNNING'
    assert updated.processedItems == 50
    assert updated.totalItems == 100

def test_get_by_id(mock_client):
    now = datetime.now(timezone.utc)
    mock_client.execute.return_value = {
        'getBatchJob': {
            'id': 'test-id',
            'accountId': 'acc-123',
            'status': 'COMPLETED',
            'type': 'inference',
            'parameters': {'model': 'gpt-4'},
            'createdAt': now.isoformat(),
            'updatedAt': now.isoformat(),
            'completedAt': now.isoformat()
        }
    }
    
    job = BatchJob.get_by_id('test-id', mock_client)
    assert job.id == 'test-id'
    assert job.status == 'COMPLETED'
    assert isinstance(job.completedAt, datetime)

def test_update_prevents_modifying_created_at(sample_batch_job):
    with pytest.raises(ValueError, match="createdAt cannot be modified"):
        sample_batch_job.update(createdAt=datetime.now(timezone.utc))

def test_from_dict_handles_datetime_fields():
    now = datetime.now(timezone.utc)
    data = {
        'id': 'test-id',
        'accountId': 'acc-123',
        'status': 'RUNNING',
        'type': 'inference',
        'parameters': {'model': 'gpt-4'},
        'createdAt': now.isoformat(),
        'updatedAt': now.isoformat(),
        'startedAt': now.isoformat(),
        'completedAt': now.isoformat()
    }
    
    job = BatchJob.from_dict(data, Mock())
    
    assert isinstance(job.createdAt, datetime)
    assert isinstance(job.updatedAt, datetime)
    assert isinstance(job.startedAt, datetime)
    assert isinstance(job.completedAt, datetime) 