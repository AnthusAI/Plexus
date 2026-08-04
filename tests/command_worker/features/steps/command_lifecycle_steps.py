from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from behave import given, then, when

from plexus.command_worker import (
    Claim,
    ClaimStatus,
    CommandEnvelope,
    CommandWorker,
    ProgressUpdate,
    LeaseLostError,
)


@dataclass
class MutableClock:
    current: datetime

    def now(self) -> datetime:
        return self.current

    def advance(self, duration: timedelta) -> None:
        self.current += duration


class MemoryLifecycleStore:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.state = "announced"
        self.lease: Claim | None = None
        self.progress_values: list[float] = []
        self._token_number = 0
        self.reject_renewal = False
        self.rotate_renewal = False
        self.mutation_tokens: list[tuple[str, str]] = []

    def claim(self, envelope, owner, now, lease_duration):
        if self.state in {"completed", "failed", "cancelled"}:
            return ClaimStatus.TERMINAL
        if self.lease is not None and self.lease.expires_at > now:
            return ClaimStatus.ACTIVE
        self._token_number += 1
        self.lease = Claim(
            token=f"lease-{self._token_number}",
            owner=owner,
            expires_at=now + lease_duration,
        )
        self.state = "running"
        return self.lease

    def report_progress(self, command_id, token, progress, now):
        self.mutation_tokens.append(("progress", token))
        if not self._accepts(token, now):
            return False
        self.progress_values.append(progress.fraction)
        self.events.append("progress")
        return True

    def renew(self, command_id, token, now, lease_duration):
        self.events.append("lifecycle-renewed")
        if self.reject_renewal:
            return None
        if not self._accepts(token, now):
            return None
        assert self.lease is not None
        renewed_token = "rotated-lease" if self.rotate_renewal else token
        self.lease = Claim(renewed_token, self.lease.owner, now + lease_duration)
        return self.lease

    def complete(self, command_id, token, result, now):
        self.mutation_tokens.append(("complete", token))
        if not self._accepts(token, now):
            return False
        self.state = "completed"
        self.events.append("completed")
        return True

    def fail(self, command_id, token, error, now):
        self.mutation_tokens.append(("fail", token))
        if not self._accepts(token, now):
            return False
        self.state = "failed"
        self.events.append("failed")
        return True

    def _accepts(self, token: str, now: datetime) -> bool:
        return bool(
            self.lease and self.lease.token == token and self.lease.expires_at > now
        )


class MemoryDelivery:
    def __init__(self, envelope: CommandEnvelope, events: list[str]) -> None:
        self.envelope = envelope
        self.events = events
        self.acknowledged = False
        self.released = False
        self.renewal_succeeds = True

    def acknowledge(self) -> None:
        self.acknowledged = True
        self.events.append("acknowledged")

    def release(self) -> None:
        self.released = True
        self.events.append("released")

    def extend_lease(self, duration: timedelta) -> bool:
        self.events.append("delivery-renewed")
        return self.renewal_succeeds


class ManualHeartbeatHandle:
    def __init__(self, scheduler) -> None:
        self.scheduler = scheduler

    def stop(self) -> bool:
        self.scheduler.running = False
        self.scheduler.events.append("heartbeat-stopped")
        return True


class ManualHeartbeatScheduler:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.callback = None
        self.running = False

    def start(self, interval: timedelta, callback):
        self.callback = callback
        self.running = True
        return ManualHeartbeatHandle(self)

    def fire(self) -> None:
        if self.running:
            self.callback()


class RecordingExecutor:
    def __init__(self, progress: float | None = None) -> None:
        self.calls = 0
        self.progress = progress
        self.fire_heartbeat = False
        self.observe_loss = False
        self.observed_loss = False
        self.scheduler = None

    def execute(self, envelope, context):
        self.calls += 1
        if self.fire_heartbeat:
            self.scheduler.fire()
        if self.observe_loss:
            try:
                context.raise_if_lease_lost()
            except LeaseLostError:
                self.observed_loss = True
        if self.progress is not None:
            context.report_progress(self.progress)
        return {"outcome": "ok"}


def _initialize(context) -> None:
    context.events = []
    context.clock = MutableClock(datetime(2026, 8, 4, tzinfo=timezone.utc))
    context.store = MemoryLifecycleStore(context.events)
    context.envelope = CommandEnvelope(
        schema_version=1,
        command_id="command-1",
        task_id="task-1",
        target="evaluation",
        idempotency_key="task-1:evaluation",
        created_at=context.clock.now(),
        payload={"scorecard_id": "scorecard-1"},
    )
    context.delivery = MemoryDelivery(context.envelope, context.events)
    context.executor = RecordingExecutor()
    context.scheduler = ManualHeartbeatScheduler(context.events)
    context.executor.scheduler = context.scheduler
    context.worker = CommandWorker(
        lifecycle=context.store,
        executor=context.executor,
        clock=context.clock,
        lease_duration=timedelta(minutes=5),
    )


def _enable_heartbeats(context) -> None:
    context.worker = CommandWorker(
        lifecycle=context.store,
        executor=context.executor,
        clock=context.clock,
        lease_duration=timedelta(minutes=5),
        heartbeat_interval=timedelta(minutes=1),
        delivery_lease_duration=timedelta(minutes=3),
        heartbeat_scheduler=context.scheduler,
    )


@given("an announced command delivery")
def announced_delivery(context):
    _initialize(context)


@given("an announced command delivery with automatic heartbeats")
def heartbeat_delivery(context):
    _initialize(context)
    _enable_heartbeats(context)


@given("lifecycle renewal rotates the fencing token")
def rotating_renewal(context):
    context.store.rotate_renewal = True


@given("lifecycle renewal will be rejected")
def rejected_renewal(context):
    context.store.reject_renewal = True


@given("delivery lease renewal will fail")
def failed_delivery_renewal(context):
    context.delivery.renewal_succeeds = False


@given("an executor that fires a heartbeat, reports progress, and succeeds")
def heartbeat_progress_executor(context):
    context.executor.fire_heartbeat = True
    context.executor.progress = 0.5


@given("an executor that fires a heartbeat and observes ownership loss")
def heartbeat_loss_executor(context):
    context.executor.fire_heartbeat = True
    context.executor.observe_loss = True


@given("an executor that fires a heartbeat and succeeds")
def heartbeat_executor(context):
    context.executor.fire_heartbeat = True


@given("an executor that reports 50 percent progress and succeeds")
def progressing_executor(context):
    context.executor.progress = 0.5


@given('worker "worker-one" holds an active lease for the command')
def active_lease(context):
    context.store.claim(
        context.envelope,
        "worker-one",
        context.clock.now(),
        timedelta(minutes=5),
    )


@given("the command has already completed")
def completed_command(context):
    lease = context.store.claim(
        context.envelope,
        "worker-one",
        context.clock.now(),
        timedelta(minutes=5),
    )
    assert isinstance(lease, Claim)
    assert context.store.complete(
        context.envelope.command_id,
        lease.token,
        {"outcome": "ok"},
        context.clock.now(),
    )
    context.events.clear()


@given("the command has already failed")
def failed_command(context):
    context.store.state = "failed"


@given('worker "worker-one" claimed an announced command')
def first_claim(context):
    _initialize(context)
    context.stale_lease = context.store.claim(
        context.envelope,
        "worker-one",
        context.clock.now(),
        timedelta(minutes=5),
    )
    assert isinstance(context.stale_lease, Claim)


@given("its lease expired")
def expire_lease(context):
    context.clock.advance(timedelta(minutes=6))


@given('worker "worker-two" claimed the command')
def second_claim(context):
    context.current_lease = context.store.claim(
        context.envelope,
        "worker-two",
        context.clock.now(),
        timedelta(minutes=5),
    )
    assert isinstance(context.current_lease, Claim)


@when('worker "worker-one" processes the delivery')
def first_worker_processes(context):
    context.worker.process(context.delivery, owner="worker-one")


@when('worker "worker-two" processes a duplicate delivery')
def second_worker_processes(context):
    context.worker.process(context.delivery, owner="worker-two")


@when("the stale worker reports progress and completes")
def stale_worker_mutates(context):
    now = context.clock.now()
    token = context.stale_lease.token
    context.stale_progress = context.store.report_progress(
        context.envelope.command_id, token, ProgressUpdate(0.9), now
    )
    context.stale_completion = context.store.complete(
        context.envelope.command_id, token, {"outcome": "stale"}, now
    )


@when("the legacy Celery command modules are imported")
def import_legacy_modules(context):
    from plexus.cli.shared import CommandDispatch, CommandTasks

    context.legacy_modules = (CommandDispatch, CommandTasks)


@then("the command is executed once")
def executed_once(context):
    assert context.executor.calls == 1


@then("progress of 50 percent is stored")
def progress_stored(context):
    assert context.store.progress_values == [0.5]


@then("completion is stored before the delivery is acknowledged")
def completion_before_ack(context):
    assert context.events.index("completed") < context.events.index("acknowledged")


@then("the command is not executed")
def not_executed(context):
    assert context.executor.calls == 0


@then("the duplicate delivery is released for retry")
def duplicate_released(context):
    assert context.delivery.released
    assert not context.delivery.acknowledged


@then("the duplicate delivery is acknowledged")
def duplicate_acknowledged(context):
    assert context.delivery.acknowledged
    assert not context.delivery.released


@then("both stale lifecycle mutations are rejected")
def stale_mutations_rejected(context):
    assert context.stale_progress is False
    assert context.stale_completion is False


@then('worker "worker-two" remains the lease owner')
def current_owner_remains(context):
    assert context.store.lease.owner == "worker-two"
    assert context.store.state == "running"


@then("lifecycle ownership is renewed before the delivery lease")
def lifecycle_before_delivery(context):
    assert context.events.index("lifecycle-renewed") < context.events.index(
        "delivery-renewed"
    )


@then("later progress and completion use the rotated fencing token")
def rotated_token_used(context):
    assert ("progress", "rotated-lease") in context.store.mutation_tokens
    assert ("complete", "rotated-lease") in context.store.mutation_tokens


@then("no terminal lifecycle mutation is stored")
def no_terminal_mutation(context):
    assert context.executor.observed_loss
    assert not any(
        operation in {"complete", "fail"}
        for operation, _token in context.store.mutation_tokens
    )


@then("the delivery is released without acknowledgement")
def released_without_ack(context):
    assert context.delivery.released
    assert not context.delivery.acknowledged


@then("heartbeat scheduling stops before completion")
def heartbeat_stops_first(context):
    assert context.events.index("heartbeat-stopped") < context.events.index("completed")


@then("no heartbeat can run after execution returns")
def heartbeat_cannot_run(context):
    renewal_count = context.events.count("lifecycle-renewed")
    context.scheduler.fire()
    assert context.events.count("lifecycle-renewed") == renewal_count


@then("both legacy modules are importable")
def legacy_imports_succeeded(context):
    assert all(context.legacy_modules)
