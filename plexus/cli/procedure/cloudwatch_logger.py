"""
CloudWatch Logs integration for procedure runs.

Each procedure invocation opens two log streams:
  {procedure_id}/run/{invocation_run_id}         - lifecycle events, tool calls, cost events
  {procedure_id}/llm-context/{invocation_run_id} - full JSON per LLM call (prompt_context)

Log group: /plexus/procedures/{account_key}

All methods degrade gracefully when AWS is not configured; they never raise.
"""

import json
import logging
import os
import re
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


def _safe_account_key(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "-", raw)[:64] or "unknown"


def _epoch_ms() -> int:
    return int(time.time() * 1000)


class ProcedureCloudWatchLogger:
    """Streams procedure execution events to two CloudWatch log streams."""

    def __init__(self, account_key: str, procedure_id: str, invocation_run_id: str) -> None:
        self._procedure_id = procedure_id
        self._invocation_run_id = invocation_run_id
        self.log_group = f"/plexus/procedures/{_safe_account_key(account_key)}"
        self._run_stream = f"{procedure_id}/run/{invocation_run_id}"
        self._llm_stream = f"{procedure_id}/llm-context/{invocation_run_id}"
        self._logs_client: Any = None
        self._closed = False
        self._init_client()

    def _init_client(self) -> None:
        aws_region = (
            os.getenv("AWS_REGION")
            or os.getenv("AWS_REGION_NAME")
            or os.getenv("AWS_DEFAULT_REGION")
        )
        if not aws_region:
            logger.debug("AWS region not set; CloudWatch procedure logging disabled")
            return
        try:
            import boto3
            is_lambda = os.getenv("AWS_EXECUTION_ENV") or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            if is_lambda or not (aws_access_key and aws_secret_key):
                self._logs_client = boto3.client("logs", region_name=aws_region)
            else:
                self._logs_client = boto3.client(
                    "logs",
                    region_name=aws_region,
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                )
        except Exception as exc:
            logger.debug("Could not initialize CloudWatch Logs client: %s", exc)

    def open(self) -> None:
        if not self._logs_client:
            return
        try:
            try:
                self._logs_client.create_log_group(logGroupName=self.log_group)
            except self._logs_client.exceptions.ResourceAlreadyExistsException:
                pass
            for stream in (self._run_stream, self._llm_stream):
                try:
                    self._logs_client.create_log_stream(
                        logGroupName=self.log_group, logStreamName=stream
                    )
                except self._logs_client.exceptions.ResourceAlreadyExistsException:
                    pass
            self._put(self._run_stream, json.dumps({
                "event": "procedure_started",
                "procedure_id": self._procedure_id,
                "invocation_run_id": self._invocation_run_id,
                "log_group": self.log_group,
                "run_stream": self._run_stream,
                "llm_context_stream": self._llm_stream,
            }))
        except Exception as exc:
            logger.debug("CloudWatch open failed: %s", exc)

    def _put(self, stream_name: str, message: str) -> None:
        try:
            self._logs_client.put_log_events(
                logGroupName=self.log_group,
                logStreamName=stream_name,
                logEvents=[{"timestamp": _epoch_ms(), "message": message}],
            )
        except Exception as exc:
            logger.debug("put_log_events(%s) failed: %s", stream_name, exc)

    def log_run_event_from_tactus(self, event: Any) -> None:
        if not self._logs_client or self._closed:
            return
        try:
            self._put(self._run_stream, _format_tactus_event(event))
        except Exception as exc:
            logger.debug("log_run_event_from_tactus failed: %s", exc)

    def log_llm_context(self, payload: Dict[str, Any]) -> None:
        if not self._logs_client or self._closed:
            return
        try:
            self._put(self._llm_stream, json.dumps(payload, ensure_ascii=False, default=str))
        except Exception as exc:
            logger.debug("log_llm_context failed: %s", exc)

    def close(self, success: bool = True) -> None:
        if self._closed or not self._logs_client:
            return
        self._closed = True
        event_name = "procedure_completed" if success else "procedure_failed"
        self._put(self._run_stream, json.dumps({
            "event": event_name,
            "procedure_id": self._procedure_id,
            "invocation_run_id": self._invocation_run_id,
        }))


def _create_procedure_cloudwatch_logger(
    account_key: str,
    procedure_id: str,
    invocation_run_id: str,
) -> Optional[ProcedureCloudWatchLogger]:
    try:
        cw = ProcedureCloudWatchLogger(account_key, procedure_id, invocation_run_id)
        cw.open()
        return cw
    except Exception as exc:
        logger.debug("Could not create ProcedureCloudWatchLogger: %s", exc)
        return None


def _install_cloudwatch_llm_context_patch(
    cw_logger: ProcedureCloudWatchLogger,
) -> Callable[[], None]:
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


def _format_tactus_event(event: Any) -> str:
    try:
        from tactus.protocols.models import CostEvent
        if isinstance(event, CostEvent):
            return json.dumps({
                "event": "cost",
                "agent": getattr(event, "agent_name", None),
                "model": getattr(event, "model", None),
                "cost_usd": getattr(event, "total_cost", None) or getattr(event, "cost", None),
                "total_tokens": getattr(event, "total_tokens", None),
                "cache_hit": getattr(event, "cache_hit", False),
            }, default=str)
    except Exception:
        pass

    event_type = getattr(event, "event_type", None) or type(event).__name__
    content = getattr(event, "content", None) or getattr(event, "message", None)
    role = getattr(event, "role", None)
    parts: Dict[str, Any] = {"event": str(event_type)}
    if role:
        parts["role"] = str(role)
    if content:
        text = str(content)
        parts["content"] = text[:500] + "…" if len(text) > 500 else text
    return json.dumps(parts, default=str) if len(parts) > 1 else str(event_type)
