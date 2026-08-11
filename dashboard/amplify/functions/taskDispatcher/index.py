"""Publish typed command envelopes from Task stream eligibility transitions."""

import json
import os
from typing import Any, Mapping

from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from celery import Celery

READY = "READY"
DISPATCHED = "DISPATCHED"
TASK_NAME = "plexus.command_worker.execute"
_deserializer = TypeDeserializer()


def deserialize_dynamo_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _deserializer.deserialize(value) for key, value in item.items()}


def envelope(task: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "id",
        "accountId",
        "target",
        "idempotencyKey",
        "createdAt",
        "commandPayload",
    )
    missing = [field for field in required if task.get(field) is None]
    if missing:
        raise ValueError("READY Task is missing " + ", ".join(missing))
    payload = task["commandPayload"]
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("READY Task commandPayload is not valid JSON") from error
    if not isinstance(payload, Mapping):
        raise ValueError("READY Task commandPayload must be a JSON object")
    return {
        "schema_version": 2,
        "command_id": task["id"],
        "tenant_id": task["accountId"],
        "target": task["target"],
        "idempotency_key": task["idempotencyKey"],
        "created_at": task["createdAt"],
        "payload": dict(payload),
    }


def _eligible(record: Mapping[str, Any]) -> bool:
    new_image = record.get("dynamodb", {}).get("NewImage")
    if (
        not isinstance(new_image, Mapping)
        or deserialize_dynamo_item(new_image).get("dispatchStatus") != READY
    ):
        return False
    if record.get("eventName") == "INSERT":
        return True
    old_image = record.get("dynamodb", {}).get("OldImage")
    return (
        record.get("eventName") == "MODIFY"
        and isinstance(old_image, Mapping)
        and deserialize_dynamo_item(old_image).get("dispatchStatus") != READY
    )


def _task_table(record: Mapping[str, Any]):
    stream_arn = str(record.get("eventSourceARN") or "")
    if ":table/" not in stream_arn or not record.get("awsRegion"):
        raise ValueError("Task stream record is missing its table identity")
    table_name = stream_arn.split(":table/", 1)[1].split("/stream/", 1)[0]
    import boto3

    return boto3.resource("dynamodb", region_name=record["awsRegion"]).Table(table_name)


def mark_dispatched(record: Mapping[str, Any], task_id: str) -> bool:
    try:
        _task_table(record).update_item(
            Key={"id": task_id},
            UpdateExpression="SET #status = :dispatched",
            ConditionExpression="#status = :ready",
            ExpressionAttributeNames={"#status": "dispatchStatus"},
            ExpressionAttributeValues={":ready": READY, ":dispatched": DISPATCHED},
        )
    except ClientError as error:
        if (
            error.response.get("Error", {}).get("Code")
            == "ConditionalCheckFailedException"
        ):
            return False
        raise
    return True


def _celery() -> Celery:
    queue_url = os.environ.get("COMMAND_QUEUE_URL", "").strip()
    if not queue_url:
        raise ValueError("COMMAND_QUEUE_URL is required")
    import boto3

    region = boto3.session.Session().region_name
    if not region:
        raise ValueError("Lambda execution region is unavailable")
    queue_name = queue_url.rstrip("/").rsplit("/", 1)[-1]
    app = Celery("plexus.command_worker.dispatcher", broker="sqs://")
    app.conf.update(
        task_default_queue=queue_name,
        task_ignore_result=True,
        broker_transport_options={
            "region": region,
            "predefined_queues": {queue_name: {"url": queue_url}},
        },
    )
    return app


def handler(event: Mapping[str, Any], _context: Any) -> dict[str, int]:
    app, processed, skipped = _celery(), 0, 0
    for record in event.get("Records", []):
        if not _eligible(record):
            skipped += 1
            continue
        task = deserialize_dynamo_item(record["dynamodb"]["NewImage"])
        app.send_task(
            os.environ.get("COMMAND_WORKER_TASK_NAME", TASK_NAME), args=[envelope(task)]
        )
        mark_dispatched(record, str(task["id"]))
        processed += 1
    return {"processed": processed, "skipped": skipped}
