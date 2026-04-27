"""
Tests for Session primitives.

Tests conversation history management including append, inject_system, clear,
history, load_from_node, and save_to_node operations.
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from plexus.cli.procedure.lua_dsl.primitives.session import SessionPrimitive


class TestSessionPrimitiveBasicOperations:
    """Test basic Session operations: append, inject_system, clear, history."""

    @pytest.fixture
    def mock_chat_recorder(self):
        """Create mock ProcedureChatRecorder."""
        recorder = Mock()
        recorder.session_id = 'session-123'
        recorder.record_message = Mock(return_value='msg-id-456')
        return recorder

    @pytest.fixture
    def mock_execution_context(self):
        """Create mock ExecutionContext."""
        context = Mock()
        context.procedure_id = 'proc-123'
        return context

    @pytest.fixture
    def mock_lua_sandbox(self):
        """Create mock LuaSandbox for Lua table creation."""
        sandbox = Mock()
        # Mock Lua table behavior
        lua_table = {}
        sandbox.lua.table = Mock(return_value=lua_table)
        return sandbox

    @pytest.fixture
    def session_primitive(self, mock_chat_recorder, mock_execution_context):
        """Create SessionPrimitive for testing."""
        return SessionPrimitive(
            chat_recorder=mock_chat_recorder,
            execution_context=mock_execution_context,
            lua_sandbox=None
        )

    @pytest.fixture
    def session_with_lua(self, mock_chat_recorder, mock_execution_context, mock_lua_sandbox):
        """Create SessionPrimitive with Lua sandbox for testing."""
        return SessionPrimitive(
            chat_recorder=mock_chat_recorder,
            execution_context=mock_execution_context,
            lua_sandbox=mock_lua_sandbox
        )

    def test_initialization(self, session_primitive, mock_chat_recorder, mock_execution_context):
        """Test that Session initializes correctly."""
        assert session_primitive.chat_recorder == mock_chat_recorder
        assert session_primitive.execution_context == mock_execution_context
        assert session_primitive._messages == []
        assert session_primitive.count() == 0

    def test_append_user_message(self, session_primitive):
        """Test appending a USER message to session."""
        session_primitive.append("USER", "What is the weather?")

        assert session_primitive.count() == 1
        messages = session_primitive._messages
        assert messages[0]['role'] == 'USER'
        assert messages[0]['content'] == "What is the weather?"
        assert messages[0]['message_type'] == 'MESSAGE'
        assert messages[0]['metadata'] == {}

    def test_append_assistant_message(self, session_primitive):
        """Test appending an ASSISTANT message to session."""
        session_primitive.append("ASSISTANT", "I need more information about location.")

        assert session_primitive.count() == 1
        messages = session_primitive._messages
        assert messages[0]['role'] == 'ASSISTANT'
        assert messages[0]['content'] == "I need more information about location."

    def test_append_system_message(self, session_primitive):
        """Test appending a SYSTEM message to session."""
        session_primitive.append("SYSTEM", "Focus on security implications")

        assert session_primitive.count() == 1
        messages = session_primitive._messages
        assert messages[0]['role'] == 'SYSTEM'
        assert messages[0]['content'] == "Focus on security implications"

    def test_append_normalizes_role_to_uppercase(self, session_primitive):
        """Test that roles are normalized to uppercase."""
        session_primitive.append("user", "test message")

        messages = session_primitive._messages
        assert messages[0]['role'] == 'USER'

    def test_append_with_metadata(self, session_primitive):
        """Test appending message with custom metadata."""
        metadata = {'tag': 'important', 'confidence': 0.95}
        session_primitive.append("USER", "Important question", metadata=metadata)

        messages = session_primitive._messages
        assert messages[0]['metadata'] == metadata

    def test_append_invalid_role_defaults_to_user(self, session_primitive):
        """Test that invalid role defaults to USER."""
        session_primitive.append("INVALID_ROLE", "test message")

        messages = session_primitive._messages
        assert messages[0]['role'] == 'USER'

    def test_inject_system(self, session_primitive):
        """Test inject_system convenience method."""
        session_primitive.inject_system("You are a helpful assistant")

        assert session_primitive.count() == 1
        messages = session_primitive._messages
        assert messages[0]['role'] == 'SYSTEM'
        assert messages[0]['content'] == "You are a helpful assistant"

    def test_clear(self, session_primitive):
        """Test clearing session history."""
        # Add some messages
        session_primitive.append("USER", "Message 1")
        session_primitive.append("ASSISTANT", "Message 2")
        session_primitive.append("USER", "Message 3")

        assert session_primitive.count() == 3

        # Clear
        session_primitive.clear()

        assert session_primitive.count() == 0
        assert session_primitive._messages == []

    def test_clear_empty_session(self, session_primitive):
        """Test clearing an already empty session."""
        assert session_primitive.count() == 0

        session_primitive.clear()

        assert session_primitive.count() == 0

    def test_count(self, session_primitive):
        """Test count method returns correct number of messages."""
        assert session_primitive.count() == 0

        session_primitive.append("USER", "Message 1")
        assert session_primitive.count() == 1

        session_primitive.append("ASSISTANT", "Message 2")
        assert session_primitive.count() == 2

        session_primitive.clear()
        assert session_primitive.count() == 0

    def test_history_without_lua_sandbox(self, session_primitive):
        """Test history() returns Python list when no Lua sandbox available."""
        session_primitive.append("USER", "Hello")
        session_primitive.append("ASSISTANT", "Hi there")

        history = session_primitive.history()

        # Should return list
        assert isinstance(history, list)
        assert len(history) == 2
        assert history[0]['role'] == 'USER'
        assert history[0]['content'] == 'Hello'
        assert history[1]['role'] == 'ASSISTANT'
        assert history[1]['content'] == 'Hi there'

    def test_history_with_lua_sandbox(self, session_with_lua, mock_lua_sandbox):
        """Test history() returns Lua table when sandbox available."""
        session_with_lua.append("USER", "Hello")
        session_with_lua.append("ASSISTANT", "Hi there")

        # Setup mock Lua table
        lua_table = {}
        mock_lua_sandbox.lua.table.return_value = lua_table

        history = session_with_lua.history()

        # Should create Lua table
        mock_lua_sandbox.lua.table.assert_called_once()
        assert history == lua_table

        # Verify 1-indexed Lua table
        assert 1 in lua_table
        assert 2 in lua_table
        assert lua_table[1]['role'] == 'USER'
        assert lua_table[2]['role'] == 'ASSISTANT'

    def test_history_returns_copies(self, session_primitive):
        """Test that history() returns copies, not references."""
        session_primitive.append("USER", "Original")

        history = session_primitive.history()
        history[0]['content'] = "Modified"

        # Original should be unchanged
        assert session_primitive._messages[0]['content'] == "Original"

    def test_multiple_operations_sequence(self, session_primitive):
        """Test sequence of multiple operations."""
        # Append messages
        session_primitive.append("USER", "Question 1")
        session_primitive.inject_system("Be concise")
        session_primitive.append("ASSISTANT", "Answer 1")

        assert session_primitive.count() == 3

        # Get history
        history = session_primitive.history()
        assert len(history) == 3
        assert history[1]['role'] == 'SYSTEM'

        # Clear and add new
        session_primitive.clear()
        session_primitive.append("USER", "Question 2")

        assert session_primitive.count() == 1
        assert session_primitive._messages[0]['content'] == "Question 2"


class TestSessionPrimitiveSave:
    """Test Session.save() for persisting to database."""

    @pytest.fixture
    def mock_chat_recorder(self):
        """Create mock ProcedureChatRecorder."""
        recorder = Mock()
        recorder.session_id = 'session-123'
        recorder.record_message = Mock(return_value='msg-id')
        return recorder

    @pytest.fixture
    def mock_execution_context(self):
        """Create mock ExecutionContext."""
        return Mock()

    @pytest.fixture
    def session_primitive(self, mock_chat_recorder, mock_execution_context):
        """Create SessionPrimitive for testing."""
        return SessionPrimitive(
            chat_recorder=mock_chat_recorder,
            execution_context=mock_execution_context,
            lua_sandbox=None
        )

    @pytest.mark.asyncio
    async def test_save_empty_session(self, session_primitive, mock_chat_recorder):
        """Test save with no messages does nothing."""
        await session_primitive.save()

        # Should not call record_message
        mock_chat_recorder.record_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_single_message(self, session_primitive, mock_chat_recorder):
        """Test save persists single message."""
        session_primitive.append("USER", "Test message")

        await session_primitive.save()

        # Should record the message
        mock_chat_recorder.record_message.assert_called_once()
        call_kwargs = mock_chat_recorder.record_message.call_args[1]
        assert call_kwargs['role'] == 'USER'
        assert call_kwargs['content'] == 'Test message'
        assert call_kwargs['message_type'] == 'MESSAGE'

    @pytest.mark.asyncio
    async def test_save_multiple_messages(self, session_primitive, mock_chat_recorder):
        """Test save persists all messages in order."""
        session_primitive.append("USER", "Question")
        session_primitive.append("ASSISTANT", "Answer")
        session_primitive.inject_system("Context")

        await session_primitive.save()

        # Should record all 3 messages
        assert mock_chat_recorder.record_message.call_count == 3

        # Verify order and content
        calls = mock_chat_recorder.record_message.call_args_list
        assert calls[0][1]['role'] == 'USER'
        assert calls[0][1]['content'] == 'Question'
        assert calls[1][1]['role'] == 'ASSISTANT'
        assert calls[1][1]['content'] == 'Answer'
        assert calls[2][1]['role'] == 'SYSTEM'
        assert calls[2][1]['content'] == 'Context'

    @pytest.mark.asyncio
    async def test_save_clears_messages_after_persist(self, session_primitive, mock_chat_recorder):
        """Test that save clears in-memory messages after persisting."""
        session_primitive.append("USER", "Test")

        assert session_primitive.count() == 1

        await session_primitive.save()

        # Should clear after save
        assert session_primitive.count() == 0
        assert session_primitive._messages == []

    @pytest.mark.asyncio
    async def test_save_with_metadata(self, session_primitive, mock_chat_recorder):
        """Test save preserves message metadata."""
        metadata = {'tag': 'important', 'score': 0.9}
        session_primitive.append("USER", "Test", metadata=metadata)

        await session_primitive.save()

        call_kwargs = mock_chat_recorder.record_message.call_args[1]
        assert call_kwargs['metadata'] == metadata

    @pytest.mark.asyncio
    async def test_save_without_chat_recorder(self, mock_execution_context):
        """Test save handles missing chat recorder."""
        session = SessionPrimitive(
            chat_recorder=None,
            execution_context=mock_execution_context,
            lua_sandbox=None
        )

        session.append("USER", "Test")

        # Should not raise exception
        await session.save()

    @pytest.mark.asyncio
    async def test_save_without_session_id(self, mock_execution_context):
        """Test save handles missing session ID."""
        recorder = Mock()
        recorder.session_id = None

        session = SessionPrimitive(
            chat_recorder=recorder,
            execution_context=mock_execution_context,
            lua_sandbox=None
        )

        session.append("USER", "Test")

        # Should not raise exception
        await session.save()
        recorder.record_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_continues_on_error(self, session_primitive, mock_chat_recorder):
        """Test save continues processing messages even if one fails."""
        # Setup recorder to fail on second message
        mock_chat_recorder.record_message.side_effect = [
            'msg-1',
            Exception('Database error'),
            'msg-3'
        ]

        session_primitive.append("USER", "Message 1")
        session_primitive.append("USER", "Message 2")
        session_primitive.append("USER", "Message 3")

        # Should not raise exception
        await session_primitive.save()

        # Should attempt all 3
        assert mock_chat_recorder.record_message.call_count == 3


class TestSessionPrimitiveRepr:
    """Test string representation."""

    def test_repr(self):
        """Test __repr__ shows message count."""
        session = SessionPrimitive(
            chat_recorder=Mock(),
            execution_context=Mock(),
            lua_sandbox=None
        )

        assert repr(session) == "SessionPrimitive(messages=0)"

        session.append("USER", "Test")
        assert repr(session) == "SessionPrimitive(messages=1)"

        session.append("ASSISTANT", "Response")
        assert repr(session) == "SessionPrimitive(messages=2)"
