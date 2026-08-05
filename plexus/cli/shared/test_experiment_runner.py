import json
import signal
import asyncio
from types import SimpleNamespace

import click
import pytest

from plexus.cli.shared.async_cleanup import drain_litellm_service_logging_tasks
from plexus.cli.shared.experiment_runner import _extract_run_parameters_from_procedure_yaml
from plexus.cli.shared.experiment_runner import _merge_task_metadata
from plexus.cli.shared.experiment_runner import create_tracker_and_experiment_task
from plexus.cli.shared.experiment_runner import run_procedure_with_task_tracking


class _FakeTask:
    def __init__(self):
        self.id = "task-123"
        self.accountId = "acct-123"
        self.type = "Procedure Run"
        self.status = "PENDING"
        self.target = "procedure/run/proc-123"
        self.command = "procedure run proc-123"
        self.metadata = json.dumps({"seed": "value"})
        self.currentStageId = "stage-1"
        self.update_calls = []

    def update(self, **kwargs):
        self.update_calls.append(kwargs)
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self

    def get_stages(self):
        return [
            SimpleNamespace(id="stage-1", name="Baseline Evaluation", status="RUNNING"),
            SimpleNamespace(id="stage-2", name="Candidate Evaluation", status="PENDING"),
        ]


class _FakeClient:
    def __init__(self):
        self.procedure_metadata = {"existing": "value", "last_failure": {"message": "stale"}}
        self.procedure_status = None
        self.calls = []

    def execute(self, query, variables):
        self.calls.append((query, variables))
        if "getProcedure(id: $id)" in query and "metadata" in query:
            return {
                "getProcedure": {
                    "id": variables["id"],
                    "metadata": json.dumps(self.procedure_metadata),
                    "waitingOnMessageId": None,
                }
            }
        if "updateProcedure(input: $input)" in query:
            input_data = variables["input"]
            self.procedure_status = input_data.get("status", self.procedure_status)
            if "metadata" in input_data:
                self.procedure_metadata = json.loads(input_data["metadata"])
            return {
                "updateProcedure": {
                    "id": input_data["id"],
                    "status": self.procedure_status,
                    "metadata": json.dumps(self.procedure_metadata),
                    "waitingOnMessageId": None,
                    "updatedAt": "2026-04-20T00:00:00Z",
                }
            }
        raise AssertionError(f"Unexpected GraphQL call: {query}")


def test_task_metadata_merge_reloads_authoritative_concurrent_report_identity(monkeypatch):
    stale_task = _FakeTask()
    stale_task._client = object()
    authoritative_task = SimpleNamespace(
        metadata=json.dumps({
            "seed": "value",
            "optimization_run_key": "run-1",
            "attempt_id": "attempt-1",
        })
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.Task.get_by_id",
        lambda task_id, client: authoritative_task,
    )

    merged = _merge_task_metadata(
        stale_task,
        {"runtime": {"tactus_run_id": "runtime-1"}},
    )

    assert merged == {
        "seed": "value",
        "optimization_run_key": "run-1",
        "attempt_id": "attempt-1",
        "runtime": {"tactus_run_id": "runtime-1"},
    }


def test_task_metadata_merge_fails_closed_when_authoritative_reload_fails(monkeypatch):
    stale_task = _FakeTask()
    stale_task._client = object()
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.Task.get_by_id",
        lambda task_id, client: (_ for _ in ()).throw(RuntimeError("API unavailable")),
    )

    with pytest.raises(
        RuntimeError,
        match="authoritative Task could not be reloaded",
    ):
        _merge_task_metadata(stale_task, {"runtime": {"tactus_run_id": "runtime-1"}})


def test_task_metadata_merge_keeps_local_behavior_for_simple_test_fakes():
    task = _FakeTask()

    assert _merge_task_metadata(task, {"runtime": {"tactus_run_id": "runtime-1"}}) == {
        "seed": "value",
        "runtime": {"tactus_run_id": "runtime-1"},
    }


def _patch_tracker(monkeypatch, fake_task):
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.create_tracker_and_experiment_task",
        lambda **_kwargs: (None, None, fake_task),
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.Task.get_by_id",
        lambda *_args, **_kwargs: fake_task,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.DashboardProcedure.get_by_id",
        lambda **_kwargs: SimpleNamespace(code=None),
    )


def _patch_service(monkeypatch, run_impl):
    class _FakeProcedureService:
        def __init__(self, _client):
            self.client = _client

        async def run_procedure(self, procedure_id, **options):
            return await run_impl(procedure_id, **options)

    monkeypatch.setattr("plexus.cli.procedure.service.ProcedureService", _FakeProcedureService)


def test_drain_litellm_service_logging_tasks_leaves_unrelated_tasks_running():
    class ServiceLogging:
        async def async_service_success_hook(self):
            await asyncio.Event().wait()

    async def unrelated_task():
        await asyncio.Event().wait()

    async def run_test():
        service_hook = asyncio.create_task(ServiceLogging().async_service_success_hook())
        unrelated = asyncio.create_task(unrelated_task())
        try:
            drained = await drain_litellm_service_logging_tasks(timeout_seconds=0)
            assert drained == 1
            assert service_hook.cancelled()
            assert not unrelated.done()
        finally:
            unrelated.cancel()
            await asyncio.gather(unrelated, return_exceptions=True)

    asyncio.run(run_test())


def test_extract_run_parameters_prefers_value_then_default_for_params_mapping():
    yaml_text = """
name: Example
class: Tactus
params:
  scorecard:
    type: string
    default: scorecard-default
  max_samples:
    type: number
    default: 100
    value: 200
  dry_run:
    type: boolean
    default: false
"""
    result = _extract_run_parameters_from_procedure_yaml(yaml_text)
    assert result["scorecard"] == "scorecard-default"
    assert result["max_samples"] == 200
    assert result["dry_run"] is False


def test_extract_run_parameters_supports_parameters_array():
    yaml_text = """
name: Example
parameters:
  - name: days
    type: number
    default: 365
  - name: hint
    type: string
    value: focus on transfer language
"""
    result = _extract_run_parameters_from_procedure_yaml(yaml_text)
    assert result["days"] == 365
    assert result["hint"] == "focus on transfer language"


def test_starting_a_run_preserves_semantic_procedure_identity(monkeypatch):
    fake_task = _FakeTask()
    fake_task.metadata = json.dumps({
        "procedure_type": "Portfolio Optimization",
        "display_title": "Account-wide optimization portfolio",
        "display_scope": "All scorecards",
    })
    procedure = SimpleNamespace(
        code=None,
        metadata={"procedure_type": "Portfolio Optimization"},
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner._find_existing_task_for_procedure",
        lambda *_args, **_kwargs: fake_task.id,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.Task.get_by_id",
        lambda *_args, **_kwargs: fake_task,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.DashboardProcedure.get_by_id",
        lambda *_args, **_kwargs: procedure,
    )

    _, _, task = create_tracker_and_experiment_task(
        client=SimpleNamespace(),
        account_id="acct-123",
        procedure_id="proc-123",
        run_parameters={"max_samples": 10},
        local_dispatch=True,
    )

    metadata = json.loads(task.metadata)
    assert metadata["procedure_type"] == "Portfolio Optimization"
    assert metadata["procedure_action"] == "run"
    assert metadata["display_title"] == "Account-wide optimization portfolio"
    assert metadata["display_scope"] == "All scorecards"


@pytest.mark.asyncio
async def test_run_procedure_persists_failed_result_telemetry(monkeypatch):
    fake_task = _FakeTask()
    fake_client = _FakeClient()
    stage_fail_calls = []

    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._fail_all_task_stages",
        lambda client, task_id, error_message="": stage_fail_calls.append((client, task_id, error_message)),
    )

    async def _run_impl(_procedure_id, **_options):
        return {"success": False, "error": "optimizer blew up"}

    _patch_service(monkeypatch, _run_impl)

    result = await run_procedure_with_task_tracking(
        procedure_id="proc-123",
        client=fake_client,
        account_id="acct-123",
    )

    assert result["status"] == "FAILED"
    assert fake_client.procedure_status == "FAILED"
    assert fake_client.procedure_metadata["runtime"]["command"] == "procedure run proc-123"
    assert "lastHeartbeatAt" in fake_client.procedure_metadata["runtime"]
    assert fake_client.procedure_metadata["last_failure"]["kind"] == "exception"
    assert fake_client.procedure_metadata["last_failure"]["message"] == "optimizer blew up"
    assert fake_client.procedure_metadata["last_failure"]["phase"] == "Baseline Evaluation"
    assert stage_fail_calls == [(fake_client, "task-123", "optimizer blew up")]
    assert fake_task.update_calls[-1]["status"] == "FAILED"
    assert fake_task.update_calls[-1]["errorMessage"] == "optimizer blew up"
    assert json.loads(fake_task.update_calls[-1]["errorDetails"])["kind"] == "exception"
    assert fake_task.update_calls[-1]["dispatchStatus"] == "LOCAL"
    assert fake_task.update_calls[-1]["workerNodeId"] is None
    assert json.loads(fake_task.update_calls[-1]["metadata"])["dispatch_mode"] == "local"


@pytest.mark.asyncio
async def test_run_procedure_launches_background_stale_timeout_scan(monkeypatch):
    fake_task = _FakeTask()
    fake_client = _FakeClient()
    launched_scans = []

    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._fail_all_task_stages",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.persist_task_output_artifact",
        lambda **_kwargs: ("{}", [], "tasks/task-123/output.json"),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout.launch_async_stale_timeout_scan",
        lambda **kwargs: launched_scans.append(kwargs),
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.persist_task_output_artifact",
        lambda **_kwargs: (
            '{"output_compacted": true, "output_attachment": "tasks/task-123/output.json"}',
            ["tasks/task-123/output.json"],
            "tasks/task-123/output.json",
        ),
    )

    async def _run_impl(_procedure_id, **_options):
        return {"success": True, "status": "completed", "message": "ok"}

    _patch_service(monkeypatch, _run_impl)

    result = await run_procedure_with_task_tracking(
        procedure_id="proc-123",
        client=fake_client,
        account_id="acct-123",
    )

    assert result["status"] == "COMPLETED"
    assert launched_scans == [{"account_id": "acct-123", "exclude_procedure_id": "proc-123"}]
    assert fake_task.update_calls[-1]["dispatchStatus"] == "LOCAL"
    assert fake_task.update_calls[-1]["workerNodeId"] is None
    assert json.loads(fake_task.update_calls[-1]["metadata"])["dispatch_mode"] == "local"


@pytest.mark.asyncio
async def test_run_procedure_persists_compacted_task_output_attachment(monkeypatch):
    fake_task = _FakeTask()
    fake_client = _FakeClient()
    persisted_calls = []

    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._fail_all_task_stages",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.persist_task_output_artifact",
        lambda **kwargs: (
            persisted_calls.append(kwargs)
            or ('{"output_compacted": true, "output_attachment": "tasks/task-123/output.json"}',
                ["tasks/task-123/output.json"],
                "tasks/task-123/output.json")
        ),
    )

    async def _run_impl(_procedure_id, **_options):
        return {"success": True, "status": "completed", "message": "ok", "score": "Dosage"}

    _patch_service(monkeypatch, _run_impl)

    result = await run_procedure_with_task_tracking(
        procedure_id="proc-123",
        client=fake_client,
        account_id="acct-123",
    )

    assert result["status"] == "COMPLETED"
    assert persisted_calls == [
        {
            "task_id": "task-123",
            "output_payload": {"success": True, "status": "completed", "message": "ok", "score": "Dosage"},
            "format_type": "json",
            "existing_attached_files": None,
            "status": "completed",
            "client": fake_client,
        }
    ]
    assert fake_task.update_calls[-1]["output"] == '{"output_compacted": true, "output_attachment": "tasks/task-123/output.json"}'
    assert fake_task.update_calls[-1]["attachedFiles"] == ["tasks/task-123/output.json"]
    assert fake_task.update_calls[-1]["dispatchStatus"] == "LOCAL"
    assert fake_task.update_calls[-1]["workerNodeId"] is None
    assert json.loads(fake_task.update_calls[-1]["metadata"])["dispatch_mode"] == "local"


@pytest.mark.asyncio
async def test_terminal_output_persistence_preserves_living_report_attachments_from_stale_task(monkeypatch):
    """A terminal output must append to, not replace, report revisions published mid-run."""
    stale_task = _FakeTask()
    stale_task.attachedFiles = []
    authoritative_task = _FakeTask()
    living_report_attachments = [
        "tasks/task-123/optimization-evidence-r0003.json",
        "tasks/task-123/optimization-workbook-r0003.xlsx",
    ]
    authoritative_task.attachedFiles = list(living_report_attachments)
    fake_client = _FakeClient()
    persisted_calls = []

    _patch_tracker(monkeypatch, stale_task)
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.Task.get_by_id",
        lambda task_id, client: authoritative_task if task_id == stale_task.id else None,
    )

    def _persist(**kwargs):
        persisted_calls.append(kwargs)
        attached_files = list(kwargs["existing_attached_files"] or [])
        output_attachment = "tasks/task-123/output.json"
        if output_attachment not in attached_files:
            attached_files.append(output_attachment)
        return ('{"output_compacted": true, "output_attachment": "tasks/task-123/output.json"}',
                attached_files, output_attachment)

    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.persist_task_output_artifact",
        _persist,
    )

    async def _run_impl(_procedure_id, **_options):
        return {"success": True, "status": "completed", "message": "ok"}

    _patch_service(monkeypatch, _run_impl)

    result = await run_procedure_with_task_tracking(
        procedure_id="proc-123",
        client=fake_client,
        account_id="acct-123",
    )

    assert result["status"] == "COMPLETED"
    assert persisted_calls[0]["existing_attached_files"] == living_report_attachments
    assert stale_task.update_calls[-1]["attachedFiles"] == [
        *living_report_attachments,
        "tasks/task-123/output.json",
    ]


@pytest.mark.asyncio
async def test_run_procedure_persists_durable_external_child_wait(monkeypatch):
    fake_task = _FakeTask()
    fake_client = _FakeClient()
    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.persist_task_output_artifact",
        lambda **_kwargs: (
            '{"output_compacted": true}',
            ["tasks/task-123/output.json"],
            "tasks/task-123/output.json",
        ),
    )

    wait_request = {
        "mode": "any",
        "children": [{
            "id": "child-task-1",
            "task_id": "child-task-1",
            "procedure_id": "child-procedure-1",
        }],
    }

    async def _run_impl(_procedure_id, **_options):
        return {
            "success": False,
            "status": "WAITING_FOR_CHILDREN",
            "request": wait_request,
            "children": [{"id": "child-task-1", "terminal": False}],
        }

    _patch_service(monkeypatch, _run_impl)

    result = await run_procedure_with_task_tracking(
        procedure_id="proc-123",
        client=fake_client,
        account_id="acct-123",
    )

    assert result["status"] == "WAITING_FOR_CHILDREN"
    task_update = fake_task.update_calls[-1]
    assert task_update["status"] == "WAITING_FOR_CHILDREN"
    assert task_update["dispatchStatus"] == "WAITING_FOR_CHILDREN"
    assert task_update["completedAt"] is None
    task_metadata = json.loads(task_update["metadata"])
    assert task_metadata["dispatch_policy"] == "resume_once"
    assert task_metadata["waiting_for_children"] == {
        "procedure_id": "proc-123",
        "parent_task_id": "task-123",
        "request": wait_request,
        "children": [{"id": "child-task-1", "terminal": False}],
    }
    assert fake_client.procedure_status == "WAITING_FOR_CHILDREN"
    assert fake_client.procedure_metadata["waiting_for_children"] == task_metadata["waiting_for_children"]


@pytest.mark.asyncio
async def test_run_procedure_persists_native_time_wait_and_releases_the_worker(monkeypatch):
    fake_task = _FakeTask()
    fake_task.workerNodeId = "worker-1"
    fake_client = _FakeClient()
    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.persist_task_output_artifact",
        lambda **_kwargs: ("{}", [], "tasks/task-123/output.json"),
    )
    request = {
        "key": "optimization-report-publication",
        "resume_at": "2026-07-31T12:00:00Z",
        "reason": "retryable_report_publication",
    }

    async def _run_impl(_procedure_id, **_options):
        return {"success": False, "status": "WAITING_FOR_TIME", "request": request}

    _patch_service(monkeypatch, _run_impl)
    result = await run_procedure_with_task_tracking(
        procedure_id="proc-123", client=fake_client, account_id="acct-123",
    )

    assert result["status"] == "WAITING_FOR_TIME"
    task_update = fake_task.update_calls[-1]
    assert task_update["status"] == "WAITING_FOR_TIME"
    assert task_update["dispatchStatus"] == "WAITING_FOR_TIME"
    assert task_update["workerNodeId"] is None
    assert task_update["completedAt"] is None
    task_metadata = json.loads(task_update["metadata"])
    assert task_metadata["dispatch_policy"] == "resume_once"
    assert task_metadata["waiting_for_time"] == {
        "procedure_id": "proc-123", "parent_task_id": "task-123", "request": request,
    }
    assert fake_client.procedure_status == "WAITING_FOR_TIME"
    assert fake_client.procedure_metadata["waiting_for_time"] == task_metadata["waiting_for_time"]


@pytest.mark.asyncio
async def test_tracked_replay_reuses_the_original_tactus_run_identity(monkeypatch):
    fake_task = _FakeTask()
    fake_task.metadata = json.dumps({
        "procedure_id": "proc-123",
        "runtime": {"tactus_run_id": "stable-run-identity"},
    })
    fake_client = _FakeClient()
    _patch_tracker(monkeypatch, fake_task)
    observed_run_ids = []

    async def _run_impl(_procedure_id, **options):
        observed_run_ids.append(options.get("_tactus_run_id"))
        return {"success": True, "status": "COMPLETED"}

    _patch_service(monkeypatch, _run_impl)
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.persist_task_output_artifact",
        lambda **_kwargs: ("{}", [], "tasks/task-123/output.json"),
    )

    await run_procedure_with_task_tracking(
        procedure_id="proc-123", client=fake_client, account_id="acct-123",
    )

    assert observed_run_ids == ["stable-run-identity"]
    runtime = json.loads(fake_task.update_calls[-1]["metadata"])["runtime"]
    assert runtime["tactus_run_id"] == "stable-run-identity"


@pytest.mark.asyncio
async def test_external_child_wait_persists_procedure_before_parent_task(monkeypatch):
    events = []
    fake_task = _FakeTask()
    original_update = fake_task.update

    def _task_update(**kwargs):
        if kwargs.get("status") == "WAITING_FOR_CHILDREN":
            events.append("task_waiting")
        return original_update(**kwargs)

    fake_task.update = _task_update

    class _OrderedClient(_FakeClient):
        def execute(self, query, variables):
            if "updateProcedure(input: $input)" in query and variables["input"].get("status") == "WAITING_FOR_CHILDREN":
                events.append("procedure_waiting")
            return super().execute(query, variables)

    fake_client = _OrderedClient()
    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.persist_task_output_artifact",
        lambda **_kwargs: ("{}", [], "tasks/task-123/output.json"),
    )

    async def _run_impl(_procedure_id, **_options):
        return {
            "success": False,
            "status": "WAITING_FOR_CHILDREN",
            "request": {"mode": "any", "children": [{
                "id": "launch-1", "procedure_id": "child-procedure-1",
                "task_id": "child-task-1", "scorecard_id": "card", "score_id": "score",
            }]},
            "children": [{"id": "launch-1", "terminal": False}],
        }

    _patch_service(monkeypatch, _run_impl)
    result = await run_procedure_with_task_tracking(
        procedure_id="proc-123", client=fake_client, account_id="acct-123",
    )

    assert result["status"] == "WAITING_FOR_CHILDREN"
    assert events == ["procedure_waiting", "task_waiting"]


@pytest.mark.asyncio
async def test_external_child_wait_procedure_publication_failure_is_fatal(monkeypatch):
    fake_task = _FakeTask()

    class _FailingClient(_FakeClient):
        def execute(self, query, variables):
            if "updateProcedure(input: $input)" in query and variables["input"].get("status") == "WAITING_FOR_CHILDREN":
                raise RuntimeError("procedure write failed")
            return super().execute(query, variables)

    fake_client = _FailingClient()
    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._fail_all_task_stages",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.persist_task_output_artifact",
        lambda **_kwargs: ("{}", [], "tasks/task-123/output.json"),
    )

    async def _run_impl(_procedure_id, **_options):
        return {
            "success": False,
            "status": "WAITING_FOR_CHILDREN",
            "request": {"mode": "any", "children": [{
                "id": "launch-1", "procedure_id": "child-procedure-1",
                "task_id": "child-task-1", "scorecard_id": "card", "score_id": "score",
            }]},
            "children": [{"id": "launch-1", "terminal": False}],
        }

    _patch_service(monkeypatch, _run_impl)
    result = await run_procedure_with_task_tracking(
        procedure_id="proc-123", client=fake_client, account_id="acct-123",
    )

    assert result["status"] == "FAILED"
    assert fake_task.status == "FAILED"


@pytest.mark.asyncio
async def test_completed_replay_clears_external_child_wait_metadata(monkeypatch):
    fake_task = _FakeTask()
    fake_task.metadata = json.dumps({
        "seed": "value",
        "dispatch_policy": "resume_once",
        "waiting_for_children": {"request": {"children": [{"id": "child-task-1"}]}},
    })
    fake_client = _FakeClient()
    fake_client.procedure_metadata["waiting_for_children"] = {
        "request": {"children": [{"id": "child-task-1"}]},
    }
    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.persist_task_output_artifact",
        lambda **_kwargs: ("{}", [], "tasks/task-123/output.json"),
    )

    async def _run_impl(_procedure_id, **_options):
        return {"success": True, "status": "COMPLETED"}

    _patch_service(monkeypatch, _run_impl)

    await run_procedure_with_task_tracking(
        procedure_id="proc-123", client=fake_client, account_id="acct-123",
    )

    task_metadata = json.loads(fake_task.update_calls[-1]["metadata"])
    assert "waiting_for_children" not in task_metadata
    assert "dispatch_policy" not in task_metadata
    assert "waiting_for_children" not in fake_client.procedure_metadata


@pytest.mark.asyncio
async def test_completed_optimizer_child_preserves_held_once_dispatch_policy(monkeypatch):
    fake_task = _FakeTask()
    fake_task.metadata = json.dumps({"dispatch_policy": "held_once"})
    fake_client = _FakeClient()
    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.persist_task_output_artifact",
        lambda **_kwargs: ("{}", [], "tasks/task-123/output.json"),
    )

    async def _run_impl(_procedure_id, **_options):
        return {"success": True, "status": "COMPLETED"}

    _patch_service(monkeypatch, _run_impl)
    await run_procedure_with_task_tracking(
        procedure_id="proc-123", client=fake_client, account_id="acct-123",
    )

    assert json.loads(fake_task.update_calls[-1]["metadata"])["dispatch_policy"] == "held_once"


@pytest.mark.asyncio
async def test_run_procedure_fails_when_required_task_output_artifact_cannot_persist(monkeypatch):
    fake_task = _FakeTask()
    fake_client = _FakeClient()
    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._fail_all_task_stages",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.persist_task_output_artifact",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("ticket rejected")),
    )

    async def _run_impl(_procedure_id, **_options):
        return {"success": True, "status": "completed", "message": "ok"}

    _patch_service(monkeypatch, _run_impl)

    result = await run_procedure_with_task_tracking(
        procedure_id="proc-123", client=fake_client, account_id="acct-123",
    )

    assert result["status"] == "FAILED"
    assert "Required task output artifact" in result["error"]
    assert fake_task.update_calls[-1]["status"] == "FAILED"


@pytest.mark.asyncio
async def test_run_procedure_persists_sigterm_as_cancelled_and_reraises(monkeypatch):
    fake_task = _FakeTask()
    fake_client = _FakeClient()
    stage_cancel_calls = []
    handlers = {}

    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._cancel_all_task_stages",
        lambda client, task_id, status_message="": stage_cancel_calls.append((client, task_id, status_message)),
    )
    monkeypatch.setattr("signal.getsignal", lambda _sig: signal.SIG_DFL)
    monkeypatch.setattr("signal.signal", lambda sig, handler: handlers.setdefault(sig, handler))

    async def _run_impl(_procedure_id, **_options):
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        raise AssertionError("SIGTERM handler should have interrupted execution")

    _patch_service(monkeypatch, _run_impl)

    with pytest.raises(SystemExit) as excinfo:
        await run_procedure_with_task_tracking(
            procedure_id="proc-123",
            client=fake_client,
            account_id="acct-123",
        )

    assert excinfo.value.code == 128 + signal.SIGTERM
    assert fake_client.procedure_status == "CANCELLED"
    assert "last_failure" not in fake_client.procedure_metadata
    assert fake_client.procedure_metadata["last_interruption"]["kind"] == "signal"
    assert fake_client.procedure_metadata["last_interruption"]["signal"] == "SIGTERM"
    assert stage_cancel_calls == [(fake_client, "task-123", "Procedure run interrupted by SIGTERM")]
    assert fake_task.update_calls[-1]["status"] == "CANCELLED"
    assert fake_task.update_calls[-1]["errorMessage"] is None
    assert json.loads(fake_task.update_calls[-1]["errorDetails"])["kind"] == "signal"


@pytest.mark.asyncio
async def test_run_procedure_persists_abort_and_reraises(monkeypatch):
    fake_task = _FakeTask()
    fake_client = _FakeClient()

    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._fail_all_task_stages",
        lambda *_args, **_kwargs: None,
    )

    async def _run_impl(_procedure_id, **_options):
        raise click.Abort()

    _patch_service(monkeypatch, _run_impl)

    with pytest.raises(click.Abort):
        await run_procedure_with_task_tracking(
            procedure_id="proc-123",
            client=fake_client,
            account_id="acct-123",
        )

    assert fake_client.procedure_status == "FAILED"
    assert fake_client.procedure_metadata["last_failure"]["kind"] == "abort"


@pytest.mark.asyncio
async def test_run_procedure_persists_nonzero_system_exit_and_reraises(monkeypatch):
    fake_task = _FakeTask()
    fake_client = _FakeClient()

    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._fail_all_task_stages",
        lambda *_args, **_kwargs: None,
    )

    async def _run_impl(_procedure_id, **_options):
        raise SystemExit(2)

    _patch_service(monkeypatch, _run_impl)

    with pytest.raises(SystemExit) as excinfo:
        await run_procedure_with_task_tracking(
            procedure_id="proc-123",
            client=fake_client,
            account_id="acct-123",
        )

    assert excinfo.value.code == 2
    assert fake_client.procedure_status == "FAILED"
    assert fake_client.procedure_metadata["last_failure"]["kind"] == "system_exit"
    assert fake_client.procedure_metadata["last_failure"]["message"] == "Procedure run exited with status 2"
