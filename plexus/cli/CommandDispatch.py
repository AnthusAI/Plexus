import click
import os
import time
from dotenv import load_dotenv
from celery import Celery
from plexus.CustomLogging import logging
from kombu.utils.url import safequote
import sys
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, \
    BarColumn, TaskProgressColumn, TimeRemainingColumn, TextColumn, ProgressColumn, Task
from rich.style import Style
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
import typing
from typing import Optional
from plexus.dashboard.api.models.action import Action
from plexus.dashboard.api.client import PlexusDashboardClient
import json
import datetime

class ItemCountColumn(ProgressColumn):
    """Renders item count and total."""
    def render(self, task: Task) -> typing.Union[str, typing.Text]:
        """Show item count and total."""
        return f"{int(task.completed)}/{int(task.total)}"

class StatusColumn(ProgressColumn):
    """Renders status in a full line above the progress bar."""
    def render(self, task: Task) -> typing.Union[str, typing.Text]:
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
    default="*",
    help='Comma-separated list of target patterns (e.g. "domain/*,*/subdomain")'
)
def worker(
    concurrency: int,
    queue: str,
    loglevel: str,
    target_patterns: str
) -> None:
    """Start a Celery worker for processing remote commands."""
    from .TaskTargeting import TaskTargetMatcher
    
    logging.info("Starting worker initialization...")
    
    # Parse and validate target patterns
    patterns = [p.strip() for p in target_patterns.split(",")]
    try:
        matcher = TaskTargetMatcher(patterns)
    except ValueError as e:
        raise click.BadParameter(f"Invalid target pattern: {e}")
    
    # Store matcher in app config for task routing
    celery_app.conf.task_target_matcher = matcher
    
    argv = [
        "worker",
        f"--concurrency={concurrency}",
        f"--queues={queue}",
        f"--loglevel={loglevel}",
    ]
    logging.info(f"Starting worker with arguments: {argv}")
    logging.info(f"Target patterns: {patterns}")
    celery_app.worker_main(argv)

@command.command()
@click.argument('command_string')
@click.option('--async', 'is_async', is_flag=True, help='Run command asynchronously')
@click.option('--timeout', default=3600, help='Command timeout in seconds')
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
                    completed=current,
                    status=status
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
    '--action-id',
    help='Action ID to update progress through the API'
)
def demo(target: str, action_id: Optional[str] = None) -> None:
    """Run a demo task that processes 2000 items over 20 seconds."""
    from .CommandProgress import CommandProgress
    import time
    import random
    import json
    from plexus.dashboard.api.models.action import Action
    from plexus.dashboard.api.client import PlexusDashboardClient
    
    total_items = 2000
    target_duration = 20  # seconds
    sleep_per_item = target_duration / total_items
    
    logging.info("Starting demo task processing...")
    
    client = PlexusDashboardClient()
    action = None
    
    if action_id:
        action = Action.get_by_id(action_id, client)
    else:
        # Create a new Action record with metadata as JSON string
        metadata_str = json.dumps({
            "total_items": total_items,
            "target_duration": target_duration
        })
        action = Action.create(
            client=client,
            accountId="default",  # Using default account for demo
            type="DEMO",
            target=target,
            command="plexus command demo",
            metadata=metadata_str
        )
        action_id = action.id
        logging.info(f"Created new Action with ID: {action_id}")
    
    # Initial state - no dispatch status
    time.sleep(random.uniform(2.0, 3.0))
    
    # Update to dispatched state
    action.update(dispatchStatus='DISPATCHED')
    time.sleep(random.uniform(2.0, 3.0))
    
    # Simulate Celery task creation
    action.update(celeryTaskId=f'demo-task-{int(time.time())}')
    time.sleep(random.uniform(2.0, 3.0))
    
    # Simulate worker claiming the task
    action.update(workerNodeId=f'demo-worker-{random.randint(1000, 9999)}')
    time.sleep(random.uniform(2.0, 3.0))
    
    # Now start actual processing
    action.start_processing()
    
    # Create all three stages
    stage_configs = {
        "Setup": {
            "order": 1,
            "totalItems": 1,
            "processedItems": 0,
            "statusMessage": "Starting initialization..."
        },
        "Running": {
            "order": 2,
            "totalItems": total_items,
            "processedItems": 0
        },
        "Finishing": {
            "order": 3,
            "totalItems": 1,
            "processedItems": 0,
            "statusMessage": "Waiting to finalize..."
        }
    }
    stages = action.update_progress(0, total_items, stage_configs)
    
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
            total=total_items,  # Only count main processing items
            status="Starting initialization..."
        )
        
        try:
            start_time = time.time()
            
            # Initialization stage
            init_time = random.uniform(4.0, 6.0)  # Random time between 4-6 seconds
            time.sleep(init_time)
            
            if action:
                stage_configs = {
                    "Setup": {
                        "order": 1,
                        "totalItems": 1,
                        "processedItems": 1,
                        "statusMessage": "Initialization complete"
                    },
                    "Running": {
                        "order": 2,
                        "totalItems": total_items,
                        "processedItems": 0
                    },
                    "Finishing": {
                        "order": 3,
                        "totalItems": 1,
                        "processedItems": 0,
                        "statusMessage": "Waiting to finalize..."
                    }
                }
                action.update_progress(0, total_items, stage_configs)
            
            progress.update(
                task_progress,
                completed=0,  # Reset to 0 for main processing
                status="Processing items..."
            )
            
            # Main processing stage
            start_time = time.time()
            for i in range(total_items):
                current_item = i + 1
                
                # Update progress every 50 items or on the last item
                if i % 50 == 0 or i == total_items - 1:
                    elapsed = time.time() - start_time
                    items_per_sec = current_item / elapsed if elapsed > 0 else 0
                    remaining_items = total_items - current_item
                    eta_seconds = remaining_items / items_per_sec if items_per_sec > 0 else 0
                    
                    # Calculate estimated completion time in UTC
                    current_time = datetime.datetime.now(datetime.timezone.utc)
                    estimated_completion = current_time + datetime.timedelta(seconds=eta_seconds) \
                        if eta_seconds > 0 else None
                    
                    # Get status message based on progress
                    percentage = (current_item / total_items) * 100
                    if percentage <= 5:
                        status = "Starting processing items..."
                    elif percentage <= 35:
                        status = f"Processing items... ({items_per_sec:.1f} items/sec)"
                    elif percentage <= 65:
                        status = f"Cruising... ({items_per_sec:.1f} items/sec)"
                    elif percentage <= 80:
                        status = f"On autopilot... ({items_per_sec:.1f} items/sec)"
                    elif percentage <= 90:
                        status = f"Finishing soon... ({items_per_sec:.1f} items/sec)"
                    elif percentage < 100:
                        status = f"Almost done... ({items_per_sec:.1f} items/sec)"
                    else:
                        status = f"Processed {total_items:,} items."
                    
                    progress.update(
                        task_progress,
                        completed=current_item,
                        status=status
                    )
                    
                    # Update Celery progress
                    CommandProgress.update(
                        current=current_item,
                        total=total_items,
                        status=status
                    )
                    
                    # Update Action progress if we have an action ID
                    if action:
                        stage_configs = {
                            "Setup": {
                                "order": 1,
                                "totalItems": 1,
                                "processedItems": 1,
                                "statusMessage": "Setup complete"
                            },
                            "Running": {
                                "order": 2,
                                "totalItems": total_items,
                                "processedItems": current_item,
                                "itemsPerSecond": items_per_sec,
                                "statusMessage": status
                            },
                            "Finishing": {
                                "order": 3,
                                "totalItems": 1,
                                "processedItems": 0,
                                "statusMessage": "Waiting to finalize..."
                            }
                        }
                        action.update_progress(
                            current_item,
                            total_items,
                            stage_configs,
                            estimated_completion_at=estimated_completion
                        )
                
                time.sleep(sleep_per_item)
            
            # Finishing stage
            finish_time = random.uniform(2.0, 4.0)  # Random time between 2-4 seconds
            progress.update(
                task_progress,
                completed=total_items,
                status="Finalizing..."
            )
            
            time.sleep(finish_time)
            
            # Complete all stages with final messages
            if action:
                stage_configs = {
                    "Setup": {
                        "order": 1,
                        "totalItems": 1,
                        "processedItems": 1,
                        "statusMessage": "Setup complete"
                    },
                    "Running": {
                        "order": 2,
                        "totalItems": total_items,
                        "processedItems": total_items
                    },
                    "Finishing": {
                        "order": 3,
                        "totalItems": None,
                        "processedItems": None,
                        "statusMessage": f"Successfully processed {total_items:,} items."
                    }
                }
                stages = action.update_progress(total_items, total_items, stage_configs)
                
                # Now mark as completed
                action.complete_processing()
                
                # Get current stages to verify their state
                final_stages = action.get_stages()
                for stage in final_stages:
                    logging.info(f"Final stage {stage.name}: status={stage.status}, message={stage.statusMessage}")
            
            total_time = time.time() - start_time
            success_message = (
                f"Demo task completed successfully in {total_time:.1f} seconds "
                f"({total_items/total_time:.1f} items/sec)"
            )
            logging.info(success_message)
            
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            items_per_sec = i / elapsed
            error_message = (
                f"Demo task cancelled by user after {elapsed:.1f} seconds "
                f"({items_per_sec:.1f} items/sec)"
            )
            logging.info(error_message)
            
            # Mark action as failed if we have one
            if action:
                action.fail_processing(
                    error_message=error_message,
                    error_details={"type": "user_interrupt"}
                )
            return
        except Exception as e:
            error_message = f"Demo task failed: {str(e)}"
            logging.error(error_message)
            
            # Mark action as failed if we have one
            if action:
                action.fail_processing(
                    error_message=error_message,
                    error_details={"type": "error", "error": str(e)}
                )
            raise

@command.command()
def _demo_internal() -> None:
    """Internal command for running the actual demo task."""
    from .CommandProgress import CommandProgress
    import time
    
    total_items = 2000
    target_duration = 20  # seconds
    sleep_per_item = target_duration / total_items
    
    logging.info("Starting demo task processing...")
    
    try:
        start_time = time.time()
        
        for i in range(total_items):
            current_item = i + 1
            # Get new status message
            new_status = get_progress_status(current_item, total_items)
            
            # Update command progress every 50 items
            if i % 50 == 0 or i == total_items - 1:
                elapsed = time.time() - start_time
                items_per_sec = current_item / elapsed
                
                CommandProgress.update(
                    current=current_item,
                    total=total_items,
                    status=new_status
                )
            
            # Simulate processing an item
            time.sleep(sleep_per_item)
        
        total_time = time.time() - start_time
        logging.info(
            f"Demo task completed successfully in {total_time:.1f} seconds "
            f"({total_items/total_time:.1f} items/sec)"
        )
        
    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        items_per_sec = i / elapsed
        logging.info(
            f"\nDemo task cancelled by user after {elapsed:.1f} seconds "
            f"({items_per_sec:.1f} items/sec)"
        )
        return