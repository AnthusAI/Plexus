import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock
from ..models.task_stage import TaskStage

@pytest.fixture
def mock_client():
    return Mock()

@pytest.fixture
def sample_stage(mock_client):
    return TaskStage(
        id="test-id",
        taskId="task-123",
        name="Test Stage",
        order=1,
        status="PENDING",
        client=mock_client
    )

def test_create_task_stage(mock_client):
    now = datetime.now(timezone.utc)
    mock_client.execute.return_value = {
        'createTaskStage': {
            'id': 'new-id',
            'taskId': 'task-123',
            'name': 'Test Stage',
            'order': 1,
            'status': 'PENDING',
            'statusMessage': 'Starting stage',
            'startedAt': now.isoformat()
        }
    }
    
    stage = TaskStage.create(
        client=mock_client,
        taskId='task-123',
        name='Test Stage',
        order=1,
        status='PENDING',
        statusMessage='Starting stage',
        startedAt=now
    )
    
    assert stage.id == 'new-id'
    assert stage.taskId == 'task-123'
    assert stage.name == 'Test Stage'
    assert stage.order == 1
    assert stage.status == 'PENDING'
    assert stage.statusMessage == 'Starting stage'
    assert isinstance(stage.startedAt, datetime)

def test_update_task_stage(sample_stage):
    now = datetime.now(timezone.utc)
    sample_stage._client.execute.side_effect = [
        {
            'getTaskStage': {
                'taskId': 'task-123',
                'name': 'Test Stage',
                'order': 1,
                'status': 'PENDING'
            }
        },
        {
            'updateTaskStage': {
                'id': sample_stage.id,
                'taskId': sample_stage.taskId,
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
        'getTaskStage': {
            'id': 'test-id',
            'taskId': 'task-123',
            'name': 'Test Stage',
            'order': 1,
            'status': 'COMPLETED',
            'completedAt': now.isoformat()
        }
    }
    
    stage = TaskStage.get_by_id('test-id', mock_client)
    assert stage.id == 'test-id'
    assert stage.status == 'COMPLETED'
    assert isinstance(stage.completedAt, datetime)

def test_from_dict_handles_datetime_fields():
    now = datetime.now(timezone.utc)
    data = {
        'id': 'test-id',
        'taskId': 'task-123',
        'name': 'Test Stage',
        'order': 1,
        'status': 'RUNNING',
        'startedAt': now.isoformat(),
        'completedAt': now.isoformat()
    }
    
    stage = TaskStage.from_dict(data, Mock())
    
    assert isinstance(stage.startedAt, datetime)
    assert isinstance(stage.completedAt, datetime)

def test_create_task_stage():
    mock_client = MagicMock()
    mock_client.execute.return_value = {
        'createTaskStage': {
            'id': 'test-stage-id',
            'taskId': 'test-task-id',
            'name': 'Setup',
            'order': 1,
            'status': 'PENDING',
            'statusMessage': 'Starting...',
            'startedAt': None,
            'completedAt': None,
            'estimatedCompletionAt': None,
            'processedItems': 0,
            'totalItems': 1
        }
    }

    stage = TaskStage.create(
        client=mock_client,
        taskId='test-task-id',
        name='Setup',
        order=1,
        status='PENDING',
        statusMessage='Starting...',
        totalItems=1
    )

    assert stage.id == 'test-stage-id'
    assert stage.taskId == 'test-task-id'
    assert stage.name == 'Setup'
    assert stage.order == 1
    assert stage.status == 'PENDING'
    assert stage.statusMessage == 'Starting...'
    assert stage.totalItems == 1
    assert stage.processedItems == 0

    mock_client.execute.assert_called_once()
    mutation = mock_client.execute.call_args[0][0]
    assert 'mutation CreateTaskStage($input: CreateTaskStageInput!)' in mutation
    assert 'createTaskStage(input: $input)' in mutation

def test_update_task_stage():
    mock_client = MagicMock()
    test_datetime = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    mock_stage = TaskStage(
        id='test-stage-id',
        taskId='test-task-id',
        name='Setup',
        order=1,
        status='PENDING',
        statusMessage='Starting...',
        totalItems=1,
        processedItems=0,
        client=mock_client
    )

    mock_client.execute.side_effect = [
        {
            'getTaskStage': {
                'taskId': 'test-task-id',
                'name': 'Setup',
                'order': 1,
                'status': 'PENDING',
                'statusMessage': 'Starting...',
                'totalItems': 1,
                'processedItems': 0
            }
        },
        {
            'updateTaskStage': {
                'id': 'test-stage-id',
                'taskId': 'test-task-id',
                'name': 'Setup',
                'order': 1,
                'status': 'RUNNING',
                'statusMessage': 'Processing...',
                'startedAt': test_datetime,
                'totalItems': 1,
                'processedItems': 0
            }
        }
    ]

    updated = mock_stage.update(
        status='RUNNING',
        statusMessage='Processing...',
        startedAt=test_datetime
    )

    assert updated.status == 'RUNNING'
    assert updated.statusMessage == 'Processing...'
    assert updated.startedAt == test_datetime

def test_get_task_stage_by_id():
    mock_client = MagicMock()
    mock_client.execute.return_value = {
        'getTaskStage': {
            'id': 'test-stage-id',
            'taskId': 'test-task-id',
            'name': 'Setup',
            'order': 1,
            'status': 'PENDING',
            'statusMessage': 'Starting...',
            'startedAt': None,
            'completedAt': None,
            'estimatedCompletionAt': None,
            'processedItems': 0,
            'totalItems': 1
        }
    }

    stage = TaskStage.get_by_id('test-stage-id', mock_client)
    assert stage.id == 'test-stage-id'
    assert stage.taskId == 'test-task-id'
    assert stage.name == 'Setup'
    assert stage.order == 1
    assert stage.status == 'PENDING'

    mock_client.execute.assert_called_once()
    query = mock_client.execute.call_args[0][0]
    assert 'query GetTaskStage($id: ID!)' in query
    assert 'getTaskStage(id: $id)' in query

def test_start_processing():
    mock_client = MagicMock()
    mock_stage = TaskStage(
        id='test-stage-id',
        taskId='test-task-id',
        name='Setup',
        order=1,
        status='PENDING',
        statusMessage='Starting...',
        totalItems=1,
        processedItems=0,
        client=mock_client
    )

    mock_client.execute.side_effect = [
        {
            'getTaskStage': {
                'taskId': 'test-task-id',
                'name': 'Setup',
                'order': 1,
                'status': 'PENDING',
                'statusMessage': 'Starting...',
                'totalItems': 1,
                'processedItems': 0
            }
        },
        {
            'updateTaskStage': {
                'id': 'test-stage-id',
                'taskId': 'test-task-id',
                'name': 'Setup',
                'order': 1,
                'status': 'RUNNING',
                'statusMessage': 'Processing...',
                'startedAt': '2024-01-01T00:00:00Z',
                'totalItems': 1,
                'processedItems': 0
            }
        }
    ]

    mock_stage.start_processing()
    assert mock_client.execute.call_count == 2

def test_complete_processing():
    mock_client = MagicMock()
    mock_stage = TaskStage(
        id='test-stage-id',
        taskId='test-task-id',
        name='Setup',
        order=1,
        status='RUNNING',
        statusMessage='Processing...',
        totalItems=1,
        processedItems=1,
        client=mock_client
    )

    mock_client.execute.side_effect = [
        {
            'getTaskStage': {
                'taskId': 'test-task-id',
                'name': 'Setup',
                'order': 1,
                'status': 'RUNNING',
                'statusMessage': 'Processing...',
                'totalItems': 1,
                'processedItems': 1
            }
        },
        {
            'updateTaskStage': {
                'id': 'test-stage-id',
                'taskId': 'test-task-id',
                'name': 'Setup',
                'order': 1,
                'status': 'COMPLETED',
                'statusMessage': 'Complete',
                'completedAt': '2024-01-01T00:00:00Z',
                'totalItems': 1,
                'processedItems': 1
            }
        }
    ]

    mock_stage.complete_processing()
    assert mock_client.execute.call_count == 2

def test_fail_processing():
    mock_client = MagicMock()
    mock_stage = TaskStage(
        id='test-stage-id',
        taskId='test-task-id',
        name='Setup',
        order=1,
        status='RUNNING',
        statusMessage='Processing...',
        totalItems=1,
        processedItems=0,
        client=mock_client
    )

    mock_client.execute.side_effect = [
        {
            'getTaskStage': {
                'taskId': 'test-task-id',
                'name': 'Setup',
                'order': 1,
                'status': 'RUNNING',
                'statusMessage': 'Processing...',
                'totalItems': 1,
                'processedItems': 0
            }
        },
        {
            'updateTaskStage': {
                'id': 'test-stage-id',
                'taskId': 'test-task-id',
                'name': 'Setup',
                'order': 1,
                'status': 'FAILED',
                'statusMessage': 'Test error',
                'totalItems': 1,
                'processedItems': 0
            }
        }
    ]

    mock_stage.fail_processing('Test error')
    assert mock_client.execute.call_count == 2 