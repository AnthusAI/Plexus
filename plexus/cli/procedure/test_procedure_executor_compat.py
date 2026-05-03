from pathlib import Path
from types import SimpleNamespace

import pytest

from plexus.cli.procedure.mcp_transport import create_procedure_mcp_server
from plexus.cli.procedure.procedure_executor import _PlexusTraceLogBridge, _execute_tactus


class _FakeRuntime:
    last_context = None

    def __init__(self, **_kwargs):
        self.toolset_registry = {}
        self.tool_primitive = None
        self.log_handler = None

    async def execute(self, _source, _context, format="yaml"):
        assert format == "yaml"
        _FakeRuntime.last_context = _context
        return {"success": True, "status": "planned"}


class _LegacyRuntimeNoTraceSink:
    last_context = None

    def __init__(
        self,
        procedure_id,
        storage_backend,
        hitl_handler,
        mcp_server=None,
        openai_api_key=None,
    ):
        assert procedure_id
        assert storage_backend is not None
        assert hitl_handler is not None
        self.toolset_registry = {}
        self.tool_primitive = None
        self.log_handler = None

    async def execute(self, _source, _context, format="yaml"):
        assert format == "yaml"
        _LegacyRuntimeNoTraceSink.last_context = _context
        return {"success": True, "status": "planned"}


class _RuntimeWithChatRecorder:
    last_context = None

    def __init__(
        self,
        procedure_id,
        storage_backend,
        hitl_handler,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=None,
    ):
        assert procedure_id
        assert storage_backend is not None
        assert hitl_handler is not None
        assert chat_recorder is not None
        self.toolset_registry = {}
        self.tool_primitive = None
        self.log_handler = None

    async def execute(self, _source, _context, format="yaml"):
        assert format == "yaml"
        _RuntimeWithChatRecorder.last_context = _context
        return {"success": True, "status": "planned"}


class _RuntimeLegacyChatNoTrace:
    def __init__(
        self,
        procedure_id,
        storage_backend,
        hitl_handler,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=None,
    ):
        self.toolset_registry = {}
        self.tool_primitive = None
        self.log_handler = None

    async def execute(self, _source, _context, format="yaml"):
        assert format == "yaml"
        return {"success": True, "response": "synthetic assistant response"}


class _RuntimeWithTraceNoMessages:
    def __init__(
        self,
        procedure_id,
        storage_backend,
        hitl_handler,
        chat_recorder=None,
        trace_sink=None,
        mcp_server=None,
        openai_api_key=None,
    ):
        assert procedure_id
        assert storage_backend is not None
        assert hitl_handler is not None
        assert chat_recorder is not None
        assert trace_sink is not None
        self.toolset_registry = {}
        self.tool_primitive = None
        self.log_handler = None

    async def execute(self, _source, _context, format="yaml"):
        assert format == "yaml"
        return {"success": True, "response": "assistant from result payload"}


class _RuntimeStreamingWithoutTraceParam:
    def __init__(
        self,
        procedure_id,
        storage_backend,
        hitl_handler,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=None,
    ):
        assert procedure_id
        assert storage_backend is not None
        assert hitl_handler is not None
        self.toolset_registry = {}
        self.tool_primitive = None
        self.log_handler = None

    async def execute(self, _source, _context, format="yaml"):
        assert format == "yaml"
        from tactus.protocols.models import AgentStreamChunkEvent, AgentTurnEvent

        self.log_handler.log(
            AgentStreamChunkEvent(
                agent_name="assistant",
                chunk_text="Hel",
                accumulated_text="Hel",
            )
        )
        self.log_handler.log(
            AgentStreamChunkEvent(
                agent_name="assistant",
                chunk_text="lo",
                accumulated_text="Hello",
            )
        )
        self.log_handler.log(
            AgentTurnEvent(
                agent_name="assistant",
                stage="completed",
            )
        )
        return {"success": True, "response": "Hello"}


class _RuntimeWithCostEvents:
    def __init__(
        self,
        procedure_id,
        storage_backend,
        hitl_handler,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=None,
    ):
        assert procedure_id
        assert storage_backend is not None
        assert hitl_handler is not None
        self.toolset_registry = {}
        self.tool_primitive = None
        self.log_handler = None

    async def execute(self, _source, _context, format="yaml"):
        assert format == "yaml"
        from tactus.protocols.models import CostEvent

        self.log_handler.log(
            CostEvent(
                agent_name="optimizer",
                model="gpt-5.2",
                provider="openai",
                prompt_tokens=100,
                completion_tokens=40,
                total_tokens=140,
                prompt_cost=0.002,
                completion_cost=0.001,
                total_cost=0.003,
            )
        )
        return {"success": True, "response": "cost event emitted"}


class _RuntimeWithFailureResult:
    def __init__(
        self,
        procedure_id,
        storage_backend,
        hitl_handler,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=None,
    ):
        assert procedure_id
        self.toolset_registry = {}
        self.tool_primitive = None
        self.log_handler = None

    async def execute(self, _source, _context, format="yaml"):
        assert format == "yaml"
        return {"success": False, "error": "planned failure"}


class _RuntimeWithWrappedFailureResult:
    def __init__(
        self,
        procedure_id,
        storage_backend,
        hitl_handler,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=None,
    ):
        assert procedure_id
        self.toolset_registry = {}
        self.tool_primitive = None
        self.log_handler = None

    async def execute(self, _source, _context, format="yaml"):
        assert format == "yaml"
        return {
            "success": True,
            "result": {
                "success": False,
                "status": "error",
                "message": "Insufficient feedback data for optimization",
            },
        }


class _RuntimeThatRaises:
    def __init__(
        self,
        procedure_id,
        storage_backend,
        hitl_handler,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=None,
    ):
        assert procedure_id
        self.toolset_registry = {}
        self.tool_primitive = None
        self.log_handler = None

    async def execute(self, _source, _context, format="yaml"):
        assert format == "yaml"
        raise RuntimeError("runtime exploded")


class _CollectingTraceSink:
    def __init__(self):
        self.events = []

    async def record(self, event):
        self.events.append(event)
        return None

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_trace_bridge_forwards_cost_events_to_trace_sink():
    from tactus.protocols.models import CostEvent

    sink = _CollectingTraceSink()
    cost_events = []
    bridge = _PlexusTraceLogBridge(sink, on_cost_event=lambda e: cost_events.append(e))
    event = CostEvent(
        agent_name="optimizer",
        model="gpt-5.4",
        provider="openai",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        prompt_cost=0.001,
        completion_cost=0.001,
        total_cost=0.002,
    )

    bridge.log(event)
    await bridge.flush()
    await bridge.close()

    assert len(cost_events) == 1
    assert len(bridge.cost_events) == 1
    assert len(sink.events) == 1
    assert getattr(sink.events[0], "event_type", None) == "cost"


@pytest.mark.asyncio
async def test_execute_tactus_initializes_embedded_mcp_transport(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    # Patch runtime and adapters to keep this test focused on MCP bridge setup.
    monkeypatch.setattr("tactus.core.TactusRuntime", _FakeRuntime)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: SimpleNamespace(),
    )

    mcp_server = await create_procedure_mcp_server(experiment_context={"procedure_id": "p-1"})
    assert mcp_server.transport.connected is False

    result = await _execute_tactus(
        procedure_id="p-1",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  local function run(input)\n"
            "    return { success = true }\n"
            "  end\n"
            "  return run(input)\n"
        ),
        client=SimpleNamespace(),
        mcp_server=mcp_server,
        context={},
    )

    assert result["success"] is True
    assert mcp_server.transport.connected is True


@pytest.mark.asyncio
async def test_execute_tactus_hydrates_context_from_params_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    monkeypatch.setattr("tactus.core.TactusRuntime", _FakeRuntime)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: SimpleNamespace(),
    )

    result = await _execute_tactus(
        procedure_id="p-ctx",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "params:\n"
            "  brief:\n"
            "    type: string\n"
            "    value: hello\n"
            "  dry_run:\n"
            "    type: boolean\n"
            "    default: true\n"
            "code: |\n"
            "  local function run(input)\n"
            "    return { success = true }\n"
            "  end\n"
            "  Procedure {\n"
            "    input = { brief = field.string{required=true} },\n"
            "    output = { success = field.boolean{required=true} },\n"
            "    function(input) return run(input) end\n"
            "  }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context=None,
    )

    assert result["success"] is True
    assert _FakeRuntime.last_context == {"brief": "hello", "dry_run": True}


@pytest.mark.asyncio
async def test_execute_tactus_supports_legacy_runtime_without_trace_sink(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    monkeypatch.setattr("tactus.core.TactusRuntime", _LegacyRuntimeNoTraceSink)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: SimpleNamespace(),
    )

    result = await _execute_tactus(
        procedure_id="p-legacy",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  local function run(input)\n"
            "    return { success = true }\n"
            "  end\n"
            "  return run(input)\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={"hello": "world"},
    )

    assert result["success"] is True
    assert _LegacyRuntimeNoTraceSink.last_context == {"hello": "world"}


@pytest.mark.asyncio
async def test_execute_tactus_passes_chat_recorder_when_supported(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithChatRecorder)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: SimpleNamespace(),
    )

    result = await _execute_tactus(
        procedure_id="p-chat-recorder",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  local function run(input)\n"
            "    return { success = true }\n"
            "  end\n"
            "  return run(input)\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={"check": "chat-recorder"},
    )

    assert result["success"] is True
    assert _RuntimeWithChatRecorder.last_context == {"check": "chat-recorder"}


@pytest.mark.asyncio
async def test_execute_tactus_injects_console_trigger_message_into_runtime_context(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _RecorderWithTrigger(SimpleNamespace):
        def get_latest_console_trigger_message(self):
            return "hello from console trigger"

    recorder = _RecorderWithTrigger()

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithChatRecorder)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: recorder,
    )

    result = await _execute_tactus(
        procedure_id="p-chat-context",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  local function run(input)\n"
            "    return { success = true }\n"
            "  end\n"
            "  return run(input)\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={"check": "chat-recorder"},
    )

    assert result["success"] is True
    assert _RuntimeWithChatRecorder.last_context == {
        "check": "chat-recorder",
        "console_user_message": "hello from console trigger",
    }


@pytest.mark.asyncio
async def test_execute_tactus_injects_console_session_history_into_runtime_context(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _RecorderWithSessionHistory(SimpleNamespace):
        def get_latest_console_trigger_message(self):
            return "latest prompt"

        def get_console_session_history(self):
            return [
                {"role": "USER", "content": "Pick a random number."},
                {"role": "ASSISTANT", "content": "How about 7?"},
            ]

    recorder = _RecorderWithSessionHistory()

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithChatRecorder)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: recorder,
    )

    result = await _execute_tactus(
        procedure_id="p-chat-history",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  local function run(input)\n"
            "    return { success = true }\n"
            "  end\n"
            "  return run(input)\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={"check": "chat-history"},
    )

    assert result["success"] is True
    assert _RuntimeWithChatRecorder.last_context == {
        "check": "chat-history",
        "console_user_message": "latest prompt",
        "console_session_history": [
            {"role": "USER", "content": "Pick a random number."},
            {"role": "ASSISTANT", "content": "How about 7?"},
        ],
    }


@pytest.mark.asyncio
async def test_execute_tactus_skips_chat_recorder_console_lookups_when_context_provides_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _RecorderWithCounters(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.trigger_calls = 0
            self.history_calls = 0

        def get_latest_console_trigger_message(self):
            self.trigger_calls += 1
            return "from-recorder"

        def get_console_session_history(self):
            self.history_calls += 1
            return [{"role": "USER", "content": "from-recorder"}]

    recorder = _RecorderWithCounters()

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithChatRecorder)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: recorder,
    )

    result = await _execute_tactus(
        procedure_id="p-chat-history-preloaded",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  local function run(input)\n"
            "    return { success = true }\n"
            "  end\n"
            "  return run(input)\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={
            "console_user_message": "from-context",
            "console_session_history": [{"role": "USER", "content": "from-context"}],
        },
    )

    assert result["success"] is True
    assert recorder.trigger_calls == 0
    assert recorder.history_calls == 0
    assert _RuntimeWithChatRecorder.last_context["console_user_message"] == "from-context"
    assert _RuntimeWithChatRecorder.last_context["console_session_history"] == [
        {"role": "USER", "content": "from-context"}
    ]


@pytest.mark.asyncio
async def test_execute_tactus_sets_chat_recorder_account_id_from_runtime_context(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _RecorderAccountAware(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.account_id = None

        def get_latest_console_trigger_message(self):
            return f"trigger-{self.account_id}"

    recorder = _RecorderAccountAware()

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithChatRecorder)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: recorder,
    )

    result = await _execute_tactus(
        procedure_id="p-chat-account",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  local function run(input)\n"
            "    return { success = true }\n"
            "  end\n"
            "  return run(input)\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={"account_id": "acct-runtime", "check": "account-binding"},
    )

    assert result["success"] is True
    assert recorder.account_id == "acct-runtime"
    assert _RuntimeWithChatRecorder.last_context == {
        "account_id": "acct-runtime",
        "check": "account-binding",
        "console_user_message": "trigger-acct-runtime",
    }


@pytest.mark.asyncio
async def test_execute_tactus_synthesizes_assistant_message_for_legacy_chat_runtime(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _RecordingChatRecorder(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.messages = []

        async def record_assistant_message(self, content: str):
            self.messages.append(content)
            return "msg-1"

    recorder = _RecordingChatRecorder()

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeLegacyChatNoTrace)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: recorder,
    )

    result = await _execute_tactus(
        procedure_id="p-legacy-chat",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
    )

    assert result["success"] is True
    assert recorder.messages == ["synthetic assistant response"]


@pytest.mark.asyncio
async def test_execute_tactus_records_result_response_when_trace_has_no_assistant_messages(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _RecordingChatRecorder(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.messages = []

        async def record_assistant_message(self, content: str):
            self.messages.append(content)
            return "msg-1"

    class _TraceSinkWithoutAssistantMessages(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.assistant_message_texts = []

    recorder = _RecordingChatRecorder()

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithTraceNoMessages)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: _TraceSinkWithoutAssistantMessages(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: recorder,
    )

    result = await _execute_tactus(
        procedure_id="p-trace-no-assistant",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
    )

    assert result["success"] is True
    assert recorder.messages == ["assistant from result payload"]


@pytest.mark.asyncio
async def test_execute_tactus_does_not_duplicate_response_when_trace_already_has_same_assistant_text(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _RecordingChatRecorder(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.messages = []

        async def record_assistant_message(self, content: str):
            self.messages.append(content)
            return "msg-1"

    class _TraceSinkWithAssistantMessages(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.assistant_message_texts = ["assistant from result payload"]

    recorder = _RecordingChatRecorder()

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithTraceNoMessages)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: _TraceSinkWithAssistantMessages(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: recorder,
    )

    result = await _execute_tactus(
        procedure_id="p-trace-has-assistant",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
    )

    assert result["success"] is True
    assert recorder.messages == []


@pytest.mark.asyncio
async def test_execute_tactus_does_not_record_result_response_when_trace_has_different_assistant_text(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _RecordingChatRecorder(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.messages = []

        async def record_assistant_message(self, content: str):
            self.messages.append(content)
            return "msg-1"

    class _TraceSinkWithDifferentAssistantMessage(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.assistant_message_texts = ["assistant streamed from trace sink"]

    recorder = _RecordingChatRecorder()

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithTraceNoMessages)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: _TraceSinkWithDifferentAssistantMessage(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: recorder,
    )

    result = await _execute_tactus(
        procedure_id="p-trace-has-different-assistant",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
    )

    assert result["success"] is True
    assert recorder.messages == []


@pytest.mark.asyncio
async def test_execute_tactus_streams_via_log_handler_without_trace_sink_constructor(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _StreamingRecorder(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.session_id = None
            self.recorded = []
            self.updated = []
            self.fallback_messages = []

        async def start_session(self, _context=None):
            self.session_id = "sess-stream"
            return self.session_id

        async def record_message(self, **kwargs):
            self.recorded.append(kwargs)
            return "msg-stream"

        async def update_message(self, **kwargs):
            self.updated.append(kwargs)
            return True

        async def record_assistant_message(self, content: str):
            self.fallback_messages.append(content)
            return "msg-fallback"

    recorder = _StreamingRecorder()

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeStreamingWithoutTraceParam)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: recorder,
    )

    result = await _execute_tactus(
        procedure_id="p-stream-no-trace-param",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
    )

    assert result["success"] is True
    assert len(recorder.recorded) == 1
    assert recorder.recorded[0]["content"] == "Hel"
    assert len(recorder.updated) >= 1
    assert recorder.updated[-1]["content"] == "Hello"
    assert recorder.fallback_messages == []


@pytest.mark.asyncio
async def test_execute_tactus_persists_inference_costs_from_cost_events(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _Recorder(SimpleNamespace):
        async def record_assistant_message(self, _content: str):
            return "msg-1"

    class _StorageWithState(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.state = {}

        def state_set(self, _procedure_id, key, value):
            self.state[key] = value

        def state_get(self, _procedure_id, key, default=None):
            return self.state.get(key, default)

    storage = _StorageWithState()

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithCostEvents)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: storage,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: _Recorder(),
    )

    result = await _execute_tactus(
        procedure_id="p-costs",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
    )

    assert result["success"] is True
    costs = storage.state.get("costs")
    assert isinstance(costs, dict)
    assert costs["inference"]["total"] == pytest.approx(0.003)
    assert len(costs["inference"]["entries"]) == 1
    assert costs["inference"]["entries"][0]["agent_name"] == "optimizer"
    assert isinstance(costs["inference"]["breakdown"], list)
    assert len(costs["inference"]["breakdown"]) == 1
    assert costs["inference"]["breakdown"][0]["provider"] == "openai"
    assert costs["inference"]["breakdown"][0]["model"] == "gpt-5.2"
    assert costs["inference"]["breakdown"][0]["spent_usd"] == pytest.approx(0.003)
    assert costs["totals"]["overall"]["incurred"] == pytest.approx(0.003)


@pytest.mark.asyncio
async def test_execute_tactus_completes_stages_only_on_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    completed = []
    failed = []

    monkeypatch.setattr("tactus.core.TactusRuntime", _FakeRuntime)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._advance_task_to_running_stage",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._complete_all_task_stages",
        lambda _client, task_id: completed.append(task_id),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._fail_all_task_stages",
        lambda _client, task_id, error_message="": failed.append((task_id, error_message)),
    )

    result = await _execute_tactus(
        procedure_id="p-stage-success",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
        _task_id_for_stage_tracking="task-success",
    )

    assert result["success"] is True
    assert completed == ["task-success"]
    assert failed == []


@pytest.mark.asyncio
async def test_execute_tactus_marks_stages_failed_when_runtime_returns_failure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    completed = []
    failed = []

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithFailureResult)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._advance_task_to_running_stage",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._complete_all_task_stages",
        lambda _client, task_id: completed.append(task_id),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._fail_all_task_stages",
        lambda _client, task_id, error_message="": failed.append((task_id, error_message)),
    )

    result = await _execute_tactus(
        procedure_id="p-stage-failure",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = false }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
        _task_id_for_stage_tracking="task-failure",
    )

    assert result["success"] is False
    assert completed == []
    assert failed == [("task-failure", "planned failure")]


@pytest.mark.asyncio
async def test_execute_tactus_marks_stages_failed_when_runtime_returns_wrapped_failure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    completed = []
    failed = []

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithWrappedFailureResult)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._advance_task_to_running_stage",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._complete_all_task_stages",
        lambda _client, task_id: completed.append(task_id),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._fail_all_task_stages",
        lambda _client, task_id, error_message="": failed.append((task_id, error_message)),
    )

    result = await _execute_tactus(
        procedure_id="p-stage-wrapped-failure",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = false }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
        _task_id_for_stage_tracking="task-wrapped-failure",
    )

    assert result["success"] is False
    assert result["error"] == "Insufficient feedback data for optimization"
    assert completed == []
    assert failed == [("task-wrapped-failure", "Insufficient feedback data for optimization")]


@pytest.mark.asyncio
async def test_execute_tactus_marks_stages_failed_when_runtime_raises(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    failed = []

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeThatRaises)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._advance_task_to_running_stage",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._fail_all_task_stages",
        lambda _client, task_id, error_message="": failed.append((task_id, error_message)),
    )

    result = await _execute_tactus(
        procedure_id="p-stage-exception",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
        _task_id_for_stage_tracking="task-exception",
    )

    assert result["success"] is False
    assert failed == [("task-exception", "runtime exploded")]


def test_scorecard_create_dry_run_skips_approval():
    yaml_path = Path("plexus/procedures/scorecard_create.yaml")
    content = yaml_path.read_text()

    dry_run_index = content.find("if dry_run then")
    approve_index = content.find("local approved = Human.approve")

    assert dry_run_index != -1, "dry-run branch must exist"
    assert approve_index != -1, "approval branch must exist for non-dry-run execution"
    assert dry_run_index < approve_index, "dry-run should return before approval"
