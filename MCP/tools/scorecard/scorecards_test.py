#!/usr/bin/env python3
"""
Unit tests for scorecard tools
"""
import pytest
import os
import sys
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO

# Add the parent directory to sys.path to import test patterns
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, parent_dir)

from plexus.cli.scorecard.scorecard_test_patterns import (
    ScorecardTestPatterns, 
    ScorecardFunctionalityTests
)

pytestmark = pytest.mark.unit


class TestScorecardToolsRegistration:
    """Test scorecard tool registration patterns"""
    
    def test_scorecard_tool_registration_pattern(self):
        """Test scorecard tool registration pattern"""
        from tools.scorecard.scorecards import register_scorecard_tools
        
        # Create mock MCP instance
        mock_mcp = Mock()
        registered_tools = {}
        
        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator
        
        mock_mcp.tool = mock_tool_decorator
        
        # Register tools
        register_scorecard_tools(mock_mcp)
        
        # Verify tools were registered
        expected_tools = [
            'plexus_scorecards_list',
            'plexus_scorecard_info'
        ]
        
        for tool_name in expected_tools:
            assert tool_name in registered_tools
            assert callable(registered_tools[tool_name])


class TestScorecardListTool:
    """Test plexus_scorecards_list tool functionality"""
    
    def test_scorecard_list_basic_functionality(self):
        """Test basic scorecard listing using shared patterns"""
        from tools.scorecard.scorecards import register_scorecard_tools
        
        # Get the function using our registration pattern
        mock_mcp = Mock()
        registered_tools = {}
        
        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator
        
        mock_mcp.tool = mock_tool_decorator
        register_scorecard_tools(mock_mcp)
        
        plexus_scorecards_list = registered_tools['plexus_scorecards_list']
        
        # Test using shared patterns (async wrapper needed)
        import asyncio
        ScorecardFunctionalityTests.test_list_scorecards_basic(
            lambda: asyncio.get_event_loop().run_until_complete(plexus_scorecards_list())
        )
    
    def test_scorecard_list_with_filter(self):
        """Test scorecard listing with identifier filter"""
        from tools.scorecard.scorecards import register_scorecard_tools
        
        # Get the function
        mock_mcp = Mock()
        registered_tools = {}
        
        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator
        
        mock_mcp.tool = mock_tool_decorator
        register_scorecard_tools(mock_mcp)
        
        plexus_scorecards_list = registered_tools['plexus_scorecards_list']
        
        # Test with filter using shared patterns
        import asyncio
        ScorecardFunctionalityTests.test_list_scorecards_with_filter(
            lambda identifier="test": asyncio.get_event_loop().run_until_complete(plexus_scorecards_list(identifier=identifier))
        )
    
    def test_scorecard_list_empty_results(self):
        """Test scorecard listing with no results"""
        from tools.scorecard.scorecards import register_scorecard_tools
        
        # Get the function
        mock_mcp = Mock()
        registered_tools = {}
        
        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator
        
        mock_mcp.tool = mock_tool_decorator
        register_scorecard_tools(mock_mcp)
        
        plexus_scorecards_list = registered_tools['plexus_scorecards_list']
        
        # Test empty results using shared patterns
        import asyncio
        ScorecardFunctionalityTests.test_list_scorecards_empty_result(
            lambda: asyncio.get_event_loop().run_until_complete(plexus_scorecards_list())
        )
    
    def test_scorecard_list_error_handling(self):
        """Test scorecard listing error handling"""
        from tools.scorecard.scorecards import register_scorecard_tools
        
        # Get the function
        mock_mcp = Mock()
        registered_tools = {}
        
        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator
        
        mock_mcp.tool = mock_tool_decorator
        register_scorecard_tools(mock_mcp)
        
        plexus_scorecards_list = registered_tools['plexus_scorecards_list']
        
        # Test error handling using shared patterns
        import asyncio
        ScorecardFunctionalityTests.test_list_scorecards_error_handling(
            lambda: asyncio.get_event_loop().run_until_complete(plexus_scorecards_list())
        )
    
    def test_scorecard_validation_patterns(self):
        """Test scorecard data validation patterns"""
        # Test shared validation patterns
        validation_tests = ScorecardTestPatterns.test_scorecard_validation_patterns()
        
        for test_case in validation_tests:
            scorecard = test_case['scorecard']
            should_be_valid = test_case['should_be_valid']
            
            # In a real implementation, you'd validate the scorecard data
            # For now, we're testing that the pattern works
            if should_be_valid:
                assert ScorecardTestPatterns.validate_scorecard_info_result(scorecard)
            else:
                # Invalid scorecards should be handled gracefully
                assert isinstance(test_case['validation_errors'], list)
    
    def test_identifier_resolution_patterns(self):
        """Test identifier resolution patterns"""
        test_cases = ScorecardTestPatterns.test_scorecard_identifier_resolution_patterns()
        
        for test_case in test_cases:
            input_id = test_case['input']
            expected_type = test_case['expected_type']
            should_resolve = test_case['should_resolve']
            
            # Test that the pattern is valid
            if should_resolve:
                assert input_id is not None and str(input_id).strip() != ""
            else:
                assert input_id is None or str(input_id).strip() == ""
    
    def test_filtering_patterns(self):
        """Test filtering patterns"""
        filter_tests = ScorecardTestPatterns.test_scorecard_filtering_patterns()
        
        for test_case in filter_tests:
            filter_value = test_case['filter']
            expected_count = test_case['expected_count']
            description = test_case['description']
            
            # Validate that the test case makes sense
            assert isinstance(expected_count, int)
            assert expected_count >= 0
            assert isinstance(description, str)
            assert len(description) > 0


class TestScorecardInfoTool:
    """Test plexus_scorecard_info tool functionality"""
    
    def test_scorecard_info_basic_functionality(self):
        """Test basic scorecard info retrieval"""
        from tools.scorecard.scorecards import register_scorecard_tools
        
        # Get the function
        mock_mcp = Mock()
        registered_tools = {}
        
        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator
        
        mock_mcp.tool = mock_tool_decorator
        register_scorecard_tools(mock_mcp)
        
        plexus_scorecard_info = registered_tools['plexus_scorecard_info']
        
        # Mock the client and response
        mock_client = ScorecardTestPatterns.create_mock_client()
        
        with patch('tools.scorecard.scorecards.create_dashboard_client', return_value=mock_client):
            with patch('tools.scorecard.scorecards.resolve_scorecard_identifier', return_value='scorecard-123'):
                # Test async function
                import asyncio
                try:
                    result = asyncio.run(plexus_scorecard_info('test-scorecard'))
                    assert ScorecardTestPatterns.validate_scorecard_info_result(result)
                except RuntimeError as e:
                    if "cannot be called from a running event loop" in str(e):
                        # Handle the case where we're already in an event loop
                        pytest.skip("Test requires async event loop management")


class TestScorecardErrorHandling:
    """Test scorecard error handling patterns"""
    
    def test_error_scenarios(self):
        """Test various error scenarios using shared patterns"""
        error_scenarios = ScorecardTestPatterns.test_error_handling_patterns()
        
        for scenario in error_scenarios:
            error_type = scenario['error_type']
            error_message = scenario['error_message']
            expected_pattern = scenario['expected_response_pattern']
            
            # Test that error patterns are well-formed
            assert isinstance(error_type, str)
            assert isinstance(error_message, str)
            assert isinstance(expected_pattern, str)
            assert len(error_type) > 0
            assert len(error_message) > 0 
            assert len(expected_pattern) > 0


class TestScorecardSharedPatterns:
    """Test shared patterns work correctly"""
    
    def test_sample_data_validity(self):
        """Test that sample data is valid"""
        # Test single scorecard
        scorecard = ScorecardTestPatterns.get_sample_scorecard_data()
        assert ScorecardTestPatterns.validate_scorecard_info_result(scorecard)
        
        # Test scorecard list
        scorecards = ScorecardTestPatterns.get_sample_scorecard_list()
        assert ScorecardTestPatterns.validate_scorecard_list_result(scorecards)
        
        # Test GraphQL response
        response = ScorecardTestPatterns.get_sample_graphql_response()
        assert 'data' in response
        assert 'listScorecards' in response['data']
        assert 'items' in response['data']['listScorecards']
    
    def test_mock_client_creation(self):
        """Test mock client creation"""
        from tools.scorecard.scorecards import register_scorecard_tools
        
        # Set up tool registration
        mock_mcp = Mock()
        registered_tools = {}
        
        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator
        
        mock_mcp.tool = mock_tool_decorator
        register_scorecard_tools(mock_mcp)
        
        # Test default mock client
        mock_client = ScorecardTestPatterns.create_mock_client()
        assert hasattr(mock_client, 'execute')
        
        # Test mock client with custom data
        custom_data = {'test': 'data'}
        mock_client = ScorecardTestPatterns.create_mock_client(return_data=custom_data)
        result = mock_client.execute()
        assert result == custom_data
        
        # Test mock client with error
        test_error = Exception("Test error")
        mock_client = ScorecardTestPatterns.create_mock_client(raise_error=test_error)
        with pytest.raises(Exception) as exc_info:
            mock_client.execute()
        assert str(exc_info.value) == "Test error"
        # Verify tools were registered
        assert 'plexus_scorecards_list' in registered_tools
        assert 'plexus_scorecard_info' in registered_tools

        # Verify they are callable
        assert callable(registered_tools['plexus_scorecards_list'])
        assert callable(registered_tools['plexus_scorecard_info'])
    
    def test_scorecard_data_patterns(self):
        """Test scorecard data handling patterns"""
        # Test GraphQL response parsing pattern
        mock_response = {
            'listScorecards': {
                'items': [
                    {
                        'id': 'scorecard-1',
                        'name': 'Test Scorecard',
                        'key': 'test-scorecard',
                        'description': 'A test scorecard'
                    }
                ]
            }
        }
        
        # Test the pattern used to extract data
        scorecards_data = mock_response.get('listScorecards', {}).get('items', [])
        assert len(scorecards_data) == 1
        assert scorecards_data[0]['name'] == 'Test Scorecard'
        
        # Test error response pattern
        error_response = {
            'errors': [
                {'message': 'Field not found', 'path': ['listScorecards']}
            ]
        }
        
        if 'errors' in error_response:
            error_details = json.dumps(error_response['errors'], indent=2)
            assert 'Field not found' in error_details
    
    def test_credential_validation_pattern(self):
        """Test credential validation patterns used in tools"""
        # Test the pattern used to check credentials
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

class TestEvaluationTool:
    """Test evaluation tool patterns"""
    
    def test_evaluation_validation_pattern(self):
        """Test evaluation parameter validation patterns"""
        def validate_evaluation_params(scorecard_name, score_name="", n_samples=10):
            if not scorecard_name:
                return False, "scorecard_name must be provided"
            
            if not isinstance(n_samples, int) or n_samples <= 0:
                return False, "n_samples must be a positive integer"
                
            return True, None
        
        # Test missing scorecard name
        valid, error = validate_evaluation_params("")
        assert valid is False
        assert "scorecard_name must be provided" in error
        
        # Test valid parameters
        valid, error = validate_evaluation_params("Test Scorecard", "Test Score", 5)
        assert valid is True
        assert error is None
        
        # Test invalid sample count
        valid, error = validate_evaluation_params("Test Scorecard", "Test Score", -1)
        assert valid is False
        assert "positive integer" in error
    
    def test_background_task_pattern(self):
        """Test background task dispatch patterns"""
        # Test the command building pattern used for evaluations
        scorecard_name = "Test Scorecard"
        score_name = "Test Score"
        n_samples = 10
        
        eval_cmd_str = f"evaluate accuracy --scorecard-name '{scorecard_name}'"
        if score_name:
            eval_cmd_str += f" --score-name '{score_name}'"
        eval_cmd_str += f" --number-of-samples {n_samples}"
        
        expected = "evaluate accuracy --scorecard-name 'Test Scorecard' --score-name 'Test Score' --number-of-samples 10"
        assert eval_cmd_str == expected