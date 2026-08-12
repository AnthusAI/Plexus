from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

from plexus.command_worker.runtime.entrypoint import (
    CommandWorkerRuntimeConfig,
    build_celery_app,
    configure_runtime_filesystem,
    load_executor,
    main,
)


def environment(**overrides: str) -> dict[str, str]:
    values = {
        "AWS_REGION": "us-east-1",
        "COMMAND_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789012/command-queue",
        "PLEXUS_API_URL": "https://example.appsync-api.us-east-1.amazonaws.com/graphql",
        "COMMAND_WORKER_EXECUTOR_FACTORY": "test_executor:create_executor",
        "COMMAND_WORKER_LEASE_SECONDS": "300",
        "COMMAND_WORKER_HEARTBEAT_SECONDS": "60",
        "COMMAND_WORKER_VISIBILITY_TIMEOUT_SECONDS": "900",
    }
    values.update(overrides)
    return values


class Executor:
    def execute(self, envelope, context):
        return {"ok": True}


class Clock:
    def now(self):
        return datetime(2026, 8, 6, tzinfo=timezone.utc)


def test_runtime_configuration_parses_queue_and_explicit_durations() -> None:
    config = CommandWorkerRuntimeConfig.from_environment(environment())

    assert config.queue_name == "command-queue"
    assert config.lease_duration.total_seconds() == 300
    assert config.heartbeat_interval.total_seconds() == 60
    assert config.visibility_timeout.total_seconds() == 900
    assert config.task_name == "plexus.command_worker.execute"
    assert (
        config.api_url == "https://example.appsync-api.us-east-1.amazonaws.com/graphql"
    )


def test_runtime_filesystem_uses_standard_writable_locations(monkeypatch) -> None:
    for name in (
        "HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "MPLCONFIGDIR",
        "NLTK_DATA",
        "SCORECARD_CACHE_DIR",
    ):
        monkeypatch.delenv(name, raising=False)

    configure_runtime_filesystem()

    assert os.environ["HOME"] == "/tmp"
    assert os.environ["NLTK_DATA"] == "/usr/local/share/nltk_data:/tmp/nltk_data"
    assert os.environ["MPLCONFIGDIR"] == "/tmp/matplotlib"
    assert all(
        Path(directory).is_dir()
        for directory in (
            "/tmp/.config",
            "/tmp/.cache",
            "/tmp/matplotlib",
            "/tmp/nltk_data",
            "/tmp/scorecards",
        )
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"COMMAND_WORKER_LEASE_SECONDS": ""}, "missing required"),
        ({"COMMAND_QUEUE_URL": "not-a-queue-url"}, "queue URL"),
        ({"COMMAND_WORKER_LEASE_SECONDS": "invalid"}, "positive integer"),
        (
            {
                "COMMAND_WORKER_LEASE_SECONDS": "60",
                "COMMAND_WORKER_HEARTBEAT_SECONDS": "60",
            },
            "less than",
        ),
        (
            {
                "COMMAND_WORKER_LEASE_SECONDS": "900",
                "COMMAND_WORKER_VISIBILITY_TIMEOUT_SECONDS": "300",
            },
            "at least the lease",
        ),
        ({"COMMAND_WORKER_VISIBILITY_TIMEOUT_SECONDS": "43201"}, "SQS maximum"),
    ],
)
def test_runtime_configuration_rejects_unsafe_bindings(overrides, message) -> None:
    with pytest.raises(ValueError, match=message):
        CommandWorkerRuntimeConfig.from_environment(environment(**overrides))


def test_load_executor_uses_explicit_integration_plugin(monkeypatch) -> None:
    module = ModuleType("test_executor")
    module.create_executor = Executor
    monkeypatch.setitem(sys.modules, "test_executor", module)

    assert isinstance(load_executor("test_executor:create_executor"), Executor)


@pytest.mark.parametrize(
    "reference",
    ["missing-separator", "missing_module:create_executor", "test_executor:missing"],
)
def test_load_executor_rejects_invalid_plugin_references(
    monkeypatch, reference
) -> None:
    module = ModuleType("test_executor")
    monkeypatch.setitem(sys.modules, "test_executor", module)

    with pytest.raises(ValueError):
        load_executor(reference)


def test_build_celery_app_uses_predefined_queue_and_registers_portable_task(
    monkeypatch,
) -> None:
    client = SimpleNamespace(execute=lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        "plexus.command_worker.runtime.entrypoint.PlexusDashboardClient",
        lambda **_kwargs: client,
    )
    config = CommandWorkerRuntimeConfig.from_environment(environment())

    app = build_celery_app(config, executor=Executor(), clock=Clock())

    assert app.conf.task_default_queue == "command-queue"
    assert app.conf.broker_transport_options["predefined_queues"] == {
        "command-queue": {"url": config.queue_url}
    }
    assert app.conf.broker_transport_options["visibility_timeout"] == 900
    assert config.task_name in app.tasks


def test_main_starts_a_worker_for_the_configured_queue(monkeypatch) -> None:
    config = CommandWorkerRuntimeConfig.from_environment(environment())
    worker = SimpleNamespace(worker_main=lambda arguments: observed.append(arguments))
    observed: list[list[str]] = []
    monkeypatch.setattr(CommandWorkerRuntimeConfig, "from_environment", lambda: config)
    monkeypatch.setattr(
        "plexus.command_worker.runtime.entrypoint.build_celery_app",
        lambda received: worker,
    )

    main()

    assert observed == [["worker", "--loglevel", "INFO", "--queues", "command-queue"]]
