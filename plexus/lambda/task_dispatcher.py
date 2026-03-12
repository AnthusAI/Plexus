import os
import json
import logging

from boto3.dynamodb.types import TypeDeserializer
from celery import Celery

# Set up basic logging
logging.basicConfig(level=logging.INFO)

# Read Celery configuration from environment variables
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND')
CELERY_QUEUE_NAME = os.environ.get('CELERY_QUEUE_NAME', 'plexus-celery')  # Changed default to "plexus-celery"

logging.info(f"Using queue name: {CELERY_QUEUE_NAME}" + 
            (f" (from CELERY_QUEUE_NAME environment variable)" if os.environ.get("CELERY_QUEUE_NAME") else " (default)"))

# Initialize Celery app
# Add queue name to broker URL if not already included
if CELERY_BROKER_URL and '/' not in CELERY_BROKER_URL.split('@')[-1]:
    CELERY_BROKER_URL = f"{CELERY_BROKER_URL}/{CELERY_QUEUE_NAME}"
    logging.info(f"Added queue name to broker URL: {CELERY_BROKER_URL}")

celery_app = Celery('plexus', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

# Set the default queue
celery_app.conf.task_default_queue = CELERY_QUEUE_NAME

# Initialize DynamoDB deserializer
deserializer = TypeDeserializer()

def deserialize_dynamo_item(item):
    """Convert a DynamoDB item to a regular dict."""
    return {key: deserializer.deserialize(value) for key, value in item.items()}


def lambda_handler(event, context):
    """
    AWS Lambda handler that processes DynamoDB stream events.
    For each new task record with dispatchStatus 'PENDING', dispatch the task using Celery.
    """
    logging.info(f"Received event: {json.dumps(event)}")

    for record in event.get('Records', []):
        event_name = record.get('eventName')
        # Only process INSERT events to dispatch Celery task when Task is first created
        if event_name != 'INSERT':
            continue
       
        new_image = record.get('dynamodb', {}).get('NewImage')
        if not new_image:
            continue

        try:
            task = deserialize_dynamo_item(new_image)
            # Only process tasks with dispatchStatus 'PENDING'
            if task.get('dispatchStatus') != 'PENDING':
                continue

            task_id = task.get('id')
            command = task.get('command')
            target = task.get('target', 'default/command')

            # Dispatch the Celery task using the existing Celery task name
            result = celery_app.send_task(
                'plexus.execute_command',
                args=[command],
                kwargs={'target': target, 'task_id': task_id}
            )
            logging.info(f"Dispatched task {task_id} via Celery. Celery task id: {result.id}")
        except Exception as e:
            logging.error(f"Error processing record: {str(e)}")

    return {"status": "done"} 