"""
CloudWatch Logs integration for procedure runs.

This module provides procedure-specific wrappers around PlexusCloudWatchLogger
and Tactus DSPyAgentHandle patching for LLM context logging.
"""

import logging
from typing import Any, Callable, Dict, Optional

from plexus.logging.cloudwatch_logger import PlexusCloudWatchLogger

logger = logging.getLogger(__name__)


def _create_procedure_cloudwatch_logger(
    account_key: str,
    procedure_id: str,
    invocation_run_id: str,
) -> Optional[PlexusCloudWatchLogger]:
    """
    Create and open a CloudWatch logger for procedure execution.

    Args:
        account_key: Account identifier for log group segmentation
        procedure_id: Procedure identifier
        invocation_run_id: Unique run identifier

    Returns:
        Opened PlexusCloudWatchLogger instance, or None if initialization failed
    """
    try:
        cw = PlexusCloudWatchLogger(
            account_key=account_key,
            component_name=procedure_id,
            invocation_id=invocation_run_id,
            log_category="procedures",
        )
        cw.open()
        return cw
    except Exception as exc:
        logger.debug("Could not create PlexusCloudWatchLogger: %s", exc)
        return None


def _install_cloudwatch_llm_context_patch(
    cw_logger: PlexusCloudWatchLogger,
) -> Callable[[], None]:
    """
    Monkey-patch Tactus DSPyAgentHandle to log LLM context to CloudWatch.

    Args:
        cw_logger: CloudWatch logger instance to receive LLM context logs

    Returns:
        Uninstall function to restore original methods
    """
    try:
        from tactus.dspy.agent import DSPyAgentHandle
    except Exception as exc:
        logger.debug("Could not import DSPyAgentHandle for CW patch: %s", exc)
        return lambda: None

    original_streaming = DSPyAgentHandle._turn_with_streaming
    original_non_streaming = DSPyAgentHandle._turn_without_streaming

    def patched_streaming(self: Any, opts: Dict[str, Any], prompt_context: Dict[str, Any]) -> Any:
        cw_logger.log_llm_context(prompt_context)
        return original_streaming(self, opts, prompt_context)

    def patched_non_streaming(self: Any, opts: Dict[str, Any], prompt_context: Dict[str, Any]) -> Any:
        cw_logger.log_llm_context(prompt_context)
        return original_non_streaming(self, opts, prompt_context)

    DSPyAgentHandle._turn_with_streaming = patched_streaming
    DSPyAgentHandle._turn_without_streaming = patched_non_streaming

    def uninstall() -> None:
        try:
            DSPyAgentHandle._turn_with_streaming = original_streaming
            DSPyAgentHandle._turn_without_streaming = original_non_streaming
        except Exception as exc:
            logger.debug("Could not uninstall CW LLM context patch: %s", exc)

    return uninstall
