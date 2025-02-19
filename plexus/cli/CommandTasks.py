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
import subprocess

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
            # IMMEDIATELY claim the task if we have a task_id
            if task_id:
                logging.info(f"Celery assigned task {task_id} to worker - attempting immediate claim")
                api_url = os.environ.get('PLEXUS_API_URL')
                api_key = os.environ.get('PLEXUS_API_KEY')
                
                if api_url and api_key:
                    from plexus.dashboard.api.models.task import Task
                    from plexus.dashboard.api.client import PlexusDashboardClient
                    
                    client = PlexusDashboardClient(api_url=api_url, api_key=api_key)
                    worker_id = f"{socket.gethostname()}-{os.getpid()}"
                    
                    try:
                        task = Task.get_by_id(task_id, client)
                        # First update - claim the task
                        task.update(
                            celeryTaskId=self.request.id,
                            workerNodeId=worker_id,
                            status='PENDING',  # Keep as pending while claimed
                            type=task.type,
                            target=task.target,
                            command=task.command,
                            accountId=task.accountId,
                            dispatchStatus='DISPATCHED',  # Set to DISPATCHED when claimed
                            updatedAt=datetime.now(timezone.utc).isoformat()
                        )
                        logging.info(f"Successfully claimed task {task_id} with worker ID {worker_id}")

                        # Initialize stages if they don't exist
                        stages = task.get_stages()
                        if not stages:
                            logging.info("No stages found for task, creating standard stages...")
                            # Create the three standard stages
                            mutation = """
                            mutation CreateTaskStage($input: CreateTaskStageInput!) {
                                createTaskStage(input: $input) {
                                    id
                                    taskId
                                    name
                                    order
                                    status
                                    statusMessage
                                }
                            }
                            """
                            
                            # Create each stage in order
                            stage_configs = [
                                {
                                    "name": "Setup",
                                    "order": 1,
                                    "status": "PENDING",
                                    "statusMessage": "Setting up evaluation...",
                                    "taskId": task.id
                                },
                                {
                                    "name": "Processing",
                                    "order": 2,
                                    "status": "PENDING",
                                    "statusMessage": "Waiting to start processing...",
                                    "taskId": task.id
                                },
                                {
                                    "name": "Finalizing",
                                    "order": 3,
                                    "status": "PENDING",
                                    "statusMessage": "Waiting to start finalization...",
                                    "taskId": task.id
                                }
                            ]
                            
                            for stage_config in stage_configs:
                                try:
                                    client.execute(mutation, {'input': stage_config})
                                    logging.info(f"Created {stage_config['name']} stage for task {task.id}")
                                except Exception as e:
                                    logging.error(f"Failed to create {stage_config['name']} stage: {str(e)}")
                                    raise
                        
                        # Second update - start processing
                        task.update(
                            status='RUNNING',
                            startedAt=datetime.now(timezone.utc).isoformat(),
                            updatedAt=datetime.now(timezone.utc).isoformat(),
                            command=command_string  # Set the command string
                        )
                        logging.info(f"Started processing task {task_id}")
                    except Exception as e:
                        logging.error(f"Failed to claim task {task_id}: {str(e)}")
            
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
                
                # Now proceed with task processing
                if task_id:
                    # Get the task for further updates
                    task = Task.get_by_id(task_id, client)
                    # Ensure command is set
                    task.update(
                        accountId=task.accountId,
                        type=task.type,
                        status=task.status,
                        target=task.target,
                        command=command_string
                    )
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
                    # Get current stages
                    stages = task.get_stages()
                    if not stages:
                        # If no stages exist, create the three standard stages
                        stages_config = {
                            "Setup": {
                                "order": 1,
                                "statusMessage": "Setting up evaluation...",
                                "taskId": task.id  # Ensure taskId is set
                            },
                            "Processing": {
                                "order": 2,
                                "totalItems": state.total,
                                "processedItems": state.current,
                                "statusMessage": state.status,
                                "taskId": task.id  # Ensure taskId is set
                            },
                            "Finalizing": {
                                "order": 3,
                                "statusMessage": "Waiting to start finalization...",
                                "taskId": task.id  # Ensure taskId is set
                            }
                        }
                    else:
                        # Update the appropriate stage based on status message
                        stages_config = {}
                        for stage in stages:
                            stage_config = {
                                "order": stage.order,
                                "statusMessage": stage.statusMessage,
                                "taskId": task.id  # Ensure taskId is set
                            }
                            
                            # Only add progress tracking to Processing stage
                            if stage.name == "Processing":
                                stage_config.update({
                                    "totalItems": state.total,
                                    "processedItems": state.current
                                })
                            
                            stages_config[stage.name] = stage_config

                        task.update_progress(
                            state.current,
                            state.total,
                            stages_config,
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
                        # Get current stages
                        stages = task.get_stages()
                        if stages:
                            # Get total items and current progress from the Processing stage
                            processing_stage = next((stage for stage in stages if stage.name == "Processing"), None)
                            if processing_stage:
                                total_items = processing_stage.totalItems
                                current_items = processing_stage.processedItems
                                logging.info(f"Final progress: {current_items}/{total_items} items")
                            else:
                                total_items = 0
                                current_items = 0
                                logging.warning("No Processing stage found for final update")
                            
                            # First update to show logging state
                            stages_config = {}
                            for stage in stages:
                                stage_config = {
                                    "order": stage.order,
                                    "statusMessage": "Logging final evaluation state..." if stage.name == "Finalizing" else stage.statusMessage,
                                    "taskId": task.id
                                }
                                # Preserve the actual progress for the Processing stage
                                if stage.name == "Processing":
                                    stage_config["totalItems"] = total_items
                                    stage_config["processedItems"] = current_items
                                stages_config[stage.name] = stage_config
                            
                            # Update with logging state
                            task.update_progress(
                                current_items,
                                total_items,
                                stages_config
                            )

                            # Then update to show completion
                            for stage in stages:
                                stage_config = {
                                    "order": stage.order,
                                    "statusMessage": "Evaluation completed." if stage.name == "Finalizing" else stage.statusMessage,
                                    "taskId": task.id
                                }
                                # Preserve the actual progress for the Processing stage
                                if stage.name == "Processing":
                                    stage_config["totalItems"] = total_items
                                    stage_config["processedItems"] = current_items
                                stages_config[stage.name] = stage_config
                            
                            # Final update before completing
                            task.update_progress(
                                current_items,
                                total_items,
                                stages_config
                            )
                        
                        task.complete_processing()
                    else:
                        # Clear progress callback immediately to prevent further updates
                        CommandProgress.set_update_callback(None)
                        
                        # Get error message from stderr if available
                        error_msg = stderr_capture.getvalue().strip()
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