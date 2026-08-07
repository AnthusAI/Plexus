"""Synchronous orchestration for a single command delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from threading import Event, RLock

from .models import Claim, JSONValue, ProgressUpdate, freeze_json
from .ports import (
    ClaimStatus,
    Clock,
    Delivery,
    Executor,
    HeartbeatScheduler,
    LifecycleStore,
    TaskScaleInProtection,
)
from .scheduler import ThreadHeartbeatScheduler


class LeaseLostError(RuntimeError):
    """Raised when the lifecycle store rejects a fenced mutation."""


class CancellationRequestedError(RuntimeError):
    """Raised at a cooperative boundary after durable cancellation is requested."""


class ProcessOutcome(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    ACTIVE_DUPLICATE = "active_duplicate"
    TERMINAL_DUPLICATE = "terminal_duplicate"
    LEASE_LOST = "lease_lost"
    CANCELLED = "cancelled"
    INTEGRITY_MISMATCH = "integrity_mismatch"


@dataclass(slots=True)
class _ExecutionContext:
    lifecycle: LifecycleStore
    clock: Clock
    command_id: str
    lease: Claim
    lease_duration: timedelta
    _lock: RLock
    _ownership_lost: Event
    _cancellation_requested: Event
    _ownership_loss_reason: str | None = None

    @property
    def ownership_lost(self) -> bool:
        return self._ownership_lost.is_set()

    def raise_if_lease_lost(self) -> None:
        if self._ownership_lost.is_set():
            raise LeaseLostError(
                self._ownership_loss_reason or "execution ownership was lost"
            )

    @property
    def cancellation_requested(self) -> bool:
        return self._cancellation_requested.is_set()

    def raise_if_cancellation_requested(self) -> None:
        if self._cancellation_requested.is_set():
            raise CancellationRequestedError("execution cancellation was requested")

    def _lose_ownership(self, reason: str) -> None:
        with self._lock:
            if not self._ownership_lost.is_set():
                self._ownership_loss_reason = reason
                self._ownership_lost.set()

    def _token(self) -> str:
        with self._lock:
            self.raise_if_lease_lost()
            return self.lease.token

    def report_progress(
        self,
        fraction: float,
        message: str | None = None,
        details: dict[str, JSONValue] | None = None,
    ) -> None:
        update = ProgressUpdate(fraction, message, details)
        with self._lock:
            self.raise_if_lease_lost()
            self.raise_if_cancellation_requested()
            accepted = self.lifecycle.report_progress(
                self.command_id, self.lease.token, update, self.clock.now()
            )
            if not accepted:
                self._lose_ownership("progress rejected because the lease is stale")
                self.raise_if_lease_lost()

    def renew_lease(self) -> Claim:
        with self._lock:
            self.raise_if_lease_lost()
            renewed = self.lifecycle.renew(
                self.command_id,
                self.lease.token,
                self.clock.now(),
                self.lease_duration,
            )
            if renewed is None:
                self._lose_ownership("renewal rejected because the lease is stale")
                self.raise_if_lease_lost()
            self.raise_if_lease_lost()
            self.lease = renewed
            if renewed.cancellation_requested:
                self._cancellation_requested.set()
            return renewed

    def heartbeat(self, delivery: Delivery, delivery_lease_duration: timedelta) -> None:
        try:
            with self._lock:
                self.renew_lease()
                if not delivery.extend_lease(delivery_lease_duration):
                    self._lose_ownership("delivery lease renewal failed")
        except LeaseLostError:
            # Another worker owns the command now; preserve the fenced state.
            return
        except Exception as exc:
            self._lose_ownership(f"heartbeat raised {type(exc).__name__}: {exc}")


class CommandWorker:
    def __init__(
        self,
        lifecycle: LifecycleStore,
        executor: Executor,
        clock: Clock,
        lease_duration: timedelta,
        heartbeat_interval: timedelta | None = None,
        delivery_lease_duration: timedelta | None = None,
        heartbeat_scheduler: HeartbeatScheduler | None = None,
        task_scale_in_protection: TaskScaleInProtection | None = None,
    ) -> None:
        if lease_duration <= timedelta(0):
            raise ValueError("lease_duration must be positive")
        if heartbeat_interval is None:
            heartbeat_interval = lease_duration / 3
        if heartbeat_interval <= timedelta(0):
            raise ValueError("heartbeat_interval must be positive")
        if heartbeat_interval >= lease_duration:
            raise ValueError("heartbeat_interval must be shorter than lease_duration")
        if delivery_lease_duration is None:
            delivery_lease_duration = lease_duration
        if delivery_lease_duration <= timedelta(0):
            raise ValueError("delivery_lease_duration must be positive")
        self._lifecycle = lifecycle
        self._executor = executor
        self._clock = clock
        self._lease_duration = lease_duration
        self._heartbeat_interval = heartbeat_interval
        self._delivery_lease_duration = delivery_lease_duration
        self._heartbeat_scheduler = heartbeat_scheduler or ThreadHeartbeatScheduler()
        self._task_scale_in_protection = task_scale_in_protection

    def _clear_task_scale_in_protection(self) -> None:
        """Best-effort cleanup after a durable terminal state.

        The protection has a finite ECS expiry, so a transient agent failure
        here cannot permanently pin a task.  It must not undo a completed Task
        lifecycle mutation by turning a successful command into a retry.
        """

        if self._task_scale_in_protection is not None:
            try:
                self._task_scale_in_protection.clear()
            except Exception:
                pass

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
        if claim is ClaimStatus.INTEGRITY_MISMATCH:
            delivery.quarantine(
                "command envelope failed durable integrity verification"
            )
            return ProcessOutcome.INTEGRITY_MISMATCH

        cancellation_requested = Event()
        if claim.cancellation_requested:
            cancellation_requested.set()
        context = _ExecutionContext(
            lifecycle=self._lifecycle,
            clock=self._clock,
            command_id=envelope.command_id,
            lease=claim,
            lease_duration=self._lease_duration,
            _lock=RLock(),
            _ownership_lost=Event(),
            _cancellation_requested=cancellation_requested,
        )
        if (
            self._task_scale_in_protection is not None
            and not self._task_scale_in_protection.enable()
        ):
            # Do not begin a long-running effect if ECS cannot acknowledge the
            # scale-in fence.  Releasing retains the at-least-once delivery.
            self._clear_task_scale_in_protection()
            delivery.release()
            return ProcessOutcome.LEASE_LOST
        try:
            heartbeat = self._heartbeat_scheduler.start(
                self._heartbeat_interval,
                lambda: context.heartbeat(delivery, self._delivery_lease_duration),
            )
        except Exception as exc:
            context._lose_ownership(
                f"heartbeat scheduling raised {type(exc).__name__}: {exc}"
            )
            self._clear_task_scale_in_protection()
            delivery.release()
            return ProcessOutcome.LEASE_LOST

        execution_error: Exception | None = None
        result: JSONValue = None
        try:
            context.raise_if_cancellation_requested()
            result = self._executor.execute(envelope, context)
        except Exception as exc:
            execution_error = exc
        finally:
            try:
                settled = heartbeat.stop()
            except Exception as exc:
                context._lose_ownership(
                    f"heartbeat shutdown raised {type(exc).__name__}: {exc}"
                )
            else:
                if not settled:
                    context._lose_ownership("heartbeat did not settle before shutdown")

        if isinstance(execution_error, LeaseLostError):
            context._lose_ownership(str(execution_error) or "execution lost ownership")
        try:
            context.raise_if_lease_lost()
        except LeaseLostError:
            self._clear_task_scale_in_protection()
            delivery.release()
            return ProcessOutcome.LEASE_LOST

        cancellation_requested = context.cancellation_requested or isinstance(
            execution_error, CancellationRequestedError
        )
        if cancellation_requested:
            accepted = self._lifecycle.finalize_cancel(
                envelope.command_id, context._token(), self._clock.now()
            )
            if accepted:
                self._clear_task_scale_in_protection()
                delivery.acknowledge()
                return ProcessOutcome.CANCELLED
            self._clear_task_scale_in_protection()
            delivery.release()
            return ProcessOutcome.LEASE_LOST

        if execution_error is not None:
            accepted = self._lifecycle.fail(
                envelope.command_id,
                context._token(),
                f"{type(execution_error).__name__}: {execution_error}",
                self._clock.now(),
            )
            if accepted:
                self._clear_task_scale_in_protection()
                delivery.acknowledge()
                return ProcessOutcome.FAILED
            self._clear_task_scale_in_protection()
            delivery.release()
            return ProcessOutcome.LEASE_LOST

        try:
            result = freeze_json(result, "result")
        except Exception as exc:
            accepted = self._lifecycle.fail(
                envelope.command_id,
                context._token(),
                f"{type(exc).__name__}: {exc}",
                self._clock.now(),
            )
            if accepted:
                self._clear_task_scale_in_protection()
                delivery.acknowledge()
                return ProcessOutcome.FAILED
            self._clear_task_scale_in_protection()
            delivery.release()
            return ProcessOutcome.LEASE_LOST

        accepted = self._lifecycle.complete(
            envelope.command_id,
            context._token(),
            result,
            self._clock.now(),
        )
        if not accepted:
            if self._lifecycle.finalize_cancel(
                envelope.command_id, context._token(), self._clock.now()
            ):
                self._clear_task_scale_in_protection()
                delivery.acknowledge()
                return ProcessOutcome.CANCELLED
            self._clear_task_scale_in_protection()
            delivery.release()
            return ProcessOutcome.LEASE_LOST
        delivery.acknowledge()
        self._clear_task_scale_in_protection()
        return ProcessOutcome.COMPLETED
