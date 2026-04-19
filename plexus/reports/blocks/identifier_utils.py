from __future__ import annotations

import uuid


def looks_like_uuid(value: str) -> bool:
    try:
        parsed = uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return False
    return str(parsed) == str(value).lower()
