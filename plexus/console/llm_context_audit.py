from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from plexus.reports.s3_utils import get_bucket_name

logger = logging.getLogger(__name__)

CONSOLE_CONTEXT_PREFIX = "console-contexts"


@dataclass
class LLMContextAuditRecord:
    procedure_id: str
    session_id: str
    trigger_message_id: str
    run_id: str
    agent_name: str
    turn_index: int
    call_index: int
    call_type: str  # "initial" | "tool_followup" | "synthesis"
    messages: List[Dict[str, Any]]
    model_config: Dict[str, Any]
    token_stats: Dict[str, int]
    timestamp_sent: str
    tool_config: Optional[Dict[str, Any]] = None
    timestamp_received: Optional[str] = None
    latency_ms: Optional[int] = None
    compaction_applied: bool = False
    compaction_metadata: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)


def _s3_key(session_id: str, turn_index: int, call_index: int) -> str:
    # Sanitize session_id so it forms a single path segment (no colons or slashes)
    safe_session = session_id.replace(":", "_").replace("/", "_")
    return f"{CONSOLE_CONTEXT_PREFIX}/{safe_session}/turn_{turn_index}_call_{call_index}.json"


def upload_llm_context_audit(
    record: LLMContextAuditRecord,
) -> str:
    """Upload an LLM context audit record to S3.

    Returns the S3 key of the uploaded artifact.
    """
    bucket_name = get_bucket_name()
    s3_key = _s3_key(record.session_id, record.turn_index, record.call_index)
    payload = record.to_json().encode("utf-8")

    s3_client = boto3.client("s3")

    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".json") as tmp:
        tmp_path = tmp.name
        tmp.write(payload)

    try:
        s3_client.upload_file(
            Filename=tmp_path,
            Bucket=bucket_name,
            Key=s3_key,
            ExtraArgs={"ContentType": "application/json"},
        )
        logger.info("Uploaded LLM context audit to s3://%s/%s", bucket_name, s3_key)
        return s3_key
    except ClientError:
        logger.exception(
            "Failed to upload LLM context audit for session %s turn %d call %d",
            record.session_id,
            record.turn_index,
            record.call_index,
        )
        raise
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def fetch_llm_context_audit(s3_key: str) -> LLMContextAuditRecord:
    """Download and parse an LLM context audit artifact from S3."""
    bucket_name = get_bucket_name()
    s3_client = boto3.client("s3")

    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".json") as tmp:
        tmp_path = tmp.name

    try:
        s3_client.download_file(Bucket=bucket_name, Key=s3_key, Filename=tmp_path)
        with open(tmp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return LLMContextAuditRecord(**data)
    except ClientError:
        logger.exception("Failed to download LLM context audit from %s", s3_key)
        raise
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
