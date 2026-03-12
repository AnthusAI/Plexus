import pytest
import click
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from datetime import datetime, timezone
from plexus.cli.task.tasks import tasks, delete, list
from plexus.dashboard.api.models.task import Task

@pytest.fixture
def mock_client():
    with patch('plexus.cli.task.tasks.create_client') as mock:
        client = MagicMock()
        mock.return_value = client
        yield client

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def mock_task_fields():
    with patch('plexus.dashboard.api.models.task.Task.fields') as mock:
        mock.return_value = """
            id
            accountId
            type
            status
            target
            command
            createdAt
            updatedAt
            stages {
                items {
                    id
                    taskId
                    name
                    order
                    status
                }
            }
            scorecardId
            scoreId
            currentStageId
            workerNodeId
            dispatchStatus
            startedAt
            completedAt
            estimatedCompletionAt
            description
            metadata
            errorMessage
            errorDetails
            stdout
            stderr
        """
        yield mock

@pytest.fixture
def mock_task_from_dict():
    with patch('plexus.dashboard.api.models.task.Task.from_dict') as mock:
        def mock_from_dict(data, client):
            task = MagicMock()
            task.id = data['id']
            task.accountId = data['accountId']
            task.type = data['type']
            task.status = data['status']
            task.target = data['target']
            task.command = data['command']
            task.createdAt = datetime.strptime(data['createdAt'], '%Y-%m-%dT%H:%M:%SZ')
            task.updatedAt = datetime.strptime(data['updatedAt'], '%Y-%m-%dT%H:%M:%SZ')
            task.stages = data['stages']
            task.get_stages.return_value = []
            task.scorecardId = data['scorecardId']
            task.scoreId = data['scoreId']
            task.currentStageId = data['currentStageId']
            task.workerNodeId = data['workerNodeId']
            task.dispatchStatus = data['dispatchStatus']
            task.startedAt = None if data['startedAt'] is None else datetime.strptime(data['startedAt'], '%Y-%m-%dT%H:%M:%SZ')
            task.completedAt = None if data['completedAt'] is None else datetime.strptime(data['completedAt'], '%Y-%m-%dT%H:%M:%SZ')
            task.estimatedCompletionAt = None if data['estimatedCompletionAt'] is None else datetime.strptime(data['estimatedCompletionAt'], '%Y-%m-%dT%H:%M:%SZ')
            task.description = data['description']
            task.metadata = data['metadata']
            task.errorMessage = data['errorMessage']
            task.errorDetails = data['errorDetails']
            task.stdout = data['stdout']
            task.stderr = data['stderr']
            task.__str__ = lambda self: f"{self.type} Task - {self.status}"
            task.__repr__ = lambda self: f"{self.type} Task - {self.status}"
            return task
        mock.side_effect = mock_from_dict
        yield mock

def test_list_tasks(mock_client, runner, mock_task_fields, mock_task_from_dict):
    # Mock the account resolution and task listing
    with patch('plexus.cli.task.tasks.resolve_account_id_for_command') as mock_resolve:
        mock_resolve.return_value = 'test-account-id'
        
        mock_client.execute.return_value = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': [
                    {
                        'id': 'task-1',
                        'accountId': 'test-account-id',
                        'type': 'TEST',
                        'status': 'COMPLETED',
                        'target': 'test/target',
                        'command': 'test command',
                        'createdAt': '2024-01-01T00:00:00Z',
                        'updatedAt': '2024-01-01T00:00:00Z',
                        'stages': {'items': []},
                        'scorecardId': None,
                        'scoreId': None,
                        'currentStageId': None,
                        'workerNodeId': None,
                        'dispatchStatus': None,
                        'startedAt': None,
                        'completedAt': None,
                        'estimatedCompletionAt': None,
                        'description': None,
                        'metadata': None,
                        'errorMessage': None,
                        'errorDetails': None,
                        'stdout': None,
                        'stderr': None
                    }
                ]
            }
        }

        result = runner.invoke(tasks, ['list', '--account', 'test-account'])
        assert result.exit_code == 0
        assert 'task-1' in result.output
        assert 'TEST' in result.output
        assert 'COMPLETED' in result.output

def test_delete_specific_task(mock_client, runner, mock_task_fields, mock_task_from_dict):
    # Mock the account resolution and task operations
    with patch('plexus.cli.task.tasks.resolve_account_id_for_command') as mock_resolve:
        mock_resolve.return_value = 'test-account-id'
        
        mock_client.execute.side_effect = [
            {
                'listTaskByAccountIdAndUpdatedAt': {
                    'items': [
                        {
                            'id': 'task-1',
                            'accountId': 'test-account-id',
                            'type': 'TEST',
                            'status': 'COMPLETED',
                            'target': 'test/target',
                            'command': 'test command',
                            'createdAt': '2024-01-01T00:00:00Z',
                            'updatedAt': '2024-01-01T00:00:00Z',
                            'stages': {'items': []},
                            'scorecardId': None,
                            'scoreId': None,
                            'currentStageId': None,
                            'workerNodeId': None,
                            'dispatchStatus': None,
                            'startedAt': None,
                            'completedAt': None,
                            'estimatedCompletionAt': None,
                            'description': None,
                            'metadata': None,
                            'errorMessage': None,
                            'errorDetails': None,
                            'stdout': None,
                            'stderr': None
                        }
                    ]
                }
            },
            # Mock successful task deletion
            {'deleteTask': {'id': 'task-1'}}
        ]

        result = runner.invoke(tasks, ['delete', '--account', 'test-account', '--task-id', 'task-1', '-y'])
        assert result.exit_code == 0
        assert 'Successfully deleted' in result.output

def test_delete_all_tasks(mock_client, runner, mock_task_fields, mock_task_from_dict):
    # Mock listing all tasks
    mock_client.execute.side_effect = [
        {
            'listTasks': {
                'items': [
                    {
                        'id': f'task-{i}',
                        'accountId': f'account-{i}',
                        'type': 'TEST',
                        'status': 'COMPLETED',
                        'target': 'test/target',
                        'command': 'test command',
                        'createdAt': '2024-01-01T00:00:00Z',
                        'updatedAt': '2024-01-01T00:00:00Z',
                        'stages': {'items': []},
                        'scorecardId': None,
                        'scoreId': None,
                        'currentStageId': None,
                        'workerNodeId': None,
                        'dispatchStatus': None,
                        'startedAt': None,
                        'completedAt': None,
                        'estimatedCompletionAt': None,
                        'description': None,
                        'metadata': None,
                        'errorMessage': None,
                        'errorDetails': None,
                        'stdout': None,
                        'stderr': None
                    }
                    for i in range(3)
                ]
            }
        },
        # Mock successful task deletions
        {'deleteTask': {'id': 'task-0'}},
        {'deleteTask': {'id': 'task-1'}},
        {'deleteTask': {'id': 'task-2'}}
    ]

    result = runner.invoke(tasks, ['delete', '--all', '-y'])
    assert result.exit_code == 0
    assert 'Successfully deleted' in result.output
    # Should have made 4 calls: 1 to list tasks, 3 to delete tasks
    assert mock_client.execute.call_count == 4

def test_delete_requires_criteria(mock_client, runner):
    result = runner.invoke(tasks, ['delete', '--account', 'test-account'])
    assert 'Error: Must specify either --task-id, --status, --type, or --all' in result.output
    assert result.exit_code == 1

def test_delete_requires_account_unless_all(mock_client, runner):
    # When delete command is called without --account and without --all, 
    # resolve_account_id_for_command will be called and should raise click.Abort()
    
    # Mock resolve_account_id_for_command to raise an exception (simulating missing account)
    with patch('plexus.cli.task.tasks.resolve_account_id_for_command') as mock_resolve:
        mock_resolve.side_effect = click.Abort()
        
        result = runner.invoke(tasks, ['delete', '--task-id', 'task-1'])
        # click.Abort() translates to exit code 1
        assert result.exit_code == 1

def test_delete_with_stages(mock_client, runner, mock_task_fields, mock_task_from_dict):
    # Mock the account resolution and task operations
    with patch('plexus.cli.task.tasks.resolve_account_id_for_command') as mock_resolve:
        mock_resolve.return_value = 'test-account-id'
        
        mock_client.execute.side_effect = [
            {
                'listTaskByAccountIdAndUpdatedAt': {
                    'items': [
                        {
                            'id': 'task-1',
                            'accountId': 'test-account-id',
                            'type': 'TEST',
                            'status': 'COMPLETED',
                            'target': 'test/target',
                            'command': 'test command',
                            'createdAt': '2024-01-01T00:00:00Z',
                            'updatedAt': '2024-01-01T00:00:00Z',
                            'stages': {
                                'items': [
                                    {
                                        'id': 'stage-1',
                                        'taskId': 'task-1',
                                        'name': 'Stage 1',
                                        'order': 1,
                                        'status': 'COMPLETED'
                                    }
                                ]
                            },
                            'scorecardId': None,
                            'scoreId': None,
                            'currentStageId': None,
                            'workerNodeId': None,
                            'dispatchStatus': None,
                            'startedAt': None,
                            'completedAt': None,
                            'estimatedCompletionAt': None,
                            'description': None,
                            'metadata': None,
                            'errorMessage': None,
                            'errorDetails': None,
                            'stdout': None,
                            'stderr': None
                        }
                    ]
                }
            },
            # Mock successful stage deletion
            {'deleteTaskStage': {'id': 'stage-1'}},
            # Mock successful task deletion
            {'deleteTask': {'id': 'task-1'}}
        ]

        result = runner.invoke(tasks, ['delete', '--account', 'test-account', '--task-id', 'task-1', '-y'])
        assert result.exit_code == 0
        assert 'Successfully deleted' in result.output
        assert 'stages' in result.output

def test_delete_confirmation_required(mock_client, runner, mock_task_fields, mock_task_from_dict):
    # Mock the account resolution and task listing
    with patch('plexus.cli.task.tasks.resolve_account_id_for_command') as mock_resolve:
        mock_resolve.return_value = 'test-account-id'
        
        mock_client.execute.return_value = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': [
                    {
                        'id': 'task-1',
                        'accountId': 'test-account-id',
                        'type': 'TEST',
                        'status': 'COMPLETED',
                        'target': 'test/target',
                        'command': 'test command',
                        'createdAt': '2024-01-01T00:00:00Z',
                        'updatedAt': '2024-01-01T00:00:00Z',
                        'stages': {'items': []},
                        'scorecardId': None,
                        'scoreId': None,
                        'currentStageId': None,
                        'workerNodeId': None,
                        'dispatchStatus': None,
                        'startedAt': None,
                        'completedAt': None,
                        'estimatedCompletionAt': None,
                        'description': None,
                        'metadata': None,
                        'errorMessage': None,
                        'errorDetails': None,
                        'stdout': None,
                        'stderr': None
                    }
                ]
            }
        }

        # Simulate user answering 'n' to confirmation
        result = runner.invoke(tasks, ['delete', '--account', 'test-account', '--task-id', 'task-1'], input='n\n')
        assert result.exit_code == 0
        assert 'Operation cancelled' in result.output 