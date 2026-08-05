"""Strict shared contract for native Tactus scheduled continuations.

The payload is intentionally small because it is copied into durable Procedure
and Task metadata.  It contains no provider error text or mutable execution
state; the indexed Tactus checkpoint remains the authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


_REQUEST_FIELDS = frozenset({"key", "resume_at", "reason"})


def canonical_time_wait_request(value: Any) -> dict[str, str] | None:
    """Validate and normalize the exact public ``Procedure.defer`` payload."""
    if not isinstance(value, Mapping) or set(value) != _REQUEST_FIELDS:
        return None
    key = value.get("key")
    resume_at = value.get("resume_at")
    reason = value.get("reason")
    if not all(isinstance(item, str) and item.strip() for item in (key, resume_at, reason)):
        return None
    if key != key.strip() or reason != reason.strip() or resume_at != resume_at.strip():
        return None
    try:
        due = datetime.fromisoformat(resume_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if due.tzinfo is None or due.utcoffset() != timezone.utc.utcoffset(due):
        return None
    normalized = due.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    # Equality protects the durable boundary from equivalent-but-ambiguous
    # offsets and makes Procedure/Task/checkpoint comparisons byte-stable.
    if resume_at != normalized:
        return None
    return {"key": key, "resume_at": resume_at, "reason": reason}


def time_wait_is_due(request: Mapping[str, Any], *, now: datetime | None = None) -> bool:
    """Return whether a validated scheduled continuation is due, inclusively."""
    canonical = canonical_time_wait_request(request)
    if canonical is None:
        return False
    due = datetime.fromisoformat(canonical["resume_at"].replace("Z", "+00:00"))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return False
    return current.astimezone(timezone.utc) >= due
