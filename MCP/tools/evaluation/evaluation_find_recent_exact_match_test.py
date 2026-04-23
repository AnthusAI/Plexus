#!/usr/bin/env python3
"""Unit tests for strict matching in plexus_evaluation_find_recent."""

import json
from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.unit


def _register_find_recent_tool():
    from tools.evaluation.evaluations import register_evaluation_tools

    mock_mcp = Mock()
    registered_tools = {}

    def mock_tool_decorator():
        def decorator(func):
            registered_tools[func.__name__] = func
            return func

        return decorator

    mock_mcp.tool = mock_tool_decorator
    register_evaluation_tools(mock_mcp)
    return registered_tools["plexus_evaluation_find_recent"]


class TestEvaluationFindRecentExactMatch:
    @pytest.mark.asyncio
    async def test_accuracy_cache_miss_when_dataset_id_differs(self):
        tool = _register_find_recent_tool()

        mock_client = Mock()
        mock_client.execute.return_value = {
            "listEvaluationByScoreVersionIdAndCreatedAt": {
                "items": [
                    {
                        "id": "eval-acc-1",
                        "type": "accuracy",
                        "status": "COMPLETED",
                        "scoreVersionId": "ver-1",
                        "totalItems": 100,
                        "createdAt": "2026-04-22T10:00:00Z",
                    }
                ]
            }
        }

        eval_info = {
            "id": "eval-acc-1",
            "type": "accuracy",
            "status": "COMPLETED",
            "score_version_id": "ver-1",
            "created_at": "2026-04-22T10:00:00Z",
            "parameters": {"dataset_id": "ds-old"},
        }

        with patch("plexus.dashboard.api.client.PlexusDashboardClient", return_value=mock_client), patch(
            "plexus.Evaluation.Evaluation.get_evaluation_info",
            return_value=eval_info,
        ):
            payload = json.loads(
                await tool(
                    score_version_id="ver-1",
                    evaluation_type="accuracy",
                    max_age_hours=168,
                    min_items=80,
                    dataset_id="ds-new",
                )
            )

        assert payload["found"] is False

    @pytest.mark.asyncio
    async def test_feedback_cache_miss_when_watermark_is_newer(self):
        tool = _register_find_recent_tool()

        mock_client = Mock()
        mock_client.execute.return_value = {
            "listEvaluationByScoreVersionIdAndCreatedAt": {
                "items": [
                    {
                        "id": "eval-fb-1",
                        "type": "feedback",
                        "status": "COMPLETED",
                        "scoreVersionId": "ver-1",
                        "totalItems": 120,
                        "createdAt": "2026-04-22T10:00:00Z",
                    }
                ]
            }
        }

        eval_info = {
            "id": "eval-fb-1",
            "type": "feedback",
            "status": "COMPLETED",
            "score_version_id": "ver-1",
            "created_at": "2026-04-22T10:00:00Z",
            "parameters": {
                "days": 180,
                "max_feedback_items": 100,
                "sampling_mode": "newest",
            },
        }

        with patch("plexus.dashboard.api.client.PlexusDashboardClient", return_value=mock_client), patch(
            "plexus.Evaluation.Evaluation.get_evaluation_info",
            return_value=eval_info,
        ):
            payload = json.loads(
                await tool(
                    score_version_id="ver-1",
                    evaluation_type="feedback",
                    max_age_hours=48,
                    min_items=80,
                    days=180,
                    max_feedback_items=100,
                    sampling_mode="newest",
                    latest_feedback_updated_at="2026-04-22T11:00:00Z",
                )
            )

        assert payload["found"] is False

    @pytest.mark.asyncio
    async def test_feedback_cache_hit_when_exact_match_and_fresh(self):
        tool = _register_find_recent_tool()

        mock_client = Mock()
        mock_client.execute.return_value = {
            "listEvaluationByScoreVersionIdAndCreatedAt": {
                "items": [
                    {
                        "id": "eval-fb-2",
                        "type": "feedback",
                        "status": "COMPLETED",
                        "scoreVersionId": "ver-1",
                        "totalItems": 120,
                        "createdAt": "2026-04-22T12:00:00Z",
                    }
                ]
            }
        }

        eval_info = {
            "id": "eval-fb-2",
            "type": "feedback",
            "status": "COMPLETED",
            "score_version_id": "ver-1",
            "created_at": "2026-04-22T12:00:00Z",
            "parameters": {
                "days": 180,
                "max_feedback_items": 100,
                "sampling_mode": "newest",
            },
            "total_items": 120,
            "processed_items": 120,
            "metrics": [],
            "accuracy": 88.0,
        }

        with patch("plexus.dashboard.api.client.PlexusDashboardClient", return_value=mock_client), patch(
            "plexus.Evaluation.Evaluation.get_evaluation_info",
            return_value=eval_info,
        ):
            payload = json.loads(
                await tool(
                    score_version_id="ver-1",
                    evaluation_type="feedback",
                    max_age_hours=48,
                    min_items=80,
                    days=180,
                    max_feedback_items=100,
                    sampling_mode="newest",
                    latest_feedback_updated_at="2026-04-22T11:00:00Z",
                )
            )

        assert payload.get("_from_cache") is True
        assert payload.get("evaluation_id") == "eval-fb-2"
