from pathlib import Path


def test_portable_command_worker_container_artifact_uses_the_package_runtime() -> None:
    dockerfile = (
        Path(__file__).parents[2] / "plexus" / "command_worker" / "Dockerfile"
    ).read_text(encoding="utf-8")

    assert "python:3.12-slim" in dockerfile
    assert ".[command-worker]" in dockerfile
    assert 'ENTRYPOINT ["plexus-command-worker"]' in dockerfile
    assert "COMMAND_WORKER_EXECUTOR_FACTORY" in dockerfile
