from plexus.cli.shared.candidate_assessment_bundle import (
    STAGE_DETERMINISTIC,
    STAGE_RANDOM_GATE,
    STAGE_RANDOM_LOOP,
)
from plexus.cli.shared.candidate_assessment_runner import (
    run_candidate_assessment_workflow,
)


def _evaluation(evaluation_id: str, ac1: float, *, sample_size: int):
    return {
        "id": evaluation_id,
        "status": "COMPLETED",
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


def _identity():
    return {
        "scorecard_id": "sc-1039",
        "score_id": "s-45425",
        "baseline_score_version_id": "v-base",
        "candidate_score_version_id": "v-candidate",
    }


def test_runner_executes_stages_in_order_and_returns_bundle():
    calls = []

    def run_stage_pair(*, stage_key, sample_size, days):
        calls.append((stage_key, sample_size, days))
        if stage_key == STAGE_DETERMINISTIC:
            return {
                "baseline": _evaluation("eval-ref-base", 0.58, sample_size=100),
                "candidate": _evaluation("eval-ref-cand", 0.64, sample_size=100),
            }
        if stage_key == STAGE_RANDOM_LOOP:
            return {
                "baseline": _evaluation("eval-loop-base", 0.57, sample_size=50),
                "candidate": _evaluation("eval-loop-cand", 0.56, sample_size=50),
            }
        if stage_key == STAGE_RANDOM_GATE:
            return {
                "baseline": _evaluation("eval-gate-base", 0.56, sample_size=200),
                "candidate": _evaluation("eval-gate-cand", 0.55, sample_size=200),
            }
        raise AssertionError(f"Unexpected stage_key: {stage_key}")

    result = run_candidate_assessment_workflow(
        identity=_identity(),
        run_stage_pair=run_stage_pair,
        deterministic_sample_size=100,
        loop_sample_size=50,
        gate_sample_size=200,
        days=180,
        persist_bundle=False,
    )

    assert [call[0] for call in calls] == [
        STAGE_DETERMINISTIC,
        STAGE_RANDOM_LOOP,
        STAGE_RANDOM_GATE,
    ]
    assert result["bundle"]["stage_runs"][STAGE_RANDOM_GATE]["protocol"]["sample_size"] == 200
    assert result["compact_summary"]["decision"] in {"accept", "reject", "inconclusive"}
    assert result["generalization_metrics"]["random_stage_count"] == 2
    assert result["workflow_decision"]["route_action"] in {
        "score_configuration_optimization",
        "bug_investigation",
        "data_remediation",
        "sme_guideline_clarification",
    }
    assert result["attachment_key"] is None


def test_runner_persists_attachment_when_configured():
    uploaded = {}

    def run_stage_pair(*, stage_key, sample_size, days):
        if stage_key == STAGE_DETERMINISTIC:
            return {
                "baseline": _evaluation("eval-ref-base", 0.58, sample_size=100),
                "candidate": _evaluation("eval-ref-cand", 0.64, sample_size=100),
            }
        if stage_key == STAGE_RANDOM_LOOP:
            return {
                "baseline": _evaluation("eval-loop-base", 0.57, sample_size=50),
                "candidate": _evaluation("eval-loop-cand", 0.56, sample_size=50),
            }
        if stage_key == STAGE_RANDOM_GATE:
            return {
                "baseline": _evaluation("eval-gate-base", 0.56, sample_size=200),
                "candidate": _evaluation("eval-gate-cand", 0.55, sample_size=200),
            }
        raise AssertionError(f"Unexpected stage_key: {stage_key}")

    def fake_uploader(*, key, payload_json):
        uploaded["key"] = key
        uploaded["payload"] = payload_json
        return key

    result = run_candidate_assessment_workflow(
        identity=_identity(),
        run_stage_pair=run_stage_pair,
        task_id="task-123",
        deterministic_sample_size=100,
        loop_sample_size=50,
        gate_sample_size=200,
        days=180,
        persist_bundle=True,
        attachment_uploader=fake_uploader,
    )

    assert uploaded["key"].startswith("candidate-assessments/task-123/")
    assert "\"schema_version\": \"candidate_assessment_bundle.v1\"" in uploaded["payload"]
    assert result["attachment_key"] == uploaded["key"]
    assert result["compact_summary"]["attachment_key"] == uploaded["key"]


def test_runner_requires_task_id_when_persisting():
    def run_stage_pair(*, stage_key, sample_size, days):
        return {
            "baseline": _evaluation(f"{stage_key}-base", 0.58, sample_size=max(sample_size or 1, 1)),
            "candidate": _evaluation(f"{stage_key}-cand", 0.60, sample_size=max(sample_size or 1, 1)),
        }

    try:
        run_candidate_assessment_workflow(
            identity=_identity(),
            run_stage_pair=run_stage_pair,
            persist_bundle=True,
            attachment_uploader=lambda **kwargs: "x",
        )
    except ValueError as exc:
        assert "task_id is required" in str(exc)
        return
    assert False, "Expected ValueError when persist_bundle=True without task_id."
