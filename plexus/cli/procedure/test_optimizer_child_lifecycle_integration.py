from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tactus.adapters.memory import MemoryStorage
from tactus.core.exceptions import ProcedureWaitingForChildren
from tactus.core.execution_context import BaseExecutionContext
from tactus.primitives.procedure import ProcedurePrimitive

from plexus.cli.procedure.tactus_adapters.external_children import (
    OptimizerExternalChildResolver,
)
from plexus.optimization.portfolio_run import _record_optimizer_child_wait_snapshot


PROCEDURE_PATH = Path(__file__).resolve().parents[2] / "procedures" / "optimization_portfolio_run.yaml"


def _spec(identity: str, score_id: str) -> dict:
    return {
        "identity": identity,
        "account_id": "account",
        "scorecard_id": "card",
        "score_id": score_id,
        "optimizer_yaml_sha256": "a" * 64,
    }


class _Backend:
    def __init__(self):
        self.procedures = {}
        self.tasks = {}

    def add(self, number: int, *, status: str):
        identity = f"launch-{number}"
        procedure_id = f"procedure-{number}"
        task_id = f"task-{number}"
        score_id = f"score-{number}"
        spec = _spec(identity, score_id)
        self.procedures[procedure_id] = {
            "id": procedure_id,
            "accountId": "account",
            "scorecardId": "card",
            "scoreId": score_id,
            "status": status,
            "metadata": {
                "optimizer_launch_spec": spec,
                "code_artifact": {
                    "key": f"procedures/{procedure_id}/code.tac",
                    "_s3_key": f"procedures/{procedure_id}/code.tac",
                    "sha256": "a" * 64,
                },
            },
        }
        self.tasks[task_id] = {
            "id": task_id,
            "accountId": "account",
            "scorecardId": "card",
            "scoreId": score_id,
            "status": status,
            "target": f"procedure/{procedure_id}",
            "command": f"procedure run {procedure_id}",
            "metadata": {
                "procedure_id": procedure_id,
                "optimizer_launch_identity": identity,
                "optimizer_launch_spec": spec,
            },
        }

    def get_procedure(self, procedure_id):
        return self.procedures[procedure_id]

    def get_task(self, task_id):
        return self.tasks[task_id]


def _reference(number: int) -> dict:
    return {
        "id": f"launch-{number}",
        "procedure_id": f"procedure-{number}",
        "task_id": f"task-{number}",
        "scorecard_id": "card",
        "score_id": f"score-{number}",
    }


def _primitive(context):
    return ProcedurePrimitive(context, runtime_factory=lambda _name, _params: None)


def test_yaml_tactus_resolver_and_portfolio_use_one_canonical_identity_across_successive_any_wakes():
    code = yaml.safe_load(PROCEDURE_PATH.read_text())["code"]
    for expression in (
        "id = launch_state.launch_spec.identity",
        "procedure_id = child.procedure_id",
        "task_id = child.task_id",
        "scorecard_id = child.target.scorecard_id",
        "score_id = child.target.score_id",
    ):
        assert expression in code

    backend = _Backend()
    backend.add(1, status="RUNNING")
    backend.add(2, status="RUNNING")
    resolver = OptimizerExternalChildResolver(backend=backend, account_id="account")
    storage = MemoryStorage()
    first_request = {"children": [_reference(1), _reference(2)], "mode": "any"}

    with pytest.raises(ProcedureWaitingForChildren):
        _primitive(BaseExecutionContext("parent", storage, child_wait_resolver=resolver)).await_children(first_request)

    backend.procedures["procedure-1"]["status"] = "FAILED"
    backend.tasks["task-1"]["status"] = "FAILED"
    resumed = BaseExecutionContext("parent", storage, child_wait_resolver=resolver)
    first_wake = _primitive(resumed).await_children(first_request)
    dispatch = {}
    durable_children = [
        {
            "procedure_id": f"procedure-{number}",
            "task_id": f"task-{number}",
            "target": {"scorecard_id": "card", "score_id": f"score-{number}"},
            "launch_state": {"phase": "running", "launch_spec": _spec(f"launch-{number}", f"score-{number}")},
        }
        for number in (1, 2)
    ]
    _record_optimizer_child_wait_snapshot(dispatch, durable_children, first_wake["children"])
    assert [row["id"] for row in dispatch["last_wait_snapshot"]] == ["launch-1", "launch-2"]

    second_request = {"children": [_reference(2)], "mode": "any"}
    with pytest.raises(ProcedureWaitingForChildren):
        _primitive(resumed).await_children(second_request)

    backend.procedures["procedure-2"]["status"] = "FAILED"
    backend.tasks["task-2"]["status"] = "FAILED"
    final = BaseExecutionContext("parent", storage, child_wait_resolver=resolver)
    _primitive(final).await_children(first_request)
    second_wake = _primitive(final).await_children(second_request)
    assert [row["id"] for row in second_wake["children"]] == ["launch-2"]
