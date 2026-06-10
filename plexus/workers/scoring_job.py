"""
Shared scoring job execution for worker entrypoints.

This module is intentionally transport-agnostic so the same scoring behavior can
be used by Celery, HTTP, or future worker adapters.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ScoringJobError(Exception):
    """Known scoring request failure with an HTTP-friendly status code."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


def process_scoring_job_sync(
    scoring_job_id: str,
    scorecard_name: Optional[str] = None,
    score_name: Optional[str] = None,
    item_id: Optional[str] = None,
    account_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a scoring job using the Plexus scoring engine.

    Args:
        scoring_job_id: ID of the scoring job for result tracking.
        scorecard_name: Scorecard identifier.
        score_name: Score identifier.
        item_id: Item ID to score.
        account_key: Optional account key override.

    Returns:
        Dictionary containing the scoring result and persisted ScoreResult ID.
    """
    logger.info("Processing scoring job: %s", scoring_job_id)

    if not scoring_job_id:
        raise ScoringJobError("scoring_job_id is required", status_code=400)
    if not scorecard_name:
        raise ScoringJobError("scorecard is required", status_code=400)
    if not score_name:
        raise ScoringJobError("score is required", status_code=400)
    if not item_id:
        raise ScoringJobError("item_id is required", status_code=400)

    # Import Plexus SDK components lazily so API app startup remains lightweight.
    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.dashboard.api.models.item import Item
    from plexus.dashboard.api.models.score import Score as ScoreModel
    from plexus.dashboard.api.models.scorecard import Scorecard as ScorecardModel
    from plexus.scores.Score import Score

    account_key = account_key or os.getenv("PLEXUS_ACCOUNT_KEY")
    if not account_key:
        raise ScoringJobError("PLEXUS_ACCOUNT_KEY must be set", status_code=400)

    client = PlexusDashboardClient()

    logger.info("Fetching item %s for scoring job %s", item_id, scoring_job_id)
    item = Item.get_by_id(item_id, client)
    if not item:
        raise ScoringJobError(f"Item '{item_id}' not found", status_code=404)

    logger.info(
        "Loading scorecard and score for scoring job %s: %s/%s",
        scoring_job_id,
        scorecard_name,
        score_name,
    )

    from plexus.cli.shared.direct_memoized_resolvers import (
        direct_memoized_resolve_scorecard_identifier,
    )

    scorecard_id = direct_memoized_resolve_scorecard_identifier(client, scorecard_name)
    if not scorecard_id:
        raise ScoringJobError(f"Scorecard '{scorecard_name}' not found", status_code=404)

    scorecard_obj = ScorecardModel.get_by_id(scorecard_id, client)
    if not scorecard_obj:
        raise ScoringJobError(f"Scorecard '{scorecard_name}' not found", status_code=404)

    score_obj = ScoreModel.get_by_name(score_name, scorecard_id, client)
    if not score_obj:
        raise ScoringJobError(
            f"Score '{score_name}' not found in scorecard",
            status_code=404,
        )

    score_id = score_obj.id
    logger.info("Found score ID for scoring job %s: %s", scoring_job_id, score_id)

    score_instance = Score.load(
        scorecard_identifier=scorecard_name,
        score_name=score_name,
        use_cache=True,
        yaml_only=False,
    )

    score_input = Score.Input(
        text=getattr(item, "text", ""),
        metadata={
            "item_id": item.id,
            "account_id": getattr(item, "accountId", account_key),
        },
    )

    async def run_prediction():
        async with score_instance:
            await score_instance.async_setup()
            return await score_instance.predict(score_input)

    result = asyncio.run(run_prediction())
    result_value = result.value
    result_metadata = getattr(result, "metadata", {}) or {}
    result_explanation = getattr(result, "explanation", None) or result_metadata.get(
        "explanation",
        "",
    )

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
        "scorecardKey": scorecard_name,
    }

    logger.info("Storing score result for scoring job %s", scoring_job_id)
    result_response = client.execute(mutation, {"input": result_input})
    score_result_id = (
        result_response.get("data", {})
        .get("createScoreResult", {})
        .get("id")
    )

    return {
        "status": "success",
        "scoring_job_id": scoring_job_id,
        "item_id": item_id,
        "scorecard": scorecard_name,
        "score": score_name,
        "value": result_value,
        "explanation": result_explanation,
        "metadata": result_metadata,
        "score_result_id": score_result_id,
        "result_id": score_result_id,
    }
