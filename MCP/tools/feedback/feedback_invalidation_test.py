#!/usr/bin/env python3
"""Unit tests for the feedback invalidation MCP tool."""

import asyncio
import json
from unittest.mock import Mock, patch

import pytest

from plexus.cli.feedback.feedback_invalidation import FeedbackInvalidationError

pytestmark = pytest.mark.unit


def _register_tools():
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
    return registered_tools


def test_feedback_invalidate_tool_registration():
    registered_tools = _register_tools()
    assert "plexus_feedback_invalidate" in registered_tools
    assert "plexus_feedback_uninvalidate" in registered_tools
    assert callable(registered_tools["plexus_feedback_invalidate"])
    assert callable(registered_tools["plexus_feedback_uninvalidate"])


def test_feedback_invalidate_tool_success():
    registered_tools = _register_tools()
    tool = registered_tools["plexus_feedback_invalidate"]
    result_payload = {
        "status": "invalidated",
        "updated": True,
        "already_invalid": False,
        "resolution": {
            "requested_identifier": "feedback-1",
            "method": "feedback_item_id",
            "resolved_item_id": "item-1",
            "scorecard_filter": None,
            "score_filter": None,
        },
        "feedback_item": {"id": "feedback-1", "is_invalid": True},
    }

    with patch("plexus.cli.shared.client_utils.create_client", return_value=Mock()), patch(
        "plexus.cli.feedback.feedback_invalidation.invalidate_feedback_item",
        return_value=result_payload,
    ):
        raw = asyncio.run(tool(identifier="feedback-1"))

    parsed = json.loads(raw)
    assert parsed["status"] == "invalidated"
    assert parsed["feedback_item"]["id"] == "feedback-1"


def test_feedback_invalidate_tool_returns_structured_error():
    registered_tools = _register_tools()
    tool = registered_tools["plexus_feedback_invalidate"]

    with patch("plexus.cli.shared.client_utils.create_client", return_value=Mock()), patch(
        "plexus.cli.feedback.feedback_invalidation.invalidate_feedback_item",
        side_effect=FeedbackInvalidationError(
            "Identifier is ambiguous",
            code="ambiguous_feedback_items",
            details={"candidates": [{"feedback_item_id": "feedback-1"}]},
        ),
    ):
        raw = asyncio.run(tool(identifier="CUSTOMER-42"))

    parsed = json.loads(raw)
    assert parsed["code"] == "ambiguous_feedback_items"
    assert parsed["details"]["candidates"][0]["feedback_item_id"] == "feedback-1"


def test_feedback_uninvalidate_tool_success():
    registered_tools = _register_tools()
    tool = registered_tools["plexus_feedback_uninvalidate"]
    result_payload = {
        "status": "reinstated",
        "updated": True,
        "already_invalid": True,
        "resolution": {
            "requested_identifier": "feedback-1",
            "method": "feedback_item_id",
            "resolved_item_id": "item-1",
            "scorecard_filter": None,
            "score_filter": None,
        },
        "feedback_item": {"id": "feedback-1", "is_invalid": False},
    }

    with patch("plexus.cli.shared.client_utils.create_client", return_value=Mock()), patch(
        "plexus.cli.feedback.feedback_invalidation.reinstate_feedback_item",
        return_value=result_payload,
    ):
        raw = asyncio.run(tool(identifier="feedback-1"))

    parsed = json.loads(raw)
    assert parsed["status"] == "reinstated"
    assert parsed["feedback_item"]["id"] == "feedback-1"
