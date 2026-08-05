from __future__ import annotations

from datetime import datetime, timedelta, timezone

from behave import given, then, when

from plexus.command_worker import (
    AuthenticatedCommandContext,
    AuthorizationDecision,
    ClaimStatus,
    CommandNotFound,
    CommandRequest,
    CommandService,
    CommandStatus,
    CommandWorker,
    IdempotencyConflict,
    InMemoryCommandRepository,
    SubmissionDisposition,
    request_digest,
)


class Clock:
    def now(self):
        return datetime(2026, 8, 4, tzinfo=timezone.utc)


class Ids:
    def __init__(self):
        self.number = 0

    def new_id(self):
        self.number += 1
        return f"command-{self.number}"


class Authorizer:
    registered_targets = {"evaluate", "optimize"}

    def can_submit(self, context, request):
        return AuthorizationDecision(
            request.target in self.registered_targets, "test-v1"
        )

    def can_read(self, context, command):
        return AuthorizationDecision(True, "test-v1")

    def can_cancel(self, context, command):
        return AuthorizationDecision(True, "test-v1")


class Audit:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


def actor(tenant, principal="principal-one"):
    return AuthenticatedCommandContext(
        tenant_id=tenant,
        principal_id=principal,
        principal_type="user",
        authentication_method="test",
        correlation_id="correlation-one",
    )


def request(target="evaluate", key="request-one", payload=None):
    return CommandRequest(
        target=target,
        idempotency_key=key,
        payload=payload or {"item_ids": ["one", "two"]},
    )


@given("a portable command service")
def portable_service(context):
    context.repository = InMemoryCommandRepository()
    context.audit = Audit()
    context.service = CommandService(
        context.repository, Clock(), Ids(), Authorizer(), context.audit
    )
    context.results = []


def submit(context, tenant, command_request, principal="principal-one"):
    result = context.service.submit(actor(tenant, principal), command_request)
    context.results.append(result)
    context.command = result.command
    return result


@when('tenant "{tenant}" submits command "{target}" with idempotency key "{key}"')
def submits(context, tenant, target, key):
    submit(context, tenant, request(target, key))


@when(
    'principal "{principal}" submits a command for tenant "{tenant}" with key "{key}"'
)
def principal_submits(context, principal, tenant, key):
    submit(context, tenant, request(key=key), principal)


@given('tenant "{tenant}" submitted command "{target}" with idempotency key "{key}"')
def submitted(context, tenant, target, key):
    submit(context, tenant, request(target, key))


@when('tenant "{tenant}" repeats the identical submission')
def repeats(context, tenant):
    submit(context, tenant, request())


@given('tenant "{tenant}" has a running command')
def running(context, tenant):
    submit(context, tenant, request())
    context.repository.set_status(
        tenant, context.command.command_id, CommandStatus.RUNNING
    )


@given('tenant "{tenant}" has a {status} command')
def terminal(context, tenant, status):
    submit(context, tenant, request())
    context.repository.set_status(
        tenant, context.command.command_id, CommandStatus(status.upper())
    )


@when("the same tenant reuses that key with a different {difference}")
def conflicting_submission(context, difference):
    changed = request(
        target="optimize" if difference == "target" else "evaluate",
        payload={"item_ids": ["different"]} if difference == "payload" else None,
    )
    try:
        submit(context, "tenant-one", changed)
    except IdempotencyConflict as error:
        context.error = error


@when('tenant "{tenant}" gets and cancels that command')
def wrong_tenant_access(context, tenant):
    context.errors = []
    for operation in (
        lambda: context.service.get(actor(tenant), context.command.command_id),
        lambda: context.service.cancel(actor(tenant), context.command.command_id),
    ):
        try:
            operation()
        except CommandNotFound as error:
            context.errors.append(error)


@when('tenant "{tenant}" cancels the command')
def cancels(context, tenant):
    context.cancellation = context.service.cancel(
        actor(tenant), context.command.command_id
    )


@when('tenant "{tenant}" cancels the command twice')
def cancels_twice(context, tenant):
    context.first_cancellation = context.service.cancel(
        actor(tenant), context.command.command_id
    )
    context.cancellation = context.service.cancel(
        actor(tenant), context.command.command_id
    )


class Delivery:
    def __init__(self, envelope):
        self.envelope = envelope
        self.events = []

    def acknowledge(self):
        self.events.append("acknowledged")

    def release(self):
        self.events.append("released")

    def quarantine(self, reason):
        self.events.append("quarantined")


class NeverExecutor:
    calls = 0

    def execute(self, envelope, context):
        self.calls += 1
        raise AssertionError("delivery must not execute")


class RepositoryLifecycleVerifier:
    """Test-only executable form of the LifecycleStore claim integrity contract."""

    def __init__(self, repository):
        self.repository = repository

    def claim(self, envelope, owner, now, lease_duration):
        command = self.repository.get(envelope.tenant_id, envelope.command_id)
        if command is None:
            return ClaimStatus.INTEGRITY_MISMATCH
        matches = (
            command.target == envelope.target
            and command.idempotency_key == envelope.idempotency_key
            and command.created_at == envelope.created_at
            and command.request_digest
            == request_digest(envelope.target, envelope.payload)
        )
        if not matches:
            return ClaimStatus.INTEGRITY_MISMATCH
        if command.status.is_terminal:
            return ClaimStatus.TERMINAL
        raise AssertionError(
            "this verifier only exercises terminal and mismatch claims"
        )


def process_delivery(context, envelope):
    context.delivery = Delivery(envelope)
    context.executor = NeverExecutor()
    worker = CommandWorker(
        RepositoryLifecycleVerifier(context.repository),
        context.executor,
        Clock(),
        timedelta(minutes=5),
    )
    context.process_outcome = worker.process(context.delivery, "worker-one")


@when("the command is cancelled before its earlier delivery is processed")
def cancel_before_delivery(context):
    envelope = context.command.envelope
    context.service.cancel(actor("tenant-one"), context.command.command_id)
    process_delivery(context, envelope)


@when("a delivery with a changed payload is processed")
def changed_delivery(context):
    message = context.command.envelope.to_message()
    message["payload"] = {"item_ids": ["changed"]}
    from plexus.command_worker import CommandEnvelope

    process_delivery(context, CommandEnvelope.from_message(message))


@then("a new announced command is returned")
def new_announced(context):
    assert context.results[-1].disposition is SubmissionDisposition.NEW
    assert context.command.status is CommandStatus.ANNOUNCED


@then("the original command is returned as existing")
def original_existing(context):
    assert context.results[-1].disposition is SubmissionDisposition.EXISTING
    assert (
        context.results[-1].command.command_id == context.results[0].command.command_id
    )


@then("exactly one dispatch is discoverable for the command")
def one_dispatch(context):
    assert context.repository.discoverable_dispatches() == (context.command.envelope,)


@then("the submission reports an idempotency conflict")
def conflict(context):
    assert isinstance(context.error, IdempotencyConflict)


@then("both tenants receive different new commands")
def tenant_independence(context):
    assert all(r.disposition is SubmissionDisposition.NEW for r in context.results)
    assert (
        context.results[0].command.command_id != context.results[1].command.command_id
    )


@then("both principals receive different new commands")
def principal_independence(context):
    tenant_independence(context)


@then("both operations report the same not-found behavior")
def same_not_found(context):
    assert len(context.errors) == 2
    assert str(context.errors[0]) == str(context.errors[1])


@then("the command is cancelled")
def cancelled(context):
    assert context.cancellation.command.status is CommandStatus.CANCELLED


@then("no dispatch is discoverable for the command")
def no_dispatch(context):
    assert context.repository.discoverable_dispatches() == ()


@then("the late delivery is acknowledged without execution")
def late_delivery_absorbed(context):
    assert context.delivery.events == ["acknowledged"]
    assert context.executor.calls == 0


@then("the mismatched delivery is quarantined without execution")
def mismatch_quarantined(context):
    assert context.delivery.events == ["quarantined"]
    assert context.executor.calls == 0


@then("cancellation is requested without status regression")
def cancellation_requested(context):
    assert context.first_cancellation.command.status is CommandStatus.CANCEL_REQUESTED
    assert context.cancellation.command.status is CommandStatus.CANCEL_REQUESTED
    assert context.cancellation.changed is False


@then("the command remains {status}")
def remains_terminal(context, status):
    assert context.cancellation.command.status is CommandStatus(status.upper())
    assert context.cancellation.changed is False
