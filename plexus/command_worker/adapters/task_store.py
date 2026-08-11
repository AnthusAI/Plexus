"""Task-backed portable command repository and lifecycle adapter.

``TaskStoreGateway`` is the boundary implemented by the dashboard Task data
service.  Its mutations are conditional mutations of one Task record (and its
authoritative lifecycle), never a projection of another command record.
TaskStages are separate UI detail written by command executors.  The in-memory
gateway is deliberately a local proof double; production gateways must provide
the same atomic operations against the Task store.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Protocol

from ..models import (
    AnnouncementResult,
    CancellationResult,
    Claim,
    CommandEnvelope,
    CommandRecord,
    JSONValue,
    ProgressUpdate,
    RequestDigest,
    CommandStatus,
    AnnouncementDisposition,
)
from ..models import _thaw_json
from ..ports import ClaimStatus, CommandRepository, LifecycleStore


class TaskStoreGateway(Protocol):
    """Atomic Task-store operations required by the portable lifecycle."""

    def announce_task(
        self, command: CommandRecord, task_fields: Mapping[str, object]
    ) -> AnnouncementResult: ...

    def get_command(self, tenant_id: str, command_id: str) -> CommandRecord | None: ...

    def get_task(self, command_id: str) -> Any | None: ...

    def request_task_cancel(
        self, tenant_id: str, command_id: str, now: datetime
    ) -> CancellationResult | None: ...

    def claim_task(
        self,
        envelope: CommandEnvelope,
        owner: str,
        now: datetime,
        lease_duration: timedelta,
    ) -> Claim | ClaimStatus: ...

    def progress_task(
        self, command_id: str, token: str, progress: ProgressUpdate, now: datetime
    ) -> bool: ...

    def renew_task(
        self, command_id: str, token: str, now: datetime, lease_duration: timedelta
    ) -> Claim | None: ...

    def complete_task(
        self, command_id: str, token: str, result: JSONValue, now: datetime
    ) -> bool: ...

    def fail_task(
        self, command_id: str, token: str, error: str, now: datetime
    ) -> bool: ...

    def finalize_task_cancel(
        self, command_id: str, token: str, now: datetime
    ) -> bool: ...


_TASK_FIELDS = """
id accountId type status target command dispatchStatus
idempotencyKey idempotencyNamespace submittedBy idempotencyDigest
digestAlgorithm digestCanonicalizationVersion lifecycleStatus leaseOwner
leaseExpiresAt fencingToken cancellationRequestedAt progressFraction
progressMessage progressDetails commandResult commandPayload createdAt updatedAt
startedAt completedAt errorMessage metadata
"""


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _awsjson(value: Any) -> str:
    """Encode a JSON value for Amplify's AWSJSON GraphQL input scalar."""

    return json.dumps(
        _thaw_json(value), ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValueError("Task timestamp is missing or invalid")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _field(result: Any, name: str) -> Any:
    if not isinstance(result, Mapping):
        return None
    data = result.get("data")
    if isinstance(data, Mapping) and name in data:
        return data[name]
    return result.get(name)


def _conditional_failure(result: Any) -> bool:
    if not isinstance(result, Mapping):
        return False
    for error in result.get("errors") or []:
        if isinstance(error, Mapping) and "condition" in (
            f"{error.get('errorType', '')} {error.get('message', '')}".lower()
        ):
            return True
    return False


def _conditional_exception(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "conditional request failed" in message or "conditionalcheckfailed" in message
    )


class GraphQLTaskStoreGateway:
    """Task-only lifecycle gateway using AppSync generated model mutations.

    The task id is the idempotency identity.  Conditional failures are normal
    contention signals; every such path reloads the single Task record rather
    than consulting or creating a secondary command index.
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    def _execute(self, document: str, variables: Mapping[str, Any]) -> Any:
        try:
            result = self._client.execute(document, dict(variables))
        except Exception as error:
            if _conditional_exception(error):
                return {"errors": [{"message": str(error)}]}
            raise
        if (
            isinstance(result, Mapping)
            and result.get("errors")
            and not _conditional_failure(result)
        ):
            raise RuntimeError(f"Task GraphQL operation failed: {result['errors']}")
        return result

    def _get_raw(self, command_id: str) -> Mapping[str, Any] | None:
        result = self._execute(
            f"query GetTask($id: ID!) {{ getTask(id: $id) {{ {_TASK_FIELDS} }} }}",
            {"id": command_id},
        )
        value = _field(result, "getTask")
        return value if isinstance(value, Mapping) else None

    def get_task(self, command_id: str) -> Any | None:
        return self._get_raw(command_id)

    @staticmethod
    def _record(task: Mapping[str, Any]) -> CommandRecord:
        payload = task.get("commandPayload")
        if isinstance(payload, str):
            for _ in range(2):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError as error:
                    raise ValueError("Task commandPayload JSON is invalid") from error
                if not isinstance(payload, str):
                    break
        if not isinstance(payload, Mapping):
            raise ValueError("Task commandPayload is missing or invalid")
        digest = RequestDigest(
            str(task.get("digestAlgorithm")),
            int(task.get("digestCanonicalizationVersion")),
            str(task.get("idempotencyDigest")),
        )
        status = CommandStatus(str(task.get("lifecycleStatus")))
        record = CommandRecord(
            command_id=str(task["id"]),
            tenant_id=str(task["accountId"]),
            target=str(task["target"]),
            idempotency_key=str(task["idempotencyKey"]),
            idempotency_namespace=str(task["idempotencyNamespace"]),
            created_at=_parse_timestamp(task["createdAt"]),
            updated_at=_parse_timestamp(task.get("updatedAt") or task["createdAt"]),
            submitted_by=str(task["submittedBy"]),
            payload=payload,
            status=status,
            request_digest=digest,
        )
        # Constructor verifies the digest against the exact persisted payload.
        return record

    def get_command(self, tenant_id: str, command_id: str) -> CommandRecord | None:
        task = self._get_raw(command_id)
        if task is None or task.get("accountId") != tenant_id:
            return None
        return self._record(task)

    def announce_task(
        self, command: CommandRecord, task_fields: Mapping[str, object]
    ) -> AnnouncementResult:
        input_data = {
            **task_fields,
            "id": command.command_id,
            "status": "PENDING",
            "target": command.target,
            "dispatchStatus": "READY",
            "lifecycleStatus": CommandStatus.ANNOUNCED.value,
            # Account identity comes from authenticated command context via
            # CommandRecord. Never trust a caller-provided Task accountId.
            "accountId": command.tenant_id,
            "submittedBy": command.submitted_by,
            "idempotencyNamespace": command.idempotency_namespace,
            "idempotencyKey": command.idempotency_key,
            "idempotencyDigest": command.request_digest.value,
            "digestAlgorithm": command.request_digest.algorithm,
            "digestCanonicalizationVersion": command.request_digest.canonicalization_version,
            "commandPayload": _awsjson(command.payload),
            "fencingToken": 0,
            "createdAt": _timestamp(command.created_at),
            "updatedAt": _timestamp(command.updated_at),
        }
        # Required dashboard display fields remain caller-owned, but durable
        # command identity always comes from the authenticated command record.
        result = self._execute(
            f"mutation CreateTask($input: CreateTaskInput!, $condition: ModelTaskConditionInput) {{ createTask(input: $input, condition: $condition) {{ {_TASK_FIELDS} }} }}",
            {"input": input_data, "condition": {"id": {"attributeExists": False}}},
        )
        created = _field(result, "createTask")
        if isinstance(created, Mapping):
            return AnnouncementResult(
                self._record(created), AnnouncementDisposition.NEW
            )
        if not _conditional_failure(result):
            raise RuntimeError("Task create returned no task")
        existing = self._get_raw(command.command_id)
        if existing is None:
            raise RuntimeError("Task create conflicted but the Task could not be read")
        record = self._record(existing)
        return AnnouncementResult(
            record,
            (
                AnnouncementDisposition.EXISTING
                if record.request_digest == command.request_digest
                else AnnouncementDisposition.CONFLICT
            ),
        )

    def _update(
        self, command_id: str, updates: Mapping[str, Any], condition: Mapping[str, Any]
    ) -> Mapping[str, Any] | None:
        result = self._execute(
            f"mutation UpdateTask($input: UpdateTaskInput!, $condition: ModelTaskConditionInput) {{ updateTask(input: $input, condition: $condition) {{ {_TASK_FIELDS} }} }}",
            {"input": {"id": command_id, **updates}, "condition": condition},
        )
        value = _field(result, "updateTask")
        return value if isinstance(value, Mapping) else None

    def request_task_cancel(
        self, tenant_id: str, command_id: str, now: datetime
    ) -> CancellationResult | None:
        task = self._get_raw(command_id)
        if task is None or task.get("accountId") != tenant_id:
            return None
        record = self._record(task)
        if record.status.is_terminal or record.status is CommandStatus.CANCEL_REQUESTED:
            return CancellationResult(record, False)
        if record.status is CommandStatus.ANNOUNCED:
            updates = {
                "lifecycleStatus": "CANCELLED",
                "status": "CANCELLED",
                "dispatchStatus": "CANCELLED",
                "completedAt": _timestamp(now),
                "updatedAt": _timestamp(now),
            }
        else:
            updates = {
                "lifecycleStatus": "CANCEL_REQUESTED",
                "cancellationRequestedAt": _timestamp(now),
                "updatedAt": _timestamp(now),
            }
        changed = self._update(
            command_id, updates, {"lifecycleStatus": {"eq": record.status.value}}
        )
        if changed is None:
            refreshed = self.get_command(tenant_id, command_id)
            return CancellationResult(refreshed, False) if refreshed else None
        return CancellationResult(self._record(changed), True)

    def _verified(self, envelope: CommandEnvelope) -> Mapping[str, Any] | None:
        task = self._get_raw(envelope.command_id)
        if task is None:
            return None
        try:
            record = self._record(task)
        except (KeyError, TypeError, ValueError):
            return None
        return task if record.envelope == envelope else None

    def _claim_from_task(self, task: Mapping[str, Any]) -> Claim:
        return Claim(
            str(task["fencingToken"]),
            str(task["leaseOwner"]),
            _parse_timestamp(task["leaseExpiresAt"]),
            task.get("lifecycleStatus") == "CANCEL_REQUESTED",
        )

    def claim_task(
        self,
        envelope: CommandEnvelope,
        owner: str,
        now: datetime,
        lease_duration: timedelta,
    ) -> Claim | ClaimStatus:
        task = self._verified(envelope)
        if task is None:
            return ClaimStatus.INTEGRITY_MISMATCH
        status = task.get("lifecycleStatus")
        if status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return ClaimStatus.TERMINAL
        expires = (
            _parse_timestamp(task["leaseExpiresAt"])
            if task.get("leaseExpiresAt")
            else None
        )
        if status == "CANCEL_REQUESTED":
            if expires and expires > now:
                return ClaimStatus.ACTIVE
            settled = self._update(
                envelope.command_id,
                {
                    "lifecycleStatus": "CANCELLED",
                    "status": "CANCELLED",
                    "completedAt": _timestamp(now),
                    "leaseOwner": None,
                    "leaseExpiresAt": None,
                    "updatedAt": _timestamp(now),
                },
                {
                    "lifecycleStatus": {"eq": "CANCEL_REQUESTED"},
                    "fencingToken": {"eq": task.get("fencingToken")},
                },
            )
            return ClaimStatus.TERMINAL if settled is not None else ClaimStatus.ACTIVE
        if status == "RUNNING" and expires and expires > now:
            return ClaimStatus.ACTIVE
        fence = int(task.get("fencingToken") or 0) + 1
        updated = self._update(
            envelope.command_id,
            {
                "lifecycleStatus": "RUNNING",
                "status": "RUNNING",
                "leaseOwner": owner,
                "leaseExpiresAt": _timestamp(now + lease_duration),
                "fencingToken": fence,
                "startedAt": task.get("startedAt") or _timestamp(now),
                "updatedAt": _timestamp(now),
            },
            {
                "or": [
                    {"lifecycleStatus": {"eq": "ANNOUNCED"}},
                    {
                        "and": [
                            {"lifecycleStatus": {"eq": "RUNNING"}},
                            {"leaseExpiresAt": {"le": _timestamp(now)}},
                        ]
                    },
                ],
                "fencingToken": {"eq": task.get("fencingToken") or 0},
            },
        )
        if updated is None:
            return ClaimStatus.ACTIVE
        return self._claim_from_task(updated)

    def _fenced_update(
        self,
        command_id: str,
        token: str,
        now: datetime,
        updates: Mapping[str, Any],
        statuses: tuple[str, ...] = ("RUNNING",),
    ) -> Mapping[str, Any] | None:
        return self._update(
            command_id,
            {**updates, "updatedAt": _timestamp(now)},
            {
                "fencingToken": {"eq": int(token)},
                "leaseExpiresAt": {"gt": _timestamp(now)},
                "or": [{"lifecycleStatus": {"eq": status}} for status in statuses],
            },
        )

    def progress_task(
        self, command_id: str, token: str, progress: ProgressUpdate, now: datetime
    ) -> bool:
        return (
            self._fenced_update(
                command_id,
                token,
                now,
                {
                    "progressFraction": progress.fraction,
                    "progressMessage": progress.message,
                    "progressDetails": (
                        _awsjson(progress.details) if progress.details else None
                    ),
                },
            )
            is not None
        )

    def renew_task(
        self, command_id: str, token: str, now: datetime, lease_duration: timedelta
    ) -> Claim | None:
        updated = self._fenced_update(
            command_id,
            token,
            now,
            {"leaseExpiresAt": _timestamp(now + lease_duration)},
            ("RUNNING", "CANCEL_REQUESTED"),
        )
        return self._claim_from_task(updated) if updated else None

    def _settle(
        self,
        command_id: str,
        token: str,
        now: datetime,
        lifecycle: str,
        status: str,
        **fields: Any,
    ) -> bool:
        return (
            self._fenced_update(
                command_id,
                token,
                now,
                {
                    "lifecycleStatus": lifecycle,
                    "status": status,
                    "completedAt": _timestamp(now),
                    "leaseOwner": None,
                    "leaseExpiresAt": None,
                    **fields,
                },
                ("RUNNING", "CANCEL_REQUESTED"),
            )
            is not None
        )

    def complete_task(
        self, command_id: str, token: str, result: JSONValue, now: datetime
    ) -> bool:
        return self._settle(
            command_id,
            token,
            now,
            "SUCCEEDED",
            "COMPLETED",
            commandResult=_awsjson(result),
        )

    def fail_task(self, command_id: str, token: str, error: str, now: datetime) -> bool:
        return self._settle(
            command_id, token, now, "FAILED", "FAILED", errorMessage=error
        )

    def finalize_task_cancel(self, command_id: str, token: str, now: datetime) -> bool:
        return self._settle(command_id, token, now, "CANCELLED", "CANCELLED")


class TaskBackedCommandStore(CommandRepository, LifecycleStore):
    """One-store adapter: Task is both command record and lifecycle record."""

    def __init__(
        self, gateway: TaskStoreGateway, task_fields: Mapping[str, object]
    ) -> None:
        self._gateway = gateway
        self._task_fields = task_fields

    def announce(self, command: CommandRecord) -> AnnouncementResult:
        return self._gateway.announce_task(command, self._task_fields)

    def get(self, tenant_id: str, command_id: str) -> CommandRecord | None:
        return self._gateway.get_command(tenant_id, command_id)

    def request_cancel(
        self, tenant_id: str, command_id: str, now: datetime
    ) -> CancellationResult | None:
        return self._gateway.request_task_cancel(tenant_id, command_id, now)

    def claim(
        self,
        envelope: CommandEnvelope,
        owner: str,
        now: datetime,
        lease_duration: timedelta,
    ) -> Claim | ClaimStatus:
        return self._gateway.claim_task(envelope, owner, now, lease_duration)

    def report_progress(
        self, command_id: str, token: str, progress: ProgressUpdate, now: datetime
    ) -> bool:
        return self._gateway.progress_task(command_id, token, progress, now)

    def renew(
        self, command_id: str, token: str, now: datetime, lease_duration: timedelta
    ) -> Claim | None:
        return self._gateway.renew_task(command_id, token, now, lease_duration)

    def complete(
        self, command_id: str, token: str, result: JSONValue, now: datetime
    ) -> bool:
        return self._gateway.complete_task(command_id, token, result, now)

    def fail(self, command_id: str, token: str, error: str, now: datetime) -> bool:
        return self._gateway.fail_task(command_id, token, error, now)

    def finalize_cancel(self, command_id: str, token: str, now: datetime) -> bool:
        return self._gateway.finalize_task_cancel(command_id, token, now)
