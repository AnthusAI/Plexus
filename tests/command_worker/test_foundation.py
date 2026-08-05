from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from plexus.command_worker import (
    Claim,
    ClaimStatus,
    CommandEnvelope,
    CommandWorker,
    ProcessOutcome,
    ProgressUpdate,
    LeaseLostError,
    ThreadHeartbeatScheduler,
)

NOW = datetime(2026, 8, 4, tzinfo=timezone.utc)


def envelope(**overrides):
    values = {
        "schema_version": 2,
        "command_id": "command-1",
        "tenant_id": "tenant-1",
        "target": "evaluation",
        "idempotency_key": "evaluation:task-1",
        "created_at": NOW,
        "payload": {"input": {"ids": ["one", "two"]}},
    }
    values.update(overrides)
    return CommandEnvelope(**values)


class Clock:
    def now(self):
        return NOW


class Delivery:
    def __init__(self):
        self.envelope = envelope()
        self.events = []

    def acknowledge(self):
        self.events.append("ack")

    def release(self):
        self.events.append("release")

    def extend_lease(self, duration):
        self.events.append("extend")
        return True


class Store:
    def __init__(self, complete_accepted=True, fail_accepted=True):
        self.events = []
        self.complete_accepted = complete_accepted
        self.fail_accepted = fail_accepted

    def claim(self, envelope, owner, now, lease_duration):
        return Claim("token", owner, now + lease_duration)

    def report_progress(self, command_id, token, progress, now):
        self.events.append("progress")
        return True

    def renew(self, command_id, token, now, lease_duration):
        return Claim(token, "worker", now + lease_duration)

    def complete(self, command_id, token, result, now):
        self.events.append("complete")
        return self.complete_accepted

    def fail(self, command_id, token, error, now):
        self.events.append("fail")
        return self.fail_accepted

    def finalize_cancel(self, command_id, token, now):
        return False


class Executor:
    def __init__(self, error=None):
        self.error = error

    def execute(self, envelope, context):
        if self.error:
            raise self.error
        return {"ok": True}


def worker(store, executor):
    return CommandWorker(store, executor, Clock(), timedelta(minutes=5))


def test_envelope_is_deeply_immutable():
    command = envelope()

    with pytest.raises(FrozenInstanceError):
        command.target = "changed"
    with pytest.raises(TypeError):
        command.payload["changed"] = True
    with pytest.raises(TypeError):
        command.payload["input"]["ids"][0] = "changed"


def test_envelope_message_is_json_serializable_and_round_trips():
    created_at = datetime(
        2026, 8, 4, 12, 30, 45, 123456, tzinfo=timezone(timedelta(hours=-7))
    )
    command = envelope(created_at=created_at)

    message = command.to_message()
    encoded = json.dumps(message)
    restored = CommandEnvelope.from_message(json.loads(encoded))

    assert restored == command
    assert restored.created_at == created_at
    assert message["payload"]["input"]["ids"] == ["one", "two"]


def test_message_containers_do_not_mutate_the_immutable_envelope():
    command = envelope()
    message = command.to_message()

    message["payload"]["input"]["ids"][0] = "changed"

    assert command.payload["input"]["ids"] == ("one", "two")


@pytest.mark.parametrize(
    "mutation, error",
    [
        (lambda message: message.pop("tenant_id"), ValueError),
        (lambda message: message.update({"unexpected": True}), ValueError),
        (lambda message: message.update({"schema_version": 1}), ValueError),
        (
            lambda message: message.update({"created_at": "not-a-datetime"}),
            ValueError,
        ),
        (
            lambda message: message.update({"created_at": "2026-08-04T12:00:00"}),
            ValueError,
        ),
        (lambda message: message.update({"payload": []}), TypeError),
        (
            lambda message: message.update({"payload": {"bad": ("tuple",)}}),
            TypeError,
        ),
    ],
)
def test_from_message_rejects_malformed_messages(mutation, error):
    message = envelope().to_message()
    mutation(message)

    with pytest.raises(error):
        CommandEnvelope.from_message(message)


def test_from_message_rejects_non_object_messages_and_non_string_keys():
    with pytest.raises(TypeError, match="must be a JSON object"):
        CommandEnvelope.from_message([])
    with pytest.raises(TypeError, match="keys must be strings"):
        CommandEnvelope.from_message({1: "not-a-message"})


@pytest.mark.parametrize(
    "overrides, error",
    [
        ({"created_at": datetime(2026, 8, 4)}, ValueError),
        ({"payload": {"when": NOW}}, TypeError),
        ({"payload": {"tuple": ("not", "json")}}, TypeError),
        ({"payload": {"number": float("nan")}}, ValueError),
        ({"payload": {1: "non-string-key"}}, TypeError),
    ],
)
def test_envelope_rejects_naive_timestamps_and_non_json_payloads(overrides, error):
    with pytest.raises(error):
        envelope(**overrides)


def test_terminal_failure_is_stored_before_acknowledgement():
    store = Store()
    delivery = Delivery()

    outcome = worker(store, Executor(ValueError("bad command"))).process(
        delivery, "worker"
    )

    assert outcome is ProcessOutcome.FAILED
    assert store.events == ["fail"]
    assert delivery.events == ["ack"]


def test_rejected_completion_releases_delivery_instead_of_acknowledging():
    store = Store(complete_accepted=False)
    delivery = Delivery()

    outcome = worker(store, Executor()).process(delivery, "worker")

    assert outcome is ProcessOutcome.LEASE_LOST
    assert store.events == ["complete"]
    assert delivery.events == ["release"]


def test_terminal_duplicate_is_acknowledged_without_execution():
    class TerminalStore(Store):
        def claim(self, envelope, owner, now, lease_duration):
            return ClaimStatus.TERMINAL

    class NeverExecutor:
        def execute(self, envelope, context):
            pytest.fail("terminal duplicate must not execute")

    delivery = Delivery()

    outcome = worker(TerminalStore(), NeverExecutor()).process(delivery, "worker")

    assert outcome is ProcessOutcome.TERMINAL_DUPLICATE
    assert delivery.events == ["ack"]


def test_renewed_rotated_token_is_used_for_subsequent_completion():
    class RotatingStore(Store):
        def __init__(self):
            super().__init__()
            self.completion_token = None

        def renew(self, command_id, token, now, lease_duration):
            assert token == "token"
            return Claim("rotated-token", "worker", now + lease_duration)

        def complete(self, command_id, token, result, now):
            self.completion_token = token
            return super().complete(command_id, token, result, now)

    class RenewingExecutor:
        def execute(self, envelope, context):
            renewed = context.renew_lease()
            assert renewed.token == "rotated-token"
            return {"ok": True}

    store = RotatingStore()
    delivery = Delivery()

    outcome = worker(store, RenewingExecutor()).process(delivery, "worker")

    assert outcome is ProcessOutcome.COMPLETED
    assert store.completion_token == "rotated-token"
    assert delivery.events == ["ack"]


class ManualHeartbeatHandle:
    def __init__(self, scheduler):
        self.scheduler = scheduler

    def stop(self):
        self.scheduler.events.append("stop")
        if self.scheduler.stop_error is not None:
            raise self.scheduler.stop_error
        self.scheduler.running = False
        return self.scheduler.settles


class ManualHeartbeatScheduler:
    def __init__(self, events=None, settles=True, stop_error=None):
        self.events = events if events is not None else []
        self.settles = settles
        self.running = False
        self.callback = None
        self.stop_error = stop_error

    def start(self, interval, callback):
        self.events.append("start")
        self.running = True
        self.callback = callback
        return ManualHeartbeatHandle(self)

    def fire(self):
        if self.running:
            self.callback()


def heartbeat_worker(store, executor, scheduler, **overrides):
    values = {
        "lifecycle": store,
        "executor": executor,
        "clock": Clock(),
        "lease_duration": timedelta(minutes=5),
        "heartbeat_interval": timedelta(minutes=1),
        "delivery_lease_duration": timedelta(minutes=3),
        "heartbeat_scheduler": scheduler,
    }
    values.update(overrides)
    return CommandWorker(**values)


def test_heartbeat_orders_renewals_and_propagates_rotated_token():
    events = []
    scheduler = ManualHeartbeatScheduler(events)

    class RotatingStore(Store):
        renewal_count = 0

        def renew(self, command_id, token, now, lease_duration):
            events.append(f"renew:{token}")
            self.renewal_count += 1
            return Claim(
                f"rotated-{self.renewal_count}", "worker", now + lease_duration
            )

        def report_progress(self, command_id, token, progress, now):
            events.append(f"progress:{token}")
            return True

        def complete(self, command_id, token, result, now):
            events.append(f"complete:{token}")
            return True

    class ExtendingDelivery(Delivery):
        def extend_lease(self, duration):
            events.append(f"extend:{duration.total_seconds()}")
            return True

    class HeartbeatingExecutor:
        def execute(self, envelope, context):
            scheduler.fire()
            scheduler.fire()
            context.report_progress(0.5)
            return {"ok": True}

    delivery = ExtendingDelivery()
    outcome = heartbeat_worker(
        RotatingStore(), HeartbeatingExecutor(), scheduler
    ).process(delivery, "worker")

    assert outcome is ProcessOutcome.COMPLETED
    assert events == [
        "start",
        "renew:token",
        "extend:180.0",
        "renew:rotated-1",
        "extend:180.0",
        "progress:rotated-2",
        "stop",
        "complete:rotated-2",
    ]
    assert delivery.events == ["ack"]


@pytest.mark.parametrize("failure", ["lifecycle", "delivery", "exception"])
def test_heartbeat_failure_is_observable_and_prevents_terminal_mutation(failure):
    scheduler = ManualHeartbeatScheduler()

    class FailingStore(Store):
        def renew(self, command_id, token, now, lease_duration):
            if failure == "lifecycle":
                return None
            if failure == "exception":
                raise RuntimeError("renewal unavailable")
            return super().renew(command_id, token, now, lease_duration)

    class FailingDelivery(Delivery):
        def extend_lease(self, duration):
            return failure != "delivery"

    class ObservingExecutor:
        observed_loss = False

        def execute(self, envelope, context):
            scheduler.fire()
            assert context.ownership_lost
            with pytest.raises(LeaseLostError):
                context.raise_if_lease_lost()
            self.observed_loss = True
            return {"must_not_complete": True}

    store = FailingStore()
    delivery = FailingDelivery()
    executor = ObservingExecutor()
    outcome = heartbeat_worker(store, executor, scheduler).process(delivery, "worker")

    assert outcome is ProcessOutcome.LEASE_LOST
    assert executor.observed_loss
    assert store.events == []
    assert delivery.events == ["release"]


def test_heartbeat_does_not_swallow_process_level_base_exceptions():
    scheduler = ManualHeartbeatScheduler()

    class InterruptingStore(Store):
        def renew(self, command_id, token, now, lease_duration):
            raise KeyboardInterrupt("stop process")

    class HeartbeatingExecutor:
        def execute(self, envelope, context):
            scheduler.fire()
            pytest.fail("the process-level exception must escape the heartbeat")

    delivery = Delivery()

    with pytest.raises(KeyboardInterrupt, match="stop process"):
        heartbeat_worker(
            InterruptingStore(), HeartbeatingExecutor(), scheduler
        ).process(delivery, "worker")

    assert delivery.events == []


def test_first_ownership_loss_reason_wins_across_context_observation():
    scheduler = ManualHeartbeatScheduler()

    class FailingStore(Store):
        calls = 0

        def renew(self, command_id, token, now, lease_duration):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("first heartbeat failure")
            return None

    class ObservingExecutor:
        def execute(self, envelope, context):
            scheduler.fire()
            scheduler.fire()
            with pytest.raises(LeaseLostError) as exc_info:
                context.raise_if_lease_lost()
            assert str(exc_info.value) == (
                "heartbeat raised RuntimeError: first heartbeat failure"
            )
            return {"must_not_complete": True}

    delivery = Delivery()
    outcome = heartbeat_worker(FailingStore(), ObservingExecutor(), scheduler).process(
        delivery, "worker"
    )

    assert outcome is ProcessOutcome.LEASE_LOST
    assert delivery.events == ["release"]


def test_scheduler_settles_before_terminal_mutation_and_cannot_fire_after_stop():
    events = []
    scheduler = ManualHeartbeatScheduler(events)

    class OrderedStore(Store):
        def complete(self, command_id, token, result, now):
            events.append("complete")
            return True

    outcome = heartbeat_worker(OrderedStore(), Executor(), scheduler).process(
        Delivery(), "worker"
    )
    scheduler.fire()

    assert outcome is ProcessOutcome.COMPLETED
    assert events == ["start", "stop", "complete"]


def test_unsettled_scheduler_prevents_terminal_mutation():
    scheduler = ManualHeartbeatScheduler(settles=False)
    store = Store()
    delivery = Delivery()

    outcome = heartbeat_worker(store, Executor(), scheduler).process(delivery, "worker")

    assert outcome is ProcessOutcome.LEASE_LOST
    assert store.events == []
    assert delivery.events == ["release"]


def test_scheduler_shutdown_exception_prevents_terminal_mutation():
    scheduler = ManualHeartbeatScheduler(stop_error=RuntimeError("cannot join"))
    store = Store()
    delivery = Delivery()

    outcome = heartbeat_worker(store, Executor(), scheduler).process(delivery, "worker")

    assert outcome is ProcessOutcome.LEASE_LOST
    assert store.events == []
    assert delivery.events == ["release"]


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"heartbeat_interval": timedelta(0)}, "heartbeat_interval"),
        ({"heartbeat_interval": timedelta(minutes=5)}, "shorter"),
        ({"heartbeat_interval": timedelta(minutes=6)}, "shorter"),
        ({"delivery_lease_duration": timedelta(0)}, "delivery_lease_duration"),
    ],
)
def test_heartbeat_durations_are_validated(overrides, message):
    with pytest.raises(ValueError, match=message):
        heartbeat_worker(Store(), Executor(), ManualHeartbeatScheduler(), **overrides)


def test_standard_scheduler_uses_a_daemon_thread_and_settles_without_sleep():
    scheduler = ThreadHeartbeatScheduler(shutdown_timeout=timedelta(seconds=1))
    handle = scheduler.start(timedelta(minutes=1), lambda: None)

    assert handle._thread.daemon
    assert handle.stop()
    assert not handle._thread.is_alive()


@pytest.mark.parametrize("fraction", [True, False, "0.5", None, []])
def test_progress_fraction_rejects_non_numeric_values(fraction):
    with pytest.raises(TypeError, match="fraction must be a number"):
        ProgressUpdate(fraction)


@pytest.mark.parametrize("fraction", [-0.1, 1.1, float("nan"), float("inf")])
def test_progress_fraction_rejects_out_of_range_or_non_finite_values(fraction):
    with pytest.raises(ValueError, match="fraction must be between 0 and 1"):
        ProgressUpdate(fraction)


def test_provider_imports_do_not_cross_the_core_boundary():
    package = Path(__file__).parents[2] / "plexus" / "command_worker"
    forbidden = {"boto3", "botocore", "celery", "kubernetes", "dashboard"}
    imported = set()
    for source_file in package.glob("*.py"):
        tree = ast.parse(source_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

    assert imported.isdisjoint(forbidden)
