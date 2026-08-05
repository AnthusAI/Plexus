"""Compact, attachment-ready handoffs for optimization-survey follow-up.

This module is deliberately pure.  It projects stakeholder-safe presentation
rows plus immutable decision packets into a small overview and page-sized JSON
attachments without reading storage or mutating a Report.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from plexus.optimization.report_actions import build_decision_summary


SCHEMA_VERSION = "optimization-agent-handoff/v1"
MAX_ITEMS_PER_PAGE = 25
MAX_PAGE_BYTES = 24 * 1024
_TEXT_LIMIT = 900

_PRIORITY = {
    "complete_promotion_evidence": 0,
    "review_promotion": 1,
    "investigate_optimizer_failure": 2,
    "resolve_guideline_code_conflict": 3,
    "resolve_feedback_guideline_question": 4,
    "add_missing_guidelines": 5,
    "repair_invalid_guidelines": 6,
    "repair_score_structure": 7,
    "collect_more_evidence": 8,
    "review_collection_policy": 9,
    "monitor_after_cooldown": 10,
    "monitor_no_improvement": 11,
}


def _text(value: Any, *, limit: int = _TEXT_LIMIT) -> str:
    if value is None:
        return ""
    result = str(value).strip()
    return result if len(result) <= limit else f"{result[:limit - 1]}…"


def _strings(values: Any, *, max_items: int = 20) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return [
        _text(value, limit=300)
        for value in values[:max_items]
        if value is not None and _text(value, limit=300)
    ]


def _limitations(overview: Mapping[str, Any]) -> list[str]:
    """Return bounded, material limitations without copying evidence packets."""
    values: list[Any] = []
    explicit = overview.get("limitations") or overview.get("limitations_and_safety")
    if isinstance(explicit, str):
        values.append(explicit)
    elif isinstance(explicit, Sequence) and not isinstance(
        explicit, (bytes, bytearray)
    ):
        values.extend(explicit)

    detail_limitation = overview.get("execution_detail_limitation")
    if isinstance(detail_limitation, str) and detail_limitation.strip():
        values.append(detail_limitation)

    diagnosis_limit = overview.get("diagnosis_limit_explanation")
    if isinstance(diagnosis_limit, str) and diagnosis_limit.strip():
        values.append(diagnosis_limit)

    blockers = overview.get("diagnosis_blockers")
    if isinstance(blockers, str):
        values.append(blockers)
    elif isinstance(blockers, Sequence) and not isinstance(
        blockers, (bytes, bytearray)
    ):
        values.extend(blockers)

    notes = overview.get("notes")
    note_values = [notes] if isinstance(notes, str) else notes
    if isinstance(note_values, Sequence) and not isinstance(
        note_values, (str, bytes, bytearray)
    ):
        material_terms = (
            "incomplete",
            "partial",
            "unavailable",
            "missing",
            "failed",
            "block",
            "limitation",
            "cannot",
            "could not",
        )
        values.extend(
            note
            for note in note_values
            if isinstance(note, str)
            and any(term in note.casefold() for term in material_terms)
        )
    return list(dict.fromkeys(_strings(values, max_items=20)))


def _coverage_summary(
    overview: Mapping[str, Any], *, provisional: bool
) -> dict[str, Any]:
    fallback = _text(overview.get("coverage_status") or "not_provided", limit=80)
    inventory = _text(
        overview.get("inventory_coverage_status") or fallback, limit=80
    )
    analysis = _text(overview.get("analysis_coverage_status") or fallback, limit=80)
    result: dict[str, Any] = {
        "inventory": inventory,
        "analysis": analysis,
        "complete": inventory == "complete" and analysis == "complete",
        "provisional": provisional,
    }
    reason = _text(overview.get("analysis_incomplete_reason"), limit=80)
    if reason:
        result["incomplete_reason"] = reason
    diagnosis_counts = {
        "selected": overview.get("diagnosis_selected_count"),
        "scheduled": overview.get("diagnosis_scheduled_count"),
        "completed": overview.get("diagnosis_completed_count"),
        "deferred": overview.get("diagnosis_deferred_count"),
        "configured_limit": overview.get("diagnosis_max_count"),
    }
    normalized_counts = {
        key: int(value)
        for key, value in diagnosis_counts.items()
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
    }
    if normalized_counts:
        result["diagnosis"] = normalized_counts
    return result


def _optimizer_metrics(packet: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    """Project only bounded numeric comparison metrics from review evidence."""
    alignment = packet.get("alignment_evidence")
    if not isinstance(alignment, Mapping):
        return {}
    result: dict[str, dict[str, float]] = {}
    for cohort in ("recent", "regression"):
        source = alignment.get(cohort)
        if not isinstance(source, Mapping):
            continue
        metrics: dict[str, float] = {}
        for field in ("baseline", "candidate", "delta"):
            value = source.get(field)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                number = float(value)
                if isfinite(number):
                    metrics[field] = number
        if metrics:
            result[cohort] = metrics
    return result


def _hash_ref(value: Any) -> str:
    return sha256(str(value).encode("utf-8")).hexdigest()[:16]


def _identifier(value: Any) -> str | None:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    identifier = str(value).strip()
    return identifier or None


def _target_key(packet: Mapping[str, Any]) -> tuple[str, str] | None:
    scope = packet.get("scope") if isinstance(packet.get("scope"), Mapping) else {}
    scorecard_id = packet.get("scorecard_id") or scope.get("scorecard_id")
    score_id = packet.get("score_id") or scope.get("score_id")
    scorecard_id = _identifier(scorecard_id)
    score_id = _identifier(score_id)
    if scorecard_id is None or score_id is None:
        return None
    return scorecard_id, score_id


def _packet_index(decision_evidence: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Join stage packets by target, accepting legacy packet envelopes."""
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for collection_name in ("rank", "assessments", "diagnoses", "reviews", "promotion_candidates"):
        records = decision_evidence.get(collection_name)
        if (
            collection_name == "rank"
            and isinstance(records, Mapping)
            and isinstance(records.get("ranked"), Sequence)
        ):
            records = records["ranked"]
        if isinstance(records, Mapping):
            records = [records]
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
            continue
        for record in records:
            if not isinstance(record, Mapping):
                continue
            packet = dict(record)
            # Review packet evidence retains legacy result fields in the common
            # packet envelope.  Merge it only as a fallback to preserve exact
            # current fields.
            evidence = packet.get("evidence")
            if isinstance(evidence, Mapping):
                packet = {**dict(evidence), **packet}
            if collection_name == "reviews":
                review_evidence_ids = packet.get("evidence_ids")
                if isinstance(review_evidence_ids, Sequence) and not isinstance(
                    review_evidence_ids, (str, bytes, bytearray)
                ):
                    packet["_optimizer_review_evidence_ids"] = list(
                        review_evidence_ids
                    )
            key = _target_key(packet)
            if key is not None:
                indexed.setdefault(key, {}).update(packet)
    dispatch = decision_evidence.get("dispatch")
    if isinstance(dispatch, Mapping):
        children = dispatch.get("children") or []
        if isinstance(children, Mapping):
            children = [children]
        for child in children if isinstance(children, Sequence) else []:
            if not isinstance(child, Mapping):
                continue
            target = child.get("target")
            target = dict(target) if isinstance(target, Mapping) else {}
            merged_child = {**target, **dict(child)}
            if (key := _target_key(merged_child)) is not None:
                indexed.setdefault(key, {}).update(merged_child)
    return indexed


def _row_key(
    row: Mapping[str, Any], indexed: Mapping[tuple[str, str], Any]
) -> tuple[str, str] | None:
    direct = _target_key(row)
    if direct is not None:
        return direct
    card_ref, score_ref = str(row.get("scorecard_ref") or ""), str(row.get("score_ref") or "")
    for key in indexed:
        if _hash_ref(key[0]) == card_ref and _hash_ref(key[1]) == score_ref:
            return key
    return None


def _evaluation_ids(packet: Mapping[str, Any]) -> list[str]:
    """Return only exact scalar evaluation references in evidence order."""
    values: list[Any] = []
    for field in (
        "evaluation_ids",
        "evaluation_id",
        "matched_recent_evaluation_id",
        "historical_regression_evaluation_id",
        "recent_evaluation_id",
        "historical_evaluation_id",
        # Legacy packets occasionally stored IDs under these result names;
        # booleans and mappings under the same names are deliberately ignored.
        "matched_recent_evaluation",
        "historical_regression_evidence",
    ):
        value = packet.get(field)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            values.extend(value)
        else:
            values.append(value)
    # Generic diagnosis evidence IDs identify restricted semantic artifacts,
    # not Evaluations.  Only the optimizer-review collection establishes that
    # its evidence IDs are evaluation references.
    evidence_ids = packet.get("_optimizer_review_evidence_ids")
    if isinstance(evidence_ids, Sequence) and not isinstance(
        evidence_ids, (str, bytes, bytearray)
    ):
        values.extend(evidence_ids)
    procedure_id = packet.get("procedure_id")
    result: list[str] = []
    for value in values:
        identifier = _identifier(value)
        if not identifier or identifier == str(procedure_id or "") or identifier in result:
            continue
        result.append(identifier)
    return result


def _promotion_evidence_complete(packet: Mapping[str, Any]) -> bool:
    state = packet.get("states") if isinstance(packet.get("states"), Mapping) else {}
    explicitly_ready = (
        packet.get("promotion_ready") is True
        or packet.get("post_run_state") == "promotion_ready"
        or state.get("post_run") == "promotion_ready"
    )
    return bool(
        explicitly_ready
        and _identifier(
            packet.get("champion_version")
            or packet.get("champion")
            or packet.get("champion_version_id")
        )
        and _identifier(
            packet.get("candidate_version_id") or packet.get("candidate_version")
        )
        and _evaluation_ids(packet)
    )


def _kind(row: Mapping[str, Any], packet: Mapping[str, Any]) -> str | None:
    disposition = _text(row.get("primary_disposition"))
    action = _text(row.get("next_action") or row.get("primary_next_action"))
    flags = set(_strings(row.get("secondary_issue_flags")))
    for value in (row.get("primary_issue"), row.get("issue_flag")):
        if isinstance(value, str) and value:
            flags.add(value)
    summary = row.get("secondary_issue_summary")
    if isinstance(summary, str):
        flags.update(value.strip() for value in summary.split(",") if value.strip())
    packet_states = packet.get("states") if isinstance(packet.get("states"), Mapping) else {}
    state = _text(packet.get("post_run_state") or packet_states.get("post_run"))
    promotion_ready = _promotion_evidence_complete(packet)
    if (
        disposition == "validated_improvement"
        or action == "complete_promotion_evidence"
        or state == "validated_improvement"
    ):
        return "review_promotion" if promotion_ready else "complete_promotion_evidence"
    if (
        disposition == "promotion_ready"
        or action in {"request_promotion_approval", "review_promotion"}
        or state == "promotion_ready"
    ):
        return "review_promotion" if promotion_ready else "complete_promotion_evidence"
    if (
        disposition == "failed_or_incomplete"
        or packet.get("failed") is True
        or state == "failed_or_incomplete"
    ):
        return "investigate_optimizer_failure"
    if "potential_code_conflict" in flags:
        return "resolve_guideline_code_conflict"
    if "feedback_rubric_contradiction" in flags:
        return "resolve_feedback_guideline_question"
    if (
        "stakeholder_question" in flags
        or _strings(row.get("stakeholder_questions"))
        or _strings(packet.get("stakeholder_questions"))
        or action in {
            "resolve_stakeholder_questions",
            "request_stakeholder_clarification",
        }
    ):
        return "resolve_feedback_guideline_question"
    if "missing_guidelines" in flags:
        return "add_missing_guidelines"
    if "invalid_guidelines" in flags:
        return "repair_invalid_guidelines"
    if (
        any(
            flag in flags
            for flag in {"missing_score_structure", "invalid_score_structure"}
        )
        or "structure" in action
        or action in {"assign_champion", "review_score_status"}
    ):
        return "repair_score_structure"
    if disposition == "targeted_feedback_collection" or action in {
        "collect_targeted_feedback",
        "increase_feedback_collection",
    }:
        return "collect_more_evidence"
    if disposition == "feedback_curation_review" or "collection_policy" in action:
        return "review_collection_policy"
    if disposition == "cooldown" or action == "wait_for_cooldown":
        return "monitor_after_cooldown"
    if disposition in {
        "monitoring_or_diminishing_returns",
        "no_safe_improvement",
    } or action in {"retain_champion", "periodic_monitoring", "monitor"}:
        return "monitor_no_improvement"
    # Incomplete evidence should remain actionable, but a merely unselected
    # score is history rather than an agent recommendation.
    if disposition == "insufficient_evidence" or "incomplete_evidence" in flags:
        return "collect_more_evidence"
    return None


def _resource_refs(key: tuple[str, str] | None, packet: Mapping[str, Any]) -> dict[str, Any]:
    refs: dict[str, Any] = {}
    if key is not None:
        refs["scorecard_id"], refs["score_id"] = key
    names = {
        "champion_version_id": ("champion_version", "champion", "champion_version_id"),
        "candidate_version_id": ("candidate_version_id", "candidate_version"),
        "procedure_id": ("procedure_id",),
        "task_id": ("task_id",),
    }
    for target, candidates in names.items():
        for source in candidates:
            value = _identifier(packet.get(source))
            if value is not None:
                refs[target] = value
                break
    evaluation_ids = _evaluation_ids(packet)
    if evaluation_ids:
        refs["evaluation_ids"] = evaluation_ids
    return refs


def _suggested_calls(kind: str, refs: Mapping[str, Any]) -> dict[str, Any]:
    read = [
        {
            "name": "plexus.score.info",
            "arguments": {
                key: refs[key]
                for key in ("scorecard_id", "score_id")
                if key in refs
            },
        }
    ]
    for evaluation_id in refs.get("evaluation_ids") or []:
        read.append({"name": "plexus.evaluation.info", "arguments": {"id": evaluation_id}})
    if refs.get("procedure_id"):
        read.append({"name": "plexus.procedure.info", "arguments": {"id": refs["procedure_id"]}})
    result: dict[str, Any] = {"read": read}
    if kind == "review_promotion" and all(
        refs.get(key)
        for key in ("score_id", "champion_version_id", "candidate_version_id")
    ):
        result["mutation"] = {
            "name": "plexus.score.set_champion",
            "arguments": {
                "score_id": refs["score_id"],
                "version_id": refs["candidate_version_id"],
                "expected_champion_version_id": refs["champion_version_id"],
            },
            "requires_human_approval": True,
        }
    return result


def _followup(
    row: Mapping[str, Any],
    packet: Mapping[str, Any],
    key: tuple[str, str] | None,
    kind: str,
) -> dict[str, Any]:
    refs = _resource_refs(key, packet)
    flags = _strings(row.get("secondary_issue_flags"))
    gaps = _strings(packet.get("missing_evidence") or packet.get("evidence_gaps"))
    if kind == "complete_promotion_evidence" and not gaps:
        gaps = [
            "Promotion evidence is incomplete; verify the terminal evaluation "
            "and required review artifacts."
        ]
    if kind == "review_promotion":
        gaps = []
    reference_key = key or (
        str(row.get("scorecard_ref") or "unknown"),
        str(row.get("score_ref") or "unknown"),
    )
    finding = _text(
        packet.get("finding")
        or row.get("finding")
        or row.get("rationale")
        or f"{kind.replace('_', ' ')} was identified."
    )
    return {
        "reference": f"followup:{reference_key[0]}:{reference_key[1]}",
        "kind": kind,
        "scorecard_name": _text(
            row.get("scorecard_name")
            or packet.get("scorecard_name")
            or "Unlabeled scorecard",
            limit=240,
        ),
        "score_name": _text(
            row.get("score_name")
            or packet.get("score_name")
            or "Unlabeled score",
            limit=240,
        ),
        "resource_refs": refs,
        "finding": finding,
        "rationale": _text(row.get("rationale") or packet.get("rationale") or finding),
        "evidence_gaps": gaps,
        "desired_outcome": _text(
            packet.get("desired_outcome")
            or "Verify live state and complete the stated follow-up safely."
        ),
        "safety_constraints": [
            "Verify live resource state before any mutation.",
            "Do not automatically change score code, guidelines, feedback settings, or champion.",
        ],
        "frozen_preconditions": {
            "champion_version_id": refs.get("champion_version_id"),
            "feedback_watermark": _text(
                packet.get("feedback_watermark") or packet.get("watermark"),
                limit=180,
            )
            or None,
            "configuration_digest": _text(
                packet.get("configuration_digest") or packet.get("config_digest"),
                limit=180,
            )
            or None,
            "guideline_digest": _text(
                packet.get("guideline_digest") or packet.get("guidelines_digest"),
                limit=180,
            )
            or None,
            "evidence_fingerprint": _text(
                packet.get("evidence_fingerprint") or packet.get("fingerprint"),
                limit=180,
            )
            or None,
        },
        # Score-brief IDs depend on the publisher's scorecard grouping and row
        # index.  Only preserve IDs already resolved by the publisher; never
        # invent a plausible-looking attachment reference here.
        "artifact_logical_ids": _strings(
            row.get("artifact_logical_ids") or packet.get("artifact_logical_ids"),
            max_items=20,
        ),
        "suggested_calls": _suggested_calls(kind, refs),
        "promotion_ready": kind == "review_promotion",
        "optimizer_metrics": _optimizer_metrics(packet),
        "issue_flags": flags,
    }


def _encoded(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _pages(
    items: Sequence[Mapping[str, Any]], *, report_id: str, revision: Any
) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    current: list[Mapping[str, Any]] = []
    def page_payload(index: int, values: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "logical_id": f"scorecard_followups:{revision}:{index:04d}",
            "report_id": report_id,
            "revision": revision,
            "items": list(values),
        }
    for item in items:
        candidate = [*current, item]
        payload = page_payload(len(pages) + 1, candidate)
        if current and (
            len(candidate) > MAX_ITEMS_PER_PAGE
            or len(_encoded(payload)) > MAX_PAGE_BYTES
        ):
            pages.append(page_payload(len(pages) + 1, current))
            current = [item]
        else:
            current = candidate
        # The fixed field limits make a one-item page safely bounded.  Keep a
        # hard error here so a future schema expansion cannot silently publish
        # an invalid artifact.
        if len(_encoded(page_payload(len(pages) + 1, current))) > MAX_PAGE_BYTES:
            raise ValueError("one scorecard follow-up exceeds the 24 KB artifact limit")
    if current:
        pages.append(page_payload(len(pages) + 1, current))
    return pages


def build_agent_handoff_artifacts(
    *,
    decision_evidence: Mapping[str, Any],
    stakeholder_view: Mapping[str, Any],
    report_metadata: Mapping[str, Any],
    finalized: bool = False,
) -> dict[str, Any]:
    """Build compact agent overview and deterministic follow-up JSON pages.

    ``decision_evidence`` may be a partial milestone packet.  Missing legacy
    fields simply remain absent in output instead of preventing publication.
    """
    indexed = _packet_index(decision_evidence)
    rows = stakeholder_view.get("portfolio") or []
    followups: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        key = _row_key(row, indexed)
        packet = indexed.get(key, {}) if key is not None else {}
        kind = _kind(row, packet)
        if kind:
            followups.append(_followup(row, packet, key, kind))
    followups.sort(key=lambda item: (_PRIORITY[item["kind"]], item["reference"]))
    report_id = _text(report_metadata.get("report_id") or report_metadata.get("id"), limit=180)
    revision = report_metadata.get("revision") or report_metadata.get("revision_number") or 1
    pages = _pages(followups, report_id=report_id, revision=revision)
    overview = (
        stakeholder_view.get("overview")
        if isinstance(stakeholder_view.get("overview"), Mapping)
        else {}
    )
    disposition_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        disposition = _text(row.get("primary_disposition")) or "not_selected"
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
    if not disposition_counts and isinstance(
        overview.get("primary_disposition_counts"), Mapping
    ):
        disposition_counts = {
            str(key): int(value)
            for key, value in overview["primary_disposition_counts"].items()
            if isinstance(value, int) and not isinstance(value, bool)
        }
    provisional = not finalized
    conclusion = build_decision_summary(overview, disposition_counts)
    # Dict insertion order is part of this artifact contract.  Agents see the
    # highest-value workstream first even before opening a page attachment.
    counts = {
        kind: count
        for kind in _PRIORITY
        if (count := sum(1 for item in followups if item["kind"] == kind))
    }
    handoff = {
        "schema_version": SCHEMA_VERSION,
        "report_id": report_id,
        "revision": revision,
        "milestone": _text(report_metadata.get("milestone"), limit=120),
        "provisional": provisional,
        "conclusion": conclusion,
        "coverage": _coverage_summary(overview, provisional=provisional),
        "limitations": _limitations(overview),
        "next_checkpoint": _text(
            overview.get("next_checkpoint")
            or "Review the highest-priority follow-up."
        ),
        "workstream_counts": counts,
        "priority_representatives": [
            {
                key: item[key]
                for key in (
                    "reference",
                    "kind",
                    "scorecard_name",
                    "score_name",
                    "finding",
                )
            }
            for item in followups[:5]
        ],
        "followup_page_logical_ids": [page["logical_id"] for page in pages],
    }
    if len(_encoded(handoff)) >= 20 * 1024:
        raise ValueError("agent handoff exceeds the 20 KB compact-response limit")
    return {"agent_handoff": handoff, "followup_pages": pages}
