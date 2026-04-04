from plexus.cli.shared.candidate_assessment_bundle import (
    STAGE_DETERMINISTIC,
    STAGE_RANDOM_GATE,
    STAGE_RANDOM_LOOP,
    build_candidate_assessment_attachment_key,
    build_candidate_assessment_attachment_payload,
    build_candidate_assessment_compact_summary,
    create_candidate_assessment_bundle,
)


def _evaluation(evaluation_id: str, ac1: float, *, status: str = "COMPLETED", sample_size: int = 50):
    return {
        "id": evaluation_id,
        "status": status,
        "processedItems": sample_size,
        "totalItems": sample_size,
        "metrics": [
            {"name": "Alignment", "value": ac1},
            {"name": "Recall", "value": 0.7},
            {"name": "Precision", "value": 0.8},
        ],
        "parameters": {
            "mode": "feedback",
            "days": 180,
            "max_samples": sample_size,
            "root_cause_required": False,
        },
    }


def _base_stage_runs():
    return {
        STAGE_DETERMINISTIC: {
            "baseline": _evaluation("eval-ref-base", 0.58, sample_size=100),
            "candidate": _evaluation("eval-ref-cand", 0.64, sample_size=100),
            "protocol": {"sample_size": 100, "days": 180, "dataset_id": "ds-abc"},
        },
        STAGE_RANDOM_LOOP: {
            "baseline": _evaluation("eval-rand50-base", 0.57, sample_size=50),
            "candidate": _evaluation("eval-rand50-cand", 0.56, sample_size=50),
            "protocol": {"sample_size": 50, "days": 180},
        },
    }


def _identity():
    return {
        "scorecard_id": "sc-1039",
        "score_id": "s-45425",
        "baseline_score_version_id": "v-base",
        "candidate_score_version_id": "v-candidate",
    }


def test_create_bundle_accept_requires_random_gate():
    stage_runs = _base_stage_runs()
    decision = {"decision": "accept", "reason": "meets_reference_and_generalization_policy"}
    try:
        create_candidate_assessment_bundle(
            identity=_identity(),
            stage_runs=stage_runs,
            decision=decision,
        )
    except ValueError as exc:
        assert "random_gate" in str(exc)
        return
    assert False, "Expected ValueError when accept decision has no random_gate."


def test_create_bundle_accept_with_gate_succeeds():
    stage_runs = _base_stage_runs()
    stage_runs[STAGE_RANDOM_GATE] = {
        "baseline": _evaluation("eval-rand200-base", 0.55, sample_size=200),
        "candidate": _evaluation("eval-rand200-cand", 0.54, sample_size=200),
        "protocol": {"sample_size": 200, "days": 180},
    }
    bundle = create_candidate_assessment_bundle(
        identity=_identity(),
        stage_runs=stage_runs,
        decision={"decision": "accept", "reason": "meets_reference_and_generalization_policy"},
        malfunction_context={
            "category_shares": {"score_configuration_problem": 0.8},
            "evaluation_red_flags": [],
            "primary_next_action": {"action": "score_configuration_optimization"},
        },
        protocol_defaults={"days": 180, "loop_sample_size": 50, "gate_sample_size": 200},
    )
    assert bundle["identity"]["score_id"] == "s-45425"
    assert bundle["stage_runs"][STAGE_RANDOM_GATE]["protocol"]["sample_size"] == 200
    assert bundle["decision"]["decision"] == "accept"


def test_compact_summary_contains_stage_refs_and_attachment():
    stage_runs = _base_stage_runs()
    stage_runs[STAGE_RANDOM_GATE] = {
        "baseline": _evaluation("eval-rand200-base", 0.55, sample_size=200),
        "candidate": _evaluation("eval-rand200-cand", 0.54, sample_size=200),
        "protocol": {"sample_size": 200, "days": 180},
    }
    bundle = create_candidate_assessment_bundle(
        identity=_identity(),
        stage_runs=stage_runs,
        decision={"decision": "reject", "reason": "generalization_regression", "confidence": "high"},
    )
    summary = build_candidate_assessment_compact_summary(
        bundle=bundle,
        attachment_key="candidate-assessments/task-1/v-base__vs__v-candidate.json",
    )
    assert summary["decision"] == "reject"
    assert summary["attachment_key"].endswith(".json")
    assert len(summary["stage_references"]) == 3
    assert summary["stage_references"][0]["stage_key"] == STAGE_DETERMINISTIC
    assert summary["baseline_generalization_gap"] is None


def test_attachment_key_and_payload_are_deterministic():
    key = build_candidate_assessment_attachment_key(
        task_id="task/123",
        baseline_score_version_id="v base",
        candidate_score_version_id="v candidate",
    )
    assert key == "candidate-assessments/task_123/v_base__vs__v_candidate.json"

    bundle = create_candidate_assessment_bundle(
        identity=_identity(),
        stage_runs=_base_stage_runs(),
        decision={"decision": "inconclusive", "reason": "insufficient_evidence"},
    )
    payload = build_candidate_assessment_attachment_payload(bundle)
    assert "\"schema_version\": \"candidate_assessment_bundle.v1\"" in payload
    assert "\"score_id\": \"s-45425\"" in payload
