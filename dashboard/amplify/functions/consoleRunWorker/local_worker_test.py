from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_local_worker_module():
    worker_path = Path(__file__).with_name("local_worker.py")
    spec = importlib.util.spec_from_file_location("console_chat_local_worker", worker_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_resolve_client_accepts_next_public_env(monkeypatch):
    worker = _load_local_worker_module()
    created = []

    class FakeClient:
        def __init__(self, *, api_url, api_key):
            created.append((api_url, api_key))

    monkeypatch.delenv("PLEXUS_API_URL", raising=False)
    monkeypatch.delenv("PLEXUS_API_KEY", raising=False)
    monkeypatch.setenv("NEXT_PUBLIC_PLEXUS_API_URL", "https://example.appsync-api.us-east-1.amazonaws.com/graphql")
    monkeypatch.setenv("NEXT_PUBLIC_PLEXUS_API_KEY", "da2-test")
    monkeypatch.setattr(worker, "_load_local_env", lambda: None)
    monkeypatch.setattr(worker, "PlexusDashboardClient", FakeClient)

    worker._resolve_client()

    assert created == [("https://example.appsync-api.us-east-1.amazonaws.com/graphql", "da2-test")]


def test_load_local_env_reads_repo_and_dashboard_env_files(monkeypatch):
    worker = _load_local_worker_module()
    loaded_calls: list[tuple[Path, bool]] = []
    repo_root = Path(__file__).resolve().parents[4]
    expected_order = [
        repo_root / ".env",
        repo_root / "dashboard" / ".env",
        repo_root / "dashboard" / ".env.local",
    ]
    expected = {str(path) for path in expected_order}

    monkeypatch.setattr(worker.Path, "exists", lambda path: str(path) in expected)
    monkeypatch.setattr(
        worker,
        "load_dotenv",
        lambda path, override=False: loaded_calls.append((path, override)),
    )

    worker._load_local_env()

    assert [str(path) for path, _ in loaded_calls] == [str(path) for path in expected_order]
    assert [override for _, override in loaded_calls] == [False, True, True]


def test_main_rejects_cloud_response_target(monkeypatch):
    worker = _load_local_worker_module()
    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "cloud")

    try:
        worker.main()
    except RuntimeError as exc:
        assert "local:<developer>" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_main_uses_next_public_response_target_from_env(monkeypatch):
    worker = _load_local_worker_module()
    calls = []
    results = iter([1, 0])

    monkeypatch.delenv("CONSOLE_RESPONSE_TARGET", raising=False)
    monkeypatch.setenv("NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET", "local:ryan")
    monkeypatch.setenv("CONSOLE_LOCAL_WORKER_IDLE_POLL_SECONDS", "0")
    monkeypatch.setattr(worker, "_resolve_client", lambda: SimpleNamespace())
    monkeypatch.setattr(worker, "_load_local_env", lambda: None)
    monkeypatch.setattr(
        worker,
        "process_pending_local_messages",
        lambda _client, **kwargs: calls.append(kwargs) or next(results),
    )
    monkeypatch.setattr(worker.time, "sleep", lambda _secs: (_ for _ in ()).throw(SystemExit(0)))

    try:
        worker.main()
    except SystemExit:
        pass
    else:
        raise AssertionError("expected SystemExit from patched sleep")

    assert len(calls) == 2
    assert calls[0]["response_target"] == "local:ryan"


def test_main_processes_pending_messages_with_local_owner(monkeypatch):
    worker = _load_local_worker_module()
    calls = []
    results = iter([1, 0])

    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "local:ryan")
    monkeypatch.setenv("CONSOLE_LOCAL_WORKER_IDLE_POLL_SECONDS", "0")
    monkeypatch.setattr(worker, "_resolve_client", lambda: SimpleNamespace())
    monkeypatch.setattr(
        worker,
        "process_pending_local_messages",
        lambda _client, **kwargs: calls.append(kwargs) or next(results),
    )
    monkeypatch.setattr(worker.time, "sleep", lambda _secs: (_ for _ in ()).throw(SystemExit(0)))

    try:
        worker.main()
    except SystemExit:
        pass
    else:
        raise AssertionError("expected SystemExit from patched sleep")

    assert len(calls) == 2
    assert calls[0]["response_target"] == "local:ryan"
    assert calls[0]["limit"] == 5
    assert calls[0]["owner"].startswith("local:ryan:")


def test_main_drain_mode_only_sleeps_when_no_work(monkeypatch):
    worker = _load_local_worker_module()
    calls = []
    results = iter([1, 1, 0])

    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "local:ryan")
    monkeypatch.setenv("CONSOLE_LOCAL_WORKER_IDLE_POLL_SECONDS", "0")
    monkeypatch.setattr(worker, "_resolve_client", lambda: SimpleNamespace())
    monkeypatch.setattr(
        worker,
        "process_pending_local_messages",
        lambda _client, **kwargs: calls.append(kwargs) or next(results),
    )
    monkeypatch.setattr(worker.time, "sleep", lambda _secs: (_ for _ in ()).throw(SystemExit(0)))

    try:
        worker.main()
    except SystemExit:
        pass
    else:
        raise AssertionError("expected SystemExit from patched sleep")

    assert len(calls) == 3
