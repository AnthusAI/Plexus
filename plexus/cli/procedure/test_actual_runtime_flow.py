"""
Test that reproduces the EXACT runtime flow to verify tools are available.
This test simulates what actually happens when service.py runs a procedure.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from .mcp_transport import create_procedure_mcp_server
from .mcp_adapter import LangChainMCPAdapter
from .procedure_sop_agent import ProcedureProcedureDefinition


@pytest.mark.asyncio
async def test_actual_service_flow_tool_availability():
    """
    Reproduce the exact flow from service.py to verify tools are available.
    
    This is what actually happens:
    1. service.py calls create_procedure_mcp_server(experiment_context={}, plexus_tools=None)
    2. Server registers all tools
    3. sop_agent_base.py connects to server and loads tools
    4. Tools are filtered to allowed list
    5. Agent should have plexus_evaluation_score_result_find available
    """
    print("\n=== Simulating actual runtime flow ===")
    
    # Step 1: Create MCP server exactly as service.py does
    print("Step 1: Creating MCP server with plexus_tools=None (all tools)...")
    experiment_context = {}
    mcp_server = await create_procedure_mcp_server(
        experiment_context=experiment_context,
        plexus_tools=None  # This is what service.py passes
    )
    print(f"✓ MCP server created")
    
    # Step 2: Connect and check what tools are registered
    print("\nStep 2: Connecting to MCP server and listing tools...")
    async with mcp_server.connect({'name': 'Test Client'}) as mcp_client:
        tools_result = await mcp_client.list_tools()
        all_tool_names = [t['name'] for t in tools_result]
        print(f"✓ MCP server has {len(all_tool_names)} tools registered")
        
        # Verify evaluation tools are present
        assert 'plexus_evaluation_score_result_find' in all_tool_names, \
            f"FAIL: plexus_evaluation_score_result_find not in {len(all_tool_names)} MCP tools"
        assert 'plexus_evaluation_info' in all_tool_names
        assert 'upsert_procedure_node' in all_tool_names
        print(f"✓ Evaluation tools present in MCP")
        
        # Step 3: Load tools through LangChain adapter (as sop_agent_base.py does)
        print("\nStep 3: Loading tools through LangChain adapter...")
        adapter = LangChainMCPAdapter(mcp_client)
        all_tools = await adapter.load_tools()
        print(f"✓ Loaded {len(all_tools)} tools through adapter")
        
        # Step 4: Get allowed tools from procedure definition
        print("\nStep 4: Getting allowed tools from ProcedureProcedureDefinition...")
        proc_def = ProcedureProcedureDefinition()
        allowed_tools = proc_def.get_allowed_tools()
        print(f"✓ Allowed tools ({len(allowed_tools)}): {allowed_tools}")
        
        # Step 5: Filter tools (as sop_agent_base.py does)
        print("\nStep 5: Filtering tools to allowed list...")
        filtered_tools = []
        for tool in all_tools:
            if tool.name in allowed_tools:
                filtered_tools.append(tool)
                print(f"  ✓ Including: {tool.name}")
        
        print(f"\n✓ After filtering: {len(filtered_tools)} tools")
        
        # Step 6: Verify plexus_evaluation_score_result_find made it through
        filtered_names = [t.name for t in filtered_tools]
        assert 'plexus_evaluation_score_result_find' in filtered_names, \
            f"FAIL: plexus_evaluation_score_result_find was filtered out! " \
            f"Filtered tools: {filtered_names}"
        assert 'upsert_procedure_node' in filtered_names
        
        print(f"\n✅ SUCCESS: plexus_evaluation_score_result_find is available to agent")
        print(f"Final tool list: {filtered_names}")
        
        return True


@pytest.mark.asyncio  
async def test_langchain_tool_binding():
    """
    Test that tools can be bound to LangChain LLM.
    This is the final step before the agent uses them.
    """
    print("\n=== Testing LangChain tool binding ===")
    
    # Create server and get tools
    mcp_server = await create_procedure_mcp_server(
        experiment_context={},
        plexus_tools=None
    )
    
    async with mcp_server.connect({'name': 'Test'}) as mcp_client:
        adapter = LangChainMCPAdapter(mcp_client)
        all_tools = await adapter.load_tools()
        
        # Filter to allowed tools
        proc_def = ProcedureProcedureDefinition()
        allowed_tools = proc_def.get_allowed_tools()
        filtered_tools = [t for t in all_tools if t.name in allowed_tools]
        
        # Convert to LangChain format
        from .mcp_adapter import convert_mcp_tools_to_langchain
        langchain_tools = convert_mcp_tools_to_langchain(filtered_tools)
        
        print(f"✓ Converted {len(langchain_tools)} tools to LangChain format")
        
        # Add stop_procedure tool (as sop_agent_base.py does)
        from langchain_core.tools import tool
        
        @tool
        def stop_procedure(reason: str, success: bool = True) -> str:
            """Signal completion."""
            return f"Stop: {reason}"
        
        langchain_tools.append(stop_procedure)
        print(f"✓ Added stop_procedure, total: {len(langchain_tools)} tools")
        
        # Verify we have all 3 expected tools
        tool_names = [t.name for t in langchain_tools]
        assert 'plexus_evaluation_score_result_find' in tool_names
        assert 'upsert_procedure_node' in tool_names  
        assert 'stop_procedure' in tool_names
        
        print(f"✅ All 3 tools ready for LangChain: {tool_names}")
        
        # Try binding to a mock LLM
        from unittest.mock import Mock
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        llm_with_tools = mock_llm.bind_tools(langchain_tools)
        mock_llm.bind_tools.assert_called_once()
        
        print(f"✅ Successfully bound tools to LLM")
        
        return True


if __name__ == "__main__":
    # Run tests and show output
    pytest.main([__file__, "-v", "-s"])

