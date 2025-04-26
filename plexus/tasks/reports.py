from celery import shared_task
from plexus.reports.service import generate_report
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.report import Report
import logging
import traceback

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def generate_report_task(self, report_config_id: str, account_id: str, parameters: dict = None):
    """
    Celery task to generate a report asynchronously.

    Args:
        report_config_id: The ID of the ReportConfiguration to use.
        account_id: The ID of the account owning the report.
        parameters: Optional dictionary of parameters for the report run.
    """
    logger.info(f"Starting report generation task for config_id: {report_config_id}, account_id: {account_id}")

    # Create a placeholder Report record first to indicate PENDING status
    client = PlexusDashboardClient()
    try:
        report = Report.create_pending_report(
            client=client,
            report_configuration_id=report_config_id,
            account_id=account_id,
            parameters=parameters,
        )
        logger.info(f"Created pending Report record with ID: {report.id}")
    except Exception as e:
        logger.error(f"Failed to create pending Report record for config {report_config_id}: {e}", exc_info=True)
        # If we can't even create the placeholder, we can't easily track failure in the DB
        # Raising the exception will mark the Celery task as failed.
        raise

    try:
        # Call the main generation service function
        # Pass the newly created report ID to the service function
        # so it can update the status directly.
        generate_report(
            report_config_id=report_config_id,
            account_id=account_id,
            parameters=parameters,
            report_id=report.id, # Pass the ID of the pending report
            task_id=self.request.id # Pass Celery task ID for potential tracking
        )
        logger.info(f"Report generation successful for report ID: {report.id}")
    except Exception as e:
        logger.error(f"Report generation failed for report ID: {report.id}: {e}", exc_info=True)
        # Update the report status to FAILED if generation fails
        try:
            Report.update_status(
                client=client,
                report_id=report.id,
                status=Report.Status.FAILED,
                error_message=str(e),
                error_details=f"Celery Task ID: {self.request.id}\n{traceback.format_exc()}" # Include traceback
            )
        except Exception as update_err:
            logger.error(f"Additionally failed to update report status to FAILED for report ID {report.id}: {update_err}", exc_info=True)
        # Re-raise the exception to mark the Celery task as FAILED
        raise 