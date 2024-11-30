import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
from .batch_job import BatchJob

@pytest.fixture
def mock_client():
    return Mock()

@pytest.fixture
def sample_batch_job(mock_client):
    return BatchJob(
        id="test-id",
        accountId="acc-123",
        status="PENDING",
        type="inference",
        provider="OPENAI",
        batchId="batch-123",
        modelProvider="openai",
        modelName="gpt-4",
        client=mock_client
    )

def test_create_batch_job(mock_client):
    now = datetime.now(timezone.utc)
    mock_client.execute.return_value = {
        'createBatchJob': {
            'id': 'new-id',
            'accountId': 'acc-123',
            'status': 'PENDING',
            'type': 'inference',
            'provider': 'OPENAI',
            'batchId': 'batch-123',
            'modelProvider': 'openai',
            'modelName': 'gpt-4'
        }
    }
    
    job = BatchJob.create(
        client=mock_client,
        accountId='acc-123',
        type='inference',
        modelProvider='openai',
        modelName='gpt-4',
        parameters={'temperature': 0.7}
    )
    
    assert job.id == 'new-id'
    assert job.accountId == 'acc-123'
    assert job.status == 'PENDING'
    assert job.modelProvider == 'openai'
    assert job.modelName == 'gpt-4'

def test_update_batch_job(sample_batch_job):
    now = datetime.now(timezone.utc)
    sample_batch_job._client.execute.return_value = {
        'updateBatchJob': {
            'id': sample_batch_job.id,
            'accountId': sample_batch_job.accountId,
            'status': 'RUNNING',
            'type': sample_batch_job.type,
            'provider': sample_batch_job.provider,
            'batchId': sample_batch_job.batchId,
            'modelProvider': sample_batch_job.modelProvider,
            'modelName': sample_batch_job.modelName,
            'totalRequests': 100,
            'completedRequests': 50
        }
    }
    
    updated = sample_batch_job.update(
        status='RUNNING',
        totalRequests=100,
        completedRequests=50
    )
    
    assert updated.status == 'RUNNING'
    assert updated.totalRequests == 100
    assert updated.completedRequests == 50

def test_get_by_id(mock_client):
    now = datetime.now(timezone.utc)
    mock_client.execute.return_value = {
        'getBatchJob': {
            'id': 'test-id',
            'accountId': 'acc-123',
            'status': 'COMPLETED',
            'type': 'inference',
            'provider': 'OPENAI',
            'batchId': 'batch-123',
            'modelProvider': 'openai',
            'modelName': 'gpt-4',
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
        'provider': 'OPENAI',
        'batchId': 'batch-123',
        'modelProvider': 'openai',
        'modelName': 'gpt-4',
        'startedAt': now.isoformat(),
        'completedAt': now.isoformat()
    }
    
    job = BatchJob.from_dict(data, Mock())
    
    assert isinstance(job.startedAt, datetime)
    assert isinstance(job.completedAt, datetime) 