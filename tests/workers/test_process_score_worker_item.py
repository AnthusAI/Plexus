import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from plexus.workers.ProcessScoreWorker import JobProcessor


@pytest.mark.asyncio
async def test_process_job_passes_item_to_scorecard():
    processor = JobProcessor.__new__(JobProcessor)
    processor.client = Mock()
    processor.account_id = "acct-1"
    processor.response_queue_url = "https://example.com/queue"
    processor.request_queue_url = "https://example.com/request-queue"
    processor.sqs_client = Mock()

    fake_item = SimpleNamespace(id="item-123", text="fallback")
    fake_result = SimpleNamespace(value="ok", metadata={})
    fake_scorecard = SimpleNamespace(
        score_entire_text=AsyncMock(return_value={"score-id": fake_result})
    )
    fake_scoring_job = Mock()

    with patch("plexus.workers.ProcessScoreWorker.ScoringJob.get_by_id", return_value=fake_scoring_job):
        with patch("plexus.workers.ProcessScoreWorker.resolve_scorecard_id", return_value="scorecard-id"):
            with patch("plexus.workers.ProcessScoreWorker.resolve_score_id", return_value={"id": "score-id"}):
                with patch("plexus.workers.ProcessScoreWorker.get_text_from_item", return_value="text"):
                    with patch("plexus.workers.ProcessScoreWorker.get_metadata_from_item", return_value={}):
                        with patch("plexus.workers.ProcessScoreWorker.get_external_id_from_item", return_value="ext-1"):
                            with patch("plexus.workers.ProcessScoreWorker.create_scorecard_instance_for_single_score", return_value=fake_scorecard):
                                with patch("plexus.workers.ProcessScoreWorker.create_score_result", return_value="srid"):
                                    with patch("plexus.dashboard.api.models.item.Item.get_by_id", return_value=fake_item):
                                        await processor.process_job(
                                            "job-1",
                                            "item-123",
                                            "scorecard-external",
                                            "score-external",
                                            "receipt-1",
                                        )

    call_kwargs = fake_scorecard.score_entire_text.call_args.kwargs
    assert call_kwargs["item"] is fake_item
