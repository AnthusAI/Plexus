from pathlib import Path
from types import SimpleNamespace

import click

from plexus.cli.chat import worker


def test_create_chat_worker_client_accepts_next_public_env(monkeypatch):
    created = []

    class FakeClient:
        def __init__(self, *, api_url, api_key):
            created.append((api_url, api_key))

    monkeypatch.delenv("PLEXUS_API_URL", raising=False)
    monkeypatch.delenv("PLEXUS_API_KEY", raising=False)
    monkeypatch.setenv("NEXT_PUBLIC_PLEXUS_API_URL", "https://example.appsync-api.us-east-1.amazonaws.com/graphql")
    monkeypatch.setenv("NEXT_PUBLIC_PLEXUS_API_KEY", "da2-test")
    monkeypatch.setattr(worker, "PlexusDashboardClient", FakeClient)

    worker.create_chat_worker_client()

    assert created == [("https://example.appsync-api.us-east-1.amazonaws.com/graphql", "da2-test")]


def test_load_chat_worker_env_reads_repo_and_dashboard_env_files(monkeypatch):
    loaded_calls: list[tuple[Path, bool]] = []
    repo_root = Path("/repo")
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

    worker.load_chat_worker_env(repo_root)

    assert [str(path) for path, _ in loaded_calls] == [str(path) for path in expected_order]
    assert [override for _, override in loaded_calls] == [False, True, True]


def test_resolve_chat_worker_target_rejects_cloud(monkeypatch):
    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "cloud")

    try:
        worker.resolve_chat_worker_target()
    except click.ClickException as exc:
        assert "local:<name>" in str(exc)
    else:
        raise AssertionError("expected ClickException")


def test_run_chat_worker_uses_next_public_response_target(monkeypatch):
    calls = []
    results = iter([1, 0])

    monkeypatch.delenv("CONSOLE_RESPONSE_TARGET", raising=False)
    monkeypatch.setenv("NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET", "local:ryan")
    monkeypatch.setattr(
        worker,
        "process_pending_local_messages",
        lambda _client, **kwargs: calls.append(kwargs) or next(results),
    )
    monkeypatch.setattr(worker.time, "sleep", lambda _secs: (_ for _ in ()).throw(SystemExit(0)))

    try:
        worker.run_chat_worker(
            poll_interval=0.2,
            client_factory=lambda: SimpleNamespace(),
            load_env=False,
        )
    except SystemExit:
        pass
    else:
        raise AssertionError("expected SystemExit from patched sleep")

    assert len(calls) == 2
    assert calls[0]["response_target"] == "local:ryan"


def test_run_chat_worker_processes_pending_messages_with_local_owner(monkeypatch):
    calls = []
    results = iter([1, 0])

    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "local:ryan")
    monkeypatch.setattr(
        worker,
        "process_pending_local_messages",
        lambda _client, **kwargs: calls.append(kwargs) or next(results),
    )
    monkeypatch.setattr(worker.time, "sleep", lambda _secs: (_ for _ in ()).throw(SystemExit(0)))

    try:
        worker.run_chat_worker(
            poll_interval=0.2,
            client_factory=lambda: SimpleNamespace(),
            load_env=False,
        )
    except SystemExit:
        pass
    else:
        raise AssertionError("expected SystemExit from patched sleep")

    assert len(calls) == 2
    assert calls[0]["response_target"] == "local:ryan"
    assert calls[0]["limit"] == 5
    assert calls[0]["owner"].startswith("local:ryan:")


def test_run_chat_worker_drain_mode_only_sleeps_when_no_work(monkeypatch):
    calls = []
    results = iter([1, 1, 0])

    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "local:ryan")
    monkeypatch.setattr(
        worker,
        "process_pending_local_messages",
        lambda _client, **kwargs: calls.append(kwargs) or next(results),
    )
    monkeypatch.setattr(worker.time, "sleep", lambda _secs: (_ for _ in ()).throw(SystemExit(0)))

    try:
        worker.run_chat_worker(
            poll_interval=0.2,
            client_factory=lambda: SimpleNamespace(),
            load_env=False,
        )
    except SystemExit:
        pass
    else:
        raise AssertionError("expected SystemExit from patched sleep")

    assert len(calls) == 3
