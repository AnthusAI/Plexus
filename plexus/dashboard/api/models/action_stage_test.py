import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
from .action_stage import ActionStage

@pytest.fixture
def mock_client():
    return Mock()

@pytest.fixture
def sample_stage(mock_client):
    return ActionStage(
        id="test-id",
        actionId="action-123",
        name="Test Stage",
        order=1,
        status="PENDING",
        client=mock_client
    )

def test_create_action_stage(mock_client):
    now = datetime.now(timezone.utc)
    mock_client.execute.return_value = {
        'createActionStage': {
            'id': 'new-id',
            'actionId': 'action-123',
            'name': 'Test Stage',
            'order': 1,
            'status': 'PENDING',
            'statusMessage': 'Starting stage',
            'startedAt': now.isoformat()
        }
    }
    
    stage = ActionStage.create(
        client=mock_client,
        actionId='action-123',
        name='Test Stage',
        order=1,
        status='PENDING',
        statusMessage='Starting stage',
        startedAt=now
    )
    
    assert stage.id == 'new-id'
    assert stage.actionId == 'action-123'
    assert stage.name == 'Test Stage'
    assert stage.order == 1
    assert stage.status == 'PENDING'
    assert stage.statusMessage == 'Starting stage'
    assert isinstance(stage.startedAt, datetime)

def test_update_action_stage(sample_stage):
    now = datetime.now(timezone.utc)
    sample_stage._client.execute.side_effect = [
        {
            'getActionStage': {
                'actionId': 'action-123',
                'name': 'Test Stage',
                'order': 1,
                'status': 'PENDING'
            }
        },
        {
            'updateActionStage': {
                'id': sample_stage.id,
                'actionId': sample_stage.actionId,
                'name': sample_stage.name,
                'order': sample_stage.order,
                'status': 'RUNNING',
                'statusMessage': 'Processing items',
                'startedAt': now.isoformat(),
                'processedItems': 50,
                'totalItems': 100
            }
        }
    ]
    
    updated = sample_stage.update(
        status='RUNNING',
        statusMessage='Processing items',
        startedAt=now,
        processedItems=50,
        totalItems=100
    )
    
    assert updated.status == 'RUNNING'
    assert updated.statusMessage == 'Processing items'
    assert updated.startedAt == now
    assert updated.processedItems == 50
    assert updated.totalItems == 100
    assert isinstance(updated.startedAt, datetime)

def test_get_by_id(mock_client):
    now = datetime.now(timezone.utc)
    mock_client.execute.return_value = {
        'getActionStage': {
            'id': 'test-id',
            'actionId': 'action-123',
            'name': 'Test Stage',
            'order': 1,
            'status': 'COMPLETED',
            'completedAt': now.isoformat()
        }
    }
    
    stage = ActionStage.get_by_id('test-id', mock_client)
    assert stage.id == 'test-id'
    assert stage.status == 'COMPLETED'
    assert isinstance(stage.completedAt, datetime)

def test_from_dict_handles_datetime_fields():
    now = datetime.now(timezone.utc)
    data = {
        'id': 'test-id',
        'actionId': 'action-123',
        'name': 'Test Stage',
        'order': 1,
        'status': 'RUNNING',
        'startedAt': now.isoformat(),
        'completedAt': now.isoformat()
    }
    
    stage = ActionStage.from_dict(data, Mock())
    
    assert isinstance(stage.startedAt, datetime)
    assert isinstance(stage.completedAt, datetime) 