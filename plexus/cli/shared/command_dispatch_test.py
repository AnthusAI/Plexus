import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import click
from click.testing import CliRunner

from plexus.cli.shared.CommandDispatch import (
    command,
    _resolve_dispatch_mode,
    _resolve_local_dispatch_timeout_seconds,
    _resolve_queue_name,
    _normalize_metadata,
    _list_pending_tasks_for_account,
    _map_procedure_status_to_task_status,
    DEFAULT_CELERY_QUEUE_NAME,
)


class TestCommandDispatchConfig(unittest.TestCase):
    def test_resolve_dispatch_mode_default(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(_resolve_dispatch_mode(), "celery")

    def test_resolve_dispatch_mode_local(self):
        with patch.dict("os.environ", {"PLEXUS_DISPATCH_MODE": "local"}, clear=True):
            self.assertEqual(_resolve_dispatch_mode(), "local")

    def test_resolve_dispatch_mode_invalid_raises(self):
        with patch.dict("os.environ", {"PLEXUS_DISPATCH_MODE": "invalid"}, clear=True):
            with self.assertRaises(click.ClickException):
                _resolve_dispatch_mode()

    def test_resolve_queue_name_prefers_explicit(self):
        with patch.dict("os.environ", {"CELERY_QUEUE_NAME": "env-queue"}, clear=True):
            self.assertEqual(_resolve_queue_name("flag-queue"), "flag-queue")

    def test_resolve_queue_name_prefers_env_over_config(self):
        with patch("plexus.cli.shared.CommandDispatch._load_queue_name_from_config", return_value="config-queue"):
            with patch.dict("os.environ", {"CELERY_QUEUE_NAME": "env-queue"}, clear=True):
                self.assertEqual(_resolve_queue_name(), "env-queue")

    def test_resolve_queue_name_uses_config_when_env_missing(self):
        with patch("plexus.cli.shared.CommandDispatch._load_queue_name_from_config", return_value="config-queue"):
            with patch.dict("os.environ", {}, clear=True):
                self.assertEqual(_resolve_queue_name(), "config-queue")

    def test_resolve_queue_name_uses_default_when_unset(self):
        with patch("plexus.cli.shared.CommandDispatch._load_queue_name_from_config", return_value=None):
            with patch.dict("os.environ", {}, clear=True):
                self.assertEqual(_resolve_queue_name(), DEFAULT_CELERY_QUEUE_NAME)

    def test_normalize_metadata_variants(self):
        self.assertEqual(_normalize_metadata({"a": 1}), {"a": 1})
        self.assertEqual(_normalize_metadata('{"a": 1}'), {"a": 1})
        self.assertEqual(_normalize_metadata(""), {})
        self.assertEqual(_normalize_metadata("not-json"), {})
        self.assertEqual(_normalize_metadata(None), {})

    def test_resolve_local_dispatch_timeout_default(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(_resolve_local_dispatch_timeout_seconds(), 900)

    def test_resolve_local_dispatch_timeout_invalid_raises(self):
        with patch.dict("os.environ", {"PLEXUS_LOCAL_TASK_TIMEOUT_SECONDS": "abc"}, clear=True):
            with self.assertRaises(click.ClickException):
                _resolve_local_dispatch_timeout_seconds()

    def test_resolve_local_dispatch_timeout_non_positive_raises(self):
        with patch.dict("os.environ", {"PLEXUS_LOCAL_TASK_TIMEOUT_SECONDS": "0"}, clear=True):
            with self.assertRaises(click.ClickException):
                _resolve_local_dispatch_timeout_seconds()

    def test_list_pending_tasks_filters_and_orders_newest_first(self):
        class FakeClient:
            def execute(self, _query, _variables):
                return {
                    "listTaskByAccountIdAndUpdatedAt": {
                        "items": [
                            {"id": "a", "status": "PENDING", "dispatchStatus": "PENDING", "createdAt": "2026-03-16T10:00:00Z"},
                            {"id": "b", "status": "COMPLETED", "dispatchStatus": "PENDING", "createdAt": "2026-03-16T12:00:00Z"},
                            {"id": "c", "status": "PENDING", "dispatchStatus": "PENDING", "createdAt": "2026-03-16T11:00:00Z"},
                            {
                                "id": "d",
                                "status": "WAITING_FOR_CHILDREN",
                                "dispatchStatus": "PENDING",
                                "metadata": '{"dispatch_policy":"resume_once"}',
                                "createdAt": "2026-03-16T13:00:00Z",
                            },
                            {
                                "id": "e",
                                "status": "WAITING_FOR_CHILDREN",
                                "dispatchStatus": "PENDING",
                                "metadata": "{}",
                                "createdAt": "2026-03-16T14:00:00Z",
                            },
                            {
                                "id": "f",
                                "status": "WAITING_FOR_TIME",
                                "dispatchStatus": "PENDING",
                                "metadata": '{"dispatch_policy":"resume_once"}',
                                "createdAt": "2026-03-16T15:00:00Z",
                            },
                            {
                                "id": "g",
                                "status": "WAITING_FOR_TIME",
                                "dispatchStatus": "PENDING",
                                "metadata": "{}",
                                "createdAt": "2026-03-16T16:00:00Z",
                            },
                        ]
                    }
                }

        pending = _list_pending_tasks_for_account(FakeClient(), "account", limit=10)
        self.assertEqual([item["id"] for item in pending], ["f", "d", "c", "a"])

    def test_map_procedure_status_to_task_status(self):
        self.assertEqual(_map_procedure_status_to_task_status("WAITING_FOR_HUMAN"), "RUNNING")
        self.assertEqual(
            _map_procedure_status_to_task_status("WAITING_FOR_CHILDREN"),
            "WAITING_FOR_CHILDREN",
        )
        self.assertEqual(
            _map_procedure_status_to_task_status("WAITING_FOR_TIME"),
            "WAITING_FOR_TIME",
        )
        self.assertEqual(_map_procedure_status_to_task_status("COMPLETED"), "COMPLETED")
        self.assertEqual(_map_procedure_status_to_task_status("COMPLETE"), "COMPLETED")
        self.assertEqual(_map_procedure_status_to_task_status("FAILED"), "FAILED")
        self.assertEqual(_map_procedure_status_to_task_status("ERROR"), "FAILED")
        self.assertEqual(_map_procedure_status_to_task_status("RUNNING"), "RUNNING")
        self.assertEqual(_map_procedure_status_to_task_status("PENDING"), "RUNNING")
        self.assertIsNone(_map_procedure_status_to_task_status(None))

    def test_local_dispatch_completes_a_non_procedure_after_successful_exit(self):
        task = SimpleNamespace(
            id="task-1",
            accountId="account-1",
            type="COMMAND",
            status="PENDING",
            target="items/info",
            command="items info item-1",
            metadata="{}",
            update=Mock(),
        )

        with (
            patch(
                "plexus.cli.shared.CommandDispatch._resolve_dispatch_mode",
                return_value="local",
            ),
            patch(
                "plexus.cli.shared.CommandDispatch._resolve_queue_name",
                return_value="queue",
            ),
            patch(
                "plexus.cli.shared.CommandDispatch._resolve_local_dispatch_timeout_seconds",
                return_value=30,
            ),
            patch("plexus.cli.shared.CommandDispatch.create_client", return_value=object()),
            patch(
                "plexus.cli.shared.CommandDispatch._resolve_required_dispatch_account_id",
                return_value="account-1",
            ),
            patch(
                "plexus.cli.shared.CommandDispatch._list_pending_tasks_for_account",
                return_value=[{"id": "task-1"}],
            ),
            patch("plexus.cli.shared.CommandDispatch.Task.get_by_id", return_value=task),
            patch(
                "plexus.cli.shared.CommandDispatch._claim_task_for_dispatch",
                return_value=True,
            ),
            patch(
                "plexus.cli.shared.CommandDispatch._build_local_run_args",
                return_value=["plexus", "items", "info"],
            ),
            patch(
                "plexus.cli.shared.CommandDispatch.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout="done", stderr=""),
            ),
            patch(
                "plexus.cli.shared.CommandDispatch._get_procedure_status_for_local_command",
                return_value=None,
            ),
        ):
            result = CliRunner().invoke(command, ["dispatcher", "--once"])

        self.assertEqual(result.exit_code, 0, result.output)
        task.update.assert_called_once()
        self.assertEqual(task.update.call_args.kwargs["status"], "COMPLETED")
        self.assertEqual(task.update.call_args.kwargs["dispatchStatus"], "DISPATCHED")
        self.assertIsNotNone(task.update.call_args.kwargs["completedAt"])

    def test_local_dispatch_preserves_durable_time_wait_without_completing_task(self):
        claimed_task = SimpleNamespace(
            id="task-1",
            accountId="account-1",
            type="PROCEDURE",
            status="RUNNING",
            target="procedure/run",
            command="plexus procedure run procedure-1",
            metadata='{"procedure_id":"procedure-1"}',
            update=Mock(),
        )
        durable_waiting_task = SimpleNamespace(
            id="task-1",
            accountId="account-1",
            type="PROCEDURE",
            status="WAITING_FOR_TIME",
            dispatchStatus="WAITING_FOR_TIME",
            workerNodeId=None,
            completedAt=None,
            target="procedure/run",
            command="plexus procedure run procedure-1",
            metadata='{"procedure_id":"procedure-1","dispatch_policy":"resume_once"}',
            update=Mock(),
        )

        with (
            patch("plexus.cli.shared.CommandDispatch._resolve_dispatch_mode", return_value="local"),
            patch("plexus.cli.shared.CommandDispatch._resolve_queue_name", return_value="queue"),
            patch("plexus.cli.shared.CommandDispatch._resolve_local_dispatch_timeout_seconds", return_value=30),
            patch("plexus.cli.shared.CommandDispatch.create_client", return_value=object()),
            patch("plexus.cli.shared.CommandDispatch._resolve_required_dispatch_account_id", return_value="account-1"),
            patch("plexus.cli.shared.CommandDispatch._list_pending_tasks_for_account", return_value=[{"id": "task-1"}]),
            patch(
                "plexus.cli.shared.CommandDispatch.Task.get_by_id",
                side_effect=[claimed_task, durable_waiting_task],
            ) as get_task,
            patch("plexus.cli.shared.CommandDispatch._claim_task_for_dispatch", return_value=True),
            patch("plexus.cli.shared.CommandDispatch._build_local_run_args", return_value=["plexus", "procedure", "run"]),
            patch(
                "plexus.cli.shared.CommandDispatch.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
            ),
            patch(
                "plexus.cli.shared.CommandDispatch._get_procedure_status_for_local_command",
                return_value="WAITING_FOR_TIME",
            ),
        ):
            result = CliRunner().invoke(command, ["dispatcher", "--once"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(get_task.call_count, 2)
        durable_waiting_task.update.assert_not_called()
        self.assertEqual(durable_waiting_task.status, "WAITING_FOR_TIME")
        self.assertEqual(durable_waiting_task.dispatchStatus, "WAITING_FOR_TIME")
        self.assertIsNone(durable_waiting_task.workerNodeId)
        self.assertIsNone(durable_waiting_task.completedAt)

    def test_local_dispatch_fails_closed_when_time_wait_was_not_persisted(self):
        claimed_task = SimpleNamespace(
            id="task-1",
            accountId="account-1",
            type="PROCEDURE",
            status="RUNNING",
            target="procedure/run",
            command="plexus procedure run procedure-1",
            metadata='{"procedure_id":"procedure-1"}',
            update=Mock(),
        )

        with (
            patch("plexus.cli.shared.CommandDispatch._resolve_dispatch_mode", return_value="local"),
            patch("plexus.cli.shared.CommandDispatch._resolve_queue_name", return_value="queue"),
            patch("plexus.cli.shared.CommandDispatch._resolve_local_dispatch_timeout_seconds", return_value=30),
            patch("plexus.cli.shared.CommandDispatch.create_client", return_value=object()),
            patch("plexus.cli.shared.CommandDispatch._resolve_required_dispatch_account_id", return_value="account-1"),
            patch("plexus.cli.shared.CommandDispatch._list_pending_tasks_for_account", return_value=[{"id": "task-1"}]),
            patch(
                "plexus.cli.shared.CommandDispatch.Task.get_by_id",
                side_effect=[claimed_task, None],
            ) as get_task,
            patch("plexus.cli.shared.CommandDispatch._claim_task_for_dispatch", return_value=True),
            patch("plexus.cli.shared.CommandDispatch._build_local_run_args", return_value=["plexus", "procedure", "run"]),
            patch(
                "plexus.cli.shared.CommandDispatch.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
            ),
            patch(
                "plexus.cli.shared.CommandDispatch._get_procedure_status_for_local_command",
                return_value="WAITING_FOR_TIME",
            ),
            patch("plexus.cli.shared.CommandDispatch.logging.error") as log_error,
        ):
            result = CliRunner().invoke(command, ["dispatcher", "--once"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(get_task.call_count, 2)
        # An uncorroborated wait cannot be rewritten as a successful result.
        claimed_task.update.assert_not_called()
        log_error.assert_called_once_with(
            "Could not reload durable waiting task %s; preserving the runner's persisted state",
            "task-1",
        )

    def test_celery_publication_failure_terminalizes_the_ambiguous_claim(self):
        claimed_task = SimpleNamespace(
            id="task-1",
            accountId="account-1",
            type="Procedure",
            status="PENDING",
            target="procedure/procedure-1",
            command="procedure run procedure-1",
            dispatchStatus="PENDING",
            workerNodeId=None,
            updatedAt=None,
            metadata='{"dispatch_mode":"local","procedure_id":"procedure-1"}',
            update=Mock(),
        )
        client = Mock()
        client.execute.return_value = {
            "updateTask": {
                "id": "task-1",
                "status": "FAILED",
                "dispatchStatus": "ERROR",
                "workerNodeId": None,
            }
        }

        with (
            patch("plexus.cli.shared.CommandDispatch._resolve_dispatch_mode", return_value="celery"),
            patch("plexus.cli.shared.CommandDispatch._resolve_queue_name", return_value="queue"),
            patch("plexus.cli.shared.CommandDispatch._resolve_local_dispatch_timeout_seconds", return_value=30),
            patch("plexus.cli.shared.CommandDispatch._validate_celery_requirements"),
            patch("plexus.cli.shared.CommandDispatch.ensure_tasks_registered"),
            patch("plexus.cli.shared.CommandDispatch.create_client", return_value=client),
            patch("plexus.cli.shared.CommandDispatch._resolve_required_dispatch_account_id", return_value="account-1"),
            patch("plexus.cli.shared.CommandDispatch._list_pending_tasks_for_account", return_value=[{"id": "task-1"}]),
            patch("plexus.cli.shared.CommandDispatch.Task.get_by_id", return_value=claimed_task),
            patch("plexus.cli.shared.CommandDispatch._claim_task_for_dispatch", return_value=True),
            patch("plexus.cli.shared.CommandDispatch.get_celery_app") as get_celery_app,
        ):
            get_celery_app.return_value.send_task.side_effect = RuntimeError("transport unavailable")
            result = CliRunner().invoke(command, ["dispatcher", "--once"])

        self.assertEqual(result.exit_code, 0, result.output)
        client.execute.assert_called_once()
        mutation_variables = client.execute.call_args.args[1]
        self.assertEqual(mutation_variables["input"]["id"], "task-1")
        self.assertEqual(mutation_variables["input"]["status"], "FAILED")
        self.assertEqual(mutation_variables["input"]["dispatchStatus"], "ERROR")
        self.assertIsNone(mutation_variables["input"]["workerNodeId"])
        self.assertEqual(
            json.loads(mutation_variables["input"]["metadata"])["procedure_id"],
            "procedure-1",
        )
        self.assertEqual(
            json.loads(mutation_variables["input"]["errorDetails"]),
            {"phase": "celery_send", "exception_class": "RuntimeError"},
        )
        self.assertNotIn("transport unavailable", mutation_variables["input"]["errorMessage"])
        self.assertNotIn("transport unavailable", mutation_variables["input"]["errorDetails"])
        self.assertEqual(
            mutation_variables["condition"]["and"][0],
            {"dispatchStatus": {"eq": "DISPATCHING"}},
        )

    def test_celery_persistence_failure_after_dispatch_does_not_rearm_task(self):
        claimed_task = SimpleNamespace(
            id="task-1",
            accountId="account-1",
            type="Procedure",
            status="PENDING",
            target="procedure/procedure-1",
            command="procedure run procedure-1",
            dispatchStatus="PENDING",
            workerNodeId=None,
            updatedAt=None,
            metadata='{"dispatch_mode":"local","procedure_id":"procedure-1"}',
            update=Mock(side_effect=RuntimeError("persistence unavailable")),
        )
        client = Mock()

        with (
            patch("plexus.cli.shared.CommandDispatch._resolve_dispatch_mode", return_value="celery"),
            patch("plexus.cli.shared.CommandDispatch._resolve_queue_name", return_value="queue"),
            patch("plexus.cli.shared.CommandDispatch._resolve_local_dispatch_timeout_seconds", return_value=30),
            patch("plexus.cli.shared.CommandDispatch._validate_celery_requirements"),
            patch("plexus.cli.shared.CommandDispatch.ensure_tasks_registered"),
            patch("plexus.cli.shared.CommandDispatch.create_client", return_value=client),
            patch("plexus.cli.shared.CommandDispatch._resolve_required_dispatch_account_id", return_value="account-1"),
            patch("plexus.cli.shared.CommandDispatch._list_pending_tasks_for_account", return_value=[{"id": "task-1"}]),
            patch("plexus.cli.shared.CommandDispatch.Task.get_by_id", return_value=claimed_task),
            patch("plexus.cli.shared.CommandDispatch._claim_task_for_dispatch", return_value=True),
            patch("plexus.cli.shared.CommandDispatch.get_celery_app") as get_celery_app,
        ):
            get_celery_app.return_value.send_task.return_value = SimpleNamespace(id="celery-1")
            result = CliRunner().invoke(command, ["dispatcher", "--once"])

        self.assertEqual(result.exit_code, 0, result.output)
        client.execute.assert_not_called()
        claimed_task.update.assert_called_once()


if __name__ == "__main__":
    unittest.main()
