import unittest
from unittest.mock import patch

import click

from plexus.cli.shared.CommandDispatch import (
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
                        ]
                    }
                }

        pending = _list_pending_tasks_for_account(FakeClient(), "account", limit=10)
        self.assertEqual([item["id"] for item in pending], ["c", "a"])

    def test_map_procedure_status_to_task_status(self):
        self.assertEqual(_map_procedure_status_to_task_status("WAITING_FOR_HUMAN"), "RUNNING")
        self.assertEqual(_map_procedure_status_to_task_status("COMPLETED"), "COMPLETED")
        self.assertEqual(_map_procedure_status_to_task_status("COMPLETE"), "COMPLETED")
        self.assertEqual(_map_procedure_status_to_task_status("FAILED"), "FAILED")
        self.assertEqual(_map_procedure_status_to_task_status("ERROR"), "FAILED")
        self.assertIsNone(_map_procedure_status_to_task_status("RUNNING"))
        self.assertIsNone(_map_procedure_status_to_task_status(None))


if __name__ == "__main__":
    unittest.main()
