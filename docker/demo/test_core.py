from __future__ import annotations

import json
from pathlib import Path

import pytest

from docker.demo.core import (
    AcceptanceMetrics,
    DemoManifest,
    acceptance_outcome,
    assert_cleanup_scope,
    benchmark_rows,
    redact_text,
    render_artifacts,
    stable_resource_id,
    validate_run_id,
)


def _source_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for label, count in (
        ("declined_cash_withdrawal", 100),
        ("cash_withdrawal_charge", 50),
        ("cash_withdrawal_not_recognised", 50),
    ):
        rows.extend(
            {"row_index": index, "text": f"private sample {label} {index}", "label": label}
            for index in range(count)
        )
    return rows


def test_benchmark_selection_is_deterministic_stratified_and_disjoint() -> None:
    first = benchmark_rows(_source_rows())
    second = benchmark_rows(list(reversed(_source_rows())))

    assert first == second
    assert len(first.feedback) == 100
    assert len(first.regression) == 100
    assert {row.resource_key for row in first.feedback}.isdisjoint(
        row.resource_key for row in first.regression
    )
    assert sum(row.expected == "Yes" for row in first.feedback) == 50
    assert sum(row.expected == "No" for row in first.feedback) == 50
    assert sum(row.source_label == "cash_withdrawal_charge" for row in first.feedback) == 25
    assert sum(row.source_label == "cash_withdrawal_not_recognised" for row in first.feedback) == 25


def test_benchmark_requires_the_exact_public_fixture_shape() -> None:
    rows = _source_rows()[:-1]
    with pytest.raises(ValueError, match="cash_withdrawal_not_recognised"):
        benchmark_rows(rows)


def test_run_ids_and_resource_ids_are_bounded_and_stable() -> None:
    run_id = validate_run_id("20260723T123456Z-ab12")
    assert run_id == "20260723T123456Z-ab12"
    assert stable_resource_id(run_id, "score") == stable_resource_id(run_id, "score")
    assert stable_resource_id(run_id, "score").startswith("k8s-demo-")
    assert len(stable_resource_id(run_id, "score")) <= 63

    for invalid in ("", "../../bad", "prod", "20260723T123456Z_secret"):
        with pytest.raises(ValueError):
            validate_run_id(invalid)


def test_redaction_removes_secrets_and_sample_content() -> None:
    text = (
        "OPENAI_API_KEY=sk-test-secret x-api-key: local-key "
        "text=customer transcript should not escape"
    )
    redacted = redact_text(text, secrets=["sk-test-secret", "local-key"])
    assert "sk-test-secret" not in redacted
    assert "local-key" not in redacted
    assert "customer transcript" not in redacted
    assert "[REDACTED" in redacted


def test_strict_and_guardrail_acceptance_rules_are_distinct() -> None:
    improved = AcceptanceMetrics(
        baseline_accuracy=0.75,
        baseline_feedback_ac1=0.70,
        baseline_regression_ac1=0.74,
        candidate_feedback_ac1=0.77,
        candidate_regression_ac1=0.73,
        final_feedback_ac1=0.77,
        evaluation_items=100,
        regression_items=100,
        execution_errors=0,
        candidate_promoted=True,
    )
    assert acceptance_outcome(improved, "strict").passed

    rejected = AcceptanceMetrics(
        baseline_accuracy=0.75,
        baseline_feedback_ac1=0.70,
        baseline_regression_ac1=0.74,
        candidate_feedback_ac1=0.69,
        candidate_regression_ac1=0.70,
        final_feedback_ac1=None,
        evaluation_items=100,
        regression_items=100,
        execution_errors=0,
        candidate_promoted=False,
        candidates_safely_rejected=True,
    )
    assert not acceptance_outcome(rejected, "strict").passed
    assert acceptance_outcome(rejected, "guardrail").passed


def test_artifacts_are_machine_readable_and_privacy_safe(tmp_path: Path) -> None:
    manifest = DemoManifest.new("20260723T123456Z-ab12", "strict", 10.0, 2)
    manifest.record_phase(
        "seed",
        passed=True,
        summary={"items": 200, "dataset_sha256": "abc123"},
    )
    render_artifacts(manifest, tmp_path)

    results = json.loads((tmp_path / "results.json").read_text())
    report = (tmp_path / "report.md").read_text()
    junit = (tmp_path / "junit.xml").read_text()
    assert results["run_id"] == manifest.run_id
    assert results["passed"] is False
    assert "private sample" not in report
    assert "private sample" not in junit
    assert "testsuite" in junit


def test_cleanup_requires_exact_manifest_ownership() -> None:
    run_id = "20260723T123456Z-ab12"
    owned = [stable_resource_id(run_id, "score"), stable_resource_id(run_id, "item-001")]
    assert_cleanup_scope(run_id, owned)
    with pytest.raises(ValueError, match="outside run scope"):
        assert_cleanup_scope(run_id, owned + ["local-demo-score"])
