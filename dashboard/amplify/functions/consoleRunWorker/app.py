import asyncio
import json
import logging
import os
import socket
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

logger = logging.getLogger()
logger.setLevel(logging.INFO)


GET_TASK_QUERY = """
query GetTaskForConsoleWorker($id: ID!) {
  getTask(id: $id) {
    id
    accountId
    type
    status
    target
    command
    metadata
    dispatchStatus
  }
}
"""

UPDATE_TASK_MUTATION = """
mutation UpdateTaskForConsoleWorker($input: UpdateTaskInput!) {
  updateTask(input: $input) {
    id
    status
    dispatchStatus
    updatedAt
  }
}
"""


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


def _merge_console_instrumentation(task: Dict[str, Any], markers: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _parse_metadata(task.get("metadata"))
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


def _resolve_graphql_endpoint(payload: Dict[str, Any]) -> str:
    endpoint = str(payload.get("graphqlEndpoint") or "").strip()
    if endpoint:
        return endpoint
    endpoint = str(os.environ.get("PLEXUS_API_URL") or "").strip()
    if endpoint:
        return endpoint
    raise RuntimeError("Missing GraphQL endpoint for console worker")


def _resolve_region(payload: Dict[str, Any]) -> str:
    return (
        str(payload.get("awsRegion") or "").strip()
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-west-2"
    )


def _signed_graphql_request(
    *,
    endpoint: str,
    region: str,
    query: str,
    variables: Dict[str, Any],
) -> Dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables})
    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError(f"Invalid GraphQL endpoint: {endpoint}")

    request = AWSRequest(
        method="POST",
        url=endpoint,
        data=body,
        headers={"content-type": "application/json"},
    )
    credentials = boto3.Session().get_credentials()
    if credentials is None:
        raise RuntimeError("Unable to resolve AWS credentials for signed GraphQL request")
    SigV4Auth(credentials, "appsync", region).add_auth(request)
    prepared = request.prepare()

    response = requests.post(
        endpoint,
        headers=dict(prepared.headers.items()),
        data=body,
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"GraphQL HTTP {response.status_code}: {response.text}")
    payload = response.json()
    errors = payload.get("errors")
    if errors:
        raise RuntimeError(f"GraphQL errors: {errors}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"GraphQL response missing data: {payload}")
    return data


def _load_task(endpoint: str, region: str, task_id: str) -> Dict[str, Any]:
    data = _signed_graphql_request(
        endpoint=endpoint,
        region=region,
        query=GET_TASK_QUERY,
        variables={"id": task_id},
    )
    task = data.get("getTask")
    if not isinstance(task, dict):
        raise RuntimeError(f"Task {task_id} was not found")
    return task


def _task_update(
    *,
    endpoint: str,
    region: str,
    task: Dict[str, Any],
    status: Optional[str] = None,
    dispatch_status: Optional[str] = None,
    updated_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any] | str] = None,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    worker_node_id: Optional[str] = None,
    error_message: Optional[str] = None,
    error_details: Optional[str] = None,
    output: Optional[str] = None,
) -> None:
    input_payload: Dict[str, Any] = {
        "id": task["id"],
        "updatedAt": updated_at or _iso_now(),
    }
    for key in ("accountId", "type", "target", "command"):
        value = task.get(key)
        if value:
            input_payload[key] = value
    if status is not None:
        input_payload["status"] = status
    if dispatch_status is not None:
        input_payload["dispatchStatus"] = dispatch_status
    if started_at is not None:
        input_payload["startedAt"] = started_at
    if completed_at is not None:
        input_payload["completedAt"] = completed_at
    if worker_node_id is not None:
        input_payload["workerNodeId"] = worker_node_id
    if error_message is not None:
        input_payload["errorMessage"] = error_message
    if error_details is not None:
        input_payload["errorDetails"] = error_details
    if output is not None:
        input_payload["output"] = output
    if metadata is not None:
        input_payload["metadata"] = metadata if isinstance(metadata, str) else json.dumps(metadata)

    _signed_graphql_request(
        endpoint=endpoint,
        region=region,
        query=UPDATE_TASK_MUTATION,
        variables={"input": input_payload},
    )

    task.update(input_payload)


def _resolve_account_id(payload: Dict[str, Any], task: Dict[str, Any]) -> str:
    account_id = str(payload.get("accountId") or "").strip()
    if account_id:
        return account_id
    task_account_id = str(task.get("accountId") or "").strip()
    if task_account_id:
        return task_account_id
    raise RuntimeError("Missing accountId for console run payload")


class _SignedDashboardClient:
    """Minimal Dashboard client surface backed by SigV4 AppSync requests."""

    def __init__(self, *, endpoint: str, region: str, account_id: str):
        self.api_url = endpoint
        self.region = region
        self.account_id = account_id

    def _resolve_account_id(self) -> str:
        return self.account_id

    def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return _signed_graphql_request(
            endpoint=self.api_url,
            region=self.region,
            query=query,
            variables=variables or {},
        )


def _run_console_job(payload: Dict[str, Any]) -> None:
    task_id = str(payload.get("taskId") or "").strip()
    procedure_id = str(payload.get("procedureId") or "").strip()
    run_id = str(payload.get("runId") or "").strip()
    if not task_id or not procedure_id:
        raise RuntimeError("SQS payload must include taskId and procedureId")

    endpoint = _resolve_graphql_endpoint(payload)
    region = _resolve_region(payload)
    task = _load_task(endpoint, region, task_id)
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
        endpoint=endpoint,
        region=region,
        task=task,
        status="RUNNING",
        dispatch_status="DISPATCHED",
        started_at=startup_mark_at,
        worker_node_id=worker_node_id,
        metadata=metadata_with_dequeue,
    )

    previous_dispatch_task_id = os.environ.get("PLEXUS_DISPATCH_TASK_ID")
    os.environ["PLEXUS_DISPATCH_TASK_ID"] = task_id

    try:
        if not str(os.environ.get("OPENAI_API_KEY") or "").strip():
            raise RuntimeError(
                "OPENAI_API_KEY is not configured for console worker runtime"
            )

        from plexus.cli.procedure.service import ProcedureService

        execution_started_at = _iso_now()
        metadata_started = _merge_console_instrumentation(
            task,
            {
                "backend_execution_started_at": execution_started_at,
            },
        )
        _task_update(
            endpoint=endpoint,
            region=region,
            task=task,
            status="RUNNING",
            dispatch_status="DISPATCHED",
            metadata=metadata_started,
            updated_at=execution_started_at,
        )

        service = ProcedureService(
            _SignedDashboardClient(endpoint=endpoint, region=region, account_id=account_id)
        )
        result = asyncio.run(
            service.run_experiment(
                procedure_id,
                account_id=account_id,
                task_id=task_id,
            )
        )
        completed_at = _iso_now()
        result_status = str((result or {}).get("status") or "").upper()
        result_success = bool((result or {}).get("success"))

        if result_status == "WAITING_FOR_HUMAN":
            task_status = "RUNNING"
            completed_marker = None
        elif result_success:
            task_status = "COMPLETED"
            completed_marker = completed_at
        else:
            task_status = "FAILED"
            completed_marker = completed_at

        metadata_finished = _merge_console_instrumentation(
            task,
            {
                "worker_run_completed_at": completed_at,
            },
        )
        _task_update(
            endpoint=endpoint,
            region=region,
            task=task,
            status=task_status,
            dispatch_status="DISPATCHED",
            completed_at=completed_marker,
            metadata=metadata_finished,
            error_message=(result or {}).get("error") if task_status == "FAILED" else None,
            output=json.dumps(result, default=str),
            updated_at=completed_at,
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
            endpoint=endpoint,
            region=region,
            task=task,
            status="FAILED",
            dispatch_status="DISPATCHED",
            completed_at=failed_at,
            metadata=metadata_failed,
            error_message=str(exc),
            error_details=json.dumps(
                {
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
            ),
            updated_at=failed_at,
        )
        raise
    finally:
        if previous_dispatch_task_id is None:
            os.environ.pop("PLEXUS_DISPATCH_TASK_ID", None)
        else:
            os.environ["PLEXUS_DISPATCH_TASK_ID"] = previous_dispatch_task_id


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
