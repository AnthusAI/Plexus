from __future__ import annotations

from typing import Any, Dict


ROUTE_SCORE_OPTIMIZATION = "score_configuration_optimization"
ROUTE_BUG_INVESTIGATION = "bug_investigation"
ROUTE_DATA_REMEDIATION = "data_remediation"
ROUTE_SME_CLARIFICATION = "sme_guideline_clarification"

ALLOWED_POLICY_DECISIONS = {"accept", "reject", "inconclusive"}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _derive_route_action(malfunction_context: Dict[str, Any]) -> Dict[str, str]:
    category_shares = malfunction_context.get("category_shares") or {}
    red_flags = malfunction_context.get("evaluation_red_flags") or []
    primary_next_action = malfunction_context.get("primary_next_action") or {}

    action_from_primary = primary_next_action.get("action")
    if action_from_primary in {
        ROUTE_SCORE_OPTIMIZATION,
        ROUTE_BUG_INVESTIGATION,
        ROUTE_DATA_REMEDIATION,
        ROUTE_SME_CLARIFICATION,
    }:
        return {
            "route_action": action_from_primary,
            "route_reason": "primary_next_action",
        }

    has_high_severity_mechanical_flag = any(
        isinstance(flag, dict)
        and str(flag.get("severity", "")).lower() == "high"
        and str(flag.get("flag", "")).lower()
        in {"mechanical_failures_present", "invalid_output_class_present"}
        for flag in red_flags
    )
    if has_high_severity_mechanical_flag:
        return {
            "route_action": ROUTE_BUG_INVESTIGATION,
            "route_reason": "high_severity_mechanical_red_flag",
        }

    mechanical_share = _to_float(category_shares.get("mechanical_malfunction"))
    info_gap_share = _to_float(category_shares.get("information_gap"))
    guideline_share = _to_float(category_shares.get("guideline_gap_requires_sme"))
    score_config_share = _to_float(category_shares.get("score_configuration_problem"))

    if mechanical_share >= 0.5:
        return {
            "route_action": ROUTE_BUG_INVESTIGATION,
            "route_reason": "mechanical_share_gte_0_5",
        }
    if info_gap_share >= 0.5:
        return {
            "route_action": ROUTE_DATA_REMEDIATION,
            "route_reason": "information_gap_share_gte_0_5",
        }
    if guideline_share >= 0.35 and score_config_share < 0.35:
        return {
            "route_action": ROUTE_SME_CLARIFICATION,
            "route_reason": "guideline_share_high_score_config_low",
        }
    return {
        "route_action": ROUTE_SCORE_OPTIMIZATION,
        "route_reason": "score_configuration_primary_fix_surface",
    }


def synthesize_workflow_decision(
    *,
    policy_decision: Dict[str, Any],
    malfunction_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Merge quantitative policy decision with malfunction-routing signals.
    """
    if not isinstance(policy_decision, dict):
        raise ValueError("policy_decision must be a dictionary.")
    raw_policy = str(policy_decision.get("decision", "")).strip().lower()
    if raw_policy not in ALLOWED_POLICY_DECISIONS:
        raise ValueError(
            f"policy_decision.decision must be one of {sorted(ALLOWED_POLICY_DECISIONS)}."
        )

    normalized_context = malfunction_context or {}
    if not isinstance(normalized_context, dict):
        raise ValueError("malfunction_context must be a dictionary when provided.")

    route = _derive_route_action(normalized_context)
    route_action = route["route_action"]

    if route_action != ROUTE_SCORE_OPTIMIZATION:
        final_decision = "reroute"
        final_reason = route["route_reason"]
        confidence = "high"
    else:
        final_decision = raw_policy
        final_reason = str(policy_decision.get("reason") or "policy_decision")
        confidence = (
            "medium" if raw_policy == "inconclusive" else "high"
        )

    return {
        "final_decision": final_decision,
        "final_reason": final_reason,
        "confidence": confidence,
        "route_action": route_action,
        "route_reason": route["route_reason"],
        "policy_decision": {
            "decision": raw_policy,
            "reason": policy_decision.get("reason"),
        },
    }
