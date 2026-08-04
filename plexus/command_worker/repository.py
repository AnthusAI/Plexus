"""Provider-neutral in-memory reference semantics for command repositories."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from threading import RLock

from .models import (
    AnnouncementDisposition,
    AnnouncementResult,
    CancellationResult,
    CommandEnvelope,
    CommandRecord,
    CommandStatus,
)


class InMemoryCommandRepository:
    """Thread-safe executable reference for the CommandRepository contract."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._commands: dict[str, CommandRecord] = {}
        self._idempotency: dict[tuple[str, str, str, str], str] = {}
        self._discoverable: dict[str, CommandEnvelope] = {}

    def announce(self, command: CommandRecord) -> AnnouncementResult:
        with self._lock:
            key = (
                command.tenant_id,
                command.submitted_by,
                command.idempotency_namespace,
                command.idempotency_key,
            )
            existing_id = self._idempotency.get(key)
            if existing_id is not None:
                existing = self._commands[existing_id]
                disposition = (
                    AnnouncementDisposition.EXISTING
                    if existing.request_digest == command.request_digest
                    else AnnouncementDisposition.CONFLICT
                )
                return AnnouncementResult(existing, disposition)

            if command.command_id in self._commands:
                raise ValueError("command_id already exists")
            self._commands[command.command_id] = command
            self._idempotency[key] = command.command_id
            self._discoverable[command.command_id] = command.envelope
            return AnnouncementResult(command, AnnouncementDisposition.NEW)

    def get(self, tenant_id: str, command_id: str) -> CommandRecord | None:
        with self._lock:
            command = self._commands.get(command_id)
            if command is None or command.tenant_id != tenant_id:
                return None
            return command

    def request_cancel(
        self, tenant_id: str, command_id: str, now: datetime
    ) -> CancellationResult | None:
        with self._lock:
            command = self._commands.get(command_id)
            if command is None or command.tenant_id != tenant_id:
                return None
            if command.status is CommandStatus.ANNOUNCED:
                updated = replace(
                    command, status=CommandStatus.CANCELLED, updated_at=now
                )
                self._discoverable.pop(command_id, None)
            elif command.status is CommandStatus.RUNNING:
                updated = replace(
                    command, status=CommandStatus.CANCEL_REQUESTED, updated_at=now
                )
            else:
                return CancellationResult(command, changed=False)
            self._commands[command_id] = updated
            return CancellationResult(updated, changed=True)

    def discoverable_dispatches(self) -> tuple[CommandEnvelope, ...]:
        with self._lock:
            return tuple(self._discoverable.values())

    def set_status(
        self, tenant_id: str, command_id: str, status: CommandStatus
    ) -> CommandRecord:
        """Advance status in reference integration tests and future adapter tests."""

        with self._lock:
            command = self.get(tenant_id, command_id)
            if command is None:
                raise LookupError(command_id)
            allowed = {
                CommandStatus.ANNOUNCED: {
                    CommandStatus.RUNNING,
                    CommandStatus.SUCCEEDED,
                    CommandStatus.FAILED,
                    CommandStatus.CANCELLED,
                },
                CommandStatus.RUNNING: {
                    CommandStatus.SUCCEEDED,
                    CommandStatus.FAILED,
                    CommandStatus.CANCEL_REQUESTED,
                    CommandStatus.CANCELLED,
                },
                CommandStatus.CANCEL_REQUESTED: {
                    CommandStatus.SUCCEEDED,
                    CommandStatus.FAILED,
                    CommandStatus.CANCELLED,
                },
            }
            if status is not command.status and status not in allowed.get(
                command.status, set()
            ):
                raise ValueError("command status transition is not allowed")
            updated = replace(command, status=status)
            self._commands[command_id] = updated
            if status is not CommandStatus.ANNOUNCED:
                self._discoverable.pop(command_id, None)
            return updated
