"""
Tests for the in-process MCP transport system.

Tests the EmbeddedMCPServer, InProcessMCPTransport, and ExperimentMCPClient
to ensure they properly implement MCP protocol patterns without requiring
a separate server process.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch
from plexus.cli.experiment.mcp_transport import (
    InProcessMCPTransport,
    EmbeddedMCPServer,
    ExperimentMCPClient,
    MCPToolInfo,
    MCPResourceInfo,
    create_experiment_mcp_server
)


class TestInProcessMCPTransport:
    """Test the core in-process MCP transport functionality."""
    
    @pytest.fixture
    def transport(self):
        return InProcessMCPTransport()
    
    @pytest.fixture
    def sample_tool(self):
        def handler(args):
            return {"result": f"Hello {args.get('name', 'World')}"}
        
        return MCPToolInfo(
            name="greet",
            description="Greet someone",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                }
            },
            handler=handler
        )
    
    @pytest.fixture
    def sample_resource(self):
        def handler(uri):
            return f"Content for {uri}"
        
        return MCPResourceInfo(
            uri="test://resource",
            name="Test Resource",
            description="A test resource",
            mime_type="text/plain",
            handler=handler
        )
    
    def test_transport_initialization(self, transport):
        """Test basic transport initialization."""
        assert not transport.connected
        assert transport.client_info is None
        assert transport.server_info["name"] == "Plexus Experiment MCP Server"
        assert len(transport.tools) == 0
        assert len(transport.resources) == 0
    
    def test_tool_registration(self, transport, sample_tool):
        """Test tool registration."""
        transport.register_tool(sample_tool)
        
        assert "greet" in transport.tools
        assert transport.tools["greet"] == sample_tool
    
    def test_resource_registration(self, transport, sample_resource):
        """Test resource registration."""
        transport.register_resource(sample_resource)
        
        assert "test://resource" in transport.resources
        assert transport.resources["test://resource"] == sample_resource
    
    @pytest.mark.asyncio
    async def test_initialize_connection(self, transport):
        """Test MCP connection initialization."""
        client_info = {"name": "Test Client", "version": "1.0.0"}
        
        result = await transport.initialize(client_info)
        
        assert transport.connected
        assert transport.client_info == client_info
        assert result["protocolVersion"] == "2024-11-05"
        assert "capabilities" in result
        assert "serverInfo" in result
    
    @pytest.mark.asyncio
    async def test_list_tools(self, transport, sample_tool):
        """Test listing available tools."""
        transport.register_tool(sample_tool)
        
        tools = await transport.list_tools()
        
        assert len(tools) == 1
        assert tools[0]["name"] == "greet"
        assert tools[0]["description"] == "Greet someone"
        assert "inputSchema" in tools[0]
    
    @pytest.mark.asyncio
    async def test_call_tool_success(self, transport, sample_tool):
        """Test successful tool execution."""
        transport.register_tool(sample_tool)
        await transport.initialize({"name": "Test"})
        
        result = await transport.call_tool("greet", {"name": "Alice"})
        
        assert "content" in result
        # The result should be wrapped in MCP content format
        content = result["content"][0]
        assert content["type"] == "text"
        assert "Alice" in content["text"]
    
    @pytest.mark.asyncio
    async def test_call_tool_not_found(self, transport):
        """Test calling non-existent tool."""
        await transport.initialize({"name": "Test"})
        
        with pytest.raises(ValueError, match="Tool 'unknown' not found"):
            await transport.call_tool("unknown", {})
    
    @pytest.mark.asyncio
    async def test_call_tool_not_initialized(self, transport, sample_tool):
        """Test calling tool without initialization."""
        transport.register_tool(sample_tool)
        
        with pytest.raises(RuntimeError, match="MCP transport not initialized"):
            await transport.call_tool("greet", {})
    
    @pytest.mark.asyncio
    async def test_call_tool_error_handling(self, transport):
        """Test error handling in tool execution."""
        def error_handler(args):
            raise ValueError("Test error")
        
        error_tool = MCPToolInfo(
            name="error_tool",
            description="Tool that raises an error",
            input_schema={"type": "object"},
            handler=error_handler
        )
        
        transport.register_tool(error_tool)
        await transport.initialize({"name": "Test"})
        
        result = await transport.call_tool("error_tool", {})
        
        assert "isError" in result
        assert result["isError"] is True
        assert "Error: Test error" in result["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_list_resources(self, transport, sample_resource):
        """Test listing available resources."""
        transport.register_resource(sample_resource)
        
        resources = await transport.list_resources()
        
        assert len(resources) == 1
        assert resources[0]["uri"] == "test://resource"
        assert resources[0]["name"] == "Test Resource"
        assert resources[0]["mimeType"] == "text/plain"
    
    @pytest.mark.asyncio
    async def test_read_resource_success(self, transport, sample_resource):
        """Test successful resource reading."""
        transport.register_resource(sample_resource)
        await transport.initialize({"name": "Test"})
        
        result = await transport.read_resource("test://resource")
        
        assert "contents" in result
        content = result["contents"][0]
        assert content["uri"] == "test://resource"
        assert content["mimeType"] == "text/plain"
        assert "Content for test://resource" in content["text"]
    
    @pytest.mark.asyncio
    async def test_read_resource_not_found(self, transport):
        """Test reading non-existent resource."""
        await transport.initialize({"name": "Test"})
        
        with pytest.raises(ValueError, match="Resource 'unknown://resource' not found"):
            await transport.read_resource("unknown://resource")


class TestEmbeddedMCPServer:
    """Test the embedded MCP server functionality."""
    
    @pytest.fixture
    def experiment_context(self):
        return {
            "experiment_id": "exp-123",
            "scorecard_name": "Test Scorecard",
            "score_name": "Test Score"
        }
    
    @pytest.fixture
    def server(self, experiment_context):
        return EmbeddedMCPServer(experiment_context)
    
    def test_server_initialization(self, server, experiment_context):
        """Test server initialization with context."""
        assert server.experiment_context == experiment_context
        assert not server.transport.connected
        # Should have core tools registered
        assert "get_experiment_context" in server.transport.tools
        assert "log_message" in server.transport.tools
    
    @pytest.mark.asyncio
    async def test_core_tool_get_context(self, server):
        """Test the get_experiment_context core tool."""
        await server.transport.initialize({"name": "Test"})
        
        result = await server.transport.call_tool("get_experiment_context", {})
        
        content_text = result["content"][0]["text"]
        context_data = json.loads(content_text)
        assert "experiment_context" in context_data
        assert context_data["experiment_context"]["experiment_id"] == "exp-123"
        assert "available_tools" in context_data
        assert "get_experiment_context" in context_data["available_tools"]
    
    @pytest.mark.asyncio
    async def test_core_tool_log_message(self, server):
        """Test the log_message core tool."""
        await server.transport.initialize({"name": "Test"})
        
        with patch('plexus.cli.experiment.mcp_transport.logger') as mock_logger:
            result = await server.transport.call_tool("log_message", {
                "message": "Test message",
                "level": "info"
            })
            
            # Check that the specific log message we expect was called
            mock_logger.info.assert_any_call("[Experiment MCP] Test message")
            
            content_text = result["content"][0]["text"]
            response_data = json.loads(content_text)
            assert "Logged message at info level" in response_data["message"]
    
    @pytest.mark.asyncio
    async def test_connection_context_manager(self, server):
        """Test the connection context manager."""
        client_info = {"name": "Test Client"}
        
        async with server.connect(client_info) as client:
            assert isinstance(client, ExperimentMCPClient)
            assert server.transport.connected
            
            # Test that we can use the client
            tools = await client.list_tools()
            assert len(tools) >= 2  # At least the core tools
        
        # Connection should be closed after context exit
        assert not server.transport.connected
    
    @pytest.mark.asyncio
    async def test_connection_default_client_info(self, server):
        """Test connection with default client info."""
        async with server.connect() as client:
            assert server.transport.client_info["name"] == "Experiment Client"
            assert server.transport.client_info["version"] == "1.0.0"


class TestExperimentMCPClient:
    """Test the experiment MCP client interface."""
    
    @pytest.fixture
    def transport(self):
        transport = InProcessMCPTransport()
        
        # Add a sample tool
        def greet_handler(args):
            return {"greeting": f"Hello {args.get('name', 'World')}"}
        
        tool = MCPToolInfo(
            name="greet",
            description="Greet someone",
            input_schema={"type": "object"},
            handler=greet_handler
        )
        transport.register_tool(tool)
        
        return transport
    
    @pytest.fixture
    def client(self, transport):
        return ExperimentMCPClient(transport)
    
    @pytest.fixture
    async def initialized_client(self, transport):
        await transport.initialize({"name": "Test Client"})
        return ExperimentMCPClient(transport)
    
    @pytest.mark.asyncio
    async def test_client_list_tools(self, transport):
        """Test client tool listing."""
        await transport.initialize({"name": "Test Client"})
        client = ExperimentMCPClient(transport)
        
        tools = await client.list_tools()
        
        assert len(tools) == 1
        assert tools[0]["name"] == "greet"
    
    @pytest.mark.asyncio
    async def test_client_call_tool(self, transport):
        """Test client tool calling."""
        await transport.initialize({"name": "Test Client"})
        client = ExperimentMCPClient(transport)
        
        result = await client.call_tool("greet", {"name": "Bob"})
        
        assert "content" in result
        content_text = result["content"][0]["text"]
        response_data = json.loads(content_text)
        assert response_data["greeting"] == "Hello Bob"
    
    @pytest.mark.asyncio
    async def test_client_list_resources(self, transport):
        """Test client resource listing."""
        await transport.initialize({"name": "Test Client"})
        client = ExperimentMCPClient(transport)
        
        resources = await client.list_resources()
        
        # Should return empty list initially
        assert isinstance(resources, list)
        assert len(resources) == 0


class TestConvenienceFunctions:
    """Test convenience functions for experiment integration."""
    
    @pytest.mark.asyncio
    async def test_create_experiment_mcp_server_basic(self):
        """Test basic server creation."""
        context = {"experiment_id": "exp-456"}
        
        server = await create_experiment_mcp_server(context)
        
        assert isinstance(server, EmbeddedMCPServer)
        assert server.experiment_context == context
        # Should have core tools
        assert len(server.transport.tools) >= 2
    
    @pytest.mark.asyncio
    async def test_create_experiment_mcp_server_with_tools(self):
        """Test server creation with Plexus tool registration."""
        # Mock the tool registration to avoid import issues in tests
        with patch.object(EmbeddedMCPServer, 'register_plexus_tools') as mock_register:
            server = await create_experiment_mcp_server(
                experiment_context={"test": "context"},
                plexus_tools=["scorecard", "score"]
            )
            
            mock_register.assert_called_once_with(["scorecard", "score"])


class TestIntegrationScenarios:
    """Integration tests for common experiment MCP usage patterns."""
    
    @pytest.mark.asyncio
    async def test_full_experiment_mcp_workflow(self):
        """Test a complete experiment MCP workflow."""
        # Create server with experiment context
        context = {
            "experiment_id": "exp-integration-test",
            "scorecard_name": "Integration Scorecard",
            "score_name": "Integration Score"
        }
        
        server = await create_experiment_mcp_server(context)
        
        # Connect and interact with the server
        async with server.connect({"name": "Integration Test Client"}) as client:
            # List available tools
            tools = await client.list_tools()
            tool_names = [tool["name"] for tool in tools]
            assert "get_experiment_context" in tool_names
            assert "log_message" in tool_names
            
            # Call get_experiment_context tool
            context_result = await client.call_tool("get_experiment_context", {})
            context_text = context_result["content"][0]["text"]
            context_data = json.loads(context_text)
            
            assert context_data["experiment_context"]["experiment_id"] == "exp-integration-test"
            assert context_data["experiment_context"]["scorecard_name"] == "Integration Scorecard"
            
            # Call log_message tool
            log_result = await client.call_tool("log_message", {
                "message": "Integration test message",
                "level": "debug"
            })
            
            assert "content" in log_result
            log_text = log_result["content"][0]["text"]
            log_data = json.loads(log_text)
            assert "debug level" in log_data["message"]
    
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling in a typical workflow."""
        server = await create_experiment_mcp_server()
        
        async with server.connect() as client:
            # Try to call non-existent tool
            with pytest.raises(ValueError):
                await client.call_tool("nonexistent_tool", {})
            
            # Call tool with invalid arguments (should not raise, but return error in content)
            result = await client.call_tool("get_experiment_context", {"invalid": "arg"})
            # Should still work since get_experiment_context ignores arguments
            assert "content" in result
            assert not result.get("isError", False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])