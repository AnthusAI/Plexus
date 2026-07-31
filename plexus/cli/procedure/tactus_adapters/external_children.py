"""Fail-closed host resolution for durable optimizer child procedures.

Tactus owns the checkpointed external-child request and waiting semantics. This
adapter owns only the Plexus side of that contract: exact GraphQL reads of the
already-persisted Procedure and Task identities, physical/immutable identity
validation, and a compact child snapshot for the next replay.
"""

from __future__ import annotations

import json
from typing import Any, Mapping


_SUCCESS_STATUSES = frozenset({"COMPLETED", "SUCCEEDED", "SUCCESS"})
_FAILED_STATUSES = frozenset({"FAILED", "ERROR", "CANCELLED", "CANCELED"})
_TERMINAL_STATUSES = _SUCCESS_STATUSES | _FAILED_STATUSES
_REQUIRED_REFERENCE_FIELDS = (
    "id",
    "procedure_id",
    "task_id",
    "scorecard_id",
    "score_id",
)


def _metadata(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, Mapping):
            return dict(parsed)
    return None


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


class OptimizerExternalChildResolver:
    """Resolve exact, persisted optimizer children without account scans.

    A malformed/missing/mismatched record is an incomplete child, never a
    substitute identity and never a success. Failed or cancelled children are
    terminal only after both indexed records corroborate the same immutable
    launch identity.
    """

    def __init__(self, *, backend: Any, account_id: str) -> None:
        if not _text(account_id):
            raise ValueError("account_id is required")
        if not callable(getattr(backend, "get_procedure", None)):
            raise TypeError("backend must provide exact get_procedure")
        if not callable(getattr(backend, "get_task", None)):
            raise TypeError("backend must provide exact get_task")
        self._backend = backend
        self._account_id = str(account_id)

    def __call__(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping) or not isinstance(request.get("children"), list):
            raise ValueError("external child wait request requires a children list")
        snapshots = [self._resolve_child(child) for child in request["children"]]
        return {"children": snapshots, "complete": all(row["terminal"] for row in snapshots)}

    def _resolve_child(self, reference: Any) -> dict[str, Any]:
        child_id = _text(reference.get("id")) if isinstance(reference, Mapping) else ""
        if not isinstance(reference, Mapping) or any(not _text(reference.get(key)) for key in _REQUIRED_REFERENCE_FIELDS):
            return self._incomplete(child_id, "malformed_child_reference")
        normalized = {key: _text(reference.get(key)) for key in _REQUIRED_REFERENCE_FIELDS}
        try:
            procedure = self._backend.get_procedure(normalized["procedure_id"])
            task = self._backend.get_task(normalized["task_id"])
        except Exception:
            return self._incomplete(normalized["id"], "child_read_failed")
        if not isinstance(procedure, Mapping) or not isinstance(task, Mapping):
            return self._incomplete(normalized["id"], "child_not_found")
        procedure = dict(procedure)
        task = dict(task)
        if not self._identity_matches(normalized, procedure, task):
            return self._incomplete(normalized["id"], "child_identity_mismatch")

        procedure_status = _text(procedure.get("status")).upper()
        task_status = _text(task.get("status")).upper()
        snapshot = {
            "id": normalized["id"],
            "procedure_id": normalized["procedure_id"],
            "task_id": normalized["task_id"],
            "scorecard_id": normalized["scorecard_id"],
            "score_id": normalized["score_id"],
            "procedure": procedure,
            "task": task,
        }
        if procedure_status not in _TERMINAL_STATUSES or task_status not in _TERMINAL_STATUSES:
            return {**snapshot, "terminal": False, "success": False, "state": "running"}
        if procedure_status not in _SUCCESS_STATUSES or task_status not in _SUCCESS_STATUSES:
            return {
                **snapshot,
                "terminal": True,
                "success": False,
                "state": "failed_or_incomplete",
                "reason": "terminal_child_failed",
            }
        artifacts = self._optimizer_artifacts(procedure, normalized["task_id"])
        if artifacts is None:
            return {
                **snapshot,
                "terminal": False,
                "success": False,
                "state": "incomplete",
                "reason": "missing_optimizer_result_evidence",
            }
        return {
            **snapshot,
            "terminal": True,
            "success": True,
            "state": "completed",
            "optimizer_artifacts": artifacts,
        }

    def _identity_matches(
        self,
        reference: Mapping[str, str],
        procedure: Mapping[str, Any],
        task: Mapping[str, Any],
    ) -> bool:
        if procedure.get("id") != reference["procedure_id"] or task.get("id") != reference["task_id"]:
            return False
        expected = {
            "accountId": self._account_id,
            "scorecardId": reference["scorecard_id"],
            "scoreId": reference["score_id"],
        }
        if any(procedure.get(key) != value or task.get(key) != value for key, value in expected.items()):
            return False
        procedure_metadata = _metadata(procedure.get("metadata"))
        task_metadata = _metadata(task.get("metadata"))
        if procedure_metadata is None or task_metadata is None:
            return False
        launch_spec = procedure_metadata.get("optimizer_launch_spec")
        if not isinstance(launch_spec, Mapping):
            return False
        if task_metadata.get("optimizer_launch_spec") != launch_spec:
            return False
        if launch_spec.get("identity") != reference["id"]:
            return False
        if any(launch_spec.get(field) != expected_value for field, expected_value in (
            ("account_id", self._account_id),
            ("scorecard_id", reference["scorecard_id"]),
            ("score_id", reference["score_id"]),
        )):
            return False
        if task_metadata.get("optimizer_launch_identity") != reference["id"]:
            return False
        procedure_id = reference["procedure_id"]
        if (
            task_metadata.get("procedure_id") != procedure_id
            or task.get("target") != f"procedure/{procedure_id}"
            or task.get("command") != f"procedure run {procedure_id}"
        ):
            return False
        code_artifact = procedure_metadata.get("code_artifact")
        if not isinstance(code_artifact, Mapping):
            return False
        expected_code_key = f"procedures/{procedure_id}/code.tac"
        if (
            code_artifact.get("key") != expected_code_key
            or code_artifact.get("_s3_key") != expected_code_key
            or code_artifact.get("sha256") != launch_spec.get("optimizer_yaml_sha256")
        ):
            return False
        return True

    @staticmethod
    def _optimizer_artifacts(procedure: Mapping[str, Any], task_id: str) -> dict[str, Any] | None:
        """Return a verified optimizer-result index owned by its Procedure.

        The optimizer indexer persists this pointer in ``Procedure.metadata``.
        A Task is the execution record, not the authority for the result
        artifact pointer; accepting a Task-local lookalike would let unrelated
        output make a completed child appear reviewable.
        """
        metadata = _metadata(procedure.get("metadata"))
        pointer = metadata.get("optimizer_artifacts") if metadata else None
        if not isinstance(pointer, Mapping):
            return None
        result = dict(pointer)
        if (
            result.get("schema_version") != 1
            or not _text(result.get("indexed_at"))
            or result.get("task_id") != task_id
        ):
            return None
        expected = {
            "manifest": f"tasks/{task_id}/optimizer/manifest.json",
            "events": f"tasks/{task_id}/optimizer/events.jsonl",
            "runtime_log": f"tasks/{task_id}/optimizer/runtime.log",
        }
        if any(result.get(key) != value for key, value in expected.items()):
            return None
        artifact_metadata = result.get("artifact_metadata")
        if not isinstance(artifact_metadata, Mapping):
            return None
        expected_content_types = {
            "manifest": "application/json",
            "events": "application/x-ndjson",
            "runtime_log": "text/plain",
        }
        for name, path in expected.items():
            descriptor = artifact_metadata.get(name)
            if not isinstance(descriptor, Mapping):
                return None
            digest = descriptor.get("sha256")
            if (
                descriptor.get("_s3_key") != path
                or not isinstance(descriptor.get("size_bytes"), int)
                or descriptor["size_bytes"] < 1
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest.lower())
                or descriptor.get("content_type") != expected_content_types[name]
            ):
                return None
        return result

    @staticmethod
    def _incomplete(child_id: str, reason: str) -> dict[str, Any]:
        return {
            "id": child_id,
            "terminal": False,
            "success": False,
            "state": "incomplete",
            "reason": reason,
        }
