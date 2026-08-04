"""Provider-neutral command application service."""

from __future__ import annotations

from uuid import uuid4

from .models import (
    AnnouncementDisposition,
    AuditEvent,
    AuditEventType,
    AuthenticatedCommandContext,
    AuthorizationDecision,
    CancellationResult,
    CommandLimits,
    CommandRecord,
    CommandRequest,
    CommandStatus,
    DEFAULT_COMMAND_LIMITS,
    SubmissionDisposition,
    SubmissionResult,
    request_digest,
)
from .ports import (
    AuditSink,
    Clock,
    CommandAuthorizer,
    CommandIdGenerator,
    CommandRepository,
)


IDEMPOTENCY_NAMESPACE = "command.submit:v1"


class CommandNotFound(LookupError):
    """A tenant-scoped command lookup did not resolve or was not authorized."""

    def __init__(self, command_id: str) -> None:
        super().__init__(f"command not found: {command_id}")


class IdempotencyConflict(ValueError):
    """An actor reused an idempotency key for different canonical work."""

    def __init__(self) -> None:
        super().__init__("idempotency key conflicts with an existing command")


class AuthorizationDenied(PermissionError):
    """Submission was denied or its target is not registered."""

    def __init__(self) -> None:
        super().__init__("command submission is not authorized")


class UUIDCommandIdGenerator:
    def new_id(self) -> str:
        return str(uuid4())


class CommandService:
    """Application boundary for context verified by an authentication adapter."""

    def __init__(
        self,
        repository: CommandRepository,
        clock: Clock,
        command_ids: CommandIdGenerator,
        authorizer: CommandAuthorizer,
        audit: AuditSink,
        limits: CommandLimits = DEFAULT_COMMAND_LIMITS,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._command_ids = command_ids
        self._authorizer = authorizer
        self._audit = audit
        self._limits = limits

    def submit(
        self, context: AuthenticatedCommandContext, request: CommandRequest
    ) -> SubmissionResult:
        self._require_context(context)
        if not isinstance(request, CommandRequest):
            raise TypeError("request must be a CommandRequest")
        self._validate_identifier(request.target, "target")
        self._validate_identifier(
            request.idempotency_key, "idempotency_key", idempotency=True
        )
        digest = request_digest(request.target, request.payload, self._limits)
        decision = self._require_decision(self._authorizer.can_submit(context, request))
        if not decision.allowed:
            self._record(
                context,
                AuditEventType.AUTHORIZATION_DENIED,
                target=request.target,
                outcome="submit",
                policy_version=decision.policy_version,
            )
            raise AuthorizationDenied()

        now = self._clock.now()
        command_id = self._command_ids.new_id()
        self._validate_identifier(command_id, "command_id")
        command = CommandRecord(
            command_id=command_id,
            tenant_id=context.tenant_id,
            target=request.target,
            idempotency_key=request.idempotency_key,
            idempotency_namespace=IDEMPOTENCY_NAMESPACE,
            created_at=now,
            updated_at=now,
            submitted_by=context.principal_id,
            payload=request.payload,
            status=CommandStatus.ANNOUNCED,
            request_digest=digest,
        )
        announcement = self._repository.announce(command)
        if announcement.disposition is AnnouncementDisposition.CONFLICT:
            self._record(
                context,
                AuditEventType.IDEMPOTENCY_CONFLICT,
                command_id=announcement.command.command_id,
                target=request.target,
                outcome="conflict",
                policy_version=decision.policy_version,
            )
            raise IdempotencyConflict()
        disposition = (
            SubmissionDisposition.NEW
            if announcement.disposition is AnnouncementDisposition.NEW
            else SubmissionDisposition.EXISTING
        )
        self._record(
            context,
            AuditEventType.SUBMIT_CREATED
            if disposition is SubmissionDisposition.NEW
            else AuditEventType.SUBMIT_EXISTING,
            command_id=announcement.command.command_id,
            target=announcement.command.target,
            outcome=disposition.value,
            policy_version=decision.policy_version,
        )
        return SubmissionResult(announcement.command, disposition)

    def get(
        self, context: AuthenticatedCommandContext, command_id: str
    ) -> CommandRecord:
        self._require_context(context)
        self._validate_identifier(command_id, "command_id")
        command = self._repository.get(context.tenant_id, command_id)
        if command is None:
            self._record(
                context,
                AuditEventType.READ,
                command_id=command_id,
                outcome="not_found",
            )
            raise CommandNotFound(command_id)
        decision = self._require_decision(self._authorizer.can_read(context, command))
        if not decision.allowed:
            self._record(
                context,
                AuditEventType.AUTHORIZATION_DENIED,
                command_id=command_id,
                target=command.target,
                outcome="read",
                policy_version=decision.policy_version,
            )
            raise CommandNotFound(command_id)
        self._record(
            context,
            AuditEventType.READ,
            command_id=command_id,
            target=command.target,
            outcome="found",
            policy_version=decision.policy_version,
        )
        return command

    def cancel(
        self, context: AuthenticatedCommandContext, command_id: str
    ) -> CancellationResult:
        self._require_context(context)
        self._validate_identifier(command_id, "command_id")
        command = self._repository.get(context.tenant_id, command_id)
        if command is None:
            self._record(
                context,
                AuditEventType.CANCELLATION,
                command_id=command_id,
                outcome="not_found",
            )
            raise CommandNotFound(command_id)
        decision = self._require_decision(self._authorizer.can_cancel(context, command))
        if not decision.allowed:
            self._record(
                context,
                AuditEventType.AUTHORIZATION_DENIED,
                command_id=command_id,
                target=command.target,
                outcome="cancel",
                policy_version=decision.policy_version,
            )
            raise CommandNotFound(command_id)
        cancellation = self._repository.request_cancel(
            context.tenant_id, command_id, self._clock.now()
        )
        self._record(
            context,
            AuditEventType.CANCELLATION,
            command_id=command_id,
            target=cancellation.command.target if cancellation else None,
            outcome=(
                cancellation.command.status.value if cancellation else "not_found"
            ),
            policy_version=decision.policy_version,
        )
        if cancellation is None:
            raise CommandNotFound(command_id)
        return cancellation

    def _require_context(self, context: AuthenticatedCommandContext) -> None:
        if not isinstance(context, AuthenticatedCommandContext):
            raise TypeError("context must be an AuthenticatedCommandContext")
        for name in (
            "tenant_id",
            "principal_id",
            "principal_type",
            "authentication_method",
            "correlation_id",
        ):
            self._validate_identifier(getattr(context, name), name)

    @staticmethod
    def _require_decision(decision: AuthorizationDecision) -> AuthorizationDecision:
        if not isinstance(decision, AuthorizationDecision):
            raise TypeError("authorizer must return an AuthorizationDecision")
        return decision

    def _validate_identifier(
        self, value: str, name: str, *, idempotency: bool = False
    ) -> None:
        maximum = (
            self._limits.max_idempotency_key_length
            if idempotency
            else self._limits.max_identifier_length
        )
        if len(value) > maximum:
            raise ValueError(f"{name} exceeds maximum length")

    def _record(
        self,
        context: AuthenticatedCommandContext,
        event_type: AuditEventType,
        *,
        outcome: str,
        command_id: str | None = None,
        target: str | None = None,
        policy_version: str | None = None,
    ) -> None:
        self._audit.record(
            AuditEvent(
                event_type=event_type,
                occurred_at=self._clock.now(),
                tenant_id=context.tenant_id,
                principal_id=context.principal_id,
                principal_type=context.principal_type,
                authentication_method=context.authentication_method,
                correlation_id=context.correlation_id,
                outcome=outcome,
                command_id=command_id,
                target=target,
                policy_version=policy_version,
            )
        )
