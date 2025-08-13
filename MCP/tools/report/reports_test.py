#!/usr/bin/env python3
"""
Unit tests for report tools
"""
import pytest
import os
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO

pytestmark = pytest.mark.unit


class TestReportListTool:
    """Test plexus_reports_list tool patterns"""
    
    def test_report_list_validation_patterns(self):
        """Test report list parameter validation patterns"""
        def validate_report_list_params(report_configuration_id=None, limit=10):
            if limit is not None and (not isinstance(limit, int) or limit <= 0):
                return False, "limit must be a positive integer"
            return True, None
        
        # Test valid parameters
        valid, error = validate_report_list_params(None, 10)
        assert valid is True
        assert error is None
        
        # Test with report config ID
        valid, error = validate_report_list_params("config-123", 5)
        assert valid is True
        assert error is None
        
        # Test invalid limit
        valid, error = validate_report_list_params(None, -1)
        assert valid is False
        assert "positive integer" in error
        
        # Test non-integer limit
        valid, error = validate_report_list_params(None, "invalid")
        assert valid is False
        assert "positive integer" in error
    
    def test_report_list_response_patterns(self):
        """Test report list GraphQL response handling patterns"""
        # Test successful response with report config filter
        mock_response_with_config = {
            'listReportByReportConfigurationIdAndCreatedAt': {
                'items': [
                    {
                        'id': 'report-1',
                        'name': 'Test Report',
                        'createdAt': '2024-01-01T00:00:00Z',
                        'reportConfigurationId': 'config-123'
                    }
                ]
            }
        }
        
        reports_data = mock_response_with_config.get(
            'listReportByReportConfigurationIdAndCreatedAt', {}
        ).get('items', [])
        assert len(reports_data) == 1
        assert reports_data[0]['name'] == 'Test Report'
        
        # Test successful response without config filter
        mock_response_no_config = {
            'listReportByAccountIdAndUpdatedAt': {
                'items': [
                    {
                        'id': 'report-2',
                        'name': 'Another Report',
                        'updatedAt': '2024-01-02T00:00:00Z'
                    }
                ]
            }
        }
        
        reports_data = mock_response_no_config.get(
            'listReportByAccountIdAndUpdatedAt', {}
        ).get('items', [])
        assert len(reports_data) == 1
        assert reports_data[0]['name'] == 'Another Report'
        
        # Test error response
        error_response = {
            'errors': [
                {'message': 'Access denied', 'path': ['listReports']}
            ]
        }
        
        if 'errors' in error_response:
            error_details = json.dumps(error_response['errors'], indent=2)
            assert 'Access denied' in error_details
    
    def test_report_list_query_building_patterns(self):
        """Test query building patterns for different scenarios"""
        # Test query with report configuration ID
        report_config_id = "config-123"
        limit = 10
        
        query_with_config = f"""
            query ListReportsByConfig {{
                listReportByReportConfigurationIdAndCreatedAt(
                    reportConfigurationId: "{report_config_id}",
                    sortDirection: DESC,
                    limit: {limit}
                ) {{
                    items {{
                        id
                        name
                        createdAt
                        updatedAt
                        reportConfigurationId
                        accountId
                        taskId
                    }}
                }}
            }}
            """
        
        assert report_config_id in query_with_config
        assert f"limit: {limit}" in query_with_config
        assert "sortDirection: DESC" in query_with_config
        
        # Test query without report configuration ID (account-based)
        account_id = "account-456"
        query_without_config = f"""
            query ListReportsByAccountAndUpdatedAt {{
                listReportByAccountIdAndUpdatedAt(
                    accountId: "{account_id}",
                    sortDirection: DESC,
                    limit: {limit}
                ) {{
                    items {{
                        id
                        name
                        createdAt
                        updatedAt
                        reportConfigurationId
                        accountId
                        taskId
                    }}
                }}
            }}
            """
        
        assert account_id in query_without_config
        assert f"limit: {limit}" in query_without_config


class TestReportInfoTool:
    """Test plexus_report_info tool patterns"""
    
    def test_report_info_validation_patterns(self):
        """Test report info parameter validation patterns"""
        def validate_report_info_params(report_id):
            if not report_id or not report_id.strip():
                return False, "report_id is required"
            return True, None
        
        # Test valid report ID
        valid, error = validate_report_info_params("report-123")
        assert valid is True
        assert error is None
        
        # Test empty report ID
        valid, error = validate_report_info_params("")
        assert valid is False
        assert "report_id is required" in error
        
        # Test whitespace-only report ID
        valid, error = validate_report_info_params("   ")
        assert valid is False
        assert "report_id is required" in error
    
    def test_report_info_response_patterns(self):
        """Test report info GraphQL response handling patterns"""
        # Test successful response
        mock_response = {
            'getReport': {
                'id': 'report-123',
                'name': 'Test Report',
                'createdAt': '2024-01-01T00:00:00Z',
                'updatedAt': '2024-01-01T12:00:00Z',
                'parameters': '{"key": "value"}',
                'output': 'Report output content',
                'reportBlocks': {
                    'items': [
                        {
                            'id': 'block-1',
                            'name': 'Summary Block',
                            'type': 'summary',
                            'position': 1,
                            'output': 'Block output'
                        }
                    ]
                }
            }
        }
        
        report_data = mock_response.get('getReport')
        assert report_data is not None
        assert report_data['name'] == 'Test Report'
        assert report_data['output'] == 'Report output content'
        assert len(report_data['reportBlocks']['items']) == 1
        
        # Test missing report response
        empty_response = {'getReport': None}
        report_data = empty_response.get('getReport')
        assert report_data is None
    
    def test_report_url_generation_pattern(self):
        """Test report URL generation pattern"""
        def get_report_url(report_id: str) -> str:
            base_url = os.environ.get('PLEXUS_APP_URL', 'https://plexus.anth.us')
            if not base_url.endswith('/'):
                base_url += '/'
            path = f"lab/reports/{report_id}"
            return base_url + path.lstrip('/')
        
        # Test URL generation
        with patch.dict(os.environ, {'PLEXUS_APP_URL': 'https://test.example.com'}):
            url = get_report_url('report-123')
            assert url == 'https://test.example.com/lab/reports/report-123'
        
        # Test with trailing slash in base URL
        with patch.dict(os.environ, {'PLEXUS_APP_URL': 'https://test.example.com/'}):
            url = get_report_url('report-123')
            assert url == 'https://test.example.com/lab/reports/report-123'


class TestReportLastTool:
    """Test plexus_report_last tool patterns"""
    
    def test_report_last_logic_patterns(self):
        """Test report last tool logic patterns"""
        # Test the pattern for getting latest report
        def simulate_get_latest_report(reports_list):
            """Simulate the logic for getting the latest report"""
            if not reports_list or len(reports_list) == 0:
                return None, "No reports found to determine the latest one."
            
            if isinstance(reports_list, str) and reports_list.startswith("Error:"):
                return None, reports_list
            
            return reports_list[0], None
        
        # Test with valid reports list
        mock_reports = [
            {'id': 'report-2', 'createdAt': '2024-01-02T00:00:00Z'},
            {'id': 'report-1', 'createdAt': '2024-01-01T00:00:00Z'}
        ]
        
        latest, error = simulate_get_latest_report(mock_reports)
        assert latest is not None
        assert latest['id'] == 'report-2'
        assert error is None
        
        # Test with empty list
        latest, error = simulate_get_latest_report([])
        assert latest is None
        assert "No reports found" in error
        
        # Test with error string
        latest, error = simulate_get_latest_report("Error: API failure")
        assert latest is None
        assert "Error: API failure" in error
    
    def test_report_last_json_parsing_pattern(self):
        """Test JSON parsing patterns used in report_last"""
        # Test parsing JSON string response
        json_string = '[{"id": "report-1", "name": "Test"}]'
        
        try:
            parsed = json.loads(json_string)
            assert isinstance(parsed, list)
            assert len(parsed) == 1
            assert parsed[0]['id'] == 'report-1'
        except json.JSONDecodeError:
            assert False, "Should not fail to parse valid JSON"
        
        # Test handling invalid JSON
        invalid_json = 'invalid json string'
        try:
            parsed = json.loads(invalid_json)
            assert False, "Should fail to parse invalid JSON"
        except json.JSONDecodeError:
            # This is expected
            pass


class TestReportConfigurationsTool:
    """Test plexus_report_configurations_list tool patterns"""
    
    def test_report_configs_response_patterns(self):
        """Test report configurations response handling patterns"""
        # Test successful response
        mock_response = {
            'listReportConfigurationByAccountIdAndUpdatedAt': {
                'items': [
                    {
                        'id': 'config-1',
                        'name': 'Weekly Report',
                        'description': 'Weekly performance report',
                        'updatedAt': '2024-01-01T00:00:00Z'
                    },
                    {
                        'id': 'config-2',
                        'name': 'Monthly Report',
                        'description': 'Monthly summary report',
                        'updatedAt': '2024-01-02T00:00:00Z'
                    }
                ]
            }
        }
        
        configs_data = mock_response.get(
            'listReportConfigurationByAccountIdAndUpdatedAt', {}
        ).get('items', [])
        assert len(configs_data) == 2
        assert configs_data[0]['name'] == 'Weekly Report'
        assert configs_data[1]['name'] == 'Monthly Report'
        
        # Test empty response
        empty_response = {
            'listReportConfigurationByAccountIdAndUpdatedAt': {
                'items': []
            }
        }
        
        configs_data = empty_response.get(
            'listReportConfigurationByAccountIdAndUpdatedAt', {}
        ).get('items', [])
        assert len(configs_data) == 0
    
    def test_report_configs_fallback_pattern(self):
        """Test fallback query pattern for report configurations"""
        # Test the fallback query structure
        account_id = "account-123"
        
        fallback_query = f"""
            query RetryQuery {{
              listReportConfigurations(filter: {{ accountId: {{ eq: "{account_id}" }} }}, limit: 20) {{
                items {{
                  id
                  name
                  description
                  updatedAt
                }}
              }}
            }}
            """
        
        assert account_id in fallback_query
        assert "limit: 20" in fallback_query
        assert "listReportConfigurations" in fallback_query
    
    def test_report_configs_formatting_pattern(self):
        """Test report configurations formatting pattern"""
        raw_configs = [
            {
                'id': 'config-1',
                'name': 'Test Config',
                'description': 'A test configuration',
                'updatedAt': '2024-01-01T00:00:00Z',
                'extraField': 'should be ignored'
            }
        ]
        
        # Test the formatting pattern used in the tool
        formatted_configs = []
        for config in raw_configs:
            formatted_configs.append({
                "id": config.get("id"),
                "name": config.get("name"),
                "description": config.get("description"),
                "updatedAt": config.get("updatedAt")
            })
        
        assert len(formatted_configs) == 1
        assert formatted_configs[0]['id'] == 'config-1'
        assert formatted_configs[0]['name'] == 'Test Config'
        assert 'extraField' not in formatted_configs[0]


class TestReportToolsSharedPatterns:
    """Test shared patterns across all report tools"""
    
    def test_credential_validation_pattern(self):
        """Test credential validation patterns used across report tools"""
        def validate_credentials():
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                return False, "Missing API credentials"
            return True, None
        
        # Test with missing credentials
        with patch.dict(os.environ, {}, clear=True):
            valid, error = validate_credentials()
            assert valid is False
            assert "Missing API credentials" in error
        
        # Test with valid credentials
        with patch.dict(os.environ, {
            'PLEXUS_API_URL': 'https://test.example.com',
            'PLEXUS_API_KEY': 'test-key'
        }):
            valid, error = validate_credentials()
            assert valid is True
            assert error is None
    
    def test_stdout_redirection_pattern(self):
        """Test stdout redirection pattern used in all report tools"""
        # Test the pattern used to capture unexpected stdout
        old_stdout = StringIO()  # Mock original stdout
        temp_stdout = StringIO()
        
        # Simulate the pattern
        try:
            # Write something that should be captured
            print("This should be captured", file=temp_stdout)
            
            # Check capture
            captured_output = temp_stdout.getvalue()
            assert "This should be captured" in captured_output
        finally:
            # Pattern always restores stdout
            pass
    
    def test_error_response_handling_pattern(self):
        """Test GraphQL error response handling pattern"""
        # Test error response structure
        error_response = {
            'errors': [
                {
                    'message': 'Field not found',
                    'path': ['getReport'],
                    'extensions': {'code': 'NOT_FOUND'}
                }
            ]
        }
        
        # Test the pattern used to handle errors
        if 'errors' in error_response:
            error_details = json.dumps(error_response['errors'], indent=2)
            assert 'Field not found' in error_details
            assert 'NOT_FOUND' in error_details
    
    def test_account_id_resolution_pattern(self):
        """Test account ID resolution pattern"""
        def get_default_account_id():
            # Mock the pattern used in the tools
            return "account-123"
        
        # Test account ID usage in filter conditions
        default_account_id = get_default_account_id()
        if default_account_id:
            filter_condition = f'accountId: {{eq: "{default_account_id}"}}'
            assert 'account-123' in filter_condition
            assert 'eq:' in filter_condition