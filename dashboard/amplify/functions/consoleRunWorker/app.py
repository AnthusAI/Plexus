import json
import logging
import os
import socket
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery import Celery
from kombu.utils.url import safequote
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.task import Task

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_metadata(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _merge_console_instrumentation(task: Task, markers: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _parse_metadata(task.metadata)
    console_chat = metadata.get("console_chat")
    if not isinstance(console_chat, dict):
        console_chat = {}
        metadata["console_chat"] = console_chat

    instrumentation = console_chat.get("instrumentation")
    if not isinstance(instrumentation, dict):
        instrumentation = {}
        console_chat["instrumentation"] = instrumentation

    instrumentation.update(markers)
    return metadata


def _task_update(task: Task, **updates: Any) -> None:
    payload = {
        "accountId": task.accountId,
        "type": task.type,
        "status": updates.pop("status", task.status),
        "target": task.target,
        "command": task.command,
        "updatedAt": updates.pop("updatedAt", _iso_now()),
    }
    payload.update(updates)
    task.update(**payload)

    if "status" in payload:
        task.status = payload["status"]
    if "metadata" in payload:
        task.metadata = payload["metadata"]
    if "dispatchStatus" in payload:
        task.dispatchStatus = payload["dispatchStatus"]


def _load_task(client: PlexusDashboardClient, task_id: str) -> Task:
    task = Task.get_by_id(task_id, client)
    if not task:
        raise RuntimeError(f"Task {task_id} was not found")
    return task


def _resolve_account_id(payload: Dict[str, Any], task: Task) -> str:
    account_id = str(payload.get("accountId") or "").strip()
    if account_id:
        return account_id
    if task.accountId:
        return str(task.accountId).strip()
    raise RuntimeError("Missing accountId for console run payload")


def _is_placeholder(value: Optional[str]) -> bool:
    raw = (value or "").strip()
    return (not raw) or raw.upper().startswith("WILL_BE_SET_AFTER_DEPLOYMENT")


def _build_celery_app() -> tuple[Celery, str]:
    queue_name = (os.environ.get("CELERY_QUEUE_NAME") or "plexus-celery-development").strip()
    aws_region = (
        os.environ.get("CELERY_AWS_REGION_NAME")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-west-2"
    ).strip()

    access_key = (os.environ.get("CELERY_AWS_ACCESS_KEY_ID") or "").strip()
    secret_key = (os.environ.get("CELERY_AWS_SECRET_ACCESS_KEY") or "").strip()

    if _is_placeholder(access_key) or _is_placeholder(secret_key):
        # Prefer IAM role credentials in Amplify/Lambda.
        broker_url = f"sqs:///{queue_name}"
    else:
        broker_url = f"sqs://{safequote(access_key)}:{safequote(secret_key)}@/{queue_name}"

    backend_template = (os.environ.get("CELERY_RESULT_BACKEND_TEMPLATE") or "").strip()
    if _is_placeholder(backend_template):
        backend_url = "rpc://"
    elif ("{aws_access_key}" in backend_template and "{aws_secret_key}" in backend_template) and (
        _is_placeholder(access_key) or _is_placeholder(secret_key)
    ):
        backend_url = "rpc://"
    elif "{aws_access_key}" in backend_template or "{aws_secret_key}" in backend_template:
        backend_url = backend_template.format(
            aws_access_key=safequote(access_key),
            aws_secret_key=safequote(secret_key),
            aws_region_name=aws_region,
        )
    elif "{aws_region_name}" in backend_template:
        backend_url = backend_template.format(aws_region_name=aws_region)
    else:
        backend_url = backend_template or "rpc://"

    app = Celery(
        "plexus",
        broker=broker_url,
        backend=backend_url,
        broker_transport_options={"region": aws_region, "is_secure": True},
    )
    app.conf.update(
        broker_connection_retry_on_startup=True,
        task_default_queue=queue_name,
    )
    return app, queue_name


def _run_console_job(payload: Dict[str, Any]) -> None:
    task_id = str(payload.get("taskId") or "").strip()
    procedure_id = str(payload.get("procedureId") or "").strip()
    run_id = str(payload.get("runId") or "").strip()
    if not task_id or not procedure_id:
        raise RuntimeError("SQS payload must include taskId and procedureId")

    client = PlexusDashboardClient()
    task = _load_task(client, task_id)
    account_id = _resolve_account_id(payload, task)
    worker_node_id = f"console-run-worker/{socket.gethostname()}"

    startup_mark_at = _iso_now()
    metadata_with_dequeue = _merge_console_instrumentation(
        task,
        {
            "worker_dequeued_at": startup_mark_at,
            "worker_run_id": run_id or None,
            "worker_node_id": worker_node_id,
            "worker_init_done_at": startup_mark_at,
            "runtime_init_done_at": startup_mark_at,
        },
    )
    _task_update(
        task,
        status="RUNNING",
        dispatchStatus="DISPATCHED",
        startedAt=startup_mark_at,
        workerNodeId=worker_node_id,
        metadata=json.dumps(metadata_with_dequeue),
    )

    try:
        celery_app, queue_name = _build_celery_app()
        command = f"procedure run {procedure_id}"
        target = f"procedure/run/{procedure_id}"
        celery_result = celery_app.send_task(
            "plexus.execute_command",
            args=[command],
            kwargs={"target": target, "task_id": task_id},
        )
        dispatched_at = _iso_now()
        metadata_dispatched = _merge_console_instrumentation(
            task,
            {
                "worker_dispatched_to_celery_at": dispatched_at,
                "worker_celery_task_id": getattr(celery_result, "id", None),
                "worker_celery_queue_name": queue_name,
            },
        )
        _task_update(
            task,
            status="RUNNING",
            dispatchStatus="DISPATCHED",
            metadata=json.dumps(metadata_dispatched),
            updatedAt=dispatched_at,
        )
    except Exception as exc:
        failed_at = _iso_now()
        metadata_failed = _merge_console_instrumentation(
            task,
            {
                "worker_run_failed_at": failed_at,
            },
        )
        _task_update(
            task,
            status="FAILED",
            dispatchStatus="DISPATCHED",
            completedAt=failed_at,
            metadata=json.dumps(metadata_failed),
            errorMessage=str(exc),
            errorDetails=json.dumps(
                {
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
            ),
            updatedAt=failed_at,
        )
        raise


def handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    records = event.get("Records") or []
    if not records:
        logger.info("No SQS records to process")
        return {"processed": 0}

    failures = []
    processed = 0

    for record in records:
        message_id = str(record.get("messageId") or "")
        body = record.get("body")
        try:
            payload = json.loads(body) if isinstance(body, str) else {}
            if not isinstance(payload, dict):
                raise RuntimeError("SQS body must decode to a JSON object")
            _run_console_job(payload)
            processed += 1
        except Exception as exc:
            logger.error("Failed processing console run record %s: %s", message_id, exc, exc_info=True)
            failures.append({"itemIdentifier": message_id})

    return {
        "processed": processed,
        "batchItemFailures": failures,
    }
