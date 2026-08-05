from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from celery import Celery
from celery.exceptions import Reject

from plexus.command_worker import Claim, ClaimStatus, CommandEnvelope
from plexus.command_worker.adapters.celery_delivery import (
    register_portable_command_task,
)

NOW = datetime(2026, 8, 5, tzinfo=timezone.utc)


class Clock:
    def now(self) -> datetime:
        return NOW


class Lifecycle:
    def __init__(self, claim_result=None) -> None:
        self.claim_result = claim_result
        self.completed = False

    def claim(self, envelope, owner, now, lease_duration):
        if self.claim_result is not None:
            return self.claim_result
        return Claim("1", owner, now + lease_duration)

    def report_progress(self, command_id, token, progress, now):
        return True

    def renew(self, command_id, token, now, lease_duration):
        return Claim(token, "worker", now + lease_duration)

    def complete(self, command_id, token, result, now):
        self.completed = True
        return True

    def fail(self, command_id, token, error, now):
        return True

    def finalize_cancel(self, command_id, token, now):
        return False


class Executor:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, envelope, context):
        self.calls += 1
        return {"ok": True}


def envelope() -> CommandEnvelope:
    return CommandEnvelope(
        schema_version=2,
        command_id="command-1",
        tenant_id="tenant-1",
        target="evaluate",
        idempotency_key="request-1",
        created_at=NOW,
        payload={"item_id": "item-1"},
    )


def register(*, lifecycle=None, executor=None):
    app = Celery("portable-command-test")
    task = register_portable_command_task(
        app,
        task_name="plexus.portable.execute_command",
        lifecycle=lifecycle or Lifecycle(),
        executor=executor or Executor(),
        clock=Clock(),
        owner_factory=lambda: "worker-one",
        lease_duration=timedelta(minutes=5),
    )
    return task


def test_registered_task_uses_late_ack_and_worker_loss_rejection() -> None:
    task = register()

    assert task.name == "plexus.portable.execute_command"
    assert task.acks_late is True
    assert task.reject_on_worker_lost is True
    assert task.task_acks_on_failure_or_timeout is False


def test_registered_task_settles_a_valid_command_through_portable_lifecycle() -> None:
    lifecycle = Lifecycle()
    executor = Executor()
    task = register(lifecycle=lifecycle, executor=executor)

    assert task.run(envelope().to_message()) == "completed"
    assert executor.calls == 1
    assert lifecycle.completed is True


def test_active_duplicate_requeues_without_execution() -> None:
    executor = Executor()
    task = register(lifecycle=Lifecycle(ClaimStatus.ACTIVE), executor=executor)

    with pytest.raises(Reject) as error:
        task.run(envelope().to_message())

    assert error.value.requeue is True
    assert executor.calls == 0


def test_integrity_mismatch_is_rejected_without_requeue() -> None:
    executor = Executor()
    task = register(
        lifecycle=Lifecycle(ClaimStatus.INTEGRITY_MISMATCH), executor=executor
    )

    with pytest.raises(Reject) as error:
        task.run(envelope().to_message())

    assert error.value.requeue is False
    assert executor.calls == 0


def test_invalid_message_is_rejected_without_requeue() -> None:
    task = register()

    with pytest.raises(Reject) as error:
        task.run({"bad": "message"})

    assert error.value.requeue is False
