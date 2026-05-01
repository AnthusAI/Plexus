import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_module(monkeypatch):
    monkeypatch.setenv("CELERY_AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("CELERY_AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("CELERY_AWS_REGION_NAME", "us-east-1")
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
