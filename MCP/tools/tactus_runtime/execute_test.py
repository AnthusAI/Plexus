"""Tests for the execute_tactus MCP prototype."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

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


def test_wrap_tactus_snippet_injects_plexus_helpers_and_capture() -> None:
    wrapped = execute._wrap_tactus_snippet(
        'evaluate{ score_id = "score_compliance_tone", item_count = 200 }'
    )

    assert 'local plexus = require("plexus")' in wrapped
    assert "function evaluate(args)" in wrapped
    assert "return __plexus_last_result" in wrapped
    assert "__execute_tactus_user_snippet" in wrapped


def test_plexus_facade_delegates_namespace_call_to_mcp_tool() -> None:
    class FakeMCP:
        def __init__(self) -> None:
            self.calls = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return SimpleNamespace(
                structured_content={
                    "id": arguments["id"],
                    "name": "Compliance Tone",
                }
            )

    fake_mcp = FakeMCP()
    facade = execute.PlexusRuntimeModule(fake_mcp)

    value = facade.score.info({"id": "score_compliance_tone"})

    assert value == {"id": "score_compliance_tone", "name": "Compliance Tone"}
    assert fake_mcp.calls == [
        ("plexus_score_info", {"id": "score_compliance_tone"})
    ]
    assert facade.api_calls == ["plexus.score.info"]


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
async def test_execute_tactus_tool_returns_structured_contract(monkeypatch) -> None:
    mcp = FastMCP("test-execute-tactus")
    execute.register_tactus_tools(mcp)

    def fake_run_tactus_sync(tactus, mcp, *, trace_id, trace_store, budget=None, **kwargs):
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
async def test_execute_tactus_reports_missing_host_module_runtime_contract(monkeypatch) -> None:
    def fake_run_tactus_sync(tactus, mcp, *, trace_id, trace_store, budget=None, **kwargs):
        raise RuntimeError("execute_tactus requires TactusRuntime.register_python_module")

    monkeypatch.setattr(execute, "_run_tactus_sync", fake_run_tactus_sync)

    result = await execute._execute_tactus_tool("return { ok = true }", FastMCP("test"))

    assert result["ok"] is False
    assert result["value"] is None
    assert result["error"]["code"] == "runtime_error"
    assert "register_python_module" in result["error"]["message"]


@pytest.mark.asyncio
async def test_execute_tactus_runs_helper_call_through_host_module() -> None:
    mcp = FastMCP("test-execute-tactus-runtime")

    @mcp.tool()
    def plexus_score_info(id: str):
        return {"id": id, "name": "Compliance Tone"}

    result = await execute._execute_tactus_tool(
        'score{ id = "score_compliance_tone" }',
        mcp,
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


@pytest.mark.asyncio
async def test_execute_tactus_implicit_last_helper_result_is_returned() -> None:
    mcp = FastMCP("test-execute-tactus-implicit")

    @mcp.tool()
    def plexus_score_info(id: str):
        return {"id": id, "name": "Implicit"}

    result = await execute._execute_tactus_tool(
        'score{ id = "score_implicit" }',
        mcp,
    )

    assert result["ok"] is True
    assert result["value"] == {"id": "score_implicit", "name": "Implicit"}


@pytest.mark.asyncio
async def test_execute_tactus_explicit_return_overrides_helper_capture() -> None:
    mcp = FastMCP("test-execute-tactus-explicit")

    @mcp.tool()
    def plexus_score_info(id: str):
        return {"id": id, "name": "Captured"}

    result = await execute._execute_tactus_tool(
        'score{ id = "score_captured" }\nreturn { override = true }',
        mcp,
    )

    assert result["ok"] is True
    assert result["value"] == {"override": True}
    assert result["api_calls"] == ["plexus.score.info"]


@pytest.mark.asyncio
async def test_execute_tactus_writes_trace_for_successful_run() -> None:
    mcp = FastMCP("test-execute-tactus-trace-success")

    @mcp.tool()
    def plexus_score_info(id: str):
        return {"id": id, "name": "Trace"}

    store = _RecordingTraceStore()
    result = await execute._execute_tactus_tool(
        'score{ id = "score_trace" }',
        mcp,
        trace_store=store,
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

    def fake_run_tactus_sync(tactus, mcp, *, trace_id, trace_store, budget=None, **kwargs):
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

    gate = execute.BudgetGate(
        execute.BudgetSpec(wallclock_seconds=1.0), clock=clock
    )

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
    assert ("evaluation", "run") in execute.LONG_RUNNING_METHODS
    assert ("report", "run") in execute.LONG_RUNNING_METHODS
    assert ("procedure", "run") in execute.LONG_RUNNING_METHODS


def test_plexus_runtime_module_marks_long_running_call_and_skips_loopback() -> None:
    class FakeMCP:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            raise AssertionError("long-running calls must not loop back through MCP in v0")

    fake_mcp = FakeMCP()
    module = execute.PlexusRuntimeModule(fake_mcp)

    with pytest.raises(execute.RequiresHandleProtocol):
        module.evaluation.run({"scorecard_name": "x"})

    assert module.handle_protocol_required == ("evaluation", "run")
    assert module.api_calls == ["plexus.evaluation.run"]
    assert fake_mcp.calls == []


@pytest.mark.asyncio
async def test_execute_tactus_returns_requires_handle_protocol_for_long_running() -> None:
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


@pytest.mark.asyncio
async def test_execute_tactus_cost_envelope_reflects_budget_remaining() -> None:
    mcp = FastMCP("test-execute-tactus-budget-remaining")

    @mcp.tool()
    def plexus_score_info(id: str):
        return {"id": id, "name": "Tracked"}

    result = await execute._execute_tactus_tool(
        'score{ id = "score_tracked" }',
        mcp,
    )

    cost = result["cost"]
    assert cost["tool_calls"] == 1
    assert cost["usd"] == 0.0
    assert cost["budget_remaining_usd"] == execute.DEFAULT_BUDGET_USD
    assert (
        cost["budget_remaining_tool_calls"]
        == execute.DEFAULT_BUDGET_TOOL_CALLS - 1
    )
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


def test_default_feedback_finder_chains_through_resolvers_and_service(monkeypatch) -> None:
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
async def test_execute_tactus_feedback_find_missing_args_surfaces_as_tactus_error() -> None:
    mcp = FastMCP("test-execute-tactus-feedback-missing-args")

    result = await execute._execute_tactus_tool(
        'feedback{ scorecard_name = "x" }',
        mcp,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "tactus_execution_failed"
    assert "scorecard_name and score_name" in result["error"]["message"]
