from plexus.cli.shared.optimization_acceptance_policy import assess_candidate


def _evaluation(ac1=0.6, recall=0.7, precision=0.7):
    return {
        "metrics": [
            {"name": "Alignment", "value": ac1},
            {"name": "Recall", "value": recall},
            {"name": "Precision", "value": precision},
        ],
        "parameters": {
            "mode": "feedback",
            "days": 180,
            "max_samples": 100,
            "root_cause_required": False,
        },
    }


def test_assess_candidate_accepts_when_reference_improves_and_random_stable():
    result = assess_candidate(
        baseline_reference_eval=_evaluation(ac1=0.60),
        candidate_reference_eval=_evaluation(ac1=0.65),
        baseline_random_eval=_evaluation(ac1=0.58),
        candidate_random_eval=_evaluation(ac1=0.57),
    )
    assert result["decision"] == "accept"


def test_assess_candidate_rejects_when_reference_gain_too_small():
    result = assess_candidate(
        baseline_reference_eval=_evaluation(ac1=0.60),
        candidate_reference_eval=_evaluation(ac1=0.605),
        baseline_random_eval=_evaluation(ac1=0.58),
        candidate_random_eval=_evaluation(ac1=0.58),
    )
    assert result["decision"] == "reject"
    assert result["reason"] == "insufficient_reference_improvement"


def test_assess_candidate_rejects_on_generalization_regression():
    result = assess_candidate(
        baseline_reference_eval=_evaluation(ac1=0.60),
        candidate_reference_eval=_evaluation(ac1=0.64),
        baseline_random_eval=_evaluation(ac1=0.58),
        candidate_random_eval=_evaluation(ac1=0.50),
    )
    assert result["decision"] == "reject"
    assert result["reason"] == "generalization_regression"


def test_assess_candidate_inconclusive_without_required_metrics():
    incomplete = {"metrics": [], "parameters": {"mode": "feedback", "days": 180, "max_samples": 100}}
    result = assess_candidate(
        baseline_reference_eval=incomplete,
        candidate_reference_eval=_evaluation(ac1=0.64),
        baseline_random_eval=_evaluation(ac1=0.58),
        candidate_random_eval=_evaluation(ac1=0.57),
    )
    assert result["decision"] == "inconclusive"
