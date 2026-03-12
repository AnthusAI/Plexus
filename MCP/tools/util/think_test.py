#!/usr/bin/env python3
"""
Unit tests for the think tool
"""
import pytest
from unittest.mock import Mock


pytestmark = pytest.mark.unit


def test_think_tool_registration():
    from tools.util.think import register_think_tool

    mock_mcp = Mock()
    registered_tools = {}

    def mock_tool_decorator():
        def decorator(func):
            registered_tools[func.__name__] = func
            return func
        return decorator

    mock_mcp.tool = mock_tool_decorator

    register_think_tool(mock_mcp)

    assert 'think' in registered_tools
    assert callable(registered_tools['think'])


@pytest.mark.asyncio
async def test_think_tool_executes():
    from tools.util.think import register_think_tool

    mock_mcp = Mock()
    registered_tools = {}

    def mock_tool_decorator():
        def decorator(func):
            registered_tools[func.__name__] = func
            return func
        return decorator

    mock_mcp.tool = mock_tool_decorator

    register_think_tool(mock_mcp)
    think_tool = registered_tools['think']

    result = await think_tool("Test thought")
    assert isinstance(result, str)
    assert "Thought processed" in result


