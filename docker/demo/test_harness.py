from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from docker.demo.core import DemoManifest, PHASES
from docker.demo.harness import (
    CommandRunner,
    completed_optimizer_identity,
    curated_dataset_identity,
    evaluation_accuracy_fraction,
    extract_last_json,
    initial_score_configuration,
    load_banking77_rows,
    metric_value,
    optimizer_cli_command,
    persisted_report_summary,
    safe_report_summary,
)
from docker.demo.runner import parser, require_external_output_dir, resolve_existing_command


class _Response:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.payload


def test_source_loader_enforces_checksum_and_keeps_text_in_memory_only(monkeypatch) -> None:
    payload = (
        b'category,text\n'
        b'declined_cash_withdrawal,"sample one"\n'
        b'cash_withdrawal_charge,"sample two"\n'
    )
    monkeypatch.setattr("docker.demo.harness.SOURCE_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: _Response(payload))
    rows = load_banking77_rows()
    assert rows == [
        {"row_index": 0, "text": "sample one", "label": "declined_cash_withdrawal"},
        {"row_index": 1, "text": "sample two", "label": "cash_withdrawal_charge"},
    ]

    monkeypatch.setattr("docker.demo.harness.SOURCE_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        load_banking77_rows()


def test_json_extraction_handles_rich_prefixes_and_pretty_payloads() -> None:
    output = "log line\n\x1b[32mready\x1b[0m\n{\n  \"result\": {\"success\": true}\n}\n"
    assert extract_last_json(output) == {"result": {"success": True}}


def test_optimizer_resume_requires_one_completed_run_scoped_procedure() -> None:
    ids = {"scorecard": "scorecard-1", "score": "score-1"}
    summary = {
        "procedure_id": "procedure-1",
        "procedure": {
            "id": "procedure-1",
            "scorecard_id": "scorecard-1",
            "score_id": "score-1",
            "task_id": "task-1",
        },
        "summary": {"effective_status": "COMPLETED"},
    }
    assert completed_optimizer_identity(summary, ids, "procedure-1") == "task-1"

    summary["summary"]["effective_status"] = "RUNNING"
    with pytest.raises(RuntimeError, match="refused to retry incomplete procedure"):
        completed_optimizer_identity(summary, ids, "procedure-1")

    summary["summary"]["effective_status"] = "COMPLETED"
    summary["procedure"]["score_id"] = "foreign-score"
    with pytest.raises(RuntimeError, match="run-scoped score"):
        completed_optimizer_identity(summary, ids, "procedure-1")


def test_curated_dataset_contract_requires_the_cli_row_count() -> None:
    assert curated_dataset_identity({"dataset_id": "dataset-1", "row_count": 100}) == "dataset-1"
    with pytest.raises(RuntimeError, match="exactly 100 rows"):
        curated_dataset_identity({"dataset_id": "dataset-1", "rows_written": 100})


def test_metric_reader_supports_persisted_metric_shapes() -> None:
    assert metric_value('[{"name":"Alignment","value":0.75}]', "Alignment") == 0.75
    assert metric_value({"alignment": 0.8}, "Alignment") == 0.8


def test_evaluation_accuracy_is_converted_from_persisted_percent_to_fraction() -> None:
    assert evaluation_accuracy_fraction(80.0) == 0.8
    with pytest.raises(RuntimeError, match="outside 0..100"):
        evaluation_accuracy_fraction(101)


def test_initial_score_uses_only_the_required_model_and_is_intentionally_incomplete() -> None:
    configuration = initial_score_configuration("score-id", "score-key")
    assert 'default_model "openai/gpt-5.4-nano"' in configuration
    assert "gpt-4o" not in configuration
    assert "unrecognized-withdrawal boundary" in configuration


def test_report_summary_returns_only_safe_identity_fields() -> None:
    payload = {
        "scorecardId": "scorecard-1",
        "scoreId": "score-1",
        "id": "report-1",
        "output": {"text": "private sample", "evidence": "private quote"},
    }
    assert safe_report_summary(payload, "scorecard-1", "score-1") == {
        "referenced_run_scope": True,
        "record_ids": ["report-1"],
    }


def test_persisted_report_summary_verifies_run_scope_without_report_body() -> None:
    reports = [
        {
            "id": "report-1",
            "name": "Demo Feedback Overview",
            "parameters": {"scorecard": "scorecard-1", "score": "score-1"},
            "output": {"text": "must not be inspected"},
        }
    ]
    assert persisted_report_summary(
        reports, "scorecard-1", "score-1", name_contains="Feedback Overview"
    ) == {"referenced_run_scope": True, "record_ids": ["report-1"]}
    with pytest.raises(RuntimeError, match="persisted report"):
        persisted_report_summary(reports, "scorecard-1", "another-score")


def test_command_log_records_status_but_not_stdout_or_secret(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    runner = CommandRunner(log, secrets=("secret-value",))
    runner.run((sys.executable, "-c", "print(''.join(map(chr,[115,97,109,112,108,101,32,116,101,120,116])))"))
    event = json.loads(log.read_text())
    assert event["returncode"] == 0
    assert "sample text" not in log.read_text()
    assert "secret-value" not in log.read_text()


def test_command_timeout_is_recorded_without_partial_output(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    runner = CommandRunner(log)
    with pytest.raises(RuntimeError, match="timed out"):
        runner.run(
            (
                sys.executable,
                "-c",
                "import time; print(''.join(map(chr,[112,114,105,118,97,116,101,32,115,97,109,112,108,101]))); time.sleep(1)",
            ),
            timeout=0.01,
        )
    event = json.loads(log.read_text())
    assert event["timed_out"] is True
    assert "private sample" not in log.read_text()


def test_existing_run_resumes_until_every_phase_passes_then_verifies() -> None:
    manifest = DemoManifest.new("20260723T123456Z-ab12", "strict", 10.0, 2)
    assert resolve_existing_command("run", manifest) == "resume"
    for phase in PHASES:
        manifest.record_phase(phase, passed=True, summary={})
    assert resolve_existing_command("run", manifest) == "verify"
    assert resolve_existing_command("resume", manifest) == "resume"


def test_artifact_directory_must_be_outside_the_repository(tmp_path: Path) -> None:
    assert require_external_output_dir(tmp_path) == tmp_path.resolve()
    repository_root = Path(__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="outside the repository"):
        require_external_output_dir(repository_root / "artifacts")


def test_optimizer_reuses_verified_paired_baselines_and_required_nano_agents() -> None:
    manifest = DemoManifest.new("20260723T123456Z-ab12", "strict", 10.0, 2)
    manifest.metadata.update(
        {
            "feedback_evaluation_id": "feedback-eval",
            "regression_evaluation_id": "regression-eval",
        }
    )
    command = optimizer_cli_command(
        manifest, {"scorecard": "scorecard-1", "score": "score-1"}
    )
    assert command[command.index("--resume-recent-eval") + 1] == "feedback-eval"
    assert command[command.index("--resume-regression-eval") + 1] == "regression-eval"
    # The optimizer adds one protected structural lane to the normal rubric
    # lanes, so requesting one normal lane yields two candidates.
    assert command[command.index("--num-candidates") + 1] == "1"
    agent_models = [command[index + 1] for index, item in enumerate(command) if item == "--agent-model"]
    assert agent_models
    assert all(model.endswith("=gpt-5.4-nano") for model in agent_models)


def test_resume_and_verify_require_an_explicit_run_id() -> None:
    for command in ("resume", "verify"):
        with pytest.raises(SystemExit):
            parser().parse_args([command])
