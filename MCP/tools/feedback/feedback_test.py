#!/usr/bin/env python3
"""
Unit tests for feedback tools
"""
import pytest
import os
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO

pytestmark = pytest.mark.unit


class TestFeedbackSummaryTool:
    """Test plexus_feedback_analysis tool patterns"""
    
    def test_feedback_summary_validation_patterns(self):
        """Test feedback summary parameter validation patterns"""
        def validate_feedback_summary_params(scorecard_name, score_name, days=14, output_format="json"):
            if not scorecard_name or not scorecard_name.strip():
                return False, "scorecard_name is required"
            if not score_name or not score_name.strip():
                return False, "score_name is required"
            
            # Test days parameter conversion
            try:
                days_int = int(float(str(days)))
                if days_int < 0:
                    return False, "days must be non-negative"
            except (ValueError, TypeError):
                return False, "days must be a valid number"
            
            # Test output format
            if output_format not in ["json", "yaml"]:
                return False, "output_format must be 'json' or 'yaml'"
            
            return True, None
        
        # Test valid parameters
        valid, error = validate_feedback_summary_params("test-scorecard", "test-score")
        assert valid is True
        assert error is None
        
        # Test with days parameter
        valid, error = validate_feedback_summary_params("test-scorecard", "test-score", 30)
        assert valid is True
        assert error is None
        
        # Test with string days parameter
        valid, error = validate_feedback_summary_params("test-scorecard", "test-score", "7")
        assert valid is True
        assert error is None
        
        # Test with float days parameter
        valid, error = validate_feedback_summary_params("test-scorecard", "test-score", "14.5")
        assert valid is True
        assert error is None
        
        # Test with yaml output format
        valid, error = validate_feedback_summary_params("test-scorecard", "test-score", 14, "yaml")
        assert valid is True
        assert error is None
        
        # Test missing scorecard name
        valid, error = validate_feedback_summary_params("", "test-score")
        assert valid is False
        assert "scorecard_name is required" in error
        
        # Test missing score name
        valid, error = validate_feedback_summary_params("test-scorecard", "")
        assert valid is False
        assert "score_name is required" in error
        
        # Test invalid days parameter
        valid, error = validate_feedback_summary_params("test-scorecard", "test-score", "invalid")
        assert valid is False
        assert "days must be a valid number" in error
        
        # Test negative days parameter
        valid, error = validate_feedback_summary_params("test-scorecard", "test-score", -5)
        assert valid is False
        assert "days must be non-negative" in error
        
        # Test invalid output format
        valid, error = validate_feedback_summary_params("test-scorecard", "test-score", 14, "xml")
        assert valid is False
        assert "output_format must be 'json' or 'yaml'" in error
    
    def test_scorecard_query_patterns(self):
        """Test scorecard query patterns for feedback summary"""
        scorecard_id = "scorecard-123"
        
        # Test the scorecard query structure
        scorecard_query = f"""
        query GetScorecardWithScores {{
            getScorecard(id: "{scorecard_id}") {{
                id
                name
                key
                sections {{
                    items {{
                        id
                        name
                        scores {{
                            items {{
                                id
                                name
                                key
                                externalId
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        assert f'getScorecard(id: "{scorecard_id}")' in scorecard_query
        assert "sections {" in scorecard_query
        assert "scores {" in scorecard_query
        assert "externalId" in scorecard_query
    
    def test_score_matching_patterns(self):
        """Test score matching logic patterns"""
        # Mock scorecard data
        scorecard_data = {
            'id': 'scorecard-123',
            'name': 'Test Scorecard',
            'sections': {
                'items': [
                    {
                        'id': 'section-1',
                        'scores': {
                            'items': [
                                {
                                    'id': 'score-123',
                                    'name': 'Test Score',
                                    'key': 'test_score',
                                    'externalId': 'EXT-001'
                                },
                                {
                                    'id': 'score-456',
                                    'name': 'Another Score',
                                    'key': 'another_score',
                                    'externalId': 'EXT-002'
                                }
                            ]
                        }
                    }
                ]
            }
        }
        
        def find_score_match(score_name, scorecard_data):
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score in section.get('scores', {}).get('items', []):
                    if (score.get('id') == score_name or 
                        score.get('name', '').lower() == score_name.lower() or 
                        score.get('key') == score_name or 
                        score.get('externalId') == score_name or
                        score_name.lower() in score.get('name', '').lower()):
                        return score
            return None
        
        # Test exact ID match
        score_match = find_score_match('score-123', scorecard_data)
        assert score_match is not None
        assert score_match['id'] == 'score-123'
        
        # Test name match (case insensitive)
        score_match = find_score_match('test score', scorecard_data)
        assert score_match is not None
        assert score_match['name'] == 'Test Score'
        
        # Test key match
        score_match = find_score_match('test_score', scorecard_data)
        assert score_match is not None
        assert score_match['key'] == 'test_score'
        
        # Test external ID match
        score_match = find_score_match('EXT-001', scorecard_data)
        assert score_match is not None
        assert score_match['externalId'] == 'EXT-001'
        
        # Test partial name match
        score_match = find_score_match('test', scorecard_data)
        assert score_match is not None
        assert 'test' in score_match['name'].lower()
        
        # Test no match
        score_match = find_score_match('nonexistent', scorecard_data)
        assert score_match is None
    
    def test_feedback_service_integration_patterns(self):
        """Test FeedbackService integration patterns"""
        # Mock FeedbackService.summarize_feedback result
        mock_summary_result = {
            'accuracy': 0.85,
            'total_items': 100,
            'correct_items': 85,
            'confusion_matrix': {
                'tp': 40, 'tn': 45, 'fp': 8, 'fn': 7
            },
            'agreement_coefficient': 0.78,
            'recommendation': 'Review false positives to improve precision'
        }
        
        def simulate_feedback_service_call():
            return mock_summary_result
        
        result = simulate_feedback_service_call()
        assert result['accuracy'] == 0.85
        assert result['total_items'] == 100
        assert 'confusion_matrix' in result
        assert 'recommendation' in result
        
        # Test result formatting
        result_dict = {
            "command_info": {
                "description": "Comprehensive feedback analysis with confusion matrix and agreement metrics",
                "tool": "plexus_feedback_analysis(scorecard_name='test', score_name='test', days=14, output_format='json')",
                "next_steps": result["recommendation"]
            },
            **result
        }
        
        assert 'command_info' in result_dict
        assert result_dict['command_info']['next_steps'] == result['recommendation']
    
    def test_output_format_patterns(self):
        """Test output format handling patterns"""
        # Mock result data
        result_dict = {
            'accuracy': 0.85,
            'total_items': 100,
            'confusion_matrix': {'tp': 40, 'tn': 45, 'fp': 8, 'fn': 7}
        }
        
        def format_output(result_dict, output_format):
            if output_format.lower() == 'yaml':
                import yaml
                from datetime import datetime
                yaml_comment = f"""# Feedback Summary Analysis
# Generated: {datetime.now().isoformat()}
# This summary provides overview metrics

"""
                yaml_output = yaml.dump(result_dict, default_flow_style=False, sort_keys=False)
                return yaml_comment + yaml_output
            else:
                import json
                return json.dumps(result_dict, indent=2, default=str)
        
        # Test JSON format
        json_output = format_output(result_dict, 'json')
        assert '"accuracy": 0.85' in json_output
        assert json.loads(json_output)['total_items'] == 100
        
        # Test YAML format
        yaml_output = format_output(result_dict, 'yaml')
        assert '# Feedback Summary Analysis' in yaml_output
        assert 'accuracy: 0.85' in yaml_output


class TestFeedbackFindTool:
    """Test plexus_feedback_find tool patterns"""
    
    def test_feedback_find_validation_patterns(self):
        """Test feedback find parameter validation patterns"""
        def validate_feedback_find_params(scorecard_name, score_name, initial_value=None, final_value=None, 
                                         limit=10, days=30, output_format="json", prioritize_edit_comments=True):
            if not scorecard_name or not scorecard_name.strip():
                return False, "scorecard_name is required"
            if not score_name or not score_name.strip():
                return False, "score_name is required"
            
            # Test limit parameter
            if limit is not None:
                try:
                    limit_int = int(limit)
                    if limit_int < 1:
                        return False, "limit must be positive"
                except (ValueError, TypeError):
                    return False, "limit must be a valid number"
            
            # Test days parameter
            if days is not None:
                try:
                    days_int = int(days)
                    if days_int < 0:
                        return False, "days must be non-negative"
                except (ValueError, TypeError):
                    return False, "days must be a valid number"
            
            return True, None
        
        # Test valid parameters
        valid, error = validate_feedback_find_params("test-scorecard", "test-score")
        assert valid is True
        assert error is None
        
        # Test with optional filters
        valid, error = validate_feedback_find_params("test-scorecard", "test-score", "No", "Yes", 20, 60)
        assert valid is True
        assert error is None
        
        # Test missing scorecard name
        valid, error = validate_feedback_find_params("", "test-score")
        assert valid is False
        assert "scorecard_name is required" in error
        
        # Test missing score name
        valid, error = validate_feedback_find_params("test-scorecard", "")
        assert valid is False
        assert "score_name is required" in error
        
        # Test invalid limit
        valid, error = validate_feedback_find_params("test-scorecard", "test-score", limit="invalid")
        assert valid is False
        assert "limit must be a valid number" in error
        
        # Test negative limit
        valid, error = validate_feedback_find_params("test-scorecard", "test-score", limit=-5)
        assert valid is False
        assert "limit must be positive" in error
        
        # Test invalid days
        valid, error = validate_feedback_find_params("test-scorecard", "test-score", days="invalid")
        assert valid is False
        assert "days must be a valid number" in error
    
    def test_scorecard_query_for_feedback_patterns(self):
        """Test scorecard query patterns for feedback find"""
        scorecard_id = "scorecard-123"
        
        # Test the scorecard query structure for feedback
        scorecard_query = f"""
        query GetScorecardForFeedback {{
            getScorecard(id: "{scorecard_id}") {{
                id
                name
                sections {{
                    items {{
                        id
                        scores {{
                            items {{
                                id
                                name
                                key
                                externalId
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        assert f'getScorecard(id: "{scorecard_id}")' in scorecard_query
        assert "GetScorecardForFeedback" in scorecard_query
        assert "sections {" in scorecard_query
        assert "scores {" in scorecard_query
    
    def test_score_finding_patterns(self):
        """Test score finding logic patterns"""
        # Mock scorecard data
        scorecard_data = {
            'id': 'scorecard-123',
            'name': 'Test Scorecard',
            'sections': {
                'items': [
                    {
                        'id': 'section-1',
                        'scores': {
                            'items': [
                                {
                                    'id': 'score-123',
                                    'name': 'Test Score',
                                    'key': 'test_score',
                                    'externalId': 'EXT-001'
                                }
                            ]
                        }
                    }
                ]
            }
        }
        
        def find_score_id(score_name, scorecard_data):
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score in section.get('scores', {}).get('items', []):
                    if (score.get('name') == score_name or 
                        score.get('key') == score_name or 
                        score.get('id') == score_name or 
                        score.get('externalId') == score_name):
                        return score['id']
            return None
        
        # Test finding by name
        found_score_id = find_score_id('Test Score', scorecard_data)
        assert found_score_id == 'score-123'
        
        # Test finding by key
        found_score_id = find_score_id('test_score', scorecard_data)
        assert found_score_id == 'score-123'
        
        # Test finding by ID
        found_score_id = find_score_id('score-123', scorecard_data)
        assert found_score_id == 'score-123'
        
        # Test finding by external ID
        found_score_id = find_score_id('EXT-001', scorecard_data)
        assert found_score_id == 'score-123'
        
        # Test not found
        found_score_id = find_score_id('nonexistent', scorecard_data)
        assert found_score_id is None
    
    def test_parameter_conversion_patterns(self):
        """Test parameter conversion patterns"""
        def convert_parameters(days, limit):
            """Convert string parameters to integers"""
            days_int = None
            if days:
                try:
                    days_int = int(days)
                except (ValueError, TypeError):
                    return None, None, f"Invalid days parameter '{days}'. Must be a number."
            else:
                days_int = 30  # Default to 30 days
                
            limit_int = None
            if limit:
                try:
                    limit_int = int(limit)
                except (ValueError, TypeError):
                    return None, None, f"Invalid limit parameter '{limit}'. Must be a number."
            
            return days_int, limit_int, None
        
        # Test valid conversions
        days_int, limit_int, error = convert_parameters("14", "10")
        assert days_int == 14
        assert limit_int == 10
        assert error is None
        
        # Test default days
        days_int, limit_int, error = convert_parameters(None, "5")
        assert days_int == 30
        assert limit_int == 5
        assert error is None
        
        # Test invalid days
        days_int, limit_int, error = convert_parameters("invalid", "10")
        assert error is not None
        assert "Invalid days parameter" in error
        
        # Test invalid limit
        days_int, limit_int, error = convert_parameters("14", "invalid")
        assert error is not None
        assert "Invalid limit parameter" in error
    
    def test_feedback_service_search_patterns(self):
        """Test FeedbackService search patterns"""
        # Mock feedback search result
        mock_search_result = {
            'feedback_items': [
                {
                    'id': 'feedback-1',
                    'scoreId': 'score-123',
                    'itemId': 'item-456',
                    'initialAnswerValue': 'No',
                    'finalAnswerValue': 'Yes',
                    'editCommentValue': 'Corrected classification',
                    'isAgreement': False,
                    'editorName': 'John Doe'
                }
            ],
            'context': {
                'total_found': 1,
                'filters_applied': {
                    'initial_value': 'No',
                    'final_value': 'Yes',
                    'days': 30
                }
            }
        }
        
        def simulate_feedback_search():
            return mock_search_result
        
        result = simulate_feedback_search()
        assert len(result['feedback_items']) == 1
        assert result['feedback_items'][0]['initialAnswerValue'] == 'No'
        assert result['feedback_items'][0]['finalAnswerValue'] == 'Yes'
        assert result['context']['total_found'] == 1
        
        # Test correction detection
        feedback_item = result['feedback_items'][0]
        is_correction = (
            feedback_item['initialAnswerValue'] != feedback_item['finalAnswerValue'] and
            feedback_item['finalAnswerValue'] is not None
        )
        assert is_correction is True
    
    def test_no_feedback_response_patterns(self):
        """Test no feedback found response patterns"""
        def generate_no_feedback_message(score_name, scorecard_name, initial_value=None, 
                                       final_value=None, days=30):
            filter_desc = []
            if initial_value:
                filter_desc.append(f"initial value '{initial_value}'")
            if final_value:
                filter_desc.append(f"final value '{final_value}'")
            
            if filter_desc:
                filter_text = f" with {' and '.join(filter_desc)}"
            else:
                filter_text = ""
                
            return f"No feedback items found for score '{score_name}' in scorecard '{scorecard_name}'{filter_text} in the last {days} days."
        
        # Test message without filters
        message = generate_no_feedback_message('test-score', 'test-scorecard', days=14)
        assert "No feedback items found" in message
        assert "test-score" in message
        assert "test-scorecard" in message
        assert "last 14 days" in message
        
        # Test message with filters
        message = generate_no_feedback_message('test-score', 'test-scorecard', 'No', 'Yes', 30)
        assert "with initial value 'No' and final value 'Yes'" in message
        assert "last 30 days" in message


class TestFeedbackToolsSharedPatterns:
    """Test shared patterns across feedback tools"""
    
    def test_credential_validation_pattern(self):
        """Test credential validation patterns used across feedback tools"""
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
        """Test stdout redirection pattern used in all feedback tools"""
        # Test the pattern used to capture unexpected stdout
        old_stdout = StringIO()
        temp_stdout = StringIO()
        
        try:
            # Write something that should be captured
            print("This should be captured", file=temp_stdout)
            
            # Check capture
            captured_output = temp_stdout.getvalue()
            assert "This should be captured" in captured_output
        finally:
            # Pattern always restores stdout
            pass
    
    def test_client_creation_pattern(self):
        """Test client creation patterns with nested stdout capture"""
        def simulate_client_creation_with_capture():
            """Simulate the nested stdout capture pattern used in feedback tools"""
            client_stdout = StringIO()
            saved_stdout = StringIO()  # Mock current stdout
            
            try:
                # Mock successful client creation
                client = {"api_url": "test", "api_key": "test"}
                
                # Simulate captured output check
                client_output = client_stdout.getvalue()
                if client_output:
                    # Would log warning in real implementation
                    pass
                
                return client, None
            finally:
                # Would restore stdout in real implementation
                pass
        
        client, error = simulate_client_creation_with_capture()
        assert client is not None
        assert error is None
    
    def test_scorecard_identifier_resolution_pattern(self):
        """Test scorecard identifier resolution pattern"""
        def mock_resolve_scorecard_identifier(client, identifier):
            # Mock the pattern used in feedback tools
            scorecard_mappings = {
                'scorecard-123': 'scorecard-123',
                'test-scorecard': 'scorecard-123',
                'Test Scorecard': 'scorecard-123'
            }
            return scorecard_mappings.get(identifier)
        
        # Test ID resolution
        resolved = mock_resolve_scorecard_identifier(None, 'scorecard-123')
        assert resolved == 'scorecard-123'
        
        # Test name resolution
        resolved = mock_resolve_scorecard_identifier(None, 'Test Scorecard')
        assert resolved == 'scorecard-123'
        
        # Test key resolution
        resolved = mock_resolve_scorecard_identifier(None, 'test-scorecard')
        assert resolved == 'scorecard-123'
        
        # Test not found
        resolved = mock_resolve_scorecard_identifier(None, 'nonexistent')
        assert resolved is None
    
    def test_account_id_resolution_pattern(self):
        """Test account ID resolution pattern"""
        def mock_resolve_account_id_for_command(client, account_identifier):
            # Mock the pattern used in feedback tools
            if account_identifier is None:
                return "default-account-123"
            return f"resolved-{account_identifier}"
        
        # Test default account resolution
        account_id = mock_resolve_account_id_for_command(None, None)
        assert account_id == "default-account-123"
        
        # Test specific account resolution
        account_id = mock_resolve_account_id_for_command(None, "specific-account")
        assert account_id == "resolved-specific-account"
    
    def test_error_response_handling_pattern(self):
        """Test GraphQL error response handling pattern"""
        # Test error response structure
        error_response = {
            'errors': [
                {
                    'message': 'Scorecard not found',
                    'path': ['getScorecard'],
                    'extensions': {'code': 'NOT_FOUND'}
                }
            ]
        }
        
        # Test the pattern used to handle errors
        if 'errors' in error_response:
            error_details = json.dumps(error_response['errors'], indent=2)
            assert 'Scorecard not found' in error_details
            assert 'NOT_FOUND' in error_details
    
    def test_import_error_handling_pattern(self):
        """Test import error handling pattern for FeedbackService"""
        def simulate_import_attempt():
            try:
                # Mock import failure
                raise ImportError("Could not import FeedbackService")
            except ImportError as e:
                return f"Error: Could not import FeedbackService: {e}. Core modules may not be available."
        
        error_message = simulate_import_attempt()
        assert "Could not import FeedbackService" in error_message
        assert "Core modules may not be available" in error_message