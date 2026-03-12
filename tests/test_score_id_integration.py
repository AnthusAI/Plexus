#!/usr/bin/env python3
"""
Integration test for the Score ID resolution fix.

Tests the complete flow from scorecard loading with external IDs through
to CLI evaluation command processing with proper Score ID resolution.
"""

import pytest
import uuid
from unittest.mock import Mock, patch
from plexus.Scorecard import Scorecard


class TestScoreIdIntegration:
    """Integration test for Score ID resolution across the system."""
    
    def setup_method(self):
        """Set up integration test fixtures."""
        self.scorecard_id = str(uuid.uuid4())
        self.score_uuid = str(uuid.uuid4())
        self.external_id = "45925"
        self.champion_version_id = str(uuid.uuid4())
        
        # Complete API data as would be returned by dashboard API
        self.complete_api_data = {
            'id': self.scorecard_id,
            'name': 'Selectquote - MEL HRA v1.0',
            'key': 'selectquote_mel_hra',
            'externalId': '1461',
            'sections': {
                'items': [{
                    'id': 'section-uuid-1',
                    'name': 'Health Questions',
                    'scores': {
                        'items': [{
                            'id': self.score_uuid,
                            'name': 'Prescriptions Question Repeated - AI',
                            'key': 'prescriptions-question-repeated',
                            'externalId': None,
                            'championVersionId': self.champion_version_id,
                            'type': 'LangGraphScore',
                            'description': 'Detects when prescription questions are repeated'
                        }]
                    }
                }]
            }
        }
        
        # YAML configuration as would be loaded from API
        self.yaml_config_string = f"""
name: Prescriptions Question Repeated - AI
key: prescriptions-question-repeated
id: {self.external_id}
class: LangGraphScore
model_provider: openai
model_name: gpt-4o-mini
description: Detects when the agent asks about prescriptions multiple times
graph:
  - name: classifier
    type: YesOrNoClassifier
    prompt: |
      Does the agent ask about prescriptions more than once in this conversation?
      Look for repeated questions about medications, drugs, or prescriptions.
output:
  type: classification
  classes: ["Yes", "No"]
data:
  class: CallCriteriaDBCache
  queries:
    - scorecard_id: 1461
      number: 10
"""

    def test_end_to_end_score_id_resolution(self):
        """Test complete Score ID resolution from API loading to CLI matching."""
        
        # Step 1: Create scorecard with YAML string config (simulating API response)
        scores_config = [self.yaml_config_string]
        
        scorecard = Scorecard.create_instance_from_api_data(
            scorecard_id=self.scorecard_id,
            api_data=self.complete_api_data,
            scores_config=scores_config
        )
        
        # Step 2: Verify scorecard initialization replaced external ID with UUID
        assert len(scorecard.scores) == 1
        score_config = scorecard.scores[0]
        
        # Should use database UUID from API
        assert score_config['id'] == self.score_uuid
        assert score_config['name'] == 'Prescriptions Question Repeated - AI'
        assert score_config['originalExternalId'] == self.external_id
        
        # Step 3: Simulate CLI evaluation command processing
        # User runs: plexus evaluate accuracy --scorecard selectquote_mel_hra --score 45925
        primary_score_identifier = self.external_id  # CLI input "45925"
        
        # Step 4: CLI matching logic (as implemented in EvaluationCommands.py)
        matched_scores = []
        for sc_config in scorecard.scores:
            if (sc_config.get('name') == primary_score_identifier or
                sc_config.get('key') == primary_score_identifier or 
                str(sc_config.get('id', '')) == primary_score_identifier or
                sc_config.get('externalId') == primary_score_identifier or
                sc_config.get('originalExternalId') == primary_score_identifier):
                matched_scores.append(sc_config)
                break
        
        # Step 5: Verify CLI found the score and extracted correct UUID
        assert len(matched_scores) == 1
        matched_score = matched_scores[0]
        
        score_id_for_eval = matched_score.get('id')
        score_version_id_for_eval = matched_score.get('version') or matched_score.get('championVersionId')
        
        # Step 6: Verify IDs are correct for evaluation record
        assert score_id_for_eval == self.score_uuid  # Database UUID, not external ID
        assert score_version_id_for_eval == self.champion_version_id
        
        # Step 7: Verify Score ID is valid for Amplify Gen2 schema association
        assert isinstance(score_id_for_eval, str)
        assert '-' in score_id_for_eval  # UUID format with hyphens
        assert len(score_id_for_eval) == 36  # Standard UUID length
        
        # Should be parseable as UUID
        try:
            parsed_uuid = uuid.UUID(score_id_for_eval)
            assert str(parsed_uuid) == score_id_for_eval
        except ValueError:
            pytest.fail(f"Score ID '{score_id_for_eval}' is not a valid UUID")

    def test_evaluation_record_compatibility(self):
        """Test that resolved Score IDs are compatible with evaluation records."""
        scorecard = Scorecard.create_instance_from_api_data(
            scorecard_id=self.scorecard_id,
            api_data=self.complete_api_data,
            scores_config=[self.yaml_config_string]
        )
        
        score_config = scorecard.scores[0]
        score_id = score_config['id']
        
        # Simulate evaluation record creation (as in EvaluationCommands.py)
        update_fields = {
            'status': 'COMPLETED',
            'accuracy': 85.5,
            'scoreId': score_id,  # This must be database UUID
            'scoreVersionId': score_config.get('championVersionId')
        }
        
        # Verify Score ID format is correct for database
        assert isinstance(update_fields['scoreId'], str)
        assert update_fields['scoreId'] == self.score_uuid
        
        # Verify Score ID passes validation that was previously failing
        # (should be UUID with hyphens, not numeric external ID)
        score_id_str = str(update_fields['scoreId'])
        assert score_id_str.count('-') == 4  # UUID has 4 hyphens
        assert not score_id_str.isdigit()  # Should NOT be numeric like "45925"

    def test_multiple_cli_invocation_patterns(self):
        """Test different ways CLI might be invoked work correctly."""
        scorecard = Scorecard.create_instance_from_api_data(
            scorecard_id=self.scorecard_id,
            api_data=self.complete_api_data,
            scores_config=[self.yaml_config_string]
        )
        
        score_config = scorecard.scores[0]
        
        # Test different CLI invocation patterns
        test_patterns = [
            # By external ID (original problem case)
            self.external_id,
            # By name
            'Prescriptions Question Repeated - AI',
            # By key
            'prescriptions-question-repeated', 
            # By database UUID
            self.score_uuid
        ]
        
        for pattern in test_patterns:
            matches = [
                sc for sc in scorecard.scores
                if (sc.get('name') == pattern or
                    sc.get('key') == pattern or 
                    str(sc.get('id', '')) == pattern or
                    sc.get('externalId') == pattern or
                    sc.get('originalExternalId') == pattern)
            ]
            
            # All patterns should find the same score
            assert len(matches) == 1, f"Pattern '{pattern}' should match exactly one score"
            assert matches[0]['id'] == self.score_uuid, f"Pattern '{pattern}' should resolve to correct UUID"

    def test_backward_compatibility_preservation(self):
        """Test that existing functionality still works after the fix."""
        # Test scorecard without originalExternalId (no replacement needed)
        api_data_with_uuid = self.complete_api_data.copy()
        
        # Config already has database UUID (no replacement scenario)
        uuid_config_string = f"""
name: Prescriptions Question Repeated - AI
key: prescriptions-question-repeated
id: {self.score_uuid}
class: LangGraphScore
description: Score already has correct UUID
"""
        
        scorecard = Scorecard.create_instance_from_api_data(
            scorecard_id=self.scorecard_id,
            api_data=api_data_with_uuid,
            scores_config=[uuid_config_string]
        )
        
        score_config = scorecard.scores[0]
        
        # Should keep the UUID as-is
        assert score_config['id'] == self.score_uuid
        
        # Should NOT have originalExternalId since no replacement occurred
        assert 'originalExternalId' not in score_config
        
        # CLI matching should still work by name and UUID
        name_matches = [
            sc for sc in scorecard.scores
            if sc.get('name') == 'Prescriptions Question Repeated - AI'
        ]
        assert len(name_matches) == 1
        
        uuid_matches = [
            sc for sc in scorecard.scores
            if str(sc.get('id', '')) == self.score_uuid
        ]
        assert len(uuid_matches) == 1


if __name__ == '__main__':
    pytest.main([__file__])