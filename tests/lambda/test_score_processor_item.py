import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _load_handler_module():
    handler_path = Path(__file__).resolve().parents[2] / "score-processor-lambda" / "handler.py"
    spec = importlib.util.spec_from_file_location("score_processor_lambda_handler", handler_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_lambda_process_job_passes_item_to_scorecard():
    handler = _load_handler_module()
    processor = handler.LambdaJobProcessor.__new__(handler.LambdaJobProcessor)
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

    with patch.object(handler.ScoringJob, "get_by_id", return_value=fake_scoring_job):
        with patch.object(handler, "resolve_scorecard_id", return_value="scorecard-id"):
            with patch.object(handler, "resolve_score_id", return_value={"id": "score-id"}):
                with patch.object(handler, "get_text_from_item", return_value="text"):
                    with patch.object(handler, "get_metadata_from_item", return_value={}):
                        with patch.object(handler, "get_external_id_from_item", return_value="ext-1"):
                            with patch.object(handler, "create_scorecard_instance_for_single_score", return_value=fake_scorecard):
                                with patch.object(handler, "create_score_result", return_value="srid"):
                                    with patch.object(handler, "Item", SimpleNamespace(get_by_id=Mock(return_value=fake_item)), create=True):
                                        await processor.process_job(
                                            "job-1",
                                            "item-123",
                                            "scorecard-external",
                                            "score-external",
                                            receipt_handle=None,
                                        )

    call_kwargs = fake_scorecard.score_entire_text.call_args.kwargs
    assert call_kwargs["item"] is fake_item
