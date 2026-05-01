import importlib.util
import json
import sys
from pathlib import Path


def _load_module(monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "cache+memory://")
    module_path = Path(__file__).with_name("task_dispatcher.py")
    spec = importlib.util.spec_from_file_location("legacy_task_dispatcher_test", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _task_image(task_id, metadata=None):
    return {
        "id": {"S": task_id},
        "dispatchStatus": {"S": "PENDING"},
        "command": {"S": "procedure run proc-1"},
        "target": {"S": "procedure/run/proc-1"},
        "metadata": {"S": json.dumps(metadata or {})},
    }


def test_lambda_handler_skips_local_insert(monkeypatch):
    module = _load_module(monkeypatch)
    sent_tasks = []
    monkeypatch.setattr(module.celery_app, "send_task", lambda *args, **kwargs: sent_tasks.append((args, kwargs)))

    result = module.lambda_handler(
        {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": _task_image("task-local", metadata={"dispatch_mode": "local"}),
                    },
                }
            ]
        },
        None,
    )

    assert result == {"status": "done"}
    assert sent_tasks == []
