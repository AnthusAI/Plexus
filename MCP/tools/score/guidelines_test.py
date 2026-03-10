#!/usr/bin/env python3
"""
Unit tests for plexus_guidelines_validate tool.
"""
import pytest
import asyncio
from unittest.mock import Mock

pytestmark = pytest.mark.unit


class TestGuidelinesToolRegistration:
    """Test guidelines tool registration patterns."""

    def test_guidelines_tool_registration(self):
        """Given the MCP server when registering guidelines tools then plexus_guidelines_validate should be available."""
        from tools.score.guidelines import register_guidelines_tools

        mock_mcp = Mock()
        registered_tools = {}

        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator

        mock_mcp.tool = mock_tool_decorator

        register_guidelines_tools(mock_mcp)

        assert 'plexus_guidelines_validate' in registered_tools
        assert callable(registered_tools['plexus_guidelines_validate'])


class TestGuidelinesValidation:
    """Test guidelines validation behavior."""

    def _get_valid_binary_guidelines(self) -> str:
        return """# Guidelines for Test Classifier

## Objective
Determine whether the transcript contains a clear compliance confirmation.

## Classes
Valid labels: [Yes, No]
Target class: Yes
Default class: No

## Definition of Yes
The agent explicitly confirms compliance with the requirement.

## Conditions for Yes
- The agent states the compliance confirmation clearly.

## Definition of No
The agent does not confirm compliance, or the confirmation is missing.

## Conditions for No
- No explicit confirmation appears in the transcript.
"""

    def _get_invalid_binary_guidelines(self) -> str:
        return """# Guidelines for Test Classifier

## Objective
Determine whether the transcript contains a clear compliance confirmation.

## Classes
Valid labels: [Yes, No]
Target class: Yes
Default class: No

## Conditions for Yes
- The agent states the compliance confirmation clearly.

## Definition of No
The agent does not confirm compliance, or the confirmation is missing.
"""

    def test_guidelines_validate_success(self):
        """Valid binary guidelines should validate successfully."""
        from tools.score.guidelines import register_guidelines_tools

        mock_mcp = Mock()
        registered_tools = {}

        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator

        mock_mcp.tool = mock_tool_decorator
        register_guidelines_tools(mock_mcp)

        plexus_guidelines_validate = registered_tools['plexus_guidelines_validate']

        result = asyncio.get_event_loop().run_until_complete(
            plexus_guidelines_validate(guidelines_markdown=self._get_valid_binary_guidelines())
        )

        assert result["success"] is True
        assert result["is_valid"] is True
        assert result["classifier_type"] == "binary"

    def test_guidelines_validate_missing_section(self):
        """Missing required sections should fail validation."""
        from tools.score.guidelines import register_guidelines_tools

        mock_mcp = Mock()
        registered_tools = {}

        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator

        mock_mcp.tool = mock_tool_decorator
        register_guidelines_tools(mock_mcp)

        plexus_guidelines_validate = registered_tools['plexus_guidelines_validate']

        result = asyncio.get_event_loop().run_until_complete(
            plexus_guidelines_validate(guidelines_markdown=self._get_invalid_binary_guidelines())
        )

        assert result["success"] is True
        assert result["is_valid"] is False
        assert "Definition of Yes" in result["missing_sections"]
