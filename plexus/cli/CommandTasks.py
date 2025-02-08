import sys
import shlex
import io
import asyncio
from contextlib import redirect_stdout, redirect_stderr
from celery import Task
from plexus.CustomLogging import logging
from .CommandProgress import CommandProgress, ProgressState
from datetime import datetime, timezone, timedelta
from typing import Optional
import socket
import os
import time
import random

def register_tasks(app):
    """Register Celery tasks with the application."""
    
    @app.task(
        bind=True,
        name="plexus.execute_command",
        acks_late=False
    )
    def execute_command(self: Task, command_string: str, target: str = "default/command", task_id: Optional[str] = None) -> dict:
        """Execute a Plexus command and return its result."""
        try:
            logging.info(f"Received command: '{command_string}' with target: '{target}' and task_id: '{task_id}'")
            
            # Initialize task tracking
            task = None
            api_url = os.environ.get('PLEXUS_API_URL')
            api_key = os.environ.get('PLEXUS_API_KEY')

            if not api_url or not api_key:
                logging.warning("PLEXUS_API_URL or PLEXUS_API_KEY not set, cannot track task")
            else:
                # Import API client classes at the top level
                from plexus.dashboard.api.models.task import Task
                from plexus.dashboard.api.client import PlexusDashboardClient
                
                client = PlexusDashboardClient(api_url=api_url, api_key=api_key)
                
                # Always try to get or create task at the Celery task level
                if task_id:
                    # If we have a task_id, try to get existing task
                    logging.info(f"Initializing PlexusDashboardClient to get task {task_id}")
                    
                    # Retry getting task a few times to handle timing issues
                    max_retries = 3
                    retry_delay = 1  # seconds
                    
                    for attempt in range(max_retries):
                        try:
                            task = Task.get_by_id(task_id, client)
                            logging.info(f"Successfully retrieved task {task_id}, starting processing")
                            task.start_processing()
                            break
                        except Exception as e:
                            if attempt < max_retries - 1:
                                logging.warning(f"Attempt {attempt + 1} to get Task {task_id} failed: {str(e)}, retrying...")
                                time.sleep(retry_delay)
                            else:
                                logging.error(f"All attempts to get Task {task_id} failed: {str(e)}")
                else:
                    # Create new task if no task_id provided
                    try:
                        task = Task.create(
                            client=client,
                            accountId="demo_account",  # You may want to make this configurable
                            type=command_string,
                            target=target,
                            command=command_string,
                            dispatchStatus="DISPATCHED"
                        )
                        task_id = task.id  # Set task_id for passing to command
                        logging.info(f"Created API Task record with ID: {task.id}")
                    except Exception as e:
                        logging.error(f"Failed to create task record: {str(e)}")
            
            # Only check target matching if a matcher is configured
            matcher = getattr(app.conf, "task_target_matcher", None)
            if matcher is not None:
                logging.info(f"Checking if worker accepts target '{target}'")
                if not matcher.matches(target):
                    logging.info(f"Worker does not accept target '{target}', rejecting task")
                    # Reject the task so another worker can pick it up
                    self.request.callbacks = None
                    self.request.errbacks = None
                    raise self.reject(requeue=True)
                logging.info(f"Worker accepts target '{target}'")

            logging.info(f"Executing command: '{command_string}'")
            # Parse the command string safely
            args = shlex.split(command_string)
            
            # Add task_id to args if we have one
            if task_id and '--task-id' not in args:
                args.extend(['--task-id', task_id])
            
            # Save the original argv
            original_argv = sys.argv
            
            # Capture stdout and stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            
            def progress_callback(state: ProgressState):
                """Update Celery task state with progress information."""
                # Convert time string to seconds if needed
                estimated_remaining = 0
                if state.estimated_remaining:
                    if isinstance(state.estimated_remaining, str):
                        # Parse time string like "3m 31s"
                        parts = state.estimated_remaining.split()
                        for part in parts:
                            if part.endswith('m'):
                                estimated_remaining += int(part[:-1]) * 60
                            elif part.endswith('s'):
                                estimated_remaining += int(part[:-1])
                    else:
                        estimated_remaining = float(state.estimated_remaining)

                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': state.current,
                        'total': state.total,
                        'status': state.status,
                        'elapsed_time': state.elapsed_time,
                        'estimated_remaining': estimated_remaining
                    }
                )
                
                # Update Task progress if we have a task
                if task:
                    task.update_progress(
                        state.current,
                        state.total,
                        {
                            "Running": {
                                "order": 1,
                                "totalItems": state.total,
                                "processedItems": state.current,
                                "statusMessage": state.status
                            }
                        },
                        estimated_completion_at=datetime.now(timezone.utc) + timedelta(seconds=estimated_remaining)
                    )
            
            # Set up progress reporting
            CommandProgress.set_update_callback(progress_callback)
            
            try:
                # Replace argv with our command
                sys.argv = ['plexus'] + args
                
                # Import the main CLI function
                from plexus.cli.CommandLineInterface import cli
                
                # Execute the command with output capture
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    try:
                        cli(standalone_mode=False)
                        status = 'success'
                    except SystemExit as e:
                        status = 'success' if e.code == 0 else 'error'
                    except Exception as e:
                        status = 'error'
                        logging.error(f"Command execution failed: {str(e)}", exc_info=True)
                
                # Update task status if we have a task
                if task:
                    if status == 'success':
                        task.complete_processing()
                    else:
                        # Clear progress callback immediately to prevent further updates
                        CommandProgress.set_update_callback(None)
                        
                        # Get error message from stderr if available, otherwise use exception message
                        error_msg = stderr_capture.getvalue().strip() or (str(e) if 'e' in locals() else None)
                        if error_msg:
                            task.fail_processing(error_msg)
                        else:
                            # If we somehow have no error message, find the failed stage's message
                            stages = task.get_stages()
                            if stages:
                                # Look for a failed stage first
                                failed_stage = next((stage for stage in stages if stage.status == 'FAILED'), None)
                                if failed_stage and failed_stage.statusMessage:
                                    error_msg = failed_stage.statusMessage
                                else:
                                    # If no failed stage found, use current stage's message
                                    current_stage = next((stage for stage in stages if stage.status == 'RUNNING'), None)
                                    error_msg = (current_stage.statusMessage if current_stage else None) or "Command failed"
                                task.fail_processing(error_msg)
                            else:
                                task.fail_processing("Command failed")
                
                return {
                    'status': status,
                    'command': command_string,
                    'target': target,
                    'stdout': stdout_capture.getvalue(),
                    'stderr': stderr_capture.getvalue(),
                }
                
            finally:
                # Restore the original argv
                sys.argv = original_argv
                # Only clear callback if not already cleared due to failure
                if status == 'success':
                    CommandProgress.set_update_callback(None)
                
        except Exception as e:
            logging.error(f"Command failed: {str(e)}")
            # Update task status if we have a task
            if 'task' in locals() and task:
                task.fail_processing(str(e))
            return {
                'status': 'error',
                'command': command_string,
                'target': target,
                'error': str(e),
                'stdout': stdout_capture.getvalue() if 'stdout_capture' in locals() else '',
                'stderr': stderr_capture.getvalue() if 'stderr_capture' in locals() else '',
            }
    
    @app.task(bind=True, name="plexus.demo_task")
    def demo_task(self: Task, target: str = "default/command") -> dict:
        """Run a demo task that processes 2000 items over 20 seconds."""
        from .CommandProgress import CommandProgress
        import time
        
        total_items = 2000
        target_duration = 20  # seconds
        sleep_per_item = target_duration / total_items
        
        # Parse command args to check for --fail flag
        args = shlex.split(target)
        should_fail = '--fail' in args
        fail_at = random.randint(600, 1400) if should_fail else None  # Fail between 30-70% progress
        
        logging.info("Starting demo task processing...")
        
        try:
            start_time = time.time()
            
            for i in range(total_items):
                current_item = i + 1
                
                # Simulate random failure if --fail flag is set
                if should_fail and current_item >= fail_at:
                    raise Exception(f"Simulated failure at {current_item}/{total_items} items")
                
                # Update progress every 50 items or on the last item
                if i % 50 == 0 or i == total_items - 1:
                    elapsed = time.time() - start_time
                    items_per_sec = current_item / elapsed
                    
                    # Get status message based on progress
                    percentage = (current_item / total_items) * 100
                    if percentage <= 5:
                        status = "Starting processing items..."
                    elif percentage <= 35:
                        status = "Processing items..."
                    elif percentage <= 65:
                        status = "Cruising..."
                    elif percentage <= 80:
                        status = "On autopilot..."
                    elif percentage <= 90:
                        status = "Finishing soon..."
                    elif percentage < 100:
                        status = "Almost done processing items..."
                    else:
                        status = "Finished processing items."
                    
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': current_item,
                            'total': total_items,
                            'status': status,
                            'elapsed_time': elapsed,
                            'estimated_remaining': (total_items - current_item) / items_per_sec
                        }
                    )
                
                time.sleep(sleep_per_item)
            
            total_time = time.time() - start_time
            logging.info(
                f"Demo task completed successfully in {total_time:.1f} seconds "
                f"({total_items/total_time:.1f} items/sec)"
            )
            
            return {
                'status': 'success',
                'target': target,
                'stdout': f"Processed {total_items} items in {total_time:.1f} seconds\n",
                'stderr': ''
            }
            
        except Exception as e:
            logging.error(f"Demo task failed: {str(e)}")
            return {
                'status': 'error',
                'target': target,
                'error': str(e),
                'stdout': '',
                'stderr': str(e)
            }
    
    return execute_command, demo_task 