"""Injected live-evidence adapters shared by optimization transports."""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Callable, Mapping, Sequence


_SUCCESS_STATES = {"COMPLETED", "SUCCESS", "SUCCEEDED"}
_FAILURE_STATES = {"FAILED", "CANCELLED", "CANCELED"}


def _alignment_metric_evidence(baseline: Any, candidate: Any) -> dict[str, float | None]:
    """Return comparable finite AC1 values without inventing missing evidence."""
    def finite_number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if isfinite(number) else None

    baseline_value = finite_number(baseline)
    candidate_value = finite_number(candidate)
    delta = (
        round(candidate_value - baseline_value, 12)
        if baseline_value is not None and candidate_value is not None
        else None
    )
    return {
        "baseline": baseline_value,
        "candidate": candidate_value,
        "delta": delta,
    }


def refresh_target_freshness(
    targets: Sequence[Mapping[str, Any]],
    *,
    read_score_info: Callable[[str, str], Mapping[str, Any]],
    read_feedback_latest: Callable[[str, str], Mapping[str, Any]],
    now: datetime | str | None = None,
) -> tuple[dict[str, str], dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """Read current champion/watermark evidence for every exact target.

    Individual read errors are reported as target-scoped failures so callers can
    reject only those targets. The assessment fingerprint is deliberately not
    recomputed here: it covers the complete assessment packet, while this live
    check only refreshes the champion and feedback watermark.
    """
    verified_assessment_fingerprints: dict[str, str] = {}
    evidence_by_target: dict[tuple[str, str], dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    frozen_now = now or datetime.now(timezone.utc).replace(microsecond=0)
    for source in targets:
        target = dict(source)
        scorecard_id = str(target.get("scorecard_id") or "")
        score_id = str(target.get("score_id") or "")
        if not scorecard_id or not score_id:
            failures.append(
                {"target": target, "reason": "exact_target_identifiers_required"}
            )
            continue
        try:
            score = read_score_info(scorecard_id, score_id)
            feedback = read_feedback_latest(scorecard_id, score_id)
            champion_version = score.get("champion_version") or score.get(
                "championVersionId"
            )
            watermark = feedback.get("feedback_watermark") or feedback.get(
                "latest_feedback_updated_at"
            )
            if not champion_version or not watermark:
                raise RuntimeError("live champion version or feedback watermark is missing")
            from plexus.optimization.decision import evaluate_score_activity

            activity = evaluate_score_activity(score, as_of=frozen_now)
            if activity.get("complete") is not True:
                raise RuntimeError(
                    "live score activity evidence is incomplete: "
                    + str(activity.get("failure") or "unknown activity failure")
                )
            if activity.get("recent") is True:
                failures.append(
                    {
                        "target": target,
                        "reason": "recent_score_activity",
                        "score_updated_at": activity.get("score_updated_at"),
                        "newest_version_id": activity.get("newest_version_id"),
                        "newest_version_created_at": activity.get(
                            "newest_version_created_at"
                        ),
                        "activity_timestamp": activity.get("activity_timestamp"),
                        "activity_as_of": activity.get("as_of"),
                    }
                )
                continue
            evidence = {
                "scorecard_id": scorecard_id,
                "score_id": score_id,
                "champion_version": champion_version,
                "feedback_watermark": watermark,
                "score_updated_at": activity.get("score_updated_at"),
                "newest_version_id": activity.get("newest_version_id"),
                "newest_version_created_at": activity.get(
                    "newest_version_created_at"
                ),
                "activity_timestamp": activity.get("activity_timestamp"),
                "activity_as_of": activity.get("as_of"),
            }
            # Preserve the original full-assessment provenance token only when
            # the two live freshness fields still match. Never invent a second
            # shorter fingerprint from this partial evidence.
            if (
                target.get("champion_version") == champion_version
                and target.get("feedback_watermark") == watermark
                and target.get("assessment_fingerprint")
            ):
                verified_assessment_fingerprints[
                    f"{scorecard_id}:{score_id}"
                ] = str(target["assessment_fingerprint"])
            evidence_by_target[(scorecard_id, score_id)] = evidence
        except Exception as exc:  # noqa: BLE001 - evidence failures are observable data
            failures.append(
                {
                    "target": target,
                    "reason": "freshness_check_failed",
                    "error": str(exc),
                }
            )
    return verified_assessment_fingerprints, evidence_by_target, failures


def build_indexed_optimizer_review_evidence(
    indexed: Mapping[str, Any],
    *,
    procedure_id: str,
    read_evaluation: Callable[[str], Mapping[str, Any]],
) -> dict[str, Any]:
    """Build promotion-review evidence from indexed optimizer artifacts.

    This adapter is intentionally conservative. Identifiers prove only that an
    artifact was referenced; terminal state, exact candidate linkage, matched
    baselines, class coverage, RCA, non-collapse, and safe improvement must all
    be established from the indexed manifest and terminal evaluation records.
    """
    summary = _mapping(indexed.get("summary"))
    baseline = _mapping(indexed.get("baseline"))
    best = _mapping(indexed.get("best"))
    review_artifacts = _mapping(indexed.get("review_artifacts"))
    effective_status = str(summary.get("effective_status") or "").upper()
    all_cycles_rejected = _all_cycles_rejected(indexed.get("cycles"))
    candidate_version = best.get("winning_version_id") or best.get(
        "last_accepted_version_id"
    )
    recent_id = best.get("best_feedback_evaluation_id")
    historical_id = best.get("best_accuracy_evaluation_id")
    if (
        historical_id == baseline.get("original_accuracy_evaluation_id")
        and candidate_version != baseline.get("version_id")
    ):
        historical_id = (
            _indexed_winning_candidate_accuracy_evaluation_id(
                indexed,
                candidate_version,
            )
            or historical_id
        )
    terminal_all_candidates_rejected = _terminal_all_candidates_rejected(
        indexed,
        effective_status=effective_status,
        baseline_version=baseline.get("version_id"),
        winning_version=candidate_version,
        artifacts_complete=review_artifacts.get("artifacts_complete") is True,
        rca_complete=review_artifacts.get("rca_complete") is True,
        read_evaluation=read_evaluation,
    )
    terminal_baselines_already_good = _terminal_baselines_already_good(
        indexed,
        effective_status=effective_status,
        baseline_version=baseline.get("version_id"),
        winning_version=candidate_version,
        read_evaluation=read_evaluation,
    )
    evidence_ids = [
        str(value)
        for value in (procedure_id, recent_id, historical_id)
        if value
    ]
    base_result: dict[str, Any] = {
        "procedure_id": procedure_id,
        "indexed_optimizer_review": True,
        "terminal": effective_status in (_SUCCESS_STATES | _FAILURE_STATES),
        "failed": effective_status in _FAILURE_STATES,
        "incomplete": effective_status not in (_SUCCESS_STATES | _FAILURE_STATES),
        "matched_recent_evaluation": False,
        "historical_regression_evidence": False,
        "class_specific_metrics": False,
        "prediction_collapse": None,
        "rca_complete": False,
        "artifacts_complete": review_artifacts.get("artifacts_complete") is True,
        "measurable_safe_improvement": (
            False
            if terminal_all_candidates_rejected or terminal_baselines_already_good
            else None
        ),
        "candidate_version_id": candidate_version,
        "evidence_ids": evidence_ids,
        "alignment_evidence": {
            "recent": _alignment_metric_evidence(
                baseline.get("feedback_alignment"), best.get("feedback_alignment")
            ),
            "regression": _alignment_metric_evidence(
                baseline.get("accuracy_alignment"), best.get("accuracy_alignment")
            ),
        },
    }
    # Some indexed manifests retain the frozen baseline evaluations as the
    # "best" pair when every candidate was rejected. Those IDs are not proof
    # that an interrupted or otherwise incomplete rejection set exhausted the
    # search, so never let that normal winner path classify it as safe.
    if all_cycles_rejected:
        return base_result
    if terminal_baselines_already_good:
        return base_result
    if (
        effective_status not in _SUCCESS_STATES
        or not candidate_version
        or not recent_id
        or not historical_id
        or recent_id == historical_id
    ):
        return base_result

    recent = dict(read_evaluation(str(recent_id)))
    historical = dict(read_evaluation(str(historical_id)))
    recent_complete = _evaluation_complete(recent)
    historical_complete = _evaluation_complete(historical)
    exact_candidate = (
        recent.get("score_version_id") == candidate_version
        and historical.get("score_version_id") == candidate_version
    )
    original_recent_id = baseline.get("original_feedback_evaluation_id")
    original_historical_id = baseline.get("original_accuracy_evaluation_id")
    matched_recent = (
        recent_complete
        and exact_candidate
        and bool(original_recent_id)
        and _evaluation_baseline_id(recent) == original_recent_id
    )
    independent_historical = (
        historical_complete
        and exact_candidate
        and bool(original_historical_id)
        and original_historical_id != original_recent_id
        and _evaluation_baseline_id(historical) == original_historical_id
    )
    class_metrics = all(
        _has_class_metrics(evaluation) for evaluation in (recent, historical)
    )
    collapse_states = [_prediction_collapse(evaluation) for evaluation in (recent, historical)]
    collapse_known = all(state is not None for state in collapse_states)
    collapse_detected = any(state is True for state in collapse_states)
    rca_complete = (
        review_artifacts.get("rca_complete") is True
        and all(isinstance(evaluation.get("root_cause"), Mapping) for evaluation in (recent, historical))
    )
    feedback_improvement = _strict_improvement(
        baseline.get("feedback_alignment"), best.get("feedback_alignment")
    )
    regression_non_regressing = _non_regressing(
        baseline.get("accuracy_alignment"), best.get("accuracy_alignment")
    )
    return {
        **base_result,
        "matched_recent_evaluation": matched_recent,
        "historical_regression_evidence": independent_historical,
        "class_specific_metrics": class_metrics,
        "prediction_collapse": collapse_detected if collapse_known else None,
        "rca_complete": rca_complete,
        "measurable_safe_improvement": (
            matched_recent
            and independent_historical
            and feedback_improvement
            and regression_non_regressing
        ),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _all_cycles_rejected(cycles: Any) -> bool:
    return (
        isinstance(cycles, list)
        and bool(cycles)
        and all(
            isinstance(cycle, Mapping)
            and cycle.get("accepted") is False
            and str(cycle.get("status") or "").lower() == "rejected"
            for cycle in cycles
        )
    )


def _indexed_winning_candidate_accuracy_evaluation_id(
    indexed: Mapping[str, Any],
    winning_version_id: Any,
) -> str | None:
    if not winning_version_id:
        return None
    evaluation_ids = {
        str(candidate["accuracy_evaluation_id"])
        for cycle in indexed.get("cycles") or []
        if isinstance(cycle, Mapping)
        for candidate in cycle.get("candidates") or []
        if isinstance(candidate, Mapping)
        and candidate.get("version_id") == winning_version_id
        and candidate.get("accuracy_evaluation_id")
    }
    return next(iter(evaluation_ids)) if len(evaluation_ids) == 1 else None


def _alignment_at_least(value: Any, minimum: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value >= minimum
    )


def _terminal_baselines_already_good(
    indexed: Mapping[str, Any],
    *,
    effective_status: str,
    baseline_version: Any,
    winning_version: Any,
    read_evaluation: Callable[[str], Mapping[str, Any]],
) -> bool:
    summary = _mapping(indexed.get("summary"))
    procedure = _mapping(indexed.get("procedure"))
    baseline = _mapping(indexed.get("baseline"))
    completion_reason = summary.get("completion_reason")
    if completion_reason == "baselines_already_good":
        if summary.get("stop_reason") != "already_good":
            return False
    elif completion_reason != "legacy_baselines_already_good":
        return False

    feedback_evaluation_id = baseline.get("original_feedback_evaluation_id")
    accuracy_evaluation_id = baseline.get("original_accuracy_evaluation_id")
    completed_cycles = summary.get("completed_cycles")
    if (
        effective_status not in _SUCCESS_STATES
        or str(procedure.get("status") or "").upper() != "COMPLETED"
        or str(procedure.get("task_status") or "").upper() != "COMPLETED"
        or type(completed_cycles) is not int
        or completed_cycles != 0
        or indexed.get("cycles") != []
        or not baseline_version
        or winning_version != baseline_version
        or not feedback_evaluation_id
        or not accuracy_evaluation_id
        or feedback_evaluation_id == accuracy_evaluation_id
        or not _alignment_at_least(baseline.get("feedback_alignment"), 0.99)
        or not _alignment_at_least(baseline.get("accuracy_alignment"), 0.99)
    ):
        return False
    try:
        feedback_evaluation = _mapping(read_evaluation(str(feedback_evaluation_id)))
        accuracy_evaluation = _mapping(read_evaluation(str(accuracy_evaluation_id)))
    except Exception:  # noqa: BLE001 - missing evidence fails closed
        return False
    return (
        feedback_evaluation.get("id") == feedback_evaluation_id
        and accuracy_evaluation.get("id") == accuracy_evaluation_id
        and _evaluation_complete(feedback_evaluation)
        and _evaluation_complete(accuracy_evaluation)
        and feedback_evaluation.get("score_version_id") == baseline_version
        and accuracy_evaluation.get("score_version_id") == baseline_version
    )


def _terminal_all_candidates_rejected(
    indexed: Mapping[str, Any],
    *,
    effective_status: str,
    baseline_version: Any,
    winning_version: Any,
    artifacts_complete: bool,
    rca_complete: bool,
    read_evaluation: Callable[[str], Mapping[str, Any]],
) -> bool:
    summary = _mapping(indexed.get("summary"))
    cycles = indexed.get("cycles")
    baseline = _mapping(indexed.get("baseline"))
    original_recent_id = baseline.get("original_feedback_evaluation_id")
    original_historical_id = baseline.get("original_accuracy_evaluation_id")
    completed_cycles = summary.get("completed_cycles")
    if (
        effective_status not in _SUCCESS_STATES
        or not artifacts_complete
        or not rca_complete
        or not baseline_version
        or winning_version != baseline_version
        or str(summary.get("stop_reason") or "").lower() != "max_iterations"
        or type(completed_cycles) is not int
        or completed_cycles < 1
        or not isinstance(cycles, list)
        or not cycles
        or completed_cycles != len(cycles)
        or not original_recent_id
        or not original_historical_id
        or original_recent_id == original_historical_id
    ):
        return False
    for cycle in cycles:
        if not isinstance(cycle, Mapping):
            return False
        if cycle.get("accepted") is not False:
            return False
        if str(cycle.get("status") or "").lower() != "rejected":
            return False
        candidates = cycle.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return False
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                return False
            candidate_version = candidate.get("version_id")
            feedback_evaluation_id = candidate.get("feedback_evaluation_id")
            accuracy_evaluation_id = candidate.get("accuracy_evaluation_id")
            if (
                not candidate_version
                or not feedback_evaluation_id
                or not accuracy_evaluation_id
                or feedback_evaluation_id == accuracy_evaluation_id
            ):
                return False
            try:
                feedback_evaluation = _mapping(
                    read_evaluation(str(feedback_evaluation_id))
                )
                accuracy_evaluation = _mapping(
                    read_evaluation(str(accuracy_evaluation_id))
                )
            except Exception:  # noqa: BLE001 - missing evidence fails closed
                return False
            if not (
                _evaluation_complete(feedback_evaluation)
                and _evaluation_complete(accuracy_evaluation)
                and feedback_evaluation.get("score_version_id") == candidate_version
                and accuracy_evaluation.get("score_version_id") == candidate_version
                and _evaluation_baseline_id(feedback_evaluation) == original_recent_id
                and _evaluation_baseline_id(accuracy_evaluation)
                == original_historical_id
            ):
                return False
    return True


def _evaluation_complete(evaluation: Mapping[str, Any]) -> bool:
    status = str(evaluation.get("status") or "").upper()
    total = evaluation.get("total_items")
    processed = evaluation.get("processed_items")
    return (
        status in _SUCCESS_STATES
        and isinstance(total, int)
        and total > 0
        and processed == total
    )


def _evaluation_baseline_id(evaluation: Mapping[str, Any]) -> Any:
    return evaluation.get("current_baseline_evaluation_id") or evaluation.get(
        "baseline_evaluation_id"
    )


def _distribution_labels(value: Any) -> set[str] | None:
    if isinstance(value, Mapping):
        return {str(label) for label, count in value.items() if int(count or 0) > 0}
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    labels = {
        str(row.get("label") or row.get("score"))
        for row in value
        if isinstance(row, Mapping)
        and (row.get("label") is not None or row.get("score") is not None)
        and int(row.get("count") or 0) > 0
    }
    return labels or None


def _has_class_metrics(evaluation: Mapping[str, Any]) -> bool:
    return (
        bool(evaluation.get("confusion_matrix"))
        and _distribution_labels(evaluation.get("dataset_class_distribution")) is not None
        and _distribution_labels(evaluation.get("predicted_class_distribution")) is not None
    )


def _prediction_collapse(evaluation: Mapping[str, Any]) -> bool | None:
    actual = _distribution_labels(evaluation.get("dataset_class_distribution"))
    predicted = _distribution_labels(evaluation.get("predicted_class_distribution"))
    if actual is None or predicted is None:
        return None
    normalized_predicted = {label.strip().lower() for label in predicted}
    if "error" in normalized_predicted:
        return True
    return len(actual) > 1 and len(predicted) < 2


def _strict_improvement(baseline: Any, candidate: Any) -> bool:
    return (
        isinstance(baseline, (int, float))
        and not isinstance(baseline, bool)
        and isinstance(candidate, (int, float))
        and not isinstance(candidate, bool)
        and candidate > baseline
    )


def _non_regressing(baseline: Any, candidate: Any) -> bool:
    return (
        isinstance(baseline, (int, float))
        and not isinstance(baseline, bool)
        and isinstance(candidate, (int, float))
        and not isinstance(candidate, bool)
        and candidate >= baseline
    )
