#!/usr/bin/env python3
"""
Tests for the Plexus FastMCP server
"""
import os
import unittest
from unittest.mock import patch
from plexus_fastmcp_server import get_plexus_url, get_report_url, get_item_url

class TestPlexusFastmcpServer(unittest.TestCase):
    """Test cases for the Plexus FastMCP server functions"""
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us"})
    def test_get_plexus_url_normal_path(self):
        """Test URL construction with normal path"""
        self.assertEqual(
            get_plexus_url("lab/items"), 
            "https://plexus.anth.us/lab/items"
        )
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us"})
    def test_get_plexus_url_leading_slash(self):
        """Test URL construction with path that has leading slash"""
        self.assertEqual(
            get_plexus_url("/lab/items"), 
            "https://plexus.anth.us/lab/items"
        )
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us/"})
    def test_get_plexus_url_trailing_slash_in_base(self):
        """Test URL construction with base URL having trailing slash"""
        self.assertEqual(
            get_plexus_url("lab/items"), 
            "https://plexus.anth.us/lab/items"
        )
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us/"})
    def test_get_plexus_url_both_slashes(self):
        """Test URL construction with both trailing slash in base and leading slash in path"""
        self.assertEqual(
            get_plexus_url("/lab/items"), 
            "https://plexus.anth.us/lab/items"
        )
    
    @patch.dict(os.environ, {})
    def test_get_plexus_url_default_base(self):
        """Test URL construction with default base URL when env var is missing"""
        self.assertEqual(
            get_plexus_url("lab/items"), 
            "https://plexus.anth.us/lab/items"
        )
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us"})
    def test_get_report_url(self):
        """Test report URL generation with a sample report ID"""
        report_id = "c4b18932-4b60-4484-afc7-cf3b47739d8d"
        expected_url = "https://plexus.anth.us/lab/reports/c4b18932-4b60-4484-afc7-cf3b47739d8d"
        self.assertEqual(get_report_url(report_id), expected_url)
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us/"})
    def test_get_report_url_with_trailing_slash(self):
        """Test report URL generation with a trailing slash in the base URL"""
        report_id = "c4b18932-4b60-4484-afc7-cf3b47739d8d"
        expected_url = "https://plexus.anth.us/lab/reports/c4b18932-4b60-4484-afc7-cf3b47739d8d"
        self.assertEqual(get_report_url(report_id), expected_url)
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us"})
    def test_get_item_url(self):
        """Test item URL generation with a sample item ID"""
        item_id = "cf749649-2467-4e5c-b27c-787ac6c61edd"
        expected_url = "https://plexus.anth.us/lab/items/cf749649-2467-4e5c-b27c-787ac6c61edd"
        self.assertEqual(get_item_url(item_id), expected_url)
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "https://plexus.anth.us/"})
    def test_get_item_url_with_trailing_slash(self):
        """Test item URL generation with a trailing slash in the base URL"""
        item_id = "cf749649-2467-4e5c-b27c-787ac6c61edd"
        expected_url = "https://plexus.anth.us/lab/items/cf749649-2467-4e5c-b27c-787ac6c61edd"
        self.assertEqual(get_item_url(item_id), expected_url)
    
    @patch.dict(os.environ, {"PLEXUS_APP_URL": "http://localhost:3001"})
    def test_get_item_url_localhost(self):
        """Test item URL generation with localhost (user's example)"""
        item_id = "cf749649-2467-4e5c-b27c-787ac6c61edd"
        expected_url = "http://localhost:3001/lab/items/cf749649-2467-4e5c-b27c-787ac6c61edd"
        self.assertEqual(get_item_url(item_id), expected_url)

if __name__ == "__main__":
    unittest.main() 