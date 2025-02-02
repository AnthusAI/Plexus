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
    '--task-id',
    help='Task ID to update progress through the API'
)
def demo(target: str, task_id: Optional[str] = None) -> None:
    """Run a demo task that processes 2000 items over 20 seconds."""
    from .CommandProgress import CommandProgress
    import time
    import random
    import json
    from plexus.dashboard.api.models.task import Task
    from plexus.dashboard.api.client import PlexusDashboardClient
    
    total_items = 2000
    target_duration = 20  # seconds
    sleep_per_item = target_duration / total_items
    
    logging.info("Starting demo task processing...")
    
    client = PlexusDashboardClient()
    task = None
    
    if task_id:
        task = Task.get_by_id(task_id, client)
    else:
        # Create a new Task record with metadata as JSON string
        metadata_str = json.dumps({
            "total_items": total_items,
            "target_duration": target_duration
        })
        task = Task.create(
            client=client,
            accountId="default",  # Using default account for demo
            type="DEMO",
            target=target,
            command="plexus command demo",
            metadata=metadata_str
        )
        task_id = task.id
        logging.info(f"Created new Task with ID: {task_id}")
    
    # Initial state - no dispatch status
    time.sleep(random.uniform(2.0, 3.0))
    
    # Update to dispatched state
    task.update(dispatchStatus='DISPATCHED')
    time.sleep(random.uniform(2.0, 3.0))
    
    # Simulate Celery task creation
    task.update(celeryTaskId=f'demo-task-{int(time.time())}')
    time.sleep(random.uniform(2.0, 3.0))
    
    # Simulate worker claiming the task
    task.update(workerNodeId=f'demo-worker-{random.randint(1000, 9999)}')
    time.sleep(random.uniform(2.0, 3.0))
    
    # Now start actual processing
    task.start_processing()
    
    # Create stage configs for TaskProgressTracker
    stage_configs = {
        "Setup": StageConfig(order=1, status_message="Setting up..."),
        "Running": StageConfig(order=2, total_items=total_items),
        "Finishing": StageConfig(order=3, status_message="Finalizing...")
    }
    
    logging.info("Stage configs:")
    for name, config in stage_configs.items():
        logging.info(f"  {name}: order={config.order}, total_items={config.total_items}, message={config.status_message}")
    
    # Initialize progress tracker
    tracker = TaskProgressTracker(total_items=total_items, stage_configs=stage_configs)
    
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
            status=tracker.status
        )
        
        try:
            # Initialization stage
            init_time = random.uniform(4.0, 6.0)  # Random time between 4-6 seconds
            time.sleep(init_time)
            
            # Update Setup stage status before advancing
            if task:
                task.update_progress(
                    0,  # current items
                    total_items,
                    {
                        "Setup": {
                            "order": stage_configs["Setup"].order,
                            "totalItems": stage_configs["Setup"].total_items,
                            "processedItems": 0,
                            "statusMessage": "Setup complete",
                            "status": "COMPLETED"
                        }
                    }
                )
            
            tracker.advance_stage()  # Complete Setup stage
            
            if task:
                task.update_progress(
                    tracker.current_items,
                    tracker.total_items,
                    {
                        name: {
                            "order": config.order,
                            "totalItems": config.total_items,
                            "processedItems": stage.processed_items if stage else 0,
                            "statusMessage": stage.status_message if stage else ""
                        }
                        for name, (config, stage) in zip(
                            stage_configs.keys(),
                            [(c, tracker._stages.get(n)) for n, c in stage_configs.items()]
                        )
                    }
                )
            
            progress.update(
                task_progress,
                completed=tracker.current_items,
                status=tracker.status
            )
            
            # Main processing stage
            for i in range(total_items):
                current_item = i + 1
                tracker.update(current_items=current_item)
                
                # Update progress every 50 items or on the last item
                if i % 50 == 0 or i == total_items - 1:
                    # Update rich progress
                    progress.update(
                        task_progress,
                        completed=current_item,
                        status=f"{tracker.status} ({tracker.items_per_second:.1f} items/sec)"
                    )
                    
                    # Update Celery progress
                    CommandProgress.update(
                        current=current_item,
                        total=total_items,
                        status=tracker.status
                    )
                    
                    # Update Task progress if we have a task ID
                    if task:
                        current_status = f"{tracker.status} ({tracker.items_per_second:.1f} items/sec)"
                        task.update_progress(
                            tracker.current_items,
                            tracker.total_items,
                            {
                                name: {
                                    "order": config.order,
                                    "totalItems": config.total_items,
                                    "processedItems": stage.processed_items if stage else 0,
                                    "statusMessage": current_status if name == "Running" else (stage.status_message if stage else ""),
                                    "itemsPerSecond": tracker.items_per_second
                                }
                                for name, (config, stage) in zip(
                                    stage_configs.keys(),
                                    [(c, tracker._stages.get(n)) for n, c in stage_configs.items()]
                                )
                            },
                            estimated_completion_at=tracker.estimated_completion_time
                        )
                
                time.sleep(sleep_per_item)
            
            # Update Running stage status before advancing
            if task:
                task.update_progress(
                    total_items,  # All items processed
                    total_items,
                    {
                        "Running": {
                            "order": stage_configs["Running"].order,
                            "totalItems": stage_configs["Running"].total_items,
                            "processedItems": total_items,
                            "statusMessage": "Processing complete",
                            "status": "COMPLETED"
                        }
                    }
                )
            
            # Finishing stage
            tracker.advance_stage()  # Move to Finishing stage
            finish_time = random.uniform(2.0, 4.0)  # Random time between 2-4 seconds
            progress.update(
                task_progress,
                completed=total_items,
                status="Finalizing..."
            )
            
            time.sleep(finish_time)
            
            # Update Finishing stage status before completing
            if task:
                task.update_progress(
                    total_items,
                    total_items,
                    {
                        "Finishing": {
                            "order": stage_configs["Finishing"].order,
                            "totalItems": stage_configs["Finishing"].total_items,
                            "processedItems": 0,
                            "statusMessage": "Finalizing...",
                            "status": "COMPLETED"
                        }
                    }
                )
            
            time.sleep(finish_time)
            
            # Update final status after finishing
            if task:
                task.update_progress(
                    total_items,
                    total_items,
                    {
                        "Finishing": {
                            "order": stage_configs["Finishing"].order,
                            "totalItems": stage_configs["Finishing"].total_items,
                            "processedItems": 0,
                            "statusMessage": "Processing complete",
                            "status": "COMPLETED"
                        }
                    }
                )
            
            # Complete all stages
            tracker.complete()
            
            if task:
                # Debug log current state
                logging.info("Final tracker state:")
                for name, stage in tracker._stages.items():
                    logging.info(f"  {name}: processed={stage.processed_items}/{stage.total_items}, status={stage.status_message}")
                
                # Debug log what we're sending to the API
                stage_updates = {
                    name: {
                        "order": config.order,
                        "totalItems": config.total_items,
                        "processedItems": stage.processed_items if stage else 0,
                        "statusMessage": stage.status_message if stage else ""
                    }
                    for name, (config, stage) in zip(
                        stage_configs.keys(),
                        [(c, tracker._stages.get(n)) for n, c in stage_configs.items()]
                    )
                }
                logging.info("Sending stage updates to API:")
                for name, update in stage_updates.items():
                    logging.info(f"  {name}: {update}")
                
                task.update_progress(
                    tracker.current_items,
                    tracker.total_items,
                    stage_updates
                )
                
                # Now mark as completed
                task.complete_processing()
                
                # Get current stages to verify their state
                final_stages = task.get_stages()
                for stage in final_stages:
                    logging.info(f"Final stage {stage.name}: status={stage.status}, message={stage.statusMessage}")
            
            success_message = (
                f"Demo task completed successfully in {tracker.elapsed_time:.1f} seconds "
                f"({tracker.items_per_second:.1f} items/sec)"
            )
            logging.info(success_message)
            
        except KeyboardInterrupt:
            error_message = (
                f"Demo task cancelled by user after {tracker.elapsed_time:.1f} seconds "
                f"({tracker.items_per_second:.1f} items/sec)"
            )
            logging.info(error_message)