import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from plexus.cli.procedure.mcp_transport import create_procedure_mcp_server
from plexus.cli.procedure.procedure_executor import (
    _PlexusTraceLogBridge,
    _ensure_direct_run_cli_path,
    _execute_tactus,
    _score_edit_audit_markdown,
)


def test_score_change_audit_calls_out_guidelines_only_candidate() -> None:
    markdown = _score_edit_audit_markdown(
        {
            "success": True,
            "version_id": "candidate-1",
            "changed_fields": ["guidelines"],
        }
    )

    assert markdown.startswith("**Guidelines update saved**")
    assert "- Changed fields: `guidelines`" in markdown


def test_direct_run_makes_its_python_console_scripts_available(monkeypatch):
    monkeypatch.setattr("plexus.cli.procedure.procedure_executor.sys.executable", "/tmp/venv/bin/python")
    monkeypatch.setenv("PATH", "/usr/bin")

    _ensure_direct_run_cli_path()

    assert os.environ["PATH"].split(os.pathsep) == ["/tmp/venv/bin", "/usr/bin"]


class _FakeRuntime:
    last_context = None
    last_instance = None
    last_kwargs = None

    def __init__(self, **_kwargs):
        _FakeRuntime.last_kwargs = _kwargs
        self.toolset_registry = {}
        self.tool_primitive = None
        self.log_handler = None
        _FakeRuntime.last_instance = self

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


class _RuntimeWithSourceCapture:
    last_context = None
    last_source = None

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
        _RuntimeWithSourceCapture.last_source = _source
        _RuntimeWithSourceCapture.last_context = _context
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


class _RuntimeStreamingManyChunksWithoutTraceParam:
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

        target = "Streaming bridge should preserve every chunk."
        partial = ""
        for char in target:
            partial += char
            self.log_handler.log(
                AgentStreamChunkEvent(
                    agent_name="assistant",
                    chunk_text=char,
                    accumulated_text=partial,
                )
            )
        self.log_handler.log(
            AgentTurnEvent(
                agent_name="assistant",
                stage="completed",
            )
        )
        return {"success": True, "response": target}


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


class _FakeMCPClient:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [
            {
                "name": "plexus_scorecards_list",
                "description": "List scorecards from Plexus.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "string"},
                    },
                },
            },
            {
                "name": "plexus_scorecard_info",
                "description": "Get scorecard details.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "scorecard_identifier": {"type": "string"},
                    },
                    "required": ["scorecard_identifier"],
                },
            },
        ]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"called {name} with {arguments}",
                }
            ]
        }


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
async def test_execute_tactus_direct_run_uses_ephemeral_storage_and_source_path(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("tactus.core.TactusRuntime", _FakeRuntime)

    direct_storages = []
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.InMemoryStorageAdapter",
        lambda procedure_id: direct_storages.append(procedure_id) or SimpleNamespace(
            state_set=lambda *_a, **_k: None,
            state_get=lambda *_a, **_k: {},
        ),
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
        procedure_id="direct-1",
        procedure_source="name: Test\nclass: Tactus\ncode: |\n  return { success = true }\n",
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
        direct_run=True,
        source_file_path="/tmp/direct_optimizer.tac",
    )

    assert result["success"] is True
    assert direct_storages == ["direct-1"]
    assert _FakeRuntime.last_kwargs["source_file_path"] == "/tmp/direct_optimizer.tac"


@pytest.mark.asyncio
async def test_direct_run_does_not_hydrate_an_unrelated_console_session(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("tactus.core.TactusRuntime", _FakeRuntime)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.InMemoryStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(
            state_set=lambda *_a, **_k: None,
            state_get=lambda *_a, **_k: {},
        ),
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
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("direct run must not construct a durable chat recorder")
        ),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("direct run must not construct a durable trace sink")
        ),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.cloudwatch_logger._create_procedure_cloudwatch_logger",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("direct run must not start CloudWatch transport")
        ),
    )

    result = await _execute_tactus(
        procedure_id="direct-2",
        procedure_source="name: Test\nclass: Tactus\ncode: |\n  return { success = true }\n",
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
        direct_run=True,
    )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_console_tactus_bridges_mcp_tools_into_toolset_registry(monkeypatch):
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

    mcp_client = _FakeMCPClient()
    result = await _execute_tactus(
        procedure_id="builtin:console/chat",
        procedure_source=(
            "name: Console\n"
            "class: Tactus\n"
            "code: |\n"
            "  local function run(input)\n"
            "    return { success = true }\n"
            "  end\n"
            "  return run(input)\n"
        ),
        client=SimpleNamespace(),
        mcp_server=mcp_client,
        context={},
    )

    assert result["success"] is True
    toolset = _FakeRuntime.last_instance.toolset_registry["plexus"]
    assert set(toolset.tools.keys()) == {"plexus_scorecards_list", "plexus_scorecard_info"}

    scorecards_tool = toolset.tools["plexus_scorecards_list"]
    output = await scorecards_tool.function(limit="1")
    assert output == "called plexus_scorecards_list with {'limit': '1'}"
    assert mcp_client.calls == [("plexus_scorecards_list", {"limit": "1"})]


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
async def test_execute_tactus_applies_agent_model_overrides_from_context(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithSourceCapture)
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
        procedure_id="p-model-override",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "agents:\n"
            "  assistant:\n"
            "    model: gpt-5.4-mini\n"
            "    max_tokens: 4096\n"
            "    system_prompt: |\n"
            "      test system prompt\n"
            "    initial_message: Ready.\n"
            "    tools:\n"
            "      - plexus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={"agent_models": {"assistant": "gpt-5-mini"}},
    )

    assert result["success"] is True
    assert _RuntimeWithSourceCapture.last_context["agent_models_applied"] == {
        "assistant": "gpt-5-mini"
    }
    parsed_source = yaml.safe_load(_RuntimeWithSourceCapture.last_source)
    assert parsed_source["agents"]["assistant"]["model"] == "gpt-5-mini"
    assert parsed_source["agents"]["assistant"]["max_tokens"] == 16000


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
async def test_execute_tactus_injects_deterministic_score_edit_audit_block(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _RecordingChatRecorder(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.updated_messages = []
            self.recorded_messages = []

        async def update_message(
            self,
            message_id: str,
            content: str | None = None,
            metadata: dict | None = None,
            human_interaction: str | None = None,
            tool_response: object | None = None,
        ) -> bool:
            self.updated_messages.append(
                {
                    "message_id": message_id,
                    "content": content,
                    "metadata": metadata,
                    "human_interaction": human_interaction,
                    "tool_response": tool_response,
                }
            )
            return True

        async def record_assistant_message(self, content: str):
            self.recorded_messages.append(content)
            return "msg-recorded"

    class _TraceSinkWithAssistant(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.assistant_message_texts = [
                "Done. I made a small scoring tweak.\n\n"
                "New candidate version: `v-1`\n"
                "- **New candidate version:** `v-1`\n"
                "- **New candidate version created:** `v-1`"
            ]
            self._recent_finalized_message_ids = {"assistant": ("msg-streamed", 12.0)}

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
        lambda *_a, **_k: _TraceSinkWithAssistant(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: recorder,
    )

    result = await _execute_tactus(
        procedure_id="builtin:console/chat",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={
            "console_audit_events": [
                {
                    "kind": "score_edit",
                    "success": True,
                    "version_id": "v-1",
                    "parent_version_id": "v-0",
                    "scorecard_id": "sc-1",
                    "score_id": "s-1",
                    "version_url": "/lab/scorecards/sc-1/scores/s-1/versions/v-1",
                    "changed_fields": ["code"],
                    "post_submit_test": {"status": "passed"},
                    "post_submit_verification": {"status": "passed"},
                }
            ]
        },
    )

    assert result["success"] is True
    assert len(recorder.updated_messages) == 1
    update_payload = recorder.updated_messages[0]
    assert update_payload["message_id"] == "msg-streamed"
    assert "**Score edit saved**" in (update_payload["content"] or "")
    assert (
        "[Updated score version](/lab/scorecards/sc-1/scores/s-1/versions/v-1)"
        in (update_payload["content"] or "")
    )
    assert update_payload["metadata"]["score_change_audit"]["version_id"] == "v-1"
    assert update_payload["metadata"]["score_change_audit"]["changed_fields"] == ["code"]
    assert (
        "Updated score version: [`v-1`](/lab/scorecards/sc-1/scores/s-1/versions/v-1)"
        in (update_payload["content"] or "")
    )
    assert (
        "- **Updated score version:** [`v-1`](/lab/scorecards/sc-1/scores/s-1/versions/v-1)"
        in (update_payload["content"] or "")
    )
    assert (
        "- **Updated score version:** "
        "[`v-1`](/lab/scorecards/sc-1/scores/s-1/versions/v-1)"
        in (update_payload["content"] or "")
    )
    assert "candidate version" not in (update_payload["content"] or "").lower()
    assert "Done. I made a small scoring tweak." in (update_payload["content"] or "")
    assert recorder.recorded_messages == []


@pytest.mark.asyncio
async def test_execute_tactus_injects_deterministic_score_edit_audit_from_trace_sink(
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _RecordingChatRecorder(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.updated_messages = []

        async def update_message(
            self,
            message_id: str,
            content: str | None = None,
            metadata: dict | None = None,
            human_interaction: str | None = None,
            tool_response: object | None = None,
        ) -> bool:
            self.updated_messages.append(
                {
                    "message_id": message_id,
                    "content": content,
                    "metadata": metadata,
                    "human_interaction": human_interaction,
                    "tool_response": tool_response,
                }
            )
            return True

        async def record_assistant_message(self, _content: str):
            return "msg-recorded"

    class _TraceSinkWithScoreEditAudit(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.assistant_message_texts = ["Done. I applied your requested score tweak."]
            self._recent_finalized_message_ids = {"assistant": ("msg-streamed", 12.0)}
            self.console_audit_events = [
                {
                    "kind": "score_edit",
                    "success": True,
                    "version_id": "v-2",
                    "parent_version_id": "v-1",
                    "scorecard_id": "sc-2",
                    "score_id": "s-2",
                    "version_url": "/lab/scorecards/sc-2/scores/s-2/versions/v-2",
                    "parent_version_url": "/lab/scorecards/sc-2/scores/s-2/versions/v-1",
                    "changed_fields": ["code"],
                    "post_submit_test": {
                        "status": "passed",
                        "evaluation_id": "ev-2",
                    },
                    "post_submit_verification": {
                        "status": "passed",
                        "validation_id": "val-2",
                    },
                    "push_outcome": "not_pushed",
                    "promoted": False,
                    "diffs": {
                        "code": {
                            "kind": "code",
                            "language": "yaml",
                            "original": "name: old\n",
                            "modified": "name: new\n",
                            "unified_diff": "--- code:previous\n+++ code:updated\n",
                            "has_changes": True,
                        }
                    },
                },
                {
                    "kind": "score_edit",
                    "handle_status": "completed",
                    "version_id": "v-2",
                    "parent_version_id": "v-1",
                    "version_url": "/lab/scorecards/sc-2/scores/s-2/versions/v-2",
                    "parent_version_url": "/lab/scorecards/sc-2/scores/s-2/versions/v-1",
                    "changed_fields": ["code"],
                    "post_submit_test": {"status": "passed"},
                    "post_submit_verification": {"status": "passed"},
                }
            ]

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
        lambda *_a, **_k: _TraceSinkWithScoreEditAudit(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: recorder,
    )

    result = await _execute_tactus(
        procedure_id="builtin:console/chat",
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
    assert len(recorder.updated_messages) == 1
    update_payload = recorder.updated_messages[0]
    assert update_payload["message_id"] == "msg-streamed"
    assert "**Score edit saved**" in (update_payload["content"] or "")
    assert (
        "[Previous score version](/lab/scorecards/sc-2/scores/s-2/versions/v-1)"
        in (update_payload["content"] or "")
    )
    assert (
        "[Updated score version](/lab/scorecards/sc-2/scores/s-2/versions/v-2)"
        in (update_payload["content"] or "")
    )
    assert "- Smoke test: `passed`" in (update_payload["content"] or "")
    assert "- Post-submit verification: `passed`" in (update_payload["content"] or "")
    assert "Done. I applied your requested score tweak." in (update_payload["content"] or "")
    assert update_payload["metadata"]["score_change_audit"]["version_id"] == "v-2"
    assert update_payload["metadata"]["score_change_audit"]["success"] is True
    assert update_payload["metadata"]["score_change_audit"]["diffs"]["code"]["language"] == "yaml"


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
    assert recorder.recorded[0]["content"] == "Hello"
    assert len(recorder.updated) >= 1
    assert recorder.updated[-1]["content"] == "Hello"
    assert recorder.fallback_messages == []


@pytest.mark.asyncio
async def test_execute_tactus_streams_many_chunks_without_loss(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _StreamingRecorder(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.session_id = None
            self.recorded = []
            self.updated = []

        async def start_session(self, _context=None):
            self.session_id = "sess-stream-many"
            return self.session_id

        async def record_message(self, **kwargs):
            self.recorded.append(kwargs)
            return "msg-stream-many"

        async def update_message(self, **kwargs):
            self.updated.append(kwargs)
            return True

        async def record_assistant_message(self, _content: str):
            return "msg-fallback"

    recorder = _StreamingRecorder()

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeStreamingManyChunksWithoutTraceParam)
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
        procedure_id="p-stream-many",
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

    expected = "Streaming bridge should preserve every chunk."
    assert result["success"] is True
    assert len(recorder.recorded) == 1
    assert recorder.recorded[0]["content"] == expected
    assert len(recorder.updated) >= 1
    assert recorder.updated[-1]["content"] == expected


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
async def test_execute_tactus_fails_when_child_budget_cost_is_exceeded(monkeypatch):
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

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeWithCostEvents)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: _StorageWithState(),
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
        procedure_id="p-cost-budget",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={
            "_plexus_child_budget": {
                "usd": 0.001,
                "wallclock_seconds": 30,
                "depth": 1,
                "tool_calls": 4,
            }
        },
    )

    assert result["success"] is False
    assert "child USD budget" in result["error"]


@pytest.mark.asyncio
async def test_execute_tactus_applies_child_depth_budget_to_runtime_source(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _RuntimeCapturesSource(_FakeRuntime):
        last_source = None

        async def execute(self, source, context, format="yaml"):
            self.__class__.last_source = source
            return await super().execute(source, context, format=format)

    monkeypatch.setattr("tactus.core.TactusRuntime", _RuntimeCapturesSource)
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
        procedure_id="p-depth-budget",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={
            "_plexus_child_budget": {
                "usd": 0.1,
                "wallclock_seconds": 30,
                "depth": 2,
                "tool_calls": 4,
            }
        },
    )

    assert result["success"] is True
    assert "max_depth: 2" in _RuntimeCapturesSource.last_source


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


@pytest.mark.asyncio
async def test_execute_tactus_stops_before_runtime_when_task_cancelled(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    completed = []
    failed = []
    advanced = []

    class RuntimeShouldNotExecute(_FakeRuntime):
        async def execute(self, *_args, **_kwargs):
            raise AssertionError("runtime should not execute after dashboard cancellation")

    monkeypatch.setattr("tactus.core.TactusRuntime", RuntimeShouldNotExecute)
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
        "plexus.cli.procedure.procedure_executor._is_dashboard_task_cancelled",
        lambda _client, task_id: task_id == "task-cancelled",
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._advance_task_to_running_stage",
        lambda _client, task_id, target_order=2: advanced.append(task_id),
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
        procedure_id="p-stage-cancelled",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  return { success = true }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context={},
        _task_id_for_stage_tracking="task-cancelled",
    )

    assert result["success"] is False
    assert result["status"] == "CANCELLED"
    assert "task-cancelled" in result["error"]
    assert advanced == []
    assert completed == []
    assert failed == []


def test_scorecard_create_dry_run_skips_approval():
    yaml_path = Path("plexus/procedures/scorecard_create.yaml")
    content = yaml_path.read_text()

    dry_run_index = content.find("if dry_run then")
    approve_index = content.find("local approved = Human.approve")

    assert dry_run_index != -1, "dry-run branch must exist"
    assert approve_index != -1, "approval branch must exist for non-dry-run execution"
    assert dry_run_index < approve_index, "dry-run should return before approval"
