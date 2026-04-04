from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, Optional

from plexus.cli.shared.evaluation_value_function import value

BUNDLE_SCHEMA_VERSION = "candidate_assessment_bundle.v1"

STAGE_DETERMINISTIC = "deterministic_reference"
STAGE_RANDOM_LOOP = "random_iteration"
STAGE_RANDOM_GATE = "random_gate"
REQUIRED_STAGE_KEYS = (STAGE_DETERMINISTIC, STAGE_RANDOM_LOOP)

ALLOWED_DECISIONS = {"accept", "reject", "inconclusive"}


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required and must be a non-empty string.")
    return value.strip()


def _normalize_status(value: Any, field_name: str) -> str:
    status = _require_non_empty_string(value, field_name).upper()
    return status


def _extract_metric(metrics: Any, *names: str) -> Optional[float]:
    if not isinstance(metrics, list):
        return None
    targets = {n.lower() for n in names}
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        metric_name = str(metric.get("name", "")).lower()
        if metric_name in targets:
            try:
                return float(metric.get("value"))
            except (TypeError, ValueError):
                return None
        if metric_name == "alignment" and "ac1" in targets:
            try:
                return float(metric.get("value"))
            except (TypeError, ValueError):
                return None
    return None


def _normalize_eval_summary(
    *,
    evaluation: Dict[str, Any],
    side: str,
    stage_key: str,
) -> Dict[str, Any]:
    if not isinstance(evaluation, dict):
        raise ValueError(f"{stage_key}.{side} must be a dictionary.")
    evaluation_id = _require_non_empty_string(
        evaluation.get("evaluation_id") or evaluation.get("id"),
        f"{stage_key}.{side}.evaluation_id",
    )
    status = _normalize_status(
        evaluation.get("status", "UNKNOWN"),
        f"{stage_key}.{side}.status",
    )

    metrics = evaluation.get("metrics")
    ac1 = _extract_metric(metrics, "ac1", "alignment")
    accuracy = _extract_metric(metrics, "accuracy")
    precision = _extract_metric(metrics, "precision")
    recall = _extract_metric(metrics, "recall")
    value_result = value(evaluation)
    value_score = (
        float(value_result.get("value"))
        if value_result.get("status") == "ok" and value_result.get("value") is not None
        else None
    )

    return {
        "evaluation_id": evaluation_id,
        "status": status,
        "processed_items": evaluation.get("processed_items") or evaluation.get("processedItems"),
        "total_items": evaluation.get("total_items") or evaluation.get("totalItems"),
        "metrics": {
            "ac1": ac1,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "value_score": value_score,
        },
    }


def _normalize_stage(
    *,
    stage_key: str,
    stage_payload: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(stage_payload, dict):
        raise ValueError(f"stage_runs.{stage_key} must be a dictionary.")

    baseline = _normalize_eval_summary(
        evaluation=stage_payload.get("baseline") or {},
        side="baseline",
        stage_key=stage_key,
    )
    candidate = _normalize_eval_summary(
        evaluation=stage_payload.get("candidate") or {},
        side="candidate",
        stage_key=stage_key,
    )

    protocol = stage_payload.get("protocol") or {}
    sample_size = protocol.get("sample_size")
    days = protocol.get("days")
    if sample_size is not None:
        try:
            sample_size = int(sample_size)
        except (TypeError, ValueError):
            raise ValueError(f"stage_runs.{stage_key}.protocol.sample_size must be an integer.")
        if sample_size <= 0:
            raise ValueError(f"stage_runs.{stage_key}.protocol.sample_size must be > 0.")
    if days is not None:
        try:
            days = int(days)
        except (TypeError, ValueError):
            raise ValueError(f"stage_runs.{stage_key}.protocol.days must be an integer.")
        if days <= 0:
            raise ValueError(f"stage_runs.{stage_key}.protocol.days must be > 0.")

    baseline_ac1 = baseline["metrics"]["ac1"]
    candidate_ac1 = candidate["metrics"]["ac1"]
    baseline_value = baseline["metrics"]["value_score"]
    candidate_value = candidate["metrics"]["value_score"]

    return {
        "stage_key": stage_key,
        "baseline": baseline,
        "candidate": candidate,
        "protocol": {
            "sample_size": sample_size,
            "days": days,
            "dataset_id": protocol.get("dataset_id"),
        },
        "deltas": {
            "ac1": (
                candidate_ac1 - baseline_ac1
                if baseline_ac1 is not None and candidate_ac1 is not None
                else None
            ),
            "value_score": (
                candidate_value - baseline_value
                if baseline_value is not None and candidate_value is not None
                else None
            ),
        },
    }


def _validate_gate_for_accept(stage_runs: Dict[str, Any], decision: Dict[str, Any]) -> None:
    if decision.get("decision") != "accept":
        return
    if STAGE_RANDOM_GATE not in stage_runs:
        raise ValueError("accept decision requires stage_runs.random_gate.")
    gate_stage = stage_runs[STAGE_RANDOM_GATE]
    gate_sample_size = gate_stage.get("protocol", {}).get("sample_size")
    if gate_sample_size is None or int(gate_sample_size) < 200:
        raise ValueError("accept decision requires random_gate sample_size >= 200.")
    baseline_status = gate_stage.get("baseline", {}).get("status")
    candidate_status = gate_stage.get("candidate", {}).get("status")
    if baseline_status != "COMPLETED" or candidate_status != "COMPLETED":
        raise ValueError("accept decision requires random_gate baseline/candidate status COMPLETED.")


def _normalize_identity(identity: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(identity, dict):
        raise ValueError("identity must be a dictionary.")
    return {
        "scorecard_id": _require_non_empty_string(identity.get("scorecard_id"), "identity.scorecard_id"),
        "score_id": _require_non_empty_string(identity.get("score_id"), "identity.score_id"),
        "baseline_score_version_id": _require_non_empty_string(
            identity.get("baseline_score_version_id"),
            "identity.baseline_score_version_id",
        ),
        "candidate_score_version_id": _require_non_empty_string(
            identity.get("candidate_score_version_id"),
            "identity.candidate_score_version_id",
        ),
    }


def _normalize_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(decision, dict):
        raise ValueError("decision must be a dictionary.")
    decision_value = _require_non_empty_string(decision.get("decision"), "decision.decision").lower()
    if decision_value not in ALLOWED_DECISIONS:
        raise ValueError(f"decision.decision must be one of {sorted(ALLOWED_DECISIONS)}.")
    reason = _require_non_empty_string(decision.get("reason"), "decision.reason")
    confidence = decision.get("confidence")
    if confidence is not None:
        confidence = _require_non_empty_string(confidence, "decision.confidence").lower()
    return {
        "decision": decision_value,
        "reason": reason,
        "confidence": confidence,
    }


def _normalize_malfunction_context(malfunction_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    context = malfunction_context or {}
    if not isinstance(context, dict):
        raise ValueError("malfunction_context must be a dictionary when provided.")
    return {
        "category_shares": context.get("category_shares") or {},
        "evaluation_red_flags": context.get("evaluation_red_flags") or [],
        "primary_next_action": context.get("primary_next_action"),
    }


def create_candidate_assessment_bundle(
    *,
    identity: Dict[str, Any],
    stage_runs: Dict[str, Any],
    decision: Dict[str, Any],
    malfunction_context: Optional[Dict[str, Any]] = None,
    protocol_defaults: Optional[Dict[str, Any]] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build and validate the canonical candidate assessment bundle payload.

    This function is the single source of truth for the bundle wire contract.
    """
    normalized_identity = _normalize_identity(identity)
    if not isinstance(stage_runs, dict):
        raise ValueError("stage_runs must be a dictionary.")

    missing_required_stages = [stage for stage in REQUIRED_STAGE_KEYS if stage not in stage_runs]
    if missing_required_stages:
        raise ValueError(f"stage_runs missing required stages: {missing_required_stages}")

    normalized_stages = {
        STAGE_DETERMINISTIC: _normalize_stage(
            stage_key=STAGE_DETERMINISTIC,
            stage_payload=stage_runs[STAGE_DETERMINISTIC],
        ),
        STAGE_RANDOM_LOOP: _normalize_stage(
            stage_key=STAGE_RANDOM_LOOP,
            stage_payload=stage_runs[STAGE_RANDOM_LOOP],
        ),
    }
    if STAGE_RANDOM_GATE in stage_runs:
        normalized_stages[STAGE_RANDOM_GATE] = _normalize_stage(
            stage_key=STAGE_RANDOM_GATE,
            stage_payload=stage_runs[STAGE_RANDOM_GATE],
        )

    normalized_decision = _normalize_decision(decision)
    _validate_gate_for_accept(normalized_stages, normalized_decision)

    if created_at is not None:
        _require_non_empty_string(created_at, "created_at")
    bundle_created_at = created_at or _iso_utc_now()

    normalized_protocol_defaults = protocol_defaults or {}
    if not isinstance(normalized_protocol_defaults, dict):
        raise ValueError("protocol_defaults must be a dictionary when provided.")

    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "created_at": bundle_created_at,
        "identity": normalized_identity,
        "protocol_defaults": normalized_protocol_defaults,
        "stage_runs": normalized_stages,
        "malfunction_context": _normalize_malfunction_context(malfunction_context),
        "decision": normalized_decision,
    }


def build_candidate_assessment_compact_summary(
    *,
    bundle: Dict[str, Any],
    attachment_key: str,
) -> Dict[str, Any]:
    """Build compact summary fields for task/evaluation-facing storage surfaces."""
    if not isinstance(bundle, dict):
        raise ValueError("bundle must be a dictionary.")
    attachment_key = _require_non_empty_string(attachment_key, "attachment_key")

    identity = bundle.get("identity") or {}
    stage_runs = bundle.get("stage_runs") or {}
    decision = bundle.get("decision") or {}
    malfunction_context = bundle.get("malfunction_context") or {}

    def _stage_ref(stage_key: str) -> Optional[Dict[str, Any]]:
        stage = stage_runs.get(stage_key) or {}
        baseline = stage.get("baseline") or {}
        candidate = stage.get("candidate") or {}
        deltas = stage.get("deltas") or {}
        if not baseline and not candidate:
            return None
        return {
            "stage_key": stage_key,
            "baseline_evaluation_id": baseline.get("evaluation_id"),
            "candidate_evaluation_id": candidate.get("evaluation_id"),
            "baseline_status": baseline.get("status"),
            "candidate_status": candidate.get("status"),
            "delta_ac1": deltas.get("ac1"),
            "delta_value_score": deltas.get("value_score"),
        }

    stage_refs = [
        stage_ref
        for stage_ref in (
            _stage_ref(STAGE_DETERMINISTIC),
            _stage_ref(STAGE_RANDOM_LOOP),
            _stage_ref(STAGE_RANDOM_GATE),
        )
        if stage_ref is not None
    ]

    return {
        "schema_version": bundle.get("schema_version"),
        "attachment_key": attachment_key,
        "scorecard_id": identity.get("scorecard_id"),
        "score_id": identity.get("score_id"),
        "baseline_score_version_id": identity.get("baseline_score_version_id"),
        "candidate_score_version_id": identity.get("candidate_score_version_id"),
        "decision": decision.get("decision"),
        "decision_reason": decision.get("reason"),
        "decision_confidence": decision.get("confidence"),
        "primary_next_action": (malfunction_context.get("primary_next_action") or {}).get("action")
        if isinstance(malfunction_context.get("primary_next_action"), dict)
        else None,
        "stage_references": stage_refs,
    }


def build_candidate_assessment_attachment_key(
    *,
    task_id: str,
    baseline_score_version_id: str,
    candidate_score_version_id: str,
) -> str:
    """
    Build canonical bundle attachment key path.
    """
    task_id = _require_non_empty_string(task_id, "task_id")
    baseline_score_version_id = _require_non_empty_string(
        baseline_score_version_id,
        "baseline_score_version_id",
    )
    candidate_score_version_id = _require_non_empty_string(
        candidate_score_version_id,
        "candidate_score_version_id",
    )

    def _safe(fragment: str) -> str:
        return re.sub(r"[^a-zA-Z0-9._-]", "_", fragment)

    return (
        "candidate-assessments/"
        f"{_safe(task_id)}/"
        f"{_safe(baseline_score_version_id)}__vs__{_safe(candidate_score_version_id)}.json"
    )


def build_candidate_assessment_attachment_payload(bundle: Dict[str, Any]) -> str:
    """
    Return canonical JSON payload for attachment upload.
    """
    if not isinstance(bundle, dict):
        raise ValueError("bundle must be a dictionary.")
    return json.dumps(bundle, sort_keys=True, indent=2, ensure_ascii=True)
