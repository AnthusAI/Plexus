from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_direct_local_run_waits_and_continues_the_exact_deferred_procedure(monkeypatch):
    from plexus.cli.procedure.procedures import (
        _run_local_procedure_through_scheduled_continuations,
    )

    calls = []
    results = iter([
        {
            "status": "WAITING_FOR_TIME",
            "procedure_id": "procedure-1",
            "task_id": "task-1",
            "request": {
                "key": "report-publication",
                "resume_at": "2026-07-31T17:05:23Z",
                "reason": "retryable_report_publication",
            },
        },
        {"status": "COMPLETED", "procedure_id": "procedure-1", "task_id": "task-1"},
    ])

    async def run_once(**kwargs):
        calls.append({
            "kwargs": kwargs,
            "dispatch_task_id": __import__("os").environ.get("PLEXUS_DISPATCH_TASK_ID"),
            "local_dispatch": __import__("os").environ.get("PLEXUS_LOCAL_DISPATCH"),
        })
        return next(results)

    resumed = []

    def resume_exact(_client, procedure_id):
        resumed.append(procedure_id)
        return {"resumed": True, "status": "PENDING"}

    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.delenv("PLEXUS_DISPATCH_TASK_ID", raising=False)
    monkeypatch.delenv("PLEXUS_LOCAL_DISPATCH", raising=False)
    result = await _run_local_procedure_through_scheduled_continuations(
        run_once=run_once,
        run_kwargs={"procedure_id": "procedure-1", "client": object()},
        client=object(),
        procedure_id="procedure-1",
        enabled=True,
        resume_exact=resume_exact,
        sleep=sleep,
        now=lambda: datetime(2026, 7, 31, 17, 5, 23, tzinfo=timezone.utc),
    )

    assert result["status"] == "COMPLETED"
    assert resumed == ["procedure-1"]
    assert sleeps == []
    assert len(calls) == 2
    assert calls[0]["dispatch_task_id"] is None
    assert calls[1]["dispatch_task_id"] == "task-1"
    assert calls[1]["local_dispatch"] == "1"
    assert "PLEXUS_DISPATCH_TASK_ID" not in __import__("os").environ
    assert "PLEXUS_LOCAL_DISPATCH" not in __import__("os").environ


@pytest.mark.asyncio
async def test_nonlocal_run_leaves_scheduled_continuation_to_its_dispatch_host():
    from plexus.cli.procedure.procedures import (
        _run_local_procedure_through_scheduled_continuations,
    )

    calls = 0

    async def run_once(**_kwargs):
        nonlocal calls
        calls += 1
        return {
            "status": "WAITING_FOR_TIME",
            "procedure_id": "procedure-1",
            "task_id": "task-1",
            "request": {
                "key": "report-publication",
                "resume_at": "2026-07-31T17:05:23Z",
                "reason": "retryable_report_publication",
            },
        }

    result = await _run_local_procedure_through_scheduled_continuations(
        run_once=run_once,
        run_kwargs={},
        client=object(),
        procedure_id="procedure-1",
        enabled=False,
        resume_exact=lambda *_args: pytest.fail("nonlocal run must not be resumed here"),
        sleep=lambda _seconds: pytest.fail("nonlocal run must not sleep here"),
    )

    assert result["status"] == "WAITING_FOR_TIME"
    assert calls == 1


@pytest.mark.asyncio
async def test_direct_local_run_fails_closed_on_malformed_scheduled_boundary():
    from plexus.cli.procedure.procedures import (
        _run_local_procedure_through_scheduled_continuations,
    )

    async def run_once(**_kwargs):
        return {
            "status": "WAITING_FOR_TIME",
            "procedure_id": "procedure-1",
            "task_id": "task-1",
            "request": {"resume_at": "not-a-time"},
        }

    result = await _run_local_procedure_through_scheduled_continuations(
        run_once=run_once,
        run_kwargs={},
        client=object(),
        procedure_id="procedure-1",
        enabled=True,
        resume_exact=lambda *_args: pytest.fail("malformed wait must not be resumed"),
        sleep=lambda _seconds: pytest.fail("malformed wait must not sleep"),
    )

    assert result["status"] == "WAITING_FOR_TIME"
    assert result["continuation_error"] == "scheduled_continuation_boundary_invalid"
