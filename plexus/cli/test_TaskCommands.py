import pytest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner
import json
import rich.table
from datetime import datetime

from plexus.cli.TaskCommands import tasks, task, list, last, delete, info, format_datetime, format_task_content


@pytest.fixture
def runner():
    """Create a Click CLI runner for testing"""
    return CliRunner()


@pytest.fixture
def mock_client():
    """Mock the PlexusDashboardClient"""
    with patch('plexus.cli.TaskCommands.create_client') as mock_create:
        mock_client = Mock()
        mock_create.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_resolve_account():
    """Mock the resolve_account_id_for_command function"""
    with patch('plexus.cli.TaskCommands.resolve_account_id_for_command') as mock:
        mock.return_value = 'account-123'
        yield mock


@pytest.fixture
def sample_task_data():
    """Sample task data for testing"""
    return {
        'id': 'task-123',
        'accountId': 'account-123',
        'scorecardId': 'scorecard-456',
        'scoreId': 'score-789',
        'type': 'SCORE',
        'status': 'COMPLETED',
        'target': 'dataset-abc',
        'command': 'score --scorecard test --score accuracy',
        'currentStageId': 'stage-final',
        'workerNodeId': 'worker-001',
        'dispatchStatus': 'DISPATCHED',
        'description': 'Test scoring task',
        'metadata': {'key': 'value'},
        'createdAt': '2024-06-15T10:00:00Z',
        'updatedAt': '2024-06-15T10:30:00Z',
        'startedAt': '2024-06-15T10:05:00Z',
        'completedAt': '2024-06-15T10:30:00Z',
        'estimatedCompletionAt': '2024-06-15T10:35:00Z',
        'errorMessage': None,
        'errorDetails': None,
        'stdout': 'Task completed successfully',
        'stderr': None
    }


@pytest.fixture
def sample_task_stages():
    """Sample task stages for testing"""
    return [
        {
            'id': 'stage-1',
            'taskId': 'task-123',
            'name': 'Setup',
            'order': 1,
            'status': 'COMPLETED',
            'totalItems': None,
            'processedItems': None,
            'startedAt': '2024-06-15T10:05:00Z',
            'completedAt': '2024-06-15T10:10:00Z',
            'estimatedCompletionAt': None,
            'statusMessage': 'Setup completed'
        },
        {
            'id': 'stage-2', 
            'taskId': 'task-123',
            'name': 'Processing',
            'order': 2,
            'status': 'COMPLETED',
            'totalItems': 100,
            'processedItems': 100,
            'startedAt': '2024-06-15T10:10:00Z',
            'completedAt': '2024-06-15T10:25:00Z',
            'estimatedCompletionAt': None,
            'statusMessage': 'Processing completed'
        }
    ]


class TestHelperFunctions:
    """Test helper functions"""
    
    def test_format_datetime_with_datetime(self):
        """Test format_datetime with a valid datetime"""
        dt = datetime(2024, 6, 15, 10, 30, 45)
        result = format_datetime(dt)
        assert result == "2024-06-15 10:30:45"
    
    def test_format_datetime_with_none(self):
        """Test format_datetime with None"""
        result = format_datetime(None)
        assert result == "N/A"
    
    def test_format_task_content(self, sample_task_data, sample_task_stages):
        """Test format_task_content function"""
        # Mock Task object
        mock_task = Mock()
        mock_task.id = sample_task_data['id']
        mock_task.accountId = sample_task_data['accountId']
        mock_task.scorecardId = sample_task_data['scorecardId']
        mock_task.scoreId = sample_task_data['scoreId']
        mock_task.type = sample_task_data['type']
        mock_task.status = sample_task_data['status']
        mock_task.target = sample_task_data['target']
        mock_task.command = sample_task_data['command']
        mock_task.currentStageId = sample_task_data['currentStageId']
        mock_task.workerNodeId = sample_task_data['workerNodeId']
        mock_task.dispatchStatus = sample_task_data['dispatchStatus']
        mock_task.description = sample_task_data['description']
        mock_task.metadata = sample_task_data['metadata']
        mock_task.createdAt = datetime.fromisoformat(sample_task_data['createdAt'].replace('Z', '+00:00'))
        mock_task.updatedAt = datetime.fromisoformat(sample_task_data['updatedAt'].replace('Z', '+00:00'))
        mock_task.startedAt = datetime.fromisoformat(sample_task_data['startedAt'].replace('Z', '+00:00'))
        mock_task.completedAt = datetime.fromisoformat(sample_task_data['completedAt'].replace('Z', '+00:00'))
        mock_task.estimatedCompletionAt = datetime.fromisoformat(sample_task_data['estimatedCompletionAt'].replace('Z', '+00:00'))
        mock_task.errorMessage = sample_task_data['errorMessage']
        mock_task.errorDetails = sample_task_data['errorDetails']
        mock_task.stdout = sample_task_data['stdout']
        mock_task.stderr = sample_task_data['stderr']
        
        # Mock stages
        mock_stages = []
        for stage_data in sample_task_stages:
            mock_stage = Mock()
            for key, value in stage_data.items():
                if key in ['startedAt', 'completedAt'] and value:
                    setattr(mock_stage, key, datetime.fromisoformat(value.replace('Z', '+00:00')))
                else:
                    setattr(mock_stage, key, value)
            mock_stages.append(mock_stage)
        
        mock_task.get_stages.return_value = mock_stages
        
        result = format_task_content(mock_task)
        
        # Verify result is a Text object with content
        assert hasattr(result, 'append')  # Text objects have append method
        # Convert to string to check content
        result_str = str(result)
        assert 'task-123' in result_str
        assert 'COMPLETED' in result_str
        assert 'Setup' in result_str
        assert 'Processing' in result_str


class TestTasksGroup:
    """Test the main tasks group command"""
    
    def test_tasks_group_exists(self, runner):
        """Test that the tasks group exists and shows help"""
        result = runner.invoke(tasks, ['--help'])
        assert result.exit_code == 0
        assert 'Manage task records in the dashboard' in result.output


class TestTaskGroup:
    """Test the task group command (alias)"""
    
    def test_task_group_exists(self, runner):
        """Test that the task group exists and shows help"""
        result = runner.invoke(task, ['--help'])
        assert result.exit_code == 0
        assert 'Manage task records in the dashboard (alias for \'tasks\')' in result.output


class TestListCommand:
    """Test the list subcommand"""
    
    def test_list_command_success(self, runner, mock_client, mock_resolve_account, sample_task_data):
        """Test list command with successful response"""
        # Setup mock response
        mock_client.execute.return_value = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': [sample_task_data]
            }
        }
        
        with patch('plexus.cli.TaskCommands.Task') as mock_task_class:
            mock_task = Mock()
            mock_task.type = 'SCORE'
            mock_task.status = 'COMPLETED'
            mock_task.get_stages.return_value = []
            mock_task_class.from_dict.return_value = mock_task
            
            with patch('plexus.cli.TaskCommands.console') as mock_console:
                with patch('plexus.cli.TaskCommands.format_task_content') as mock_format:
                    mock_format.return_value = "Formatted task content"
                    
                    result = runner.invoke(tasks, ['list'])
                    
                    assert result.exit_code == 0
                    mock_resolve_account.assert_called_once_with(mock_client, None)
                    mock_client.execute.assert_called_once()
                    mock_console.print.assert_called()  # Panel should be printed
    
    def test_list_command_with_filters(self, runner, mock_client, mock_resolve_account, sample_task_data):
        """Test list command with status and type filters"""
        mock_client.execute.return_value = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': [sample_task_data]
            }
        }
        
        with patch('plexus.cli.TaskCommands.Task') as mock_task_class:
            mock_task = Mock()
            mock_task.type = 'SCORE'
            mock_task.status = 'COMPLETED'
            mock_task.get_stages.return_value = []
            mock_task_class.from_dict.return_value = mock_task
            
            with patch('plexus.cli.TaskCommands.console'):
                with patch('plexus.cli.TaskCommands.format_task_content') as mock_format:
                    mock_format.return_value = "Formatted task content"
                    
                    result = runner.invoke(tasks, [
                        'list',
                        '--status', 'COMPLETED',
                        '--type', 'SCORE',
                        '--limit', '5'
                    ])
                    
                    assert result.exit_code == 0
                    mock_client.execute.assert_called_once()
    
    def test_list_command_no_tasks_found(self, runner, mock_client, mock_resolve_account):
        """Test list command when no tasks are found"""
        mock_client.execute.return_value = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': []
            }
        }
        
        with patch('plexus.cli.TaskCommands.console') as mock_console:
            result = runner.invoke(tasks, ['list'])
            
            assert result.exit_code == 0
            # Should print "No tasks found" message
            mock_console.print.assert_called_with('[yellow]No tasks found matching the criteria[/yellow]')
    
    def test_list_command_with_account(self, runner, mock_client, mock_resolve_account, sample_task_data):
        """Test list command with specific account"""
        mock_client.execute.return_value = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': [sample_task_data]
            }
        }
        
        with patch('plexus.cli.TaskCommands.Task') as mock_task_class:
            mock_task = Mock()
            mock_task.type = 'SCORE'
            mock_task.status = 'COMPLETED'
            mock_task.get_stages.return_value = []
            mock_task_class.from_dict.return_value = mock_task
            
            with patch('plexus.cli.TaskCommands.console'):
                with patch('plexus.cli.TaskCommands.format_task_content') as mock_format:
                    mock_format.return_value = "Formatted task content"
                    
                    result = runner.invoke(tasks, ['list', '--account', 'test-account'])
                    
                    assert result.exit_code == 0
                    mock_resolve_account.assert_called_once_with(mock_client, 'test-account')


class TestLastCommand:
    """Test the last subcommand"""
    
    def test_last_command_success(self, runner, mock_client, mock_resolve_account, sample_task_data):
        """Test last command with successful response"""
        mock_client.execute.return_value = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': [sample_task_data]
            }
        }
        
        with patch('plexus.cli.TaskCommands.Task') as mock_task_class:
            mock_task = Mock()
            mock_task.type = 'SCORE'
            mock_task.status = 'COMPLETED'
            mock_task.get_stages.return_value = []
            mock_task_class.from_dict.return_value = mock_task
            
            with patch('plexus.cli.TaskCommands.console') as mock_console:
                with patch('plexus.cli.TaskCommands.format_task_content') as mock_format:
                    mock_format.return_value = "Formatted task content"
                    
                    result = runner.invoke(tasks, ['last'])
                    
                    assert result.exit_code == 0
                    mock_resolve_account.assert_called_once_with(mock_client, None)
                    mock_client.execute.assert_called_once()
                    # Should print a panel with the most recent task
                    mock_console.print.assert_called()
    
    def test_last_command_no_tasks(self, runner, mock_client, mock_resolve_account):
        """Test last command when no tasks exist"""
        mock_client.execute.return_value = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': []
            }
        }
        
        with patch('plexus.cli.TaskCommands.console') as mock_console:
            result = runner.invoke(tasks, ['last'])
            
            assert result.exit_code == 0
            mock_console.print.assert_called_with('[yellow]No tasks found for this account[/yellow]')


class TestInfoCommand:
    """Test the info subcommand"""
    
    def test_info_command_success(self, runner, mock_client, sample_task_data):
        """Test info command with valid task ID"""
        with patch('plexus.cli.TaskCommands.Task') as mock_task_class:
            mock_task = Mock()
            mock_task.id = 'task-123'
            mock_task.type = 'SCORE'
            mock_task.status = 'COMPLETED'
            mock_task.get_stages.return_value = []
            mock_task_class.get_by_id.return_value = mock_task
            
            with patch('plexus.cli.TaskCommands.console') as mock_console:
                result = runner.invoke(tasks, ['info', '--id', 'task-123'])
                
                assert result.exit_code == 0
                mock_task_class.get_by_id.assert_called_once_with('task-123', mock_client)
                mock_console.print.assert_called()  # Panel should be printed
    
    def test_info_command_task_not_found(self, runner, mock_client):
        """Test info command with non-existent task ID"""
        with patch('plexus.cli.TaskCommands.Task') as mock_task_class:
            mock_task_class.get_by_id.return_value = None
            
            with patch('plexus.cli.TaskCommands.console') as mock_console:
                result = runner.invoke(tasks, ['info', '--id', 'nonexistent'])
                
                assert result.exit_code == 0
                mock_console.print.assert_called_with('[yellow]Task not found: nonexistent[/yellow]')
    
    def test_info_command_missing_id(self, runner, mock_client):
        """Test info command without required ID parameter"""
        result = runner.invoke(tasks, ['info'])
        
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()
    
    def test_info_command_exception(self, runner, mock_client):
        """Test info command when an exception occurs"""
        with patch('plexus.cli.TaskCommands.Task') as mock_task_class:
            mock_task_class.get_by_id.side_effect = Exception("Database error")
            
            with patch('plexus.cli.TaskCommands.console') as mock_console:
                result = runner.invoke(tasks, ['info', '--id', 'task-123'])
                
                assert result.exit_code == 0
                # Should print error message
                mock_console.print.assert_called()
                assert any('Error retrieving task' in str(call) for call in mock_console.print.call_args_list)


class TestDeleteCommand:
    """Test the delete subcommand"""
    
    def test_delete_command_missing_criteria(self, runner, mock_client):
        """Test delete command without any deletion criteria"""
        with patch('plexus.cli.TaskCommands.console') as mock_console:
            result = runner.invoke(tasks, ['delete'])
            
            assert result.exit_code == 1
            mock_console.print.assert_called_with('[red]Error: Must specify either --task-id, --status, --type, or --all[/red]')
    
    def test_delete_command_by_task_id(self, runner, mock_client, mock_resolve_account, sample_task_data):
        """Test delete command with specific task ID"""
        mock_client.execute.side_effect = [
            # First call: get tasks
            {
                'listTaskByAccountIdAndUpdatedAt': {
                    'items': [sample_task_data]
                }
            },
            # Subsequent calls: delete stages and task
            {'deleteTaskStage': {'id': 'stage-1'}},
            {'deleteTask': {'id': 'task-123'}}
        ]
        
        with patch('plexus.cli.TaskCommands.Task') as mock_task_class:
            mock_task = Mock()
            mock_task.id = 'task-123'
            mock_task.accountId = 'account-123'
            mock_task.type = 'SCORE'
            mock_task.status = 'COMPLETED'
            mock_task.target = 'dataset-abc'
            mock_task.command = 'score --scorecard test'
            mock_task.get_stages.return_value = []  # No stages for simplicity
            mock_task_class.from_dict.return_value = mock_task
            
            with patch('plexus.cli.TaskCommands.console') as mock_console:
                with patch('click.progressbar') as mock_progress:
                    mock_progress.return_value.__enter__.return_value = [sample_task_data]
                    
                    result = runner.invoke(tasks, [
                        'delete',
                        '--task-id', 'task-123',
                        '--yes'  # Skip confirmation
                    ])
                    
                    assert result.exit_code == 0
                    # Should show success message
                    assert any('Successfully deleted' in str(call) for call in mock_console.print.call_args_list)
    
    def test_delete_command_by_status(self, runner, mock_client, mock_resolve_account, sample_task_data):
        """Test delete command by status"""
        mock_client.execute.side_effect = [
            # First call: get tasks
            {
                'listTaskByAccountIdAndUpdatedAt': {
                    'items': [sample_task_data]
                }
            },
            # Subsequent calls: delete task
            {'deleteTask': {'id': 'task-123'}}
        ]
        
        with patch('plexus.cli.TaskCommands.Task') as mock_task_class:
            mock_task = Mock()
            mock_task.id = 'task-123'
            mock_task.accountId = 'account-123'
            mock_task.type = 'SCORE'
            mock_task.status = 'COMPLETED'
            mock_task.target = 'dataset-abc'
            mock_task.command = 'score --scorecard test'
            mock_task.get_stages.return_value = []
            mock_task_class.from_dict.return_value = mock_task
            
            with patch('plexus.cli.TaskCommands.console'):
                with patch('click.progressbar') as mock_progress:
                    mock_progress.return_value.__enter__.return_value = [sample_task_data]
                    
                    result = runner.invoke(tasks, [
                        'delete',
                        '--status', 'COMPLETED',
                        '--yes'
                    ])
                    
                    assert result.exit_code == 0
    
    def test_delete_command_no_confirmation(self, runner, mock_client, mock_resolve_account, sample_task_data):
        """Test delete command when user declines confirmation"""
        mock_client.execute.return_value = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': [sample_task_data]
            }
        }
        
        with patch('plexus.cli.TaskCommands.Task') as mock_task_class:
            mock_task = Mock()
            mock_task.id = 'task-123'
            mock_task.accountId = 'account-123'
            mock_task.type = 'SCORE'
            mock_task.status = 'COMPLETED'
            mock_task.target = 'dataset-abc'
            mock_task.command = 'score --scorecard test'
            mock_task.get_stages.return_value = []
            mock_task_class.from_dict.return_value = mock_task
            
            with patch('plexus.cli.TaskCommands.console') as mock_console:
                with patch('click.confirm', return_value=False):
                    result = runner.invoke(tasks, [
                        'delete',
                        '--status', 'COMPLETED'
                    ])
                    
                    assert result.exit_code == 0
                    mock_console.print.assert_called_with('[yellow]Operation cancelled[/yellow]')
    
    def test_delete_command_no_tasks_found(self, runner, mock_client, mock_resolve_account):
        """Test delete command when no tasks match criteria"""
        mock_client.execute.return_value = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': []
            }
        }
        
        with patch('plexus.cli.TaskCommands.console') as mock_console:
            result = runner.invoke(tasks, [
                'delete',
                '--status', 'NONEXISTENT'
            ])
            
            assert result.exit_code == 0
            # The actual message from the code is "No tasks found for the account" 
            mock_console.print.assert_called_with('[yellow]No tasks found for the account[/yellow]')


class TestIntegration:
    """Integration tests combining multiple commands"""
    
    def test_list_then_info_workflow(self, runner, mock_client, mock_resolve_account, sample_task_data):
        """Test typical workflow: list tasks then get info on specific task"""
        # Setup mock for list command
        mock_client.execute.return_value = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': [sample_task_data]
            }
        }
        
        with patch('plexus.cli.TaskCommands.Task') as mock_task_class:
            mock_task = Mock()
            mock_task.id = 'task-123'
            mock_task.type = 'SCORE'
            mock_task.status = 'COMPLETED'
            mock_task.get_stages.return_value = []
            mock_task_class.from_dict.return_value = mock_task
            mock_task_class.get_by_id.return_value = mock_task
            
            with patch('plexus.cli.TaskCommands.console'):
                with patch('plexus.cli.TaskCommands.format_task_content') as mock_format:
                    mock_format.return_value = "Formatted task content"
                    
                    # First list tasks
                    list_result = runner.invoke(tasks, ['list', '--limit', '1'])
                    assert list_result.exit_code == 0
                    
                    # Then get info on specific task
                    info_result = runner.invoke(tasks, ['info', '--id', 'task-123'])
                    assert info_result.exit_code == 0
                    
                    # Verify both commands worked
                    mock_task_class.from_dict.assert_called()
                    mock_task_class.get_by_id.assert_called_with('task-123', mock_client)