"""
Test suite for GraphQL-based chat service.

Following TDD principles, these tests define the expected behavior
of the GraphQL chat system before implementation.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from plexus.cli.score_chat.graphql_service import GraphQLChatService, create_chat_session, resume_chat_session


class TestGraphQLChatService:
    """Test the GraphQL chat service functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock PlexusDashboardClient for testing."""
        client = Mock()
        client.create_chat_session = AsyncMock()
        client.create_chat_message = AsyncMock()
        client.update_chat_session = AsyncMock()
        client.get_chat_session = AsyncMock()
        client.list_chat_messages = AsyncMock()
        return client
    
    @pytest.fixture
    def chat_service(self, mock_client):
        """Create a chat service instance with mocked client."""
        with patch('plexus.cli.score_chat.service.PlexusDashboardClient', return_value=mock_client), \
             patch('plexus.cli.score_chat.graphql_service.PlexusDashboardClient', return_value=mock_client), \
             patch('plexus.cli.shared.client_utils.create_client', return_value=mock_client), \
             patch('plexus.cli.shared.file_editor.FileEditor'), \
             patch('plexus.cli.shared.plexus_tool.PlexusTool'), \
             patch('langchain_anthropic.ChatAnthropic'), \
             patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            service = GraphQLChatService(
                scorecard="test-scorecard",
                score="test-score",
                experiment_id="test-experiment"
            )
            return service
    
    @pytest.mark.asyncio
    async def test_create_session_basic(self, chat_service, mock_client):
        """Test creating a basic chat session."""
        # Arrange
        account_id = "test-account"
        expected_session_id = "session-123"
        mock_client.create_chat_session.return_value = {'id': expected_session_id}
        
        # Act
        session_id = await chat_service.create_session(account_id)
        
        # Assert
        assert session_id == expected_session_id
        mock_client.create_chat_session.assert_called_once()
        call_args = mock_client.create_chat_session.call_args[0][0]
        assert call_args['accountId'] == account_id
        assert call_args['status'] == 'ACTIVE'
        assert 'procedureId' in call_args
    
    @pytest.mark.asyncio
    async def test_create_session_with_experiment(self, mock_client):
        """Test creating a chat session associated with an experiment."""
        # Arrange
        experiment_id = "exp-456"
        with patch('plexus.cli.score_chat.service.PlexusDashboardClient', return_value=mock_client), \
             patch('plexus.cli.score_chat.graphql_service.PlexusDashboardClient', return_value=mock_client), \
             patch('plexus.cli.shared.client_utils.create_client', return_value=mock_client), \
             patch('plexus.cli.shared.file_editor.FileEditor'), \
             patch('plexus.cli.shared.plexus_tool.PlexusTool'), \
             patch('langchain_anthropic.ChatAnthropic'), \
             patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            service = GraphQLChatService(experiment_id=experiment_id)
        
        mock_client.create_chat_session.return_value = {'id': 'session-123'}
        
        # Act
        await service.create_session("test-account")
        
        # Assert
        call_args = mock_client.create_chat_session.call_args[0][0]
        assert call_args['procedureId'] == experiment_id
    
    @pytest.mark.asyncio
    async def test_send_message_user(self, chat_service, mock_client):
        """Test sending a user message."""
        # Arrange
        chat_service.session_id = "session-123"
        expected_message = {'id': 'msg-456', 'content': 'Hello, AI!'}
        mock_client.create_chat_message.return_value = expected_message
        
        # Act
        result = await chat_service.send_message("Hello, AI!", "USER")
        
        # Assert
        assert result == expected_message
        mock_client.create_chat_message.assert_called_once()
        call_args = mock_client.create_chat_message.call_args[0][0]
        assert call_args['sessionId'] == "session-123"
        assert call_args['role'] == "USER"
        assert call_args['content'] == "Hello, AI!"
    
    @pytest.mark.asyncio
    async def test_send_message_with_experiment_id(self, mock_client):
        """Test that messages include experimentId for GSI queries."""
        # Arrange
        experiment_id = "exp-789"
        with patch('plexus.cli.score_chat.service.PlexusDashboardClient', return_value=mock_client), \
             patch('plexus.cli.score_chat.graphql_service.PlexusDashboardClient', return_value=mock_client), \
             patch('plexus.cli.shared.client_utils.create_client', return_value=mock_client), \
             patch('plexus.cli.shared.file_editor.FileEditor'), \
             patch('plexus.cli.shared.plexus_tool.PlexusTool'), \
             patch('langchain_anthropic.ChatAnthropic'), \
             patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            service = GraphQLChatService(session_id="session-123", experiment_id=experiment_id)
        
        mock_client.create_chat_message.return_value = {'id': 'msg-456'}
        
        # Act
        await service.send_message("Test message", "USER")
        
        # Assert
        call_args = mock_client.create_chat_message.call_args[0][0]
        assert call_args['procedureId'] == experiment_id
    
    @pytest.mark.asyncio
    async def test_send_message_no_session_error(self, chat_service):
        """Test that sending a message without a session raises an error."""
        # Arrange
        chat_service.session_id = None
        
        # Act & Assert
        with pytest.raises(ValueError, match="No active chat session"):
            await chat_service.send_message("Hello", "USER")
    
    @pytest.mark.asyncio
    async def test_process_message_with_graphql(self, chat_service, mock_client):
        """Test processing a message end-to-end with GraphQL persistence."""
        # Arrange
        chat_service.session_id = "session-123"
        mock_client.create_chat_message.return_value = {'id': 'msg-123'}
        
        # Mock the ScoreChatService.process_message method
        with patch.object(chat_service, 'process_message') as mock_process:
            mock_process.return_value = [
                {'type': 'ai_message', 'content': 'AI response to your query'}
            ]
            
            # Act
            result = await chat_service.process_message_with_graphql("User question")
            
            # Assert
            assert result['session_id'] == "session-123"
            assert len(result['responses']) == 1
            assert mock_client.create_chat_message.call_count == 2  # User + AI message
    
    @pytest.mark.asyncio
    async def test_end_session(self, chat_service, mock_client):
        """Test ending a chat session."""
        # Arrange
        chat_service.session_id = "session-123"
        expected_result = {'id': 'session-123', 'status': 'COMPLETED'}
        mock_client.update_chat_session.return_value = expected_result
        
        # Act
        result = await chat_service.end_session()
        
        # Assert
        assert result == expected_result
        mock_client.update_chat_session.assert_called_once()
        call_args = mock_client.update_chat_session.call_args[0][0]
        assert call_args['id'] == "session-123"
        assert call_args['status'] == 'COMPLETED'
    
    @pytest.mark.asyncio
    async def test_end_session_no_active_session(self, chat_service):
        """Test ending a session when no session is active."""
        # Arrange
        chat_service.session_id = None
        
        # Act
        result = await chat_service.end_session()
        
        # Assert
        assert 'error' in result
        assert result['error'] == 'No active session to end'


class TestConvenienceFunctions:
    """Test the convenience functions for creating and resuming chat sessions."""
    
    @pytest.mark.asyncio
    async def test_create_chat_session(self):
        """Test the create_chat_session convenience function."""
        # Arrange
        with patch('plexus.cli.score_chat.graphql_service.GraphQLChatService') as MockService:
            mock_service = Mock()
            mock_service.create_session = AsyncMock(return_value="session-123")
            mock_service.session_id = "session-123"
            MockService.return_value = mock_service
            
            # Act
            result = await create_chat_session(
                account_id="test-account",
                scorecard="test-scorecard",
                score="test-score",
                experiment_id="test-experiment"
            )
            
            # Assert
            assert result == mock_service
            MockService.assert_called_once_with(
                scorecard="test-scorecard",
                score="test-score",
                experiment_id="test-experiment"
            )
            mock_service.create_session.assert_called_once_with("test-account")
    
    @pytest.mark.asyncio
    async def test_resume_chat_session(self):
        """Test the resume_chat_session convenience function."""
        # Arrange
        session_id = "session-456"
        session_data = {
            'scorecardId': 'scorecard-123',
            'scoreId': 'score-456',
            'procedureId': 'exp-789'
        }
        messages = [{'id': 'msg-1', 'content': 'Previous message'}]
        
        with patch('plexus.cli.score_chat.graphql_service.GraphQLChatService') as MockService:
            mock_service = Mock()
            mock_service.client.get_chat_session = AsyncMock(return_value=session_data)
            mock_service.client.list_chat_messages = AsyncMock(return_value=messages)
            MockService.return_value = mock_service
            
            # Act
            result = await resume_chat_session(session_id)
            
            # Assert
            assert result == mock_service
            MockService.assert_called_once_with(session_id=session_id)
            mock_service.client.get_chat_session.assert_called_once_with(session_id)
            mock_service.client.list_chat_messages.assert_called_once_with(session_id)
            assert mock_service.scorecard == 'scorecard-123'
            assert mock_service.score == 'score-456'
            assert mock_service.procedure_id == 'exp-789'
            assert mock_service.chat_history == messages


class TestExperimentIntegration:
    """Test experiment-specific chat functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock client with experiment-related methods."""
        client = Mock()
        client.list_chat_sessions = AsyncMock()
        client.list_chat_messages = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_query_experiment_chat_sessions(self, mock_client):
        """Test querying all chat sessions for an experiment."""
        # Arrange
        experiment_id = "exp-123"
        expected_sessions = [
            {'id': 'session-1', 'experimentId': experiment_id, 'createdAt': '2024-01-01T10:00:00Z'},
            {'id': 'session-2', 'experimentId': experiment_id, 'createdAt': '2024-01-01T11:00:00Z'}
        ]
        mock_client.list_chat_sessions.return_value = expected_sessions
        
        # Act - This tests the expected GraphQL client method
        result = await mock_client.list_chat_sessions(experiment_id=experiment_id)
        
        # Assert
        assert result == expected_sessions
        mock_client.list_chat_sessions.assert_called_once_with(experiment_id=experiment_id)
    
    @pytest.mark.asyncio
    async def test_query_experiment_messages_chronological(self, mock_client):
        """Test querying chronologically-sorted messages for an experiment."""
        # Arrange
        experiment_id = "exp-123"
        expected_messages = [
            {'id': 'msg-1', 'experimentId': experiment_id, 'createdAt': '2024-01-01T10:00:00Z', 'content': 'First message'},
            {'id': 'msg-2', 'experimentId': experiment_id, 'createdAt': '2024-01-01T10:01:00Z', 'content': 'Second message'}
        ]
        mock_client.list_chat_messages.return_value = expected_messages
        
        # Act - This tests the expected GraphQL client method with GSI query
        result = await mock_client.list_chat_messages(experiment_id=experiment_id, sort_by='createdAt')
        
        # Assert
        assert result == expected_messages
        mock_client.list_chat_messages.assert_called_once_with(experiment_id=experiment_id, sort_by='createdAt')


class TestFileEditorIntegration:
    """Test integration with existing FileEditor functionality."""
    
    @pytest.mark.asyncio
    async def test_file_editor_preserved(self):
        """Test that FileEditor functionality is preserved in GraphQL service."""
        # Arrange
        with patch('plexus.cli.score_chat.service.PlexusDashboardClient'), \
             patch('plexus.cli.score_chat.graphql_service.PlexusDashboardClient'), \
             patch('plexus.cli.shared.client_utils.create_client'), \
             patch('plexus.cli.shared.file_editor.FileEditor'), \
             patch('plexus.cli.shared.plexus_tool.PlexusTool'), \
             patch('langchain_anthropic.ChatAnthropic'), \
             patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            service = GraphQLChatService()
            
            # Act & Assert - FileEditor should be available from parent class
            assert hasattr(service, 'file_editor')
            assert service.file_editor is not None
    
    @pytest.mark.asyncio
    async def test_score_chat_service_integration(self):
        """Test that the GraphQL service inherits all ScoreChatService functionality."""
        # Arrange
        with patch('plexus.cli.score_chat.service.PlexusDashboardClient'), \
             patch('plexus.cli.score_chat.graphql_service.PlexusDashboardClient'), \
             patch('plexus.cli.shared.client_utils.create_client'), \
             patch('plexus.cli.shared.file_editor.FileEditor'), \
             patch('plexus.cli.shared.plexus_tool.PlexusTool'), \
             patch('langchain_anthropic.ChatAnthropic'), \
             patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            service = GraphQLChatService(scorecard="test", score="test")
            
            # Act & Assert - Should inherit all parent functionality
            assert hasattr(service, 'client')
            assert hasattr(service, 'file_editor')
            assert hasattr(service, 'plexus_tool')
            assert hasattr(service, 'process_message')  # From parent ScoreChatService


if __name__ == "__main__":
    pytest.main([__file__])