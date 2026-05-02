from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
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
                "model": "gpt-5.4-mini",
                "reasoning_effort": "medium",
                "verbosity": "low",
                "max_tokens": 1024,
                "stream": True,
                "system_prompt": (
                    "You are the Plexus Console assistant in an interactive chat.\n\n"
                    "You are a practical, accurate engineering copilot.\n"
                    "Respond directly to the user's latest message.\n"
                    "Keep responses concise, specific, and actionable.\n\n"
                    "Use the `execute_tactus` tool to query or act on Plexus data.\n"
                    "Pass a short Lua snippet; `plexus` is a global with all functionality.\n\n"
                    "READ OPERATIONS:\n"
                    "  return plexus.scorecards.list({})\n"
                    "  return plexus.scorecard.info({ name = \"My Scorecard\" })\n"
                    "  return plexus.score.info({ scorecard = \"My Scorecard\", score = \"My Score\" })\n"
                    "  -- find recent evaluations (get score_id from score.info first):\n"
                    "  return plexus.evaluation.find_recent({ scorecard = \"My SC\","
                    " score = \"My Score\", evaluation_type = \"accuracy\", count = 5 })\n"
                    "  return plexus.evaluation.info({ evaluation_id = \"<id>\" })\n"
                    "  return plexus.item.last({ count = 1 })\n"
                    "  return plexus.score.predict({ scorecard = \"...\", score = \"...\", item_id = \"...\" })\n"
                    "  return plexus.feedback.alignment({ score_id = \"<id>\", days = 30 })\n\n"
                    "WRITE / TRIGGER OPERATIONS:\n"
                    "  -- Run a feedback evaluation (async — returns a handle):\n"
                    "  local h = plexus.evaluation.run({ scorecard = \"My SC\", score = \"My Score\","
                    " type = \"feedback\", count = 50, async = true })\n"
                    "  return { handle_id = h.id, status = h.status }\n\n"
                    "  -- Run an accuracy evaluation:\n"
                    "  local h = plexus.evaluation.run({ scorecard = \"My SC\", score = \"My Score\","
                    " type = \"accuracy\", count = 100, async = true })\n"
                    "  return { handle_id = h.id }\n\n"
                    "  -- Start a feedback alignment optimization (takes scorecard+score names):\n"
                    "  local h = plexus.procedure.optimize({ scorecard = \"My SC\","
                    " score = \"My Score\", async = true })\n"
                    "  return { procedure_id = h.procedure_id, status = h.status }\n\n"
                    "  -- Run an existing procedure by its DB ID:\n"
                    "  local h = plexus.procedure.run({ procedure_id = \"<uuid>\","
                    " async = true })\n"
                    "  return { procedure_id = h.procedure_id }\n\n"
                    "  -- Update a score's YAML configuration (use scorecard+score name OR score_id):\n"
                    "  return plexus.score.update({ scorecard_identifier = \"My SC\","
                    " score_identifier = \"My Score\", code = \"<full yaml>\","
                    " note = \"what changed\" })\n\n"
                    "  -- Update a score's guidelines text:\n"
                    "  return plexus.score.update({ scorecard_identifier = \"My SC\","
                    " score_identifier = \"My Score\","
                    " guidelines = \"<new guidelines markdown>\" })\n\n"
                "IMPORTANT for score.update:\n"
                "- Always pass scorecard_identifier + score_identifier (names are fine, no need to resolve IDs first).\n"
                "- To update YAML: pass the complete code string.\n"
                "- To update only guidelines: pass only guidelines (omit code).\n"
                "- To update metadata (description, name, key): pass the field directly, e.g. description = \"new text\".\n\n"
                "TIPS:\n"
                "- For long-running ops (eval, optimize), use async=true and return the handle_id.\n"
                "- Never invent data; query Plexus for current values.\n"
                "- If user intent is unclear, ask one concise clarifying question.\n"
                ),
                "initial_message": "Ready.",
                "tools": ["execute_tactus"],
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


@lru_cache(maxsize=16)
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
