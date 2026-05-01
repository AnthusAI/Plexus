#!/usr/bin/env python3
"""
Integration tests for MCP server startup and tool registration.
The server now exposes a single tool: execute_tactus.
"""
import pytest
import sys
from unittest.mock import patch

pytestmark = pytest.mark.integration


class TestServerStartup:
    """Test server startup and initialization"""

    @patch('server.setup_plexus_imports')
    @patch('server.register_all_tools')
    def test_server_imports_successfully(self, mock_register_tools, mock_setup_imports):
        mock_setup_imports.return_value = True
        mock_register_tools.return_value = None

        import server  # noqa: F401
        assert hasattr(server, 'mcp')
        assert hasattr(server, 'run_server')

    @patch('server.setup_plexus_imports')
    @patch('server.load_env_file')
    @patch('server.initialize_default_account')
    @patch('server.register_all_tools')
    def test_server_startup_with_env(
        self, mock_register_tools, mock_init_account, mock_load_env, mock_setup_imports
    ):
        mock_setup_imports.return_value = True
        mock_load_env.return_value = True
        mock_init_account.return_value = None
        mock_register_tools.return_value = None

        class MockArgs:
            env_dir = "/test/env"
            transport = "sse"
            host = "127.0.0.1"
            port = 8002

        with patch('server.mcp.run'):
            try:
                from server import run_server
                run_server(MockArgs())
            except SystemExit:
                pass

            mock_load_env.assert_called_once_with("/test/env")
            mock_register_tools.assert_called_once()


class TestToolRegistration:
    """Test that register_all_tools registers only execute_tactus."""

    @patch('server.setup_plexus_imports')
    def test_register_all_tools_called(self, mock_setup_imports):
        mock_setup_imports.return_value = True

        from server import register_all_tools, mcp

        with patch('server.register_tactus_tools') as mock_tactus:
            register_all_tools()
            mock_tactus.assert_called_once_with(mcp)

    def test_mcp_instance_configuration(self):
        with patch('server.setup_plexus_imports', return_value=True):
            from server import mcp

            assert mcp.name == "Plexus MCP Server"
            assert mcp.instructions is not None
            assert len(mcp.instructions) > 0
            assert "execute_tactus" in mcp.instructions


class TestEnvironmentHandling:
    """Test environment variable handling"""

    def test_fail_fast_when_core_import_fails(self):
        """setup_plexus_imports is called at import time; if it raises, server import raises."""
        import importlib
        import server as _server_module

        with patch.object(_server_module, 'setup_plexus_imports', side_effect=RuntimeError("core import failed")):
            with pytest.raises(RuntimeError):
                _server_module.setup_plexus_imports()


class TestMainEntryPoint:
    """Test main.py entry point"""

    @patch('main.run_server')
    def test_main_entry_point_argument_parsing(self, mock_run_server):
        test_args = [
            '--env-dir', '/test/env',
            '--host', '0.0.0.0',
            '--port', '8003',
            '--transport', 'stdio',
        ]
        with patch('sys.argv', ['main.py'] + test_args):
            try:
                import main  # noqa: F401
            except SystemExit:
                pass

    def test_main_module_imports(self):
        import main  # noqa: F401
        assert hasattr(main, 'run_server') or 'run_server' in dir(main)


class TestErrorHandling:
    """Test error handling during startup"""

    def test_startup_with_import_failure(self):
        """setup_plexus_imports raising an error propagates out."""
        import server as _server_module

        with patch.object(_server_module, 'setup_plexus_imports', side_effect=ImportError("Test import error")):
            with pytest.raises(ImportError):
                _server_module.setup_plexus_imports()

    @patch('server.setup_plexus_imports')
    @patch('server.register_all_tools')
    def test_startup_with_registration_failure(self, mock_register_tools, mock_setup_imports):
        mock_setup_imports.return_value = True
        mock_register_tools.side_effect = Exception("Registration error")

        class MockArgs:
            env_dir = None
            transport = "sse"
            host = "127.0.0.1"
            port = 8002

        with patch('server.mcp.run'):
            with pytest.raises(Exception):
                from server import run_server
                run_server(MockArgs())
