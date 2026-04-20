from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plexus.reports.blocks.acceptance_rate_timeline import AcceptanceRateTimeline


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.account_id = "acct-1"
    return client


@pytest.mark.asyncio
async def test_acceptance_rate_timeline_buckets_and_counts(mock_api_client):
    block = AcceptanceRateTimeline(
        config={
            "scorecard": "sc-1",
            "score": "score-1",
            "start_date": "2026-04-01",
            "end_date": "2026-04-15",
            "bucket_type": "trailing_7d",
            "bucket_count": 2,
            "show_bucket_details": True,
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    score = MagicMock(id="score-1", name="Test Score")

    score_results = [
        # Bucket 0 (Apr 1..8)
        {
            "id": "sr-1",
            "itemId": "item-a",
            "scorecardId": "sc-1",
            "scoreId": "score-1",
            "value": "yes",
            "type": "prediction",
            "status": "COMPLETED",
            "code": "200",
            "evaluationId": None,
            "updatedAt": "2026-04-02T12:00:00+00:00",
            "score": {"id": "score-1", "name": "Test Score"},
        },
        # Bucket 1 (Apr 8..15)
        {
            "id": "sr-2",
            "itemId": "item-b",
            "scorecardId": "sc-1",
            "scoreId": "score-1",
            "value": "yes",
            "type": "prediction",
            "status": "COMPLETED",
            "code": "200",
            "evaluationId": None,
            "updatedAt": "2026-04-10T12:00:00+00:00",
            "score": {"id": "score-1", "name": "Test Score"},
        },
    ]
    feedback_items = [
        {
            "id": "fi-1",
            "itemId": "item-b",
            "scorecardId": "sc-1",
            "scoreId": "score-1",
            "initialAnswerValue": "yes",
            "finalAnswerValue": "no",
            "isInvalid": False,
            "editedAt": "2026-04-11T01:00:00+00:00",
            "createdAt": "2026-04-11T01:00:00+00:00",
            "updatedAt": "2026-04-11T01:00:00+00:00",
        }
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_score", new=AsyncMock(return_value=score)),
        patch.object(block, "_fetch_score_results_window", new=AsyncMock(return_value=score_results)),
        patch.object(block, "_fetch_feedback_items_window", new=AsyncMock(return_value=feedback_items)),
    ):
        output, _ = await block.generate()

    assert output["report_type"] == "acceptance_rate_timeline"
    assert output["show_bucket_details"] is True
    points = output["points"]
    assert len(points) == 2

    # Bucket 0: 1 accepted, 0 corrected
    assert points[0]["total_score_results"] == 1
    assert points[0]["accepted_score_results"] == 1
    assert points[0]["corrected_score_results"] == 0
    assert points[0]["score_result_acceptance_rate"] == 1.0

    # Bucket 1: 0 accepted, 1 corrected (feedback flips yes->no)
    assert points[1]["total_score_results"] == 1
    assert points[1]["accepted_score_results"] == 0
    assert points[1]["corrected_score_results"] == 1
    assert points[1]["score_result_acceptance_rate"] == 0.0
    assert points[1]["feedback_items_total"] == 1
    assert points[1]["feedback_items_valid"] == 1
    assert points[1]["feedback_items_changed"] == 1

    summary = output["summary"]
    assert summary["total_score_results"] == 2
    assert summary["accepted_score_results"] == 1
    assert summary["corrected_score_results"] == 1
    assert summary["score_result_acceptance_rate"] == 0.5
    assert summary["feedback_items_total"] == 1
    assert summary["feedback_items_valid"] == 1
    assert summary["feedback_items_changed"] == 1
    assert summary["score_results_with_feedback"] == 1
