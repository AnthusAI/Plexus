"""App-side redaction helpers for log messages before external ingestion."""

from __future__ import annotations

import logging
import re
from typing import Any


_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
        "[REDACTED_EMAIL]",
    ),
    (
        re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)"),
        "[REDACTED_PHONE]",
    ),
    (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[REDACTED_SSN]",
    ),
    (
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        "[REDACTED_CARD]",
    ),
    (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_ACCESS_KEY]",
    ),
    (
        re.compile(r"(?i)\b(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/=-]+"),
        r"\1[REDACTED_TOKEN]",
    ),
    (
        re.compile(
            r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|token|access[_-]?key|secret[_-]?key)"
            r"(\s*[:=]\s*)"
            r"([^\s,;]+)"
        ),
        r"\1\2[REDACTED_SECRET]",
    ),
)


def redact_text(value: str) -> str:
    redacted = value
    for pattern, replacement in _REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_object(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, tuple):
        return tuple(redact_object(item) for item in value)
    if isinstance(value, list):
        return [redact_object(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_object(item) for key, item in value.items()}
    return value


class RedactingLogFilter(logging.Filter):
    """Redact high-risk values before handlers format or ship a record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            record.msg = redact_object(record.msg)
            record.args = redact_object(record.args)
            return True

        record.msg = redact_text(rendered)
        record.args = ()
        return True
