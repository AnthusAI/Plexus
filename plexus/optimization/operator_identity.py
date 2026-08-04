"""Stable, human-readable identities for optimization work.

Machine identifiers remain in evidence and mutation preconditions.  This
module deliberately projects only operator-safe names and selector counts.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence


_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OptimizationOperatorIdentity:
    kind: str
    display_title: str
    display_scope: str

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "display_title": self.display_title,
            "display_scope": self.display_scope,
        }


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split()).strip()
    if not normalized or _UUID.fullmatch(normalized):
        return None
    return normalized[:240]


def _collection_values(value: Any) -> list[Any]:
    """Accept Python sequences and Lua-array mappings from the runtime bridge."""
    if isinstance(value, Mapping):
        return list(value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _values(value: Any) -> list[str]:
    return [text for item in _collection_values(value) if (text := _text(item))]


def _name_list(names: Sequence[str]) -> str:
    unique = sorted(set(names), key=str.casefold)
    if len(unique) == 1:
        return unique[0]
    if len(unique) == 2:
        return f"{unique[0]} and {unique[1]}"
    if len(unique) <= 4:
        return f"{', '.join(unique[:-1])}, and {unique[-1]}"
    return f"{', '.join(unique[:3])}, and {len(unique) - 3} more scorecards"


def _quoted_prefixes(prefixes: Sequence[str]) -> str:
    quoted = [f'"{prefix.replace(chr(34), chr(39))}"' for prefix in prefixes]
    if len(quoted) == 1:
        return quoted[0]
    if len(quoted) == 2:
        return f"{quoted[0]} or {quoted[1]}"
    return f"{', '.join(quoted[:-1])}, or {quoted[-1]}"


def _feedback_survey_title(
    *,
    prefixes: Sequence[str],
    safe_scorecard: str | None,
    matched_names: Sequence[str],
) -> str:
    """Name a survey by the operator's useful scope, not its implementation."""
    if len(prefixes) == 1:
        return f"Feedback survey: {prefixes[0]}"
    if safe_scorecard:
        return f"Feedback survey: {safe_scorecard}"
    if len(matched_names) == 1:
        return f"Feedback survey: {matched_names[0]}"
    return "Feedback survey: Selected scorecards"


def optimization_operator_identity(
    *,
    scope: Mapping[str, Any] | None = None,
    scorecard_name: str | None = None,
    score_name: str | None = None,
    matched_scorecard_names: Sequence[str] | None = None,
) -> OptimizationOperatorIdentity:
    """Classify an optimization and construct its operator-safe display text."""

    safe_scorecard = _text(scorecard_name)
    safe_score = _text(score_name)
    if safe_score:
        display_scope = (
            f"{safe_scorecard} / {safe_score}" if safe_scorecard else safe_score
        )
        return OptimizationOperatorIdentity(
            kind="single_score",
            display_title="Single-score optimization",
            display_scope=display_scope,
        )

    scope = scope if isinstance(scope, Mapping) else {}
    scorecard_ids = scope.get("scorecard_ids")
    exact_count = len(_collection_values(scorecard_ids))
    prefixes = _values(scope.get("scorecard_name_prefixes"))
    matched_names = _values(matched_scorecard_names)
    scoped = bool(exact_count or prefixes or safe_scorecard or matched_names)

    if not scoped:
        return OptimizationOperatorIdentity(
            kind="account_wide_portfolio",
            display_title="Feedback survey: All",
            display_scope="All scorecards",
        )

    if matched_names:
        display_scope = _name_list(matched_names)
    else:
        parts: list[str] = []
        if safe_scorecard:
            parts.append(safe_scorecard)
        elif exact_count:
            noun = "scorecard" if exact_count == 1 else "scorecards"
            parts.append(f"{exact_count} selected {noun}")
        if prefixes:
            parts.append(
                f"scorecard names beginning with {_quoted_prefixes(prefixes)}"
            )
        display_scope = " plus ".join(parts) or "Selected scorecards"

    return OptimizationOperatorIdentity(
        kind="scorecard_scoped_portfolio",
        display_title=_feedback_survey_title(
            prefixes=prefixes,
            safe_scorecard=safe_scorecard,
            matched_names=matched_names,
        ),
        display_scope=display_scope,
    )
