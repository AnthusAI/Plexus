from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from botocore.exceptions import ClientError


def _load_module():
    module_path = Path(__file__).with_name("index.py")
    spec = importlib.util.spec_from_file_location("task_dispatcher_index", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _stream_insert_record():
    return {
        "eventID": "evt-1",
        "eventName": "INSERT",
        "eventSourceARN": (
            "arn:aws:dynamodb:us-west-2:123456789012:"
            "table/Task-test-NONE/stream/2026-05-05T00:00:00.000"
        ),
        "dynamodb": {
            "NewImage": {
                "id": {"S": "task-1"},
                "dispatchStatus": {"S": "PENDING"},
                "command": {"S": "feedback report run-programmatic-block --payload-base64 abc"},
                "target": {"S": "report/block/test"},
            }
        },
    }


def test_handler_logs_decimal_task_without_crashing(monkeypatch):
    monkeypatch.setenv("CELERY_AWS_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("CELERY_AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("CELERY_AWS_REGION_NAME", "us-west-2")
    monkeypatch.setenv("CELERY_QUEUE_NAME", "plexus-celery-staging")
    monkeypatch.setenv(
        "CELERY_RESULT_BACKEND_TEMPLATE",
        "db+postgresql://{aws_access_key}:{aws_secret_key}@localhost/test",
    )
    module = _load_module()

    sent = {}

    class FakeResult:
        id = "celery-task-1"

    def fake_send_task(name, args=None, kwargs=None):
        sent["name"] = name
        sent["args"] = args
        sent["kwargs"] = kwargs
        return FakeResult()

    monkeypatch.setattr(module, "deserialize_dynamo_item", lambda _item: {
        "id": "task-1",
        "dispatchStatus": "PENDING",
        "command": "feedback report run-programmatic-block --payload-base64 abc",
        "target": "report/block/test",
        "ttl_hours": Decimal("24"),
    })
    monkeypatch.setattr(module.celery_app, "send_task", fake_send_task)

    updates = []

    class FakeTable:
        def update_item(self, **kwargs):
            updates.append(kwargs)

    monkeypatch.setattr(
        module,
        "dynamodb",
        SimpleNamespace(Table=lambda table_name: FakeTable()),
    )

    result = module.handler(
        {"Records": [_stream_insert_record()]},
        SimpleNamespace(aws_request_id="req-1"),
    )

    assert result == {"status": "done", "processed": 1, "skipped": 0, "errors": 0}
    assert sent["name"] == "plexus.execute_command"
    assert sent["args"] == ["feedback report run-programmatic-block --payload-base64 abc"]
    assert sent["kwargs"] == {"target": "report/block/test", "task_id": "task-1"}
    assert len(updates) == 2
    assert updates[0]["Key"] == {"id": "task-1"}
    assert updates[0]["ConditionExpression"] == "#expectedDispatchStatus = :expectedDispatchStatus"
    assert updates[0]["ExpressionAttributeValues"][":expectedDispatchStatus"] == "PENDING"
    assert "DISPATCHING" in updates[0]["ExpressionAttributeValues"].values()
    assert "DISPATCHED" in updates[1]["ExpressionAttributeValues"].values()
    assert "celery-task-1" in updates[1]["ExpressionAttributeValues"].values()


def test_handler_skips_already_claimed_task_without_sending(monkeypatch):
    monkeypatch.setenv("CELERY_AWS_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("CELERY_AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("CELERY_AWS_REGION_NAME", "us-west-2")
    monkeypatch.setenv("CELERY_QUEUE_NAME", "plexus-celery-staging")
    monkeypatch.setenv(
        "CELERY_RESULT_BACKEND_TEMPLATE",
        "db+postgresql://{aws_access_key}:{aws_secret_key}@localhost/test",
    )
    module = _load_module()

    sent = {}

    def fake_send_task(name, args=None, kwargs=None):
        sent["name"] = name
        return SimpleNamespace(id="celery-task-1")

    monkeypatch.setattr(module, "deserialize_dynamo_item", lambda _item: {
        "id": "task-1",
        "dispatchStatus": "PENDING",
        "command": "feedback report run-programmatic-block --payload-base64 abc",
        "target": "report/block/test",
    })
    monkeypatch.setattr(module.celery_app, "send_task", fake_send_task)

    class FakeTable:
        def update_item(self, **kwargs):
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}},
                "UpdateItem",
            )

    monkeypatch.setattr(
        module,
        "dynamodb",
        SimpleNamespace(Table=lambda table_name: FakeTable()),
    )

    result = module.handler(
        {"Records": [_stream_insert_record()]},
        SimpleNamespace(aws_request_id="req-1"),
    )

    assert result == {"status": "done", "processed": 0, "skipped": 1, "errors": 0}
    assert sent == {}


def test_module_rejects_placeholder_dispatch_config(monkeypatch):
    monkeypatch.setenv("CELERY_AWS_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("CELERY_AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("CELERY_AWS_REGION_NAME", "us-west-2")
    monkeypatch.setenv("CELERY_QUEUE_NAME", "plexus-celery-staging")
    monkeypatch.setenv("CELERY_RESULT_BACKEND_TEMPLATE", "WILL_BE_SET_AFTER_DEPLOYMENT")

    try:
        _load_module()
    except ValueError as exc:
        assert "CELERY_RESULT_BACKEND_TEMPLATE" in str(exc)
    else:
        raise AssertionError("placeholder dispatch config should fail module import")
