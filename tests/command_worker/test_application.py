from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from plexus.command_worker import (
    AuditEventType,
    AuthenticatedCommandContext,
    AuthorizationDecision,
    AuthorizationDenied,
    ClaimStatus,
    CommandEnvelope,
    CommandLimits,
    CommandNotFound,
    CommandRequest,
    CommandService,
    CommandStatus,
    IdempotencyConflict,
    InMemoryCommandRepository,
    SubmissionDisposition,
    UUIDCommandIdGenerator,
    request_digest,
)


NOW = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)


class Clock:
    def now(self):
        return NOW


class Ids:
    def __init__(self):
        self.number = 0

    def new_id(self):
        self.number += 1
        return f"command-{self.number}"


class Authorizer:
    policy_version = "test-policy-v3"

    def __init__(self, targets=("evaluate",), read=True, cancel=True):
        self.targets = set(targets)
        self.read = read
        self.cancel = cancel

    def can_submit(self, context, command_request):
        return AuthorizationDecision(
            command_request.target in self.targets, self.policy_version
        )

    def can_read(self, context, command):
        return AuthorizationDecision(self.read, self.policy_version)

    def can_cancel(self, context, command):
        return AuthorizationDecision(self.cancel, self.policy_version)


class Audit:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


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


def actor(tenant="tenant-one", principal="principal-one"):
    return AuthenticatedCommandContext(
        tenant_id=tenant,
        principal_id=principal,
        principal_type="user",
        authentication_method="signed-token",
        correlation_id="request-one",
    )


def request(**overrides):
    values = {
        "target": "evaluate",
        "idempotency_key": "key-one",
        "payload": {"input": {"ids": ["one", "two"]}},
    }
    values.update(overrides)
    return CommandRequest(**values)


def service(*, repository=None, authorizer=None, audit=None, limits=None):
    return CommandService(
        repository or InMemoryCommandRepository(),
        Clock(),
        Ids(),
        authorizer or Authorizer(),
        audit or Audit(),
        limits or CommandLimits(),
    )


def test_request_and_context_are_immutable_and_payload_is_deeply_frozen():
    context = actor()
    command_request = request()

    with pytest.raises(FrozenInstanceError):
        context.tenant_id = "changed"
    with pytest.raises(FrozenInstanceError):
        command_request.target = "changed"
    with pytest.raises(TypeError):
        command_request.payload["input"]["ids"][0] = "changed"


def test_digest_is_versioned_sha256_and_independent_of_map_order():
    first = request_digest("evaluate", {"b": 2, "a": {"y": 1, "x": 0}})
    second = request_digest("evaluate", {"a": {"x": 0, "y": 1}, "b": 2})

    assert first == second
    assert first.algorithm == "sha256"
    assert first.canonicalization_version == 1
    assert len(first.value) == 64
    assert request_digest("different", {"b": 2, "a": {"y": 1, "x": 0}}) != first


@pytest.mark.parametrize(
    "limits,payload,error",
    [
        (CommandLimits(max_json_depth=2), {"one": {"two": {}}}, "depth"),
        (CommandLimits(max_json_containers=2), {"one": [], "two": []}, "container"),
        (CommandLimits(max_json_bytes=8), {"value": "too long"}, "byte"),
    ],
)
def test_configurable_json_limits_reject_before_repository_announce(
    limits, payload, error
):
    class NeverRepository:
        def announce(self, command):
            pytest.fail("invalid work must not reach durable announce")

    command_service = service(repository=NeverRepository(), limits=limits)

    with pytest.raises(ValueError, match=error):
        command_service.submit(actor(), request(payload=payload))


def test_identifier_and_idempotency_limits_are_configurable():
    command_service = service(limits=CommandLimits(max_identifier_length=8))

    with pytest.raises(ValueError, match="tenant_id"):
        command_service.submit(actor(tenant="tenant-too-long"), request())

    command_service = service(limits=CommandLimits(max_idempotency_key_length=3))
    with pytest.raises(ValueError, match="idempotency_key"):
        command_service.submit(actor(), request(idempotency_key="long"))


def test_submission_uses_trusted_context_not_payload_identity():
    result = service().submit(
        actor(tenant="trusted-tenant", principal="trusted-principal"),
        request(payload={"tenant_id": "untrusted", "principal_id": "untrusted"}),
    )

    assert result.command.tenant_id == "trusted-tenant"
    assert result.command.submitted_by == "trusted-principal"
    assert not hasattr(result.command.envelope, "submitted_by")


def test_unknown_target_and_denied_submission_fail_before_repository_access():
    class NeverRepository:
        def announce(self, command):
            pytest.fail("unauthorized work must not reach the repository")

    audit = Audit()
    command_service = service(repository=NeverRepository(), audit=audit)

    with pytest.raises(AuthorizationDenied):
        command_service.submit(actor(), request(target="unregistered"))

    assert audit.events[-1].event_type is AuditEventType.AUTHORIZATION_DENIED
    assert audit.events[-1].outcome == "submit"
    assert audit.events[-1].policy_version == "test-policy-v3"


def test_submit_authorization_receives_the_immutable_resource_bearing_request():
    class RecordingAuthorizer(Authorizer):
        seen = None

        def can_submit(self, context, command_request):
            self.seen = command_request
            return super().can_submit(context, command_request)

    authorizer = RecordingAuthorizer()
    command_request = request(payload={"resource_id": "resource-one"})

    service(authorizer=authorizer).submit(actor(), command_request)

    assert authorizer.seen is command_request
    with pytest.raises(TypeError):
        authorizer.seen.payload["resource_id"] = "changed"


def test_denied_read_and_cancel_are_indistinguishable_from_absence():
    repository = InMemoryCommandRepository()
    command_service = service(repository=repository)
    command = command_service.submit(actor(), request()).command
    denied = service(
        repository=repository, authorizer=Authorizer(read=False, cancel=False)
    )

    messages = []
    for operation in (denied.get, denied.cancel):
        with pytest.raises(CommandNotFound) as error:
            operation(actor(), command.command_id)
        messages.append(str(error.value))

    assert messages[0] == messages[1]
    assert (
        repository.get("tenant-one", command.command_id).status
        is CommandStatus.ANNOUNCED
    )


def test_denied_and_absent_resource_access_are_both_audited_without_disclosure():
    repository = InMemoryCommandRepository()
    command = service(repository=repository).submit(actor(), request()).command
    audit = Audit()
    denied = service(
        repository=repository,
        authorizer=Authorizer(read=False, cancel=False),
        audit=audit,
    )

    for operation, context in (
        (denied.get, actor()),
        (denied.cancel, actor()),
        (denied.get, actor(tenant="other")),
        (denied.cancel, actor(tenant="other")),
    ):
        with pytest.raises(CommandNotFound):
            operation(context, command.command_id)

    assert [event.event_type for event in audit.events] == [
        AuditEventType.AUTHORIZATION_DENIED,
        AuditEventType.AUTHORIZATION_DENIED,
        AuditEventType.READ,
        AuditEventType.CANCELLATION,
    ]
    assert [event.policy_version for event in audit.events] == [
        "test-policy-v3",
        "test-policy-v3",
        None,
        None,
    ]


def test_read_and_cancel_authorization_receive_tenant_scoped_record():
    class RecordingAuthorizer(Authorizer):
        def __init__(self):
            super().__init__()
            self.records = []

        def can_read(self, context, command):
            self.records.append(command)
            return super().can_read(context, command)

        def can_cancel(self, context, command):
            self.records.append(command)
            return super().can_cancel(context, command)

    repository = InMemoryCommandRepository()
    authorizer = RecordingAuthorizer()
    command_service = service(repository=repository, authorizer=authorizer)
    command = command_service.submit(actor(), request()).command

    command_service.get(actor(), command.command_id)
    command_service.cancel(actor(), command.command_id)

    assert authorizer.records == [command, command]


def test_reference_announce_is_atomic_idempotent_and_concurrency_safe():
    repository = InMemoryCommandRepository()
    command_service = service(repository=repository)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _: command_service.submit(actor(), request()), range(20))
        )

    command_ids = {result.command.command_id for result in results}
    assert len(command_ids) == 1
    assert sum(r.disposition is SubmissionDisposition.NEW for r in results) == 1
    assert len(repository.discoverable_dispatches()) == 1
    stored = repository.get("tenant-one", next(iter(command_ids)))
    assert stored is not None
    assert repository.discoverable_dispatches() == (stored.envelope,)
    assert not hasattr(repository, "claim")


def test_idempotency_is_principal_scoped_and_conflicts_on_changed_work():
    repository = InMemoryCommandRepository()
    command_service = service(
        repository=repository, authorizer=Authorizer(("evaluate", "optimize"))
    )
    first = command_service.submit(actor(principal="one"), request()).command
    second = command_service.submit(actor(principal="two"), request()).command

    assert first.command_id != second.command_id
    secret_key = "secret-idempotency-material"
    command_service.submit(actor(principal="one"), request(idempotency_key=secret_key))
    with pytest.raises(IdempotencyConflict) as error:
        command_service.submit(
            actor(principal="one"),
            request(target="optimize", idempotency_key=secret_key),
        )
    assert secret_key not in str(error.value)


def test_wrong_tenant_get_and_cancel_have_identical_not_found_behavior():
    command_service = service()
    command = command_service.submit(actor(), request()).command

    messages = []
    for operation in (command_service.get, command_service.cancel):
        with pytest.raises(CommandNotFound) as error:
            operation(actor(tenant="other"), command.command_id)
        messages.append(str(error.value))

    assert messages[0] == messages[1]


def test_cancellation_transitions_and_terminal_semantics_are_explicit():
    repository = InMemoryCommandRepository()
    command_service = service(repository=repository)
    announced = command_service.submit(actor(), request()).command
    cancelled = command_service.cancel(actor(), announced.command_id)

    assert cancelled.command.status is CommandStatus.CANCELLED
    assert cancelled.command.status.is_terminal
    assert (
        RepositoryLifecycleVerifier(repository).claim(
            announced.envelope, "worker", NOW, timedelta(minutes=5)
        )
        is ClaimStatus.TERMINAL
    )

    running = command_service.submit(
        actor(), request(idempotency_key="running")
    ).command
    repository.set_status("tenant-one", running.command_id, CommandStatus.RUNNING)
    requested = command_service.cancel(actor(), running.command_id)
    repeated = command_service.cancel(actor(), running.command_id)
    assert requested.command.status is CommandStatus.CANCEL_REQUESTED
    assert not requested.command.status.is_terminal
    assert repeated.command.status is CommandStatus.CANCEL_REQUESTED
    assert repeated.changed is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("command_id", "different-command"),
        ("tenant_id", "different-tenant"),
        ("target", "different-target"),
        ("idempotency_key", "different-key"),
        ("created_at", "2026-08-04T13:00:00+00:00"),
        ("payload", {"input": {"ids": ["different"]}}),
    ],
)
def test_reference_claim_rejects_each_untrusted_envelope_identity_mismatch(
    field, value
):
    repository = InMemoryCommandRepository()
    command = service(repository=repository).submit(actor(), request()).command
    message = command.envelope.to_message()
    message[field] = value
    untrusted = CommandEnvelope.from_message(message)

    assert (
        RepositoryLifecycleVerifier(repository).claim(
            untrusted, "worker", NOW, timedelta(minutes=5)
        )
        is ClaimStatus.INTEGRITY_MISMATCH
    )


def test_audit_events_are_structured_and_payload_free_for_all_outcomes():
    repository = InMemoryCommandRepository()
    audit = Audit()
    command_service = service(
        repository=repository,
        authorizer=Authorizer(("evaluate", "optimize")),
        audit=audit,
    )
    command = command_service.submit(actor(), request()).command
    command_service.submit(actor(), request())
    with pytest.raises(IdempotencyConflict):
        command_service.submit(actor(), request(target="optimize"))
    command_service.get(actor(), command.command_id)
    command_service.cancel(actor(), command.command_id)

    assert [event.event_type for event in audit.events] == [
        AuditEventType.SUBMIT_CREATED,
        AuditEventType.SUBMIT_EXISTING,
        AuditEventType.IDEMPOTENCY_CONFLICT,
        AuditEventType.READ,
        AuditEventType.CANCELLATION,
    ]
    assert all(not hasattr(event, "payload") for event in audit.events)
    assert all(not hasattr(event, "result") for event in audit.events)
    assert all(event.principal_type == "user" for event in audit.events)
    assert all(event.authentication_method == "signed-token" for event in audit.events)
    assert all(event.policy_version == "test-policy-v3" for event in audit.events)


def test_uuid_generator_returns_distinct_standard_uuid_strings():
    from uuid import UUID

    generator = UUIDCommandIdGenerator()
    first = generator.new_id()
    second = generator.new_id()

    assert UUID(first)
    assert UUID(second)
    assert first != second


def test_version_one_messages_are_rejected_without_fallback():
    command = service().submit(actor(), request()).command
    message = command.envelope.to_message()
    message["schema_version"] = 1

    with pytest.raises(ValueError, match="schema_version must be 2"):
        CommandEnvelope.from_message(message)
