from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any

from plexus.cli.shared.evaluation_value_function import value, ValueFunctionConfig


@dataclass(frozen=True)
class AcceptancePolicyConfig:
    min_reference_delta: float = 0.01
    max_generalization_drop: float = 0.02
    require_reference_improvement: bool = True
    value_config: ValueFunctionConfig = ValueFunctionConfig()


def assess_candidate(
    *,
    baseline_reference_eval: Dict[str, Any],
    candidate_reference_eval: Dict[str, Any],
    baseline_random_eval: Dict[str, Any],
    candidate_random_eval: Dict[str, Any],
    config: AcceptancePolicyConfig = AcceptancePolicyConfig(),
) -> Dict[str, Any]:
    """
    Decide accept/reject/inconclusive for a candidate score version.
    """
    b_ref = value(baseline_reference_eval, config=config.value_config)
    c_ref = value(candidate_reference_eval, config=config.value_config)
    b_rand = value(baseline_random_eval, config=config.value_config)
    c_rand = value(candidate_random_eval, config=config.value_config)

    if any(v.get("status") != "ok" for v in (b_ref, c_ref, b_rand, c_rand)):
        return {
            "decision": "inconclusive",
            "reason": "insufficient_evidence",
            "details": {
                "baseline_reference": b_ref,
                "candidate_reference": c_ref,
                "baseline_random": b_rand,
                "candidate_random": c_rand,
                "config": asdict(config),
            },
        }

    reference_delta = c_ref["value"] - b_ref["value"]
    random_delta = c_rand["value"] - b_rand["value"]

    if config.require_reference_improvement and reference_delta < config.min_reference_delta:
        return {
            "decision": "reject",
            "reason": "insufficient_reference_improvement",
            "details": {
                "reference_delta": reference_delta,
                "random_delta": random_delta,
                "config": asdict(config),
            },
        }

    if random_delta < -config.max_generalization_drop:
        return {
            "decision": "reject",
            "reason": "generalization_regression",
            "details": {
                "reference_delta": reference_delta,
                "random_delta": random_delta,
                "config": asdict(config),
            },
        }

    return {
        "decision": "accept",
        "reason": "meets_reference_and_generalization_policy",
        "details": {
            "reference_delta": reference_delta,
            "random_delta": random_delta,
            "config": asdict(config),
        },
    }
