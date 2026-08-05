from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import sys

import pytest

from plexus.cli.shared.CommandProgress import CommandProgress
from plexus.command_worker.executors import PlexusCliExecutor
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


def test_executor_invokes_cli_with_typed_argv_and_reports_progress() -> None:
    observed = {}

    def invoke_cli() -> None:
        observed["argv"] = list(sys.argv)
        observed["task_id"] = os.environ.get("PLEXUS_DISPATCH_TASK_ID")
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
