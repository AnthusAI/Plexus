import json

from plexus.cli.shared.CommandDispatch import _list_pending_tasks_for_account


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


def test_list_pending_tasks_skips_console_async_worker_tasks():
    client = _StubClient([
        {
            "id": "task-console",
            "dispatchStatus": "PENDING",
            "status": "PENDING",
            "createdAt": "2026-03-30T10:00:01Z",
            "metadata": json.dumps({"dispatch_mode": "console_async_worker"}),
        },
        {
            "id": "task-normal",
            "dispatchStatus": "PENDING",
            "status": "PENDING",
            "createdAt": "2026-03-30T10:00:02Z",
            "metadata": json.dumps({"dispatch_mode": "local"}),
        },
    ])

    pending = _list_pending_tasks_for_account(client, "acct-1")
    assert [task["id"] for task in pending] == ["task-normal"]


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
