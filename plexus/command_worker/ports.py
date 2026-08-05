"""Provider ports for the portable command-worker runtime."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from typing import Protocol

from .models import (
    AnnouncementResult,
    AuditEvent,
    AuthenticatedCommandContext,
    AuthorizationDecision,
    CancellationResult,
    Claim,
    CommandEnvelope,
    CommandRecord,
    CommandRequest,
    JSONValue,
    ProgressUpdate,
)


class ClaimStatus(str, Enum):
    ACTIVE = "active"
    TERMINAL = "terminal"
    INTEGRITY_MISMATCH = "integrity_mismatch"


class Delivery(Protocol):
    envelope: CommandEnvelope

    def acknowledge(self) -> None: ...

    def release(self) -> None: ...

    def quarantine(self, reason: str) -> None: ...

    def extend_lease(self, duration: timedelta) -> bool: ...


class Transport(Protocol):
    def receive(self, timeout: timedelta) -> Delivery | None: ...


class DrainSignal(Protocol):
    def is_requested(self) -> bool: ...

    def wait(self, timeout: timedelta) -> bool:
        """Wait until draining is requested or the timeout elapses."""

        ...


class LifecycleStore(Protocol):
    """Durable lifecycle and integrity boundary for untrusted envelopes.

    Before issuing a lease, ``claim`` must atomically load durable command state
    and verify command identity, tenant, target, idempotency identity, and the
    canonical payload digest. CANCELLED is terminal even when a broker message
    was published before cancellation. Any mismatch returns INTEGRITY_MISMATCH.
    """

    def claim(
        self,
        envelope: CommandEnvelope,
        owner: str,
        now: datetime,
        lease_duration: timedelta,
    ) -> Claim | ClaimStatus: ...

    def report_progress(
        self,
        command_id: str,
        token: str,
        progress: ProgressUpdate,
        now: datetime,
    ) -> bool: ...

    def renew(
        self,
        command_id: str,
        token: str,
        now: datetime,
        lease_duration: timedelta,
    ) -> Claim | None: ...

    def complete(
        self,
        command_id: str,
        token: str,
        result: JSONValue,
        now: datetime,
    ) -> bool: ...

    def fail(
        self,
        command_id: str,
        token: str,
        error: str,
        now: datetime,
    ) -> bool: ...


class ExecutionContext(Protocol):
    def report_progress(
        self,
        fraction: float,
        message: str | None = None,
        details: dict[str, JSONValue] | None = None,
    ) -> None: ...

    def renew_lease(self) -> Claim: ...

    @property
    def ownership_lost(self) -> bool: ...

    def raise_if_lease_lost(self) -> None: ...


class Executor(Protocol):
    def execute(
        self, envelope: CommandEnvelope, context: ExecutionContext
    ) -> JSONValue: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class CommandIdGenerator(Protocol):
    def new_id(self) -> str: ...


class CommandRepository(Protocol):
    """Atomic persistence boundary for portable command state.

    ``announce`` must atomically resolve the tenant/principal/operation-scoped
    idempotency key,
    durably store a new command, and make that command's dispatch discoverable.
    A caller must never observe durable state without its corresponding dispatch
    eligibility, or dispatch eligibility without durable state.

    ``get`` and ``request_cancel`` are tenant scoped. Implementations must return
    ``None`` both when a command is absent and when it belongs to another tenant.
    ``request_cancel`` atomically applies the cancellation transition and, for an
    ANNOUNCED command, removes dispatch eligibility in the same operation.
    """

    def announce(self, command: CommandRecord) -> AnnouncementResult: ...

    def get(self, tenant_id: str, command_id: str) -> CommandRecord | None: ...

    def request_cancel(
        self, tenant_id: str, command_id: str, now: datetime
    ) -> CancellationResult | None: ...


class CommandAuthorizer(Protocol):
    """Fail-closed policy for authenticated contexts and registered targets."""

    def can_submit(
        self, context: AuthenticatedCommandContext, request: CommandRequest
    ) -> AuthorizationDecision: ...

    def can_read(
        self, context: AuthenticatedCommandContext, command: CommandRecord
    ) -> AuthorizationDecision: ...

    def can_cancel(
        self, context: AuthenticatedCommandContext, command: CommandRecord
    ) -> AuthorizationDecision: ...


class AuditSink(Protocol):
    def record(self, event: AuditEvent) -> None: ...


class HeartbeatHandle(Protocol):
    def stop(self) -> bool:
        """Stop scheduling and synchronously settle activity when possible."""

        ...


class HeartbeatScheduler(Protocol):
    def start(
        self, interval: timedelta, callback: Callable[[], None]
    ) -> HeartbeatHandle: ...
