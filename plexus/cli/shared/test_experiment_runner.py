import json
import signal
from types import SimpleNamespace

import click
import pytest

from plexus.cli.shared.experiment_runner import _extract_run_parameters_from_procedure_yaml
from plexus.cli.shared.experiment_runner import run_experiment_with_task_tracking


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


def _patch_tracker(monkeypatch, fake_task):
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.create_tracker_and_experiment_task",
        lambda **_kwargs: (None, None, fake_task),
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.DashboardProcedure.get_by_id",
        lambda **_kwargs: SimpleNamespace(code=None),
    )


def _patch_service(monkeypatch, run_impl):
    class _FakeProcedureService:
        def __init__(self, _client):
            self.client = _client

        async def run_experiment(self, procedure_id, **options):
            return await run_impl(procedure_id, **options)

    monkeypatch.setattr("plexus.cli.procedure.service.ProcedureService", _FakeProcedureService)


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


@pytest.mark.asyncio
async def test_run_experiment_persists_failed_result_telemetry(monkeypatch):
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

    result = await run_experiment_with_task_tracking(
        procedure_id="proc-123",
        client=fake_client,
        account_id="acct-123",
    )

    assert result["status"] == "FAILED"
    assert fake_client.procedure_status == "FAILED"
    assert fake_client.procedure_metadata["runtime"]["command"] == "procedure run proc-123"
    assert fake_client.procedure_metadata["last_failure"]["kind"] == "exception"
    assert fake_client.procedure_metadata["last_failure"]["message"] == "optimizer blew up"
    assert fake_client.procedure_metadata["last_failure"]["phase"] == "Baseline Evaluation"
    assert stage_fail_calls == [(fake_client, "task-123", "optimizer blew up")]
    assert fake_task.update_calls[-1]["status"] == "FAILED"
    assert fake_task.update_calls[-1]["errorMessage"] == "optimizer blew up"
    assert json.loads(fake_task.update_calls[-1]["errorDetails"])["kind"] == "exception"


@pytest.mark.asyncio
async def test_run_experiment_persists_sigterm_telemetry_and_reraises(monkeypatch):
    fake_task = _FakeTask()
    fake_client = _FakeClient()
    stage_fail_calls = []
    handlers = {}

    _patch_tracker(monkeypatch, fake_task)
    monkeypatch.setattr(
        "plexus.cli.procedure.procedure_executor._fail_all_task_stages",
        lambda client, task_id, error_message="": stage_fail_calls.append((client, task_id, error_message)),
    )
    monkeypatch.setattr("signal.getsignal", lambda _sig: signal.SIG_DFL)
    monkeypatch.setattr("signal.signal", lambda sig, handler: handlers.setdefault(sig, handler))

    async def _run_impl(_procedure_id, **_options):
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        raise AssertionError("SIGTERM handler should have interrupted execution")

    _patch_service(monkeypatch, _run_impl)

    with pytest.raises(SystemExit) as excinfo:
        await run_experiment_with_task_tracking(
            procedure_id="proc-123",
            client=fake_client,
            account_id="acct-123",
        )

    assert excinfo.value.code == 128 + signal.SIGTERM
    assert fake_client.procedure_status == "FAILED"
    assert fake_client.procedure_metadata["last_failure"]["kind"] == "signal"
    assert fake_client.procedure_metadata["last_failure"]["signal"] == "SIGTERM"
    assert stage_fail_calls == [(fake_client, "task-123", "Procedure run interrupted by SIGTERM")]


@pytest.mark.asyncio
async def test_run_experiment_persists_abort_and_reraises(monkeypatch):
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
        await run_experiment_with_task_tracking(
            procedure_id="proc-123",
            client=fake_client,
            account_id="acct-123",
        )

    assert fake_client.procedure_status == "FAILED"
    assert fake_client.procedure_metadata["last_failure"]["kind"] == "abort"


@pytest.mark.asyncio
async def test_run_experiment_persists_nonzero_system_exit_and_reraises(monkeypatch):
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
        await run_experiment_with_task_tracking(
            procedure_id="proc-123",
            client=fake_client,
            account_id="acct-123",
        )

    assert excinfo.value.code == 2
    assert fake_client.procedure_status == "FAILED"
    assert fake_client.procedure_metadata["last_failure"]["kind"] == "system_exit"
    assert fake_client.procedure_metadata["last_failure"]["message"] == "Procedure run exited with status 2"
