from celery import shared_task
from plexus.reports.service import generate_report
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.task import Task
from plexus.cli.task_progress_tracker import TaskProgressTracker
import logging
import traceback

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def generate_report_task(self, task_id: str):
    """
    Celery task to generate a report asynchronously, driven by a Task ID.

    Args:
        task_id: The ID of the Task record driving this report generation.
    """
    logger.info(f"Starting report generation Celery task for Task ID: {task_id}")

    client = PlexusDashboardClient()
    # No need to create a pending report here - Task is the source of truth

    try:
        # Call the main generation service function, passing only the task_id
        # The service is now responsible for fetching the Task, creating the Report,
        # and updating Task status via TaskProgressTracker.
        # Use asyncio.run() if generate_report is async
        import asyncio
        asyncio.run(generate_report(task_id=task_id))

        # If generate_report completes without error, the Task status
        # should have been set to COMPLETED by the TaskProgressTracker within the service.
        logger.info(f"Celery task completed for report generation Task ID: {task_id}")

    except Exception as e:
        # If generate_report raises an exception, mark the Task as FAILED.
        logger.error(f"Report generation service failed for Task ID: {task_id}. Error: {e}", exc_info=True)
        error_message = f"Celery task failed: {type(e).__name__}: {e}"
        error_details_str = traceback.format_exc()

        # Update the Task status to FAILED
        try:
            # Use TaskProgressTracker to consistently update task failure status
            logger.info(f"Attempting to mark Task {task_id} as FAILED.")
            tracker = TaskProgressTracker(task_id=task_id, client=client)
            # Fetch stages first to avoid race conditions if tracker needs them
            # Although fail_task might not strictly need full stage config
            try:
                 import asyncio
                 asyncio.run(tracker.fetch_task_and_stages())
            except Exception as fetch_err:
                 logger.warning(f"Failed to fetch stages for task {task_id} before marking as failed: {fetch_err}. Proceeding to fail task anyway.")
            
            tracker.fail_task(error_message=error_message, error_details=error_details_str)
            logger.info(f"Successfully marked Task {task_id} as FAILED.")

        except Exception as update_err:
            # Log critical error if we can't even update the Task status
            logger.critical(f"CRITICAL: Failed to update Task status to FAILED for Task ID {task_id} after service error. Update Error: {update_err}", exc_info=True)

        # Re-raise the original exception to mark the Celery task itself as FAILED
        raise 