"""Synchronous orchestration for a single command delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from .models import Claim, JSONValue, ProgressUpdate, freeze_json
from .ports import ClaimStatus, Clock, Delivery, Executor, LifecycleStore


class LeaseLostError(RuntimeError):
    """Raised when the lifecycle store rejects a fenced mutation."""


class ProcessOutcome(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    ACTIVE_DUPLICATE = "active_duplicate"
    TERMINAL_DUPLICATE = "terminal_duplicate"
    LEASE_LOST = "lease_lost"


@dataclass(slots=True)
class _ExecutionContext:
    lifecycle: LifecycleStore
    clock: Clock
    command_id: str
    lease: Claim
    lease_duration: timedelta

    def report_progress(
        self,
        fraction: float,
        message: str | None = None,
        details: dict[str, JSONValue] | None = None,
    ) -> None:
        update = ProgressUpdate(fraction, message, details)
        accepted = self.lifecycle.report_progress(
            self.command_id, self.lease.token, update, self.clock.now()
        )
        if not accepted:
            raise LeaseLostError("progress rejected because the lease is stale")

    def renew_lease(self) -> Claim:
        renewed = self.lifecycle.renew(
            self.command_id,
            self.lease.token,
            self.clock.now(),
            self.lease_duration,
        )
        if renewed is None:
            raise LeaseLostError("renewal rejected because the lease is stale")
        self.lease = renewed
        return renewed


class CommandWorker:
    def __init__(
        self,
        lifecycle: LifecycleStore,
        executor: Executor,
        clock: Clock,
        lease_duration: timedelta,
    ) -> None:
        if lease_duration <= timedelta(0):
            raise ValueError("lease_duration must be positive")
        self._lifecycle = lifecycle
        self._executor = executor
        self._clock = clock
        self._lease_duration = lease_duration

    def process(self, delivery: Delivery, owner: str) -> ProcessOutcome:
        if not owner:
            raise ValueError("owner must be non-empty")

        envelope = delivery.envelope
        claim = self._lifecycle.claim(
            envelope, owner, self._clock.now(), self._lease_duration
        )
        if claim is ClaimStatus.ACTIVE:
            delivery.release()
            return ProcessOutcome.ACTIVE_DUPLICATE
        if claim is ClaimStatus.TERMINAL:
            delivery.acknowledge()
            return ProcessOutcome.TERMINAL_DUPLICATE

        context = _ExecutionContext(
            lifecycle=self._lifecycle,
            clock=self._clock,
            command_id=envelope.command_id,
            lease=claim,
            lease_duration=self._lease_duration,
        )
        try:
            result = freeze_json(self._executor.execute(envelope, context), "result")
        except LeaseLostError:
            delivery.release()
            return ProcessOutcome.LEASE_LOST
        except Exception as exc:
            accepted = self._lifecycle.fail(
                envelope.command_id,
                context.lease.token,
                f"{type(exc).__name__}: {exc}",
                self._clock.now(),
            )
            if accepted:
                delivery.acknowledge()
                return ProcessOutcome.FAILED
            delivery.release()
            return ProcessOutcome.LEASE_LOST

        accepted = self._lifecycle.complete(
            envelope.command_id,
            context.lease.token,
            result,
            self._clock.now(),
        )
        if not accepted:
            delivery.release()
            return ProcessOutcome.LEASE_LOST
        delivery.acknowledge()
        return ProcessOutcome.COMPLETED
