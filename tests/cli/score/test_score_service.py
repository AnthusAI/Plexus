"""
Unit tests for ScoreService.

Tests score finding, deletion with safety checks, credential validation,
and various error conditions.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from plexus.cli.score.score_service import ScoreService


class TestScoreService:
    """Test class for ScoreService functionality."""
    
    def setup_method(self):
        """Setup method to create mocks for each test."""
        self.mock_client = Mock()
        self.score_service = ScoreService(client=self.mock_client)
    
    def test_init_with_client(self):
        """Test ScoreService initialization with provided client."""
        mock_client = Mock()
        service = ScoreService(client=mock_client)
        assert service.client == mock_client
    
    @patch('plexus.cli.score.score_service.ScoreService._create_client')
    def test_init_without_client(self, mock_create_client):
        """Test ScoreService initialization without provided client."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        service = ScoreService()
        assert service.client == mock_client
        mock_create_client.assert_called_once()
    
    @patch('plexus.cli.client_utils.create_client')
    def test_create_client_success(self, mock_create_client):
        """Test successful client creation."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        # Create service with provided client to avoid constructor call
        service = ScoreService(client=Mock())
        created_client = service._create_client()
        
        assert created_client == mock_client
        mock_create_client.assert_called_once()
    
    @patch('plexus.cli.client_utils.create_client')
    def test_create_client_import_error(self, mock_create_client):
        """Test client creation with import error."""
        mock_create_client.side_effect = ImportError("Module not found")
        
        service = ScoreService()
        created_client = service._create_client()
        
        assert created_client is None
    
    @patch.dict(os.environ, {'PLEXUS_API_URL': 'https://api.example.com', 'PLEXUS_API_KEY': 'test-key'})
    def test_validate_credentials_success(self):
        """Test successful credential validation."""
        is_valid, error_msg = self.score_service.validate_credentials()
        
        assert is_valid is True
        assert error_msg == ""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_validate_credentials_missing_url(self):
        """Test credential validation with missing API URL."""
        is_valid, error_msg = self.score_service.validate_credentials()
        
        assert is_valid is False
        assert "PLEXUS_API_URL" in error_msg
    
    @patch.dict(os.environ, {'PLEXUS_API_URL': 'https://api.example.com'}, clear=True)
    def test_validate_credentials_missing_key(self):
        """Test credential validation with missing API key."""
        is_valid, error_msg = self.score_service.validate_credentials()
        
        assert is_valid is False
        assert "PLEXUS_API_KEY" in error_msg
    
    @patch('plexus.cli.score.score_service.ScoreService._create_client')
    def test_validate_credentials_no_client(self, mock_create_client):
        """Test credential validation with no client."""
        # Mock _create_client to return None to simulate client creation failure
        mock_create_client.return_value = None
        
        service = ScoreService(client=None)
        is_valid, error_msg = service.validate_credentials()
        
        assert is_valid is False
        assert "Could not create Plexus client" in error_msg
    
    @patch('plexus.cli.identifier_resolution.resolve_scorecard_identifier')
    def test_resolve_scorecard_identifier_success(self, mock_resolve):
        """Test successful scorecard identifier resolution."""
        mock_resolve.return_value = 'scorecard-123'
        
        result = self.score_service.resolve_scorecard_identifier('test-scorecard')
        
        assert result == 'scorecard-123'
        mock_resolve.assert_called_once_with(self.mock_client, 'test-scorecard')
    
    @patch('plexus.cli.identifier_resolution.resolve_scorecard_identifier')
    def test_resolve_scorecard_identifier_import_error(self, mock_resolve):
        """Test scorecard identifier resolution with import error."""
        mock_resolve.side_effect = ImportError("Module not found")
        
        # Mock the fallback method
        self.score_service._resolve_scorecard_fallback = Mock(return_value='scorecard-123')
        
        result = self.score_service.resolve_scorecard_identifier('test-scorecard')
        
        assert result == 'scorecard-123'
        self.score_service._resolve_scorecard_fallback.assert_called_once_with('test-scorecard')
    
    def test_resolve_scorecard_fallback_direct_id(self):
        """Test scorecard fallback resolution with direct ID."""
        self.mock_client.execute.return_value = {'getScorecard': {'id': 'scorecard-123'}}
        
        result = self.score_service._resolve_scorecard_fallback('scorecard-123')
        
        assert result == 'scorecard-123'
    
    def test_resolve_scorecard_fallback_by_key(self):
        """Test scorecard fallback resolution by key."""
        # First call (direct ID) fails
        # Second call (by key) succeeds
        self.mock_client.execute.side_effect = [
            Exception("Not found"),
            {'listScorecards': {'items': [{'id': 'scorecard-456'}]}}
        ]
        
        result = self.score_service._resolve_scorecard_fallback('test-key')
        
        assert result == 'scorecard-456'
    
    def test_resolve_scorecard_fallback_not_found(self):
        """Test scorecard fallback resolution when not found."""
        # Both calls fail
        self.mock_client.execute.side_effect = [
            Exception("Not found"),
            {'listScorecards': {'items': []}}
        ]
        
        result = self.score_service._resolve_scorecard_fallback('nonexistent')
        
        assert result is None
    
    def test_find_scores_by_pattern_success(self):
        """Test successful score finding by pattern."""
        # Mock scorecard resolution
        self.score_service.resolve_scorecard_identifier = Mock(return_value='scorecard-123')
        
        # Mock GraphQL response
        mock_response = {
            'getScorecard': {
                'id': 'scorecard-123',
                'name': 'Test Scorecard',
                'key': 'test-scorecard',
                'sections': {
                    'items': [{
                        'id': 'section-1',
                        'name': 'Test Section',
                        'scores': {
                            'items': [{
                                'id': 'score-1',
                                'name': 'Test Score (DELETE ME)',
                                'key': 'test-score',
                                'externalId': 'ext-1',
                                'type': 'test',
                                'order': 1
                            }]
                        }
                    }]
                }
            }
        }
        
        self.score_service._execute_with_error_handling = Mock(return_value=(True, mock_response))
        
        result = self.score_service.find_scores_by_pattern('DELETE ME', 'test-scorecard')
        
        assert len(result) == 1
        assert result[0]['id'] == 'score-1'
        assert result[0]['name'] == 'Test Score (DELETE ME)'
        assert result[0]['section']['name'] == 'Test Section'
        assert result[0]['scorecard']['name'] == 'Test Scorecard'
    
    def test_find_scores_by_pattern_no_scorecard(self):
        """Test score finding when scorecard not found."""
        self.score_service.resolve_scorecard_identifier = Mock(return_value=None)
        
        result = self.score_service.find_scores_by_pattern('DELETE ME', 'nonexistent')
        
        assert result == []
    
    def test_find_scores_by_pattern_no_scorecard_identifier(self):
        """Test score finding without scorecard identifier."""
        result = self.score_service.find_scores_by_pattern('DELETE ME')
        
        assert result == []
    
    def test_find_scores_by_pattern_no_matches(self):
        """Test score finding with no pattern matches."""
        # Mock scorecard resolution
        self.score_service.resolve_scorecard_identifier = Mock(return_value='scorecard-123')
        
        # Mock GraphQL response with no matching scores
        mock_response = {
            'getScorecard': {
                'id': 'scorecard-123',
                'name': 'Test Scorecard',
                'key': 'test-scorecard',
                'sections': {
                    'items': [{
                        'id': 'section-1',
                        'name': 'Test Section',
                        'scores': {
                            'items': [{
                                'id': 'score-1',
                                'name': 'Regular Score',
                                'key': 'regular-score',
                                'externalId': 'ext-1',
                                'type': 'standard',
                                'order': 1
                            }]
                        }
                    }]
                }
            }
        }
        
        self.score_service._execute_with_error_handling = Mock(return_value=(True, mock_response))
        
        result = self.score_service.find_scores_by_pattern('DELETE ME', 'test-scorecard')
        
        assert result == []
    
    @patch.dict(os.environ, {'PLEXUS_API_URL': 'https://api.example.com', 'PLEXUS_API_KEY': 'test-key'})
    def test_delete_score_success(self):
        """Test successful score deletion."""
        mock_response = {'deleteScore': {'id': 'score-123'}}
        self.score_service._execute_with_error_handling = Mock(return_value=(True, mock_response))
        
        result = self.score_service.delete_score('score-123', confirm=True)
        
        assert "Successfully deleted" in result
        assert "score-123" in result
    
    def test_delete_score_no_confirmation(self):
        """Test score deletion without confirmation."""
        result = self.score_service.delete_score('score-123', confirm=False)
        
        assert "requires confirmation" in result
        assert "score-123" in result
    
    @patch.dict(os.environ, {}, clear=True)
    def test_delete_score_invalid_credentials(self):
        """Test score deletion with invalid credentials."""
        result = self.score_service.delete_score('score-123', confirm=True)
        
        assert "Error:" in result
        assert "PLEXUS_API_URL" in result
    
    @patch.dict(os.environ, {'PLEXUS_API_URL': 'https://api.example.com', 'PLEXUS_API_KEY': 'test-key'})
    def test_delete_score_graphql_error(self):
        """Test score deletion with GraphQL error."""
        self.score_service._execute_with_error_handling = Mock(return_value=(False, "GraphQL error occurred"))
        
        result = self.score_service.delete_score('score-123', confirm=True)
        
        assert "Error from deleteScore mutation" in result
        assert "GraphQL error occurred" in result
    
    @patch.dict(os.environ, {'PLEXUS_API_URL': 'https://api.example.com', 'PLEXUS_API_KEY': 'test-key'})
    def test_delete_score_no_response(self):
        """Test score deletion with no response from server."""
        mock_response = {}  # No deleteScore in response
        self.score_service._execute_with_error_handling = Mock(return_value=(True, mock_response))
        
        result = self.score_service.delete_score('score-123', confirm=True)
        
        assert "Failed to delete score" in result
        assert "No response from server" in result
    
    def test_get_score_details_success(self):
        """Test successful score details retrieval."""
        mock_response = {
            'getScore': {
                'id': 'score-123',
                'name': 'Test Score',
                'key': 'test-score',
                'externalId': 'ext-123',
                'description': 'A test score',
                'type': 'standard',
                'order': 1,
                'championVersionId': 'version-123',
                'sectionId': 'section-123',
                'scorecardId': 'scorecard-123'
            }
        }
        
        self.score_service._execute_with_error_handling = Mock(return_value=(True, mock_response))
        
        result = self.score_service.get_score_details('score-123')
        
        assert result is not None
        assert result['id'] == 'score-123'
        assert result['name'] == 'Test Score'
    
    def test_get_score_details_error(self):
        """Test score details retrieval with error."""
        self.score_service._execute_with_error_handling = Mock(return_value=(False, "GraphQL error"))
        
        result = self.score_service.get_score_details('score-123')
        
        assert result is None
    
    def test_execute_with_error_handling_success(self):
        """Test successful GraphQL execution."""
        mock_response = {'data': 'test'}
        self.mock_client.execute.return_value = mock_response
        
        success, result = self.score_service._execute_with_error_handling('query Test { test }')
        
        assert success is True
        assert result == mock_response
    
    def test_execute_with_error_handling_graphql_errors(self):
        """Test GraphQL execution with errors in response."""
        mock_response = {'errors': [{'message': 'Test error'}]}
        self.mock_client.execute.return_value = mock_response
        
        success, result = self.score_service._execute_with_error_handling('query Test { test }')
        
        assert success is False
        assert "GraphQL errors" in result
    
    def test_execute_with_error_handling_exception(self):
        """Test GraphQL execution with exception."""
        self.mock_client.execute.side_effect = Exception("Connection error")
        
        success, result = self.score_service._execute_with_error_handling('query Test { test }')
        
        assert success is False
        assert "Execution error" in result
        assert "Connection error" in result 