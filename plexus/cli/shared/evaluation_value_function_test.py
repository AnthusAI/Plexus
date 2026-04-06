from plexus.cli.shared.evaluation_value_function import best_of, value


def _evaluation(ac1=0.6, recall=0.7, precision=0.7, *, mode="feedback", days=180, max_samples=100, root_cause=True):
    params = {
        "mode": mode,
        "days": days,
        "max_samples": max_samples,
        "root_cause_required": True,
    }
    if root_cause:
        params["root_cause"] = {"topics": [{"name": "t1"}]}
    return {
        "metrics": [
            {"name": "Alignment", "value": ac1},
            {"name": "Recall", "value": recall},
            {"name": "Precision", "value": precision},
        ],
        "parameters": params,
    }


def test_value_prefers_ac1_with_guardrails():
    eval_record = _evaluation(ac1=0.65, recall=0.2, precision=0.9, root_cause=True)
    result = value(eval_record)
    assert result["status"] == "ok"
    assert result["value"] < 0.65
    assert "low_recall" in result["reason"]


def test_value_penalizes_missing_root_cause_when_required():
    eval_record = _evaluation(ac1=0.55, recall=0.8, precision=0.8, root_cause=False)
    result = value(eval_record)
    assert result["status"] == "ok"
    assert result["value"] < 0.55
    assert "missing_root_cause" in result["reason"]


def test_best_of_returns_inconclusive_on_protocol_mismatch():
    a = _evaluation(ac1=0.7, days=30)
    b = _evaluation(ac1=0.8, days=180)
    result = best_of(a, b)
    assert result["status"] == "inconclusive"
    assert result["reason"] == "protocol_mismatch"


def test_best_of_selects_higher_value():
    a = _evaluation(ac1=0.6, recall=0.7, precision=0.7)
    b = _evaluation(ac1=0.7, recall=0.7, precision=0.7)
    result = best_of(a, b)
    assert result["status"] == "ok"
    assert result["winner"] == "b"
