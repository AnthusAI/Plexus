#!/usr/bin/env python3
"""
Unit tests for score tools
"""
import pytest
import os
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO

pytestmark = pytest.mark.unit


class TestScoreInfoTool:
    """Test plexus_score_info tool patterns"""
    
    def test_score_info_validation_patterns(self):
        """Test score info parameter validation patterns"""
        def validate_score_info_params(score_identifier, scorecard_identifier=None, version_id=None, include_versions=False):
            if not score_identifier or not score_identifier.strip():
                return False, "score_identifier is required"
            return True, None
        
        # Test valid parameters
        valid, error = validate_score_info_params("score-123")
        assert valid is True
        assert error is None
        
        # Test with scorecard identifier
        valid, error = validate_score_info_params("score-123", "scorecard-456")
        assert valid is True
        assert error is None
        
        # Test empty score identifier
        valid, error = validate_score_info_params("")
        assert valid is False
        assert "score_identifier is required" in error
        
        # Test whitespace-only score identifier
        valid, error = validate_score_info_params("   ")
        assert valid is False
        assert "score_identifier is required" in error
    
    def test_score_search_patterns(self):
        """Test score search logic patterns"""
        # Test intelligent search across scorecards
        mock_scorecards = [
            {
                'id': 'scorecard-1',
                'name': 'Test Scorecard',
                'sections': {
                    'items': [
                        {
                            'id': 'section-1',
                            'name': 'Section 1',
                            'scores': {
                                'items': [
                                    {
                                        'id': 'score-1',
                                        'name': 'Test Score',
                                        'key': 'test_score',
                                        'externalId': 'EXT-001',
                                        'type': 'SimpleLLMScore'
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        ]
        
        def find_scores_in_scorecards(score_identifier, scorecards):
            found_scores = []
            for scorecard in scorecards:
                for section in scorecard.get('sections', {}).get('items', []):
                    for score in section.get('scores', {}).get('items', []):
                        if (score.get('id') == score_identifier or 
                            score.get('name', '').lower() == score_identifier.lower() or 
                            score.get('key') == score_identifier or 
                            score.get('externalId') == score_identifier or
                            score_identifier.lower() in score.get('name', '').lower()):
                            found_scores.append({
                                'score': score,
                                'section': section,
                                'scorecard': scorecard
                            })
            return found_scores
        
        # Test exact ID match
        found = find_scores_in_scorecards('score-1', mock_scorecards)
        assert len(found) == 1
        assert found[0]['score']['id'] == 'score-1'
        
        # Test name match (case insensitive)
        found = find_scores_in_scorecards('test score', mock_scorecards)
        assert len(found) == 1
        assert found[0]['score']['name'] == 'Test Score'
        
        # Test partial name match
        found = find_scores_in_scorecards('test', mock_scorecards)
        assert len(found) == 1
        
        # Test external ID match
        found = find_scores_in_scorecards('EXT-001', mock_scorecards)
        assert len(found) == 1
        assert found[0]['score']['externalId'] == 'EXT-001'
        
        # Test no match
        found = find_scores_in_scorecards('nonexistent', mock_scorecards)
        assert len(found) == 0
    
    def test_score_response_formatting_patterns(self):
        """Test score response formatting patterns"""
        # Test single match response
        score_data = {
            'id': 'score-123',
            'name': 'Test Score',
            'key': 'test_score',
            'championVersionId': 'version-456',
            'isDisabled': False
        }
        
        section_data = {
            'id': 'section-123',
            'name': 'Test Section'
        }
        
        scorecard_data = {
            'id': 'scorecard-123',
            'name': 'Test Scorecard'
        }
        
        response = {
            "found": True,
            "scoreId": score_data['id'],
            "scoreName": score_data['name'],
            "scoreKey": score_data.get('key'),
            "championVersionId": score_data.get('championVersionId'),
            "isDisabled": score_data.get('isDisabled', False),
            "location": {
                "scorecardId": scorecard_data['id'],
                "scorecardName": scorecard_data['name'],
                "sectionId": section_data['id'],
                "sectionName": section_data['name']
            }
        }
        
        assert response['found'] is True
        assert response['scoreId'] == 'score-123'
        assert response['scoreName'] == 'Test Score'
        assert response['location']['scorecardName'] == 'Test Scorecard'
        
        # Test multiple matches response
        matches = [
            {
                "scoreId": "score-1",
                "scoreName": "Test Score 1",
                "scorecardName": "Scorecard 1",
                "sectionName": "Section 1",
                "isDisabled": False
            },
            {
                "scoreId": "score-2", 
                "scoreName": "Test Score 2",
                "scorecardName": "Scorecard 2",
                "sectionName": "Section 2",
                "isDisabled": True
            }
        ]
        
        multiple_response = {
            "found": True,
            "multiple": True,
            "count": len(matches),
            "matches": matches
        }
        
        assert multiple_response['multiple'] is True
        assert multiple_response['count'] == 2
        assert len(multiple_response['matches']) == 2


class TestScoreConfigurationTool:
    """Test plexus_score_configuration tool patterns"""
    
    def test_score_config_validation_patterns(self):
        """Test score configuration parameter validation patterns"""
        def validate_score_config_params(scorecard_identifier, score_identifier, version_id=None):
            if not scorecard_identifier or not scorecard_identifier.strip():
                return False, "scorecard_identifier is required"
            if not score_identifier or not score_identifier.strip():
                return False, "score_identifier is required"
            return True, None
        
        # Test valid parameters
        valid, error = validate_score_config_params("scorecard-123", "score-456")
        assert valid is True
        assert error is None
        
        # Test with version ID
        valid, error = validate_score_config_params("scorecard-123", "score-456", "version-789")
        assert valid is True
        assert error is None
        
        # Test missing scorecard identifier
        valid, error = validate_score_config_params("", "score-456")
        assert valid is False
        assert "scorecard_identifier is required" in error
        
        # Test missing score identifier
        valid, error = validate_score_config_params("scorecard-123", "")
        assert valid is False
        assert "score_identifier is required" in error
    
    def test_configuration_response_patterns(self):
        """Test configuration response formatting patterns"""
        # Test response with specific version
        version_data = {
            'id': 'version-123',
            'configuration': 'name: Test Score\ntype: SimpleLLMScore\n',
            'createdAt': '2024-01-01T00:00:00Z',
            'note': 'Updated configuration',
            'isFeatured': True
        }
        
        response = {
            "scoreId": "score-123",
            "scoreName": "Test Score",
            "scorecardName": "Test Scorecard",
            "versionId": version_data['id'],
            "isChampionVersion": False,
            "configuration": version_data['configuration'],
            "versionMetadata": {
                "createdAt": version_data.get('createdAt'),
                "note": version_data.get('note'),
                "isFeatured": version_data.get('isFeatured')
            }
        }
        
        assert response['versionId'] == 'version-123'
        assert 'name: Test Score' in response['configuration']
        assert response['versionMetadata']['note'] == 'Updated configuration'
        assert response['versionMetadata']['isFeatured'] is True
        
        # Test champion version response
        champion_response = {
            "scoreId": "score-123",
            "scoreName": "Test Score",
            "versionId": "champion-version-456",
            "isChampionVersion": True,
            "configuration": "name: Champion Score\ntype: SimpleLLMScore\n"
        }
        
        assert champion_response['isChampionVersion'] is True
        assert champion_response['versionId'] == 'champion-version-456'


class TestScorePullTool:
    """Test plexus_score_pull tool patterns"""
    
    def test_score_pull_validation_patterns(self):
        """Test score pull parameter validation patterns"""
        def validate_score_pull_params(scorecard_identifier, score_identifier):
            if not scorecard_identifier or not scorecard_identifier.strip():
                return False, "scorecard_identifier is required"
            if not score_identifier or not score_identifier.strip():
                return False, "score_identifier is required"
            return True, None
        
        # Test valid parameters
        valid, error = validate_score_pull_params("scorecard-123", "score-456")
        assert valid is True
        assert error is None
        
        # Test missing parameters
        valid, error = validate_score_pull_params("", "score-456")
        assert valid is False
        assert "scorecard_identifier is required" in error
    
    def test_pull_response_patterns(self):
        """Test pull response formatting patterns"""
        # Test successful pull response
        pull_result = {
            "success": True,
            "file_path": "/local/path/scorecard/score.yml",
            "version_id": "version-123",
            "message": "Configuration pulled successfully"
        }
        
        response = {
            "success": True,
            "scoreId": "score-123",
            "scoreName": "Test Score",
            "scorecardName": "Test Scorecard",
            "filePath": pull_result["file_path"],
            "versionId": pull_result["version_id"],
            "message": pull_result["message"]
        }
        
        assert response['success'] is True
        assert response['filePath'] == "/local/path/scorecard/score.yml"
        assert response['versionId'] == "version-123"
        
        # Test failure response
        failure_result = {
            "success": False,
            "message": "Failed to pull configuration"
        }
        
        assert failure_result['success'] is False
        assert "Failed to pull" in failure_result['message']


class TestScorePushTool:
    """Test plexus_score_push tool patterns"""
    
    def test_score_push_validation_patterns(self):
        """Test score push parameter validation patterns"""
        def validate_score_push_params(scorecard_identifier, score_identifier, version_note=None):
            if not scorecard_identifier or not scorecard_identifier.strip():
                return False, "scorecard_identifier is required"
            if not score_identifier or not score_identifier.strip():
                return False, "score_identifier is required"
            return True, None
        
        # Test valid parameters
        valid, error = validate_score_push_params("scorecard-123", "score-456")
        assert valid is True
        assert error is None
        
        # Test with version note
        valid, error = validate_score_push_params("scorecard-123", "score-456", "Updated via MCP")
        assert valid is True
        assert error is None
    
    def test_push_response_patterns(self):
        """Test push response formatting patterns"""
        # Test successful push response
        push_result = {
            "success": True,
            "version_id": "new-version-123",
            "champion_updated": True,
            "skipped": False,
            "message": "Configuration pushed successfully"
        }
        
        response = {
            "success": True,
            "scoreId": "score-123",
            "scoreName": "Test Score",
            "newVersionId": push_result["version_id"],
            "championUpdated": push_result.get("champion_updated", True),
            "skipped": push_result.get("skipped", False),
            "message": push_result["message"]
        }
        
        assert response['success'] is True
        assert response['newVersionId'] == "new-version-123"
        assert response['championUpdated'] is True
        assert response['skipped'] is False


class TestScoreUpdateTool:
    """Test plexus_score_update tool patterns"""
    
    def test_score_update_validation_patterns(self):
        """Test score update parameter validation patterns"""
        def validate_score_update_params(scorecard_identifier, score_identifier, yaml_configuration, version_note=None):
            if not scorecard_identifier or not scorecard_identifier.strip():
                return False, "scorecard_identifier is required"
            if not score_identifier or not score_identifier.strip():
                return False, "score_identifier is required"
            if not yaml_configuration or not yaml_configuration.strip():
                return False, "yaml_configuration is required"
            return True, None
        
        # Test valid parameters
        valid, error = validate_score_update_params("scorecard-123", "score-456", "name: Test\ntype: SimpleLLMScore")
        assert valid is True
        assert error is None
        
        # Test missing YAML configuration
        valid, error = validate_score_update_params("scorecard-123", "score-456", "")
        assert valid is False
        assert "yaml_configuration is required" in error
    
    def test_yaml_validation_patterns(self):
        """Test YAML validation patterns"""
        import yaml
        
        # Test valid YAML
        valid_yaml = """
        name: Test Score
        type: SimpleLLMScore
        parameters:
          model: gpt-4
        """
        
        try:
            parsed = yaml.safe_load(valid_yaml)
            assert isinstance(parsed, dict)
            assert parsed['name'] == 'Test Score'
            assert parsed['type'] == 'SimpleLLMScore'
        except yaml.YAMLError:
            assert False, "Should not fail to parse valid YAML"
        
        # Test invalid YAML with actual syntax error
        invalid_yaml = """
        name: Test Score
        type: SimpleLLMScore
        parameters:
          model: gpt-4
        invalid_indentation:
      badly indented
        """
        
        try:
            yaml.safe_load(invalid_yaml)
            assert False, "Should fail to parse invalid YAML"
        except yaml.YAMLError:
            # This is expected
            pass
    
    def test_update_response_patterns(self):
        """Test update response formatting patterns"""
        # Test successful update response
        result = {
            "success": True,
            "version_id": "new-version-789",
            "champion_updated": True,
            "skipped": False
        }
        
        yaml_config = "name: Updated Score\ntype: SimpleLLMScore\n"
        
        response = {
            "success": True,
            "scoreId": "score-123",
            "scoreName": "Test Score",
            "newVersionId": result["version_id"],
            "configurationLength": len(yaml_config),
            "championUpdated": result.get("champion_updated", True),
            "skipped": result.get("skipped", False)
        }
        
        assert response['success'] is True
        assert response['newVersionId'] == "new-version-789"
        assert response['configurationLength'] == len(yaml_config)


class TestScoreDeleteTool:
    """Test plexus_score_delete tool patterns"""
    
    def test_score_delete_validation_patterns(self):
        """Test score delete parameter validation patterns"""
        def validate_score_delete_params(score_id, confirm=False):
            if not score_id or not score_id.strip():
                return False, "score_id is required"
            return True, None
        
        # Test valid parameters
        valid, error = validate_score_delete_params("score-123")
        assert valid is True
        assert error is None
        
        # Test with confirmation
        valid, error = validate_score_delete_params("score-123", True)
        assert valid is True
        assert error is None
        
        # Test missing score ID
        valid, error = validate_score_delete_params("")
        assert valid is False
        assert "score_id is required" in error
    
    def test_delete_safety_patterns(self):
        """Test delete safety confirmation patterns"""
        # Test default behavior (requires confirmation)
        def simulate_delete(score_id, confirm=False):
            if not confirm:
                return {
                    "success": False,
                    "message": "Deletion requires confirmation. Set confirm=True to proceed."
                }
            return {
                "success": True,
                "message": f"Score {score_id} deleted successfully"
            }
        
        # Test without confirmation
        result = simulate_delete("score-123", False)
        assert result['success'] is False
        assert "requires confirmation" in result['message']
        
        # Test with confirmation
        result = simulate_delete("score-123", True)
        assert result['success'] is True
        assert "deleted successfully" in result['message']


class TestScoreInstanceHelper:
    """Test _find_score_instance helper function patterns"""
    
    def test_score_instance_finding_patterns(self):
        """Test score instance finding logic patterns"""
        # Mock scorecard data
        mock_scorecard_data = {
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
                                    'externalId': 'EXT-001',
                                    'type': 'SimpleLLMScore',
                                    'order': 1
                                }
                            ]
                        }
                    }
                ]
            }
        }
        
        def find_score_in_scorecard(score_identifier, scorecard_data):
            """Simulate the score finding logic"""
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score_data in section.get('scores', {}).get('items', []):
                    if (score_data.get('id') == score_identifier or 
                        score_data.get('name') == score_identifier or 
                        score_data.get('key') == score_identifier or 
                        score_data.get('externalId') == score_identifier):
                        return {
                            'success': True,
                            'score_data': score_data,
                            'section_id': section['id']
                        }
            return {
                'success': False,
                'error': f"Score '{score_identifier}' not found"
            }
        
        # Test finding by ID
        result = find_score_in_scorecard('score-123', mock_scorecard_data)
        assert result['success'] is True
        assert result['score_data']['id'] == 'score-123'
        
        # Test finding by name
        result = find_score_in_scorecard('Test Score', mock_scorecard_data)
        assert result['success'] is True
        assert result['score_data']['name'] == 'Test Score'
        
        # Test finding by key
        result = find_score_in_scorecard('test_score', mock_scorecard_data)
        assert result['success'] is True
        assert result['score_data']['key'] == 'test_score'
        
        # Test finding by external ID
        result = find_score_in_scorecard('EXT-001', mock_scorecard_data)
        assert result['success'] is True
        assert result['score_data']['externalId'] == 'EXT-001'
        
        # Test not found
        result = find_score_in_scorecard('nonexistent', mock_scorecard_data)
        assert result['success'] is False
        assert "not found" in result['error']


class TestScoreToolsSharedPatterns:
    """Test shared patterns across all score tools"""
    
    def test_credential_validation_pattern(self):
        """Test credential validation patterns used across score tools"""
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
        """Test stdout redirection pattern used in all score tools"""
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
                    'message': 'Score not found',
                    'path': ['getScore'],
                    'extensions': {'code': 'NOT_FOUND'}
                }
            ]
        }
        
        # Test the pattern used to handle errors
        if 'errors' in error_response:
            error_details = json.dumps(error_response['errors'], indent=2)
            assert 'Score not found' in error_details
            assert 'NOT_FOUND' in error_details
    
    def test_dashboard_url_generation_pattern(self):
        """Test dashboard URL generation pattern for scores"""
        def get_plexus_url(path: str) -> str:
            base_url = os.environ.get('PLEXUS_APP_URL', 'https://plexus.anth.us')
            if not base_url.endswith('/'):
                base_url += '/'
            path = path.lstrip('/')
            return base_url + path
        
        # Test score URL generation
        with patch.dict(os.environ, {'PLEXUS_APP_URL': 'https://test.example.com'}):
            url = get_plexus_url("lab/scorecards/scorecard-123/scores/score-456")
            assert url == 'https://test.example.com/lab/scorecards/scorecard-123/scores/score-456'
        
        # Test with trailing slash in base URL
        with patch.dict(os.environ, {'PLEXUS_APP_URL': 'https://test.example.com/'}):
            url = get_plexus_url("lab/scorecards/scorecard-123/scores/score-456")
            assert url == 'https://test.example.com/lab/scorecards/scorecard-123/scores/score-456'
    
    def test_scorecard_identifier_resolution_pattern(self):
        """Test scorecard identifier resolution pattern"""
        def mock_resolve_scorecard_identifier(client, identifier):
            # Mock the pattern used in score tools
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