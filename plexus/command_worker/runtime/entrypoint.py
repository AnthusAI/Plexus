"""Configure and run the portable command worker in a container process."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from importlib import import_module
import os
from pathlib import Path
from socket import gethostname
import sys
from uuid import uuid4

from celery import Celery

from ..adapters.celery_delivery import register_portable_command_task
from ..adapters.ecs_task_protection import EcsAgentTaskScaleInProtection
from ..adapters.task_store import GraphQLTaskStoreGateway, TaskBackedCommandStore
from plexus.dashboard.api.client import PlexusDashboardClient
from ..ports import Clock, Executor

_REQUIRED_ENVIRONMENT = (
    "AWS_REGION",
    "COMMAND_QUEUE_URL",
    "PLEXUS_API_URL",
    "COMMAND_WORKER_EXECUTOR_FACTORY",
    "COMMAND_WORKER_LEASE_SECONDS",
    "COMMAND_WORKER_HEARTBEAT_SECONDS",
    "COMMAND_WORKER_VISIBILITY_TIMEOUT_SECONDS",
)
_MAX_SQS_VISIBILITY_SECONDS = 12 * 60 * 60
_RUNTIME_ENVIRONMENT_DEFAULTS = {
    "HOME": "/tmp",
    "XDG_CONFIG_HOME": "/tmp/.config",
    "XDG_CACHE_HOME": "/tmp/.cache",
    "MPLCONFIGDIR": "/tmp/matplotlib",
    "NLTK_DATA": "/usr/local/share/nltk_data:/tmp/nltk_data",
    "SCORECARD_CACHE_DIR": "/tmp/scorecards",
}
_RUNTIME_DIRECTORIES = (
    "/tmp/.config",
    "/tmp/.cache",
    "/tmp/matplotlib",
    "/tmp/nltk_data",
    "/tmp/scorecards",
)


class UtcClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


def configure_runtime_filesystem() -> None:
    """Set one writable runtime contract for every command implementation.

    Command workers execute Plexus, LangGraph, Tactus, and third-party score
    implementations in the same non-root container. Standard runtime locations
    prevent individual node types from falling back to the read-only application
    directory for caches, tokenizer resources, or plotting configuration.
    """
    for name, value in _RUNTIME_ENVIRONMENT_DEFAULTS.items():
        os.environ.setdefault(name, value)
    for directory in _RUNTIME_DIRECTORIES:
        Path(directory).mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class CommandWorkerRuntimeConfig:
    """Validated runtime bindings supplied by the deployment environment."""

    region: str
    api_url: str
    queue_url: str
    queue_name: str
    executor_factory: str
    lease_duration: timedelta
    heartbeat_interval: timedelta
    visibility_timeout: timedelta
    task_name: str
    log_level: str

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "CommandWorkerRuntimeConfig":
        values = environment if environment is not None else os.environ
        missing = [
            name for name in _REQUIRED_ENVIRONMENT if not values.get(name, "").strip()
        ]
        if missing:
            raise ValueError(
                "missing required command-worker environment variables: "
                + ", ".join(missing)
            )
        queue_url = values["COMMAND_QUEUE_URL"].strip()
        queue_name = queue_url.rstrip("/").rsplit("/", maxsplit=1)[-1]
        if not queue_name or queue_name == queue_url:
            raise ValueError("COMMAND_QUEUE_URL must be an SQS queue URL")
        lease_duration = cls._duration(values, "COMMAND_WORKER_LEASE_SECONDS")
        heartbeat_interval = cls._duration(values, "COMMAND_WORKER_HEARTBEAT_SECONDS")
        visibility_timeout = cls._duration(
            values, "COMMAND_WORKER_VISIBILITY_TIMEOUT_SECONDS"
        )
        if heartbeat_interval >= lease_duration:
            raise ValueError(
                "COMMAND_WORKER_HEARTBEAT_SECONDS must be less than the lease"
            )
        if visibility_timeout < lease_duration:
            raise ValueError(
                "COMMAND_WORKER_VISIBILITY_TIMEOUT_SECONDS must be at least the lease"
            )
        if visibility_timeout.total_seconds() > _MAX_SQS_VISIBILITY_SECONDS:
            raise ValueError(
                "COMMAND_WORKER_VISIBILITY_TIMEOUT_SECONDS exceeds SQS maximum"
            )

        return cls(
            region=values["AWS_REGION"].strip(),
            api_url=values["PLEXUS_API_URL"].strip(),
            queue_url=queue_url,
            queue_name=queue_name,
            executor_factory=values["COMMAND_WORKER_EXECUTOR_FACTORY"].strip(),
            lease_duration=lease_duration,
            heartbeat_interval=heartbeat_interval,
            visibility_timeout=visibility_timeout,
            task_name=values.get(
                "COMMAND_WORKER_TASK_NAME", "plexus.command_worker.execute"
            ).strip(),
            log_level=values.get("COMMAND_WORKER_LOG_LEVEL", "INFO").strip(),
        )

    @staticmethod
    def _duration(values: Mapping[str, str], name: str) -> timedelta:
        try:
            seconds = int(values[name])
        except ValueError as error:
            raise ValueError(f"{name} must be a positive integer") from error
        if seconds <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return timedelta(seconds=seconds)


def load_executor(factory_reference: str) -> Executor:
    """Load an integration-owned executor factory without importing its package eagerly."""

    module_name, separator, attribute_name = factory_reference.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError(
            "COMMAND_WORKER_EXECUTOR_FACTORY must use module:factory syntax"
        )
    try:
        factory = getattr(import_module(module_name), attribute_name)
    except (ImportError, AttributeError) as error:
        raise ValueError(
            f"could not load command worker executor factory: {factory_reference}"
        ) from error
    if not callable(factory):
        raise ValueError("COMMAND_WORKER_EXECUTOR_FACTORY must resolve to a callable")
    executor = factory()
    if not callable(getattr(executor, "execute", None)):
        raise ValueError(
            "command worker executor must provide execute(envelope, context)"
        )
    return executor


def build_celery_app(
    config: CommandWorkerRuntimeConfig,
    *,
    executor: Executor | None = None,
    clock: Clock | None = None,
) -> Celery:
    """Build the Celery app and register the portable command task."""

    celery_app = Celery(
        "plexus.command_worker", broker="sqs://", backend="cache+memory://"
    )
    celery_app.conf.update(
        task_default_queue=config.queue_name,
        task_ignore_result=True,
        broker_transport_options={
            "region": config.region,
            "predefined_queues": {config.queue_name: {"url": config.queue_url}},
            "visibility_timeout": int(config.visibility_timeout.total_seconds()),
        },
    )
    client = PlexusDashboardClient(
        api_url=config.api_url,
        auth_mode="iam",
    )
    lifecycle = TaskBackedCommandStore(GraphQLTaskStoreGateway(client), {})
    register_portable_command_task(
        celery_app,
        task_name=config.task_name,
        lifecycle=lifecycle,
        executor=executor or load_executor(config.executor_factory),
        clock=clock or UtcClock(),
        owner_factory=lambda: f"{gethostname()}:{os.getpid()}:{uuid4()}",
        lease_duration=config.lease_duration,
        heartbeat_interval=config.heartbeat_interval,
        task_scale_in_protection=(
            EcsAgentTaskScaleInProtection(os.environ["ECS_AGENT_URI"])
            if os.environ.get("ECS_AGENT_URI", "").strip()
            else None
        ),
    )
    return celery_app


def main() -> None:
    """Run the named command queue until the container is stopped by ECS."""

    if any(argument in {"-h", "--help"} for argument in sys.argv[1:]):
        print(
            "Usage: plexus-command-worker\n\nRun the configured command-worker queue."
        )
        return

    configure_runtime_filesystem()
    config = CommandWorkerRuntimeConfig.from_environment()
    app = build_celery_app(config)
    app.worker_main(
        [
            "worker",
            "--loglevel",
            config.log_level,
            "--queues",
            config.queue_name,
        ]
    )


if __name__ == "__main__":  # pragma: no cover - exercised by the package script.
    main()
