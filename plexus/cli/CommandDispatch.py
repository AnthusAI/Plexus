import click
import os
import time
from dotenv import load_dotenv
from celery import Celery
from plexus.CustomLogging import logging
from kombu.utils.url import safequote
import sys
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, \
    BarColumn, TaskProgressColumn, TimeRemainingColumn, TextColumn, ProgressColumn
from rich.style import Style
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
import typing

class ItemCountColumn(ProgressColumn):
    """Renders item count and total."""
    def render(self, task: "Task") -> typing.Union[str, typing.Text]:
        """Show item count and total."""
        return f"{int(task.completed)}/{int(task.total)}"

class StatusColumn(ProgressColumn):
    """Renders status in a full line above the progress bar."""
    def render(self, task: "Task") -> typing.Union[str, typing.Text]:
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
def demo() -> None:
    """Run a demo task that processes 2000 items over 20 seconds."""
    from .CommandProgress import CommandProgress
    import time
    
    total_items = 2000
    target_duration = 20  # seconds
    sleep_per_item = target_duration / total_items
    
    logging.info("Starting demo task processing...")
    
    try:
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
            task = progress.add_task(
                "Processing...",
                total=total_items,
                status="Starting processing items..."
            )
            
            start_time = time.time()
            
            for i in range(total_items):
                current_item = i + 1
                # Get new status message
                new_status = get_progress_status(current_item, total_items)
                
                # Update progress and status
                progress.update(task, advance=1, status=new_status)
                
                # Simulate processing an item
                time.sleep(sleep_per_item)
                
                # Update command progress every 50 items
                if i % 50 == 0 or i == total_items - 1:
                    elapsed = time.time() - start_time
                    items_per_sec = current_item / elapsed
                    
                    CommandProgress.update(
                        current=current_item,
                        total=total_items,
                        status=new_status
                    )
        
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

# Remove duplicate ItemCountColumn class definition 