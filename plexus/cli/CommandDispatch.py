import click
import os
import time
from dotenv import load_dotenv
from celery import Celery
from plexus.CustomLogging import logging
from kombu.utils.url import safequote
import sys
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, \
    BarColumn, TaskProgressColumn, TimeRemainingColumn, TextColumn, ProgressColumn, Task as RichTask
from rich.style import Style
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
import typing
from typing import Optional
from plexus.dashboard.api.models.task import Task
from plexus.dashboard.api.client import PlexusDashboardClient
import json
import datetime
from plexus.cli.task_progress_tracker import TaskProgressTracker, StageConfig
from datetime import timezone
from urllib.parse import quote
import boto3

class ItemCountColumn(ProgressColumn):
    """Renders item count and total."""
    def render(self, task: RichTask) -> typing.Union[str, typing.Text]:
        """Show item count and total."""
        return f"{int(task.completed)}/{int(task.total)}"

class StatusColumn(ProgressColumn):
    """Renders status in a full line above the progress bar."""
    def render(self, task: RichTask) -> typing.Union[str, typing.Text]:
        return f"[bright_magenta]{task.fields.get('status', '')}"

load_dotenv()

def create_celery_app() -> Celery:
    """Create a configured Celery application with AWS credentials."""
    # Get AWS credentials from standard environment variables
    raw_aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    raw_aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION_NAME")

    if not all([raw_aws_access_key, raw_aws_secret_key, aws_region]):
        raise ValueError(
            "Missing required AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME) in environment"
        )

    # Quote credentials for use in URLs if they are part of the host:port section of the broker URL
    quoted_aws_access_key = safequote(raw_aws_access_key)
    quoted_aws_secret_key = safequote(raw_aws_secret_key)

    # Get queue name from environment variable or use default
    sqs_queue_name = os.getenv("CELERY_QUEUE_NAME", "plexus-celery")  # Changed default to "plexus-celery"

    # Check if queue exists and create if it doesn't
    try:
        logging.info("=" * 80)
        logging.info(f"SQS QUEUE AUTO-CREATION: Checking if queue '{sqs_queue_name}' exists in region '{aws_region}'...")
        
        sqs = boto3.client(
            'sqs',
            region_name=aws_region,
            aws_access_key_id=raw_aws_access_key,
            aws_secret_access_key=raw_aws_secret_key
        )
        
        # Try to get the queue URL - this will fail with an exception if the queue doesn't exist
        try:
            queue_url_response = sqs.get_queue_url(QueueName=sqs_queue_name)
            queue_url = queue_url_response['QueueUrl']
            logging.info(f"SQS QUEUE AUTO-CREATION: Queue '{sqs_queue_name}' already exists at URL: {queue_url}")
        except sqs.exceptions.QueueDoesNotExist:
            # Queue doesn't exist, create it
            logging.info(f"SQS QUEUE AUTO-CREATION: Queue '{sqs_queue_name}' does not exist in region '{aws_region}', creating now...")
            
            create_response = sqs.create_queue(
                QueueName=sqs_queue_name,
                Attributes={
                    'VisibilityTimeout': '1800',  # 30 minutes (matches task timeout)
                    'MessageRetentionPeriod': '86400',  # 1 day
                    'ReceiveMessageWaitTimeSeconds': '20'  # Enable long polling
                }
            )
            
            new_queue_url = create_response['QueueUrl']
            logging.info(f"SQS QUEUE AUTO-CREATION: Queue '{sqs_queue_name}' successfully created in region '{aws_region}'")
            logging.info(f"SQS QUEUE AUTO-CREATION: Queue URL: {new_queue_url}")
        logging.info("=" * 80)
    except Exception as e:
        logging.warning("=" * 80)
        logging.warning(f"SQS QUEUE AUTO-CREATION ERROR: Failed to check/create queue '{sqs_queue_name}' in region '{aws_region}'")
        logging.warning(f"SQS QUEUE AUTO-CREATION ERROR: {str(e)}")
        logging.warning("SQS QUEUE AUTO-CREATION ERROR: Continuing with queue configuration - worker will try to use the queue if it exists")
        logging.warning("=" * 80)

    # Broker URL: Provide credentials. Region and queue details are in transport options.
    broker_url = f"sqs://{quoted_aws_access_key}:{quoted_aws_secret_key}@/{sqs_queue_name}"

    # Backend URL configuration
    backend_url_template = os.getenv("CELERY_RESULT_BACKEND_TEMPLATE")
    if not backend_url_template:
        raise ValueError("Missing required result backend URL template (CELERY_RESULT_BACKEND_TEMPLATE) in environment")
    
    backend_url = backend_url_template.format(
        aws_access_key=quoted_aws_access_key, 
        aws_secret_key=quoted_aws_secret_key, 
        aws_region_name=aws_region
    )

    app = Celery(
        "plexus-actions",
        broker=broker_url,
        backend=backend_url,
    )
    
    logging.info(
        f"Celery configured for SQS in region '{aws_region}'. "
        f"Queue name: '{sqs_queue_name}'" + 
        (f" (from CELERY_QUEUE_NAME environment variable)" if os.getenv("CELERY_QUEUE_NAME") else " (default)") + 
        f". The AWS SDK (Boto3) will resolve the queue name to its full URL."
    )
    logging.debug(f"Celery Broker base URL (credentials part): {broker_url}")
    logging.debug(f"Celery Backend URL: {backend_url}")
    
    app.conf.update(
        broker_connection_retry_on_startup=True,
        task_default_queue=sqs_queue_name, 
        task_acks_late=False,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=0, 
        worker_max_tasks_per_child=100, 
        broker_transport_options={      
            "region": aws_region, 
            "visibility_timeout": 1800,
            "polling_interval": 1, 
            "wait_time_seconds": 20, 
            "queue_name_prefix": "", 
            "is_secure": True, 
            "predefined_queues": {
                sqs_queue_name: { 
                    # Provide the queue name as the 'url'. Boto3, via Kombu's SQS transport,
                    # will use this name along with the region and credentials to resolve the full SQS queue URL.
                    "url": sqs_queue_name, 
                    "access_key_id": raw_aws_access_key, 
                    "secret_access_key": raw_aws_secret_key,
                }
            },
        },
        task_queue_max_priority=10,     
        task_default_priority=5,        
        task_create_missing_queues=True,  # Attempting to enable queue creation, though may not apply for SQS
        task_default_delivery_mode=1,   
        worker_soft_shutdown_timeout=30,
        worker_cancel_long_running_tasks_on_connection_loss=True
    )
    
    # Register task modules
    from plexus.cli.CommandTasks import register_tasks as register_command_tasks
    from plexus.cli.ScoreChatCommands import register_tasks as register_score_chat_tasks
    
    # Register tasks
    register_command_tasks(app)
    register_score_chat_tasks(app)
    
    return app

# Create the Celery app instance
celery_app = create_celery_app()

# Register tasks for both worker and dispatcher
from .CommandTasks import register_tasks
execute_command, demo_task = register_tasks(celery_app)

@click.group()
def command():
    """Commands for remote command dispatch and worker management."""
    pass

@command.command()
@click.option('--concurrency', default=4, help='Number of worker processes')
@click.option('--queue', default=None, help='Queue to process (defaults to CELERY_QUEUE_NAME if set, otherwise "celery")')
@click.option('--loglevel', default='INFO', help='Logging level')
@click.option(
    '--target-patterns',
    help='Comma-separated list of target patterns (e.g. "domain/*,*/subdomain"). If not provided, accepts all targets.'
)
def worker(
    concurrency: int,
    queue: Optional[str],
    loglevel: str,
    target_patterns: Optional[str] = None
) -> None:
    """Start a Celery worker for processing remote commands."""
    from .TaskTargeting import TaskTargetMatcher
    
    logging.info("Starting worker initialization...")
    
    # Use queue from parameter, or from environment, or default
    if queue is None:
        queue = os.getenv("CELERY_QUEUE_NAME", "plexus-celery")  # Changed default to "plexus-celery"
    
    # Only set up target matching if patterns are provided
    if target_patterns:
        # Parse and validate target patterns
        patterns = [p.strip() for p in target_patterns.split(",")]
        try:
            matcher = TaskTargetMatcher(patterns)
        except ValueError as e:
            raise click.BadParameter(f"Invalid target pattern: {e}")
        
        # Store matcher in app config for task routing
        celery_app.conf.task_target_matcher = matcher
        logging.info(f"Target patterns: {patterns}")
    else:
        logging.info("No target patterns specified - accepting all targets")
    
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
@click.option('--timeout', default=1800, help='Command timeout in seconds')
@click.option('--loglevel', default='INFO', help='Logging level')
@click.option(
    '--target',
    default='default/command',
    help='Target string in format domain/subdomain'
)
def dispatch(
    command_string: str,
    is_async: bool,
    timeout: int,
    loglevel: str,
    target: str
) -> None:
    """Execute a Plexus command remotely via Celery."""
    from .TaskTargeting import TaskTargetMatcher
    
    logging.getLogger().setLevel(loglevel)
    
    if not TaskTargetMatcher.validate_target(target):
        raise click.BadParameter(
            "Target must be in format 'domain/subdomain' with valid identifiers"
        )
    
    logging.info(f"Dispatching command: {command_string}")
    logging.info(f"Target: {target}")
    logging.debug("Celery app: %s", celery_app)
    logging.debug("Broker URL: %s", celery_app.conf.broker_url)
    logging.debug("Backend URL: %s", celery_app.conf.result_backend)
    
    console = Console()
    
    try:
        # Send the task to Celery
        task = celery_app.send_task(
            'plexus.execute_command',
            args=[command_string],
            expires=timeout,
            kwargs={'target': target}
        )
        
        logging.info(f"Successfully dispatched Celery task. Task ID: {task.id}")
        logging.debug("Task ID: %s", task.id)
        
        if is_async:
            console.print(f"[green]Task dispatched successfully[/green]")
            console.print(f"Task ID: {task.id}")
            console.print(f"\nTo check status, run:")
            console.print(f"  plexus command status {task.id}")
        else:
            # Wait for the result while showing progress
            try:
                logging.debug("Waiting for task result...")
                
                with Progress(
                    TextColumn("[bright_magenta]{task.fields[status]}"),
                    TextColumn(""), 
                    TextColumn("\n"),
                    SpinnerColumn(style="bright_magenta"),
                    ItemCountColumn(),
                    BarColumn(
                        complete_style="bright_magenta",
                        finished_style="bright_magenta"
                    ),
                    TaskProgressColumn(),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    expand=True
                ) as progress:
                    stage_configs = {
                        "Setup": StageConfig(
                            order=1,
                            status_message="Setting up...",
                            total_items=100  # Set a default total
                        )
                    }
                    task_progress = progress.add_task(
                        "Processing...",
                        total=100,  # Set a default total
                        status=stage_configs["Setup"].status_message
                    )
                    
                    while not task.ready():
                        if task.info and isinstance(task.info, dict):
                            current = task.info.get('current')
                            total_from_worker = task.info.get('total')
                            status_from_worker = task.info.get('status')
                            
                            if all([current is not None, total_from_worker is not None, status_from_worker is not None]):
                                progress.update(
                                    task_progress,
                                    total=float(total_from_worker),
                                    completed=float(current),
                                    status=status_from_worker
                                )
                                    
                        time.sleep(0.5)  # Brief pause between updates
                    
                    # Ensure progress bar reaches 100% on success if it hasn't already
                    if task.successful():
                        # Initialize defaults for final update
                        final_current = None
                        final_total = None
                        final_status_message = "Finished processing items."

                        # Attempt to get last known values from the loop if they were set
                        try:
                            final_current = current # Will use 'current' from the loop if it was set
                            final_total = total_from_worker # Will use 'total_from_worker' from the loop if it was set
                        except NameError: # If current or total_from_worker were not set in the loop
                            pass # Keep them as None, they will be fetched from task.info or defaulted

                        # Fetch the final state from task.info one last time if available
                        if task.info and isinstance(task.info, dict):
                            final_current = task.info.get('current', final_current)
                            final_total = task.info.get('total', final_total)
                            # Potentially use a final status message from the task info if one exists
                            final_status_message = task.info.get('status', final_status_message)

                        # Ensure final_total is not None and not 0 before using for completed if final_current is None
                        # This prevents division by zero if progress.tasks[task_progress].total is 0
                        # and provides a fallback if final_total isn't set.
                        effective_total = float(final_total if final_total is not None else 0)
                        effective_current = float(final_current if final_current is not None 
                                                else (effective_total if effective_total > 0 else 0))

                        progress.update(
                            task_progress,
                            completed=effective_current, 
                            total=effective_total,
                            status=final_status_message
                        )

                # Get the final result
                result = task.get(timeout=timeout)
                
                # Clear progress display for final results
                console.print("\n")
                
                if result['status'] == 'success':
                    console.print("\n--- COMMAND EXECUTION SUCCESSFUL ---")
                    console.print("[green]Command executed successfully on worker")
                    
                    # Print command output
                    if result.get('stdout'):
                        console.print("\n[bold]Command Output:[/bold]")
                        console.print(result['stdout'], end='')
                    if result.get('stderr'):
                        console.print("\n[bold]Command Errors/Warnings:[/bold]")
                        console.print(result['stderr'], end='', style="yellow")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    console.print("\n--- COMMAND EXECUTION FAILED ---")
                    console.print(f"[red]Command failed: {error_msg}")
                    
                    # Print error output if available
                    if result.get('stderr'):
                        console.print("\n[bold]Error Details:[/bold]")
                        console.print(result['stderr'], end='', style="red")
                    if result.get('stdout'):
                        console.print("\n[bold]Command Output (before failure):[/bold]")
                        console.print(result['stdout'], end='')
            except TimeoutError:
                console.print("\n--- COMMAND TIMEOUT ---")
                console.print(f"[yellow]Command timed out after {timeout} seconds")
                logging.error(f"Command timed out after {timeout} seconds")
                console.print(f"\nTask ID: {task.id}")
                console.print(f"You can still check the status later with:")
                console.print(f"  plexus command status {task.id}")
            except Exception as e:
                console.print("\n--- MONITORING ERROR ---")
                console.print(f"[red]Error monitoring task: {str(e)}")
                logging.error(f"Error getting task result: {e}", exc_info=True)
                console.print(f"\nTask ID: {task.id}")
                console.print(f"You can still check the status later with:")
                console.print(f"  plexus command status {task.id}")
    except Exception as e:
        console.print("\n--- DISPATCH ERROR ---")
        console.print(f"[red]Error dispatching task: {str(e)}")
        logging.error(f"Failed to dispatch task: {e}", exc_info=True)

@command.command()
@click.argument('task_id')
@click.option('--loglevel', default='INFO', help='Logging level')
def status(task_id: str, loglevel: str) -> None:
    """Check the status of a dispatched command."""
    logging.getLogger().setLevel(loglevel)
    
    try:
        # Attempt to retrieve the task status
        task = celery_app.AsyncResult(task_id)
        
        # Log the Celery state clearly, before anything else
        logging.info(f"CELERY_TASK_STATE: {task.state}")
        
        # Log the raw task data as JSON for complete transparency
        if task.ready() and task.successful():
            result = task.get()
            import json
            logging.info(f"TASK_RESULT_JSON: {json.dumps(result, default=str)}")
            
    except Exception as e:
        logging.error(f"Error retrieving task status: {e}", exc_info=True)

@command.command()
@click.argument('task_id')
def cancel(task_id: str) -> None:
    """Cancel a running command."""
    task = celery_app.AsyncResult(task_id)
    task.revoke(terminate=True)
    logging.info(f"Cancelled command task: {task_id}")

def get_progress_status(current: int, total: int) -> str:
    """Get a status message based on progress percentage."""
    percentage = (current / total) * 100
    
    if percentage <= 5:
        return "Starting processing items..."
    elif percentage <= 15:
        return "Starting processing items..."
    elif percentage <= 35:
        return "Processing items..."
    elif percentage <= 65:
        return "Cruising..."
    elif percentage <= 80:
        return "On autopilot..."
    elif percentage <= 90:
        return "Finishing soon..."
    elif percentage < 100:
        return "Almost done processing items..."
    else:
        return "Finished processing items."

@command.command()
@click.option(
    '--target',
    default='default/command',
    help='Target string in format domain/subdomain'
)
@click.option(
    '--task-id',
    help='Task ID to update progress through the API'
)
@click.option(
    '--fail',
    is_flag=True,
    help='Simulate a random failure during the Running stage'
)
def demo(target: str, task_id: Optional[str] = None, fail: bool = False) -> None:
    """Run a demo task that processes 2000 items over 20 seconds."""
    from .CommandProgress import CommandProgress
    import time
    import random
    import json
    from plexus.dashboard.api.models.task import Task
    from plexus.dashboard.api.client import PlexusDashboardClient
    import os
    
    # Set logging level to INFO for clearer progress output
    logging.getLogger().setLevel(logging.INFO)
    
    total_items = 2000
    target_duration = 20  # Keep the 20 second target
    min_batch_size = 30
    max_batch_size = 70
    avg_batch_size = 50  # For calculating sleep time
    estimated_batches = total_items / avg_batch_size
    sleep_per_batch = target_duration / estimated_batches
    
    # Create stage configs for TaskProgressTracker
    stage_configs = {
        "Setup": StageConfig(
            order=1, 
            status_message="Loading AI models..."
        ),
        "Processing": StageConfig(
            order=2, 
            total_items=total_items,
            status_message="Processing items..."
        ),
        "Finalizing": StageConfig(
            order=3, 
            status_message="Computing metrics..."
        )
    }
    
    # Verify API environment
    api_url = os.environ.get('PLEXUS_API_URL')
    api_key = os.environ.get('PLEXUS_API_KEY')
    
    if not api_url or not api_key:
        logging.warning("PLEXUS_API_URL or PLEXUS_API_KEY not set, cannot track task")
        return

    # Initialize API client
    client = PlexusDashboardClient(api_url=api_url, api_key=api_key)

    # Get the account ID by key
    ACCOUNT_KEY = 'call-criteria'
    # Use GraphQL query to get account by key
    response = client.execute(
        """
        query ListAccountByKey($key: String!) {
            listAccountByKey(key: $key) {
                items {
                    id
                }
            }
        }
        """,
        {'key': ACCOUNT_KEY}
    )

    print("API Response:", response)  # Debug the raw response

    if not response.get('listAccountByKey', {}).get('items'):
        raise ValueError(f"No account found with key: {ACCOUNT_KEY}")
        
    account_id = response['listAccountByKey']['items'][0]['id']
    logging.info(f"Found account ID: {account_id} for key: {ACCOUNT_KEY}")
    
    # Initialize progress tracker with API task management and account ID
    tracker = TaskProgressTracker(
        total_items=total_items,
        stage_configs=stage_configs,
        task_id=task_id,
        target=target,
        command="plexus command demo",  # Remove $ prefix since component adds it
        description="Running demo task with progress tracking",
        dispatch_status="DISPATCHED",
        prevent_new_task=False,
        metadata={
            "type": "Demo Task",
            "scorecard": "Outbound Sales",
            "score": "DNC Requested?"
        },
        account_id=account_id  # Add the account ID here
    )
    
    with Progress(
        TextColumn("[bright_magenta]{task.fields[status]}"),
        TextColumn(""),  # Empty column for spacing
        TextColumn("\n"),
        SpinnerColumn(style="bright_magenta"),
        ItemCountColumn(),
        BarColumn(complete_style="bright_magenta", finished_style="bright_magenta"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        expand=True
    ) as progress:
        task_progress = progress.add_task(
            "Processing...",
            total=total_items,
            status=stage_configs["Setup"].status_message
        )
        _run_demo_task(tracker, progress, task_progress, total_items, min_batch_size, max_batch_size, sleep_per_batch, fail)

def _run_demo_task(tracker, progress, task_progress, total_items, min_batch_size, max_batch_size, sleep_per_batch, fail):
    """Helper function to run the demo task with Rich progress bar."""
    import random
    
    try:
        # Setup stage with multiple status updates
        tracker.update(current_items=0)
        
        # Quick setup phase with multiple status messages
        setup_messages = [
            "Loading base AI model...",
            "Initializing model parameters...",
            "Loading custom configurations...",
            "Preparing processing pipeline..."
        ]
        
        for msg in setup_messages:
            tracker.current_stage.status_message = msg
            tracker.update(current_items=0)
            time.sleep(0.15)  # Reduced from 0.3s to 0.15s per message
        
        # Main processing stage
        tracker.advance_stage()  # Advance to "Processing" stage
        
        # Process items with target rate - doubled duration with ±5s jitter
        current_item = 0
        stage_start_time = time.time()  # Track stage-specific start time
        last_api_update = 0  # To control API update frequency
        api_update_interval = 1  # Update API every 1 second
        target_duration = 40.0 + random.uniform(-5.0, 5.0)  # 40 seconds ±5s jitter
        
        # If fail flag is set, calculate failure point between 30-70% progress
        fail_at = int(total_items * random.uniform(0.3, 0.7)) if fail else None
        
        while current_item < total_items:
            # Check for simulated failure
            if fail and current_item >= fail_at:
                error_msg = f"Simulated failure at {current_item}/{total_items} items"
                logging.error(f"TASK EXECUTION ERROR: {error_msg}")
                # First mark the task as failed to prevent further updates
                tracker.fail(error_msg)
                # Then update the progress display
                progress.update(
                    task_progress,
                    completed=current_item,
                    status="EXECUTION ERROR: Simulated failure"
                )
                raise Exception(error_msg)
                
            # Calculate how many items we should have processed by now to stay on target
            elapsed = time.time() - stage_start_time
            target_items = min(
                total_items,
                int((elapsed / target_duration) * total_items)
            )
            
            # Process enough items to catch up to where we should be
            items_to_process = max(1, target_items - current_item)
            current_item = min(current_item + items_to_process, total_items)
            
            # Calculate metrics for display using stage timing
            elapsed = time.time() - stage_start_time
            actual_items_per_sec = current_item / elapsed if elapsed > 0 else 0
            
            # Update tracker with current progress
            tracker.update(current_items=current_item)
            
            # Update Rich progress bar
            progress.update(
                task_progress,
                completed=current_item,
                status=f"{tracker.status} ({actual_items_per_sec:.1f} items/sec)"
            )
            
            # If we've reached total items, advance to finalizing and exit immediately
            if current_item >= total_items:
                tracker.advance_stage()  # Advance to "Finalizing" stage
                break
            
            # Only update API task periodically if we're still processing
            current_time = time.time()
            if current_time - last_api_update >= api_update_interval:
                tracker.update(current_items=current_item)
                last_api_update = current_time
            
            # Sleep a tiny amount to allow for API updates and logging
            time.sleep(0.05)
        
        # Finalizing stage with just two messages
        finalizing_messages = [
            "Computing metrics...",
            "Generating report..."
        ]
        
        for msg in finalizing_messages:
            tracker.current_stage.status_message = msg
            tracker.update(current_items=total_items)
            time.sleep(0.15)  # Reduced from 0.3s to 0.15s per message
        
        # Set completion message and complete task in one atomic operation
        tracker.current_stage.status_message = "Demo command completed"
        tracker.complete()  # This will mark the task as complete and send the final update
        
    except KeyboardInterrupt:
        error_message = (
            f"Demo task cancelled by user after {tracker.elapsed_time:.1f} seconds "
            f"({tracker.items_per_second:.1f} items/sec)"
        )
        logging.info("USER INTERRUPT: " + error_message)
        try:
            tracker.fail("Task cancelled by user")  # Use new fail() method
            progress.update(task_progress, status="CANCELLED: Task was interrupted by user")
        except Exception as e:
            logging.error(f"TRACKER ERROR: Failed to update task status on cancellation: {str(e)}")
    except Exception as e:
        error_message = str(e)
        # Check if this is our simulated error or something else
        if fail and "Simulated failure" in error_message:
            logging.error(f"SIMULATED ERROR: {error_message}")
        else:
            logging.error(f"REAL ERROR: Demo task failed unexpectedly: {error_message}", exc_info=True)
        
        try:
            if not tracker.is_failed:  # Only fail if not already failed
                tracker.fail(error_message)  # Use new fail() method
            
            # Update progress with more informative error status
            if "Simulated failure" in error_message:
                progress.update(task_progress, status="EXECUTION ERROR: Simulated failure (expected)")
            else:
                progress.update(task_progress, status="UNEXPECTED ERROR: See logs for details")
        except Exception as update_error:
            logging.error(f"TRACKER ERROR: Failed to update task status after error: {str(update_error)}")
        
        # Only re-raise if it's not a simulated error
        if fail and "Simulated failure" in error_message:
            # We don't re-raise simulated errors when --fail flag is used
            pass
        else:
            # Re-raise unexpected errors
            raise  # Re-raise the original exception after updating the task status

def safequote(value: str) -> str:
    """Safely quote a string value, handling None."""
    if value is None:
        return ""
    return quote(str(value))

# Define OrderCommands class here
class OrderCommands(click.Group):
    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands)

def create_cli():
    """Create and configure the command line interface."""
    # Remove the import of CommandLineInterface
    # from plexus.cli import CommandLineInterface 
    
    # Define the base cli group here
    @click.group(cls=OrderCommands)
    def cli():
        """
        Plexus CLI for managing scorecards, scores, and evaluations.
        """
        pass
    
    # Import and register commands
    from plexus.cli.ScoreCommands import score
    from plexus.cli.ScorecardCommands import scorecards
    from plexus.cli.EvaluationCommands import evaluate
    from plexus.cli.DataCommands import data
    from plexus.cli.BatchCommands import batch
    from plexus.cli.TaskCommands import tasks
    from plexus.cli.ResultCommands import results
    from plexus.cli.AnalyzeCommands import analyze
    from plexus.cli.DataLakeCommands import lake_group as datalake
    from plexus.cli.TrainingCommands import train
    from plexus.cli.TuningCommands import tuning
    from plexus.cli.PredictionCommands import predict
    from plexus.cli.ScoreChatCommands import score_chat
    from plexus.cli.ReportCommands import report # Import the new command group
    
    # Add top-level commands
    cli.add_command(score)
    cli.add_command(scorecards)
    cli.add_command(evaluate)
    cli.add_command(data)
    cli.add_command(batch)
    cli.add_command(tasks)
    cli.add_command(results)
    cli.add_command(analyze)
    cli.add_command(datalake)
    cli.add_command(train)
    cli.add_command(tuning)
    cli.add_command(predict)
    cli.add_command(score_chat)
    cli.add_command(report) # Register the new command group
    cli.add_command(command)
    
    return cli