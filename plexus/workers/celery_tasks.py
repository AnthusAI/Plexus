"""
Celery tasks for processing Plexus scoring jobs.
"""

import logging
from typing import Dict, Any, Optional
from celery import Task
from plexus.workers.celery_app import app
from plexus.workers.scoring_job import process_scoring_job_sync

logger = logging.getLogger(__name__)


@app.task(bind=True, name="plexus.workers.celery_tasks.process_scoring_job")
def process_scoring_job(
    self: Task,
    scoring_job_id: str,
    scorecard_name: Optional[str] = None,
    score_name: Optional[str] = None,
    item_id: Optional[str] = None,
    account_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a scoring job using the Plexus scoring engine.

    This task processes a specific item with a score using the Plexus SDK.

    Args:
        scoring_job_id: The ID of the scoring job (for result tracking)
        scorecard_name: Scorecard identifier
        score_name: Score identifier
        item_id: Item ID to score
        account_key: Account key

    Returns:
        Dictionary containing the scoring results
    """
    try:
        return process_scoring_job_sync(
            scoring_job_id=scoring_job_id,
            scorecard_name=scorecard_name,
            score_name=score_name,
            item_id=item_id,
            account_key=account_key,
        )

    except Exception as e:
        logger.error(f"Error processing scoring job {scoring_job_id}: {str(e)}", exc_info=True)

        # Re-raise the exception so Celery knows the task failed
        raise


@app.task(name="plexus.workers.celery_tasks.health_check")
def health_check() -> Dict[str, str]:
    """
    Simple health check task for monitoring worker availability.

    Returns:
        Status dictionary
    """
    return {
        "status": "healthy",
        "worker": "celery",
        "version": "1.0.0"
    }
