"""End-to-end integration test for the agent documentation knowledge base.

This test wires a *real* Tactus agent to the
:class:`plexus.documentation.repository.DocumentationRepository` through
the same primitives that production procedures use:

* :class:`plexus.cli.procedure.lua_dsl.primitives.agent.AgentPrimitive`
  (the Tactus agent loop that invokes an LLM, executes tool calls, and
  appends results to its conversation),
* :class:`plexus.cli.procedure.model_config.ModelConfig` (the same
  factory production agents use to build a tool-bound LangChain
  ``ChatOpenAI``), and
* the standard :class:`ToolPrimitive` /
  :class:`StopPrimitive` / :class:`IterationsPrimitive` companions.

The model defaults to ``gpt-5.4-mini`` and can be overridden via
``PLEXUS_DOC_KB_TEST_MODEL``.

The agent is given exactly three tools - ``docs_list``, ``docs_get``,
and ``done`` - and a system prompt that instructs it to discover a
topic from the index, fetch its body, and then signal completion via
``done``. We then assert that the agent actually exercised the docs
tools (rather than hallucinating an answer) and that its final
``done.reason`` references the canonical topic id from the loaded
markdown.

The test is marked ``integration`` and is skipped automatically when
``OPENAI_API_KEY`` is not present, so it does not run in default CI but
can be invoked explicitly with::

    pytest -m integration plexus/documentation/test_documentation_kb_integration.py
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from plexus.config.loader import load_config
from plexus.documentation.repository import (
    DocumentationRepository,
    InvalidDocumentationKeyError,
)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - optional dependency
    pass

load_config()


pytestmark = pytest.mark.integration


_logger = logging.getLogger(__name__)


_DEFAULT_MODEL = os.environ.get("PLEXUS_DOC_KB_TEST_MODEL", "gpt-5.4-mini")
_MAX_AGENT_TURNS = int(os.environ.get("PLEXUS_DOC_KB_TEST_MAX_TURNS", "12"))
_AGENT_DOCS_ROOT = (
    Path(__file__).resolve().parents[2] / "documentation" / "agent"
)


# ---------------------------------------------------------------------------
# Tool wiring (matches the StructuredTool shape the real Tactus runtime uses)
# ---------------------------------------------------------------------------


def _format_list_result(repo: DocumentationRepository, namespace: Optional[str]) -> str:
    result = repo.list_docs(namespace=namespace)
    payload = {
        "entries": [
            {
                "id": entry["id"],
                "title": entry["title"],
                "summary": entry["summary"],
                "namespace": entry["namespace"],
                "tags": entry["tags"],
                "related": entry["related"],
            }
            for entry in result.entries
        ]
    }
    return json.dumps(payload)


def _format_get_result(repo: DocumentationRepository, doc_id: str) -> str:
    try:
        doc = repo.get_doc(doc_id)
    except InvalidDocumentationKeyError as exc:
        return json.dumps({"error": "invalid_id", "message": str(exc)})
    body = doc.body
    truncated = False
    if len(body) > 8000:
        body = body[:8000]
        truncated = True
    return json.dumps(
        {
            "id": doc.metadata.get("id"),
            "title": doc.metadata.get("title"),
            "namespace": doc.metadata.get("namespace"),
            "summary": doc.metadata.get("summary"),
            "related": doc.metadata.get("related") or [],
            "body": body,
            "truncated": truncated,
        }
    )


def _build_doc_tools(repo: DocumentationRepository):
    """Build StructuredTool instances whose ``.func`` accepts a single dict.

    This mirrors how :func:`plexus.cli.procedure.mcp_adapter.convert_mcp_tools_to_langchain`
    shapes MCP tools for the AgentPrimitive (which calls ``tool.func(args_dict)``
    in :meth:`AgentPrimitive._execute_single_tool`).
    """

    from langchain.tools import StructuredTool
    from pydantic import BaseModel, Field

    class DocsListArgs(BaseModel):
        namespace: Optional[str] = Field(
            default=None,
            description=(
                "Optional namespace filter, e.g. 'mcp', 'score-authoring', "
                "'evaluation-feedback', 'procedures', 'reports', "
                "'optimizer', 'repo-workflows'."
            ),
        )

    class DocsGetArgs(BaseModel):
        id: str = Field(
            description=(
                "Canonical namespaced id, e.g. "
                "'score-authoring.score-yaml-format' or "
                "'mcp.execute-tactus-overview'."
            ),
        )

    class DoneArgs(BaseModel):
        reason: str = Field(
            description=(
                "Brief explanation of why you are done. Cite the canonical "
                "topic id(s) you used to ground your answer."
            ),
        )
        success: bool = Field(default=True)

    def _docs_list_func(args: dict) -> str:
        namespace = args.get("namespace") if isinstance(args, dict) else None
        if isinstance(namespace, str) and not namespace.strip():
            namespace = None
        return _format_list_result(repo, namespace)

    def _docs_get_func(args: dict) -> str:
        doc_id = args.get("id") if isinstance(args, dict) else None
        if not isinstance(doc_id, str) or not doc_id:
            return json.dumps({"error": "missing_id"})
        return _format_get_result(repo, doc_id)

    def _done_func(args: dict) -> str:
        reason = (args or {}).get("reason", "")
        success = (args or {}).get("success", True)
        return f"Done: {reason} (success: {success})"

    docs_list_tool = StructuredTool(
        name="docs_list",
        description=(
            "List Plexus agent documentation topics. Returns metadata "
            "summaries (id, title, summary, namespace, tags, related) "
            "but not the full markdown body. Optionally filter by "
            "`namespace`."
        ),
        func=_docs_list_func,
        args_schema=DocsListArgs,
    )
    docs_get_tool = StructuredTool(
        name="docs_get",
        description=(
            "Get the full markdown body and metadata for a single "
            "documentation topic by its canonical namespaced id."
        ),
        func=_docs_get_func,
        args_schema=DocsGetArgs,
    )
    done_tool = StructuredTool(
        name="done",
        description=(
            "Signal completion of the task. Provide a `reason` that cites "
            "the canonical topic id(s) you used."
        ),
        func=_done_func,
        args_schema=DoneArgs,
    )
    return [docs_list_tool, docs_get_tool, done_tool]


# ---------------------------------------------------------------------------
# Tactus agent driver
# ---------------------------------------------------------------------------


def _build_tactus_agent(
    *,
    name: str,
    system_prompt: str,
    initial_message: str,
    tools: list,
    model: str,
):
    """Build a real :class:`AgentPrimitive` wired to a tool-bound ChatOpenAI."""

    from plexus.cli.procedure.lua_dsl.primitives.agent import AgentPrimitive
    from plexus.cli.procedure.lua_dsl.primitives.control import (
        IterationsPrimitive,
        StopPrimitive,
    )
    from plexus.cli.procedure.lua_dsl.primitives.tool import ToolPrimitive
    from plexus.cli.procedure.model_config import ModelConfig

    tool_primitive = ToolPrimitive()
    stop_primitive = StopPrimitive()
    iterations_primitive = IterationsPrimitive()

    llm = ModelConfig(
        model=model,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    ).create_langchain_llm()
    llm_with_tools = llm.bind_tools(tools)

    agent = AgentPrimitive(
        name=name,
        system_prompt=system_prompt,
        initial_message=initial_message,
        llm=llm_with_tools,
        available_tools=tools,
        tool_primitive=tool_primitive,
        stop_primitive=stop_primitive,
        iterations_primitive=iterations_primitive,
    )
    return agent, tool_primitive, stop_primitive, iterations_primitive


def _run_tactus_loop(
    agent,
    *,
    stop_primitive,
    iterations_primitive,
    max_turns: int,
) -> list[dict[str, Any]]:
    """Drive ``agent.turn()`` until the agent calls ``done`` or stops talking.

    This mirrors how a Tactus procedure's Lua loop calls ``Worker.turn()``
    until ``Stop.requested()`` becomes true. We additionally stop when the
    agent emits no tool calls, which signals the model considered itself
    finished even without explicitly calling ``done``.
    """

    turn_records: list[dict[str, Any]] = []
    for _ in range(max_turns):
        result = agent.turn()
        turn_records.append(result)
        if stop_primitive.requested():
            break
        if not result.get("tool_calls"):
            break
    else:
        raise AssertionError(
            f"Tactus agent exceeded {max_turns} turns without finishing. "
            f"Last turn: {turn_records[-1] if turn_records else 'n/a'}"
        )
    _logger.info(
        "Tactus loop finished after %d turns (stop_requested=%s)",
        iterations_primitive.current(),
        stop_primitive.requested(),
    )
    return turn_records


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def repo() -> DocumentationRepository:
    assert _AGENT_DOCS_ROOT.is_dir(), (
        f"Expected agent KB at {_AGENT_DOCS_ROOT}; the migration step has "
        "not run yet."
    )
    return DocumentationRepository(str(_AGENT_DOCS_ROOT))


@pytest.fixture(scope="module")
def doc_tools(repo: DocumentationRepository):
    return _build_doc_tools(repo)


@pytest.fixture(scope="module", autouse=True)
def _require_openai_key():
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip(
            "OPENAI_API_KEY is not set; skipping live documentation KB "
            "integration test."
        )


# ---------------------------------------------------------------------------
# Helpers for assertions
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You are a Plexus runtime agent running inside a Tactus procedure. "
    "You can answer questions about the Plexus runtime by calling the "
    "available tools.\n"
    "\n"
    "Workflow you must follow on every task:\n"
    "1. Call `docs_list` first to see which topics exist. The list "
    "returns metadata summaries only (id, title, summary, namespace, "
    "tags, related) - not full bodies.\n"
    "2. Pick the most relevant topic ids from the metadata.\n"
    "3. Call `docs_get` for those ids to read the full body.\n"
    "4. When you have enough information, call the `done` tool with a "
    "`reason` that *cites the canonical topic id(s) you used* (for "
    "example `score-authoring.score-yaml-format` or "
    "`mcp.execute-tactus-overview`) and a one- to three-sentence summary "
    "of the answer.\n"
    "\n"
    "Do not invent topic ids or content. If a fact is not in the loaded "
    "topics, say so in the `done` reason."
)


def _last_done_call(tool_primitive) -> Optional[dict[str, Any]]:
    return tool_primitive.last_call("done")


def _all_get_ids(tool_primitive) -> list[str]:
    ids: list[str] = []
    for call in tool_primitive.get_all_calls():
        if call.name == "docs_get" and isinstance(call.args, dict):
            value = call.args.get("id")
            if isinstance(value, str):
                ids.append(value)
    return ids


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_tactus_agent_can_look_up_score_authoring_topic(doc_tools):
    """A real Tactus agent should discover the score YAML topic via docs_list."""

    initial_message = (
        "I'm new to Plexus. Find the canonical agent documentation "
        "topic that explains how to author a Plexus score YAML "
        "configuration. When you call `done`, your `reason` must "
        "include the canonical topic id (for example "
        "`score-authoring.score-yaml-format`) and a one-line "
        "description of what it covers."
    )

    agent, tool_primitive, stop_primitive, iterations_primitive = _build_tactus_agent(
        name="docs_lookup_worker",
        system_prompt=_SYSTEM_PROMPT,
        initial_message=initial_message,
        tools=doc_tools,
        model=_DEFAULT_MODEL,
    )

    turns = _run_tactus_loop(
        agent,
        stop_primitive=stop_primitive,
        iterations_primitive=iterations_primitive,
        max_turns=_MAX_AGENT_TURNS,
    )

    _logger.info("[lookup] turn count: %d", len(turns))
    _logger.info(
        "[lookup] tools called: %s",
        [c.name for c in tool_primitive.get_all_calls()],
    )

    assert tool_primitive.called("docs_list"), (
        "Tactus agent never called docs_list; it must consult the index "
        "before answering."
    )
    assert stop_primitive.requested(), (
        "Tactus agent finished without calling `done`; the loop ended "
        "because the model stopped emitting tool calls."
    )

    done_call = _last_done_call(tool_primitive)
    assert done_call is not None, "agent did not call the `done` tool"
    done_reason = (done_call.get("args") or {}).get("reason") or ""
    assert "score-authoring.score-yaml-format" in done_reason, (
        "done.reason should cite the canonical topic id "
        f"'score-authoring.score-yaml-format'; got: {done_reason!r}"
    )

    get_ids = _all_get_ids(tool_primitive)
    if get_ids:
        assert "score-authoring.score-yaml-format" in get_ids, (
            f"agent loaded topics {get_ids} but not the canonical "
            "score-authoring.score-yaml-format topic"
        )


def test_tactus_agent_can_explain_how_to_set_up_a_new_score(
    doc_tools, repo: DocumentationRepository
):
    """A real Tactus agent should consult the docs to walk through a how-to."""

    initial_message = (
        "Suppose someone wants to create a new Plexus score from scratch. "
        "Walk through, at a high level, how an agent inside "
        "`execute_tactus` would: (a) discover what runtime calls are "
        "available, (b) find the documentation topic that explains the "
        "score YAML format, and (c) describe creating the score record. "
        "Use docs_list and docs_get to ground your explanation in real "
        "documentation. When you call `done`, the `reason` must (1) cite "
        "the canonical topic ids you consulted, and (2) mention at least "
        "one specific `plexus.*` runtime method per step."
    )

    agent, tool_primitive, stop_primitive, iterations_primitive = _build_tactus_agent(
        name="docs_howto_worker",
        system_prompt=_SYSTEM_PROMPT,
        initial_message=initial_message,
        tools=doc_tools,
        model=_DEFAULT_MODEL,
    )

    turns = _run_tactus_loop(
        agent,
        stop_primitive=stop_primitive,
        iterations_primitive=iterations_primitive,
        max_turns=_MAX_AGENT_TURNS,
    )

    _logger.info("[howto] turn count: %d", len(turns))
    _logger.info(
        "[howto] tools called: %s",
        [c.name for c in tool_primitive.get_all_calls()],
    )

    assert tool_primitive.called("docs_list"), (
        "Tactus agent never called docs_list; it must browse the index "
        "before answering a how-to question."
    )
    assert tool_primitive.called("docs_get"), (
        "Tactus agent never called docs_get; a how-to answer should be "
        "grounded in actual topic bodies."
    )
    assert stop_primitive.requested(), (
        "Tactus agent finished without calling `done`."
    )

    get_ids = _all_get_ids(tool_primitive)
    assert get_ids, "expected at least one docs_get call with a real id"

    namespaces_loaded: set[str] = set()
    for doc_id in get_ids:
        try:
            doc = repo.get_doc(doc_id)
        except InvalidDocumentationKeyError:
            continue
        ns = doc.metadata.get("namespace")
        if isinstance(ns, str):
            namespaces_loaded.add(ns)

    assert namespaces_loaded.intersection({"mcp", "score-authoring"}), (
        "expected the Tactus agent to load at least one mcp or "
        f"score-authoring topic; got namespaces {namespaces_loaded}"
    )

    done_call = _last_done_call(tool_primitive)
    assert done_call is not None, "agent did not call the `done` tool"
    done_reason = (done_call.get("args") or {}).get("reason") or ""

    assert "plexus." in done_reason.lower(), (
        "done.reason should mention at least one plexus.* runtime "
        f"method; got: {done_reason!r}"
    )

    expected_topic_signals = (
        "score-authoring.score-yaml-format",
        "mcp.execute-tactus-overview",
        "mcp.discovery",
    )
    assert any(signal in done_reason for signal in expected_topic_signals), (
        "done.reason should cite at least one canonical topic id "
        f"({expected_topic_signals}); got: {done_reason!r}"
    )


# ---------------------------------------------------------------------------
# Console chat agent (built-in) end-to-end smoke
# ---------------------------------------------------------------------------
#
# The two tests above exercise a synthetic Tactus agent against direct
# `docs_list` / `docs_get` tools. Production Console chat sessions are
# different: they ship a single `execute_tactus` tool, and the
# assistant must emit Lua snippets like
# `return plexus.docs.list({ namespace = "mcp" })` and
# `return plexus.docs.get({ id = "..." })`. The test below proves the
# *built-in Console chat agent's actual system prompt* steers
# `gpt-5.4-mini` to use that pattern when asked a "how does X work?"
# question.


_CONSOLE_DOCS_LIST_RE = re.compile(
    r"plexus\.docs\.list\s*[\(\{]"
)
_CONSOLE_DOCS_GET_RE = re.compile(
    r"plexus\.docs\.get\s*[\(\{][^}]*?id\s*=\s*['\"]([^'\"]+)['\"]"
)
_CONSOLE_DOCS_NAMESPACE_RE = re.compile(
    r"namespace\s*=\s*['\"]([^'\"]+)['\"]"
)


def _build_execute_tactus_shim(repo: DocumentationRepository):
    """Build a single tool shaped like the production ``execute_tactus``.

    The shim handles the two snippet shapes the Console chat prompt
    teaches the assistant: ``plexus.docs.list(...)`` (optionally with
    ``namespace = "..."``) and ``plexus.docs.get{ id = "..." }``.
    Anything else returns a stub envelope so the assistant is forced to
    use the documented patterns.
    """

    from langchain.tools import StructuredTool
    from pydantic import BaseModel, Field

    class ExecuteTactusArgs(BaseModel):
        tactus: str = Field(
            description=(
                "Tactus (Lua) snippet to execute. Must use plexus.* "
                "namespaces. For docs use plexus.docs.list(...) and "
                "plexus.docs.get({ id = '...' })."
            )
        )

    invocation_log: list[dict[str, Any]] = []

    def _execute_tactus_func(args: dict) -> str:
        snippet = (args or {}).get("tactus") or ""
        invocation_log.append({"tactus": snippet})

        get_match = _CONSOLE_DOCS_GET_RE.search(snippet)
        if get_match:
            doc_id = get_match.group(1)
            try:
                doc = repo.get_doc(doc_id)
            except InvalidDocumentationKeyError as exc:
                return json.dumps(
                    {"ok": False, "error": str(exc), "value": None}
                )
            body = doc.body
            truncated = False
            if len(body) > 6000:
                body = body[:6000]
                truncated = True
            return json.dumps(
                {
                    "ok": True,
                    "value": {
                        "id": doc.metadata.get("id"),
                        "title": doc.metadata.get("title"),
                        "namespace": doc.metadata.get("namespace"),
                        "summary": doc.metadata.get("summary"),
                        "related": doc.metadata.get("related") or [],
                        "content": body,
                        "truncated": truncated,
                    },
                    "error": None,
                }
            )

        if _CONSOLE_DOCS_LIST_RE.search(snippet):
            ns_match = _CONSOLE_DOCS_NAMESPACE_RE.search(snippet)
            namespace = ns_match.group(1) if ns_match else None
            result = repo.list_docs(namespace=namespace)
            entries = [
                {
                    "id": entry["id"],
                    "title": entry["title"],
                    "summary": entry["summary"],
                    "namespace": entry["namespace"],
                    "tags": entry["tags"],
                    "related": entry["related"],
                }
                for entry in result.entries
            ]
            return json.dumps({"ok": True, "value": entries, "error": None})

        return json.dumps(
            {
                "ok": False,
                "error": (
                    "This test shim only supports plexus.docs.list(...) "
                    "and plexus.docs.get({ id = '...' }). Use those to "
                    "answer the question."
                ),
                "value": None,
            }
        )

    tool = StructuredTool(
        name="execute_tactus",
        description=(
            "Execute a Tactus (Lua) snippet against the Plexus runtime. "
            "Use plexus.docs.list({}) to discover topics and "
            "plexus.docs.get({ id = '...' }) to load topic bodies. "
            "Returns a {ok, value, error} envelope as a JSON string."
        ),
        func=_execute_tactus_func,
        args_schema=ExecuteTactusArgs,
    )
    return tool, invocation_log


def _extract_console_assistant_prompt() -> str:
    from plexus.cli.procedure.builtin_procedures import (
        CONSOLE_CHAT_BUILTIN_ID,
        get_builtin_procedure_yaml,
    )
    import yaml as _yaml

    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = _yaml.safe_load(yaml_text)
    return parsed["agents"]["assistant"]["system_prompt"]


def test_console_chat_prompt_drives_real_agent_to_use_docs(repo):
    """Live: the built-in Console chat prompt makes gpt-5.4-mini consult plexus.docs."""

    system_prompt = _extract_console_assistant_prompt()
    execute_tactus_tool, invocation_log = _build_execute_tactus_shim(repo)

    # The Console chat .tac wraps the user message into a contextual prompt
    # before calling `assistant({ message = ... })`. Replicating the exact
    # wrapper here would couple this test to the .tac internals; the
    # essential signal is whether the documented prompt + execute_tactus
    # tool together steer the model toward plexus.docs.* usage.
    initial_message = (
        "User question: How do I author a Plexus score YAML "
        "configuration? Walk me through the canonical structure and "
        "cite the documentation topic you used.\n\n"
        "Use the execute_tactus tool to consult the plexus.docs "
        "knowledge base before answering."
    )

    agent, tool_primitive, stop_primitive, iterations_primitive = _build_tactus_agent(
        name="console_assistant",
        system_prompt=system_prompt,
        initial_message=initial_message,
        tools=[execute_tactus_tool],
        model=_DEFAULT_MODEL,
    )

    turns = _run_tactus_loop(
        agent,
        stop_primitive=stop_primitive,
        iterations_primitive=iterations_primitive,
        max_turns=_MAX_AGENT_TURNS,
    )

    snippets = [entry["tactus"] for entry in invocation_log]
    _logger.info("[console] turn count: %d", len(turns))
    _logger.info("[console] tactus snippets: %s", snippets)
    final_response = (turns[-1] or {}).get("content", "") if turns else ""
    _logger.info("[console] final assistant content: %s", final_response[:500])

    assert tool_primitive.called("execute_tactus"), (
        "Console assistant never called execute_tactus; the prompt "
        "should steer it to consult the runtime."
    )
    assert any(_CONSOLE_DOCS_LIST_RE.search(s) for s in snippets), (
        "Console assistant should emit a plexus.docs.list(...) snippet; "
        f"got snippets: {snippets!r}"
    )
    assert any(_CONSOLE_DOCS_GET_RE.search(s) for s in snippets), (
        "Console assistant should emit a plexus.docs.get({ id = ... }) "
        f"snippet; got snippets: {snippets!r}"
    )

    canonical_signals = (
        "score-authoring.score-yaml-format",
        "mcp.execute-tactus-overview",
    )
    assert any(
        signal in final_response or any(signal in s for s in snippets)
        for signal in canonical_signals
    ), (
        "Console assistant final response should cite a canonical topic "
        f"id; got response: {final_response!r}, snippets: {snippets!r}"
    )
