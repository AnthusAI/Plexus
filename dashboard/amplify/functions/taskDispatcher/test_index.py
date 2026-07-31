import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_module(monkeypatch):
    monkeypatch.setenv("CELERY_AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("CELERY_AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("CELERY_AWS_REGION_NAME", "us-east-1")
    monkeypatch.setenv("CELERY_QUEUE_NAME", "plexus-celery-test")
    monkeypatch.setenv("CELERY_RESULT_BACKEND_TEMPLATE", "dynamodb://@")

    module_path = Path(__file__).with_name("index.py")
    spec = importlib.util.spec_from_file_location("task_dispatcher_index_test", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _task_image(task_id, dispatch_status="PENDING", metadata=None):
    return {
        "id": {"S": task_id},
        "dispatchStatus": {"S": dispatch_status},
        "command": {"S": "procedure run proc-1"},
        "target": {"S": "procedure/run/proc-1"},
        "metadata": {"S": json.dumps(metadata or {})},
    }


def _modify_record(task_id, old_status, new_status, metadata):
    return {
        "eventID": "1",
        "eventName": "MODIFY",
        "awsRegion": "us-east-1",
        "eventSourceARN": (
            "arn:aws:dynamodb:us-east-1:123456789012:"
            "table/Task-test-NONE/stream/2026-07-30T00:00:00.000"
        ),
        "dynamodb": {
            "OldImage": _task_image(task_id, dispatch_status=old_status, metadata=metadata),
            "NewImage": _task_image(task_id, dispatch_status=new_status, metadata=metadata),
        },
    }


def test_handler_skips_local_insert(monkeypatch):
    module = _load_module(monkeypatch)
    sent_tasks = []
    monkeypatch.setattr(module.celery_app, "send_task", lambda *args, **kwargs: sent_tasks.append((args, kwargs)))

    result = module.handler(
        {
            "Records": [
                {
                    "eventID": "1",
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": _task_image("task-local", metadata={"dispatch_mode": "local"}),
                    },
                }
            ]
        },
        SimpleNamespace(aws_request_id="request-1"),
    )

    assert result["processed"] == 0
    assert result["skipped"] == 1
    assert sent_tasks == []


def test_handler_skips_local_modify_to_pending(monkeypatch):
    module = _load_module(monkeypatch)
    sent_tasks = []
    monkeypatch.setattr(module.celery_app, "send_task", lambda *args, **kwargs: sent_tasks.append((args, kwargs)))

    result = module.handler(
        {
            "Records": [
                {
                    "eventID": "1",
                    "eventName": "MODIFY",
                    "dynamodb": {
                        "OldImage": _task_image("task-local", dispatch_status="LOCAL", metadata={"dispatch_mode": "local"}),
                        "NewImage": _task_image("task-local", dispatch_status="PENDING", metadata={"dispatch_mode": "local"}),
                    },
                }
            ]
        },
        SimpleNamespace(aws_request_id="request-1"),
    )

    assert result["processed"] == 0
    assert result["skipped"] == 1
    assert sent_tasks == []


def test_held_once_task_dispatches_only_on_literal_held_to_pending_modify(monkeypatch):
    module = _load_module(monkeypatch)
    sent_tasks = []
    updates = []

    class FakeTable:
        def update_item(self, **kwargs):
            updates.append(kwargs)

    monkeypatch.setattr(module, "_task_table", lambda _record: FakeTable())
    monkeypatch.setattr(
        module.celery_app,
        "send_task",
        lambda *args, **kwargs: (
            sent_tasks.append((args, kwargs)) or SimpleNamespace(id="celery-1")
        ),
    )

    result = module.handler(
        {"Records": [_modify_record(
            "task-held-once", "HELD", "PENDING", {"dispatch_policy": "held_once"}
        )]},
        SimpleNamespace(aws_request_id="request-1"),
    )

    assert result["processed"] == 1
    assert result["skipped"] == 0
    assert len(sent_tasks) == 1
    assert len(updates) == 2


@pytest.mark.parametrize("old_status", ["PENDING", "DISPATCHING"])
def test_held_once_racing_or_replayed_pending_transition_never_sends(monkeypatch, old_status):
    module = _load_module(monkeypatch)
    sent_tasks = []
    monkeypatch.setattr(
        module.celery_app,
        "send_task",
        lambda *args, **kwargs: sent_tasks.append((args, kwargs)),
    )

    result = module.handler(
        {"Records": [_modify_record(
            "task-held-once", old_status, "PENDING", {"dispatch_policy": "held_once"}
        )]},
        SimpleNamespace(aws_request_id="request-1"),
    )

    assert result["processed"] == 0
    assert result["skipped"] == 1
    assert sent_tasks == []


def test_held_once_pending_insert_never_sends(monkeypatch):
    module = _load_module(monkeypatch)
    sent_tasks = []
    monkeypatch.setattr(
        module.celery_app,
        "send_task",
        lambda *args, **kwargs: sent_tasks.append((args, kwargs)),
    )

    result = module.handler(
        {"Records": [{
            "eventID": "1",
            "eventName": "INSERT",
            "dynamodb": {"NewImage": _task_image(
                "task-held-once", metadata={"dispatch_policy": "held_once"}
            )},
        }]},
        SimpleNamespace(aws_request_id="request-1"),
    )

    assert result["processed"] == 0
    assert result["skipped"] == 1
    assert sent_tasks == []


@pytest.mark.parametrize("old_status", ["WAITING_FOR_CHILDREN", "WAITING_FOR_TIME"])
def test_resume_once_task_dispatches_only_on_literal_waiting_to_pending_modify(
    monkeypatch, old_status,
):
    module = _load_module(monkeypatch)
    sent_tasks = []
    monkeypatch.setattr(module, "_task_table", lambda _record: SimpleNamespace(update_item=lambda **_kwargs: None))
    monkeypatch.setattr(
        module.celery_app,
        "send_task",
        lambda *args, **kwargs: (
            sent_tasks.append((args, kwargs)) or SimpleNamespace(id="celery-resume")
        ),
    )

    result = module.handler(
        {"Records": [_modify_record(
            "parent-task", old_status, "PENDING",
            {"dispatch_policy": "resume_once"},
        )]},
        SimpleNamespace(aws_request_id="request-1"),
    )

    assert result["processed"] == 1
    assert len(sent_tasks) == 1


@pytest.mark.parametrize(
    "event_name,old_status",
    [("INSERT", None), ("MODIFY", "PENDING"), ("MODIFY", "DISPATCHING"), ("MODIFY", "DISPATCHED")],
)
def test_resume_once_duplicate_or_racing_ticks_never_send(
    monkeypatch, event_name, old_status,
):
    module = _load_module(monkeypatch)
    sent_tasks = []
    monkeypatch.setattr(module.celery_app, "send_task", lambda *args, **kwargs: sent_tasks.append((args, kwargs)))
    if event_name == "INSERT":
        record = {
            "eventID": "1",
            "eventName": "INSERT",
            "dynamodb": {"NewImage": _task_image(
                "parent-task", metadata={"dispatch_policy": "resume_once"},
            )},
        }
    else:
        record = _modify_record(
            "parent-task", old_status, "PENDING", {"dispatch_policy": "resume_once"},
        )

    result = module.handler(
        {"Records": [record]}, SimpleNamespace(aws_request_id="request-1"),
    )

    assert result["processed"] == 0
    assert result["skipped"] == 1
    assert sent_tasks == []
