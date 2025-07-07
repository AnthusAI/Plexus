import sys
import shlex
import io
import asyncio
import json
from contextlib import redirect_stdout, redirect_stderr
from celery import Task
from plexus.CustomLogging import logging
from .CommandProgress import CommandProgress, ProgressState
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import socket
import os
import time
import random
import subprocess
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from .universal_code import (
    generate_universal_code_yaml, 
    detect_task_type_from_command,
    extract_scorecard_from_command,
    extract_score_from_command
)
from .command_output import CommandOutputManager, set_output_manager

# Load environment variables from .env file
load_dotenv()

def upload_file_to_s3(bucket_name: str, key: str, content: str, content_type: str = 'text/plain') -> bool:
    """
    Upload a file to S3.
    
    Args:
        bucket_name: S3 bucket name
        key: S3 object key
        content: File content as string
        content_type: MIME type of the content
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        s3_client = boto3.client('s3')
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=content.encode('utf-8'),
            ContentType=content_type
        )
        logging.info(f"Successfully uploaded file to s3://{bucket_name}/{key}")
        return True
    except ClientError as e:
        logging.error(f"Failed to upload file to S3: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error uploading to S3: {e}")
        return False


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
            
            status = 'error'  # Initialize status before the try block
            
            # Set up output manager for commands to use
            output_manager = None
            format_type = None
            
            # Detect format from command args
            if '--format' in command_string:
                for i, arg in enumerate(args):
                    if arg == '--format' and i + 1 < len(args):
                        format_type = args[i + 1]
                        break
                    elif arg.startswith('--format='):
                        format_type = arg.split('=', 1)[1]
                        break
            
            if task_id:
                output_manager = CommandOutputManager(task_id=task_id, format_type=format_type)
                set_output_manager(output_manager)
                logging.info(f"Set up output manager for task {task_id} with format: {format_type}")
            
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
                        
                        # Generate Universal Code and upload attachments before completing
                        stdout_content = stdout_capture.getvalue()
                        stderr_content = stderr_capture.getvalue()
                        
                        # Detect task type and extract context from command
                        task_type = detect_task_type_from_command(command_string)
                        scorecard_name = extract_scorecard_from_command(command_string)
                        score_name = extract_score_from_command(command_string)
                        
                        # Generate Universal Code YAML
                        universal_code_yaml = None
                        attached_files = []
                        
                        # Universal Code will be generated after file uploads
                        
                        # Upload command-generated output files and logs to S3
                        bucket_name = os.getenv('AMPLIFY_STORAGE_TASKATTACHMENTS_BUCKET_NAME')
                        logging.info(f"Bucket name from env: {bucket_name}")
                        if bucket_name and task_id:
                            # Upload any output files created by the command
                            if output_manager:
                                created_files = output_manager.get_created_files()
                                logging.info(f"Command created files: {list(created_files.keys())}")
                                for filename, file_path in created_files.items():
                                    if os.path.exists(file_path):
                                        try:
                                            with open(file_path, 'r', encoding='utf-8') as f:
                                                file_content = f.read()
                                            
                                            # Determine content type
                                            content_type = 'text/plain'
                                            if filename.endswith('.json'):
                                                content_type = 'application/json'
                                            elif filename.endswith('.yaml') or filename.endswith('.yml'):
                                                content_type = 'text/yaml'
                                            elif filename.endswith('.csv'):
                                                content_type = 'text/csv'
                                            
                                            s3_key = f"tasks/{task_id}/{filename}"
                                            if upload_file_to_s3(bucket_name, s3_key, file_content, content_type):
                                                attached_files.append(s3_key)
                                                logging.info(f"Uploaded command output file: {s3_key}")
                                        except Exception as e:
                                            logging.error(f"Failed to upload output file {filename}: {e}")
                                    else:
                                        logging.warning(f"Expected output file does not exist: {file_path}")
                            
                            # Upload stdout as separate file if we have content
                            if stdout_content.strip():
                                stdout_key = f"tasks/{task_id}/stdout.txt"
                                if upload_file_to_s3(bucket_name, stdout_key, stdout_content, 'text/plain'):
                                    attached_files.append(stdout_key)
                                    logging.info(f"Uploaded stdout: {stdout_key}")
                            
                            # Upload stderr as separate file if we have content
                            if stderr_content.strip():
                                stderr_key = f"tasks/{task_id}/stderr.txt"
                                if upload_file_to_s3(bucket_name, stderr_key, stderr_content, 'text/plain'):
                                    attached_files.append(stderr_key)
                                    logging.info(f"Uploaded stderr: {stderr_key}")
                        else:
                            if not bucket_name:
                                logging.warning("AMPLIFY_STORAGE_TASKATTACHMENTS_BUCKET_NAME not set, skipping file uploads")
                        
                        # NOW generate Universal Code YAML using available clean data
                        try:
                            if output_manager:
                                created_files = output_manager.get_created_files()
                                output_file = created_files.get('output.json')
                                
                                if output_file and os.path.exists(output_file):
                                    # Use clean JSON output for Universal Code
                                    try:
                                        with open(output_file, 'r', encoding='utf-8') as f:
                                            clean_json_data = json.load(f)
                                        universal_code_yaml = generate_universal_code_yaml(
                                            command=command_string,
                                            output_data=clean_json_data,
                                            task_type=task_type,
                                            scorecard_name=scorecard_name,
                                            score_name=score_name
                                        )
                                        logging.info("Generated Universal Code from clean JSON output file")
                                    except Exception as e:
                                        logging.warning(f"Failed to use clean JSON for Universal Code: {e}")
                                        # Fallback to basic info
                                        universal_code_yaml = generate_universal_code_yaml(
                                            command=command_string,
                                            output_data={"status": "completed", "note": "Output files created successfully"},
                                            task_type=task_type,
                                            scorecard_name=scorecard_name,
                                            score_name=score_name
                                        )
                                else:
                                    # No clean output file, use basic task completion info
                                    logging.info("No output.json file found, using basic completion info for Universal Code")
                                    universal_code_yaml = generate_universal_code_yaml(
                                        command=command_string,
                                        output_data={"status": "completed", "note": "Task completed successfully"},
                                        task_type=task_type,
                                        scorecard_name=scorecard_name,
                                        score_name=score_name
                                    )
                            else:
                                # No output manager, use basic completion info
                                logging.info("No output manager available, using basic completion info for Universal Code")
                                universal_code_yaml = generate_universal_code_yaml(
                                    command=command_string,
                                    output_data={"status": "completed", "output_summary": "Command completed successfully"},
                                    task_type=task_type,
                                    scorecard_name=scorecard_name,
                                    score_name=score_name
                                )
                        except Exception as e:
                            logging.error(f"Failed to generate Universal Code YAML: {e}")
                            # Create a simple fallback
                            universal_code_yaml = f"""# {task_type} Task Output
#
# Command: {command_string}
# Status: Completed successfully
# Generated: {datetime.now(timezone.utc).isoformat()}

task_info:
  command: {command_string}
  type: {task_type}
  status: completed
"""
                        
                        # Store the command output and Universal Code in the task before completing
                        try:
                            update_data = {
                                'stdout': stdout_content,
                                'stderr': stderr_content,
                            }
                            
                            if universal_code_yaml:
                                update_data['output'] = universal_code_yaml
                            
                            if attached_files:
                                update_data['attachedFiles'] = attached_files
                            
                            task.update(**update_data)
                        except Exception as e:
                            logging.error(f"Failed to store command output in task: {str(e)}")
                        
                        task.complete_processing()
                    else:
                        # Clear progress callback immediately to prevent further updates
                        CommandProgress.set_update_callback(None)
                        
                        # Get error message from stderr if available
                        error_msg = stderr_capture.getvalue().strip()
                        
                        # Generate Universal Code and upload attachments for failed task
                        stdout_content = stdout_capture.getvalue()
                        stderr_content = stderr_capture.getvalue()
                        
                        # Generate error-focused Universal Code
                        task_type = detect_task_type_from_command(command_string)
                        scorecard_name = extract_scorecard_from_command(command_string)
                        score_name = extract_score_from_command(command_string)
                        
                        error_yaml = None
                        attached_files = []
                        
                        try:
                            error_data = {
                                "status": "error",
                                "error_message": error_msg,
                                "stdout": stdout_content if stdout_content else None,
                                "stderr": stderr_content if stderr_content else None
                            }
                            error_yaml = generate_universal_code_yaml(
                                command=command_string,
                                output_data=error_data,
                                task_type=f"{task_type} (Failed)",
                                scorecard_name=scorecard_name,
                                score_name=score_name
                            )
                        except Exception as e:
                            logging.error(f"Failed to generate error Universal Code: {e}")
                        
                        # Upload error files
                        bucket_name = os.getenv('AMPLIFY_STORAGE_TASKATTACHMENTS_BUCKET_NAME')
                        if bucket_name and task_id:
                            # Upload stdout as separate file if we have content
                            if stdout_content.strip():
                                stdout_key = f"tasks/{task_id}/stdout.txt"
                                if upload_file_to_s3(bucket_name, stdout_key, stdout_content, 'text/plain'):
                                    attached_files.append(stdout_key)
                            
                            # Upload stderr as separate file if we have content
                            if stderr_content.strip():
                                stderr_key = f"tasks/{task_id}/stderr.txt"
                                if upload_file_to_s3(bucket_name, stderr_key, stderr_content, 'text/plain'):
                                    attached_files.append(stderr_key)
                        
                        # Store the command output and error info in the task before failing
                        try:
                            update_data = {
                                'stdout': stdout_content,
                                'stderr': stderr_content,
                            }
                            
                            if error_yaml:
                                update_data['error'] = error_yaml
                                
                            if attached_files:
                                update_data['attachedFiles'] = attached_files
                                
                            task.update(**update_data)
                        except Exception as e:
                            logging.error(f"Failed to store command output in task: {str(e)}")
                        
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
                
                # Return a result dict with stdout and stderr
                result = {
                    'status': status,
                    'command': command_string,
                    'target': target,
                    'stdout': stdout_capture.getvalue(),
                    'stderr': stderr_capture.getvalue(),
                    'started_at': datetime.now(timezone.utc).timestamp(),
                    'completed_at': datetime.now(timezone.utc).timestamp()
                }
                
                # Task status update is already handled above in the success/failure branches

                return result
                
            finally:
                # Restore the original argv
                sys.argv = original_argv
                # Only clear callback if not already cleared due to failure
                if status == 'success':
                    CommandProgress.set_update_callback(None)
                # Clean up output manager
                if output_manager:
                    output_manager.cleanup()
                    set_output_manager(None)
                
        except Exception as e:
            logging.error(f"Error executing command '{command_string}': {e}", exc_info=True)
            
            # Return an error result
            result = {
                'status': 'error',
                'command': command_string,
                'target': target,
                'error': str(e),
                'stdout': stdout_capture.getvalue() if 'stdout_capture' in locals() else '',
                'stderr': stderr_capture.getvalue() if 'stderr_capture' in locals() else '',
                'started_at': datetime.now(timezone.utc).timestamp(),
                'completed_at': datetime.now(timezone.utc).timestamp()
            }
            
            # Update task status to failed if available
            if 'task' in locals() and task:
                try:
                    stdout_content = stdout_capture.getvalue() if 'stdout_capture' in locals() else ''
                    stderr_content = stderr_capture.getvalue() if 'stderr_capture' in locals() else ''
                    
                    # Generate error Universal Code for exception
                    error_yaml = None
                    attached_files = []
                    
                    if 'command_string' in locals():
                        try:
                            task_type = detect_task_type_from_command(command_string)
                            scorecard_name = extract_scorecard_from_command(command_string)
                            score_name = extract_score_from_command(command_string)
                            
                            error_data = {
                                "status": "exception",
                                "exception": str(e),
                                "traceback": str(sys.exc_info()) if sys.exc_info() else None,
                                "stdout": stdout_content if stdout_content else None,
                                "stderr": stderr_content if stderr_content else None
                            }
                            error_yaml = generate_universal_code_yaml(
                                command=command_string,
                                output_data=error_data,
                                task_type=f"{task_type} (Exception)",
                                scorecard_name=scorecard_name,
                                score_name=score_name
                            )
                        except Exception as yaml_error:
                            logging.error(f"Failed to generate exception Universal Code: {yaml_error}")
                        
                        # Upload exception files
                        bucket_name = os.getenv('AMPLIFY_STORAGE_TASKATTACHMENTS_BUCKET_NAME')
                        if bucket_name and 'task_id' in locals() and task_id:
                            # Upload exception details
                            exception_content = f"EXCEPTION: {str(e)}\nTRACEBACK: {str(sys.exc_info())}"
                            exception_key = f"tasks/{task_id}/exception.txt"
                            if upload_file_to_s3(bucket_name, exception_key, exception_content, 'text/plain'):
                                attached_files.append(exception_key)
                            
                            # Upload stdout as separate file if we have content
                            if stdout_content.strip():
                                stdout_key = f"tasks/{task_id}/stdout.txt"
                                if upload_file_to_s3(bucket_name, stdout_key, stdout_content, 'text/plain'):
                                    attached_files.append(stdout_key)
                            
                            # Upload stderr as separate file if we have content
                            if stderr_content.strip():
                                stderr_key = f"tasks/{task_id}/stderr.txt"
                                if upload_file_to_s3(bucket_name, stderr_key, stderr_content, 'text/plain'):
                                    attached_files.append(stderr_key)
                    
                    update_data = {
                        'status': 'FAILED',
                        'errorMessage': str(e),
                        'errorDetails': {"traceback": str(sys.exc_info())} if sys.exc_info() else None,
                        'stdout': stdout_content,
                        'stderr': stderr_content,
                        'completedAt': datetime.now(timezone.utc).isoformat()
                    }
                    
                    if error_yaml:
                        update_data['error'] = error_yaml
                        
                    if attached_files:
                        update_data['attachedFiles'] = attached_files
                    
                    task.update(**update_data)
                except Exception as update_error:
                    logging.error(f"Failed to update task status to failed: {str(update_error)}")
            
            return result
    
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