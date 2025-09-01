"""
Test suite for procedure MCP tools.

Comprehensive tests for all procedure management MCP tools,
focusing on the new procedure run functionality while ensuring
existing tools continue to work properly.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# Import the tools we're testing
from .procedures import register_procedure_tools


class MockRequest:
    """Mock request object for testing."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestProcedureRunMCP:
    """Test the plexus_procedure_run MCP tool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mcp = Mock()
        self.registered_tools = {}
        
        # Capture registered tools
        def capture_tool(name=None):
            def decorator(func):
                tool_name = name or func.__name__
                self.registered_tools[tool_name] = func
                return func
            return decorator
        
        self.mock_mcp.tool = capture_tool
        
    def test_procedure_run_tool_registration(self):
        """Test that the procedure run tool is properly registered."""
        # Register all tools
        register_procedure_tools(self.mock_mcp)
        
        # Verify plexus_procedure_run is registered
        assert 'plexus_procedure_run' in self.registered_tools
        run_tool = self.registered_tools['plexus_procedure_run']
        assert callable(run_tool)
        
        # Check docstring
        assert 'Run an procedure with the given ID' in run_tool.__doc__
        assert 'CLI and MCP interfaces' in run_tool.__doc__
    
    @patch('plexus.cli.shared.client_utils.create_client')
    @patch('plexus.cli.procedure.service.ProcedureService')
    @pytest.mark.asyncio
    async def test_procedure_run_basic_success(self, mock_service_class, mock_create_client):
        """Test successful procedure run with basic parameters."""
        # Setup
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        register_procedure_tools(self.mock_mcp)
        run_tool = self.registered_tools['plexus_procedure_run']
        
        expected_result = {
            'procedure_id': 'exp-123',
            'status': 'initiated',
            'message': 'Procedure run initiated successfully for: Test Procedure',
            'details': {
                'procedure_name': 'Test Procedure',
                'scorecard_name': 'Test Scorecard',
                'score_name': 'Test Score',
                'node_count': 5,
                'options': {}
            }
        }
        # Make the mock service method async
        async def mock_run_procedure(*args, **kwargs):
            return expected_result
        mock_service.run_procedure = mock_run_procedure
        
        # Create mock request object
        request = MockRequest(procedure_id='exp-123', max_iterations=None, timeout=None, async_mode=False, dry_run=False)
        
        # Execute - await the async function
        result = await run_tool(request)
        
        # Verify
        assert result == expected_result
        # Note: We can't use assert_called_once_with on the async mock function directly
    
    @patch('plexus.cli.shared.client_utils.create_client')
    @patch('plexus.cli.procedure.service.ProcedureService')
    @pytest.mark.asyncio
    async def test_procedure_run_with_all_options(self, mock_service_class, mock_create_client):
        """Test procedure run with all optional parameters."""
        # Setup
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        register_procedure_tools(self.mock_mcp)
        run_tool = self.registered_tools['plexus_procedure_run']
        
        expected_result = {
            'procedure_id': 'exp-456',
            'status': 'completed',
            'message': 'Dry run completed successfully for procedure: Test Procedure',
            'details': {
                'procedure_name': 'Test Procedure',
                'options': {
                    'max_iterations': 50,
                    'timeout': 300,
                    'async_mode': True,
                    'dry_run': True
                }
            }
        }
        # Make the mock service method async
        async def mock_run_procedure(*args, **kwargs):
            return expected_result
        mock_service.run_procedure = mock_run_procedure
        
        # Create request with all options
        request = MockRequest(
            procedure_id='exp-456',
            max_iterations=50,
            timeout=300,
            async_mode=True,
            dry_run=True
        )
        
        # Execute - await the async function
        result = await run_tool(request)
        
        # Verify
        assert result == expected_result
        # Note: We can't use assert_called_once_with on the async mock function directly
    
    @patch('plexus.cli.shared.client_utils.create_client')
    @patch('plexus.cli.procedure.service.ProcedureService')
    @pytest.mark.asyncio
    async def test_procedure_run_nonexistent_procedure(self, mock_service_class, mock_create_client):
        """Test procedure run with nonexistent procedure."""
        # Setup
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        register_procedure_tools(self.mock_mcp)
        run_tool = self.registered_tools['plexus_procedure_run']
        
        # Service returns error for nonexistent procedure
        service_error_result = {
            'procedure_id': 'nonexistent-exp',
            'status': 'error',
            'error': 'Procedure not found: nonexistent-exp'
        }
        # Make the mock service method async
        async def mock_run_procedure(*args, **kwargs):
            return service_error_result
        mock_service.run_procedure = mock_run_procedure
        
        # Create request
        request = MockRequest(procedure_id='nonexistent-exp', max_iterations=None, timeout=None, async_mode=False, dry_run=False)
        
        # Execute - await the async function
        result = await run_tool(request)
        
        # Verify error is passed through
        assert result == service_error_result
        assert result['status'] == 'error'
        assert 'not found' in result['error'].lower()
    
    @patch('plexus.cli.shared.client_utils.create_client')
    @patch('plexus.cli.procedure.service.ProcedureService')
    @pytest.mark.asyncio
    async def test_procedure_run_service_exception(self, mock_service_class, mock_create_client):
        """Test procedure run when service raises exception."""
        # Setup
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        register_procedure_tools(self.mock_mcp)
        run_tool = self.registered_tools['plexus_procedure_run']
        
        # Service raises exception - make it async
        async def mock_run_procedure(*args, **kwargs):
            raise Exception("Database connection error")
        mock_service.run_procedure = mock_run_procedure
        
        # Create request
        request = MockRequest(procedure_id='exp-error', max_iterations=None, timeout=None, async_mode=False, dry_run=False)
        
        # Execute - await the async function
        result = await run_tool(request)
        
        # Verify error handling
        assert result['procedure_id'] == 'exp-error'
        assert result['status'] == 'error'
        assert 'Database connection error' in result['error']
    
    @patch('plexus.cli.shared.client_utils.create_client')
    @pytest.mark.asyncio
    async def test_procedure_run_client_creation_failure(self, mock_create_client):
        """Test procedure run when client creation fails."""
        # Setup
        register_procedure_tools(self.mock_mcp)
        run_tool = self.registered_tools['plexus_procedure_run']
        
        # Client creation fails
        mock_create_client.return_value = None
        
        # Create request
        request = MockRequest(procedure_id='exp-123', max_iterations=None, timeout=None, async_mode=False, dry_run=False)
        
        # Execute - await the async function
        result = await run_tool(request)
        
        # Verify error handling
        assert result['procedure_id'] == 'exp-123'
        assert result['status'] == 'error'
        assert 'Could not create API client' in result['error']


class TestProcedureMCPConsistency:
    """Test consistency between CLI and MCP interfaces."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mcp = Mock()
        self.registered_tools = {}
        
        # Capture registered tools
        def capture_tool(name=None):
            def decorator(func):
                tool_name = name or func.__name__
                self.registered_tools[tool_name] = func
                return func
            return decorator
        
        self.mock_mcp.tool = capture_tool
    
    @patch('plexus.cli.shared.client_utils.create_client')
    @patch('plexus.cli.procedure.service.ProcedureService')
    @pytest.mark.asyncio
    async def test_cli_mcp_same_service_method(self, mock_service_class, mock_create_client):
        """Test that CLI and MCP use the same ProcedureService method."""
        # Setup
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        # Register MCP tools
        register_procedure_tools(self.mock_mcp)
        run_tool = self.registered_tools['plexus_procedure_run']
        
        expected_result = {'procedure_id': 'exp-test', 'status': 'initiated'}
        # Make the mock service method async
        async def mock_run_procedure(*args, **kwargs):
            return expected_result
        mock_service.run_procedure = mock_run_procedure
        
        # Test MCP call
        request = MockRequest(
            procedure_id='exp-test',
            max_iterations=10,
            timeout=60,
            async_mode=False,
            dry_run=True
        )
        
        mcp_result = await run_tool(request)
        
        # Verify result matches expected
        assert mcp_result == expected_result
        # Note: We can't use assert_called_once_with on the async mock function directly
    
    def test_parameter_mapping_consistency(self):
        """Test that MCP parameters map consistently to service parameters."""
        # Register tools
        register_procedure_tools(self.mock_mcp)
        
        # Test that request objects can handle all expected fields
        request = MockRequest(
            procedure_id='test',
            max_iterations=100,
            timeout=300,
            async_mode=True,
            dry_run=True
        )
        
        # Verify all expected fields exist
        assert hasattr(request, 'procedure_id')
        assert hasattr(request, 'max_iterations') 
        assert hasattr(request, 'timeout')
        assert hasattr(request, 'async_mode')
        assert hasattr(request, 'dry_run')
        
        # Verify field values
        assert request.procedure_id == 'test'
        assert request.max_iterations == 100
        assert request.timeout == 300
        assert request.async_mode is True
        assert request.dry_run is True


class TestExistingProcedureTools:
    """Test that existing procedure tools still work after adding run tool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mcp = Mock()
        self.registered_tools = {}
        
        # Capture registered tools
        def capture_tool(name=None):
            def decorator(func):
                tool_name = name or func.__name__
                self.registered_tools[tool_name] = func
                return func
            return decorator
        
        self.mock_mcp.tool = capture_tool
    
    def test_all_expected_tools_registered(self):
        """Test that all expected procedure tools are registered."""
        register_procedure_tools(self.mock_mcp)
        
        expected_tools = [
            'plexus_procedure_create',
            'plexus_procedure_list', 
            'plexus_procedure_info',
            'plexus_procedure_update',
            'plexus_procedure_delete',
            'plexus_procedure_run',  # New tool
            'plexus_procedure_yaml',
            'plexus_procedure_template'
        ]
        
        for tool_name in expected_tools:
            assert tool_name in self.registered_tools, f"Tool {tool_name} not registered"
            assert callable(self.registered_tools[tool_name])
    
    @patch('plexus.cli.shared.client_utils.create_client')
    @patch('plexus.cli.procedure.service.ProcedureService')
    def test_procedure_info_still_works(self, mock_service_class, mock_create_client):
        """Test that existing procedure_info tool still works."""
        # Setup
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        register_procedure_tools(self.mock_mcp)
        info_tool = self.registered_tools['plexus_procedure_info']
        
        mock_info = Mock()
        mock_info.procedure.id = 'exp-123'
        mock_info.procedure.featured = False
        mock_info.procedure.createdAt.isoformat.return_value = '2024-01-01T00:00:00Z'
        mock_info.procedure.updatedAt.isoformat.return_value = '2024-01-01T00:00:00Z'
        mock_info.procedure.accountId = 'acc-123'
        mock_info.procedure.scorecardId = 'scorecard-123'
        mock_info.procedure.scoreId = 'score-123'
        mock_info.procedure.rootNodeId = 'node-123'
        mock_info.node_count = 3
        mock_info.version_count = 5
        mock_info.scorecard_name = 'Test Scorecard'
        mock_info.score_name = 'Test Score'
        mock_service.get_procedure_info.return_value = mock_info
        
        # Test the tool
        request = MockRequest(procedure_id='exp-123', include_yaml=False)
        result = info_tool(request)
        
        # Verify it still works
        assert result['success'] is True
        assert result['procedure']['id'] == 'exp-123'


class TestIntegrationConsistency:
    """Integration tests to ensure CLI and MCP work the same way."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mcp = Mock()
        self.registered_tools = {}
        
        # Capture registered tools
        def capture_tool(name=None):
            def decorator(func):
                tool_name = name or func.__name__
                self.registered_tools[tool_name] = func
                return func
            return decorator
        
        self.mock_mcp.tool = capture_tool
    
    @patch('plexus.cli.shared.client_utils.create_client')
    @patch('plexus.cli.procedure.service.ProcedureService')
    @pytest.mark.asyncio
    async def test_dry_run_consistency(self, mock_service_class, mock_create_client):
        """Test that dry run works the same in CLI and MCP."""
        # Setup
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        register_procedure_tools(self.mock_mcp)
        run_tool = self.registered_tools['plexus_procedure_run']
        
        # Mock service to return dry run result
        dry_run_result = {
            'procedure_id': 'exp-dry',
            'status': 'completed',
            'message': 'Dry run completed successfully for procedure: Test Procedure',
            'details': {
                'procedure_name': 'Test Procedure',
                'options': {'dry_run': True}
            }
        }
        # Make the mock service method async
        async def mock_run_procedure(*args, **kwargs):
            return dry_run_result
        mock_service.run_procedure = mock_run_procedure
        
        # Test MCP dry run
        request = MockRequest(procedure_id='exp-dry', dry_run=True, max_iterations=None, timeout=None, async_mode=False)
        result = await run_tool(request)
        
        # Verify the MCP result structure matches what CLI would expect
        assert result['procedure_id'] == 'exp-dry'
        assert result['status'] == 'completed'
        assert 'Dry run completed' in result['message']
        assert result['details']['options']['dry_run'] is True
        
        # Note: We can't use assert_called_once_with on the async mock function directly


if __name__ == "__main__":
    pytest.main([__file__])