"""
Celery tasks for processing Plexus scoring jobs.

These tasks are designed to work with RabbitMQ and the private GraphQL proxy,
replacing the SQS-based score processor workflow.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from celery import Task
from plexus.workers.celery_app import app

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
    logger.info(f"Processing scoring job: {scoring_job_id}")

    try:
        # Import Plexus SDK components
        import asyncio
        from plexus.dashboard.api.client import PlexusDashboardClient
        from plexus.dashboard.api.models.item import Item
        from plexus.dashboard.api.models.scorecard import Scorecard as ScorecardModel
        from plexus.dashboard.api.models.score import Score as ScoreModel
        from plexus.scores.Score import Score

        # Get configuration
        account_key = account_key or os.getenv("PLEXUS_ACCOUNT_KEY")
        if not account_key:
            raise ValueError("PLEXUS_ACCOUNT_KEY must be set")

        # Initialize client
        client = PlexusDashboardClient()

        logger.info(f"Fetching item {item_id}")

        # Fetch the item using SDK
        item = Item.get_by_id(item_id, client)
        if not item:
            raise ValueError(f"Item {item_id} not found")

        logger.info(f"Loading scorecard and score: {scorecard_name}/{score_name}")

        # Fetch the scorecard and score IDs from the API
        scorecard_obj = ScorecardModel.get_by_key(scorecard_name, client)
        if not scorecard_obj:
            raise ValueError(f"Scorecard '{scorecard_name}' not found")

        scorecard_id = scorecard_obj.id
        logger.info(f"Found scorecard ID: {scorecard_id}")

        # Get the score ID
        score_obj = ScoreModel.get_by_name(score_name, scorecard_id, client)
        if not score_obj:
            raise ValueError(f"Score '{score_name}' not found in scorecard")

        score_id = score_obj.id
        logger.info(f"Found score ID: {score_id}")

        # Use Score.load() which handles fetching and caching from the API
        # This downloads the scorecard configuration if not already cached
        score_instance = Score.load(
            scorecard_identifier=scorecard_name,
            score_name=score_name,
            use_cache=True,
            yaml_only=False
        )

        logger.info(f"Score loaded successfully")

        logger.info(f"Executing score: {score_name}")

        # Prepare Score.Input object for scoring
        score_input = Score.Input(
            text=getattr(item, 'text', ""),
            metadata={
                "item_id": item.id,
                "account_id": getattr(item, 'accountId', account_key)
            }
        )

        # Run the prediction (handle both sync and async)
        async def run_prediction():
            async with score_instance:
                await score_instance.async_setup()
                return await score_instance.predict(score_input)

        # Execute in the event loop
        result = asyncio.run(run_prediction())

        logger.info(f"Scoring complete. Result: {result}")

        # Extract values from Score.Result object
        # Result has attributes: value, explanation, metadata, etc.
        result_value = result.value
        # Try to get explanation from direct field, fall back to metadata
        result_explanation = (
            getattr(result, 'explanation', None) or
            result.metadata.get('explanation', '') if hasattr(result, 'metadata') else ''
        )
        result_metadata = getattr(result, 'metadata', {})

        # Store the result using GraphQL mutation
        mutation = """
        mutation CreateScoreResult($input: CreateScoreResultInput!) {
          createScoreResult(input: $input) {
            id
            value
            reasoning
            createdAt
          }
        }
        """

        result_input = {
            "scoringJobId": scoring_job_id,
            "itemId": item_id,
            "scorecardId": scorecard_id,
            "scoreId": score_id,
            "accountId": account_key,
            "value": json.dumps(result_value) if not isinstance(result_value, str) else result_value,
            "reasoning": result_explanation if result_explanation else "",
            "scoreKey": score_name,
            "scorecardKey": scorecard_name
        }

        logger.info(f"Storing result via GraphQL proxy...")
        result_response = client.execute(mutation, {"input": result_input})

        logger.info(f"Result stored successfully")

        return {
            "status": "success",
            "scoring_job_id": scoring_job_id,
            "item_id": item_id,
            "scorecard": scorecard_name,
            "score": score_name,
            "value": result_value,
            "explanation": result_explanation,
            "metadata": result_metadata,
            "result_id": result_response.get("data", {}).get("createScoreResult", {}).get("id")
        }

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
