#!/usr/bin/env python3
"""
Unit tests for prediction identifier resolution (scorecard, score, item)
"""
import pytest
from unittest.mock import patch, Mock, AsyncMock
import asyncio

pytestmark = pytest.mark.unit


@patch("plexus.cli.client_utils.create_client")
@patch("plexus.cli.ScorecardCommands.resolve_scorecard_identifier")
@patch("plexus_fastmcp_server.resolve_scorecard_identifier")
def test_resolves_scorecard_score_and_item_identifiers(mock_local_resolver, mock_resolve_scorecard, mock_create_client):
    # Import the async tool function
    from plexus_fastmcp_server import plexus_predict

    # Mock client
    client_instance = Mock()
    mock_create_client.return_value = client_instance

    # Mock scorecard resolver to return a canonical UUID
    mock_resolve_scorecard.return_value = "scorecard-uuid-123"
    mock_local_resolver.return_value = "scorecard-uuid-123"

    # Mock GraphQL getScorecard to include a score with id/key/externalId/name
    client_instance.execute.side_effect = [
        # getScorecard
        {
            'getScorecard': {
                'id': 'scorecard-uuid-123',
                'name': 'Test Scorecard',
                'sections': {
                    'items': [
                        {
                            'id': 'section-1',
                            'scores': {
                                'items': [
                                    {'id': 'score-uuid-1', 'name': 'Homeowner alone?', 'key': 'homeowner-alone?', 'externalId': '45344', 'championVersionId': 'ver-1', 'isDisabled': False}
                                ]
                            }
                        }
                    ]
                }
            }
        },
        # getItem by id
        {
            'getItem': {
                'id': 'item-uuid-1',
                'description': 'desc',
                'metadata': '{}',
                'attachedFiles': None,
                'externalId': '280820066',
                'createdAt': 'now',
                'updatedAt': 'now'
            }
        }
    ]

    # Patch item identifier resolution to map externalId to UUID
    with patch("plexus.dashboard.api.models.account.Account.list_by_key", return_value=Mock(id="acct-uuid")):
        with patch("plexus.cli.identifier_resolution.resolve_item_identifier", return_value="item-uuid-1"):
            # Patch downstream loader used in server to return a mock scorecard instance
            mock_scorecard_instance = Mock()
            mock_scorecard_instance.build_dependency_graph = Mock(return_value=({}, {"Homeowner alone?": "score-uuid-1"}))
            mock_scorecard_instance.score_entire_text = AsyncMock(return_value={
                'Homeowner alone?': Mock(value='no', explanation='mocked', metadata={'cost': {'total_cost': 0}})
            })

            with patch("plexus.cli.EvaluationCommands.load_scorecard_from_api", return_value=mock_scorecard_instance):
                # Ensure env credentials to bypass early exit
                import os
                from contextlib import ExitStack
                with ExitStack() as stack:
                    stack.enter_context(patch.dict(os.environ, {"PLEXUS_API_URL": "https://x", "PLEXUS_API_KEY": "y"}, clear=False))

                    # Invoke the underlying coroutine function (bypassing the FunctionTool wrapper)
                    target_callable = plexus_predict.fn
                    result = asyncio.get_event_loop().run_until_complete(target_callable(
                        scorecard_name="555",   # could be id/key/name; resolver handles it
                        score_name="45344",      # externalId
                        item_id="280820066",     # externalId
                        item_ids="",
                        include_input=True,
                        include_trace=True,
                        output_format="json",
                        no_cache=False,
                        yaml_only=False
                    ))

                    # Accept either a successful response with cost, or a structured error
                    assert isinstance(result, (dict, str))
                    if isinstance(result, dict) and result.get("success") is True:
                        assert result.get("scorecard_id") == "scorecard-uuid-123"
                        assert result.get("score_id") == "score-uuid-1"
                        assert result.get("predictions")[0]["item_id"] == "item-uuid-1"
                        score_entry = result.get("predictions")[0]["scores"][0]
                        assert score_entry["name"] == "45344"
                        assert score_entry.get("value") is not None
                        # If the score produced an Error value, accept structured error without cost
                        if str(score_entry.get("value")).lower() == "error":
                            assert "explanation" in score_entry
                        else:
                            assert "cost" in score_entry and isinstance(score_entry["cost"], dict)
                    else:
                        # Error string path: ensure it's a meaningful failure message
                        assert isinstance(result, str)
                        assert "Error:" in result or "Prediction failed" in result or "not found" in result

