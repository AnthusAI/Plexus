"""Structured procedure parameters must survive the worker CLI boundary."""

from __future__ import annotations

import sys
import os
from unittest.mock import Mock
from datetime import datetime, timezone

from click.testing import CliRunner

from plexus.cli.procedure import procedures
from plexus.command_worker.executors import PlexusCliExecutor
from plexus.command_worker.models import CommandEnvelope


class Context:
    def report_progress(self, *_args, **_kwargs) -> None: pass
    def raise_if_lease_lost(self) -> None: pass
    def raise_if_cancellation_requested(self) -> None: pass
    @property
    def ownership_lost(self) -> bool: return False
    @property
    def cancellation_requested(self) -> bool: return False


def envelope(payload: dict[str, object]) -> CommandEnvelope:
    return CommandEnvelope(schema_version=2, command_id="command-1", tenant_id="tenant-1", target="dashboard.command", idempotency_key="request-1", created_at=datetime(2026, 8, 5, tzinfo=timezone.utc), payload=payload)


def test_worker_argv_preserves_scalar_array_and_nested_procedure_parameters(monkeypatch) -> None:
    """The same argv emitted by submitCommand reaches procedure ``context`` intact."""
    captured: dict[str, object] = {}
    monkeypatch.setattr(procedures, "create_client", lambda: Mock())
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command", lambda *_: "account-1"
    )

    async def run_with_tracking(**kwargs):
        captured.update(kwargs)
        captured["dispatch_task_id"] = os.environ.get("PLEXUS_DISPATCH_TASK_ID")
        return {"status": "completed", "procedure_id": kwargs["procedure_id"]}

    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.run_procedure_with_task_tracking",
        run_with_tracking,
    )

    argv = [
        "procedure", "run", "procedure-1", "--output", "json",
        "--set", "max_iterations=5",
        "--set", "enabled=true",
        "--set", 'scorecard_ids=["card-1","card-2"]',
        "--set", 'selection={"window":{"days":14},"labels":["new","priority"]}',
    ]

    def invoke_cli() -> None:
        # PlexusCliExecutor supplies the root command; invoke this Click leaf
        # with the arguments the root command dispatches to ``procedure run``.
        result = CliRunner().invoke(procedures.run, sys.argv[3:])
        assert result.exit_code == 0, result.output

    PlexusCliExecutor(invoke_cli).execute(
        envelope({"argv": argv, "task_id": "command-1"}), Context()
    )

    assert captured["procedure_id"] == "procedure-1"
    assert captured["dispatch_task_id"] == "command-1"
    assert captured["context"] == {
        "max_iterations": 5,
        "enabled": True,
        "scorecard_ids": ["card-1", "card-2"],
        "selection": {"window": {"days": 14}, "labels": ["new", "priority"]},
    }
