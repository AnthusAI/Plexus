"""Typed-envelope Celery delivery adapter for the Task-backed command worker.

Celery is transport only; Task conditional claims and fencing provide lifecycle
safety and absorb the stream transport's at-least-once delivery semantics.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Protocol

from celery import Celery
from celery.exceptions import Reject

from ..models import CommandEnvelope
from ..ports import (
    Clock,
    Delivery,
    Executor,
    HeartbeatScheduler,
    LifecycleStore,
    TaskScaleInProtection,
)
from ..worker import CommandWorker


class OwnerFactory(Protocol):
    def __call__(self) -> str: ...


class _CeleryDelivery:
    """Maps worker settlement intent to Celery's task acknowledgement model."""

    def __init__(self, envelope: CommandEnvelope) -> None:
        self.envelope = envelope
        self.released = False
        self.quarantine_reason: str | None = None

    def acknowledge(self) -> None:
        """Normal Celery task return performs the late acknowledgement."""

    def release(self) -> None:
        self.released = True

    def quarantine(self, reason: str) -> None:
        self.quarantine_reason = reason

    def extend_lease(self, duration: timedelta) -> bool:
        """Celery has no broker-neutral delivery visibility-extension API.

        The task keeps its acknowledgement late. Deployments using a broker
        with a delivery visibility timeout must configure it above their
        maximum command duration; durable lifecycle fencing absorbs any
        redelivery if that broker nevertheless exposes one.
        """

        return duration > timedelta(0)


def register_portable_command_task(
    app: Celery,
    *,
    task_name: str,
    lifecycle: LifecycleStore,
    executor: Executor,
    clock: Clock,
    owner_factory: OwnerFactory,
    lease_duration: timedelta,
    heartbeat_interval: timedelta | None = None,
    heartbeat_scheduler: HeartbeatScheduler | None = None,
    task_scale_in_protection: TaskScaleInProtection | None = None,
) -> Any:
    """Register an isolated, late-acknowledged Celery command task.

    A released delivery is rejected with ``requeue=True`` so the broker retains
    ownership of retry timing. An integrity mismatch is rejected without
    requeue so broker-native dead-letter configuration receives the message.
    """

    if not task_name.strip():
        raise ValueError("task_name must be non-empty")

    worker = CommandWorker(
        lifecycle=lifecycle,
        executor=executor,
        clock=clock,
        lease_duration=lease_duration,
        heartbeat_interval=heartbeat_interval,
        heartbeat_scheduler=heartbeat_scheduler,
        task_scale_in_protection=task_scale_in_protection,
    )

    @app.task(
        bind=True,
        name=task_name,
        acks_late=True,
        reject_on_worker_lost=True,
        task_acks_on_failure_or_timeout=False,
    )
    def execute_portable_command(_task: Any, message: dict[str, Any]) -> str:
        try:
            envelope = CommandEnvelope.from_message(message)
        except (TypeError, ValueError) as error:
            raise Reject(f"invalid portable command envelope: {error}", requeue=False)

        delivery: Delivery = _CeleryDelivery(envelope)
        outcome = worker.process(delivery, owner_factory())
        assert isinstance(delivery, _CeleryDelivery)
        if delivery.quarantine_reason is not None:
            raise Reject(delivery.quarantine_reason, requeue=False)
        if delivery.released:
            raise Reject("portable command lifecycle requested retry", requeue=True)
        return outcome.value

    return execute_portable_command
