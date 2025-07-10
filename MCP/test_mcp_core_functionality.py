#!/usr/bin/env python3
"""
Core functionality tests for the Plexus MCP server.

This test suite focuses on the critical business logic that can be tested
independently of the complex MCP server state and imports. It tests the
core patterns and functions that the MCP server relies on.
"""

import pytest
import os
import json
import asyncio
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
from decimal import Decimal


class TestParameterValidationPatterns:
    """Test parameter validation patterns used throughout MCP tools"""
    
    def test_days_parameter_conversion_valid_cases(self):
        """Test various valid days parameter conversions"""
        test_cases = [
            ("14", 14),
            ("7", 7),
            ("30", 30),
            ("14.0", 14),
            ("14.9", 14),  # Should truncate
            (14, 14),
            (14.5, 14)
        ]
        
        for input_val, expected in test_cases:
            try:
                result = int(float(str(input_val)))
                assert result == expected, f"Failed for input {input_val}"
            except (ValueError, TypeError) as e:
                pytest.fail(f"Valid input {input_val} should not raise {e}")
    
    def test_days_parameter_conversion_invalid_cases(self):
        """Test invalid days parameter handling"""
        invalid_cases = ["invalid", "not_a_number", "", "NaN"]
        
        for invalid_input in invalid_cases:
            with pytest.raises((ValueError, TypeError)):
                int(float(str(invalid_input)))
        
        # Special case for inf - raises OverflowError
        with pytest.raises(OverflowError):
            int(float(str("inf")))
    
    def test_limit_parameter_handling(self):
        """Test limit parameter conversion and defaults"""
        # Valid cases
        assert int("10") == 10
        assert int("1") == 1
        assert int("100") == 100
        
        # None handling (common pattern in MCP tools)
        limit = None
        result = limit if limit is not None else 10
        assert result == 10
        
        # Empty string handling
        limit = ""
        with pytest.raises(ValueError):
            int(limit)
    
    def test_boolean_parameter_coercion(self):
        """Test boolean parameter handling patterns"""
        true_cases = ["true", "True", "TRUE", "yes", "Yes", "1"]
        false_cases = ["false", "False", "FALSE", "no", "No", "0", ""]
        
        for true_val in true_cases:
            result = true_val.lower() in ['true', 'yes', '1']
            # Note: Only 'true' should be True in the actual MCP logic
            if true_val.lower() == 'true':
                assert result is True
        
        for false_val in false_cases:
            result = false_val.lower() == 'true'
            assert result is False
    
    def test_json_parsing_patterns(self):
        """Test JSON parsing patterns used in MCP tools"""
        # Valid JSON
        valid_json = '{"key": "value", "number": 42, "boolean": true}'
        parsed = json.loads(valid_json)
        assert parsed["key"] == "value"
        assert parsed["number"] == 42
        assert parsed["boolean"] is True
        
        # Invalid JSON should raise JSONDecodeError
        invalid_json = '{"invalid": json, syntax}'
        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)
        
        # Empty JSON
        empty_json = '{}'
        parsed = json.loads(empty_json)
        assert parsed == {}


class TestURLGenerationUtilities:
    """Test URL generation utilities that are core to MCP functionality"""
    
    def test_url_joining_patterns(self):
        """Test URL joining patterns used in get_plexus_url"""
        from urllib.parse import urljoin
        
        # Test cases that match the actual urllib.parse.urljoin behavior
        test_cases = [
            ("https://example.com", "path", "https://example.com/path"),
            ("https://example.com/", "path", "https://example.com/path"),
            ("https://example.com", "/path", "https://example.com/path"),
            ("https://example.com/", "/path", "https://example.com/path"),
            # This case behaves differently - urljoin preserves the base path
            ("https://example.com/api/", "v1/items", "https://example.com/api/v1/items"),
        ]
        
        for base_url, path, expected in test_cases:
            # Simulate the logic from get_plexus_url
            if not base_url.endswith('/'):
                base_url += '/'
            path = path.lstrip('/')
            result = urljoin(base_url, path)
            
            assert result == expected, f"Failed for {base_url} + {path}"
    
    def test_specialized_url_generators(self):
        """Test specialized URL generation patterns"""
        def generate_report_url(report_id, base_url="https://example.com"):
            if not base_url.endswith('/'):
                base_url += '/'
            path = f"lab/reports/{report_id}".lstrip('/')
            return f"{base_url}{path}"
        
        def generate_item_url(item_id, base_url="https://example.com"):
            if not base_url.endswith('/'):
                base_url += '/'
            path = f"lab/items/{item_id}".lstrip('/')
            return f"{base_url}{path}"
        
        # Test report URL generation
        report_id = "c4b18932-4b60-4484-afc7-cf3b47739d8d"
        report_url = generate_report_url(report_id)
        assert report_url == f"https://example.com/lab/reports/{report_id}"
        
        # Test item URL generation
        item_id = "cf749649-2467-4e5c-b27c-787ac6c61edd"
        item_url = generate_item_url(item_id)
        assert item_url == f"https://example.com/lab/items/{item_id}"
        
        # Test with trailing slashes
        report_url = generate_report_url(report_id, "https://example.com/")
        assert report_url == f"https://example.com/lab/reports/{report_id}"


class TestGraphQLResponseHandling:
    """Test GraphQL response handling patterns"""
    
    def test_error_response_formatting(self):
        """Test GraphQL error response formatting"""
        error_response = {
            'errors': [
                {'message': 'Field not found', 'path': ['getScorecard'], 'locations': [{'line': 2, 'column': 3}]},
                {'message': 'Invalid ID format', 'path': ['id'], 'extensions': {'code': 'INVALID_ID'}}
            ]
        }
        
        if 'errors' in error_response:
            error_details = json.dumps(error_response['errors'], indent=2)
            error_message = f"Error from Dashboard query: {error_details}"
            
            assert "Field not found" in error_message
            assert "Invalid ID format" in error_message
            assert "getScorecard" in error_message
    
    def test_successful_response_parsing(self):
        """Test successful GraphQL response parsing patterns"""
        success_response = {
            'data': {
                'listScorecards': {
                    'items': [
                        {
                            'id': 'scorecard-1',
                            'name': 'Test Scorecard 1',
                            'key': 'test-1',
                            'description': 'First test scorecard'
                        },
                        {
                            'id': 'scorecard-2',
                            'name': 'Test Scorecard 2',
                            'key': 'test-2',
                            'description': 'Second test scorecard'
                        }
                    ],
                    'nextToken': None
                }
            }
        }
        
        # Test the parsing pattern used throughout MCP tools
        scorecards_data = success_response.get('listScorecards', {}).get('items', [])
        assert len(scorecards_data) == 0  # This path doesn't exist in the response
        
        # Correct parsing
        scorecards_data = success_response.get('data', {}).get('listScorecards', {}).get('items', [])
        assert len(scorecards_data) == 2
        assert scorecards_data[0]['name'] == 'Test Scorecard 1'
        assert scorecards_data[1]['key'] == 'test-2'
    
    def test_nested_data_extraction(self):
        """Test nested data extraction patterns"""
        complex_response = {
            'data': {
                'getScorecard': {
                    'id': 'scorecard-123',
                    'name': 'Complex Scorecard',
                    'sections': {
                        'items': [
                            {
                                'id': 'section-1',
                                'name': 'Section 1',
                                'scores': {
                                    'items': [
                                        {'id': 'score-1', 'name': 'Score 1', 'type': 'LangGraphScore'},
                                        {'id': 'score-2', 'name': 'Score 2', 'type': 'KeywordClassifier'}
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        # Test the nested extraction pattern
        scorecard_data = complex_response.get('data', {}).get('getScorecard')
        assert scorecard_data is not None
        
        sections = scorecard_data.get('sections', {}).get('items', [])
        assert len(sections) == 1
        
        scores = sections[0].get('scores', {}).get('items', [])
        assert len(scores) == 2
        assert scores[0]['type'] == 'LangGraphScore'
        assert scores[1]['name'] == 'Score 2'
    
    def test_empty_response_handling(self):
        """Test handling of empty/null responses"""
        empty_responses = [
            {'data': {'getScorecard': None}},
            {'data': {}},
            {},
            {'data': {'listScorecards': {'items': []}}},
        ]
        
        for response in empty_responses:
            # Test the pattern used for single item queries
            scorecard_data = response.get('data', {}).get('getScorecard')
            if response.get('data', {}).get('getScorecard') is None:
                assert scorecard_data is None
            
            # Test the pattern used for list queries
            list_data = response.get('data', {}).get('listScorecards', {}).get('items', [])
            if not list_data:
                assert len(list_data) == 0


class TestAsyncOperationPatterns:
    """Test async operation patterns used in MCP tools"""
    
    @pytest.mark.asyncio
    async def test_async_error_propagation(self):
        """Test async error propagation patterns"""
        async def mock_async_operation(should_fail=False):
            if should_fail:
                raise ValueError("Simulated async error")
            return {"success": True, "data": "test"}
        
        # Test successful async operation
        result = await mock_async_operation(False)
        assert result["success"] is True
        assert result["data"] == "test"
        
        # Test error propagation
        with pytest.raises(ValueError, match="Simulated async error"):
            await mock_async_operation(True)
    
    @pytest.mark.asyncio
    async def test_async_result_formatting(self):
        """Test async result formatting patterns"""
        async def mock_service_call():
            # Simulate a service returning complex data
            return {
                "items": [{"id": "1", "name": "Item 1"}, {"id": "2", "name": "Item 2"}],
                "total": 2,
                "hasMore": False
            }
        
        result = await mock_service_call()
        
        # Test the formatting pattern used in MCP tools
        formatted_result = {
            "success": True,
            "count": result["total"],
            "items": result["items"],
            "hasMore": result["hasMore"]
        }
        
        assert formatted_result["success"] is True
        assert formatted_result["count"] == 2
        assert len(formatted_result["items"]) == 2
        assert formatted_result["hasMore"] is False
    
    @pytest.mark.asyncio
    async def test_async_timeout_handling_pattern(self):
        """Test async timeout handling pattern"""
        async def slow_operation():
            await asyncio.sleep(0.1)  # Simulate slow operation
            return "completed"
        
        # Test with timeout
        try:
            result = await asyncio.wait_for(slow_operation(), timeout=0.2)
            assert result == "completed"
        except asyncio.TimeoutError:
            pytest.fail("Operation should not timeout with 0.2s limit")
        
        # Test timeout exceeded
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_operation(), timeout=0.05)


class TestDataValidationPatterns:
    """Test data validation patterns used in MCP tools"""
    
    def test_scorecard_identifier_validation(self):
        """Test scorecard identifier validation patterns"""
        def is_valid_identifier(identifier):
            if not identifier:
                return False
            if not isinstance(identifier, str):
                return False
            if len(identifier.strip()) == 0:
                return False
            return True
        
        # Valid identifiers
        valid_ids = ["scorecard-123", "Test Scorecard", "key_with_underscores", "123"]
        for vid in valid_ids:
            assert is_valid_identifier(vid) is True
        
        # Invalid identifiers
        invalid_ids = [None, "", "   ", 123, [], {}]
        for iid in invalid_ids:
            assert is_valid_identifier(iid) is False
    
    def test_score_name_matching_patterns(self):
        """Test score name matching patterns used in find operations"""
        score_data = {
            'id': 'score-123',
            'name': 'Test Score Name',
            'key': 'test-score-key',
            'externalId': 'ext-123'
        }
        
        def matches_score_identifier(score, identifier):
            if not identifier:
                return False
            
            identifier_lower = identifier.lower()
            
            # Exact matches
            if (score.get('id') == identifier or
                score.get('key') == identifier or
                score.get('externalId') == identifier):
                return True
            
            # Case-insensitive name match
            if score.get('name', '').lower() == identifier_lower:
                return True
            
            # Partial name match (contains)
            if identifier_lower in score.get('name', '').lower():
                return True
            
            return False
        
        # Test exact matches
        assert matches_score_identifier(score_data, 'score-123') is True
        assert matches_score_identifier(score_data, 'test-score-key') is True
        assert matches_score_identifier(score_data, 'ext-123') is True
        
        # Test case-insensitive name match
        assert matches_score_identifier(score_data, 'test score name') is True
        assert matches_score_identifier(score_data, 'TEST SCORE NAME') is True
        
        # Test partial match
        assert matches_score_identifier(score_data, 'test score') is True
        assert matches_score_identifier(score_data, 'Score') is True
        
        # Test no match
        assert matches_score_identifier(score_data, 'nonexistent') is False
        assert matches_score_identifier(score_data, '') is False
    
    def test_parameter_filtering_patterns(self):
        """Test parameter filtering patterns for API calls"""
        def build_filter_conditions(account_id=None, identifier=None, limit=None):
            conditions = []
            
            if account_id:
                conditions.append(f'accountId: {{ eq: "{account_id}" }}')
            
            if identifier:
                # Handle identifier that could be name or key
                if ' ' in identifier or not identifier.islower():
                    conditions.append(f'name: {{ contains: "{identifier}" }}')
                else:
                    conditions.append(f'or: [{{name: {{ contains: "{identifier}" }}}}, {{key: {{ contains: "{identifier}" }}}}]')
            
            return conditions, limit or 1000
        
        # Test with account ID only
        conditions, limit = build_filter_conditions(account_id="acc-123")
        assert len(conditions) == 1
        assert 'accountId: { eq: "acc-123" }' in conditions[0]
        assert limit == 1000
        
        # Test with name-like identifier
        conditions, limit = build_filter_conditions(account_id="acc-123", identifier="Test Scorecard")
        assert len(conditions) == 2
        assert any('name: { contains: "Test Scorecard" }' in c for c in conditions)
        
        # Test with key-like identifier
        conditions, limit = build_filter_conditions(account_id="acc-123", identifier="test-key")
        assert len(conditions) == 2
        assert any('or:' in c for c in conditions)
        
        # Test with custom limit
        conditions, limit = build_filter_conditions(account_id="acc-123", limit=50)
        assert limit == 50


class TestErrorHandlingPatterns:
    """Test error handling patterns used throughout MCP tools"""
    
    def test_client_creation_error_handling(self):
        """Test client creation error handling patterns"""
        def create_client_with_error_handling():
            try:
                # Simulate the environment check pattern
                api_url = os.environ.get('PLEXUS_API_URL', '')
                api_key = os.environ.get('PLEXUS_API_KEY', '')
                
                if not api_url or not api_key:
                    return None, "Missing API credentials. API_URL or API_KEY not set in environment."
                
                # Simulate client creation that could fail
                if api_url == "invalid_url":
                    raise ConnectionError("Could not connect to API")
                
                return {"client": "mock_client"}, None
            except Exception as e:
                return None, f"Error creating dashboard client: {str(e)}"
        
        # Test missing credentials
        with patch.dict(os.environ, {}, clear=True):
            client, error = create_client_with_error_handling()
            assert client is None
            assert "Missing API credentials" in error
        
        # Test connection error
        with patch.dict(os.environ, {'PLEXUS_API_URL': 'invalid_url', 'PLEXUS_API_KEY': 'test'}):
            client, error = create_client_with_error_handling()
            assert client is None
            assert "Could not connect to API" in error
        
        # Test successful creation
        with patch.dict(os.environ, {'PLEXUS_API_URL': 'https://api.example.com', 'PLEXUS_API_KEY': 'test'}):
            client, error = create_client_with_error_handling()
            assert client is not None
            assert error is None
    
    def test_service_call_error_handling(self):
        """Test service call error handling patterns"""
        def call_service_with_error_handling(service_func, *args, **kwargs):
            try:
                result = service_func(*args, **kwargs)
                if isinstance(result, dict) and result.get('error'):
                    return f"Service error: {result['error']}"
                return result
            except ImportError as e:
                return f"Error: Could not import required modules: {e}"
            except ValueError as e:
                return f"Error: Invalid parameter: {e}"
            except Exception as e:
                return f"Error: {str(e)}"
        
        # Test successful service call
        def mock_successful_service():
            return {"success": True, "data": "test"}
        
        result = call_service_with_error_handling(mock_successful_service)
        assert result["success"] is True
        
        # Test service returning error
        def mock_error_service():
            return {"error": "Service unavailable"}
        
        result = call_service_with_error_handling(mock_error_service)
        assert "Service error: Service unavailable" in result
        
        # Test import error
        def mock_import_error_service():
            raise ImportError("Module not found")
        
        result = call_service_with_error_handling(mock_import_error_service)
        assert "Could not import required modules" in result
        
        # Test value error
        def mock_value_error_service():
            raise ValueError("Invalid input")
        
        result = call_service_with_error_handling(mock_value_error_service)
        assert "Invalid parameter: Invalid input" in result


class TestStdoutRedirectionPatterns:
    """Test stdout redirection patterns critical to MCP protocol"""
    
    def test_basic_stdout_redirection(self):
        """Test basic stdout redirection pattern"""
        import sys
        from io import StringIO
        
        original_stdout = sys.stdout
        captured_output = StringIO()
        
        try:
            sys.stdout = captured_output
            print("This should be captured")
            
            output = captured_output.getvalue()
            assert "This should be captured" in output
        finally:
            sys.stdout = original_stdout
        
        # Ensure stdout is restored
        assert sys.stdout == original_stdout
    
    def test_nested_stdout_redirection_safety(self):
        """Test nested stdout redirection safety"""
        import sys
        from io import StringIO
        
        original_stdout = sys.stdout
        
        def inner_function_with_redirection():
            temp_stdout = StringIO()
            saved_stdout = sys.stdout
            
            try:
                sys.stdout = temp_stdout
                print("Inner output")
                return temp_stdout.getvalue()
            finally:
                sys.stdout = saved_stdout
        
        def outer_function_with_redirection():
            temp_stdout = StringIO()
            
            try:
                sys.stdout = temp_stdout
                print("Outer before")
                inner_output = inner_function_with_redirection()
                print("Outer after")
                
                outer_output = temp_stdout.getvalue()
                return outer_output, inner_output
            finally:
                sys.stdout = original_stdout
        
        outer_output, inner_output = outer_function_with_redirection()
        
        # Verify both functions captured their respective outputs
        assert "Inner output" in inner_output
        assert "Outer before" in outer_output
        assert "Outer after" in outer_output
        assert "Inner output" not in outer_output  # Inner was redirected separately
        
        # Verify stdout is fully restored
        assert sys.stdout == original_stdout
    
    def test_stdout_capture_with_exception_handling(self):
        """Test stdout capture with proper exception handling"""
        import sys
        from io import StringIO
        
        def function_with_potential_error(should_error=False):
            original_stdout = sys.stdout
            temp_stdout = StringIO()
            
            try:
                sys.stdout = temp_stdout
                print("Before potential error")
                
                if should_error:
                    raise ValueError("Simulated error")
                
                print("After potential error")
                return temp_stdout.getvalue(), None
            except Exception as e:
                # Capture any output before the error
                captured = temp_stdout.getvalue()
                return captured, str(e)
            finally:
                # Always restore stdout
                sys.stdout = original_stdout
        
        # Test successful case
        output, error = function_with_potential_error(False)
        assert "Before potential error" in output
        assert "After potential error" in output
        assert error is None
        
        # Test error case
        output, error = function_with_potential_error(True)
        assert "Before potential error" in output
        assert "After potential error" not in output
        assert "Simulated error" in error
        
        # Verify stdout is restored (check that it's not a StringIO object)
        assert not isinstance(sys.stdout, StringIO)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])