"""
Integration tests for MCP tool filtering in procedure execution.

These tests verify that the tool filtering logic in StandardOperatingProcedureAgent
correctly filters MCP tools based on the ProcedureDefinition's allowed tools list.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from .procedure_sop_agent import ProcedureProcedureDefinition
from .mcp_transport import create_procedure_mcp_server
from .mcp_adapter import LangChainMCPAdapter


@pytest.mark.asyncio
async def test_procedure_definition_returns_correct_tools():
    """Test that ProcedureProcedureDefinition returns the correct list of allowed tools."""
    proc_def = ProcedureProcedureDefinition()
    
    # Get the allowed tools
    allowed_tools = proc_def.get_allowed_tools()
    
    # Verify it's a non-empty list
    assert isinstance(allowed_tools, list)
    assert len(allowed_tools) > 0
    
    # Verify the expected evaluation tools are present
    assert "plexus_evaluation_score_result_find" in allowed_tools
    assert "upsert_procedure_node" in allowed_tools
    assert "stop_procedure" in allowed_tools
    
    # Verify it's exactly 3 tools
    assert len(allowed_tools) == 3


@pytest.mark.asyncio
async def test_mcp_server_registers_evaluation_tools():
    """Test that create_procedure_mcp_server actually registers evaluation tools."""
    # Create MCP server with all tools
    mcp_server = await create_procedure_mcp_server(
        experiment_context={},
        plexus_tools=None  # None means all tools
    )
    
    # Connect and get tool list
    async with mcp_server.connect({'name': 'Test Client'}) as mcp_client:
        tools_result = await mcp_client.list_tools()
        # tools_result is already a list of dicts
        tool_names = [t['name'] for t in tools_result]
        
        # Verify evaluation tools are registered
        assert 'plexus_evaluation_score_result_find' in tool_names, \
            f"plexus_evaluation_score_result_find not found in {len(tool_names)} registered tools"
        assert 'plexus_evaluation_info' in tool_names
        assert 'plexus_evaluation_run' in tool_names


@pytest.mark.asyncio
async def test_tool_filtering_matches_allowed_tools():
    """Test that tool filtering correctly filters MCP tools based on allowed list."""
    # Create procedure definition
    proc_def = ProcedureProcedureDefinition()
    allowed_tools = proc_def.get_allowed_tools()
    
    # Create MCP server with all tools
    mcp_server = await create_procedure_mcp_server(
        experiment_context={},
        plexus_tools=None
    )
    
    # Get all available tools
    async with mcp_server.connect({'name': 'Test Client'}) as mcp_client:
        adapter = LangChainMCPAdapter(mcp_client)
        all_tools = await adapter.load_tools()
        
        # Simulate the filtering logic from sop_agent_base.py
        filtered_tools = []
        for tool in all_tools:
            if tool.name in allowed_tools:
                filtered_tools.append(tool)
        
        # Verify the correct tools were filtered
        filtered_names = [t.name for t in filtered_tools]
        
        # Check that evaluation tool made it through
        assert 'plexus_evaluation_score_result_find' in filtered_names, \
            f"Expected plexus_evaluation_score_result_find in filtered tools, got: {filtered_names}"
        
        # Check that other allowed tools made it through
        assert 'upsert_procedure_node' in filtered_names
        # Note: stop_procedure is added separately, not from MCP
        
        # Verify that disallowed tools were filtered out
        all_names = [t.name for t in all_tools]
        assert 'plexus_score_info' in all_names, "Sanity check: score tools should be in all_tools"
        assert 'plexus_score_info' not in filtered_names, "score tools should be filtered out"


@pytest.mark.asyncio
async def test_end_to_end_tool_availability():
    """
    End-to-end test that verifies tools are available through the full stack:
    1. ProcedureDefinition returns correct allowed tools
    2. MCP server has the tools registered
    3. Tool filtering correctly includes the allowed tools
    4. LangChain adapter can convert them
    """
    # Step 1: Verify procedure definition
    proc_def = ProcedureProcedureDefinition()
    allowed_tools = proc_def.get_allowed_tools()
    assert "plexus_evaluation_score_result_find" in allowed_tools, \
        "Step 1 failed: plexus_evaluation_score_result_find not in allowed_tools"
    
    # Step 2: Verify MCP server registration
    mcp_server = await create_procedure_mcp_server(
        experiment_context={},
        plexus_tools=None
    )
    
    async with mcp_server.connect({'name': 'Test'}) as mcp_client:
        # Step 3: Verify tool is in MCP
        tools_result = await mcp_client.list_tools()
        # tools_result is already a list of dicts
        mcp_tool_names = [t['name'] for t in tools_result]
        assert 'plexus_evaluation_score_result_find' in mcp_tool_names, \
            f"Step 2 failed: plexus_evaluation_score_result_find not in MCP tools. Found: {mcp_tool_names[:5]}..."
        
        # Step 4: Verify LangChain adapter can load it
        adapter = LangChainMCPAdapter(mcp_client)
        all_tools = await adapter.load_tools()
        all_tool_names = [t.name for t in all_tools]
        assert 'plexus_evaluation_score_result_find' in all_tool_names, \
            f"Step 3 failed: plexus_evaluation_score_result_find not in adapter tools. Found: {all_tool_names[:5]}..."
        
        # Step 5: Verify filtering works
        filtered_tools = [t for t in all_tools if t.name in allowed_tools]
        filtered_names = [t.name for t in filtered_tools]
        assert 'plexus_evaluation_score_result_find' in filtered_names, \
            f"Step 4 failed: plexus_evaluation_score_result_find filtered out. Filtered: {filtered_names}"
    
    print("✅ End-to-end test passed: plexus_evaluation_score_result_find available through full stack")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

