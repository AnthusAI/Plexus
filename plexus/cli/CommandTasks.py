import sys
import shlex
import io
from contextlib import redirect_stdout, redirect_stderr
from celery import Task
from plexus.CustomLogging import logging
from .CommandProgress import CommandProgress, ProgressState

def register_tasks(app):
    """Register Celery tasks with the application."""
    
    @app.task(bind=True, name="plexus.execute_command")
    def execute_command(self: Task, command_string: str) -> dict:
        """Execute a Plexus command and return its result."""
        try:
            # Parse the command string safely
            args = shlex.split(command_string)
            
            # Save the original argv
            original_argv = sys.argv
            
            # Capture stdout and stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            
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
                
                return {
                    'status': status,
                    'command': command_string,
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
            return {
                'status': 'error',
                'command': command_string,
                'error': str(e),
                'stdout': stdout_capture.getvalue() if 'stdout_capture' in locals() else '',
                'stderr': stderr_capture.getvalue() if 'stderr_capture' in locals() else '',
            }
    
    return execute_command 