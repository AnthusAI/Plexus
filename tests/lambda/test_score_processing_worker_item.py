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
    fake_result = SimpleNamespace(
        value="ok",
        explanation='The agent said "General Kenobi" [0:01.20-0:02.00].',
        metadata={},
        start_time_seconds=1.2,
        end_time_seconds=2.0,
    )
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
                            with patch.object(handler, "create_score_result_for_api", return_value=None) as mock_create:
                                with patch.object(handler, "Item", SimpleNamespace(get_by_id=Mock(return_value=fake_item)), create=True):
                                    await processor.process_job(
                                        "job-1",
                                        "report-1",
                                        "scorecard-external",
                                        "score-external",
                                    )

    call_kwargs = fake_scorecard.score_entire_text.call_args.kwargs
    assert call_kwargs["item"] is fake_item
    create_kwargs = mock_create.call_args.kwargs
    assert create_kwargs["start_time_seconds"] == 1.2
    assert create_kwargs["end_time_seconds"] == 2.0


@pytest.mark.asyncio
async def test_create_score_result_for_api_includes_timestamp_fields():
    handler = _load_handler_module()
    captured_inputs = []

    def fake_gql(query, variables=None):
        if "listAccountByKey" in query:
            return {"listAccountByKey": {"items": [{"id": "account-1", "name": "Account"}]}}
        if "createScoreResult" in query:
            captured_inputs.append(variables["input"])
            return {
                "createScoreResult": {
                    "id": "score-result-1",
                    "createdAt": "2026-05-21T00:00:00Z",
                }
            }
        return {}

    fake_item_model = SimpleNamespace(
        upsert_by_identifiers=Mock(return_value=("item-1", True, None)),
        find_by_identifier=Mock(return_value=SimpleNamespace(id="item-1")),
    )

    with patch.object(handler, "gql", side_effect=fake_gql):
        with patch.object(handler, "ACCOUNT_KEY", "account-key"):
            with patch.object(handler, "PlexusDashboardClient", Mock(return_value=Mock())):
                with patch.object(handler, "resolve_scorecard_id", AsyncMock(return_value="scorecard-1")):
                    with patch.object(handler, "resolve_score_id", AsyncMock(return_value={"id": "score-1"})):
                        with patch.object(handler, "get_text_from_report", AsyncMock(return_value="text")):
                            with patch.object(handler, "get_metadata_from_report", AsyncMock(return_value={})):
                                with patch.object(handler, "PLEXUS_ITEM_AVAILABLE", True):
                                    with patch.object(handler, "Item", fake_item_model):
                                        await handler.create_score_result_for_api(
                                            report_id="report-1",
                                            scorecard_id="scorecard-external",
                                            score_id="score-external",
                                            value="Yes",
                                            explanation='The agent said "General Kenobi" [0:01.20-0:02.00].',
                                            start_time_seconds=5,
                                            end_time_seconds=6,
                                        )

    assert captured_inputs[0]["startTimeSeconds"] == 5.0
    assert captured_inputs[0]["endTimeSeconds"] == 6.0
