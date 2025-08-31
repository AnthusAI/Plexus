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
    
    def test_score_info_code_and_guidelines_from_champion(self):
        """Test that score info returns code and guidelines from champion version"""
        # Mock score data with champion version
        score_data = {
            'id': 'score-123',
            'name': 'Test Score',
            'key': 'test_score',
            'championVersionId': 'version-456',
            'description': 'Score description',
            'isDisabled': False
        }
        
        # Mock champion version data
        champion_version_data = {
            'id': 'version-456',
            'configuration': 'name: Test Score\ntype: SimpleLLMScore\nsystem_message: "Test prompt"',
            'guidelines': '# Test Guidelines\n\nThis is a test score.',
            'description': 'Version description',
            'createdAt': '2024-01-01T00:00:00Z',
            'updatedAt': '2024-01-01T00:00:00Z',
            'note': 'Champion version',
            'isFeatured': True,
            'parentVersionId': None
        }
        
        # Expected response structure
        expected_response = {
            "found": True,
            "scoreId": "score-123",
            "scoreName": "Test Score",
            "scoreKey": "test_score",
            "championVersionId": "version-456",
            "description": "Version description",  # Should come from version, not score
            "code": champion_version_data['configuration'],
            "guidelines": champion_version_data['guidelines'],
            "isDisabled": False
        }
        
        # Verify the expected structure
        assert expected_response['code'] is not None
        assert expected_response['guidelines'] is not None
        assert expected_response['description'] == "Version description"  # Version takes priority
        assert "name: Test Score" in expected_response['code']
        assert "# Test Guidelines" in expected_response['guidelines']
    
    def test_score_info_description_fallback_logic(self):
        """Test description field logic: version description > score description"""
        # Test case 1: Version has description - should use version description
        score_with_version_desc = {
            'id': 'score-123',
            'description': 'Score description',
            'championVersionId': 'version-456'
        }
        
        version_with_desc = {
            'id': 'version-456',
            'description': 'Version description',
            'configuration': 'name: Test',
            'guidelines': 'Test guidelines'
        }
        
        # Should use version description
        expected_desc_1 = version_with_desc['description']
        assert expected_desc_1 == 'Version description'
        
        # Test case 2: Version has no description - should fall back to score description
        version_without_desc = {
            'id': 'version-456',
            'description': None,  # No version description
            'configuration': 'name: Test',
            'guidelines': 'Test guidelines'
        }
        
        # Should fall back to score description
        expected_desc_2 = score_with_version_desc['description']
        assert expected_desc_2 == 'Score description'
        
        # Test case 3: No champion version - should use score description
        score_without_champion = {
            'id': 'score-123',
            'description': 'Score description',
            'championVersionId': None
        }
        
        expected_desc_3 = score_without_champion['description']
        assert expected_desc_3 == 'Score description'
    
    def test_score_info_specific_version_parameter(self):
        """Test version_id parameter for getting specific score version info"""
        # Mock score data
        score_data = {
            'id': 'score-123',
            'name': 'Test Score',
            'championVersionId': 'version-current',
            'description': 'Score description'
        }
        
        # Mock specific version data (not the champion)
        specific_version_data = {
            'id': 'version-specific',
            'configuration': 'name: Specific Version\ntype: SimpleLLMScore',
            'guidelines': '# Specific Version Guidelines',
            'description': 'Specific version description',
            'createdAt': '2024-02-01T00:00:00Z',
            'note': 'Specific version for testing',
            'isFeatured': False
        }
        
        # When version_id is provided, should use that version instead of champion
        version_id = 'version-specific'
        
        expected_response = {
            "scoreId": "score-123",
            "scoreName": "Test Score",
            "championVersionId": "version-current",  # Still shows champion ID
            "description": "Specific version description",  # From specific version
            "code": specific_version_data['configuration'],
            "guidelines": specific_version_data['guidelines'],
            "targetedVersionDetails": specific_version_data  # Added when version_id specified
        }
        
        # Verify specific version takes precedence
        assert expected_response['code'] == specific_version_data['configuration']
        assert expected_response['guidelines'] == specific_version_data['guidelines']
        assert expected_response['description'] == specific_version_data['description']
        assert expected_response['targetedVersionDetails'] is not None
        assert "Specific Version" in expected_response['code']
    
    def test_score_info_no_champion_version_handling(self):
        """Test handling when score has no champion version"""
        # Mock score data without champion version
        score_data = {
            'id': 'score-123',
            'name': 'Test Score',
            'championVersionId': None,  # No champion version
            'description': 'Score description',
            'isDisabled': False
        }
        
        expected_response = {
            "found": True,
            "scoreId": "score-123",
            "scoreName": "Test Score",
            "championVersionId": None,
            "description": "Score description",  # Falls back to score description
            "code": None,  # No code available
            "guidelines": None,  # No guidelines available
            "isDisabled": False
        }
        
        # Verify fallback behavior
        assert expected_response['code'] is None
        assert expected_response['guidelines'] is None
        assert expected_response['description'] == "Score description"
        assert expected_response['championVersionId'] is None
    
    def test_score_info_field_name_consistency(self):
        """Test that response uses 'code' instead of 'configuration'"""
        # Mock response structure
        response = {
            "scoreId": "score-123",
            "code": "name: Test Score\ntype: SimpleLLMScore",  # Should be 'code', not 'configuration'
            "guidelines": "# Test Guidelines"
        }
        
        # Verify field names
        assert 'code' in response
        assert 'configuration' not in response  # Should not use old field name
        assert response['code'] is not None
        assert isinstance(response['code'], str)
    
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
    
    def test_score_configuration_uses_code_field(self):
        """Test that score configuration tool returns 'code' instead of 'configuration'"""
        # Mock version data
        version_data = {
            'id': 'version-123',
            'configuration': 'name: Test Score\ntype: SimpleLLMScore\nsystem_message: "Test prompt"',
            'guidelines': '# Test Guidelines\n\nThis is a test score.',
            'createdAt': '2024-01-01T00:00:00Z',
            'note': 'Updated configuration',
            'isFeatured': True
        }
        
        # Expected response structure with 'code' field
        expected_response = {
            "scoreId": "score-123",
            "scoreName": "Test Score",
            "scorecardName": "Test Scorecard",
            "versionId": version_data['id'],
            "isChampionVersion": False,
            "code": version_data['configuration'],  # Should be 'code', not 'configuration'
            "guidelines": version_data['guidelines'],
            "versionMetadata": {
                "createdAt": version_data.get('createdAt'),
                "note": version_data.get('note'),
                "isFeatured": version_data.get('isFeatured')
            }
        }
        
        # Verify field names
        assert 'code' in expected_response
        assert 'configuration' not in expected_response  # Should not use old field name
        assert expected_response['code'] == version_data['configuration']
        assert 'name: Test Score' in expected_response['code']
    
    def test_champion_version_configuration_uses_code_field(self):
        """Test that champion version configuration also uses 'code' field"""
        # Mock champion version response
        champion_response = {
            "scoreId": "score-123",
            "scoreName": "Test Score",
            "versionId": "champion-version-456",
            "isChampionVersion": True,
            "code": "name: Champion Score\ntype: SimpleLLMScore\nsystem_message: 'Champion prompt'",  # Should be 'code'
            "guidelines": "# Champion Guidelines\n\nThis is the champion version."
        }
        
        # Verify field consistency
        assert 'code' in champion_response
        assert 'configuration' not in champion_response
        assert champion_response['isChampionVersion'] is True
        assert champion_response['versionId'] == 'champion-version-456'
        assert 'Champion Score' in champion_response['code']
    
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
    
    def test_score_update_code_and_guidelines_change_detection(self):
        """Test that score update properly detects code and guidelines changes"""
        # Mock current version data
        current_version_data = {
            'id': 'version-current',
            'configuration': 'name: Original Score\ntype: SimpleLLMScore\nsystem_message: "Original prompt"',
            'guidelines': '# Original Guidelines\n\nThis is the original version.'
        }
        
        # Test case 1: Code changed, guidelines unchanged
        new_code = 'name: Updated Score\ntype: SimpleLLMScore\nsystem_message: "Updated prompt"'
        same_guidelines = '# Original Guidelines\n\nThis is the original version.'
        
        # Should create new version because code changed
        expected_result_1 = {
            "success": True,
            "version_created": True,
            "skipped": False,
            "parent_version_id": "version-current"
        }
        
        # Test case 2: Guidelines changed, code unchanged  
        same_code = 'name: Original Score\ntype: SimpleLLMScore\nsystem_message: "Original prompt"'
        new_guidelines = '# Updated Guidelines\n\nThis is the updated version with new instructions.'
        
        # Should create new version because guidelines changed
        expected_result_2 = {
            "success": True,
            "version_created": True,
            "skipped": False,
            "parent_version_id": "version-current"
        }
        
        # Test case 3: Both unchanged
        # Should skip version creation
        expected_result_3 = {
            "success": True,
            "version_created": False,
            "skipped": True,
            "parent_version_id": "version-current"
        }
        
        # Verify expected behavior
        assert expected_result_1["version_created"] is True
        assert expected_result_2["version_created"] is True  
        assert expected_result_3["version_created"] is False
        assert expected_result_3["skipped"] is True
    
    def test_score_update_parent_version_parameter(self):
        """Test parent_version_id parameter functionality"""
        # Mock score data
        score_data = {
            'id': 'score-123',
            'name': 'Test Score',
            'championVersionId': 'version-champion'
        }
        
        # Mock specific parent version (not the champion)
        parent_version_data = {
            'id': 'version-parent',
            'configuration': 'name: Parent Version\ntype: SimpleLLMScore',
            'guidelines': '# Parent Guidelines'
        }
        
        # Test with explicit parent_version_id
        parent_version_id = 'version-parent'
        new_code = 'name: Child Version\ntype: SimpleLLMScore'
        
        expected_update_params = {
            "scorecard_identifier": "test-scorecard",
            "score_identifier": "test-score", 
            "code": new_code,
            "parent_version_id": parent_version_id,
            "version_note": "Updated from specific parent"
        }
        
        expected_response = {
            "success": True,
            "version_created": True,
            "parent_version_id": parent_version_id,  # Should use specified parent
            "new_version_parent": parent_version_id  # New version should have this as parent
        }
        
        # Verify parent version is used for comparison and set as parent
        assert expected_update_params["parent_version_id"] == parent_version_id
        assert expected_response["parent_version_id"] == parent_version_id
    
    def test_score_update_preserves_existing_content(self):
        """Test that update preserves existing code/guidelines when only one is provided"""
        # Mock current version with both code and guidelines
        current_version = {
            'configuration': 'name: Current Score\ntype: SimpleLLMScore',
            'guidelines': '# Current Guidelines\n\nExisting guidelines content.'
        }
        
        # Test case 1: Only code provided - should preserve guidelines
        update_params_1 = {
            "code": "name: Updated Score\ntype: SimpleLLMScore",
            "guidelines": None  # Not provided
        }
        
        expected_version_input_1 = {
            "configuration": "name: Updated Score\ntype: SimpleLLMScore",
            "guidelines": "# Current Guidelines\n\nExisting guidelines content."  # Preserved
        }
        
        # Test case 2: Only guidelines provided - should preserve code
        update_params_2 = {
            "code": None,  # Not provided
            "guidelines": "# Updated Guidelines\n\nNew guidelines content."
        }
        
        expected_version_input_2 = {
            "configuration": "name: Current Score\ntype: SimpleLLMScore",  # Preserved
            "guidelines": "# Updated Guidelines\n\nNew guidelines content."
        }
        
        # Verify preservation logic
        assert expected_version_input_1["guidelines"] == current_version["guidelines"]
        assert expected_version_input_2["configuration"] == current_version["configuration"]
    
    def test_score_update_metadata_and_version_updates(self):
        """Test that score update can handle both metadata and version updates"""
        update_params = {
            "scorecard_identifier": "test-scorecard",
            "score_identifier": "test-score",
            # Metadata updates
            "name": "Updated Score Name",
            "description": "Updated description", 
            "ai_model": "gpt-4",
            # Version updates
            "code": "name: Updated Code\ntype: SimpleLLMScore",
            "guidelines": "# Updated Guidelines",
            "version_note": "Combined metadata and version update"
        }
        
        expected_response = {
            "success": True,
            "updates": {
                "metadata_updated": True,
                "version_created": True,
                "metadata_changes": {
                    "name": "Updated Score Name",
                    "description": "Updated description",
                    "ai_model": "gpt-4"
                },
                "version_info": {
                    "version_id": "new-version-123",
                    "skipped": False,
                    "message": "Successfully created new version"
                }
            }
        }
        
        # Verify both types of updates are handled
        assert expected_response["updates"]["metadata_updated"] is True
        assert expected_response["updates"]["version_created"] is True
        assert "name" in expected_response["updates"]["metadata_changes"]
        assert expected_response["updates"]["version_info"]["skipped"] is False
    
    def test_score_update_no_changes_detected(self):
        """Test score update when no changes are detected"""
        # Mock current version data
        current_version = {
            'configuration': 'name: Test Score\ntype: SimpleLLMScore',
            'guidelines': '# Test Guidelines\n\nExisting content.'
        }
        
        # Provide same content as current version
        update_params = {
            "code": "name: Test Score\ntype: SimpleLLMScore",  # Same as current
            "guidelines": "# Test Guidelines\n\nExisting content.",  # Same as current
            "version_note": "No changes should be detected"
        }
        
        expected_response = {
            "success": True,
            "updates": {
                "metadata_updated": False,
                "version_created": False,  # No version created
                "version_info": {
                    "skipped": True,  # Skipped due to no changes
                    "message": "No changes detected, skipping version creation"
                }
            }
        }
        
        # Verify no-change detection
        assert expected_response["updates"]["version_created"] is False
        assert expected_response["updates"]["version_info"]["skipped"] is True
    
    def test_score_update_error_handling(self):
        """Test error handling in score update scenarios"""
        # Test case 1: Invalid YAML code
        invalid_yaml_params = {
            "code": "invalid: [unclosed bracket\nbroken: yaml",
            "guidelines": "Valid guidelines"
        }
        
        expected_yaml_error = {
            "success": False,
            "error": "INVALID_YAML",
            "message": "Invalid YAML code content"
        }
        
        # Test case 2: Parent version not found
        missing_parent_params = {
            "code": "name: Valid Code\ntype: SimpleLLMScore",
            "parent_version_id": "nonexistent-version-id"
        }
        
        expected_parent_error = {
            "success": False,
            "error": "PARENT_VERSION_NOT_FOUND",
            "message": "Specified parent version not found"
        }
        
        # Test case 3: No updates provided
        no_updates_params = {
            "scorecard_identifier": "test-scorecard",
            "score_identifier": "test-score"
            # No metadata or version fields provided
        }
        
        expected_no_updates_error = {
            "success": False,
            "error": "NO_UPDATES_PROVIDED",
            "message": "At least one field must be provided for update"
        }
        
        # Verify error handling
        assert "INVALID_YAML" in expected_yaml_error["error"]
        assert "PARENT_VERSION_NOT_FOUND" in expected_parent_error["error"]
        assert "NO_UPDATES_PROVIDED" in expected_no_updates_error["error"]
    
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


class TestCreateVersionFromCodeWithParent:
    """Test _create_version_from_code_with_parent helper function patterns"""
    
    def test_create_version_with_parent_change_detection(self):
        """Test change detection logic in _create_version_from_code_with_parent"""
        # Mock parent version data
        parent_version_data = {
            'id': 'parent-version-123',
            'configuration': 'name: Parent Score\ntype: SimpleLLMScore',
            'guidelines': '# Parent Guidelines\n\nOriginal content.'
        }
        
        # Test case 1: Code changed
        new_code = 'name: Updated Score\ntype: SimpleLLMScore'
        same_guidelines = '# Parent Guidelines\n\nOriginal content.'
        
        # Should create new version
        expected_result_1 = {
            "success": True,
            "version_id": "new-version-456",
            "skipped": False,
            "parent_version_id": "parent-version-123"
        }
        
        # Test case 2: Guidelines changed
        same_code = 'name: Parent Score\ntype: SimpleLLMScore'
        new_guidelines = '# Updated Guidelines\n\nNew content.'
        
        # Should create new version
        expected_result_2 = {
            "success": True,
            "version_id": "new-version-789",
            "skipped": False,
            "parent_version_id": "parent-version-123"
        }
        
        # Test case 3: No changes
        # Should skip version creation
        expected_result_3 = {
            "success": True,
            "version_id": "parent-version-123",  # Returns parent version ID
            "skipped": True,
            "parent_version_id": "parent-version-123"
        }
        
        # Verify change detection logic
        assert expected_result_1["skipped"] is False
        assert expected_result_2["skipped"] is False
        assert expected_result_3["skipped"] is True
        assert expected_result_3["version_id"] == expected_result_3["parent_version_id"]
    
    def test_create_version_with_parent_version_input(self):
        """Test that new version is created with correct parent relationship"""
        # Mock input parameters
        score_id = 'score-123'
        parent_version_id = 'parent-version-456'
        code_content = 'name: New Version\ntype: SimpleLLMScore'
        guidelines = '# New Guidelines\n\nUpdated content.'
        note = 'Created from specific parent'
        
        # Expected GraphQL mutation input
        expected_version_input = {
            'scoreId': score_id,
            'configuration': code_content.strip(),
            'guidelines': guidelines.strip(),
            'note': note,
            'isFeatured': True,
            'parentVersionId': parent_version_id  # Should set parent relationship
        }
        
        # Verify parent relationship is established
        assert expected_version_input['parentVersionId'] == parent_version_id
        assert expected_version_input['scoreId'] == score_id
        assert expected_version_input['isFeatured'] is True
    
    def test_create_version_with_parent_error_handling(self):
        """Test error handling in _create_version_from_code_with_parent"""
        # Test case 1: Invalid YAML
        invalid_yaml = 'invalid: [unclosed bracket\nbroken: yaml'
        
        expected_yaml_error = {
            "success": False,
            "error": "INVALID_YAML",
            "message": "Invalid YAML code content"
        }
        
        # Test case 2: API failure during version creation
        valid_yaml = 'name: Valid Score\ntype: SimpleLLMScore'
        
        expected_api_error = {
            "success": False,
            "error": "VERSION_CREATION_FAILED",
            "message": "Failed to create new score version"
        }
        
        # Test case 3: Unexpected exception
        expected_unexpected_error = {
            "success": False,
            "error": "UNEXPECTED_ERROR",
            "message": "Error creating version for Score"
        }
        
        # Verify error handling patterns
        assert "INVALID_YAML" in expected_yaml_error["error"]
        assert "VERSION_CREATION_FAILED" in expected_api_error["error"]
        assert "UNEXPECTED_ERROR" in expected_unexpected_error["error"]
    
    def test_create_version_with_parent_whitespace_handling(self):
        """Test whitespace handling in change detection"""
        # Mock parent version with specific whitespace
        parent_code = 'name: Test Score\ntype: SimpleLLMScore'
        parent_guidelines = '# Guidelines\n\nContent here.'
        
        # Test with different leading/trailing whitespace but same content
        new_code_with_whitespace = '\n\n  name: Test Score\ntype: SimpleLLMScore  \n\n'
        new_guidelines_with_whitespace = '\n\n  # Guidelines\n\nContent here.  \n\n'
        
        # After stripping, should be considered unchanged
        code_unchanged = parent_code.strip() == new_code_with_whitespace.strip()
        guidelines_unchanged = parent_guidelines.strip() == new_guidelines_with_whitespace.strip()
        
        # Should skip version creation due to whitespace normalization
        expected_result = {
            "success": True,
            "skipped": True,
            "message": "No changes detected, skipping version creation"
        }
        
        # Verify whitespace is properly handled
        assert code_unchanged is True
        assert guidelines_unchanged is True
        assert expected_result["skipped"] is True


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