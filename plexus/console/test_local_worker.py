from __future__ import annotations

import pytest

from plexus.console import local_worker


class _StopWorker(Exception):
    pass


def test_summarize_exception_collapses_and_truncates_long_messages():
    message = "GraphQL query failed:\n" + ("x" * 600)

    summary = local_worker._summarize_exception(Exception(message))

    assert "\n" not in summary
    assert summary.startswith("GraphQL query failed:")
    assert len(summary) <= local_worker.MAX_ERROR_SUMMARY_LENGTH
    assert summary.endswith("…")


def test_continuous_worker_logs_compact_warning_and_backs_off(monkeypatch):
    sleep_calls = []
    warning_calls = []
    exception_calls = []

    monkeypatch.setattr(local_worker, "_load_local_env", lambda: None)
    monkeypatch.setattr(local_worker, "_resolve_client", lambda: object())
    monkeypatch.setattr(local_worker, "build_response_owner", lambda _target: "local:test")
    monkeypatch.setenv("CONSOLE_LOCAL_WORKER_ERROR_BACKOFF_SECONDS", "2.5")
    monkeypatch.setattr(local_worker.logger, "warning", lambda *args: warning_calls.append(args))
    monkeypatch.setattr(local_worker.logger, "exception", lambda *args: exception_calls.append(args))

    def fail_poll(*_args, **_kwargs):
        raise Exception("GraphQL query failed: DNS resolution failed")

    def stop_after_sleep(seconds):
        sleep_calls.append(seconds)
        raise _StopWorker()

    monkeypatch.setattr(local_worker, "process_pending_local_messages", fail_poll)
    monkeypatch.setattr(local_worker.time, "sleep", stop_after_sleep)

    with pytest.raises(_StopWorker):
        local_worker.main(response_target="local:test")

    assert sleep_calls == [2.5]
    assert len(warning_calls) == 1
    assert exception_calls == []
    message_template, summary, delay = warning_calls[0]
    assert "Local Console chat worker poll failed" in message_template
    assert summary == "GraphQL query failed: DNS resolution failed"
    assert delay == 2.5


def test_once_worker_preserves_exception_traceback_behavior(monkeypatch):
    exception_calls = []

    monkeypatch.setattr(local_worker, "_load_local_env", lambda: None)
    monkeypatch.setattr(local_worker, "_resolve_client", lambda: object())
    monkeypatch.setattr(local_worker, "build_response_owner", lambda _target: "local:test")
    monkeypatch.setattr(local_worker.logger, "exception", lambda *args: exception_calls.append(args))

    def fail_poll(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(local_worker, "process_pending_local_messages", fail_poll)

    with pytest.raises(RuntimeError, match="boom"):
        local_worker.main(response_target="local:test", once=True)

    assert exception_calls == [("Local Console chat worker poll failed",)]
