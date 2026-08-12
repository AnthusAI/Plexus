"""Execute an explicit Plexus CLI argv through the portable worker contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import redirect_stderr, redirect_stdout
import io
import logging
import os
from pathlib import Path
from threading import RLock
import sys

from plexus.cli.shared.CommandProgress import CommandProgress, ProgressState

from ..models import CommandEnvelope, JSONValue
from ..ports import ExecutionContext

_CLI_LOCK = RLock()
_TASK_ID_KEY = "task_id"
_ARGV_KEY = "argv"
_ACCOUNT_ID_ENV = "PLEXUS_ACCOUNT_ID"
_RUNTIME_PROFILE_ENV = "PLEXUS_RUNTIME_PROFILE"
_DASHBOARD_RUNTIME_PROFILE = "dashboard"
_WORKER_RUNTIME_DIR_ENV = "PLEXUS_WORKER_RUNTIME_DIR"
_DEFAULT_WORKER_RUNTIME_DIR = "/tmp"
_MAX_RESULT_OUTPUT_BYTES = 65_536
_logger = logging.getLogger(__name__)


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
        self._guard_langchain_cache_writability()

        stdout = io.StringIO()
        stderr = io.StringIO()
        with _CLI_LOCK:
            previous_argv = sys.argv
            previous_task_id = os.environ.get("PLEXUS_DISPATCH_TASK_ID")
            previous_account_id = os.environ.get(_ACCOUNT_ID_ENV)
            previous_runtime_profile = os.environ.get(_RUNTIME_PROFILE_ENV)
            previous_cwd = os.getcwd()
            runtime_cwd = self._runtime_working_directory()
            try:
                with CommandProgress.bind_update_callback(
                    lambda state: self._report_progress(context, state)
                ), redirect_stdout(stdout), redirect_stderr(stderr):
                    if runtime_cwd is not None:
                        os.chdir(runtime_cwd)
                    sys.argv = ["plexus", *argv]
                    # The envelope is verified against the authoritative Task
                    # before execution. Bind its account ID without treating it
                    # as the distinct legacy account-key configuration.
                    os.environ[_ACCOUNT_ID_ENV] = envelope.tenant_id
                    os.environ[_RUNTIME_PROFILE_ENV] = _DASHBOARD_RUNTIME_PROFILE
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
                if previous_runtime_profile is None:
                    os.environ.pop(_RUNTIME_PROFILE_ENV, None)
                else:
                    os.environ[_RUNTIME_PROFILE_ENV] = previous_runtime_profile
                os.chdir(previous_cwd)

        return {
            "argv": list(argv),
            "stdout": self._bounded_output(stdout.getvalue()),
            "stderr": self._bounded_output(stderr.getvalue()),
        }

    @staticmethod
    def _guard_langchain_cache_writability() -> None:
        """Disable non-writable LangChain SQLite caches before command execution.

        Some score modules set a global LangChain SQLite cache path during import.
        In ECS command-worker containers the selected path can be non-writable for
        the runtime user, causing every LLM call to raise sqlite OperationalError
        and trigger expensive retry loops.
        """
        try:
            from langchain_core.globals import get_llm_cache, set_llm_cache
            from langchain_community.cache import SQLiteCache
        except Exception:
            return

        cache = get_llm_cache()
        if not isinstance(cache, SQLiteCache):
            return

        db_path = getattr(getattr(cache, "engine", None), "url", None)
        db_file = getattr(db_path, "database", None) if db_path is not None else None
        if not isinstance(db_file, str) or not db_file:
            return

        writable = False
        if os.path.exists(db_file):
            writable = os.access(db_file, os.W_OK)
        else:
            parent = os.path.dirname(db_file) or "."
            writable = os.path.isdir(parent) and os.access(parent, os.W_OK)

        if writable:
            return

        _logger.warning(
            "Disabling non-writable LangChain SQLite cache at %s to prevent runtime retry stalls",
            db_file,
        )
        set_llm_cache(None)

    @staticmethod
    def _runtime_working_directory() -> Path | None:
        """Choose a writable working directory for command execution.

        Some command libraries initialize SQLite-backed caches with a default
        relative path. In immutable container image directories that can become
        read-only at runtime and trigger retry loops. Running commands from a
        writable runtime directory keeps relative SQLite paths safe.
        """
        configured = os.environ.get(
            _WORKER_RUNTIME_DIR_ENV, _DEFAULT_WORKER_RUNTIME_DIR
        )
        if not configured:
            return None
        candidate = Path(configured)
        if candidate.is_dir() and os.access(candidate, os.W_OK):
            return candidate
        _logger.warning(
            "Command worker runtime directory %s is not writable; using existing cwd",
            configured,
        )
        return None

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
