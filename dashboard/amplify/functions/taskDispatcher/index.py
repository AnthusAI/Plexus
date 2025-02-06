import os
import json
import logging
from kombu.utils.url import safequote

from boto3.dynamodb.types import TypeDeserializer
from celery import Celery

# Set up basic logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get and quote AWS credentials
aws_access_key = safequote(os.environ.get("CELERY_AWS_ACCESS_KEY_ID", ""))
aws_secret_key = safequote(os.environ.get("CELERY_AWS_SECRET_ACCESS_KEY", ""))
aws_region = os.environ.get("CELERY_AWS_REGION_NAME", "")

logger.info(f"AWS Region configured: {bool(aws_region)}")
logger.info(f"AWS credentials configured: {bool(aws_access_key and aws_secret_key)}")

# Construct broker URL from AWS credentials
broker_url = f"sqs://{aws_access_key}:{aws_secret_key}@"

# Get backend URL template and construct full URL
backend_url_template = os.environ.get("CELERY_RESULT_BACKEND_TEMPLATE")
logger.info(f"Backend template configured: {bool(backend_url_template)}")

if not all([aws_access_key, aws_secret_key, aws_region, backend_url_template]):
    raise ValueError("Missing required AWS credentials or backend template in environment")

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
    task_default_queue='celery'
)

# Initialize DynamoDB deserializer
deserializer = TypeDeserializer()

def deserialize_dynamo_item(item):
    """Convert a DynamoDB item to a regular dict."""
    return {key: deserializer.deserialize(value) for key, value in item.items()}


def handler(event, context):
    """
    AWS Lambda handler that processes DynamoDB stream events.
    For each new or modified task record with dispatchStatus 'PENDING', dispatch the task using Celery.
    """
    logger.info(f"Lambda function started with RequestId: {context.aws_request_id}")
    logger.info(f"Received event: {json.dumps(event)}")
    
    if not event.get('Records'):
        logger.warning("No records found in event")
        return {"status": "done", "message": "no records to process"}

    processed_count = 0
    skipped_count = 0
    error_count = 0

    for record in event.get('Records', []):
        logger.info(f"Processing record: {json.dumps(record.get('eventID'))}")
        
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
            logger.info(f"Deserialized task: {json.dumps(task)}")
            
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

            logger.info(f"Dispatching task: id={task_id}, command={command}, target={target}")

            # Dispatch the Celery task using the existing Celery task name
            result = celery_app.send_task(
                'plexus.execute_command',
                args=[command],
                kwargs={'target': target, 'task_id': task_id}
            )
            logger.info(f"Successfully dispatched task {task_id} via Celery. Celery task id: {result.id}")
            processed_count += 1
            
        except Exception as e:
            error_msg = f"Error processing record: {str(e)}"
            logger.error(error_msg, exc_info=True)
            error_count += 1

    summary = {
        "status": "done",
        "processed": processed_count,
        "skipped": skipped_count,
        "errors": error_count
    }
    logger.info(f"Lambda execution complete. Summary: {json.dumps(summary)}")
    return summary 