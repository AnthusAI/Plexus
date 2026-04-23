from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import boto3

TASK_OUTPUT_PREVIEW_CHARS = 800
TASK_OUTPUT_ATTACHMENT_BUCKET_ENV = "AMPLIFY_STORAGE_TASKATTACHMENTS_BUCKET_NAME"


def upload_task_attachment_bytes(
    *,
    bucket_name: str,
    key: str,
    body: bytes,
    content_type: str,
) -> str:
    """Upload task output bytes to the task attachments bucket and return the key."""
    if not bucket_name:
        raise ValueError("bucket_name is required for task attachment upload.")
    if not key:
        raise ValueError("key is required for task attachment upload.")
    if not body:
        raise ValueError("body is required for task attachment upload.")

    s3_client = boto3.client("s3")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=body,
        ContentType=content_type,
    )
    return key


def _normalize_attached_files(existing_attached_files: Optional[List[str]]) -> List[str]:
    normalized: List[str] = []
    for path in existing_attached_files or []:
        if isinstance(path, str) and path not in normalized:
            normalized.append(path)
    return normalized


def _task_output_preview_from_payload(output_payload: Any) -> Dict[str, Any]:
    if isinstance(output_payload, dict):
        preview: Dict[str, Any] = {}
        for key in (
            "status",
            "type",
            "summary",
            "message",
            "error",
            "decision",
            "accuracy",
            "score",
            "scorecard",
        ):
            if key in output_payload:
                preview[key] = output_payload[key]
        if preview:
            return preview
        compact_json = json.dumps(output_payload, ensure_ascii=False, default=str)
        return {"raw_preview": compact_json[:TASK_OUTPUT_PREVIEW_CHARS]}

    if isinstance(output_payload, (list, tuple)):
        compact_json = json.dumps(output_payload, ensure_ascii=False, default=str)
        return {"raw_preview": compact_json[:TASK_OUTPUT_PREVIEW_CHARS]}

    if output_payload is None:
        return {"message": "Task returned no output."}

    return {"raw_preview": str(output_payload)[:TASK_OUTPUT_PREVIEW_CHARS]}


def _serialize_task_output_payload(
    output_payload: Any,
    *,
    format_type: str,
) -> Tuple[str, str, str]:
    normalized_format = (format_type or "json").lower()

    if normalized_format == "json":
        serialized = json.dumps(output_payload, indent=2, ensure_ascii=False, default=str)
        return serialized, "output.json", "application/json"

    if normalized_format in {"yaml", "yml"}:
        return str(output_payload), "output.yaml", "text/yaml"

    if normalized_format == "txt":
        return str(output_payload), "output.txt", "text/plain"

    raise ValueError(f"Unsupported task output format: {format_type}")


def compact_task_output_for_storage(
    output_payload: Any,
    *,
    output_attachment_path: str,
    status: str = "ok",
    error_message: Optional[str] = None,
) -> str:
    if not output_attachment_path:
        raise ValueError("output_attachment_path is required")

    compact_payload: Dict[str, Any] = {
        "status": status,
        "output_compacted": True,
        "preview": _task_output_preview_from_payload(output_payload),
        "output_attachment": output_attachment_path,
    }
    if error_message:
        compact_payload["error"] = error_message
    return json.dumps(compact_payload)


def persist_task_output_artifact(
    *,
    task_id: str,
    output_payload: Any,
    format_type: str,
    existing_attached_files: Optional[List[str]] = None,
    status: str = "ok",
    error_message: Optional[str] = None,
    bucket_name: Optional[str] = None,
    uploader: Optional[Callable[..., str]] = None,
) -> Tuple[str, List[str], str]:
    """
    Persist full task output as a task attachment and return a compact inline envelope.

    This is the only supported task-output storage path. The full payload never
    belongs inline in DynamoDB.
    """
    if not task_id:
        raise ValueError("task_id is required to persist task output artifacts.")

    resolved_bucket_name = bucket_name or os.getenv(TASK_OUTPUT_ATTACHMENT_BUCKET_ENV)
    if not resolved_bucket_name:
        raise RuntimeError(
            f"{TASK_OUTPUT_ATTACHMENT_BUCKET_ENV} is required to persist task output attachments."
        )

    serialized_payload, attachment_name, content_type = _serialize_task_output_payload(
        output_payload,
        format_type=format_type,
    )
    attachment_key = f"tasks/{task_id}/{attachment_name}"
    resolved_uploader = uploader or upload_task_attachment_bytes
    uploaded_key = resolved_uploader(
        bucket_name=resolved_bucket_name,
        key=attachment_key,
        body=serialized_payload.encode("utf-8"),
        content_type=content_type,
    )
    if not uploaded_key:
        raise RuntimeError("Task output attachment uploader returned an empty key.")

    attached_files = _normalize_attached_files(existing_attached_files)
    if uploaded_key not in attached_files:
        attached_files.append(uploaded_key)

    compact_output = compact_task_output_for_storage(
        output_payload,
        output_attachment_path=uploaded_key,
        status=status,
        error_message=error_message,
    )
    return compact_output, attached_files, uploaded_key
