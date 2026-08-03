"""Deterministic operator-facing action projections for optimization reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any


_AUTOMATIC_DISPOSITIONS = {
    "continue_optimization",
    "awaiting_optimizer_review",
    "optimization_in_progress",
    "optimizer_launching",
}
_HUMAN_DISPOSITIONS = {
    "promotion_ready",
    "stakeholder_decision_required",
    "stakeholder_clarification_required",
    "awaiting_optimization_approval",
}
_TECHNICAL_DISPOSITIONS = {"guideline_or_code_repair"}
_FEEDBACK_DISPOSITIONS = {
    "feedback_curation_review",
    "targeted_feedback_collection",
}
_MONITOR_DISPOSITIONS = {
    "monitoring_or_diminishing_returns",
    "cooldown",
    "no_safe_improvement",
}
_INCOMPLETE_DISPOSITIONS = {"insufficient_evidence", "failed_or_incomplete"}

_ACTION_GROUP_METADATA = {
    "automatic_work": {
        "title": "Automatic optimization work",
        "owner_role": "automation",
        "queue_state": "open",
        "consequence_of_inaction": "The selected improvement work will not advance to validated evidence.",
    },
    "stakeholder_decision": {
        "title": "Stakeholder decision",
        "owner_role": "stakeholder",
        "queue_state": "open",
        "consequence_of_inaction": "The affected score remains blocked at its current decision checkpoint.",
    },
    "technical_repair": {
        "title": "Score definition repair",
        "owner_role": "score_maintainer",
        "queue_state": "open",
        "consequence_of_inaction": "The affected score remains ineligible for safe automatic optimization.",
    },
    "feedback_investment": {
        "title": "Feedback evidence work",
        "owner_role": "feedback_owner",
        "queue_state": "open",
        "consequence_of_inaction": "Future optimization decisions remain weak or inconclusive.",
    },
    "monitor": {
        "title": "Monitor later",
        "owner_role": "operator",
        "queue_state": "monitor",
        "consequence_of_inaction": "No immediate action is expected; the item remains eligible for a later review.",
    },
    "incomplete_evidence": {
        "title": "Repair incomplete evidence",
        "owner_role": "operator",
        "queue_state": "open",
        "consequence_of_inaction": "The portfolio cannot claim an exact or optimization-ready decision.",
    },
    "no_action": {
        "title": "No action supported",
        "owner_role": "operator",
        "queue_state": "history",
        "consequence_of_inaction": "No follow-up is currently required.",
    },
}


def _count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _action_group(row: Mapping[str, Any]) -> str:
    disposition = str(row.get("primary_disposition") or "")
    action = str(row.get("next_action") or row.get("primary_next_action") or "")
    if disposition in _AUTOMATIC_DISPOSITIONS or action in {
        "run_approved_optimization",
        "dispatch_approved_targets",
        "continue_optimization",
        "await_optimizer_review",
    }:
        return "automatic_work"
    if disposition in _HUMAN_DISPOSITIONS or action in {
        "request_optimization_approval",
        "request_promotion_approval",
        "resolve_stakeholder_questions",
        "request_stakeholder_clarification",
    }:
        return "stakeholder_decision"
    if disposition in _TECHNICAL_DISPOSITIONS or action.startswith("repair_guideline"):
        return "technical_repair"
    if disposition in _FEEDBACK_DISPOSITIONS or action in {
        "review_feedback_curation",
        "collect_targeted_feedback",
        "increase_feedback_collection",
    }:
        return "feedback_investment"
    if disposition in _MONITOR_DISPOSITIONS or action in {
        "wait_for_cooldown",
        "retain_champion",
        "monitor",
        "periodic_monitoring",
    }:
        return "monitor"
    if disposition in _INCOMPLETE_DISPOSITIONS or action.startswith("repair_"):
        return "incomplete_evidence"
    return "no_action"


def _dominant_issue(row: Mapping[str, Any]) -> str:
    explicit = row.get("primary_issue") or row.get("issue_flag")
    if explicit:
        return str(explicit)
    flags = sorted({str(flag) for flag in row.get("secondary_issue_flags") or [] if flag})
    return flags[0] if flags else "none"


def _workstream_id(action_group: str, action: str, issue: str) -> str:
    identity = f"{action_group}\0{action}\0{issue}".encode("utf-8")
    return f"workstream-{sha256(identity).hexdigest()[:16]}"


def build_action_projection(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Group every score into exactly one deterministic operator workstream."""
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for source in rows:
        row = dict(source)
        action_group = _action_group(row)
        action = str(row.get("next_action") or row.get("primary_next_action") or "review")
        issue = _dominant_issue(row)
        grouped.setdefault((action_group, action, issue), []).append(row)

    workstreams: list[dict[str, Any]] = []
    for (action_group, action, issue), members in grouped.items():
        metadata = _ACTION_GROUP_METADATA[action_group]
        ordered = sorted(
            members,
            key=lambda row: (
                -_count(row.get("valid_feedback_count") or row.get("evidence_count")),
                str(row.get("scorecard_name") or "").casefold(),
                str(row.get("score_name") or "").casefold(),
            ),
        )
        scorecards = {
            str(row.get("scorecard_ref") or row.get("scorecard_name") or "Unlabeled scorecard")
            for row in ordered
        }
        evidence_count = sum(
            _count(row.get("valid_feedback_count") or row.get("evidence_count"))
            for row in ordered
        )
        representative_rows = [
            {
                "scorecard_name": row.get("scorecard_name"),
                "score_name": row.get("score_name"),
                "primary_disposition": row.get("primary_disposition"),
                "evidence_count": _count(
                    row.get("valid_feedback_count") or row.get("evidence_count")
                ),
                "rationale": row.get("rationale"),
                "next_action": action,
                "dashboard_url": row.get("dashboard_url"),
            }
            for row in ordered[:5]
        ]
        workstreams.append(
            {
                "id": _workstream_id(action_group, action, issue),
                "action_group": action_group,
                "title": str(metadata["title"]),
                "owner_role": str(metadata["owner_role"]),
                "queue_state": str(metadata["queue_state"]),
                "score_count": len(ordered),
                "scorecard_count": len(scorecards),
                "evidence_count": evidence_count,
                "next_action": action,
                "dominant_issue": issue,
                "rationale": next(
                    (str(row.get("rationale")) for row in ordered if row.get("rationale")),
                    "This workstream groups scores with the same required next action.",
                ),
                "consequence_of_inaction": str(metadata["consequence_of_inaction"]),
                "representative_rows": representative_rows,
            }
        )

    queue_order = {"open": 0, "monitor": 1, "history": 2}
    group_order = {
        "automatic_work": 0,
        "stakeholder_decision": 1,
        "technical_repair": 2,
        "feedback_investment": 3,
        "incomplete_evidence": 4,
        "monitor": 5,
        "no_action": 6,
    }
    workstreams.sort(
        key=lambda item: (
            queue_order[str(item["queue_state"])],
            group_order[str(item["action_group"])],
            -int(item["evidence_count"]),
            str(item["id"]),
        )
    )
    grouped_counts = {
        group: sum(int(item["score_count"]) for item in workstreams if item["action_group"] == group)
        for group in _ACTION_GROUP_METADATA
    }
    action_counts = {
        "automatic_work": grouped_counts["automatic_work"],
        "human_decisions": grouped_counts["stakeholder_decision"],
        "repairs_and_evidence": (
            grouped_counts["technical_repair"]
            + grouped_counts["feedback_investment"]
            + grouped_counts["incomplete_evidence"]
        ),
        "monitor_later": grouped_counts["monitor"],
        "no_action": grouped_counts["no_action"],
    }
    return {
        "score_count": len(rows),
        "action_counts": action_counts,
        "action_workstreams": workstreams,
    }


def build_decision_summary(
    overview: Mapping[str, Any],
    disposition_counts: Mapping[str, Any],
) -> dict[str, str]:
    """Return one honest, backend-authored conclusion for the current revision."""
    lifecycle = str(overview.get("lifecycle_status") or "running").lower()
    inventory = str(overview.get("inventory_coverage_status") or "complete").lower()
    analysis = str(overview.get("analysis_coverage_status") or "pending").lower()
    selected = _count(overview.get("execution_selected_count"))
    launched = _count(overview.get("execution_launched_count"))
    reviewed = _count(overview.get("optimizer_review_count"))
    improved = _count(disposition_counts.get("promotion_ready"))
    next_action = str(overview.get("next_checkpoint") or "Review the latest Report evidence.")

    if lifecycle in {"failed", "blocked"}:
        return {
            "state": "failure",
            "headline": "The optimization run could not complete",
            "explanation": "A run-level failure prevents a reliable portfolio decision.",
            "next_action": next_action,
        }
    if lifecycle == "incomplete" or inventory == "incomplete" or analysis == "incomplete":
        return {
            "state": "incomplete_evidence",
            "headline": "The available evidence is incomplete",
            "explanation": "The run cannot claim an exact ranking or a safe automatic optimization decision.",
            "next_action": next_action,
        }
    if improved > 0:
        return {
            "state": "validated_improvement",
            "headline": f"{improved} validated improvement{'s' if improved != 1 else ''} require{'s' if improved == 1 else ''} review",
            "explanation": "Evaluation evidence supports improvement, but champion promotion remains a separate human decision.",
            "next_action": "Review the promotion evidence and decide whether to promote.",
        }
    terminal = lifecycle in {
        "complete",
        "completed",
        "complete_with_unresolved_actions",
        "completed_with_unresolved_actions",
    }
    if launched > reviewed or (launched > 0 and not terminal):
        return {
            "state": "optimization_running",
            "headline": f"{launched} optimization{'s are' if launched != 1 else ' is'} in progress",
            "explanation": "The run is waiting for terminal optimizer and evaluation evidence.",
            "next_action": next_action,
        }
    if selected > 0 and launched == 0 and not terminal:
        return {
            "state": "safe_target_selected",
            "headline": f"{selected} score{'s are' if selected != 1 else ' is'} selected for optimization",
            "explanation": "The selected targets passed the current automatic execution policy and await launch-time checks.",
            "next_action": next_action,
        }
    if terminal and launched > 0:
        return {
            "state": "no_validated_improvement",
            "headline": "Optimization completed without a validated improvement",
            "explanation": "No candidate produced evidence sufficient for promotion review.",
            "next_action": next_action,
        }
    if terminal:
        return {
            "state": "no_safe_target",
            "headline": "No score was safe to optimize automatically",
            "explanation": "The run found portfolio work, but no target passed every execution policy gate.",
            "next_action": next_action,
        }
    return {
        "state": "analysis_pending",
        "headline": "No optimization decision yet",
        "explanation": "Analysis is still determining which scores are safe and worthwhile to optimize.",
        "next_action": next_action,
    }
