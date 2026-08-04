from __future__ import annotations

from datetime import timedelta

from behave import given, then, when

from plexus.command_worker import (
    CommandWorkerService,
    ProcessOutcome,
    ServiceStopReason,
)


class Delivery:
    def __init__(self) -> None:
        self.released = False
        self.acknowledged = False

    def release(self) -> None:
        self.released = True

    def acknowledge(self) -> None:
        self.acknowledged = True


class DrainSignal:
    def __init__(self, requested: bool = False) -> None:
        self.requested = requested
        self.waits: list[timedelta] = []

    def is_requested(self) -> bool:
        return self.requested

    def wait(self, timeout: timedelta) -> bool:
        self.waits.append(timeout)
        self.requested = True
        return True


class Transport:
    def __init__(self, deliveries, drain=None, drain_after_receive=False) -> None:
        self.deliveries = list(deliveries)
        self.drain = drain
        self.drain_after_receive = drain_after_receive
        self.receive_calls = 0

    def receive(self, timeout: timedelta):
        self.receive_calls += 1
        delivery = self.deliveries.pop(0) if self.deliveries else None
        if self.drain_after_receive:
            self.drain.requested = True
        return delivery


class Worker:
    def __init__(self, drain=None) -> None:
        self.drain = drain
        self.deliveries = []

    def process(self, delivery, owner: str) -> ProcessOutcome:
        self.deliveries.append(delivery)
        if self.drain is not None:
            self.drain.requested = True
        return ProcessOutcome.COMPLETED


def _service(context, deliveries, *, drain_during_process=False):
    context.drain = DrainSignal()
    context.transport = Transport(deliveries)
    context.worker = Worker(context.drain if drain_during_process else None)
    context.service = CommandWorkerService(
        transport=context.transport,
        worker=context.worker,
        owner="worker-one",
        drain=context.drain,
        receive_timeout=timedelta(seconds=10),
        idle_wait=timedelta(seconds=2),
    )


@given("a command service with one delivery followed by an empty receive")
def delivery_then_empty(context):
    context.delivery = Delivery()
    _service(context, [context.delivery, None])


@given("a command service whose idle wait requests drain")
def idle_drain(context):
    _service(context, [None, Delivery()])


@given("a command service whose active execution requests drain")
def drain_during_execution(context):
    context.delivery = Delivery()
    _service(context, [context.delivery], drain_during_process=True)


@given("a command service that observes drain after receiving a delivery")
def drain_after_receive(context):
    context.delivery = Delivery()
    _service(context, [context.delivery])
    context.transport.drain = context.drain
    context.transport.drain_after_receive = True


@given("a command service with an empty receive")
def empty_receive(context):
    _service(context, [None])


@when("the command service runs until drained")
def run_service(context):
    context.outcome = context.service.run()


@then("one delivery is processed successfully")
def processed_once(context):
    assert context.outcome.stop_reason is ServiceStopReason.DRAIN_REQUESTED
    assert context.outcome.processed_count == 1
    assert context.outcome.count(ProcessOutcome.COMPLETED) == 1


@then("the service receives again after completing the command")
def receives_again(context):
    assert context.transport.receive_calls == 2


@then("the service exits without a second receive")
def exits_without_second_receive(context):
    assert context.transport.receive_calls == 1
    assert context.outcome.processed_count == 0


@then("the active delivery settles successfully")
def active_settles(context):
    assert context.worker.deliveries == [context.delivery]
    assert context.outcome.count(ProcessOutcome.COMPLETED) == 1


@then("the service does not receive a second delivery")
def no_second_receive(context):
    assert context.transport.receive_calls == 1


@then("the untouched delivery is released without acknowledgement")
def untouched_released(context):
    assert context.delivery.released
    assert not context.delivery.acknowledged


@then("the received delivery is not processed")
def received_not_processed(context):
    assert context.worker.deliveries == []
    assert context.outcome.processed_count == 0


@then("the configured idle wait is used once")
def idle_wait_used(context):
    assert context.drain.waits == [timedelta(seconds=2)]
    assert context.transport.receive_calls == 1
