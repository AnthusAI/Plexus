#!/usr/bin/env python3
"""Unit tests for feedback watermark MCP tool."""

import json
from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.unit


def _register_tool(name: str):
    from tools.feedback.feedback import register_feedback_tools

    mock_mcp = Mock()
    registered_tools = {}

    def mock_tool_decorator():
        def decorator(func):
            registered_tools[func.__name__] = func
            return func

        return decorator

    mock_mcp.tool = mock_tool_decorator
    register_feedback_tools(mock_mcp)
    return registered_tools[name]


class TestFeedbackLatestUpdateTool:
    @pytest.mark.asyncio
    async def test_returns_latest_updated_at_from_window(self):
        tool = _register_tool("plexus_feedback_latest_update")

        mock_client = Mock()
        mock_client.execute.return_value = {
            "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
                "items": [
                    {
                        "id": "fi-old",
                        "editedAt": "2026-04-10T00:00:00Z",
                        "updatedAt": "2026-04-10T00:01:00Z",
                        "isInvalid": False,
                    },
                    {
                        "id": "fi-new-invalidated",
                        "editedAt": "2026-04-08T00:00:00Z",
                        "updatedAt": "2026-04-22T20:00:00Z",
                        "isInvalid": True,
                    },
                ],
                "nextToken": None,
            }
        }

        with patch("plexus.cli.shared.client_utils.create_client", return_value=mock_client), patch(
            "plexus.cli.report.utils.resolve_account_id_for_command",
            return_value="acct-1",
        ), patch(
            "plexus.cli.shared.memoized_resolvers.memoized_resolve_scorecard_identifier",
            return_value="sc-1",
        ), patch(
            "plexus.cli.shared.memoized_resolvers.memoized_resolve_score_identifier",
            return_value="score-1",
        ):
            payload = json.loads(
                await tool(
                    scorecard_name="SelectQuote HCS Medium-Risk",
                    score_name="Medication Review: Prescriber",
                    days=180,
                )
            )

        assert payload["found"] is True
        assert payload["latest_feedback_item_id"] == "fi-new-invalidated"
        assert payload["latest_feedback_updated_at"] == "2026-04-22T20:00:00Z"
        assert payload["days"] == 180

    @pytest.mark.asyncio
    async def test_returns_not_found_when_window_empty(self):
        tool = _register_tool("plexus_feedback_latest_update")

        mock_client = Mock()
        mock_client.execute.return_value = {
            "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
                "items": [],
                "nextToken": None,
            }
        }

        with patch("plexus.cli.shared.client_utils.create_client", return_value=mock_client), patch(
            "plexus.cli.report.utils.resolve_account_id_for_command",
            return_value="acct-1",
        ), patch(
            "plexus.cli.shared.memoized_resolvers.memoized_resolve_scorecard_identifier",
            return_value="sc-1",
        ), patch(
            "plexus.cli.shared.memoized_resolvers.memoized_resolve_score_identifier",
            return_value="score-1",
        ):
            payload = json.loads(
                await tool(
                    scorecard_name="SelectQuote HCS Medium-Risk",
                    score_name="Medication Review: Prescriber",
                    days=180,
                )
            )

        assert payload["found"] is False
        assert payload["latest_feedback_updated_at"] is None
        assert payload["latest_feedback_item_id"] is None
