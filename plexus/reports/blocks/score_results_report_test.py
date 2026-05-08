from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import json

import pytest

from plexus.reports.blocks.score_results_report import (
    ScoreResultsReport,
    _ResolvedItem,
    _ResolvedScoreScope,
)


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.account_id = "acct-1"
    return client


def _block(config, api_client):
    return ScoreResultsReport(config=config, params={"account_id": "acct-1"}, api_client=api_client)


@pytest.mark.asyncio
async def test_scorecard_scope_runs_all_scores_and_groups_results_by_score(mock_api_client):
    block = _block({"scorecard": "1562", "ids": ["a", "b"]}, mock_api_client)
    scorecard = SimpleNamespace(id="sc-1", name="Test Scorecard")
    scopes = [
        _ResolvedScoreScope(score_id="score-1", score_name="Score 1"),
        _ResolvedScoreScope(score_id="score-2", score_name="Score 2"),
    ]
    resolved_items = [
        _ResolvedItem(input_identifier="a", item_id="item-a", resolution_source="id", order_index=0),
        _ResolvedItem(input_identifier="b", item_id="item-b", resolution_source="identifier", order_index=1),
    ]
    unresolved = [{"input_identifier": "x", "status": "unresolved", "error": "Not found"}]

    async def _prediction_side_effect(scorecard_identifier, score_scope, item):
        return (
            score_scope.score_id,
            {
                "input_identifier": item.input_identifier,
                "resolved_item_id": item.item_id,
                "status": "success",
                "score_result_id": f"sr-{score_scope.score_id}-{item.item_id}",
                "value": "yes",
                "explanation": "ok",
                "cost": {"total_cost": 0.1},
                "trace": {"node_results": []},
                "error": None,
                "_order_index": item.order_index,
            },
            None,
        )

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=scopes)),
        patch.object(block, "_resolve_account_id", new=AsyncMock(return_value="acct-1")),
        patch.object(block, "_resolve_items", new=AsyncMock(return_value=(resolved_items, unresolved))),
        patch.object(block, "_run_prediction_for_item_score", new=AsyncMock(side_effect=_prediction_side_effect)),
    ):
        output, _ = await block.generate()

    assert output["report_type"] == "score_results_report"
    assert output["scope"] == "scorecard_all_scores"
    assert output["score_id"] is None
    assert [score["score_id"] for score in output["scores"]] == ["score-1", "score-2"]
    assert [row["input_identifier"] for row in output["scores"][0]["results"]] == ["a", "b"]
    assert [row["input_identifier"] for row in output["scores"][1]["results"]] == ["a", "b"]
    assert output["unresolved_identifiers"] == unresolved
    assert output["summary"]["total_predictions"] == 4
    assert output["summary"]["failed_predictions"] == 0
    assert output["summary"]["successful_predictions"] == 4


@pytest.mark.asyncio
async def test_single_score_scope_sets_score_fields(mock_api_client):
    block = _block({"scorecard": "1562", "score": "my-score", "ids": ["a"]}, mock_api_client)
    scorecard = SimpleNamespace(id="sc-1", name="Test Scorecard")
    scope = _ResolvedScoreScope(score_id="score-1", score_name="Score 1")
    resolved_items = [_ResolvedItem(input_identifier="a", item_id="item-a", resolution_source="id", order_index=0)]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])) as resolve_scores,
        patch.object(block, "_resolve_account_id", new=AsyncMock(return_value="acct-1")),
        patch.object(block, "_resolve_items", new=AsyncMock(return_value=(resolved_items, []))),
        patch.object(
            block,
            "_run_prediction_for_item_score",
            new=AsyncMock(
                return_value=(
                    "score-1",
                    {
                        "input_identifier": "a",
                        "resolved_item_id": "item-a",
                        "status": "success",
                        "score_result_id": "sr-1",
                        "value": "yes",
                        "explanation": "ok",
                        "cost": {"total_cost": 0.2},
                        "trace": {"node_results": []},
                        "error": None,
                        "_order_index": 0,
                    },
                    None,
                )
            ),
        ),
    ):
        output, _ = await block.generate()

    resolve_scores.assert_awaited_once_with(scorecard_id="sc-1", score_identifier="my-score")
    assert output["scope"] == "single_score"
    assert output["score_id"] == "score-1"
    assert output["score_name"] == "Score 1"


@pytest.mark.asyncio
async def test_prediction_failures_are_reported_without_failing_report(mock_api_client):
    block = _block({"scorecard": "1562", "ids": ["a"]}, mock_api_client)
    scorecard = SimpleNamespace(id="sc-1", name="Test Scorecard")
    scope = _ResolvedScoreScope(score_id="score-1", score_name="Score 1")
    resolved_items = [_ResolvedItem(input_identifier="a", item_id="item-a", resolution_source="id", order_index=0)]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])),
        patch.object(block, "_resolve_account_id", new=AsyncMock(return_value="acct-1")),
        patch.object(block, "_resolve_items", new=AsyncMock(return_value=(resolved_items, []))),
        patch.object(
            block,
            "_run_prediction_for_item_score",
            new=AsyncMock(
                return_value=(
                    "score-1",
                    {
                        "input_identifier": "a",
                        "resolved_item_id": "item-a",
                        "status": "failed",
                        "score_result_id": None,
                        "value": None,
                        "explanation": None,
                        "cost": None,
                        "trace": None,
                        "error": "Prediction failed",
                        "_order_index": 0,
                    },
                    {
                        "input_identifier": "a",
                        "resolved_item_id": "item-a",
                        "score_id": "score-1",
                        "score_name": "Score 1",
                        "error": "Prediction failed",
                    },
                )
            ),
        ),
    ):
        output, _ = await block.generate()

    assert output["scores"][0]["results"][0]["status"] == "failed"
    assert output["failed_predictions"] == [
        {
            "input_identifier": "a",
            "resolved_item_id": "item-a",
            "score_id": "score-1",
            "score_name": "Score 1",
            "error": "Prediction failed",
        }
    ]
    assert output["summary"]["total_predictions"] == 1
    assert output["summary"]["failed_predictions"] == 1


def test_parse_ids_accepts_comma_and_list_and_dedupes(mock_api_client):
    block = _block({"scorecard": "1562", "ids": "one,two, one", "id": ["three", "two"]}, mock_api_client)
    assert block._parse_ids() == ["one", "two", "three"]


@pytest.mark.asyncio
async def test_generate_errors_when_no_identifiers(mock_api_client):
    block = _block({"scorecard": "1562"}, mock_api_client)
    output, _ = await block.generate()
    assert "At least one item identifier is required" in output["error"]


@pytest.mark.asyncio
async def test_generate_output_is_json_serializable_when_cost_contains_decimal(mock_api_client):
    block = _block({"scorecard": "1562", "ids": ["a"]}, mock_api_client)
    scorecard = SimpleNamespace(id="sc-1", name="Test Scorecard")
    scope = _ResolvedScoreScope(score_id="score-1", score_name="Score 1")
    resolved_items = [_ResolvedItem(input_identifier="a", item_id="item-a", resolution_source="id", order_index=0)]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])),
        patch.object(block, "_resolve_account_id", new=AsyncMock(return_value="acct-1")),
        patch.object(block, "_resolve_items", new=AsyncMock(return_value=(resolved_items, []))),
        patch.object(
            block,
            "_run_prediction_for_item_score",
            new=AsyncMock(
                return_value=(
                    "score-1",
                    {
                        "input_identifier": "a",
                        "resolved_item_id": "item-a",
                        "status": "success",
                        "score_result_id": "sr-1",
                        "value": "yes",
                        "explanation": "ok",
                        "cost": {"total_cost": Decimal("0.25"), "parts": [Decimal("0.10"), Decimal("0.15")]},
                        "trace": {"created_at": "2026-05-07T00:00:00Z"},
                        "error": None,
                        "_order_index": 0,
                    },
                    None,
                )
            ),
        ),
    ):
        output, _ = await block.generate()

    assert output["scores"][0]["results"][0]["cost"]["total_cost"] == 0.25
    json.dumps(output)
