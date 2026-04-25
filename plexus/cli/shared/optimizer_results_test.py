import json
from types import SimpleNamespace

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
                "exploration_results": [
                    {
                        "index": 2,
                        "version_id": "version-candidate",
                        "fb_eval_id": "eval-fb-candidate",
                        "acc_eval_id": "eval-acc-candidate",
                        "fb_metrics": {"alignment": 0.61, "accuracy": 82.0},
                        "acc_metrics": {"alignment": 0.63, "accuracy": 83.0},
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
        "scorecard": {"name": "Medication Review"},
        "score": {"name": "Prescriber"},
        "metadata": json.dumps(metadata or {}),
    }


def test_build_manifest_extracts_best_versions_and_cycles():
    service = OptimizerResultsService(_FakeClient())
    manifest = service.build_manifest(
        procedure=_sample_procedure(),
        task=_FakeTask(),
        state=_sample_state(),
    )

    assert manifest["procedure"]["id"] == "proc-123"
    assert manifest["baseline"]["version_id"] == "version-baseline"
    assert manifest["best"]["winning_version_id"] == "version-accepted"
    assert manifest["best"]["best_feedback_evaluation_id"] == "eval-fb-best"
    assert manifest["summary"]["completed_cycles"] == 2
    assert manifest["summary"]["stop_reason"] == "max_iterations"
    assert manifest["cycles"][0]["candidates"][0]["version_id"] == "version-candidate"
    assert manifest["cycles"][1]["status"] == "accepted"


def test_index_optimizer_run_persists_manifest_and_pointer(monkeypatch):
    client = _FakeClient()
    service = OptimizerResultsService(client)
    task = _FakeTask()
    uploads = []

    monkeypatch.setattr(service, "_load_procedure_record", lambda _procedure_id: _sample_procedure())
    monkeypatch.setattr(service, "_load_optimizer_state", lambda _procedure: _sample_state())
    monkeypatch.setattr(service, "_find_task_for_procedure", lambda **_kwargs: task)
    monkeypatch.setattr(
        "plexus.cli.shared.optimizer_results.resolve_task_output_attachment_bucket_name",
        lambda: "task-attachments-test",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.optimizer_results.upload_task_attachment_bytes",
        lambda **kwargs: uploads.append(kwargs) or kwargs["key"],
    )

    result = service.index_optimizer_run("proc-123")

    assert result["task_id"] == "task-123"
    assert len(uploads) == 3
    upload_keys = {item["key"] for item in uploads}
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
        score_name="Medication Review: Prescriber",
        scorecard_name="SelectQuote HCS Medium-Risk",
        champion_version_id="version-old",
    )

    assert packet["version_id"] == "version-best"
    assert packet["best_feedback_evaluation_url"].endswith("/eval-fb-best")
    assert packet["best_accuracy_evaluation_url"].endswith("/eval-acc-best")
    assert packet["guidelines_relative_path"] == (
        "scorecards/SelectQuote HCS Medium-Risk/guidelines/Medication Review- Prescriber.md"
    )
    assert packet["is_champion"] is False
