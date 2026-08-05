"""Outside-in specifications for optimizer external-child resolution."""

from __future__ import annotations

from copy import deepcopy
import pytest


def _launch_spec() -> dict[str, object]:
    spec: dict[str, object] = {
        "version": "optimizer-task-dispatch-v1",
        "account_id": "account-opaque",
        "run_key": "run-opaque",
        "scorecard_id": "scorecard-opaque",
        "score_id": "score-opaque",
        "assessment_fingerprint": "assessment-opaque",
        "limits": {
            "max_cost_usd": 1.0,
            "max_samples": 20,
            "max_iterations": 2,
            "max_concurrency": 1,
        },
        "optimizer_yaml_sha256": "a" * 64,
    }
    spec["identity"] = "launch-identity-opaque"
    return spec


def _records(
    *,
    procedure_status: str = "COMPLETED",
    task_status: str = "COMPLETED",
) -> tuple[dict[str, object], dict[str, object]]:
    spec = _launch_spec()
    procedure = {
        "id": "procedure-opaque",
        "accountId": "account-opaque",
        "scorecardId": "scorecard-opaque",
        "scoreId": "score-opaque",
        "status": procedure_status,
        "metadata": {
            "optimizer_launch_spec": spec,
            "code_artifact": {
                "key": "procedures/procedure-opaque/code.tac",
                "_s3_key": "procedures/procedure-opaque/code.tac",
                "sha256": "a" * 64,
            },
            "optimizer_result": {"manifest": "result-manifest-opaque"},
            "optimizer_artifacts": {
                "schema_version": 1,
                "indexed_at": "2026-07-30T12:00:00Z",
                "task_id": "task-opaque",
                "manifest": "tasks/task-opaque/optimizer/manifest.json",
                "events": "tasks/task-opaque/optimizer/events.jsonl",
                "runtime_log": "tasks/task-opaque/optimizer/runtime.log",
                "artifact_metadata": {
                    "manifest": {
                        "_s3_key": "tasks/task-opaque/optimizer/manifest.json",
                        "size_bytes": 100,
                        "sha256": "b" * 64,
                        "content_type": "application/json",
                    },
                    "events": {
                        "_s3_key": "tasks/task-opaque/optimizer/events.jsonl",
                        "size_bytes": 100,
                        "sha256": "c" * 64,
                        "content_type": "application/x-ndjson",
                    },
                    "runtime_log": {
                        "_s3_key": "tasks/task-opaque/optimizer/runtime.log",
                        "size_bytes": 100,
                        "sha256": "d" * 64,
                        "content_type": "text/plain",
                    },
                },
            },
        },
    }
    task = {
        "id": "task-opaque",
        "accountId": "account-opaque",
        "scorecardId": "scorecard-opaque",
        "scoreId": "score-opaque",
        "status": task_status,
        "target": "procedure/procedure-opaque",
        "command": "procedure run procedure-opaque",
        "metadata": {
            "procedure_id": "procedure-opaque",
            "optimizer_launch_identity": "launch-identity-opaque",
            "optimizer_launch_spec": spec,
        },
    }
    return procedure, task


def _request() -> dict[str, object]:
    return {
        "mode": "all",
        "children": [{
            "id": "launch-identity-opaque",
            "procedure_id": "procedure-opaque",
            "task_id": "task-opaque",
            "scorecard_id": "scorecard-opaque",
            "score_id": "score-opaque",
        }],
    }


class _Backend:
    def __init__(self, procedure: object, task: object) -> None:
        self.procedure = procedure
        self.task = task
        self.calls: list[tuple[str, str]] = []

    def get_procedure(self, procedure_id: str):
        self.calls.append(("procedure", procedure_id))
        return deepcopy(self.procedure)

    def get_task(self, task_id: str):
        self.calls.append(("task", task_id))
        return deepcopy(self.task)


def test_optimizer_child_resolver_reads_only_each_requested_exact_procedure_and_task() -> None:
    from plexus.cli.procedure.tactus_adapters.external_children import (
        OptimizerExternalChildResolver,
    )

    procedure, task = _records()
    backend = _Backend(procedure, task)

    resolved = OptimizerExternalChildResolver(
        backend=backend, account_id="account-opaque",
    )(_request())

    assert backend.calls == [
        ("procedure", "procedure-opaque"),
        ("task", "task-opaque"),
    ]
    assert resolved["complete"] is True
    child = resolved["children"][0]
    assert child["id"] == "launch-identity-opaque"
    assert child["terminal"] is True
    assert child["success"] is True
    assert child["procedure"]["id"] == "procedure-opaque"
    assert child["task"]["id"] == "task-opaque"
    assert child["optimizer_artifacts"]["manifest"] == "tasks/task-opaque/optimizer/manifest.json"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("accountId", "other-account"),
        ("scorecardId", "other-scorecard"),
        ("scoreId", "other-score"),
    ],
)
def test_optimizer_child_resolver_fails_closed_when_exact_records_do_not_match_immutable_child_identity(
    field: str, value: str,
) -> None:
    from plexus.cli.procedure.tactus_adapters.external_children import (
        OptimizerExternalChildResolver,
    )

    procedure, task = _records()
    task[field] = value
    resolved = OptimizerExternalChildResolver(
        backend=_Backend(procedure, task), account_id="account-opaque",
    )(_request())

    child = resolved["children"][0]
    assert child["terminal"] is False
    assert child["success"] is False
    assert child["state"] == "incomplete"
    assert child["reason"] == "child_identity_mismatch"


def test_optimizer_child_resolver_never_reports_success_without_terminal_procedure_task_and_result_evidence() -> None:
    from plexus.cli.procedure.tactus_adapters.external_children import (
        OptimizerExternalChildResolver,
    )

    procedure, task = _records(procedure_status="RUNNING")
    waiting = OptimizerExternalChildResolver(
        backend=_Backend(procedure, task), account_id="account-opaque",
    )(_request())["children"][0]
    assert waiting["terminal"] is False
    assert waiting["success"] is False
    assert waiting["state"] == "running"

    procedure, task = _records()
    procedure["metadata"].pop("optimizer_artifacts")
    incomplete = OptimizerExternalChildResolver(
        backend=_Backend(procedure, task), account_id="account-opaque",
    )(_request())["children"][0]
    assert incomplete["terminal"] is False
    assert incomplete["success"] is False
    assert incomplete["state"] == "incomplete"
    assert incomplete["reason"] == "missing_optimizer_result_evidence"


def test_optimizer_child_resolver_allows_verified_terminal_failure_without_claiming_success() -> None:
    from plexus.cli.procedure.tactus_adapters.external_children import (
        OptimizerExternalChildResolver,
    )

    procedure, task = _records(procedure_status="FAILED", task_status="FAILED")
    procedure["metadata"].pop("optimizer_artifacts")

    child = OptimizerExternalChildResolver(
        backend=_Backend(procedure, task), account_id="account-opaque",
    )(_request())["children"][0]

    assert child["terminal"] is True
    assert child["success"] is False
    assert child["state"] == "failed_or_incomplete"
    assert child["reason"] == "terminal_child_failed"


def test_optimizer_child_resolver_fails_closed_when_procedure_index_points_to_another_task() -> None:
    from plexus.cli.procedure.tactus_adapters.external_children import (
        OptimizerExternalChildResolver,
    )

    procedure, task = _records()
    procedure["metadata"]["optimizer_artifacts"]["task_id"] = "other-task"

    child = OptimizerExternalChildResolver(
        backend=_Backend(procedure, task), account_id="account-opaque",
    )(_request())["children"][0]

    assert child["terminal"] is False
    assert child["success"] is False
    assert child["state"] == "incomplete"
    assert child["reason"] == "missing_optimizer_result_evidence"


def test_optimizer_child_resolver_rejects_missing_or_malformed_persisted_child_references_without_guessing() -> None:
    from plexus.cli.procedure.tactus_adapters.external_children import (
        OptimizerExternalChildResolver,
    )

    procedure, task = _records()
    request = _request()
    request["children"][0].pop("task_id")

    child = OptimizerExternalChildResolver(
        backend=_Backend(procedure, task), account_id="account-opaque",
    )(request)["children"][0]

    assert child == {
        "id": "launch-identity-opaque",
        "terminal": False,
        "success": False,
        "state": "incomplete",
        "reason": "malformed_child_reference",
    }
