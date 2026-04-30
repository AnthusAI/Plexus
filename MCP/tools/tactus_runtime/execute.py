#!/usr/bin/env python3
"""Single-tool Tactus execution prototype for the Plexus MCP server."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import signal
import threading
import time
import traceback
import uuid
from typing import Annotated, Any, Callable

from fastmcp import Context, FastMCP
from pydantic import Field
from plexus.runtime_budget import RuntimeBudgetSpec

logger = logging.getLogger(__name__)


PLEXUS_DOCS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "plexus", "docs")
)

PLEXUS_TACTUS_TRACE_DIR_DEFAULT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "tmp", "tactus_traces")
)


def _resolve_trace_dir() -> str:
    return os.environ.get("PLEXUS_TACTUS_TRACE_DIR", PLEXUS_TACTUS_TRACE_DIR_DEFAULT)


class TactusTraceStore:
    """Pluggable persistence for execute_tactus run traces."""

    def write(self, record: dict[str, Any]) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class FileTactusTraceStore(TactusTraceStore):
    """Default trace store that writes one JSON file per run under ``directory``."""

    def __init__(self, directory: str) -> None:
        self._directory = directory

    @property
    def directory(self) -> str:
        return self._directory

    def write(self, record: dict[str, Any]) -> str:
        os.makedirs(self._directory, exist_ok=True)
        trace_id = record["trace_id"]
        path = os.path.join(self._directory, f"{trace_id}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True, default=str)
        return path


def _default_trace_store() -> TactusTraceStore:
    return FileTactusTraceStore(_resolve_trace_dir())


class TactusHandleStore:
    """Pluggable persistence for long-running execute_tactus handles."""

    def create(
        self,
        *,
        kind: str,
        parent_trace_id: str,
        api_call: str,
        args: dict[str, Any],
        dispatch_result: dict[str, Any],
        child_budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    def get(self, handle_id: str) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    def update(
        self, handle_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError


class FileTactusHandleStore(TactusHandleStore):
    """Default handle store backed by JSON files next to Tactus traces."""

    def __init__(self, directory: str) -> None:
        self._directory = directory

    def _path(self, handle_id: str) -> str:
        if (
            not handle_id
            or "/" in handle_id
            or "\\" in handle_id
            or handle_id.startswith(".")
        ):
            raise ValueError(f"Invalid execute_tactus handle id: {handle_id!r}")
        return os.path.join(self._directory, f"{handle_id}.json")

    def create(
        self,
        *,
        kind: str,
        parent_trace_id: str,
        api_call: str,
        args: dict[str, Any],
        dispatch_result: dict[str, Any],
        child_budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        os.makedirs(self._directory, exist_ok=True)
        handle_id = str(uuid.uuid4())
        created_at = _iso(time.time())
        dashboard_url = dispatch_result.get("dashboard_url") or dispatch_result.get(
            "status_url"
        )
        status = str(dispatch_result.get("status") or "running")
        if status == "dispatched":
            status = "running"
        record = {
            "id": handle_id,
            "kind": kind,
            "status": status,
            "status_url": dashboard_url,
            "created_at": created_at,
            "updated_at": created_at,
            "parent_trace_id": parent_trace_id,
            "api_call": api_call,
            "args": _jsonable(args),
            "dispatch_result": _jsonable(dispatch_result),
            "child_budget": _jsonable(child_budget),
        }
        with open(self._path(handle_id), "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True, default=str)
        return _public_handle(record)

    def get(self, handle_id: str) -> dict[str, Any]:
        path = self._path(handle_id)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Unknown execute_tactus handle: {handle_id}")
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def update(self, handle_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        record = self.get(handle_id)
        record.update(_jsonable(updates))
        record["updated_at"] = _iso(time.time())
        with open(self._path(handle_id), "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True, default=str)
        return record


def _default_handle_store() -> TactusHandleStore:
    return FileTactusHandleStore(os.path.join(_resolve_trace_dir(), "handles"))


def _build_trace_record(
    *,
    trace_id: str,
    envelope: dict[str, Any],
    submitted_tactus: str,
    wrapped_tactus: str | None,
    runtime_result: Any = None,
    started_at_wall: float,
    ended_at_wall: float,
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "started_at": _iso(started_at_wall),
        "ended_at": _iso(ended_at_wall),
        "duration_ms": int(round((ended_at_wall - started_at_wall) * 1000)),
        "ok": envelope.get("ok"),
        "value": envelope.get("value"),
        "error": envelope.get("error"),
        "cost": envelope.get("cost"),
        "partial": envelope.get("partial", False),
        "api_calls": envelope.get("api_calls", []),
        "submitted_tactus": submitted_tactus,
        "wrapped_tactus": wrapped_tactus,
        "tactus_runtime_result": (
            _jsonable(runtime_result) if runtime_result is not None else None
        ),
    }


def _iso(epoch_seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_seconds))


def _safe_write_trace(store: TactusTraceStore, record: dict[str, Any]) -> None:
    try:
        store.write(record)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to write Tactus trace %s: %s", record.get("trace_id"), exc
        )


HELPER_BINDINGS: tuple[tuple[str, str, str], ...] = (
    ("scorecards_list", "scorecards", "list"),
    ("scorecards_info", "scorecards", "info"),
    ("score_info", "score", "info"),
    ("score_evaluations", "score", "evaluations"),
    ("score_predict", "score", "predict"),
    ("score_set_champion", "score", "set_champion"),
    ("score_contradictions", "score", "contradictions"),
    ("set_champion", "score", "set_champion"),
    ("item_info", "item", "info"),
    ("item_last", "item", "last"),
    ("feedback_find", "feedback", "find"),
    ("feedback_alignment", "feedback", "alignment"),
    ("evaluation_info", "evaluation", "info"),
    ("evaluation_find_recent", "evaluation", "find_recent"),
    ("evaluation_compare", "evaluation", "compare"),
    ("evaluation_run", "evaluation", "run"),
    ("dataset_build_from_feedback_window", "dataset", "build_from_feedback_window"),
    ("dataset_check_associated", "dataset", "check_associated"),
    ("report_configurations_list", "report", "configurations_list"),
    ("report_run", "report", "run"),
    ("procedure_info", "procedure", "info"),
    ("procedure_list", "procedure", "list"),
    ("procedure_chat_sessions", "procedure", "chat_sessions"),
    ("procedure_chat_messages", "procedure", "chat_messages"),
    ("procedure_run", "procedure", "run"),
    ("procedure_optimize", "procedure", "optimize"),
    ("handle_peek", "handle", "peek"),
    ("handle_status", "handle", "status"),
    ("handle_await", "handle", "await"),
    ("handle_cancel", "handle", "cancel"),
    ("docs_list", "docs", "list"),
    ("docs_get", "docs", "get"),
    ("api_list", "api", "list"),
    ("scorecards", "scorecards", "list"),
    ("scorecard", "scorecards", "info"),
    ("evaluate", "evaluation", "run"),
    ("evaluation", "evaluation", "info"),
    ("recent_evaluations", "evaluation", "find_recent"),
    ("compare_evaluations", "evaluation", "compare"),
    ("predict", "score", "predict"),
    ("score", "score", "info"),
    ("last_item", "item", "last"),
    ("item", "item", "info"),
    ("feedback", "feedback", "find"),
    ("dataset", "dataset", "build_from_feedback_window"),
    ("dataset_association", "dataset", "check_associated"),
    ("report", "report", "run"),
    ("report_configs", "report", "configurations_list"),
    ("procedure", "procedure", "info"),
    ("procedures", "procedure", "list"),
    ("procedure_sessions", "procedure", "chat_sessions"),
    ("procedure_messages", "procedure", "chat_messages"),
)

# Long-running operations require handle/streaming semantics that the v0 prototype
# does not yet implement. See Kanbus epic plx-247588 (streaming + handle ergonomics)
# for the contract these will follow. Until that lands, these calls short-circuit
# with a structured `requires_handle_protocol` error rather than blocking the
# synchronous Tactus runtime for tens of minutes or hours.
LONG_RUNNING_METHODS: frozenset[tuple[str, str]] = frozenset({})


class RequiresHandleProtocol(RuntimeError):
    """Raised when a long-running Plexus runtime API is called in v0."""

    def __init__(self, namespace: str, method: str) -> None:
        super().__init__(
            f"plexus.{namespace}.{method} requires the long-running handle/streaming "
            "protocol (see Kanbus epic plx-247588) and is not enabled in this "
            "execute_tactus build."
        )
        self.namespace = namespace
        self.method = method


MCP_TOOL_MAP: dict[tuple[str, str], str] = {}


# Per-method handlers implemented directly on PlexusRuntimeModule (no MCP loopback).
# Each (namespace, method) here MUST NOT also appear in MCP_TOOL_MAP — every
# method has exactly one dispatcher.
DIRECT_HANDLERS: dict[tuple[str, str], str] = {
    ("scorecards", "list"): "_call_scorecards",
    ("scorecards", "info"): "_call_scorecards",
    ("score", "info"): "_call_score",
    ("score", "evaluations"): "_call_score",
    ("score", "predict"): "_call_score",
    ("score", "set_champion"): "_call_score",
    ("score", "contradictions"): "_call_score",
    ("item", "info"): "_call_item",
    ("item", "last"): "_call_item",
    ("feedback", "find"): "_call_feedback",
    ("feedback", "alignment"): "_call_feedback",
    ("evaluation", "info"): "_call_evaluation_read",
    ("evaluation", "find_recent"): "_call_evaluation_read",
    ("evaluation", "compare"): "_call_evaluation_read",
    ("evaluation", "run"): "_call_evaluation_run",
    ("report", "run"): "_call_report_run",
    ("report", "configurations_list"): "_call_report_read",
    ("dataset", "build_from_feedback_window"): "_call_dataset",
    ("dataset", "check_associated"): "_call_dataset",
    ("procedure", "list"): "_call_procedure_read",
    ("procedure", "info"): "_call_procedure_read",
    ("procedure", "chat_sessions"): "_call_procedure_read",
    ("procedure", "chat_messages"): "_call_procedure_read",
    ("procedure", "run"): "_call_procedure_run",
    ("procedure", "optimize"): "_call_procedure_run",
    ("handle", "peek"): "_call_handle",
    ("handle", "status"): "_call_handle",
    ("handle", "await"): "_call_handle",
    ("handle", "cancel"): "_call_handle",
}


def _default_scorecards_list(args: dict[str, Any]) -> Any:
    """Run plexus.scorecards.list directly against the dashboard.

    Equivalent to the legacy `plexus_scorecards_list` MCP tool but native
    Python so the runtime no longer depends on the legacy tool registration.
    """

    import json as _json

    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.memoized_resolvers import (
        memoized_resolve_scorecard_identifier,
    )
    from shared.utils import get_default_account_id

    identifier = args.get("identifier") or args.get("name") or args.get("key")
    next_token = args.get("next_token") or args.get("nextToken")
    return_metadata = bool(args.get("return_metadata", False))

    raw_limit = args.get("limit")
    if raw_limit is None:
        fetch_limit = 1000
    else:
        try:
            fetch_limit = int(raw_limit)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"plexus.scorecards.list limit must be an integer, got {raw_limit!r}"
            ) from exc
        if fetch_limit < 1:
            raise ValueError(
                "plexus.scorecards.list limit must be a positive integer"
            )

    client = create_client()
    if not client:
        raise RuntimeError("plexus.scorecards.list: could not create dashboard client")

    if identifier:
        scorecard_id = memoized_resolve_scorecard_identifier(client, str(identifier))
        if scorecard_id:
            query = (
                'query GetScorecard { '
                f'getScorecard(id: "{scorecard_id}") {{ '
                "id name key description externalId createdAt updatedAt "
                "} }"
            )
            response = client.execute(query)
            if "errors" in response:
                raise RuntimeError(
                    "plexus.scorecards.list dashboard error: "
                    + _json.dumps(response["errors"])
                )
            scorecard_data = response.get("getScorecard")
            items = [scorecard_data] if scorecard_data else []
            if return_metadata:
                return {"items": items, "nextToken": None}
            return items

    filter_parts: list[str] = []
    default_account_id = get_default_account_id()
    if default_account_id:
        filter_parts.append(f'accountId: {{ eq: "{default_account_id}" }}')
    if identifier:
        ident = str(identifier)
        if " " in ident or not ident.islower():
            filter_parts.append(f'name: {{ contains: "{ident}" }}')
        else:
            filter_parts.append(
                f'or: [{{name: {{ contains: "{ident}" }}}}, '
                f'{{key: {{ contains: "{ident}" }}}}]'
            )

    filter_str = ", ".join(filter_parts)
    next_token_arg = f', nextToken: "{next_token}"' if next_token else ""
    query = (
        "query ListScorecards { "
        f"listScorecards(filter: {{ {filter_str} }}, limit: {fetch_limit}{next_token_arg}) {{ "
        "items { id name key description externalId createdAt updatedAt } "
        "nextToken } }"
    )
    response = client.execute(query)
    if "errors" in response:
        raise RuntimeError(
            "plexus.scorecards.list dashboard error: "
            + _json.dumps(response["errors"])
        )

    list_scorecards = response.get("listScorecards") or {}
    items = list_scorecards.get("items") or []
    next_token_value = list_scorecards.get("nextToken")
    if return_metadata:
        return {"items": items, "nextToken": next_token_value}
    return items


def _default_scorecards_info(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.scorecards.info directly against the dashboard."""

    import json as _json

    from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
    from plexus.cli.shared.client_utils import create_client

    identifier = (
        args.get("identifier")
        or args.get("scorecard_identifier")
        or args.get("id")
        or args.get("name")
        or args.get("key")
        or args.get("external_id")
        or args.get("externalId")
    )
    if not identifier:
        raise ValueError(
            "plexus.scorecards.info requires identifier (id, name, key, or external_id)"
        )

    client = create_client()
    if not client:
        raise RuntimeError("plexus.scorecards.info: could not create dashboard client")

    scorecard_id = resolve_scorecard_identifier(client, str(identifier))
    if not scorecard_id:
        raise ValueError(
            f"plexus.scorecards.info: scorecard {identifier!r} not found"
        )

    query = (
        "query GetScorecard { "
        f'getScorecard(id: "{scorecard_id}") {{ '
        "id name key description guidelines externalId createdAt updatedAt "
        "sections { items { id name order scores { items { "
        "id name key description type order externalId } } } } "
        "} }"
    )
    response = client.execute(query)
    if "errors" in response:
        raise RuntimeError(
            "plexus.scorecards.info dashboard error: "
            + _json.dumps(response["errors"])
        )

    data = response.get("getScorecard")
    if not data:
        raise ValueError(
            f"plexus.scorecards.info: scorecard {identifier!r} (id {scorecard_id}) "
            "not found after query"
        )

    return {
        "name": data.get("name"),
        "key": data.get("key"),
        "externalId": data.get("externalId"),
        "description": data.get("description"),
        "guidelines": data.get("guidelines"),
        "additionalDetails": {
            "id": data.get("id"),
            "createdAt": data.get("createdAt"),
            "updatedAt": data.get("updatedAt"),
        },
        "sections": data.get("sections"),
    }


def _make_procedure_service():
    """Build a ProcedureService bound to a fresh dashboard client."""

    from plexus.cli.procedure.service import ProcedureService
    from plexus.cli.shared.client_utils import create_client

    client = create_client()
    if not client:
        raise RuntimeError(
            "plexus.procedure.*: could not create dashboard client"
        )
    return ProcedureService(client)


def _default_procedure_list(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.procedure.list directly via ProcedureService."""

    account_identifier = (
        args.get("account_identifier")
        or args.get("account")
        or os.environ.get("PLEXUS_ACCOUNT_KEY")
    )
    if not account_identifier:
        raise ValueError(
            "plexus.procedure.list requires account_identifier or "
            "PLEXUS_ACCOUNT_KEY environment variable"
        )

    scorecard_identifier = args.get("scorecard_identifier") or args.get("scorecard")
    limit = int(args.get("limit") or 20)

    service = _make_procedure_service()
    procedures = service.list_procedures(
        account_identifier=account_identifier,
        scorecard_identifier=scorecard_identifier,
        limit=limit,
    )
    return {
        "success": True,
        "count": len(procedures),
        "procedures": [
            {
                "id": exp.id,
                "name": getattr(exp, "name", None),
                "status": getattr(exp, "status", None),
                "featured": exp.featured,
                "created_at": exp.createdAt.isoformat(),
                "updated_at": exp.updatedAt.isoformat(),
                "scorecard_id": exp.scorecardId,
                "score_id": exp.scoreId,
            }
            for exp in procedures
        ],
    }


def _default_procedure_info(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.procedure.info directly via ProcedureService."""

    procedure_id = args.get("procedure_id") or args.get("id")
    if not procedure_id:
        raise ValueError("plexus.procedure.info requires id or procedure_id")
    include_yaml = bool(args.get("include_yaml", False))

    service = _make_procedure_service()
    info = service.get_procedure_info(str(procedure_id))
    if not info:
        return {
            "success": False,
            "error": f"Procedure {procedure_id} not found",
        }

    result: dict[str, Any] = {
        "success": True,
        "procedure": {
            "id": info.procedure.id,
            "status": getattr(info.procedure, "status", None),
            "featured": info.procedure.featured,
            "created_at": info.procedure.createdAt.isoformat(),
            "updated_at": info.procedure.updatedAt.isoformat(),
            "account_id": info.procedure.accountId,
            "scorecard_id": info.procedure.scorecardId,
            "score_id": info.procedure.scoreId,
        },
        "summary": {
            "scorecard_name": info.scorecard_name,
            "score_name": info.score_name,
        },
    }
    if include_yaml:
        yaml_config = service.get_procedure_yaml(str(procedure_id))
        if yaml_config:
            result["yaml_config"] = yaml_config
    return result


def _default_procedure_chat_sessions(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.procedure.chat_sessions directly via dashboard GraphQL."""

    from plexus.dashboard.api.client import PlexusDashboardClient

    procedure_id = args.get("procedure_id") or args.get("id")
    if not procedure_id:
        raise ValueError(
            "plexus.procedure.chat_sessions requires id or procedure_id"
        )
    limit = int(args.get("limit") or 10)

    client = PlexusDashboardClient()
    query = """
    query ListChatSessionByProcedureId($procedureId: String!, $limit: Int!) {
        listChatSessionByProcedureIdAndCreatedAt(
            procedureId: $procedureId
            sortDirection: DESC
            limit: $limit
        ) {
            items {
                id status procedureId createdAt updatedAt
                messages { items { id messageType } }
            }
        }
    }
    """
    result = client.execute(query, {"procedureId": str(procedure_id), "limit": limit})
    if "errors" in result:
        raise RuntimeError(
            f"plexus.procedure.chat_sessions GraphQL errors: {result['errors']}"
        )

    sessions: list = []
    if "data" in result:
        sessions = (
            result["data"]
            .get("listChatSessionByProcedureIdAndCreatedAt", {})
            .get("items", [])
        )
    elif "listChatSessionByProcedureIdAndCreatedAt" in result:
        sessions = result["listChatSessionByProcedureIdAndCreatedAt"].get("items", [])

    processed: list[dict[str, Any]] = []
    for session in sessions:
        messages = session.get("messages", {}).get("items", []) or []
        message_types: dict[str, int] = {}
        for msg in messages:
            mt = msg.get("messageType", "MESSAGE")
            message_types[mt] = message_types.get(mt, 0) + 1
        processed.append(
            {
                "id": session["id"],
                "status": session["status"],
                "created_at": session["createdAt"],
                "updated_at": session.get("updatedAt"),
                "message_count": len(messages),
                "message_types": message_types,
            }
        )

    return {
        "success": True,
        "procedure_id": str(procedure_id),
        "session_count": len(processed),
        "sessions": processed,
    }


def _default_procedure_chat_messages(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.procedure.chat_messages directly via dashboard GraphQL."""

    import json as _json

    from plexus.dashboard.api.client import PlexusDashboardClient

    procedure_id = args.get("procedure_id") or args.get("id")
    session_id = args.get("session_id")
    if not procedure_id and not session_id:
        raise ValueError(
            "plexus.procedure.chat_messages requires id (procedure_id) or session_id"
        )
    limit = int(args.get("limit") or 50)
    show_tool_calls = bool(args.get("show_tool_calls", True))
    show_tool_responses = bool(args.get("show_tool_responses", True))

    client = PlexusDashboardClient()
    if session_id:
        query = """
        query GetChatSession($id: ID!) {
            getChatSession(id: $id) {
                id status procedureId createdAt
                messages { items { id role messageType toolName content
                    toolResponse sequenceNumber parentMessageId createdAt } }
            }
        }
        """
        result = client.execute(query, {"id": str(session_id)})
        if "errors" in result:
            raise RuntimeError(
                f"plexus.procedure.chat_messages GraphQL errors: {result['errors']}"
            )
        session = None
        if "data" in result:
            session = result["data"].get("getChatSession")
        elif "getChatSession" in result:
            session = result["getChatSession"]
        if not session:
            return {
                "success": False,
                "error": f"Session {session_id} not found",
            }
        sessions = [session]
    else:
        query = """
        query ListChatSessionByProcedureId($procedureId: String!, $limit: Int!) {
            listChatSessionByProcedureIdAndCreatedAt(
                procedureId: $procedureId sortDirection: DESC limit: $limit
            ) {
                items {
                    id status procedureId createdAt
                    messages { items { id role messageType toolName content
                        toolResponse sequenceNumber parentMessageId createdAt } }
                }
            }
        }
        """
        result = client.execute(
            query, {"procedureId": str(procedure_id), "limit": limit}
        )
        if "errors" in result:
            raise RuntimeError(
                f"plexus.procedure.chat_messages GraphQL errors: {result['errors']}"
            )
        sessions = []
        if "data" in result:
            sessions = (
                result["data"]
                .get("listChatSessionByProcedureIdAndCreatedAt", {})
                .get("items", [])
            )
        elif "listChatSessionByProcedureIdAndCreatedAt" in result:
            sessions = result["listChatSessionByProcedureIdAndCreatedAt"].get(
                "items", []
            )

    processed_sessions: list[dict[str, Any]] = []
    total_messages = 0
    tool_calls = 0
    tool_responses = 0
    missing_responses = 0

    for session in sessions:
        messages = session.get("messages", {}).get("items", []) or []
        messages.sort(key=lambda m: m.get("sequenceNumber", 0))
        session_tool_calls: list[str] = []
        session_tool_responses: list[str] = []
        processed_messages: list[dict[str, Any]] = []

        for msg in messages[:limit]:
            msg_type = msg.get("messageType", "MESSAGE")
            role = msg.get("role", "")

            raw_content = msg.get("content", "") or ""
            parsed_content: Any = raw_content
            if isinstance(raw_content, str) and raw_content.startswith("{") and raw_content.endswith("}"):
                try:
                    parsed_content = _json.loads(raw_content)
                except (ValueError, TypeError):
                    parsed_content = raw_content

            processed_msg: dict[str, Any] = {
                "id": msg["id"],
                "sequence_number": msg.get("sequenceNumber", 0),
                "role": role,
                "message_type": msg_type,
                "content": parsed_content,
                "created_at": msg["createdAt"],
                "parent_message_id": msg.get("parentMessageId"),
            }
            is_tool_response = role == "SYSTEM" and msg.get("parentMessageId")

            if msg_type == "TOOL_CALL":
                processed_msg["tool_name"] = msg.get("toolName")
                session_tool_calls.append(msg["id"])
                tool_calls += 1
                tool_response_raw = msg.get("toolResponse") or ""
                if show_tool_responses and tool_response_raw:
                    tool_response_parsed: Any = tool_response_raw
                    if (
                        isinstance(tool_response_raw, str)
                        and tool_response_raw.startswith("{")
                        and tool_response_raw.endswith("}")
                    ):
                        try:
                            tool_response_parsed = _json.loads(tool_response_raw)
                        except (ValueError, TypeError):
                            tool_response_parsed = tool_response_raw
                    processed_msg["tool_response"] = tool_response_parsed
                    session_tool_responses.append(msg["id"])
                    tool_responses += 1
            elif (msg_type == "TOOL_RESPONSE" or is_tool_response) and show_tool_responses:
                processed_msg["tool_name"] = msg.get("toolName", "Unknown")
                session_tool_responses.append(msg["id"])
                tool_responses += 1

            if not show_tool_calls and msg_type == "TOOL_CALL":
                continue

            processed_messages.append(processed_msg)
            total_messages += 1

        session_missing = 0
        for call_id in session_tool_calls:
            call_msg = next((m for m in messages if m.get("id") == call_id), None)
            has_inline_response = bool(call_msg and (call_msg.get("toolResponse") or ""))
            has_child_response = any(
                resp_msg.get("parentMessageId") == call_id
                for resp_msg in messages
                if resp_msg.get("messageType") == "TOOL_RESPONSE"
                or (resp_msg.get("role") == "SYSTEM" and resp_msg.get("parentMessageId"))
            )
            if not (has_inline_response or has_child_response):
                session_missing += 1

        missing_responses += session_missing

        processed_sessions.append(
            {
                "session_id": session["id"],
                "status": session["status"],
                "created_at": session["createdAt"],
                "message_count": len(processed_messages),
                "tool_calls": len(session_tool_calls),
                "tool_responses": len(session_tool_responses),
                "missing_responses": session_missing,
                "messages": processed_messages,
            }
        )

    return {
        "success": True,
        "procedure_id": str(procedure_id),
        "session_count": len(processed_sessions),
        "total_messages": total_messages,
        "summary": {
            "tool_calls": tool_calls,
            "tool_responses": tool_responses,
            "missing_responses": missing_responses,
            "response_rate": (
                f"{((tool_responses / tool_calls) * 100):.1f}%"
                if tool_calls > 0
                else "N/A"
            ),
        },
        "sessions": processed_sessions,
    }


def _default_feedback_alignment(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.feedback.alignment directly via FeedbackService.

    Mirrors the legacy plexus_feedback_alignment MCP tool but native Python,
    using memoized resolvers for scorecard/score lookup.
    """

    from plexus.cli.feedback.feedback_service import FeedbackService
    from plexus.cli.report.utils import resolve_account_id_for_command
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.memoized_resolvers import (
        memoized_resolve_score_identifier,
        memoized_resolve_scorecard_identifier,
    )

    scorecard_name = args.get("scorecard_name") or args.get("scorecard")
    score_name = args.get("score_name") or args.get("score")
    if not scorecard_name or not score_name:
        raise ValueError(
            "plexus.feedback.alignment requires scorecard_name and score_name"
        )
    days = int(float(args.get("days", 7)))

    client = create_client()
    if not client:
        raise RuntimeError(
            "plexus.feedback.alignment: could not create dashboard client"
        )
    account_id = resolve_account_id_for_command(client, None)
    scorecard_id = memoized_resolve_scorecard_identifier(client, str(scorecard_name))
    if not scorecard_id:
        raise ValueError(
            f"plexus.feedback.alignment: scorecard {scorecard_name!r} not found"
        )
    score_id = memoized_resolve_score_identifier(
        client, scorecard_id, str(score_name)
    )
    if not score_id:
        raise ValueError(
            f"plexus.feedback.alignment: score {score_name!r} not found in "
            f"scorecard {scorecard_name!r}"
        )

    summary = _run_async_from_sync(
        FeedbackService.summarize_feedback(
            client=client,
            scorecard_name=str(scorecard_name),
            score_name=str(score_name),
            scorecard_id=scorecard_id,
            score_id=score_id,
            account_id=account_id,
            days=days,
        )
    )
    return FeedbackService.format_summary_result_as_dict(summary)


def _default_feedback_finder(args: dict[str, Any]) -> dict[str, Any]:
    """Run the production plexus.feedback.find chain.

    Lifted from MCP/tools/feedback/feedback.py so the Tactus host module no
    longer has to bounce back through FastMCP for this read-only call.
    """

    from plexus.cli.feedback.feedback_service import FeedbackService
    from plexus.cli.report.utils import resolve_account_id_for_command
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.memoized_resolvers import (
        memoized_resolve_score_identifier,
        memoized_resolve_scorecard_identifier,
    )

    scorecard_name = args.get("scorecard_name") or args.get("scorecard")
    score_name = args.get("score_name") or args.get("score")
    if not scorecard_name or not score_name:
        raise ValueError("plexus.feedback.find requires scorecard_name and score_name")

    days = int(args["days"]) if args.get("days") is not None else 7
    limit = int(args["limit"]) if args.get("limit") is not None else None
    offset = int(args["offset"]) if args.get("offset") is not None else None
    prioritize_edit_comments = bool(args.get("prioritize_edit_comments", True))

    client = create_client()
    account_id = resolve_account_id_for_command(client, None)
    scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard_name)
    score_id = memoized_resolve_score_identifier(client, scorecard_id, score_name)

    result = _run_async_from_sync(
        FeedbackService.search_feedback(
            client=client,
            scorecard_name=scorecard_name,
            score_name=score_name,
            scorecard_id=scorecard_id,
            score_id=score_id,
            account_id=account_id,
            days=days,
            initial_value=args.get("initial_value"),
            final_value=args.get("final_value"),
            limit=limit,
            offset=offset,
            prioritize_edit_comments=prioritize_edit_comments,
        )
    )
    return FeedbackService.format_search_result_as_dict(result)


def _default_evaluation_info(args: dict[str, Any]) -> dict[str, Any]:
    """Run the production plexus.evaluation.info chain directly.

    Bypasses MCP loopback by calling Evaluation.get_evaluation_info or
    Evaluation.get_latest_evaluation in plexus/Evaluation.py. Returns a
    structured dict; callers that need a JSON string should serialize it.

    include_examples is intentionally not implemented in this slice; that
    GraphQL example-loop logic lives in MCP/tools/evaluation/evaluations.py
    and will be lifted in a follow-up so it remains unit-testable.
    """

    from plexus.Evaluation import Evaluation

    raw_id = args.get("evaluation_id")
    evaluation_id = raw_id.strip() if isinstance(raw_id, str) else raw_id
    use_latest = bool(args.get("use_latest", False))

    if bool(evaluation_id) == use_latest:
        raise ValueError(
            "plexus.evaluation.info requires exactly one of evaluation_id or use_latest"
        )

    if args.get("include_examples"):
        raise ValueError(
            "plexus.evaluation.info include_examples is not yet supported in the "
            "Tactus runtime; use plexus.evaluation.info without include_examples or "
            "the MCP plexus_evaluation_info tool until the example-fetching helper "
            "is lifted out of MCP/tools/evaluation/evaluations.py."
        )

    include_score_results = bool(args.get("include_score_results", False))

    if use_latest:
        account_key = args.get("account_key") or os.environ.get("PLEXUS_ACCOUNT_KEY")
        if not account_key:
            raise ValueError(
                "plexus.evaluation.info use_latest requires account_key or "
                "PLEXUS_ACCOUNT_KEY environment variable"
            )
        evaluation_type = args.get("evaluation_type")
        if isinstance(evaluation_type, str):
            evaluation_type = evaluation_type.strip() or None
        return Evaluation.get_latest_evaluation(account_key, evaluation_type)

    return Evaluation.get_evaluation_info(evaluation_id, include_score_results)


def _default_score_info(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.score.info directly — mirrors plexus_score_info."""

    import os as _os

    from plexus.cli.report.utils import resolve_account_id_for_command
    from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
    from plexus.cli.shared.client_utils import create_client

    score_identifier = (
        args.get("score_identifier")
        or args.get("id")
        or args.get("score")
        or args.get("name")
        or args.get("key")
    )
    if not score_identifier:
        raise ValueError("plexus.score.info requires score_identifier (id/name/key)")

    scorecard_identifier = (
        args.get("scorecard_identifier")
        or args.get("scorecard")
        or args.get("scorecard_id")
    )
    version_id = args.get("version_id")

    plexus_url_base = _os.environ.get("PLEXUS_APP_URL", "https://capacity-plexus.anth.us").rstrip("/")

    def _plexus_url(path: str) -> str:
        return f"{plexus_url_base}/{path.lstrip('/')}"

    client = create_client()
    if not client:
        raise RuntimeError("plexus.score.info: could not create dashboard client")

    found_scores: list[dict] = []

    if scorecard_identifier:
        scorecard_id = resolve_scorecard_identifier(client, str(scorecard_identifier))
        if not scorecard_id:
            raise ValueError(
                f"plexus.score.info: scorecard {scorecard_identifier!r} not found"
            )
        result = client.execute(
            f"""query GetScorecardWithScores {{
                getScorecard(id: "{scorecard_id}") {{
                    id name key
                    sections {{ items {{ id name scores {{ items {{
                        id name key externalId description type
                        championVersionId isDisabled
                    }} }} }} }}
                }}
            }}"""
        )
        scorecard_data = result.get("getScorecard")
        if scorecard_data:
            for section in scorecard_data.get("sections", {}).get("items", []):
                for score in section.get("scores", {}).get("items", []):
                    sid = str(score_identifier).lower()
                    if (
                        score.get("id") == str(score_identifier)
                        or score.get("name", "").lower() == sid
                        or score.get("key") == str(score_identifier)
                        or score.get("externalId") == str(score_identifier)
                        or sid in score.get("name", "").lower()
                    ):
                        found_scores.append({"score": score, "section": section, "scorecard": scorecard_data})
    else:
        account_id = resolve_account_id_for_command(client, None)
        if not account_id:
            raise RuntimeError(
                "plexus.score.info: no default account — is PLEXUS_ACCOUNT_KEY set?"
            )
        result = client.execute(
            f"""query ListScorecardsForSearch {{
                listScorecards(filter: {{ accountId: {{ eq: "{account_id}" }} }}, limit: 100) {{
                    items {{
                        id name key
                        sections {{ items {{ id name scores {{ items {{
                            id name key externalId description type
                            championVersionId isDisabled
                        }} }} }} }}
                    }}
                }}
            }}"""
        )
        for scorecard in result.get("listScorecards", {}).get("items", []):
            for section in scorecard.get("sections", {}).get("items", []):
                for score in section.get("scores", {}).get("items", []):
                    sid = str(score_identifier).lower()
                    if (
                        score.get("id") == str(score_identifier)
                        or score.get("name", "").lower() == sid
                        or score.get("key") == str(score_identifier)
                        or score.get("externalId") == str(score_identifier)
                        or sid in score.get("name", "").lower()
                    ):
                        found_scores.append({"score": score, "section": section, "scorecard": scorecard})

    if not found_scores:
        scope = f" within scorecard {scorecard_identifier!r}" if scorecard_identifier else ""
        raise ValueError(
            f"plexus.score.info: no scores found matching {score_identifier!r}{scope}"
        )

    if len(found_scores) > 1:
        return {
            "found": True,
            "multiple": True,
            "count": len(found_scores),
            "matches": [
                {
                    "scoreId": m["score"]["id"],
                    "scoreName": m["score"]["name"],
                    "scorecardName": m["scorecard"]["name"],
                    "sectionName": m["section"]["name"],
                    "isDisabled": m["score"].get("isDisabled", False),
                    "dashboardUrl": _plexus_url(
                        f"lab/scorecards/{m['scorecard']['id']}/scores/{m['score']['id']}"
                    ),
                }
                for m in found_scores
            ],
            "message": (
                f"Found {len(found_scores)} scores matching {score_identifier!r}. "
                "Use a more specific identifier."
            ),
        }

    m = found_scores[0]
    score = m["score"]
    section = m["section"]
    scorecard = m["scorecard"]
    score_id = score["id"]
    scorecard_id = scorecard["id"]

    response: dict[str, Any] = {
        "found": True,
        "scoreId": score_id,
        "scoreName": score["name"],
        "scoreKey": score.get("key"),
        "externalId": score.get("externalId"),
        "type": score.get("type"),
        "championVersionId": score.get("championVersionId"),
        "isDisabled": score.get("isDisabled", False),
        "location": {
            "scorecardId": scorecard_id,
            "scorecardName": scorecard["name"],
            "sectionId": section["id"],
            "sectionName": section["name"],
        },
        "dashboardUrl": _plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score_id}"),
    }

    versions_result = client.execute(
        f"""query GetScoreVersions {{
            getScore(id: "{score_id}") {{
                id name key externalId championVersionId
                versions(sortDirection: DESC, limit: 20) {{
                    items {{ id createdAt isFeatured parentVersionId note metadata }}
                }}
            }}
        }}"""
    )
    if "errors" in versions_result:
        response["versions"] = []
        response["versionsError"] = str(versions_result["errors"])
    else:
        score_data = versions_result.get("getScore") or {}
        all_versions = score_data.get("versions", {}).get("items", []) or []
        response["versions"] = [
            {
                "id": v.get("id"),
                "createdAt": v.get("createdAt"),
                "note": v.get("note"),
                "isFeatured": v.get("isFeatured"),
                "parentVersionId": v.get("parentVersionId"),
                "isChampion": v.get("id") == score.get("championVersionId"),
                "metadata": v.get("metadata"),
            }
            for v in all_versions
        ]

    target_version_id = version_id or score.get("championVersionId")
    if target_version_id:
        ver_result = client.execute(
            f"""query GetScoreVersionForInfo {{
                getScoreVersion(id: "{target_version_id}") {{
                    id configuration guidelines createdAt updatedAt
                    note isFeatured parentVersionId metadata
                }}
            }}"""
        )
        version_data = ver_result.get("getScoreVersion") if "errors" not in ver_result else None
        if version_data:
            response["code"] = version_data.get("configuration")
            response["guidelines"] = version_data.get("guidelines")
            response["description"] = score.get("description")
            response["targetVersionId"] = target_version_id
            response["isChampionVersion"] = target_version_id == score.get("championVersionId")
            response["versionDetails"] = {
                "id": target_version_id,
                "createdAt": version_data.get("createdAt"),
                "updatedAt": version_data.get("updatedAt"),
                "note": version_data.get("note"),
                "isFeatured": version_data.get("isFeatured"),
                "parentVersionId": version_data.get("parentVersionId"),
                "metadata": version_data.get("metadata"),
                "isChampion": target_version_id == score.get("championVersionId"),
            }
            response["isSpecificVersion"] = bool(
                version_id and version_id != score.get("championVersionId")
            )
        else:
            response.update({"description": score.get("description"), "code": None,
                             "guidelines": None, "targetVersionId": None,
                             "isChampionVersion": False, "versionDetails": None})
    else:
        response.update({"description": score.get("description"), "code": None,
                         "guidelines": None, "targetVersionId": None,
                         "isChampionVersion": False, "versionDetails": None})

    return response


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _default_score_evaluations(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.score.evaluations directly via OptimizerResultsService.

    Accepts either:
      - { id = "<score-uuid>" }  — direct score ID, no scorecard lookup needed
      - { scorecard = "...", score = "..." }  — resolved via memoized resolvers
    """
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.optimizer_results import OptimizerResultsService

    version_id = args.get("version_id")
    sort_by = str(args.get("sort_by") or "updated")
    limit = int(args.get("limit") or 25)

    client = create_client()
    if not client:
        raise RuntimeError(
            "plexus.score.evaluations: could not create dashboard client"
        )

    # Fast path: direct UUID provided — no resolution needed.
    direct_id = args.get("id")
    if direct_id and _UUID_RE.match(str(direct_id)):
        score_id = str(direct_id)
    else:
        from plexus.cli.shared.memoized_resolvers import (
            memoized_resolve_score_identifier,
            memoized_resolve_scorecard_identifier,
        )

        scorecard_identifier = args.get("scorecard_identifier") or args.get("scorecard")
        score_identifier = (
            args.get("score_identifier") or args.get("score") or direct_id
        )
        if not scorecard_identifier or not score_identifier:
            raise ValueError(
                "plexus.score.evaluations requires either { id = '<score-uuid>' } "
                "or { scorecard = '...', score = '...' }"
            )

        scorecard_id = memoized_resolve_scorecard_identifier(client, str(scorecard_identifier))
        if not scorecard_id:
            raise ValueError(
                f"plexus.score.evaluations: scorecard {scorecard_identifier!r} not found"
            )
        score_id = memoized_resolve_score_identifier(client, scorecard_id, str(score_identifier))
        if not score_id:
            raise ValueError(
                f"plexus.score.evaluations: score {score_identifier!r} not found"
            )

    service = OptimizerResultsService(client)
    evaluations = service.list_score_evaluations(
        score_id, version_id=version_id, sort_by=sort_by, limit=limit
    )
    return {"success": True, "score_id": score_id, "evaluations": evaluations}


def _default_score_predict(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.score.predict directly — mirrors plexus_predict."""

    import asyncio
    import json as _json
    import traceback as _traceback
    from decimal import Decimal

    from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
    from plexus.cli.shared.client_utils import create_client
    from plexus.dashboard.api.models.item import Item as PlexusItem
    from plexus.scores.Score import Score

    def _sanitize_dec(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, dict):
            return {k: _sanitize_dec(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_sanitize_dec(v) for v in obj]
        return obj

    scorecard_name = args.get("scorecard_name") or args.get("scorecard")
    score_name = args.get("score_name") or args.get("score")
    if not scorecard_name or not score_name:
        raise ValueError("plexus.score.predict requires scorecard_name and score_name")

    item_id = args.get("item_id") or args.get("id") or args.get("item")
    item_ids_raw = args.get("item_ids")
    include_input = bool(args.get("include_input", False))
    include_trace = bool(args.get("include_trace", False))
    no_cache = bool(args.get("no_cache", False))
    yaml_mode = bool(args.get("yaml", False))
    version = args.get("version") or args.get("version_id")
    latest = bool(args.get("latest", False))
    yaml_path = args.get("yaml_path")

    if not item_id and not item_ids_raw:
        raise ValueError("plexus.score.predict requires item_id or item_ids")
    if item_id and item_ids_raw:
        raise ValueError("plexus.score.predict: specify item_id or item_ids, not both")

    client = create_client()
    if not client:
        raise RuntimeError("plexus.score.predict: could not create dashboard client")

    if yaml_mode:
        scorecard_id = "yaml-mode-scorecard"
        resolved_score: dict[str, Any] = {"id": "yaml-mode-score", "name": str(score_name),
                                           "key": str(score_name).lower().replace(" ", "-"),
                                           "championVersionId": "yaml-mode-version"}
    else:
        scorecard_id_resolved = resolve_scorecard_identifier(client, str(scorecard_name))
        if not scorecard_id_resolved:
            raise ValueError(
                f"plexus.score.predict: scorecard {scorecard_name!r} not found"
            )
        scorecard_id = scorecard_id_resolved
        sc_result = client.execute(
            f"""query GetScorecardForPrediction {{
                getScorecard(id: "{scorecard_id}") {{
                    id name
                    sections {{ items {{ id scores {{ items {{
                        id name key externalId championVersionId isDisabled
                    }} }} }} }}
                }}
            }}"""
        )
        scorecard_data = sc_result.get("getScorecard")
        if not scorecard_data:
            raise ValueError(
                f"plexus.score.predict: could not load scorecard {scorecard_name!r}"
            )

        try:
            from plexus.cli.shared.identifier_resolution import (
                resolve_score_identifier as _rsi,
            )
            resolved_score_id = _rsi(client, scorecard_id, str(score_name))
        except Exception:
            resolved_score_id = None

        resolved_score = None
        for section in scorecard_data.get("sections", {}).get("items", []):
            for sc in section.get("scores", {}).get("items", []):
                if (
                    (resolved_score_id and sc.get("id") == resolved_score_id)
                    or sc.get("id") == str(score_name)
                    or sc.get("externalId") == str(score_name)
                    or sc.get("key") == str(score_name)
                    or sc.get("name") == str(score_name)
                ):
                    resolved_score = sc
                    break
            if resolved_score:
                break
        if not resolved_score:
            raise ValueError(
                f"plexus.score.predict: score {score_name!r} not found in "
                f"scorecard {scorecard_name!r}"
            )

    resolved_version = version if not latest else None
    if latest and not yaml_mode:
        try:
            from plexus.cli.evaluation.evaluations import get_latest_score_version
            v = get_latest_score_version(client, resolved_score["id"])
            if v:
                resolved_version = v
        except Exception:
            pass

    if item_id:
        target_item_ids: list[str] = [str(item_id)]
    else:
        target_item_ids = [x.strip() for x in str(item_ids_raw).split(",")]

    if not yaml_mode:
        try:
            import os as _os
            from plexus.cli.shared.identifier_resolution import (
                resolve_item_identifier as _rii,
            )
            from plexus.dashboard.api.models.account import Account as _Account
            account_id = None
            try:
                ak = _os.getenv("PLEXUS_ACCOUNT_KEY")
                if ak:
                    acc = _Account.list_by_key(key=ak, client=client)
                    if acc:
                        account_id = acc.id
            except Exception:
                pass
            resolved_ids = []
            for raw_id in target_item_ids:
                try:
                    r = _rii(client, raw_id, account_id)
                except Exception:
                    r = None
                resolved_ids.append(r or raw_id)
            target_item_ids = resolved_ids
        except Exception:
            pass

    if yaml_mode and yaml_path:
        import yaml as _yaml
        from plexus.scores.Scorecard import Scorecard
        with open(yaml_path, "r") as f:
            sc_cfg = _yaml.safe_load(f.read())
        scorecard_instance = Scorecard({"name": scorecard_name, "sections": [{"name": "Custom", "scores": [sc_cfg]}]})
        scorecard_instance.yaml_only = True
    elif yaml_mode:
        from plexus.cli.evaluation.evaluations import load_scorecard_from_yaml_files
        scorecard_instance = load_scorecard_from_yaml_files(str(scorecard_name), score_names=[str(score_name)])
        scorecard_instance.yaml_only = True
    else:
        from plexus.cli.evaluation.evaluations import load_scorecard_from_api
        scorecard_instance = load_scorecard_from_api(
            str(scorecard_name), score_names=[str(score_name)],
            use_cache=not no_cache, specific_version=resolved_version
        )

    resolved_score_name = str(score_name)
    if hasattr(scorecard_instance, "scores") and isinstance(scorecard_instance.scores, list):
        for s in scorecard_instance.scores:
            sn = s.get("name")
            if sn and (
                sn == str(score_name) or str(s.get("id", "")) == str(score_name)
                or str(s.get("key", "")) == str(score_name)
                or str(s.get("externalId", "")) == str(score_name)
            ):
                resolved_score_name = sn
                break

    try:
        _, name_to_id = scorecard_instance.build_dependency_graph([resolved_score_name])
    except Exception:
        name_to_id = {}

    item_query_fields = """id text description metadata attachedFiles externalId createdAt updatedAt"""

    async def _predict_one(target_id: str) -> dict:
        try:
            item_result = client.execute(
                f'query GetItem {{ getItem(id: "{target_id}") {{ {item_query_fields} }} }}'
            )
            item_data = item_result.get("getItem")
            if not item_data:
                return {"item_id": target_id, "error": f"Item {target_id!r} not found"}

            item_text = item_data.get("text", "") or item_data.get("description", "")
            if not item_text:
                return {"item_id": target_id, "error": "No text content found in item"}

            meta_raw = item_data.get("metadata", {})
            item_metadata: dict = {}
            if isinstance(meta_raw, dict):
                item_metadata = meta_raw
            else:
                try:
                    item_metadata = _json.loads(meta_raw)
                except Exception:
                    pass

            try:
                item_obj = PlexusItem.from_dict(item_data, client)
            except Exception:
                item_obj = None

            try:
                results = await scorecard_instance.score_entire_text(
                    text=item_text, metadata=item_metadata, modality=None,
                    subset_of_score_names=[resolved_score_name], item=item_obj
                )
                target_result_id = name_to_id.get(resolved_score_name)
                score_result_obj = None
                if results:
                    if target_result_id and target_result_id in results:
                        score_result_obj = results[target_result_id]
                    elif resolved_score_name in results:
                        score_result_obj = results[resolved_score_name]

                if score_result_obj is None:
                    if results and any(isinstance(v, Score.Result) and v.value == "SKIPPED" for v in results.values()):
                        return {"item_id": target_id, "scores": [{"name": score_name, "value": None,
                                "explanation": "Not applicable — unmet dependency conditions", "cost": {}}]}
                    return {"item_id": target_id, "error": f"No result for score {resolved_score_name!r}"}

                explanation = (
                    getattr(score_result_obj, "explanation", None)
                    or (score_result_obj.metadata.get("explanation", "") if hasattr(score_result_obj, "metadata") and score_result_obj.metadata else "")
                )
                costs = {}
                if hasattr(score_result_obj, "cost"):
                    costs = score_result_obj.cost
                elif hasattr(score_result_obj, "metadata") and score_result_obj.metadata:
                    costs = score_result_obj.metadata.get("cost", {})

                prediction_result: dict = {"item_id": target_id, "scores": [{
                    "name": score_name, "value": score_result_obj.value,
                    "explanation": explanation, "cost": costs
                }]}
                if include_trace:
                    trace = getattr(score_result_obj, "trace", None) or (
                        score_result_obj.metadata.get("trace") if hasattr(score_result_obj, "metadata") and score_result_obj.metadata else None
                    )
                    prediction_result["scores"][0]["trace"] = trace
            except Exception as exc:
                prediction_result = {"item_id": target_id, "scores": [{
                    "name": score_name, "value": "ERROR",
                    "explanation": f"Prediction failed: {exc}",
                    "error_details": {"error_message": str(exc), "error_type": type(exc).__name__,
                                      "traceback": _traceback.format_exc()},
                    "cost": {}
                }]}

            if include_input:
                prediction_result["input"] = {"description": item_data.get("description"),
                                               "metadata": item_data.get("metadata"),
                                               "attachedFiles": item_data.get("attachedFiles"),
                                               "externalId": item_data.get("externalId")}
            return prediction_result
        except Exception as e:
            return {"item_id": target_id, "error": str(e)}

    async def _gather_all() -> list:
        return list(await asyncio.gather(*[_predict_one(tid) for tid in target_item_ids]))

    prediction_results_list = _run_async_from_sync(_gather_all())
    return _sanitize_dec({
        "success": True,
        "scorecard_name": scorecard_name,
        "score_name": score_name,
        "scorecard_id": scorecard_id,
        "score_id": resolved_score["id"],
        "item_count": len(target_item_ids),
        "predictions": prediction_results_list,
    })


def _default_score_set_champion(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.score.set_champion directly — mirrors plexus_score_set_champion."""

    import uuid as _uuid
    from datetime import datetime, timezone

    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.optimizer_shadow_invalidation import (
        extract_shadow_invalid_feedback_item_ids_from_yaml_text,
    )

    score_id = args.get("score_id") or args.get("id")
    version_id = args.get("version_id") or args.get("version")
    if not score_id or not version_id:
        raise ValueError(
            "plexus.score.set_champion requires score_id and version_id"
        )

    client = create_client()
    if not client:
        raise RuntimeError(
            "plexus.score.set_champion: could not create dashboard client"
        )

    check_result = client.execute(
        """
        query GetScoreVersionForChampionGuard($scoreId: ID!, $versionId: ID!) {
            getScore(id: $scoreId) { id championVersionId }
            getScoreVersion(id: $versionId) { id scoreId configuration metadata }
        }
        """,
        {"scoreId": str(score_id), "versionId": str(version_id)},
    )
    score_data = check_result.get("getScore") or {}
    version_data = check_result.get("getScoreVersion") or {}

    shadow_ids = extract_shadow_invalid_feedback_item_ids_from_yaml_text(
        version_data.get("configuration") or ""
    )
    if shadow_ids:
        return {
            "success": False,
            "error": "SHADOW_INVALIDATION_PRESENT",
            "message": (
                "Cannot promote: version still contains "
                "optimizer_shadow_invalid_feedback_item_ids. "
                "Remove that field in a cleanup version first."
            ),
            "scoreId": str(score_id),
            "versionId": str(version_id),
            "optimizer_shadow_invalid_feedback_item_ids": shadow_ids,
        }
    if version_data.get("scoreId") != str(score_id):
        return {
            "success": False,
            "error": "VERSION_SCORE_MISMATCH",
            "message": (
                f"Version {version_id} belongs to score "
                f"{version_data.get('scoreId')}, not {score_id}."
            ),
            "scoreId": str(score_id),
            "versionId": str(version_id),
        }

    previous_champion_version_id = score_data.get("championVersionId")
    previous_version_meta: dict[str, Any] = {}
    if previous_champion_version_id and previous_champion_version_id != str(version_id):
        prev_result = client.execute(
            """
            query GetScoreVersionForManagement($id: ID!) {
              getScoreVersion(id: $id) { id scoreId configuration guidelines isFeatured
                note branch parentVersionId metadata createdAt updatedAt }
            }
            """,
            {"id": previous_champion_version_id},
        )
        previous_version_meta = prev_result.get("getScoreVersion") or {}

    promo_result = client.execute(
        "mutation UpdateScore($input: UpdateScoreInput!) { "
        "updateScore(input: $input) { id championVersionId } }",
        {"input": {"id": str(score_id), "championVersionId": str(version_id)}},
    )
    if not promo_result or "updateScore" not in promo_result:
        raise RuntimeError(
            f"plexus.score.set_champion: mutation failed: {promo_result}"
        )

    updated = promo_result["updateScore"]
    promoted_at = datetime.now(timezone.utc).isoformat()
    transition_id = str(_uuid.uuid4())

    def _build_meta(
        metadata: Any,
        *,
        score_id: str,
        version_id: str,
        transition_id: str,
        incoming: bool,
        entered_at: str | None = None,
        exited_at: str | None = None,
        previous_champion_version_id: str | None = None,
        next_champion_version_id: str | None = None,
    ) -> dict:
        next_meta: dict = dict(metadata or {})
        history: list = list(next_meta.get("championHistory") or [])
        if incoming:
            history.append({
                "scoreId": score_id, "versionId": version_id,
                "enteredAt": entered_at, "exitedAt": None,
                "previousChampionVersionId": previous_champion_version_id,
                "nextChampionVersionId": None, "transitionId": transition_id,
            })
        else:
            open_idx = next((i for i in range(len(history) - 1, -1, -1)
                             if not history[i].get("exitedAt")), None)
            if open_idx is None:
                history.append({
                    "scoreId": score_id, "versionId": version_id,
                    "enteredAt": None, "exitedAt": exited_at,
                    "previousChampionVersionId": None,
                    "nextChampionVersionId": next_champion_version_id,
                    "transitionId": transition_id, "inferred": True,
                })
            else:
                history[open_idx] = {
                    **history[open_idx],
                    "exitedAt": exited_at,
                    "nextChampionVersionId": next_champion_version_id,
                    "transitionId": transition_id,
                }
        next_meta["championHistory"] = history
        return next_meta

    update_version_mutation = (
        "mutation UpdateScoreVersionMetadata($input: UpdateScoreVersionInput!) { "
        "updateScoreVersion(input: $input) { id isFeatured metadata } }"
    )
    incoming_meta = _build_meta(
        version_data.get("metadata"),
        score_id=str(score_id), version_id=str(version_id),
        transition_id=transition_id, incoming=True, entered_at=promoted_at,
        previous_champion_version_id=(
            previous_champion_version_id
            if previous_champion_version_id != str(version_id) else None
        ),
    )
    client.execute(update_version_mutation, {"input": {
        "id": str(version_id), "metadata": incoming_meta, "isFeatured": "true"
    }})
    if previous_champion_version_id and previous_champion_version_id != str(version_id):
        outgoing_meta = _build_meta(
            previous_version_meta.get("metadata"),
            score_id=str(score_id), version_id=previous_champion_version_id,
            transition_id=transition_id, incoming=False, exited_at=promoted_at,
            next_champion_version_id=str(version_id),
        )
        client.execute(update_version_mutation, {"input": {
            "id": previous_champion_version_id, "metadata": outgoing_meta
        }})

    return {
        "success": True,
        "scoreId": updated["id"],
        "championVersionId": updated["championVersionId"],
        "previousChampionVersionId": previous_champion_version_id,
        "transitionId": transition_id,
        "promotedAt": promoted_at,
    }


def _default_score_contradictions(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.score.contradictions — checks ScoreVersion code vs. rubric for consistency.

    Required args:
        scorecard (str): Scorecard name, key, or ID.
        score (str): Score name, key, or ID.
        version (str): ScoreVersion UUID to check.

    Optional args:
        item_id (str): Item UUID whose transcript text is included as spot-check context.
        output_format (str): 'json' (default) or 'markdown'.

    Returns dict with keys: status ('consistent'|'potential_conflict'|'inconclusive'),
    paragraph, scorecard_identifier, score_identifier, score_version_id,
    checked_at, model, diagnostics.
    """

    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.score.scores import (
        memoized_resolve_scorecard_identifier,
        memoized_resolve_score_identifier,
    )
    from plexus.score_rubric_consistency import ScoreRubricConsistencyService

    scorecard_identifier = args.get("scorecard") or args.get("scorecard_identifier") or args.get("scorecard_name")
    score_identifier = args.get("score") or args.get("score_identifier") or args.get("score_name")
    score_version_id = args.get("version") or args.get("version_id") or args.get("score_version_id")

    if not scorecard_identifier:
        raise ValueError("plexus.score.contradictions requires 'scorecard'")
    if not score_identifier:
        raise ValueError("plexus.score.contradictions requires 'score'")
    if not score_version_id:
        raise ValueError("plexus.score.contradictions requires 'version' (ScoreVersion UUID)")

    client = create_client()
    if not client:
        raise RuntimeError("plexus.score.contradictions: could not create dashboard client")

    scorecard_id = memoized_resolve_scorecard_identifier(client, str(scorecard_identifier))
    if not scorecard_id:
        raise ValueError(f"Could not resolve scorecard: {scorecard_identifier}")
    score_id = memoized_resolve_score_identifier(client, scorecard_id, str(score_identifier))
    if not score_id:
        raise ValueError(f"Could not resolve score '{score_identifier}' in scorecard '{scorecard_identifier}'")

    item_text = ""
    item_id = args.get("item_id") or args.get("item")
    if item_id:
        from MCP.tools.tactus_runtime._item_helpers import _get_identifiers_for_item
        from plexus.cli.shared.client_utils import create_client as _cc

        _client2 = _cc()
        try:
            item_data = _get_identifiers_for_item(_client2, str(item_id))
            item_text = item_data.get("text") or ""
        except Exception:
            pass

    result = ScoreRubricConsistencyService().generate_from_api(
        client=client,
        scorecard_identifier=str(scorecard_identifier),
        score_identifier=str(score_identifier),
        score_id=str(score_id),
        score_version_id=str(score_version_id),
        item_text=item_text,
    )
    return result.to_parameters_payload()


def _default_item_last(args: dict[str, Any]) -> Any:
    """Run plexus.item.last directly using Item dashboard API."""

    import asyncio

    from plexus.cli.report.utils import resolve_account_id_for_command
    from plexus.cli.shared.client_utils import create_client
    from plexus.dashboard.api.models.item import Item
    from MCP.tools.tactus_runtime._item_helpers import (
        _get_feedback_items_for_item,
        _get_identifiers_for_item,
        _get_score_results_for_item,
        _get_item_url,
    )

    minimal = bool(args.get("minimal", False))
    count = min(max(1, int(args.get("count", 1))), 20)

    client = create_client()
    if not client:
        raise RuntimeError("plexus.item.last: could not create dashboard client")

    account_id = resolve_account_id_for_command(client, None)
    if not account_id:
        raise RuntimeError(
            "plexus.item.last: could not resolve account ID — is PLEXUS_ACCOUNT_KEY set?"
        )

    query = f"""
    query ListItemByAccountIdAndCreatedAt($accountId: String!, $limit: Int!) {{
        listItemByAccountIdAndCreatedAt(
            accountId: $accountId, sortDirection: DESC, limit: $limit
        ) {{
            items {{ {Item.fields()} }}
        }}
    }}
    """
    response = client.execute(query, {"accountId": account_id, "limit": count})
    if "errors" in response:
        raise RuntimeError(
            f"plexus.item.last dashboard error: {response['errors']}"
        )

    items = (
        response.get("listItemByAccountIdAndCreatedAt") or {}
    ).get("items") or []

    if not items:
        return {"items": [], "count": 0}

    async def _build(item_data: dict) -> dict:
        item = Item.from_dict(item_data, client)
        d: dict = {
            "id": item.id,
            "accountId": item.accountId,
            "evaluationId": item.evaluationId,
            "scoreId": item.scoreId,
            "description": item.description,
            "externalId": item.externalId,
            "isEvaluation": item.isEvaluation,
            "createdByType": item.createdByType,
            "metadata": item.metadata,
            "identifiers": await _get_identifiers_for_item(item.id, client) or item.identifiers,
            "attachedFiles": item.attachedFiles,
            "createdAt": item.createdAt.isoformat() if item.createdAt else None,
            "updatedAt": item.updatedAt.isoformat() if item.updatedAt else None,
            "url": _get_item_url(item.id),
        }
        if not minimal:
            d["scoreResults"] = await _get_score_results_for_item(item.id, client)
            d["feedbackItems"] = await _get_feedback_items_for_item(item.id, client)
        return d

    async def _build_all() -> list:
        return [await _build(item_data) for item_data in items]

    built = _run_async_from_sync(_build_all())
    if count == 1:
        return built[0]
    return {"items": built, "count": len(built)}


def _default_item_info(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.item.info directly using Item dashboard API."""

    from datetime import datetime

    from plexus.cli.shared.client_utils import create_client
    from plexus.dashboard.api.models.item import Item
    from plexus.utils.identifier_search import find_item_by_identifier
    from MCP.tools.tactus_runtime._item_helpers import (
        _get_feedback_items_for_item,
        _get_identifiers_for_item,
        _get_score_results_for_item,
        _get_item_url,
        _get_default_account_id,
    )

    item_id = (
        args.get("item_id")
        or args.get("id")
        or args.get("item")
    )
    if not item_id:
        raise ValueError("plexus.item.info requires id or item_id")
    minimal = bool(args.get("minimal", False))

    client = create_client()
    if not client:
        raise RuntimeError("plexus.item.info: could not create dashboard client")

    item = None
    lookup_method = "unknown"

    try:
        item = Item.get_by_id(str(item_id), client)
        if item:
            lookup_method = "direct_id"
    except ValueError:
        pass
    except Exception:
        pass

    if not item:
        default_account_id = _get_default_account_id()
        if default_account_id:
            try:
                item = find_item_by_identifier(str(item_id), default_account_id, client)
                if item:
                    lookup_method = "identifier_search"
            except Exception:
                pass

    if not item:
        default_account_id = _get_default_account_id()
        if default_account_id:
            try:
                gsi_query = """
                query GetIdentifierByAccountAndValue($accountId: String!, $value: String!) {
                    listIdentifierByAccountIdAndValue(
                        accountId: $accountId, value: {eq: $value}, limit: 1
                    ) {
                        items {
                            itemId name value url position
                            item {
                                id accountId evaluationId scoreId description
                                externalId isEvaluation text metadata identifiers
                                attachedFiles createdAt updatedAt
                            }
                        }
                    }
                }
                """
                result = client.execute(gsi_query, {"accountId": default_account_id, "value": str(item_id)})
                identifiers = (
                    result.get("listIdentifierByAccountIdAndValue") or {}
                ).get("items") or []
                if identifiers:
                    ident_data = identifiers[0]
                    item_data = ident_data.get("item") or {}
                    if item_data:
                        class _MockItem:
                            def __init__(self, data: dict) -> None:
                                for k, v in data.items():
                                    setattr(self, k, v)
                                for ts_field in ("createdAt", "updatedAt"):
                                    raw = getattr(self, ts_field, None)
                                    if raw and isinstance(raw, str):
                                        try:
                                            setattr(self, ts_field, datetime.fromisoformat(raw.replace("Z", "+00:00")))
                                        except Exception:
                                            pass
                        item = _MockItem(item_data)
                        lookup_method = f"identifiers_table_gsi (name: {ident_data.get('name', 'N/A')})"
            except Exception:
                pass

    if not item:
        raise ValueError(
            f"plexus.item.info: item {item_id!r} not found "
            "(tried direct ID, identifier search, identifiers table GSI)"
        )

    def _trunc(value: Any, max_chars: int = 5000) -> Any:
        if isinstance(value, str) and len(value) > max_chars:
            return f"{value[:max_chars]}... (truncated from {len(value):,} to {max_chars:,} chars)"
        return value

    item_dict: dict = {
        "id": item.id,
        "accountId": item.accountId,
        "evaluationId": item.evaluationId,
        "scoreId": item.scoreId,
        "description": _trunc(item.description, 1000),
        "externalId": item.externalId,
        "isEvaluation": item.isEvaluation,
        "createdByType": getattr(item, "createdByType", None),
        "text": _trunc(getattr(item, "text", None), 5000),
        "metadata": item.metadata,
        "identifiers": _run_async_from_sync(
            _get_identifiers_for_item(item.id, client)
        ) or item.identifiers,
        "attachedFiles": item.attachedFiles,
        "createdAt": (
            item.createdAt.isoformat()
            if hasattr(item.createdAt, "isoformat")
            else item.createdAt
        ),
        "updatedAt": (
            item.updatedAt.isoformat()
            if hasattr(item.updatedAt, "isoformat")
            else item.updatedAt
        ),
        "url": _get_item_url(item.id),
        "lookupMethod": lookup_method,
    }

    if not minimal:
        item_dict["scoreResults"] = _run_async_from_sync(
            _get_score_results_for_item(item.id, client)
        )
        item_dict["feedbackItems"] = _run_async_from_sync(
            _get_feedback_items_for_item(item.id, client)
        )

    return item_dict


def _default_dataset_build_from_feedback_window(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.dataset.build_from_feedback_window directly via curation."""

    from plexus.cli.dataset.curation import (
        build_associated_dataset_from_feedback_window,
    )
    from plexus.cli.dataset.datasets import create_client
    from plexus.cli.evaluation.evaluations import validate_dataset_materialization
    from plexus.cli.shared.identifier_resolution import (
        resolve_score_identifier,
        resolve_scorecard_identifier,
    )

    scorecard = args.get("scorecard") or args.get("scorecard_identifier")
    score = args.get("score") or args.get("score_identifier")
    if not scorecard or not score:
        raise ValueError(
            "plexus.dataset.build_from_feedback_window requires scorecard and score"
        )

    max_items = int(args.get("max_items", 100))
    days = args.get("days")
    balance = bool(args.get("balance", True))
    score_version_id = args.get("score_version_id")

    client = create_client()
    scorecard_id = resolve_scorecard_identifier(client, str(scorecard))
    if not scorecard_id:
        raise ValueError(
            f"plexus.dataset.build_from_feedback_window: scorecard {scorecard!r} not found"
        )
    score_id = resolve_score_identifier(client, scorecard_id, str(score))
    if not score_id:
        raise ValueError(
            f"plexus.dataset.build_from_feedback_window: score {score!r} not found"
        )

    result = build_associated_dataset_from_feedback_window(
        client=client,
        scorecard_id=scorecard_id,
        score_id=score_id,
        max_items=max_items,
        days=days,
        balance=balance,
        class_source_score_version_id=score_version_id or None,
    )
    dataset_id = result.get("dataset_id")
    dataset_file = result.get("dataset_file") or result.get("s3_key")
    readiness = validate_dataset_materialization(
        {"id": dataset_id, "file": dataset_file}
    )
    if not readiness.get("is_materialized"):
        reason = readiness.get("materialization_error") or "unknown"
        raise RuntimeError(
            "plexus.dataset.build_from_feedback_window completed without a "
            f"materialized file pointer. dataset_id={dataset_id} reason={reason}"
        )

    result["dataset_file"] = dataset_file
    result["is_materialized"] = True
    result["materialization_error"] = None
    return result


def _default_dataset_check_associated(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.dataset.check_associated directly."""

    from plexus.cli.dataset.datasets import create_client
    from plexus.cli.evaluation.evaluations import (
        list_associated_datasets_for_score,
        validate_dataset_materialization,
    )
    from plexus.cli.shared.identifier_resolution import (
        resolve_score_identifier,
        resolve_scorecard_identifier,
    )
    from plexus.cli.shared.optimizer_shadow_invalidation import (
        resolve_score_version_shadow_invalidation_metadata,
    )

    scorecard = args.get("scorecard") or args.get("scorecard_identifier")
    score = args.get("score") or args.get("score_identifier")
    if not scorecard or not score:
        raise ValueError(
            "plexus.dataset.check_associated requires scorecard and score"
        )
    score_version_id = args.get("score_version_id")
    days = args.get("days")

    client = create_client()
    scorecard_id = resolve_scorecard_identifier(client, str(scorecard))
    if not scorecard_id:
        raise ValueError(
            f"plexus.dataset.check_associated: scorecard {scorecard!r} not found"
        )
    score_id = resolve_score_identifier(client, scorecard_id, str(score))
    if not score_id:
        raise ValueError(
            f"plexus.dataset.check_associated: score {score!r} not found"
        )

    expected_feedback_target_hash: str | None = None
    if score_version_id is not None or days is not None:
        target_metadata = resolve_score_version_shadow_invalidation_metadata(
            client,
            score_id=score_id,
            score_version_id=score_version_id,
            days=days,
        )
        expected_feedback_target_hash = target_metadata.get(
            "feedback_target_hash"
        )

    datasets = list_associated_datasets_for_score(client, score_id)
    if not datasets:
        return {
            "has_dataset": False,
            "dataset_id": None,
            "dataset_name": None,
            "created_at": None,
            "row_count": None,
            "is_materialized": False,
            "dataset_file": None,
            "materialization_error": None,
            "feedback_target_hash": expected_feedback_target_hash,
        }

    dataset = None
    row_count: Any = None
    stored_feedback_target_hash: str | None = None
    for candidate in datasets:
        candidate_row_count: Any = None
        candidate_feedback_target_hash: str | None = None
        if candidate.get("dataSourceVersionId"):
            try:
                dsv_result = client.execute(
                    """
                    query GetDataSourceVersion($id: ID!) {
                        getDataSourceVersion(id: $id) { id yamlConfiguration }
                    }
                    """,
                    {"id": candidate["dataSourceVersionId"]},
                )
                dsv = dsv_result.get("getDataSourceVersion")
                if dsv and dsv.get("yamlConfiguration"):
                    import yaml

                    config = yaml.safe_load(dsv["yamlConfiguration"])
                    if isinstance(config, dict):
                        stats = config.get("dataset_stats", {}) or {}
                        candidate_row_count = stats.get("row_count")
                        candidate_feedback_target_hash = stats.get(
                            "feedback_target_hash"
                        )
            except Exception:
                pass

        if (
            expected_feedback_target_hash
            and candidate_feedback_target_hash != expected_feedback_target_hash
        ):
            continue

        dataset = candidate
        row_count = candidate_row_count
        stored_feedback_target_hash = candidate_feedback_target_hash
        break

    if not dataset:
        return {
            "has_dataset": False,
            "dataset_id": None,
            "dataset_name": None,
            "created_at": None,
            "row_count": None,
            "is_materialized": False,
            "dataset_file": None,
            "materialization_error": None,
            "feedback_target_hash": expected_feedback_target_hash,
        }

    readiness = validate_dataset_materialization(dataset)
    return {
        "has_dataset": True,
        "dataset_id": dataset.get("id"),
        "dataset_name": dataset.get("name"),
        "created_at": dataset.get("createdAt"),
        "row_count": row_count,
        "is_materialized": bool(readiness.get("is_materialized")),
        "dataset_file": readiness.get("dataset_file"),
        "materialization_error": readiness.get("materialization_error"),
        "feedback_target_hash": stored_feedback_target_hash
        or expected_feedback_target_hash,
    }


def _default_report_configurations_list(args: dict[str, Any]) -> Any:
    """Run plexus.report.configurations_list directly via dashboard GraphQL."""

    from plexus.cli.shared.client_utils import create_client
    from shared.utils import get_default_account_id

    client = create_client()
    if not client:
        raise RuntimeError(
            "plexus.report.configurations_list: could not create dashboard client"
        )

    account_id = get_default_account_id()
    if not account_id:
        raise RuntimeError(
            "plexus.report.configurations_list: PLEXUS_ACCOUNT_KEY not set or "
            "default account could not be resolved"
        )

    query = (
        "query MyQuery { "
        f'listReportConfigurationByAccountIdAndUpdatedAt(accountId: "{account_id}", '
        "sortDirection: DESC) { items { description name id updatedAt } "
        "nextToken } }"
    )
    response = client.execute(query)
    if "errors" in response:
        raise RuntimeError(
            f"plexus.report.configurations_list dashboard error: {response['errors']}"
        )

    configs = (
        response.get("listReportConfigurationByAccountIdAndUpdatedAt") or {}
    ).get("items") or []

    if not configs:
        retry_query = (
            "query RetryQuery { "
            f'listReportConfigurations(filter: {{ accountId: {{ eq: "{account_id}" }} }}, '
            "limit: 20) { items { id name description updatedAt } } }"
        )
        retry_response = client.execute(retry_query)
        configs = (retry_response.get("listReportConfigurations") or {}).get(
            "items"
        ) or []

    return [
        {
            "id": cfg.get("id"),
            "name": cfg.get("name"),
            "description": cfg.get("description"),
            "updatedAt": cfg.get("updatedAt"),
        }
        for cfg in configs
    ]


def _default_evaluation_compare(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.evaluation.compare directly via Evaluation.get_evaluation_info."""

    from plexus.Evaluation import Evaluation

    evaluation_id = args.get("evaluation_id")
    baseline_evaluation_id = (
        args.get("baseline_evaluation_id") or args.get("baseline_id")
    )
    if not evaluation_id or not str(evaluation_id).strip():
        raise ValueError("plexus.evaluation.compare requires evaluation_id")
    if not baseline_evaluation_id or not str(baseline_evaluation_id).strip():
        raise ValueError(
            "plexus.evaluation.compare requires baseline_evaluation_id"
        )

    current_eval = Evaluation.get_evaluation_info(
        str(evaluation_id).strip(), include_score_results=False
    )
    baseline_eval = Evaluation.get_evaluation_info(
        str(baseline_evaluation_id).strip(), include_score_results=False
    )
    if not current_eval:
        raise ValueError(f"Current evaluation not found: {evaluation_id}")
    if not baseline_eval:
        raise ValueError(
            f"Baseline evaluation not found: {baseline_evaluation_id}"
        )

    def extract(eval_info: dict[str, Any]) -> dict[str, float]:
        out: dict[str, float] = {}
        metrics = eval_info.get("metrics")
        if isinstance(metrics, list):
            for metric in metrics:
                if (
                    isinstance(metric, dict)
                    and "name" in metric
                    and "value" in metric
                ):
                    try:
                        out[metric["name"]] = float(metric["value"])
                    except (TypeError, ValueError):
                        continue
        return out

    current_metrics = extract(current_eval)
    baseline_metrics = extract(baseline_eval)
    deltas = {
        k: current_metrics[k] - baseline_metrics[k]
        for k in current_metrics
        if k in baseline_metrics
    }
    return {
        "evaluation_id": str(evaluation_id),
        "baseline_evaluation_id": str(baseline_evaluation_id),
        "current_metrics": current_metrics,
        "baseline_metrics": baseline_metrics,
        "deltas": deltas,
        "improved": deltas.get("Alignment", 0) > 0,
    }


def _default_evaluation_find_recent(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.evaluation.find_recent directly against the dashboard."""

    from datetime import datetime, timedelta, timezone

    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.Evaluation import Evaluation

    score_version_id = args.get("score_version_id")
    evaluation_type = args.get("evaluation_type")

    # Auto-resolve score_version_id when scorecard/score names are supplied.
    if not score_version_id:
        scorecard_id_or_name = args.get("scorecard") or args.get("scorecard_identifier")
        score_id_or_name = args.get("score") or args.get("score_identifier") or args.get("id")
        if scorecard_id_or_name and score_id_or_name:
            try:
                from plexus.cli.shared.client_utils import create_client as _cc
                from plexus.cli.shared.memoized_resolvers import (
                    memoized_resolve_scorecard_identifier,
                )

                _client = _cc()
                if _client:
                    _sc_id = memoized_resolve_scorecard_identifier(_client, str(scorecard_id_or_name))
                    if _sc_id:
                        # Fetch championVersionId directly via GraphQL — it's a
                        # scorecard-level field not exposed on the Python Score model.
                        _sid_needle = str(score_id_or_name).lower()
                        _sc_result = _client.execute(
                            f"""query GetScorecardChampionVersion {{
                                getScorecard(id: "{_sc_id}") {{
                                    sections {{ items {{ scores {{ items {{
                                        id name key externalId championVersionId
                                    }} }} }} }}
                                }}
                            }}"""
                        )
                        _sc_data = _sc_result.get("getScorecard") or {}
                        for _sec in (_sc_data.get("sections") or {}).get("items", []):
                            for _s in (_sec.get("scores") or {}).get("items", []):
                                if (
                                    _s.get("id") == str(score_id_or_name)
                                    or _s.get("key") == str(score_id_or_name)
                                    or (_s.get("name") or "").lower() == _sid_needle
                                    or _sid_needle in (_s.get("name") or "").lower()
                                ):
                                    score_version_id = _s.get("championVersionId")
                                    break
                            if score_version_id:
                                break
            except Exception:
                pass

    if not score_version_id:
        raise ValueError(
            "plexus.evaluation.find_recent requires score_version_id "
            "(or { scorecard = '...', score = '...' } to auto-resolve it)"
        )
    if not evaluation_type:
        raise ValueError("plexus.evaluation.find_recent requires evaluation_type")

    max_age_hours = float(args.get("max_age_hours", 24.0))
    min_items = int(args.get("min_items", 0))
    dataset_id = args.get("dataset_id")
    days = args.get("days")
    max_feedback_items = args.get("max_feedback_items")
    sampling_mode = args.get("sampling_mode")
    latest_feedback_updated_at = args.get("latest_feedback_updated_at")

    client = PlexusDashboardClient()
    query = """
    query FindRecentEvalByVersion($scoreVersionId: String!, $limit: Int) {
      listEvaluationByScoreVersionIdAndCreatedAt(
        scoreVersionId: $scoreVersionId sortDirection: DESC limit: $limit
      ) { items { id type status scoreVersionId totalItems createdAt } }
    }
    """
    result = client.execute(
        query, {"scoreVersionId": str(score_version_id), "limit": 20}
    )
    items = (
        (result.get("listEvaluationByScoreVersionIdAndCreatedAt") or {})
        .get("items", [])
    )

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    normalized_eval_type = str(evaluation_type or "").strip().lower()
    normalized_sampling_mode = (
        str(sampling_mode or "").strip().lower()
        if sampling_mode is not None
        else None
    )
    latest_feedback_dt = None
    if latest_feedback_updated_at:
        try:
            latest_feedback_dt = datetime.fromisoformat(
                str(latest_feedback_updated_at).replace("Z", "+00:00")
            )
            if latest_feedback_dt.tzinfo is None:
                latest_feedback_dt = latest_feedback_dt.replace(tzinfo=timezone.utc)
        except Exception:
            latest_feedback_dt = None

    for item in items:
        if item.get("status") != "COMPLETED":
            continue
        if item.get("type", "").lower() != normalized_eval_type:
            continue
        if (item.get("totalItems") or 0) < min_items:
            continue
        created_raw = item.get("createdAt")
        if not created_raw:
            continue
        try:
            if isinstance(created_raw, str):
                created_at = datetime.fromisoformat(
                    created_raw.replace("Z", "+00:00")
                )
            else:
                created_at = created_raw
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at < cutoff:
                continue
        except Exception:
            continue

        eval_id = item["id"]
        try:
            eval_info = Evaluation.get_evaluation_info(eval_id)
        except Exception:
            continue

        parameters = eval_info.get("parameters") or {}
        if not isinstance(parameters, dict):
            parameters = {}

        if normalized_eval_type == "accuracy" and dataset_id is not None:
            eval_dataset_id = parameters.get("dataset_id")
            if (
                not eval_dataset_id
                and isinstance(parameters.get("metadata"), dict)
            ):
                eval_dataset_id = parameters["metadata"].get("dataset_id")
            if str(eval_dataset_id or "") != str(dataset_id):
                continue

        if normalized_eval_type == "feedback":
            if days is not None:
                try:
                    requested_days = int(days)
                    eval_days_int = (
                        int(parameters.get("days"))
                        if parameters.get("days") is not None
                        else None
                    )
                except Exception:
                    eval_days_int = None
                    requested_days = int(days)
                if eval_days_int is None or eval_days_int != requested_days:
                    continue
            if max_feedback_items is not None:
                try:
                    requested_max_items = int(max_feedback_items)
                    eval_max_items_int = (
                        int(parameters.get("max_feedback_items"))
                        if parameters.get("max_feedback_items") is not None
                        else None
                    )
                except Exception:
                    eval_max_items_int = None
                    requested_max_items = int(max_feedback_items)
                if (
                    eval_max_items_int is None
                    or eval_max_items_int != requested_max_items
                ):
                    continue
            if normalized_sampling_mode is not None:
                eval_sampling_mode = (
                    str(parameters.get("sampling_mode") or "").strip().lower()
                )
                if eval_sampling_mode != normalized_sampling_mode:
                    continue
            if latest_feedback_dt is not None:
                created_text = eval_info.get("created_at") or item.get("createdAt")
                try:
                    created_dt = datetime.fromisoformat(
                        str(created_text).replace("Z", "+00:00")
                    )
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                if created_dt < latest_feedback_dt:
                    continue

        return {
            "_from_cache": True,
            "evaluation_id": eval_id,
            "id": eval_id,
            "type": eval_info.get("type"),
            "status": eval_info.get("status"),
            "scorecard": eval_info.get("scorecard_name")
            or eval_info.get("scorecard_id"),
            "score": eval_info.get("score_name") or eval_info.get("score_id"),
            "score_version_id": eval_info.get("score_version_id"),
            "total_items": eval_info.get("total_items"),
            "processed_items": eval_info.get("processed_items"),
            "metrics": eval_info.get("metrics"),
            "accuracy": eval_info.get("accuracy"),
            "confusionMatrix": eval_info.get("confusion_matrix"),
            "predictedClassDistribution": eval_info.get(
                "predicted_class_distribution"
            ),
            "datasetClassDistribution": eval_info.get(
                "dataset_class_distribution"
            ),
            "baselineEvaluationId": eval_info.get("baseline_evaluation_id"),
            "currentBaselineEvaluationId": eval_info.get(
                "current_baseline_evaluation_id"
            ),
            "cost": eval_info.get("cost"),
            "cost_details": eval_info.get("cost_details"),
            "started_at": eval_info.get("started_at"),
            "created_at": eval_info.get("created_at"),
            "updated_at": eval_info.get("updated_at"),
            "root_cause": eval_info.get("root_cause"),
            "misclassification_analysis": eval_info.get(
                "misclassification_analysis"
            ),
        }

    return {"found": False}


def _default_evaluation_runner(args: dict[str, Any], mcp: FastMCP) -> dict[str, Any]:
    """Dispatch evaluation.run directly through the Plexus CLI in async mode."""

    import shutil
    import subprocess

    scorecard_name = args.get("scorecard_name") or args.get("scorecard")
    if not scorecard_name:
        raise ValueError("plexus.evaluation.run requires scorecard_name")

    evaluation_type = str(args.get("evaluation_type") or "accuracy").strip().lower()
    plexus_bin = shutil.which("plexus") or "plexus"

    if evaluation_type == "feedback":
        score_name = args.get("score_name") or args.get("score")
        if not score_name:
            raise ValueError("plexus.evaluation.run feedback requires score_name")
        cmd = [
            plexus_bin,
            "evaluate",
            "feedback",
            "--scorecard",
            str(scorecard_name),
            "--score",
            str(score_name),
            "--max-items",
            str(int(args.get("max_feedback_items") or 200)),
            "--sampling-mode",
            str(args.get("sampling_mode") or "newest"),
        ]
        _append_optional_cli_arg(cmd, "--days", args.get("days"))
        _append_optional_cli_arg(cmd, "--version", args.get("version"))
        _append_optional_cli_arg(cmd, "--sample-seed", args.get("sample_seed"))
        _append_optional_cli_arg(
            cmd, "--max-category-summary-items", args.get("max_category_summary_items")
        )
        if args.get("score_rubric_consistency_check"):
            cmd.append("--score-rubric-consistency-check")
    elif evaluation_type == "accuracy":
        cmd = [
            plexus_bin,
            "evaluate",
            "accuracy",
            "--scorecard",
            str(scorecard_name),
            "--number-of-samples",
            str(int(args.get("n_samples") or 10)),
            "--json-only",
        ]
        _append_optional_cli_arg(
            cmd, "--score", args.get("score_name") or args.get("score")
        )
        _append_optional_cli_arg(cmd, "--version", args.get("version"))
        _append_optional_cli_arg(cmd, "--dataset-id", args.get("dataset_id"))
        if args.get("latest"):
            cmd.append("--latest")
        if args.get("fresh"):
            cmd.append("--fresh")
        if args.get("reload"):
            cmd.append("--reload")
        if args.get("allow_no_labels"):
            cmd.append("--allow-no-labels")
        if args.get("use_score_associated_dataset"):
            cmd.append("--use-score-associated-dataset")
        if args.get("yaml", True):
            cmd.append("--yaml")
    else:
        raise ValueError(
            "plexus.evaluation.run evaluation_type must be 'accuracy' or 'feedback'"
        )

    _append_optional_cli_arg(cmd, "--baseline", args.get("baseline"))
    _append_optional_cli_arg(cmd, "--current-baseline", args.get("current_baseline"))
    _append_optional_cli_arg(cmd, "--notes", args.get("notes"))

    child_budget = args.get("budget")
    env = os.environ.copy()
    if isinstance(child_budget, dict):
        env["PLEXUS_CHILD_BUDGET"] = json.dumps(_jsonable(child_budget), sort_keys=True)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )
    return {
        "status": "dispatched",
        "process_id": process.pid,
        "command": cmd,
        "evaluation_type": evaluation_type,
        "scorecard": scorecard_name,
        "score": args.get("score_name") or args.get("score"),
        "child_budget": _jsonable(child_budget),
        "message": "Evaluation dispatched in background.",
        "dashboard_url": "https://lab.callcriteria.com/lab/evaluations",
    }


def _append_optional_cli_arg(cmd: list[str], flag: str, value: Any) -> None:
    if value is not None and value != "":
        cmd.extend([flag, str(value)])


def _default_report_runner(args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch report.run directly for durable background report-block work."""

    if args.get("config_id"):
        raise ValueError(
            "plexus.report.run async handles currently require block_class; "
            "configuration report handles need a dedicated report task dispatch path"
        )
    block_class = args.get("block_class")
    if not block_class:
        raise ValueError("plexus.report.run async requires block_class")

    from plexus.cli.report.utils import resolve_account_id_for_command
    from plexus.cli.shared.client_utils import create_client as create_dashboard_client
    from plexus.reports.service import run_block_cached

    client = create_dashboard_client()
    if not client:
        raise ValueError("Could not create dashboard client")
    account_id = resolve_account_id_for_command(client, args.get("account"))
    if not account_id:
        raise ValueError("Could not determine default account ID")

    output_data, log_output, was_cached = run_block_cached(
        block_class=str(block_class),
        block_config=args.get("block_config") or {},
        account_id=account_id,
        client=client,
        cache_key=args.get("cache_key"),
        ttl_hours=args.get("ttl_hours") if args.get("ttl_hours") is not None else 24,
        fresh=bool(args.get("fresh", False)),
        background=True,
        child_budget=args.get("budget"),
    )
    if not isinstance(output_data, dict):
        raise ValueError(log_output or "Report block background dispatch failed")
    if output_data.get("status") not in {"dispatched", "already_dispatched"}:
        raise ValueError(f"Unexpected report dispatch status: {output_data!r}")
    return {
        **output_data,
        "cached": was_cached,
        "block_class": block_class,
        "child_budget": _jsonable(args.get("budget")),
    }


def _default_procedure_runner(args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch procedure.run directly through ProcedureService async mode."""

    procedure_id = args.get("procedure_id") or args.get("id")
    if not procedure_id:
        raise ValueError("plexus.procedure.run requires procedure_id")

    from plexus.cli.procedure.service import ProcedureService
    from plexus.cli.shared.client_utils import create_client

    client = create_client()
    if not client:
        raise ValueError("Could not create API client")

    options: dict[str, Any] = {
        "async_mode": True,
        "dry_run": bool(args.get("dry_run", False)),
    }
    if args.get("max_iterations") is not None:
        options["max_iterations"] = int(args["max_iterations"])
    if args.get("timeout") is not None:
        options["timeout"] = int(args["timeout"])
    if isinstance(args.get("budget"), dict):
        context = args.get("context") if isinstance(args.get("context"), dict) else {}
        options["context"] = {
            **context,
            "_plexus_child_budget": _jsonable(args["budget"]),
        }

    service = ProcedureService(client)
    result = _run_async_from_sync(service.run_procedure(str(procedure_id), **options))
    if not isinstance(result, dict):
        raise ValueError(
            f"plexus.procedure.run async dispatch returned {type(result).__name__}"
        )
    if result.get("status") == "error" or result.get("error"):
        raise ValueError(str(result.get("error") or result))
    return result


def _default_procedure_optimize(args: dict[str, Any]) -> dict[str, Any]:
    """Start a Feedback Alignment Optimizer run for a given score.

    Creates a new procedure from the built-in feedback_alignment_optimizer.yaml,
    injects the supplied parameters, and dispatches it asynchronously.

    Required args:
        scorecard (str): Scorecard name, key, or ID.
        score (str): Score name, key, or ID.

    Optional args (all optimizer params):
        days (int): Feedback lookback window in days. Default 90.
        max_iterations (int): Maximum optimization cycles. Default 3.
        max_samples (int): Max feedback items per evaluation. Default 100.
        improvement_threshold (float): Min per-cycle AC1 gain. Default 0.02.
        target_accuracy (float): Stop early if AC1 reaches this. Default 0.95.
        num_candidates (int): Hypotheses per cycle. Default 3.
        optimization_objective (str): 'alignment'|'precision_safe'|'precision'|
            'recall_safe'|'recall'. Default 'alignment'.
        hint (str): Expert guidance injected into planning context.
        start_version (str): ScoreVersion UUID to start from instead of champion.
        resume_regression_eval (str): Reuse a prior regression baseline eval ID.
        resume_recent_eval (str): Reuse a prior recent baseline eval ID.
        prior_run_prescription (str): Prescription text from a prior run.
        dry_run (bool): Analyse only; never promote. Default false.
        context_window (int): Model context window in tokens. Default 180000.
        agent_models (dict): Per-agent model overrides.

    Returns dict with: procedure_id, status, message.
    """
    import os
    import yaml as yaml_lib

    from plexus.cli.procedure.service import ProcedureService
    from plexus.cli.shared.client_utils import create_client

    scorecard_identifier = args.get("scorecard") or args.get("scorecard_name") or args.get("scorecard_identifier")
    score_identifier = args.get("score") or args.get("score_name") or args.get("score_identifier")
    if not scorecard_identifier:
        raise ValueError("plexus.procedure.optimize requires 'scorecard'")
    if not score_identifier:
        raise ValueError("plexus.procedure.optimize requires 'score'")

    # Load the built-in optimizer YAML from the installed package.
    optimizer_yaml_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "plexus", "procedures", "feedback_alignment_optimizer.yaml",
    )
    optimizer_yaml_path = os.path.normpath(optimizer_yaml_path)
    if not os.path.exists(optimizer_yaml_path):
        raise FileNotFoundError(
            f"feedback_alignment_optimizer.yaml not found at {optimizer_yaml_path}"
        )
    with open(optimizer_yaml_path) as fh:
        yaml_text = fh.read()

    # Inject caller-supplied params into the YAML params block.
    OPTIMIZER_PARAMS = {
        "scorecard", "score", "days", "max_iterations", "max_samples",
        "improvement_threshold", "target_accuracy", "num_candidates",
        "optimization_objective", "hint", "start_version",
        "resume_regression_eval", "resume_recent_eval",
        "prior_run_prescription", "dry_run", "context_window", "agent_models",
    }
    config = yaml_lib.safe_load(yaml_text)
    params_def = config.get("params", {}) if isinstance(config, dict) else {}
    for key in OPTIMIZER_PARAMS:
        val = args.get(key)
        if val is None:
            continue
        if key in params_def and isinstance(params_def[key], dict):
            params_def[key]["value"] = val
        else:
            params_def[key] = {"value": val}
    # Always inject the required scorecard/score.
    if "scorecard" in params_def and isinstance(params_def["scorecard"], dict):
        params_def["scorecard"]["value"] = str(scorecard_identifier)
    if "score" in params_def and isinstance(params_def["score"], dict):
        params_def["score"]["value"] = str(score_identifier)
    yaml_text = yaml_lib.dump(config, allow_unicode=True, default_flow_style=False)

    client = create_client()
    if not client:
        raise RuntimeError("plexus.procedure.optimize: could not create dashboard client")

    service = ProcedureService(client)
    account = os.environ.get("PLEXUS_ACCOUNT_KEY") or ""
    if not account:
        raise RuntimeError(
            "plexus.procedure.optimize: PLEXUS_ACCOUNT_KEY environment variable is required"
        )

    result = service.create_procedure(
        account_identifier=account,
        scorecard_identifier=str(scorecard_identifier),
        score_identifier=str(score_identifier),
        yaml_config=yaml_text,
        featured=False,
    )
    if not result.success:
        raise RuntimeError(f"plexus.procedure.optimize: failed to create procedure — {result.message}")

    procedure_id = result.procedure.id

    options: dict[str, Any] = {
        "async_mode": True,
        "dry_run": bool(args.get("dry_run", False)),
    }
    run_result = _run_async_from_sync(service.run_procedure(str(procedure_id), **options))
    if not isinstance(run_result, dict):
        raise ValueError(
            f"plexus.procedure.optimize async dispatch returned {type(run_result).__name__}"
        )
    if run_result.get("status") == "error" or run_result.get("error"):
        raise ValueError(str(run_result.get("error") or run_result))

    return {
        "procedure_id": procedure_id,
        "status": run_result.get("status", "dispatched"),
        "message": run_result.get("message") or "Optimizer procedure dispatched asynchronously.",
        "scorecard": str(scorecard_identifier),
        "score": str(score_identifier),
        "dashboard_url": f"https://lab.callcriteria.com/lab/procedures/{procedure_id}",
    }


def _plain_value(value: Any) -> Any:
    """Convert Tactus/Lupa table values into plain Python containers."""

    if isinstance(value, dict):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain_value(item) for item in value]
    items = getattr(value, "items", None)
    if callable(items):
        pairs = [(key, _plain_value(item)) for key, item in items()]
        if pairs and all(isinstance(key, int) for key, _ in pairs):
            keys = sorted(key for key, _ in pairs)
            if keys == list(range(1, len(keys) + 1)):
                by_key = dict(pairs)
                return [by_key[index] for index in keys]
        return {key: item for key, item in pairs}
    return value


def _args(value: Any = None) -> dict[str, Any]:
    if value is None:
        return {}
    converted = _plain_value(value)
    if not isinstance(converted, dict):
        raise ValueError(
            f"Expected Tactus table arguments, got {type(converted).__name__}"
        )
    return converted


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        sequence = _dict_as_lua_sequence(value)
        if sequence is not None:
            return [_jsonable(item) for item in sequence]
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    items = getattr(value, "items", None)
    if callable(items):
        try:
            pairs = list(items())
        except TypeError:
            return repr(value)
        as_dict = {key: item for key, item in pairs}
        return _jsonable(as_dict)
    return repr(value)


def _normalize_mcp_tool_args(
    namespace: str, method: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Translate runtime-friendly Tactus names to legacy MCP tool parameters."""

    normalized = dict(args)
    return normalized


def _public_handle(record: dict[str, Any]) -> dict[str, Any]:
    public = {
        "id": record["id"],
        "kind": record["kind"],
        "status": record["status"],
        "status_url": record.get("status_url"),
        "created_at": record["created_at"],
        "parent_trace_id": record["parent_trace_id"],
    }
    if record.get("child_budget") is not None:
        public["child_budget"] = record.get("child_budget")
    return public


TERMINAL_HANDLE_STATUSES = frozenset(
    {"completed", "completed_unknown", "failed", "cancelled"}
)


def _normalize_handle_status(status: Any) -> str:
    normalized = str(status or "running").strip().lower()
    status_map = {
        "complete": "completed",
        "completed": "completed",
        "failed": "failed",
        "error": "failed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "running": "running",
        "pending": "running",
        "dispatched": "running",
    }
    return status_map.get(normalized, normalized or "running")


def _timeout_seconds(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, int | float):
        return max(float(value), 0.0)
    text = str(value).strip().upper()
    if not text:
        return default
    match = re.fullmatch(r"PT(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?", text)
    if match:
        minutes = float(match.group(1) or 0.0)
        seconds = float(match.group(2) or 0.0)
        return max((minutes * 60.0) + seconds, 0.0)
    return max(float(text), 0.0)


def _dict_as_lua_sequence(value: dict) -> list | None:
    """Detect string- or int-keyed dicts that represent 1-indexed Lua sequences."""

    if not value:
        return None
    indexed: list[tuple[int, Any]] = []
    for key, item in value.items():
        if isinstance(key, int):
            index = key
        elif isinstance(key, str) and key.isdigit():
            index = int(key)
        else:
            return None
        if index < 1:
            return None
        indexed.append((index, item))
    indexed.sort(key=lambda pair: pair[0])
    expected = list(range(1, len(indexed) + 1))
    if [pair[0] for pair in indexed] != expected:
        return None
    return [item for _, item in indexed]


def _extract_tool_value(result: Any) -> Any:
    def parse_json_string(value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    structured = getattr(result, "structured_content", None)
    if structured is not None:
        if (
            isinstance(structured, dict)
            and len(structured) == 1
            and "result" in structured
        ):
            value = structured["result"]
            return parse_json_string(value) if isinstance(value, str) else value
        if isinstance(structured, str):
            return parse_json_string(structured)
        return structured

    content = getattr(result, "content", None) or []
    if len(content) == 1 and hasattr(content[0], "text"):
        text = content[0].text
        return parse_json_string(text)
    return _jsonable(result)


def _structured_error(
    code: str, message: str, exc: BaseException | None = None
) -> dict[str, Any]:
    line_match = re.search(r":(\d+):", message)
    raw_lineno = int(line_match.group(1)) if line_match else None
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "traceback": None,
        "tactus_lineno": _user_tactus_lineno(raw_lineno),
    }
    if exc is not None:
        error["traceback"] = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
    return error


def _user_tactus_lineno(raw_lineno: int | None) -> int | None:
    if raw_lineno is None:
        return None
    prefix_lines = 5 + (3 * len(HELPER_BINDINGS)) + 1
    user_lineno = raw_lineno - prefix_lines
    return user_lineno if user_lineno > 0 else None


DEFAULT_BUDGET_USD = 0.25
DEFAULT_BUDGET_WALLCLOCK_SECONDS = 60.0
DEFAULT_BUDGET_DEPTH = 3
DEFAULT_BUDGET_TOOL_CALLS = 50


class BudgetExceeded(RuntimeError):
    """Raised when a Plexus runtime API call would exceed the active budget."""


class ChildBudgetRequired(ValueError):
    """Raised when async work is spawned without an explicit child budget."""


class BudgetSpec:
    """Conservative default budget for execute_tactus runs."""

    __slots__ = ("usd", "wallclock_seconds", "depth", "tool_calls")

    def __init__(
        self,
        *,
        usd: float = DEFAULT_BUDGET_USD,
        wallclock_seconds: float = DEFAULT_BUDGET_WALLCLOCK_SECONDS,
        depth: int = DEFAULT_BUDGET_DEPTH,
        tool_calls: int = DEFAULT_BUDGET_TOOL_CALLS,
    ) -> None:
        self.usd = float(usd)
        self.wallclock_seconds = float(wallclock_seconds)
        self.depth = int(depth)
        self.tool_calls = int(tool_calls)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BudgetSpec":
        spec = RuntimeBudgetSpec.from_dict(value)
        return cls(
            usd=spec.usd,
            wallclock_seconds=spec.wallclock_seconds,
            depth=spec.depth,
            tool_calls=spec.tool_calls,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "usd": self.usd,
            "wallclock_seconds": self.wallclock_seconds,
            "depth": self.depth,
            "tool_calls": self.tool_calls,
        }


class BudgetGate:
    """Single choke point that enforces a BudgetSpec around every Plexus runtime API call."""

    def __init__(
        self,
        spec: BudgetSpec | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.spec = spec or BudgetSpec()
        self._clock = clock or time.monotonic
        self._start = self._clock()
        self.spent_usd = 0.0
        self.tool_calls = 0
        self.reserved_wallclock_seconds = 0.0
        self.depth_max_observed = 0
        self.exceeded_reason: str | None = None
        self.child_budget_required_reason: str | None = None

    @property
    def exceeded(self) -> bool:
        return self.exceeded_reason is not None

    def elapsed_seconds(self) -> float:
        return self._clock() - self._start

    def _trip(self, reason: str) -> BudgetExceeded:
        self.exceeded_reason = reason
        return BudgetExceeded(reason)

    def check_before(
        self, namespace: str, method: str, *, estimated_usd: float = 0.0
    ) -> None:
        elapsed = self.elapsed_seconds()
        if elapsed + self.reserved_wallclock_seconds >= self.spec.wallclock_seconds:
            raise self._trip(
                f"wallclock budget exceeded before plexus.{namespace}.{method}: "
                f"{elapsed + self.reserved_wallclock_seconds:.3f}s >= "
                f"{self.spec.wallclock_seconds:.3f}s"
            )
        if self.spent_usd + estimated_usd > self.spec.usd:
            raise self._trip(
                f"USD budget exceeded before plexus.{namespace}.{method}: "
                f"${self.spent_usd + estimated_usd:.4f} > ${self.spec.usd:.4f}"
            )
        if self.tool_calls + 1 > self.spec.tool_calls:
            raise self._trip(
                f"tool_calls budget exceeded before plexus.{namespace}.{method}: "
                f"{self.tool_calls + 1} > {self.spec.tool_calls}"
            )

    def record_after(self, namespace: str, method: str, *, usd: float = 0.0) -> None:
        self.tool_calls += 1
        self.spent_usd += float(usd)

    def carve_child(
        self,
        namespace: str,
        method: str,
        budget_value: Any,
    ) -> dict[str, Any]:
        if not isinstance(budget_value, dict):
            self.child_budget_required_reason = (
                f"plexus.{namespace}.{method} async requires explicit budget"
            )
            raise ChildBudgetRequired(self.child_budget_required_reason)
        child_spec = BudgetSpec.from_dict(budget_value)
        elapsed = self.elapsed_seconds()
        remaining_usd = max(self.spec.usd - self.spent_usd, 0.0)
        remaining_seconds = max(
            self.spec.wallclock_seconds - elapsed - self.reserved_wallclock_seconds,
            0.0,
        )
        remaining_tool_calls = max(self.spec.tool_calls - self.tool_calls - 1, 0)
        if child_spec.usd > remaining_usd:
            raise self._trip(
                f"child USD budget exceeded before plexus.{namespace}.{method}: "
                f"${child_spec.usd:.4f} > ${remaining_usd:.4f}"
            )
        if child_spec.wallclock_seconds > remaining_seconds:
            raise self._trip(
                f"child wallclock budget exceeded before plexus.{namespace}.{method}: "
                f"{child_spec.wallclock_seconds:.3f}s > {remaining_seconds:.3f}s"
            )
        if child_spec.tool_calls > remaining_tool_calls:
            raise self._trip(
                f"child tool_calls budget exceeded before plexus.{namespace}.{method}: "
                f"{child_spec.tool_calls} > {remaining_tool_calls}"
            )
        if child_spec.depth > max(self.spec.depth - 1, 0):
            raise self._trip(
                f"child depth budget exceeded before plexus.{namespace}.{method}: "
                f"{child_spec.depth} > {max(self.spec.depth - 1, 0)}"
            )
        self.spent_usd += child_spec.usd
        self.reserved_wallclock_seconds += child_spec.wallclock_seconds
        self.tool_calls += child_spec.tool_calls
        self.depth_max_observed = max(self.depth_max_observed, child_spec.depth)
        return child_spec.to_dict()


def _cost_envelope(
    api_calls: list[str],
    wallclock_seconds: float,
    *,
    budget: BudgetGate | None = None,
) -> dict[str, Any]:
    if budget is not None:
        return {
            "usd": round(budget.spent_usd, 6),
            "wallclock_seconds": wallclock_seconds,
            "tokens": 0,
            "llm_calls": 0,
            "tool_calls": budget.tool_calls,
            "workers": 0,
            "depth_max_observed": budget.depth_max_observed,
            "budget_remaining_usd": round(
                max(budget.spec.usd - budget.spent_usd, 0.0), 6
            ),
            "budget_remaining_seconds": round(
                max(
                    budget.spec.wallclock_seconds
                    - wallclock_seconds
                    - budget.reserved_wallclock_seconds,
                    0.0,
                ),
                3,
            ),
            "budget_remaining_tool_calls": max(
                budget.spec.tool_calls - budget.tool_calls, 0
            ),
        }
    return {
        "usd": 0.0,
        "wallclock_seconds": wallclock_seconds,
        "tokens": 0,
        "llm_calls": 0,
        "tool_calls": len(api_calls),
        "workers": 0,
        "depth_max_observed": 0,
        "budget_remaining_usd": DEFAULT_BUDGET_USD,
        "budget_remaining_seconds": DEFAULT_BUDGET_WALLCLOCK_SECONDS,
        "budget_remaining_tool_calls": DEFAULT_BUDGET_TOOL_CALLS,
    }


def _response_envelope(
    *,
    ok: bool,
    value: Any,
    trace_id: str,
    api_calls: list[str],
    started_at: float,
    error: dict[str, Any] | None = None,
    partial: bool = False,
    budget: BudgetGate | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "value": _jsonable(value),
        "error": error,
        "cost": _cost_envelope(api_calls, time.monotonic() - started_at, budget=budget),
        "trace_id": trace_id,
        "partial": partial,
        "api_calls": api_calls,
    }


def _run_async_from_sync(awaitable: Any) -> Any:
    """Run an async FastMCP call from synchronous Tactus host-module code."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    outcome: dict[str, Any] = {}

    def run_in_thread() -> None:
        try:
            outcome["value"] = asyncio.run(awaitable)
        except Exception as exc:  # noqa: BLE001
            outcome["error"] = exc

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()
    thread.join()
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


def _stream_event_payload(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        return _jsonable(event)
    model_dump = getattr(event, "model_dump", None)
    if callable(model_dump):
        try:
            return _jsonable(model_dump(mode="json"))
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Falling back after stream event JSON serialization failed: %s",
                exc,
            )
            try:
                return _jsonable(model_dump(mode="python"))
            except Exception:  # noqa: BLE001
                logger.debug("Falling back to stream event attributes", exc_info=True)
    if hasattr(event, "__dict__"):
        return _jsonable(vars(event))
    return {"message": str(event)}


def _stream_event_message(kind: str, payload: dict[str, Any]) -> str:
    if kind == "agent_stream_chunk":
        agent = payload.get("agent_name") or "agent"
        chunk = str(payload.get("chunk_text") or "")
        return f"{agent}: {chunk}" if chunk else f"{agent} streamed output"
    if kind == "agent_turn":
        agent = payload.get("agent_name") or "agent"
        stage = payload.get("stage") or "updated"
        return f"{agent} {stage}"
    if kind == "tool_call_started":
        tool = payload.get("tool_name") or "tool"
        agent = payload.get("agent_name") or "agent"
        return f"{agent} calling {tool}"
    if kind == "tool_call":
        tool = payload.get("tool_name") or "tool"
        agent = payload.get("agent_name") or "agent"
        return f"{agent} completed {tool}"
    if kind == "cost":
        agent = payload.get("agent_name") or "agent"
        cost = payload.get("total_cost")
        if isinstance(cost, int | float):
            return f"{agent} cost ${cost:.6f}"
        return f"{agent} cost update"
    if kind == "execution_summary":
        return "Tactus execution summary"
    return str(payload.get("message") or kind)


def _stream_event_cost(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("event_type") != "cost":
        return None
    cost_keys = (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cost",
        "completion_cost",
        "total_cost",
        "duration_ms",
    )
    return {key: payload.get(key) for key in cost_keys if key in payload}


class _MCPStreamEmitter:
    """Thread-safe bridge from Tactus runtime events to MCP progress messages."""

    supports_streaming = True

    def __init__(self, *, trace_id: str, loop: asyncio.AbstractEventLoop) -> None:
        self.trace_id = trace_id
        self._loop = loop
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._progress = 0

    def empty(self) -> bool:
        return self._queue.empty()

    async def get(self) -> dict[str, Any]:
        return await self._queue.get()

    def emit(
        self,
        *,
        kind: str,
        message: str,
        payload: dict[str, Any] | None = None,
        progress: float | None = None,
        total: float | None = None,
        cost: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "kind": kind,
            "message": message,
            "payload": _jsonable(payload or {}),
            "cost": _jsonable(cost),
            "trace_id": self.trace_id,
        }
        if progress is not None:
            event["progress"] = progress
        if total is not None:
            event["total"] = total
        self._loop.call_soon_threadsafe(self._queue.put_nowait, event)

    def log(self, event: Any) -> None:
        payload = _stream_event_payload(event)
        kind = str(payload.get("event_type") or "log")
        self.emit(
            kind=kind,
            message=_stream_event_message(kind, payload),
            payload=payload,
            cost=_stream_event_cost(payload),
        )

    def api_call(self, api_call: str) -> None:
        self._progress += 1
        self.emit(
            kind="api_call",
            message=f"Calling {api_call}",
            payload={"api_call": api_call},
            progress=self._progress,
        )


async def _maybe_await(value: Any) -> Any:
    if asyncio.iscoroutine(value):
        return await value
    return value


async def _send_mcp_stream_event(ctx: Context, event: dict[str, Any]) -> None:
    progress = event.get("progress")
    if isinstance(progress, int | float):
        try:
            await _maybe_await(
                ctx.report_progress(
                    float(progress),
                    total=event.get("total"),
                    message=str(event.get("message") or event.get("kind") or "progress"),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ignoring failed execute_tactus progress event: %s", exc)
    try:
        await _maybe_await(
            ctx.info(
                str(event.get("message") or event.get("kind") or "execute_tactus update"),
                logger_name="plexus.execute_tactus",
                extra={"event": event},
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Ignoring failed execute_tactus info event: %s", exc)


class _Namespace:
    def __init__(
        self,
        dispatcher: Callable[[str, str, Any], Any],
        name: str,
        methods: set[str],
    ) -> None:
        self._dispatcher = dispatcher
        self._name = name
        for method_name in methods:
            setattr(self, method_name, self._make_call(method_name))

    def _make_call(self, method_name: str) -> Callable[[Any], Any]:
        def call(args: Any = None) -> Any:
            return self._dispatcher(self._name, method_name, args)

        return call


class PlexusRuntimeModule:
    """Tactus host module exposing curated Plexus runtime namespaces.

    Read-only namespaces with no service-layer dependency are implemented
    directly inside this module (no MCP loopback). The remaining namespaces
    delegate to existing FastMCP tools while the broader service-layer
    refactor is in progress.
    """

    def __init__(
        self,
        mcp: FastMCP,
        trace_id: str | None = None,
        docs_dir: str | None = None,
        budget: BudgetGate | None = None,
        handle_store: TactusHandleStore | None = None,
        scorecards_lister: Callable[[dict[str, Any]], Any] | None = None,
        scorecards_infoer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_evaluations: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_predict: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_set_champion: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_contradictions: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        item_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        item_last: Callable[[dict[str, Any]], Any] | None = None,
        procedure_listers: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
        feedback_finder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        feedback_aligner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluation_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluation_compare: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluation_find_recent: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluation_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        report_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        report_configurations_list: Callable[[dict[str, Any]], Any] | None = None,
        dataset_handlers: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
        procedure_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        procedure_optimize: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        stream_handler: _MCPStreamEmitter | None = None,
    ) -> None:
        self._mcp = mcp
        self._trace_id = trace_id or str(uuid.uuid4())
        self._docs_dir = docs_dir if docs_dir is not None else PLEXUS_DOCS_DIR
        self._budget = budget if budget is not None else BudgetGate()
        self._handle_store = (
            handle_store if handle_store is not None else _default_handle_store()
        )
        self._scorecards_lister = (
            scorecards_lister
            if scorecards_lister is not None
            else _default_scorecards_list
        )
        self._scorecards_infoer = (
            scorecards_infoer
            if scorecards_infoer is not None
            else _default_scorecards_info
        )
        self._score_info = score_info if score_info is not None else _default_score_info
        self._score_evaluations = (
            score_evaluations if score_evaluations is not None else _default_score_evaluations
        )
        self._score_predict = score_predict if score_predict is not None else _default_score_predict
        self._score_set_champion = (
            score_set_champion if score_set_champion is not None else _default_score_set_champion
        )
        self._score_contradictions = (
            score_contradictions if score_contradictions is not None else _default_score_contradictions
        )
        self._item_info = (
            item_info if item_info is not None else _default_item_info
        )
        self._item_last = (
            item_last if item_last is not None else _default_item_last
        )
        default_procedure_readers = {
            "list": _default_procedure_list,
            "info": _default_procedure_info,
            "chat_sessions": _default_procedure_chat_sessions,
            "chat_messages": _default_procedure_chat_messages,
        }
        if procedure_listers:
            default_procedure_readers.update(procedure_listers)
        self._procedure_readers: dict[str, Callable[[dict[str, Any]], Any]] = (
            default_procedure_readers
        )
        self._feedback_finder = (
            feedback_finder if feedback_finder is not None else _default_feedback_finder
        )
        self._feedback_aligner = (
            feedback_aligner
            if feedback_aligner is not None
            else _default_feedback_alignment
        )
        self._evaluation_info = (
            evaluation_info if evaluation_info is not None else _default_evaluation_info
        )
        self._evaluation_compare = (
            evaluation_compare
            if evaluation_compare is not None
            else _default_evaluation_compare
        )
        self._evaluation_find_recent = (
            evaluation_find_recent
            if evaluation_find_recent is not None
            else _default_evaluation_find_recent
        )
        self._evaluation_runner = (
            evaluation_runner
            if evaluation_runner is not None
            else lambda args: _default_evaluation_runner(args, self._mcp)
        )
        self._report_runner = (
            report_runner if report_runner is not None else _default_report_runner
        )
        self._report_configurations_list = (
            report_configurations_list
            if report_configurations_list is not None
            else _default_report_configurations_list
        )
        default_dataset_handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "build_from_feedback_window": _default_dataset_build_from_feedback_window,
            "check_associated": _default_dataset_check_associated,
        }
        if dataset_handlers:
            default_dataset_handlers.update(dataset_handlers)
        self._dataset_handlers = default_dataset_handlers
        self._procedure_runner = (
            procedure_runner
            if procedure_runner is not None
            else _default_procedure_runner
        )
        self._procedure_optimize = (
            procedure_optimize
            if procedure_optimize is not None
            else _default_procedure_optimize
        )
        self._stream_handler = stream_handler
        self._api_calls: list[str] = []
        self.handle_protocol_required: tuple[str, str] | None = None
        methods_by_namespace: dict[str, set[str]] = {}
        for namespace_name, method_name in MCP_TOOL_MAP.keys():
            methods_by_namespace.setdefault(namespace_name, set()).add(method_name)
        for namespace_name, method_name in DIRECT_HANDLERS.keys():
            methods_by_namespace.setdefault(namespace_name, set()).add(method_name)
        for namespace, methods in methods_by_namespace.items():
            setattr(self, namespace, _Namespace(self._call, namespace, methods))
        self.docs = _Namespace(self._call_docs, "docs", {"list", "get"})
        self.api = _Namespace(self._call_api, "api", {"list"})

    @property
    def api_calls(self) -> list[str]:
        return list(self._api_calls)

    @property
    def budget(self) -> BudgetGate:
        return self._budget

    def _record_api_call(self, namespace: str, method: str) -> None:
        api_call = f"plexus.{namespace}.{method}"
        self._api_calls.append(api_call)
        if self._stream_handler is not None:
            self._stream_handler.api_call(api_call)

    def _call(self, namespace: str, method: str, args: Any = None) -> Any:
        direct_handler = DIRECT_HANDLERS.get((namespace, method))
        if direct_handler is not None:
            return getattr(self, direct_handler)(namespace, method, args)
        tool_name = MCP_TOOL_MAP.get((namespace, method))
        if tool_name is None:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        if (namespace, method) in LONG_RUNNING_METHODS:
            self._record_api_call(namespace, method)
            self.handle_protocol_required = (namespace, method)
            raise RequiresHandleProtocol(namespace, method)
        self._budget.check_before(namespace, method)
        self._record_api_call(namespace, method)
        try:
            result = _run_async_from_sync(
                self._mcp.call_tool(
                    tool_name,
                    _normalize_mcp_tool_args(namespace, method, _args(args)),
                )
            )
        finally:
            self._budget.record_after(namespace, method)
        return _extract_tool_value(result)

    def _call_score(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "score" or method not in {"info", "evaluations", "predict", "set_champion", "contradictions"}:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("score", method)
        self._record_api_call("score", method)
        try:
            parsed = _args(args)
            if method == "info":
                return self._score_info(parsed)
            if method == "evaluations":
                return self._score_evaluations(parsed)
            if method == "predict":
                return self._score_predict(parsed)
            if method == "contradictions":
                return self._score_contradictions(parsed)
            return self._score_set_champion(parsed)
        finally:
            self._budget.record_after("score", method)

    def _call_item(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "item" or method not in {"info", "last"}:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("item", method)
        self._record_api_call("item", method)
        try:
            parsed = _args(args)
            if method == "info":
                return self._item_info(parsed)
            return self._item_last(parsed)
        finally:
            self._budget.record_after("item", method)

    def _call_procedure_read(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if namespace != "procedure" or method not in self._procedure_readers:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("procedure", method)
        self._record_api_call("procedure", method)
        try:
            return self._procedure_readers[method](_args(args))
        finally:
            self._budget.record_after("procedure", method)

    def _call_scorecards(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "scorecards" or method not in {"list", "info"}:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("scorecards", method)
        self._record_api_call("scorecards", method)
        try:
            parsed = _args(args)
            if method == "list":
                return self._scorecards_lister(parsed)
            return self._scorecards_infoer(parsed)
        finally:
            self._budget.record_after("scorecards", method)

    def _call_feedback(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "feedback" or method not in {"find", "alignment"}:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("feedback", method)
        self._record_api_call("feedback", method)
        try:
            parsed = _args(args)
            if method == "find":
                return self._feedback_finder(parsed)
            return self._feedback_aligner(parsed)
        finally:
            self._budget.record_after("feedback", method)

    def _call_evaluation_read(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if namespace != "evaluation" or method not in {
            "info",
            "compare",
            "find_recent",
        }:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("evaluation", method)
        self._record_api_call("evaluation", method)
        try:
            parsed = _args(args)
            if method == "info":
                return self._evaluation_info(parsed)
            if method == "compare":
                return self._evaluation_compare(parsed)
            return self._evaluation_find_recent(parsed)
        finally:
            self._budget.record_after("evaluation", method)

    def _call_evaluation_run(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if (namespace, method) != ("evaluation", "run"):
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        parsed = _args(args)
        if not bool(parsed.get("async")):
            self._record_api_call("evaluation", "run")
            self.handle_protocol_required = ("evaluation", "run")
            raise RequiresHandleProtocol("evaluation", "run")

        self._budget.check_before("evaluation", "run")
        self._record_api_call("evaluation", "run")
        child_budget = self._budget.carve_child(
            "evaluation", "run", parsed.get("budget")
        )
        parsed["budget"] = child_budget
        try:
            dispatch_result = self._evaluation_runner(parsed)
            return self._handle_store.create(
                kind="evaluation",
                parent_trace_id=self._trace_id,
                api_call="plexus.evaluation.run",
                args=parsed,
                dispatch_result=dispatch_result,
                child_budget=child_budget,
            )
        finally:
            self._budget.record_after("evaluation", "run")

    def _call_dataset(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "dataset" or method not in self._dataset_handlers:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("dataset", method)
        self._record_api_call("dataset", method)
        try:
            return self._dataset_handlers[method](_args(args))
        finally:
            self._budget.record_after("dataset", method)

    def _call_report_read(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if (namespace, method) != ("report", "configurations_list"):
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("report", "configurations_list")
        self._record_api_call("report", "configurations_list")
        try:
            return self._report_configurations_list(_args(args))
        finally:
            self._budget.record_after("report", "configurations_list")

    def _call_report_run(self, namespace: str, method: str, args: Any = None) -> Any:
        if (namespace, method) != ("report", "run"):
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        parsed = _args(args)
        if not bool(parsed.get("async")):
            self._record_api_call("report", "run")
            self.handle_protocol_required = ("report", "run")
            raise RequiresHandleProtocol("report", "run")

        self._budget.check_before("report", "run")
        self._record_api_call("report", "run")
        child_budget = self._budget.carve_child("report", "run", parsed.get("budget"))
        parsed["budget"] = child_budget
        try:
            dispatch_result = self._report_runner(parsed)
            return self._handle_store.create(
                kind="report",
                parent_trace_id=self._trace_id,
                api_call="plexus.report.run",
                args=parsed,
                dispatch_result=dispatch_result,
                child_budget=child_budget,
            )
        finally:
            self._budget.record_after("report", "run")

    def _call_procedure_run(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "procedure" or method not in {"run", "optimize"}:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        parsed = _args(args)

        if method == "optimize":
            # plexus.procedure.optimize always runs asynchronously — no handle protocol needed.
            self._budget.check_before("procedure", "optimize")
            self._record_api_call("procedure", "optimize")
            child_budget = self._budget.carve_child("procedure", "optimize", parsed.get("budget"))
            parsed["budget"] = child_budget
            try:
                return self._procedure_optimize(parsed)
            finally:
                self._budget.record_after("procedure", "optimize")

        if not bool(parsed.get("async")):
            self._record_api_call("procedure", "run")
            self.handle_protocol_required = ("procedure", "run")
            raise RequiresHandleProtocol("procedure", "run")

        self._budget.check_before("procedure", "run")
        self._record_api_call("procedure", "run")
        child_budget = self._budget.carve_child(
            "procedure", "run", parsed.get("budget")
        )
        parsed["budget"] = child_budget
        try:
            dispatch_result = self._procedure_runner(parsed)
            return self._handle_store.create(
                kind="procedure",
                parent_trace_id=self._trace_id,
                api_call="plexus.procedure.run",
                args=parsed,
                dispatch_result=dispatch_result,
                child_budget=child_budget,
            )
        finally:
            self._budget.record_after("procedure", "run")

    def _call_handle(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "handle":
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        parsed = _args(args)
        handle_id = parsed.get("id")
        if not handle_id:
            raise ValueError(f"plexus.handle.{method} requires id")

        self._budget.check_before("handle", method)
        self._record_api_call("handle", method)
        try:
            if method in {"peek", "status"}:
                return self._refresh_handle(str(handle_id))
            if method == "cancel":
                return self._cancel_handle(str(handle_id))
            if method == "await":
                timeout = _timeout_seconds(parsed.get("timeout"), default=0.0)
                poll_interval = _timeout_seconds(
                    parsed.get("poll_interval"), default=2.0
                )
                deadline = time.monotonic() + timeout
                while True:
                    record = self._refresh_handle(str(handle_id))
                    if record["status"] in TERMINAL_HANDLE_STATUSES:
                        return record
                    if time.monotonic() >= deadline:
                        return record
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return record
                    time.sleep(min(max(poll_interval, 0.1), remaining))
            raise ValueError(f"Unsupported Plexus runtime API: plexus.handle.{method}")
        finally:
            self._budget.record_after("handle", method)

    def _cancel_handle(self, handle_id: str) -> dict[str, Any]:
        record = self._handle_store.get(handle_id)
        dispatch_result = record.get("dispatch_result") or {}
        actions: list[dict[str, Any]] = []

        process_id = dispatch_result.get("process_id")
        if process_id:
            try:
                os.kill(int(process_id), signal.SIGTERM)
                actions.append(
                    {"kind": "process", "id": str(process_id), "status": "terminated"}
                )
            except ProcessLookupError:
                actions.append(
                    {"kind": "process", "id": str(process_id), "status": "not_running"}
                )
            except Exception as exc:  # noqa: BLE001
                actions.append(
                    {
                        "kind": "process",
                        "id": str(process_id),
                        "status": "error",
                        "error": str(exc),
                    }
                )

        task_id = dispatch_result.get("task_id")
        if task_id:
            actions.append(self._cancel_dashboard_task(str(task_id)))

        evaluation_id = dispatch_result.get("evaluation_id") or dispatch_result.get(
            "id"
        )
        if record.get("kind") == "evaluation" and evaluation_id:
            actions.append(self._cancel_evaluation_record(str(evaluation_id)))

        return self._handle_store.update(
            handle_id,
            {
                "status": "cancelled",
                "cancel_requested": True,
                "cancelled_at": _iso(time.time()),
                "cancel_actions": actions,
                "cancel_propagated": any(
                    action.get("status") in {"cancelled", "terminated", "not_running"}
                    for action in actions
                ),
            },
        )

    def _cancel_dashboard_task(self, task_id: str) -> dict[str, Any]:
        try:
            from plexus.cli.shared.client_utils import create_client
            from plexus.dashboard.api.models.task import Task

            client = create_client()
            task = Task.get_by_id(task_id, client)
            if not task:
                return {"kind": "task", "id": task_id, "status": "not_found"}
            task.update(
                status="CANCELLED",
                errorMessage="Cancellation requested by execute_tactus handle.",
                completedAt=_iso(time.time()),
            )
            return {"kind": "task", "id": task_id, "status": "cancelled"}
        except Exception as exc:  # noqa: BLE001
            return {"kind": "task", "id": task_id, "status": "error", "error": str(exc)}

    def _cancel_evaluation_record(self, evaluation_id: str) -> dict[str, Any]:
        try:
            from plexus.cli.shared.client_utils import create_client
            from plexus.dashboard.api.models.evaluation import (
                Evaluation as DashboardEvaluation,
            )

            evaluation = DashboardEvaluation.get_by_id(evaluation_id, create_client())
            if not evaluation:
                return {
                    "kind": "evaluation",
                    "id": evaluation_id,
                    "status": "not_found",
                }
            evaluation.update(
                status="CANCELLED",
                errorMessage="Cancellation requested by execute_tactus handle.",
            )
            return {"kind": "evaluation", "id": evaluation_id, "status": "cancelled"}
        except Exception as exc:  # noqa: BLE001
            return {
                "kind": "evaluation",
                "id": evaluation_id,
                "status": "error",
                "error": str(exc),
            }

    def _refresh_handle(self, handle_id: str) -> dict[str, Any]:
        record = self._handle_store.get(handle_id)
        dispatch_result = record.get("dispatch_result") or {}
        evaluation_id = dispatch_result.get("evaluation_id") or dispatch_result.get(
            "id"
        )
        if record.get("kind") == "evaluation" and not evaluation_id:
            process_id = dispatch_result.get("process_id")
            if process_id:
                try:
                    os.kill(int(process_id), 0)
                except ProcessLookupError:
                    return self._handle_store.update(
                        handle_id, {"status": "completed_unknown"}
                    )
                except PermissionError:
                    return self._handle_store.update(
                        handle_id, {"status": "running_unknown"}
                    )
                return self._handle_store.update(handle_id, {"status": "running"})
        if record.get("kind") != "evaluation" or not evaluation_id:
            return record

        try:
            evaluation = self._evaluation_info({"evaluation_id": evaluation_id})
        except Exception as exc:  # noqa: BLE001
            return self._handle_store.update(handle_id, {"last_status_error": str(exc)})

        status = _normalize_handle_status(evaluation.get("status"))
        return self._handle_store.update(
            handle_id,
            {
                "status": status,
                "evaluation_id": evaluation_id,
                "evaluation": evaluation,
                "status_url": record.get("status_url")
                or evaluation.get("dashboard_url")
                or f"https://lab.callcriteria.com/lab/evaluations/{evaluation_id}",
            },
        )

    def _call_docs(self, namespace: str, method: str, args: Any = None) -> Any:
        if method == "list":
            self._budget.check_before("docs", "list")
            self._record_api_call("docs", "list")
            try:
                return self._docs_list()
            finally:
                self._budget.record_after("docs", "list")
        if method == "get":
            parsed = _args(args)
            key = parsed.get("key") or parsed.get("name") or parsed.get("filename")
            if not key:
                raise ValueError("plexus.docs.get requires key, name, or filename")
            self._budget.check_before("docs", "get")
            self._record_api_call("docs", "get")
            try:
                return {"key": key, "content": self._docs_read(key)}
            finally:
                self._budget.record_after("docs", "get")
        raise ValueError(f"Unsupported Plexus runtime API: plexus.docs.{method}")

    def _call_api(self, namespace: str, method: str, args: Any = None) -> Any:
        if method != "list":
            raise ValueError(f"Unsupported Plexus runtime API: plexus.api.{method}")
        self._budget.check_before("api", "list")
        self._record_api_call("api", "list")
        try:
            api: dict[str, list[str]] = {}
            for namespace_name, method_name in MCP_TOOL_MAP:
                api.setdefault(f"plexus.{namespace_name}", []).append(method_name)
            for namespace_name, method_name in DIRECT_HANDLERS:
                api.setdefault(f"plexus.{namespace_name}", []).append(method_name)
            api.setdefault("plexus.docs", []).extend(["list", "get"])
            api.setdefault("plexus.api", []).append("list")
            return {key: sorted(set(values)) for key, values in sorted(api.items())}
        finally:
            self._budget.record_after("api", "list")

    def _docs_list(self) -> list[str]:
        if not os.path.isdir(self._docs_dir):
            raise FileNotFoundError(
                f"Plexus docs directory not found: {self._docs_dir}"
            )
        entries: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(self._docs_dir):
            for name in filenames:
                stem, ext = os.path.splitext(name)
                if ext.lower() != ".md" or stem.lower() == "readme":
                    continue
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, self._docs_dir)
                rel_no_ext, _ = os.path.splitext(rel)
                key = rel_no_ext.replace(os.sep, "/")
                entries.append(key)
        return sorted(entries)

    def _docs_read(self, key: str) -> str:
        if (
            key == ""
            or "\\" in key
            or key.startswith(".")
            or key.startswith("/")
            or ".." in key.split("/")
        ):
            raise ValueError(f"Invalid plexus.docs key: {key!r}")

        nested_path = os.path.normpath(os.path.join(self._docs_dir, f"{key}.md"))
        docs_root = os.path.normpath(self._docs_dir) + os.sep
        if not nested_path.startswith(docs_root):
            raise ValueError(f"Invalid plexus.docs key: {key!r}")
        if os.path.isfile(nested_path):
            with open(nested_path, "r", encoding="utf-8") as handle:
                return handle.read()

        if "/" not in key:
            for dirpath, _dirnames, filenames in os.walk(self._docs_dir):
                for name in filenames:
                    stem, ext = os.path.splitext(name)
                    if ext.lower() != ".md" or stem.lower() == "readme":
                        continue
                    if stem == key:
                        full = os.path.join(dirpath, name)
                        with open(full, "r", encoding="utf-8") as handle:
                            return handle.read()

        raise FileNotFoundError(f"Unknown plexus docs key: {key}")


def _wrap_tactus_snippet(tactus: str) -> str:
    helper_lines = [
        'local plexus = require("plexus")',
        "local __plexus_last_result = nil",
        "local function __plexus_capture(value)",
        "  __plexus_last_result = value",
        "  return value",
        "end",
    ]
    for helper_name, namespace, method in HELPER_BINDINGS:
        helper_lines.extend(
            [
                f"function {helper_name}(args)",
                f"  return __plexus_capture(plexus.{namespace}.{method}(args))",
                "end",
            ]
        )
    return "\n".join(
        [
            *helper_lines,
            "local function __execute_tactus_user_snippet()",
            tactus,
            "end",
            "local __plexus_explicit_result = __execute_tactus_user_snippet()",
            "if __plexus_explicit_result ~= nil then",
            "  return __plexus_explicit_result",
            "end",
            "return __plexus_last_result",
            "",
        ]
    )


def _run_tactus_sync(
    tactus: str,
    mcp: FastMCP,
    *,
    trace_id: str,
    trace_store: TactusTraceStore,
    budget: BudgetGate | None = None,
    handle_store: TactusHandleStore | None = None,
    feedback_finder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    evaluation_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    evaluation_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    report_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    procedure_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    stream_handler: _MCPStreamEmitter | None = None,
    score_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    gate = budget if budget is not None else BudgetGate()

    async def run() -> dict[str, Any]:
        from tactus.adapters.memory import MemoryStorage
        from tactus.core import TactusRuntime

        started_mono = time.monotonic()
        started_wall = time.time()
        wrapped = _wrap_tactus_snippet(tactus)
        runtime_result: Any = None
        envelope: dict[str, Any]
        try:
            runtime = TactusRuntime(
                procedure_id=f"execute_tactus_{trace_id}",
                storage_backend=MemoryStorage(),
                log_handler=stream_handler,
                run_id=trace_id,
            )
            if not hasattr(runtime, "register_python_module"):
                raise RuntimeError(
                    "execute_tactus requires TactusRuntime.register_python_module; "
                    "update the installed tactus package to the version specified by pyproject.toml."
                )
            plexus = PlexusRuntimeModule(
                mcp,
                trace_id=trace_id,
                budget=gate,
                handle_store=handle_store,
                feedback_finder=feedback_finder,
                evaluation_info=evaluation_info,
                evaluation_runner=evaluation_runner,
                report_runner=report_runner,
                procedure_runner=procedure_runner,
                stream_handler=stream_handler,
                score_info=score_info,
            )
            runtime.register_python_module("plexus", plexus)
            if stream_handler is not None:
                stream_handler.emit(
                    kind="execution",
                    message="execute_tactus runtime started",
                    payload={"stage": "started"},
                    progress=0,
                    total=1,
                )
            runtime_result = await runtime.execute(wrapped, context={}, format="lua")
            api_calls = plexus.api_calls
            if plexus.handle_protocol_required is not None:
                ns, mt = plexus.handle_protocol_required
                envelope = _response_envelope(
                    ok=False,
                    value=None,
                    trace_id=trace_id,
                    api_calls=api_calls,
                    started_at=started_mono,
                    error=_structured_error(
                        "requires_handle_protocol",
                        f"plexus.{ns}.{mt} requires the long-running handle/streaming "
                        "protocol from Kanbus epic plx-247588 and is not enabled in "
                        "this execute_tactus build.",
                    ),
                    budget=gate,
                )
            elif gate.child_budget_required_reason:
                envelope = _response_envelope(
                    ok=False,
                    value=None,
                    trace_id=trace_id,
                    api_calls=api_calls,
                    started_at=started_mono,
                    error=_structured_error(
                        "child_budget_required",
                        gate.child_budget_required_reason,
                    ),
                    budget=gate,
                )
            elif gate.exceeded:
                envelope = _response_envelope(
                    ok=False,
                    value=None,
                    trace_id=trace_id,
                    api_calls=api_calls,
                    started_at=started_mono,
                    error=_structured_error(
                        "budget_exceeded", gate.exceeded_reason or "Budget exceeded"
                    ),
                    budget=gate,
                )
            elif not isinstance(runtime_result, dict):
                envelope = _response_envelope(
                    ok=True,
                    value=runtime_result,
                    trace_id=trace_id,
                    api_calls=api_calls,
                    started_at=started_mono,
                    budget=gate,
                )
            else:
                ok = bool(runtime_result.get("success"))
                value = runtime_result.get("result")
                if ok:
                    envelope = _response_envelope(
                        ok=True,
                        value=value,
                        trace_id=trace_id,
                        api_calls=api_calls,
                        started_at=started_mono,
                        budget=gate,
                    )
                else:
                    message = str(
                        runtime_result.get("error") or "Tactus execution failed"
                    )
                    envelope = _response_envelope(
                        ok=False,
                        value=value,
                        trace_id=trace_id,
                        api_calls=api_calls,
                        started_at=started_mono,
                        error=_structured_error("tactus_execution_failed", message),
                        budget=gate,
                    )
        finally:
            ended_wall = time.time()
            record = _build_trace_record(
                trace_id=trace_id,
                envelope=locals().get(
                    "envelope",
                    _response_envelope(
                        ok=False,
                        value=None,
                        trace_id=trace_id,
                        api_calls=[],
                        started_at=started_mono,
                        error=_structured_error(
                            "runtime_error",
                            "execute_tactus aborted before envelope was built",
                        ),
                        budget=gate,
                    ),
                ),
                submitted_tactus=tactus,
                wrapped_tactus=wrapped,
                runtime_result=runtime_result,
                started_at_wall=started_wall,
                ended_at_wall=ended_wall,
            )
            _safe_write_trace(trace_store, record)
            if stream_handler is not None:
                envelope_for_stream = locals().get("envelope")
                stream_handler.emit(
                    kind="execution",
                    message="execute_tactus runtime completed",
                    payload={
                        "stage": "completed",
                        "ok": bool(
                            isinstance(envelope_for_stream, dict)
                            and envelope_for_stream.get("ok")
                        ),
                    },
                    progress=1,
                    total=1,
                )
        return envelope

    return asyncio.run(run())


async def _execute_tactus_tool(
    tactus: str,
    mcp: FastMCP,
    *,
    ctx: Context | None = None,
    trace_store: TactusTraceStore | None = None,
    budget: BudgetGate | None = None,
    handle_store: TactusHandleStore | None = None,
    feedback_finder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    evaluation_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    evaluation_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    report_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    procedure_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    score_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    store = trace_store if trace_store is not None else _default_trace_store()
    started_mono = time.monotonic()
    started_wall = time.time()
    trace_id = str(uuid.uuid4())

    if not isinstance(tactus, str) or not tactus.strip():
        envelope = _response_envelope(
            ok=False,
            value=None,
            trace_id=trace_id,
            api_calls=[],
            started_at=started_mono,
            error=_structured_error(
                "invalid_request",
                "tactus must be a non-empty string",
            ),
        )
        record = _build_trace_record(
            trace_id=trace_id,
            envelope=envelope,
            submitted_tactus=tactus if isinstance(tactus, str) else "",
            wrapped_tactus=None,
            started_at_wall=started_wall,
            ended_at_wall=time.time(),
        )
        _safe_write_trace(store, record)
        return envelope

    try:
        stream_handler = (
            _MCPStreamEmitter(trace_id=trace_id, loop=asyncio.get_running_loop())
            if ctx is not None
            else None
        )
        run_task = asyncio.create_task(
            asyncio.to_thread(
                _run_tactus_sync,
                tactus,
                mcp,
                trace_id=trace_id,
                trace_store=store,
                budget=budget,
                handle_store=handle_store,
                feedback_finder=feedback_finder,
                evaluation_info=evaluation_info,
                evaluation_runner=evaluation_runner,
                report_runner=report_runner,
                procedure_runner=procedure_runner,
                stream_handler=stream_handler,
                score_info=score_info,
            )
        )
        if stream_handler is None:
            return await run_task

        while True:
            if run_task.done():
                await asyncio.sleep(0)
                if stream_handler.empty():
                    break
            try:
                event = await asyncio.wait_for(stream_handler.get(), timeout=0.05)
            except asyncio.TimeoutError:
                continue
            await _send_mcp_stream_event(ctx, event)

        return await run_task
    except Exception as exc:
        logger.error("execute_tactus failed: %s", exc, exc_info=True)
        envelope = _response_envelope(
            ok=False,
            value=None,
            trace_id=trace_id,
            api_calls=[],
            started_at=started_mono,
            error=_structured_error("runtime_error", str(exc), exc),
        )
        record = _build_trace_record(
            trace_id=trace_id,
            envelope=envelope,
            submitted_tactus=tactus,
            wrapped_tactus=None,
            started_at_wall=started_wall,
            ended_at_wall=time.time(),
        )
        _safe_write_trace(store, record)
        return envelope


EXECUTE_TACTUS_DESCRIPTION = """\
Execute a short Tactus (Lua) snippet inside the Plexus runtime. This is the
single Plexus MCP tool; use it for every Plexus operation.

Runtime ground rules:
- `plexus` is a global. Do NOT write `local plexus = require("plexus")`.
- The runtime captures the result of the last Plexus operation your snippet
  calls and returns it as the value of this tool call. Use an explicit
  `return` only when you want a custom output shape.
- Always use table arguments: `plexus.score.info{ id = "..." }`.
- Errors are structured (`error.code`, `error.message`, `error.retryable`).
- Destructive ops (champion promotion, score updates, deletes, feedback
  invalidation) request `Human.approve` automatically; pass
  `no_confirm = true` only when the user explicitly approved.
- Long-running async calls (`plexus.evaluation.run`, `plexus.report.run`,
  `plexus.procedure.run` with `async = true`) require an explicit child
  budget table:
  `budget = { usd = <n>, wallclock_seconds = <n>, depth = <int>, tool_calls = <int> }`.

Helper aliases injected before your snippet runs:
- High-frequency: `evaluate`, `predict`, `scorecards`, `scorecard`, `score`,
  `item`, `last_item`, `feedback`, `feedback_alignment`, `dataset`,
  `report`, `report_configs`, `procedure`, `procedures`,
  `procedure_sessions`, `procedure_messages`.
- Canonical `namespace_method`: `scorecards_list`, `score_info`,
  `evaluation_info`, `evaluation_run`, `handle_status`, `handle_await`,
  `handle_cancel`, `docs_list`, `docs_get`, `api_list`, plus one helper
  per advertised API.
- Fall back to `plexus.<namespace>.<method>{...}` for anything else.

Examples:

1) Find a scorecard by name:
```tactus
local cards = scorecards{}
for _, card in ipairs(cards) do
  if card.name == "SelectQuote HCS Medium-Risk" then
    return { id = card.id, key = card.key, external_id = card.externalId }
  end
end
return { error = { code = "SCORECARD_NOT_FOUND", retryable = false } }
```

2) Inspect a score:
```tactus
return score{ id = "score_compliance_tone" }
```

3) Get an item's info:
```tactus
return item{ id = "item_1007" }
```

4) Run a single prediction:
```tactus
return predict{ score_id = "score_compliance_tone", item_id = "item_1007" }
```

5) Run a bounded synchronous evaluation:
```tactus
evaluate{ score_id = "score_compliance_tone", item_count = 200 }
```

6) Discover what's available (always do this when unsure):
```tactus
local apis = api_list()
local topics = docs_list()
local overview = docs_get{ key = "overview" }
return { apis = apis, topics = topics, overview = overview.content }
```

7) Long-running async with explicit budget and a handle:
```tactus
local handle = evaluate{
  score_id = "score_compliance_tone",
  item_count = 1000,
  async = true,
  budget = { usd = 0.50, wallclock_seconds = 1800, depth = 1, tool_calls = 10 },
}
return { handle_id = handle.id, status = handle.status }
```

Then poll, await, or cancel from a later `execute_tactus` call:
`handle_status{ id = "<id>" }`,
`handle_await{ id = "<id>", timeout = "PT10M" }`,
`handle_cancel{ id = "<id>" }`.

Read the canonical long form at any time with
`plexus.docs.get{ key = "overview" }`. Themed docs include `discovery`,
`read-apis`, `long-running-apis`, `handles-and-budgets`,
`score-and-dataset-authoring/`, `evaluation-and-feedback/`, `procedures/`,
`reports/`. Use `plexus.docs.list()` to see every available key.

The response envelope always has `ok`, `value`, `error`, `cost`, `trace_id`,
`partial`, and `api_calls`.
"""


def register_tactus_tools(mcp: FastMCP) -> None:
    """Register Tactus runtime tools with the MCP server."""

    @mcp.tool(description=EXECUTE_TACTUS_DESCRIPTION)
    async def execute_tactus(
        tactus: Annotated[
            str,
            Field(
                description=(
                    "Tactus (Lua) snippet to execute. `plexus` is global; helper "
                    "aliases like `evaluate`, `predict`, `score`, `item`, "
                    "`scorecards`, `api_list`, `docs_list`, `docs_get`, "
                    "`handle_status` are injected. Async long-running calls "
                    "(`evaluation.run`, `report.run`, `procedure.run` with "
                    "`async = true`) require an explicit child `budget = { usd, "
                    "wallclock_seconds, depth, tool_calls }`. Read "
                    "`plexus.docs.get{ key = \"overview\" }` for the full guide."
                )
            ),
        ],
        ctx: Context,
    ) -> dict[str, Any]:
        return await _execute_tactus_tool(tactus, mcp, ctx=ctx)
