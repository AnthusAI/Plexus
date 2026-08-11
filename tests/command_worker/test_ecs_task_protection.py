from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from plexus.command_worker.adapters.ecs_task_protection import (
    EcsAgentTaskScaleInProtection,
)
from plexus.command_worker.models import Claim, CommandEnvelope
from plexus.command_worker.worker import CommandWorker, ProcessOutcome


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_ecs_agent_protection_sets_and_clears_current_task(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        assert timeout == 5
        requests.append(request)
        return _Response()

    monkeypatch.setattr(
        "plexus.command_worker.adapters.ecs_task_protection.urlopen", fake_urlopen
    )
    protection = EcsAgentTaskScaleInProtection("http://169.254.170.2")

    assert protection.enable() is True
    assert protection.clear() is True
    assert [request.full_url for request in requests] == [
        "http://169.254.170.2/task-protection/v1/state",
        "http://169.254.170.2/task-protection/v1/state",
    ]
    assert json.loads(requests[0].data) == {
        "ProtectionEnabled": True,
        "ExpiresInMinutes": 2880,
    }
    assert json.loads(requests[1].data) == {"ProtectionEnabled": False}


@pytest.mark.parametrize("uri", ["", "169.254.170.2", "ftp://agent"])
def test_ecs_agent_protection_rejects_non_http_endpoint(uri) -> None:
    with pytest.raises(ValueError, match="ECS_AGENT_URI"):
        EcsAgentTaskScaleInProtection(uri)


class _Clock:
    def now(self):
        return datetime(2026, 8, 6, tzinfo=timezone.utc)


class _Delivery:
    envelope = CommandEnvelope(
        schema_version=2,
        command_id="c1",
        tenant_id="a1",
        target="evaluate",
        idempotency_key="evaluate:c1",
        created_at=datetime(2026, 8, 6, tzinfo=timezone.utc),
        payload={"argv": ["plexus", "evaluate"]},
    )
    released = False
    acknowledged = False

    def acknowledge(self):
        self.acknowledged = True

    def release(self):
        self.released = True

    def quarantine(self, _reason):
        raise AssertionError("unexpected quarantine")

    def extend_lease(self, _duration):
        return True


class _Store:
    def claim(self, _envelope, _owner, _now, _lease):
        return Claim(
            token="token",
            owner="worker",
            expires_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
        )

    def complete(self, *_args):
        return True

    def renew(self, _command_id, token, _now, _lease_duration):
        return Claim(
            token=token,
            owner="worker",
            expires_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
        )

    def fail(self, *_args):
        return True

    def finalize_cancel(self, *_args):
        return True


class _Executor:
    def __init__(self, events):
        self.events = events

    def execute(self, _envelope, _context):
        self.events.append("execute")
        return {"ok": True}


class _Protection:
    def __init__(self, events, enabled=True):
        self.events = events
        self.enabled = enabled

    def enable(self):
        self.events.append("enable")
        return self.enabled

    def clear(self):
        self.events.append("clear")
        return True


def test_worker_protects_before_execution_and_clears_terminal_task() -> None:
    events = []
    worker = CommandWorker(
        _Store(),
        _Executor(events),
        _Clock(),
        timedelta(minutes=5),
        task_scale_in_protection=_Protection(events),
    )
    delivery = _Delivery()

    assert worker.process(delivery, "worker") is ProcessOutcome.COMPLETED
    assert events == ["enable", "execute", "clear"]


def test_worker_releases_without_starting_if_scale_in_protection_cannot_enable() -> (
    None
):
    events = []
    worker = CommandWorker(
        _Store(),
        _Executor(events),
        _Clock(),
        timedelta(minutes=5),
        task_scale_in_protection=_Protection(events, enabled=False),
    )
    delivery = _Delivery()

    assert worker.process(delivery, "worker") is ProcessOutcome.LEASE_LOST
    assert delivery.released is True
    assert events == ["enable", "clear"]
