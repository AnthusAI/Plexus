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
    # Get and quote AWS credentials
    aws_access_key = safequote(os.getenv("CELERY_AWS_ACCESS_KEY_ID"))
    aws_secret_key = safequote(os.getenv("CELERY_AWS_SECRET_ACCESS_KEY"))
    aws_region = os.getenv("CELERY_AWS_REGION_NAME")
    
    if not all([aws_access_key, aws_secret_key, aws_region]):
        raise ValueError("Missing required AWS credentials in environment")

    # Construct broker URL from AWS credentials
    broker_url = f"sqs://{aws_access_key}:{aws_secret_key}@sqs.{aws_region}.amazonaws.com"

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
    )
    
    logging.debug("Celery Configuration:")
    logging.debug(f"Broker URL: {broker_url}")
    logging.debug(f"Backend URL: {backend_url}")
    logging.debug(f"Region: {aws_region}")
    
    # Configure Celery app
    app.conf.update(
        broker_connection_retry_on_startup=True,
        task_default_queue='celery',
        task_acks_late=False,  # Change to early ack to prevent redelivery
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=0,  # Disable prefetch completely
        worker_max_tasks_per_child=100, # Restart worker after 100 tasks
        broker_transport_options={      
            "region": aws_region,
            "visibility_timeout": 1800,  # 30 minutes (matches max task duration)
            "visibility_timeout_high_priority": 60,  # For priority tasks
            "polling_interval": 1,      
            "wait_time_seconds": 20,
            "queue_name_prefix": "",    
            "is_secure": True,
            "predefined_queues": {
                "celery": {
                    "url": f"https://sqs.{aws_region}.amazonaws.com/celery",
                    "access_key_id": aws_access_key,
                    "secret_access_key": aws_secret_key,
                    "visibility_timeout": 1800
                }
            },
            "sqs-queue-name": "celery",
            "sqs-base64-encoded": False,
            "stall_wait_seconds": 5
        },
        # Additional settings to prevent task duplication
        task_queue_max_priority=10,     # Enable priority queue
        task_default_priority=5,        # Default task priority
        task_create_missing_queues=False, # Don't create queues automatically
        task_default_delivery_mode=1,   # Non-persistent messages
        broker_transport_options_high_priority={
            "queue_name_prefix": "high_",
            "visibility_timeout": 60
        },
        worker_soft_shutdown_timeout=30,  # 30s grace period for task completion
        worker_cancel_long_running_tasks_on_connection_loss=True
    )
    
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
@click.option('--queue', default='celery', help='Queue to process')
@click.option('--loglevel', default='INFO', help='Logging level')
@click.option(
    '--target-patterns',
    help='Comma-separated list of target patterns (e.g. "domain/*,*/subdomain"). If not provided, accepts all targets.'
)
def worker(
    concurrency: int,
    queue: str,
    loglevel: str,
    target_patterns: Optional[str] = None
) -> None:
    """Start a Celery worker for processing remote commands."""
    from .TaskTargeting import TaskTargetMatcher
    
    logging.info("Starting worker initialization...")
    
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
    
    # Send the task to Celery
    task = celery_app.send_task(
        'plexus.execute_command',
        args=[command_string],
        expires=timeout,
        kwargs={'target': target}
    )
    
    logging.debug("Task ID: %s", task.id)
    
    if is_async:
        print(f"Task ID: {task.id}")
        print(f"\nTo check status, run:")
        print(f"  plexus command status {task.id}")
    else:
        # Wait for the result while showing progress
        try:
            logging.debug("Waiting for task result...")
            
            with Progress(
                # First row - status only
                TextColumn("[bright_magenta]{task.fields[status]}"),
                TextColumn(""),  # Empty column for spacing
                # New line for visual separation
                TextColumn("\n"),
                # Second row - progress bar and details
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
                # Add a single task that tracks both status and progress
                task_progress = progress.add_task(
                    "Processing...",
                    total=100,
                    status="Initializing..."
                )
                
                while not task.ready():
                    if task.info and isinstance(task.info, dict):
                        current = task.info.get('current')
                        total = task.info.get('total')
                        status = task.info.get('status')
                        
                        if all([current, total, status]):
                            # Update progress and status
                            progress.update(
                                task_progress,
                                total=total,
                                completed=current,
                                status=status
                            )
                                
                    time.sleep(0.5)  # Brief pause between updates
                
                # Ensure progress bar reaches 100% on success
                if task.successful():
                    final_status = "Finished processing items."
                    progress.update(
                        task_progress,
                        completed=progress.tasks[task_progress].total,
                        status=final_status
                    )

            # Get the final result
            result = task.get(timeout=timeout)
            
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
@click.option('--loglevel', default='INFO', help='Logging level')
def status(task_id: str, loglevel: str) -> None:
    """Check the status of a dispatched command."""
    logging.getLogger().setLevel(loglevel)
    
    console = Console()
    task = celery_app.AsyncResult(task_id)
    
    # Debug logging
    logging.debug(f"Task state: {task.state}")
    logging.debug(f"Task info type: {type(task.info)}")
    logging.debug(f"Task info: {task.info}")
    logging.debug(f"Task result: {task.result}")
    
    console.print(f"\n[bright_magenta]Task {task_id}:")
    console.print(f"State: {task.state}")
    
    # Add detailed debug logging
    if task.info:
        logging.info(f"Task info: {task.info}")
        if isinstance(task.info, dict):
            logging.info(f"Task info result: {task.info.get('result', {})}")
            
    if task.ready():
        if task.successful():
            result = task.get()
            logging.info(f"Task result: {result}")
            console.print("Status: " + ("[green]Success" if result['status'] == 'success' else "[red]Failed"))
            if result['status'] == 'success':
                if result.get('stdout'):
                    console.print("\nOutput:")
                    console.print(result['stdout'], end='')
                if result.get('stderr'):
                    console.print("\nErrors:")
                    console.print(result['stderr'], end='')
            else:
                console.print(f"\nError: {result.get('error', 'Unknown error')}")
                if result.get('stderr'):
                    console.print("\nError Details:")
                    console.print(result['stderr'], end='')
        else:
            console.print("[red]Status: Failed with exception")
            if task.info:
                console.print(f"Error: {str(task.info)}")
    else:
        console.print("[bright_magenta]Status: Running")
        
    # Show progress info if available
    if task.info and isinstance(task.info, dict):
        current = task.info.get('current')
        total = task.info.get('total')
        status = task.info.get('status')
        
        if all([current, total, status]):
            with Progress(
                # First row - status only
                TextColumn("[bright_magenta]{task.fields[status]}"),
                TextColumn(""),  # Empty column for spacing
                # New line for visual separation
                TextColumn("\n"),
                # Second row - progress bar and details
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
                # Add a single task that tracks both status and progress
                task_progress = progress.add_task(
                    "Processing...",
                    total=total,
                    status=stage_configs["Setup"].status_message
                )
                progress.refresh()

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
        "Running": StageConfig(
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
        tracker.advance_stage()  # Advance to "Running" stage
        
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
                raise Exception(f"Simulated failure at {current_item}/{total_items} items")
                
            # Calculate how many items we should have processed by now to stay on target
            elapsed = time.time() - stage_start_time  # Use stage-specific elapsed time
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
            time.sleep(0.05)  # Reduced sleep time for smoother updates
        
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
        tracker.current_stage.status_message = "Task completed."
        tracker.complete()  # This will mark the task as complete and send the final update
        
    except KeyboardInterrupt:
        error_message = (
            f"Demo task cancelled by user after {tracker.elapsed_time:.1f} seconds "
            f"({tracker.items_per_second:.1f} items/sec)"
        )
        logging.info(error_message)
        try:
            if tracker.api_task:
                tracker.api_task.fail_processing("Task cancelled by user")
        except Exception as e:
            logging.error(f"Failed to update task status on cancellation: {str(e)}")
    except Exception as e:
        error_message = str(e)
        logging.error(f"Demo task failed: {error_message}", exc_info=True)
        try:
            if tracker.api_task:
                tracker.api_task.fail_processing(error_message)
        except Exception as update_error:
            logging.error(f"Failed to update task status on error: {str(update_error)}")
        raise  # Re-raise the original exception after updating the task status