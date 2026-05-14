"""
CloudWatch Logs integration for Plexus components.

Each component invocation opens two log streams:
  {component_name}/run/{invocation_id}         - lifecycle events, tool calls, cost events
  {component_name}/llm-context/{invocation_id} - full JSON per LLM call (prompt_context)

Log group: /plexus/{log_category}/{account_key}

All methods degrade gracefully when AWS is not configured; they never raise.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _safe_account_key(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "-", raw)[:64] or "unknown"


def _epoch_ms() -> int:
    return int(time.time() * 1000)


class PlexusCloudWatchLogger:
    """Streams Plexus component execution events to two CloudWatch log streams."""

    def __init__(
        self,
        account_key: str,
        component_name: str,
        invocation_id: str,
        log_category: str = "procedures",
    ) -> None:
        """
        Initialize CloudWatch logger.

        Args:
            account_key: Account identifier for log group segmentation
            component_name: Component identifier (e.g., procedure ID, "console/chat")
            invocation_id: Unique invocation identifier (e.g., run ID, message ID)
            log_category: Category for log group (default: "procedures")
        """
        self._component_name = component_name
        self._invocation_id = invocation_id
        self.log_group = f"/plexus/{log_category}/{_safe_account_key(account_key)}"
        self._run_stream = f"{component_name}/run/{invocation_id}"
        self._llm_stream = f"{component_name}/llm-context/{invocation_id}"
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
            logger.debug("AWS region not set; CloudWatch logging disabled")
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
                "event": "component_started",
                "component_name": self._component_name,
                "invocation_id": self._invocation_id,
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
        event_name = "component_completed" if success else "component_failed"
        self._put(self._run_stream, json.dumps({
            "event": event_name,
            "component_name": self._component_name,
            "invocation_id": self._invocation_id,
        }))


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
