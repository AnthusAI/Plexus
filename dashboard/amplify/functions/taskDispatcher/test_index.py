import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load(monkeypatch):
    monkeypatch.setenv(
        "COMMAND_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/commands"
    )
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    path = Path(__file__).with_name("index.py")
    spec = importlib.util.spec_from_file_location("task_dispatcher_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _image(status="READY"):
    return {
        "id": {"S": "task-1"},
        "accountId": {"S": "account-1"},
        "dispatchStatus": {"S": status},
        "target": {"S": "evaluate"},
        "idempotencyKey": {"S": "key"},
        "createdAt": {"S": "2026-08-06T00:00:00Z"},
        "commandPayload": {
            "M": {
                "argv": {"L": [{"S": "evaluate"}]},
                "task_id": {"S": "task-1"},
            }
        },
    }


def _record(event_name="INSERT", old_status=None):
    data = {"NewImage": _image()}
    if old_status:
        data["OldImage"] = _image(old_status)
    return {
        "eventName": event_name,
        "dynamodb": data,
        "eventSourceARN": "arn:aws:dynamodb:us-east-1:1:table/Task/stream/x",
        "awsRegion": "us-east-1",
    }


def test_dispatches_only_initial_ready_eligibility(monkeypatch):
    module = _load(monkeypatch)
    sent, marked = [], []
    monkeypatch.setattr(
        module,
        "_celery",
        lambda: SimpleNamespace(
            send_task=lambda name, *, args: sent.append((name, args))
        ),
    )
    monkeypatch.setattr(
        module, "mark_dispatched", lambda _record, task_id: marked.append(task_id)
    )
    assert module.handler(
        {"Records": [_record(), _record("MODIFY", "READY")]}, None
    ) == {"processed": 1, "skipped": 1}
    assert sent == [
        (
            "plexus.command_worker.execute",
            [
                {
                    "schema_version": 2,
                    "command_id": "task-1",
                    "tenant_id": "account-1",
                    "target": "evaluate",
                    "idempotency_key": "key",
                    "created_at": "2026-08-06T00:00:00Z",
                    "payload": {"argv": ["evaluate"], "task_id": "task-1"},
                }
            ],
        )
    ]
    assert marked == ["task-1"]


def test_broker_or_post_publish_marker_failure_escapes_for_stream_retry(monkeypatch):
    module = _load(monkeypatch)
    monkeypatch.setattr(
        module,
        "_celery",
        lambda: SimpleNamespace(
            send_task=lambda *_a, **_k: (_ for _ in ()).throw(
                RuntimeError("broker down")
            )
        ),
    )
    with pytest.raises(RuntimeError, match="broker down"):
        module.handler({"Records": [_record()]}, None)
