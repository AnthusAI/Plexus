"""
Tests for ExecutionContext and LocalExecutionContext.

Tests checkpoint storage, replay, and HITL blocking behavior.
"""

import pytest
import json
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from plexus.cli.procedure.lua_dsl.execution_context import (
    LocalExecutionContext,
    ProcedureWaitingForHuman,
    HumanResponse
)


class TestLocalExecutionContext:
    """Test LocalExecutionContext checkpoint and HITL operations."""

    @pytest.fixture
    def mock_graphql_service(self):
        """Create mock GraphQL service."""
        service = Mock()

        # Mock procedure query
        service.query.return_value = {
            'getProcedure': {
                'id': 'proc-123',
                'status': 'RUNNING',
                'metadata': json.dumps({
                    'checkpoints': {},
                    'state': {},
                    'lua_state': {}
                })
            }
        }

        return service

    @pytest.fixture
    def mock_chat_recorder(self):
        """Create mock chat recorder."""
        recorder = Mock()
        recorder.session_id = 'session-456'
        # record_message is async, so use AsyncMock
        recorder.record_message = AsyncMock(return_value='msg-789')
        return recorder

    @pytest.fixture
    def execution_context(self, mock_graphql_service, mock_chat_recorder):
        """Create LocalExecutionContext for testing."""
        return LocalExecutionContext(
            procedure_id='proc-123',
            session_id='session-456',
            graphql_service=mock_graphql_service,
            chat_recorder=mock_chat_recorder
        )

    def test_initialization_loads_procedure(self, mock_graphql_service, mock_chat_recorder):
        """Test that context loads procedure and metadata on init."""
        context = LocalExecutionContext(
            procedure_id='proc-123',
            session_id='session-456',
            graphql_service=mock_graphql_service,
            chat_recorder=mock_chat_recorder
        )

        # Should query procedure
        mock_graphql_service.query.assert_called_once()
        call_args = mock_graphql_service.query.call_args
        assert 'getProcedure' in call_args[0][0]
        # Check variables dict (second positional arg or 'variables' keyword arg)
        variables = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
        assert variables['id'] == 'proc-123'

        # Should load checkpoints from metadata
        assert context.checkpoints == {}
        assert context.procedure_id == 'proc-123'
        assert context.session_id == 'session-456'

    def test_step_run_executes_function_first_time(self, execution_context):
        """Test that step_run executes function on first call."""
        # Function to checkpoint
        mock_fn = Mock(return_value={'result': 'success'})

        # First execution
        result = execution_context.step_run('test_step', mock_fn)

        # Should execute function
        mock_fn.assert_called_once()
        assert result == {'result': 'success'}

        # Should save checkpoint
        assert 'test_step' in execution_context.checkpoints
        checkpoint = execution_context.checkpoints['test_step']
        assert checkpoint['result'] == {'result': 'success'}
        assert 'completed_at' in checkpoint

    def test_step_run_returns_cached_on_replay(self, execution_context):
        """Test that step_run returns cached result without re-executing."""
        # Setup existing checkpoint
        execution_context.checkpoints['test_step'] = {
            'result': {'cached': 'data'},
            'completed_at': datetime.now(timezone.utc).isoformat()
        }

        # Function that should NOT be called
        mock_fn = Mock(return_value={'new': 'data'})

        # Replay
        result = execution_context.step_run('test_step', mock_fn)

        # Should NOT execute function
        mock_fn.assert_not_called()

        # Should return cached result
        assert result == {'cached': 'data'}

    def test_step_run_saves_metadata_to_database(self, execution_context, mock_graphql_service):
        """Test that step_run persists checkpoint to database."""
        # Reset mock to clear init call
        mock_graphql_service.mutate.reset_mock()

        mock_fn = Mock(return_value='result')
        execution_context.step_run('test_step', mock_fn)

        # Should call mutate to save metadata
        mock_graphql_service.mutate.assert_called_once()
        call_args = mock_graphql_service.mutate.call_args

        assert 'updateProcedure' in call_args[0][0]
        # Get variables
        variables = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
        assert variables['id'] == 'proc-123'

        # Should include checkpoint in metadata
        metadata = json.loads(variables['metadata'])
        assert 'test_step' in metadata['checkpoints']

    def test_checkpoint_clear_all(self, execution_context, mock_graphql_service):
        """Test clearing all checkpoints."""
        # Setup some checkpoints
        execution_context.checkpoints = {
            'step1': {'result': 1, 'completed_at': '2024-01-01T00:00:00Z'},
            'step2': {'result': 2, 'completed_at': '2024-01-01T00:01:00Z'}
        }
        execution_context.metadata['state'] = {'key': 'value'}

        mock_graphql_service.mutate.reset_mock()

        # Clear all
        execution_context.checkpoint_clear_all()

        # Should clear checkpoints and state
        assert execution_context.checkpoints == {}
        assert execution_context.metadata.get('state') == {}

        # Should save to database
        mock_graphql_service.mutate.assert_called_once()

    def test_checkpoint_clear_after(self, execution_context, mock_graphql_service):
        """Test partial checkpoint clearing."""
        # Setup checkpoints with timestamps
        execution_context.checkpoints = {
            'step1': {'result': 1, 'completed_at': '2024-01-01T00:00:00Z'},
            'step2': {'result': 2, 'completed_at': '2024-01-01T00:01:00Z'},
            'step3': {'result': 3, 'completed_at': '2024-01-01T00:02:00Z'}
        }

        mock_graphql_service.mutate.reset_mock()

        # Clear after step2
        execution_context.checkpoint_clear_after('step2')

        # Should keep only step1 (before step2)
        assert 'step1' in execution_context.checkpoints
        assert 'step2' not in execution_context.checkpoints
        assert 'step3' not in execution_context.checkpoints

        # Should save to database
        mock_graphql_service.mutate.assert_called_once()

    def test_checkpoint_exists(self, execution_context):
        """Test checking checkpoint existence."""
        execution_context.checkpoints = {
            'existing': {'result': 'data', 'completed_at': '2024-01-01T00:00:00Z'}
        }

        assert execution_context.checkpoint_exists('existing') is True
        assert execution_context.checkpoint_exists('missing') is False

    def test_checkpoint_get(self, execution_context):
        """Test getting checkpoint value."""
        execution_context.checkpoints = {
            'step1': {'result': {'data': 'value'}, 'completed_at': '2024-01-01T00:00:00Z'}
        }

        # Existing checkpoint
        result = execution_context.checkpoint_get('step1')
        assert result == {'data': 'value'}

        # Missing checkpoint
        result = execution_context.checkpoint_get('missing')
        assert result is None

    def test_wait_for_human_first_time_creates_pending_message(
        self, execution_context, mock_graphql_service, mock_chat_recorder
    ):
        """Test that wait_for_human creates PENDING message on first call."""
        # No existing pending messages
        mock_graphql_service.query.return_value = {
            'listChatMessages': {'items': []}
        }

        # Should raise exception to exit
        with pytest.raises(ProcedureWaitingForHuman) as exc_info:
            execution_context.wait_for_human(
                request_type='approval',
                message='Approve this?',
                timeout_seconds=3600,
                default_value=False,
                options=None,
                metadata={}
            )

        # Should create pending message
        mock_chat_recorder.record_message.assert_called_once()
        call_args = mock_chat_recorder.record_message.call_args[1]
        assert call_args['role'] == 'ASSISTANT'
        assert call_args['human_interaction'] == 'PENDING_APPROVAL'
        assert 'Approve this?' in call_args['content']

        # Should update procedure status
        mutate_calls = [call for call in mock_graphql_service.mutate.call_args_list
                       if 'updateProcedure' in call[0][0]]
        assert len(mutate_calls) > 0
        last_mutate = mutate_calls[-1]
        # Get variables from the call
        variables = last_mutate[0][1] if len(last_mutate[0]) > 1 else last_mutate[1]
        assert variables['status'] == 'WAITING_FOR_HUMAN'

        # Exception should have correct IDs
        assert exc_info.value.procedure_id == 'proc-123'
        assert exc_info.value.pending_message_id == 'msg-789'

    def test_wait_for_human_finds_response_and_continues(
        self, execution_context, mock_graphql_service
    ):
        """Test that wait_for_human returns response when found."""
        # Set up procedure as if it's resuming (has waitingOnMessageId)
        execution_context.procedure['waitingOnMessageId'] = 'pending-msg'

        # Mock finding response to the pending message
        mock_graphql_service.query.return_value = {
            'listChatMessageByParentMessageId': {
                'items': [{
                    'id': 'response-msg',
                    'content': json.dumps({'approved': True}),
                    'createdAt': '2024-01-01T00:05:00Z'
                }]
            }
        }

        # Should return response value
        response = execution_context.wait_for_human(
            request_type='approval',
            message='Approve this?',
            timeout_seconds=3600,
            default_value=False,
            options=None,
            metadata={}
        )

        # Should return HumanResponse with approval
        assert isinstance(response, HumanResponse)
        assert response.value is True
        assert response.responded_at == '2024-01-01T00:05:00Z'

    def test_wait_for_human_returns_default_on_timeout(
        self, execution_context, mock_graphql_service
    ):
        """Test that wait_for_human returns default when timed out."""
        # Set up procedure as if it's resuming (has waitingOnMessageId)
        execution_context.procedure['waitingOnMessageId'] = 'pending-msg'

        # Mock finding old pending message (old timestamp)
        old_time = '2020-01-01T00:00:00Z'
        mock_graphql_service.query.side_effect = [
            # First query: no response found (use GSI query name)
            {
                'listChatMessageByParentMessageId': {'items': []}
            },
            # Second query: get the pending message by ID to check timeout
            {
                'getChatMessage': {
                    'id': 'pending-msg',
                    'content': 'Approve?',
                    'metadata': '{}',
                    'createdAt': old_time
                }
            }
        ]

        # Should return default value
        response = execution_context.wait_for_human(
            request_type='approval',
            message='Approve this?',
            timeout_seconds=60,  # Short timeout
            default_value=False,
            options=None,
            metadata={}
        )

        # Should return default
        assert isinstance(response, HumanResponse)
        assert response.value is False

        # Should mark message as timed out
        mutate_calls = [call for call in mock_graphql_service.mutate.call_args_list
                       if 'updateChatMessage' in call[0][0]]
        assert len(mutate_calls) > 0

    def test_wait_for_human_with_input_type(
        self, execution_context, mock_graphql_service
    ):
        """Test wait_for_human with input request type."""
        # Set up procedure as if it's resuming (has waitingOnMessageId)
        execution_context.procedure['waitingOnMessageId'] = 'pending-msg'

        # Mock response with input text
        mock_graphql_service.query.return_value = {
            'listChatMessageByParentMessageId': {
                'items': [{
                    'id': 'response-msg',
                    'content': json.dumps({'input': 'User typed this'}),
                    'createdAt': '2024-01-01T00:05:00Z'
                }]
            }
        }

        response = execution_context.wait_for_human(
            request_type='input',
            message='Enter your name:',
            timeout_seconds=3600,
            default_value='',
            options=None,
            metadata={'placeholder': 'Name...'}
        )

        assert response.value == 'User typed this'

    def test_wait_for_human_with_review_type(
        self, execution_context, mock_graphql_service
    ):
        """Test wait_for_human with review request type."""
        # Set up procedure as if it's resuming (has waitingOnMessageId)
        execution_context.procedure['waitingOnMessageId'] = 'pending-msg'

        # Mock response with review decision
        mock_graphql_service.query.return_value = {
            'listChatMessageByParentMessageId': {
                'items': [{
                    'id': 'response-msg',
                    'content': json.dumps({
                        'decision': 'Approve',
                        'feedback': 'Looks good',
                        'edited_artifact': None
                    }),
                    'createdAt': '2024-01-01T00:05:00Z'
                }]
            }
        }

        response = execution_context.wait_for_human(
            request_type='review',
            message='Review this document',
            timeout_seconds=3600,
            default_value={'decision': 'reject'},
            options=[
                {'label': 'Approve', 'type': 'action'},
                {'label': 'Reject', 'type': 'cancel'}
            ],
            metadata={'artifact': 'document content'}
        )

        assert response.value['decision'] == 'Approve'
        assert response.value['feedback'] == 'Looks good'


class TestHumanResponse:
    """Test HumanResponse dataclass."""

    def test_human_response_creation(self):
        """Test creating HumanResponse."""
        response = HumanResponse(
            value=True,
            responded_at='2024-01-01T00:00:00Z'
        )

        assert response.value is True
        assert response.responded_at == '2024-01-01T00:00:00Z'

    def test_human_response_with_complex_value(self):
        """Test HumanResponse with complex value types."""
        # Test with dict value (review response)
        response = HumanResponse(
            value={'decision': 'Approve', 'feedback': 'Looks good'},
            responded_at='2024-01-01T00:00:00Z'
        )

        assert response.value['decision'] == 'Approve'
        assert response.value['feedback'] == 'Looks good'

        # Test with string value (input response)
        response2 = HumanResponse(
            value='user input text',
            responded_at='2024-01-01T00:00:00Z'
        )

        assert response2.value == 'user input text'


class TestProcedureWaitingForHuman:
    """Test ProcedureWaitingForHuman exception."""

    def test_exception_creation(self):
        """Test creating exception with procedure and message IDs."""
        exc = ProcedureWaitingForHuman(
            procedure_id='proc-123',
            pending_message_id='msg-456'
        )

        assert exc.procedure_id == 'proc-123'
        assert exc.pending_message_id == 'msg-456'
        assert 'proc-123' in str(exc)
        assert 'msg-456' in str(exc)
