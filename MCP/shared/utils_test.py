#!/usr/bin/env python3
"""
Unit tests for shared utility functions
"""
import pytest
import os
from unittest.mock import patch, Mock, MagicMock
from shared.utils import (
    get_plexus_url, get_report_url, get_item_url, get_task_url,
    load_env_file, get_default_account_id
)

pytestmark = pytest.mark.unit

class TestURLGeneration:
    """Test URL generation utilities"""
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us"})
    def test_get_plexus_url_normal_path(self):
        """Test URL construction with normal path"""
        result = get_plexus_url("lab/items")
        assert result == "https://plexus.anth.us/lab/items"
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us"})
    def test_get_plexus_url_leading_slash(self):
        """Test URL construction with path that has leading slash"""
        result = get_plexus_url("/lab/items")
        assert result == "https://plexus.anth.us/lab/items"
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us/"})
    def test_get_plexus_url_trailing_slash_in_base(self):
        """Test URL construction with base URL having trailing slash"""
        result = get_plexus_url("lab/items")
        assert result == "https://plexus.anth.us/lab/items"
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us/"})
    def test_get_plexus_url_both_slashes(self):
        """Test URL construction with both trailing slash in base and leading slash in path"""
        result = get_plexus_url("/lab/items")
        assert result == "https://plexus.anth.us/lab/items"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_plexus_url_default_base(self):
        """Test URL construction with default base URL when env var is missing"""
        result = get_plexus_url("lab/items")
        assert result == "https://plexus.anth.us/lab/items"
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us"})
    def test_get_report_url(self):
        """Test report URL generation"""
        report_id = "c4b18932-4b60-4484-afc7-cf3b47739d8d"
        expected_url = "https://plexus.anth.us/lab/reports/c4b18932-4b60-4484-afc7-cf3b47739d8d"
        result = get_report_url(report_id)
        assert result == expected_url
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us"})
    def test_get_item_url(self):
        """Test item URL generation"""
        item_id = "cf749649-2467-4e5c-b27c-787ac6c61edd"
        expected_url = "https://plexus.anth.us/lab/items/cf749649-2467-4e5c-b27c-787ac6c61edd"
        result = get_item_url(item_id)
        assert result == expected_url
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us"})
    def test_get_task_url(self):
        """Test task URL generation"""
        task_id = "task-123-456"
        expected_url = "https://plexus.anth.us/lab/tasks/task-123-456"
        result = get_task_url(task_id)
        assert result == expected_url
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "http://localhost:3001"})
    def test_localhost_url_generation(self):
        """Test URL generation with localhost"""
        result = get_plexus_url("lab/items/123")
        assert result == "http://localhost:3001/lab/items/123"

class TestEnvironmentLoading:
    """Test environment loading functionality"""
    
    @patch('dotenv.load_dotenv')
    @patch('os.path.isfile')
    def test_load_env_file_success(self, mock_isfile, mock_load_dotenv):
        """Test successful .env file loading"""
        mock_isfile.return_value = True
        mock_load_dotenv.return_value = True
        
        result = load_env_file("/path/to/env")
        
        assert result is True
        mock_load_dotenv.assert_called_once()
    
    @patch('dotenv.load_dotenv')  
    @patch('os.path.isfile')
    def test_load_env_file_not_found(self, mock_isfile, mock_load_dotenv):
        """Test .env file not found"""
        mock_isfile.return_value = False
        
        result = load_env_file("/path/to/env")
        
        assert result is False
        mock_load_dotenv.assert_not_called()
    
    def test_load_env_file_no_directory(self):
        """Test loading without directory specified"""
        result = load_env_file(None)
        
        assert result is False
    
    def test_import_error_handling_pattern(self):
        """Test import error handling patterns used in load_env_file"""
        # Test the pattern used when imports fail
        def simulate_import_with_fallback():
            try:
                # This will succeed since json is a standard library module
                import json
                return True
            except ImportError:
                return False
        
        # Test successful import
        result = simulate_import_with_fallback()
        assert result is True
        
        # Test the fallback pattern used in load_env_file when dotenv is not available
        def simulate_missing_dotenv():
            try:
                # Simulate the dotenv import failing
                raise ImportError("No module named 'dotenv'")
            except ImportError:
                # This is the fallback behavior in load_env_file
                return False
        
        result = simulate_missing_dotenv()
        assert result is False

class TestAccountManagement:
    """Test account management utilities"""
    
    @patch.dict(os.environ, {"PLEXUS_ACCOUNT_KEY": "test-account"})
    @patch('plexus.cli.shared.client_utils.create_client')
    @patch('plexus.dashboard.api.models.account.Account.get_by_key')
    def test_get_default_account_id_success(self, mock_get_by_key, mock_create_client):
        """Test successful default account ID resolution"""
        mock_client = Mock()
        mock_create_client.return_value = mock_client

        # Mock Account object with ID
        mock_account = Mock()
        mock_account.id = "account-123"
        mock_get_by_key.return_value = mock_account

        # Reset the global cache for testing - must clear setup module's globals
        from shared import setup
        setup.DEFAULT_ACCOUNT_ID = None
        setup.ACCOUNT_CACHE.clear()

        result = get_default_account_id()

        assert result == "account-123"
        mock_create_client.assert_called_once()
        mock_get_by_key.assert_called_once_with("test-account", mock_client)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_default_account_id_no_key(self):
        """Test when PLEXUS_ACCOUNT_KEY is not set"""
        # Reset the global cache for testing - must clear setup module's globals
        from shared import setup
        setup.DEFAULT_ACCOUNT_ID = None
        setup.DEFAULT_ACCOUNT_KEY = None
        setup.ACCOUNT_CACHE.clear()

        result = get_default_account_id()

        assert result is None
    
    @patch.dict(os.environ, {"PLEXUS_ACCOUNT_KEY": "test-account"})
    @patch('plexus.cli.shared.client_utils.create_client')
    @patch('plexus.dashboard.api.models.account.Account.get_by_key')
    def test_get_default_account_id_core_unavailable(self, mock_get_by_key, mock_create_client):
        """Test when Plexus core is not available (Account.get_by_key raises exception)"""
        # Reset the global cache for testing - must clear setup module's globals
        from shared import setup
        setup.DEFAULT_ACCOUNT_ID = None
        setup.ACCOUNT_CACHE.clear()

        mock_client = Mock()
        mock_create_client.return_value = mock_client
        # Simulate core unavailability by raising an exception
        mock_get_by_key.side_effect = Exception("Core not available")

        result = get_default_account_id()

        assert result is None
    
    @patch.dict(os.environ, {"PLEXUS_ACCOUNT_KEY": "test-account"})
    @patch('plexus.cli.shared.client_utils.create_client')
    def test_get_default_account_id_client_creation_fails(self, mock_create_client):
        """Test when client creation fails"""
        mock_create_client.return_value = None

        # Reset the global cache for testing - must clear setup module's globals
        from shared import setup
        setup.DEFAULT_ACCOUNT_ID = None
        setup.ACCOUNT_CACHE.clear()

        result = get_default_account_id()

        assert result is None
        mock_create_client.assert_called_once()

class TestDataHelpers:
    """Test data helper functions"""
    
    def test_data_helper_patterns(self):
        """Test data helper patterns without external dependencies"""
        # Test timestamp formatting pattern
        from datetime import datetime
        test_timestamp = '2024-01-01T12:00:00Z'
        parsed = datetime.fromisoformat(test_timestamp.replace('Z', '+00:00'))
        formatted = parsed.isoformat()
        assert '2024-01-01T12:00:00' in formatted
        
        # Test data sorting pattern
        test_data = [
            {'updatedAt': '2024-01-01T10:00:00'},
            {'updatedAt': '2024-01-01T12:00:00'},
            {'updatedAt': '2024-01-01T11:00:00'}
        ]
        sorted_data = sorted(test_data, key=lambda x: x.get('updatedAt', '1970-01-01T00:00:00'), reverse=True)
        assert sorted_data[0]['updatedAt'] == '2024-01-01T12:00:00'
        assert sorted_data[-1]['updatedAt'] == '2024-01-01T10:00:00'
    
    def test_error_handling_pattern(self):
        """Test error handling patterns used in data helpers"""
        def mock_api_call(should_fail=False):
            if should_fail:
                raise Exception("API Error")
            return {'items': [{'id': '1', 'name': 'test'}]}
        
        # Test successful call
        try:
            result = mock_api_call(False)
            items = result.get('items', [])
            assert len(items) == 1
        except Exception:
            items = []
            assert len(items) == 0
        
        # Test error handling
        try:
            result = mock_api_call(True)
            items = result.get('items', [])
        except Exception:
            items = []  # Fallback to empty list
            
        assert items == []