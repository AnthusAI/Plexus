from __future__ import annotations

from datetime import timedelta

import pytest

from plexus.command_worker import (
    CommandWorkerService,
    EventDrainSignal,
    ProcessOutcome,
    ServiceReceiveError,
    ServiceStopReason,
)

RECEIVE_TIMEOUT = timedelta(seconds=10)
IDLE_WAIT = timedelta(seconds=2)


class Delivery:
    def __init__(self, events=None):
        self.events = events if events is not None else []

    def release(self):
        self.events.append("release")

    def acknowledge(self):
        self.events.append("ack")


class Drain:
    def __init__(self, requested=False):
        self.requested = requested
        self.checks = 0
        self.waits = []
        self.on_check = None

    def is_requested(self):
        self.checks += 1
        if self.on_check is not None:
            self.on_check(self)
        return self.requested

    def wait(self, timeout):
        self.waits.append(timeout)
        self.requested = True
        return True


class Transport:
    def __init__(self, deliveries=(), events=None):
        self.deliveries = list(deliveries)
        self.events = events if events is not None else []
        self.timeouts = []
        self.error = None

    def receive(self, timeout):
        self.events.append("receive")
        self.timeouts.append(timeout)
        if self.error is not None:
            raise self.error
        return self.deliveries.pop(0) if self.deliveries else None


class Worker:
    def __init__(self, outcomes=(ProcessOutcome.COMPLETED,), events=None):
        self.outcomes = list(outcomes)
        self.events = events if events is not None else []
        self.calls = []
        self.on_process = None

    def process(self, delivery, owner):
        self.events.append("process")
        self.calls.append((delivery, owner))
        if self.on_process is not None:
            self.on_process()
        return self.outcomes.pop(0)


def service(transport, worker, drain, **overrides):
    values = {
        "transport": transport,
        "worker": worker,
        "owner": "worker-one",
        "drain": drain,
        "receive_timeout": RECEIVE_TIMEOUT,
        "idle_wait": IDLE_WAIT,
    }
    values.update(overrides)
    return CommandWorkerService(**values)


def test_drain_before_receive_stops_without_touching_transport():
    transport = Transport()

    outcome = service(transport, Worker(), Drain(requested=True)).run()

    assert outcome.stop_reason is ServiceStopReason.DRAIN_REQUESTED
    assert outcome.processed_count == 0
    assert transport.timeouts == []


def test_drain_observed_after_receive_releases_before_process():
    events = []
    delivery = Delivery(events)
    transport = Transport([delivery], events)
    worker = Worker(events=events)
    drain = Drain()
    drain.on_check = lambda signal: setattr(signal, "requested", signal.checks == 2)

    outcome = service(transport, worker, drain).run()

    assert events == ["receive", "release"]
    assert worker.calls == []
    assert outcome.processed_count == 0


def test_drain_during_process_allows_settlement_and_prevents_second_receive():
    events = []
    first = Delivery(events)
    second = Delivery(events)
    drain = Drain()
    transport = Transport([first, second], events)
    worker = Worker(events=events)
    worker.on_process = lambda: setattr(drain, "requested", True)

    outcome = service(transport, worker, drain).run()

    assert events == ["receive", "process"]
    assert worker.calls == [(first, "worker-one")]
    assert outcome.processed_count == 1
    assert outcome.count(ProcessOutcome.COMPLETED) == 1


def test_empty_receive_uses_injected_idle_wait_without_busy_spin():
    transport = Transport([None])
    drain = Drain()

    outcome = service(transport, Worker(), drain).run()

    assert transport.timeouts == [RECEIVE_TIMEOUT]
    assert drain.waits == [IDLE_WAIT]
    assert outcome.processed_count == 0


def test_service_records_each_settled_process_outcome():
    first = Delivery()
    second = Delivery()
    drain = Drain()
    transport = Transport([first, second, None])
    worker = Worker([ProcessOutcome.COMPLETED, ProcessOutcome.FAILED])

    outcome = service(transport, worker, drain).run()

    assert outcome.processed_count == 2
    assert outcome.outcome_counts == {
        ProcessOutcome.COMPLETED: 1,
        ProcessOutcome.FAILED: 1,
    }


def test_receive_error_is_propagated_with_prior_processing_count():
    class FailingSecondTransport(Transport):
        def receive(self, timeout):
            if self.timeouts:
                raise ConnectionError("broker unavailable")
            return super().receive(timeout)

    transport = FailingSecondTransport([Delivery()])

    with pytest.raises(ServiceReceiveError, match="broker unavailable") as exc_info:
        service(transport, Worker(), Drain()).run()

    assert isinstance(exc_info.value.__cause__, ConnectionError)
    assert exc_info.value.processed_count == 1
    assert exc_info.value.process_outcomes == (ProcessOutcome.COMPLETED,)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"owner": ""}, "owner"),
        ({"receive_timeout": timedelta(0)}, "receive_timeout"),
        ({"idle_wait": timedelta(0)}, "idle_wait"),
    ],
)
def test_service_configuration_requires_bounded_positive_waits(overrides, message):
    with pytest.raises(ValueError, match=message):
        service(Transport(), Worker(), Drain(), **overrides)


def test_event_drain_signal_supports_immediate_drain_and_idle_wait():
    drain = EventDrainSignal()

    assert not drain.is_requested()
    assert not drain.wait(timedelta(0))
    drain.request()
    assert drain.is_requested()
    assert drain.wait(timedelta(minutes=1))


def test_event_drain_signal_rejects_negative_wait():
    with pytest.raises(ValueError, match="negative"):
        EventDrainSignal().wait(timedelta(microseconds=-1))
