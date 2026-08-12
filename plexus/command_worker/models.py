"""Provider-neutral command and lease value objects."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, ClassVar, Mapping, TypeAlias


JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | Mapping[str, "JSONValue"] | tuple["JSONValue", ...]


@dataclass(frozen=True, slots=True)
class CommandLimits:
    """Provider-neutral safety limits; adapters may impose stricter values."""

    max_identifier_length: int = 256
    max_idempotency_key_length: int = 512
    max_json_depth: int = 32
    max_json_containers: int = 10_000
    max_json_bytes: int = 1_048_576

    def __post_init__(self) -> None:
        for name in (
            "max_identifier_length",
            "max_idempotency_key_length",
            "max_json_depth",
            "max_json_containers",
            "max_json_bytes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


DEFAULT_COMMAND_LIMITS = CommandLimits()


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def freeze_json(
    value: Any,
    path: str = "payload",
    limits: CommandLimits = DEFAULT_COMMAND_LIMITS,
) -> JSONValue:
    """Validate JSON-compatible input and return an immutable snapshot."""

    containers = [0]

    def freeze(item: Any, item_path: str, depth: int) -> JSONValue:
        if item is None or isinstance(item, (str, bool)):
            return item
        if isinstance(item, int):
            return item
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError(f"{item_path} contains a non-finite number")
            return item
        if isinstance(item, (list, Mapping)):
            if depth > limits.max_json_depth:
                raise ValueError(f"{path} exceeds maximum JSON depth")
            containers[0] += 1
            if containers[0] > limits.max_json_containers:
                raise ValueError(f"{path} exceeds maximum JSON container count")
        if isinstance(item, list):
            return tuple(freeze(child, f"{item_path}[]", depth + 1) for child in item)
        if isinstance(item, Mapping):
            frozen: dict[str, JSONValue] = {}
            for key, child in item.items():
                if not isinstance(key, str):
                    raise TypeError(f"{item_path} keys must be strings")
                frozen[key] = freeze(child, f"{item_path}.{key}", depth + 1)
            return MappingProxyType(frozen)
        raise TypeError(f"{item_path} contains non-JSON value {type(item).__name__}")

    frozen = freeze(value, path, 1)
    encoded = json.dumps(
        _thaw_json(frozen), allow_nan=False, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    if len(encoded) > limits.max_json_bytes:
        raise ValueError(f"{path} exceeds maximum encoded JSON byte size")
    return frozen


def _thaw_json(value: JSONValue) -> Any:
    """Convert an immutable JSON snapshot to standard message containers."""

    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    """Immutable, versioned command contract shared by all providers."""

    CURRENT_SCHEMA_VERSION: ClassVar[int] = 2
    _MESSAGE_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "command_id",
            "tenant_id",
            "target",
            "idempotency_key",
            "created_at",
            "payload",
        }
    )

    schema_version: int
    command_id: str
    tenant_id: str
    target: str
    idempotency_key: str
    created_at: datetime
    payload: Mapping[str, JSONValue]

    def __post_init__(self) -> None:
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != self.CURRENT_SCHEMA_VERSION
        ):
            raise ValueError(f"schema_version must be {self.CURRENT_SCHEMA_VERSION}")
        for name in ("command_id", "tenant_id", "target", "idempotency_key"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
            maximum = (
                DEFAULT_COMMAND_LIMITS.max_idempotency_key_length
                if name == "idempotency_key"
                else DEFAULT_COMMAND_LIMITS.max_identifier_length
            )
            if len(value) > maximum:
                raise ValueError(f"{name} exceeds maximum length")
        _require_aware(self.created_at, "created_at")
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a JSON object")
        frozen = freeze_json(self.payload)
        if not isinstance(frozen, Mapping):  # pragma: no cover - guarded above
            raise TypeError("payload must be a JSON object")
        object.__setattr__(self, "payload", frozen)

    def to_message(self) -> dict[str, Any]:
        """Create a strict JSON-serializable transport message."""

        return {
            "schema_version": self.schema_version,
            "command_id": self.command_id,
            "tenant_id": self.tenant_id,
            "target": self.target,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at.isoformat(),
            "payload": _thaw_json(self.payload),
        }

    @classmethod
    def from_message(cls, message: Mapping[str, Any]) -> "CommandEnvelope":
        """Validate and deserialize a transport message."""

        if not isinstance(message, Mapping):
            raise TypeError("command message must be a JSON object")
        if not all(isinstance(key, str) for key in message):
            raise TypeError("command message keys must be strings")
        received_fields = set(message)
        if received_fields != cls._MESSAGE_FIELDS:
            missing = sorted(cls._MESSAGE_FIELDS - received_fields)
            extra = sorted(received_fields - cls._MESSAGE_FIELDS)
            raise ValueError(
                f"command message fields are invalid; missing={missing}, extra={extra}"
            )
        created_at = message["created_at"]
        if not isinstance(created_at, str):
            raise TypeError("created_at must be an ISO-8601 string")
        try:
            parsed_created_at = datetime.fromisoformat(created_at)
        except ValueError as exc:
            raise ValueError("created_at must be a valid ISO-8601 datetime") from exc
        payload = message["payload"]
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a JSON object")
        return cls(
            schema_version=message["schema_version"],
            command_id=message["command_id"],
            tenant_id=message["tenant_id"],
            target=message["target"],
            idempotency_key=message["idempotency_key"],
            created_at=parsed_created_at,
            payload=payload,
        )


@dataclass(frozen=True, slots=True)
class RequestDigest:
    algorithm: str
    canonicalization_version: int
    value: str

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ValueError("algorithm must be sha256")
        if self.canonicalization_version != 1:
            raise ValueError("canonicalization_version must be 1")
        if len(self.value) != 64 or any(
            character not in "0123456789abcdef" for character in self.value
        ):
            raise ValueError("value must be a lowercase SHA-256 digest")


def request_digest(
    target: str,
    payload: Mapping[str, Any],
    limits: CommandLimits = DEFAULT_COMMAND_LIMITS,
) -> RequestDigest:
    """Digest strict, bounded, canonically ordered request content."""

    if not isinstance(target, str) or not target.strip():
        raise ValueError("target must be a non-empty string")
    if len(target) > limits.max_identifier_length:
        raise ValueError("target exceeds maximum length")
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a JSON object")
    source = _thaw_json(payload) if isinstance(payload, MappingProxyType) else payload
    frozen = freeze_json(source, limits=limits)
    assert isinstance(frozen, Mapping)
    canonical = json.dumps(
        {"payload": _thaw_json(frozen), "target": target},
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return RequestDigest("sha256", 1, hashlib.sha256(canonical).hexdigest())


class CommandStatus(str, Enum):
    ANNOUNCED = "ANNOUNCED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in {
            CommandStatus.SUCCEEDED,
            CommandStatus.FAILED,
            CommandStatus.CANCELLED,
        }


@dataclass(frozen=True, slots=True)
class AuthenticatedCommandContext:
    """Identity asserted only by a future authentication adapter."""

    tenant_id: str
    principal_id: str
    principal_type: str
    authentication_method: str
    correlation_id: str

    def __post_init__(self) -> None:
        for name in (
            "tenant_id",
            "principal_id",
            "principal_type",
            "authentication_method",
            "correlation_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
            if len(value) > DEFAULT_COMMAND_LIMITS.max_identifier_length:
                raise ValueError(f"{name} exceeds maximum length")


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    policy_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise TypeError("allowed must be a bool")
        if not isinstance(self.policy_version, str) or not self.policy_version.strip():
            raise ValueError("policy_version must be a non-empty string")
        if len(self.policy_version) > DEFAULT_COMMAND_LIMITS.max_identifier_length:
            raise ValueError("policy_version exceeds maximum length")


class AuditEventType(str, Enum):
    SUBMIT_CREATED = "SUBMIT_CREATED"
    SUBMIT_EXISTING = "SUBMIT_EXISTING"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    READ = "READ"
    CANCELLATION = "CANCELLATION"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Structured payload-free security and command audit event."""

    event_type: AuditEventType
    occurred_at: datetime
    tenant_id: str
    principal_id: str
    principal_type: str
    authentication_method: str
    correlation_id: str
    outcome: str
    policy_version: str | None = None
    command_id: str | None = None
    target: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, AuditEventType):
            raise TypeError("event_type must be an AuditEventType")
        _require_aware(self.occurred_at, "occurred_at")
        for name in (
            "tenant_id",
            "principal_id",
            "principal_type",
            "authentication_method",
            "correlation_id",
            "outcome",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        for name in ("command_id", "target", "policy_version"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string when present")


@dataclass(frozen=True, slots=True)
class CommandRequest:
    """Work requested by a trusted adapter; tenant identity is intentionally absent."""

    target: str
    idempotency_key: str
    payload: Mapping[str, JSONValue]

    def __post_init__(self) -> None:
        for name in ("target", "idempotency_key"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
            maximum = (
                DEFAULT_COMMAND_LIMITS.max_idempotency_key_length
                if name == "idempotency_key"
                else DEFAULT_COMMAND_LIMITS.max_identifier_length
            )
            if len(value) > maximum:
                raise ValueError(f"{name} exceeds maximum length")
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a JSON object")
        frozen = freeze_json(self.payload)
        assert isinstance(frozen, Mapping)
        object.__setattr__(self, "payload", frozen)


@dataclass(frozen=True, slots=True)
class CommandRecord:
    """Immutable durable command snapshot."""

    command_id: str
    tenant_id: str
    target: str
    idempotency_key: str
    idempotency_namespace: str
    created_at: datetime
    updated_at: datetime
    submitted_by: str
    payload: Mapping[str, JSONValue]
    status: CommandStatus
    request_digest: RequestDigest

    def __post_init__(self) -> None:
        for name in (
            "command_id",
            "tenant_id",
            "target",
            "idempotency_key",
            "idempotency_namespace",
            "submitted_by",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.request_digest, RequestDigest):
            raise TypeError("request_digest must be a RequestDigest")
        _require_aware(self.created_at, "created_at")
        _require_aware(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if not isinstance(self.status, CommandStatus):
            raise TypeError("status must be a CommandStatus")
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a JSON object")
        source = (
            _thaw_json(self.payload)
            if isinstance(self.payload, MappingProxyType)
            else self.payload
        )
        frozen = freeze_json(source)
        assert isinstance(frozen, Mapping)
        object.__setattr__(self, "payload", frozen)
        expected = request_digest(self.target, frozen)
        if self.request_digest != expected:
            raise ValueError("request_digest must match the canonical request")

    @property
    def envelope(self) -> CommandEnvelope:
        return CommandEnvelope(
            schema_version=CommandEnvelope.CURRENT_SCHEMA_VERSION,
            command_id=self.command_id,
            tenant_id=self.tenant_id,
            target=self.target,
            idempotency_key=self.idempotency_key,
            created_at=self.created_at,
            payload=_thaw_json(self.payload),
        )


class SubmissionDisposition(str, Enum):
    NEW = "NEW"
    EXISTING = "EXISTING"


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    command: CommandRecord
    disposition: SubmissionDisposition


@dataclass(frozen=True, slots=True)
class CancellationResult:
    command: CommandRecord
    changed: bool


class AnnouncementDisposition(str, Enum):
    NEW = "NEW"
    EXISTING = "EXISTING"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class AnnouncementResult:
    command: CommandRecord
    disposition: AnnouncementDisposition


@dataclass(frozen=True, slots=True)
class Claim:
    """A lifecycle-store-issued fencing lease."""

    token: str
    owner: str
    expires_at: datetime
    cancellation_requested: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.token, str) or not self.token:
            raise ValueError("token must be non-empty")
        if not isinstance(self.owner, str) or not self.owner:
            raise ValueError("owner must be non-empty")
        _require_aware(self.expires_at, "expires_at")
        if not isinstance(self.cancellation_requested, bool):
            raise TypeError("cancellation_requested must be a boolean")


@dataclass(frozen=True, slots=True)
class ProgressUpdate:
    fraction: float
    message: str | None = None
    details: Mapping[str, JSONValue] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.fraction, bool) or not isinstance(
            self.fraction, (int, float)
        ):
            raise TypeError("fraction must be a number")
        if (
            isinstance(self.fraction, float) and not math.isfinite(self.fraction)
        ) or not 0.0 <= self.fraction <= 1.0:
            raise ValueError("fraction must be between 0 and 1")
        if self.message is not None and not isinstance(self.message, str):
            raise TypeError("message must be a string")
        if self.details is not None:
            if not isinstance(self.details, Mapping):
                raise TypeError("details must be a JSON object")
            frozen = freeze_json(self.details, "details")
            assert isinstance(frozen, Mapping)
            object.__setattr__(self, "details", frozen)
