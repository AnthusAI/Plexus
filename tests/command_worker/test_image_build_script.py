import os
import subprocess
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).parents[2]
    / "dashboard"
    / "scripts"
    / "build-command-worker-image.sh"
)
REPOSITORY = "123456789012.dkr.ecr.us-east-1.amazonaws.com/plexus-staging-worker"
DIGEST_A = f"sha256:{'a' * 64}"
DIGEST_B = f"sha256:{'b' * 64}"
IMAGE_A = f"{REPOSITORY}@{DIGEST_A}"
IMAGE_B = f"{REPOSITORY}@{DIGEST_B}"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def image_build(tmp_path: Path):
    root = tmp_path / "repo"
    (root / "dashboard" / "scripts").mkdir(parents=True)
    (root / "dashboard" / "scripts" / SCRIPT.name).write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (root / "plexus" / "command_worker").mkdir(parents=True)
    (root / "plexus" / "command_worker" / "Dockerfile").write_text(
        "FROM scratch\n", encoding="utf-8"
    )
    (root / "plexus" / "command_worker" / "worker.py").write_text(
        "# worker\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (root / "poetry.lock").write_text("", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "docker",
        """#!/usr/bin/env bash
set -euo pipefail
cat >/dev/null
printf '%s\\n' "$*" >> "${AWS_STUB_LOG}/docker.log"
""",
    )
    _write_executable(
        bin_dir / "aws",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "${AWS_STUB_LOG}/aws.log"
service="${1:-}"
operation="${2:-}"
if [ "$service $operation" = "ssm get-parameter" ]; then
  case "$*" in
    *worker-image-repository-uri*) printf '%s\\n' "$AWS_STUB_REPOSITORY" ;;
    *current-worker-image-uri*)
      case "${AWS_STUB_CURRENT_MODE:-missing}" in
        value) printf '%s\\n' "$AWS_STUB_CURRENT" ;;
        missing) echo 'ParameterNotFound' >&2; exit 254 ;;
        denied) echo 'AccessDeniedException' >&2; exit 255 ;;
      esac
      ;;
    *task-table-name*)
      case "${AWS_STUB_TABLE_MODE:-missing}" in
        value) printf '%s\\n' "${AWS_STUB_TABLE:-TaskTable}" ;;
        missing) echo 'ParameterNotFound' >&2; exit 254 ;;
        denied) echo 'AccessDeniedException' >&2; exit 255 ;;
      esac
      ;;
  esac
elif [ "$service $operation" = "ecr get-login-password" ]; then
  echo password
elif [ "$service $operation" = "ecr describe-images" ]; then
  printf '%s\\n' "$AWS_STUB_DIGEST"
elif [ "$service $operation" = "dynamodb scan" ]; then
  if [[ "$*" != *RUNNING* || "$*" != *CANCEL_REQUESTED* ]]; then
    echo 'missing active lifecycle status filter' >&2
    exit 3
  fi
  if [ "${AWS_STUB_SCAN_MODE:-value}" = "error" ]; then
    echo 'AccessDeniedException' >&2
    exit 255
  fi
  printf '%s\\n' "${AWS_STUB_ACTIVE_COUNT:-0}"
fi
""",
    )

    def run(**overrides: str) -> subprocess.CompletedProcess[str]:
        log_dir = tmp_path / f"logs-{len(list(tmp_path.glob('logs-*')))}"
        log_dir.mkdir()
        env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "AWS_BRANCH": "staging",
            "AWS_STUB_LOG": str(log_dir),
            "AWS_STUB_REPOSITORY": REPOSITORY,
            "AWS_STUB_DIGEST": DIGEST_A,
            **overrides,
        }
        return subprocess.run(
            ["bash", str(root / "dashboard" / "scripts" / SCRIPT.name)],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    return root, run


def _deployment_environment(root: Path) -> dict[str, str]:
    command = "source dashboard/.command-worker-image.env; env"
    completed = subprocess.run(
        ["bash", "-c", command], cwd=root, text=True, capture_output=True, check=True
    )
    return dict(line.split("=", 1) for line in completed.stdout.splitlines() if "=" in line)


def test_initial_deployment_exports_candidate_digest_to_child_process(image_build) -> None:
    root, run = image_build

    completed = run(AWS_STUB_CURRENT_MODE="missing", AWS_STUB_DIGEST=DIGEST_A)

    assert completed.returncode == 0, completed.stderr
    deployment_env = _deployment_environment(root)
    assert deployment_env["PLEXUS_COMMAND_WORKER_FOUNDATION_REPOSITORY_URI"] == REPOSITORY
    assert deployment_env["PLEXUS_COMMAND_WORKER_IMAGE_URI"] == IMAGE_A
    assert deployment_env["PLEXUS_COMMAND_WORKER_IMAGE_REPLACEMENT_DEFERRED"] == "0"


@pytest.mark.parametrize("active_count", ["1", "2"])
def test_changed_candidate_retains_active_digest_then_advances(image_build, active_count) -> None:
    root, run = image_build

    deferred = run(
        AWS_STUB_CURRENT_MODE="value",
        AWS_STUB_CURRENT=IMAGE_A,
        AWS_STUB_TABLE_MODE="value",
        AWS_STUB_ACTIVE_COUNT=active_count,
        AWS_STUB_DIGEST=DIGEST_B,
    )

    assert deferred.returncode == 0, deferred.stderr
    assert _deployment_environment(root)["PLEXUS_COMMAND_WORKER_IMAGE_URI"] == IMAGE_A

    advanced = run(
        AWS_STUB_CURRENT_MODE="value",
        AWS_STUB_CURRENT=IMAGE_A,
        AWS_STUB_TABLE_MODE="value",
        AWS_STUB_ACTIVE_COUNT="0",
        AWS_STUB_DIGEST=DIGEST_B,
    )

    assert advanced.returncode == 0, advanced.stderr
    deployment_env = _deployment_environment(root)
    assert deployment_env["PLEXUS_COMMAND_WORKER_IMAGE_URI"] == IMAGE_B
    assert deployment_env["PLEXUS_COMMAND_WORKER_IMAGE_REPLACEMENT_DEFERRED"] == "0"


def test_missing_task_table_retains_deployed_digest(image_build) -> None:
    root, run = image_build

    completed = run(
        AWS_STUB_CURRENT_MODE="value",
        AWS_STUB_CURRENT=IMAGE_A,
        AWS_STUB_TABLE_MODE="missing",
        AWS_STUB_DIGEST=DIGEST_B,
    )

    assert completed.returncode == 0, completed.stderr
    deployment_env = _deployment_environment(root)
    assert deployment_env["PLEXUS_COMMAND_WORKER_IMAGE_URI"] == IMAGE_A
    assert deployment_env["PLEXUS_COMMAND_WORKER_IMAGE_REPLACEMENT_DEFERRED"] == "1"


def test_all_zero_multipage_scan_advances_candidate(image_build) -> None:
    root, run = image_build

    completed = run(
        AWS_STUB_CURRENT_MODE="value",
        AWS_STUB_CURRENT=IMAGE_A,
        AWS_STUB_TABLE_MODE="value",
        AWS_STUB_ACTIVE_COUNT="0\n0\n0",
        AWS_STUB_DIGEST=DIGEST_B,
    )

    assert completed.returncode == 0, completed.stderr
    assert _deployment_environment(root)["PLEXUS_COMMAND_WORKER_IMAGE_URI"] == IMAGE_B


def test_active_item_on_later_scan_page_retains_deployed_digest(image_build) -> None:
    root, run = image_build

    completed = run(
        AWS_STUB_CURRENT_MODE="value",
        AWS_STUB_CURRENT=IMAGE_A,
        AWS_STUB_TABLE_MODE="value",
        AWS_STUB_ACTIVE_COUNT="0\n1",
        AWS_STUB_DIGEST=DIGEST_B,
    )

    assert completed.returncode == 0, completed.stderr
    deployment_env = _deployment_environment(root)
    assert deployment_env["PLEXUS_COMMAND_WORKER_IMAGE_URI"] == IMAGE_A
    assert deployment_env["PLEXUS_COMMAND_WORKER_IMAGE_REPLACEMENT_DEFERRED"] == "1"


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"AWS_STUB_CURRENT_MODE": "denied"}, "AccessDeniedException"),
        (
            {
                "AWS_STUB_CURRENT_MODE": "missing",
                "AWS_STUB_TABLE_MODE": "value",
            },
            "current worker image state is missing",
        ),
        (
            {
                "AWS_STUB_CURRENT_MODE": "value",
                "AWS_STUB_CURRENT": "malformed-current-image",
            },
            "invalid current worker image",
        ),
        (
            {
                "AWS_STUB_CURRENT_MODE": "value",
                "AWS_STUB_CURRENT": IMAGE_A,
                "AWS_STUB_TABLE_MODE": "denied",
                "AWS_STUB_DIGEST": DIGEST_B,
            },
            "AccessDeniedException",
        ),
        (
            {
                "AWS_STUB_CURRENT_MODE": "value",
                "AWS_STUB_CURRENT": IMAGE_A,
                "AWS_STUB_TABLE_MODE": "value",
                "AWS_STUB_TABLE": "not a table name",
                "AWS_STUB_DIGEST": DIGEST_B,
            },
            "invalid Task table identity",
        ),
        (
            {
                "AWS_STUB_CURRENT_MODE": "missing",
                "AWS_STUB_DIGEST": "not-a-digest",
            },
            "Invalid command-worker image digest",
        ),
        (
            {
                "AWS_STUB_CURRENT_MODE": "value",
                "AWS_STUB_CURRENT": IMAGE_A,
                "AWS_STUB_TABLE_MODE": "value",
                "AWS_STUB_SCAN_MODE": "error",
                "AWS_STUB_DIGEST": DIGEST_B,
            },
            "AccessDeniedException",
        ),
        (
            {
                "AWS_STUB_CURRENT_MODE": "value",
                "AWS_STUB_CURRENT": IMAGE_A,
                "AWS_STUB_TABLE_MODE": "value",
                "AWS_STUB_ACTIVE_COUNT": "not-a-count",
                "AWS_STUB_DIGEST": DIGEST_B,
            },
            "invalid active command count",
        ),
    ],
)
def test_unreadable_activity_state_fails_closed_without_handoff(
    image_build, overrides, error
) -> None:
    root, run = image_build
    handoff = root / "dashboard" / ".command-worker-image.env"
    handoff.write_text("stale=must-not-survive\n", encoding="utf-8")

    completed = run(**overrides)

    assert completed.returncode != 0
    assert error in completed.stderr
    assert not handoff.exists()
