from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from plexus.storage.graphql_artifact_store import ArtifactTransferRequest, GraphQLArtifactStore


TASK_OUTPUT_PREVIEW_CHARS = 800


def _normalize_attached_files(existing_attached_files: Optional[List[str]]) -> List[str]:
    normalized: List[str] = []
    for path in existing_attached_files or []:
        if isinstance(path, str) and path not in normalized:
            normalized.append(path)
    return normalized


def _artifact_store(*, client: Any = None, artifact_store: Optional[GraphQLArtifactStore] = None) -> GraphQLArtifactStore:
    if artifact_store is not None:
        return artifact_store
    if client is None:
        raise ValueError("client or artifact_store is required for task attachment persistence.")
    return GraphQLArtifactStore(client)


def upload_task_attachment_bytes(
    *,
    task_id: str,
    filename: str,
    body: bytes,
    content_type: str,
    client: Any = None,
    artifact_store: Optional[GraphQLArtifactStore] = None,
) -> Dict[str, Any]:
    """Upload a task attachment through an application-authorized HTTPS ticket."""
    if not task_id:
        raise ValueError("task_id is required for task attachment upload.")
    if not filename:
        raise ValueError("filename is required for task attachment upload.")
    if not isinstance(body, bytes) or not body:
        raise ValueError("body must be non-empty bytes for task attachment upload.")

    request = ArtifactTransferRequest(
        operation="WRITE",
        resource_type="TASK",
        resource_id=task_id,
        artifact_type="TASK_ATTACHMENT",
        filename=filename,
        content_type=content_type,
        size_bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )
    return _artifact_store(client=client, artifact_store=artifact_store).upload_bytes(request, body)


def _task_output_preview_from_payload(output_payload: Any) -> Dict[str, Any]:
    if isinstance(output_payload, dict):
        preview: Dict[str, Any] = {}
        for key in (
            "status", "type", "summary", "message", "error", "decision", "accuracy", "score", "scorecard",
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


def _serialize_task_output_payload(output_payload: Any, *, format_type: str) -> Tuple[str, str, str]:
    normalized_format = (format_type or "json").lower()
    if normalized_format == "json":
        return json.dumps(output_payload, indent=2, ensure_ascii=False, default=str), "output.json", "application/json"
    if normalized_format in {"yaml", "yml"}:
        return str(output_payload), "output.yaml", "text/yaml"
    if normalized_format == "txt":
        return str(output_payload), "output.txt", "text/plain"
    raise ValueError(f"Unsupported task output format: {format_type}")


def compact_task_output_for_storage(
    output_payload: Any, *, output_attachment_path: str, status: str = "ok", error_message: Optional[str] = None,
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
    client: Any = None,
    artifact_store: Optional[GraphQLArtifactStore] = None,
) -> Tuple[str, List[str], str]:
    """Persist full task output as a GraphQL-authorized attachment and compact envelope."""
    if not task_id:
        raise ValueError("task_id is required to persist task output artifacts.")
    serialized_payload, attachment_name, content_type = _serialize_task_output_payload(output_payload, format_type=format_type)
    metadata = upload_task_attachment_bytes(
        task_id=task_id,
        filename=attachment_name,
        body=serialized_payload.encode("utf-8"),
        content_type=content_type,
        client=client,
        artifact_store=artifact_store,
    )
    uploaded_key = metadata.get("_s3_key")
    if not isinstance(uploaded_key, str) or not uploaded_key:
        raise RuntimeError("Task output artifact store returned an empty object key.")
    attached_files = _normalize_attached_files(existing_attached_files)
    if uploaded_key not in attached_files:
        attached_files.append(uploaded_key)
    return (
        compact_task_output_for_storage(output_payload, output_attachment_path=uploaded_key, status=status, error_message=error_message),
        attached_files,
        uploaded_key,
    )
