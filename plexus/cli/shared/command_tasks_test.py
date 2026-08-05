from types import SimpleNamespace

from plexus.cli.shared import CommandTasks
from plexus.cli.shared.CommandTasks import _should_append_task_id_arg


def test_should_not_append_task_id_to_procedure_run_command():
    assert _should_append_task_id_arg(["procedure", "run", "proc-1"]) is False


def test_should_not_append_task_id_to_programmatic_report_block_command():
    assert (
        _should_append_task_id_arg(
            ["feedback", "report", "run-programmatic-block", "--payload-base64", "abc123"]
        )
        is False
    )


def test_should_append_task_id_to_evaluation_command():
    assert _should_append_task_id_arg(["evaluate", "accuracy", "--scorecard", "Card"]) is True


def test_delayed_worker_message_for_terminal_task_is_skipped_before_command_execution(monkeypatch):
    registered = {}

    class _App:
        conf = SimpleNamespace(task_target_matcher=None)

        def task(self, **_kwargs):
            def _decorator(function):
                registered[function.__name__] = function
                return function
            return _decorator

    terminal_task = SimpleNamespace(
        id="task-123",
        accountId="account-123",
        type="Procedure",
        target="procedure/procedure-1",
        command="procedure run procedure-1",
        status="FAILED",
        dispatchStatus="ERROR",
        update=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("terminal task must not be updated")
        ),
    )
    cli_calls = []
    monkeypatch.setattr(CommandTasks, "create_client", lambda: object())
    monkeypatch.setattr(
        "plexus.dashboard.api.models.task.Task.get_by_id",
        lambda *_args, **_kwargs: terminal_task,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.CommandLineInterface.cli",
        lambda **_kwargs: cli_calls.append(_kwargs),
    )

    CommandTasks.register_tasks(_App())
    celery_task = SimpleNamespace(
        request=SimpleNamespace(id="celery-delayed"),
        update_state=lambda **_kwargs: None,
    )
    result = registered["execute_command"](
        celery_task,
        "procedure run procedure-1",
        task_id="task-123",
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "task_terminal"
    assert cli_calls == []


def test_command_task_fails_and_does_not_complete_when_canonical_output_persistence_fails(monkeypatch):
    registered = {}

    class _App:
        conf = SimpleNamespace(task_target_matcher=None)

        def task(self, **_kwargs):
            def _decorator(function):
                registered[function.__name__] = function
                return function
            return _decorator

    class _DashboardTask:
        id = "task-123"
        accountId = "account-123"
        type = "Command"
        target = "test"
        command = "test"
        attachedFiles = []

        def __init__(self):
            self.update_calls = []
            self.completed = False

        def update(self, **kwargs):
            self.update_calls.append(kwargs)
            for key, value in kwargs.items():
                setattr(self, key, value)

        def get_stages(self):
            return []

        def complete_processing(self):
            self.completed = True

    dashboard_task = _DashboardTask()
    monkeypatch.setattr(CommandTasks, "create_client", lambda: object())
    monkeypatch.setattr(
        "plexus.dashboard.api.models.task.Task.get_by_id",
        lambda *_args, **_kwargs: dashboard_task,
    )
    monkeypatch.setattr(CommandTasks, "CommandOutputManager", lambda **_kwargs: SimpleNamespace(
        get_created_files=lambda: {}, cleanup=lambda: None,
    ))
    monkeypatch.setattr(CommandTasks, "set_output_manager", lambda *_args: None)
    monkeypatch.setattr(CommandTasks, "generate_universal_code_yaml", lambda **_kwargs: "status: completed\n")
    monkeypatch.setattr(
        CommandTasks,
        "persist_task_output_artifact",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("ticket rejected")),
    )
    monkeypatch.setattr("plexus.cli.shared.CommandLineInterface.cli", lambda **_kwargs: None)

    CommandTasks.register_tasks(_App())
    celery_task = SimpleNamespace(request=SimpleNamespace(id="celery-123"), update_state=lambda **_kwargs: None)
    result = registered["execute_command"](celery_task, "test command", task_id="task-123")

    assert result["status"] == "error"
    assert dashboard_task.completed is False
    assert dashboard_task.update_calls[-1]["status"] == "FAILED"
    assert "Required task output artifact" in dashboard_task.update_calls[-1]["errorMessage"]
