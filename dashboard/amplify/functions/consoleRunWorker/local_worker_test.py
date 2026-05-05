from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_local_worker_module():
    worker_path = Path(__file__).with_name("local_worker.py")
    spec = importlib.util.spec_from_file_location("console_chat_local_worker", worker_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_local_worker_wrapper_delegates_to_cli_worker(monkeypatch):
    worker = _load_local_worker_module()
    calls = []
    monkeypatch.setattr(worker, "run_chat_worker", lambda: calls.append("called"))

    worker.main()

    assert calls == ["called"]
