"""Behavior checks for the local command-worker smoke harness."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "smoke_local_command_worker_report.py"


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("local_command_worker_report_smoke", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_container_receives_the_json_payload_on_stdin(monkeypatch):
    """A local report run supplies its command envelope to the container."""
    smoke = load_smoke_module()
    observed = {}

    class Process:
        returncode = 0
        stdin = object()
        stdout = object()

        def communicate(self, payload):
            observed["payload"] = payload
            return ('{"status": "ok", "result": {}}\n', None)

    def popen(command, **kwargs):
        observed["command"] = command
        return Process()

    monkeypatch.setattr(smoke.subprocess, "Popen", popen)
    monkeypatch.setattr(smoke.uuid, "uuid4", lambda: SimpleNamespace(hex="test-command"))

    smoke.run_worker(
        "worker:smoke",
        "config-123",
        {
            "PLEXUS_ACCOUNT_ID": "tenant-123",
            "AWS_ACCESS_KEY_ID": "key",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "AWS_SESSION_TOKEN": "token",
        },
    )

    assert "-i" in observed["command"]
    assert '"argv": ["report", "run", "--config", "config-123"]' in observed["payload"]
