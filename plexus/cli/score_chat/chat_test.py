import pytest
from unittest.mock import Mock, patch, AsyncMock
from click.testing import CliRunner
import json

from plexus.cli.score_chat.chat import score_chat, repl, message, end, register_tasks


@pytest.fixture
def runner():
    """Create a Click CLI runner for testing"""
    return CliRunner()


@pytest.fixture
def mock_repl():
    """Mock the ScoreChatREPL class"""
    with patch('plexus.cli.score_chat.chat.ScoreChatREPL') as mock:
        yield mock


@pytest.fixture
def mock_celery_functions():
    """Mock the Celery task functions"""
    with patch('plexus.cli.score_chat.chat.generate_chat_id') as mock_generate, \
         patch('plexus.cli.score_chat.chat.process_chat_message') as mock_process, \
         patch('plexus.cli.score_chat.chat.end_chat_session') as mock_end:
        yield {
            'generate_chat_id': mock_generate,
            'process_chat_message': mock_process,
            'end_chat_session': mock_end
        }


class TestScoreChatGroup:
    """Test the main score-chat group command"""
    
    def test_score_chat_group_exists(self, runner):
        """Test that the score-chat group exists and shows help"""
        result = runner.invoke(score_chat, ['--help'])
        assert result.exit_code == 0
        assert 'Commands for working with the Plexus score chat feature' in result.output


class TestReplCommand:
    """Test the repl subcommand"""
    
    def test_repl_command_without_options(self, runner, mock_repl):
        """Test repl command without scorecard and score options"""
        mock_instance = Mock()
        mock_repl.return_value = mock_instance
        
        result = runner.invoke(score_chat, ['repl'])
        
        assert result.exit_code == 0
        mock_repl.assert_called_once_with(None, None)
        mock_instance.run.assert_called_once()
    
    def test_repl_command_with_scorecard_only(self, runner, mock_repl):
        """Test repl command with only scorecard option"""
        mock_instance = Mock()
        mock_repl.return_value = mock_instance
        
        result = runner.invoke(score_chat, ['repl', '--scorecard', 'test-scorecard'])
        
        assert result.exit_code == 0
        mock_repl.assert_called_once_with('test-scorecard', None)
        mock_instance.run.assert_called_once()
    
    def test_repl_command_with_score_only(self, runner, mock_repl):
        """Test repl command with only score option"""
        mock_instance = Mock()
        mock_repl.return_value = mock_instance
        
        result = runner.invoke(score_chat, ['repl', '--score', 'test-score'])
        
        assert result.exit_code == 0
        mock_repl.assert_called_once_with(None, 'test-score')
        mock_instance.run.assert_called_once()
    
    def test_repl_command_with_both_options(self, runner, mock_repl):
        """Test repl command with both scorecard and score options"""
        mock_instance = Mock()
        mock_repl.return_value = mock_instance
        
        result = runner.invoke(score_chat, [
            'repl', 
            '--scorecard', 'test-scorecard',
            '--score', 'test-score'
        ])
        
        assert result.exit_code == 0
        mock_repl.assert_called_once_with('test-scorecard', 'test-score')
        mock_instance.run.assert_called_once()


class TestMessageCommand:
    """Test the message subcommand"""
    
    def test_message_command_required_params(self, runner, mock_celery_functions):
        """Test message command with all required parameters"""
        # Setup mock return values
        mock_celery_functions['generate_chat_id'].return_value = 'chat-123'
        mock_celery_functions['process_chat_message'].return_value = {
            'success': True,
            'response': 'Test response'
        }
        
        result = runner.invoke(score_chat, [
            'message',
            '--scorecard', 'test-scorecard',
            '--score', 'test-score', 
            '--message', 'Hello, world!'
        ])
        
        assert result.exit_code == 0
        assert 'Generated chat ID: chat-123' in result.output
        assert '"success": true' in result.output
        assert '"response": "Test response"' in result.output
        
        # Verify function calls
        mock_celery_functions['generate_chat_id'].assert_called_once()
        mock_celery_functions['process_chat_message'].assert_called_once_with(
            chat_id='chat-123',
            message='Hello, world!',
            scorecard='test-scorecard',
            score='test-score'
        )
    
    def test_message_command_with_chat_id(self, runner, mock_celery_functions):
        """Test message command with provided chat ID"""
        mock_celery_functions['process_chat_message'].return_value = {
            'success': True,
            'response': 'Test response'
        }
        
        result = runner.invoke(score_chat, [
            'message',
            '--scorecard', 'test-scorecard',
            '--score', 'test-score',
            '--message', 'Hello, world!',
            '--chat-id', 'existing-chat-123'
        ])
        
        assert result.exit_code == 0
        assert 'Generated chat ID' not in result.output  # Should not generate new ID
        assert '"success": true' in result.output
        
        # Verify generate_chat_id was not called
        mock_celery_functions['generate_chat_id'].assert_not_called()
        mock_celery_functions['process_chat_message'].assert_called_once_with(
            chat_id='existing-chat-123',
            message='Hello, world!',
            scorecard='test-scorecard',
            score='test-score'
        )
    
    def test_message_command_missing_scorecard(self, runner, mock_celery_functions):
        """Test message command fails without required scorecard parameter"""
        result = runner.invoke(score_chat, [
            'message',
            '--score', 'test-score',
            '--message', 'Hello, world!'
        ])
        
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()
    
    def test_message_command_missing_score(self, runner, mock_celery_functions):
        """Test message command fails without required score parameter"""
        result = runner.invoke(score_chat, [
            'message',
            '--scorecard', 'test-scorecard',
            '--message', 'Hello, world!'
        ])
        
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()
    
    def test_message_command_missing_message(self, runner, mock_celery_functions):
        """Test message command fails without required message parameter"""
        result = runner.invoke(score_chat, [
            'message',
            '--scorecard', 'test-scorecard',
            '--score', 'test-score'
        ])
        
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()
    
    def test_message_command_json_output(self, runner, mock_celery_functions):
        """Test that message command outputs valid JSON"""
        expected_result = {
            'success': True,
            'response': 'Test response',
            'metadata': {'tokens': 150}
        }
        mock_celery_functions['generate_chat_id'].return_value = 'chat-123'
        mock_celery_functions['process_chat_message'].return_value = expected_result
        
        result = runner.invoke(score_chat, [
            'message',
            '--scorecard', 'test-scorecard',
            '--score', 'test-score',
            '--message', 'Hello, world!'
        ])
        
        assert result.exit_code == 0
        
        # Extract JSON from output (skip the "Generated chat ID" line)
        output_lines = result.output.strip().split('\n')
        json_output = '\n'.join(output_lines[1:])  # Skip first line with chat ID
        
        try:
            parsed_json = json.loads(json_output)
            assert parsed_json == expected_result
        except json.JSONDecodeError:
            pytest.fail(f"Output is not valid JSON: {json_output}")


class TestEndCommand:
    """Test the end subcommand"""
    
    def test_end_command_success(self, runner, mock_celery_functions):
        """Test end command with valid chat ID"""
        mock_celery_functions['end_chat_session'].return_value = {
            'success': True,
            'message': 'Chat session ended'
        }
        
        result = runner.invoke(score_chat, [
            'end',
            '--chat-id', 'chat-123'
        ])
        
        assert result.exit_code == 0
        assert '"success": true' in result.output
        assert '"message": "Chat session ended"' in result.output
        
        mock_celery_functions['end_chat_session'].assert_called_once_with(
            chat_id='chat-123'
        )
    
    def test_end_command_missing_chat_id(self, runner, mock_celery_functions):
        """Test end command fails without required chat-id parameter"""
        result = runner.invoke(score_chat, ['end'])
        
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()
    
    def test_end_command_json_output(self, runner, mock_celery_functions):
        """Test that end command outputs valid JSON"""
        expected_result = {
            'success': False,
            'error': 'Chat session not found'
        }
        mock_celery_functions['end_chat_session'].return_value = expected_result
        
        result = runner.invoke(score_chat, [
            'end',
            '--chat-id', 'nonexistent-chat'
        ])
        
        assert result.exit_code == 0
        
        try:
            parsed_json = json.loads(result.output.strip())
            assert parsed_json == expected_result
        except json.JSONDecodeError:
            pytest.fail(f"Output is not valid JSON: {result.output}")


class TestRegisterTasks:
    """Test the register_tasks function"""
    
    def test_register_tasks_function(self):
        """Test that register_tasks properly registers Celery tasks"""
        mock_app = Mock()
        mock_app.task.return_value = lambda func: func  # Mock decorator
        
        with patch('plexus.cli.score_chat.chat.process_chat_message') as mock_process, \
             patch('plexus.cli.score_chat.chat.end_chat_session') as mock_end:
            
            # Set up mock function names to match the actual Celery task names
            mock_process.name = 'plexus.score_chat.message'
            mock_end.name = 'plexus.score_chat.end_session'
            
            result = register_tasks(mock_app)
            
            # Verify the function returns the app
            assert result == mock_app
            
            # Verify tasks were registered (called twice, once for each task)
            assert mock_app.task.call_count == 2
            
            # Check that the app.task decorator was called with the correct name keyword arguments
            call_args_list = mock_app.task.call_args_list
            
            # Extract the 'name' keyword arguments from the calls
            names_called = []
            for call in call_args_list:
                args, kwargs = call
                if 'name' in kwargs:
                    names_called.append(kwargs['name'])
            
            assert 'plexus.score_chat.message' in names_called
            assert 'plexus.score_chat.end_session' in names_called


class TestIntegration:
    """Integration tests combining multiple commands"""
    
    def test_message_and_end_workflow(self, runner, mock_celery_functions):
        """Test a typical workflow: send message then end session"""
        # Setup mocks
        chat_id = 'workflow-test-123'
        mock_celery_functions['generate_chat_id'].return_value = chat_id
        mock_celery_functions['process_chat_message'].return_value = {
            'success': True,
            'response': 'Hello there!'
        }
        mock_celery_functions['end_chat_session'].return_value = {
            'success': True,
            'message': 'Session ended'
        }
        
        # Send message
        message_result = runner.invoke(score_chat, [
            'message',
            '--scorecard', 'test-scorecard',
            '--score', 'test-score',
            '--message', 'Test workflow'
        ])
        
        assert message_result.exit_code == 0
        assert f'Generated chat ID: {chat_id}' in message_result.output
        
        # End session  
        end_result = runner.invoke(score_chat, [
            'end',
            '--chat-id', chat_id
        ])
        
        assert end_result.exit_code == 0
        assert '"success": true' in end_result.output
        
        # Verify all functions were called correctly
        mock_celery_functions['generate_chat_id'].assert_called_once()
        mock_celery_functions['process_chat_message'].assert_called_once()
        mock_celery_functions['end_chat_session'].assert_called_once_with(chat_id=chat_id)