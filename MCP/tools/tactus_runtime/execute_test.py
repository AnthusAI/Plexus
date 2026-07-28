"""Tests for the execute_tactus MCP prototype."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import os
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from fastmcp import Client, FastMCP

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
            "dispatch_result": dispatch_result,
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


def test_attach_console_audit_events_adds_events_to_envelope() -> None:
    envelope = {
        "ok": True,
        "value": {"status": "completed"},
        "error": None,
        "cost": {"usd": 0},
        "trace_id": "trace-1",
        "partial": False,
        "api_calls": ["plexus.score.edit"],
    }
    runtime_context = {
        "console_audit_events": [
            {
                "kind": "score_edit",
                "version_id": "v-1",
                "version_url": "/lab/scorecards/sc-1/scores/s-1/versions/v-1",
            }
        ]
    }

    attached = execute._attach_console_audit_events(
        envelope,
        runtime_context,
        score_edit_events=[
            {
                "kind": "score_edit",
                "version_id": "v-2",
                "version_url": "/lab/scorecards/sc-2/scores/s-2/versions/v-2",
            }
        ],
    )

    assert attached["console_audit_events"][0]["kind"] == "score_edit"
    assert attached["console_audit_events"][0]["version_id"] == "v-1"
    assert attached["console_audit_events"][1]["version_id"] == "v-2"
    assert attached["score_edit_audit_compact"]["s"] is False
    assert attached["score_edit_audit_compact"]["v"] == "v-2"
    assert "pu" in attached["score_edit_audit_compact"]


def test_extract_score_edit_audit_events_from_value_returns_event() -> None:
    events = execute._extract_score_edit_audit_events_from_value(
        {
            "status": "completed",
            "score_edit_audit": {
                "k": "score_edit",
                "s": True,
                "v": "v-1",
            },
        }
    )

    assert len(events) == 1
    assert events[0]["kind"] == "score_edit"
    assert events[0]["success"] is True
    assert events[0]["version_id"] == "v-1"


def test_truncate_envelope_preserves_console_audit_events() -> None:
    envelope = {
        "ok": True,
        "value": {"payload": "x" * 50000},
        "error": None,
        "cost": {"usd": 0},
        "trace_id": "trace-1",
        "partial": False,
        "api_calls": ["plexus.score.edit"],
        "console_audit_events": [
            {
                "kind": "score_edit",
                "version_id": "v-1",
                "version_url": "/lab/scorecards/sc-1/scores/s-1/versions/v-1",
            }
        ],
        "score_edit_audit_compact": {"k": "score_edit", "v": "v-1"},
    }

    truncated = execute._truncate_envelope(envelope)

    assert isinstance(truncated["value"], dict)
    assert truncated["value"].get("__truncated__") is True
    assert truncated["console_audit_events"][0]["version_id"] == "v-1"
    assert truncated["score_edit_audit_compact"]["v"] == "v-1"


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
    assert "function skills_list(args)" in wrapped
    assert "function skills_get(args)" in wrapped
    assert "function guidelines_validate(args)" in wrapped
    assert "function api_list(args)" in wrapped
    assert "function scorecards_search(args)" in wrapped
    assert "function score_search(args)" in wrapped
    assert "function score_resolve(args)" in wrapped
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


def test_default_score_info_accepts_version_alias(monkeypatch) -> None:
    queries: list[str] = []

    class FakeClient:
        def execute(self, query: str) -> dict[str, Any]:
            queries.append(query)
            if "GetScorecardWithScores" in query:
                return {
                    "getScorecard": {
                        "id": "sc-1",
                        "name": "Example Scorecard",
                        "key": "example-scorecard",
                        "sections": {
                            "items": [
                                {
                                    "id": "section-1",
                                    "name": "Default",
                                    "scores": {
                                        "items": [
                                            {
                                                "id": "score-1",
                                                "name": "Example Score",
                                                "key": "example-score",
                                                "externalId": "123",
                                                "description": "Example",
                                                "type": "STANDARD",
                                                "championVersionId": "sv-champion",
                                                "updatedAt": "2026-01-03T00:00:00Z",
                                                "isDisabled": False,
                                            }
                                        ]
                                    },
                                }
                            ]
                        },
                    }
                }
            if "GetScoreVersions" in query:
                return {
                    "getScore": {
                        "id": "score-1",
                        "name": "Example Score",
                        "key": "example-score",
                        "externalId": "123",
                        "championVersionId": "sv-champion",
                        "versions": {
                            "items": [
                                {
                                    "id": "sv-candidate",
                                    "createdAt": "2026-01-02T00:00:00Z",
                                    "isFeatured": False,
                                    "parentVersionId": "sv-champion",
                                    "note": "Candidate",
                                    "metadata": None,
                                },
                                {
                                    "id": "sv-champion",
                                    "createdAt": "2026-01-01T00:00:00Z",
                                    "isFeatured": False,
                                    "parentVersionId": None,
                                    "note": "Champion",
                                    "metadata": None,
                                },
                            ]
                        },
                    }
                }
            if "GetScoreVersionForInfo" in query:
                assert 'getScoreVersion(id: "sv-candidate")' in query
                return {
                    "getScoreVersion": {
                        "id": "sv-candidate",
                        "configuration": "name: Candidate\n",
                        "guidelines": "# Candidate guidelines\n",
                        "createdAt": "2026-01-02T00:00:00Z",
                        "updatedAt": "2026-01-02T00:00:00Z",
                        "note": "Candidate",
                        "isFeatured": False,
                        "parentVersionId": "sv-champion",
                        "metadata": None,
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(
        "plexus.cli.scorecard.scorecards.resolve_scorecard_identifier",
        lambda _client, identifier: "sc-1" if identifier == "Example Scorecard" else None,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        lambda: FakeClient(),
    )

    result = execute._default_score_info(
        {
            "scorecard_identifier": "Example Scorecard",
            "score_identifier": "Example Score",
            "version": "sv-candidate",
        }
    )

    assert result["targetVersionId"] == "sv-candidate"
    assert result["isChampionVersion"] is False
    assert result["isSpecificVersion"] is True
    assert result["versionDetails"]["id"] == "sv-candidate"
    assert result["previousVersionId"] == "sv-champion"
    assert result["previousVersionSource"] == "parent"
    assert result["code"] == "name: Candidate\n"
    assert result["updatedAt"] == "2026-01-03T00:00:00Z"
    discovery_query = next(query for query in queries if "GetScorecardWithScores" in query)
    assert "championVersionId isDisabled updatedAt" in discovery_query
    assert result["versions"][0]["id"] == "sv-candidate"


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
    search_args: list = []

    def fake_list(args):
        list_args.append(args)
        return [{"id": "card-1", "name": "Example Scorecard"}]

    def fake_info(args):
        info_args.append(args)
        return {
            "name": "Example Scorecard",
            "key": "example_scorecard",
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

    def fake_search(args):
        search_args.append(args)
        return {"success": True, "query": args.get("query"), "count": 1, "matches": []}

    fake_mcp = FakeMCP()
    facade = execute.PlexusRuntimeModule(
        fake_mcp,
        scorecards_lister=fake_list,
        scorecards_infoer=fake_info,
        scorecards_searcher=fake_search,
    )

    listed = facade.scorecards.list({"identifier": "hcs"})
    info = facade.scorecards.info({"id": "card-1"})
    searched = facade.scorecards.search({"query": "HCS"})

    assert listed == [{"id": "card-1", "name": "Example Scorecard"}]
    assert info["key"] == "example_scorecard"
    assert searched["count"] == 1
    assert list_args == [{"identifier": "hcs"}]
    assert info_args == [{"id": "card-1"}]
    assert search_args == [{"query": "HCS"}]
    assert fake_mcp.calls == []
    assert facade.api_calls == [
        "plexus.scorecards.list",
        "plexus.scorecards.info",
        "plexus.scorecards.search",
    ]


def test_tactus_dataflow_preserves_opaque_id_between_collection_calls(monkeypatch) -> None:
    """Dependent reads receive the exact opaque ID returned by discovery."""
    opaque_id = "0a0a0a0a-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    info_args: list[dict[str, Any]] = []

    def fake_list(args: dict[str, Any]) -> dict[str, Any]:
        assert args == {"return_metadata": True}
        return {
            "items": [{"id": opaque_id, "name": "Example Scorecard"}],
            "nextToken": None,
        }

    def fake_info(args: dict[str, Any]) -> dict[str, Any]:
        info_args.append(args)
        return {"name": "Example Scorecard", "sections": {"items": []}}

    runtime_module = execute.PlexusRuntimeModule

    def module_factory(*args, **kwargs):
        return runtime_module(
            *args,
            **kwargs,
            scorecards_lister=fake_list,
            scorecards_infoer=fake_info,
        )

    monkeypatch.setattr(execute, "PlexusRuntimeModule", module_factory)
    result = execute._run_tactus_sync(
        """
        local page = plexus.scorecards.list({ return_metadata = true })
        local record = page.items[1]
        local detail = plexus.scorecards.info({ identifier = record.id })
        return { id = record.id, name = detail.name }
        """,
        FastMCP("test-opaque-value-dataflow"),
        trace_id="trace-opaque-value-dataflow",
        trace_store=_RecordingTraceStore(),
    )

    assert result["ok"] is True
    assert result["value"] == {
        "id": opaque_id,
        "name": "Example Scorecard",
    }
    assert info_args == [{"identifier": opaque_id}]


def test_complete_collection_program_returns_empty_coverage_without_batch_call(
    monkeypatch,
) -> None:
    batch_calls: list[dict[str, Any]] = []

    def fake_list(args: dict[str, Any]) -> dict[str, Any]:
        assert args == {"return_metadata": True}
        return {"items": [], "nextToken": None}

    runtime_module = execute.PlexusRuntimeModule

    def module_factory(*args, **kwargs):
        module = runtime_module(*args, **kwargs, scorecards_lister=fake_list)
        module._feedback_aligner_batch = lambda batch_args: batch_calls.append(batch_args)
        return module

    monkeypatch.setattr(execute, "PlexusRuntimeModule", module_factory)
    result = execute._run_tactus_sync(
        """
        local page = plexus.scorecards.list({ return_metadata = true })
        local scorecard_ids = {}
        for _, record in ipairs(page.items or {}) do
          scorecard_ids[#scorecard_ids + 1] = record.id
        end
        if #scorecard_ids == 0 then
          return { complete = true, discovered = 0, coverage = {
            target_count = 0, completed_count = 0, failed_count = 0, complete = true,
          } }
        end
        local analysis = plexus.feedback.alignment_batch({ scorecards = scorecard_ids })
        return analysis.coverage
        """,
        FastMCP("test-empty-complete-coverage"),
        trace_id="trace-empty-complete-coverage",
        trace_store=_RecordingTraceStore(),
    )

    assert result["ok"] is True
    assert result["value"] == {
        "complete": True,
        "discovered": 0,
        "coverage": {
            "target_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "complete": True,
        },
    }
    assert batch_calls == []
    assert result["api_calls"] == ["plexus.scorecards.list"]


def test_complete_collection_program_retries_failed_page_then_stops_before_batch(
    monkeypatch,
) -> None:
    page_two_attempts = 0
    batch_calls: list[dict[str, Any]] = []

    def fake_list(args: dict[str, Any]) -> dict[str, Any]:
        nonlocal page_two_attempts
        if args == {"return_metadata": True}:
            return {
                "items": [{"id": "scorecard-one", "name": "One"}],
                "nextToken": "page-two",
            }
        assert args == {"return_metadata": True, "next_token": "page-two"}
        page_two_attempts += 1
        return None

    runtime_module = execute.PlexusRuntimeModule

    def module_factory(*args, **kwargs):
        module = runtime_module(*args, **kwargs, scorecards_lister=fake_list)
        module._feedback_aligner_batch = lambda batch_args: batch_calls.append(batch_args)
        return module

    monkeypatch.setattr(execute, "PlexusRuntimeModule", module_factory)
    result = execute._run_tactus_sync(
        """
        local token, pages, scorecard_ids = nil, 0, {}
        repeat
          local ok, page = pcall(function()
            local args = { return_metadata = true }
            if token then args.next_token = token end
            return plexus.scorecards.list(args)
          end)
          if ok and page == nil then ok = false end
          if not ok then
            ok, page = pcall(function()
              return plexus.scorecards.list({ return_metadata = true, next_token = token })
            end)
          end
          if ok and page == nil then ok = false end
          if not ok then
            return { complete = false, pages = pages, error = "continuation page failed after retry" }
          end
          pages = pages + 1
          for _, record in ipairs(page.items or {}) do
            scorecard_ids[#scorecard_ids + 1] = record.id
          end
          token = page.nextToken
        until not token
        local analysis = plexus.feedback.alignment_batch({ scorecards = scorecard_ids })
        return analysis.coverage
        """,
        FastMCP("test-incomplete-collection-coverage"),
        trace_id="trace-incomplete-collection-coverage",
        trace_store=_RecordingTraceStore(),
    )

    assert result["ok"] is True
    assert result["value"]["complete"] is False
    assert result["value"]["pages"] == 1
    assert result["value"]["error"] == "continuation page failed after retry"
    assert page_two_attempts == 2
    assert batch_calls == []


def test_default_scorecards_list_returns_metadata_for_account_wide_pages(monkeypatch) -> None:
    """Metadata pagination remains available without identifier resolution."""
    from plexus.cli.shared import client_utils, memoized_resolvers

    queries: list[str] = []

    class FakeClient:
        def execute(self, query: str) -> dict[str, Any]:
            queries.append(query)
            if 'nextToken: "page-2"' in query:
                return {
                    "listScorecards": {
                        "items": [{"id": "card-2", "name": "Duplicate"}],
                        "nextToken": None,
                    }
                }
            return {
                "listScorecards": {
                    "items": [{"id": "card-1", "name": "Duplicate"}],
                    "nextToken": "page-2",
                }
            }

    monkeypatch.setattr(client_utils, "create_client", FakeClient)
    monkeypatch.setattr(execute, "_resolve_runtime_account_id", lambda *_args: "account-1")
    monkeypatch.setattr(
        memoized_resolvers,
        "memoized_resolve_scorecard_identifier",
        lambda *_args: (_ for _ in ()).throw(AssertionError("enumeration must not resolve an identifier")),
    )

    first_page = execute._default_scorecards_list({"return_metadata": True})
    second_page = execute._default_scorecards_list(
        {"return_metadata": True, "next_token": first_page["nextToken"]}
    )

    assert first_page == {
        "items": [{"id": "card-1", "name": "Duplicate"}],
        "nextToken": "page-2",
    }
    assert second_page == {
        "items": [{"id": "card-2", "name": "Duplicate"}],
        "nextToken": None,
    }
    assert len(queries) == 2
    assert 'nextToken: "page-2"' in queries[1]


def test_default_scorecards_list_requests_only_newest_version_activity_for_rank_inventory(
    monkeypatch,
) -> None:
    """Exhaustive rank inventory receives immutable score activity evidence."""
    from plexus.cli.shared import client_utils

    queries: list[str] = []
    opaque_version_id = "version:opaque/with+punctuation_123"

    class FakeClient:
        def execute(self, query: str) -> dict[str, Any]:
            queries.append(query)
            return {
                "listScorecards": {
                    "items": [{
                        "id": "card-1",
                        "sections": {"items": [{"scores": {"items": [{
                            "id": "score-1",
                            "updatedAt": "2024-02-03T04:05:06Z",
                            "versions": {"items": [{
                                "id": opaque_version_id,
                                "createdAt": "2024-02-02T03:04:05Z",
                            }]},
                        }]}}]},
                    }],
                    "nextToken": None,
                }
            }

    monkeypatch.setattr(client_utils, "create_client", FakeClient)
    monkeypatch.setattr(execute, "_resolve_runtime_account_id", lambda *_args: "account-1")

    result = execute._default_scorecards_list({
        "return_metadata": True,
        "_include_scores": True,
    })

    assert result["items"][0]["sections"]["items"][0]["scores"]["items"][0]["versions"]["items"][0]["id"] == opaque_version_id
    query = queries[0]
    assert "id name championVersionId isDisabled updatedAt" in query
    assert "versions(sortDirection: DESC, limit: 1)" in query
    assert "items { id createdAt }" in query


def test_default_scorecards_list_uses_identifier_resolution_for_single_record_lookup(monkeypatch) -> None:
    """Targeted single-record lookup retains its canonical resolver behavior."""
    from plexus.cli.shared import client_utils, memoized_resolvers

    class FakeClient:
        def execute(self, query: str) -> dict[str, Any]:
            assert "getScorecard(id: \"card-1\")" in query
            return {"getScorecard": {"id": "card-1", "name": "Duplicate"}}

    monkeypatch.setattr(client_utils, "create_client", FakeClient)
    monkeypatch.setattr(
        memoized_resolvers,
        "memoized_resolve_scorecard_identifier",
        lambda _client, identifier: "card-1" if identifier == "Duplicate" else None,
    )

    assert execute._default_scorecards_list({"identifier": "Duplicate"}) == [
        {"id": "card-1", "name": "Duplicate"}
    ]


def test_default_score_update_applies_actor_attribution(monkeypatch) -> None:
    from plexus.cli.shared import client_utils, direct_identifier_resolution
    from plexus.linting import schemas

    mutation_inputs: list[dict[str, Any]] = []

    class FakeClient:
        context = SimpleNamespace(
            actor_user_id="user-123",
            actor_type="agent",
            actor_key="optimizer-agent",
            actor_source="agent",
        )

        def execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
            if "GetParentScoreVersionGuidelines" in query:
                return {
                    "getScoreVersion": {
                        "id": variables["id"],
                        "guidelines": "# Legacy parent guidelines\n",
                    }
                }
            if "GetScoreVersionForConsoleAudit" in query:
                if variables["id"] == "parent-123":
                    return {
                        "getScoreVersion": {
                            "id": "parent-123",
                            "configuration": "name: old\n",
                            "guidelines": "# Legacy parent guidelines\n",
                        }
                    }
                return {
                    "getScoreVersion": {
                        "id": "version-123",
                        "configuration": "name: Test\nkey: test\nclass: LangGraphScore\n",
                        "guidelines": "# Legacy parent guidelines\n",
                    }
                }
            if "createScoreVersion" in query:
                mutation_inputs.append(variables["input"])
                return {"createScoreVersion": {"id": "version-123", "createdAt": "now"}}
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(client_utils, "create_client", lambda: FakeClient())
    monkeypatch.setattr(
        direct_identifier_resolution,
        "direct_resolve_scorecard_identifier",
        lambda client, identifier: "scorecard-123",
    )
    monkeypatch.setattr(
        direct_identifier_resolution,
        "direct_resolve_score_identifier",
        lambda client, scorecard_id, identifier: "score-123",
    )
    monkeypatch.setattr(
        schemas,
        "create_score_linter",
        lambda: SimpleNamespace(
            lint=lambda code: SimpleNamespace(is_valid=True, messages=[])
        ),
    )

    result = execute._default_score_update(
        {
            "scorecard_identifier": "Example Scorecard",
            "score_identifier": "Example Score",
            "code": "name: Test\nkey: test\nclass: LangGraphScore\n",
            "parent_version_id": "parent-123",
            "version_note": "candidate",
        }
    )

    assert result["success"] is True
    assert result["version_id"] == "version-123"
    assert mutation_inputs
    created = mutation_inputs[0]
    assert created["createdByUserId"] == "user-123"
    assert isinstance(created["metadata"], str)
    metadata = json.loads(created["metadata"])
    assert metadata["attribution"] == {
        "actorType": "agent",
        "actorKey": "optimizer-agent",
        "source": "agent",
        "requestUserId": "user-123",
    }
    assert result["changed_fields"] == ["code"]
    assert result["version_url"] == "/lab/scorecards/scorecard-123/scores/score-123/versions/version-123"
    assert result["parent_version_url"] == "/lab/scorecards/scorecard-123/scores/score-123/versions/parent-123"
    assert result["diffs"]["code"]["has_changes"] is True


def test_default_rubric_memory_recent_entries_runs_provider_awaitable(monkeypatch) -> None:
    class FakeCitation:
        def model_dump(self, mode: str = "json") -> dict:
            return {"id": "citation-1", "mode": mode}

    class FakeContext:
        markdown_context = "Recent rubric context"
        citation_index = [FakeCitation()]
        machine_context = {"topic": "project-intent"}
        diagnostics = []

    class FakeProvider:
        def __init__(self, api_client) -> None:
            self.api_client = api_client

        async def retrieve_recent(self, **kwargs):
            assert kwargs["score_id"] == "score-1"
            return FakeContext()

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        object,
    )
    monkeypatch.setattr(
        execute,
        "_resolve_rubric_memory_score_id",
        lambda client, scorecard_identifier, score_identifier, score_id: "score-1",
    )
    monkeypatch.setattr(
        "plexus.rubric_memory.RubricMemoryRecentBriefingProvider",
        FakeProvider,
    )

    result = execute._default_rubric_memory_recent_entries(
        {"scorecard_identifier": "card", "score_identifier": "score"}
    )

    assert result["success"] is True
    assert result["score_id"] == "score-1"
    assert result["markdown_context"] == "Recent rubric context"
    assert result["citation_index"] == [{"id": "citation-1", "mode": "json"}]


def test_default_rubric_memory_evidence_pack_runs_provider_awaitable(monkeypatch) -> None:
    class FakeCitation:
        def model_dump(self, mode: str = "json") -> dict:
            return {"id": "citation-2", "mode": mode}

    class FakeContext:
        markdown_context = "Evidence context"
        citation_index = [FakeCitation()]
        machine_context = {"item": "item-1"}
        diagnostics = []

    class FakeProvider:
        def __init__(self, api_client) -> None:
            self.api_client = api_client

        async def retrieve_for_score_item(self, **kwargs):
            assert kwargs["score_id"] == "score-1"
            return FakeContext()

        async def generate_for_score_item(self, **kwargs):
            raise AssertionError("synthesize=false should use retrieval-only context")

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        object,
    )
    monkeypatch.setattr(
        execute,
        "_resolve_rubric_memory_score_id",
        lambda client, scorecard_identifier, score_identifier, score_id: "score-1",
    )
    monkeypatch.setattr(
        "plexus.rubric_memory.RubricMemoryContextProvider",
        FakeProvider,
    )

    result = execute._default_rubric_memory_evidence_pack(
        {"scorecard_identifier": "card", "score_identifier": "score"}
    )

    assert result["success"] is True
    assert result["synthesized"] is False
    assert result["score_id"] == "score-1"
    assert result["markdown_context"] == "Evidence context"
    assert result["citation_index"] == [{"id": "citation-2", "mode": "json"}]


def test_default_procedure_chat_messages_handles_null_sequence_number(
    monkeypatch,
) -> None:
    """Regression: GraphQL may return ChatMessage.sequenceNumber=null.

    Prior to the fix, _default_procedure_chat_messages sorted messages with
    `m.get("sequenceNumber", 0)`, but the default only fires when the key is
    absent. A None value made `sorted` raise
    `'<' not supported between instances of 'NoneType' and 'int'`, which the
    Tactus runtime surfaced as a confusing "Failed to parse DSL" error.
    """

    session_payload = {
        "id": "session-1",
        "status": "COMPLETED",
        "procedureId": "proc-1",
        "createdAt": "2026-05-04T13:00:00Z",
        "messages": {
            "items": [
                {
                    "id": "msg-2",
                    "role": "ASSISTANT",
                    "messageType": "MESSAGE",
                    "toolName": None,
                    "content": "second",
                    "toolResponse": None,
                    "sequenceNumber": 2,
                    "parentMessageId": None,
                    "createdAt": "2026-05-04T13:00:02Z",
                },
                {
                    "id": "msg-null",
                    "role": "USER",
                    "messageType": "MESSAGE",
                    "toolName": None,
                    "content": "no sequence",
                    "toolResponse": None,
                    "sequenceNumber": None,
                    "parentMessageId": None,
                    "createdAt": "2026-05-04T13:00:00Z",
                },
                {
                    "id": "msg-1",
                    "role": "USER",
                    "messageType": "MESSAGE",
                    "toolName": None,
                    "content": "first",
                    "toolResponse": None,
                    "sequenceNumber": 1,
                    "parentMessageId": None,
                    "createdAt": "2026-05-04T13:00:01Z",
                },
            ]
        },
    }

    class FakeClient:
        def execute(self, query: str, variables: dict | None = None) -> dict:
            assert "getChatSession" in query
            return {"data": {"getChatSession": session_payload}}

    monkeypatch.setattr(
        "plexus.dashboard.api.client.PlexusDashboardClient",
        lambda *a, **kw: FakeClient(),
    )

    result = execute._default_procedure_chat_messages(
        {"session_id": "session-1"}
    )

    assert isinstance(result, dict)
    sessions = result["sessions"] if "sessions" in result else result.get("data", {}).get("sessions")
    assert sessions, f"expected sessions in result, got: {result!r}"
    messages = sessions[0]["messages"]
    assert [m["id"] for m in messages] == ["msg-null", "msg-1", "msg-2"], (
        "Null sequenceNumber should sort first (treated as 0); other messages "
        f"should keep ascending order. Got: {[m['id'] for m in messages]!r}"
    )


def test_default_scorecards_search_ranks_matches(monkeypatch) -> None:
    items = [
        {
            "id": "sc-z",
            "name": "Zebra Analytics",
            "key": "zebra",
            "externalId": "ext-z",
            "description": "",
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-02T00:00:00Z",
        },
        {
            "id": "sc-a",
            "name": "Example Scorecard",
            "key": "example_scorecard",
            "externalId": "ext-hcs",
            "description": "health",
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-02T00:00:00Z",
        },
    ]

    class FakeClient:
        def execute(self, query: str, variables: dict | None = None) -> dict:
            assert "listScorecards" in query
            return {"listScorecards": {"items": items, "nextToken": None}}

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: FakeClient()
    )

    result = execute._default_scorecards_search(
        {
            "query": "Example Scorecard",
            "limit": 5,
            "account_id": "00000000-0000-0000-0000-000000000001",
        }
    )
    assert result["success"] is True
    assert result["count"] == 1
    assert result["matches"][0]["scorecard"]["id"] == "sc-a"
    assert result["matches"][0]["match_score"] >= 55.0


def test_default_score_search_cross_scorecards_and_scorecard_filter(monkeypatch) -> None:
    nested = {
        "items": [
            {
                "id": "sc-one",
                "name": "Card One",
                "key": "c1",
                "sections": {
                    "items": [
                        {
                            "id": "sec-1",
                            "name": "Main",
                            "scores": {
                                "items": [
                                    {
                                        "id": "score-a",
                                        "name": "Refund Policy",
                                        "key": "refund_a",
                                        "externalId": "e-a",
                                        "description": "",
                                        "type": "LANGGRAPH",
                                        "championVersionId": "v1",
                                        "isDisabled": False,
                                    }
                                ]
                            },
                        }
                    ]
                },
            },
            {
                "id": "sc-two",
                "name": "Card Two",
                "key": "c2",
                "sections": {
                    "items": [
                        {
                            "id": "sec-2",
                            "name": "Main",
                            "scores": {
                                "items": [
                                    {
                                        "id": "score-b",
                                        "name": "Refund Escalation",
                                        "key": "refund_b",
                                        "externalId": "e-b",
                                        "description": "",
                                        "type": "LANGGRAPH",
                                        "championVersionId": "v2",
                                        "isDisabled": False,
                                    }
                                ]
                            },
                        }
                    ]
                },
            },
        ]
    }

    class FakeClient:
        def execute(self, query: str, variables: dict | None = None) -> dict:
            if "ListScorecardsForScoreSearch" in query:
                return {"listScorecards": nested}
            if "GetScorecardWithScores" in query:
                return {"getScorecard": nested["items"][0]}
            raise AssertionError(f"Unexpected query: {query!r}")

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: FakeClient()
    )
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda client, key: "00000000-0000-0000-0000-000000000001",
    )

    wide = execute._default_score_search({"query": "Refund", "limit": 10, "min_score": 40.0})
    assert wide["success"] is True
    assert wide["count"] == 2
    ids = {m["score_id"] for m in wide["matches"]}
    assert ids == {"score-a", "score-b"}
    assert wide["matches"][0]["match_score"] >= wide["matches"][1]["match_score"]

    monkeypatch.setattr(
        "plexus.cli.scorecard.scorecards.resolve_scorecard_identifier",
        lambda client, ident: "sc-one" if ident == "Card One" else None,
    )
    narrow = execute._default_score_search(
        {"query": "Refund", "scorecard": "Card One", "limit": 5}
    )
    assert narrow["success"] is True
    assert narrow["count"] == 1
    assert narrow["matches"][0]["score_id"] == "score-a"
    assert narrow["matches"][0]["scorecard_id"] == "sc-one"


def test_default_score_set_champion_serializes_champion_history_metadata(
    monkeypatch,
) -> None:
    captured_version_inputs: list[dict] = []

    class FakeClient:
        def execute(self, query: str, variables: dict | None = None) -> dict:
            if "GetScoreVersionForChampionGuard" in query:
                return {
                    "getScore": {"id": "score-1", "championVersionId": "version-1"},
                    "getScoreVersion": {
                        "id": "version-1",
                        "scoreId": "score-1",
                        "configuration": "name: test",
                        "metadata": None,
                        "createdAt": "2026-05-01T00:00:00.000Z",
                    },
                }
            if "mutation UpdateScore(" in query:
                return {
                    "updateScore": {
                        "id": variables["input"]["id"],
                        "championVersionId": variables["input"]["championVersionId"],
                    }
                }
            if "UpdateScoreVersionMetadata" in query:
                captured_version_inputs.append(variables["input"])
                return {
                    "updateScoreVersion": {
                        "id": variables["input"]["id"],
                        "isFeatured": variables["input"].get("isFeatured"),
                        "metadata": variables["input"].get("metadata"),
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: FakeClient()
    )

    result = execute._default_score_set_champion(
        {"score_id": "score-1", "version_id": "version-1"}
    )

    assert result["success"] is True
    assert len(captured_version_inputs) == 1
    update_input = captured_version_inputs[0]
    assert update_input["scoreId"] == "score-1"
    assert update_input["createdAt"] == "2026-05-01T00:00:00.000Z"
    assert update_input["isFeatured"] == "true"
    assert isinstance(update_input["metadata"], str)
    metadata = json.loads(update_input["metadata"])
    assert metadata["championHistory"][0]["scoreId"] == "score-1"
    assert metadata["championHistory"][0]["versionId"] == "version-1"
    assert metadata["championHistory"][0]["exitedAt"] is None


def test_default_score_update_serializes_attribution_metadata(monkeypatch) -> None:
    captured_inputs: list[dict] = []

    class FakeClient:
        context = SimpleNamespace(account_id="account-1")

        def execute(self, query: str, variables: dict | None = None) -> dict:
            if "GetScoreChampionId" in query:
                return {"getScore": {"championVersionId": "version-1"}}
            if "GetScoreVersionForConsoleAudit" in query:
                if variables["id"] == "version-1":
                    return {
                        "getScoreVersion": {
                            "id": "version-1",
                            "configuration": "name: old\n",
                            "guidelines": "# old\n",
                        }
                    }
                return {
                    "getScoreVersion": {
                        "id": "version-2",
                        "configuration": "name: old\n",
                        "guidelines": captured_inputs[0]["guidelines"],
                    }
                }
            if "CreateScoreVersion" in query:
                captured_inputs.append(variables["input"])
                return {
                    "createScoreVersion": {
                        "id": "version-2",
                        "createdAt": "2026-05-08T00:00:00.000Z",
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setenv("PLEXUS_ACTOR_USER_ID", "user-1")
    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        "plexus.cli.shared.direct_identifier_resolution.direct_resolve_scorecard_identifier",
        lambda _client, _identifier: "scorecard-1",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.direct_identifier_resolution.direct_resolve_score_identifier",
        lambda _client, _scorecard_id, _identifier: "score-1",
    )

    result = execute._default_score_update(
        {
            "scorecard_identifier": "Scorecard",
            "score_identifier": "Score",
            "guidelines": (
                "# Test Classifier\n\n"
                "## Objective\n\n"
                "Classify Yes/No.\n\n"
                "## Classes\n"
                "- Valid labels: [Yes, No]\n"
                "- Target class: Yes\n"
                "- Default class: No\n\n"
                "## Definition of Yes\n\n"
                "Positive class.\n\n"
                "## Conditions for Yes\n\n"
                "- Condition.\n\n"
                "## Definition of No\n\n"
                "Negative class.\n\n"
                "## Conditions for No\n\n"
                "- Condition.\n"
            ),
            "version_note": "Test version",
        }
    )

    assert result["success"] is True
    assert result["version_id"] == "version-2"
    metadata = captured_inputs[0]["metadata"]
    assert isinstance(metadata, str)
    parsed = json.loads(metadata)
    assert parsed["attribution"]["requestUserId"] == "user-1"
    assert parsed["attribution"]["source"] == "execute_tactus"
    assert result["guidelines_validation"]["is_valid"] is True
    assert result["changed_fields"] == ["guidelines"]
    assert result["configuration_preserved"] is True
    assert result["configuration_source"] == "parent_version"
    assert captured_inputs[0]["configuration"] == "name: old\n"
    assert result["diffs"]["guidelines"]["has_changes"] is True
    assert result["post_submit_test"] == {
        "status": "skipped",
        "reason": "guidelines_only_no_behavior_change",
    }
    assert result["post_submit_verification"] == {
        "status": "passed",
        "kind": "guidelines_only_persistence",
        "guidelines_valid": True,
        "guidelines_persisted": True,
        "configuration_unchanged": True,
    }
    assert result["version_url"] == "/lab/scorecards/scorecard-1/scores/score-1/versions/version-2"
    assert result["parent_version_url"] == "/lab/scorecards/scorecard-1/scores/score-1/versions/version-1"


def test_default_score_update_rejects_invalid_guidelines_before_mutation(monkeypatch) -> None:
    create_score_version_called = False

    class FakeClient:
        def execute(self, query: str, variables: dict | None = None) -> dict:
            nonlocal create_score_version_called
            if "CreateScoreVersion" in query:
                create_score_version_called = True
            if "GetScoreChampionId" in query:
                return {"getScore": {"championVersionId": "version-1"}}
            return {}

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        "plexus.cli.shared.direct_identifier_resolution.direct_resolve_scorecard_identifier",
        lambda _client, _identifier: "scorecard-1",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.direct_identifier_resolution.direct_resolve_score_identifier",
        lambda _client, _scorecard_id, _identifier: "score-1",
    )

    result = execute._default_score_update(
        {
            "scorecard_identifier": "Scorecard",
            "score_identifier": "Score",
            "guidelines": "# Invalid\n\nNo classes section.\n",
        }
    )

    assert result["success"] is False
    assert result["error_code"] == "guidelines_validation_failed"
    assert result["guidelines_validation"]["is_valid"] is False
    assert create_score_version_called is False


def test_default_score_update_preserves_parent_guidelines_for_code_only_edits(
    monkeypatch,
) -> None:
    captured_inputs: list[dict] = []

    class FakeClient:
        def execute(self, query: str, variables: dict | None = None) -> dict:
            if "GetScoreChampionId" in query:
                return {
                    "getScore": {
                        "championVersionId": "version-parent",
                        "championVersion": {"guidelines": "# Legacy rubric\n\nFreeform text.\n"},
                    }
                }
            if "GetScoreVersionForConsoleAudit" in query:
                if variables["id"] == "version-parent":
                    return {
                        "getScoreVersion": {
                            "id": "version-parent",
                            "configuration": "name: baseline\n",
                            "guidelines": "# Legacy rubric\n\nFreeform text.\n",
                        }
                    }
                return {
                    "getScoreVersion": {
                        "id": "version-child",
                        "configuration": "name: updated\n",
                        "guidelines": "# Legacy rubric\n\nFreeform text.\n",
                    }
                }
            if "CreateScoreVersion" in query:
                captured_inputs.append(variables["input"])
                return {"createScoreVersion": {"id": "version-child", "createdAt": "now"}}
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        "plexus.cli.shared.direct_identifier_resolution.direct_resolve_scorecard_identifier",
        lambda _client, _identifier: "scorecard-1",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.direct_identifier_resolution.direct_resolve_score_identifier",
        lambda _client, _scorecard_id, _identifier: "score-1",
    )

    result = execute._default_score_update(
        {
            "scorecard_identifier": "Scorecard",
            "score_identifier": "Score",
            "code": "name: updated\n",
            "version_note": "code-only",
        }
    )

    assert result["success"] is True
    assert result["version_id"] == "version-child"
    assert result["guidelines_preserved"] is True
    assert result["guidelines_source"] == "parent_version"
    assert captured_inputs
    assert captured_inputs[0]["guidelines"] == "# Legacy rubric\n\nFreeform text.\n"
    assert result["changed_fields"] == ["code"]
    assert result["diffs"]["code"]["has_changes"] is True


def test_default_score_update_preserves_empty_parent_guidelines_for_code_only_edits(
    monkeypatch,
) -> None:
    captured_inputs: list[dict] = []

    class FakeClient:
        def execute(self, query: str, variables: dict | None = None) -> dict:
            if "GetScoreChampionId" in query:
                return {
                    "getScore": {
                        "championVersionId": "version-parent",
                        "championVersion": {"guidelines": None},
                    }
                }
            if "GetScoreVersionForConsoleAudit" in query:
                if variables["id"] == "version-parent":
                    return {
                        "getScoreVersion": {
                            "id": "version-parent",
                            "configuration": "name: baseline\n",
                            "guidelines": None,
                        }
                    }
                return {
                    "getScoreVersion": {
                        "id": "version-child",
                        "configuration": "name: updated\n",
                        "guidelines": "",
                    }
                }
            if "CreateScoreVersion" in query:
                captured_inputs.append(variables["input"])
                return {"createScoreVersion": {"id": "version-child", "createdAt": "now"}}
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        "plexus.cli.shared.direct_identifier_resolution.direct_resolve_scorecard_identifier",
        lambda _client, _identifier: "scorecard-1",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.direct_identifier_resolution.direct_resolve_score_identifier",
        lambda _client, _scorecard_id, _identifier: "score-1",
    )

    result = execute._default_score_update(
        {
            "scorecard_identifier": "Scorecard",
            "score_identifier": "Score",
            "code": "name: updated\n",
            "version_note": "code-only",
        }
    )

    assert result["success"] is True
    assert result["guidelines_preserved"] is True
    assert result["guidelines_source"] == "parent_version"
    assert captured_inputs[0]["guidelines"] == ""


def test_default_score_set_champion_does_not_duplicate_open_history_entry(
    monkeypatch,
) -> None:
    captured_version_inputs: list[dict] = []
    existing_metadata = {
        "championHistory": [
            {
                "scoreId": "score-1",
                "versionId": "version-1",
                "enteredAt": "2026-05-01T00:00:00+00:00",
                "exitedAt": None,
                "previousChampionVersionId": None,
                "nextChampionVersionId": None,
                "transitionId": "transition-existing",
            }
        ]
    }

    class FakeClient:
        def execute(self, query: str, variables: dict | None = None) -> dict:
            if "GetScoreVersionForChampionGuard" in query:
                return {
                    "getScore": {"id": "score-1", "championVersionId": "version-1"},
                    "getScoreVersion": {
                        "id": "version-1",
                        "scoreId": "score-1",
                        "configuration": "name: test",
                        "metadata": json.dumps(existing_metadata),
                        "createdAt": "2026-05-01T00:00:00.000Z",
                    },
                }
            if "mutation UpdateScore(" in query:
                return {
                    "updateScore": {
                        "id": variables["input"]["id"],
                        "championVersionId": variables["input"]["championVersionId"],
                    }
                }
            if "UpdateScoreVersionMetadata" in query:
                captured_version_inputs.append(variables["input"])
                return {
                    "updateScoreVersion": {
                        "id": variables["input"]["id"],
                        "isFeatured": variables["input"].get("isFeatured"),
                        "metadata": variables["input"].get("metadata"),
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: FakeClient()
    )

    result = execute._default_score_set_champion(
        {"score_id": "score-1", "version_id": "version-1"}
    )

    assert result["success"] is True
    metadata = json.loads(captured_version_inputs[0]["metadata"])
    assert metadata["championHistory"] == existing_metadata["championHistory"]


def test_default_score_set_champion_updates_previous_champion_metadata_only(
    monkeypatch,
) -> None:
    captured_version_inputs: list[dict] = []

    class FakeClient:
        def execute(self, query: str, variables: dict | None = None) -> dict:
            if "GetScoreVersionForChampionGuard" in query:
                return {
                    "getScore": {"id": "score-1", "championVersionId": "version-old"},
                    "getScoreVersion": {
                        "id": "version-new",
                        "scoreId": "score-1",
                        "configuration": "name: test",
                        "metadata": None,
                        "createdAt": "2026-05-02T00:00:00.000Z",
                    },
                }
            if "GetScoreVersionForManagement" in query:
                return {
                    "getScoreVersion": {
                        "id": "version-old",
                        "scoreId": "score-1",
                        "configuration": "name: old",
                        "guidelines": None,
                        "isFeatured": None,
                        "note": "old",
                        "branch": None,
                        "parentVersionId": None,
                        "metadata": None,
                        "createdAt": "2026-05-01T00:00:00.000Z",
                        "updatedAt": "2026-05-01T00:00:00.000Z",
                    },
                }
            if "mutation UpdateScore(" in query:
                return {
                    "updateScore": {
                        "id": variables["input"]["id"],
                        "championVersionId": variables["input"]["championVersionId"],
                    }
                }
            if "UpdateScoreVersionMetadata" in query:
                captured_version_inputs.append(variables["input"])
                return {
                    "updateScoreVersion": {
                        "id": variables["input"]["id"],
                        "isFeatured": variables["input"].get("isFeatured"),
                        "metadata": variables["input"].get("metadata"),
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: FakeClient()
    )

    result = execute._default_score_set_champion(
        {"score_id": "score-1", "version_id": "version-new"}
    )

    assert result["success"] is True
    assert len(captured_version_inputs) == 2

    incoming_input = captured_version_inputs[0]
    assert incoming_input["id"] == "version-new"
    assert incoming_input["scoreId"] == "score-1"
    assert incoming_input["createdAt"] == "2026-05-02T00:00:00.000Z"
    assert incoming_input["isFeatured"] == "true"

    outgoing_input = captured_version_inputs[1]
    assert outgoing_input["id"] == "version-old"
    assert set(outgoing_input) == {"id", "metadata"}
    outgoing_metadata = json.loads(outgoing_input["metadata"])
    assert outgoing_metadata["championHistory"][0]["versionId"] == "version-old"
    assert outgoing_metadata["championHistory"][0]["nextChampionVersionId"] == "version-new"
    assert outgoing_metadata["championHistory"][0]["exitedAt"] is not None


def test_plexus_facade_delegates_score_set_champion_to_direct_handler() -> None:
    champion_args: list[dict] = []

    def fake_set_champion(args):
        champion_args.append(args)
        return {"success": True, "championVersionId": args["version_id"]}

    facade = execute.PlexusRuntimeModule(
        FastMCP("test"),
        score_set_champion=fake_set_champion,
    )

    value = facade.score.set_champion({
        "score_id": "score-1",
        "version_id": "version-new",
    })

    assert value == {"success": True, "championVersionId": "version-new"}
    assert champion_args == [{"score_id": "score-1", "version_id": "version-new"}]
    assert facade.api_calls == ["plexus.score.set_champion"]


def test_dispatch_routes_scorecards_to_direct_handlers() -> None:
    assert execute.DIRECT_HANDLERS[("scorecards", "list")] == "_call_scorecards"
    assert execute.DIRECT_HANDLERS[("scorecards", "info")] == "_call_scorecards"
    assert execute.DIRECT_HANDLERS[("scorecards", "search")] == "_call_scorecards"
    assert execute.DIRECT_HANDLERS[("scorecards", "create")] == "_call_scorecards"
    assert ("scorecards", "list") not in execute.MCP_TOOL_MAP
    assert ("scorecards", "info") not in execute.MCP_TOOL_MAP
    assert ("scorecards", "search") not in execute.MCP_TOOL_MAP
    assert ("scorecards", "create") not in execute.MCP_TOOL_MAP


def test_dispatch_routes_score_to_direct_handlers() -> None:
    for method in ("info", "create", "search", "evaluations", "predict", "edit", "set_champion"):
        assert execute.DIRECT_HANDLERS[("score", method)] == "_call_score"
        assert ("score", method) not in execute.MCP_TOOL_MAP


def test_dispatch_routes_procedure_reads_to_direct_handlers() -> None:
    for method in ("list", "info", "chat_sessions", "chat_messages", "steering_messages"):
        assert execute.DIRECT_HANDLERS[("procedure", method)] == "_call_procedure_read"
        assert ("procedure", method) not in execute.MCP_TOOL_MAP


def test_dispatch_routes_procedure_archive_to_direct_handler() -> None:
    assert execute.DIRECT_HANDLERS[("procedure", "archive")] == "_call_procedure_write"
    assert ("procedure", "archive") not in execute.MCP_TOOL_MAP


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
        None,
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


def test_plexus_facade_uses_direct_procedure_archive_handler_without_mcp_loopback() -> None:
    received_args: dict[str, Any] = {}

    def fake_archive(args: dict[str, Any]) -> dict[str, Any]:
        received_args.update(args)
        return {"success": True, "procedure_id": args["id"], "status": "ARCHIVED"}

    class FakeMCP:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            raise AssertionError("plexus.procedure.archive must not call MCP tools")

    fake_mcp = FakeMCP()
    module = execute.PlexusRuntimeModule(fake_mcp, procedure_archive=fake_archive)

    value = module.procedure.archive({"id": "proc-1", "reason": "noise cleanup"})

    assert value == {"success": True, "procedure_id": "proc-1", "status": "ARCHIVED"}
    assert received_args == {"id": "proc-1", "reason": "noise cleanup"}
    assert module.api_calls == ["plexus.procedure.archive"]
    assert fake_mcp.calls == []


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
    (docs_dir / "score-yaml-format.md").write_text(
        "---\n"
        "id: score-authoring.score-yaml-format\n"
        "title: Score YAML Format\n"
        "summary: Test\n"
        "namespace: score-authoring\n"
        "status: canonical\n"
        "disclosure: reference\n"
        "audience: agent\n"
        "tags: [test]\n"
        "---\n"
        "# Score docs",
        encoding="utf-8",
    )

    class FakeMCP:
        def __init__(self) -> None:
            self.calls = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            raise AssertionError("plexus.docs.get must not call MCP tools")

    fake_mcp = FakeMCP()
    facade = execute.PlexusRuntimeModule(fake_mcp, docs_dir=str(docs_dir))

    value = facade.docs.get({"key": "score-authoring.score-yaml-format"})

    assert value["key"] == "score-authoring.score-yaml-format"
    assert value["id"] == "score-authoring.score-yaml-format"
    assert value["content"] == "# Score docs"
    assert value["metadata"]["title"] == "Score YAML Format"
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

    async with Client(mcp) as client:
        tools = await client.list_tools()
    tool = next(tool for tool in tools if tool.name == "execute_tactus")
    schema = tool.inputSchema

    assert "tactus" in schema["properties"]
    assert "lua" not in schema["properties"]
    assert "code" not in schema["properties"]
    assert schema["required"] == ["tactus"]


@pytest.mark.asyncio
async def test_execute_tactus_tool_description_contains_curated_examples() -> None:
    mcp = FastMCP("test-execute-tactus")
    execute.register_tactus_tools(mcp)

    async with Client(mcp) as client:
        tools = await client.list_tools()
    tool = next(tool for tool in tools if tool.name == "execute_tactus")
    description = tool.description or ""

    for term in (
        "execute_tactus",
        "plexus.docs.get",
        "api_list()",
        "docs_list()",
        "docs_get",
        "skills_list",
        "skills_get",
        "evaluate{",
        "predict{",
        "scorecards{",
        "scorecards_search{",
        "score_search{",
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
    assert "scorecard_identifier = \"My Scorecard\"" in description
    assert "score_identifier = \"Compliance Tone\"" in description
    assert "predict{ score_id" not in description


def test_execute_tactus_description_constant_includes_themed_doc_pointers() -> None:
    description = execute.EXECUTE_TACTUS_DESCRIPTION

    assert "mcp.execute-tactus-overview" in description, (
        "tool description should point at the canonical overview topic id"
    )
    assert "plexus.docs.list" in description, (
        "tool description should tell agents how to discover topics"
    )
    for namespace in (
        "mcp",
        "score-authoring",
        "evaluation-feedback",
        "procedures",
        "reports",
        "optimizer",
        "repo-workflows",
    ):
        assert namespace in description, (
            f"tool description should reference namespace {namespace!r}"
        )


def test_execute_tactus_description_teaches_complete_coverage_composition() -> None:
    description = execute.EXECUTE_TACTUS_DESCRIPTION

    assert "Never silently reduce complete requested coverage to a sample" in description
    assert "scorecards.list" in description
    assert "metadata pagination" in description
    assert "plexus.feedback.alignment_batch" in description
    assert "coverage" in description
    assert "Never return the unaggregated alignment batch payload" in description
    assert "ranked_from_count" in description
    assert "reviewed_error_opportunity" in description
    assert "evaluation-feedback.batch-operations-cookbook" in description
    assert (
        "for _, scorecard_result in ipairs(analysis.scorecards or {})"
        not in description
    )
    assert len(description) < 8_500
    assert "result = analysis" not in description


def test_execute_tactus_description_documents_optimization_approval_boundary() -> None:
    description = execute.EXECUTE_TACTUS_DESCRIPTION

    assert "plexus.optimization.rank" in description
    assert "plexus.optimization.run" in description
    assert "approved = true" in description
    assert "never promotes a champion" in description
    assert "no inline output fallback" in description
    assert "total_items * disagreement_rate" in description
    assert "evaluation-feedback.batch-operations-cookbook" in description


def test_execute_tactus_description_documents_scoped_optimization_ranking() -> None:
    description = execute.EXECUTE_TACTUS_DESCRIPTION

    assert "scorecard_ids" in description
    assert "scorecard_name_prefixes" in description
    assert "opaque" in description
    assert "literal case-insensitive" in description
    assert "empty arrays are invalid" in description


def test_execute_tactus_description_documents_fixed_optimization_cooldown() -> None:
    description = execute.EXECUTE_TACTUS_DESCRIPTION

    assert "score-activity-cooldown-v1" in description
    assert "168-hour inclusive cutoff" in description
    assert "score.updatedAt" in description
    assert "newest score-version `createdAt`" in description
    assert "recent_score_activity" in description
    assert "wait_for_cooldown" in description
    assert "rechecks live activity before dispatch" in description


def test_execute_tactus_description_teaches_progressive_disclosure() -> None:
    """The boot prompt must explicitly teach the docs_list -> docs_get pattern.

    Progressive disclosure is the whole reason agent docs carry YAML
    frontmatter: callers browse cheap metadata summaries first, then
    pay to load only the topic bodies they actually need. This test
    locks in the language so future edits can't silently regress to a
    "dump everything" model that would blow the token budget.
    """

    description = execute.EXECUTE_TACTUS_DESCRIPTION

    assert "progressive disclosure" in description.lower(), (
        "tool description should name the progressive-disclosure pattern"
    )
    # The two-step language: metadata summaries first, then full body.
    assert "metadata" in description.lower(), (
        "tool description should explain that docs_list returns metadata "
        "(not full bodies)"
    )
    for marker in ("summary", "id", "namespace", "tags", "related"):
        assert marker in description, (
            f"tool description should list metadata field {marker!r} so "
            "agents know what to filter on"
        )
    # Canonical accessor for docs_get.
    assert 'docs.get{ id = "' in description or 'docs_get{ id = "' in description, (
        "tool description should show the canonical "
        "`docs_get{ id = \"...\" }` form"
    )
    # The example block exists.
    assert 'docs_list{ namespace = "score-authoring" }' in description, (
        "tool description should include a concrete docs_list example "
        "filtered by namespace"
    )


def test_execute_tactus_description_teaches_skill_progressive_disclosure() -> None:
    description = execute.EXECUTE_TACTUS_DESCRIPTION

    assert "plexus.skills.list" in description
    assert "plexus.skills.get" in description
    assert "skills_list{}" in description
    assert "metadata only" in description
    assert "loads one full skill body" in description
    assert "Cite the skill id" in description
    assert "Do not preload every skill" in description


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

    async with Client(mcp) as client:
        result = await client.call_tool(
            "execute_tactus", {"tactus": "return { ok = true }"}
        )

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
async def test_execute_tactus_score_predict_uses_canonical_identifiers(
    monkeypatch,
) -> None:
    mcp = FastMCP("test-execute-tactus-predict-canonical")
    seen: dict[str, Any] = {}

    def fake_score_predict(args):
        seen.update(args)
        return {"success": True, "predictions": [{"item_id": args["item_id"]}]}

    monkeypatch.setattr(execute, "_default_score_predict", fake_score_predict)

    result = await execute._execute_tactus_tool(
        (
            'return plexus.score.predict({ scorecard_identifier = "card", '
            'score_identifier = "score", item_id = "item-1" })'
        ),
        mcp,
        runtime_context={"account_id": "acct-console"},
    )

    assert result["ok"] is True
    assert result["value"] == {
        "success": True,
        "predictions": [{"item_id": "item-1"}],
    }
    assert result["api_calls"] == ["plexus.score.predict"]
    assert seen["scorecard_identifier"] == "card"
    assert seen["score_identifier"] == "score"
    assert seen["item_id"] == "item-1"
    assert seen["account_id"] == "acct-console"


def test_default_score_predict_requires_canonical_identifier_fields() -> None:
    with pytest.raises(
        ValueError,
        match="scorecard_identifier and score_identifier",
    ):
        execute._default_score_predict({"item_id": "item-1"})

    with pytest.raises(
        ValueError,
        match="scorecard_identifier and score_identifier",
    ):
        execute._default_score_predict(
            {"scorecard": "card", "score": "score", "item_id": "item-1"}
        )


def test_default_score_predict_requires_account_context(monkeypatch) -> None:
    fake_client = SimpleNamespace(
        context=SimpleNamespace(account_id=None, account_key=None)
    )

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: fake_client
    )
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("default account resolver should not run")
        ),
    )

    with pytest.raises(execute.AccountContextRequired, match="requires account context"):
        execute._default_score_predict(
            {
                "scorecard_identifier": "card",
                "score_identifier": "score",
                "item_id": "external-item",
            }
        )


def test_default_score_predict_uses_account_context_for_item_resolution(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeClient:
        def __init__(self):
            self.context = SimpleNamespace(account_id=None, account_key=None)

        def execute(self, query):
            if "getScorecard" in query:
                return {
                    "getScorecard": {
                        "id": "sc-id",
                        "name": "Example Scorecard",
                        "sections": {
                            "items": [
                                {
                                    "id": "section-1",
                                    "scores": {
                                        "items": [
                                            {
                                                "id": "score-id",
                                                "name": "Example Score",
                                                "key": "example-score",
                                                "externalId": "48849",
                                                "championVersionId": "version-1",
                                                "isDisabled": False,
                                            }
                                        ]
                                    },
                                }
                            ]
                        },
                    }
                }
            if "getItem" in query:
                return {
                    "getItem": {
                        "id": "item-internal",
                        "text": "hello",
                        "description": "",
                        "metadata": {},
                        "attachedFiles": None,
                        "externalId": "311432364",
                        "createdAt": "2026-05-07T00:00:00Z",
                        "updatedAt": "2026-05-07T00:00:00Z",
                    }
                }
            raise AssertionError(query)

    class FakeScorecard:
        scores = [
            {
                "id": "score-id",
                "name": "Example Score",
                "key": "example-score",
                "externalId": "48849",
            }
        ]

        def build_dependency_graph(self, names):
            captured["dependency_names"] = names
            return {}, {"Example Score": "score-id"}

        async def score_entire_text(self, **kwargs):
            captured["score_kwargs"] = kwargs
            return {
                "score-id": SimpleNamespace(
                    value="No",
                    explanation="prediction explanation",
                    cost={},
                    metadata={},
                )
            }

    fake_client = FakeClient()

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: fake_client
    )
    monkeypatch.setattr(
        "plexus.cli.scorecard.scorecards.resolve_scorecard_identifier",
        lambda client, identifier: f"sc:{identifier}",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.identifier_resolution.resolve_score_identifier",
        lambda client, scorecard_id, identifier: f"score:{identifier}",
    )

    def fake_resolve_item_identifier(client, identifier, account_id=None):
        captured["item_resolution"] = {
            "identifier": identifier,
            "account_id": account_id,
        }
        return "item-internal"

    monkeypatch.setattr(
        "plexus.cli.shared.identifier_resolution.resolve_item_identifier",
        fake_resolve_item_identifier,
    )
    def fake_load_scorecard_from_api(*args, **kwargs):
        captured["load_scorecard_from_api"] = {"args": args, "kwargs": kwargs}
        return FakeScorecard()

    monkeypatch.setattr(
        "plexus.cli.evaluation.evaluations.load_scorecard_from_api",
        fake_load_scorecard_from_api,
    )
    monkeypatch.setattr(
        "plexus.dashboard.api.models.item.Item.from_dict",
        lambda item_data, client: SimpleNamespace(id=item_data["id"]),
    )

    result = execute._default_score_predict(
        {
            "scorecard_identifier": "Example Scorecard",
            "score_identifier": "48849",
            "item_id": "311432364",
            "account_id": "acct-console",
        }
    )

    assert fake_client.context.account_id == "acct-console"
    assert captured["item_resolution"] == {
        "identifier": "311432364",
        "account_id": "acct-console",
    }
    assert captured["load_scorecard_from_api"]["kwargs"]["use_cache"] is False
    assert captured["dependency_names"] == ["Example Score"]
    assert captured["score_kwargs"]["subset_of_score_names"] == [
        "Example Score"
    ]
    assert result["success"] is True
    assert result["scorecard_identifier"] == "Example Scorecard"
    assert result["score_identifier"] == "48849"
    assert result["predictions"][0]["item_id"] == "item-internal"
    assert result["predictions"][0]["scores"][0]["value"] == "No"


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


def test_sanitize_instruction_string_literals_converts_to_lua_long_brackets() -> None:
    tactus = (
        "local edit = plexus.score.edit({ scorecard_identifier = \"sc\", "
        "score_identifier = \"s\", instruction = 'Tighten customer''s evidence requirement', "
        "async = true })\n"
    )

    sanitized = execute._sanitize_instruction_string_literals(tactus)

    assert "instruction = [[" in sanitized
    assert "customer''s evidence requirement" in sanitized
    assert "async = true" in sanitized


@pytest.mark.asyncio
async def test_execute_tactus_retries_once_after_unterminated_string_for_instruction(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def fake_run_tactus_sync(
        tactus,
        mcp,
        *,
        trace_id,
        trace_store,
        budget=None,
        **kwargs,
    ):
        calls.append(tactus)
        if len(calls) == 1:
            return {
                "ok": False,
                "value": None,
                "error": {
                    "code": "tactus_execution_failed",
                    "message": "Unterminated string starting at line 2 column 11",
                    "retryable": False,
                },
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
        return {
            "ok": True,
            "value": {"ok": True},
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

    snippet = (
        "local edit = plexus.score.edit({ scorecard_identifier = \"sc\", "
        "score_identifier = \"s\", instruction = 'Tighten customer''s evidence requirement', "
        "async = true })\n"
    )
    result = await execute._execute_tactus_tool(snippet, FastMCP("retry-test"))

    assert result["ok"] is True
    assert len(calls) == 2
    assert "instruction = [[" in calls[1]


def test_plexus_facade_rejects_unsupported_namespace_method() -> None:
    facade = execute.PlexusRuntimeModule(FastMCP("test"))

    with pytest.raises(ValueError, match="Unsupported Plexus runtime API"):
        facade._call("score", "no_such_method", {"id": "x"})


def test_plexus_api_list_advertises_known_namespaces() -> None:
    facade = execute.PlexusRuntimeModule(FastMCP("test"))

    catalog = facade.api.list()

    assert "plexus.docs" in catalog
    assert "plexus.skills" in catalog
    assert "plexus.guidelines" in catalog
    assert "plexus.api" in catalog
    assert "plexus.score" in catalog
    assert "info" in catalog["plexus.score"]
    assert "create" in catalog["plexus.score"]
    assert "plexus.scorecards" in catalog
    assert "create" in catalog["plexus.scorecards"]
    assert catalog["plexus.skills"] == ["get", "list"]
    assert catalog["plexus.guidelines"] == ["validate"]
    assert facade.api_calls == ["plexus.api.list"]


def test_optimization_namespace_advertises_all_decision_methods_and_helpers() -> None:
    module = execute.PlexusRuntimeModule(FastMCP("test-optimization-catalog"))

    assert module.api.list()["plexus.optimization"] == [
        "assess", "diagnose", "rank", "review", "run", "summary"
    ]
    helpers = {name for name, _, _ in execute.HELPER_BINDINGS}
    assert {
        "optimization_rank",
        "optimization_assess",
        "optimization_diagnose",
        "optimization_run",
        "optimization_review",
        "optimization_summary",
    } <= helpers


def test_optimization_read_methods_delegate_to_injected_handlers_in_planning_mode() -> None:
    calls: list[tuple[str, dict]] = []

    def handler(method: str):
        def invoke(args: dict) -> dict:
            calls.append((method, args))
            return {"packet_version": "optimization-decision-v1", "method": method}
        return invoke

    module = execute.PlexusRuntimeModule(
        FastMCP("test-optimization-planning"),
        runtime_context={"tool_access_mode": "planning", "account_id": "acct-opaque"},
        optimization_handlers={
            method: handler(method)
            for method in ("rank", "assess", "diagnose", "review", "summary")
        },
    )

    for method in ("rank", "assess", "diagnose", "review", "summary"):
        assert getattr(module.optimization, method)({"score_id": "score-opaque"})["method"] == method

    assert [method for method, _ in calls] == ["rank", "assess", "diagnose", "review", "summary"]
    assert all(args["account_id"] == "acct-opaque" for _, args in calls)
    assert module.api_calls == [f"plexus.optimization.{method}" for method, _ in calls]


def test_optimization_run_is_execution_only_and_never_promotes() -> None:
    dispatched: list[dict] = []
    promoted = False

    def fake_run(args: dict) -> dict:
        dispatched.append(args)
        return {"packet_version": "optimization-decision-v1", "dispatches": []}

    planning = execute.PlexusRuntimeModule(
        FastMCP("test-optimization-run-planning"),
        runtime_context={"tool_access_mode": "planning"},
        optimization_handlers={"run": fake_run},
    )
    with pytest.raises(execute.PlanningModeToolNotAllowed):
        planning.optimization.run({"approved": True, "targets": []})
    assert dispatched == []
    assert promoted is False

    execution = execute.PlexusRuntimeModule(
        FastMCP("test-optimization-run-execution"),
        optimization_handlers={"run": fake_run},
    )
    assert execution.optimization.run({"approved": True, "targets": []})["packet_version"] == "optimization-decision-v1"
    assert dispatched == [{"approved": True, "targets": []}]


def _ready_optimization_target(
    scorecard_id: str, score_id: str, champion_version: str, feedback_watermark: str
) -> dict:
    """Build an actual ready assessment packet for public-run provenance tests."""
    from plexus.optimization.decision import assess_investment

    assessment = assess_investment({
        "scorecard_id": scorecard_id, "score_id": score_id,
        "complete": True, "champion_version": champion_version,
        "feedback_watermark": feedback_watermark,
        "terminal_classes_resolved": True, "guideline_state": "consistent",
        "valid_feedback_count": 250, "reviewed_disagreements": 200,
        "reachable_classes": ["Yes", "No"],
        "final_label_counts": {"Yes": 125, "No": 125},
        "weekly_disagreement_rates": [0.8] * 4,
        "weekly_ac1_values": [0.7] * 4,
        "weekly_bucket_counts": [20] * 4,
        "score_activity": {
            "policy_version": "score-activity-cooldown-v1",
            "as_of": "2026-07-28T00:00:00Z",
            "cutoff": "2026-07-21T00:00:00Z",
            "complete": True,
            "recent": False,
            "score_updated_at": "2024-01-02T00:00:00Z",
            "activity_timestamp": "2024-01-02T00:00:00Z",
            "newest_version_id": "old-version",
            "newest_version_created_at": "2024-01-01T00:00:00Z",
            "activity_source": "score_record",
            "eligibility_timestamp": "2024-01-09T00:00:00Z",
            "failure": None,
        },
    })
    assert assessment["readiness_state"] == "ready_to_optimize"
    return {
        "scorecard_id": scorecard_id, "score_id": score_id,
        "assessment": assessment,
        "assessment_fingerprint": assessment["evidence_fingerprint"],
        "champion_version": champion_version,
        "feedback_watermark": feedback_watermark,
    }


def _old_live_score_info(champion_version: str) -> dict:
    return {
        "championVersionId": champion_version,
        "updatedAt": "2024-01-02T00:00:00Z",
        "versions": [{
            "id": "old-version",
            "createdAt": "2024-01-01T00:00:00Z",
        }],
    }


def _rank_inventory_card(card_id: str, score_id: str, champion_version: str) -> dict:
    return {
        "id": card_id,
        "name": card_id,
        "sections": {"items": [{"scores": {"items": [{
            "id": score_id,
            "name": score_id,
            "championVersionId": champion_version,
            "updatedAt": "2024-01-02T00:00:00Z",
            "versions": {"items": [{
                "id": "old-version",
                "createdAt": "2024-01-01T00:00:00Z",
            }]},
        }]}}]},
    }


def test_default_optimization_run_dispatches_only_exact_approved_targets() -> None:
    optimizer_calls: list[dict] = []

    module = execute.PlexusRuntimeModule(
        FastMCP("test-default-optimization-run"),
        score_info=lambda _args: _old_live_score_info("v-1"),
        feedback_latest_update=lambda _args: {"latest_feedback_updated_at": "2026-01-01T00:00:00Z"},
        procedure_optimize=lambda args: optimizer_calls.append(args) or {"procedure_id": "proc-1"},
    )

    rejected = module.optimization.run({"approved": False, "targets": [{"scorecard_id": "sc-1", "score_id": "s-1"}]})
    assert rejected["accepted_targets"] == []
    assert optimizer_calls == []

    result = module.optimization.run({
        "approved": True,
        "targets": [_ready_optimization_target(
            "sc-1", "s-1", "v-1", "2026-01-01T00:00:00Z"
        )],
        "max_iterations": 2, "max_samples": 20, "max_cost_usd": 1.0, "max_concurrency": 1,
    })

    assert result["rejected"] == []
    assert result["dispatches"][0]["target"] == {"scorecard_id": "sc-1", "score_id": "s-1"}
    assert result["dispatches"][0]["status"] == "dispatched"
    assert result["dispatch_coverage"]["complete"] is True
    assert optimizer_calls == [{
        "scorecard": "sc-1", "score": "s-1", "max_iterations": 2,
        "max_samples": 20, "max_cost_usd": 1.0,
    }]


def test_default_optimization_run_rejects_recent_score_activity_before_launch() -> None:
    optimizer_calls: list[dict] = []
    module = execute.PlexusRuntimeModule(
        FastMCP("test-optimization-run-recent-score-activity"),
        score_info=lambda _args: {
            "championVersionId": "v-1",
            "updatedAt": "2026-07-27T12:00:00Z",
            "versions": [{"id": "new-version", "createdAt": "2026-07-27T12:00:00Z"}],
        },
        feedback_latest_update=lambda _args: {
            "latest_feedback_updated_at": "2026-01-01T00:00:00Z",
        },
        procedure_optimize=lambda args: optimizer_calls.append(args) or {"procedure_id": "proc-1"},
    )

    result = module.optimization.run({
        "approved": True,
        "targets": [_ready_optimization_target(
            "sc-1", "s-1", "v-1", "2026-01-01T00:00:00Z"
        )],
        "max_iterations": 2, "max_samples": 20, "max_cost_usd": 1.0,
        "max_concurrency": 1,
    })

    assert optimizer_calls == []
    assert result["accepted_targets"] == []
    assert result["dispatches"] == []
    assert result["rejected"][0]["reason"] == "recent_score_activity"


def test_default_optimization_run_reports_each_dispatch_failure_without_losing_success() -> None:
    calls: list[str] = []
    targets = [
        _ready_optimization_target("card", score_id, "champion", "watermark")
        for score_id in ("good", "broken")
    ]
    module = execute.PlexusRuntimeModule(
        FastMCP("test-run-dispatch-coverage"),
        score_info=lambda _args: _old_live_score_info("champion"),
        feedback_latest_update=lambda _args: {"latest_feedback_updated_at": "watermark"},
        procedure_optimize=lambda args: (
            calls.append(args["score"])
            or ((_ for _ in ()).throw(RuntimeError("launch failed")) if args["score"] == "broken" else {"procedure_id": "procedure-good"})
        ),
    )

    result = module.optimization.run({
        "approved": True, "targets": targets, "max_cost_usd": 2.0,
        "max_samples": 40, "max_iterations": 2, "max_concurrency": 2,
        "current_fingerprints": {f"card:{target['score_id']}": target["assessment_fingerprint"] for target in targets},
    })

    assert calls == ["good", "broken"]
    assert [row["status"] for row in result["dispatches"]] == ["dispatched", "failed"]
    assert result["dispatch_coverage"] == {
        "target_count": 2,
        "dispatched_count": 1,
        "failed_count": 1,
        "complete": False,
    }


def test_default_optimization_rank_paginates_with_one_retry_and_one_frozen_alignment_read() -> None:
    page_calls: list[str | None] = []
    alignment_calls: list[dict] = []
    first_page_attempts = 0

    def list_cards(args: dict) -> dict:
        nonlocal first_page_attempts
        token = args.get("next_token")
        page_calls.append(token)
        if token is None:
            first_page_attempts += 1
            if first_page_attempts == 1:
                raise RuntimeError("transient page failure")
            return {"items": [_rank_inventory_card("sc-1", "s-1", "v-1")], "nextToken": "page-2"}
        return {"items": [_rank_inventory_card("sc-2", "s-2", "v-2")], "nextToken": None}

    def alignment(args: dict) -> dict:
        alignment_calls.append(args)
        return {
                "coverage": {
                    "complete": True,
                    "target_count": 2,
                    "completed_count": 2,
                    "failed_count": 0,
                },
            "scorecards": [
                {"scorecard_id": "sc-1", "scorecard_name": "One", "scores": [
                    {"score_id": "s-1", "score_name": "A", "champion_version": "v-1", "total_items": 10, "disagreements": 4}
                ]},
                {"scorecard_id": "sc-2", "scorecard_name": "Two", "scores": [
                    {"score_id": "s-2", "score_name": "B", "champion_version": "v-2", "total_items": 20, "disagreements": 2}
                ]},
            ],
        }

    module = execute.PlexusRuntimeModule(
        FastMCP("test-default-optimization-rank"),
        scorecards_lister=list_cards,
        feedback_aligner=lambda _args: {},
    )
    module._feedback_aligner_batch = alignment

    result = module.optimization.rank({"days": 90})

    assert page_calls == [None, None, "page-2"]
    assert alignment_calls[0]["scorecards"] == ["sc-1", "sc-2"]
    assert alignment_calls[0]["days"] == 90
    assert alignment_calls[0]["window_start"].endswith("T00:00:00Z")
    assert alignment_calls[0]["window_end"].endswith("T00:00:00Z")
    assert alignment_calls[0]["account_id"] is None
    assert result["exact"] is True
    assert [row["score_id"] for row in result["ranked"]] == ["s-1", "s-2"]


def test_optimization_persist_uses_one_exact_packet_handler(monkeypatch) -> None:
    packet = {"version": "optimization-decision-packet-v1", "value": "compact"}
    default_persisted: list[dict] = []
    monkeypatch.setattr(
        execute,
        "_default_optimization_persist",
        default_persisted.append,
    )
    default_module = execute.PlexusRuntimeModule(
        FastMCP("test-optimization-persistence-default"),
        optimization_handlers={"summary": lambda _args: packet},
    )
    assert default_module.optimization.summary({"persist": True}) is packet
    assert default_persisted == [packet]

    persisted: list[dict] = []
    module = execute.PlexusRuntimeModule(
        FastMCP("test-optimization-persistence-configured"),
        optimization_handlers={"summary": lambda _args: packet},
        optimization_persister=persisted.append,
    )
    assert module.optimization.summary({"persist": True}) is packet
    assert persisted == [packet]


def test_default_optimization_rank_uses_frozen_complete_window_and_inventory_metadata() -> None:
    alignment_calls: list[dict] = []

    def list_cards(_args: dict) -> dict:
        return {
            "items": [{
                "id": "sc-1",
                "name": "One",
                "sections": {"items": [{"scores": {"items": [
                        {**_rank_inventory_card("unused", "s-live", "v-1")["sections"]["items"][0]["scores"]["items"][0], "name": "Live", "isDisabled": False},
                        {"id": "s-off", "name": "Off", "championVersionId": "v-2", "isDisabled": True},
                ]}}]},
            }],
            "nextToken": None,
        }

    def alignment(args: dict) -> dict:
        alignment_calls.append(args)
        return {"coverage": {
            "complete": True,
            "target_count": 1,
            "completed_count": 1,
            "failed_count": 0,
        }, "scorecards": [{
            "scorecard_id": "sc-1", "scorecard_name": "One", "scores": [
                {"score_id": "s-live", "score_name": "Live", "total_items": 4, "disagreements": 2,
                 "class_distribution": [{"label": "Yes", "count": 3}], "predicted_class_distribution": [{"label": "Yes", "count": 4}]},
                {"score_id": "s-off", "score_name": "Off", "total_items": 4, "disagreements": 4},
            ],
        }]}

    module = execute.PlexusRuntimeModule(FastMCP("test-frozen-rank"), scorecards_lister=list_cards)
    module._feedback_aligner_batch = alignment
    result = module.optimization.rank({})

    assert alignment_calls[0]["days"] == 90
    assert alignment_calls[0]["window_start"].endswith("T00:00:00Z")
    assert alignment_calls[0]["window_end"].endswith("T00:00:00Z")
    frozen_as_of = datetime.fromisoformat(
        result["coverage"]["activity"]["as_of"].replace("Z", "+00:00")
    )
    frozen_window_end = datetime.fromisoformat(
        result["window"]["end"].replace("Z", "+00:00")
    )
    assert frozen_window_end == frozen_as_of.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    assert result["ranked"][0]["score_id"] == "s-live"
    assert result["ranked"][0]["valid_feedback_count"] == 4
    assert result["ranked"][0]["class_distribution"] == [{"label": "Yes", "count": 3}]
    assert result["unranked"][0]["score_id"] == "s-off"
    assert result["unranked"][0]["unranked_reason"] == "disabled"


def test_optimization_rank_never_labels_mismatched_analysis_coverage_exact() -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-rank-mismatched-analysis-coverage"),
        scorecards_lister=lambda _args: {
            "items": [{"id": "sc-1"}, {"id": "sc-2"}], "nextToken": None,
        },
    )
    module._feedback_aligner_batch = lambda _args: {
        "coverage": {
            "complete": True,
            "target_count": 1,
            "completed_count": 1,
            "failed_count": 0,
        },
        "scorecards": [{"scorecard_id": "sc-1", "scores": []}],
    }

    result = module.optimization.rank({})

    assert result["exact"] is False
    assert result["coverage"]["complete"] is False
    assert "does not match discovered scope" in str(result["coverage"]["failures"])


def test_default_optimization_run_rechecks_champion_and_feedback_watermark_before_dispatch() -> None:
    optimizer_calls: list[dict] = []
    score_calls: list[dict] = []
    feedback_calls: list[dict] = []

    def score_info(args: dict) -> dict:
        score_calls.append(args)
        return _old_live_score_info("v-current")

    def feedback_update(args: dict) -> dict:
        feedback_calls.append(args)
        return {"latest_feedback_updated_at": "2026-07-01T00:00:00Z"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-fresh-run"),
        score_info=score_info,
        feedback_latest_update=feedback_update,
        procedure_optimize=lambda args: optimizer_calls.append(args) or {"procedure_id": "p-1"},
    )
    target = _ready_optimization_target(
        "sc-1", "s-1", "v-assessed", "2026-06-01T00:00:00Z"
    )

    result = module.optimization.run({"approved": True, "targets": [target], "max_iterations": 2, "max_samples": 20, "max_cost_usd": 1.0, "max_concurrency": 1})

    assert result["accepted_targets"] == []
    assert result["dispatches"] == []
    assert "stale_assessment" in {row["reason"] for row in result["rejected"]}
    assert score_calls == [{"scorecard_identifier": "sc-1", "score_identifier": "s-1"}]
    assert feedback_calls == [{"scorecard_name": "sc-1", "score_name": "s-1", "days": 90}]
    assert optimizer_calls == []


def test_default_optimization_assess_composes_score_guidelines_classes_and_rank_evidence() -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-runtime-assess"),
        score_info=lambda _args: {
            "championVersionId": "v-1", "code": "classifier", "guidelines": "# Guidelines",
        },
        guidelines_validator=lambda _text: {"is_valid": True},
        terminal_class_resolver=lambda _code: {"classes": ["Yes", "No"]},
    )
    result = module.optimization.assess({
        "scorecard_id": "sc-1", "score_id": "s-1",
        "rank_evidence": {
            "coverage": {"complete": True}, "valid_feedback_count": 250,
            "scope": {"scorecard_id": "sc-1", "score_id": "s-1"},
            "window": {
                "start": "2026-04-01T00:00:00Z",
                "end": "2026-06-30T00:00:00Z",
                "timezone": "UTC",
                "complete_days": 90,
            },
            "reviewed_disagreements": 100,
            "class_distribution": [{"label": "Yes", "count": 200}],
            "weekly_disagreement_rates": [0.4, 0.4, 0.4, 0.4],
            "weekly_ac1_values": [0.7, 0.7, 0.7, 0.7],
            "weekly_bucket_counts": [1, 1, 1, 1],
                "feedback_watermark": "2026-07-01T00:00:00Z",
                "score_activity": {
                    "policy_version": "score-activity-cooldown-v1",
                    "as_of": "2026-07-28T00:00:00Z",
                    "cutoff": "2026-07-21T00:00:00Z",
                    "score_updated_at": "2024-01-02T00:00:00Z",
                    "newest_version_id": "old-version",
                    "newest_version_created_at": "2024-01-01T00:00:00Z",
                    "activity_timestamp": "2024-01-02T00:00:00Z",
                    "activity_source": "score_record",
                    "eligibility_timestamp": "2024-01-09T00:00:00Z",
                    "recent": False,
                    "complete": True,
                },
        },
    })

    assert result["scope"] == {"scorecard_id": "sc-1", "score_id": "s-1"}
    assert result["champion_version"] == "v-1"
    assert result["class_counts"] == {"Yes": 200, "No": 0}
    assert result["readiness_state"] == "insufficient_evidence"
    assert result["feedback_watermark"] == "2026-07-01T00:00:00Z"


def test_optimization_assess_exact_ids_compose_canonical_frozen_rank_evidence() -> None:
    alignment_calls: list[dict] = []
    module = execute.PlexusRuntimeModule(
        FastMCP("test-runtime-assess-id-only"),
            scorecards_lister=lambda _args: {
                "items": [_rank_inventory_card("sc-1", "s-1", "v-1")],
                "nextToken": None,
            },
        score_info=lambda _args: {
            "championVersionId": "v-1", "code": "classifier", "guidelines": "# Guidelines",
        },
        guidelines_validator=lambda _text: {"is_valid": True},
        terminal_class_resolver=lambda _code: {"classes": ["Yes", "No"]},
    )
    module._feedback_aligner_batch = lambda args: alignment_calls.append(args) or {
        "coverage": {
            "complete": True, "target_count": 1, "completed_count": 1,
            "failed_count": 0,
        },
        "scorecards": [{
            "scorecard_id": "sc-1",
            "scores": [{
                "score_id": "s-1", "champion_version": "v-1",
                "total_items": 250, "disagreements": 100,
                "class_distribution": [{"label": "Yes", "count": 200}],
                "weekly_disagreement_rates": [0.4] * 4,
                "weekly_ac1_values": [0.7] * 4,
                "weekly_bucket_counts": [1] * 4,
            }],
        }],
    }

    result = module.optimization.assess({"scorecard_id": "sc-1", "score_id": "s-1"})

    assert alignment_calls[0]["scorecards"] == ["sc-1"]
    assert alignment_calls[0]["window_start"].endswith("T00:00:00Z")
    assert result["coverage"]["complete"] is True
    assert result["readiness_state"] == "insufficient_evidence"


def test_default_optimization_diagnose_marks_dependency_failure_incomplete_without_mutating() -> None:
    calls: list[str] = []
    module = execute.PlexusRuntimeModule(
        FastMCP("test-runtime-diagnose"),
        score_info=lambda _args: _old_live_score_info("v-1"),
        score_contradictions=lambda _args: (_ for _ in ()).throw(RuntimeError("semantic service unavailable")),
        rubric_memory_recent_entries=lambda _args: calls.append("recent") or {"entries": []},
        rubric_memory_evidence_pack=lambda _args: calls.append("pack") or {"evidence": []},
        rubric_memory_sme_question_gate=lambda _args: calls.append("sme") or {"questions": []},
    )

    result = module.optimization.diagnose({"scorecard_id": "sc-1", "score_id": "s-1"})

    assert result["coverage"]["complete"] is False
    assert result["states"]["readiness"] == "incomplete"
    assert "semantic service unavailable" in str(result["coverage"]["failures"])
    assert calls == ["recent", "pack", "sme"]


def test_default_optimization_diagnose_preserves_ready_assessment_when_semantics_are_clear() -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-runtime-diagnose-ready"),
        score_info=lambda _args: {"championVersionId": "v-1"},
        score_contradictions=lambda _args: {"status": "consistent"},
        rubric_memory_recent_entries=lambda _args: {"entries": []},
        rubric_memory_evidence_pack=lambda _args: {"evidence": []},
        rubric_memory_sme_question_gate=lambda _args: {"questions": []},
    )

    result = module.optimization.diagnose({
        "scorecard_id": "sc-1",
        "score_id": "s-1",
        "assessment": {"readiness_state": "ready_to_optimize"},
    })

    assert result["readiness_state"] == "ready_to_optimize"
    assert result["states"]["readiness"] == "ready_to_optimize"


def test_optimization_diagnose_threads_rubric_evidence_and_version_into_sme_gate() -> None:
    gate_calls: list[dict] = []
    rubric_context = {
        "markdown_context": "citation-backed context",
        "citation_index": [{"id": "citation-1"}],
        "machine_context": {"source": "memory"},
        "diagnostics": [],
    }
    module = execute.PlexusRuntimeModule(
        FastMCP("test-diagnose-sme-inputs"),
        score_info=lambda _args: {"championVersionId": "v-1"},
        score_contradictions=lambda _args: {"status": "consistent"},
        rubric_memory_recent_entries=lambda _args: {"markdown_context": "recent"},
        rubric_memory_evidence_pack=lambda _args: rubric_context,
        rubric_memory_sme_question_gate=lambda args: gate_calls.append(args) or {"questions": []},
    )

    result = module.optimization.diagnose({
        "scorecard_id": "sc-1",
        "score_id": "s-1",
        "assessment": {"readiness_state": "ready_to_optimize"},
        "candidate_agenda_markdown": "### Question\nWhat policy applies?",
    })

    assert result["readiness_state"] == "ready_to_optimize"
    assert gate_calls[0]["score_version_id"] == "v-1"
    assert gate_calls[0]["rubric_memory_context"] is rubric_context
    assert gate_calls[0]["candidate_agenda_markdown"].startswith("### Question")
    assert "citation-backed context" in gate_calls[0]["optimizer_context"]


def test_optimization_diagnose_surfaces_only_true_open_sme_questions() -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-diagnose-open-sme-question"),
        score_info=lambda _args: {"championVersionId": "v-1"},
        score_contradictions=lambda _args: {"status": "consistent"},
        rubric_memory_recent_entries=lambda _args: {},
        rubric_memory_evidence_pack=lambda _args: {},
        rubric_memory_sme_question_gate=lambda _args: {
            "final_items": [
                {
                    "answer_status": "true_open_question",
                    "original_text": "Which policy should apply?",
                    "final_text": "Which policy should apply?",
                },
                {
                    "answer_status": "answered_by_evidence",
                    "original_text": "Already answered",
                    "final_text": "Already answered",
                },
            ],
            "suppressed_items": [{
                "answer_status": "true_open_question",
                "original_text": "Suppressed question",
            }],
        },
    )

    result = module.optimization.diagnose({
        "scorecard_id": "sc-1", "score_id": "s-1",
        "assessment": {"readiness_state": "ready_to_optimize"},
    })

    assert result["stakeholder_questions"] == ["Which policy should apply?"]
    assert result["readiness_state"] == "stakeholder_clarification_required"


def test_default_optimization_run_requires_explicit_resource_limits() -> None:
    dispatched: list[dict] = []
    module = execute.PlexusRuntimeModule(
        FastMCP("test-run-limits"),
        procedure_optimize=lambda args: dispatched.append(args) or {},
    )

    result = module.optimization.run({"approved": True, "targets": []})

    assert result["accepted_targets"] == []
    assert dispatched == []
    assert result["blockers"] == ["invalid_run_limits"]


def test_optimization_run_accepts_actual_assessment_packet_fingerprint_when_live_evidence_is_unchanged() -> None:
    dispatched: list[dict] = []
    module = execute.PlexusRuntimeModule(
        FastMCP("test-assessment-fingerprint-freshness"),
        score_info=lambda _args: _old_live_score_info("v-1"),
        feedback_latest_update=lambda _args: {"latest_feedback_updated_at": "2026-07-01T00:00:00Z"},
        procedure_optimize=lambda args: dispatched.append(args) or {"procedure_id": "proc-1"},
    )
    target = _ready_optimization_target(
        "sc-1", "s-1", "v-1", "2026-07-01T00:00:00Z"
    )
    result = module.optimization.run({
        "approved": True, "targets": [target], "max_cost_usd": 1.0,
        "max_samples": 20, "max_iterations": 2, "max_concurrency": 1,
    })

    assert result["accepted_targets"] == [target]
    assert len(dispatched) == 1

    changed = {**target, "champion_version": "v-old"}
    rejected = module.optimization.run({
        "approved": True, "targets": [changed], "max_cost_usd": 1.0,
        "max_samples": 20, "max_iterations": 2, "max_concurrency": 1,
    })
    assert rejected["accepted_targets"] == []
    assert rejected["rejected"][0]["reason"] == "assessment_freshness_mismatch"


def test_alignment_batch_preserves_honest_complete_monday_week_metrics_from_valid_pairs() -> None:
    from datetime import datetime, timedelta, timezone

    end = datetime(2026, 7, 27, tzinfo=timezone.utc)
    items = []
    for offset in range(12):
        items.append({
            "scorecardId": "sc-1", "scoreId": "s-1", "initialAnswerValue": "Yes",
            "finalAnswerValue": "Yes", "isInvalid": False,
            "editedAt": (end - timedelta(days=7 * (offset + 1))).isoformat().replace("+00:00", "Z"),
        })
    items.extend([
        {"scorecardId": "sc-1", "scoreId": "s-1", "initialAnswerValue": "Yes", "finalAnswerValue": None, "isInvalid": False, "editedAt": "2026-07-20T00:00:00Z"},
        {"scorecardId": "sc-1", "scoreId": "s-1", "initialAnswerValue": "Yes", "finalAnswerValue": "No", "isInvalid": True, "editedAt": "2026-07-20T00:00:00Z"},
    ])
    result = execute._default_feedback_alignment_batch(
        {"scorecard": "sc-1", "days": 90, "window_end": "2026-07-27T00:00:00Z"},
        _prefetched_feedback_items=items,
        _prefetched_account_id="acct-1",
        _prefetched_scorecard_data={"id": "sc-1", "name": "One", "sections": {"items": [{"scores": {"items": [{"id": "s-1", "name": "One"}]}}]}},
    )
    score = result["scores"][0]

    assert score["total_items"] == 12
    assert score["weekly_bucket_counts"] == [1] * 12
    assert score["weekly_disagreement_rates"] == [0.0] * 12
    assert len(score["weekly_ac1_values"]) == 12


def test_optimization_review_loads_indexed_procedure_evidence_conservatively() -> None:
    evaluation_calls: list[str] = []
    def evaluation(evaluation_id: str, baseline_id: str) -> dict:
        return {
            "id": evaluation_id, "status": "COMPLETED", "score_version_id": "v-1",
            "baseline_evaluation_id": baseline_id, "total_items": 20, "processed_items": 20,
            "confusion_matrix": {"matrix": {"Yes": {"Yes": 9, "No": 1}}},
            "dataset_class_distribution": [{"label": "Yes", "count": 10}, {"label": "No", "count": 10}],
            "predicted_class_distribution": [{"label": "Yes", "count": 11}, {"label": "No", "count": 9}],
            "root_cause": {"misclassification_analysis": {}},
        }
    evaluations = {
        "recent": evaluation("recent", "recent-baseline"),
        "historical": evaluation("historical", "historical-baseline"),
    }
    module = execute.PlexusRuntimeModule(
        FastMCP("test-procedure-review"),
        review_evidence_loader=lambda procedure_id: {
            "procedure_id": procedure_id, "summary": {"effective_status": "COMPLETED"},
            "baseline": {
                "original_feedback_evaluation_id": "recent-baseline",
                "original_accuracy_evaluation_id": "historical-baseline",
                "feedback_alignment": 0.6, "accuracy_alignment": 0.7,
            },
            "best": {
                "winning_version_id": "v-1", "best_feedback_evaluation_id": "recent",
                "best_accuracy_evaluation_id": "historical", "feedback_alignment": 0.8,
                "accuracy_alignment": 0.7,
            },
            "review_artifacts": {"artifacts_complete": True, "rca_complete": True},
        },
        evaluation_info=lambda args: evaluation_calls.append(args["evaluation_id"]) or evaluations[args["evaluation_id"]],
    )
    result = module.optimization.review({"procedure_id": "proc-1"})

    assert evaluation_calls == ["recent", "historical"]
    assert result["post_run_state"] == "promotion_ready"


def test_optimization_review_does_not_treat_winning_id_as_safety_proof() -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-procedure-review-unknown-safety"),
        review_evidence_loader=lambda procedure_id: {
            "procedure_id": procedure_id, "summary": {"effective_status": "COMPLETED"},
            "best": {"winning_version_id": "v-1", "best_feedback_evaluation_id": "recent", "best_accuracy_evaluation_id": "historical"},
        },
        evaluation_info=lambda _args: {"status": "COMPLETED", "score_version_id": "v-1"},
    )

    result = module.optimization.review({"procedure_id": "proc-1"})

    assert result["post_run_state"] != "promotion_ready"
    assert result["promotion_ready"] is False


def test_optimization_review_missing_indexed_manifest_never_promotes() -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-procedure-review-missing"),
        review_evidence_loader=lambda _procedure_id: (_ for _ in ()).throw(RuntimeError("not indexed")),
    )
    result = module.optimization.review({"procedure_id": "proc-1"})

    assert result["post_run_state"] == "failed_or_incomplete"


def test_optimization_review_ignores_caller_supplied_safety_booleans() -> None:
    module = execute.PlexusRuntimeModule(FastMCP("test-review-requires-indexed-evidence"))

    result = module.optimization.review({
        "evidence": {
            "terminal": True,
            "matched_recent_evaluation": True,
            "historical_regression_evidence": True,
            "class_specific_metrics": True,
            "prediction_collapse": False,
            "rca_complete": True,
            "artifacts_complete": True,
            "measurable_safe_improvement": True,
        },
    })

    assert result["post_run_state"] == "failed_or_incomplete"
    assert result["promotion_ready"] is False


def test_plexus_api_list_stays_complete_in_planning_mode() -> None:
    facade = execute.PlexusRuntimeModule(
        FastMCP("test"),
        runtime_context={"tool_access_mode": "planning"},
    )

    catalog = facade.api.list()

    assert "run" in catalog["plexus.report"]
    assert "run" in catalog["plexus.evaluation"]
    assert "optimize" in catalog["plexus.procedure"]
    assert catalog["plexus.skills"] == ["get", "list"]
    assert catalog["plexus.guidelines"] == ["validate"]
    assert facade.api_calls == ["plexus.api.list"]


def test_guidelines_validate_returns_structured_validation_result() -> None:
    module = execute.PlexusRuntimeModule(FastMCP("test"))

    result = module.guidelines.validate(
        {
            "guidelines": "# Test\n\n"
            "## Objective\n\nDetect a condition.\n\n"
            "## Classes\n- Valid labels: [Yes, No]\n- Target class: Yes\n- Default class: No\n\n"
            "## Definition of Yes\n\nPositive examples.\n\n"
            "## Conditions for Yes\n\n- Positive condition.\n\n"
            "## Definition of No\n\nNegative examples.\n\n"
        }
    )

    assert result["is_valid"] is False
    assert result["classifier_type"] == "binary"
    assert result["missing_sections"] == ["Conditions for No"]
    assert "found_sections" in result
    assert module.api_calls == ["plexus.guidelines.validate"]


def test_guidelines_validate_accepts_content_alias_and_is_allowed_in_planning_mode() -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        runtime_context={"tool_access_mode": "planning"},
    )

    result = module.guidelines.validate(
        {
            "content": "# Test\n\n"
            "## Objective\n\nDetect a condition.\n\n"
            "## Classes\n- Valid labels: [Yes, No]\n- Target class: Yes\n- Default class: No\n\n"
            "## Definition of Yes\n\nPositive examples.\n\n"
            "## Conditions for Yes\n\n- Positive condition.\n\n"
            "## Definition of No\n\nNegative examples.\n\n"
            "## Conditions for No\n\n- Negative condition.\n"
        }
    )

    assert result["is_valid"] is True
    assert module.api_calls == ["plexus.guidelines.validate"]


def test_guidelines_validate_requires_markdown_text() -> None:
    module = execute.PlexusRuntimeModule(FastMCP("test"))

    with pytest.raises(ValueError, match="requires guidelines markdown text"):
        module.guidelines.validate({"guidelines": None})


def test_planning_mode_allows_safe_analysis_and_procedure_inspection() -> None:
    seen: dict[str, dict] = {}

    def fake_score_contradictions(args: dict) -> dict:
        seen["contradictions"] = args
        return {"ok": True}

    def fake_score_predict(args: dict) -> dict:
        seen["predict"] = args
        return {"prediction": "Yes"}

    def fake_evaluation_runner(args: dict) -> dict:
        seen["evaluation_run"] = args
        return {"evaluation_id": "eval-1"}

    def fake_report_runner(args: dict) -> dict:
        seen["report_run"] = args
        return {"task_id": "task-1", "report_id": "report-1"}

    def fake_report_reader(args: dict) -> dict:
        seen["report_list"] = args
        return {"items": []}

    def fake_procedure_reader(args: dict) -> dict:
        seen["procedure_list"] = args
        return {"procedures": []}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        runtime_context={"tool_access_mode": "planning", "account_id": "acct-1"},
        score_predict=fake_score_predict,
        score_contradictions=fake_score_contradictions,
        evaluation_runner=fake_evaluation_runner,
        report_runner=fake_report_runner,
        report_readers={"list": fake_report_reader},
        procedure_listers={"list": fake_procedure_reader},
    )

    assert module.score.contradictions({"score_id": "score-1"}) == {"ok": True}
    assert module.score.predict({
        "scorecard_identifier": "card",
        "score_identifier": "score",
        "item_id": "item-1",
    }) == {"prediction": "Yes"}
    assert module.evaluation.run({
        "scorecard_name": "card",
        "score_name": "score",
        "evaluation_type": "accuracy",
        "async": True,
        "budget": {"usd": 0.01, "wallclock_seconds": 10, "depth": 1, "tool_calls": 1},
    })["kind"] == "evaluation"
    assert module.report.run({
        "block_class": "FeedbackAlignment",
        "async": True,
        "budget": {"usd": 0.01, "wallclock_seconds": 10, "depth": 1, "tool_calls": 1},
    })["kind"] == "report"
    assert module.report.list({}) == {"items": []}
    assert module.procedure.list({"limit": 5}) == {"procedures": []}
    assert seen["contradictions"]["account_id"] == "acct-1"
    assert seen["predict"]["account_id"] == "acct-1"
    assert seen["evaluation_run"]["account_id"] == "acct-1"
    assert seen["report_run"]["account_id"] == "acct-1"
    assert seen["report_list"]["account_id"] == "acct-1"
    assert seen["procedure_list"]["account_id"] == "acct-1"


@pytest.mark.asyncio
async def test_planning_mode_blocks_procedure_start() -> None:
    called = False

    def fake_procedure_runner(_args: dict) -> dict:
        nonlocal called
        called = True
        return {"status": "dispatched"}

    result = await execute._execute_tactus_tool(
        (
            'return plexus.procedure.run({ procedure_id = "proc-1", '
            'async = true, budget = { usd = 0.01, wallclock_seconds = 10, '
            'depth = 1, tool_calls = 1 } })'
        ),
        FastMCP("test-planning-mode-blocks-procedure-run"),
        procedure_runner=fake_procedure_runner,
        runtime_context={"tool_access_mode": "planning"},
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "tool_not_allowed_in_planning_mode"
    assert "plexus.procedure.run" in result["error"]["message"]
    assert called is False


def test_planning_mode_blocks_champion_promotion() -> None:
    called = False

    def fake_set_champion(_args: dict) -> dict:
        nonlocal called
        called = True
        return {"success": True}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-planning-mode-blocks-set-champion"),
        score_set_champion=fake_set_champion,
        runtime_context={"tool_access_mode": "planning"},
    )

    with pytest.raises(execute.PlanningModeToolNotAllowed) as exc_info:
        module.score.set_champion({"score_id": "score-1", "version_id": "version-1"})

    assert "plexus.score.set_champion" in str(exc_info.value)
    assert called is False


def test_planning_mode_blocks_score_create() -> None:
    called = False

    def fake_score_create(_args: dict) -> dict:
        nonlocal called
        called = True
        return {"success": True, "id": "score-1"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-planning-mode-blocks-score-create"),
        score_create=fake_score_create,
        runtime_context={"tool_access_mode": "planning"},
    )

    with pytest.raises(execute.PlanningModeToolNotAllowed) as exc_info:
        module.score.create({"scorecard_identifier": "card-1", "name": "New Score"})

    assert "plexus.score.create" in str(exc_info.value)
    assert called is False


def test_score_delete_requires_confirmation_and_dispatches_when_confirmed() -> None:
    calls: list[dict] = []

    def fake_score_delete(args: dict) -> dict:
        calls.append(args)
        return {"success": True, "id": args["id"]}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-score-delete"),
        score_delete=fake_score_delete,
    )

    with pytest.raises(ValueError, match="confirmed = true"):
        module.score.delete({"id": "score-1"})

    assert calls == []
    assert module.score.delete({"id": "score-1", "confirmed": True}) == {
        "success": True,
        "id": "score-1",
    }
    assert calls == [{"id": "score-1", "confirmed": True}]


def test_default_score_delete_keeps_runtime_confirmation_out_of_graphql_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        context = None

        def execute(self, query: str, variables: dict) -> dict:
            calls.append((query, variables))
            return {"deleteScore": {"id": "score-1"}}

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: FakeClient()
    )

    assert execute._default_score_delete({"id": "score-1", "confirmed": True}) == {
        "success": True,
        "id": "score-1",
    }
    assert calls[0][1] == {"input": {"id": "score-1"}}


def test_planning_mode_blocks_score_delete() -> None:
    called = False

    def fake_score_delete(_args: dict) -> dict:
        nonlocal called
        called = True
        return {"success": True}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-planning-mode-blocks-score-delete"),
        score_delete=fake_score_delete,
        runtime_context={"tool_access_mode": "planning"},
    )

    with pytest.raises(execute.PlanningModeToolNotAllowed) as exc_info:
        module.score.delete({"id": "score-1", "confirmed": True})

    assert "plexus.score.delete" in str(exc_info.value)
    assert called is False


def test_scorecards_update_and_delete_use_explicit_lifecycle_handlers() -> None:
    update_calls: list[dict] = []
    delete_calls: list[dict] = []

    module = execute.PlexusRuntimeModule(
        FastMCP("test-scorecard-lifecycle"),
        scorecards_updater=lambda args: update_calls.append(args) or {"success": True},
        scorecards_deleter=lambda args: delete_calls.append(args) or {"success": True},
    )

    assert module.scorecards.update({"id": "card-1", "name": "Renamed"}) == {
        "success": True
    }
    with pytest.raises(ValueError, match="confirmed = true"):
        module.scorecards.delete({"id": "card-1"})
    assert module.scorecards.delete({"id": "card-1", "confirmed": True}) == {
        "success": True
    }
    assert update_calls == [{"id": "card-1", "name": "Renamed"}]
    assert delete_calls == [{"id": "card-1", "confirmed": True}]


def test_default_scorecards_update_keeps_attribution_metadata_out_of_graphql_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        context = None

        def execute(self, query: str, variables: dict | None = None) -> dict:
            if "getScorecard" in query:
                return {"getScorecard": {"id": "card-1"}}
            calls.append((query, variables or {}))
            return {"updateScorecard": {"id": "card-1", "name": "Renamed"}}

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: FakeClient()
    )
    monkeypatch.setattr(
        "plexus.cli.shared.direct_identifier_resolution.direct_resolve_scorecard_identifier",
        lambda _client, _identifier: "card-1",
    )

    result = execute._default_scorecards_update({"id": "card-1", "name": "Renamed"})

    assert result["success"] is True
    assert calls[0][1] == {"input": {"id": "card-1", "name": "Renamed"}}


def test_planning_mode_blocks_scorecards_create() -> None:
    called = False

    def fake_scorecards_create(_args: dict) -> dict:
        nonlocal called
        called = True
        return {"success": True, "id": "scorecard-1"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-planning-mode-blocks-scorecards-create"),
        scorecards_creator=fake_scorecards_create,
        runtime_context={"tool_access_mode": "planning"},
    )

    with pytest.raises(execute.PlanningModeToolNotAllowed) as exc_info:
        module.scorecards.create({"name": "New Scorecard"})

    assert "plexus.scorecards.create" in str(exc_info.value)
    assert called is False


def test_planning_mode_blocks_procedure_archive() -> None:
    called = False

    def fake_archive(_args: dict) -> dict:
        nonlocal called
        called = True
        return {"success": True}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-planning-mode-blocks-procedure-archive"),
        procedure_archive=fake_archive,
        runtime_context={"tool_access_mode": "planning"},
    )

    with pytest.raises(execute.PlanningModeToolNotAllowed) as exc_info:
        module.procedure.archive({"id": "proc-1"})

    assert "plexus.procedure.archive" in str(exc_info.value)
    assert called is False


_FRONTMATTER_TEMPLATE = (
    "---\n"
    "id: {doc_id}\n"
    "title: {title}\n"
    "summary: {summary}\n"
    "namespace: {namespace}\n"
    "status: canonical\n"
    "disclosure: reference\n"
    "audience: agent\n"
    "tags: {tags}\n"
    "---\n"
    "{body}"
)


def _write_doc(
    path,
    doc_id: str,
    title: str,
    namespace: str,
    body: str,
    *,
    summary: str = "Test document.",
    tags: str = "[test]",
) -> None:
    path.write_text(
        _FRONTMATTER_TEMPLATE.format(
            doc_id=doc_id,
            title=title,
            summary=summary,
            namespace=namespace,
            tags=tags,
            body=body,
        )
    )


def _write_skill(
    path,
    *,
    name: str,
    description: str,
    body: str = "# Skill\n",
    tags: str = "[score-workflow]",
    applies_to: str = "[score code editing]",
    console_supported: str = "true",
    requires_subagent: str = "false",
    allowed_modes: str = "[planning, execution]",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"tags: {tags}\n"
        f"applies_to: {applies_to}\n"
        f"console_supported: {console_supported}\n"
        f"requires_subagent: {requires_subagent}\n"
        f"allowed_modes: {allowed_modes}\n"
        "resources: []\n"
        "---\n"
        f"{body}",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_execute_tactus_docs_list_and_get_use_repository(tmp_path) -> None:
    mcp = FastMCP("test-execute-tactus-docs")

    docs_dir = tmp_path / "docs"
    (docs_dir / "score-authoring").mkdir(parents=True)
    (docs_dir / "evaluation-feedback").mkdir(parents=True)
    _write_doc(
        docs_dir / "score-authoring" / "score-yaml-format.md",
        doc_id="score-authoring.score-yaml-format",
        title="Score YAML",
        namespace="score-authoring",
        body="# Score YAML\n",
    )
    _write_doc(
        docs_dir / "evaluation-feedback" / "feedback-alignment.md",
        doc_id="evaluation-feedback.feedback-alignment",
        title="Feedback Alignment",
        namespace="evaluation-feedback",
        body="# Feedback Alignment\n",
    )
    (docs_dir / "README.md").write_text("# index\n")

    original_docs_dir = execute.PLEXUS_DOCS_DIR
    execute.PLEXUS_DOCS_DIR = str(docs_dir)
    try:
        list_result = await execute._execute_tactus_tool(
            "return plexus.docs.list()",
            mcp,
        )

        assert list_result["ok"] is True
        ids = [entry["id"] for entry in list_result["value"]]
        assert ids == [
            "evaluation-feedback.feedback-alignment",
            "score-authoring.score-yaml-format",
        ]
        for entry in list_result["value"]:
            assert "title" in entry and "summary" in entry and "namespace" in entry
            assert "content" not in entry and "body" not in entry
        assert list_result["api_calls"] == ["plexus.docs.list"]

        get_result = await execute._execute_tactus_tool(
            'return plexus.docs.get{ key = "score-authoring.score-yaml-format" }',
            mcp,
        )

        assert get_result["ok"] is True
        value = get_result["value"]
        assert value["key"] == "score-authoring.score-yaml-format"
        assert value["id"] == "score-authoring.score-yaml-format"
        assert value["content"] == "# Score YAML\n"
        assert value["metadata"]["title"] == "Score YAML"
        assert value["metadata"]["namespace"] == "score-authoring"
        assert get_result["api_calls"] == ["plexus.docs.get"]
        assert get_result["cost"]["tool_calls"] == 1
    finally:
        execute.PLEXUS_DOCS_DIR = original_docs_dir


@pytest.mark.asyncio
async def test_execute_tactus_skills_list_and_get_use_repository(tmp_path) -> None:
    mcp = FastMCP("test-execute-tactus-skills")

    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir / "score-code-editor" / "SKILL.md",
        name="Score Code Editor",
        description="Edit score Tactus code",
        body=(
            "# Score Code Editor\n"
            "<ide-only>\nUse local file editing.\n</ide-only>\n"
            "<console-hidden>\nHide this from console.\n</console-hidden>\n"
            "Console must use score.edit.\n"
        ),
        tags="[score-workflow, code]",
        applies_to="[score code editing]",
        requires_subagent="true",
    )
    _write_skill(
        skills_dir / "client-redaction" / "SKILL.md",
        name="Client Redaction",
        description="Repository-only redaction",
        body="# Client Redaction\n",
        tags="[repository-hygiene]",
        applies_to="[redaction]",
        console_supported="false",
        allowed_modes="[ide]",
    )

    original_skills_dir = execute.PLEXUS_SKILLS_DIR
    execute.PLEXUS_SKILLS_DIR = str(skills_dir)
    try:
        list_result = await execute._execute_tactus_tool(
            (
                'return plexus.skills.list({ query = "score", '
                'tags = {"score-workflow"}, mode = "planning" })'
            ),
            mcp,
        )

        assert list_result["ok"] is True
        assert [entry["id"] for entry in list_result["value"]] == [
            "score-code-editor"
        ]
        entry = list_result["value"][0]
        assert entry["requires_subagent"] is True
        assert entry["console_supported"] is True
        assert "content" not in entry and "body" not in entry
        assert list_result["api_calls"] == ["plexus.skills.list"]

        get_result = await execute._execute_tactus_tool(
            'return skills_get{ id = "score-code-editor", mode = "console" }',
            mcp,
        )

        assert get_result["ok"] is True
        value = get_result["value"]
        assert value["id"] == "score-code-editor"
        assert value["metadata"]["id"] == "score-code-editor"
        assert value["content"].startswith("# Score Code Editor")
        assert "Use local file editing." not in value["content"]
        assert "Hide this from console." not in value["content"]
        assert "Console must use score.edit." in value["content"]
        assert value["resources"] in ([], {})
        assert get_result["api_calls"] == ["plexus.skills.get"]
    finally:
        execute.PLEXUS_SKILLS_DIR = original_skills_dir


@pytest.mark.asyncio
async def test_planning_mode_allows_skills_list_and_get(tmp_path) -> None:
    mcp = FastMCP("test-planning-mode-skills")
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir / "score-setup" / "SKILL.md",
        name="Score Setup",
        description="Set up score records",
        body="# Score Setup\n",
    )

    original_skills_dir = execute.PLEXUS_SKILLS_DIR
    execute.PLEXUS_SKILLS_DIR = str(skills_dir)
    try:
        result = await execute._execute_tactus_tool(
            (
                'local index = skills_list{ mode = "planning" }\n'
                'local skill = skills_get{ id = "score-setup" }\n'
                'return { count = #index, skill_id = skill["id"] }'
            ),
            mcp,
            runtime_context={"tool_access_mode": "planning"},
        )
    finally:
        execute.PLEXUS_SKILLS_DIR = original_skills_dir

    assert result["ok"] is True
    assert result["value"] == {"count": 1, "skill_id": "score-setup"}
    assert result["api_calls"] == ["plexus.skills.list", "plexus.skills.get"]


def test_plexus_runtime_module_docs_get_rejects_unsafe_keys(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _write_doc(
        docs_dir / "ok.md",
        doc_id="mcp.ok",
        title="OK",
        namespace="mcp",
        body="ok",
    )

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
        module._docs_read("missing.id")


def test_plexus_runtime_module_docs_list_excludes_readme_and_index(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _write_doc(
        docs_dir / "alpha.md",
        doc_id="ns.alpha",
        title="Alpha",
        namespace="ns",
        body="a",
    )
    _write_doc(
        docs_dir / "beta.md",
        doc_id="ns.beta",
        title="Beta",
        namespace="ns",
        body="b",
    )
    (docs_dir / "README.md").write_text("readme")
    _write_doc(
        docs_dir / "_index.md",
        doc_id="ns._index",
        title="Index",
        namespace="ns",
        body="index",
    )
    (docs_dir / "notes.txt").write_text("ignored")

    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=str(docs_dir))

    ids = [entry["id"] for entry in module._docs_list()]
    assert ids == ["ns.alpha", "ns.beta"]


def test_plexus_runtime_module_docs_list_returns_namespaced_metadata(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    (docs_dir / "evaluation-feedback").mkdir(parents=True)
    (docs_dir / "score-authoring").mkdir(parents=True)
    _write_doc(
        docs_dir / "evaluation-feedback" / "feedback-alignment.md",
        doc_id="evaluation-feedback.feedback-alignment",
        title="Feedback Alignment",
        namespace="evaluation-feedback",
        body="feedback",
    )
    _write_doc(
        docs_dir / "evaluation-feedback" / "_index.md",
        doc_id="evaluation-feedback._index",
        title="Evaluation Feedback",
        namespace="evaluation-feedback",
        body="index",
    )
    _write_doc(
        docs_dir / "score-authoring" / "score-yaml-format.md",
        doc_id="score-authoring.score-yaml-format",
        title="Score YAML",
        namespace="score-authoring",
        body="score",
    )
    (docs_dir / "README.md").write_text("top readme")

    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=str(docs_dir))

    entries = module._docs_list()
    ids = [entry["id"] for entry in entries]
    assert ids == [
        "evaluation-feedback.feedback-alignment",
        "score-authoring.score-yaml-format",
    ]
    namespaces = {entry["namespace"] for entry in entries}
    assert namespaces == {"evaluation-feedback", "score-authoring"}


def test_plexus_runtime_module_docs_list_supports_namespace_filter(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    (docs_dir / "mcp").mkdir(parents=True)
    (docs_dir / "score-authoring").mkdir(parents=True)
    _write_doc(
        docs_dir / "mcp" / "discovery.md",
        doc_id="mcp.discovery",
        title="Discovery",
        namespace="mcp",
        body="d",
    )
    _write_doc(
        docs_dir / "score-authoring" / "score-yaml-format.md",
        doc_id="score-authoring.score-yaml-format",
        title="Score YAML",
        namespace="score-authoring",
        body="s",
    )

    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=str(docs_dir))

    mcp_entries = module._docs_list(namespace="mcp")
    assert [e["id"] for e in mcp_entries] == ["mcp.discovery"]


def test_plexus_runtime_module_docs_read_returns_metadata_and_body(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    (docs_dir / "evaluation-feedback").mkdir(parents=True)
    _write_doc(
        docs_dir / "evaluation-feedback" / "feedback-alignment.md",
        doc_id="evaluation-feedback.feedback-alignment",
        title="Feedback Alignment",
        namespace="evaluation-feedback",
        body="nested-content",
    )

    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=str(docs_dir))

    metadata, body = module._docs_read("evaluation-feedback.feedback-alignment")
    assert body == "nested-content"
    assert metadata["title"] == "Feedback Alignment"
    assert metadata["namespace"] == "evaluation-feedback"


def test_plexus_runtime_module_docs_read_unknown_id_raises(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    (docs_dir / "procedures").mkdir(parents=True)
    _write_doc(
        docs_dir / "procedures" / "_index.md",
        doc_id="procedures._index",
        title="Procedures",
        namespace="procedures",
        body="index",
    )

    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=str(docs_dir))

    with pytest.raises(FileNotFoundError):
        module._docs_read("procedures.no-such-doc")


def test_plexus_docs_repository_layout_exposes_themed_keys() -> None:
    docs_dir = execute.PLEXUS_DOCS_DIR
    module = execute.PlexusRuntimeModule(FastMCP("test"), docs_dir=docs_dir)

    entries = module._docs_list()
    ids = {entry["id"] for entry in entries}

    assert "mcp.execute-tactus-overview" in ids
    assert "mcp.discovery" in ids
    assert "mcp.read-apis" in ids
    assert "mcp.long-running-apis" in ids
    assert "mcp.handles-and-budgets" in ids
    assert "evaluation-feedback.feedback-alignment" in ids
    assert "reports.reports-catalog" in ids
    assert "reports.feedback-alignment" in ids
    assert "reports.score-champion-version-timeline" in ids
    assert "score-authoring.score-yaml-format" in ids
    for entry in entries:
        assert not entry["id"].endswith("._index")
        assert "readme" not in entry["id"].lower()

    metadata, body = module._docs_read("evaluation-feedback.feedback-alignment")
    assert "feedback" in body.lower()
    assert metadata["namespace"] == "evaluation-feedback"

    overview_meta, overview_body = module._docs_read("mcp.execute-tactus-overview")
    assert "execute_tactus" in overview_body
    assert "docs.list" in overview_body or "docs_list" in overview_body
    assert overview_meta["namespace"] == "mcp"

    reports_meta, reports_body = module._docs_read("reports.reports-catalog")
    assert "Feedback Alignment" in reports_body
    assert "Score Champion Version Timeline" in reports_body
    assert reports_meta["namespace"] == "reports"


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


@pytest.mark.asyncio
async def test_execute_tactus_sets_runtime_actor_context_from_request_context(monkeypatch) -> None:
    observed: dict[str, str] = {}

    def fake_run_tactus_sync(tactus, mcp, *, trace_id, trace_store, budget=None, **kwargs):
        actor = execute.resolve_actor_context(explicit_source="cli")
        observed["user_id"] = actor.user_id or ""
        observed["source"] = actor.actor_source
        return {
            "ok": True,
            "value": {"ok": True},
            "error": None,
            "cost": {"usd": 0.0},
            "trace_id": trace_id,
            "partial": False,
            "api_calls": [],
        }

    class _Ctx:
        def __init__(self) -> None:
            self.request_context = {"claims": {"sub": "user-ctx-123"}}

    monkeypatch.setattr(execute, "_run_tactus_sync", fake_run_tactus_sync)
    result = await execute._execute_tactus_tool("return 1", FastMCP("test"), ctx=_Ctx())

    assert result["ok"] is True
    assert observed["user_id"] == "user-ctx-123"
    assert observed["source"] == "execute_tactus"


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


def test_default_trace_store_uses_lambda_writable_tmp(monkeypatch) -> None:
    monkeypatch.delenv("PLEXUS_TACTUS_TRACE_DIR", raising=False)
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "console-chat-responder")

    store = execute._default_trace_store()

    assert isinstance(store, execute.FileTactusTraceStore)
    assert store.directory == "/tmp/tactus_traces"


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
    _write_doc(
        docs_dir / "alpha.md",
        doc_id="ns.alpha",
        title="Alpha",
        namespace="ns",
        body="a",
    )

    gate = execute.BudgetGate()
    module = execute.PlexusRuntimeModule(
        FastMCP("test"), docs_dir=str(docs_dir), budget=gate
    )

    module.docs.list({})
    module.docs.get({"key": "ns.alpha"})

    assert gate.tool_calls == 2
    assert gate.exceeded is False


def test_plexus_runtime_module_blocks_call_when_budget_already_exceeded(
    tmp_path,
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _write_doc(
        docs_dir / "alpha.md",
        doc_id="ns.alpha",
        title="Alpha",
        namespace="ns",
        body="a",
    )

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
        "dispatch_result": {
            "status": "dispatched",
            "evaluation_id": "eval-1",
            "dashboard_url": "https://example.test/evaluations/eval-1",
        },
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


def test_score_edit_blocking_requires_handle_protocol() -> None:
    module = execute.PlexusRuntimeModule(FastMCP("test"))

    with pytest.raises(execute.RequiresHandleProtocol):
        module.score.edit(
            {
                "scorecard_identifier": "Compliance",
                "score_identifier": "Tone",
                "instruction": "tighten refund handling",
            }
        )

    assert module.handle_protocol_required == ("score", "edit")
    assert module.api_calls == ["plexus.score.edit"]


def test_score_edit_async_always_waits_and_records_budget(tmp_path, monkeypatch) -> None:
    seen_args: dict = {}
    handles = _MemoryHandleStore()
    result_file = tmp_path / "score-edit-result.json"
    result_file.write_text(
        json.dumps({"success": True, "version_id": "sv-abc"}),
        encoding="utf-8",
    )

    def fake_runner(args: dict) -> dict:
        seen_args.update(args)
        return {
            "status": "dispatched",
            "result_file": str(result_file),
        }

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        handle_store=handles,
        score_edit_runner=fake_runner,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        object,
    )
    monkeypatch.setattr(
        execute,
        "_resolve_scorecard_for_score_edit",
        lambda _client, _identifier: {"id": "scorecard-1"},
    )
    monkeypatch.setattr(
        execute,
        "_resolve_score_for_score_edit",
        lambda _client, _scorecard_id, _identifier: {"id": "score-1"},
    )

    budget = _child_budget()
    completed = module.score.edit(
        {
            "scorecard_identifier": "Compliance",
            "score_identifier": "Tone",
            "instruction": "tighten refund handling",
            "async": True,
            "wait_for_completion": False,
            "budget": budget,
        }
    )

    assert completed["status"] == "completed"
    assert completed["result"]["version_id"] == "sv-abc"
    assert seen_args["instruction"] == "tighten refund handling"
    assert module.api_calls == ["plexus.score.edit", "plexus.handle.await"]
    assert handles.created[0]["id"] == "handle-1"
    assert handles.created[0]["dispatch_result"]["result_file"] == str(result_file)
    assert handles.created[0]["child_budget"] == budget


def test_score_edit_async_waits_for_terminal_result_by_default(tmp_path, monkeypatch) -> None:
    handles = _MemoryHandleStore()
    result_file = tmp_path / "score-edit-result.json"
    result_file.write_text(
        json.dumps({"success": True, "version_id": "sv-123"}),
        encoding="utf-8",
    )

    def fake_runner(_args: dict) -> dict:
        return {"status": "dispatched", "result_file": str(result_file)}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        handle_store=handles,
        score_edit_runner=fake_runner,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        object,
    )
    monkeypatch.setattr(
        execute,
        "_resolve_scorecard_for_score_edit",
        lambda _client, _identifier: {"id": "scorecard-1"},
    )
    monkeypatch.setattr(
        execute,
        "_resolve_score_for_score_edit",
        lambda _client, _scorecard_id, _identifier: {"id": "score-1"},
    )

    budget = _child_budget()
    completed = module.score.edit(
        {
            "scorecard_identifier": "Compliance",
            "score_identifier": "Tone",
            "instruction": "tighten refund handling",
            "async": True,
            "budget": budget,
        }
    )

    assert completed["status"] == "completed"
    assert completed["result"]["version_id"] == "sv-123"
    assert module.api_calls == ["plexus.score.edit", "plexus.handle.await"]


def test_score_edit_chains_followup_from_session_latest(tmp_path, monkeypatch) -> None:
    handles = _MemoryHandleStore()
    result_files = [
        tmp_path / "score-edit-result-1.json",
        tmp_path / "score-edit-result-2.json",
    ]
    result_files[0].write_text(
        json.dumps({"success": True, "version_id": "sv-1", "parent_version_id": "champion-1"}),
        encoding="utf-8",
    )
    result_files[1].write_text(
        json.dumps({"success": True, "version_id": "sv-2", "parent_version_id": "sv-1"}),
        encoding="utf-8",
    )
    seen_args: list[dict] = []

    def fake_runner(args: dict) -> dict:
        seen_args.append(dict(args))
        return {"status": "dispatched", "result_file": str(result_files[len(seen_args) - 1])}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        handle_store=handles,
        score_edit_runner=fake_runner,
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr(
        execute,
        "_resolve_scorecard_for_score_edit",
        lambda _client, _identifier: {"id": "scorecard-1"},
    )
    monkeypatch.setattr(
        execute,
        "_resolve_score_for_score_edit",
        lambda _client, _scorecard_id, _identifier: {"id": "score-1"},
    )

    module.score.edit(
        {
            "scorecard_identifier": "Compliance",
            "score_identifier": "Tone",
            "instruction": "first edit",
            "async": True,
            "budget": _child_budget(),
        }
    )
    completed = module.score.edit(
        {
            "scorecard_identifier": "Compliance",
            "score_identifier": "Tone",
            "instruction": "follow-up edit",
            "async": True,
            "budget": _child_budget(),
        }
    )

    assert "version_id" not in seen_args[0]
    assert seen_args[0]["base_version_source"] == "champion"
    assert seen_args[1]["version_id"] == "sv-1"
    assert seen_args[1]["base_version_source"] == "session_latest"
    assert completed["result"]["version_id"] == "sv-2"
    assert completed["result"]["base_version_source"] == "session_latest"


def test_score_edit_cache_is_keyed_by_score(tmp_path, monkeypatch) -> None:
    result_files = [
        tmp_path / "score-edit-result-1.json",
        tmp_path / "score-edit-result-2.json",
    ]
    result_files[0].write_text(
        json.dumps({"success": True, "version_id": "sv-score-1"}),
        encoding="utf-8",
    )
    result_files[1].write_text(
        json.dumps({"success": True, "version_id": "sv-score-2"}),
        encoding="utf-8",
    )
    seen_args: list[dict] = []

    def fake_runner(args: dict) -> dict:
        seen_args.append(dict(args))
        return {"status": "dispatched", "result_file": str(result_files[len(seen_args) - 1])}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        handle_store=_MemoryHandleStore(),
        score_edit_runner=fake_runner,
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr(
        execute,
        "_resolve_scorecard_for_score_edit",
        lambda _client, _identifier: {"id": "scorecard-1"},
    )
    monkeypatch.setattr(
        execute,
        "_resolve_score_for_score_edit",
        lambda _client, _scorecard_id, identifier: {
            "Tone": {"id": "score-1"},
            "Resolution": {"id": "score-2"},
        }[identifier],
    )

    for score_name in ("Tone", "Resolution"):
        module.score.edit(
            {
                "scorecard_identifier": "Compliance",
                "score_identifier": score_name,
                "instruction": f"edit {score_name}",
                "async": True,
                "budget": _child_budget(),
            }
        )

    assert "version_id" not in seen_args[0]
    assert "version_id" not in seen_args[1]
    assert seen_args[1]["base_version_source"] == "champion"


def test_score_edit_explicit_version_and_champion_start_override_cache(
    tmp_path, monkeypatch
) -> None:
    result_files = [
        tmp_path / "score-edit-result-1.json",
        tmp_path / "score-edit-result-2.json",
        tmp_path / "score-edit-result-3.json",
    ]
    for index, result_file in enumerate(result_files, start=1):
        result_file.write_text(
            json.dumps({"success": True, "version_id": f"sv-{index}"}),
            encoding="utf-8",
        )
    seen_args: list[dict] = []

    def fake_runner(args: dict) -> dict:
        seen_args.append(dict(args))
        return {"status": "dispatched", "result_file": str(result_files[len(seen_args) - 1])}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        handle_store=_MemoryHandleStore(),
        score_edit_runner=fake_runner,
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr(
        execute,
        "_resolve_scorecard_for_score_edit",
        lambda _client, _identifier: {"id": "scorecard-1"},
    )
    monkeypatch.setattr(
        execute,
        "_resolve_score_for_score_edit",
        lambda _client, _scorecard_id, _identifier: {"id": "score-1"},
    )

    module.score.edit(
        {
            "scorecard_identifier": "Compliance",
            "score_identifier": "Tone",
            "instruction": "seed cache",
            "async": True,
            "budget": _child_budget(),
        }
    )
    module.score.edit(
        {
            "scorecard_identifier": "Compliance",
            "score_identifier": "Tone",
            "instruction": "explicit base",
            "version_id": "explicit-base",
            "async": True,
            "budget": _child_budget(),
        }
    )
    module.score.edit(
        {
            "scorecard_identifier": "Compliance",
            "score_identifier": "Tone",
            "instruction": "restart from champion",
            "start_version": "champion",
            "async": True,
            "budget": _child_budget(),
        }
    )

    assert seen_args[1]["version_id"] == "explicit-base"
    assert seen_args[1]["base_version_source"] == "explicit"
    assert "version_id" not in seen_args[2]
    assert seen_args[2]["base_version_source"] == "champion"


def test_score_update_chains_parent_from_session_latest(monkeypatch) -> None:
    seen_args: list[dict] = []

    def fake_update(args: dict) -> dict:
        seen_args.append(dict(args))
        return {"success": True, "version_id": f"sv-{len(seen_args)}"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        score_update=fake_update,
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr(
        execute,
        "_resolve_scorecard_for_score_edit",
        lambda _client, _identifier: {"id": "scorecard-1"},
    )
    monkeypatch.setattr(
        execute,
        "_resolve_score_for_score_edit",
        lambda _client, _scorecard_id, _identifier: {"id": "score-1"},
    )

    module.score.update(
        {
            "scorecard_identifier": "Compliance",
            "score_identifier": "Tone",
            "code": "name: Tone\n",
        }
    )
    result = module.score.update(
        {
            "scorecard_identifier": "Compliance",
            "score_identifier": "Tone",
            "code": "name: Tone\n",
        }
    )

    assert "parent_version_id" not in seen_args[0]
    assert seen_args[0]["base_version_source"] == "champion"
    assert seen_args[1]["parent_version_id"] == "sv-1"
    assert seen_args[1]["base_version_source"] == "session_latest"
    assert result["parent_version_id"] == "sv-1"


@pytest.mark.asyncio
async def test_console_origin_score_update_code_returns_structured_guard_error() -> None:
    result = await execute._execute_tactus_tool(
        (
            'return plexus.score.update({ '
            'scorecard_identifier = "nonexistent-console-skills-smoke", '
            'score_identifier = "nonexistent-score", '
            'code = "name: x\\nkey: x" })'
        ),
        FastMCP("test-console-score-update-guard"),
        runtime_context={"chat_session_id": "chat-1"},
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "console_score_code_update_requires_subagent"
    assert result["api_calls"] == ["plexus.score.update"]


def test_console_origin_score_update_yaml_content_is_rejected() -> None:
    called = False

    def fake_update(_args: dict) -> dict:
        nonlocal called
        called = True
        return {"success": True}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-console-yaml-content-guard"),
        score_update=fake_update,
        runtime_context={"chat_session_id": "chat-1"},
    )

    with pytest.raises(execute.ConsoleScoreCodeUpdateRequiresSubagent):
        module.score.update(
            {
                "scorecard_identifier": "card",
                "score_identifier": "score",
                "yaml_content": "name: score\n",
            }
        )

    assert called is False


def test_console_origin_score_update_guidelines_only_is_allowed(monkeypatch) -> None:
    seen_args: dict = {}

    def fake_update(args: dict) -> dict:
        seen_args.update(args)
        return {"success": True, "version_id": "sv-guidelines"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-console-guidelines-only-update"),
        score_update=fake_update,
        runtime_context={
            "chat_session_id": "chat-1",
            "console_user_message": "Please update this score's guidelines wording.",
        },
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr(
        execute,
        "_resolve_scorecard_for_score_edit",
        lambda _client, _identifier: {"id": "scorecard-1"},
    )
    monkeypatch.setattr(
        execute,
        "_resolve_score_for_score_edit",
        lambda _client, _scorecard_id, _identifier: {"id": "score-1"},
    )

    result = module.score.update(
        {
            "scorecard_identifier": "card",
            "score_identifier": "score",
            "guidelines": "# Guidelines\n",
        }
    )

    assert result["version_id"] == "sv-guidelines"
    assert seen_args["guidelines"] == "# Guidelines\n"
    assert seen_args["scorecard_id"] == "scorecard-1"
    assert seen_args["score_id"] == "score-1"
    assert result["version_url"] == "/lab/scorecards/scorecard-1/scores/score-1/versions/sv-guidelines"
    assert result["score_edit_audit"]["k"] == "score_edit"
    runtime_events = module._runtime_context.get("console_audit_events")
    assert isinstance(runtime_events, list) and len(runtime_events) == 1
    assert runtime_events[0]["version_id"] == "sv-guidelines"


def test_console_origin_score_update_guidelines_requires_guidelines_intent(monkeypatch) -> None:
    called = False

    def fake_update(_args: dict) -> dict:
        nonlocal called
        called = True
        return {"success": True, "version_id": "sv-guidelines"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-console-guidelines-intent-guard"),
        score_update=fake_update,
        runtime_context={
            "chat_session_id": "chat-1",
            "console_user_message": (
                "Please make the scoring stricter so Yes requires clear transcript evidence."
            ),
        },
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)

    with pytest.raises(execute.ConsoleGuidelinesUpdateRequiresGuidelinesIntent):
        module.score.update(
            {
                "scorecard_identifier": "card",
                "score_identifier": "score",
                "guidelines": "# Guidelines\n",
            }
        )

    assert called is False


def test_console_origin_score_edit_is_blocked_for_guidelines_only_request() -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-console-guidelines-only-edit-guard"),
        runtime_context={
            "chat_session_id": "chat-1",
            "console_user_message": (
                "Make the guidelines wording clearer; keep behavior exactly the same."
            ),
        },
    )

    with pytest.raises(execute.ConsoleScoreEditBlockedForGuidelinesOnly):
        module.score.edit(
            {
                "scorecard_identifier": "card",
                "score_identifier": "score",
                "instruction": "Change the score code",
                "async": True,
            }
        )


def test_console_origin_score_edit_is_blocked_for_written_rule_request() -> None:
    """Human phrasing must retain the no-code-edit safety boundary.

    This mirrors the browser acceptance prompt: it does not use the implementation
    words "guidelines" or "wording", but it clearly requests a written-rule-only
    revision and explicitly preserves scoring behavior.
    """
    module = execute.PlexusRuntimeModule(
        FastMCP("test-console-written-rule-edit-guard"),
        runtime_context={
            "chat_session_id": "chat-1",
            "console_user_message": (
                "make the written rule clearer that skipped missing deps need no "
                "manual review. behavior stays the same. save a candidate, not live."
            ),
        },
    )

    with pytest.raises(execute.ConsoleScoreEditBlockedForGuidelinesOnly):
        module.score.edit(
            {
                "scorecard_identifier": "card",
                "score_identifier": "score",
                "instruction": "Change the score code",
                "async": True,
            }
        )


def test_console_origin_score_edit_is_blocked_for_vague_wording_preservation_request() -> None:
    """The browser acceptance phrasing must not fall through to code editing."""
    module = execute.PlexusRuntimeModule(
        FastMCP("test-console-vague-wording-edit-guard"),
        runtime_context={
            "chat_session_id": "chat-1",
            "console_user_message": (
                "the wording is kind of confusing. can u make it clearer? "
                "dont change how it scores tho. just a candidate please"
            ),
        },
    )

    with pytest.raises(execute.ConsoleScoreEditBlockedForGuidelinesOnly):
        module.score.edit(
            {
                "scorecard_identifier": "card",
                "score_identifier": "score",
                "instruction": "Revise the score code for clarity",
                "async": True,
            }
        )


def test_console_origin_score_edit_rejects_candidate_only_non_instruction() -> None:
    """A fresh session must not infer a code change from a bare affirmative."""
    module = execute.PlexusRuntimeModule(
        FastMCP("test-console-candidate-only-edit-guard"),
        runtime_context={
            "chat_session_id": "chat-1",
            "console_user_message": "yes, do it for this one. candidate only please",
        },
    )

    with pytest.raises(execute.ConsoleScoreEditRequiresConcreteInstruction):
        module.score.edit(
            {
                "scorecard_identifier": "card",
                "score_identifier": "score",
                "instruction": "make this score candidate-only; do not change the champion",
                "async": True,
            }
        )


def test_score_edit_structured_output_schema_requires_every_declared_property() -> None:
    """Strict Responses schemas must require every declared property."""
    schema = execute._score_edit_llm_schema()

    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["guidelines"]["type"] == ["string", "null"]


def test_score_edit_smoke_test_requires_an_explicit_mechanical_pass() -> None:
    assert execute._score_edit_smoke_test_passed({"success": True, "passed": True})
    assert not execute._score_edit_smoke_test_passed({"success": True, "passed": False})
    assert not execute._score_edit_smoke_test_passed({"success": False, "passed": True})


def test_console_origin_score_update_metadata_only_is_allowed() -> None:
    seen_args: dict = {}

    def fake_update(args: dict) -> dict:
        seen_args.update(args)
        return {"success": True, "metadata_updated": True}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-console-metadata-only-update"),
        score_update=fake_update,
        runtime_context={"chat_session_id": "chat-1"},
    )

    result = module.score.update(
        {
            "scorecard_identifier": "card",
            "score_identifier": "score",
            "description": "Updated description",
        }
    )

    assert result["metadata_updated"] is True
    assert seen_args["description"] == "Updated description"


def test_non_console_score_update_code_is_allowed(monkeypatch) -> None:
    seen_args: dict = {}

    def fake_update(args: dict) -> dict:
        seen_args.update(args)
        return {"success": True, "version_id": "sv-code"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-non-console-score-update-code"),
        score_update=fake_update,
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr(
        execute,
        "_resolve_scorecard_for_score_edit",
        lambda _client, _identifier: {"id": "scorecard-1"},
    )
    monkeypatch.setattr(
        execute,
        "_resolve_score_for_score_edit",
        lambda _client, _scorecard_id, _identifier: {"id": "score-1"},
    )

    result = module.score.update(
        {
            "scorecard_identifier": "card",
            "score_identifier": "score",
            "code": "name: score\n",
        }
    )

    assert result["version_id"] == "sv-code"
    assert seen_args["code"] == "name: score\n"


def test_console_origin_score_edit_routes_through_worker(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "score-edit-worker"
    run_dir.mkdir()
    result_file = run_dir / "result.json"
    seen_args: dict = {}
    runtime_context = {"chat_session_id": "chat-1"}

    def fake_score_edit_runner(args: dict) -> dict:
        seen_args.update(args)
        result_file.write_text(
            json.dumps(
                {
                    "success": True,
                    "version_id": "sv-candidate",
                    "parent_version_id": "sv-parent",
                    "changed_fields": ["code"],
                }
            ),
            encoding="utf-8",
        )
        return {
            "status": "dispatched",
            "run_id": "run-1",
            "temp_dir": str(run_dir),
            "result_file": str(result_file),
        }

    module = execute.PlexusRuntimeModule(
        FastMCP("test-console-score-edit-routes"),
        score_edit_runner=fake_score_edit_runner,
        handle_store=_MemoryHandleStore(),
        runtime_context=runtime_context,
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr(
        execute,
        "_resolve_scorecard_for_score_edit",
        lambda _client, _identifier: {"id": "scorecard-1"},
    )
    monkeypatch.setattr(
        execute,
        "_resolve_score_for_score_edit",
        lambda _client, _scorecard_id, _identifier: {"id": "score-1"},
    )

    result = module.score.edit(
        {
            "scorecard_identifier": "card",
            "score_identifier": "score",
            "instruction": "add a harmless test note",
            "async": True,
            "budget": _child_budget(),
            "await_timeout": "PT1S",
        }
    )

    assert result["status"] == "completed"
    assert result["result"]["version_id"] == "sv-candidate"
    assert result["result"]["parent_version_id"] == "sv-parent"
    assert result["result"]["changed_fields"] == ["code"]
    assert result["result"]["version_url"] == (
        "/lab/scorecards/scorecard-1/scores/score-1/versions/sv-candidate"
    )
    assert result["result"]["parent_version_url"] == (
        "/lab/scorecards/scorecard-1/scores/score-1/versions/sv-parent"
    )
    assert result["result"]["promoted"] is False
    assert result["result"]["push_outcome"] == "not_pushed"
    assert result["score_edit_audit"]["k"] == "score_edit"
    assert result["score_edit_audit"]["v"] == "sv-candidate"
    assert seen_args["scorecard_id"] == "scorecard-1"
    assert seen_args["score_id"] == "score-1"
    audit_events = runtime_context.get("console_audit_events")
    assert isinstance(audit_events, list) and len(audit_events) == 1
    assert audit_events[0]["kind"] == "score_edit"
    assert audit_events[0]["version_id"] == "sv-candidate"


def test_run_score_edit_job_runs_post_submit_smoke_test_for_code_changes(
    tmp_path, monkeypatch
) -> None:
    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.responses = self

        def create(self, **_kwargs):
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "code": "name: updated\n",
                        "guidelines": "same guidelines",
                        "note": "updated",
                        "summary": "summary",
                    }
                )
            )

    class FakeToolset:
        def setup(self, _args: dict) -> dict:
            return {"success": True}

        def str_replace_editor(self, _args: dict) -> str:
            return "ok"

        async def submit_score_version(self, _args: dict) -> dict:
            return {
                "success": True,
                "version_id": "sv-1",
                "changed_fields": ["code"],
            }

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.score_editor_toolset.ScoreEditorToolset",
        FakeToolset,
    )
    monkeypatch.setattr(
        execute,
        "_default_score_pull",
        lambda args: (
            {
                "yaml_content": "name: updated\n",
                "guidelines": "same guidelines",
                "version_id": "sv-1",
                "parent_version_id": "sv-parent",
            }
            if str(args.get("version_id") or "") == "sv-1"
            else {
                "yaml_content": "name: base\n",
                "guidelines": "same guidelines",
                "version_id": "sv-parent",
                "parent_version_id": "sv-grandparent",
            }
        ),
    )
    monkeypatch.setattr(
        execute,
        "_default_score_test",
        lambda args: {
            "success": True,
            "passed": True,
            "version": args.get("version"),
            "samples": args.get("samples"),
        },
    )

    result_path = tmp_path / "result.json"
    execute._run_score_edit_job(
        {
            "scorecard_identifier": "card",
            "score_identifier": "score",
            "scorecard_id": "scorecard-1",
            "score_id": "score-1",
            "instruction": "update code",
        },
        str(result_path),
    )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert payload["version_id"] == "sv-1"
    assert payload["post_submit_test"]["status"] == "passed"
    assert payload["post_submit_test"]["result"]["success"] is True
    assert payload["post_submit_test"]["result"]["version"] == "sv-1"
    assert payload["post_submit_test"]["result"]["samples"] == 3
    assert payload["post_submit_verification"]["status"] == "passed"
    assert payload["post_submit_verification"]["guidelines_preserved"] is True
    assert payload["version_url"] == "/lab/scorecards/scorecard-1/scores/score-1/versions/sv-1"
    assert payload["parent_version_url"] == "/lab/scorecards/scorecard-1/scores/score-1/versions/sv-parent"
    assert payload["diffs"]["code"]["has_changes"] is True


def test_run_score_edit_job_ignores_llm_guidelines_edits_by_default(
    tmp_path, monkeypatch
) -> None:
    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.responses = self

        def create(self, **_kwargs):
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "code": "name: updated\n",
                        "guidelines": "invalid or unintended guidelines rewrite",
                        "note": "updated",
                        "summary": "summary",
                    }
                )
            )

    class FakeToolset:
        replace_paths: list[str] = []

        def setup(self, _args: dict) -> dict:
            return {"success": True}

        def str_replace_editor(self, args: dict) -> str:
            self.replace_paths.append(str(args.get("path")))
            return "ok"

        async def submit_score_version(self, _args: dict) -> dict:
            return {
                "success": True,
                "version_id": "sv-1",
                "changed_fields": ["code"],
            }

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.score_editor_toolset.ScoreEditorToolset",
        FakeToolset,
    )
    monkeypatch.setattr(
        execute,
        "_default_score_pull",
        lambda args: (
            {
                "yaml_content": "name: updated\n",
                "guidelines": "base guidelines",
                "version_id": "sv-1",
                "parent_version_id": "sv-parent",
            }
            if str(args.get("version_id") or "") == "sv-1"
            else {
                "yaml_content": "name: base\n",
                "guidelines": "base guidelines",
                "version_id": "sv-parent",
                "parent_version_id": "sv-grandparent",
            }
        ),
    )
    monkeypatch.setattr(
        execute,
        "_default_score_test",
        lambda _args: {"success": True, "passed": True},
    )

    result_path = tmp_path / "result.json"
    execute._run_score_edit_job(
        {
            "scorecard_identifier": "card",
            "score_identifier": "score",
            "scorecard_id": "scorecard-1",
            "score_id": "score-1",
            "instruction": "update code only",
        },
        str(result_path),
    )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert payload["changed_fields"] == ["code"]
    assert payload["diffs"]["code"]["has_changes"] is True
    assert FakeToolset.replace_paths == ["score_config.yaml"]


def test_run_score_edit_job_skips_post_submit_smoke_test_without_code_change(
    tmp_path, monkeypatch
) -> None:
    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.responses = self

        def create(self, **_kwargs):
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "code": "name: base\n",
                        "guidelines": "updated guidelines",
                        "note": "updated",
                        "summary": "summary",
                    }
                )
            )

    class FakeToolset:
        def setup(self, _args: dict) -> dict:
            return {"success": True}

        def str_replace_editor(self, _args: dict) -> str:
            return "ok"

        async def submit_score_version(self, _args: dict) -> dict:
            return {
                "success": True,
                "version_id": "sv-2",
                "changed_fields": ["guidelines"],
            }

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.score_editor_toolset.ScoreEditorToolset",
        FakeToolset,
    )
    monkeypatch.setattr(
        execute,
        "_default_score_pull",
        lambda args: (
            {
                "yaml_content": "name: base\n",
                "guidelines": "updated guidelines",
                "version_id": "sv-2",
                "parent_version_id": "sv-parent",
            }
            if str(args.get("version_id") or "") == "sv-2"
            else {
                "yaml_content": "name: base\n",
                "guidelines": "base guidelines",
                "version_id": "sv-parent",
                "parent_version_id": "sv-grandparent",
            }
        ),
    )

    def _unexpected_test_call(_args):
        raise AssertionError("score.test must not run for guidelines-only edits")

    monkeypatch.setattr(execute, "_default_score_test", _unexpected_test_call)

    result_path = tmp_path / "result.json"
    execute._run_score_edit_job(
        {
            "scorecard_identifier": "card",
            "score_identifier": "score",
            "scorecard_id": "scorecard-1",
            "score_id": "score-1",
            "instruction": "update guidelines",
            "allow_guidelines_edit": True,
        },
        str(result_path),
    )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert payload["version_id"] == "sv-2"
    assert payload["post_submit_test"]["status"] == "skipped"
    assert payload["post_submit_test"]["reason"] == "no_code_change"
    assert payload["post_submit_verification"]["status"] == "passed"
    assert payload["diffs"]["guidelines"]["has_changes"] is True


def test_run_score_edit_job_fails_when_candidate_guidelines_change_unexpectedly(
    tmp_path, monkeypatch
) -> None:
    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.responses = self

        def create(self, **_kwargs):
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "code": "name: updated\n",
                        "guidelines": "llm attempted rewrite",
                        "note": "updated",
                        "summary": "summary",
                    }
                )
            )

    class FakeToolset:
        def setup(self, _args: dict) -> dict:
            return {"success": True}

        def str_replace_editor(self, _args: dict) -> str:
            return "ok"

        async def submit_score_version(self, _args: dict) -> dict:
            return {
                "success": True,
                "version_id": "sv-3",
                "changed_fields": ["code"],
            }

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.score_editor_toolset.ScoreEditorToolset",
        FakeToolset,
    )
    monkeypatch.setattr(
        execute,
        "_default_score_pull",
        lambda args: (
            {
                "yaml_content": "name: updated\n",
                "guidelines": "candidate changed guidelines unexpectedly",
                "version_id": "sv-3",
                "parent_version_id": "sv-parent",
            }
            if str(args.get("version_id") or "") == "sv-3"
            else {
                "yaml_content": "name: base\n",
                "guidelines": "base guidelines",
                "version_id": "sv-parent",
                "parent_version_id": "sv-grandparent",
            }
        ),
    )
    monkeypatch.setattr(
        execute,
        "_default_score_test",
        lambda _args: {"success": True},
    )

    result_path = tmp_path / "result.json"
    execute._run_score_edit_job(
        {
            "scorecard_identifier": "card",
            "score_identifier": "score",
            "scorecard_id": "scorecard-1",
            "score_id": "score-1",
            "instruction": "update code only",
        },
        str(result_path),
    )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["success"] is False
    assert payload["error_code"] == "score_edit_post_submit_verification_failed"
    assert payload["post_submit_verification"]["status"] == "failed"


def test_run_score_edit_job_retries_with_fallback_model_after_parse_failure(
    tmp_path, monkeypatch
) -> None:
    model_calls: list[str] = []

    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.responses = self

        def create(self, **kwargs):
            if kwargs.get("text") is not None:
                raise RuntimeError("unknown parameter: text.format")
            model = str(kwargs.get("model"))
            model_calls.append(model)
            if model == "primary-model":
                return SimpleNamespace(output_text="not-json")
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "code": "name: updated\n",
                        "guidelines": "same guidelines",
                        "note": "updated",
                        "summary": "summary",
                    }
                )
            )

    class FakeToolset:
        def setup(self, _args: dict) -> dict:
            return {"success": True}

        def str_replace_editor(self, _args: dict) -> str:
            return "ok"

        async def submit_score_version(self, _args: dict) -> dict:
            return {
                "success": True,
                "version_id": "sv-2",
                "changed_fields": ["code"],
                "parent_version_id": "sv-parent",
            }

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.score_editor_toolset.ScoreEditorToolset",
        FakeToolset,
    )
    monkeypatch.setattr(
        execute,
        "_default_score_pull",
        lambda args: (
            {
                "yaml_content": "name: updated\n",
                "guidelines": "same guidelines",
                "version_id": "sv-2",
                "parent_version_id": "sv-parent",
            }
            if str(args.get("version_id") or "") == "sv-2"
            else {
                "yaml_content": "name: base\n",
                "guidelines": "same guidelines",
                "version_id": "sv-parent",
                "parent_version_id": "sv-grandparent",
            }
        ),
    )
    monkeypatch.setattr(execute, "_default_score_test", lambda _args: {"success": True, "passed": True})

    result_path = tmp_path / "result.json"
    execute._run_score_edit_job(
        {
            "scorecard_identifier": "card",
            "score_identifier": "score",
            "scorecard_id": "scorecard-1",
            "score_id": "score-1",
            "instruction": "update code",
            "model": "primary-model",
            "fallback_model": "fallback-model",
            "max_attempts": 2,
        },
        str(result_path),
    )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert payload["version_id"] == "sv-2"
    assert model_calls == ["primary-model", "fallback-model"]
    assert len(payload["attempts"]) == 2
    assert payload["attempts"][0]["status"] == "failed"
    assert payload["attempts"][0]["error_code"] == "score_edit_model_parse_failed"
    assert payload["attempts"][1]["status"] == "succeeded"
    assert payload["attempts"][1]["model"] == "fallback-model"


def test_run_score_edit_job_retries_after_post_save_smoke_failure(
    tmp_path, monkeypatch
) -> None:
    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.responses = self

        def create(self, **kwargs):
            if kwargs.get("text") is not None:
                raise RuntimeError("unknown parameter: text.format")
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "code": "name: updated\n",
                        "guidelines": "same guidelines",
                        "note": "updated",
                        "summary": "summary",
                    }
                )
            )

    class FakeToolset:
        submits = 0

        def setup(self, _args: dict) -> dict:
            return {"success": True}

        def str_replace_editor(self, _args: dict) -> str:
            return "ok"

        async def submit_score_version(self, _args: dict) -> dict:
            FakeToolset.submits += 1
            return {
                "success": True,
                "version_id": f"sv-{FakeToolset.submits}",
                "changed_fields": ["code"],
                "parent_version_id": "sv-parent",
            }

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.score_editor_toolset.ScoreEditorToolset",
        FakeToolset,
    )
    monkeypatch.setattr(
        execute,
        "_default_score_pull",
        lambda args: (
            {
                "yaml_content": "name: updated\n",
                "guidelines": "same guidelines",
                "version_id": "sv-2",
                "parent_version_id": "sv-parent",
            }
            if str(args.get("version_id") or "") == "sv-2"
            else {
                "yaml_content": "name: base\n",
                "guidelines": "same guidelines",
                "version_id": "sv-parent",
                "parent_version_id": "sv-grandparent",
            }
        ),
    )

    def _smoke(args: dict[str, Any]) -> dict[str, Any]:
        version = str(args.get("version") or "")
        if version == "sv-1":
            return {
                "success": True,
                "passed": False,
                "failure_code": "selection_shortfall",
                "reason": "simulated missing samples",
            }
        return {"success": True, "passed": True, "version": version}

    monkeypatch.setattr(execute, "_default_score_test", _smoke)

    result_path = tmp_path / "result.json"
    execute._run_score_edit_job(
        {
            "scorecard_identifier": "card",
            "score_identifier": "score",
            "scorecard_id": "scorecard-1",
            "score_id": "score-1",
            "instruction": "update code",
            "model": "primary-model",
            "fallback_model": "fallback-model",
            "max_attempts": 2,
        },
        str(result_path),
    )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert payload["version_id"] == "sv-2"
    assert len(payload["attempts"]) == 2
    assert payload["attempts"][0]["status"] == "failed"
    assert payload["attempts"][0]["error_code"] == "score_edit_post_submit_test_failed"
    assert payload["attempts"][0]["version_id"] == "sv-1"
    assert payload["attempts"][1]["status"] == "succeeded"
    assert payload["attempts"][1]["version_id"] == "sv-2"


def test_evaluation_run_uses_cached_latest_score_version_after_edit(monkeypatch) -> None:
    update_seen: list[dict] = []
    evaluation_seen: dict = {}

    def fake_update(args: dict) -> dict:
        update_seen.append(dict(args))
        return {"success": True, "version_id": "sv-candidate"}

    def fake_evaluation_runner(args: dict) -> dict:
        evaluation_seen.update(args)
        return {"status": "dispatched", "evaluation_id": "eval-1"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        score_update=fake_update,
        evaluation_runner=fake_evaluation_runner,
        handle_store=_MemoryHandleStore(),
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr(
        execute,
        "_resolve_scorecard_for_score_edit",
        lambda _client, _identifier: {"id": "scorecard-1"},
    )
    monkeypatch.setattr(
        execute,
        "_resolve_score_for_score_edit",
        lambda _client, _scorecard_id, _identifier: {"id": "score-1"},
    )

    module.score.update(
        {
            "scorecard_identifier": "Compliance",
            "score_identifier": "Tone",
            "code": "name: Tone\n",
        }
    )
    module.evaluation.run(
        {
            "scorecard_name": "Compliance",
            "score_name": "Tone",
            "evaluation_type": "feedback",
            "max_feedback_items": 20,
            "sampling_mode": "newest",
            "async": True,
            "budget": _child_budget(),
        }
    )

    assert update_seen[0]["base_version_source"] == "champion"
    assert evaluation_seen["version"] == "sv-candidate"
    assert evaluation_seen["base_version_source"] == "session_latest"


def test_score_edit_resolver_accepts_external_id_identifiers() -> None:
    class FakeClient:
        def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
            if "GetScorecardById" in query:
                return {"getScorecard": None}
            if "ListScorecardsForExactIdentifier" in query:
                return {
                    "listScorecards": {
                        "items": [
                            {
                                "id": "sc-1",
                                "name": "Compliance",
                                "key": "compliance",
                                "externalId": "sc-ext",
                            }
                        ]
                    }
                }
            if "GetScoreByIdForEdit" in query:
                return {"getScore": None}
            if "GetScorecardSectionIdsForEdit" in query:
                return {
                    "getScorecard": {
                        "sections": {
                            "items": [
                                {"id": "section-1"}
                            ]
                        }
                    }
                }
            if "ListScoresBySectionForEdit" in query:
                assert variables == {"sectionId": "section-1", "limit": 200, "nextToken": None}
                return {
                    "listScoreBySectionId": {
                        "items": [
                            {
                                "id": "s-1",
                                "name": "Tone",
                                "key": "tone",
                                "externalId": "s-ext",
                            }
                        ],
                        "nextToken": None,
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    client = FakeClient()
    scorecard = execute._resolve_scorecard_for_score_edit(client, "sc-ext")
    score = execute._resolve_score_for_score_edit(client, "sc-1", "s-ext")

    assert scorecard["id"] == "sc-1"
    assert score["id"] == "s-1"


def test_score_edit_resolver_fails_for_ambiguous_matches() -> None:
    class FakeClient:
        def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
            if "GetScorecardById" in query:
                return {"getScorecard": None}
            if "ListScorecardsForExactIdentifier" in query:
                return {
                    "listScorecards": {
                        "items": [
                            {"id": "sc-1", "name": "Compliance", "key": "c-1", "externalId": "ext-1"},
                            {"id": "sc-2", "name": "Compliance", "key": "c-2", "externalId": "ext-2"},
                        ]
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    with pytest.raises(ValueError, match="ambiguous"):
        execute._resolve_scorecard_for_score_edit(FakeClient(), "Compliance")


def test_score_edit_resolver_accepts_identifiers_with_trailing_punctuation() -> None:
    class FakeClient:
        def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
            if "GetScorecardById" in query:
                return {"getScorecard": None}
            if "ListScorecardsForExactIdentifier" in query:
                return {
                    "listScorecards": {
                        "items": [
                            {
                                "id": "sc-1",
                                "name": "Example Scorecard",
                                "key": "example_scorecard",
                                "externalId": "1438",
                            }
                        ]
                    }
                }
            if "GetScoreByIdForEdit" in query:
                return {"getScore": None}
            if "GetScorecardSectionIdsForEdit" in query:
                return {
                    "getScorecard": {
                        "sections": {
                            "items": [
                                {"id": "section-1"}
                            ]
                        }
                    }
                }
            if "ListScoresBySectionForEdit" in query:
                return {
                    "listScoreBySectionId": {
                        "items": [
                            {
                                "id": "s-1",
                                "name": "Example Score",
                                "key": "example-score",
                                "externalId": "45813",
                            }
                        ],
                        "nextToken": None,
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    client = FakeClient()
    scorecard = execute._resolve_scorecard_for_score_edit(
        client, "Example Scorecard."
    )
    score = execute._resolve_score_for_score_edit(
        client, "sc-1", "\"Example Score.\""
    )

    assert scorecard["id"] == "sc-1"
    assert score["id"] == "s-1"


def test_score_edit_resolver_accepts_separator_insensitive_identifiers() -> None:
    class FakeClient:
        def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
            if "GetScorecardById" in query:
                return {"getScorecard": None}
            if "ListScorecardsForExactIdentifier" in query:
                return {
                    "listScorecards": {
                        "items": [
                            {
                                "id": "sc-1",
                                "name": "Example Scorecard",
                                "key": "example_scorecard",
                                "externalId": "1438",
                            }
                        ]
                    }
                }
            if "GetScoreByIdForEdit" in query:
                return {"getScore": None}
            if "GetScorecardSectionIdsForEdit" in query:
                return {
                    "getScorecard": {
                        "sections": {
                            "items": [
                                {"id": "section-1"}
                            ]
                        }
                    }
                }
            if "ListScoresBySectionForEdit" in query:
                return {
                    "listScoreBySectionId": {
                        "items": [
                            {
                                "id": "s-1",
                                "name": "Example Score",
                                "key": "example-score",
                                "externalId": "45813",
                            }
                        ],
                        "nextToken": None,
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    client = FakeClient()
    scorecard = execute._resolve_scorecard_for_score_edit(
        client, "example scorecard"
    )
    score = execute._resolve_score_for_score_edit(
        client, "sc-1", "example_score"
    )

    assert scorecard["id"] == "sc-1"
    assert score["id"] == "s-1"


def test_score_resolve_returns_unique_exact_score_match(monkeypatch) -> None:
    class FakeClient:
        def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
            if "GetScorecardById" in query:
                return {"getScorecard": None}
            if "ListScorecardsForExactIdentifier" in query:
                return {
                    "listScorecards": {
                        "items": [
                            {
                                "id": "sc-1",
                                "name": "Example Scorecard",
                                "key": "example_scorecard",
                                "externalId": "1438",
                            }
                        ],
                        "nextToken": None,
                    }
                }
            if "GetScoreByIdForEdit" in query:
                return {"getScore": None}
            if "GetScorecardSectionIdsForEdit" in query:
                return {
                    "getScorecard": {
                        "sections": {
                            "items": [{"id": "section-1"}],
                            "nextToken": None,
                        }
                    }
                }
            if "ListScoresBySectionForEdit" in query:
                return {
                    "listScoreBySectionId": {
                        "items": [
                            {
                                "id": "score-1",
                                "name": "Example Score",
                                "key": "example-score",
                                "externalId": "45813",
                            },
                            {
                                "id": "score-2",
                                "name": "Example Score - With Confidence",
                                "key": "example-score-confidence",
                                "externalId": "45814",
                            },
                        ],
                        "nextToken": None,
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        lambda: FakeClient(),
    )
    module = execute.PlexusRuntimeModule(FastMCP("test"))

    result = module.score.resolve(
        {
            "scorecard_identifier": "Example Scorecard",
            "score_identifier": "Example Score",
        }
    )

    assert result["status"] == "resolved"
    assert result["scorecard_id"] == "sc-1"
    assert result["score_id"] == "score-1"
    assert result["score"]["name"] == "Example Score"
    assert module.api_calls == ["plexus.score.resolve"]


def test_score_resolve_returns_ambiguous_score_candidates(monkeypatch) -> None:
    class FakeClient:
        def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
            if "GetScorecardById" in query:
                return {"getScorecard": None}
            if "ListScorecardsForExactIdentifier" in query:
                return {
                    "listScorecards": {
                        "items": [
                            {
                                "id": "sc-1",
                                "name": "Example Scorecard",
                                "key": "example_scorecard",
                                "externalId": "1438",
                            }
                        ],
                        "nextToken": None,
                    }
                }
            if "GetScoreByIdForEdit" in query:
                return {"getScore": None}
            if "GetScorecardSectionIdsForEdit" in query:
                return {
                    "getScorecard": {
                        "sections": {
                            "items": [{"id": "section-1"}],
                            "nextToken": None,
                        }
                    }
                }
            if "ListScoresBySectionForEdit" in query:
                return {
                    "listScoreBySectionId": {
                        "items": [
                            {
                                "id": "score-1",
                                "name": "Example Score",
                                "key": "example",
                                "externalId": "1",
                            },
                            {
                                "id": "score-2",
                                "name": "Example-Score",
                                "key": "example_score",
                                "externalId": "2",
                            },
                        ],
                        "nextToken": None,
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        lambda: FakeClient(),
    )
    module = execute.PlexusRuntimeModule(FastMCP("test"))

    result = module.score.resolve(
        {
            "scorecard_identifier": "Example Scorecard",
            "score_identifier": "example score",
        }
    )

    assert result["status"] == "ambiguous"
    assert result["target"] == "score"
    assert [candidate["id"] for candidate in result["candidates"]] == [
        "score-1",
        "score-2",
    ]


def test_score_edit_resolver_paginates_scorecards_and_sections() -> None:
    class FakeClient:
        def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
            if "GetScorecardById" in query:
                return {"getScorecard": None}
            if "ListScorecardsForExactIdentifier" in query:
                next_token = (variables or {}).get("nextToken")
                if next_token is None:
                    return {
                        "listScorecards": {
                            "items": [{"id": "sc-a", "name": "Other", "key": "other", "externalId": "1"}],
                            "nextToken": "page-2",
                        }
                    }
                return {
                    "listScorecards": {
                        "items": [{"id": "sc-1", "name": "Compliance", "key": "compliance", "externalId": "2"}],
                        "nextToken": None,
                    }
                }
            if "GetScoreByIdForEdit" in query:
                return {"getScore": None}
            if "GetScorecardSectionIdsForEdit" in query:
                next_token = (variables or {}).get("nextToken")
                if next_token is None:
                    return {"getScorecard": {"sections": {"items": [{"id": "section-1"}], "nextToken": "s2"}}}
                return {"getScorecard": {"sections": {"items": [{"id": "section-2"}], "nextToken": None}}}
            if "ListScoresBySectionForEdit" in query:
                section_id = (variables or {}).get("sectionId")
                if section_id == "section-1":
                    return {"listScoreBySectionId": {"items": [], "nextToken": None}}
                return {
                    "listScoreBySectionId": {
                        "items": [{"id": "score-1", "name": "Tone", "key": "tone", "externalId": "s-ext"}],
                        "nextToken": None,
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    client = FakeClient()
    scorecard = execute._resolve_scorecard_for_score_edit(client, "Compliance")
    score = execute._resolve_score_for_score_edit(client, "sc-1", "Tone")

    assert scorecard["id"] == "sc-1"
    assert score["id"] == "score-1"


def test_score_edit_preflight_gate_blocks_dispatch_on_ambiguous_targets(monkeypatch) -> None:
    handles = _MemoryHandleStore()
    dispatched = False

    def fake_runner(_args: dict) -> dict:
        nonlocal dispatched
        dispatched = True
        return {"status": "dispatched"}

    class FakeClient:
        pass

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        execute,
        "_resolve_scorecard_for_score_edit",
        lambda _client, _identifier: (_ for _ in ()).throw(
            ValueError("Clarification required before plexus.score.edit: scorecard_identifier is ambiguous")
        ),
    )

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        trace_id="trace-1",
        handle_store=handles,
        score_edit_runner=fake_runner,
    )
    budget = _child_budget()
    with pytest.raises(ValueError, match="Clarification required before plexus.score.edit"):
        module.score.edit(
            {
                "scorecard_identifier": "Example Scorecard",
                "score_identifier": "Example Score",
                "instruction": "set model to gpt-4o-mini",
                "async": True,
                "budget": budget,
            }
        )

    assert dispatched is False


def test_default_score_pull_does_not_fallback_to_fuzzy_search(monkeypatch) -> None:
    from plexus.cli.shared import client_utils, direct_identifier_resolution

    class FakeClient:
        def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
            raise AssertionError(f"unexpected query: {query}")

    monkeypatch.setattr(client_utils, "create_client", lambda: FakeClient())
    monkeypatch.setattr(
        direct_identifier_resolution,
        "direct_resolve_scorecard_identifier",
        lambda _client, _identifier: None,
    )
    monkeypatch.setattr(
        direct_identifier_resolution,
        "direct_resolve_score_identifier",
        lambda _client, _scorecard_id, _identifier: None,
    )
    monkeypatch.setattr(
        execute,
        "_default_scorecards_search",
        lambda _args: (_ for _ in ()).throw(AssertionError("fuzzy fallback must not run")),
    )

    with pytest.raises(ValueError, match="Scorecard not found"):
        execute._default_score_pull(
            {
                "scorecard_identifier": "Example Scorecard",
                "score_identifier": "Example Score",
            }
        )


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

        def poll(self) -> None:
            return None  # still running while the asynchronous record is created

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

    with execute.set_runtime_actor_context(
        {
            "actor_user_id": "user-ctx-123",
            "actor_type": "agent",
            "actor_key": "execute_tactus",
            "actor_source": "execute_tactus",
        }
    ):
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
    assert json.loads(captured["kwargs"]["env"]["PLEXUS_ACTOR_CONTEXT_JSON"])["actor_user_id"] == "user-ctx-123"
    assert result["child_budget"] == _child_budget()


def test_default_evaluation_runner_reports_clean_child_exit_before_evaluation_creation(monkeypatch) -> None:
    class CleanExitProcess:
        pid = 4242

        def poll(self) -> int:
            return 0

    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/plexus")
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: CleanExitProcess())
    monkeypatch.setattr("time.sleep", lambda _: None)

    result = execute._default_evaluation_runner(
        {
            "evaluation_type": "feedback",
            "scorecard_name": "Compliance",
            "score_name": "Tone",
        },
        None,
    )

    assert result["status"] == "error"
    assert "exit=0" in result["error"]
    assert result["evaluation_id"] is None


def test_default_evaluation_runner_passes_frozen_feedback_window(monkeypatch) -> None:
    captured: dict = {}

    class FakeProcess:
        pid = 4242

        def poll(self) -> int:
            return 1

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return FakeProcess()

    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/plexus")
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr("time.sleep", lambda _: None)

    execute._default_evaluation_runner(
        {
            "evaluation_type": "feedback",
            "scorecard_name": "Compliance",
            "score_name": "Tone",
            "max_feedback_items": 25,
            "days": 30,
            "feedback_start_at": "2026-02-01T00:00:00Z",
            "feedback_end_at": "2026-05-01T00:00:00Z",
            "budget": _child_budget(),
        },
        None,
    )

    assert "--feedback-start-at" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--feedback-start-at") + 1] == "2026-02-01T00:00:00Z"
    assert "--feedback-end-at" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--feedback-end-at") + 1] == "2026-05-01T00:00:00Z"


def test_default_evaluation_runner_forwards_exact_feedback_item_ids(monkeypatch) -> None:
    captured: dict = {}

    class FakeProcess:
        pid = 4242

        def poll(self) -> int:
            return 1

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return FakeProcess()

    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/plexus")
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr("time.sleep", lambda _: None)

    execute._default_evaluation_runner(
        {
            "evaluation_type": "feedback",
            "scorecard_name": "Compliance",
            "score_name": "Tone",
            "feedback_item_ids": ["opaque-id-B", "opaque-id-A"],
            "budget": _child_budget(),
        },
        None,
    )

    cmd = captured["cmd"]
    positions = [index for index, value in enumerate(cmd) if value == "--feedback-item-id"]
    assert [cmd[index + 1] for index in positions] == ["opaque-id-B", "opaque-id-A"]


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


def test_handle_peek_captures_late_evaluation_id_file(tmp_path) -> None:
    id_file = tmp_path / "evaluation_id.txt"
    id_file.write_text("eval-late", encoding="utf-8")
    handles = _MemoryHandleStore()
    handle = handles.create(
        kind="evaluation",
        parent_trace_id="trace-1",
        api_call="plexus.evaluation.run",
        args={"async": True},
        dispatch_result={
            "process_id": 4242,
            "evaluation_id_file": str(id_file),
        },
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
    assert snapshot["evaluation_id"] == "eval-late"
    assert snapshot["evaluation"]["id"] == "eval-late"
    assert snapshot["evaluation"]["status"] == "COMPLETED"
    assert not id_file.exists()


def test_handle_peek_marks_no_id_exited_process_failed(monkeypatch) -> None:
    handles = _MemoryHandleStore()
    handle = handles.create(
        kind="evaluation",
        parent_trace_id="trace-1",
        api_call="plexus.evaluation.run",
        args={"async": True},
        dispatch_result={"process_id": 4242},
    )

    monkeypatch.setattr(execute.os, "waitpid", lambda pid, options: (pid, 256))

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        handle_store=handles,
    )

    snapshot = module.handle.peek({"id": handle["id"]})

    assert snapshot["status"] == "failed"
    assert snapshot["process_status"] == "exited"
    assert snapshot["process_exit_code"] == 1
    assert snapshot["error"] == (
        "Evaluation subprocess exited before emitting an evaluation ID."
    )


def test_handle_peek_marks_no_id_successful_process_failed_with_logs(
    monkeypatch, tmp_path
) -> None:
    stdout_log = tmp_path / "eval.out.log"
    stderr_log = tmp_path / "eval.err.log"
    stdout_log.write_text("created task but no evaluation id\n", encoding="utf-8")
    stderr_log.write_text("warning: id file was not written\n", encoding="utf-8")
    handles = _MemoryHandleStore()
    handle = handles.create(
        kind="evaluation",
        parent_trace_id="trace-1",
        api_call="plexus.evaluation.run",
        args={"async": True},
        dispatch_result={
            "process_id": 4242,
            "stdout_log": str(stdout_log),
            "stderr_log": str(stderr_log),
        },
    )

    monkeypatch.setattr(execute.os, "waitpid", lambda pid, options: (pid, 0))

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        handle_store=handles,
    )

    snapshot = module.handle.peek({"id": handle["id"]})

    assert snapshot["status"] == "failed"
    assert snapshot["process_status"] == "exited"
    assert snapshot["process_exit_code"] == 0
    assert snapshot["error"] == (
        "Evaluation subprocess exited before emitting an evaluation ID."
    )
    assert snapshot["stdout_tail"] == "created task but no evaluation id"
    assert snapshot["stderr_tail"] == "warning: id file was not written"


def test_handle_peek_marks_running_evaluation_exited_process_failed(monkeypatch) -> None:
    handles = _MemoryHandleStore()
    handle = handles.create(
        kind="evaluation",
        parent_trace_id="trace-1",
        api_call="plexus.evaluation.run",
        args={"async": True},
        dispatch_result={"evaluation_id": "eval-1", "process_id": 4242},
    )

    monkeypatch.setattr(execute.os, "waitpid", lambda pid, options: (pid, 256))

    def fake_evaluation_info(args: dict) -> dict:
        return {"id": args["evaluation_id"], "status": "RUNNING"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        handle_store=handles,
        evaluation_info=fake_evaluation_info,
    )

    snapshot = module.handle.peek({"id": handle["id"]})

    assert snapshot["status"] == "failed"
    assert snapshot["evaluation"]["process_status"] == "exited"
    assert snapshot["evaluation"]["process_exit_code"] == 1
    assert snapshot["evaluation"]["error"] == (
        "Evaluation subprocess exited before the evaluation reached a terminal status."
    )


def test_handle_peek_marks_successfully_exited_nonterminal_evaluation_failed(monkeypatch) -> None:
    handles = _MemoryHandleStore()
    handle = handles.create(
        kind="evaluation",
        parent_trace_id="trace-1",
        api_call="plexus.evaluation.run",
        args={"async": True},
        dispatch_result={"evaluation_id": "eval-1", "process_id": 4242},
    )

    monkeypatch.setattr(execute.os, "waitpid", lambda pid, options: (pid, 0))

    def fake_evaluation_info(args: dict) -> dict:
        return {
            "id": args["evaluation_id"],
            "status": "RUNNING",
            "processed_items": 10,
            "total_items": 10,
        }

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        handle_store=handles,
        evaluation_info=fake_evaluation_info,
    )

    snapshot = module.handle.peek({"id": handle["id"]})

    assert snapshot["status"] == "failed"
    assert snapshot["evaluation"]["process_status"] == "exited"
    assert snapshot["evaluation"]["process_exit_code"] == 0
    assert snapshot["evaluation"]["error"] == (
        "Evaluation subprocess exited before the evaluation reached a terminal status."
    )


def test_handle_peek_reaps_completed_evaluation_process(monkeypatch) -> None:
    handles = _MemoryHandleStore()
    handle = handles.create(
        kind="evaluation",
        parent_trace_id="trace-1",
        api_call="plexus.evaluation.run",
        args={"async": True},
        dispatch_result={"evaluation_id": "eval-1", "process_id": 4242},
    )

    monkeypatch.setattr(execute.os, "waitpid", lambda pid, options: (pid, 0))

    def fake_evaluation_info(args: dict) -> dict:
        return {"id": args["evaluation_id"], "status": "COMPLETED"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        handle_store=handles,
        evaluation_info=fake_evaluation_info,
    )

    snapshot = module.handle.peek({"id": handle["id"]})

    assert snapshot["status"] == "completed"
    assert snapshot["evaluation"]["process_status"] == "exited"
    assert snapshot["evaluation"]["process_exit_code"] == 0


def test_handle_peek_keeps_completed_evaluation_running_until_its_process_exits(
    monkeypatch,
) -> None:
    handles = _MemoryHandleStore()
    handle = handles.create(
        kind="evaluation",
        parent_trace_id="trace-1",
        api_call="plexus.evaluation.run",
        args={"async": True},
        dispatch_result={"evaluation_id": "eval-1", "process_id": 4242},
    )

    monkeypatch.setattr(execute, "_exited_process_status", lambda _pid: None)

    def fake_evaluation_info(args: dict) -> dict:
        return {"id": args["evaluation_id"], "status": "COMPLETED"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        handle_store=handles,
        evaluation_info=fake_evaluation_info,
    )

    snapshot = module.handle.peek({"id": handle["id"]})

    assert snapshot["status"] == "running"
    assert snapshot["evaluation"]["completion_pending_process_exit"] is True


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


def test_handle_status_can_resume_report_by_durable_task_id(monkeypatch) -> None:
    """A later console turn can poll a report without Lambda-local handle state."""

    class FakeTask:
        id = "task-1"
        status = "COMPLETED"
        statusMessage = "Report complete"
        errorMessage = None
        output = None
        updatedAt = "2026-07-17T00:00:00Z"
        completedAt = "2026-07-17T00:00:00Z"

    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: object())
    monkeypatch.setattr(
        "plexus.dashboard.api.models.task.Task.get_by_id",
        lambda task_id, _client: FakeTask() if task_id == "task-1" else None,
    )

    module = execute.PlexusRuntimeModule(FastMCP("test"))
    status = module.handle.status({"task_id": "task-1"})

    assert status["id"] == "task-1"
    assert status["durable_id"] == "task-1"
    assert status["kind"] == "report"
    assert status["status"] == "completed"


def test_report_run_async_receives_runtime_account_context() -> None:
    seen_args: dict = {}

    def fake_runner(args: dict) -> dict:
        seen_args.update(args)
        return {"status": "dispatched", "task_id": "task-1"}

    module = execute.PlexusRuntimeModule(
        FastMCP("test"),
        report_runner=fake_runner,
        runtime_context={"account_id": "acct-from-console"},
    )

    module.report.run(
        {
            "block_class": "FeedbackAlignment",
            "block_config": {"scorecard": "Example Scorecard", "days": 30},
            "async": True,
            "budget": _child_budget(),
        }
    )

    assert seen_args["account_id"] == "acct-from-console"


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
        runtime_context={"tool_access_mode": "planning"},
    )

    budget = _child_budget()
    handle = module.report.score_champion_version_timeline(
        {
            "scorecard": "Example Scorecard",
            "days": 21,
            "include_unchanged": True,
            "async": True,
            "budget": budget,
        }
    )

    assert handle["kind"] == "report"
    assert seen_args["block_class"] == "ScoreChampionVersionTimeline"
    assert seen_args["block_config"] == {
        "scorecard": "Example Scorecard",
        "days": 21,
        "include_unchanged": True,
    }
    assert module.api_calls == ["plexus.report.run"]


def test_default_report_runner_uses_remote_dispatch_by_default(monkeypatch) -> None:
    captured: dict = {}
    client = object()

    def fake_run_block_cached(**kwargs):
        captured.update(kwargs)
        return ({"status": "dispatched", "cache_key": "report-cache", "task_id": "task-1"}, None, False)

    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: client)
    monkeypatch.setattr("plexus.reports.service.run_block_cached", fake_run_block_cached)
    monkeypatch.delenv("PLEXUS_DISPATCH_MODE", raising=False)
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("local subprocess should not run")),
    )

    budget = {"usd": 1.0, "wallclock_seconds": 900, "depth": 1, "tool_calls": 3}
    result = execute._default_report_runner(
        {
            "block_class": "FeedbackContradictions",
            "cache_key": "report-cache",
            "ttl_hours": 24,
            "budget": budget,
            "block_config": {
                "scorecard": "Card",
                "score": "Score",
                "days": 30,
                "mode": "contradictions",
                "max_feedback_items": 200,
                "num_topics": 8,
                "include_rubric_memory": True,
                "score_version_id": "version-1",
            },
        }
    )

    assert result == {
        "status": "dispatched",
        "cache_key": "report-cache",
        "task_id": "task-1",
        "block_class": "FeedbackContradictions",
        "child_budget": budget,
    }
    assert captured == {
        "block_class": "FeedbackContradictions",
        "block_config": {
            "scorecard": "Card",
            "score": "Score",
            "days": 30,
            "mode": "contradictions",
            "max_feedback_items": 200,
            "num_topics": 8,
            "include_rubric_memory": True,
            "score_version_id": "version-1",
        },
        "account_id": "acct-1",
        "client": client,
        "cache_key": "report-cache",
        "ttl_hours": 24,
        "fresh": False,
        "background": True,
        "child_budget": budget,
    }


def test_default_report_runner_normalizes_cached_output_without_status(monkeypatch) -> None:
    client = object()

    def fake_run_block_cached(**_kwargs):
        return ({"rows": [{"score": "A"}]}, None, True)

    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: client)
    monkeypatch.setattr("plexus.reports.service.run_block_cached", fake_run_block_cached)
    monkeypatch.delenv("PLEXUS_DISPATCH_MODE", raising=False)

    result = execute._default_report_runner(
        {
            "block_class": "FeedbackAlignment",
            "cache_key": "report-cache",
            "block_config": {"scorecard": "Card", "days": 30},
        }
    )

    assert result["status"] == "completed"
    assert result["cached"] is True
    assert result["result"] == {"rows": [{"score": "A"}]}
    assert result["block_class"] == "FeedbackAlignment"


def test_default_report_runner_rejects_empty_remote_payload(monkeypatch) -> None:
    client = object()

    def fake_run_block_cached(**_kwargs):
        return ({}, None, False)

    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: client)
    monkeypatch.setattr("plexus.reports.service.run_block_cached", fake_run_block_cached)
    monkeypatch.delenv("PLEXUS_DISPATCH_MODE", raising=False)

    with pytest.raises(ValueError, match="empty payload"):
        execute._default_report_runner(
            {
                "block_class": "FeedbackAlignment",
                "cache_key": "report-cache",
                "block_config": {"scorecard": "Card", "days": 30},
            }
        )


def test_default_report_runner_disables_feedback_alignment_memory_by_default(monkeypatch) -> None:
    captured: dict = {}
    client = object()

    def fake_run_block_cached(**kwargs):
        captured.update(kwargs)
        return ({"status": "dispatched", "cache_key": "report-cache", "task_id": "task-1"}, None, False)

    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: client)
    monkeypatch.setattr("plexus.reports.service.run_block_cached", fake_run_block_cached)
    monkeypatch.delenv("PLEXUS_DISPATCH_MODE", raising=False)

    result = execute._default_report_runner(
        {
            "block_class": "FeedbackAlignment",
            "cache_key": "report-cache",
            "block_config": {"scorecard": "Example Scorecard", "days": 30},
        }
    )

    assert result["task_id"] == "task-1"
    assert captured["block_config"] == {
        "scorecard": "Example Scorecard",
        "days": 30,
        "memory_analysis": False,
    }


def test_default_report_runner_preserves_explicit_feedback_alignment_memory(monkeypatch) -> None:
    captured: dict = {}
    client = object()

    def fake_run_block_cached(**kwargs):
        captured.update(kwargs)
        return ({"status": "dispatched", "cache_key": "report-cache", "task_id": "task-1"}, None, False)

    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: client)
    monkeypatch.setattr("plexus.reports.service.run_block_cached", fake_run_block_cached)
    monkeypatch.delenv("PLEXUS_DISPATCH_MODE", raising=False)

    execute._default_report_runner(
        {
            "block_class": "FeedbackAlignment",
            "cache_key": "report-cache",
            "block_config": {
                "scorecard": "Example Scorecard",
                "days": 30,
                "memory_analysis": True,
            },
        }
    )

    assert captured["block_config"]["memory_analysis"] is True


def test_default_report_runner_requires_account_context_without_null_key(monkeypatch) -> None:
    fake_client = SimpleNamespace(
        context=SimpleNamespace(account_id=None, account_key=None)
    )

    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: fake_client)
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not resolve default account with a null key")
        ),
    )
    monkeypatch.delenv("PLEXUS_DISPATCH_MODE", raising=False)

    with pytest.raises(execute.AccountContextRequired, match="requires account context"):
        execute._default_report_runner({"block_class": "FeedbackAlignment"})


def test_default_report_runner_uses_remote_dispatch_for_celery_mode(monkeypatch) -> None:
    calls: list[dict] = []
    client = object()

    def fake_run_block_cached(**kwargs):
        calls.append(kwargs)
        return ({"status": "dispatched", "cache_key": "report-cache", "task_id": "task-1"}, None, False)

    monkeypatch.setenv("PLEXUS_DISPATCH_MODE", "celery")
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: client)
    monkeypatch.setattr("plexus.reports.service.run_block_cached", fake_run_block_cached)

    result = execute._default_report_runner(
        {
            "block_class": "AcceptanceRate",
            "cache_key": "report-cache",
            "block_config": {"scorecard": "Card", "score": "Score", "days": 7},
        }
    )

    assert result["status"] == "dispatched"
    assert result["block_class"] == "AcceptanceRate"
    assert calls[0]["background"] is True


def test_default_report_runner_dispatches_report_config_remotely(monkeypatch) -> None:
    created: dict = {}
    client = object()

    def fake_create(**kwargs):
        created.update(kwargs)
        return SimpleNamespace(id="task-1")

    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: client)
    monkeypatch.setattr("plexus.dashboard.api.models.task.Task.create", fake_create)
    monkeypatch.delenv("PLEXUS_DISPATCH_MODE", raising=False)
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("local subprocess should not run")),
    )

    result = execute._default_report_runner(
        {
            "configuration_id": "config-1",
            "parameters": {"days": 7, "score": "Example Score"},
        }
    )

    assert result == {
        "status": "dispatched",
        "configuration_id": "config-1",
        "parameters": {"days": 7, "score": "Example Score"},
        "task_id": "task-1",
    }
    assert created["client"] is client
    assert created["accountId"] == "acct-1"
    assert created["type"] == "Report"
    assert created["target"] == "report/configuration"
    assert created["command"] == "report run --config config-1 days=7 'score=Example Score'"
    assert created["dispatchStatus"] == "PENDING"
    assert created["status"] == "PENDING"
    assert json.loads(created["metadata"]) == {
        "report_configuration_id": "config-1",
        "report_parameters": {"days": 7, "score": "Example Score"},
        "account_id": "acct-1",
        "trigger": "mcp_remote",
    }


def test_default_report_runner_rejects_invalid_dispatch_mode(monkeypatch) -> None:
    monkeypatch.setenv("PLEXUS_DISPATCH_MODE", "invalid")

    with pytest.raises(ValueError, match="Invalid PLEXUS_DISPATCH_MODE"):
        execute._default_report_runner({"block_class": "AcceptanceRate"})


def test_runtime_env_dispatch_mode_overrides_dotenv_default() -> None:
    # Reproduce the historical regression: importing execute used to let .env
    # overwrite an explicitly set PLEXUS_DISPATCH_MODE.
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    script = (
        "import os\n"
        "os.environ['PLEXUS_DISPATCH_MODE'] = 'celery'\n"
        "from MCP.tools.tactus_runtime import execute\n"
        "print(execute._resolve_report_dispatch_mode())\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{env.get('PYTHONPATH', '')}"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "celery"


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
    monkeypatch.setenv("PLEXUS_DISPATCH_MODE", "local")
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr("subprocess.Popen", fake_popen)

    with execute.set_runtime_actor_context(
        {
            "actor_user_id": "user-ctx-123",
            "actor_type": "agent",
            "actor_key": "execute_tactus",
            "actor_source": "execute_tactus",
        }
    ):
        result = execute._default_report_runner(
            {
                "block_class": "FeedbackContradictions",
                "cache_key": "report-cache",
                "ttl_hours": 24,
                "block_config": {
                    "scorecard": "Card",
                    "score": "Score",
                    "days": 30,
                    "mode": "contradictions",
                    "max_feedback_items": 200,
                    "num_topics": 8,
                    "include_rubric_memory": True,
                    "score_version_id": "version-1",
                },
                "fresh": True,
            }
        )

    assert result == {"status": "running", "block_class": "FeedbackContradictions", "pid": 12345}
    assert captured["cmd"] == [
        captured["cmd"][0],
        "-m",
        "plexus",
        "feedback",
        "report",
        "contradictions",
        "--scorecard",
        "Card",
        "--score",
        "Score",
        "--days",
        "30",
        "--cache-key",
        "report-cache",
        "--ttl-hours",
        "24",
        "--score-version-id",
        "version-1",
        "--mode",
        "contradictions",
        "--max-feedback-items",
        "200",
        "--num-topics",
        "8",
        "--include-rubric-memory",
        "--fresh",
    ]
    assert captured["kwargs"]["stdout"] is not None
    assert captured["kwargs"]["stderr"] is not None
    assert json.loads(captured["kwargs"]["env"]["PLEXUS_ACTOR_CONTEXT_JSON"])["actor_user_id"] == "user-ctx-123"


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
    monkeypatch.setenv("PLEXUS_DISPATCH_MODE", "local")
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr("subprocess.Popen", fake_popen)

    result = execute._default_report_runner(
        {
            "block_class": "ScoreChampionVersionTimeline",
            "block_config": {
                "scorecard": "Example Scorecard",
                "score": "Example Score",
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
        "Example Scorecard",
        "--score",
        "Example Score",
        "--days",
        "21",
        "--include-unchanged",
        "--fresh",
    ]


def test_default_report_runner_rejects_unknown_block_class_for_local_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )
    monkeypatch.setenv("PLEXUS_DISPATCH_MODE", "local")
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)

    with pytest.raises(ValueError) as exc:
        execute._default_report_runner(
            {
                "block_class": "UnknownReportBlock",
                "block_config": {"scorecard": "Card"},
            }
        )

    assert "Unsupported block_class for local report dispatch" in str(exc.value)


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
    assert result["value"]["dispatch_result"]["task_id"] == "task-1"
    assert result["api_calls"] == ["plexus.report.run"]
    assert result["cost"]["tool_calls"] == 3


@pytest.mark.asyncio
async def test_execute_tactus_report_run_async_remote_dispatch_when_mode_celery(monkeypatch) -> None:
    monkeypatch.setattr(execute, "_resolve_report_dispatch_mode", lambda: "celery")
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )

    captured: dict[str, Any] = {}

    def fake_run_block_cached(**kwargs):
        captured.update(kwargs)
        return (
            {"status": "dispatched", "cache_key": "report-cache", "task_id": "task-1"},
            None,
            False,
        )

    monkeypatch.setattr("plexus.reports.service.run_block_cached", fake_run_block_cached)

    handles = _MemoryHandleStore()
    mcp = FastMCP("test-execute-tactus-report-run-celery-dispatch")
    result = await execute._execute_tactus_tool(
        (
            'report{ block_class = "FeedbackContradictions", cache_key = "report-cache", '
            'ttl_hours = 24, async = true, '
            'budget = { usd = 0.01, wallclock_seconds = 10, depth = 1, tool_calls = 2 }, '
            'block_config = { scorecard = "Card", score = "Score", days = 90, '
            'mode = "contradictions", max_feedback_items = 200, num_topics = 8, '
            'include_rubric_memory = true, score_version_id = "version-1" } }'
        ),
        mcp,
        handle_store=handles,
    )

    assert result["ok"] is True
    assert result["value"]["kind"] == "report"
    assert handles.created[0]["dispatch_result"]["task_id"] == "task-1"
    assert captured["background"] is True
    assert captured["cache_key"] == "report-cache"
    assert captured["ttl_hours"] == 24
    assert captured["block_config"]["mode"] == "contradictions"
    assert captured["child_budget"] == {
        "usd": 0.01,
        "wallclock_seconds": 10,
        "depth": 1,
        "tool_calls": 2,
    }


@pytest.mark.asyncio
async def test_execute_tactus_report_run_async_local_dispatch_when_mode_local(monkeypatch) -> None:
    monkeypatch.setattr(execute, "_resolve_report_dispatch_mode", lambda: "local")
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )
    monkeypatch.setattr(
        "plexus.reports.service.run_block_cached",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("remote dispatcher should not run in local mode")
        ),
    )

    class FakeProcess:
        pid = 9999

    captured_cmd: dict[str, Any] = {}

    def fake_popen(cmd, **kwargs):
        captured_cmd["cmd"] = cmd
        captured_cmd["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    handles = _MemoryHandleStore()
    mcp = FastMCP("test-execute-tactus-report-run-local-dispatch")
    result = await execute._execute_tactus_tool(
        (
            'report{ block_class = "FeedbackContradictions", async = true, '
            'budget = { usd = 0.01, wallclock_seconds = 10, depth = 1, tool_calls = 2 }, '
            'block_config = { scorecard = "Card", score = "Score", days = 90, mode = "contradictions" } }'
        ),
        mcp,
        handle_store=handles,
    )

    assert result["ok"] is True
    assert result["value"]["kind"] == "report"
    assert handles.created[0]["dispatch_result"]["status"] == "running"
    assert handles.created[0]["dispatch_result"]["pid"] == 9999
    assert "feedback" in captured_cmd["cmd"]
    assert "contradictions" in captured_cmd["cmd"]


@pytest.mark.asyncio
async def test_execute_tactus_report_run_async_invalid_dispatch_mode_returns_error(monkeypatch) -> None:
    monkeypatch.setenv("PLEXUS_DISPATCH_MODE", "invalid-mode")
    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", object)
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "acct-1",
    )

    mcp = FastMCP("test-execute-tactus-report-run-invalid-dispatch")
    result = await execute._execute_tactus_tool(
        (
            'report{ block_class = "AcceptanceRate", async = true, '
            'budget = { usd = 0.01, wallclock_seconds = 10, depth = 1, tool_calls = 2 }, '
            'block_config = { scorecard = "Card", score = "Score", days = 30 } }'
        ),
        mcp,
    )

    assert result["ok"] is False
    assert "Invalid PLEXUS_DISPATCH_MODE" in result["error"]["message"]


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


def test_evaluation_archive_no_longer_in_mcp_tool_map() -> None:
    assert ("evaluation", "archive") not in execute.MCP_TOOL_MAP
    assert ("evaluation", "archive") in execute.DIRECT_HANDLERS


def test_evaluation_info_is_listed_in_plexus_api_list() -> None:
    module = execute.PlexusRuntimeModule(FastMCP("test"))

    catalog = module.api.list()

    assert "info" in catalog["plexus.evaluation"]
    assert "compare" in catalog["plexus.evaluation"]
    assert "find_recent" in catalog["plexus.evaluation"]
    assert "archive" in catalog["plexus.evaluation"]


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


def test_plexus_facade_uses_direct_evaluation_archive_handler_without_mcp_loopback() -> None:
    received_args: dict[str, Any] = {}

    def fake_archive(args: dict[str, Any]) -> dict[str, Any]:
        received_args.update(args)
        return {"success": True, "evaluation_id": args["id"], "status": "ARCHIVED"}

    class FakeMCP:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            raise AssertionError("plexus.evaluation.archive must not call MCP tools")

    fake_mcp = FakeMCP()
    module = execute.PlexusRuntimeModule(fake_mcp, evaluation_archive=fake_archive)

    value = module.evaluation.archive({"id": "eval-1", "reason": "duplicate run"})

    assert value == {"success": True, "evaluation_id": "eval-1", "status": "ARCHIVED"}
    assert received_args == {"id": "eval-1", "reason": "duplicate run"}
    assert module.api_calls == ["plexus.evaluation.archive"]
    assert fake_mcp.calls == []


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


def test_default_evaluation_archive_sets_archived_status_and_metadata(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeClient:
        def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
            if "query GetEvaluationForArchive" in query:
                return {
                    "getEvaluation": {
                        "id": "eval-1",
                        "status": "COMPLETED",
                        "metadata": json.dumps({"source": "test"}),
                    }
                }
            if "mutation UpdateEvaluationArchive" in query:
                captured["update_input"] = (variables or {}).get("input")
                return {
                    "updateEvaluation": {
                        "id": "eval-1",
                        "status": "ARCHIVED",
                        "metadata": captured["update_input"]["metadata"],
                        "updatedAt": "2026-05-13T12:00:00Z",
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: FakeClient())

    result = execute._default_evaluation_archive(
        {"id": "eval-1", "reason": "noise cleanup", "archived_by": "agent"}
    )

    assert result["success"] is True
    assert result["evaluation_id"] == "eval-1"
    assert result["status"] == "ARCHIVED"
    assert result["previous_status"] == "COMPLETED"
    assert captured["update_input"]["id"] == "eval-1"
    assert captured["update_input"]["status"] == "ARCHIVED"
    metadata = json.loads(captured["update_input"]["metadata"])
    assert metadata["source"] == "test"
    assert metadata["archive"]["archived"] is True
    assert metadata["archive"]["reason"] == "noise cleanup"
    assert metadata["archive"]["archivedBy"] == "agent"
    assert metadata["archive"]["previousStatus"] == "COMPLETED"


def test_default_procedure_archive_sets_archived_status_and_metadata(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeClient:
        def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
            if "query GetProcedureForArchive" in query:
                return {
                    "getProcedure": {
                        "id": "proc-1",
                        "status": "RUNNING",
                        "metadata": {"source": "test"},
                    }
                }
            if "mutation UpdateProcedureArchive" in query:
                captured["update_input"] = (variables or {}).get("input")
                return {
                    "updateProcedure": {
                        "id": "proc-1",
                        "status": "ARCHIVED",
                        "metadata": captured["update_input"]["metadata"],
                        "updatedAt": "2026-05-13T12:00:00Z",
                    }
                }
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr("plexus.cli.shared.client_utils.create_client", lambda: FakeClient())

    result = execute._default_procedure_archive(
        {"id": "proc-1", "reason": "noise cleanup", "archivedBy": "agent"}
    )

    assert result["success"] is True
    assert result["procedure_id"] == "proc-1"
    assert result["status"] == "ARCHIVED"
    assert result["previous_status"] == "RUNNING"
    assert captured["update_input"]["id"] == "proc-1"
    assert captured["update_input"]["status"] == "ARCHIVED"
    metadata = json.loads(captured["update_input"]["metadata"])
    assert metadata["source"] == "test"
    assert metadata["archive"]["archived"] is True
    assert metadata["archive"]["reason"] == "noise cleanup"
    assert metadata["archive"]["archivedBy"] == "agent"
    assert metadata["archive"]["previousStatus"] == "RUNNING"


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
    assert kwargs["days"] == 30
    assert kwargs["limit"] == 4
    assert kwargs["offset"] == 8
    assert kwargs["initial_value"] == "Yes"
    assert kwargs["final_value"] == "No"
    assert kwargs["prioritize_edit_comments"] is False


def test_default_feedback_alignment_uses_explicit_runtime_account(
    monkeypatch,
) -> None:
    captured: dict = {}

    class FakeFeedbackService:
        @staticmethod
        async def summarize_feedback(**kwargs):
            captured["summary_kwargs"] = kwargs
            return SimpleNamespace(stub_summary_result=True)

        @staticmethod
        def format_summary_result_as_dict(result):
            captured["formatted_from"] = result
            return {"summary": {"total": 3}}

    fake_client = SimpleNamespace(
        context=SimpleNamespace(account_id=None, account_key=None)
    )

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: fake_client
    )
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("default account resolver should not run")
        ),
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

    result = execute._default_feedback_alignment(
        {
            "scorecard_name": "Example Scorecard",
            "score_name": "Example Score",
            "account_id": "acct-console",
            "days": 14,
        }
    )

    assert result == {"summary": {"total": 3}}
    assert fake_client.context.account_id == "acct-console"
    kwargs = captured["summary_kwargs"]
    assert kwargs["account_id"] == "acct-console"
    assert kwargs["scorecard_name"] == "Example Scorecard"
    assert kwargs["score_name"] == "Example Score"
    assert kwargs["days"] == 14


def test_default_feedback_alignment_requires_account_context_without_null_key(
    monkeypatch,
) -> None:
    fake_client = SimpleNamespace(
        context=SimpleNamespace(account_id=None, account_key=None)
    )

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client", lambda: fake_client
    )
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not resolve default account with a null key")
        ),
    )

    with pytest.raises(execute.AccountContextRequired, match="requires account context"):
        execute._default_feedback_alignment(
            {
                "scorecard_name": "Example Scorecard",
                "score_name": "Example Score",
            }
        )


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
async def test_execute_tactus_injects_runtime_account_into_feedback_handler() -> None:
    mcp = FastMCP("test-execute-tactus-feedback-context")
    seen_args: dict = {}

    def fake_finder(args: dict) -> dict:
        seen_args.update(args)
        return {"context": {"account_id": args.get("account_id")}, "feedback_items": []}

    result = await execute._execute_tactus_tool(
        'feedback{ scorecard_name = "x", score_name = "y" }',
        mcp,
        feedback_finder=fake_finder,
        runtime_context={"account_id": "acct-console"},
    )

    assert result["ok"] is True
    assert result["value"]["context"]["account_id"] == "acct-console"
    assert seen_args["account_id"] == "acct-console"


def test_plexus_facade_injects_runtime_account_into_scorecard_search() -> None:
    class FakeMCP:
        async def call_tool(self, name, arguments):
            raise AssertionError(
                "scorecards.search must not loop back through MCP; got "
                f"{name!r} with {arguments!r}"
            )

    seen_args: dict = {}

    def fake_search(args: dict) -> dict:
        seen_args.update(args)
        return {"success": True, "matches": [], "account_id": args.get("account_id")}

    facade = execute.PlexusRuntimeModule(
        FakeMCP(),
        scorecards_searcher=fake_search,
        runtime_context={"account_id": "acct-console"},
    )
    result = facade.scorecards.search({"query": "Example Scorecard"})

    assert result["account_id"] == "acct-console"
    assert seen_args["account_id"] == "acct-console"


@pytest.mark.asyncio
async def test_execute_tactus_direct_handler_exception_is_structured() -> None:
    mcp = FastMCP("test-execute-tactus-feedback-handler-error")

    def fake_finder(_args: dict) -> dict:
        raise RuntimeError("original handler failure")

    result = await execute._execute_tactus_tool(
        'feedback{ scorecard_name = "x", score_name = "y" }',
        mcp,
        feedback_finder=fake_finder,
    )

    assert result["ok"] is False
    assert result["value"] is None
    assert result["error"]["code"] == "runtime_api_error"
    assert result["error"]["type"] == "RuntimeError"
    assert "original handler failure" in result["error"]["message"]
    assert "Sandbox error:" not in result["error"]["message"]


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
    assert result["error"]["code"] == "invalid_request"
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


def test_feedback_alignment_batch_accepts_scorecard_id(monkeypatch) -> None:
    from plexus.cli.shared import client_utils, memoized_resolvers

    class FakeClient:
        def execute(self, query, _variables=None):
            if "ListFeedbackItemsByEditedTime" in query:
                return {
                    "listFeedbackItemByAccountIdAndEditedAt": {
                        "items": [],
                        "nextToken": None,
                    }
                }
            return {
                "getScorecard": {
                    "id": "scorecard-1",
                    "name": "Example Scorecard",
                    "sections": {"items": []},
                }
            }

    resolved_identifiers = []
    monkeypatch.setattr(client_utils, "create_client", lambda: FakeClient())
    monkeypatch.setattr(
        memoized_resolvers,
        "memoized_resolve_scorecard_identifier",
        lambda _client, identifier: resolved_identifiers.append(identifier) or "scorecard-1",
    )
    monkeypatch.setattr(execute, "_resolve_runtime_account_id", lambda *_args: "account-1")

    result = execute._default_feedback_alignment_batch({"scorecard_id": "scorecard-1"})

    assert resolved_identifiers == ["scorecard-1"]
    assert result["scorecard_id"] == "scorecard-1"
    assert result["scores"] == []


def test_feedback_alignment_window_aggregates_pages_without_retaining_raw_items() -> None:
    """Complete windows keep only compact pair counts across continuation pages."""
    requests = []

    class FakeClient:
        def execute(self, _query, variables):
            requests.append(variables["nextToken"])
            if variables["nextToken"] is None:
                return {
                    "listFeedbackItemByAccountIdAndEditedAt": {
                        "items": [
                            {
                                "scorecardId": "card-1",
                                "scoreId": "score-1",
                                "initialAnswerValue": "No",
                                "finalAnswerValue": "Yes",
                                "isInvalid": False,
                            },
                            {
                                "scorecardId": "card-1",
                                "scoreId": "score-1",
                                "initialAnswerValue": "No",
                                "finalAnswerValue": "Yes",
                                "isInvalid": True,
                            },
                        ],
                        "nextToken": "page-2",
                    }
                }
            return {
                "listFeedbackItemByAccountIdAndEditedAt": {
                    "items": [
                        {
                            "scorecardId": "card-1",
                            "scoreId": "score-1",
                            "initialAnswerValue": "Yes",
                            "finalAnswerValue": "Yes",
                            "isInvalid": False,
                        },
                    ],
                    "nextToken": None,
                }
            }

    aggregates = execute._aggregate_feedback_alignment_window(
        FakeClient(), account_id="account-1", days=14
    )

    assert requests == [None, "page-2"]
    assert aggregates == {
        ("card-1", "score-1"): {("Yes", "No"): 1, ("Yes", "Yes"): 1}
    }


def test_feedback_alignment_batch_accepts_bounded_scorecard_list(monkeypatch) -> None:
    from plexus.cli.shared import client_utils, memoized_resolvers

    class FakeClient:
        def execute(self, query, _variables=None):
            if "ListFeedbackItemsByEditedTime" in query:
                return {
                    "listFeedbackItemByAccountIdAndEditedAt": {
                        "items": [],
                        "nextToken": None,
                    }
                }
            requested_name = next(
                name for name in ("One", "Two", "Three") if f"id-{name}" in query
            )
            return {
                "getScorecard": {
                    "id": f"id-{requested_name}",
                    "name": requested_name,
                    "sections": {"items": []},
                }
            }

    monkeypatch.setattr(client_utils, "create_client", lambda: FakeClient())
    monkeypatch.setattr(
        memoized_resolvers,
        "memoized_resolve_scorecard_identifier",
        lambda _client, identifier: f"id-{identifier}",
    )
    monkeypatch.setattr(execute, "_resolve_runtime_account_id", lambda *_args: "account-1")

    result = execute._default_feedback_alignment_batch(
        {"scorecards": ["One", "Two", "Three"], "days": 30}
    )

    assert result["days"] == 30
    assert result["scorecards_requested"] == 3
    assert result["scorecards_analyzed"] == 3
    assert [row["scorecard_name"] for row in result["scorecards"]] == [
        "One",
        "Two",
        "Three",
    ]


def test_feedback_alignment_batch_preserves_opaque_list_identifier(monkeypatch) -> None:
    from plexus.cli.shared import client_utils, memoized_resolvers

    opaque_id = "  opaque_UUID:with/slashes+punctuation  "
    resolved: list[str] = []

    class FakeClient:
        def execute(self, query, _variables=None):
            if "ListFeedbackItemsByEditedTime" in query:
                return {
                    "listFeedbackItemByAccountIdAndEditedAt": {
                        "items": [], "nextToken": None,
                    }
                }
            return {
                "getScorecard": {
                    "id": opaque_id, "name": "Opaque", "sections": {"items": []},
                }
            }

    monkeypatch.setattr(client_utils, "create_client", lambda: FakeClient())
    monkeypatch.setattr(
        memoized_resolvers,
        "memoized_resolve_scorecard_identifier",
        lambda _client, identifier: resolved.append(identifier) or identifier,
    )
    monkeypatch.setattr(execute, "_resolve_runtime_account_id", lambda *_args: "account-1")

    result = execute._default_feedback_alignment_batch({"scorecards": [opaque_id]})

    assert resolved == [opaque_id]
    assert result["scorecards"][0]["scorecard_id"] == opaque_id


def test_feedback_alignment_batch_selects_bounded_portfolio_in_one_call(monkeypatch) -> None:
    from plexus.cli.shared import client_utils, memoized_resolvers

    inventory_args = []
    created_clients = []

    class FakeClient:
        def execute(self, query, _variables=None):
            if "ListFeedbackItemsByEditedTime" in query:
                return {
                    "listFeedbackItemByAccountIdAndEditedAt": {
                        "items": [],
                        "nextToken": None,
                    }
                }
            raise AssertionError("bounded portfolio analysis must reuse inventory score data")

    monkeypatch.setattr(
        client_utils,
        "create_client",
        lambda: created_clients.append(FakeClient()) or created_clients[-1],
    )
    monkeypatch.setattr(
        memoized_resolvers,
        "memoized_resolve_scorecard_identifier",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("bounded portfolio analysis must not re-resolve inventory IDs")
        ),
    )
    monkeypatch.setattr(execute, "_resolve_runtime_account_id", lambda *_args: "account-1")
    monkeypatch.setattr(
        execute,
        "_default_scorecards_list",
        lambda args: inventory_args.append(args) or [
            {"id": "id-One", "name": "One", "sections": {"items": []}},
            {"id": "id-Two", "name": "Two", "sections": {"items": []}},
        ],
    )

    result = execute._default_feedback_alignment_batch(
        {"scorecard_limit": 2, "days": 30}
    )

    assert inventory_args == [{"limit": 2, "_include_scores": True}]
    assert len(created_clients) == 1
    assert result["selection_rule"] == "first 2 scorecards returned"
    assert result["scorecards_requested"] == 2
    assert [row["scorecard_name"] for row in result["scorecards"]] == ["One", "Two"]


def test_feedback_alignment_batch_prefetches_portfolio_window_once(monkeypatch) -> None:
    from plexus.cli.feedback.feedback_service import FeedbackService
    from plexus.cli.shared import client_utils, memoized_resolvers

    executed_queries = []

    class FakeClient:
        def execute(self, query, variables=None):
            executed_queries.append((query, variables or {}))
            if "ListFeedbackItemsByEditedTime" in query:
                return {
                    "listFeedbackItemByAccountIdAndEditedAt": {
                        "items": [
                            {
                                "id": "feedback-1",
                                "scorecardId": "id-One",
                                "scoreId": "score-one",
                                "initialAnswerValue": "No",
                                "finalAnswerValue": "Yes",
                                "isInvalid": False,
                            },
                            *[
                                {
                                    "id": f"feedback-{index}",
                                    "scorecardId": "id-One",
                                    "scoreId": "score-one",
                                    "initialAnswerValue": "Yes",
                                    "finalAnswerValue": "Yes",
                                    "isInvalid": False,
                                }
                                for index in range(2, 5)
                            ],
                        ],
                        "nextToken": None,
                    }
                }

            scorecard_name = "One" if "id-One" in query else "Two"
            score_id = "score-one" if scorecard_name == "One" else "score-two"
            return {
                "getScorecard": {
                    "id": f"id-{scorecard_name}",
                    "name": scorecard_name,
                    "sections": {
                        "items": [
                            {
                                "scores": {
                                    "items": [{"id": score_id, "name": f"Score {scorecard_name}"}]
                                }
                            }
                        ]
                    },
                }
            }

    monkeypatch.setattr(client_utils, "create_client", lambda: FakeClient())
    monkeypatch.setattr(
        memoized_resolvers,
        "memoized_resolve_scorecard_identifier",
        lambda _client, identifier: f"id-{identifier}",
    )
    monkeypatch.setattr(execute, "_resolve_runtime_account_id", lambda *_args: "account-1")
    monkeypatch.setattr(
        FeedbackService,
        "summarize_feedback",
        staticmethod(lambda **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected per-score query"))),
    )

    result = execute._default_feedback_alignment_batch(
        {"scorecards": ["One", "Two"], "days": 30}
    )

    feedback_window_queries = [
        query for query, _variables in executed_queries
        if "ListFeedbackItemsByEditedTime" in query
    ]
    assert len(feedback_window_queries) == 1
    assert result["scorecards"][0]["scores"][0]["total_items"] == 4
    assert result["scorecards"][0]["scores"][0]["accuracy"] == 75
    assert result["scorecards"][0]["scores"][0]["disagreements"] == 1
    assert result["scorecards"][0]["scores"][0]["disagreement_rate"] == 0.25
    assert result["scorecards"][0]["scores"][0]["reviewed_error_opportunity"] == 1.0
    assert result["scorecards"][1]["scores"][0]["total_items"] == 0
    assert result["scorecards"][1]["scores"][0]["disagreements"] == 0
    assert result["scorecards"][1]["scores"][0]["disagreement_rate"] is None
    assert result["scorecards"][1]["scores"][0]["reviewed_error_opportunity"] == 0.0


def test_feedback_alignment_batch_derives_percent_accuracy_from_reviewed_counts(
    monkeypatch,
) -> None:
    """Portfolio results have one percent accuracy contract, regardless of source units."""
    from plexus.cli.feedback.feedback_service import FeedbackService

    monkeypatch.setattr(
        FeedbackService,
        "_analyze_feedback_items",
        staticmethod(
            lambda _items: {
                # Simulate a legacy ratio-valued upstream analysis.  The
                # reviewed counts remain the canonical portfolio evidence.
                "accuracy": 0.25,
                "total_items": 4,
                "disagreements": 1,
            }
        ),
    )

    result = execute._default_feedback_alignment_batch(
        {"scorecard": "Example", "days": 30},
        _prefetched_account_id="account-1",
        _prefetched_scorecard_data={
            "id": "scorecard-1",
            "name": "Example",
            "sections": {
                "items": [
                    {"scores": {"items": [{"id": "score-1", "name": "Score"}]}}
                ]
            },
        },
        _prefetched_feedback_items=[
            {
                "id": f"feedback-{index}",
                "scorecardId": "scorecard-1",
                "scoreId": "score-1",
                "initialAnswerValue": "No" if index == 1 else "Yes",
                "finalAnswerValue": "Yes",
                "isInvalid": False,
            }
            for index in range(1, 5)
        ],
    )

    row = result["scores"][0]
    assert row["accuracy"] == 75.0
    assert row["disagreement_rate"] == 0.25
    assert row["reviewed_error_opportunity"] == 1.0


def test_feedback_alignment_batch_bounds_concurrent_score_reads(monkeypatch) -> None:
    from plexus.cli.feedback.feedback_service import FeedbackService
    from plexus.cli.shared import client_utils, memoized_resolvers

    score_count = 7

    class FakeClient:
        def execute(self, _query):
            return {
                "getScorecard": {
                    "id": "scorecard-1",
                    "name": "Example Scorecard",
                    "sections": {
                        "items": [
                            {
                                "scores": {
                                    "items": [
                                        {"id": f"score-{index}", "name": f"Score {index}"}
                                        for index in range(score_count)
                                    ]
                                }
                            }
                        ]
                    },
                }
            }

    active_reads = 0
    max_active_reads = 0

    async def fake_summarize_feedback(**kwargs):
        nonlocal active_reads, max_active_reads
        active_reads += 1
        max_active_reads = max(max_active_reads, active_reads)
        await asyncio.sleep(0.01)
        active_reads -= 1
        return {"analysis": {"accuracy": 100}, "score_name": kwargs["score_name"]}

    monkeypatch.setattr(client_utils, "create_client", lambda: FakeClient())
    monkeypatch.setattr(
        memoized_resolvers,
        "memoized_resolve_scorecard_identifier",
        lambda _client, _identifier: "scorecard-1",
    )
    monkeypatch.setattr(execute, "_resolve_runtime_account_id", lambda *_args: "account-1")
    monkeypatch.setattr(
        FeedbackService,
        "summarize_feedback",
        staticmethod(fake_summarize_feedback),
    )
    monkeypatch.setattr(
        FeedbackService,
        "format_summary_result_as_dict",
        staticmethod(lambda summary: summary),
    )

    result = execute._default_feedback_alignment_batch({"scorecard": "Example"})

    assert result["scores_analyzed"] == score_count
    assert max_active_reads == execute.FEEDBACK_ALIGNMENT_SCORE_CONCURRENCY


def test_feedback_alignment_batch_accepts_complete_target_set_with_bounded_workers(
    monkeypatch,
) -> None:
    from plexus.cli.shared import client_utils, memoized_resolvers

    identifiers = [f"opaque-scorecard-{index}" for index in range(7)]
    display_names = {
        identifier: f"Display Scorecard {index}"
        for index, identifier in enumerate(identifiers)
    }
    feedback_window_queries = 0
    executor_workers: list[int] = []

    class FakeClient:
        def execute(self, query, _variables=None):
            nonlocal feedback_window_queries
            if "ListFeedbackItemsByEditedTime" in query:
                feedback_window_queries += 1
                return {
                    "listFeedbackItemByAccountIdAndEditedAt": {
                        "items": [],
                        "nextToken": None,
                    }
                }
            identifier = next(value for value in identifiers if value in query)
            return {
                "getScorecard": {
                    "id": identifier,
                    "name": display_names[identifier],
                    "sections": {"items": []},
                }
            }

    class RecordingExecutor:
        def __init__(self, *, max_workers):
            executor_workers.append(max_workers)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def map(self, function, values):
            return map(function, values)

    monkeypatch.setattr(client_utils, "create_client", lambda: FakeClient())
    monkeypatch.setattr(
        memoized_resolvers,
        "memoized_resolve_scorecard_identifier",
        lambda _client, identifier: identifier,
    )
    monkeypatch.setattr(execute, "_resolve_runtime_account_id", lambda *_args: "account-1")
    monkeypatch.setattr("concurrent.futures.ThreadPoolExecutor", RecordingExecutor)

    result = execute._default_feedback_alignment_batch(
        {"scorecards": identifiers, "days": 14}
    )

    assert executor_workers == [5]
    assert feedback_window_queries == 1
    assert [row["scorecard_id"] for row in result["scorecards"]] == identifiers
    assert [row["scorecard_name"] for row in result["scorecards"]] == [
        display_names[identifier] for identifier in identifiers
    ]
    assert result["coverage"] == {
        "target_count": 7,
        "completed_count": 7,
        "failed_count": 0,
        "complete": True,
    }


def test_feedback_alignment_batch_reports_incomplete_coverage_without_losing_results(
    monkeypatch,
) -> None:
    from plexus.cli.shared import client_utils, memoized_resolvers

    identifiers = ["scorecard-one", "scorecard-missing", "scorecard-three"]

    class FakeClient:
        def execute(self, query, _variables=None):
            if "ListFeedbackItemsByEditedTime" in query:
                return {
                    "listFeedbackItemByAccountIdAndEditedAt": {
                        "items": [],
                        "nextToken": None,
                    }
                }
            identifier = next(value for value in identifiers if value in query)
            return {
                "getScorecard": {
                    "id": identifier,
                    "name": identifier,
                    "sections": {"items": []},
                }
            }

    monkeypatch.setattr(client_utils, "create_client", lambda: FakeClient())
    monkeypatch.setattr(
        memoized_resolvers,
        "memoized_resolve_scorecard_identifier",
        lambda _client, identifier: None if identifier == "scorecard-missing" else identifier,
    )
    monkeypatch.setattr(execute, "_resolve_runtime_account_id", lambda *_args: "account-1")

    result = execute._default_feedback_alignment_batch({"scorecards": identifiers})

    assert [row["scorecard_name"] for row in result["scorecards"]] == identifiers
    assert "error" not in result["scorecards"][0]
    assert "error" in result["scorecards"][1]
    assert "error" not in result["scorecards"][2]
    assert result["coverage"] == {
        "target_count": 3,
        "completed_count": 2,
        "failed_count": 1,
        "complete": False,
    }
