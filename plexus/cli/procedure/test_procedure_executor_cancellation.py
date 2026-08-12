from unittest.mock import Mock

from plexus.cli.procedure.procedure_executor import _is_dashboard_task_cancelled


def test_is_dashboard_task_cancelled_true_for_cancelled_status() -> None:
    client = Mock()
    client.execute.return_value = {"getTask": {"status": "CANCELLED"}}

    assert _is_dashboard_task_cancelled(client, "task-1") is True


def test_is_dashboard_task_cancelled_true_for_cancel_requested_status() -> None:
    client = Mock()
    client.execute.return_value = {"getTask": {"status": "CANCEL_REQUESTED"}}

    assert _is_dashboard_task_cancelled(client, "task-2") is True


def test_is_dashboard_task_cancelled_false_for_running_status() -> None:
    client = Mock()
    client.execute.return_value = {"getTask": {"status": "RUNNING"}}

    assert _is_dashboard_task_cancelled(client, "task-3") is False

