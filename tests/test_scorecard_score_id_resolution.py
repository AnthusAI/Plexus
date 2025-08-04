#!/usr/bin/env python3
"""
Unit tests for Scorecard Score ID resolution functionality.

Tests the fix for the issue where scorecard API loading was using external IDs
instead of database UUIDs, causing evaluation records to have invalid Score IDs
for Amplify Gen2 schema associations.
"""

import pytest
import json
import uuid
from unittest.mock import Mock, patch
from plexus.Scorecard import Scorecard


class TestScorecardScoreIdResolution:
    """Test Score ID resolution in scorecard API loading."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.scorecard_id = str(uuid.uuid4())
        self.score_uuid = str(uuid.uuid4())
        self.external_id = "45925"
        self.champion_version_id = str(uuid.uuid4())
        
        # Mock API data structure
        self.api_data = {
            'id': self.scorecard_id,
            'name': 'Test Scorecard',
            'key': 'test_scorecard',
            'sections': {
                'items': [{
                    'id': 'section-1',
                    'name': 'Test Section',
                    'scores': {
                        'items': [{
                            'id': self.score_uuid,  # Database UUID from API
                            'name': 'Test Score',
                            'key': 'test_score',
                            'externalId': None,
                            'championVersionId': self.champion_version_id
                        }]
                    }
                }]
            }
        }
        
        # Mock score config with external ID (as would come from YAML)
        self.scores_config = [{
            'name': 'Test Score',
            'key': 'test_score', 
            'id': self.external_id,  # External ID from YAML config
            'class': 'LangGraphScore',
            'description': 'Test score description'
        }]

    def test_initialize_from_api_data_replaces_external_id_with_uuid(self):
        """Test that initialize_from_api_data replaces external IDs with database UUIDs."""
        # Create scorecard instance
        scorecard = Scorecard(
            scorecard=self.scorecard_id,
            api_data=self.api_data,
            scores_config=self.scores_config
        )
        
        # Verify the score config was updated with database UUID
        assert len(scorecard.scores) == 1
        score_config = scorecard.scores[0]
        
        # Should have database UUID, not external ID
        assert score_config['id'] == self.score_uuid
        assert score_config['name'] == 'Test Score'
        
        # Should preserve original external ID for matching
        assert score_config['originalExternalId'] == self.external_id
        
        # Should have version info
        assert score_config['version'] == self.champion_version_id

    def test_create_instance_from_api_data_handles_id_replacement(self):
        """Test that create_instance_from_api_data properly replaces external IDs."""
        scorecard = Scorecard.create_instance_from_api_data(
            scorecard_id=self.scorecard_id,
            api_data=self.api_data,
            scores_config=self.scores_config.copy()  # Copy to avoid modifying original
        )
        
        # Verify the score was registered with database UUID
        assert len(scorecard.scores) == 1
        score_config = scorecard.scores[0]
        
        # Should use database UUID from API
        assert score_config['id'] == self.score_uuid
        
        # Should preserve original external ID
        assert score_config['originalExternalId'] == self.external_id

    def test_score_matching_by_original_external_id(self):
        """Test that scores can be matched by their original external ID."""
        scorecard = Scorecard(
            scorecard=self.scorecard_id,
            api_data=self.api_data,
            scores_config=self.scores_config
        )
        
        score_config = scorecard.scores[0]
        
        # Should match by original external ID
        assert score_config.get('originalExternalId') == self.external_id
        
        # Should have proper database UUID
        assert score_config.get('id') == self.score_uuid
        
        # Simulate CLI matching logic
        primary_score_identifier = self.external_id
        matches = [
            sc for sc in scorecard.scores 
            if (sc.get('name') == primary_score_identifier or
                sc.get('key') == primary_score_identifier or 
                str(sc.get('id', '')) == primary_score_identifier or
                sc.get('externalId') == primary_score_identifier or
                sc.get('originalExternalId') == primary_score_identifier)
        ]
        
        # Should find exactly one match via originalExternalId
        assert len(matches) == 1
        assert matches[0]['id'] == self.score_uuid

    def test_no_replacement_when_ids_already_match(self):
        """Test that no replacement occurs when API ID already matches config ID."""
        # Score config already has database UUID
        scores_config_with_uuid = [{
            'name': 'Test Score',
            'key': 'test_score',
            'id': self.score_uuid,  # Already has database UUID
            'class': 'LangGraphScore'
        }]
        
        scorecard = Scorecard(
            scorecard=self.scorecard_id,
            api_data=self.api_data,
            scores_config=scores_config_with_uuid
        )
        
        score_config = scorecard.scores[0]
        
        # Should keep the UUID
        assert score_config['id'] == self.score_uuid
        
        # Should NOT have originalExternalId since no replacement occurred
        assert 'originalExternalId' not in score_config

    def test_multiple_scores_id_replacement(self):
        """Test ID replacement works correctly with multiple scores."""
        # Add second score to API data
        second_score_uuid = str(uuid.uuid4())
        second_external_id = "12345"
        
        self.api_data['sections']['items'][0]['scores']['items'].append({
            'id': second_score_uuid,
            'name': 'Second Score',
            'key': 'second_score',
            'externalId': None,
            'championVersionId': str(uuid.uuid4())
        })
        
        # Add second score to config
        scores_config_multi = self.scores_config + [{
            'name': 'Second Score',
            'key': 'second_score',
            'id': second_external_id,  # External ID
            'class': 'LangGraphScore'
        }]
        
        scorecard = Scorecard(
            scorecard=self.scorecard_id,
            api_data=self.api_data,
            scores_config=scores_config_multi
        )
        
        # Should have both scores with proper UUIDs
        assert len(scorecard.scores) == 2
        
        # First score
        first_score = next(sc for sc in scorecard.scores if sc['name'] == 'Test Score')
        assert first_score['id'] == self.score_uuid
        assert first_score['originalExternalId'] == self.external_id
        
        # Second score  
        second_score = next(sc for sc in scorecard.scores if sc['name'] == 'Second Score')
        assert second_score['id'] == second_score_uuid
        assert second_score['originalExternalId'] == second_external_id

    def test_string_yaml_config_parsing_and_id_replacement(self):
        """Test that string YAML configurations are parsed and IDs are replaced correctly."""
        yaml_string_config = f'''
name: Test Score
key: test_score
id: {self.external_id}
class: LangGraphScore
description: Test score from YAML string
'''
        
        scores_config_yaml = [yaml_string_config]
        
        scorecard = Scorecard(
            scorecard=self.scorecard_id,
            api_data=self.api_data,
            scores_config=scores_config_yaml
        )
        
        # Should parse YAML and replace ID
        assert len(scorecard.scores) == 1
        score_config = scorecard.scores[0]
        
        assert score_config['id'] == self.score_uuid
        assert score_config['originalExternalId'] == self.external_id
        assert score_config['name'] == 'Test Score'

    def test_missing_score_in_api_data(self):
        """Test behavior when score config has no matching score in API data."""
        # Score config for non-existent score
        scores_config_missing = [{
            'name': 'Missing Score',
            'key': 'missing_score',
            'id': '99999',
            'class': 'LangGraphScore'
        }]
        
        scorecard = Scorecard(
            scorecard=self.scorecard_id,
            api_data=self.api_data,
            scores_config=scores_config_missing
        )
        
        # Score should remain unchanged since no API match found
        assert len(scorecard.scores) == 1
        score_config = scorecard.scores[0]
        
        assert score_config['id'] == '99999'  # Original external ID preserved
        assert 'originalExternalId' not in score_config  # No replacement occurred

    def test_evaluation_score_id_validation(self):
        """Test that final score IDs are valid UUIDs for evaluation records."""
        scorecard = Scorecard(
            scorecard=self.scorecard_id,
            api_data=self.api_data,
            scores_config=self.scores_config
        )
        
        score_config = scorecard.scores[0]
        score_id = score_config['id']
        
        # Should be a valid UUID with hyphens (for Amplify Gen2 schema association)
        assert isinstance(score_id, str)
        assert '-' in score_id
        assert len(score_id) == 36  # Standard UUID length
        
        # Should be parseable as UUID
        try:
            parsed_uuid = uuid.UUID(score_id)
            assert str(parsed_uuid) == score_id
        except ValueError:
            pytest.fail(f"Score ID '{score_id}' is not a valid UUID")


if __name__ == '__main__':
    pytest.main([__file__])