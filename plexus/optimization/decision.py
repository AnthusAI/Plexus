"""Pure decision logic for the optimization toolchain.

This module deliberately accepts and returns plain dictionaries and lists.  It
contains no API access, persistence, model calls, or score mutations so the MCP
and CLI surfaces can share identical, reproducible decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from numbers import Real
from typing import Any, Iterable, Mapping, Sequence


PACKET_SCHEMA_VERSION = "optimization-decision-packet-v1"
POLICY_PROFILE_V1: dict[str, Any] = {
    "version": "feedback-investment-v1",
    "timezone": "UTC",
    "complete_days": 90,
    "complete_weeks": 12,
    "minimum_valid_feedback": 200,
    "minimum_final_labels_per_reachable_class": 30,
    "maximum_acceptable_disagreement": 0.10,
    "wilson_confidence": 0.95,
    "latest_weeks_for_stability": 4,
    "maximum_disagreement_range": 0.05,
    "maximum_ac1_range": 0.05,
    # Low-volume weekly buckets are an explanatory warning, never a blocker.
    "weekly_minimum_count": None,
}
SCORE_ACTIVITY_COOLDOWN_V1: dict[str, Any] = {
    "version": "score-activity-cooldown-v1",
    "timezone": "UTC",
    "duration_hours": 168,
    "cutoff_inclusive": True,
}
_WILSON_Z_95 = 1.959963984540054
_RANK_SELECTOR_FIELDS = ("scorecard_ids", "scorecard_name_prefixes")


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return _utc(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return _utc(value)
    normalized = value.replace("Z", "+00:00")
    return _utc(datetime.fromisoformat(normalized))


def _iso_z(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def evaluate_score_activity(
    score: Mapping[str, Any], *, as_of: datetime | str | None = None
) -> dict[str, Any]:
    """Evaluate the fixed rolling cooldown from complete inventory evidence.

    Both the mutable score timestamp and the newest immutable version timestamp
    are required.  Missing or malformed evidence fails closed.  Future
    timestamps are conservatively treated as recent rather than silently
    repairing clock skew.
    """
    frozen_as_of = _parse_utc(as_of) if as_of is not None else datetime.now(timezone.utc)
    duration = timedelta(hours=int(SCORE_ACTIVITY_COOLDOWN_V1["duration_hours"]))
    cutoff = frozen_as_of - duration
    updated_value = score.get("updatedAt", score.get("score_updated_at"))
    versions_value = score.get("versions")
    if isinstance(versions_value, Mapping):
        versions_value = versions_value.get("items")
    versions = list(versions_value or []) if isinstance(versions_value, (list, tuple)) else []
    if not versions and (
        score.get("newest_version_id") or score.get("newest_version_created_at")
    ):
        versions = [{
            "id": score.get("newest_version_id"),
            "createdAt": score.get("newest_version_created_at"),
        }]
    parsed_versions: list[tuple[datetime, str, Any]] = []
    version_failure: str | None = None
    for version in versions:
        if not isinstance(version, Mapping):
            version_failure = "malformed newest version evidence"
            break
        version_id_value = version.get("id")
        created_value = version.get("createdAt")
        if not isinstance(version_id_value, str) or not version_id_value or not isinstance(
            created_value, (str, datetime)
        ) or not created_value:
            version_failure = "missing newest version id or createdAt"
            break
        try:
            parsed_versions.append(
                (_parse_utc(created_value), version_id_value, created_value)
            )
        except (TypeError, ValueError) as exc:
            version_failure = f"malformed newest version timestamp: {exc}"
            break
    newest_parsed = max(parsed_versions, default=None, key=lambda item: item[0])
    version_id = newest_parsed[1] if newest_parsed else None
    version_created_value = newest_parsed[2] if newest_parsed else None

    base = {
        "policy_version": SCORE_ACTIVITY_COOLDOWN_V1["version"],
        "as_of": _iso_z(frozen_as_of),
        "cutoff": _iso_z(cutoff),
        "score_updated_at": updated_value,
        "newest_version_id": version_id,
        "newest_version_created_at": version_created_value,
    }
    missing = []
    if not isinstance(updated_value, (str, datetime)) or not updated_value:
        missing.append("score.updatedAt")
    if not isinstance(version_id, str) or not version_id:
        missing.append("newest version id")
    if not isinstance(version_created_value, (str, datetime)) or not version_created_value:
        missing.append("newest version createdAt")
    if missing or version_failure:
        return {
            **base,
            "activity_source": None,
            "activity_timestamp": None,
            "eligibility_timestamp": None,
            "recent": True,
            "complete": False,
            "failure": ("incomplete inventory activity evidence: " + version_failure)
            if version_failure
            else None
            or "missing inventory activity evidence: " + ", ".join(missing),
        }
    try:
        score_updated = _parse_utc(updated_value)
        version_created = _parse_utc(version_created_value)
    except (TypeError, ValueError) as exc:
        return {
            **base,
            "activity_source": None,
            "activity_timestamp": None,
            "eligibility_timestamp": None,
            "recent": True,
            "complete": False,
            "failure": f"malformed inventory activity timestamp: {exc}",
        }

    if score_updated > version_created:
        activity, source = score_updated, "score_record"
    elif version_created > score_updated:
        activity, source = version_created, "newest_version"
    else:
        activity, source = score_updated, "score_record_and_newest_version"
    return {
        **base,
        "score_updated_at": _iso_z(score_updated),
        "newest_version_created_at": _iso_z(version_created),
        "activity_source": source,
        "activity_timestamp": _iso_z(activity),
        "eligibility_timestamp": _iso_z(activity + duration),
        # The cutoff is inclusive: exactly 168 hours old remains deferred.
        "recent": activity >= cutoff,
        "complete": True,
        "failure": None,
    }


def _validated_score_activity_evidence(
    evidence: Any,
) -> dict[str, Any] | None:
    """Return canonical fixed-policy activity evidence or fail closed.

    Callers may persist decision packets and later submit them at another
    boundary.  Recompute the derived cooldown fields from their source
    timestamps so malformed booleans, timestamps, or internally inconsistent
    evidence cannot bypass the policy.
    """
    if (
        not isinstance(evidence, Mapping)
        or evidence.get("policy_version")
        != SCORE_ACTIVITY_COOLDOWN_V1["version"]
        or evidence.get("complete") is not True
        or type(evidence.get("recent")) is not bool
    ):
        return None
    required_fields = (
        "as_of",
        "cutoff",
        "score_updated_at",
        "newest_version_id",
        "newest_version_created_at",
        "activity_source",
        "activity_timestamp",
        "eligibility_timestamp",
    )
    if not all(evidence.get(field) for field in required_fields):
        return None
    try:
        canonical = evaluate_score_activity(
            {
                "updatedAt": evidence.get("score_updated_at"),
                "versions": [{
                    "id": evidence.get("newest_version_id"),
                    "createdAt": evidence.get("newest_version_created_at"),
                }],
            },
            as_of=evidence.get("as_of"),
        )
        if canonical.get("complete") is not True:
            return None
        if evidence.get("recent") is not canonical.get("recent"):
            return None
        for field in ("newest_version_id", "activity_source"):
            if evidence.get(field) != canonical.get(field):
                return None
        for field in (
            "as_of",
            "cutoff",
            "score_updated_at",
            "newest_version_created_at",
            "activity_timestamp",
            "eligibility_timestamp",
        ):
            if _parse_utc(evidence[field]) != _parse_utc(canonical[field]):
                return None
    except (TypeError, ValueError):
        return None
    return canonical


@dataclass(frozen=True)
class OptimizationDecisionPacket:
    """Versioned portable result envelope shared by every toolchain stage."""

    account_id: str | None
    scope: Mapping[str, Any]
    window: Mapping[str, Any]
    evidence: Mapping[str, Any]
    states: Mapping[str, str]
    primary_next_action: str
    policy_version: str = POLICY_PROFILE_V1["version"]
    champion_version: str | None = None
    feedback_watermark: str | None = None
    secondary_actions: Sequence[str] = field(default_factory=tuple)
    blockers: Sequence[str] = field(default_factory=tuple)
    evidence_ids: Sequence[str] = field(default_factory=tuple)
    rationale: str = ""
    evidence_fingerprint: str | None = None
    stakeholder_questions: Sequence[str] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        evidence = dict(self.evidence)
        fingerprint = self.evidence_fingerprint or evidence_fingerprint(
            {
                "account_id": self.account_id,
                "scope": self.scope,
                "window": self.window,
                "policy_version": self.policy_version,
                "champion_version": self.champion_version,
                "feedback_watermark": self.feedback_watermark,
                "evidence": evidence,
            }
        )
        coverage = {
            "complete": bool(evidence.get("coverage_complete", evidence.get("complete", False))),
            "failures": list(evidence.get("coverage_failures") or evidence.get("failures") or []),
        }
        return {
            "version": PACKET_SCHEMA_VERSION,
            "account_id": self.account_id,
            "scope": _jsonable(dict(self.scope)),
            "window": _jsonable(dict(self.window)),
            "policy_version": self.policy_version,
            "policy": {"version": self.policy_version},
            "champion_version": self.champion_version,
            "champion": self.champion_version,
            "feedback_watermark": self.feedback_watermark,
            "watermark": self.feedback_watermark,
            "coverage": coverage,
            "evidence": _jsonable(evidence),
            "states": dict(self.states),
            "primary_next_action": self.primary_next_action,
            "secondary_actions": list(self.secondary_actions),
            "actions": {"primary": self.primary_next_action, "secondary": list(self.secondary_actions)},
            "blockers": list(self.blockers),
            "evidence_ids": list(self.evidence_ids),
            "rationale": self.rationale,
            "evidence_fingerprint": fingerprint,
            "fingerprint": fingerprint,
            "stakeholder_questions": list(self.stakeholder_questions),
        }


def _packet_result(stage: str, result: Mapping[str, Any], source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Add the common packet envelope without removing legacy stage fields."""
    source = dict(source or {})
    legacy = dict(result)
    source_coverage = dict(source.get("coverage") or {})
    complete = bool(legacy.get("coverage_complete", source_coverage.get("complete", source.get("coverage_complete", source.get("complete", False)))))
    failures = list(legacy.get("coverage_failures") or source_coverage.get("failures") or source.get("coverage_failures") or source.get("failures") or [])
    coverage = {**source_coverage, "complete": complete, "failures": failures}
    guideline = str(legacy.get("guideline_state") or "inconclusive")
    feedback_rubric = str(legacy.get("feedback_rubric_state") or "inconclusive")
    readiness = str(legacy.get("readiness_state") or ("incomplete" if not complete else "inconclusive"))
    post_run = str(legacy.get("post_run_state") or "inconclusive")
    promotion = "promotion_ready" if legacy.get("promotion_ready") or post_run == "promotion_ready" else "inconclusive"
    states = {
        "feedback_collection": str(legacy.get("feedback_collection_state") or "inconclusive"),
        "guideline_health": guideline,
        "guidelines": guideline,
        "feedback_rubric_health": feedback_rubric,
        "feedback_rubric": feedback_rubric,
        "optimization": readiness,
        "readiness": readiness,
        "post_run": post_run,
        "promotion_readiness": promotion,
    }
    scope = dict(source.get("scope") or legacy.get("scope") or {})
    if not scope:
        for key in ("scorecard_id", "score_id"):
            value = source.get(key, legacy.get(key))
            if value is not None:
                scope[key] = value
    evidence_ids = list(legacy.get("evidence_ids") or source.get("evidence_ids") or [])
    packet = OptimizationDecisionPacket(
        account_id=source.get("account_id", source.get("accountId", legacy.get("account_id"))),
        scope=scope,
        window=dict(source.get("window") or source.get("frozen_window") or legacy.get("window") or {}),
        evidence=legacy,
        states=states,
        primary_next_action=str(legacy.get("primary_next_action") or f"{stage}_complete"),
        policy_version=str(legacy.get("policy_version") or source.get("policy_version") or POLICY_PROFILE_V1["version"]),
        champion_version=source.get("champion_version", source.get("championVersionId", legacy.get("champion_version", legacy.get("championVersionId")))),
        feedback_watermark=source.get("feedback_watermark", source.get("feedbackWatermark", legacy.get("feedback_watermark"))),
        secondary_actions=list(legacy.get("secondary_actions") or source.get("secondary_actions") or []),
        blockers=list(legacy.get("blockers") or []),
        evidence_ids=evidence_ids,
        rationale=str(legacy.get("rationale") or f"Deterministic {stage} decision."),
        stakeholder_questions=list(legacy.get("stakeholder_questions") or source.get("stakeholder_questions") or []),
    ).to_dict()
    return {**legacy, **packet, "coverage": coverage}


def frozen_utc_window(now: datetime | None = None, complete_days: int | None = None) -> dict[str, Any]:
    """Return the preceding complete UTC days; the current partial day is excluded."""
    if complete_days is None:
        complete_days = int(POLICY_PROFILE_V1["complete_days"])
    if complete_days <= 0:
        raise ValueError("complete_days must be positive")
    current = _utc(now or datetime.now(timezone.utc))
    end = current.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=complete_days)
    return {"start": _iso_z(start), "end": _iso_z(end), "timezone": "UTC", "complete_days": complete_days}


def normalize_rank_scope(request: Mapping[str, Any] | None) -> dict[str, list[str]]:
    """Validate and normalize optional scorecard selectors for portfolio ranking.

    Omitted selectors mean account-wide ranking. Explicit selector arrays must
    each contain at least one non-blank string so a malformed scoped request can
    never widen silently to the whole account. Values are deduplicated without
    changing opaque IDs. Prefixes are case-folded because their matching
    semantics are case-insensitive and equivalent scopes need one fingerprint.
    """
    source = dict(request or {})
    nested = source.get("scope")
    selector_source: Mapping[str, Any] = source
    if not any(field in source for field in _RANK_SELECTOR_FIELDS) and isinstance(nested, Mapping):
        selector_source = nested

    present = [field for field in _RANK_SELECTOR_FIELDS if field in selector_source]
    if not present:
        return {}

    normalized: dict[str, list[str]] = {}
    for field in _RANK_SELECTOR_FIELDS:
        if field not in selector_source:
            normalized[field] = []
            continue
        raw = selector_source[field]
        if not isinstance(raw, (list, tuple)):
            raise ValueError(f"{field} selector must be an array of strings")
        if not raw:
            raise ValueError(f"explicitly supplied empty selector: {field}")
        values: list[str] = []
        for value in raw:
            if not isinstance(value, str):
                raise ValueError(f"{field} selector entries must be strings")
            if not value.strip():
                raise ValueError(f"{field} selector entries must not be blank")
            normalized_value = (
                value.casefold() if field == "scorecard_name_prefixes" else value
            )
            if normalized_value not in values:
                values.append(normalized_value)
        normalized[field] = values
    return normalized


def rank_scope_matches(
    scorecard_id: Any,
    scorecard_name: Any,
    scope: Mapping[str, Sequence[str]] | None,
) -> bool:
    """Return whether one scorecard belongs to a normalized rank scope."""
    if not scope:
        return True
    card_id = scorecard_id if isinstance(scorecard_id, str) else ""
    card_name = scorecard_name if isinstance(scorecard_name, str) else ""
    if card_id in scope.get("scorecard_ids", ()):
        return True
    folded_name = card_name.casefold()
    return any(
        folded_name.startswith(prefix.casefold())
        for prefix in scope.get("scorecard_name_prefixes", ())
    )


def wilson_interval(successes: int | float, total: int | float, confidence: float = 0.95) -> tuple[float, float]:
    """Two-sided Wilson score interval, including exact zero and one endpoints."""
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("successes must be between zero and total")
    if total == 0:
        return (0.0, 1.0)
    if confidence != 0.95:
        raise ValueError("only the policy's 95% Wilson interval is supported")
    n = float(total)
    p = float(successes) / n
    z2 = _WILSON_Z_95 * _WILSON_Z_95
    center = (p + z2 / (2 * n)) / (1 + z2 / n)
    margin = _WILSON_Z_95 * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / (1 + z2 / n)
    return (max(0.0, center - margin), min(1.0, center + margin))


def weekly_buckets(
    timestamps: Iterable[str | datetime], *, window_end: str | datetime, weeks: int | None = None
) -> list[dict[str, Any]]:
    """Bucket timestamps into complete Monday-based UTC weeks ending at window_end."""
    if weeks is None:
        weeks = int(POLICY_PROFILE_V1["complete_weeks"])
    if weeks <= 0:
        raise ValueError("weeks must be positive")
    end = _parse_utc(window_end).replace(hour=0, minute=0, second=0, microsecond=0)
    # A frozen window normally ends on a Monday.  If it does not, exclude its
    # partial week by moving back to the most recent Monday.
    end -= timedelta(days=end.weekday())
    starts = [end - timedelta(days=7 * offset) for offset in range(weeks, 0, -1)]
    parsed = [_parse_utc(value) for value in timestamps]
    buckets: list[dict[str, Any]] = []
    for start in starts:
        bucket_end = start + timedelta(days=7)
        count = sum(start <= timestamp < bucket_end for timestamp in parsed)
        buckets.append(
            {
                "start": _iso_z(start),
                "end": _iso_z(bucket_end),
                "count": count,
                # This is informational only. It deliberately is not a policy
                # gate; the meaningful per-class minimum is assessed separately.
                "low_volume_warning": count < int(POLICY_PROFILE_V1["minimum_final_labels_per_reachable_class"]),
            }
        )
    return buckets


def _disagreement(score: Mapping[str, Any]) -> tuple[int, float, float]:
    if score.get("valid_feedback_count") is not None:
        valid_count = int(score.get("valid_feedback_count") or 0)
    else:
        total = int(score.get("total_items", score.get("totalItems", 0)) or 0)
        excluded = sum(
            int(score.get(key) or 0)
            for key in (
                "invalid_feedback_count", "invalid_count", "invalid_feedback_items", "invalid_items",
                "incomplete_label_pair_count", "incomplete_label_pairs", "incomplete_initial_final_pairs", "incomplete_pairs",
            )
        )
        valid_count = max(0, total - excluded)
    disagreement_count = score.get("reviewed_disagreements", score.get("disagreement_count", score.get("disagreements")))
    rate = score.get("disagreement_rate")
    if disagreement_count is None and rate is not None:
        disagreement_count = valid_count * float(rate)
    disagreement_count = float(disagreement_count or 0)
    if valid_count and rate is None:
        rate = disagreement_count / valid_count
    rate = float(rate or 0)
    return valid_count, disagreement_count, rate


def rank_portfolio(scores: Sequence[Mapping[str, Any]], *, coverage: Mapping[str, Any] | None = None, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Rank fully analyzed scores without silently treating partial enumeration as exact."""
    context = dict(context or {})
    scope = normalize_rank_scope(context)
    if scope:
        scores = [
            score
            for score in scores
            if rank_scope_matches(
                score.get("scorecard_id", score.get("scorecardId")),
                score.get("scorecard_name", score.get("scorecardName")),
                scope,
            )
        ]
        context["scope"] = scope
    coverage = dict(coverage or {})
    if scope:
        required_scope_evidence = {
            "requested_scorecard_ids",
            "requested_scorecard_name_prefixes",
            "matched_scorecard_ids",
            "matched_scorecard_count",
            "unmatched_scorecard_ids",
            "unmatched_scorecard_name_prefixes",
            "total_scorecards_inspected",
        }
        scope_evidence = coverage.get("scope")
        if not isinstance(scope_evidence, Mapping) or not required_scope_evidence.issubset(
            scope_evidence
        ):
            failures = list(coverage.get("failures") or [])
            failures.append("complete scope coverage evidence is required")
            coverage.update({"complete": False, "failures": failures})
    activity_coverage = coverage.get("activity")
    activity_coverage_complete = (
        isinstance(activity_coverage, Mapping)
        and activity_coverage.get("complete") is True
        and activity_coverage.get("policy_version")
        == SCORE_ACTIVITY_COOLDOWN_V1["version"]
        and bool(activity_coverage.get("as_of"))
    )
    if bool(coverage.get("complete", coverage.get("coverage_complete", False))) and not activity_coverage_complete:
        failures = list(coverage.get("failures") or [])
        failures.append("complete inventory activity coverage evidence is required")
        coverage.update({"complete": False, "failures": failures})
    activity_as_of = (
        activity_coverage.get("as_of")
        if isinstance(activity_coverage, Mapping)
        else context.get("as_of")
    )
    try:
        frozen_activity_as_of = (
            _parse_utc(activity_as_of)
            if activity_as_of
            else datetime.now(timezone.utc).replace(microsecond=0)
        )
    except (TypeError, ValueError) as exc:
        frozen_activity_as_of = datetime.now(timezone.utc).replace(microsecond=0)
        failures = list(coverage.get("failures") or [])
        failures.append({"stage": "score_activity", "error": f"invalid frozen as_of: {exc}"})
        coverage.update({"complete": False, "failures": failures})
    activity_cutoff = frozen_activity_as_of - timedelta(
        hours=int(SCORE_ACTIVITY_COOLDOWN_V1["duration_hours"])
    )
    # Absence of coverage evidence is not evidence of exhaustive enumeration.
    complete = bool(coverage.get("complete", coverage.get("coverage_complete", False)))
    ranked: list[dict[str, Any]] = []
    unranked: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    activity_failures: list[dict[str, Any]] = []
    recent_activity_excluded_count = 0
    for source in scores:
        score = dict(source)
        enabled = score.get("enabled", True) is not False and score.get("isDisabled") is not True
        champion = score.get("champion_version") or score.get("champion_id") or score.get("championVersionId")
        valid_count, disagreements, rate = _disagreement(score)
        row = {
            **score,
            "scorecard_id": score.get("scorecard_id", score.get("scorecardId")),
            "score_id": score.get("score_id", score.get("scoreId", score.get("id"))),
            "scorecard_name": score.get("scorecard_name", score.get("scorecardName")),
            "score_name": score.get("score_name", score.get("scoreName")),
            "champion_version": champion,
            "valid_feedback_count": valid_count,
            "reviewed_disagreements": disagreements,
            "disagreement_rate": rate,
            "reviewed_error_opportunity": valid_count * rate,
        }
        if not enabled:
            row["unranked_reason"] = "disabled"
            row["policy_disposition"] = "blocked"
            row["policy_reason"] = "disabled"
            row["eligible_for_optimization"] = False
            unranked.append(row)
        elif not champion:
            row["unranked_reason"] = "missing_champion"
            row["policy_disposition"] = "blocked"
            row["policy_reason"] = "missing_champion"
            row["eligible_for_optimization"] = False
            unranked.append(row)
        elif score.get("champion_relationship_valid") is False:
            row["unranked_reason"] = "unresolved_champion_reference"
            row["policy_disposition"] = "blocked"
            row["policy_reason"] = "unresolved_champion_reference"
            row["eligible_for_optimization"] = False
            unranked.append(row)
        else:
            supplied_activity = score.get("score_activity")
            if isinstance(supplied_activity, Mapping):
                supplied_as_of = supplied_activity.get("as_of")
                try:
                    supplied_as_of_matches = bool(supplied_as_of) and (
                        _iso_z(_parse_utc(supplied_as_of))
                        == _iso_z(frozen_activity_as_of)
                    )
                except (TypeError, ValueError):
                    supplied_as_of_matches = False
                if (
                    supplied_activity.get("policy_version")
                    != SCORE_ACTIVITY_COOLDOWN_V1["version"]
                    or not supplied_as_of_matches
                ):
                    activity = {
                        **dict(supplied_activity),
                        "complete": False,
                        "recent": True,
                        "failure": "inventory activity policy metadata is incomplete",
                    }
                else:
                    activity = evaluate_score_activity(
                        {
                            "updatedAt": supplied_activity.get("score_updated_at"),
                            "versions": [{
                                "id": supplied_activity.get("newest_version_id"),
                                "createdAt": supplied_activity.get(
                                    "newest_version_created_at"
                                ),
                            }],
                        },
                        as_of=supplied_as_of,
                    )
            else:
                activity = evaluate_score_activity(score, as_of=frozen_activity_as_of)
            row["score_activity"] = activity
            if activity.get("complete") is not True:
                row["unranked_reason"] = "incomplete_score_activity"
                row["policy_disposition"] = "incomplete"
                row["policy_reason"] = "incomplete_score_activity"
                row["eligible_for_optimization"] = False
                unranked.append(row)
                activity_failures.append(
                    {
                        "stage": "score_activity",
                        "scorecard_id": row.get("scorecard_id"),
                        "score_id": row.get("score_id"),
                        "error": activity.get("failure")
                        or "inventory activity evidence is incomplete",
                    }
                )
            elif activity.get("recent") is True:
                row["unranked_reason"] = "recent_score_activity"
                row["policy_disposition"] = "cooldown"
                row["policy_reason"] = "recent_score_activity"
                row["eligible_for_optimization"] = False
                unranked.append(row)
                recent_activity_excluded_count += 1
            else:
                row["policy_disposition"] = "eligible"
                row["policy_reason"] = "meets_rank_policy"
                row["eligible_for_optimization"] = True
                ranked.append(row)
        evidence_rows.append(row)

    def evidence_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
        return (
            -float(row["reviewed_error_opportunity"]),
            -int(row["valid_feedback_count"]),
            str(row.get("scorecard_name") or ""),
            str(row.get("score_name") or ""),
            str(row.get("score_id") or ""),
        )

    evidence_rows.sort(key=evidence_sort_key)
    for evidence_rank, row in enumerate(evidence_rows, start=1):
        row["evidence_rank"] = evidence_rank

    ranked.sort(key=evidence_sort_key)
    for candidate_rank, row in enumerate(ranked, start=1):
        row["candidate_rank"] = candidate_rank
    unranked.sort(key=lambda row: (str(row["unranked_reason"]), str(row.get("score_id") or "")))
    coverage_failures = list(
        coverage.get("failures") or coverage.get("coverage_failures") or []
    ) + activity_failures
    complete = complete and not activity_failures
    coverage["complete"] = complete
    coverage["failures"] = coverage_failures
    coverage["activity"] = {
        "policy_version": SCORE_ACTIVITY_COOLDOWN_V1["version"],
        "duration_hours": SCORE_ACTIVITY_COOLDOWN_V1["duration_hours"],
        "cutoff_inclusive": SCORE_ACTIVITY_COOLDOWN_V1["cutoff_inclusive"],
        "as_of": _iso_z(frozen_activity_as_of),
        "cutoff": _iso_z(activity_cutoff),
        "complete": not activity_failures,
        "incomplete_score_count": len(activity_failures),
        "recent_activity_excluded_count": recent_activity_excluded_count,
    }
    result = {
        "coverage_complete": complete,
        "coverage_failures": coverage_failures,
        "exact": complete,
        "total_population": len(scores),
        "total_evidence_ranked": len(evidence_rows),
        "total_ranked": len(ranked),
        "recent_activity_excluded_count": recent_activity_excluded_count,
        "activity_policy": dict(coverage["activity"]),
        "ranked": ranked,
        "unranked": unranked,
        "primary_next_action": (
            "rank_complete" if complete else "repair_ranking_coverage"
        ),
        "blockers": ([] if complete else [
            "Portfolio ranking coverage is incomplete."
        ]),
    }
    return _packet_result("rank", result, {**context, "coverage": coverage})


rank_opportunities = rank_portfolio


def normalize_guideline_state(raw: Any) -> str:
    """Normalize mechanical/semantic adapter results into the public state set."""
    if raw is None or raw is False or raw == "":
        return "missing"
    if isinstance(raw, Mapping):
        if raw.get("missing") or raw.get("present") is False:
            return "missing"
        if raw.get("valid") is False or raw.get("syntax_valid") is False:
            return "invalid"
        if raw.get("code_conflict") or raw.get("potential_code_conflict"):
            return "potential_code_conflict"
        if raw.get("complete") is False or raw.get("inconclusive"):
            return "inconclusive"
        return "consistent"
    value = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if value in {"missing", "none", "absent"}:
        return "missing"
    if value in {"invalid", "syntax_error", "unreadable"}:
        return "invalid"
    if value in {"code_conflict", "potential_code_conflict", "conflict"}:
        return "potential_code_conflict"
    if value in {"inconclusive", "unknown", "pending"}:
        return "inconclusive"
    return "consistent"


def normalize_structural_state(raw: Any) -> str:
    """Normalize champion/configuration/terminal-class checks into one state."""
    if raw is None:
        return "consistent"
    if isinstance(raw, Mapping):
        if raw.get("champion_present") is False or raw.get("missing_champion"):
            return "missing_champion"
        if raw.get("configuration_readable") is False or raw.get("config_readable") is False:
            return "unreadable_configuration"
        if raw.get("terminal_classes_resolved") is False or raw.get("unresolved_terminal_classes"):
            return "unresolved_terminal_classes"
        if raw.get("complete") is False or raw.get("inconclusive"):
            return "inconclusive"
        return "consistent"
    value = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "missing_champion": "missing_champion",
        "unreadable": "unreadable_configuration",
        "unreadable_configuration": "unreadable_configuration",
        "unresolved_terminal_classes": "unresolved_terminal_classes",
        "invalid": "invalid",
        "inconclusive": "inconclusive",
        "unknown": "inconclusive",
    }
    return aliases.get(value, "consistent")


def normalize_diagnosis(diagnosis: Mapping[str, Any] | None, *, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Normalize asynchronous semantic diagnosis without inventing a model decision."""
    diagnosis = {**dict(context or {}), **dict(diagnosis or {})}
    guideline_state = normalize_guideline_state(diagnosis.get("guideline_state", diagnosis.get("guidelines")))
    feedback_rubric_state = str(diagnosis.get("feedback_rubric_state") or "inconclusive")
    if diagnosis.get("feedback_contradiction") or diagnosis.get("feedback_inconsistent"):
        feedback_rubric_state = "inconsistent"
    elif diagnosis.get("feedback_rubric_consistent") is True:
        feedback_rubric_state = "consistent"
    elif feedback_rubric_state not in {"consistent", "inconsistent", "inconclusive"}:
        feedback_rubric_state = "inconclusive"
    questions = list(diagnosis.get("stakeholder_questions") or [])
    blockers = list(diagnosis.get("blockers") or [])
    assessment = (
        diagnosis.get("assessment")
        if isinstance(diagnosis.get("assessment"), Mapping)
        else diagnosis.get("assessment_packet")
        if isinstance(diagnosis.get("assessment_packet"), Mapping)
        else {}
    )
    assessment_states = (
        assessment.get("states")
        if isinstance(assessment.get("states"), Mapping)
        else {}
    )
    assessment_readiness = (
        assessment.get("readiness_state")
        or assessment_states.get("readiness")
        or assessment_states.get("optimization")
    )
    complete = bool(diagnosis.get("complete", True))
    if not complete:
        readiness_state = "incomplete"
        primary_next_action = "complete_diagnosis"
    elif guideline_state in {"missing", "invalid", "potential_code_conflict"}:
        readiness_state = "repair_required"
        primary_next_action = "repair_guidelines"
    elif questions:
        readiness_state = "stakeholder_clarification_required"
        primary_next_action = "resolve_stakeholder_questions"
    elif feedback_rubric_state == "inconsistent":
        readiness_state = "feedback_curation_review"
        primary_next_action = "review_feedback_curation"
    elif blockers:
        readiness_state = "incomplete"
        primary_next_action = "resolve_diagnosis_blockers"
    elif assessment_readiness == "ready_to_optimize":
        readiness_state = "ready_to_optimize"
        primary_next_action = "request_optimization_approval"
    else:
        readiness_state = str(assessment_readiness or "inconclusive")
        primary_next_action = str(
            assessment.get("primary_next_action") or "review_diagnosis"
        )
    result = {
        "guideline_state": guideline_state,
        "feedback_rubric_state": feedback_rubric_state,
        "readiness_state": readiness_state,
        "primary_next_action": primary_next_action,
        "stakeholder_questions": questions,
        "blockers": blockers,
        "complete": complete,
        "evidence_ids": list(diagnosis.get("evidence_ids") or []),
    }
    return _packet_result("diagnose", result, diagnosis)


def _range(values: Sequence[float]) -> float | None:
    return max(values) - min(values) if values else None


def assess_investment(evidence: Mapping[str, Any], *, policy: Mapping[str, Any] | None = None, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Apply feedback-investment-v1 gates in documented safety-first order.

    Ordering is: coverage, mechanical structure, guideline/semantic defects,
    stakeholder questions, feedback curation, count, class reachability,
    stability, then Wilson-backed disagreement outcome.
    """
    policy = {**POLICY_PROFILE_V1, **dict(policy or {})}
    data = {**dict(context or {}), **dict(evidence)}
    blockers: list[str] = []
    coverage_complete = bool(data.get("coverage_complete", data.get("complete", False)))
    if not coverage_complete:
        blockers.extend(list(data.get("coverage_failures") or data.get("failures") or ["coverage is incomplete"]))
        return _assessment("incomplete", "inconclusive", blockers, "repair_coverage", data, policy)

    score_activity = _validated_score_activity_evidence(data.get("score_activity"))
    if score_activity is None:
        return _assessment(
            "incomplete",
            "inconclusive",
            ["complete fixed-policy score activity evidence is required"],
            "repair_activity_evidence",
            data,
            policy,
        )
    data["score_activity"] = score_activity
    cooldown_active = bool(data.get("cooldown_active")) or (
        score_activity.get("recent") is True
    )
    if cooldown_active:
        return _assessment(
            "cooldown_active",
            "inconclusive",
            [],
            "wait_for_cooldown",
            data,
            policy,
        )

    structural = normalize_structural_state(data.get("structural_state"))
    if data.get("configuration_readable", data.get("config_readable", True)) is False:
        structural = "unreadable_configuration"
    if data.get("terminal_classes_resolved", True) is False:
        structural = "unresolved_terminal_classes"
    if not data.get("champion_version") or structural in {"missing_champion", "unreadable_configuration", "unresolved_terminal_classes", "invalid"}:
        if not data.get("champion_version"):
            blockers.append("missing champion")
        if structural:
            blockers.append(str(structural).replace("_", " "))
        blockers.extend(data.get("structural_blockers") or [])
        return _assessment("repair_required", "pause_pending_repair_or_clarification", blockers, "repair_structure", data, policy)

    guideline_state = normalize_guideline_state(data.get("guideline_state"))
    if guideline_state in {"missing", "invalid", "potential_code_conflict"}:
        blockers.append(f"guideline state: {guideline_state}")
        return _assessment("repair_required", "pause_pending_repair_or_clarification", blockers, "repair_guidelines", data, policy, guideline_state)

    diagnosis = normalize_diagnosis(data.get("diagnosis")) if data.get("diagnosis") is not None else None
    questions = list(data.get("stakeholder_questions") or (diagnosis or {}).get("stakeholder_questions") or [])
    if questions:
        return _assessment("stakeholder_clarification_required", "pause_pending_repair_or_clarification", questions, "resolve_stakeholder_questions", data, policy, guideline_state)
    if (diagnosis or {}).get("feedback_rubric_state") == "inconsistent" or data.get("feedback_inconsistent"):
        return _assessment("feedback_curation_review", "pause_pending_repair_or_clarification", ["feedback and rubric evidence conflict"], "review_feedback_curation", data, policy, guideline_state)

    valid_count, disagreement_count, _ = _disagreement(data)
    if valid_count < int(policy["minimum_valid_feedback"]):
        return _assessment("insufficient_evidence", "continue_broad_collection", [f"valid feedback count {valid_count} is below {policy['minimum_valid_feedback']}"], "collect_broad_feedback", data, policy, guideline_state)

    classes = list(data.get("reachable_classes") or [])
    class_counts = dict(data.get("final_label_counts") or data.get("reachable_class_counts") or {})
    deficient = [str(label) for label in classes if int(class_counts.get(label, 0) or 0) < int(policy["minimum_final_labels_per_reachable_class"])]
    if deficient:
        return _assessment("insufficient_evidence", "collect_targeted_classes", [f"reachable class below minimum: {label}" for label in deficient], "collect_targeted_classes", data, policy, guideline_state)

    lower, upper = wilson_interval(disagreement_count, valid_count)
    threshold = float(policy["maximum_acceptable_disagreement"])
    # Once the lower confidence bound is above the acceptable rate, more broad
    # collection only reconfirms an established problem. Weekly stability is a
    # gate for reducing collection, not for deciding that repair/optimization
    # is already warranted.
    if lower > threshold:
        return _assessment(
            "ready_to_optimize",
            "pause_pending_repair_or_clarification",
            [],
            "run_approved_optimization",
            data,
            policy,
            guideline_state,
            wilson=(lower, upper),
        )

    latest = int(policy["latest_weeks_for_stability"])
    raw_weekly_buckets = [
        dict(bucket)
        for bucket in (data.get("weekly_buckets") or [])[-latest:]
        if isinstance(bucket, Mapping)
    ]
    if raw_weekly_buckets:
        weekly_disagreement = [
            float(bucket["disagreement_rate"])
            for bucket in raw_weekly_buckets
            if bucket.get("disagreement_rate") is not None
        ]
        weekly_ac1 = [
            float(bucket["ac1"])
            for bucket in raw_weekly_buckets
            if bucket.get("ac1") is not None
        ]
        weekly_counts = [
            int(bucket.get("valid_feedback_count", bucket.get("count", 0)) or 0)
            for bucket in raw_weekly_buckets
        ]
    else:
        weekly_disagreement = [float(value) for value in (data.get("weekly_disagreement_rates") or [])[-latest:]]
        weekly_ac1 = [float(value) for value in (data.get("weekly_ac1_values") or [])[-latest:]]
        weekly_counts = list(data.get("weekly_bucket_counts") or [])[-latest:]
    stability = {
        "weekly_disagreement_range": _range(weekly_disagreement),
        "weekly_ac1_range": _range(weekly_ac1),
        "weekly_bucket_counts": weekly_counts,
        "weekly_low_volume_warning": any(
            int(value or 0) < int(policy["minimum_final_labels_per_reachable_class"])
            for value in weekly_counts
        ),
    }
    unstable = (
        (bool(raw_weekly_buckets) and len(raw_weekly_buckets) < latest)
        or len(weekly_disagreement) < latest
        or len(weekly_ac1) < latest
        or (stability["weekly_disagreement_range"] or 0) > float(policy["maximum_disagreement_range"])
        or (stability["weekly_ac1_range"] or 0) > float(policy["maximum_ac1_range"])
    )
    if unstable:
        return _assessment("insufficient_evidence", "continue_broad_collection", ["recent weekly metrics are insufficient or unstable"], "collect_stable_feedback", data, policy, guideline_state, stability)

    # Equality is safe: <= threshold means the acceptable side of a boundary.
    if upper <= threshold:
        return _assessment("monitoring_candidate", "reduce_to_periodic_monitoring", [], "monitor_periodically", data, policy, guideline_state, stability, (lower, upper))
    return _assessment("insufficient_evidence", "continue_broad_collection", ["Wilson interval crosses acceptable disagreement threshold"], "collect_more_feedback", data, policy, guideline_state, stability, (lower, upper))


def _assessment(readiness: str, collection: str, blockers: Sequence[str], action: str, data: Mapping[str, Any], policy: Mapping[str, Any], guideline_state: str = "inconclusive", stability: Mapping[str, Any] | None = None, wilson: tuple[float, float] | None = None) -> dict[str, Any]:
    result = {
        "policy_version": policy["version"],
        "readiness_state": readiness,
        "feedback_collection_state": collection,
        "guideline_state": guideline_state,
        "feedback_rubric_state": normalize_diagnosis(data.get("diagnosis")).get("feedback_rubric_state") if data.get("diagnosis") else "inconclusive",
        "primary_next_action": action,
        "blockers": list(blockers),
        "coverage_complete": bool(data.get("coverage_complete", data.get("complete", False))),
        "class_counts": dict(data.get("final_label_counts") or data.get("reachable_class_counts") or {}),
        "weekly_stability": dict(stability or {}),
        "cooldown_active": bool(data.get("cooldown_active")) or (
            isinstance(data.get("score_activity"), Mapping)
            and data["score_activity"].get("recent") is True
        ),
    }
    if isinstance(data.get("score_activity"), Mapping):
        result["score_activity"] = dict(data["score_activity"])
    if wilson is not None:
        result["wilson_95"] = {"lower": wilson[0], "upper": wilson[1]}
    return _packet_result("assess", result, data)


def evidence_fingerprint(evidence: Mapping[str, Any]) -> str:
    """Hash canonical evidence so a caller can reject stale assessments."""
    return hashlib.sha256(_canonical(evidence).encode("utf-8")).hexdigest()


def validate_run_limits(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate public optimizer-dispatch limits once for every transport.

    Cost may be a positive real number. Sample and iteration caps are positive
    integers, and concurrency is an explicitly bounded integer from one to
    five. Missing values are never defaulted.
    """
    data = dict(payload)
    invalid: list[str] = []
    cost = data.get("max_cost_usd")
    if isinstance(cost, bool) or not isinstance(cost, Real) or not math.isfinite(float(cost)) or float(cost) <= 0:
        invalid.append("max_cost_usd")
    for field in ("max_samples", "max_iterations"):
        value = data.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            invalid.append(field)
    concurrency = data.get("max_concurrency")
    if isinstance(concurrency, bool) or not isinstance(concurrency, int) or not 1 <= concurrency <= 5:
        invalid.append("max_concurrency")
    return {
        "valid": not invalid,
        "invalid_fields": invalid,
        "limits": {
            "max_cost_usd": cost,
            "max_samples": data.get("max_samples"),
            "max_iterations": data.get("max_iterations"),
            "max_concurrency": concurrency,
        },
    }


def _assessment_packet_fingerprint(packet: Mapping[str, Any]) -> str | None:
    """Recompute the canonical fingerprint of a returned assessment packet.

    A target must carry the actual assessment packet, not an unverified string
    that merely looks like a fingerprint.  This is deliberately the same
    envelope that :meth:`OptimizationDecisionPacket.to_dict` fingerprints.
    """
    evidence = packet.get("evidence")
    if not isinstance(evidence, Mapping):
        return None
    return evidence_fingerprint(
        {
            "account_id": packet.get("account_id"),
            "scope": packet.get("scope") or {},
            "window": packet.get("window") or {},
            "policy_version": packet.get("policy_version"),
            "champion_version": packet.get("champion_version"),
            "feedback_watermark": packet.get("feedback_watermark"),
            "evidence": dict(evidence),
        }
    )


def _ready_target_provenance_failure(target: Mapping[str, Any]) -> str | None:
    """Return one fail-closed reason when a launch target lacks provenance."""
    scorecard_id = str(target.get("scorecard_id") or "")
    score_id = str(target.get("score_id") or "")
    if not scorecard_id or not score_id:
        return "exact_target_identifiers_required"

    assessment_value = target.get("assessment")
    if not isinstance(assessment_value, Mapping):
        return "assessment_packet_required"
    assessment = dict(assessment_value)
    scope = assessment.get("scope")
    if not isinstance(scope, Mapping) or (
        str(scope.get("scorecard_id") or "") != scorecard_id
        or str(scope.get("score_id") or "") != score_id
    ):
        return "assessment_scope_mismatch"

    claimed_fingerprint = target.get("assessment_fingerprint")
    packet_fingerprint = assessment.get("evidence_fingerprint") or assessment.get("fingerprint")
    recomputed_fingerprint = _assessment_packet_fingerprint(assessment)
    if not isinstance(claimed_fingerprint, str) or not claimed_fingerprint:
        return "assessment_fingerprint_required"
    if (
        not isinstance(packet_fingerprint, str)
        or packet_fingerprint != recomputed_fingerprint
        or claimed_fingerprint != packet_fingerprint
    ):
        return "assessment_fingerprint_mismatch"

    coverage = assessment.get("coverage")
    states = assessment.get("states")
    readiness = (
        states.get("optimization", states.get("readiness"))
        if isinstance(states, Mapping)
        else assessment.get("readiness_state")
    )
    if not isinstance(coverage, Mapping) or coverage.get("complete") is not True or readiness != "ready_to_optimize":
        return "assessment_not_ready"

    champion_version = assessment.get("champion_version")
    feedback_watermark = assessment.get("feedback_watermark")
    if not champion_version:
        return "champion_version_required"
    if not feedback_watermark:
        return "feedback_watermark_required"
    evidence = assessment.get("evidence")
    activity = _validated_score_activity_evidence(
        evidence.get("score_activity") if isinstance(evidence, Mapping) else None
    )
    if activity is None or activity.get("recent") is not False:
        return "score_activity_evidence_required"
    if (
        target.get("champion_version") != champion_version
        or target.get("feedback_watermark") != feedback_watermark
    ):
        return "assessment_freshness_mismatch"
    return None


def _validate_ready_targets(targets: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return explicit provenance failures for public optimizer dispatch."""
    rejected: list[dict[str, Any]] = []
    for target_source in targets:
        target = dict(target_source)
        reason = _ready_target_provenance_failure(target)
        if reason:
            rejected.append({"target": target, "reason": reason})
    return rejected


def validate_public_run_dispatch(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Apply limits and assessment provenance before lower-level batch checks."""
    data = dict(payload)
    targets = list(data.get("targets") or [])
    limits = validate_run_limits(data)
    if not limits["valid"]:
        result = {
            "accepted": False,
            "accepted_targets": [],
            "rejected": [{"reason": "invalid_run_limits", "invalid_fields": limits["invalid_fields"]}],
            "run_limits": limits,
            "primary_next_action": "provide_valid_run_limits",
            "blockers": ["invalid_run_limits"],
        }
        return _packet_result("run", result, data)
    provenance_rejections = _validate_ready_targets(targets)
    if provenance_rejections:
        result = {
            "accepted": False,
            "accepted_targets": [],
            "rejected": provenance_rejections,
            "run_limits": limits,
            "primary_next_action": "repair_target_assessment_provenance",
            "blockers": [str(item["reason"]) for item in provenance_rejections],
        }
        return _packet_result("run", result, data)
    result = validate_approved_batch(
        targets,
        approved=bool(data.get("approved")),
        current_fingerprints=data.get("current_fingerprints"),
        context=data,
    )
    result["run_limits"] = limits
    return result


def validate_approved_batch(targets: Sequence[Mapping[str, Any]], *, approved: bool, current_fingerprints: Mapping[str, str] | None = None, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Validate an explicit <=5 target approval and reject stale targets individually."""
    targets = list(targets)
    rejected: list[dict[str, Any]] = []
    source = {**dict(context or {}), "targets": targets, "approved": approved}
    if not approved:
        return _packet_result("run", {"accepted": False, "accepted_targets": [], "rejected": [{"reason": "approval_required"}], "primary_next_action": "obtain_batch_approval", "blockers": ["approval_required"]}, source)
    if not targets:
        return _packet_result("run", {"accepted": False, "accepted_targets": [], "rejected": [{"reason": "targets_required"}], "primary_next_action": "select_exact_targets", "blockers": ["targets_required"]}, source)
    if len(targets) > 5:
        return _packet_result("run", {"accepted": False, "accepted_targets": [], "rejected": [{"reason": "maximum_five_targets"}], "primary_next_action": "reduce_approved_batch", "blockers": ["maximum_five_targets"]}, source)
    current_fingerprints = dict(current_fingerprints or {})
    accepted: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for target_source in targets:
        target = dict(target_source)
        scorecard_id, score_id = str(target.get("scorecard_id") or ""), str(target.get("score_id") or "")
        key = (scorecard_id, score_id)
        printable = f"{scorecard_id}:{score_id}"
        provenance_failure = _ready_target_provenance_failure(target)
        current_fingerprint = current_fingerprints.get(printable)
        if provenance_failure:
            rejected.append({"target": target, "reason": provenance_failure})
        elif key in seen:
            rejected.append({"target": target, "reason": "duplicate_target"})
        elif not isinstance(current_fingerprint, str) or not current_fingerprint:
            rejected.append({"target": target, "reason": "current_assessment_fingerprint_required"})
        elif target.get("assessment_fingerprint") != current_fingerprint:
            rejected.append({"target": target, "reason": "stale_assessment"})
        else:
            accepted.append(target)
        seen.add(key)
    result = {
        "accepted": not rejected,
        "accepted_targets": accepted,
        "rejected": rejected,
        "primary_next_action": "dispatch_approved_targets" if not rejected else "resolve_batch_rejections",
        "blockers": [str(item["reason"]) for item in rejected],
    }
    return _packet_result("run", result, source)


def classify_post_run_review(evidence: Mapping[str, Any], *, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Classify optimizer evidence; it never promotes anything itself."""
    data = {**dict(context or {}), **dict(evidence)}
    if not data.get("terminal") or data.get("failed") or data.get("incomplete"):
        return _packet_result("review", {"post_run_state": "failed_or_incomplete", "promotion_ready": False, "primary_next_action": "complete_or_repair_evaluation"}, data)
    if data.get("stakeholder_questions") or data.get("stakeholder_decision_required"):
        return _packet_result("review", {"post_run_state": "stakeholder_decision_required", "promotion_ready": False, "primary_next_action": "resolve_stakeholder_questions", "stakeholder_questions": list(data.get("stakeholder_questions") or [])}, data)
    if data.get("prediction_collapse") is True or data.get("measurable_safe_improvement") is False:
        return _packet_result("review", {"post_run_state": "no_safe_improvement", "promotion_ready": False, "primary_next_action": "retain_champion"}, data)
    required = (
        "indexed_optimizer_review",
        "candidate_version_id",
        "matched_recent_evaluation",
        "historical_regression_evidence",
        "class_specific_metrics",
        "prediction_collapse",
        "rca_complete",
        "artifacts_complete",
        "measurable_safe_improvement",
    )
    missing = [
        name
        for name in required
        if (data.get(name) is not False if name == "prediction_collapse" else not data.get(name))
    ]
    if not missing:
        return _packet_result("review", {"post_run_state": "promotion_ready", "promotion_ready": True, "primary_next_action": "request_promotion_approval", "missing_evidence": []}, data)
    return _packet_result("review", {"post_run_state": "continue_optimization", "promotion_ready": False, "primary_next_action": "continue_optimization", "missing_evidence": missing, "blockers": missing}, data)


review_optimizer_result = classify_post_run_review


def summarize_packets(packets: Sequence[Mapping[str, Any]], *, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Produce a compact, deterministic portfolio summary from decision packets."""
    packets = [dict(packet) for packet in packets]
    questions: list[str] = []
    failures: list[str] = []
    actions: list[str] = []
    collection_recommendations: list[str] = []
    per_score_outcomes: list[dict[str, Any]] = []
    approvals = 0
    recently_deferred = 0
    for packet in packets:
        states = dict(packet.get("states") or {})
        action = packet.get("primary_next_action")
        if action:
            actions.append(str(action))
        questions.extend(str(item) for item in packet.get("stakeholder_questions") or [])
        failures.extend(str(item) for item in packet.get("blockers") or [])
        collection = states.get("feedback_collection") or packet.get("feedback_collection_state")
        if collection:
            collection_recommendations.append(str(collection))
        post_run = states.get("post_run") or packet.get("post_run_state")
        readiness = states.get("optimization") or states.get("readiness") or packet.get(
            "readiness_state"
        )
        rank_deferred = int(packet.get("recent_activity_excluded_count") or 0)
        if rank_deferred:
            recently_deferred += rank_deferred
        elif readiness == "cooldown_active" or action == "wait_for_cooldown":
            recently_deferred += 1
        if post_run == "promotion_ready" or action == "request_promotion_approval":
            approvals += 1
        scope = dict(packet.get("scope") or {})
        scorecard_id = scope.get("scorecard_id", packet.get("scorecard_id"))
        score_id = scope.get("score_id", packet.get("score_id"))
        if not scope:
            scope = {key: value for key, value in (("scorecard_id", scorecard_id), ("score_id", score_id)) if value is not None}
        outcome = post_run if post_run and post_run != "inconclusive" else (readiness or "inconclusive")
        packet_failures = _unique(
            [str(item) for item in packet.get("blockers") or []]
            + [str(item) for item in (packet.get("coverage") or {}).get("failures") or []]
            + [str(item) for item in packet.get("coverage_failures") or []]
        )
        per_score_outcomes.append(
            {
                "scope": scope,
                "scorecard_id": scorecard_id,
                "score_id": score_id,
                "states": states,
                "outcome": outcome,
                "blockers": list(packet.get("blockers") or []),
                "collection_recommendation": collection,
                "stakeholder_questions": list(packet.get("stakeholder_questions") or []),
                "approval_request": post_run == "promotion_ready" or action == "request_promotion_approval",
                "failures": packet_failures,
                "next_action": action,
            }
        )
    result = {
        "packet_count": len(packets),
        "executive_update": (
            f"{len(packets)} decision packet(s); {approvals} promotion approval request(s); "
            f"{recently_deferred} recently modified score(s) deferred."
        ),
        "promotion_approval_requests": approvals,
        "recent_activity_deferred_count": recently_deferred,
        "stakeholder_questions": _unique(questions),
        "failures": _unique(failures),
        "next_actions": _unique(actions),
        "collection_policy_recommendations": _unique(collection_recommendations),
        "per_score_outcomes": per_score_outcomes,
    }
    return _packet_result("summary", result, {**dict(context or {}), "packets": packets})


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def dispatch_optimization_operation(operation: str, payload: Mapping[str, Any], **dependencies: Any) -> dict[str, Any]:
    """Route transport payloads to pure operations without accessing services.

    Runtime adapters own pagination, semantic jobs, persistence, and optimizer
    dispatch. This router intentionally handles only deterministic decisions.
    """
    del dependencies  # Reserved for adapters; pure decisions need no services.
    data = dict(payload)
    normalized = operation.removeprefix("optimization.").lower()
    if normalized == "rank":
        return rank_portfolio(data.get("scores") or [], coverage=data.get("coverage"), context=data)
    if normalized == "assess":
        return assess_investment(data.get("evidence") or data, policy=data.get("policy"), context=data)
    if normalized == "diagnose":
        return normalize_diagnosis(data.get("diagnosis") or data, context=data)
    if normalized == "run":
        return validate_public_run_dispatch(data)
    if normalized == "review":
        return classify_post_run_review(data.get("evidence") or data, context=data)
    if normalized == "summary":
        return summarize_packets(data.get("packets") or [], context=data)
    if normalized in {"validate", "validate_batch"}:
        return validate_approved_batch(
            data.get("targets") or [],
            approved=bool(data.get("approved")),
            current_fingerprints=data.get("current_fingerprints"),
            context=data,
        )
    raise ValueError(f"Unsupported optimization operation in pure context: {operation}")


run_operation = dispatch_optimization_operation
