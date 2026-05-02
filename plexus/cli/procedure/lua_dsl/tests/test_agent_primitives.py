"""
Tests for Agent Primitive - LLM agent operations.

Tests Agent.turn() method for executing agent reasoning and tool calls.
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, AsyncMock
from plexus.cli.procedure.lua_dsl.primitives.agent import AgentPrimitive, AgentResponse
from plexus.cli.procedure.lua_dsl.lua_sandbox import LuaSandbox


@pytest.fixture
def mock_llm():
    """Create a mock LangChain LLM."""
    return Mock()


@pytest.fixture
def mock_tool_primitive():
    """Create a mock ToolPrimitive."""
    tool = Mock()
    tool.record_call = Mock()
    return tool


@pytest.fixture
def mock_stop_primitive():
    """Create a mock StopPrimitive."""
    stop = Mock()
    stop.request = Mock()
    return stop


@pytest.fixture
def mock_iterations_primitive():
    """Create a mock IterationsPrimitive."""
    iterations = Mock()
    iterations.increment = Mock()
    iterations.current = Mock(return_value=1)
    return iterations


@pytest.fixture
def mock_chat_recorder():
    """Create a mock ProcedureChatRecorder."""
    recorder = Mock()
    recorder.session_id = 'session-123'
    recorder.record_message = AsyncMock()
    return recorder


@pytest.fixture
def agent_primitive(
    mock_llm,
    mock_tool_primitive,
    mock_stop_primitive,
    mock_iterations_primitive,
    mock_chat_recorder
):
    """Create an AgentPrimitive for testing."""
    return AgentPrimitive(
        name='worker',
        system_prompt='You are a helpful assistant.',
        initial_message='Start working.',
        llm=mock_llm,
        available_tools=[],
        tool_primitive=mock_tool_primitive,
        stop_primitive=mock_stop_primitive,
        iterations_primitive=mock_iterations_primitive,
        chat_recorder=mock_chat_recorder
    )


class TestAgentTurn:
    """Tests for Agent.turn() execution."""

    def test_turn_initializes_conversation_on_first_call(
        self, agent_primitive, mock_llm
    ):
        """Test that first turn() initializes conversation with system prompt and initial message."""
        # Mock LLM response
        mock_response = Mock()
        mock_response.content = 'Hello'
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response

        agent_primitive.turn()

        # Should call LLM with initialized conversation
        mock_llm.invoke.assert_called_once()

        # Conversation should have been initialized
        assert agent_primitive._initialized is True
        # After turn, conversation has system + initial + AI response
        assert len(agent_primitive._conversation) == 3

    def test_turn_captures_context_before_llm_invoke(
        self, agent_primitive, mock_llm, monkeypatch, tmp_path
    ):
        """AgentPrimitive writes the exact initialized conversation before invoking the LLM."""
        monkeypatch.setenv("PLEXUS_CAPTURE_LLM_CONTEXT_DIR", str(tmp_path))
        mock_response = Mock()
        mock_response.content = 'Hello'
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response

        agent_primitive.turn()

        payload = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
        markdown = next(tmp_path.glob("*.md")).read_text(encoding="utf-8")

        assert payload["agent_name"] == "Tactus AgentPrimitive: worker"
        assert payload["call_site"] == "tactus_agent_turn"
        assert payload["messages"][0]["content"] == "You are a helpful assistant."
        assert payload["messages"][1]["content"] == "Start working."
        assert "You are a helpful assistant." in markdown

    def test_turn_increments_iteration_counter(
        self, agent_primitive, mock_llm, mock_iterations_primitive
    ):
        """Test that turn() increments the iteration counter."""
        mock_response = Mock()
        mock_response.content = 'Response'
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response

        agent_primitive.turn()

        mock_iterations_primitive.increment.assert_called_once()

    def test_turn_returns_response_dict(self, agent_primitive, mock_llm):
        """Test that turn() returns a dict with content and tool_calls."""
        mock_response = Mock()
        mock_response.content = 'Agent response text'
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response

        result = agent_primitive.turn()

        assert isinstance(result, dict)
        assert 'content' in result
        assert 'tool_calls' in result
        assert 'token_usage' in result
        assert result['content'] == 'Agent response text'
        assert result['tool_calls'] == []

    def test_turn_with_inject_option(self, agent_primitive, mock_llm):
        """Test that turn() can inject additional context."""
        mock_response = Mock()
        mock_response.content = 'Response'
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response

        # First turn to initialize
        agent_primitive.turn()

        # Second turn with injection
        agent_primitive.turn({'inject': 'Additional context message'})

        # Should have added the injected message to conversation
        # System + Initial + AI Response 1 + Injected + AI Response 2
        assert len(agent_primitive._conversation) == 5

    def test_turn_injects_procedure_steering_once_before_next_llm_call(
        self,
        mock_llm,
        mock_tool_primitive,
        mock_stop_primitive,
        mock_iterations_primitive,
        mock_chat_recorder,
    ):
        """Each agent receives new procedure steering once before its next LLM call."""
        state = {}
        state_primitive = Mock()
        state_primitive.get.side_effect = lambda key, default=None: state.get(key, default)
        state_primitive.set.side_effect = lambda key, value: state.__setitem__(key, value)
        mock_chat_recorder.get_steering_messages.return_value = {
            "messages": [
                {
                    "id": "msg-steer-1",
                    "created_at": "2026-04-01T00:00:02.000Z",
                    "content": "Focus summary on reviewer contradictions.",
                    "metadata": {"source": "procedure-steering-input", "scope": "all_agents"},
                }
            ],
            "watermark": "2026-04-01T00:00:02.000Z",
        }
        captured_conversations = []

        def invoke(messages):
            captured_conversations.append([getattr(message, "content", "") for message in messages])
            response = Mock()
            response.content = "Response"
            response.tool_calls = []
            return response

        mock_llm.invoke.side_effect = invoke

        planner = AgentPrimitive(
            name="hypothesis_planner",
            system_prompt="Planner system",
            initial_message="Plan",
            llm=mock_llm,
            available_tools=[],
            tool_primitive=mock_tool_primitive,
            stop_primitive=mock_stop_primitive,
            iterations_primitive=mock_iterations_primitive,
            chat_recorder=mock_chat_recorder,
            state_primitive=state_primitive,
        )
        reporter = AgentPrimitive(
            name="report_writer",
            system_prompt="Reporter system",
            initial_message="Report",
            llm=mock_llm,
            available_tools=[],
            tool_primitive=mock_tool_primitive,
            stop_primitive=mock_stop_primitive,
            iterations_primitive=mock_iterations_primitive,
            chat_recorder=mock_chat_recorder,
            state_primitive=state_primitive,
        )

        planner.turn()
        reporter.turn()

        assert "USER STEERING RECEIVED MID-RUN" in "\n".join(captured_conversations[0])
        assert "Focus summary on reviewer contradictions." in "\n".join(captured_conversations[1])
        assert state["procedure_steering_watermark:hypothesis_planner"] == "2026-04-01T00:00:02.000Z"
        assert state["procedure_steering_watermark:report_writer"] == "2026-04-01T00:00:02.000Z"

    def test_turn_executes_tool_calls(
        self, agent_primitive, mock_llm, mock_tool_primitive
    ):
        """Test that turn() executes tool calls returned by LLM."""
        # Create a mock tool with proper attributes (not Mock properties)
        mock_tool = Mock()
        type(mock_tool).name = 'test_tool'  # Set as class attribute
        mock_tool.func = Mock(return_value='Tool result')

        agent_primitive.available_tools = [mock_tool]

        # Mock LLM response with tool call
        mock_response = Mock()
        mock_response.content = 'I will use the tool'
        # Create tool call mock with proper attributes
        tool_call = Mock()
        tool_call.name = 'test_tool'
        tool_call.args = {'param': 'value'}
        tool_call.id = 'call-1'
        mock_response.tool_calls = [tool_call]
        mock_llm.invoke.return_value = mock_response

        result = agent_primitive.turn()

        # Should execute the tool
        mock_tool.func.assert_called_once_with({'param': 'value'})

        # Should record the tool call
        mock_tool_primitive.record_call.assert_called_once()

        # Should return tool execution info
        assert len(result['tool_calls']) == 1
        assert result['tool_calls'][0]['name'] == 'test_tool'
        assert result['tool_calls'][0]['result'] == 'Tool result'

    def test_turn_appends_tool_result_when_tool_call_has_no_id(
        self, agent_primitive, mock_llm, mock_tool_primitive
    ):
        """Tool results must still enter conversation history even without tool_call_id."""
        mock_tool = Mock()
        type(mock_tool).name = 'test_tool'
        mock_tool.func = Mock(return_value='Tool result')
        agent_primitive.available_tools = [mock_tool]

        mock_response = Mock()
        mock_response.content = 'Using tool'
        tool_call = Mock()
        tool_call.name = 'test_tool'
        tool_call.args = {'param': 'value'}
        tool_call.id = None
        mock_response.tool_calls = [tool_call]
        mock_llm.invoke.return_value = mock_response

        agent_primitive.turn()

        mock_tool_primitive.record_call.assert_called_once_with('test_tool', {'param': 'value'}, 'Tool result')
        # system + initial + ai response + synthetic tool result message
        assert len(agent_primitive._conversation) == 4
        synthetic_tool_result = agent_primitive._conversation[-1]
        assert getattr(synthetic_tool_result, 'content', '') == "Tool 'test_tool' result: Tool result"

    def test_turn_handles_multiple_tool_calls(
        self, agent_primitive, mock_llm, mock_tool_primitive
    ):
        """Test that turn() can execute multiple tool calls in one turn."""
        # Create mock tools with proper attributes
        tool1 = Mock()
        type(tool1).name = 'tool_one'
        tool1.func = Mock(return_value='Result 1')

        tool2 = Mock()
        type(tool2).name = 'tool_two'
        tool2.func = Mock(return_value='Result 2')

        agent_primitive.available_tools = [tool1, tool2]

        # Mock LLM response with multiple tool calls
        mock_response = Mock()
        mock_response.content = 'Using multiple tools'
        # Create tool call mocks with proper attributes
        tool_call1 = Mock()
        tool_call1.name = 'tool_one'
        tool_call1.args = {'a': 1}
        tool_call1.id = 'call-1'

        tool_call2 = Mock()
        tool_call2.name = 'tool_two'
        tool_call2.args = {'b': 2}
        tool_call2.id = 'call-2'

        mock_response.tool_calls = [tool_call1, tool_call2]
        mock_llm.invoke.return_value = mock_response

        result = agent_primitive.turn()

        # Should execute both tools
        tool1.func.assert_called_once()
        tool2.func.assert_called_once()

        # Should record both calls
        assert mock_tool_primitive.record_call.call_count == 2

        # Should return both executions
        assert len(result['tool_calls']) == 2

    def test_turn_detects_stop_tool(
        self, agent_primitive, mock_llm, mock_stop_primitive
    ):
        """Test that turn() detects 'done' or 'stop' tool calls."""
        # Create a done tool with proper attributes
        done_tool = Mock()
        type(done_tool).name = 'done'
        done_tool.func = Mock(return_value='Stopped')

        agent_primitive.available_tools = [done_tool]

        # Mock LLM response with done tool call
        mock_response = Mock()
        mock_response.content = 'I am done'
        # Create tool call mock with proper attributes
        tool_call = Mock()
        tool_call.name = 'done'
        tool_call.args = {'reason': 'Task complete', 'success': True}
        tool_call.id = 'call-1'
        mock_response.tool_calls = [tool_call]
        mock_llm.invoke.return_value = mock_response

        agent_primitive.turn()

        # Should request stop
        mock_stop_primitive.request.assert_called_once_with('Task complete', True)

    def test_turn_extracts_token_usage(self, agent_primitive, mock_llm):
        """Test that turn() extracts token usage from LLM response."""
        mock_response = Mock()
        mock_response.content = 'Response'
        mock_response.tool_calls = []

        # Add usage metadata (newer LangChain format)
        mock_usage = Mock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50
        mock_usage.total_tokens = 150
        mock_response.usage_metadata = mock_usage

        mock_llm.invoke.return_value = mock_response

        result = agent_primitive.turn()

        # Should extract token usage
        assert result['token_usage']['input'] == 100
        assert result['token_usage']['output'] == 50
        assert result['token_usage']['total'] == 150

    def test_turn_normalizes_object_tool_call_args_with_args_as_dict(
        self, agent_primitive, mock_llm, mock_tool_primitive
    ):
        """Object tool calls should prefer args_as_dict() and record normalized args."""
        mock_tool = Mock()
        type(mock_tool).name = 'test_tool'
        mock_tool.func = Mock(return_value='Tool result')
        agent_primitive.available_tools = [mock_tool]

        class _ToolCallWithArgsAsDict:
            def __init__(self):
                self.name = 'test_tool'
                self.id = 'call-1'
                self.args = '{"ignored": true}'

            def args_as_dict(self):
                return {'param': 'value'}

        mock_response = Mock()
        mock_response.content = 'Use tool'
        tool_call = _ToolCallWithArgsAsDict()
        mock_response.tool_calls = [tool_call]
        mock_llm.invoke.return_value = mock_response

        result = agent_primitive.turn()

        mock_tool.func.assert_called_once_with({'param': 'value'})
        mock_tool_primitive.record_call.assert_called_once_with('test_tool', {'param': 'value'}, 'Tool result')
        assert result['tool_calls'][0]['args'] == {'param': 'value'}

    def test_turn_normalizes_json_string_args_from_tool_call_object(
        self, agent_primitive, mock_llm, mock_tool_primitive
    ):
        """JSON-string args should be parsed into a dict before execution."""
        mock_tool = Mock()
        type(mock_tool).name = 'test_tool'
        mock_tool.func = Mock(return_value='Tool result')
        agent_primitive.available_tools = [mock_tool]

        mock_response = Mock()
        mock_response.content = 'Use tool'
        tool_call = Mock()
        tool_call.name = 'test_tool'
        tool_call.id = 'call-1'
        tool_call.args = '{"param": "value"}'
        mock_response.tool_calls = [tool_call]
        mock_llm.invoke.return_value = mock_response

        result = agent_primitive.turn()

        mock_tool.func.assert_called_once_with({'param': 'value'})
        mock_tool_primitive.record_call.assert_called_once_with('test_tool', {'param': 'value'}, 'Tool result')
        assert result['tool_calls'][0]['args'] == {'param': 'value'}

    def test_turn_normalizes_callable_args_attribute(
        self, agent_primitive, mock_llm, mock_tool_primitive
    ):
        """Callable args attributes should be called once and normalized to a dict."""
        mock_tool = Mock()
        type(mock_tool).name = 'test_tool'
        mock_tool.func = Mock(return_value='Tool result')
        agent_primitive.available_tools = [mock_tool]

        mock_response = Mock()
        mock_response.content = 'Use tool'
        tool_call = Mock()
        tool_call.name = 'test_tool'
        tool_call.id = 'call-1'
        tool_call.args_as_dict = None
        tool_call.args = Mock(return_value={'param': 'value'})
        mock_response.tool_calls = [tool_call]
        mock_llm.invoke.return_value = mock_response

        result = agent_primitive.turn()

        tool_call.args.assert_called_once_with()
        mock_tool.func.assert_called_once_with({'param': 'value'})
        mock_tool_primitive.record_call.assert_called_once_with('test_tool', {'param': 'value'}, 'Tool result')
        assert result['tool_calls'][0]['args'] == {'param': 'value'}

    def test_turn_handles_malformed_tool_args_without_crashing(
        self, agent_primitive, mock_llm, mock_tool_primitive
    ):
        """Malformed tool args should become a deterministic tool error and record empty args."""
        mock_tool = Mock()
        type(mock_tool).name = 'test_tool'
        mock_tool.func = Mock(return_value='Tool result')
        agent_primitive.available_tools = [mock_tool]

        mock_response = Mock()
        mock_response.content = 'Use tool'
        tool_call = Mock()
        tool_call.name = 'test_tool'
        tool_call.id = 'call-1'
        tool_call.args_as_dict = None
        tool_call.args = object()
        mock_response.tool_calls = [tool_call]
        mock_llm.invoke.return_value = mock_response

        result = agent_primitive.turn()

        mock_tool.func.assert_not_called()
        mock_tool_primitive.record_call.assert_called_once()
        record_args = mock_tool_primitive.record_call.call_args[0]
        assert record_args[0] == 'test_tool'
        assert record_args[1] == {}
        assert "Tool argument error:" in record_args[2]
        assert result['tool_calls'][0]['args'] == {}
        assert "Tool argument error:" in result['tool_calls'][0]['result']

    def test_turn_handles_error_gracefully(self, agent_primitive, mock_llm):
        """Test that turn() handles LLM errors gracefully."""
        mock_llm.invoke.side_effect = Exception('LLM error')

        result = agent_primitive.turn()

        # Should return error response
        assert isinstance(result, dict)
        assert 'error' in result
        assert 'LLM error' in result['error']
        assert result['content'] == ''
        assert result['tool_calls'] == []

    def test_turn_queues_messages_for_recording(
        self, agent_primitive, mock_llm, mock_chat_recorder
    ):
        """Test that turn() queues messages for async recording."""
        mock_response = Mock()
        mock_response.content = 'Agent response'
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response

        agent_primitive.turn()

        # Should have queued messages (system, user, assistant)
        assert len(agent_primitive._recording_queue) == 3

    @pytest.mark.asyncio
    async def test_flush_recordings(self, agent_primitive, mock_llm, mock_chat_recorder):
        """Test that queued messages are flushed to chat recorder."""
        mock_response = Mock()
        mock_response.content = 'Response'
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response

        # Execute a turn to queue messages
        agent_primitive.turn()

        # Flush recordings
        await agent_primitive.flush_recordings()

        # Should have recorded 3 messages (system, user, assistant)
        assert mock_chat_recorder.record_message.call_count == 3

        # Queue should be cleared
        assert len(agent_primitive._recording_queue) == 0

    def test_turn_injects_procedure_steering_once_per_agent(
        self,
        mock_llm,
        mock_tool_primitive,
        mock_stop_primitive,
        mock_iterations_primitive,
        mock_chat_recorder,
    ):
        """Every agent should receive new steering once before its next LLM call."""
        state = {}
        state_primitive = Mock()
        state_primitive.get.side_effect = lambda key, default=None: state.get(key, default)
        state_primitive.set.side_effect = lambda key, value: state.__setitem__(key, value)
        mock_chat_recorder.get_steering_messages.return_value = {
            "messages": [
                {
                    "id": "steer-1",
                    "created_at": "2026-05-02T15:00:00.000Z",
                    "content": "Make sure the report emphasizes reviewer contradictions.",
                }
            ],
            "watermark": "2026-05-02T15:00:00.000Z",
        }
        mock_response = Mock()
        mock_response.content = "Done"
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response

        planner = AgentPrimitive(
            name="hypothesis_planner",
            system_prompt="Planner system",
            initial_message="Plan",
            llm=mock_llm,
            available_tools=[],
            tool_primitive=mock_tool_primitive,
            stop_primitive=mock_stop_primitive,
            iterations_primitive=mock_iterations_primitive,
            chat_recorder=mock_chat_recorder,
            state_primitive=state_primitive,
        )
        reporter = AgentPrimitive(
            name="report_writer",
            system_prompt="Reporter system",
            initial_message="Report",
            llm=mock_llm,
            available_tools=[],
            tool_primitive=mock_tool_primitive,
            stop_primitive=mock_stop_primitive,
            iterations_primitive=mock_iterations_primitive,
            chat_recorder=mock_chat_recorder,
            state_primitive=state_primitive,
        )

        planner.turn()
        reporter.turn()

        planner_messages = mock_llm.invoke.call_args_list[0].args[0]
        reporter_messages = mock_llm.invoke.call_args_list[1].args[0]
        assert any(
            "USER STEERING RECEIVED MID-RUN" in getattr(message, "content", "")
            for message in planner_messages
        )
        assert any(
            "Make sure the report emphasizes reviewer contradictions." in getattr(message, "content", "")
            for message in reporter_messages
        )
        assert state["procedure_steering_watermark:hypothesis_planner"] == "2026-05-02T15:00:00.000Z"
        assert state["procedure_steering_watermark:report_writer"] == "2026-05-02T15:00:00.000Z"


class TestAgentReset:
    """Tests for Agent.reset() behavior."""

    def test_reset_clears_conversation(self, agent_primitive, mock_llm):
        """Reset should clear conversation and mark agent as uninitialized."""
        mock_response = Mock()
        mock_response.content = 'Hello'
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response

        # Initialize conversation
        agent_primitive.turn()
        assert agent_primitive._initialized is True
        assert len(agent_primitive._conversation) > 0

        # Reset and verify
        agent_primitive.reset()
        assert agent_primitive._initialized is False
        assert agent_primitive._conversation == []

    def test_reset_preserves_recording_queue(self, agent_primitive):
        """Reset should not clear the recording queue."""
        agent_primitive._recording_queue.append({"role": "SYSTEM", "content": "keep"})
        agent_primitive.reset()
        assert len(agent_primitive._recording_queue) == 1


class TestLuaFacingAgentInterface:
    """Regression coverage for the optimizer-facing Lua agent contract."""

    def test_clear_history_alias_resets_state(self, agent_primitive, mock_llm):
        mock_response = Mock()
        mock_response.content = 'Hello'
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response

        agent_primitive.turn()
        assert agent_primitive._initialized is True
        assert len(agent_primitive._conversation) > 0

        agent_primitive.clear_history()
        assert agent_primitive._initialized is False
        assert agent_primitive._conversation == []

    def test_history_accessor_supports_add_get_and_token_count_in_lua(
        self,
        agent_primitive,
    ):
        sandbox = LuaSandbox()
        sandbox.inject_primitive("code_editor", agent_primitive)

        result = sandbox.execute(
            """
            code_editor.clear_history()
            code_editor.history:add({role = "system", content = "Current YAML"})
            code_editor.history:add({role = "user", content = "Apply the edit"})
            local msgs = code_editor.history:get()
            return {
              count = msgs[1] ~= nil and msgs[2] ~= nil and 2 or 0,
              tokens = code_editor.history:count_tokens(),
              first = msgs[1].content,
              second = msgs[2].content
            }
            """
        )

        assert result["count"] == 2
        assert result["tokens"] >= 2
        assert result["first"] == "Current YAML"
        assert result["second"] == "Apply the edit"

    def test_agent_callable_alias_maps_message_to_inject(
        self,
        agent_primitive,
        mock_llm,
    ):
        mock_response = Mock()
        mock_response.content = 'Edited'
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response

        sandbox = LuaSandbox()
        sandbox.inject_primitive("code_editor", agent_primitive)

        result = sandbox.execute(
            """
            code_editor.clear_history()
            code_editor.history:add({role = "system", content = "Current YAML"})
            return code_editor({message = "Make the smallest safe edit"})
            """
        )

        assert result["content"] == "Edited"
        invoked_messages = mock_llm.invoke.call_args.args[0]
        contents = [getattr(msg, "content", "") for msg in invoked_messages]
        assert contents[:2] == ["Current YAML", "Make the smallest safe edit"]


class TestAgentResponse:
    """Tests for AgentResponse helper class."""

    def test_agent_response_to_dict(self):
        """Test AgentResponse.to_dict() conversion."""
        response = AgentResponse(
            content='Test content',
            tool_calls=[{'name': 'tool1', 'args': {}}],
            token_usage={'input': 10, 'output': 5}
        )

        result = response.to_dict()

        assert result['content'] == 'Test content'
        assert len(result['tool_calls']) == 1
        assert result['token_usage']['input'] == 10

    def test_agent_response_repr(self):
        """Test AgentResponse string representation."""
        response = AgentResponse(
            content='Test',
            tool_calls=[{}, {}],
            token_usage={}
        )

        repr_str = repr(response)

        assert 'AgentResponse' in repr_str
        assert 'content_len=4' in repr_str
        assert 'tools=2' in repr_str
