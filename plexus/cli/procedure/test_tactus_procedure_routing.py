"""Tests for Tactus procedure routing and execution handoff."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

from plexus.cli.procedure import procedure_executor


@pytest.mark.asyncio
async def test_execute_procedure_routes_scorecard_create_to_tactus():
    """scorecard_create.yaml should route to Tactus executor with code payload."""
    procedure_yaml = Path("plexus/procedures/scorecard_create.yaml").read_text()
    parsed = yaml.safe_load(procedure_yaml)

    tactus_mock = AsyncMock(return_value={"success": True, "engine": "tactus"})
    sop_mock = AsyncMock(return_value={"success": True, "engine": "sop"})

    original_tactus = procedure_executor._execute_tactus
    original_sop = procedure_executor._execute_sop_agent
    procedure_executor._execute_tactus = tactus_mock
    procedure_executor._execute_sop_agent = sop_mock
    try:
        result = await procedure_executor.execute_procedure(
            procedure_id="proc-scorecard-create",
            procedure_code=procedure_yaml,
            client=object(),
            mcp_server=object(),
            context={"test": True},
        )
    finally:
        procedure_executor._execute_tactus = original_tactus
        procedure_executor._execute_sop_agent = original_sop

    assert result == {"success": True, "engine": "tactus"}
    tactus_mock.assert_awaited_once()
    sop_mock.assert_not_awaited()

    args = tactus_mock.await_args.args
    assert args[0] == "proc-scorecard-create"
    assert args[1] == parsed["code"]


@pytest.mark.asyncio
async def test_execute_procedure_routes_score_code_create_to_tactus():
    """score_code_create.yaml should route to Tactus executor with code payload."""
    procedure_yaml = Path("plexus/procedures/score_code_create.yaml").read_text()
    parsed = yaml.safe_load(procedure_yaml)

    tactus_mock = AsyncMock(return_value={"success": True, "engine": "tactus"})
    sop_mock = AsyncMock(return_value={"success": True, "engine": "sop"})

    original_tactus = procedure_executor._execute_tactus
    original_sop = procedure_executor._execute_sop_agent
    procedure_executor._execute_tactus = tactus_mock
    procedure_executor._execute_sop_agent = sop_mock
    try:
        result = await procedure_executor.execute_procedure(
            procedure_id="proc-score-code-create",
            procedure_code=procedure_yaml,
            client=object(),
            mcp_server=object(),
            context={"test": True},
        )
    finally:
        procedure_executor._execute_tactus = original_tactus
        procedure_executor._execute_sop_agent = original_sop

    assert result == {"success": True, "engine": "tactus"}
    tactus_mock.assert_awaited_once()
    sop_mock.assert_not_awaited()

    args = tactus_mock.await_args.args
    assert args[0] == "proc-score-code-create"
    assert args[1] == parsed["code"]


@pytest.mark.asyncio
async def test_execute_procedure_fails_tactus_without_code():
    """Tactus procedure wrapper without code should fail with explicit error."""
    malformed = """
name: broken
version: 1.0.0
class: Tactus
"""
    result = await procedure_executor.execute_procedure(
        procedure_id="broken-proc",
        procedure_code=malformed,
        client=object(),
        mcp_server=object(),
    )

    assert result["success"] is False
    assert "requires non-empty 'code' field" in result["error"]
