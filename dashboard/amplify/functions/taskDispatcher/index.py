import os
import json
import logging

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

# Read Celery configuration from environment variables
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND')

# Log configuration status
logger.info(f"CELERY_BROKER_URL configured: {bool(CELERY_BROKER_URL)}")
logger.info(f"CELERY_RESULT_BACKEND configured: {bool(CELERY_RESULT_BACKEND)}")

# Initialize Celery app
celery_app = Celery('plexus', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

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
            
            if task.get('dispatchStatus') != 'PENDING':
                logger.info(f"Skipping task with dispatchStatus: {task.get('dispatchStatus')}")
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