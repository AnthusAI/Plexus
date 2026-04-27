from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from plexus.cli.procedure.lua_dsl.lua_sandbox import LuaSandboxError
from plexus.cli.procedure.lua_dsl.runtime import LuaDSLRuntime


class _DummyPrimitive:
    def __init__(self, *args, **kwargs):
        pass

    async def flush_recordings(self):
        return None

    async def save(self):
        return None


@pytest.mark.asyncio
async def test_runtime_marks_chat_session_failed_when_execution_errors(monkeypatch):
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"
    recorder.session_id = "sess-1"

    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_args, **_kwargs: recorder,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.lua_dsl.runtime.ProcedureYAMLParser.parse",
        lambda _yaml: {
            "name": "Test Procedure",
            "version": "1.0.0",
            "outputs": {},
            "hitl": {},
            "stages": [],
            "agents": {
                "worker": {
                    "system_prompt": "sys",
                    "initial_message": "hello",
                    "tools": [],
                }
            },
            "workflow": "return {}",
        },
    )
    monkeypatch.setattr(
        "plexus.dashboard.api.models.procedure.Procedure.get_by_id",
        lambda *_args, **_kwargs: SimpleNamespace(accountId="acct-1"),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.lua_dsl.runtime.LocalExecutionContext",
        lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.lua_dsl.runtime.LuaDSLRuntime._initialize_primitives",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.lua_dsl.runtime.LuaDSLRuntime._setup_agents",
        AsyncMock(side_effect=LuaSandboxError("synthetic runtime failure")),
    )

    for symbol in (
        "HumanPrimitive",
        "SystemPrimitive",
        "StepPrimitive",
        "CheckpointPrimitive",
        "LogPrimitive",
        "SessionPrimitive",
        "StagePrimitive",
        "JsonPrimitive",
        "RetryPrimitive",
        "FilePrimitive",
        "ProcedurePrimitive",
    ):
        monkeypatch.setattr(f"plexus.cli.procedure.lua_dsl.runtime.{symbol}", _DummyPrimitive)

    runtime = LuaDSLRuntime(
        procedure_id="proc-123",
        client=SimpleNamespace(),
        mcp_server=None,
        openai_api_key="test-key",
    )

    result = await runtime.execute("ignored")

    assert result["success"] is False
    assert "Lua execution error" in result["error"]
    recorder.end_session.assert_awaited_once_with(status="FAILED")
