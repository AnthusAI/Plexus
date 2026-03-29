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
        "version": "1.2.0",
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
            }
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
                    "You are the Plexus Console assistant.\n\n"
                    "You are a practical, accurate engineering copilot.\n"
                    "Respond directly to the user's latest message in the active chat session.\n"
                    "Keep responses concise, specific, and actionable.\n\n"
                    "If user intent is unclear, ask one clarifying question.\n"
                    "Avoid filler and avoid inventing data.\n"
                ),
                "initial_message": "Ready for the next user message.",
                "tools": [],
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
