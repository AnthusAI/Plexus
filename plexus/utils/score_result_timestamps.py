import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class ScoreResultTimestamps:
    start_time_seconds: Optional[float] = None
    end_time_seconds: Optional[float] = None

    @property
    def has_any(self) -> bool:
        return self.start_time_seconds is not None or self.end_time_seconds is not None

    def as_graphql_input(self) -> dict:
        data = {}
        if self.start_time_seconds is not None:
            data["startTimeSeconds"] = self.start_time_seconds
        if self.end_time_seconds is not None:
            data["endTimeSeconds"] = self.end_time_seconds
        return data


STRUCTURED_START_KEYS = ("start_time_seconds", "startTimeSeconds", "start")
STRUCTURED_END_KEYS = ("end_time_seconds", "endTimeSeconds", "end")

BRACKET_SPAN_PATTERN = re.compile(
    r"\[\s*(?P<start>\d+(?::\d+){0,2}(?:\.\d+)?s?)\s*-\s*"
    r"(?P<end>\d+(?::\d+){0,2}(?:\.\d+)?s?)\s*\]"
)
BRACKET_SINGLE_PATTERN = re.compile(r"\[\s*(?P<start>\d+(?::\d+){0,2}(?:\.\d+)?)s\s*\]")


def extract_score_result_timestamps(
    source: Optional[Mapping[str, Any]] = None,
    explanation: Optional[str] = None,
) -> ScoreResultTimestamps:
    """
    Normalize ScoreResult evidence timestamps from structured output first,
    falling back to the first bracketed span in explanation text.
    """
    source = source or {}
    structured_start = _first_coerced(source, STRUCTURED_START_KEYS)
    structured_end = _first_coerced(source, STRUCTURED_END_KEYS)

    parsed = parse_first_timestamp_span(explanation)
    return ScoreResultTimestamps(
        start_time_seconds=structured_start
        if structured_start is not None
        else parsed.start_time_seconds,
        end_time_seconds=structured_end if structured_end is not None else parsed.end_time_seconds,
    )


def parse_first_timestamp_span(explanation: Optional[str]) -> ScoreResultTimestamps:
    if not explanation:
        return ScoreResultTimestamps()

    span_match = BRACKET_SPAN_PATTERN.search(explanation)
    if span_match:
        return ScoreResultTimestamps(
            start_time_seconds=_coerce_seconds(span_match.group("start")),
            end_time_seconds=_coerce_seconds(span_match.group("end")),
        )

    single_match = BRACKET_SINGLE_PATTERN.search(explanation)
    if single_match:
        return ScoreResultTimestamps(start_time_seconds=_coerce_seconds(single_match.group("start")))

    return ScoreResultTimestamps()


def _first_coerced(source: Mapping[str, Any], keys: tuple[str, ...]) -> Optional[float]:
    for key in keys:
        if key in source:
            value = _coerce_seconds(source.get(key))
            if value is not None:
                return value
    return None


def _coerce_seconds(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        if value.endswith("s"):
            value = value[:-1].strip()
        if ":" in value:
            return _parse_colon_time(value)
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _parse_colon_time(value: str) -> Optional[float]:
    parts = value.split(":")
    if len(parts) not in (2, 3):
        return None
    try:
        numeric_parts = [float(part) for part in parts]
    except ValueError:
        return None
    if len(numeric_parts) == 2:
        minutes, seconds = numeric_parts
        return minutes * 60 + seconds
    hours, minutes, seconds = numeric_parts
    return hours * 3600 + minutes * 60 + seconds
