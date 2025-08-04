#!/usr/bin/env python3
"""
Basic functionality tests to demonstrate test coverage
"""
import pytest
import os
from unittest.mock import patch, Mock

pytestmark = pytest.mark.unit

class TestBasicFunctionality:
    """Test basic functionality that doesn't require complex mocking"""
    
    def test_url_generation_basic(self):
        """Test basic URL generation without complex dependencies"""
        from shared.utils import get_plexus_url
        
        with patch.dict(os.environ, {"PLEXUS_APP_URL": "https://test.example.com"}):
            result = get_plexus_url("path/to/resource")
            assert result == "https://test.example.com/path/to/resource"
    
    def test_url_generation_with_slashes(self):
        """Test URL generation handles slashes correctly"""
        from shared.utils import get_plexus_url
        
        with patch.dict(os.environ, {"PLEXUS_APP_URL": "https://test.example.com/"}):
            result = get_plexus_url("/path/to/resource")
            assert result == "https://test.example.com/path/to/resource"
    
    def test_report_url_generation(self):
        """Test report URL generation"""
        from shared.utils import get_report_url
        
        with patch.dict(os.environ, {"PLEXUS_APP_URL": "https://test.example.com"}):
            report_id = "report-123"
            result = get_report_url(report_id)
            assert result == "https://test.example.com/lab/reports/report-123"
    
    def test_item_url_generation(self):
        """Test item URL generation"""
        from shared.utils import get_item_url
        
        with patch.dict(os.environ, {"PLEXUS_APP_URL": "https://test.example.com"}):
            item_id = "item-456"
            result = get_item_url(item_id)
            assert result == "https://test.example.com/lab/items/item-456"
    
    def test_task_url_generation(self):
        """Test task URL generation"""
        from shared.utils import get_task_url
        
        with patch.dict(os.environ, {"PLEXUS_APP_URL": "https://test.example.com"}):
            task_id = "task-789"
            result = get_task_url(task_id)
            assert result == "https://test.example.com/lab/tasks/task-789"
    
    def test_default_url_when_env_missing(self):
        """Test default URL when environment variable is missing"""
        from shared.utils import get_plexus_url
        
        with patch.dict(os.environ, {}, clear=True):
            result = get_plexus_url("test/path")
            assert "plexus.anth.us" in result
    
    def test_environment_variable_handling(self):
        """Test environment variable handling patterns"""
        # Test getting environment variable with default
        api_url = os.environ.get('PLEXUS_API_URL', 'default_value')
        assert isinstance(api_url, str)
        
        # Test boolean environment variable patterns
        debug_str = os.environ.get('DEBUG', 'false')
        debug_bool = debug_str.lower() in ['true', '1', 'yes']
        assert isinstance(debug_bool, bool)
    
    def test_import_patterns(self):
        """Test that our import patterns work correctly"""
        # Test that we can import shared modules
        from shared.utils import get_plexus_url
        assert callable(get_plexus_url)
        
        from shared.setup import logger
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
    
    def test_stdout_redirection_pattern(self):
        """Test stdout redirection pattern used throughout the codebase"""
        import sys
        from io import StringIO
        
        original_stdout = sys.stdout
        temp_stdout = StringIO()
        
        try:
            sys.stdout = temp_stdout
            print("test output")
            captured = temp_stdout.getvalue()
            assert "test output" in captured
        finally:
            sys.stdout = original_stdout
        
        # Verify stdout is properly restored
        assert sys.stdout == original_stdout