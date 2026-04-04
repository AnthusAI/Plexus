from plexus.cli.shared.workflow_decision_synthesis import (
    ROUTE_BUG_INVESTIGATION,
    ROUTE_DATA_REMEDIATION,
    ROUTE_SCORE_OPTIMIZATION,
    ROUTE_SME_CLARIFICATION,
    synthesize_workflow_decision,
)


def test_reroutes_on_high_severity_mechanical_flag():
    decision = synthesize_workflow_decision(
        policy_decision={"decision": "accept", "reason": "meets_reference_and_generalization_policy"},
        malfunction_context={
            "evaluation_red_flags": [
                {"flag": "mechanical_failures_present", "severity": "high"},
            ],
            "category_shares": {
                "mechanical_malfunction": 0.2,
                "information_gap": 0.1,
                "guideline_gap_requires_sme": 0.1,
                "score_configuration_problem": 0.6,
            },
        },
    )
    assert decision["final_decision"] == "reroute"
    assert decision["route_action"] == ROUTE_BUG_INVESTIGATION


def test_reroutes_on_information_gap_dominance():
    decision = synthesize_workflow_decision(
        policy_decision={"decision": "accept", "reason": "meets_reference_and_generalization_policy"},
        malfunction_context={
            "category_shares": {
                "mechanical_malfunction": 0.1,
                "information_gap": 0.6,
                "guideline_gap_requires_sme": 0.1,
                "score_configuration_problem": 0.2,
            },
        },
    )
    assert decision["final_decision"] == "reroute"
    assert decision["route_action"] == ROUTE_DATA_REMEDIATION


def test_reroutes_on_guideline_gap_threshold():
    decision = synthesize_workflow_decision(
        policy_decision={"decision": "accept", "reason": "meets_reference_and_generalization_policy"},
        malfunction_context={
            "category_shares": {
                "mechanical_malfunction": 0.1,
                "information_gap": 0.1,
                "guideline_gap_requires_sme": 0.4,
                "score_configuration_problem": 0.2,
            },
        },
    )
    assert decision["final_decision"] == "reroute"
    assert decision["route_action"] == ROUTE_SME_CLARIFICATION


def test_keeps_policy_decision_when_score_optimization_route():
    decision = synthesize_workflow_decision(
        policy_decision={"decision": "reject", "reason": "generalization_regression"},
        malfunction_context={
            "category_shares": {
                "mechanical_malfunction": 0.1,
                "information_gap": 0.1,
                "guideline_gap_requires_sme": 0.1,
                "score_configuration_problem": 0.7,
            },
        },
    )
    assert decision["final_decision"] == "reject"
    assert decision["route_action"] == ROUTE_SCORE_OPTIMIZATION
