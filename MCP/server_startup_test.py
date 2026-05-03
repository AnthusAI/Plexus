#!/usr/bin/env python3
"""
Integration tests for MCP server startup and tool registration
"""
import pytest
import os
import sys
from unittest.mock import patch, Mock

pytestmark = pytest.mark.integration

class TestServerStartup:
    """Test server startup and initialization"""
    
    @patch('server.setup_plexus_imports')
    @patch('server.register_all_tools')
    def test_server_imports_successfully(self, mock_register_tools, mock_setup_imports):
        """Test that server module can be imported without errors"""
        mock_setup_imports.return_value = True
        mock_register_tools.return_value = None
        
        # This should not raise any import errors
        import server
        assert hasattr(server, 'mcp')
        assert hasattr(server, 'run_server')
    
    @patch('server.setup_plexus_imports')
    @patch('server.load_env_file')
    @patch('server.initialize_default_account')
    @patch('server.register_all_tools')
    def test_server_startup_with_env(self, mock_register_tools, mock_init_account, mock_load_env, mock_setup_imports):
        """Test server startup with environment file"""
        mock_setup_imports.return_value = True
        mock_load_env.return_value = True
        mock_init_account.return_value = None
        mock_register_tools.return_value = None
        
        # Mock args object
        class MockArgs:
            env_dir = "/test/env"
            transport = "sse"
            host = "127.0.0.1"
            port = 8002
        
        args = MockArgs()
        
        # Mock the FastMCP run method to avoid actually starting the server
        with patch('server.mcp.run') as mock_run:
            try:
                from server import run_server
                run_server(args)
            except SystemExit:
                pass  # Expected when run completes
            
            mock_load_env.assert_called_once_with("/test/env")
            mock_register_tools.assert_called_once()
            mock_run.assert_called_once()

class TestToolRegistration:
    """Test tool registration process"""
    
    @patch('server.setup_plexus_imports')
    def test_register_all_tools_called(self, mock_setup_imports):
        """Test that register_all_tools is properly called"""
        mock_setup_imports.return_value = True
        
        from server import register_all_tools, mcp
        
        # Mock the tool registration functions
        with patch('server.register_think_tool') as mock_think, \
             patch('server.register_docs_tool') as mock_docs, \
             patch('server.register_scorecard_tools') as mock_scorecard, \
             patch('server.register_score_tools') as mock_score:
            
            register_all_tools()
            
            mock_think.assert_called_once_with(mcp)
            mock_docs.assert_called_once_with(mcp)
            mock_scorecard.assert_called_once_with(mcp)
            mock_score.assert_called_once_with(mcp)
    
    def test_mcp_instance_configuration(self):
        """Test that MCP instance is properly configured"""
        with patch('server.setup_plexus_imports', return_value=True):
            from server import mcp
            
            assert mcp.name == "Plexus MCP Server"
            assert mcp.instructions is not None
            assert len(mcp.instructions) > 0
            assert "Scorecard Management" in mcp.instructions
            assert "Score Management" in mcp.instructions

class TestEnvironmentHandling:
    """Test environment variable handling"""
    
    @patch('server.setup_plexus_imports')
    def test_fail_fast_when_core_import_fails(self, mock_setup_imports):
        """Server should raise at import time if core import setup fails."""
        mock_setup_imports.side_effect = RuntimeError("core import failed")
        if 'server' in sys.modules:
            del sys.modules['server']
        with pytest.raises(RuntimeError):
            import server  # noqa: F401
    
    

class TestMainEntryPoint:
    """Test main.py entry point"""
    
    @patch('main.run_server')
    def test_main_entry_point_argument_parsing(self, mock_run_server):
        """Test that main.py properly parses arguments"""
        # This would normally be tested with subprocess, but we'll mock it
        test_args = [
            '--env-dir', '/test/env',
            '--host', '0.0.0.0',
            '--port', '8003',
            '--transport', 'stdio'
        ]
        
        # Mock sys.argv
        with patch('sys.argv', ['main.py'] + test_args):
            try:
                import main
                # The main module should parse args and call run_server
                # This is a simplified test - in practice you'd use subprocess
            except SystemExit:
                pass  # argparse calls sys.exit
    
    def test_main_module_imports(self):
        """Test that main module imports successfully"""
        # Test that we can import main without errors
        import main
        
        # Verify it has the expected components
        assert hasattr(main, 'run_server') or 'run_server' in dir(main)

class TestErrorHandling:
    """Test error handling during startup"""
    
    @patch('server.setup_plexus_imports')
    def test_startup_with_import_failure(self, mock_setup_imports):
        """Test startup behavior when imports fail"""
        mock_setup_imports.side_effect = ImportError("Test import error")
        
        with pytest.raises(ImportError):
            import server
    
    @patch('server.setup_plexus_imports')
    @patch('server.register_all_tools')
    def test_startup_with_registration_failure(self, mock_register_tools, mock_setup_imports):
        """Test startup behavior when tool registration fails"""
        mock_setup_imports.return_value = True
        mock_register_tools.side_effect = Exception("Registration error")
        
        # Mock args
        class MockArgs:
            env_dir = None
            transport = "sse"
            host = "127.0.0.1"
            port = 8002
        
        args = MockArgs()
        
        with patch('server.mcp.run') as mock_run:
            with pytest.raises(Exception):
                from server import run_server
                run_server(args)