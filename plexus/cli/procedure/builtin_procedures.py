from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

CONSOLE_CHAT_BUILTIN_ID = "builtin:console/chat"


@dataclass(frozen=True)
class BuiltinProcedureSpec:
    procedure_id: str
    name: str
    description: str
    version: str
    tac_path: Path


def _procedures_root() -> Path:
    return Path(__file__).resolve().parents[2] / "procedures"


def _build_console_chat_config(tac_source: str) -> Dict[str, Any]:
    return {
        "name": "Console Chat Agent",
        "version": "1.4.0",
        "class": "Tactus",
        "description": "General-purpose Console chat procedure for /lab/console.",
        "params": {
            "fallback_prompt": {
                "type": "string",
                "required": False,
                "default": "Hello. How can I help you today?",
                "description": "Fallback prompt when no user message is available.",
            }
        },
        "input": {
            "console_user_message": {
                "type": "string",
                "required": False,
                "default": "",
            },
            "console_session_history": {
                "type": "array",
                "required": False,
                "default": [],
                "description": "Recent USER/ASSISTANT turns for continuity in detached runs.",
            },
        },
        "outputs": {
            "success": {"type": "boolean", "required": True},
            "response": {"type": "string", "required": True},
            "prompt_used": {"type": "string", "required": True},
            "iterations": {"type": "number", "required": True},
        },
        "agents": {
            "assistant": {
                "system_prompt": (
                    "You are the Plexus Console assistant in an interactive chat.\n\n"
                    "You are a practical, accurate engineering copilot with access to read-only\n"
                    "Plexus MCP tools. Respond directly to the user's latest message.\n"
                    "Keep responses concise, specific, and actionable.\n\n"
                    "TOOL USE:\n"
                    "- Use tools when the user asks about Plexus data (scorecards, scores,\n"
                    "  evaluations, feedback, items, reports, procedures, tasks).\n"
                    "- Prefer the most specific tool for the question. Chain tools when needed.\n"
                    "- Use `think` to plan multi-step tool use before acting.\n"
                    "- Use `get_plexus_documentation` when you need information on a topic or\n"
                    "  format you are unsure about.\n"
                    "- When you have enough information to answer, stop calling tools and reply\n"
                    "  to the user in natural language. Do not call `done` in chat mode.\n\n"
                    "CONTEXT:\n"
                    "- Recent conversation turns are provided as prior context.\n"
                    "- Refer back to earlier turns and tool results instead of re-querying.\n"
                    "- If user intent is unclear, ask one concise clarifying question.\n"
                    "- Avoid filler and never invent data. If a tool fails, report the failure.\n"
                ),
                "initial_message": "Ready.",
                "tools": [
                    "think",
                    "get_plexus_documentation",
                    "plexus_scorecards_list",
                    "plexus_scorecard_info",
                    "plexus_score_info",
                    "plexus_evaluation_info",
                    "plexus_evaluation_run",
                    "plexus_evaluation_find_recent",
                    "plexus_evaluation_score_result_find",
                    "plexus_feedback_find",
                    "plexus_feedback_alignment",
                    "plexus_feedback_latest_update",
                    "plexus_item_info",
                    "plexus_item_last",
                    "plexus_task_info",
                    "plexus_task_last",
                    "plexus_report_info",
                    "plexus_reports_list",
                    "plexus_report_last",
                    "plexus_predict",
                    "plexus_cost_analysis",
                    "plexus_procedure_info",
                    "plexus_procedure_list",
                ],
            }
        },
        "stages": ["preparing", "responding", "complete"],
        "code": tac_source,
    }


_BUILTINS: Dict[str, BuiltinProcedureSpec] = {
    CONSOLE_CHAT_BUILTIN_ID: BuiltinProcedureSpec(
        procedure_id=CONSOLE_CHAT_BUILTIN_ID,
        name="Console Chat Agent",
        description="Built-in general-purpose chat procedure for Plexus Console.",
        version="1.2.0",
        tac_path=_procedures_root() / "console" / "chat_agent.tac",
    ),
}


def is_builtin_procedure_id(procedure_id: Optional[str]) -> bool:
    return bool(procedure_id and procedure_id in _BUILTINS)


def get_builtin_procedure_spec(procedure_id: str) -> Optional[BuiltinProcedureSpec]:
    return _BUILTINS.get(procedure_id)


def get_builtin_procedure_yaml(procedure_id: str) -> Optional[str]:
    spec = get_builtin_procedure_spec(procedure_id)
    if not spec:
        return None

    tac_source = spec.tac_path.read_text(encoding="utf-8")

    if procedure_id == CONSOLE_CHAT_BUILTIN_ID:
        config = _build_console_chat_config(tac_source)
    else:
        return None

    return yaml.safe_dump(config, sort_keys=False)
