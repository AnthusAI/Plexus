from __future__ import annotations

import contextlib
import contextvars
import json
import os
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional

_RUNTIME_ACTOR_CONTEXT: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "plexus_runtime_actor_context",
    default=None,
)

_ACTOR_CONTEXT_JSON_ENV = "PLEXUS_ACTOR_CONTEXT_JSON"


@dataclass(frozen=True)
class ActorContext:
    user_id: Optional[str] = None
    actor_type: str = "service"
    actor_key: str = "cli"
    actor_source: str = "cli"

    def as_dict(self) -> dict[str, str]:
        payload: dict[str, str] = {
            "actor_type": self.actor_type,
            "actor_key": self.actor_key,
            "actor_source": self.actor_source,
        }
        if self.user_id:
            payload["actor_user_id"] = self.user_id
        return payload


def _clean_text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _env_context() -> dict[str, str]:
    payload = _parse_json_object(os.getenv(_ACTOR_CONTEXT_JSON_ENV))
    user_id = _clean_text(payload.get("actor_user_id")) or _clean_text(os.getenv("PLEXUS_ACTOR_USER_ID"))
    actor_type = _clean_text(payload.get("actor_type")) or _clean_text(os.getenv("PLEXUS_ACTOR_TYPE"))
    actor_key = _clean_text(payload.get("actor_key")) or _clean_text(os.getenv("PLEXUS_ACTOR_KEY"))
    actor_source = _clean_text(payload.get("actor_source")) or _clean_text(os.getenv("PLEXUS_ACTOR_SOURCE"))
    out: dict[str, str] = {}
    if user_id:
        out["actor_user_id"] = user_id
    if actor_type:
        out["actor_type"] = actor_type
    if actor_key:
        out["actor_key"] = actor_key
    if actor_source:
        out["actor_source"] = actor_source
    return out


def _normalize_override(override: Any) -> dict[str, str]:
    if override is None:
        return {}
    if isinstance(override, Mapping):
        source = override
    else:
        source = {
            "actor_user_id": getattr(override, "actor_user_id", None)
            or getattr(override, "user_id", None),
            "actor_type": getattr(override, "actor_type", None),
            "actor_key": getattr(override, "actor_key", None),
            "actor_source": getattr(override, "actor_source", None),
        }
    normalized: dict[str, str] = {}
    for key in ("actor_user_id", "actor_type", "actor_key", "actor_source"):
        cleaned = _clean_text(source.get(key)) if isinstance(source, Mapping) else None
        if cleaned:
            normalized[key] = cleaned
    return normalized


def _safe_getattr(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name, None)
    except Exception:
        return None


def resolve_actor_context(
    *,
    request_user_id: Optional[str] = None,
    runtime_override: Any = None,
    explicit_source: str = "cli",
) -> ActorContext:
    request_user_id = _clean_text(request_user_id)
    runtime_data = _normalize_override(runtime_override) or _normalize_override(_RUNTIME_ACTOR_CONTEXT.get())
    env_data = _env_context()

    user_id = request_user_id or runtime_data.get("actor_user_id") or env_data.get("actor_user_id")
    actor_source = runtime_data.get("actor_source") or env_data.get("actor_source") or explicit_source

    default_actor_type = "agent" if actor_source in {"execute_tactus", "agent"} else "service"
    actor_type = runtime_data.get("actor_type") or env_data.get("actor_type") or default_actor_type
    actor_key = runtime_data.get("actor_key") or env_data.get("actor_key") or actor_source

    return ActorContext(
        user_id=user_id,
        actor_type=actor_type,
        actor_key=actor_key,
        actor_source=actor_source,
    )


@contextlib.contextmanager
def set_runtime_actor_context(context: ActorContext | Mapping[str, Any]) -> Iterator[None]:
    normalized = _normalize_override(context)
    token = _RUNTIME_ACTOR_CONTEXT.set(normalized)
    try:
        yield
    finally:
        _RUNTIME_ACTOR_CONTEXT.reset(token)


def apply_actor_context_to_env(env: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    target = dict(env or os.environ)
    actor = resolve_actor_context(explicit_source="worker")
    actor_payload = actor.as_dict()
    target[_ACTOR_CONTEXT_JSON_ENV] = json.dumps(actor_payload, sort_keys=True)
    if actor.user_id:
        target["PLEXUS_ACTOR_USER_ID"] = actor.user_id
    return target


def _find_sub_value(value: Any, *, depth: int = 0) -> Optional[str]:
    if depth > 6:
        return None
    if isinstance(value, Mapping):
        for key in ("sub", "user_id", "userId", "cognito:username", "username"):
            candidate = _clean_text(value.get(key))
            if candidate:
                return candidate
        for child in value.values():
            candidate = _find_sub_value(child, depth=depth + 1)
            if candidate:
                return candidate
        return None
    if isinstance(value, (list, tuple)):
        for child in value:
            candidate = _find_sub_value(child, depth=depth + 1)
            if candidate:
                return candidate
    return None


def extract_request_user_id_from_mcp_context(ctx: Any) -> Optional[str]:
    if ctx is None:
        return None

    for direct in (
        _safe_getattr(ctx, "request_context"),
        _safe_getattr(ctx, "meta"),
        _safe_getattr(ctx, "_meta"),
        _safe_getattr(ctx, "session"),
        _safe_getattr(ctx, "__dict__"),
    ):
        candidate = _find_sub_value(direct)
        if candidate:
            return candidate
    return None


def _merge_metadata_with_attribution(
    metadata: Any,
    *,
    actor: ActorContext,
) -> dict[str, Any]:
    base = _parse_json_object(metadata)
    attribution = base.get("attribution")
    if not isinstance(attribution, dict):
        attribution = {}

    attribution.setdefault("actorType", actor.actor_type)
    attribution.setdefault("actorKey", actor.actor_key)
    attribution.setdefault("source", actor.actor_source)
    if actor.user_id:
        attribution.setdefault("requestUserId", actor.user_id)

    base["attribution"] = attribution
    return base


def apply_actor_attribution(
    input_data: dict[str, Any],
    *,
    client_context: Any = None,
    request_user_id: Optional[str] = None,
    source: str = "cli",
) -> dict[str, Any]:
    actor = resolve_actor_context(
        request_user_id=request_user_id,
        runtime_override=client_context,
        explicit_source=source,
    )

    result = dict(input_data)
    if actor.user_id and not _clean_text(result.get("createdByUserId")):
        result["createdByUserId"] = actor.user_id
    result["metadata"] = _merge_metadata_with_attribution(
        result.get("metadata"),
        actor=actor,
    )
    return result
