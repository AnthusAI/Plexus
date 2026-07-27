"""
Shared scoring job execution for worker entrypoints.

This module is intentionally transport-agnostic so the same scoring behavior can
be used by Celery, HTTP, or future worker adapters.
"""

import asyncio
import json
import logging
import os
from uuid import NAMESPACE_URL, uuid5
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ScoringJobError(Exception):
    """Known scoring request failure with an HTTP-friendly status code.

    reason_code is a constant, log-safe classifier set at the raise site so
    diagnostics never depend on parsing user-influenced message text.
    """

    def __init__(self, message: str, status_code: int = 500, reason_code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.reason_code = reason_code


def score_result_id_for_job(
    *,
    scoring_job_id: str,
    item_id: str,
    scorecard_id: str,
    score_id: str,
    account_id: str,
) -> str:
    """Return a stable persistence ID for one scoped scoring job.

    The same caller job key may be retried by different workers after a gateway
    interruption. A deterministic result ID makes the normal GraphQL create
    operation converge on one database row even when two workers race before a
    result exists. It deliberately includes the full target scope so a caller
    cannot overwrite a different resource by reusing a job key.
    """
    scope = "\x1f".join((account_id, scoring_job_id, item_id, scorecard_id, score_id))
    return str(uuid5(NAMESPACE_URL, f"plexus-score-result:{scope}"))


def _find_existing_score_result(
    client: Any,
    *,
    scoring_job_id: str,
    item_id: str,
    scorecard_id: str,
    score_id: str,
    account_id: str,
) -> Optional[Dict[str, Any]]:
    """Return the single durable result already stored for a scoring job.

    `scoring_job_id` is the caller's idempotency key for synchronous scoring.
    A failed lookup must stop the request rather than allowing an uncertain retry
    to make another model call and persist another result.
    """
    query = """
    query ExistingScoreResults($filter: ModelScoreResultFilterInput!) {
      listScoreResults(filter: $filter, limit: 3) {
        items {
          id
          value
          explanation
          metadata
          scoringJobId
          itemId
          scorecardId
          scoreId
          accountId
        }
      }
    }
    """
    result = client.execute(
        query,
        {"filter": {"scoringJobId": {"eq": scoring_job_id}}},
    )
    items = (result.get("listScoreResults") or {}).get("items") or []
    matching_items = [
        item
        for item in items
        if item.get("itemId") == item_id
        and item.get("scorecardId") == scorecard_id
        and item.get("scoreId") == score_id
        and item.get("accountId") == account_id
    ]
    if items and not matching_items:
        raise ScoringJobError(
            "Scoring job ID is already bound to a different resource",
            status_code=409,
            reason_code="scoring_job_scope_conflict",
        )
    if not matching_items:
        return None
    if len(matching_items) > 1:
        raise ScoringJobError(
            "Multiple persisted results exist for this scoring job",
            status_code=409,
            reason_code="duplicate_scoring_job_results",
        )
    return matching_items[0]


def _claim_scoring_job(
    client: Any,
    *,
    scoring_job_id: str,
    item_id: str,
    scorecard_id: str,
    score_id: str,
    account_id: str,
    score_result_id: str,
) -> Dict[str, Any]:
    mutation = """
    mutation ClaimScoringJob($input: ClaimScoringJobInput!) {
      claimScoringJob(input: $input) {
        state
        scoreResultId
      }
    }
    """
    response = client.execute(
        mutation,
        {
            "input": {
                "accountId": account_id,
                "scoringJobId": scoring_job_id,
                "itemId": item_id,
                "scorecardId": scorecard_id,
                "scoreId": score_id,
                "scoreResultId": score_result_id,
            }
        },
    )
    claim = response.get("claimScoringJob")
    if not isinstance(claim, dict) or claim.get("state") not in {
        "CLAIMED",
        "COMPLETED",
        "IN_PROGRESS",
        "CONFLICT",
    }:
        raise ScoringJobError(
            "Scoring job claim returned an invalid response",
            status_code=500,
            reason_code="scoring_job_claim_failed",
        )
    return claim


def _get_score_result_by_id(client: Any, score_result_id: str) -> Optional[Dict[str, Any]]:
    query = """
    query ExistingScoreResult($id: ID!) {
      getScoreResult(id: $id) {
        id
        value
        explanation
        metadata
      }
    }
    """
    return client.execute(query, {"id": score_result_id}).get("getScoreResult")


def _existing_score_result_response(
    score_result: Dict[str, Any],
    *,
    scoring_job_id: str,
    item_id: str,
    scorecard_name: str,
    score_name: str,
) -> Dict[str, Any]:
    metadata = score_result.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    return {
        "status": "success",
        "scoring_job_id": scoring_job_id,
        "item_id": item_id,
        "scorecard": scorecard_name,
        "score": score_name,
        "value": score_result.get("value"),
        "explanation": score_result.get("explanation") or "",
        "metadata": metadata,
        "score_result_id": score_result["id"],
        "result_id": score_result["id"],
        "idempotent_replay": True,
    }


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
        raise ScoringJobError("scoring_job_id is required", status_code=400, reason_code="invalid_request")
    if not scorecard_name:
        raise ScoringJobError("scorecard is required", status_code=400, reason_code="invalid_request")
    if not score_name:
        raise ScoringJobError("score is required", status_code=400, reason_code="invalid_request")
    if not item_id:
        raise ScoringJobError("item_id is required", status_code=400, reason_code="invalid_request")

    # Import Plexus SDK components lazily so API app startup remains lightweight.
    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.dashboard.api.models.item import Item
    from plexus.dashboard.api.models.scorecard import Scorecard as ScorecardModel
    from plexus.scores.Score import Score

    account_key = account_key or os.getenv("PLEXUS_ACCOUNT_KEY")
    if not account_key:
        raise ScoringJobError(
            "PLEXUS_ACCOUNT_KEY must be set",
            status_code=500,
            reason_code="account_configuration_missing",
        )

    client = PlexusDashboardClient()

    logger.info("Fetching item %s for scoring job %s", item_id, scoring_job_id)
    item = Item.get_by_id(item_id, client)
    if not item:
        raise ScoringJobError(f"Item '{item_id}' not found", status_code=404, reason_code="item_not_found")
    item_account_id = getattr(item, "accountId", None) or account_key

    logger.info(
        "Loading scorecard and score for scoring job %s: %s/%s",
        scoring_job_id,
        scorecard_name,
        score_name,
    )

    from plexus.cli.shared.direct_memoized_resolvers import (
        direct_memoized_resolve_score_identifier,
        direct_memoized_resolve_scorecard_identifier,
    )

    scorecard_id = direct_memoized_resolve_scorecard_identifier(client, scorecard_name)
    if not scorecard_id:
        raise ScoringJobError(
            f"Scorecard '{scorecard_name}' not found",
            status_code=404,
            reason_code="scorecard_not_found",
        )

    scorecard_obj = ScorecardModel.get_by_id(scorecard_id, client)
    if not scorecard_obj:
        raise ScoringJobError(
            f"Scorecard '{scorecard_name}' not found",
            status_code=404,
            reason_code="scorecard_not_found",
        )

    score_id = direct_memoized_resolve_score_identifier(client, scorecard_id, score_name)
    if not score_id:
        raise ScoringJobError(
            f"Score '{score_name}' not found in scorecard",
            status_code=404,
            reason_code="score_not_found",
        )

    logger.info("Found score ID for scoring job %s: %s", scoring_job_id, score_id)

    existing_score_result = _find_existing_score_result(
        client,
        scoring_job_id=scoring_job_id,
        item_id=item_id,
        scorecard_id=scorecard_id,
        score_id=score_id,
        account_id=item_account_id,
    )
    if existing_score_result:
        logger.info("Reusing persisted score result for scoring job %s", scoring_job_id)
        return _existing_score_result_response(
            existing_score_result,
            scoring_job_id=scoring_job_id,
            item_id=item_id,
            scorecard_name=scorecard_name,
            score_name=score_name,
        )

    score_result_id = score_result_id_for_job(
        scoring_job_id=scoring_job_id,
        item_id=item_id,
        scorecard_id=scorecard_id,
        score_id=score_id,
        account_id=item_account_id,
    )
    claim = _claim_scoring_job(
        client,
        scoring_job_id=scoring_job_id,
        item_id=item_id,
        scorecard_id=scorecard_id,
        score_id=score_id,
        account_id=item_account_id,
        score_result_id=score_result_id,
    )
    if claim["state"] == "COMPLETED":
        completed_result = _get_score_result_by_id(client, claim["scoreResultId"])
        if not completed_result:
            raise ScoringJobError(
                "Completed scoring job result is unavailable",
                status_code=500,
                reason_code="scoring_job_completed_result_missing",
            )
        return _existing_score_result_response(
            completed_result,
            scoring_job_id=scoring_job_id,
            item_id=item_id,
            scorecard_name=scorecard_name,
            score_name=score_name,
        )
    if claim["state"] == "IN_PROGRESS":
        raise ScoringJobError(
            "Scoring job is already being processed",
            status_code=409,
            reason_code="scoring_job_in_progress",
        )
    if claim["state"] == "CONFLICT":
        raise ScoringJobError(
            "Scoring job ID is already bound to a different resource",
            status_code=409,
            reason_code="scoring_job_scope_conflict",
        )

    score_instance = Score.load(
        scorecard_identifier=scorecard_id,
        score_name=score_name,
        use_cache=True,
        yaml_only=False,
    )

    score_input = Score.Input(
        text=getattr(item, "text", ""),
        metadata={
            "item_id": item.id,
            "account_id": item_account_id,
        },
    )

    async def run_prediction():
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
        "id": score_result_id,
        "scoringJobId": scoring_job_id,
        "itemId": item_id,
        "scorecardId": scorecard_id,
        "scoreId": score_id,
        "accountId": item_account_id,
        "value": json.dumps(result_value) if not isinstance(result_value, str) else result_value,
        "reasoning": result_explanation if result_explanation else "",
        "scoreKey": score_name,
        "scorecardKey": scorecard_name,
    }

    logger.info("Storing score result for scoring job %s", scoring_job_id)
    result_response = client.execute(mutation, {"input": result_input})
    score_result_id = (
        result_response
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
