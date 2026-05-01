"""In-process MCP tool registration for rubric-memory tools.

Sub-agents (e.g. code_editor) that list rubric-memory tool names in their
``tools:`` YAML stanza receive these as callable MCP tools on the embedded
procedure transport.  The implementations delegate to the same Python
functions exposed through ``plexus.rubric_memory.*`` in the Tactus runtime.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Add the MCP directory to sys.path so the tactus_runtime module is importable.
_MCP_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "MCP")
)


def _ensure_mcp_on_path() -> None:
    if os.path.isdir(_MCP_DIR) and _MCP_DIR not in sys.path:
        sys.path.insert(0, _MCP_DIR)


def register_on_transport(transport: Any) -> None:
    """Register plexus_rubric_memory_* tools on an InProcessMCPTransport."""
    from plexus.cli.procedure.mcp_transport import MCPToolInfo

    _ensure_mcp_on_path()

    async def plexus_rubric_memory_recent_entries(args: Any) -> Any:
        try:
            from tools.tactus_runtime.execute import _default_rubric_memory_recent_entries  # type: ignore
            a = args if isinstance(args, dict) else {}
            return json.dumps(_default_rubric_memory_recent_entries(a), default=str)
        except Exception as exc:
            logger.warning("plexus_rubric_memory_recent_entries: %s", exc)
            return json.dumps({"success": False, "error": str(exc)})

    async def plexus_rubric_memory_evidence_pack(args: Any) -> Any:
        try:
            from tools.tactus_runtime.execute import _default_rubric_memory_evidence_pack  # type: ignore
            a = args if isinstance(args, dict) else {}
            return json.dumps(_default_rubric_memory_evidence_pack(a), default=str)
        except Exception as exc:
            logger.warning("plexus_rubric_memory_evidence_pack: %s", exc)
            return json.dumps({"success": False, "error": str(exc)})

    async def plexus_rubric_memory_sme_question_gate(args: Any) -> Any:
        try:
            from tools.tactus_runtime.execute import _default_rubric_memory_sme_question_gate  # type: ignore
            a = args if isinstance(args, dict) else {}
            return json.dumps(_default_rubric_memory_sme_question_gate(a), default=str)
        except Exception as exc:
            logger.warning("plexus_rubric_memory_sme_question_gate: %s", exc)
            return json.dumps({"success": False, "error": str(exc)})

    transport.register_tool(MCPToolInfo(
        name="plexus_rubric_memory_recent_entries",
        description=(
            "Retrieve recent rubric-memory citation context for one score. "
            "Use before optimization or SME-question drafting to find knowledge-base "
            "entries that may require guideline updates."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "scorecard_identifier": {"type": "string"},
                "score_identifier": {"type": "string"},
                "score_id": {"type": "string"},
                "score_version_id": {"type": "string"},
                "query": {"type": "string"},
                "days": {"type": "integer"},
                "since": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["scorecard_identifier", "score_identifier"],
            "additionalProperties": False,
        },
        handler=plexus_rubric_memory_recent_entries,
    ))

    transport.register_tool(MCPToolInfo(
        name="plexus_rubric_memory_evidence_pack",
        description=(
            "Generate rubric-memory citation context for a disputed score item. "
            "The champion ScoreVersion rubric is the policy authority; "
            "local .knowledge-base corpus evidence is supporting context."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "scorecard_identifier": {"type": "string"},
                "score_identifier": {"type": "string"},
                "score_id": {"type": "string"},
                "score_version_id": {"type": "string"},
                "transcript_text": {"type": "string"},
                "model_value": {"type": "string"},
                "model_explanation": {"type": "string"},
                "feedback_value": {"type": "string"},
                "feedback_comment": {"type": "string"},
                "topic_hint": {"type": "string"},
                "synthesize": {"type": "boolean"},
            },
            "required": ["scorecard_identifier", "score_identifier"],
            "additionalProperties": False,
        },
        handler=plexus_rubric_memory_evidence_pack,
    ))

    transport.register_tool(MCPToolInfo(
        name="plexus_rubric_memory_sme_question_gate",
        description=(
            "Gate proposed SME agenda questions against rubric-memory citations. "
            "Suppresses questions already answered by official rubric evidence."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "scorecard_identifier": {"type": "string"},
                "score_identifier": {"type": "string"},
                "score_version_id": {"type": "string"},
                "candidate_agenda_markdown": {"type": "string"},
                "rubric_memory_context": {},
                "optimizer_context": {"type": "string"},
            },
            "required": [
                "scorecard_identifier",
                "score_identifier",
                "score_version_id",
                "candidate_agenda_markdown",
            ],
            "additionalProperties": False,
        },
        handler=plexus_rubric_memory_sme_question_gate,
    ))

    logger.info("Registered 3 rubric-memory tools on procedure transport")
