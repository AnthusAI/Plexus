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

def register_tasks(app):
    """Register Celery tasks with the application."""
    
    @app.task(bind=True, name="plexus.execute_command")
    def execute_command(self: Task, command_string: str, target: str = "default/command", task_id: Optional[str] = None) -> dict:
        """Execute a Plexus command and return its result."""
        try:
            # Check if this worker accepts this target
            matcher = getattr(app.conf, "task_target_matcher", None)
            if matcher and not matcher.matches(target):
                # Reject the task so another worker can pick it up
                self.request.callbacks = None
                self.request.errbacks = None
                raise self.reject(requeue=True)

            # Parse the command string safely
            args = shlex.split(command_string)
            
            # Save the original argv
            original_argv = sys.argv
            
            # Capture stdout and stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            
            # Initialize task if we have a task ID
            task = None
            if task_id:
                from plexus.dashboard.api.models.task import Task
                task = Task.get(task_id)
                if task:
                    task.start_processing()
            
            def progress_callback(state: ProgressState):
                """Update Celery task state with progress information."""
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': state.current,
                        'total': state.total,
                        'status': state.status,
                        'elapsed_time': state.elapsed_time,
                        'estimated_remaining': state.estimated_remaining
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
                        estimated_completion_at=datetime.now(timezone.utc) + timedelta(seconds=state.estimated_remaining)
                    )
            
            # Set up progress reporting
            CommandProgress.set_update_callback(progress_callback)
            
            try:
                # Replace argv with our command
                sys.argv = ['plexus'] + args
                
                # Import the main CLI function
                from plexus.cli.CommandLineInterface import main
                
                # Execute the command with output capture
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    try:
                        main(standalone_mode=False)
                        status = 'success'
                    except SystemExit as e:
                        status = 'success' if e.code == 0 else 'error'
                    except Exception as e:
                        status = 'error'
                        logging.error(f"Command execution failed: {str(e)}")
                
                # Update task status if we have a task
                if task:
                    if status == 'success':
                        task.complete_processing()
                    else:
                        task.fail_processing(str(e) if 'e' in locals() else 'Command failed')
                
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
                # Clear progress callback
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
        
        logging.info("Starting demo task processing...")
        
        try:
            start_time = time.time()
            
            for i in range(total_items):
                current_item = i + 1
                
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