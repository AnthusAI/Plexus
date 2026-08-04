"""Provider-neutral command and lease value objects."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, ClassVar, Mapping, TypeAlias


JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | Mapping[str, "JSONValue"] | tuple["JSONValue", ...]


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def freeze_json(value: Any, path: str = "payload") -> JSONValue:
    """Validate JSON-compatible input and return an immutable snapshot."""

    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, list):
        return tuple(freeze_json(item, f"{path}[]") for item in value)
    if isinstance(value, Mapping):
        frozen: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} keys must be strings")
            frozen[key] = freeze_json(item, f"{path}.{key}")
        return MappingProxyType(frozen)
    raise TypeError(f"{path} contains non-JSON value {type(value).__name__}")


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

    CURRENT_SCHEMA_VERSION: ClassVar[int] = 1
    _MESSAGE_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "command_id",
            "task_id",
            "target",
            "idempotency_key",
            "created_at",
            "payload",
        }
    )

    schema_version: int
    command_id: str
    task_id: str
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
        for name in ("command_id", "task_id", "target", "idempotency_key"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
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
            "task_id": self.task_id,
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
            task_id=message["task_id"],
            target=message["target"],
            idempotency_key=message["idempotency_key"],
            created_at=parsed_created_at,
            payload=payload,
        )


@dataclass(frozen=True, slots=True)
class Claim:
    """A lifecycle-store-issued fencing lease."""

    token: str
    owner: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.token, str) or not self.token:
            raise ValueError("token must be non-empty")
        if not isinstance(self.owner, str) or not self.owner:
            raise ValueError("owner must be non-empty")
        _require_aware(self.expires_at, "expires_at")


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
