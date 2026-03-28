import asyncio
import json
import logging
import os
import socket
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from plexus.cli.shared.experiment_runner import run_experiment_with_task_tracking
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

    dequeued_at = _iso_now()
    metadata_with_dequeue = _merge_console_instrumentation(
        task,
        {
            "worker_dequeued_at": dequeued_at,
            "worker_run_id": run_id or None,
            "worker_node_id": worker_node_id,
        },
    )
    _task_update(
        task,
        status="RUNNING",
        dispatchStatus="DISPATCHED",
        startedAt=dequeued_at,
        workerNodeId=worker_node_id,
        metadata=json.dumps(metadata_with_dequeue),
    )

    init_done_at = _iso_now()
    metadata_init_done = _merge_console_instrumentation(
        task,
        {
            "worker_init_done_at": init_done_at,
        },
    )
    _task_update(
        task,
        metadata=json.dumps(metadata_init_done),
    )

    runtime_init_done_at = _iso_now()
    metadata_runtime_init = _merge_console_instrumentation(
        task,
        {
            "runtime_init_done_at": runtime_init_done_at,
        },
    )
    _task_update(
        task,
        metadata=json.dumps(metadata_runtime_init),
    )

    os.environ["PLEXUS_DISPATCH_TASK_ID"] = task_id
    try:
        result = asyncio.run(
            run_experiment_with_task_tracking(
                procedure_id=procedure_id,
                client=client,
                account_id=account_id,
            )
        )
        completed_at = _iso_now()
        metadata_completed = _merge_console_instrumentation(
            task,
            {
                "worker_run_completed_at": completed_at,
                "worker_result_status": result.get("status"),
            },
        )
        _task_update(
            task,
            metadata=json.dumps(metadata_completed),
            updatedAt=completed_at,
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
    finally:
        if os.environ.get("PLEXUS_DISPATCH_TASK_ID") == task_id:
            os.environ.pop("PLEXUS_DISPATCH_TASK_ID", None)


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
