import json
from types import SimpleNamespace

from plexus.cli.shared.CommandDispatch import (
    _build_local_run_args,
    _claim_task_for_dispatch,
    _list_pending_tasks_for_account,
)


class _StubClient:
    def __init__(self, items):
        self._items = items

    def execute(self, _query, _variables):
        return {
            "listTaskByAccountIdAndUpdatedAt": {
                "items": self._items,
                "nextToken": None,
            }
        }


def test_list_pending_tasks_skips_self_managed_dispatch_modes():
    client = _StubClient([
        {
            "id": "task-console",
            "dispatchStatus": "PENDING",
            "status": "PENDING",
            "createdAt": "2026-03-30T10:00:01Z",
            "metadata": json.dumps({"dispatch_mode": "console_async_worker"}),
        },
        {
            "id": "task-local",
            "dispatchStatus": "PENDING",
            "status": "PENDING",
            "createdAt": "2026-03-30T10:00:02Z",
            "metadata": json.dumps({"dispatch_mode": "local"}),
        },
        {
            "id": "task-normal",
            "dispatchStatus": "PENDING",
            "status": "PENDING",
            "createdAt": "2026-03-30T10:00:03Z",
            "metadata": "{}",
        },
    ])

    pending = _list_pending_tasks_for_account(client, "acct-1")
    assert [task["id"] for task in pending] == ["task-normal"]


def test_claim_task_for_dispatch_refuses_self_managed_task():
    task = SimpleNamespace(
        dispatchStatus="PENDING",
        metadata=json.dumps({"dispatch_mode": "local"}),
        accountId="acct-1",
        type="Procedure",
        status="PENDING",
        target="procedure/proc-1",
        command="procedure run proc-1",
        update=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("local task should not be claimed")),
    )

    assert _claim_task_for_dispatch(task, "dispatcher-1", "celery") is False


def test_list_pending_tasks_only_returns_pending_and_sorts_newest_first():
    client = _StubClient([
        {
            "id": "old-pending",
            "dispatchStatus": "PENDING",
            "status": "PENDING",
            "createdAt": "2026-03-30T10:00:01Z",
            "metadata": "{}",
        },
        {
            "id": "new-pending",
            "dispatchStatus": "PENDING",
            "status": "PENDING",
            "createdAt": "2026-03-30T10:00:03Z",
            "metadata": "{}",
        },
        {
            "id": "already-dispatched",
            "dispatchStatus": "DISPATCHED",
            "status": "PENDING",
            "createdAt": "2026-03-30T10:00:04Z",
            "metadata": "{}",
        },
        {
            "id": "completed",
            "dispatchStatus": "PENDING",
            "status": "COMPLETED",
            "createdAt": "2026-03-30T10:00:05Z",
            "metadata": "{}",
        },
    ])

    pending = _list_pending_tasks_for_account(client, "acct-1")
    assert [task["id"] for task in pending] == ["new-pending", "old-pending"]


def test_build_local_run_args_uses_python_module_for_programmatic_report_blocks():
    task = SimpleNamespace(
        type="ProgrammaticReportBlock",
        command="feedback report run-programmatic-block --payload-base64 abc123",
    )
    run_args = _build_local_run_args(task)
    assert run_args[:3] == [run_args[0], "-m", "plexus.cli"]
    assert run_args[3:] == [
        "feedback",
        "report",
        "run-programmatic-block",
        "--payload-base64",
        "abc123",
    ]


def test_build_local_run_args_uses_plexus_entrypoint_for_other_task_types():
    task = SimpleNamespace(type="Procedure", command="procedure run --id proc-1")
    run_args = _build_local_run_args(task)
    assert run_args == ["plexus", "procedure", "run", "--id", "proc-1"]
