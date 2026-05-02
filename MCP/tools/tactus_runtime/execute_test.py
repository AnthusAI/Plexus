"""Tests for the execute_tactus MCP prototype."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any

import pytest
from fastmcp import FastMCP

from . import execute

pytestmark = pytest.mark.unit


class _RecordingTraceStore(execute.TactusTraceStore):
    def __init__(self) -> None:
        self.records: list[dict] = []

    def write(self, record: dict) -> str:
        self.records.append(record)
        return f"memory://{record['trace_id']}"


class _MemoryHandleStore(execute.TactusHandleStore):
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}
        self.created: list[dict] = []

    def create(
        self,
        *,
        kind: str,
        parent_trace_id: str,
        api_call: str,
        args: dict,
        dispatch_result: dict,
        child_budget: dict | None = None,
    ) -> dict:
        handle_id = f"handle-{len(self.records) + 1}"
        record = {
            "id": handle_id,
            "kind": kind,
            "status": "running",
            "status_url": dispatch_result.get("dashboard_url"),
            "created_at": "2026-04-29T00:00:00Z",
            "updated_at": "2026-04-29T00:00:00Z",
            "parent_trace_id": parent_trace_id,
            "api_call": api_call,
            "args": args,
            "dispatch_result": dispatch_result,
            "child_budget": child_budget,
        }
        self.records[handle_id] = record
        self.created.append(record)
        public = {
            "id": handle_id,
            "kind": kind,
            "status": "running",
            "status_url": dispatch_result.get("dashboard_url"),
            "created_at": record["created_at"],
            "parent_trace_id": parent_trace_id,
        }
        if child_budget is not None:
            public["child_budget"] = child_budget
        return public

    def get(self, handle_id: str) -> dict:
        return dict(self.records[handle_id])

    def update(self, handle_id: str, updates: dict) -> dict:
        self.records[handle_id].update(updates)
        return dict(self.records[handle_id])


class _RecordingMCPContext:
    def __init__(self) -> None:
        self.progress: list[dict] = []
        self.info_messages: list[dict] = []

    async def report_progress(self, progress, total=None, message=None):
        self.progress.append(
            {"progress": progress, "total": total, "message": message}
        )

    async def info(self, message, logger_name=None, extra=None):
        self.info_messages.append(
            {"message": message, "logger_name": logger_name, "extra": extra}
        )


class _FailingMCPContext:
    async def report_progress(self, progress, total=None, message=None):
        raise ImportError("progress transport unavailable")

    async def info(self, message, logger_name=None, extra=None):
        raise RuntimeError("info transport unavailable")


def _child_budget() -> dict:
    return {"usd": 0.01, "wallclock_seconds": 10, "depth": 1, "tool_calls": 2}


def test_wrap_tactus_snippet_injects_plexus_helpers_and_capture() -> None:
    wrapped = execute._wrap_tactus_snippet(
        'evaluate{ score_id = "score_compliance_tone", item_count = 200 }'
    )

    assert 'local plexus = require("plexus")' in wrapped
    assert "function evaluate(args)" in wrapped
    assert "function scorecards_list(args)" in wrapped
    assert "function scorecards(args)" in wrapped
    assert "function scorecard(args)" in wrapped
    assert "function evaluation_info(args)" in wrapped
    assert "function report_configs(args)" in wrapped
    assert "function procedures(args)" in wrapped
    assert "function handle_status(args)" in wrapped
    assert "function docs_get(args)" in wrapped
    assert "function api_list(args)" in wrapped
    assert "return __plexus_last_result" in wrapped
    assert "__execute_tactus_user_snippet" in wrapped


def test_helper_bindings_cover_advertised_runtime_api_surface() -> None:
    facade = execute.PlexusRuntimeModule(FastMCP("test"))
    catalog = facade.api.list()
    helpers = {helper_name for helper_name, _, _ in execute.HELPER_BINDINGS}

    expected_helpers = {
        f"{namespace.removeprefix('plexus.')}_{method}"
        for namespace, methods in catalog.items()
        for method in methods
    }

    assert len(helpers) == len([binding[0] for binding in execute.HELPER_BINDINGS])
    assert expected_helpers <= helpers


def test_plexus_facade_delegates_score_info_call_to_direct_handler() -> None:
    """plexus.score.info must go through DIRECT_HANDLERS, not MCP loopback."""

    class FakeMCP:
        def __init__(self) -> None:
            self.calls: list = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            raise AssertionError(
                "score.info must not loop back through MCP; "
                f"got {name!r} with {arguments!r}"
            )

    info_args: list = []

    def fake_info(args):
        info_args.append(args)
        return {"id": args.get("id"), "name": "Compliance Tone"}

    fake_mcp = FakeMCP()
    facade = execute.PlexusRuntimeModule(fake_mcp, score_info=fake_info)

    value = facade.score.info({"id": "score_compliance_tone"})

    assert value == {"id": "score_compliance_tone", "name": "Compliance Tone"}
    assert info_args == [{"id": "score_compliance_tone"}]
    assert fake_mcp.calls == []
    assert facade.api_calls == ["plexus.score.info"]


def test_plexus_facade_uses_direct_scorecards_handler_without_mcp_loopback() -> None:
    """plexus.scorecards.list/info must go through DIRECT_HANDLERS, not MCP loopback."""

    class FakeMCP:
        def __init__(self) -> None:
            self.calls: list = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            raise AssertionError(
                "scorecards.* must not loop back through MCP; got "
                f"{name!r} with {arguments!r}"
            )

    list_args: list = []
    info_args: list = []

    def fake_list(args):
        list_args.append(args)
        return [{"id": "card-1", "name": "HCS Medium Risk"}]

    def fake_info(args):
        info_args.append(args)
        return {
            "name": "HCS Medium Risk",
            "key": "hcs_medium_risk",
            "externalId": "ext-1",
            "description": None,
            "guidelines": None,
            "additionalDetails": {
                "id": "card-1",
                "createdAt": None,
                "updatedAt": None,
            },
            "sections": None,
        }

    fake_mcp = FakeMCP()
    facade = execute.PlexusRuntimeModule(
        fake_mcp,
        scorecards_lister=fake_list,
        scorecards_infoer=fake_info,
    )

    listed = facade.scorecards.list({"identifier": "hcs"})
    info = facade.scorecards.info({"id": "card-1"})

    assert listed == [{"id": "card-1", "name": "HCS Medium Risk"}]
    assert info["key"] == "hcs_medium_risk"
    assert list_args == [{"identifier": "hcs"}]
    assert info_args == [{"id": "card-1"}]
    assert fake_mcp.calls == []
    assert facade.api_calls == ["plexus.scorecards.list", "plexus.scorecards.info"]


def test_dispatch_routes_scorecards_to_direct_handlers() -> None:
    assert execute.DIRECT_HANDLERS[("scorecards", "list")] == "_call_scorecards"
    assert execute.DIRECT_HANDLERS[("scorecards", "info")] == "_call_scorecards"
    assert ("scorecards", "list") not in execute.MCP_TOOL_MAP
    assert ("scorecards", "info") not in execute.MCP_TOOL_MAP


def test_dispatch_routes_score_to_direct_handlers() -> None:
    for method in ("info", "evaluations", "predict", "set_champion"):
        assert execute.DIRECT_HANDLERS[("score", method)] == "_call_score"
        assert ("score", method) not in execute.MCP_TOOL_MAP


def test_dispatch_routes_procedure_reads_to_direct_handlers() -> None:
    for method in ("list", "info", "chat_sessions", "chat_messages", "steering_messages"):
        assert execute.DIRECT_HANDLERS[("procedure", method)] == "_call_procedure_read"
        assert ("procedure", method) not in execute.MCP_TOOL_MAP


def test_plexus_facade_uses_direct_procedure_handlers_without_mcp_loopback(
    monkeypatch,
) -> None:
    """plexus.procedure read methods must NOT loop back."""

    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "call-criteria")

    class FakeMCP:
        async def call_tool(self, name, arguments):
            raise AssertionError(
                f"procedure.* must not loop back through MCP: {name!r}"
            )

    received: list[tuple[str, dict[str, Any]]] = []

    def make_reader(method):
        def reader(args):
            received.append((method, args))
            return {"success": True, "method": method, "args": args}

        return reader

    facade = execute.PlexusRuntimeModule(
        FakeMCP(),
        procedure_listers={
            "list": make_reader("list"),
            "info": make_reader("info"),
            "chat_sessions": make_reader("chat_sessions"),
            "chat_messages": make_reader("chat_messages"),
            "steering_messages": make_reader("steering_messages"),
        },
    )

    facade.procedure.list({"limit": 3})
    facade.procedure.info({"id": "proc-1"})
    facade.procedure.chat_sessions({"id": "proc-1", "limit": 2})
    facade.procedure.chat_messages({"id": "proc-1", "session_id": "session-1"})
    facade.procedure.steering_messages({"id": "proc-1", "agent_name": "report_writer"})

    assert [m for m, _ in received] == [
        "list",
        "info",
        "chat_sessions",
        "chat_messages",
        "steering_messages",
    ]
    assert facade.api_calls == [
        "plexus.procedure.list",
        "plexus.procedure.info",
        "plexus.procedure.chat_sessions",
        "plexus.procedure.chat_messages",
        "plexus.procedure.steering_messages",
    ]


def test_extract_tool_value_parses_structured_json_string() -> None:
    result = SimpleNamespace(structured_content='{"id": "score-1", "name": "Score"}')

    assert execute._extract_tool_value(result) == {"id": "score-1", "name": "Score"}


def test_extract_tool_value_parses_result_json_string() -> None:
    result = SimpleNamespace(
        structured_content={"result": '{"id": "score-1", "name": "Score"}'}
    )

    assert execute._extract_tool_value(result) == {"id": "score-1", "name": "Score"}


def test_plexus_docs_get_reads_filesystem_directly(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "score-yaml-format.md").write_text("# Score docs", encoding="utf-8")

    class FakeMCP:
        def __init__(self) -> None:
            self.calls = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            raise AssertionError("plexus.docs.get must not call MCP tools")

    fake_mcp = FakeMCP()
    facade = execute.PlexusRuntimeModule(fake_mcp, docs_dir=str(docs_dir))

    value = facade.docs.get({"key": "score-yaml-format"})

    assert value == {"key": "score-yaml-format", "content": "# Score docs"}
    assert fake_mcp.calls == []
    assert facade.api_calls == ["plexus.docs.get"]


def test_structured_error_extracts_tactus_line_number() -> None:
    first_user_line = 5 + (3 * len(execute.HELPER_BINDINGS)) + 1 + 1
    error = execute._structured_error(
        "tactus_execution_failed",
        f'[string "<python>"]:{first_user_line}: unexpected symbol near "}}"',
    )

    assert error["code"] == "tactus_execution_failed"
    assert error["tactus_lineno"] == 1


@pytest.mark.asyncio
async def test_execute_tactus_tool_schema_uses_tactus_parameter() -> None:
    mcp = FastMCP("test-execute-tactus")
    execute.register_tactus_tools(mcp)

    tools = await mcp.list_tools()
    tool = next(tool for tool in tools if tool.name == "execute_tactus")
    schema = tool.parameters

    assert "tactus" in schema["properties"]
    assert "lua" not in schema["properties"]
    assert "code" not in schema["properties"]
    assert schema["required"] == ["tactus"]


@pytest.mark.asyncio
async def test_execute_tactus_tool_description_contains_curated_examples() -> None:
    mcp = FastMCP("test-execute-tactus")
    execute.register_tactus_tools(mcp)

    tools = await mcp.list_tools()
    tool = next(tool for tool in tools if tool.name == "execute_tactus")
    description = tool.description or ""

    for term in (
        "execute_tactus",
        "plexus.docs.get",
        "api_list()",
        "docs_list()",
        "docs_get",
        "evaluate{",
        "predict{",
        "scorecards{",
        "item{",
        "handle_status",
        "handle_await",
        "handle_cancel",
        "async = true",
        "budget = {",
        "usd",
        "wallclock_seconds",
        "depth",
        "tool_calls",
        "Human.approve",
    ):
        assert term in description, f"description missing curated term: {term!r}"


def test_execute_tactus_description_constant_includes_themed_doc_pointers() -> None:
    description = execute.EXECUTE_TACTUS_DESCRIPTION

    for theme in (
        "overview",
        "discovery",
        "read-apis",
        "long-running-apis",
        "handles-and-budgets",
        "score-and-dataset-authoring/",
        "evaluation-and-feedback/",
        "procedures/",
        "reports/",
    ):
        assert theme in description, (
            f"tool description should reference theme {theme!r}"
        )


@pytest.mark.asyncio
async def test_execute_tactus_streams_runtime_events_to_mcp_context(
    monkeypatch,
) -> None:
    ctx = _RecordingMCPContext()

    def fake_run_tactus_sync(
        tactus,
        mcp,
        *,
        trace_id,
        trace_store,
        stream_handler=None,
        budget=None,
        **kwargs,
    ):
        assert stream_handler is not None
        stream_handler.emit(
            kind="execution",
            message="runtime started",
            payload={"stage": "started"},
            progress=0,
            total=1,
        )
        stream_handler.log(
            {
                "event_type": "agent_turn",
                "agent_name": "worker",
                "stage": "started",
            }
        )
        stream_handler.api_call("plexus.docs.list")
        stream_handler.emit(
            kind="execution",
            message="runtime completed",
            payload={"stage": "completed"},
            progress=1,
            total=1,
        )
        return {
            "ok": True,
            "value": {"ok": True, "source": tactus},
            "error": None,
            "cost": {
                "usd": 0.0,
                "wallclock_seconds": 0.01,
                "tokens": 0,
                "llm_calls": 0,
                "tool_calls": 1,
                "workers": 0,
                "depth_max_observed": 0,
            },
            "trace_id": trace_id,
            "partial": False,
            "api_calls": ["plexus.docs.list"],
        }

    monkeypatch.setattr(execute, "_run_tactus_sync", fake_run_tactus_sync)

    result = await execute._execute_tactus_tool(
        'plexus.docs.list{}',
        FastMCP("test-streaming"),
        ctx=ctx,
    )

    assert result["ok"] is True
    assert [item["message"] for item in ctx.progress] == [
        "runtime started",
        "Calling plexus.docs.list",
        "runtime completed",
    ]
    messages = [item["message"] for item in ctx.info_messages]
    assert "worker started" in messages
    assert "Calling plexus.docs.list" in messages
    streamed_event = next(
        item["extra"]["event"]
        for item in ctx.info_messages
        if item["message"] == "Calling plexus.docs.list"
    )
    assert streamed_event["kind"] == "api_call"
    assert streamed_event["payload"] == {"api_call": "plexus.docs.list"}


@pytest.mark.asyncio
async def test_execute_tactus_ignores_failed_mcp_stream_transport(
    monkeypatch,
) -> None:
    def fake_run_tactus_sync(
        tactus,
        mcp,
        *,
        trace_id,
        trace_store,
        stream_handler=None,
        budget=None,
        **kwargs,
    ):
        assert stream_handler is not None
        stream_handler.emit(
            kind="execution",
            message="runtime started",
            payload={"stage": "started"},
            progress=0,
            total=1,
        )
        return {
            "ok": True,
            "value": {"ok": True, "source": tactus},
            "error": None,
            "cost": {
                "usd": 0.0,
                "wallclock_seconds": 0.01,
                "tokens": 0,
                "llm_calls": 0,
                "tool_calls": 0,
                "workers": 0,
                "depth_max_observed": 0,
            },
            "trace_id": trace_id,
            "partial": False,
            "api_calls": [],
        }

    monkeypatch.setattr(execute, "_run_tactus_sync", fake_run_tactus_sync)

    result = await execute._execute_tactus_tool(
        "return { ok = true }",
        FastMCP("test-failing-stream-context"),
        ctx=_FailingMCPContext(),
    )

    assert result["ok"] is True


def test_stream_event_payload_falls_back_when_model_dump_json_fails() -> None:
    class FakeLuaTable:
        def items(self):
            return [(1, "a"), (2, "b")]

    class FakeEvent:
        event_type = "execution_summary"
        result = FakeLuaTable()

        def model_dump(self, mode):
            if mode == "json":
                raise ValueError("cannot serialize Lua table")
            return {"event_type": self.event_type, "result": self.result}

    assert execute._stream_event_payload(FakeEvent()) == {
        "event_type": "execution_summary",
        "result": ["a", "b"],
    }


@pytest.mark.asyncio
async def test_execute_tactus_tool_returns_structured_contract(monkeypatch) -> None:
    mcp = FastMCP("test-execute-tactus")
    execute.register_tactus_tools(mcp)

    def fake_run_tactus_sync(
        tactus, mcp, *, trace_id, trace_store, budget=None, **kwargs
    ):
        return {
            "ok": True,
            "value": {"ok": True, "source": tactus},
            "error": None,
            "cost": {
                "usd": 0.0,
                "wallclock_seconds": 0.01,
                "tokens": 0,
                "llm_calls": 0,
                "tool_calls": 1,
                "workers": 0,
                "depth_max_observed": 0,
            },
            "trace_id": trace_id,
            "partial": False,
            "api_calls": ["plexus.api.list"],
        }

    monkeypatch.setattr(execute, "_run_tactus_sync", fake_run_tactus_sync)

    result = await mcp.call_tool("execute_tactus", {"tactus": "return { ok = true }"})

    structured = result.structured_content
    assert structured["ok"] is True
    assert structured["value"] == {"ok": True, "source": "return { ok = true }"}
    assert structured["error"] is None
    assert structured["cost"]["tool_calls"] == 1
    assert isinstance(structured["trace_id"], str) and structured["trace_id"]
    assert structured["partial"] is False
    assert structured["api_calls"] == ["plexus.api.list"]


@pytest.mark.asyncio
async def test_execute_tactus_reports_missing_host_module_runtime_contract(
    monkeypatch,
) -> None:
    def fake_run_tactus_sync(
        tactus, mcp, *, trace_id, trace_store, budget=None, **kwargs
    ):
        raise RuntimeError(
            "execute_tactus requires TactusRuntime.register_python_module"
        )

    monkeypatch.setattr(execute, "_run_tactus_sync", fake_run_tactus_sync)

    result = await execute._execute_tactus_tool("return { ok = true }", FastMCP("test"))

    assert result["ok"] is False
    assert result["value"] is None
    assert result["error"]["code"] == "runtime_error"
    assert "register_python_module" in result["error"]["message"]


@pytest.mark.asyncio
async def test_execute_tactus_runs_helper_call_through_host_module() -> None:
    mcp = FastMCP("test-execute-tactus-runtime")

    def fake_score_info(args):
        return {"id": args.get("id"), "name": "Compliance Tone"}

    result = await execute._execute_tactus_tool(
        'score{ id = "score_compliance_tone" }',
        mcp,
        score_info=fake_score_info,
    )

    assert result["value"] == {
        "id": "score_compliance_tone",
        "name": "Compliance Tone",
    }
    assert result["ok"] is True
    assert result["error"] is None
    assert result["api_calls"] == ["plexus.score.info"]
    assert result["cost"]["tool_calls"] == 1


@pytest.mark.asyncio
async def test_execute_tactus_runs_canonical_helper_call_through_host_module() -> None:
    mcp = FastMCP("test-execute-tactus-canonical-helper")

    def fake_score_info(args):
        return {"id": args.get("id"), "name": "Compliance Tone"}

    result = await execute._execute_tactus_tool(
        'score_info{ id = "score_compliance_tone" }',
        mcp,
        score_info=fake_score_info,
    )

    assert result["value"] == {
        "id": "score_compliance_tone",
        "name": "Compliance Tone",
    }
    assert result["ok"] is True
    assert result["api_calls"] == ["plexus.score.info"]


@pytest.mark.asyncio
async def test_execute_tactus_reports_invalid_request_as_structured_error() -> None:
    result = await execute._execute_tactus_tool("", FastMCP("test"))

    assert result["ok"] is False
    assert result["value"] is None
    assert result["error"]["code"] == "invalid_request"
    assert result["partial"] is False
    assert result["cost"]["tool_calls"] == 0


@pytest.mark.asyncio
async def test_execute_tactus_reports_tactus_syntax_error_as_structured_error() -> None:
    mcp = FastMCP("test-execute-tactus-syntax")

    result = await execute._execute_tactus_tool("local x =", mcp)

    assert result["ok"] is False
    assert result["error"] is not None
    assert result["error"]["code"] == "tactus_execution_failed"
    assert "trace_id" in result
    assert result["cost"]["tool_calls"] == 0


def test_plexus_facade_rejects_unsupported_namespace_method() -> None:
    facade = execute.PlexusRuntimeModule(FastMCP("test"))

    with pytest.raises(ValueError, match="Unsupported Plexus runtime API"):
        facade._call("score", "no_such_method", {"id": "x"})


def test_plexus_api_list_advertises_known_namespaces() -> None:
    facade = execute.PlexusRuntimeModule(FastMCP("test"))

    catalog = facade.api.list()

    assert "plexus.docs" in catalog
    assert "plexus.api" in catalog
    assert "plexus.score" in catalog
    assert "info" in catalog["plexus.score"]
    assert facade.api_calls == ["plexus.api.list"]


@pytest.mark.asyncio
async def test_execute_tactus_docs_list_and_get_use_filesystem_directly(
    tmp_path,
) -> None:
    mcp = FastMCP("test-execute-tactus-docs")

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "score-yaml-format.md").write_text("# Score YAML\n")
    (docs_dir / "feedback-alignment.md").write_text("# Feedback Alignment\n")
    (docs_dir / "README.md").write_text("# index\n")

    original_docs_dir = execute.PLEXUS_DOCS_DIR
    execute.PLEXUS_DOCS_DIR = str(docs_dir)
    try:
        list_result = await execute._execute_tactus_tool(
            "return plexus.docs.list()",
            mcp,
        )

        assert list_result["ok"] is True
        assert list_result["value"] == ["feedback-alignment", "score-yaml-format"]
        assert list_result["api_calls"] == ["plexus.docs.list"]

        get_result = await execute._execute_tactus_tool(
            'return plexus.docs.get{ key = "score-yaml-format" }',
            mcp,
        )

        assert get_result["ok"] is True
        assert get_result["value"] == {
            "key": "score-yaml-format",
            "content": "# Score YAML\n",
        }
        assert get_result["api_calls"] == ["plexus.docs.get"]
        assert get_result["cost"]["tool_calls"] == 1
    finally:
        execute.PLEXUS_DOCS_DIR = original_docs_dir


def test_plexus_runtime_module_docs_get_rejects_unsafe_keys(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "ok.md").write_text("ok")

    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=str(docs_dir))

    with pytest.raises(ValueError, match="Invalid plexus.docs key"):
        module._docs_read("../etc/passwd")
    with pytest.raises(ValueError, match="Invalid plexus.docs key"):
        module._docs_read("")
    with pytest.raises(ValueError, match="Invalid plexus.docs key"):
        module._docs_read("/etc/passwd")
    with pytest.raises(ValueError, match="Invalid plexus.docs key"):
        module._docs_read("evaluation/../../etc/passwd")
    with pytest.raises(FileNotFoundError):
        module._docs_read("missing")


def test_plexus_runtime_module_docs_list_excludes_readme(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "alpha.md").write_text("a")
    (docs_dir / "beta.md").write_text("b")
    (docs_dir / "README.md").write_text("readme")
    (docs_dir / "notes.txt").write_text("ignored")

    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=str(docs_dir))

    assert module._docs_list() == ["alpha", "beta"]


def test_plexus_runtime_module_docs_list_returns_nested_keys(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    (docs_dir / "evaluation-and-feedback").mkdir(parents=True)
    (docs_dir / "score-and-dataset-authoring").mkdir(parents=True)
    (docs_dir / "overview.md").write_text("overview")
    (docs_dir / "evaluation-and-feedback" / "feedback-alignment.md").write_text(
        "feedback"
    )
    (docs_dir / "evaluation-and-feedback" / "README.md").write_text("theme readme")
    (docs_dir / "score-and-dataset-authoring" / "score-yaml-format.md").write_text(
        "score"
    )
    (docs_dir / "README.md").write_text("top readme")

    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=str(docs_dir))

    assert module._docs_list() == [
        "evaluation-and-feedback/feedback-alignment",
        "overview",
        "score-and-dataset-authoring/score-yaml-format",
    ]


def test_plexus_runtime_module_docs_read_resolves_nested_key(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    (docs_dir / "evaluation-and-feedback").mkdir(parents=True)
    (docs_dir / "evaluation-and-feedback" / "feedback-alignment.md").write_text(
        "nested-content"
    )

    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=str(docs_dir))

    assert (
        module._docs_read("evaluation-and-feedback/feedback-alignment")
        == "nested-content"
    )


def test_plexus_runtime_module_docs_read_legacy_stem_fallback(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    (docs_dir / "evaluation-and-feedback").mkdir(parents=True)
    (docs_dir / "evaluation-and-feedback" / "feedback-alignment.md").write_text(
        "legacy-stem-resolves"
    )

    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=str(docs_dir))

    assert module._docs_read("feedback-alignment") == "legacy-stem-resolves"


def test_plexus_runtime_module_docs_read_legacy_fallback_skips_readme(
    tmp_path,
) -> None:
    docs_dir = tmp_path / "docs"
    (docs_dir / "procedures").mkdir(parents=True)
    (docs_dir / "procedures" / "README.md").write_text("theme readme")

    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=str(docs_dir))

    with pytest.raises(FileNotFoundError):
        module._docs_read("README")
    with pytest.raises(FileNotFoundError):
        module._docs_read("readme")


def test_plexus_docs_repository_layout_exposes_themed_keys() -> None:
    docs_dir = execute.PLEXUS_DOCS_DIR
    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=docs_dir)

    keys = module._docs_list()

    assert "overview" in keys
    assert "discovery" in keys
    assert "read-apis" in keys
    assert "long-running-apis" in keys
    assert "handles-and-budgets" in keys
    assert "evaluation-and-feedback/feedback-alignment" in keys
    assert "score-and-dataset-authoring/score-yaml-format" in keys
    assert all(not key.endswith("/README") for key in keys)
    assert all(not key.endswith("readme") for key in keys)

    legacy = module._docs_read("feedback-alignment")
    assert "Feedback Alignment" in legacy or "feedback-alignment" in legacy.lower()

    nested = module._docs_read(
        "evaluation-and-feedback/feedback-alignment"
    )
    assert nested == legacy

    overview = module._docs_read("overview")
    assert "execute_tactus" in overview
    assert "docs.list" in overview or "docs_list" in overview


@pytest.mark.asyncio
async def test_execute_tactus_implicit_last_helper_result_is_returned() -> None:
    mcp = FastMCP("test-execute-tactus-implicit")

    def fake_score_info(args):
        return {"id": args.get("id"), "name": "Implicit"}

    result = await execute._execute_tactus_tool(
        'score{ id = "score_implicit" }',
        mcp,
        score_info=fake_score_info,
    )

    assert result["ok"] is True
    assert result["value"] == {"id": "score_implicit", "name": "Implicit"}


@pytest.mark.asyncio
async def test_execute_tactus_explicit_return_overrides_helper_capture() -> None:
    mcp = FastMCP("test-execute-tactus-explicit")

    def fake_score_info(args):
        return {"id": args.get("id"), "name": "Captured"}

    result = await execute._execute_tactus_tool(
        'score{ id = "score_captured" }\nreturn { override = true }',
        mcp,
        score_info=fake_score_info,
    )

    assert result["ok"] is True
    assert result["value"] == {"override": True}
    assert result["api_calls"] == ["plexus.score.info"]


@pytest.mark.asyncio
async def test_execute_tactus_writes_trace_for_successful_run() -> None:
    mcp = FastMCP("test-execute-tactus-trace-success")

    def fake_score_info(args):
        return {"id": args.get("id"), "name": "Trace"}

    store = _RecordingTraceStore()
    result = await execute._execute_tactus_tool(
        'score{ id = "score_trace" }',
        mcp,
        trace_store=store,
        score_info=fake_score_info,
    )

    assert result["ok"] is True
    assert len(store.records) == 1
    record = store.records[0]
    assert record["trace_id"] == result["trace_id"]
    assert record["ok"] is True
    assert record["api_calls"] == ["plexus.score.info"]
    assert record["submitted_tactus"] == 'score{ id = "score_trace" }'
    assert 'local plexus = require("plexus")' in record["wrapped_tactus"]
    assert record["error"] is None
    assert record["cost"]["tool_calls"] == 1
    assert record["partial"] is False
    assert "duration_ms" in record
    assert record["started_at"].endswith("Z")
    assert record["ended_at"].endswith("Z")


@pytest.mark.asyncio
async def test_execute_tactus_writes_trace_for_syntax_error() -> None:
    store = _RecordingTraceStore()
    result = await execute._execute_tactus_tool(
        "local x =",
        FastMCP("test-execute-tactus-trace-syntax"),
        trace_store=store,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "tactus_execution_failed"
    assert len(store.records) == 1
    record = store.records[0]
    assert record["trace_id"] == result["trace_id"]
    assert record["ok"] is False
    assert record["error"]["code"] == "tactus_execution_failed"
    assert record["submitted_tactus"] == "local x ="
    assert record["wrapped_tactus"] is not None
    assert record["tactus_runtime_result"] is not None


@pytest.mark.asyncio
async def test_execute_tactus_writes_trace_for_invalid_request() -> None:
    store = _RecordingTraceStore()
    result = await execute._execute_tactus_tool("", FastMCP("test"), trace_store=store)

    assert result["ok"] is False
    assert len(store.records) == 1
    record = store.records[0]
    assert record["trace_id"] == result["trace_id"]
    assert record["error"]["code"] == "invalid_request"
    assert record["wrapped_tactus"] is None


@pytest.mark.asyncio
async def test_execute_tactus_writes_trace_for_runtime_error(monkeypatch) -> None:
    store = _RecordingTraceStore()

    def fake_run_tactus_sync(
        tactus, mcp, *, trace_id, trace_store, budget=None, **kwargs
    ):
        raise RuntimeError("boom")

    monkeypatch.setattr(execute, "_run_tactus_sync", fake_run_tactus_sync)

    result = await execute._execute_tactus_tool(
        "return 1", FastMCP("test"), trace_store=store
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "runtime_error"
    assert len(store.records) == 1
    record = store.records[0]
    assert record["trace_id"] == result["trace_id"]
    assert record["error"]["code"] == "runtime_error"


def test_file_trace_store_writes_json_file_per_trace(tmp_path) -> None:
    store = execute.FileTactusTraceStore(str(tmp_path / "traces"))
    record = {
        "trace_id": "abc-123",
        "ok": True,
        "api_calls": ["plexus.api.list"],
        "value": {"hello": "world"},
        "started_at": "2026-04-29T00:00:00Z",
        "ended_at": "2026-04-29T00:00:00Z",
        "duration_ms": 0,
        "error": None,
        "cost": {"usd": 0.0},
        "partial": False,
        "submitted_tactus": "return 1",
        "wrapped_tactus": "wrapped",
        "tactus_runtime_result": None,
    }

    path = store.write(record)

    assert os.path.isfile(path)
    with open(path, "r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    assert loaded == record


def test_default_trace_store_honours_env_override(monkeypatch, tmp_path) -> None:
    target = tmp_path / "custom-traces"
    monkeypatch.setenv("PLEXUS_TACTUS_TRACE_DIR", str(target))

    store = execute._default_trace_store()

    assert isinstance(store, execute.FileTactusTraceStore)
    assert store.directory == str(target)


def test_default_budget_spec_uses_initiative_defaults() -> None:
    spec = execute.BudgetSpec()

    assert spec.usd == execute.DEFAULT_BUDGET_USD == 0.25
    assert spec.wallclock_seconds == execute.DEFAULT_BUDGET_WALLCLOCK_SECONDS == 60.0
    assert spec.depth == execute.DEFAULT_BUDGET_DEPTH == 3
    assert spec.tool_calls == execute.DEFAULT_BUDGET_TOOL_CALLS


def test_budget_gate_trips_on_tool_call_count() -> None:
    gate = execute.BudgetGate(execute.BudgetSpec(tool_calls=2))

    gate.check_before("api", "list")
    gate.record_after("api", "list")
    gate.check_before("api", "list")
    gate.record_after("api", "list")

    with pytest.raises(execute.BudgetExceeded, match="tool_calls budget exceeded"):
        gate.check_before("api", "list")
    assert gate.exceeded is True
    assert "tool_calls" in (gate.exceeded_reason or "")


def test_budget_gate_trips_on_wallclock() -> None:
    fake_now = [0.0]

    def clock() -> float:
        return fake_now[0]

    gate = execute.BudgetGate(execute.BudgetSpec(wallclock_seconds=1.0), clock=clock)

    gate.check_before("api", "list")
    gate.record_after("api", "list")

    fake_now[0] = 2.5

    with pytest.raises(execute.BudgetExceeded, match="wallclock budget exceeded"):
        gate.check_before("api", "list")
    assert gate.exceeded is True


def test_plexus_runtime_module_records_tool_call_against_budget(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "alpha.md").write_text("a", encoding="utf-8")

    gate = execute.BudgetGate()
    module = execute.PlexusRuntimeModule(
        FastMCP("test"), docs_dir=str(docs_dir), budget=gate
    )

    module.docs.list({})
    module.docs.get({"key": "alpha"})

    assert gate.tool_calls == 2
    assert gate.exceeded is False


def test_plexus_runtime_module_blocks_call_when_budget_already_exceeded(
    tmp_path,
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "alpha.md").write_text("a", encoding="utf-8")

    gate = execute.BudgetGate(execute.BudgetSpec(tool_calls=1))
    module = execute.PlexusRuntimeModule(
        FastMCP("test"), docs_dir=str(docs_dir), budget=gate
    )

    module.docs.list({})
    with pytest.raises(execute.BudgetExceeded):
        module.docs.list({})


@pytest.mark.asyncio
async def test_execute_tactus_returns_budget_exceeded_when_tool_calls_overrun() -> None:
    mcp = FastMCP("test-execute-tactus-budget")

    tight_budget = execute.BudgetGate(execute.BudgetSpec(tool_calls=1))
    store = _RecordingTraceStore()

    result = await execute._execute_tactus_tool(
        "plexus.api.list()\nplexus.api.list()\nreturn 'never'",
        mcp,
        trace_store=store,
        budget=tight_budget,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "budget_exceeded"
    assert result["api_calls"] == ["plexus.api.list"]
    assert result["cost"]["tool_calls"] == 1
    assert result["cost"]["budget_remaining_tool_calls"] == 0
    assert len(store.records) == 1
    assert store.records[0]["error"]["code"] == "budget_exceeded"


def test_long_running_methods_constant_lists_run_apis() -> None:
    assert ("evaluation", "run") not in execute.LONG_RUNNING_METHODS
    assert ("evaluation", "run") in execute.DIRECT_HANDLERS
    assert ("report", "run") not in execute.LONG_RUNNING_METHODS
    assert ("report", "run") in execute.DIRECT_HANDLERS
    assert ("procedure", "run") not in execute.LONG_RUNNING_METHODS
    assert ("procedure", "run") in execute.DIRECT_HANDLERS


def test_plexus_runtime_module_requires_async_for_evaluation_run() -> None:
    class FakeMCP:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            raise AssertionError(
                "long-running calls must not loop back through MCP in v0"
            )

    fake_mcp = FakeMCP()
    module = execute.PlexusRuntimeModule(fake_mcp)

    with pytest.raises(execute.RequiresHandleProtocol):
        module.evaluation.run({"scorecard_name": "x"})

    assert module.handle_protocol_required == ("evaluation", "run")
    assert module.api_calls == ["plexus.evaluation.run"]
    assert fake_mcp.calls == []


@pytest.mark.asyncio
async def test_execute_tactus_returns_requires_handle_protocol_for_blocking_run() -> (
    None
):
    mcp = FastMCP("test-execute-tactus-handle")

    @mcp.tool()
    def plexus_evaluation_run(scorecard_name: str):  # pragma: no cover - must not run
        raise AssertionError("MCP-loopback long-running run should be blocked in v0")

    store = _RecordingTraceStore()
    result = await execute._execute_tactus_tool(
        'evaluate{ scorecard_name = "x", item_count = 1 }',
        mcp,
        trace_store=store,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "requires_handle_protocol"
    assert "evaluation.run" in result["error"]["message"]
    assert result["api_calls"] == ["plexus.evaluation.run"]
    assert len(store.records) == 1
    assert store.records[0]["error"]["code"] == "requires_handle_protocol"


def test_evaluation_run_async_creates_handle_and_records_budget() -> None:
    seen_args: dict = {}
    handles = _MemoryHandleStore()

    def fake_runner(args: dict) -> dict:
        seen_args.update(args)
        return {
            "status": "dispatched",
            "evaluation_id": "eval-1",
            "dashboard_url": "https://example.test/evaluations/eval-1",
        }

    gate = execute.BudgetGate()
    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        budget=gate,
        handle_store=handles,
        evaluation_runner=fake_runner,
    )

    budget = _child_budget()
    handle = module.evaluation.run(
        {
            "scorecard_name": "Compliance",
            "score_name": "Tone",
            "async": True,
            "budget": budget,
        }
    )

    assert handle == {
        "id": "handle-1",
        "kind": "evaluation",
        "status": "running",
        "status_url": "https://example.test/evaluations/eval-1",
        "created_at": "2026-04-29T00:00:00Z",
        "parent_trace_id": "trace-1",
        "child_budget": budget,
    }
    assert seen_args == {
        "scorecard_name": "Compliance",
        "score_name": "Tone",
        "async": True,
        "budget": budget,
        "procedure_id": "trace-1",
    }
    assert gate.tool_calls == 3
    assert gate.spent_usd == pytest.approx(0.01)
    assert module.api_calls == ["plexus.evaluation.run"]
    assert handles.created[0]["dispatch_result"]["evaluation_id"] == "eval-1"
    assert handles.created[0]["child_budget"] == budget


def test_evaluation_run_async_requires_explicit_child_budget() -> None:
    called = False

    def fake_runner(_args: dict) -> dict:
        nonlocal called
        called = True
        return {"status": "dispatched"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        evaluation_runner=fake_runner,
    )

    with pytest.raises(execute.ChildBudgetRequired):
        module.evaluation.run(
            {"scorecard_name": "Compliance", "score_name": "Tone", "async": True}
        )

    assert called is False
    assert module.api_calls == ["plexus.evaluation.run"]


def test_evaluation_run_async_preserves_explicit_procedure_id() -> None:
    seen_args: dict = {}

    def fake_runner(args: dict) -> dict:
        seen_args.update(args)
        return {
            "status": "dispatched",
            "evaluation_id": "eval-1",
            "dashboard_url": "https://example.test/evaluations/eval-1",
        }

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        evaluation_runner=fake_runner,
        handle_store=_MemoryHandleStore(),
    )

    module.evaluation.run(
        {
            "scorecard_name": "Compliance",
            "async": True,
            "budget": _child_budget(),
            "procedure_id": "proc-explicit",
        }
    )

    assert seen_args["procedure_id"] == "proc-explicit"


def test_evaluation_run_async_injects_trace_id_procedure_id_when_missing() -> None:
    seen_args: dict = {}

    def fake_runner(args: dict) -> dict:
        seen_args.update(args)
        return {
            "status": "dispatched",
            "evaluation_id": "eval-2",
            "dashboard_url": "https://example.test/evaluations/eval-2",
        }

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="proc-trace-123",
        evaluation_runner=fake_runner,
        handle_store=_MemoryHandleStore(),
    )

    module.evaluation.run(
        {
            "scorecard_name": "Compliance",
            "async": True,
            "budget": _child_budget(),
        }
    )

    assert seen_args["procedure_id"] == "proc-trace-123"


def test_async_child_budget_overrun_blocks_dispatch() -> None:
    called = False

    def fake_runner(_args: dict) -> dict:
        nonlocal called
        called = True
        return {"status": "dispatched"}

    gate = execute.BudgetGate(execute.BudgetSpec(usd=0.005, wallclock_seconds=60, depth=3, tool_calls=10))
    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        budget=gate,
        evaluation_runner=fake_runner,
    )

    with pytest.raises(execute.BudgetExceeded):
        module.evaluation.run(
            {
                "scorecard_name": "Compliance",
                "async": True,
                "budget": _child_budget(),
            }
        )

    assert called is False
    assert gate.exceeded is True
    assert module.api_calls == ["plexus.evaluation.run"]


def test_default_evaluation_runner_dispatches_cli_without_mcp_loopback(
    monkeypatch,
) -> None:
    captured: dict = {}

    class FakeProcess:
        pid = 4242

        def poll(self) -> int:
            return 1  # immediately signals process exited (fast-fail path)

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProcess()

    class FakeMCP:
        async def call_tool(self, name, arguments):  # pragma: no cover - must not run
            raise AssertionError("default evaluation runner must not call MCP tools")

    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/plexus")
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr("time.sleep", lambda _: None)

    result = execute._default_evaluation_runner(
        {
            "evaluation_type": "feedback",
            "scorecard_name": "Compliance",
            "score_name": "Tone",
            "max_feedback_items": 25,
            "days": 30,
            "procedure_id": "proc-123",
            "budget": _child_budget(),
        },
        FakeMCP(),
    )

    assert result["status"] == "dispatched"
    assert result["process_id"] == 4242
    cmd = captured["cmd"]
    # Strip out the --emit-id-file flag and its temp-file path since the path is dynamic
    emit_idx = cmd.index("--emit-id-file") if "--emit-id-file" in cmd else None
    if emit_idx is not None:
        cmd = cmd[:emit_idx] + cmd[emit_idx + 2:]
    assert cmd == [
        "/usr/local/bin/plexus",
        "evaluate",
        "feedback",
        "--scorecard",
        "Compliance",
        "--score",
        "Tone",
        "--max-items",
        "25",
        "--sampling-mode",
        "newest",
        "--days",
        "30",
        "--procedure-id",
        "proc-123",
    ]
    assert captured["kwargs"]["start_new_session"] is True
    assert json.loads(captured["kwargs"]["env"]["PLEXUS_CHILD_BUDGET"]) == _child_budget()
    assert result["child_budget"] == _child_budget()


def test_handle_peek_refreshes_evaluation_status() -> None:
    handles = _MemoryHandleStore()
    handle = handles.create(
        kind="evaluation",
        parent_trace_id="trace-1",
        api_call="plexus.evaluation.run",
        args={"async": True},
        dispatch_result={"evaluation_id": "eval-1"},
    )

    def fake_evaluation_info(args: dict) -> dict:
        return {"id": args["evaluation_id"], "status": "COMPLETED"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        handle_store=handles,
        evaluation_info=fake_evaluation_info,
    )

    snapshot = module.handle.peek({"id": handle["id"]})

    assert snapshot["status"] == "completed"
    assert snapshot["evaluation"] == {"id": "eval-1", "status": "COMPLETED"}
    assert module.api_calls == ["plexus.handle.peek"]


def test_handle_cancel_terminates_process() -> None:
    handles = _MemoryHandleStore()
    handle = handles.create(
        kind="evaluation",
        parent_trace_id="trace-1",
        api_call="plexus.evaluation.run",
        args={"async": True},
        dispatch_result={"process_id": 4242},
    )
    killed: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        killed.append((pid, sig))

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        handle_store=handles,
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(execute.os, "kill", fake_kill)
    try:
        result = module.handle.cancel({"id": handle["id"]})
    finally:
        monkeypatch.undo()

    assert result["status"] == "cancelled"
    assert result["cancel_requested"] is True
    assert result["cancel_propagated"] is True
    assert result["cancel_actions"] == [
        {"kind": "process", "id": "4242", "status": "terminated"}
    ]
    assert killed == [(4242, execute.signal.SIGTERM)]
    assert module.api_calls == ["plexus.handle.cancel"]


def test_handle_cancel_marks_dashboard_task_cancelled(monkeypatch) -> None:
    handles = _MemoryHandleStore()
    handle = handles.create(
        kind="report",
        parent_trace_id="trace-1",
        api_call="plexus.report.run",
        args={"async": True},
        dispatch_result={"task_id": "task-1"},
    )
    updates: list[dict] = []

    class FakeTask:
        def update(self, **kwargs):
            updates.append(kwargs)

    class FakeTaskModel:
        @staticmethod
        def get_by_id(task_id, client):
            assert task_id == "task-1"
            assert client == "client"
            return FakeTask()

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: "client"
    )
    monkeypatch.setattr("plexus.dashboard.api.models.task.Task", FakeTaskModel)

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        handle_store=handles,
    )

    result = module.handle.cancel({"id": handle["id"]})

    assert result["status"] == "cancelled"
    assert result["cancel_propagated"] is True
    assert result["cancel_actions"] == [
        {"kind": "task", "id": "task-1", "status": "cancelled"}
    ]
    assert updates == [
        {
            "status": "CANCELLED",
            "errorMessage": "Cancellation requested by execute_tactus handle.",
            "completedAt": updates[0]["completedAt"],
        }
    ]


def test_handle_cancel_marks_evaluation_cancelled(monkeypatch) -> None:
    handles = _MemoryHandleStore()
    handle = handles.create(
        kind="evaluation",
        parent_trace_id="trace-1",
        api_call="plexus.evaluation.run",
        args={"async": True},
        dispatch_result={"evaluation_id": "eval-1"},
    )
    updates: list[dict] = []

    class FakeEvaluation:
        def update(self, **kwargs):
            updates.append(kwargs)

    class FakeEvaluationModel:
        @staticmethod
        def get_by_id(evaluation_id, client):
            assert evaluation_id == "eval-1"
            assert client == "client"
            return FakeEvaluation()

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: "client"
    )
    monkeypatch.setattr(
        "plexus.dashboard.api.models.evaluation.Evaluation",
        FakeEvaluationModel,
    )

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        handle_store=handles,
    )

    result = module.handle.cancel({"id": handle["id"]})

    assert result["status"] == "cancelled"
    assert result["cancel_propagated"] is True
    assert result["cancel_actions"] == [
        {"kind": "evaluation", "id": "eval-1", "status": "cancelled"}
    ]
    assert updates == [
        {
            "status": "CANCELLED",
            "errorMessage": "Cancellation requested by execute_tactus handle.",
        }
    ]


@pytest.mark.asyncio
async def test_execute_tactus_evaluation_run_async_returns_handle() -> None:
    mcp = FastMCP("test-execute-tactus-evaluation-run-handle")
    handles = _MemoryHandleStore()

    def fake_runner(args: dict) -> dict:
        return {
            "status": "dispatched",
            "evaluation_id": "eval-1",
            "dashboard_url": "https://example.test/evaluations/eval-1",
        }

    store = _RecordingTraceStore()
    result = await execute._execute_tactus_tool(
        (
            'evaluate{ scorecard_name = "Compliance", score_name = "Tone", '
            'async = true, budget = { usd = 0.01, wallclock_seconds = 10, '
            'depth = 1, tool_calls = 2 } }'
        ),
        mcp,
        trace_store=store,
        handle_store=handles,
        evaluation_runner=fake_runner,
    )

    assert result["ok"] is True
    assert result["value"]["kind"] == "evaluation"
    assert result["value"]["id"] == "handle-1"
    assert result["api_calls"] == ["plexus.evaluation.run"]
    assert result["cost"]["tool_calls"] == 3
    assert store.records[0]["value"]["id"] == "handle-1"
    assert result["value"]["child_budget"] == _child_budget()


@pytest.mark.asyncio
async def test_execute_tactus_async_run_without_budget_returns_clear_error() -> None:
    called = False

    def fake_runner(_args: dict) -> dict:
        nonlocal called
        called = True
        return {"status": "dispatched"}

    result = await execute._execute_tactus_tool(
        'evaluate{ scorecard_name = "Compliance", async = true }',
        FastMCP("test-execute-tactus-missing-child-budget"),
        evaluation_runner=fake_runner,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "child_budget_required"
    assert "explicit budget" in result["error"]["message"]
    assert result["api_calls"] == ["plexus.evaluation.run"]
    assert called is False


def test_report_run_async_creates_handle_and_records_budget() -> None:
    seen_args: dict = {}
    handles = _MemoryHandleStore()

    def fake_runner(args: dict) -> dict:
        seen_args.update(args)
        return {
            "status": "dispatched",
            "cache_key": "report-cache",
            "task_id": "task-1",
        }

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        handle_store=handles,
        report_runner=fake_runner,
    )

    budget = _child_budget()
    handle = module.report.run(
        {
            "block_class": "FeedbackContradictions",
            "cache_key": "report-cache",
            "async": True,
            "budget": budget,
        }
    )

    assert handle["id"] == "handle-1"
    assert handle["kind"] == "report"
    assert handle["parent_trace_id"] == "trace-1"
    assert seen_args == {
        "block_class": "FeedbackContradictions",
        "cache_key": "report-cache",
        "async": True,
        "budget": budget,
    }
    assert module.api_calls == ["plexus.report.run"]
    assert handles.created[0]["dispatch_result"]["task_id"] == "task-1"
    assert handles.created[0]["child_budget"] == budget


def test_score_champion_version_timeline_convenience_maps_report_block() -> None:
    seen_args: dict = {}
    handles = _MemoryHandleStore()

    def fake_runner(args: dict) -> dict:
        seen_args.update(args)
        return {
            "status": "dispatched",
            "cache_key": "champion-timeline-cache",
            "task_id": "task-1",
        }

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        handle_store=handles,
        report_runner=fake_runner,
    )

    budget = _child_budget()
    handle = module.report.score_champion_version_timeline(
        {
            "scorecard": "Suco - Home Improvement",
            "days": 21,
            "include_unchanged": True,
            "async": True,
            "budget": budget,
        }
    )

    assert handle["kind"] == "report"
    assert seen_args["block_class"] == "ScoreChampionVersionTimeline"
    assert seen_args["block_config"] == {
        "scorecard": "Suco - Home Improvement",
        "days": 21,
        "include_unchanged": True,
    }
    assert module.api_calls == ["plexus.report.run"]


def test_default_report_runner_launches_detached_local_subprocess(monkeypatch) -> None:
    captured: dict = {}

    class FakeProcess:
        pid = 12345
        returncode = 0
        args = None

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def communicate(self, _input=None, timeout=None):
            return "", ""

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

        def kill(self):
            self.returncode = -9

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        proc = FakeProcess()
        proc.args = cmd
        return proc

    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: object())
    monkeypatch.setattr("subprocess.Popen", fake_popen)

    result = execute._default_report_runner(
        {
            "block_class": "FeedbackContradictions",
            "cache_key": "report-cache",
            "block_config": {"scorecard": "Card", "score": "Score", "days": 30},
            "fresh": True,
        }
    )

    assert result == {"status": "running", "block_class": "FeedbackContradictions", "pid": 12345}
    assert captured["cmd"][-7:] == [
        "contradictions",
        "--scorecard",
        "Card",
        "--score",
        "Score",
        "--days",
        "30",
        "--fresh",
    ][-7:]
    assert captured["kwargs"]["stdout"] is not None
    assert captured["kwargs"]["stderr"] is not None


def test_default_report_runner_launches_score_champion_timeline_command(monkeypatch) -> None:
    captured: dict = {}

    class FakeProcess:
        pid = 12345

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: object())
    monkeypatch.setattr("subprocess.Popen", fake_popen)

    result = execute._default_report_runner(
        {
            "block_class": "ScoreChampionVersionTimeline",
            "block_config": {
                "scorecard": "Suco - Home Improvement",
                "score": "Project Type AI",
                "days": 21,
                "include_unchanged": True,
            },
            "fresh": True,
        }
    )

    assert result == {"status": "running", "block_class": "ScoreChampionVersionTimeline", "pid": 12345}
    assert captured["cmd"][1:] == [
        "-m",
        "plexus",
        "feedback",
        "report",
        "score-champion-version-timeline",
        "--scorecard",
        "Suco - Home Improvement",
        "--score",
        "Project Type AI",
        "--days",
        "21",
        "--include-unchanged",
        "--fresh",
    ]


def test_report_run_blocking_requires_handle_protocol() -> None:
    module = execute.PlexusRuntimeModule(FastMCP("test"))

    with pytest.raises(execute.RequiresHandleProtocol):
        module.report.run({"block_class": "FeedbackContradictions"})

    assert module.handle_protocol_required == ("report", "run")
    assert module.api_calls == ["plexus.report.run"]


def test_procedure_run_async_creates_handle_and_records_budget() -> None:
    seen_args: dict = {}
    handles = _MemoryHandleStore()

    def fake_runner(args: dict) -> dict:
        seen_args.update(args)
        return {
            "status": "initiated",
            "procedure_id": "proc-1",
            "message": "Procedure run initiated",
        }

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        handle_store=handles,
        procedure_runner=fake_runner,
    )

    budget = _child_budget()
    handle = module.procedure.run(
        {
            "procedure_id": "proc-1",
            "max_iterations": 3,
            "async": True,
            "budget": budget,
        }
    )

    assert handle["id"] == "handle-1"
    assert handle["kind"] == "procedure"
    assert handle["parent_trace_id"] == "trace-1"
    assert seen_args == {
        "procedure_id": "proc-1",
        "max_iterations": 3,
        "async": True,
        "budget": budget,
    }
    assert module.api_calls == ["plexus.procedure.run"]
    assert handles.created[0]["dispatch_result"]["procedure_id"] == "proc-1"
    assert handles.created[0]["child_budget"] == budget


def test_default_procedure_runner_launches_detached_local_subprocess(monkeypatch) -> None:
    captured: dict = {}

    class FakeProcess:
        pid = 12345

    def fake_launch(cmd, procedure_id):
        captured["cmd"] = cmd
        captured["procedure_id"] = procedure_id
        return FakeProcess(), "/tmp/proc-1.log"

    monkeypatch.setattr(execute, "_launch_local_procedure_subprocess", fake_launch)

    result = execute._default_procedure_runner(
        {
            "procedure_id": "proc-1",
            "max_iterations": 2,
            "dry_run": True,
        }
    )

    assert result == {
        "status": "running",
        "procedure_id": "proc-1",
        "pid": 12345,
        "log_path": "/tmp/proc-1.log",
    }
    assert captured["procedure_id"] == "proc-1"
    assert captured["cmd"][-4:] == ["proc-1", "--max-iterations", "2", "--dry-run"]


def test_procedure_run_blocking_requires_handle_protocol() -> None:
    module = execute.PlexusRuntimeModule(FastMCP("test"))

    with pytest.raises(execute.RequiresHandleProtocol):
        module.procedure.run({"procedure_id": "proc-1"})

    assert module.handle_protocol_required == ("procedure", "run")
    assert module.api_calls == ["plexus.procedure.run"]


@pytest.mark.asyncio
async def test_execute_tactus_report_run_async_returns_handle() -> None:
    mcp = FastMCP("test-execute-tactus-report-run-handle")
    handles = _MemoryHandleStore()

    def fake_runner(args: dict) -> dict:
        return {
            "status": "dispatched",
            "cache_key": args["cache_key"],
            "task_id": "task-1",
        }

    result = await execute._execute_tactus_tool(
        (
            'report{ block_class = "FeedbackContradictions", '
            'cache_key = "report-cache", async = true, '
            'budget = { usd = 0.01, wallclock_seconds = 10, '
            'depth = 1, tool_calls = 2 } }'
        ),
        mcp,
        handle_store=handles,
        report_runner=fake_runner,
    )

    assert result["ok"] is True
    assert result["value"]["kind"] == "report"
    assert result["value"]["id"] == "handle-1"
    assert result["api_calls"] == ["plexus.report.run"]
    assert result["cost"]["tool_calls"] == 3


@pytest.mark.asyncio
async def test_execute_tactus_procedure_run_async_returns_handle() -> None:
    mcp = FastMCP("test-execute-tactus-procedure-run-handle")
    handles = _MemoryHandleStore()

    def fake_runner(args: dict) -> dict:
        return {
            "status": "initiated",
            "procedure_id": args["procedure_id"],
            "message": "Procedure run initiated",
        }

    result = await execute._execute_tactus_tool(
        (
            'return plexus.procedure.run{ procedure_id = "proc-1", async = true, '
            'budget = { usd = 0.01, wallclock_seconds = 10, '
            'depth = 1, tool_calls = 2 } }'
        ),
        mcp,
        handle_store=handles,
        procedure_runner=fake_runner,
    )

    assert result["ok"] is True
    assert result["value"]["kind"] == "procedure"
    assert result["value"]["id"] == "handle-1"
    assert result["api_calls"] == ["plexus.procedure.run"]
    assert result["cost"]["tool_calls"] == 3


@pytest.mark.asyncio
async def test_execute_tactus_cost_envelope_reflects_budget_remaining() -> None:
    mcp = FastMCP("test-execute-tactus-budget-remaining")

    def fake_score_info(args):
        return {"id": args.get("id"), "name": "Tracked"}

    result = await execute._execute_tactus_tool(
        'score{ id = "score_tracked" }',
        mcp,
        score_info=fake_score_info,
    )

    cost = result["cost"]
    assert cost["tool_calls"] == 1
    assert cost["usd"] == 0.0
    assert cost["budget_remaining_usd"] == execute.DEFAULT_BUDGET_USD
    assert cost["budget_remaining_tool_calls"] == execute.DEFAULT_BUDGET_TOOL_CALLS - 1
    assert cost["budget_remaining_seconds"] >= 0.0


def test_feedback_find_no_longer_in_mcp_tool_map() -> None:
    assert ("feedback", "find") not in execute.MCP_TOOL_MAP
    assert ("feedback", "find") in execute.DIRECT_HANDLERS


def test_feedback_find_uses_injected_finder_and_skips_mcp_loopback() -> None:
    received_args: dict = {}
    canned = {
        "context": {
            "scorecard_name": "x",
            "score_name": "y",
            "scorecard_id": "sc-1",
            "score_id": "s-1",
            "account_id": "acct-1",
            "filters": {},
            "total_found": 0,
        },
        "feedback_items": [],
    }

    def fake_finder(args: dict) -> dict:
        received_args.update(args)
        return canned

    class FakeMCP:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            raise AssertionError("plexus.feedback.find must not call MCP tools")

    fake_mcp = FakeMCP()
    module = execute.PlexusRuntimeModule(fake_mcp, feedback_finder=fake_finder)

    value = module.feedback.find(
        {"scorecard_name": "x", "score_name": "y", "days": 14, "limit": 3}
    )

    assert value is canned
    assert received_args == {
        "scorecard_name": "x",
        "score_name": "y",
        "days": 14,
        "limit": 3,
    }
    assert module.api_calls == ["plexus.feedback.find"]
    assert fake_mcp.calls == []


def test_feedback_find_records_one_tool_call_against_budget() -> None:
    def fake_finder(args: dict) -> dict:
        return {"context": {}, "feedback_items": []}

    gate = execute.BudgetGate()
    module = execute.PlexusRuntimeModule(
        FastMCP("test"), budget=gate, feedback_finder=fake_finder
    )

    module.feedback.find({"scorecard_name": "x", "score_name": "y"})

    assert gate.tool_calls == 1
    assert gate.exceeded is False
    assert module.api_calls == ["plexus.feedback.find"]


def test_feedback_find_validates_required_args_through_default_finder() -> None:
    module = execute.PlexusRuntimeModule(FastMCP("test"))

    with pytest.raises(ValueError, match="scorecard_name and score_name"):
        module.feedback.find({"scorecard_name": "only-one"})


def test_feedback_find_is_listed_in_plexus_api_list() -> None:
    module = execute.PlexusRuntimeModule(FastMCP("test"))

    catalog = module.api.list()

    assert "find" in catalog["plexus.feedback"]
    assert "alignment" in catalog["plexus.feedback"]


def test_evaluation_info_no_longer_in_mcp_tool_map() -> None:
    assert ("evaluation", "info") not in execute.MCP_TOOL_MAP
    assert ("evaluation", "info") in execute.DIRECT_HANDLERS


def test_evaluation_info_is_listed_in_plexus_api_list() -> None:
    module = execute.PlexusRuntimeModule(FastMCP("test"))

    catalog = module.api.list()

    assert "info" in catalog["plexus.evaluation"]
    assert "compare" in catalog["plexus.evaluation"]
    assert "find_recent" in catalog["plexus.evaluation"]


def test_evaluation_info_uses_injected_function_and_skips_mcp_loopback() -> None:
    received_args: dict = {}
    canned = {"id": "eval-1", "status": "COMPLETED"}

    def fake_evaluation_info(args: dict) -> dict:
        received_args.update(args)
        return canned

    class FakeMCP:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            raise AssertionError("plexus.evaluation.info must not call MCP tools")

    fake_mcp = FakeMCP()
    module = execute.PlexusRuntimeModule(fake_mcp, evaluation_info=fake_evaluation_info)

    value = module.evaluation.info(
        {"evaluation_id": "eval-1", "include_score_results": True}
    )

    assert value is canned
    assert received_args == {
        "evaluation_id": "eval-1",
        "include_score_results": True,
    }
    assert module.api_calls == ["plexus.evaluation.info"]
    assert fake_mcp.calls == []


def test_evaluation_info_records_one_tool_call_against_budget() -> None:
    def fake_evaluation_info(args: dict) -> dict:
        return {"id": args["evaluation_id"]}

    gate = execute.BudgetGate()
    module = execute.PlexusRuntimeModule(
        FastMCP("test"), budget=gate, evaluation_info=fake_evaluation_info
    )

    module.evaluation.info({"evaluation_id": "eval-1"})

    assert gate.tool_calls == 1
    assert gate.exceeded is False
    assert module.api_calls == ["plexus.evaluation.info"]


def test_default_evaluation_info_gets_by_id(monkeypatch) -> None:
    from plexus.Evaluation import Evaluation

    captured: dict = {}

    def fake_get_evaluation_info(evaluation_id, include_score_results=False):
        captured["evaluation_id"] = evaluation_id
        captured["include_score_results"] = include_score_results
        return {"id": evaluation_id, "include_score_results": include_score_results}

    monkeypatch.setattr(
        Evaluation,
        "get_evaluation_info",
        staticmethod(fake_get_evaluation_info),
    )

    result = execute._default_evaluation_info(
        {"evaluation_id": " eval-1 ", "include_score_results": True}
    )

    assert result == {"id": "eval-1", "include_score_results": True}
    assert captured == {"evaluation_id": "eval-1", "include_score_results": True}


def test_default_evaluation_info_gets_latest(monkeypatch) -> None:
    from plexus.Evaluation import Evaluation

    captured: dict = {}

    def fake_get_latest_evaluation(account_key=None, evaluation_type=None):
        captured["account_key"] = account_key
        captured["evaluation_type"] = evaluation_type
        return {"id": "latest", "account_key": account_key}

    monkeypatch.setattr(
        Evaluation,
        "get_latest_evaluation",
        staticmethod(fake_get_latest_evaluation),
    )

    result = execute._default_evaluation_info(
        {
            "use_latest": True,
            "account_key": "acct-1",
            "evaluation_type": "  ",
        }
    )

    assert result == {"id": "latest", "account_key": "acct-1"}
    assert captured == {"account_key": "acct-1", "evaluation_type": None}


def test_default_evaluation_info_validates_lookup_mode() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        execute._default_evaluation_info({})

    with pytest.raises(ValueError, match="exactly one"):
        execute._default_evaluation_info(
            {"evaluation_id": "eval-1", "use_latest": True}
        )

    with pytest.raises(ValueError, match="include_examples"):
        execute._default_evaluation_info(
            {"evaluation_id": "eval-1", "include_examples": True}
        )


def test_default_feedback_finder_chains_through_resolvers_and_service(
    monkeypatch,
) -> None:
    captured: dict = {}

    class FakeFeedbackService:
        @staticmethod
        async def search_feedback(**kwargs):
            captured["search_kwargs"] = kwargs
            return SimpleNamespace(stub_search_result=True)

        @staticmethod
        def format_search_result_as_dict(result):
            captured["formatted_from"] = result
            return {"context": {"total_found": 7}, "feedback_items": []}

    fake_client = SimpleNamespace(name="client")

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: fake_client
    )
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda client, identifier: "acct-default",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.memoized_resolvers.memoized_resolve_scorecard_identifier",
        lambda client, name: f"sc:{name}",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.memoized_resolvers.memoized_resolve_score_identifier",
        lambda client, scorecard_id, score_name: f"sn:{scorecard_id}:{score_name}",
    )
    monkeypatch.setattr(
        "plexus.cli.feedback.feedback_service.FeedbackService",
        FakeFeedbackService,
    )

    result = execute._default_feedback_finder(
        {
            "scorecard_name": "Compliance",
            "score_name": "Tone",
            "limit": 4,
            "offset": 8,
            "initial_value": "Yes",
            "final_value": "No",
            "prioritize_edit_comments": False,
        }
    )

    assert result == {"context": {"total_found": 7}, "feedback_items": []}
    kwargs = captured["search_kwargs"]
    assert kwargs["client"] is fake_client
    assert kwargs["scorecard_name"] == "Compliance"
    assert kwargs["score_name"] == "Tone"
    assert kwargs["scorecard_id"] == "sc:Compliance"
    assert kwargs["score_id"] == "sn:sc:Compliance:Tone"
    assert kwargs["account_id"] == "acct-default"
    assert kwargs["days"] == 7
    assert kwargs["limit"] == 4
    assert kwargs["offset"] == 8
    assert kwargs["initial_value"] == "Yes"
    assert kwargs["final_value"] == "No"
    assert kwargs["prioritize_edit_comments"] is False


@pytest.mark.asyncio
async def test_execute_tactus_runs_feedback_find_through_direct_finder() -> None:
    mcp = FastMCP("test-execute-tactus-feedback-direct")

    canned = {
        "context": {
            "scorecard_name": "x",
            "score_name": "y",
            "scorecard_id": "sc",
            "score_id": "s",
            "account_id": "acct",
            "filters": {},
            "total_found": 2,
        },
        "feedback_items": [
            {"item_id": "i1", "external_id": "e1"},
            {"item_id": "i2", "external_id": "e2"},
        ],
    }
    seen_args: dict = {}

    def fake_finder(args: dict) -> dict:
        seen_args.update(args)
        return canned

    store = _RecordingTraceStore()
    result = await execute._execute_tactus_tool(
        'feedback{ scorecard_name = "x", score_name = "y", days = 30 }',
        mcp,
        trace_store=store,
        feedback_finder=fake_finder,
    )

    assert result["ok"] is True
    assert result["value"] == canned
    assert result["api_calls"] == ["plexus.feedback.find"]
    assert seen_args == {"scorecard_name": "x", "score_name": "y", "days": 30}
    assert len(store.records) == 1
    record = store.records[0]
    assert record["api_calls"] == ["plexus.feedback.find"]
    assert record["ok"] is True


@pytest.mark.asyncio
async def test_execute_tactus_feedback_find_missing_args_surfaces_as_tactus_error() -> (
    None
):
    mcp = FastMCP("test-execute-tactus-feedback-missing-args")

    result = await execute._execute_tactus_tool(
        'feedback{ scorecard_name = "x" }',
        mcp,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "tactus_execution_failed"
    assert "scorecard_name and score_name" in result["error"]["message"]


@pytest.mark.asyncio
async def test_execute_tactus_runs_evaluation_info_through_direct_function() -> None:
    mcp = FastMCP("test-execute-tactus-evaluation-direct")
    canned = {
        "id": "eval-1",
        "status": "COMPLETED",
        "metrics": {"accuracy": 0.91},
    }
    seen_args: dict = {}

    def fake_evaluation_info(args: dict) -> dict:
        seen_args.update(args)
        return canned

    store = _RecordingTraceStore()
    result = await execute._execute_tactus_tool(
        'return plexus.evaluation.info{ evaluation_id = "eval-1", include_score_results = true }',
        mcp,
        trace_store=store,
        evaluation_info=fake_evaluation_info,
    )

    assert result["ok"] is True
    assert result["value"] == canned
    assert result["api_calls"] == ["plexus.evaluation.info"]
    assert seen_args == {
        "evaluation_id": "eval-1",
        "include_score_results": True,
    }
    assert len(store.records) == 1
    record = store.records[0]
    assert record["api_calls"] == ["plexus.evaluation.info"]
    assert record["ok"] is True
