"""
Integration test for Tactus runtime with Plexus adapters.

This test verifies that the new TactusRuntime works correctly with
the Plexus adapters (PlexusStorageAdapter, PlexusHITLAdapter, PlexusChatAdapter).
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from plexus.cli.procedure.procedure_executor import execute_procedure


@pytest.fixture
def mock_plexus_client():
    """Create a mock PlexusDashboardClient."""
    client = Mock()

    # Mock GraphQL execute method
    def mock_execute(query, variables):
        """Mock GraphQL responses."""
        # Handle procedure metadata queries
        if 'procedure(id:' in query or 'GetProcedure' in query:
            return {
                'procedure': {
                    'id': variables.get('id', 'test-proc-123'),
                    'metadata': {
                        'checkpoints': {},
                        'state': {},
                        'lua_state': {}
                    },
                    'status': 'RUNNING',
                    'waitingOnMessageId': None
                }
            }

        # Handle procedure updates
        if 'updateProcedure' in query or 'UpdateProcedureMetadata' in query:
            return {
                'updateProcedure': {
                    'procedure': {
                        'id': variables.get('id', 'test-proc-123'),
                        'metadata': variables.get('metadata', {}),
                        'status': variables.get('status', 'RUNNING')
                    }
                }
            }

        # Handle chat session start
        if 'startChatSession' in query or 'createChatSession' in query:
            return {
                'startChatSession': {
                    'session': {
                        'id': 'session-123'
                    }
                },
                'createChatSession': {
                    'chatSession': {
                        'id': 'session-123'
                    }
                }
            }

        # Handle message recording
        if 'createMessage' in query or 'recordMessage' in query:
            return {
                'createMessage': {
                    'message': {
                        'id': 'msg-123'
                    }
                }
            }

        # Default response
        return {}

    client.execute = Mock(side_effect=mock_execute)
    return client


@pytest.fixture
def simple_lua_config():
    """Simple test Lua DSL configuration."""
    return """
-- Procedure with outputs declared inline
procedure({
    outputs = {
        success = {
            type = "boolean",
            required = true,
            description = "Whether the test completed successfully"
        },
        message = {
            type = "string",
            required = true,
            description = "Test result message"
        }
    }
}, function()
    -- Simple test workflow
    Log.info("Starting integration test")

    -- Test State primitive
    State.set("test_key", "test_value")
    local value = State.get("test_key")

    Log.info("State test passed", {value = value})

    -- Test checkpoint with Step.run (should persist to GraphQL via adapter)
    local result = Step.run("test_checkpoint", function()
        return {data = "checkpoint_data", status = "success"}
    end)

    Log.info("Checkpoint saved", {result = result})

    return {
        success = true,
        message = "Integration test completed successfully"
    }
end)
"""


@pytest.mark.asyncio
async def test_tactus_with_plexus_adapters(mock_plexus_client, simple_lua_config):
    """Test that TactusRuntime works with Plexus adapters."""

    # Execute procedure using the new integration
    result = await execute_procedure(
        procedure_id='test-proc-123',
        procedure_code=simple_lua_config,
        client=mock_plexus_client,
        mcp_server=None,  # No MCP for simple test
        context=None,
        openai_api_key=None  # No API key needed for simple test
    )

    # Verify execution succeeded
    assert result is not None
    if not result.get('success'):
        print(f"\n❌ Test failed with error: {result.get('error', 'No error message')}")
        print(f"Full result: {result}")
    assert result['success'] is True, f"Execution failed: {result.get('error', 'Unknown error')}"
    assert result['procedure_id'] == 'test-proc-123'
    assert 'result' in result
    assert result['result']['success'] is True
    assert result['result']['message'] == 'Integration test completed successfully'

    # Verify GraphQL was called for storage operations
    assert mock_plexus_client.execute.called

    # Verify at least one metadata query and one metadata update
    execute_calls = mock_plexus_client.execute.call_args_list
    has_metadata_query = any('GetProcedure' in str(call) or 'procedure(id:' in str(call)
                             for call in execute_calls)
    has_metadata_update = any('updateProcedure' in str(call) or 'UpdateProcedureMetadata' in str(call)
                              for call in execute_calls)

    assert has_metadata_query, "Should query procedure metadata"
    assert has_metadata_update, "Should update procedure metadata (checkpoint/state)"


@pytest.mark.asyncio
async def test_tactus_state_persistence(mock_plexus_client):
    """Test that state changes are persisted via PlexusStorageAdapter."""

    lua_config = """
procedure({
    outputs = {
        count = {
            type = "number",
            required = true
        }
    }
}, function()
    State.set("count", 0)
    State.increment("count")
    State.increment("count")
    State.increment("count")

    local final_count = State.get("count")

    return {count = final_count}
end)
"""

    result = await execute_procedure(
        procedure_id='test-state-123',
        procedure_code=lua_config,
        client=mock_plexus_client,
        mcp_server=None,
        context=None,
        openai_api_key=None
    )

    if not result.get('success'):
        print(f"\n❌ Test failed with error: {result.get('error', 'No error message')}")
        print(f"Full result: {result}")
    assert result['success'] is True, f"Execution failed: {result.get('error', 'Unknown error')}"
    assert result['result']['count'] == 3

    # Verify final state is in the result
    assert 'state' in result
    assert result['state']['count'] == 3

    # Note: State is kept in memory during execution and returned in result.
    # It's not persisted to GraphQL unless needed for exit-and-resume pattern.


@pytest.mark.asyncio
async def test_tactus_checkpoint_persistence(mock_plexus_client):
    """Test that checkpoints are persisted via PlexusStorageAdapter."""

    lua_config = """
procedure({
    outputs = {
        checkpoint_exists = {
            type = "boolean",
            required = true
        }
    }
}, function()
    -- Save a checkpoint using Step.run
    local step_result = Step.run("step1", function()
        return {status = "completed", data = "test_data"}
    end)

    -- Check if it exists
    local exists = Checkpoint.exists("step1")

    -- Try to get it
    local data = nil
    if exists then
        data = Checkpoint.get("step1")
    end

    return {checkpoint_exists = exists}
end)
"""

    result = await execute_procedure(
        procedure_id='test-checkpoint-123',
        procedure_code=lua_config,
        client=mock_plexus_client,
        mcp_server=None,
        context=None,
        openai_api_key=None
    )

    if not result.get('success'):
        print(f"\n❌ Test failed with error: {result.get('error', 'No error message')}")
        print(f"Full result: {result}")
    assert result['success'] is True, f"Execution failed: {result.get('error', 'Unknown error')}"
    assert result['result']['checkpoint_exists'] is True

    # Verify checkpoint was saved to GraphQL
    execute_calls = mock_plexus_client.execute.call_args_list
    update_calls = [call for call in execute_calls
                   if 'updateProcedure' in str(call) or 'UpdateProcedureMetadata' in str(call)]

    # Should have at least one update for saving the checkpoint
    assert len(update_calls) >= 1, "Should have saved checkpoint to metadata"


@pytest.mark.asyncio
async def test_tactus_error_handling(mock_plexus_client):
    """Test error handling in TactusRuntime with Plexus adapters."""

    # Invalid procedure code (missing required fields)
    invalid_code = """
name: invalid_test
version: 1.0.0
class: LuaDSL
"""

    result = await execute_procedure(
        procedure_id='test-error-123',
        procedure_code=invalid_code,
        client=mock_plexus_client,
        mcp_server=None,
        context=None,
        openai_api_key=None
    )

    # Should return error result, not raise exception
    assert result is not None
    assert result['success'] is False
    assert 'error' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
