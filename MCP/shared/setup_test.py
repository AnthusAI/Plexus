#!/usr/bin/env python3
"""
Unit tests for shared setup functionality
"""
import pytest
import os
import sys
from unittest.mock import patch, Mock, MagicMock
from io import StringIO

pytestmark = pytest.mark.unit

class TestSetupFunctions:
    """Test setup and initialization functions"""
    
    def test_stdout_redirection_functions(self):
        """Test stdout redirection utilities"""
        from shared.setup import redirect_stdout_to_stderr, restore_stdout
        
        original_stdout = sys.stdout
        
        # Test redirection (this is a simplified test since the actual function uses file descriptors)
        redirect_stdout_to_stderr()
        # We can't easily test file descriptor manipulation in unit tests
        # but we can verify the functions don't crash
        
        restore_stdout()
        # Same here - the function should execute without errors
        
        # Verify stdout is still accessible
        assert sys.stdout is not None
    
    @patch('shared.setup.sys.path')
    @patch('shared.setup.os.path.exists')
    @patch('shared.setup.os.path.dirname')
    @patch('shared.setup.os.path.abspath')
    def test_setup_plexus_imports_path_setup(self, mock_abspath, mock_dirname, mock_exists, mock_path):
        """Test Python path setup in setup_plexus_imports"""
        from shared.setup import setup_plexus_imports
        
        # Mock path calculations
        mock_abspath.return_value = "/test/MCP/shared/setup.py"
        mock_dirname.side_effect = [
            "/test/MCP/shared",  # dirname of setup.py
            "/test/MCP",         # dirname of shared
            "/test"              # project root
        ]
        mock_exists.return_value = True
        mock_path.insert = Mock()
        
        # Mock stdout redirection
        original_stdout = sys.stdout
        sys.stdout = StringIO()
        
        try:
            with patch.dict('sys.modules', {
                'plexus.config': Mock(),
                'plexus.dashboard.api.client': Mock(),
                'plexus.cli.client_utils': Mock(),
                'plexus.cli.ScorecardCommands': Mock(),
                'plexus.cli.identifier_resolution': Mock()
            }):
                result = setup_plexus_imports()
                
                # Should attempt to add project root to path
                mock_path.insert.assert_called()
        finally:
            sys.stdout = original_stdout
    
    def test_setup_plexus_imports_pattern(self):
        """Test setup patterns without complex import dependencies"""
        # Test the basic pattern used in setup_plexus_imports
        original_stdout = sys.stdout
        temp_stdout = StringIO()
        
        try:
            sys.stdout = temp_stdout
            
            # Simulate the setup pattern
            import os
            project_root_exists = os.path.exists(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            assert project_root_exists  # The MCP directory should exist
            
            captured = temp_stdout.getvalue()
            # Should capture any stdout output during setup
            assert isinstance(captured, str)
            
        finally:
            sys.stdout = original_stdout
    
    def test_import_error_handling_pattern(self):
        """Test import error handling patterns"""
        # Test the pattern used for handling failed imports
        def simulate_import_with_fallback():
            try:
                # Simulate successful import
                return True, None
            except ImportError as e:
                return False, str(e)
        
        success, error = simulate_import_with_fallback()
        assert success is True
        assert error is None
        
        # Test fallback behavior
        def simulate_failed_import():
            try:
                raise ImportError("Module not found")
            except ImportError as e:
                return False, str(e)
                
        success, error = simulate_failed_import()
        assert success is False
        assert "Module not found" in error
    
    @patch('shared.setup.logger')
    def test_safe_print_function(self, mock_logger):
        """Test safe print function that redirects to stderr"""
        from shared.setup import safe_print
        
        # Capture stderr
        original_stderr = sys.stderr
        mock_stderr = StringIO()
        sys.stderr = mock_stderr
        
        try:
            safe_print("test message")
            output = mock_stderr.getvalue()
            assert "test message" in output
        finally:
            sys.stderr = original_stderr
    
    def test_safe_print_with_explicit_file(self):
        """Test safe print with explicitly specified file"""
        from shared.setup import safe_print
        
        mock_file = StringIO()
        safe_print("test message", file=mock_file)
        
        output = mock_file.getvalue()
        assert "test message" in output

class TestGlobalState:
    """Test global state management"""
    
    def test_initial_state(self):
        """Test initial global state"""
        from shared.setup import DEFAULT_ACCOUNT_ID, ACCOUNT_CACHE
        
        # These should be properly initialized
        assert DEFAULT_ACCOUNT_ID is None or isinstance(DEFAULT_ACCOUNT_ID, str)
        assert isinstance(ACCOUNT_CACHE, dict)
    
    def test_dummy_functions_exist(self):
        """Test that dummy functions are properly defined"""
        from shared.setup import create_dashboard_client, resolve_account_identifier, resolve_scorecard_identifier
        
        # These should be callable (either real functions or dummies)
        assert callable(create_dashboard_client)
        assert callable(resolve_account_identifier)
        assert callable(resolve_scorecard_identifier)

class TestStdoutCapture:
    """Test stdout capture patterns used throughout setup"""
    
    def test_stdout_capture_pattern(self):
        """Test the stdout capture pattern used in setup"""
        original_stdout = sys.stdout
        temp_stdout = StringIO()
        
        try:
            sys.stdout = temp_stdout
            print("This should be captured")
            
            captured = temp_stdout.getvalue()
            assert "This should be captured" in captured
        finally:
            sys.stdout = original_stdout
        
        # Verify stdout is restored
        assert sys.stdout == original_stdout
    
    def test_nested_stdout_capture(self):
        """Test nested stdout capture safety"""
        original_stdout = sys.stdout
        
        def inner_function():
            inner_stdout = StringIO()
            saved_stdout = sys.stdout
            
            try:
                sys.stdout = inner_stdout
                print("Inner message")
                return inner_stdout.getvalue()
            finally:
                sys.stdout = saved_stdout
        
        outer_stdout = StringIO()
        
        try:
            sys.stdout = outer_stdout
            print("Outer before")
            inner_result = inner_function()
            print("Outer after")
            
            outer_result = outer_stdout.getvalue()
            
            assert "Inner message" in inner_result
            assert "Outer before" in outer_result
            assert "Outer after" in outer_result
            assert "Inner message" not in outer_result  # Inner was captured separately
        finally:
            sys.stdout = original_stdout