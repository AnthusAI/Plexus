"""Observable one-Task-store proof for portable command lifecycle."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plexus.command_worker import (
    ClaimStatus,
    CommandEnvelope,
    CommandRecord,
    CommandStatus,
    ProgressUpdate,
    request_digest,
)
from plexus.command_worker.adapters.task_store import TaskBackedCommandStore
from plexus.command_worker.models import (
    AnnouncementDisposition,
    AnnouncementResult,
    CancellationResult,
)

NOW = datetime(2026, 8, 6, tzinfo=timezone.utc)


class TaskGateway:
    """Local Task-store gateway; every record below is a subscription-visible Task."""

    def __init__(self) -> None:
        self.tasks: dict[str, dict[str, object]] = {}
        self._keys: dict[tuple[str, str, str, str], str] = {}
        self.fail_next_create = False

    def announce_task(self, command, task_fields):
        if self.fail_next_create:
            self.fail_next_create = False
            raise RuntimeError("Task create failed")
        key = (
            command.tenant_id,
            command.submitted_by,
            command.idempotency_namespace,
            command.idempotency_key,
        )
        existing_id = self._keys.get(key)
        if existing_id:
            existing = self.tasks[existing_id]["command"]
            disposition = (
                AnnouncementDisposition.EXISTING
                if existing.request_digest == command.request_digest
                else AnnouncementDisposition.CONFLICT
            )
            return AnnouncementResult(existing, disposition)
        digest = command.request_digest
        self.tasks[command.command_id] = {
            **task_fields,
            "id": command.command_id,
            "command": command,
            "status": "PENDING",
            "lifecycleStatus": "ANNOUNCED",
            "dispatchStatus": "READY",
            "idempotencyKey": command.idempotency_key,
            "idempotencyDigest": digest.value,
            "digestAlgorithm": digest.algorithm,
            "digestCanonicalizationVersion": digest.canonicalization_version,
            "fencingToken": 0,
            "stages": [
                {
                    "name": "Processing",
                    "status": "PENDING",
                    "processedItems": 0,
                    "totalItems": None,
                }
            ],
        }
        self._keys[key] = command.command_id
        return AnnouncementResult(command, AnnouncementDisposition.NEW)

    def get_command(self, tenant_id, command_id):
        task = self.tasks.get(command_id)
        if task is None or task["command"].tenant_id != tenant_id:
            return None
        return task["command"]

    def get_task(self, command_id):
        return self.tasks.get(command_id)

    def request_task_cancel(self, tenant_id, command_id, now):
        command = self.get_command(tenant_id, command_id)
        if command is None:
            return None
        task = self.tasks[command_id]
        if command.status is CommandStatus.ANNOUNCED:
            updated = replace(command, status=CommandStatus.CANCELLED, updated_at=now)
            task.update(
                command=updated,
                status="CANCELLED",
                lifecycleStatus="CANCELLED",
                dispatchStatus="CANCELLED",
                completedAt=now,
            )
        elif command.status is CommandStatus.RUNNING:
            updated = replace(
                command, status=CommandStatus.CANCEL_REQUESTED, updated_at=now
            )
            task.update(
                command=updated,
                lifecycleStatus="CANCEL_REQUESTED",
                cancellationRequestedAt=now,
            )
        else:
            return CancellationResult(command, False)
        return CancellationResult(updated, True)

    def claim_task(self, envelope, owner, now, lease_duration):
        task = self.tasks.get(envelope.command_id)
        if task is None or task["command"].envelope != envelope:
            return ClaimStatus.INTEGRITY_MISMATCH
        command = task["command"]
        if command.status in {
            CommandStatus.SUCCEEDED,
            CommandStatus.FAILED,
            CommandStatus.CANCELLED,
            CommandStatus.CANCEL_REQUESTED,
        }:
            return ClaimStatus.TERMINAL
        if command.status is CommandStatus.RUNNING and task["leaseExpiresAt"] > now:
            return ClaimStatus.ACTIVE
        token = str(int(task["fencingToken"]) + 1)
        updated = replace(command, status=CommandStatus.RUNNING, updated_at=now)
        task.update(
            command=updated,
            status="RUNNING",
            lifecycleStatus="RUNNING",
            fencingToken=int(token),
            leaseOwner=owner,
            leaseExpiresAt=now + lease_duration,
            startedAt=now,
        )
        stage = task["stages"][0]
        stage.update(status="RUNNING", startedAt=now)
        return self._claim(task)

    def _fenced(self, command_id, token, now, allowed):
        task = self.tasks.get(command_id)
        return (
            task
            if task
            and str(task["fencingToken"]) == token
            and task["command"].status in allowed
            and task["leaseExpiresAt"] > now
            else None
        )

    def _claim(self, task):
        return __import__("plexus.command_worker", fromlist=["Claim"]).Claim(
            str(task["fencingToken"]),
            task["leaseOwner"],
            task["leaseExpiresAt"],
            task["command"].status is CommandStatus.CANCEL_REQUESTED,
        )

    def progress_task(self, command_id, token, progress, now):
        task = self._fenced(command_id, token, now, {CommandStatus.RUNNING})
        if not task:
            return False
        task.update(
            progressFraction=progress.fraction,
            progressMessage=progress.message,
            progressDetails=progress.details,
        )
        task["stages"][0].update(
            processedItems=round(progress.fraction * 100),
            totalItems=100,
            statusMessage=progress.message,
        )
        return True

    def renew_task(self, command_id, token, now, lease_duration):
        task = self._fenced(
            command_id,
            token,
            now,
            {CommandStatus.RUNNING, CommandStatus.CANCEL_REQUESTED},
        )
        if not task:
            return None
        task["leaseExpiresAt"] = now + lease_duration
        return self._claim(task)

    def _settle(self, command_id, token, now, status, **fields):
        task = self._fenced(
            command_id,
            token,
            now,
            {CommandStatus.RUNNING, CommandStatus.CANCEL_REQUESTED},
        )
        if not task:
            return False
        task.update(
            command=replace(task["command"], status=status, updated_at=now),
            lifecycleStatus=status.value,
            status={
                CommandStatus.SUCCEEDED: "COMPLETED",
                CommandStatus.FAILED: "FAILED",
                CommandStatus.CANCELLED: "CANCELLED",
            }[status],
            completedAt=now,
            **fields,
        )
        task.pop("leaseOwner", None)
        task.pop("leaseExpiresAt", None)
        task["stages"][0].update(status=task["status"], completedAt=now)
        return True

    def complete_task(self, command_id, token, result, now):
        return self._settle(
            command_id, token, now, CommandStatus.SUCCEEDED, commandResult=result
        )

    def fail_task(self, command_id, token, error, now):
        return self._settle(
            command_id, token, now, CommandStatus.FAILED, errorMessage=error
        )

    def finalize_task_cancel(self, command_id, token, now):
        return self._settle(command_id, token, now, CommandStatus.CANCELLED)


def envelope() -> CommandEnvelope:
    return CommandEnvelope(
        2, "task-1", "tenant-1", "evaluate", "key-1", NOW, {"argv": ["evaluate"]}
    )


def store(gateway=None):
    return TaskBackedCommandStore(
        gateway or TaskGateway(),
        {"accountId": "account-1", "type": "evaluate", "target": "evaluate"},
    )


def announce(s, command_id="task-1"):
    e = envelope()
    return s.announce(
        CommandRecord(
            command_id,
            e.tenant_id,
            e.target,
            e.idempotency_key,
            "command.submit:v1",
            NOW,
            NOW,
            "account-1",
            e.payload,
            CommandStatus.ANNOUNCED,
            request_digest(e.target, e.payload),
        )
    )


def test_task_store_fences_lifecycle_and_updates_task_and_stage() -> None:
    gateway = TaskGateway()
    s = store(gateway)
    announce(s)
    first = s.claim(envelope(), "one", NOW, timedelta(minutes=5))
    assert first.token == "1"
    assert s.renew("task-1", first.token, NOW, timedelta(minutes=5)) is not None
    assert s.report_progress("task-1", first.token, ProgressUpdate(0.5, "half"), NOW)
    second = s.claim(
        envelope(), "two", NOW + timedelta(minutes=6), timedelta(minutes=5)
    )
    assert second.token == "2"
    assert not s.complete(
        "task-1", first.token, {"stale": True}, NOW + timedelta(minutes=6)
    )
    assert s.complete("task-1", second.token, {"ok": True}, NOW + timedelta(minutes=6))
    task = gateway.tasks["task-1"]
    assert task["status"] == "COMPLETED" and task["commandResult"] == {"ok": True}
    assert (
        task["stages"][0]["status"] == "COMPLETED" and task["progressFraction"] == 0.5
    )


def test_cancellation_is_task_state_and_current_fence_settles_it() -> None:
    gateway = TaskGateway()
    s = store(gateway)
    announce(s)
    claim = s.claim(envelope(), "one", NOW, timedelta(minutes=5))
    assert s.request_cancel("tenant-1", "task-1", NOW).changed
    assert s.renew(
        "task-1", claim.token, NOW, timedelta(minutes=5)
    ).cancellation_requested
    assert not s.report_progress("task-1", claim.token, ProgressUpdate(0.5), NOW)
    assert s.finalize_cancel("task-1", claim.token, NOW)
    assert gateway.tasks["task-1"]["status"] == "CANCELLED"
