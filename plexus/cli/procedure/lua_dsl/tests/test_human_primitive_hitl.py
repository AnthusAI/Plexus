"""
Tests for HumanPrimitive with ExecutionContext integration.

Tests blocking HITL operations (approve, input, review).
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch
from plexus.cli.procedure.lua_dsl.primitives.human import HumanPrimitive
from plexus.cli.procedure.lua_dsl.execution_context import (
    ProcedureWaitingForHuman,
    HumanResponse
)


class TestHumanPrimitiveWithExecutionContext:
    """Test HumanPrimitive blocking HITL operations."""

    @pytest.fixture
    def mock_execution_context(self):
        """Create mock execution context."""
        context = Mock()
        context.wait_for_human = Mock()
        return context

    @pytest.fixture
    def mock_chat_recorder(self):
        """Create mock chat recorder."""
        recorder = Mock()
        recorder.session_id = 'session-123'
        return recorder

    @pytest.fixture
    def human_primitive(self, mock_chat_recorder, mock_execution_context):
        """Create HumanPrimitive for testing."""
        return HumanPrimitive(
            chat_recorder=mock_chat_recorder,
            execution_context=mock_execution_context,
            hitl_config={}
        )

    def test_approve_delegates_to_execution_context(
        self, human_primitive, mock_execution_context
    ):
        """Test that Human.approve() delegates to execution context."""
        # Mock response
        mock_execution_context.wait_for_human.return_value = HumanResponse(
            value=True,
            responded_at='2024-01-01T00:00:00Z'
        )

        result = human_primitive.approve({
            'message': 'Approve deployment?',
            'timeout': 3600,
            'default': False
        })

        # Should delegate to context
        mock_execution_context.wait_for_human.assert_called_once()
        call_args = mock_execution_context.wait_for_human.call_args[1]

        assert call_args['request_type'] == 'approval'
        assert call_args['message'] == 'Approve deployment?'
        assert call_args['timeout_seconds'] == 3600
        assert call_args['default_value'] is False
        assert call_args['options'] is None

        # Should return the value from response
        assert result is True

    def test_approve_raises_exception_when_context_does(
        self, human_primitive, mock_execution_context
    ):
        """Test that approve() propagates ProcedureWaitingForHuman."""
        # Mock context raising exception (first time, no response yet)
        mock_execution_context.wait_for_human.side_effect = ProcedureWaitingForHuman(
            procedure_id='proc-123',
            pending_message_id='msg-456'
        )

        # Should propagate exception
        with pytest.raises(ProcedureWaitingForHuman) as exc_info:
            human_primitive.approve({'message': 'Approve?'})

        assert exc_info.value.procedure_id == 'proc-123'
        assert exc_info.value.pending_message_id == 'msg-456'

    def test_approve_with_context_metadata(
        self, human_primitive, mock_execution_context
    ):
        """Test that approve() passes context metadata."""
        mock_execution_context.wait_for_human.return_value = HumanResponse(
            value=True,
            responded_at='2024-01-01T00:00:00Z'
        )

        human_primitive.approve({
            'message': 'Deploy?',
            'context': {
                'environment': 'production',
                'version': 'v2.1.0'
            }
        })

        call_args = mock_execution_context.wait_for_human.call_args[1]
        assert call_args['metadata'] == {
            'environment': 'production',
            'version': 'v2.1.0'
        }

    def test_input_delegates_to_execution_context(
        self, human_primitive, mock_execution_context
    ):
        """Test that Human.input() delegates to execution context."""
        mock_execution_context.wait_for_human.return_value = HumanResponse(
            value='User input text',
            responded_at='2024-01-01T00:00:00Z'
        )

        result = human_primitive.input({
            'message': 'Enter your name:',
            'placeholder': 'Name...',
            'timeout': 1800,
            'default': 'Anonymous'
        })

        # Should delegate
        mock_execution_context.wait_for_human.assert_called_once()
        call_args = mock_execution_context.wait_for_human.call_args[1]

        assert call_args['request_type'] == 'input'
        assert call_args['message'] == 'Enter your name:'
        assert call_args['timeout_seconds'] == 1800
        assert call_args['default_value'] == 'Anonymous'
        assert call_args['metadata'] == {'placeholder': 'Name...'}

        # Should return value
        assert result == 'User input text'

    def test_input_raises_exception_when_waiting(
        self, human_primitive, mock_execution_context
    ):
        """Test that input() propagates ProcedureWaitingForHuman."""
        mock_execution_context.wait_for_human.side_effect = ProcedureWaitingForHuman(
            procedure_id='proc-123',
            pending_message_id='msg-789'
        )

        with pytest.raises(ProcedureWaitingForHuman):
            human_primitive.input({'message': 'Enter text:'})

    def test_review_delegates_with_formatted_options(
        self, human_primitive, mock_execution_context
    ):
        """Test that Human.review() formats options correctly."""
        mock_execution_context.wait_for_human.return_value = HumanResponse(
            value={
                'decision': 'Approve',
                'feedback': 'Looks good',
                'edited_artifact': None,
                'responded_at': '2024-01-01T00:00:00Z'
            },
            responded_at='2024-01-01T00:00:00Z'
        )

        result = human_primitive.review({
            'message': 'Review this document',
            'artifact': 'Document content...',
            'artifact_type': 'document',
            'options': ['approve', 'edit', 'reject'],
            'timeout': 86400
        })

        # Should delegate
        mock_execution_context.wait_for_human.assert_called_once()
        call_args = mock_execution_context.wait_for_human.call_args[1]

        assert call_args['request_type'] == 'review'
        assert call_args['message'] == 'Review this document'

        # Should format options
        options = call_args['options']
        assert len(options) == 3
        assert options[0] == {'label': 'Approve', 'type': 'action'}
        assert options[1] == {'label': 'Edit', 'type': 'action'}
        assert options[2] == {'label': 'Reject', 'type': 'action'}

        # Should include artifact in metadata
        assert call_args['metadata']['artifact'] == 'Document content...'
        assert call_args['metadata']['artifact_type'] == 'document'

        # Should return review response
        assert result['decision'] == 'Approve'
        assert result['feedback'] == 'Looks good'

    def test_review_with_dict_options(
        self, human_primitive, mock_execution_context
    ):
        """Test review() with pre-formatted dict options."""
        mock_execution_context.wait_for_human.return_value = HumanResponse(
            value={'decision': 'Revise'},
            responded_at='2024-01-01T00:00:00Z'
        )

        human_primitive.review({
            'message': 'Review',
            'artifact': 'content',
            'options': [
                {'label': 'Approve', 'type': 'action'},
                {'label': 'Reject', 'type': 'cancel'},
                {'label': 'Revise', 'type': 'action'}
            ]
        })

        call_args = mock_execution_context.wait_for_human.call_args[1]
        options = call_args['options']

        # Should preserve pre-formatted options
        assert options[0] == {'label': 'Approve', 'type': 'action'}
        assert options[1] == {'label': 'Reject', 'type': 'cancel'}
        assert options[2] == {'label': 'Revise', 'type': 'action'}

    def test_review_raises_exception_when_waiting(
        self, human_primitive, mock_execution_context
    ):
        """Test that review() propagates ProcedureWaitingForHuman."""
        mock_execution_context.wait_for_human.side_effect = ProcedureWaitingForHuman(
            procedure_id='proc-123',
            pending_message_id='msg-999'
        )

        with pytest.raises(ProcedureWaitingForHuman):
            human_primitive.review({
                'message': 'Review',
                'artifact': 'content'
            })

    def test_approve_with_config_key(
        self, mock_chat_recorder, mock_execution_context
    ):
        """Test approve() using declared HITL config."""
        hitl_config = {
            'confirm_deployment': {
                'type': 'approval',
                'message': 'Deploy to production?',
                'timeout': 3600,
                'default': False
            }
        }

        human = HumanPrimitive(
            chat_recorder=mock_chat_recorder,
            execution_context=mock_execution_context,
            hitl_config=hitl_config
        )

        mock_execution_context.wait_for_human.return_value = HumanResponse(
            value=True,
            responded_at='2024-01-01T00:00:00Z'
        )

        # Use config key
        result = human.approve({'config_key': 'confirm_deployment'})

        # Should use config values
        call_args = mock_execution_context.wait_for_human.call_args[1]
        assert call_args['message'] == 'Deploy to production?'
        assert call_args['timeout_seconds'] == 3600
        assert call_args['default_value'] is False

        assert result is True

    def test_approve_config_override(
        self, mock_chat_recorder, mock_execution_context
    ):
        """Test that runtime options override config."""
        hitl_config = {
            'ask': {
                'message': 'Config message',
                'timeout': 1800
            }
        }

        human = HumanPrimitive(
            chat_recorder=mock_chat_recorder,
            execution_context=mock_execution_context,
            hitl_config=hitl_config
        )

        mock_execution_context.wait_for_human.return_value = HumanResponse(
            value=True,
            responded_at='2024-01-01T00:00:00Z'
        )

        # Override config
        human.approve({
            'config_key': 'ask',
            'message': 'Runtime message',  # Override
            'timeout': 3600  # Override
        })

        call_args = mock_execution_context.wait_for_human.call_args[1]
        # Runtime values should win
        assert call_args['message'] == 'Runtime message'
        assert call_args['timeout_seconds'] == 3600

    def test_notify_does_not_block(
        self, human_primitive, mock_execution_context
    ):
        """Test that Human.notify() does NOT use execution context."""
        # Notify should queue message, not block
        human_primitive.notify({
            'message': 'Processing complete',
            'level': 'info'
        })

        # Should NOT call execution context
        mock_execution_context.wait_for_human.assert_not_called()

        # Should queue message
        assert len(human_primitive._message_queue) == 1
        msg = human_primitive._message_queue[0]
        assert msg['content'] == 'Processing complete'
        assert msg['human_interaction'] == 'NOTIFICATION'


class TestHumanPrimitiveLuaConversion:
    """Test Lua table to Python dict conversion."""

    @pytest.fixture
    def human_primitive(self):
        """Create HumanPrimitive for testing."""
        mock_recorder = Mock()
        mock_recorder.session_id = 'session-123'
        mock_context = Mock()
        mock_context.wait_for_human.return_value = HumanResponse(
            value=True,
            responded_at='2024-01-01T00:00:00Z'
        )
        return HumanPrimitive(mock_recorder, mock_context, {})

    def test_approve_converts_lua_table_to_dict(self, human_primitive):
        """Test that Lua tables are converted to dicts."""
        # Mock Lua table (has items() but isn't a dict)
        class LuaTable:
            def items(self):
                return [('message', 'Test'), ('timeout', 3600)]

        lua_options = LuaTable()

        result = human_primitive.approve(lua_options)

        # Should convert and process
        assert result is True

    def test_input_converts_lua_table(self, human_primitive):
        """Test input() with Lua table."""
        class LuaTable:
            def items(self):
                return [('message', 'Enter:'), ('default', 'test')]

        human_primitive.execution_context.wait_for_human.return_value = HumanResponse(
            value='input',
            responded_at='2024-01-01T00:00:00Z'
        )

        result = human_primitive.input(LuaTable())

        assert result == 'input'


class TestHumanEscalate:
    """Test Human.escalate() functionality."""

    @pytest.fixture
    def mock_execution_context(self):
        """Create mock execution context."""
        context = Mock()
        context.wait_for_human = Mock()
        return context

    @pytest.fixture
    def mock_chat_recorder(self):
        """Create mock chat recorder."""
        recorder = Mock()
        recorder.session_id = 'session-123'
        return recorder

    @pytest.fixture
    def human_primitive(self, mock_chat_recorder, mock_execution_context):
        """Create HumanPrimitive for testing."""
        return HumanPrimitive(
            chat_recorder=mock_chat_recorder,
            execution_context=mock_execution_context,
            hitl_config={}
        )

    def test_escalate_delegates_to_execution_context(
        self, human_primitive, mock_execution_context
    ):
        """Test that Human.escalate() delegates to execution context."""
        # Mock response (escalation resolved)
        mock_execution_context.wait_for_human.return_value = None

        human_primitive.escalate({
            'message': 'Cannot resolve automatically',
            'context': {'attempts': 3, 'error': 'timeout'},
            'severity': 'error'
        })

        # Should delegate to context
        mock_execution_context.wait_for_human.assert_called_once()
        call_args = mock_execution_context.wait_for_human.call_args[1]

        assert call_args['request_type'] == 'escalation'
        assert call_args['message'] == 'Cannot resolve automatically'
        assert call_args['timeout_seconds'] is None  # No timeout
        assert call_args['default_value'] is None  # No default
        assert call_args['options'] is None
        assert call_args['metadata']['severity'] == 'error'
        assert call_args['metadata']['context'] == {'attempts': 3, 'error': 'timeout'}

    def test_escalate_no_timeout(
        self, human_primitive, mock_execution_context
    ):
        """Test that escalate() has no timeout (blocks indefinitely)."""
        mock_execution_context.wait_for_human.return_value = None

        human_primitive.escalate({
            'message': 'Need human intervention'
        })

        call_args = mock_execution_context.wait_for_human.call_args[1]
        # No timeout - blocks until human resolves
        assert call_args['timeout_seconds'] is None
        assert call_args['default_value'] is None

    def test_escalate_raises_exception_when_waiting(
        self, human_primitive, mock_execution_context
    ):
        """Test that escalate() propagates ProcedureWaitingForHuman."""
        mock_execution_context.wait_for_human.side_effect = ProcedureWaitingForHuman(
            procedure_id='proc-123',
            pending_message_id='msg-escalate'
        )

        with pytest.raises(ProcedureWaitingForHuman) as exc_info:
            human_primitive.escalate({'message': 'Critical error'})

        assert exc_info.value.procedure_id == 'proc-123'
        assert exc_info.value.pending_message_id == 'msg-escalate'

    def test_escalate_with_default_severity(
        self, human_primitive, mock_execution_context
    ):
        """Test escalate() defaults severity to 'error'."""
        mock_execution_context.wait_for_human.return_value = None

        human_primitive.escalate({
            'message': 'Problem occurred'
        })

        call_args = mock_execution_context.wait_for_human.call_args[1]
        assert call_args['metadata']['severity'] == 'error'

    def test_escalate_converts_lua_table(self, human_primitive, mock_execution_context):
        """Test that escalate() converts Lua tables to dicts."""
        # Mock Lua table
        class LuaTable:
            def items(self):
                return [
                    ('message', 'Lua escalation'),
                    ('severity', 'critical'),
                    ('context', {'key': 'value'})
                ]

        mock_execution_context.wait_for_human.return_value = None

        human_primitive.escalate(LuaTable())

        call_args = mock_execution_context.wait_for_human.call_args[1]
        assert call_args['message'] == 'Lua escalation'
        assert call_args['metadata']['severity'] == 'critical'
        assert call_args['metadata']['context'] == {'key': 'value'}

    def test_escalate_with_config_key(
        self, mock_chat_recorder, mock_execution_context
    ):
        """Test escalate() using declared HITL config."""
        hitl_config = {
            'critical_error': {
                'message': 'Critical system error',
                'severity': 'critical',
                'context': {'system': 'payment'}
            }
        }

        human = HumanPrimitive(
            chat_recorder=mock_chat_recorder,
            execution_context=mock_execution_context,
            hitl_config=hitl_config
        )

        mock_execution_context.wait_for_human.return_value = None

        # Use config key
        human.escalate({'config_key': 'critical_error'})

        # Should use config values
        call_args = mock_execution_context.wait_for_human.call_args[1]
        assert call_args['message'] == 'Critical system error'
        assert call_args['metadata']['severity'] == 'critical'
        assert call_args['metadata']['context'] == {'system': 'payment'}


class TestSystemAlert:
    """Test System.alert() functionality."""

    @pytest.fixture
    def mock_chat_recorder(self):
        """Create mock chat recorder."""
        recorder = Mock()
        recorder.session_id = 'session-123'
        return recorder

    @pytest.fixture
    def system_primitive(self, mock_chat_recorder):
        """Create SystemPrimitive for testing."""
        from plexus.cli.procedure.lua_dsl.primitives.system import SystemPrimitive
        return SystemPrimitive(chat_recorder=mock_chat_recorder)

    def test_alert_queues_message(self, system_primitive):
        """Test that System.alert() queues a message."""
        system_primitive.alert({
            'message': 'Test alert',
            'level': 'info',
            'source': 'test_system'
        })

        assert len(system_primitive._message_queue) == 1
        msg = system_primitive._message_queue[0]
        assert msg['role'] == 'SYSTEM'
        assert msg['content'] == 'Test alert'
        assert msg['message_type'] == 'MESSAGE'
        assert msg['human_interaction'] == 'ALERT_INFO'

    def test_alert_level_info(self, system_primitive):
        """Test System.alert() with info level."""
        system_primitive.alert({
            'message': 'Info message',
            'level': 'info'
        })

        msg = system_primitive._message_queue[0]
        assert msg['human_interaction'] == 'ALERT_INFO'

    def test_alert_level_warning(self, system_primitive):
        """Test System.alert() with warning level."""
        system_primitive.alert({
            'message': 'Warning message',
            'level': 'warning'
        })

        msg = system_primitive._message_queue[0]
        assert msg['human_interaction'] == 'ALERT_WARNING'

    def test_alert_level_error(self, system_primitive):
        """Test System.alert() with error level."""
        system_primitive.alert({
            'message': 'Error message',
            'level': 'error'
        })

        msg = system_primitive._message_queue[0]
        assert msg['human_interaction'] == 'ALERT_ERROR'

    def test_alert_level_critical(self, system_primitive):
        """Test System.alert() with critical level."""
        system_primitive.alert({
            'message': 'Critical message',
            'level': 'critical'
        })

        msg = system_primitive._message_queue[0]
        assert msg['human_interaction'] == 'ALERT_CRITICAL'

    def test_alert_default_level(self, system_primitive):
        """Test System.alert() defaults to info level."""
        system_primitive.alert({
            'message': 'Default level alert'
        })

        msg = system_primitive._message_queue[0]
        assert msg['human_interaction'] == 'ALERT_INFO'

    def test_alert_non_blocking(self, system_primitive):
        """Test that System.alert() does not block."""
        # Should return immediately without waiting
        system_primitive.alert({
            'message': 'Non-blocking alert',
            'level': 'warning'
        })

        # Message should be queued, not sent immediately
        assert len(system_primitive._message_queue) == 1

    def test_alert_converts_lua_table(self, system_primitive):
        """Test that System.alert() converts Lua tables to dicts."""
        # Mock Lua table
        class LuaTable:
            def items(self):
                return [
                    ('message', 'Lua alert'),
                    ('level', 'error'),
                    ('source', 'lua_script')
                ]

        system_primitive.alert(LuaTable())

        msg = system_primitive._message_queue[0]
        assert msg['content'] == 'Lua alert'
        assert msg['human_interaction'] == 'ALERT_ERROR'

    def test_alert_multiple_calls(self, system_primitive):
        """Test System.alert() can be called multiple times."""
        system_primitive.alert({'message': 'Alert 1', 'level': 'info'})
        system_primitive.alert({'message': 'Alert 2', 'level': 'warning'})
        system_primitive.alert({'message': 'Alert 3', 'level': 'error'})

        assert len(system_primitive._message_queue) == 3
        assert system_primitive._message_queue[0]['human_interaction'] == 'ALERT_INFO'
        assert system_primitive._message_queue[1]['human_interaction'] == 'ALERT_WARNING'
        assert system_primitive._message_queue[2]['human_interaction'] == 'ALERT_ERROR'

    @pytest.mark.asyncio
    async def test_alert_flush_recordings(self, system_primitive, mock_chat_recorder):
        """Test that queued alerts are flushed to chat recorder."""
        # Queue some alerts
        system_primitive.alert({'message': 'Alert 1', 'level': 'info'})
        system_primitive.alert({'message': 'Alert 2', 'level': 'warning'})

        # Mock async record_message
        mock_chat_recorder.record_message = Mock(return_value=asyncio.Future())
        mock_chat_recorder.record_message.return_value.set_result('msg-id')

        # Flush recordings
        await system_primitive.flush_recordings()

        # Should have called record_message twice
        assert mock_chat_recorder.record_message.call_count == 2
        # Queue should be cleared
        assert len(system_primitive._message_queue) == 0
