import os
import json
import logging
from datetime import datetime, timezone
from kombu.utils.url import safequote

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from celery import Celery

# Set up basic logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

PLACEHOLDER_VALUE = "WILL_BE_SET_AFTER_DEPLOYMENT"


def _required_env(name):
    value = os.environ.get(name, "").strip()
    if not value or value == PLACEHOLDER_VALUE:
        raise ValueError(
            f"Missing required TaskDispatcher environment variable: {name}"
        )
    return value


# Get and quote AWS credentials
aws_access_key = safequote(_required_env("CELERY_AWS_ACCESS_KEY_ID"))
aws_secret_key = safequote(_required_env("CELERY_AWS_SECRET_ACCESS_KEY"))
aws_region = _required_env("CELERY_AWS_REGION_NAME")

# Require an explicit queue so staging/production cannot silently dispatch to
# the development default.
sqs_queue_name = _required_env("CELERY_QUEUE_NAME")
logger.info(f"Using queue name: {sqs_queue_name}")

logger.info(f"AWS Region configured: {bool(aws_region)}")
logger.info(f"AWS credentials configured: {bool(aws_access_key and aws_secret_key)}")

# Construct broker URL from AWS credentials
broker_url = f"sqs://{aws_access_key}:{aws_secret_key}@/{sqs_queue_name}"

# Get backend URL template and construct full URL
backend_url_template = _required_env("CELERY_RESULT_BACKEND_TEMPLATE")
logger.info(f"Backend template configured: {bool(backend_url_template)}")

backend_url = backend_url_template.format(
    aws_access_key=aws_access_key,
    aws_secret_key=aws_secret_key,
    aws_region_name=aws_region
)

# Initialize Celery app
celery_app = Celery(
    "plexus",
    broker=broker_url,
    backend=backend_url,
    broker_transport_options={
        "region": aws_region,
        "is_secure": True,
    }
)

# Configure Celery app
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_default_queue=sqs_queue_name
)

# Initialize DynamoDB deserializer
deserializer = TypeDeserializer()
dynamodb = boto3.resource("dynamodb")

def deserialize_dynamo_item(item):
    """Convert a DynamoDB item to a regular dict."""
    return {key: deserializer.deserialize(value) for key, value in item.items()}


def _json_for_log(payload):
    """Serialize log payloads defensively (DynamoDB numbers may be Decimal)."""
    return json.dumps(payload, default=str)


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _task_table_name(record):
    stream_arn = record.get("eventSourceARN") or ""
    marker = ":table/"
    if marker not in stream_arn:
        raise ValueError("DynamoDB stream record is missing eventSourceARN table name")
    table_segment = stream_arn.split(marker, 1)[1]
    table_name = table_segment.split("/stream/", 1)[0]
    if not table_name:
        raise ValueError("DynamoDB stream record has an empty table name")
    return table_name


def _update_task_record(record, task_id, updates, expected_dispatch_status=None):
    if not task_id:
        raise ValueError("Cannot update Task dispatch state without a task id")

    names = {}
    values = {}
    assignments = []
    for index, (field, value) in enumerate(updates.items()):
        name_key = f"#field{index}"
        value_key = f":value{index}"
        names[name_key] = field
        values[value_key] = value
        assignments.append(f"{name_key} = {value_key}")

    update_args = {
        "Key": {"id": task_id},
        "UpdateExpression": "SET " + ", ".join(assignments),
        "ExpressionAttributeNames": names,
        "ExpressionAttributeValues": values,
    }

    if expected_dispatch_status is not None:
        names["#expectedDispatchStatus"] = "dispatchStatus"
        values[":expectedDispatchStatus"] = expected_dispatch_status
        update_args["ConditionExpression"] = (
            "#expectedDispatchStatus = :expectedDispatchStatus"
        )

    table = dynamodb.Table(_task_table_name(record))
    table.update_item(**update_args)


def _claim_task_for_dispatch(record, task_id, dispatcher_id):
    try:
        _update_task_record(
            record,
            task_id,
            {
                "dispatchStatus": "DISPATCHING",
                "workerNodeId": dispatcher_id,
                "updatedAt": _utc_now(),
            },
            expected_dispatch_status="PENDING",
        )
        return True
    except ClientError as exc:
        error = exc.response.get("Error", {})
        if error.get("Code") == "ConditionalCheckFailedException":
            logger.info(
                f"Skipping task {task_id}; dispatchStatus was claimed by another dispatcher"
            )
            return False
        raise


def _mark_task_dispatched(record, task_id, dispatcher_id, celery_task_id):
    _update_task_record(
        record,
        task_id,
        {
            "dispatchStatus": "DISPATCHED",
            "workerNodeId": dispatcher_id,
            "celeryTaskId": celery_task_id,
            "updatedAt": _utc_now(),
        },
    )


def _mark_task_dispatch_failed(record, task_id, error_message):
    if not task_id:
        return
    try:
        _update_task_record(
            record,
            task_id,
            {
                "status": "FAILED",
                "dispatchStatus": "ERROR",
                "errorMessage": error_message,
                "updatedAt": _utc_now(),
            },
        )
    except Exception:
        logger.error(f"Failed to mark task {task_id} dispatch failure", exc_info=True)


def handler(event, context):
    """
    AWS Lambda handler that processes DynamoDB stream events.
    For each new or modified task record with dispatchStatus 'PENDING', dispatch the task using Celery.
    """
    logger.info(f"Lambda function started with RequestId: {context.aws_request_id}")
    logger.info(f"Received event: {_json_for_log(event)}")
    
    if not event.get('Records'):
        logger.warning("No records found in event")
        return {"status": "done", "message": "no records to process"}

    processed_count = 0
    skipped_count = 0
    error_count = 0

    for record in event.get('Records', []):
        logger.info(f"Processing record: {_json_for_log(record.get('eventID'))}")
        task_id = None
        
        event_name = record.get('eventName')
        logger.info(f"Event type: {event_name}")
        
        if event_name not in ['INSERT', 'MODIFY']:
            logger.info(f"Skipping record with event type: {event_name}")
            skipped_count += 1
            continue
        
        new_image = record.get('dynamodb', {}).get('NewImage')
        if not new_image:
            logger.warning("No new image found in record")
            skipped_count += 1
            continue

        try:
            task = deserialize_dynamo_item(new_image)
            logger.info(f"Deserialized task: {_json_for_log(task)}")
            
            # For MODIFY events, check if dispatchStatus changed to PENDING
            if event_name == 'MODIFY':
                old_image = record.get('dynamodb', {}).get('OldImage')
                if old_image:
                    old_task = deserialize_dynamo_item(old_image)
                    old_status = old_task.get('dispatchStatus')
                    new_status = task.get('dispatchStatus')
                    
                    # Skip if not transitioning to PENDING
                    if old_status == new_status or new_status != 'PENDING':
                        logger.info(f"Skipping MODIFY event - dispatchStatus not transitioning to PENDING (old: {old_status}, new: {new_status})")
                        skipped_count += 1
                        continue
            
            # For INSERT events, only process if dispatchStatus is PENDING
            elif event_name == 'INSERT' and task.get('dispatchStatus') != 'PENDING':
                logger.info(f"Skipping INSERT event with dispatchStatus: {task.get('dispatchStatus')}")
                skipped_count += 1
                continue

            task_id = task.get('id')
            command = task.get('command')
            target = task.get('target', 'default/command')
            dispatcher_id = f"lambda:{context.aws_request_id}"

            logger.info(f"Dispatching task: id={task_id}, command={command}, target={target}")
            logger.info(f"Command breakdown: {repr(command)}")

            if not _claim_task_for_dispatch(record, task_id, dispatcher_id):
                skipped_count += 1
                continue

            # Dispatch the Celery task using the existing Celery task name
            result = celery_app.send_task(
                'plexus.execute_command',
                args=[command],
                kwargs={'target': target, 'task_id': task_id}
            )
            _mark_task_dispatched(record, task_id, dispatcher_id, result.id)
            logger.info(f"Successfully dispatched task {task_id} via Celery. Celery task id: {result.id}")
            processed_count += 1
            
        except Exception as e:
            error_msg = f"Error processing record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            try:
                _mark_task_dispatch_failed(record, task_id, error_msg)
            except Exception:
                logger.error("Failed while recording dispatch error", exc_info=True)
            error_count += 1

    summary = {
        "status": "done",
        "processed": processed_count,
        "skipped": skipped_count,
        "errors": error_count
    }
    logger.info(f"Lambda execution complete. Summary: {_json_for_log(summary)}")
    return summary
