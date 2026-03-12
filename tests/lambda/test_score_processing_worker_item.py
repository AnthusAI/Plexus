import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _load_handler_module():
    handler_path = Path(__file__).resolve().parents[2] / "lambda_functions" / "score_processing" / "handler.py"
    spec = importlib.util.spec_from_file_location("score_processing_handler", handler_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_score_processing_job_passes_item_to_scorecard():
    handler = _load_handler_module()
    processor = handler.JobProcessor.__new__(handler.JobProcessor)
    processor.client = Mock()
    processor.account_id = "acct-1"

    fake_item = SimpleNamespace(id="item-123", text="fallback")
    fake_result = SimpleNamespace(value="ok", metadata={})
    fake_scorecard = SimpleNamespace(
        score_entire_text=AsyncMock(return_value={"score-id": fake_result})
    )
    fake_scoring_job = SimpleNamespace(itemId="item-123", update=Mock())

    with patch.object(handler.ScoringJob, "get_by_id", return_value=fake_scoring_job):
        with patch.object(handler, "resolve_scorecard_id", return_value="scorecard-id"):
            with patch.object(handler, "resolve_score_id", return_value={"id": "score-id"}):
                with patch.object(handler, "get_text_from_report", return_value="text"):
                    with patch.object(handler, "get_metadata_from_report", return_value={}):
                        with patch.object(handler, "create_scorecard_instance_for_single_score", return_value=fake_scorecard):
                            with patch.object(handler, "create_score_result_for_api", return_value=None):
                                with patch.object(handler, "Item", SimpleNamespace(get_by_id=Mock(return_value=fake_item)), create=True):
                                    await processor.process_job(
                                        "job-1",
                                        "report-1",
                                        "scorecard-external",
                                        "score-external",
                                    )

    call_kwargs = fake_scorecard.score_entire_text.call_args.kwargs
    assert call_kwargs["item"] is fake_item
