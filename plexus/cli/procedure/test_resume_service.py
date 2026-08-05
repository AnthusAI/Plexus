import json
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

from plexus.cli.procedure.resume_service import resume_all_pending, resume_procedure


def _canonical_request():
    return {"mode": "any", "children": [{
        "id": "launch-1",
        "procedure_id": "child-procedure-1",
        "task_id": "child-task-1",
        "scorecard_id": "card-1",
        "score_id": "score-1",
    }]}


def _parent_records(*, procedure_status="WAITING_FOR_CHILDREN", task_status="RUNNING", dispatch_status="DISPATCHED"):
    boundary = {
        "procedure_id": "parent-procedure",
        "parent_task_id": "parent-task",
        "request": _canonical_request(),
        "children": [{"id": "launch-1", "terminal": False}],
    }
    procedure = {
        "id": "parent-procedure",
        "status": procedure_status,
        "accountId": "account-1",
        "metadata": {
            "runtime": {"task_id": "parent-task", "tactus_run_id": "run-1"},
            **({"waiting_for_children": boundary} if procedure_status == "WAITING_FOR_CHILDREN" else {}),
        },
    }
    task = {
        "id": "parent-task",
        "accountId": "account-1",
        "status": task_status,
        "dispatchStatus": dispatch_status,
        "target": "procedure/parent-procedure",
        "command": "procedure run parent-procedure",
        "metadata": {"procedure_id": "parent-procedure"},
    }
    return procedure, task, boundary


def _time_parent_records(*, resume_at="2026-07-31T12:00:00Z"):
    request = {
        "key": "optimization-report-publication",
        "resume_at": resume_at,
        "reason": "retryable_report_publication",
    }
    boundary = {
        "procedure_id": "parent-procedure",
        "parent_task_id": "parent-task",
        "request": request,
    }
    procedure = {
        "id": "parent-procedure", "status": "WAITING_FOR_TIME",
        "accountId": "account-1",
        "metadata": {
            "runtime": {"task_id": "parent-task", "tactus_run_id": "run-1"},
            "waiting_for_time": boundary,
        },
    }
    task = {
        "id": "parent-task", "accountId": "account-1",
        "status": "WAITING_FOR_TIME", "dispatchStatus": "WAITING_FOR_TIME",
        "updatedAt": "2026-07-31T11:59:30.000Z",
        "target": "procedure/parent-procedure", "command": "procedure run parent-procedure",
        "metadata": {
            "procedure_id": "parent-procedure", "dispatch_policy": "resume_once",
            "waiting_for_time": boundary,
        },
    }
    return procedure, task, boundary


class _RecoveryBackend:
    def __init__(self, parent_task, *, child_terminal=True):
        self.parent_task = parent_task
        spec = {
            "identity": "launch-1", "account_id": "account-1",
            "scorecard_id": "card-1", "score_id": "score-1",
            "optimizer_yaml_sha256": "a" * 64,
        }
        status = "FAILED" if child_terminal else "RUNNING"
        self.procedure = {
            "id": "child-procedure-1", "accountId": "account-1",
            "scorecardId": "card-1", "scoreId": "score-1", "status": status,
            "metadata": {"optimizer_launch_spec": spec, "code_artifact": {
                "key": "procedures/child-procedure-1/code.tac",
                "_s3_key": "procedures/child-procedure-1/code.tac", "sha256": "a" * 64,
            }},
        }
        self.child_task = {
            "id": "child-task-1", "accountId": "account-1",
            "scorecardId": "card-1", "scoreId": "score-1", "status": status,
            "target": "procedure/child-procedure-1",
            "command": "procedure run child-procedure-1",
            "metadata": {"procedure_id": "child-procedure-1", "optimizer_launch_identity": "launch-1", "optimizer_launch_spec": spec},
        }

    def get_task(self, task_id):
        return deepcopy(self.parent_task if task_id == "parent-task" else self.child_task)

    def get_procedure(self, procedure_id):
        assert procedure_id == "child-procedure-1"
        return deepcopy(self.procedure)


def test_pending_external_child_checkpoint_loader_accepts_only_exact_replay_position(monkeypatch):
    from plexus.cli.procedure.resume_service import _load_pending_external_child_request

    metadata = SimpleNamespace(
        replay_index=2,
        execution_log=[
            SimpleNamespace(
                position=0, type="other", run_id="run-1", result={"cached": True},
            ),
            SimpleNamespace(
                position=1,
                type="external_children_wait",
                run_id="run-1",
                result={"pending": True, "request": _canonical_request()},
            ),
        ],
    )

    class _Storage:
        def __init__(self, _client, _procedure_id):
            pass

        def load_procedure_metadata(self, _procedure_id):
            return metadata

    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.storage.PlexusStorageAdapter", _Storage,
    )
    assert _load_pending_external_child_request(
        object(), "parent-procedure", expected_run_id="run-1",
    ) == _canonical_request()

    metadata.replay_index = 1
    assert _load_pending_external_child_request(
        object(), "parent-procedure", expected_run_id="run-1",
    ) is None
    metadata.replay_index = 0
    assert _load_pending_external_child_request(
        object(), "parent-procedure", expected_run_id="run-1",
    ) is None
    metadata.replay_index = 2
    metadata.execution_log[1].run_id = "another-run"
    assert _load_pending_external_child_request(
        object(), "parent-procedure", expected_run_id="run-1",
    ) is None


def test_pending_time_checkpoint_loader_uses_actual_tactus_checkpoint_shape(monkeypatch):
    from plexus.cli.procedure.resume_service import _load_pending_time_wait_request

    request = _time_parent_records()[2]["request"]
    metadata = SimpleNamespace(
        replay_index=1,
        execution_log=[SimpleNamespace(
            position=0,
            type="scheduled_continuation",
            run_id="run-1",
            result={"pending": True, "request": request},
        )],
    )

    class _Storage:
        def __init__(self, _client, _procedure_id):
            pass

        def load_procedure_metadata(self, _procedure_id):
            return metadata

    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.storage.PlexusStorageAdapter", _Storage,
    )

    assert _load_pending_time_wait_request(
        object(), "parent-procedure", expected_run_id="run-1",
    ) == request
    metadata.replay_index = 0
    assert _load_pending_time_wait_request(
        object(), "parent-procedure", expected_run_id="run-1",
    ) is None
    metadata.replay_index = 1
    metadata.execution_log[0].type = "external_children_wait"
    assert _load_pending_time_wait_request(
        object(), "parent-procedure", expected_run_id="run-1",
    ) is None


def test_resume_uses_local_task_tracked_execution_to_finalize_state(monkeypatch):
    calls = []

    class _Client:
        def execute(self, query, variables):
            if "query GetProcedure" in query:
                return {
                    "getProcedure": {
                        "id": "procedure-1",
                        "status": "WAITING_FOR_HUMAN",
                        "waitingOnMessageId": "pending-1",
                        "code": "name: validation",
                        "accountId": "account-1",
                    }
                }
            if "query FindResponse" in query:
                return {
                    "listChatMessageByParentMessageId": {
                        "items": [{"id": "response-1", "createdAt": "2026-07-28T00:00:00Z"}]
                    }
                }
            raise AssertionError(f"Unexpected GraphQL operation: {query}")

    class _DirectServiceMustNotRun:
        def __init__(self, _client):
            pass

        async def run_procedure(self, **_kwargs):
            raise AssertionError("resume must use the task-tracked local runner")

    async def _run_tracked(**kwargs):
        calls.append(kwargs)
        return {"success": True, "status": "COMPLETED", "message": "complete"}

    monkeypatch.setattr(
        "plexus.cli.procedure.service.ProcedureService",
        _DirectServiceMustNotRun,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.run_procedure_with_task_tracking",
        _run_tracked,
    )

    client = _Client()
    result = resume_procedure(client, "procedure-1")

    assert result == {
        "resumed": True,
        "status": "COMPLETED",
        "message": "Procedure resumed and executed successfully",
    }
    assert calls == [
        {
            "procedure_id": "procedure-1",
            "client": client,
            "account_id": "account-1",
        }
    ]


def test_waiting_parent_is_rearmed_only_after_any_exact_child_is_terminal(monkeypatch):
    mutations = []
    procedure, task, boundary = _parent_records(
        task_status="WAITING_FOR_CHILDREN", dispatch_status="WAITING_FOR_CHILDREN",
    )
    task["metadata"] = {
        "procedure_id": "parent-procedure", "dispatch_policy": "resume_once",
        "waiting_for_children": boundary,
    }

    class _Client:
        def execute(self, query, variables=None):
            variables = variables or {}
            if "query GetProcedure" in query:
                return {"getProcedure": deepcopy(procedure)}
            if "mutation RearmWaitingParent" in query:
                mutations.append(variables)
                return {"updateTask": {**deepcopy(task), "dispatchStatus": "PENDING"}}
            raise AssertionError(f"Unexpected GraphQL operation: {query}")

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._load_pending_external_child_request",
        lambda _client, _id, **_kwargs: _canonical_request(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._optimizer_backend",
        lambda _client: _RecoveryBackend(task),
    )

    result = resume_procedure(_Client(), "parent-procedure")

    assert result == {
        "resumed": True,
        "status": "PENDING",
        "message": "Procedure resume scheduled after child completion",
    }
    assert mutations[0]["input"]["id"] == "parent-task"
    assert mutations[0]["input"]["dispatchStatus"] == "PENDING"


def test_waiting_parent_stays_suspended_when_no_child_is_terminal(monkeypatch):
    procedure, task, boundary = _parent_records(
        task_status="WAITING_FOR_CHILDREN", dispatch_status="WAITING_FOR_CHILDREN",
    )
    task["metadata"] = {
        "procedure_id": "parent-procedure", "dispatch_policy": "resume_once",
        "waiting_for_children": boundary,
    }

    class _Client:
        def execute(self, query, variables=None):
            if "query GetProcedure" in query:
                return {"getProcedure": deepcopy(procedure)}
            raise AssertionError(f"Unexpected GraphQL operation: {query}")

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._load_pending_external_child_request",
        lambda _client, _id, **_kwargs: _canonical_request(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._optimizer_backend",
        lambda _client: _RecoveryBackend(task, child_terminal=False),
    )

    result = resume_procedure(_Client(), "parent-procedure")

    assert result["resumed"] is False
    assert result["status"] == "WAITING_FOR_CHILDREN"
    assert result["reason"] == "Still waiting for an optimizer child to finish"


def test_time_wait_resumes_at_the_inclusive_utc_due_time(monkeypatch):
    from plexus.cli.procedure.resume_service import _resume_after_time_due

    procedure, task, boundary = _time_parent_records()
    mutations = []

    class _Client:
        def execute(self, query, variables=None):
            variables = variables or {}
            if "mutation RearmWaitingTimeParent" in query:
                mutations.append(variables)
                return {"updateTask": {
                    **deepcopy(task), "status": "PENDING", "dispatchStatus": "PENDING",
                }}
            raise AssertionError(f"Unexpected GraphQL operation: {query}")

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._optimizer_backend",
        lambda _client: SimpleNamespace(get_task=lambda task_id: deepcopy(task)),
    )

    result = _resume_after_time_due(
        _Client(), procedure, checkpoint_request=boundary["request"],
        now=datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc),
    )

    assert result == {
        "resumed": True, "status": "PENDING",
        "message": "Procedure resume scheduled at its due time",
    }
    assert mutations[0]["input"] == {
        "id": "parent-task", "status": "PENDING", "dispatchStatus": "PENDING",
        "workerNodeId": None,
    }


def test_time_wait_claims_the_exact_read_version_after_validating_metadata(monkeypatch):
    from plexus.cli.procedure.resume_service import _resume_after_time_due

    procedure, task, boundary = _time_parent_records()
    procedure_metadata = json.dumps(procedure["metadata"], separators=(",", ":"))
    task_metadata = json.dumps(task["metadata"], separators=(",", ":"))
    procedure["metadata"] = procedure_metadata
    task["metadata"] = task_metadata
    claims = []

    class _Client:
        def execute(self, query, variables=None):
            if "mutation RearmWaitingTimeParent" in query:
                claims.append(deepcopy(variables))
                return {"updateTask": {
                    **deepcopy(task), "status": "PENDING", "dispatchStatus": "PENDING",
                }}
            raise AssertionError(f"Unexpected GraphQL operation: {query}")

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._optimizer_backend",
        lambda _client: SimpleNamespace(get_task=lambda task_id: deepcopy(task)),
    )

    result = _resume_after_time_due(
        _Client(), procedure, checkpoint_request=boundary["request"],
        now=datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc),
    )

    assert result["resumed"] is True
    assert claims[0]["condition"]["and"][2] == {
        "updatedAt": {"eq": task["updatedAt"]},
    }


def test_time_wait_repairs_checkpoint_first_and_procedure_first_crash_windows(monkeypatch):
    from plexus.cli.procedure.resume_service import _resume_after_time_due

    procedure, task, boundary = _time_parent_records()
    procedure["status"] = "RUNNING"
    procedure["metadata"].pop("waiting_for_time")
    task["status"] = "RUNNING"
    task["dispatchStatus"] = "DISPATCHED"
    task["metadata"] = {"procedure_id": "parent-procedure"}
    mutations = []

    class _Client:
        def execute(self, query, variables=None):
            mutations.append((query, deepcopy(variables)))
            if "mutation RepairWaitingTimeProcedure" in query:
                return {"updateProcedure": {
                    **deepcopy(procedure),
                    "status": "WAITING_FOR_TIME",
                    "metadata": variables["input"]["metadata"],
                }}
            if "mutation RepairWaitingTimeTask" in query:
                return {"updateTask": {
                    **deepcopy(task),
                    "status": "WAITING_FOR_TIME",
                    "dispatchStatus": "WAITING_FOR_TIME",
                    "metadata": variables["input"]["metadata"],
                }}
            raise AssertionError(f"Unexpected GraphQL operation: {query}")

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._optimizer_backend",
        lambda _client: SimpleNamespace(get_task=lambda task_id: deepcopy(task)),
    )

    result = _resume_after_time_due(
        _Client(), procedure, checkpoint_request=boundary["request"],
        now=datetime(2026, 7, 31, 11, 59, 59, tzinfo=timezone.utc),
    )

    assert result == {
        "resumed": False,
        "status": "WAITING_FOR_TIME",
        "reason": "Scheduled continuation is not due",
    }
    assert any("RepairWaitingTimeProcedure" in query for query, _ in mutations)
    assert any("RepairWaitingTimeTask" in query for query, _ in mutations)


def test_time_wait_repairs_procedure_first_crash_without_rewriting_procedure(monkeypatch):
    from plexus.cli.procedure.resume_service import _resume_after_time_due

    procedure, task, boundary = _time_parent_records()
    task["status"] = "RUNNING"
    task["dispatchStatus"] = "DISPATCHED"
    task["metadata"] = {"procedure_id": "parent-procedure"}
    mutations = []

    class _Client:
        def execute(self, query, variables=None):
            mutations.append((query, deepcopy(variables)))
            if "mutation RepairWaitingTimeTask" in query:
                return {"updateTask": {
                    **deepcopy(task),
                    "status": "WAITING_FOR_TIME",
                    "dispatchStatus": "WAITING_FOR_TIME",
                    "metadata": variables["input"]["metadata"],
                }}
            raise AssertionError(f"Unexpected GraphQL operation: {query}")

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._optimizer_backend",
        lambda _client: SimpleNamespace(get_task=lambda task_id: deepcopy(task)),
    )

    result = _resume_after_time_due(
        _Client(), procedure, checkpoint_request=boundary["request"],
        now=datetime(2026, 7, 31, 11, 59, 59, tzinfo=timezone.utc),
    )

    assert result == {
        "resumed": False,
        "status": "WAITING_FOR_TIME",
        "reason": "Scheduled continuation is not due",
    }
    assert not any("RepairWaitingTimeProcedure" in query for query, _ in mutations)
    assert [
        query for query, _ in mutations if "RepairWaitingTimeTask" in query
    ]


def test_time_wait_before_due_and_stale_or_cross_run_boundaries_fail_closed(monkeypatch):
    from plexus.cli.procedure.resume_service import _resume_after_time_due

    procedure, task, boundary = _time_parent_records()
    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._optimizer_backend",
        lambda _client: SimpleNamespace(get_task=lambda task_id: deepcopy(task)),
    )

    before_due = _resume_after_time_due(
        object(), procedure, checkpoint_request=boundary["request"],
        now=datetime(2026, 7, 31, 11, 59, 59, tzinfo=timezone.utc),
    )
    assert before_due["resumed"] is False
    assert before_due["reason"] == "Scheduled continuation is not due"

    task["metadata"]["waiting_for_time"] = {
        **deepcopy(boundary),
        "request": {**boundary["request"], "key": "different-run"},
    }
    cross_run = _resume_after_time_due(
        object(), procedure, checkpoint_request=boundary["request"],
        now=datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc),
    )
    assert cross_run["resumed"] is False
    assert "boundary" in cross_run["reason"].lower()

    malformed = _resume_after_time_due(
        object(), procedure,
        checkpoint_request={"key": "x", "resume_at": "not-a-time", "reason": "r"},
        now=datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc),
    )
    assert malformed["resumed"] is False
    assert "checkpoint" in malformed["reason"].lower()


def test_time_wait_duplicate_claim_dispatches_once(monkeypatch):
    from plexus.cli.procedure.resume_service import _resume_after_time_due

    procedure, task, boundary = _time_parent_records()
    claims = []

    class _Client:
        def execute(self, query, variables=None):
            if "mutation RearmWaitingTimeParent" not in query:
                raise AssertionError(f"Unexpected GraphQL operation: {query}")
            claims.append(variables)
            if len(claims) == 1:
                return {"updateTask": {
                    **deepcopy(task), "status": "PENDING", "dispatchStatus": "PENDING",
                }}
            raise RuntimeError("conditional update lost")

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._optimizer_backend",
        lambda _client: SimpleNamespace(get_task=lambda task_id: deepcopy(task)),
    )
    now = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
    first = _resume_after_time_due(_Client(), procedure, checkpoint_request=boundary["request"], now=now)
    second = _resume_after_time_due(_Client(), procedure, checkpoint_request=boundary["request"], now=now)

    assert first["resumed"] is True
    assert second["resumed"] is False
    assert len(claims) == 2


def test_waiting_parent_fails_closed_without_durable_checkpoint_boundary():
    class _Client:
        def execute(self, query, variables=None):
            if "query GetProcedure" in query:
                return {"getProcedure": {
                    "id": "parent-procedure",
                    "status": "WAITING_FOR_CHILDREN",
                    "accountId": "account-1",
                    "metadata": "{}",
                }}
            raise AssertionError("A missing checkpoint must not inspect or release children")

    result = resume_procedure(_Client(), "parent-procedure")

    assert result["resumed"] is False
    assert result["reason"] == "Durable child-wait checkpoint is missing or malformed"


def test_resume_all_includes_child_waits_and_preserves_human_waits(monkeypatch):
    calls = []

    class _Client:
        def execute(self, query, variables=None):
            if "query ListWaitingProcedures" in query:
                status = variables["status"]
                return {"listProcedures": {"items": [{
                    "id": (
                        "human-1" if status == "WAITING_FOR_HUMAN"
                        else "children-1" if status == "WAITING_FOR_CHILDREN"
                        else "running-1"
                    ),
                }]}}
            raise AssertionError(f"Unexpected GraphQL operation: {query}")

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service.resume_procedure",
        lambda _client, procedure_id: (
            calls.append(procedure_id) or {
                "resumed": procedure_id == "children-1",
                "reason": "pending",
            }
        ),
    )

    result = resume_all_pending(_Client())

    assert calls == ["human-1", "children-1", "running-1"]
    assert result == {
        "complete": True,
        "found": 3,
        "resumed": 1,
        "resumed_ids": ["children-1"],
    }


def test_resume_all_exhaustively_scans_later_pages_before_resuming(monkeypatch):
    calls = []
    page_calls = []

    class _Client:
        def execute(self, query, variables=None):
            assert "query ListWaitingProcedures" in query
            variables = variables or {}
            status = variables["status"]
            token = variables.get("nextToken")
            page_calls.append((status, token, variables.get("limit")))
            if status == "WAITING_FOR_CHILDREN":
                if token is None:
                    return {"listProcedures": {
                        "items": [{"id": "waiting-page-1"}],
                        "nextToken": "waiting-page-2",
                    }}
                assert token == "waiting-page-2"
                return {"listProcedures": {
                    "items": [{"id": "waiting-page-2"}],
                    "nextToken": None,
                }}
            if status == "RUNNING":
                if token is None:
                    return {"listProcedures": {
                        "items": [{"id": "running-page-1"}],
                        "nextToken": "running-page-2",
                    }}
                assert token == "running-page-2"
                return {"listProcedures": {
                    "items": [{"id": "running-page-2-checkpoint"}],
                    "nextToken": None,
                }}
            return {"listProcedures": {"items": [], "nextToken": None}}

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service.resume_procedure",
        lambda _client, procedure_id: (
            calls.append(procedure_id) or {
                "resumed": procedure_id == "running-page-2-checkpoint",
                "reason": "pending",
            }
        ),
    )

    result = resume_all_pending(_Client())

    assert result == {
        "complete": True,
        "found": 4,
        "resumed": 1,
        "resumed_ids": ["running-page-2-checkpoint"],
    }
    assert calls == [
        "waiting-page-1",
        "waiting-page-2",
        "running-page-1",
        "running-page-2-checkpoint",
    ]
    assert ("WAITING_FOR_CHILDREN", "waiting-page-2", 1000) in page_calls
    assert ("RUNNING", "running-page-2", 1000) in page_calls


def test_resume_all_repairs_exact_running_checkpoint_found_on_later_page(monkeypatch):
    procedure, task, _boundary = _parent_records(procedure_status="RUNNING")
    operations = []

    class _Client:
        def execute(self, query, variables=None):
            variables = variables or {}
            if "query ListWaitingProcedures" in query:
                if variables["status"] != "RUNNING":
                    return {"listProcedures": {"items": [], "nextToken": None}}
                if variables.get("nextToken") is None:
                    return {"listProcedures": {
                        "items": [], "nextToken": "running-page-2",
                    }}
                assert variables["nextToken"] == "running-page-2"
                return {"listProcedures": {
                    "items": [{"id": "parent-procedure"}], "nextToken": None,
                }}
            if "query GetProcedure" in query:
                return {"getProcedure": deepcopy(procedure)}
            if "mutation RepairWaitingProcedure" in query:
                operations.append("repair_procedure")
                procedure["status"] = "WAITING_FOR_CHILDREN"
                procedure["metadata"] = variables["input"]["metadata"]
                return {"updateProcedure": deepcopy(procedure)}
            if "mutation RepairWaitingParentTask" in query:
                operations.append("repair_task")
                task.update({
                    "status": "WAITING_FOR_CHILDREN",
                    "dispatchStatus": "WAITING_FOR_CHILDREN",
                    "metadata": variables["input"]["metadata"],
                })
                return {"updateTask": deepcopy(task)}
            if "mutation RearmWaitingParent" in query:
                operations.append("rearm")
                task["dispatchStatus"] = "PENDING"
                return {"updateTask": deepcopy(task)}
            raise AssertionError(query)

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._load_pending_external_child_request",
        lambda _client, _id, **_kwargs: _canonical_request(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._optimizer_backend",
        lambda _client: _RecoveryBackend(task),
    )

    result = resume_all_pending(_Client())

    assert result == {
        "complete": True,
        "found": 1,
        "resumed": 1,
        "resumed_ids": ["parent-procedure"],
    }
    assert operations == ["repair_procedure", "repair_task", "rearm"]


def test_resume_all_fails_closed_when_a_later_page_fails(monkeypatch):
    resumed = []

    class _Client:
        def execute(self, query, variables=None):
            variables = variables or {}
            status = variables["status"]
            token = variables.get("nextToken")
            if status == "WAITING_FOR_HUMAN":
                return {"listProcedures": {
                    "items": [{"id": "human-1"}], "nextToken": None,
                }}
            if status == "WAITING_FOR_CHILDREN" and token is None:
                return {"listProcedures": {
                    "items": [{"id": "must-not-rearm"}],
                    "nextToken": "next-page",
                }}
            raise RuntimeError("later page unavailable")

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service.resume_procedure",
        lambda _client, procedure_id: (
            resumed.append(procedure_id) or {"resumed": True}
        ),
    )

    result = resume_all_pending(_Client())

    assert result["complete"] is False
    assert result["resumed"] == 0
    assert result["resumed_ids"] == []
    assert result["failure"]["status"] == "WAITING_FOR_CHILDREN"
    assert result["failure"]["reason"] == "later page unavailable"
    assert resumed == []


def test_resume_all_fails_closed_on_repeated_pagination_token(monkeypatch):
    resumed = []

    class _Client:
        def execute(self, query, variables=None):
            variables = variables or {}
            status = variables["status"]
            if status == "WAITING_FOR_CHILDREN":
                return {"listProcedures": {
                    "items": [{"id": "must-not-rearm"}],
                    "nextToken": "same-token",
                }}
            return {"listProcedures": {"items": [], "nextToken": None}}

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service.resume_procedure",
        lambda _client, procedure_id: (
            resumed.append(procedure_id) or {"resumed": True}
        ),
    )

    result = resume_all_pending(_Client())

    assert result["complete"] is False
    assert result["resumed"] == 0
    assert result["failure"]["status"] == "WAITING_FOR_CHILDREN"
    assert "repeated pagination token" in result["failure"]["reason"]
    assert resumed == []


def test_recovery_repairs_procedure_first_crash_then_rearms_only_after_exact_terminal_child(monkeypatch):
    procedure, task, _boundary = _parent_records()
    operations = []

    class _Client:
        def execute(self, query, variables=None):
            variables = variables or {}
            if "query GetProcedure" in query:
                return {"getProcedure": deepcopy(procedure)}
            if "mutation RepairWaitingParentTask" in query:
                operations.append("repair_task")
                task.update({"status": "WAITING_FOR_CHILDREN", "dispatchStatus": "WAITING_FOR_CHILDREN", "metadata": variables["input"]["metadata"]})
                return {"updateTask": deepcopy(task)}
            if "mutation RearmWaitingParent" in query:
                operations.append("rearm")
                task["dispatchStatus"] = "PENDING"
                return {"updateTask": deepcopy(task)}
            raise AssertionError(query)

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._load_pending_external_child_request",
        lambda _client, _id, **_kwargs: _canonical_request(), raising=False,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._optimizer_backend",
        lambda _client: _RecoveryBackend(task), raising=False,
    )

    result = resume_procedure(_Client(), "parent-procedure")

    assert result["resumed"] is True
    assert operations == ["repair_task", "rearm"]


def test_recovery_repairs_checkpoint_first_crash_before_rearming(monkeypatch):
    procedure, task, _boundary = _parent_records(procedure_status="RUNNING")
    operations = []

    class _Client:
        def execute(self, query, variables=None):
            variables = variables or {}
            if "query GetProcedure" in query:
                return {"getProcedure": deepcopy(procedure)}
            if "mutation RepairWaitingProcedure" in query:
                operations.append("repair_procedure")
                procedure["status"] = "WAITING_FOR_CHILDREN"
                procedure["metadata"] = variables["input"]["metadata"]
                return {"updateProcedure": deepcopy(procedure)}
            if "mutation RepairWaitingParentTask" in query:
                operations.append("repair_task")
                task.update({"status": "WAITING_FOR_CHILDREN", "dispatchStatus": "WAITING_FOR_CHILDREN", "metadata": variables["input"]["metadata"]})
                return {"updateTask": deepcopy(task)}
            if "mutation RearmWaitingParent" in query:
                operations.append("rearm")
                task["dispatchStatus"] = "PENDING"
                return {"updateTask": deepcopy(task)}
            raise AssertionError(query)

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._load_pending_external_child_request",
        lambda _client, _id, **_kwargs: _canonical_request(), raising=False,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._optimizer_backend",
        lambda _client: _RecoveryBackend(task), raising=False,
    )

    result = resume_procedure(_Client(), "parent-procedure")

    assert result["resumed"] is True
    assert operations == ["repair_procedure", "repair_task", "rearm"]


def test_recovery_rejects_nonexclusive_parent_or_changed_wait_boundary(monkeypatch):
    procedure, task, boundary = _parent_records(
        task_status="WAITING_FOR_CHILDREN", dispatch_status="WAITING_FOR_CHILDREN",
    )
    task["metadata"] = {
        "procedure_id": "parent-procedure",
        "dispatch_policy": "resume_once",
        "waiting_for_children": {**boundary, "request": {**_canonical_request(), "mode": "all"}},
    }
    mutations = []

    class _Client:
        def execute(self, query, variables=None):
            if "query GetProcedure" in query:
                return {"getProcedure": deepcopy(procedure)}
            mutations.append(query)
            raise AssertionError("mismatched boundary must not mutate")

    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._load_pending_external_child_request",
        lambda _client, _id, **_kwargs: _canonical_request(), raising=False,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.resume_service._optimizer_backend",
        lambda _client: _RecoveryBackend(task), raising=False,
    )

    result = resume_procedure(_Client(), "parent-procedure")

    assert result["resumed"] is False
    assert "exclusive parent" in result["reason"].lower()
    assert mutations == []
