import click
import os
from dotenv import load_dotenv
from celery import Celery
from plexus.CustomLogging import logging
from kombu.utils.url import safequote
import sys

load_dotenv()

def create_celery_app() -> Celery:
    """Create a configured Celery application with AWS credentials."""
    # Get and quote AWS credentials
    aws_access_key = safequote(os.getenv("CELERY_AWS_ACCESS_KEY_ID"))
    aws_secret_key = safequote(os.getenv("CELERY_AWS_SECRET_ACCESS_KEY"))
    aws_region = os.getenv("CELERY_AWS_REGION_NAME")
    
    if not all([aws_access_key, aws_secret_key, aws_region]):
        raise ValueError("Missing required AWS credentials in environment")

    # Construct broker URL from AWS credentials
    broker_url = "sqs://{aws_access_key}:{aws_secret_key}@".format(
        aws_access_key=aws_access_key,
        aws_secret_key=aws_secret_key,
        aws_region_name=aws_region,
    )

    # Construct backend URL from template and AWS credentials
    backend_url_template = os.getenv("CELERY_RESULT_BACKEND_TEMPLATE")
    if not backend_url_template:
        raise ValueError("Missing required result backend URL template in environment")
        
    backend_url = backend_url_template.format(
        aws_access_key=aws_access_key,
        aws_secret_key=aws_secret_key,
        aws_region_name=aws_region
    )

    app = Celery(
        "plexus-actions",
        broker=broker_url,
        backend=backend_url,
        broker_transport_options={
            "region": aws_region,
            "is_secure": True,
        },
    )
    
    logging.debug("Celery Configuration:")
    logging.debug(f"Broker URL: {broker_url}")
    logging.debug(f"Backend URL: {backend_url}")
    logging.debug(f"Region: {aws_region}")
    
    # Configure Celery app
    app.conf.update(
        broker_connection_retry_on_startup=True,
        task_default_queue='celery',
    )
    
    return app

# Create the Celery app instance
celery_app = create_celery_app()

# Register tasks for both worker and dispatcher
from .ActionTasks import register_tasks
register_tasks(celery_app)

@click.group()
def command():
    """Commands for remote command dispatch and worker management."""
    pass

@command.command()
@click.option('--concurrency', default=4, help='Number of worker processes')
@click.option('--queue', default='celery', help='Queue to process')
@click.option('--loglevel', default='INFO', help='Logging level')
def worker(concurrency: int, queue: str, loglevel: str) -> None:
    """Start a Celery worker for processing remote commands."""
    logging.info("Starting worker initialization...")
    
    argv = [
        "worker",
        f"--concurrency={concurrency}",
        f"--queues={queue}",
        f"--loglevel={loglevel}",
    ]
    logging.info(f"Starting worker with arguments: {argv}")
    celery_app.worker_main(argv)

@command.command()
@click.argument('command_string')
@click.option('--async', 'is_async', is_flag=True, help='Run command asynchronously')
@click.option('--timeout', default=3600, help='Command timeout in seconds')
@click.option('--loglevel', default='INFO', help='Logging level')
def dispatch(command_string: str, is_async: bool, timeout: int, loglevel: str) -> None:
    """Execute a Plexus command remotely via Celery."""
    logging.getLogger().setLevel(loglevel)
    
    logging.info(f"Dispatching command: {command_string}")
    logging.debug("Celery app: %s", celery_app)
    logging.debug("Broker URL: %s", celery_app.conf.broker_url)
    logging.debug("Backend URL: %s", celery_app.conf.result_backend)
    
    # Send the task to Celery
    task = celery_app.send_task(
        'plexus.execute_command',
        args=[command_string],
        expires=timeout
    )
    
    logging.debug("Task ID: %s", task.id)
    
    if is_async:
        print(f"Task ID: {task.id}")
        logging.info("Use 'plexus command status <task-id>' to check status")
    else:
        # Wait for the result
        try:
            logging.debug("Waiting for task result...")
            result = task.get(timeout=timeout)
            logging.debug("Got result: %s", result)
            
            if result['status'] == 'success':
                logging.info("Command completed successfully")
                # Print command output
                if result.get('stdout'):
                    print(result['stdout'], end='')
                if result.get('stderr'):
                    print(result['stderr'], end='', file=sys.stderr)
            else:
                logging.error(f"Command failed: {result.get('error', 'Unknown error')}")
                # Print error output if available
                if result.get('stderr'):
                    print(result['stderr'], end='', file=sys.stderr)
                if result.get('stdout'):
                    print(result['stdout'], end='')
        except TimeoutError:
            logging.error(f"Command timed out after {timeout} seconds")
        except Exception as e:
            logging.error(f"Error getting task result: {e}", exc_info=True)

@command.command()
@click.argument('task_id')
def status(task_id: str) -> None:
    """Check the status of a dispatched command."""
    task = celery_app.AsyncResult(task_id)
    
    print(f"\nTask {task_id}:")
    print(f"State: {task.state}")
    
    if task.ready():
        if task.successful():
            result = task.get()
            print("Status: " + ("Success" if result['status'] == 'success' else "Failed"))
            if result['status'] == 'success':
                if result.get('stdout'):
                    print("\nOutput:")
                    print(result['stdout'], end='')
                if result.get('stderr'):
                    print("\nErrors:")
                    print(result['stderr'], end='')
            else:
                print(f"\nError: {result.get('error', 'Unknown error')}")
                if result.get('stderr'):
                    print("\nError Details:")
                    print(result['stderr'], end='')
        else:
            print("Status: Failed with exception")
            if task.info:
                print(f"Error: {str(task.info)}")
    else:
        print("Status: Running")
        if task.info:
            meta = task.info.get('meta', {})
            if meta:
                if 'current' in meta and 'total' in meta:
                    print(f"Progress: {meta['current']}/{meta['total']} items")
                if 'status' in meta:
                    print(f"Current operation: {meta['status']}")
                if 'elapsed_time' in meta:
                    print(f"Elapsed time: {meta['elapsed_time']}")
                if 'estimated_remaining' in meta:
                    print(f"Estimated remaining: {meta['estimated_remaining']}")

@command.command()
@click.argument('task_id')
def cancel(task_id: str) -> None:
    """Cancel a running command."""
    task = celery_app.AsyncResult(task_id)
    task.revoke(terminate=True)
    logging.info(f"Cancelled command task: {task_id}") 