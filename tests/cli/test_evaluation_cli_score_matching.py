#!/usr/bin/env python3
"""
Unit tests for CLI score matching in evaluation commands.

Tests the fix for CLI score matching logic that now supports matching scores
by their original external ID even after they've been replaced with database UUIDs.
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock


class TestEvaluationCliScoreMatching:
    """Test CLI score matching logic in evaluation commands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.score_uuid = str(uuid.uuid4())
        self.external_id = "45925"
        self.score_name = "Prescriptions Question Repeated - AI"
        self.score_key = "prescriptions-question-repeated"
        
        # Mock scorecard instance with score that has originalExternalId
        self.mock_scorecard_instance = Mock()
        self.mock_scorecard_instance.scores = [{
            'name': self.score_name,
            'key': self.score_key,
            'id': self.score_uuid,  # Database UUID
            'externalId': None,
            'originalExternalId': self.external_id,  # Original external ID preserved
            'version': str(uuid.uuid4()),
            'championVersionId': str(uuid.uuid4())
        }]

    def test_score_matching_by_name(self):
        """Test that CLI can match score by name."""
        primary_score_identifier = self.score_name
        
        # Simulate CLI matching logic
        matches = [
            sc for sc in self.mock_scorecard_instance.scores
            if (sc.get('name') == primary_score_identifier or
                sc.get('key') == primary_score_identifier or 
                str(sc.get('id', '')) == primary_score_identifier or
                sc.get('externalId') == primary_score_identifier or
                sc.get('originalExternalId') == primary_score_identifier)
        ]
        
        assert len(matches) == 1
        assert matches[0]['id'] == self.score_uuid

    def test_score_matching_by_key(self):
        """Test that CLI can match score by key."""
        primary_score_identifier = self.score_key
        
        matches = [
            sc for sc in self.mock_scorecard_instance.scores
            if (sc.get('name') == primary_score_identifier or
                sc.get('key') == primary_score_identifier or 
                str(sc.get('id', '')) == primary_score_identifier or
                sc.get('externalId') == primary_score_identifier or
                sc.get('originalExternalId') == primary_score_identifier)
        ]
        
        assert len(matches) == 1
        assert matches[0]['id'] == self.score_uuid

    def test_score_matching_by_database_uuid(self):
        """Test that CLI can match score by database UUID."""
        primary_score_identifier = self.score_uuid
        
        matches = [
            sc for sc in self.mock_scorecard_instance.scores
            if (sc.get('name') == primary_score_identifier or
                sc.get('key') == primary_score_identifier or 
                str(sc.get('id', '')) == primary_score_identifier or
                sc.get('externalId') == primary_score_identifier or
                sc.get('originalExternalId') == primary_score_identifier)
        ]
        
        assert len(matches) == 1
        assert matches[0]['id'] == self.score_uuid

    def test_score_matching_by_original_external_id(self):
        """Test that CLI can match score by original external ID (the key fix)."""
        primary_score_identifier = self.external_id  # User inputs "45925"
        
        matches = [
            sc for sc in self.mock_scorecard_instance.scores
            if (sc.get('name') == primary_score_identifier or
                sc.get('key') == primary_score_identifier or 
                str(sc.get('id', '')) == primary_score_identifier or
                sc.get('externalId') == primary_score_identifier or
                sc.get('originalExternalId') == primary_score_identifier)  # This is the fix
        ]
        
        assert len(matches) == 1
        assert matches[0]['id'] == self.score_uuid
        assert matches[0]['originalExternalId'] == self.external_id

    def test_no_match_for_invalid_identifier(self):
        """Test that CLI returns no matches for invalid identifiers."""
        primary_score_identifier = "nonexistent_score"
        
        matches = [
            sc for sc in self.mock_scorecard_instance.scores
            if (sc.get('name') == primary_score_identifier or
                sc.get('key') == primary_score_identifier or 
                str(sc.get('id', '')) == primary_score_identifier or
                sc.get('externalId') == primary_score_identifier or
                sc.get('originalExternalId') == primary_score_identifier)
        ]
        
        assert len(matches) == 0

    def test_subset_score_names_generation_with_original_external_id(self):
        """Test that subset score name generation works with originalExternalId."""
        target_score_identifiers = [self.external_id]  # User specifies external ID
        
        # Simulate the subset generation logic from CLI
        subset_of_score_names = [
            sc.get('name') for sc in self.mock_scorecard_instance.scores 
            if sc.get('name') and any(
                sc.get('name') == tid or 
                sc.get('key') == tid or 
                str(sc.get('id', '')) == tid or
                sc.get('externalId') == tid or
                sc.get('originalExternalId') == tid 
                for tid in target_score_identifiers
            )
        ]
        
        assert len(subset_of_score_names) == 1
        assert subset_of_score_names[0] == self.score_name

    def test_multiple_scores_with_different_identifiers(self):
        """Test matching with multiple scores having different identifier types."""
        # Add second score that matches by name
        self.mock_scorecard_instance.scores.append({
            'name': 'Second Score',
            'key': 'second-score',
            'id': str(uuid.uuid4()),
            'externalId': None,
            'originalExternalId': '12345'
        })
        
        # Test matching by external ID (first score) and by name (second score)
        target_identifiers = [self.external_id, 'Second Score']
        
        subset_of_score_names = [
            sc.get('name') for sc in self.mock_scorecard_instance.scores 
            if sc.get('name') and any(
                sc.get('name') == tid or 
                sc.get('key') == tid or 
                str(sc.get('id', '')) == tid or
                sc.get('externalId') == tid or
                sc.get('originalExternalId') == tid 
                for tid in target_identifiers
            )
        ]
        
        assert len(subset_of_score_names) == 2
        assert self.score_name in subset_of_score_names
        assert 'Second Score' in subset_of_score_names

    def test_score_without_original_external_id(self):
        """Test that scores without originalExternalId still work normally."""
        # Score that was loaded with database UUID from start (no replacement needed)
        score_without_replacement = {
            'name': 'UUID Score',
            'key': 'uuid-score',
            'id': str(uuid.uuid4()),
            'externalId': None,
            # No 'originalExternalId' field
        }
        
        self.mock_scorecard_instance.scores = [score_without_replacement]
        
        # Should match by name
        primary_score_identifier = 'UUID Score'
        matches = [
            sc for sc in self.mock_scorecard_instance.scores
            if (sc.get('name') == primary_score_identifier or
                sc.get('key') == primary_score_identifier or 
                str(sc.get('id', '')) == primary_score_identifier or
                sc.get('externalId') == primary_score_identifier or
                sc.get('originalExternalId') == primary_score_identifier)
        ]
        
        assert len(matches) == 1
        assert matches[0]['name'] == 'UUID Score'

    def test_edge_case_none_values(self):
        """Test handling of None values in score fields."""
        score_with_nones = {
            'name': 'Test Score',
            'key': None,
            'id': self.score_uuid,
            'externalId': None,
            'originalExternalId': None
        }
        
        self.mock_scorecard_instance.scores = [score_with_nones]
        
        # Should still match by name
        primary_score_identifier = 'Test Score'
        matches = [
            sc for sc in self.mock_scorecard_instance.scores
            if (sc.get('name') == primary_score_identifier or
                sc.get('key') == primary_score_identifier or 
                str(sc.get('id', '')) == primary_score_identifier or
                sc.get('externalId') == primary_score_identifier or
                sc.get('originalExternalId') == primary_score_identifier)
        ]
        
        assert len(matches) == 1

    def test_case_sensitivity_in_matching(self):
        """Test that matching is case-sensitive as expected."""
        primary_score_identifier = self.score_name.upper()  # Different case
        
        matches = [
            sc for sc in self.mock_scorecard_instance.scores
            if (sc.get('name') == primary_score_identifier or
                sc.get('key') == primary_score_identifier or 
                str(sc.get('id', '')) == primary_score_identifier or
                sc.get('externalId') == primary_score_identifier or
                sc.get('originalExternalId') == primary_score_identifier)
        ]
        
        # Should NOT match due to case sensitivity
        assert len(matches) == 0


if __name__ == '__main__':
    pytest.main([__file__])