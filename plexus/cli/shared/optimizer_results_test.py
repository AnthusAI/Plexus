import hashlib
import json
from types import SimpleNamespace

import boto3

from plexus.cli.shared.optimizer_results import (
    OPTIMIZER_ARTIFACTS_METADATA_KEY,
    OptimizerResultsService,
)


class _FakeClient:
    def __init__(self):
        self.update_calls = []

    def execute(self, query, variables):
        if "updateProcedure(input:" in query:
            self.update_calls.append({"query": query, "variables": variables})
            return {"updateProcedure": {"id": variables["input"]["id"], "metadata": variables["input"]["metadata"]}}
        raise AssertionError(f"Unexpected query: {query}")


class _FakeTask:
    def __init__(self, task_id="task-123"):
        self.id = task_id
        self.status = "RUNNING"
        self.target = "procedure/run/proc-123"
        self.command = "plexus procedure run"
        self.attachedFiles = ["tasks/task-123/stdout.txt"]
        self.update_calls = []

    def update(self, **kwargs):
        self.update_calls.append(kwargs)
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self


class _FakeArtifactStore:
    def __init__(self):
        self.uploads = []
        self.downloads = []

    def upload_bytes(self, request, content):
        self.uploads.append((request, content))
        return {
            "_s3_key": f"tasks/{request.resource_id}/{request.filename}",
            "sha256": request.sha256,
            "size_bytes": request.size_bytes,
            "content_type": request.content_type,
        }

    def download_bytes(self, request):
        self.downloads.append(request)
        raise AssertionError("test must configure a downloaded artifact")


def _sample_state():
    return {
        "baseline_version_id": "version-baseline",
        "recent_baseline_id": "eval-fb-baseline",
        "regression_baseline_id": "eval-acc-baseline",
        "current_recent_baseline_id": "eval-fb-current",
        "current_regression_baseline_id": "eval-acc-current",
        "last_accepted_version_id": "version-accepted",
        "last_accepted_fb_eval_id": "eval-fb-best",
        "last_accepted_acc_eval_id": "eval-acc-best",
        "recent_initial_baseline_metrics": {"alignment": 0.51, "accuracy": 76.0},
        "regression_initial_baseline_metrics": {"alignment": 0.49, "accuracy": 74.0},
        "procedure_summary": {"headline": "steady gains"},
        "end_of_run_report": {"run_summary": {"stop_reason": "max_iterations", "cycles": 10}},
        "iterations": [
            {
                "iteration": 1,
                "score_version_id": "version-1",
                "accepted": False,
                "recent_evaluation_id": "eval-fb-1",
                "regression_evaluation_id": "eval-acc-1",
                "recent_metrics": {"alignment": 0.55, "accuracy": 78.0},
                "regression_metrics": {"alignment": 0.57, "accuracy": 79.0},
                "recent_deltas": {"alignment": 0.04},
                "regression_deltas": {"alignment": 0.08},
                "dual_synthesis": {
                    "status": "not_evaluated",
                    "reason": "no_synthesis_version_and_no_successful_hypothesis",
                    "strategy_a": {"status": "no_version"},
                },
                "exploration_results": [
                    {
                        "index": 2,
                        "version_id": "version-candidate",
                        "fb_eval_id": "eval-fb-candidate",
                        "acc_eval_id": "eval-acc-candidate",
                        "fb_metrics": {"alignment": 0.61, "accuracy": 82.0},
                        "acc_metrics": {"alignment": 0.63, "accuracy": 83.0},
                        "slot": "structural",
                        "harmful_repeat_warning": "overlaps strongly harmful cycle 1",
                    }
                ],
            },
            {
                "iteration": 2,
                "score_version_id": "version-accepted",
                "accepted": True,
                "recent_evaluation_id": "eval-fb-best",
                "regression_evaluation_id": "eval-acc-best",
                "recent_metrics": {"alignment": 0.72, "accuracy": 88.0},
                "regression_metrics": {"alignment": 0.74, "accuracy": 89.0},
                "recent_deltas": {"alignment": 0.21},
                "regression_deltas": {"alignment": 0.25},
                "done_reason": "keep",
            },
        ],
    }


def _sample_procedure(metadata=None):
    return {
        "id": "proc-123",
        "name": "Optimizer Run",
        "status": "RUNNING",
        "createdAt": "2026-04-25T10:00:00+00:00",
        "updatedAt": "2026-04-25T11:00:00+00:00",
        "accountId": "acct-1",
        "scorecardId": "scorecard-1",
        "scoreId": "score-1",
        "scoreVersionId": "version-baseline",
        "scorecard": {"name": "Example Scorecard"},
        "score": {"name": "Example Score"},
        "metadata": json.dumps(metadata or {}),
    }


def test_build_manifest_extracts_best_versions_and_cycles():
    service = OptimizerResultsService(_FakeClient())
    state = _sample_state()
    state["end_of_run_report"]["run_summary"]["configured_max_iterations"] = 10
    manifest = service.build_manifest(
        procedure=_sample_procedure(),
        task=_FakeTask(),
        state=state,
    )

    assert manifest["procedure"]["id"] == "proc-123"
    assert manifest["baseline"]["version_id"] == "version-baseline"
    assert manifest["best"]["winning_version_id"] == "version-accepted"
    assert manifest["best"]["best_feedback_evaluation_id"] == "eval-fb-best"
    assert manifest["summary"]["completed_cycles"] == 2
    assert manifest["summary"]["configured_max_iterations"] == 10
    assert manifest["summary"]["stop_reason"] == "max_iterations"
    assert manifest["cycles"][0]["candidates"][0]["version_id"] == "version-candidate"
    assert manifest["cycles"][0]["candidates"][0]["slot"] == "structural"
    assert manifest["cycles"][0]["candidates"][0]["harmful_repeat_warning"] == "overlaps strongly harmful cycle 1"
    assert manifest["cycles"][0]["dual_synthesis"]["status"] == "not_evaluated"
    assert manifest["cycles"][1]["status"] == "accepted"


def test_build_manifest_marks_no_feedback_skip_terminal():
    service = OptimizerResultsService(_FakeClient())
    state = {
        "baseline_version_id": "version-baseline",
        "scorecard_name": "Example Scorecard",
        "score_name": "Information Accuracy: Copay Guarantees",
        "configured_max_iterations": 10,
        "skip_reason": "No qualifying recent feedback is available; skipping optimization.",
        "iterations": [],
    }

    manifest = service.build_manifest(
        procedure=_sample_procedure(),
        task=_FakeTask(),
        state=state,
    )

    assert manifest["summary"]["completed_cycles"] == 0
    assert manifest["summary"]["configured_max_iterations"] == 10
    assert manifest["summary"]["stop_reason"] == "skipped_no_feedback"


def test_build_manifest_uses_final_report_evidence_for_handoff_metrics_and_partial_failures():
    """The compact handoff must not contradict the final report it links to."""
    service = OptimizerResultsService(_FakeClient())
    state = _sample_state()
    state.update(
        {
            "last_accepted_version_id": "stale-selected-version",
            "last_accepted_fb_eval_id": "eval-fb-stale",
            "last_accepted_acc_eval_id": "eval-acc-stale",
            "recent_baseline_feedback_item_ids": ["item-a", "item-b"],
            "frozen_regression_dataset_id": "dataset-frozen",
            "feedback_window_start_at": "2026-04-01T00:00:00Z",
            "feedback_window_end_at": "2026-04-02T00:00:00Z",
            "final_report_phase_statuses": {
                "end_executive_summary": {"status": "succeeded"},
                "end_lab_report": {"status": "failed", "error": "unavailable"},
            },
            "end_of_run_report": {
                "generated_at": "2026-04-25T12:00:00Z",
                "run_summary": {
                    "cycles": 2,
                    "configured_max_iterations": 4,
                    "stop_reason": "max_iterations",
                    "baseline_fb_ac1": 0.51,
                    "baseline_regression_ac1": 0.49,
                    "final_fb_ac1": 0.72,
                    "final_regression_ac1": 0.74,
                    "last_accepted_version_id": "version-final-selected",
                    "champion_version_id": "version-current-leader",
                    "final_recent_evaluation_id": "eval-fb-final",
                    "final_regression_evaluation_id": "eval-acc-final",
                },
            },
        }
    )

    manifest = service.build_manifest(
        procedure=_sample_procedure(),
        task=_FakeTask(),
        state=state,
    )

    assert manifest["best"]["winning_version_id"] == "version-final-selected"
    assert manifest["best"]["best_feedback_evaluation_id"] == "eval-fb-final"
    assert manifest["best"]["best_accuracy_evaluation_id"] == "eval-acc-final"
    assert manifest["best"]["winning_feedback_metrics"]["alignment"] == 0.72
    assert manifest["best"]["winning_accuracy_metrics"]["alignment"] == 0.74
    assert manifest["baseline"]["feedback_metrics"]["alignment"] == 0.51
    assert manifest["baseline"]["accuracy_metrics"]["alignment"] == 0.49
    assert manifest["summary"]["configured_max_iterations"] == 4
    assert manifest["summary"]["terminal_state"] == "PARTIAL_FAILURE"
    assert manifest["summary"]["partial_failures"] == [
        {"phase": "end_lab_report", "error": "unavailable"}
    ]
    assert manifest["evidence"]["source"] == "end_of_run_report"
    assert manifest["evidence"]["selected_candidate"]["version_id"] == "version-final-selected"
    assert manifest["evidence"]["current_leader_version_id"] == "version-current-leader"
    assert manifest["evidence"]["cohorts"]["feedback"]["item_ids"] == ["item-a", "item-b"]
    assert manifest["evidence"]["cohorts"]["regression"]["dataset_id"] == "dataset-frozen"

    compact_handoff = service.summarize_optimizer_run(
        SimpleNamespace(
            procedure=_sample_procedure(),
            manifest=manifest,
            artifact_pointer={"manifest": "tasks/task-123/optimizer/manifest.json"},
            indexed=True,
        )
    )
    assert compact_handoff["terminal_state"] == "PARTIAL_FAILURE"


def test_index_optimizer_run_persists_manifest_and_pointer_without_direct_s3(monkeypatch):
    client = _FakeClient()
    store = _FakeArtifactStore()
    service = OptimizerResultsService(client, artifact_store=store)
    task = _FakeTask()
    monkeypatch.setattr(boto3, "client", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("S3 must not be used")))

    monkeypatch.setattr(service, "_load_procedure_record", lambda _procedure_id: _sample_procedure())
    monkeypatch.setattr(service, "_load_optimizer_state", lambda _procedure: _sample_state())
    monkeypatch.setattr(service, "_find_task_for_procedure", lambda **_kwargs: task)
    result = service.index_optimizer_run("proc-123")

    assert result["task_id"] == "task-123"
    assert len(store.uploads) == 3
    upload_keys = {f"tasks/{request.resource_id}/{request.filename}" for request, _content in store.uploads}
    assert "tasks/task-123/optimizer/manifest.json" in upload_keys
    assert "tasks/task-123/optimizer/events.jsonl" in upload_keys
    assert "tasks/task-123/optimizer/runtime.log" in upload_keys
    assert task.update_calls[-1]["attachedFiles"] == [
        "tasks/task-123/stdout.txt",
        "tasks/task-123/optimizer/manifest.json",
        "tasks/task-123/optimizer/events.jsonl",
        "tasks/task-123/optimizer/runtime.log",
    ]

    saved_metadata = json.loads(client.update_calls[-1]["variables"]["input"]["metadata"])
    pointer = saved_metadata[OPTIMIZER_ARTIFACTS_METADATA_KEY]
    assert pointer["task_id"] == "task-123"
    assert pointer["manifest"] == "tasks/task-123/optimizer/manifest.json"
    assert pointer["artifact_metadata"]["manifest"]["sha256"]


def test_load_indexed_manifest_uses_authorized_artifact_store_without_s3(monkeypatch):
    client = _FakeClient()
    store = _FakeArtifactStore()
    manifest = {"schema_version": 1, "procedure": {"id": "proc-123"}}
    manifest_bytes = json.dumps(manifest).encode("utf-8")

    def _download(request):
        store.downloads.append(request)
        return manifest_bytes

    store.download_bytes = _download
    service = OptimizerResultsService(client, artifact_store=store)
    monkeypatch.setattr(boto3, "client", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("S3 must not be used")))
    pointer = {
        "task_id": "task-123",
        "manifest": "tasks/task-123/optimizer/manifest.json",
        "artifact_metadata": {
            "manifest": {
                "_s3_key": "tasks/task-123/optimizer/manifest.json",
                "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "size_bytes": len(manifest_bytes),
                "content_type": "application/json",
            }
        },
    }

    assert service.load_indexed_manifest_for_procedure(_sample_procedure({OPTIMIZER_ARTIFACTS_METADATA_KEY: pointer})) == manifest
    assert store.downloads[0].resource_type == "TASK"
    assert store.downloads[0].filename == "optimizer/manifest.json"


def test_list_optimizer_candidates_for_score_aggregates_best_visible_metrics(monkeypatch):
    service = OptimizerResultsService(_FakeClient())
    manifest = service.build_manifest(
        procedure=_sample_procedure(),
        task=_FakeTask(),
        state=_sample_state(),
    )
    run = SimpleNamespace(
        procedure=_sample_procedure(),
        manifest=manifest,
        artifact_pointer={"manifest": "tasks/task-123/optimizer/manifest.json"},
        indexed=True,
    )

    monkeypatch.setattr(service, "list_optimizer_runs_for_score", lambda *_args, **_kwargs: [run])
    monkeypatch.setattr(
        service,
        "_list_score_versions",
        lambda *_args, **_kwargs: [
            {
                "id": "version-accepted",
                "isFeatured": True,
                "note": "best run",
                "branch": "optimizer",
                "parentVersionId": "version-baseline",
                "createdAt": "2026-04-25T11:00:00+00:00",
                "updatedAt": "2026-04-25T11:10:00+00:00",
            },
            {
                "id": "version-candidate",
                "isFeatured": False,
                "note": None,
                "branch": None,
                "parentVersionId": None,
                "createdAt": "2026-04-25T10:30:00+00:00",
                "updatedAt": "2026-04-25T10:31:00+00:00",
            },
        ],
    )

    candidates = service.list_optimizer_candidates_for_score("score-1")

    assert candidates[0]["version_id"] == "version-accepted"
    assert candidates[0]["best_feedback_evaluation_id"] == "eval-fb-best"
    assert candidates[0]["best_accuracy_evaluation_id"] == "eval-acc-best"
    assert candidates[0]["pinned"] is True
    assert candidates[1]["version_id"] == "version-candidate"


def test_optimizer_summaries_are_compact_and_url_ready(monkeypatch):
    service = OptimizerResultsService(_FakeClient())
    manifest = service.build_manifest(
        procedure=_sample_procedure(),
        task=_FakeTask(),
        state=_sample_state(),
    )
    run = SimpleNamespace(
        procedure=_sample_procedure(),
        manifest=manifest,
        artifact_pointer={"manifest": "tasks/task-123/optimizer/manifest.json"},
        indexed=True,
    )
    run_summary = service.summarize_optimizer_run(run)

    assert run_summary["procedure_id"] == "proc-123"
    assert run_summary["winning_version_id"] == "version-accepted"
    assert run_summary["best_feedback_evaluation_url"].endswith("/eval-fb-best")
    assert "end_of_run_report" not in run_summary


def test_optimizer_summary_uses_effective_completed_status_for_terminal_running_manifest(monkeypatch):
    service = OptimizerResultsService(_FakeClient())
    manifest = service.build_manifest(
        procedure=_sample_procedure(),
        task=_FakeTask(),
        state=_sample_state(),
    )
    indexed_procedure = _sample_procedure(
        {
            OPTIMIZER_ARTIFACTS_METADATA_KEY: {
                "manifest": "tasks/task-123/optimizer/manifest.json"
            }
        }
    )

    monkeypatch.setattr(service, "_load_procedure_record", lambda _procedure_id: indexed_procedure)
    monkeypatch.setattr(service, "load_indexed_manifest_for_procedure", lambda _procedure: manifest)

    payload = service.summarize_optimizer_procedure("proc-123")

    assert payload["procedure"]["status"] == "RUNNING"
    assert payload["summary"]["stop_reason"] == "max_iterations"
    assert payload["summary"]["effective_status"] == "COMPLETED"

    candidate = {
        "version_id": "version-accepted",
        "runs": ["proc-123"],
        "best_feedback_evaluation_id": "eval-fb-best",
        "best_accuracy_evaluation_id": "eval-acc-best",
        "best_feedback_alignment": 0.72,
        "best_accuracy_alignment": 0.74,
        "best_feedback_metrics": {"accuracy": 88.0},
        "best_accuracy_metrics": {"accuracy": 89.0},
        "pinned": True,
    }
    candidate_summary = service.summarize_optimizer_candidate(candidate)
    assert candidate_summary["best_feedback_evaluation_url"].endswith("/eval-fb-best")
    assert candidate_summary["best_feedback_accuracy"] == 88.0
    assert candidate_summary["pinned"] is True


def test_list_score_evaluations_filters_sorts_and_extracts_metadata():
    class EvaluationClient:
        def execute(self, query, variables):
            assert "listEvaluationByScoreIdAndUpdatedAt" in query
            return {
                "listEvaluationByScoreIdAndUpdatedAt": {
                    "items": [
                        {
                            "id": "eval-low",
                            "type": "feedback",
                            "status": "COMPLETED",
                            "scoreVersionId": "version-1",
                            "updatedAt": "2026-04-25T10:00:00+00:00",
                            "accuracy": 75.0,
                            "cost": 0.4,
                            "processedItems": 10,
                            "totalItems": 10,
                            "parameters": json.dumps({
                                "notes": "baseline",
                                "metadata": {"baseline_evaluation_id": "eval-base"},
                            }),
                            "metrics": json.dumps({"alignment": 0.51, "precision": 0.72, "recall": 0.81}),
                        },
                        {
                            "id": "eval-high",
                            "type": "accuracy",
                            "status": "COMPLETED",
                            "scoreVersionId": "version-2",
                            "updatedAt": "2026-04-25T11:00:00+00:00",
                            "accuracy": 91.0,
                            "cost": 0.2,
                            "processedItems": 12,
                            "totalItems": 12,
                            "parameters": json.dumps({
                                "notes": "candidate",
                                "metadata": {"current_baseline_evaluation_id": "eval-current"},
                            }),
                            "metrics": json.dumps({"alignment": 0.83, "precision": 0.91, "recall": 0.62}),
                        },
                        {
                            "id": "eval-missing-cost",
                            "type": "feedback",
                            "status": "COMPLETED",
                            "scoreVersionId": "version-3",
                            "updatedAt": "2026-04-25T12:00:00+00:00",
                            "accuracy": 82.0,
                            "cost": None,
                            "processedItems": 14,
                            "totalItems": 14,
                            "parameters": json.dumps({"notes": "missing cost"}),
                            "metrics": json.dumps({"alignment": 0.70, "recall": 0.93}),
                        },
                    ],
                    "nextToken": None,
                }
            }

    service = OptimizerResultsService(EvaluationClient())
    rows = service.list_score_evaluations("score-1", sort_by="alignment")

    assert [row["evaluation_id"] for row in rows] == ["eval-high", "eval-missing-cost", "eval-low"]
    assert rows[0]["evaluation_url"].endswith("/eval-high")
    assert rows[0]["notes"] == "candidate"
    assert rows[0]["current_baseline_evaluation_id"] == "eval-current"
    assert rows[0]["precision"] == 0.91
    assert rows[0]["recall"] == 0.62
    assert rows[0]["cost"] == 0.2

    by_precision = service.list_score_evaluations("score-1", sort_by="precision")
    assert [row["evaluation_id"] for row in by_precision] == ["eval-high", "eval-low", "eval-missing-cost"]

    by_recall = service.list_score_evaluations("score-1", sort_by="recall")
    assert [row["evaluation_id"] for row in by_recall] == ["eval-missing-cost", "eval-low", "eval-high"]

    by_cost = service.list_score_evaluations("score-1", sort_by="cost")
    assert [row["evaluation_id"] for row in by_cost] == ["eval-high", "eval-low", "eval-missing-cost"]

    filtered = service.list_score_evaluations("score-1", version_id="version-1")
    assert [row["evaluation_id"] for row in filtered] == ["eval-low"]


def test_build_optimizer_review_packet_counts_unindexed_runs(monkeypatch):
    service = OptimizerResultsService(_FakeClient())
    indexed_run = SimpleNamespace(
        procedure=_sample_procedure(),
        manifest=service.build_manifest(procedure=_sample_procedure(), task=_FakeTask(), state=_sample_state()),
        artifact_pointer={"manifest": "tasks/task-123/optimizer/manifest.json"},
        indexed=True,
    )
    unindexed_run = SimpleNamespace(
        procedure={**_sample_procedure(), "id": "proc-unindexed"},
        manifest=None,
        artifact_pointer=None,
        indexed=False,
    )
    monkeypatch.setattr(service, "list_optimizer_runs_for_score", lambda *_args, **_kwargs: [indexed_run, unindexed_run])
    monkeypatch.setattr(
        service,
        "list_optimizer_candidates_for_score",
        lambda *_args, **_kwargs: [
            {
                "version_id": "version-best",
                "runs": ["proc-123"],
                "best_feedback_evaluation_id": "eval-fb-best",
                "best_accuracy_evaluation_id": "eval-acc-best",
                "best_feedback_alignment": 0.91,
                "best_accuracy_alignment": 0.89,
                "best_feedback_metrics": {"accuracy": 95.0},
                "best_accuracy_metrics": {"accuracy": 94.0},
                "pinned": True,
            }
        ],
    )

    packet = service.build_optimizer_review_packet_for_score(
        "score-1",
        score_name="Example Score",
        scorecard_name="Example Scorecard",
        champion_version_id="version-old",
    )

    assert packet["unindexed_run_count"] == 1
    assert packet["best_candidate"]["version_id"] == "version-best"
    assert packet["promotion_packet"]["best_feedback_evaluation_url"].endswith("/eval-fb-best")
    assert "promote manually" in packet["promotion_recommendation"]


def test_summarize_optimizer_procedure_requires_index_and_returns_cycles(monkeypatch):
    service = OptimizerResultsService(_FakeClient())
    manifest = service.build_manifest(
        procedure=_sample_procedure({"optimizer_artifacts": {"manifest": "tasks/task-123/optimizer/manifest.json"}}),
        task=_FakeTask(),
        state=_sample_state(),
    )
    monkeypatch.setattr(
        service,
        "_load_procedure_record",
        lambda _procedure_id: _sample_procedure({"optimizer_artifacts": {"manifest": "tasks/task-123/optimizer/manifest.json"}}),
    )
    monkeypatch.setattr(service, "load_indexed_manifest_for_procedure", lambda _procedure: manifest)

    payload = service.summarize_optimizer_procedure("proc-123")

    assert payload["procedure_id"] == "proc-123"
    assert payload["best"]["best_feedback_evaluation_url"].endswith("/eval-fb-best")
    assert payload["cycles"][0]["feedback_evaluation_url"].endswith("/eval-fb-1")


def test_build_promotion_packet_uses_best_candidate_and_guideline_paths(monkeypatch, tmp_path):
    service = OptimizerResultsService(_FakeClient())
    monkeypatch.setenv("SCORECARD_CACHE_DIR", str(tmp_path / "scorecards"))

    monkeypatch.setattr(
        service,
        "list_optimizer_candidates_for_score",
        lambda *_args, **_kwargs: [
            {
                "version_id": "version-best",
                "best_feedback_evaluation_id": "eval-fb-best",
                "best_accuracy_evaluation_id": "eval-acc-best",
                "best_feedback_alignment": 0.91,
                "best_accuracy_alignment": 0.89,
                "pinned": True,
                "note": "send to client",
                "branch": "optimizer",
                "runs": ["proc-123"],
            }
        ],
    )

    packet = service.build_promotion_packet_for_score(
        "score-1",
        score_name="Example Score",
        scorecard_name="Example Scorecard",
        champion_version_id="version-old",
    )

    assert packet["version_id"] == "version-best"
    assert packet["best_feedback_evaluation_url"].endswith("/eval-fb-best")
    assert packet["best_accuracy_evaluation_url"].endswith("/eval-acc-best")
    assert packet["guidelines_relative_path"] == (
        "scorecards/Example Scorecard/guidelines/Example Score.md"
    )
    assert packet["is_champion"] is False
