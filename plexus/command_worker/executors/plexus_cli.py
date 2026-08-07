"""Execute an explicit Plexus CLI argv through the portable worker contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from threading import RLock
import sys

from plexus.cli.shared.CommandProgress import CommandProgress, ProgressState

from ..models import CommandEnvelope, JSONValue
from ..ports import ExecutionContext

_CLI_LOCK = RLock()
_TASK_ID_KEY = "task_id"
_ARGV_KEY = "argv"
_ACCOUNT_ID_ENV = "PLEXUS_ACCOUNT_ID"
_MAX_RESULT_OUTPUT_BYTES = 65_536


def _invoke_plexus_cli() -> None:
    from plexus.cli.shared.CommandLineInterface import cli

    cli(standalone_mode=False)


class PlexusCliExecutor:
    """Run a typed CLI request and publish its progress through ``ExecutionContext``.

    The transport contract deliberately accepts an argv array rather than a shell
    command string. This keeps dispatch data unambiguous and prevents command
    parsing from becoming an execution boundary. ``task_id`` is optional and is
    exposed only as the established CLI environment binding for task-aware
    commands.
    """

    def __init__(self, invoke_cli: Callable[[], None] | None = None) -> None:
        self._invoke_cli = invoke_cli or _invoke_plexus_cli

    def execute(
        self, envelope: CommandEnvelope, context: ExecutionContext
    ) -> JSONValue:
        argv, task_id = self._parse_payload(envelope.payload)
        context.raise_if_cancellation_requested()

        stdout = io.StringIO()
        stderr = io.StringIO()
        with _CLI_LOCK:
            previous_argv = sys.argv
            previous_task_id = os.environ.get("PLEXUS_DISPATCH_TASK_ID")
            previous_account_id = os.environ.get(_ACCOUNT_ID_ENV)
            try:
                with CommandProgress.bind_update_callback(
                    lambda state: self._report_progress(context, state)
                ), redirect_stdout(stdout), redirect_stderr(stderr):
                    sys.argv = ["plexus", *argv]
                    # The envelope is verified against the authoritative Task
                    # before execution. Bind its account ID without treating it
                    # as the distinct legacy account-key configuration.
                    os.environ[_ACCOUNT_ID_ENV] = envelope.tenant_id
                    if task_id is not None:
                        os.environ["PLEXUS_DISPATCH_TASK_ID"] = task_id
                    self._invoke_cli()
                    context.raise_if_cancellation_requested()
            finally:
                sys.argv = previous_argv
                if previous_task_id is None:
                    os.environ.pop("PLEXUS_DISPATCH_TASK_ID", None)
                else:
                    os.environ["PLEXUS_DISPATCH_TASK_ID"] = previous_task_id
                if previous_account_id is None:
                    os.environ.pop(_ACCOUNT_ID_ENV, None)
                else:
                    os.environ[_ACCOUNT_ID_ENV] = previous_account_id

        return {
            "argv": list(argv),
            "stdout": self._bounded_output(stdout.getvalue()),
            "stderr": self._bounded_output(stderr.getvalue()),
        }

    @staticmethod
    def _parse_payload(
        payload: Mapping[str, JSONValue],
    ) -> tuple[tuple[str, ...], str | None]:
        if set(payload) - {_ARGV_KEY, _TASK_ID_KEY}:
            raise ValueError("command payload contains unsupported fields")
        raw_argv = payload.get(_ARGV_KEY)
        if not isinstance(raw_argv, tuple) or not raw_argv:
            raise ValueError("command payload argv must be a non-empty array")
        if not all(isinstance(argument, str) and argument for argument in raw_argv):
            raise ValueError("command payload argv must contain non-empty strings")
        task_id = payload.get(_TASK_ID_KEY)
        if task_id is not None and (not isinstance(task_id, str) or not task_id):
            raise ValueError("command payload task_id must be a non-empty string")
        return raw_argv, task_id

    @staticmethod
    def _report_progress(context: ExecutionContext, state: ProgressState) -> None:
        fraction = state.current / state.total if state.total else 0.0
        context.report_progress(
            fraction,
            state.status,
            {"current": state.current, "total": state.total},
        )

    @staticmethod
    def _bounded_output(value: str) -> str:
        encoded = value.encode("utf-8")
        if len(encoded) <= _MAX_RESULT_OUTPUT_BYTES:
            return value
        return encoded[:_MAX_RESULT_OUTPUT_BYTES].decode("utf-8", errors="ignore")


def create_executor() -> PlexusCliExecutor:
    """Runtime plugin factory for the portable command-worker entrypoint."""
    return PlexusCliExecutor()
