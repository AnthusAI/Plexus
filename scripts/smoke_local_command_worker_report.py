#!/usr/bin/env python3
"""Run a saved report through the current command-worker image locally.

This is a pre-deploy smoke, not an ECS replacement.  It executes the same
``PlexusCliExecutor`` and immutable argv contract as the worker, while using
the selected staging control plane.  The report configuration is supplied by
ID so the script never embeds account-specific configuration or data.

The report and its Task are intentionally retained: deletion is not safe until
the report's attachments and stages have reached their terminal state.  The
script prints both IDs so a caller can inspect or remove the disposable run
through the supported dashboard APIs afterwards.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = "plexus-command-worker:local-smoke"
REQUIRED_ENV = (
    "PLEXUS_API_URL",
    "PLEXUS_ACCOUNT_ID",
    "AMPLIFY_STORAGE_DATASOURCES_BUCKET_NAME",
    "AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME",
    "AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-id", required=True, help="Saved ReportConfiguration ID")
    parser.add_argument("--image", default=DEFAULT_IMAGE, help="Local Docker image tag")
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Use an already-built --image instead of building the current source",
    )
    return parser.parse_args()


def require_environment() -> dict[str, str]:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    environment = {name: os.environ[name] for name in REQUIRED_ENV}
    environment["PLEXUS_GRAPHQL_AUTH_MODE"] = "iam"
    return environment


def aws_credentials() -> dict[str, str]:
    """Export the active AWS CLI session without printing credential values."""
    completed = subprocess.run(
        ["aws", "configure", "export-credentials", "--format", "env-no-export"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError("Could not export AWS credentials; run aws login first")
    values: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        name, separator, value = line.partition("=")
        if separator and name in {
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_CREDENTIAL_EXPIRATION",
        }:
            values[name] = value
    if not {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"} <= values.keys():
        raise RuntimeError("Active AWS session did not provide usable credentials")
    return values


def build_image(image: str) -> None:
    subprocess.run(
        [
            "docker",
            "build",
            "--platform",
            "linux/amd64",
            "-f",
            str(ROOT / "plexus" / "command_worker" / "Dockerfile"),
            "-t",
            image,
            str(ROOT),
        ],
        check=True,
    )


def run_worker(image: str, config_id: str, environment: dict[str, str]) -> dict[str, Any]:
    command_id = f"local-report-smoke-{uuid.uuid4().hex}"
    payload = {
        "schema_version": 2,
        "command_id": command_id,
        "tenant_id": environment["PLEXUS_ACCOUNT_ID"],
        "target": "report",
        "idempotency_key": command_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": {"argv": ["report", "run", "--config", config_id]},
    }
    program = """
import json
import sys
from datetime import datetime
from types import SimpleNamespace
from plexus.command_worker.executors.plexus_cli import PlexusCliExecutor
from plexus.command_worker.models import CommandEnvelope

payload = json.loads(sys.stdin.read())
envelope = CommandEnvelope(
    schema_version=payload[\"schema_version\"], command_id=payload[\"command_id\"],
    tenant_id=payload[\"tenant_id\"], target=payload[\"target\"],
    idempotency_key=payload[\"idempotency_key\"],
    created_at=datetime.fromisoformat(payload[\"created_at\"]), payload=payload[\"payload\"],
)
context = SimpleNamespace(
    raise_if_cancellation_requested=lambda: None,
    report_progress=lambda *args, **kwargs: None,
)
try:
    print(json.dumps({\"status\": \"ok\", \"result\": PlexusCliExecutor().execute(envelope, context)}))
except Exception as exc:
    print(json.dumps({\"status\": \"error\", \"error_type\": type(exc).__name__, \"error\": str(exc)}))
    raise SystemExit(1)
    """
    docker_command = ["docker", "run", "--rm", "--platform", "linux/amd64"]
    # Forward names only.  Passing values in argv would expose temporary AWS
    # credentials through process inspection while the smoke is running.
    for name in environment:
        docker_command.extend(["-e", name])
    docker_command.extend(["--entrypoint", "python", image, "-c", program])
    runner_environment = os.environ.copy()
    runner_environment.update(environment)
    completed = subprocess.run(
        docker_command,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=runner_environment,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"Worker produced no structured result: {completed.stderr[-4000:]}")
    try:
        result = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Worker produced invalid result: {lines[-1][-4000:]}") from exc
    if completed.returncode or result.get("status") != "ok":
        raise RuntimeError(json.dumps(result, default=str))
    return {"command_id": command_id, **result["result"]}


def main() -> int:
    args = parse_args()
    environment = {**require_environment(), **aws_credentials()}
    if not args.skip_build:
        build_image(args.image)
    result = run_worker(args.image, args.config_id, environment)
    print(json.dumps({"status": "ok", "image": args.image, **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
