#!/usr/bin/env python3
"""
Unit tests for scorecard tools
"""
import pytest
import os
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO

pytestmark = pytest.mark.unit

class TestScorecardListTool:
    """Test plexus_scorecards_list tool patterns"""
    
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
        assert 'plexus_scorecards_list' in registered_tools
        assert 'plexus_scorecard_info' in registered_tools
        assert 'run_plexus_evaluation' in registered_tools
        
        # Verify they are callable
        assert callable(registered_tools['plexus_scorecards_list'])
        assert callable(registered_tools['plexus_scorecard_info'])
        assert callable(registered_tools['run_plexus_evaluation'])
    
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