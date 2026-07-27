"""Supported Tactus runtime controls shared by procedure and Console hosts."""

import logging
import os
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS = 300.0


def llm_request_timeout_seconds() -> float:
    """Return the positive provider timeout configured for Tactus agents."""
    raw_value = os.environ.get(
        "PLEXUS_LLM_REQUEST_TIMEOUT_SECONDS",
        str(DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS),
    )
    try:
        timeout_seconds = float(raw_value)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid PLEXUS_LLM_REQUEST_TIMEOUT_SECONDS=%r; using %.0f seconds",
            raw_value,
            DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS,
        )
        return DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS
    if timeout_seconds <= 0:
        logger.warning(
            "PLEXUS_LLM_REQUEST_TIMEOUT_SECONDS must be positive; using %.0f seconds",
            DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS,
        )
        return DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS
    return timeout_seconds


def apply_default_agent_request_timeout(procedure_source: str) -> str:
    """Set Tactus's public per-Agent timeout without replacing runtime methods."""
    try:
        parsed: Any = yaml.safe_load(procedure_source)
    except yaml.YAMLError:
        return procedure_source
    if not isinstance(parsed, dict):
        return procedure_source
    agents = parsed.get("agents")
    if not isinstance(agents, dict):
        return procedure_source

    timeout_seconds = llm_request_timeout_seconds()
    changed = False
    for agent_config in agents.values():
        if isinstance(agent_config, dict) and "request_timeout" not in agent_config:
            agent_config["request_timeout"] = timeout_seconds
            changed = True
    if not changed:
        return procedure_source
    return yaml.safe_dump(parsed, sort_keys=False)
