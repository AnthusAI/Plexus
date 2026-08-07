from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import sys
from types import SimpleNamespace

import pytest

from plexus.cli.shared.CommandProgress import CommandProgress
from plexus.command_worker.executors import PlexusCliExecutor
from plexus.command_worker.executors.plexus_cli import create_executor
from plexus.command_worker.models import CommandEnvelope


@dataclass
class Context:
    progress: list[tuple[float, str | None, dict]] = field(default_factory=list)
    cancellation_checks: int = 0

    def report_progress(self, fraction, message=None, details=None) -> None:
        self.progress.append((fraction, message, details or {}))

    def renew_lease(self):  # pragma: no cover - not called by this executor
        raise AssertionError("unexpected lease renewal")

    @property
    def ownership_lost(self) -> bool:
        return False

    def raise_if_lease_lost(self) -> None:
        return None

    @property
    def cancellation_requested(self) -> bool:
        return False

    def raise_if_cancellation_requested(self) -> None:
        self.cancellation_checks += 1


def envelope(payload) -> CommandEnvelope:
    return CommandEnvelope(
        schema_version=2,
        command_id="command-1",
        tenant_id="tenant-1",
        target="dashboard.command",
        idempotency_key="request-1",
        created_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        payload=payload,
    )


def test_runtime_plugin_factory_creates_the_cli_executor() -> None:
    assert isinstance(create_executor(), PlexusCliExecutor)


def test_executor_invokes_cli_with_typed_argv_and_reports_progress(monkeypatch) -> None:
    monkeypatch.delenv("PLEXUS_ACCOUNT_KEY", raising=False)
    observed = {}

    def invoke_cli() -> None:
        observed["argv"] = list(sys.argv)
        observed["task_id"] = os.environ.get("PLEXUS_DISPATCH_TASK_ID")
        observed["account_id"] = os.environ.get("PLEXUS_ACCOUNT_ID")
        observed["account_key"] = os.environ.get("PLEXUS_ACCOUNT_KEY")
        print("command output")
        CommandProgress.update(2, 4, "running")

    context = Context()
    result = PlexusCliExecutor(invoke_cli).execute(
        envelope({"argv": ["evaluate", "run"], "task_id": "dashboard-task-1"}),
        context,
    )

    assert observed == {
        "argv": ["plexus", "evaluate", "run"],
        "task_id": "dashboard-task-1",
        "account_id": "tenant-1",
        "account_key": None,
    }
    assert result == {
        "argv": ["evaluate", "run"],
        "stdout": "command output\n",
        "stderr": "",
    }
    assert context.progress == [(0.5, "running", {"current": 2, "total": 4})]
    assert context.cancellation_checks == 2


def test_executor_restores_process_bindings_after_cli_failure(monkeypatch) -> None:
    original_argv = list(sys.argv)
    monkeypatch.setenv("PLEXUS_DISPATCH_TASK_ID", "prior-task")
    monkeypatch.setenv("PLEXUS_ACCOUNT_ID", "prior-account-id")
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "prior-account-key")

    def invoke_cli() -> None:
        assert os.environ["PLEXUS_DISPATCH_TASK_ID"] == "dashboard-task-1"
        raise RuntimeError("command failed")

    with pytest.raises(RuntimeError, match="command failed"):
        PlexusCliExecutor(invoke_cli).execute(
            envelope({"argv": ["evaluate"], "task_id": "dashboard-task-1"}),
            Context(),
        )

    assert sys.argv == original_argv
    assert os.environ["PLEXUS_DISPATCH_TASK_ID"] == "prior-task"
    assert os.environ["PLEXUS_ACCOUNT_ID"] == "prior-account-id"
    assert os.environ["PLEXUS_ACCOUNT_KEY"] == "prior-account-key"


def test_executor_binds_each_envelope_account_without_sequential_leakage(
    monkeypatch,
) -> None:
    observed: list[str | None] = []
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "ambient-account")

    def invoke_cli() -> None:
        observed.append(os.environ.get("PLEXUS_ACCOUNT_ID"))
        assert os.environ.get("PLEXUS_ACCOUNT_KEY") == "ambient-account"

    executor = PlexusCliExecutor(invoke_cli)
    executor.execute(envelope({"argv": ["procedure"]}), Context())
    second = CommandEnvelope(
        schema_version=2,
        command_id="command-2",
        tenant_id="tenant-2",
        target="dashboard.command",
        idempotency_key="request-2",
        created_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        payload={"argv": ["procedure"]},
    )
    executor.execute(second, Context())

    assert observed == ["tenant-1", "tenant-2"]
    assert os.environ["PLEXUS_ACCOUNT_KEY"] == "ambient-account"
    assert "PLEXUS_ACCOUNT_ID" not in os.environ


def test_registered_report_cli_resolves_envelope_account_id(monkeypatch) -> None:
    from plexus.cli.report import report_commands
    from plexus.cli.shared import client_utils
    from plexus.reports import service

    monkeypatch.setattr(client_utils, "load_config", lambda: None)
    monkeypatch.setenv("PLEXUS_API_URL", "https://example.test/graphql")
    monkeypatch.setenv("PLEXUS_GRAPHQL_AUTH_MODE", "api_key")
    monkeypatch.setenv("PLEXUS_API_KEY", "test-api-key")
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "ambient-account-key")

    observed: dict[str, str | None] = {}

    def resolve_report_config(identifier, account_id, client):
        observed["identifier"] = identifier
        observed["account_id"] = account_id
        observed["client_account_id"] = client.context.account_id
        observed["account_key"] = client.context.account_key
        return SimpleNamespace(
            id="report-config-1",
            name="Test Report",
            configuration="",
        )

    monkeypatch.setattr(report_commands, "resolve_report_config", resolve_report_config)
    monkeypatch.setattr(
        service,
        "generate_report_with_parameters",
        lambda **_kwargs: ("report-1", None, "task-1"),
    )

    result = PlexusCliExecutor().execute(
        envelope({"argv": ["report", "run", "--config", "report-config-1"]}),
        Context(),
    )

    assert observed == {
        "identifier": "report-config-1",
        "account_id": "tenant-1",
        "client_account_id": "tenant-1",
        "account_key": "ambient-account-key",
    }
    assert "Report generation completed successfully!" in result["stdout"]
    assert os.environ["PLEXUS_ACCOUNT_KEY"] == "ambient-account-key"
    assert "PLEXUS_ACCOUNT_ID" not in os.environ


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"argv": []},
        {"argv": ["evaluate", 1]},
        {"argv": ["evaluate"], "unknown": "value"},
        {"argv": ["evaluate"], "task_id": ""},
    ],
)
def test_executor_rejects_invalid_typed_command_payload(payload) -> None:
    with pytest.raises(ValueError):
        PlexusCliExecutor().execute(envelope(payload), Context())


def test_executor_bounds_result_output() -> None:
    def invoke_cli() -> None:
        print("x" * 70_000)

    result = PlexusCliExecutor(invoke_cli).execute(
        envelope({"argv": ["evaluate"]}), Context()
    )

    assert len(result["stdout"].encode("utf-8")) == 65_536
