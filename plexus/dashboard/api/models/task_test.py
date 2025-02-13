from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from .task import Task
from .task_stage import TaskStage

def test_create_task():
    mock_client = MagicMock()
    mock_client.execute.return_value = {
        'createTask': {
            'id': 'test-task-id',
            'accountId': 'test-account',
            'type': 'TEST',
            'status': 'PENDING',
            'target': 'test/target',
            'command': 'test command',
            'createdAt': '2024-01-01T00:00:00Z',
            'metadata': {'test': 'data'},
            'startedAt': None,
            'completedAt': None,
            'estimatedCompletionAt': None,
            'errorMessage': None,
            'errorDetails': None,
            'stdout': None,
            'stderr': None,
            'currentStageId': None
        }
    }

    task = Task.create(
        client=mock_client,
        accountId='test-account',
        type='TEST',
        target='test/target',
        command='test command',
        metadata={'test': 'data'}
    )

    assert task.id == 'test-task-id'
    assert task.accountId == 'test-account'
    assert task.type == 'TEST'
    assert task.status == 'PENDING'
    assert task.target == 'test/target'
    assert task.command == 'test command'
    assert task.createdAt == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert task.metadata == {'test': 'data'}

    mock_client.execute.assert_called_once()
    mutation = mock_client.execute.call_args[0][0]
    assert 'mutation CreateTask($input: CreateTaskInput!)' in mutation
    assert 'createTask(input: $input)' in mutation

def test_update_task():
    mock_client = MagicMock()
    mock_task = Task(
        id='test-task-id',
        accountId='test-account',
        type='TEST',
        status='PENDING',
        target='test/target',
        command='test command',
        client=mock_client
    )

    mock_client.execute.side_effect = [
        {
            'getTask': {
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'PENDING',
                'target': 'test/target',
                'command': 'test command'
            }
        },
        {
            'updateTask': {
                'id': 'test-task-id',
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'RUNNING',
                'target': 'test/target',
                'command': 'test command',
                'createdAt': '2024-01-01T00:00:00Z',
                'startedAt': '2024-01-01T00:00:00Z'
            }
        }
    ]

    updated = mock_task.update(
        status='RUNNING',
        startedAt=datetime(2024, 1, 1, tzinfo=timezone.utc)
    )

    assert updated.status == 'RUNNING'
    assert updated.startedAt == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert mock_client.execute.call_count == 2

def test_get_task_by_id():
    mock_client = MagicMock()
    mock_client.execute.return_value = {
        'getTask': {
            'id': 'test-task-id',
            'accountId': 'test-account',
            'type': 'TEST',
            'status': 'PENDING',
            'target': 'test/target',
            'command': 'test command',
            'createdAt': '2024-01-01T00:00:00Z'
        }
    }

    task = Task.get_by_id('test-task-id', mock_client)
    assert task.id == 'test-task-id'
    assert task.accountId == 'test-account'
    assert task.type == 'TEST'
    assert task.status == 'PENDING'

    mock_client.execute.assert_called_once()
    query = mock_client.execute.call_args[0][0]
    assert 'query GetTask($id: ID!)' in query
    assert 'getTask(id: $id)' in query

def test_get_stages():
    mock_client = MagicMock()
    mock_task = Task(
        id='test-task-id',
        accountId='test-account',
        type='TEST',
        status='PENDING',
        target='test/target',
        command='test command',
        client=mock_client
    )

    mock_client.execute.return_value = {
        'listTaskStageByTaskId': {
            'items': [
                {
                    'id': 'test-stage-1',
                    'taskId': mock_task.id,
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
            ]
        }
    }

    stages = mock_task.get_stages()
    assert len(stages) == 1
    assert isinstance(stages[0], TaskStage)
    assert stages[0].id == 'test-stage-1'
    assert stages[0].name == 'Setup'

    mock_client.execute.assert_called_once()
    query = mock_client.execute.call_args[0][0]
    assert 'query ListTaskStageByTaskId($taskId: String!, $limit: Int, $nextToken: String)' in query
    assert 'listTaskStageByTaskId(taskId: $taskId, limit: $limit, nextToken: $nextToken)' in query

def test_start_processing():
    mock_client = MagicMock()
    mock_task = Task(
        id='test-task-id',
        accountId='test-account',
        type='TEST',
        status='PENDING',
        target='test/target',
        command='test command',
        client=mock_client
    )

    mock_client.execute.side_effect = [
        {
            'getTask': {
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'PENDING',
                'target': 'test/target',
                'command': 'test command'
            }
        },
        {
            'updateTask': {
                'id': 'test-task-id',
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'RUNNING',
                'target': 'test/target',
                'command': 'test command',
                'startedAt': '2024-01-01T00:00:00Z'
            }
        }
    ]

    mock_task.start_processing()
    assert mock_client.execute.call_count == 2

def test_complete_processing():
    mock_client = MagicMock()
    mock_task = Task(
        id='test-task-id',
        accountId='test-account',
        type='TEST',
        status='RUNNING',
        target='test/target',
        command='test command',
        client=mock_client
    )

    mock_client.execute.side_effect = [
        {
            'getTask': {
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'RUNNING',
                'target': 'test/target',
                'command': 'test command'
            }
        },
        {
            'updateTask': {
                'id': 'test-task-id',
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'COMPLETED',
                'target': 'test/target',
                'command': 'test command',
                'completedAt': '2024-01-01T00:00:00Z'
            }
        }
    ]

    mock_task.complete_processing()
    assert mock_client.execute.call_count == 2

def test_fail_processing():
    mock_client = MagicMock()
    mock_task = Task(
        id='test-task-id',
        accountId='test-account',
        type='TEST',
        status='RUNNING',
        target='test/target',
        command='test command',
        client=mock_client
    )

    def mock_execute(query, variables):
        if 'query GetTask($id: ID!)' in query:
            return {
                'getTask': {
                    'id': 'test-task-id',
                    'accountId': 'test-account',
                    'type': 'TEST',
                    'status': 'RUNNING',
                    'target': 'test/target',
                    'command': 'test command'
                }
            }
        elif 'query ListTaskStageByTaskId' in query:
            return {
                'listTaskStageByTaskId': {
                    'items': [
                        {
                            'id': 'test-stage-1',
                            'taskId': 'test-task-id',
                            'name': 'Running',
                            'order': 1,
                            'status': 'RUNNING',
                            'statusMessage': None,
                            'startedAt': None,
                            'completedAt': None,
                            'estimatedCompletionAt': None,
                            'processedItems': 0,
                            'totalItems': 1
                        }
                    ]
                }
            }
        elif 'mutation UpdateTaskStage' in query:
            return {
                'updateTaskStage': {
                    'id': 'test-stage-1',
                    'taskId': 'test-task-id',
                    'name': 'Running',
                    'order': 1,
                    'status': 'FAILED',
                    'statusMessage': 'Error: Test error',
                    'startedAt': None,
                    'completedAt': '2024-01-01T00:00:00Z',
                    'estimatedCompletionAt': None,
                    'processedItems': 0,
                    'totalItems': 1
                }
            }
        elif 'mutation UpdateTask' in query:
            return {
                'updateTask': {
                    'id': 'test-task-id',
                    'accountId': 'test-account',
                    'type': 'TEST',
                    'status': 'FAILED',
                    'target': 'test/target',
                    'command': 'test command',
                    'errorMessage': 'Test error',
                    'errorDetails': {'details': 'test'}
                }
            }
        elif 'query GetTaskStage($id: ID!)' in query:
            if variables['id'] == 'test-stage-1':
                return {
                    'getTaskStage': {
                        'id': 'test-stage-1',
                        'taskId': 'test-task-id',
                        'name': 'Running',
                        'order': 1,
                        'status': variables.get('status', 'RUNNING')
                    }
                }
            return {}
        return {}

    mock_client.execute = MagicMock(side_effect=mock_execute)
    mock_task.fail_processing('Test error', {'details': 'test'})
    assert mock_client.execute.call_count == 6

def test_update_progress():
    mock_client = MagicMock()
    mock_task = Task(
        id='test-task-id',
        accountId='test-account',
        type='TEST',
        status='RUNNING',
        target='test/target',
        command='test command',
        client=mock_client
    )

    stage_configs = {
        'Setup': {
            'order': 1,
            'totalItems': 1,
            'processedItems': 1,
            'statusMessage': 'Setup complete'
        },
        'Running': {
            'order': 2,
            'totalItems': 100,
            'processedItems': 50,
            'statusMessage': 'Processing...'
        }
    }

    def mock_execute(query, variables):
        if 'query GetTask($id: ID!)' in query:
            return {
                'getTask': {
                    'id': 'test-task-id',
                    'accountId': 'test-account',
                    'type': 'TEST',
                    'status': 'RUNNING',
                    'target': 'test/target',
                    'command': 'test command'
                }
            }
        elif 'query ListTaskStageByTaskId' in query:
            return {
                'listTaskStageByTaskId': {
                    'items': []
                }
            }
        elif 'mutation CreateTaskStage' in query:
            if variables['input']['name'] == 'Setup':
                return {
                    'createTaskStage': {
                        'id': 'test-stage-1',
                        'taskId': mock_task.id,
                        'name': 'Setup',
                        'order': 1,
                        'status': 'COMPLETED',
                        'statusMessage': 'Setup complete',
                        'processedItems': 1,
                        'totalItems': 1,
                        'startedAt': None,
                        'completedAt': None,
                        'estimatedCompletionAt': None
                    }
                }
            else:
                return {
                    'createTaskStage': {
                        'id': 'test-stage-2',
                        'taskId': mock_task.id,
                        'name': 'Running',
                        'order': 2,
                        'status': 'RUNNING',
                        'statusMessage': 'Processing...',
                        'processedItems': 50,
                        'totalItems': 100,
                        'startedAt': None,
                        'completedAt': None,
                        'estimatedCompletionAt': None
                    }
                }
        elif 'mutation UpdateTaskStage' in query:
            if variables['input']['name'] == 'Setup':
                return {
                    'updateTaskStage': {
                        'id': 'test-stage-1',
                        'taskId': mock_task.id,
                        'name': 'Setup',
                        'order': 1,
                        'status': 'COMPLETED',
                        'statusMessage': 'Setup complete',
                        'processedItems': 1,
                        'totalItems': 1,
                        'startedAt': None,
                        'completedAt': None,
                        'estimatedCompletionAt': None
                    }
                }
            else:
                return {
                    'updateTaskStage': {
                        'id': 'test-stage-2',
                        'taskId': mock_task.id,
                        'name': 'Running',
                        'order': 2,
                        'status': 'RUNNING',
                        'statusMessage': 'Processing...',
                        'processedItems': 50,
                        'totalItems': 100,
                        'startedAt': None,
                        'completedAt': None,
                        'estimatedCompletionAt': None
                    }
                }
        elif 'mutation UpdateTask' in query:
            if 'currentStageId' in variables['input']:
                return {
                    'updateTask': {
                        'id': 'test-task-id',
                        'accountId': 'test-account',
                        'type': 'TEST',
                        'status': 'RUNNING',
                        'target': 'test/target',
                        'command': 'test command',
                        'currentStageId': variables['input']['currentStageId']
                    }
                }
            else:
                return {
                    'updateTask': {
                        'id': 'test-task-id',
                        'accountId': 'test-account',
                        'type': 'TEST',
                        'status': 'RUNNING',
                        'target': 'test/target',
                        'command': 'test command'
                    }
                }
        elif 'query GetTaskStage($id: ID!)' in query:
            if variables['id'] == 'test-stage-1':
                return {
                    'getTaskStage': {
                        'taskId': 'test-task-id',
                        'name': 'Setup',
                        'order': 1,
                        'status': 'COMPLETED'
                    }
                }
            elif variables['id'] == 'test-stage-2':
                return {
                    'getTaskStage': {
                        'taskId': 'test-task-id',
                        'name': 'Running',
                        'order': 2,
                        'status': 'RUNNING'
                    }
                }
            return {}
        return {}

    mock_client.execute = MagicMock(side_effect=mock_execute)

    stages = mock_task.update_progress(
        50,  # current
        100,  # total
        stage_configs,
        estimated_completion_at=datetime(2024, 1, 1, tzinfo=timezone.utc)
    )

    assert len(stages) == 2
    assert stages[0].name == 'Setup'
    assert stages[0].status == 'COMPLETED'
    assert stages[1].name == 'Running'
    assert stages[1].status == 'RUNNING'
    assert mock_client.execute.call_count == 11