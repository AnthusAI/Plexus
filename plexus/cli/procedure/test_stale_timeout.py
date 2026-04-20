import json
from datetime import datetime, timedelta, timezone

from plexus.cli.procedure.stale_timeout import STALE_PROCEDURE_TIMEOUT_MESSAGE
from plexus.cli.procedure.stale_timeout import STALLED_STATUS
from plexus.cli.procedure.stale_timeout import timeout_stale_procedures


class _FakeTask:
    def __init__(self):
        self.id = "task-1"
        self.accountId = "acct-1"
        self.type = "Procedure Run"
        self.status = "RUNNING"
        self.target = "procedure/proc-stale"
        self.command = "procedure run proc-stale"
        self.metadata = json.dumps({"runtime": {"pid": 1234}})
        self.update_calls = []

    def update(self, **kwargs):
        self.update_calls.append(kwargs)
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self


def test_timeout_stale_procedures_marks_chat_silent_run_stalled(monkeypatch):
    now = datetime(2026, 4, 20, 18, 0, tzinfo=timezone.utc)
    fake_task = _FakeTask()
    stage_stalled_calls = []
    procedure_update_calls = []
    chat_session_stalled_calls = []

    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._list_procedure_tasks",
        lambda _client, _account_id: [
            {
                "id": "task-1",
                "status": "RUNNING",
                "target": "procedure/proc-stale",
                "metadata": json.dumps({}),
                "startedAt": "2026-04-20T15:00:00+00:00",
                "updatedAt": "2026-04-20T17:59:00Z",
            }
        ],
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._get_procedure_status_snapshot",
        lambda _client, _procedure_id: {
            "status": "RUNNING",
            "metadata": {"runtime": {"pid": 444, "host": "test-host"}},
        },
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._get_latest_chat_activity_at",
        lambda _client, _procedure_id: now - timedelta(hours=2),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout.Task.get_by_id",
        lambda _task_id, _client: fake_task,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._update_procedure_status_and_metadata",
        lambda client, procedure_id, **kwargs: procedure_update_calls.append((procedure_id, kwargs)),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._mark_procedure_chat_sessions_stalled",
        lambda _client, procedure_id: chat_session_stalled_calls.append(procedure_id),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._mark_nonterminal_task_stages_status",
        lambda _client, task_id, **kwargs: stage_stalled_calls.append((task_id, kwargs)),
    )

    result = timeout_stale_procedures(
        client=object(),
        account_id="acct-1",
        threshold_seconds=3600,
        lookback_hours=72,
        now=now,
    )

    assert result["recent_started_count"] == 1
    assert result["recent_started"][0]["procedure_id"] == "proc-stale"
    assert result["checked"] == 1
    assert len(result["timed_out"]) == 1
    assert fake_task.update_calls[-1]["status"] == STALLED_STATUS
    assert fake_task.update_calls[-1]["errorMessage"] == STALE_PROCEDURE_TIMEOUT_MESSAGE
    failure = json.loads(fake_task.update_calls[-1]["errorDetails"])
    assert failure["kind"] == "timeout"
    assert failure["last_chat_activity_at"] == "2026-04-20T16:00:00+00:00"
    assert stage_stalled_calls == [("task-1", {"status": STALLED_STATUS, "status_message": STALE_PROCEDURE_TIMEOUT_MESSAGE, "now": now})]
    assert chat_session_stalled_calls == ["proc-stale"]
    assert procedure_update_calls[0][0] == "proc-stale"
    assert procedure_update_calls[0][1]["status"] == STALLED_STATUS
    assert procedure_update_calls[0][1]["metadata_patch"]["last_failure"]["kind"] == "timeout"


def test_timeout_stale_procedures_skips_fresh_chat_activity(monkeypatch):
    now = datetime(2026, 4, 20, 18, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._list_procedure_tasks",
        lambda _client, _account_id: [
            {
                "id": "task-2",
                "status": "RUNNING",
                "target": "procedure/proc-fresh",
                "metadata": json.dumps({}),
                "startedAt": "2026-04-20T16:30:00+00:00",
                "updatedAt": "2026-04-20T17:59:00Z",
            }
        ],
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._get_procedure_status_snapshot",
        lambda _client, _procedure_id: {"status": "RUNNING", "metadata": {}},
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._get_latest_chat_activity_at",
        lambda _client, _procedure_id: now - timedelta(minutes=20),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout.Task.get_by_id",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Task.get_by_id should not run for fresh procedures")),
    )

    result = timeout_stale_procedures(
        client=object(),
        account_id="acct-1",
        threshold_seconds=3600,
        lookback_hours=72,
        now=now,
    )

    assert result["recent_started_count"] == 1
    assert result["checked"] == 1
    assert result["timed_out"] == []
    assert result["skipped"] == [
        {
            "procedure_id": "proc-fresh",
            "reason": "fresh_chat_activity",
            "last_activity_at": "2026-04-20T17:40:00+00:00",
            "activity_source": "chat",
        }
    ]


def test_timeout_stale_procedures_skips_waiting_for_human(monkeypatch):
    now = datetime(2026, 4, 20, 18, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._list_procedure_tasks",
        lambda _client, _account_id: [
            {
                "id": "task-3",
                "status": "RUNNING",
                "target": "procedure/proc-hitl",
                "metadata": json.dumps({}),
                "startedAt": "2026-04-20T14:00:00+00:00",
                "updatedAt": "2026-04-20T15:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._get_procedure_status_snapshot",
        lambda _client, _procedure_id: {"status": "WAITING_FOR_HUMAN", "metadata": {}},
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._get_latest_chat_activity_at",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("No chat lookup expected for WAITING_FOR_HUMAN")),
    )

    result = timeout_stale_procedures(
        client=object(),
        account_id="acct-1",
        threshold_seconds=3600,
        lookback_hours=72,
        now=now,
    )

    assert result["recent_started_count"] == 1
    assert result["checked"] == 1
    assert result["timed_out"] == []
    assert result["skipped"] == [{"procedure_id": "proc-hitl", "reason": "waiting_for_human"}]


def test_timeout_stale_procedures_excludes_runs_started_before_lookback(monkeypatch):
    now = datetime(2026, 4, 20, 18, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._list_procedure_tasks",
        lambda _client, _account_id: [
            {
                "id": "task-old",
                "status": "RUNNING",
                "target": "procedure/proc-old",
                "metadata": json.dumps({}),
                "startedAt": "2026-04-16T17:59:59+00:00",
                "updatedAt": "2026-04-20T17:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._get_procedure_status_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Should not inspect status for out-of-window runs")),
    )

    result = timeout_stale_procedures(
        client=object(),
        account_id="acct-1",
        threshold_seconds=3600,
        lookback_hours=72,
        now=now,
    )

    assert result["recent_started_count"] == 0
    assert result["recent_started"] == []
    assert result["checked"] == 0
    assert result["timed_out"] == []


def test_timeout_stale_procedures_times_out_no_chat_when_started_is_stale(monkeypatch):
    now = datetime(2026, 4, 20, 18, 0, tzinfo=timezone.utc)
    fake_task = _FakeTask()
    fake_task.id = "task-no-chat"
    fake_task.target = "procedure/proc-no-chat"
    fake_task.command = "procedure run proc-no-chat"
    stage_stalled_calls = []

    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._list_procedure_tasks",
        lambda _client, _account_id: [
            {
                "id": "task-no-chat",
                "status": "RUNNING",
                "target": "procedure/proc-no-chat",
                "metadata": json.dumps({}),
                "startedAt": "2026-04-20T15:00:00+00:00",
                "updatedAt": "2026-04-20T15:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._get_procedure_status_snapshot",
        lambda _client, _procedure_id: {"status": "RUNNING", "metadata": {}},
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._get_latest_chat_activity_at",
        lambda _client, _procedure_id: None,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout.Task.get_by_id",
        lambda _task_id, _client: fake_task,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._update_procedure_status_and_metadata",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._mark_procedure_chat_sessions_stalled",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._mark_nonterminal_task_stages_status",
        lambda _client, task_id, **kwargs: stage_stalled_calls.append((task_id, kwargs)),
    )

    result = timeout_stale_procedures(
        client=object(),
        account_id="acct-1",
        threshold_seconds=3600,
        lookback_hours=72,
        now=now,
    )

    assert result["checked"] == 1
    assert len(result["timed_out"]) == 1
    assert result["timed_out"][0]["failure"]["activity_source"] == "task_started_at"
    assert json.loads(fake_task.update_calls[-1]["errorDetails"])["activity_source"] == "task_started_at"
    assert stage_stalled_calls == [("task-no-chat", {"status": STALLED_STATUS, "status_message": STALE_PROCEDURE_TIMEOUT_MESSAGE, "now": now})]


def test_timeout_stale_procedures_continues_when_procedure_update_conflicts(monkeypatch):
    now = datetime(2026, 4, 20, 18, 0, tzinfo=timezone.utc)
    fake_task = _FakeTask()

    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._list_procedure_tasks",
        lambda _client, _account_id: [
            {
                "id": "task-1",
                "status": "RUNNING",
                "target": "procedure/proc-conflict",
                "metadata": json.dumps({}),
                "startedAt": "2026-04-20T15:00:00+00:00",
                "updatedAt": "2026-04-20T15:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._get_procedure_status_snapshot",
        lambda _client, _procedure_id: {"status": "RUNNING", "metadata": {}},
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._get_latest_chat_activity_at",
        lambda _client, _procedure_id: None,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout.Task.get_by_id",
        lambda _task_id, _client: fake_task,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._update_procedure_status_and_metadata",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(Exception("conditional check failed")),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._mark_procedure_chat_sessions_stalled",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.stale_timeout._mark_nonterminal_task_stages_status",
        lambda *_args, **_kwargs: None,
    )

    result = timeout_stale_procedures(
        client=object(),
        account_id="acct-1",
        threshold_seconds=3600,
        lookback_hours=72,
        now=now,
    )

    assert len(result["timed_out"]) == 1
    assert "warnings" in result["timed_out"][0]
    assert "procedure_update_failed" in result["timed_out"][0]["warnings"][0]
