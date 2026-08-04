"""Provider ports for the portable command-worker runtime."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from typing import Protocol

from .models import Claim, CommandEnvelope, JSONValue, ProgressUpdate


class ClaimStatus(str, Enum):
    ACTIVE = "active"
    TERMINAL = "terminal"


class Delivery(Protocol):
    envelope: CommandEnvelope

    def acknowledge(self) -> None: ...

    def release(self) -> None: ...

    def extend_lease(self, duration: timedelta) -> bool: ...


class Transport(Protocol):
    def receive(self, timeout: timedelta) -> Delivery | None: ...


class DrainSignal(Protocol):
    def is_requested(self) -> bool: ...

    def wait(self, timeout: timedelta) -> bool:
        """Wait until draining is requested or the timeout elapses."""

        ...


class LifecycleStore(Protocol):
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


class HeartbeatHandle(Protocol):
    def stop(self) -> bool:
        """Stop scheduling and synchronously settle activity when possible."""

        ...


class HeartbeatScheduler(Protocol):
    def start(
        self, interval: timedelta, callback: Callable[[], None]
    ) -> HeartbeatHandle: ...
