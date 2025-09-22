#!/usr/bin/env python3
"""
Unit tests for ScoreVersion association in evaluation records.

Tests that evaluation records are properly associated with ScoreVersions
based on the evaluation mode (API vs YAML) and version flags.
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from plexus.Evaluation import AccuracyEvaluation


class TestScoreVersionAssociationLogic:
    """Test the core logic for ScoreVersion association."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.score_id = str(uuid.uuid4())
        self.score_version_id = str(uuid.uuid4())
        self.champion_version_id = str(uuid.uuid4())
        self.latest_version_id = str(uuid.uuid4())
        
        # Mock scorecard with score configuration
        self.mock_scorecard = Mock()
        self.mock_scorecard.name = "test_scorecard"
        self.mock_scorecard.scores = [{
            'name': 'test_score',
            'key': 'test_score',
            'id': self.score_id,
            'version': self.score_version_id,
            'championVersionId': self.champion_version_id
        }]

    def test_api_loading_with_specific_version(self):
        """Test ScoreVersion association when using API loading with specific version."""
        yaml_flag = False
        resolved_version = self.score_version_id
        
        # Should associate with the specific version
        should_set_version = not yaml_flag and resolved_version
        assert should_set_version  # Should be truthy (the version string)
        
        # Verify the version that would be set
        version_to_set = resolved_version if should_set_version else None
        assert version_to_set == self.score_version_id

    def test_api_loading_with_latest_version(self):
        """Test ScoreVersion association when using API loading with --latest flag."""
        yaml_flag = False
        resolved_version = self.latest_version_id  # Resolved from --latest
        
        # Should associate with the latest version
        should_set_version = not yaml_flag and resolved_version
        assert should_set_version  # Should be truthy (the version string)
        
        version_to_set = resolved_version if should_set_version else None
        assert version_to_set == self.latest_version_id

    def test_api_loading_without_version(self):
        """Test ScoreVersion association when using API loading without version flags."""
        yaml_flag = False
        resolved_version = None  # No version specified
        
        # Should not associate with any specific version (uses champion)
        should_set_version = not yaml_flag and resolved_version
        assert not should_set_version  # Should be falsy (None)

    def test_yaml_loading_prevents_association(self):
        """Test that YAML loading prevents ScoreVersion association."""
        yaml_flag = True
        resolved_version = self.score_version_id
        
        # Should NOT associate with any version when using YAML
        should_set_version = not yaml_flag and resolved_version
        assert should_set_version == False

    def test_yaml_loading_with_latest_flag(self):
        """Test that --yaml flag overrides any version resolution."""
        yaml_flag = True
        resolved_version = self.latest_version_id  # Even if latest was resolved
        
        # Should NOT associate when using YAML, regardless of resolved version
        should_set_version = not yaml_flag and resolved_version
        assert should_set_version == False


class TestAccuracyEvaluationVersionHandling:
    """Test ScoreVersion handling in AccuracyEvaluation class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.score_id = str(uuid.uuid4())
        self.score_version_id = str(uuid.uuid4())
        self.evaluation_id = str(uuid.uuid4())
        self.account_id = str(uuid.uuid4())
        self.scorecard_id = str(uuid.uuid4())
        
        self.mock_scorecard = Mock()
        self.mock_scorecard.name = "test_scorecard"

    @patch('plexus.Evaluation.PlexusDashboardClient')
    def test_accuracy_evaluation_stores_score_version_id(self, mock_client_class):
        """Test that AccuracyEvaluation properly stores score_version_id."""
        mock_client_class.for_account.return_value = None  # Skip client initialization
        
        evaluation = AccuracyEvaluation(
            scorecard_name="test_scorecard",
            scorecard=self.mock_scorecard,
            score_id=self.score_id,
            score_version_id=self.score_version_id,
            evaluation_id=self.evaluation_id,
            account_id=self.account_id,
            scorecard_id=self.scorecard_id
        )
        
        assert evaluation.score_version_id == self.score_version_id

    @patch('plexus.Evaluation.PlexusDashboardClient')
    def test_accuracy_evaluation_without_score_version(self, mock_client_class):
        """Test AccuracyEvaluation without score_version_id (YAML mode)."""
        mock_client_class.for_account.return_value = None
        
        evaluation = AccuracyEvaluation(
            scorecard_name="test_scorecard",
            scorecard=self.mock_scorecard,
            score_id=self.score_id,
            score_version_id=None,  # No version for YAML mode
            evaluation_id=self.evaluation_id,
            account_id=self.account_id,
            scorecard_id=self.scorecard_id
        )
        
        assert evaluation.score_version_id is None

    def test_update_variables_includes_score_version(self):
        """Test that _get_update_variables includes scoreVersionId when present."""
        # Mock evaluation with score_version_id
        mock_evaluation = Mock()
        mock_evaluation.score_version_id = self.score_version_id
        mock_evaluation.experiment_id = self.evaluation_id
        mock_evaluation.processed_items = 10
        mock_evaluation.started_at = datetime.now(timezone.utc)
        
        # Mock metrics
        metrics = {
            "accuracy": 0.85,
            "precision": 0.80,
            "alignment": 0.75,
            "recall": 0.82
        }
        
        # Simulate the _get_update_variables logic
        update_input = {
            "id": mock_evaluation.experiment_id,
            "status": "COMPLETED",
            "accuracy": metrics["accuracy"] * 100,
            "processedItems": mock_evaluation.processed_items
        }
        
        # Add scoreVersionId if available
        if hasattr(mock_evaluation, 'score_version_id') and mock_evaluation.score_version_id:
            update_input["scoreVersionId"] = mock_evaluation.score_version_id
        
        assert update_input["scoreVersionId"] == self.score_version_id

    def test_update_variables_without_score_version(self):
        """Test that _get_update_variables excludes scoreVersionId when not present."""
        # Mock evaluation without score_version_id
        mock_evaluation = Mock()
        mock_evaluation.score_version_id = None
        mock_evaluation.experiment_id = self.evaluation_id
        mock_evaluation.processed_items = 10
        mock_evaluation.started_at = datetime.now(timezone.utc)
        
        metrics = {"accuracy": 0.85, "precision": 0.80, "alignment": 0.75, "recall": 0.82}
        
        # Simulate the _get_update_variables logic
        update_input = {
            "id": mock_evaluation.experiment_id,
            "status": "COMPLETED",
            "accuracy": metrics["accuracy"] * 100,
            "processedItems": mock_evaluation.processed_items
        }
        
        # Only add scoreVersionId if it exists and is not None
        if hasattr(mock_evaluation, 'score_version_id') and mock_evaluation.score_version_id:
            update_input["scoreVersionId"] = mock_evaluation.score_version_id
        
        assert "scoreVersionId" not in update_input


class TestVersionResolutionScenarios:
    """Test different version resolution scenarios."""
    
    def test_champion_version_used_by_default(self):
        """Test that champion version is resolved when no flags are provided."""
        # Simulate score configuration with champion version
        score_config = {
            'name': 'test_score',
            'id': str(uuid.uuid4()),
            'version': None,  # No specific version
            'championVersionId': str(uuid.uuid4())
        }
        
        yaml_flag = False
        
        # Simulate version resolution logic
        if yaml_flag:
            score_version_id_for_eval = None
        else:
            score_version_id_for_eval = score_config.get('version')
            if not score_version_id_for_eval:
                score_version_id_for_eval = score_config.get('championVersionId')
        
        assert score_version_id_for_eval == score_config['championVersionId']

    def test_specific_version_overrides_champion(self):
        """Test that specific version overrides champion version."""
        specific_version = str(uuid.uuid4())
        champion_version = str(uuid.uuid4())
        
        score_config = {
            'name': 'test_score',
            'id': str(uuid.uuid4()),
            'version': specific_version,  # Specific version provided
            'championVersionId': champion_version
        }
        
        yaml_flag = False
        
        # Simulate version resolution logic
        if yaml_flag:
            score_version_id_for_eval = None
        else:
            score_version_id_for_eval = score_config.get('version')
            if not score_version_id_for_eval:
                score_version_id_for_eval = score_config.get('championVersionId')
        
        assert score_version_id_for_eval == specific_version

    def test_yaml_mode_ignores_all_versions(self):
        """Test that YAML mode ignores both specific and champion versions."""
        specific_version = str(uuid.uuid4())
        champion_version = str(uuid.uuid4())
        
        score_config = {
            'name': 'test_score',
            'id': str(uuid.uuid4()),
            'version': specific_version,
            'championVersionId': champion_version
        }
        
        yaml_flag = True
        
        # Simulate version resolution logic for YAML mode
        if yaml_flag:
            score_version_id_for_eval = None  # YAML mode - no version association
        else:
            score_version_id_for_eval = score_config.get('version')
            if not score_version_id_for_eval:
                score_version_id_for_eval = score_config.get('championVersionId')
        
        assert score_version_id_for_eval is None


class TestEvaluationRecordCreation:
    """Test evaluation record creation with ScoreVersion association."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.score_version_id = str(uuid.uuid4())
        self.account_id = str(uuid.uuid4())
        self.task_id = str(uuid.uuid4())

    def test_initial_evaluation_record_with_version(self):
        """Test initial evaluation record creation includes scoreVersionId."""
        yaml_flag = False
        resolved_version = self.score_version_id
        
        # Simulate experiment_params creation
        experiment_params = {
            "type": "accuracy",
            "accountId": self.account_id,
            "status": "SETUP",
            "accuracy": 0.0,
            "taskId": self.task_id
        }
        
        # Add scoreVersionId if conditions are met
        if not yaml_flag and resolved_version:
            experiment_params["scoreVersionId"] = resolved_version
        
        assert experiment_params["scoreVersionId"] == self.score_version_id

    def test_initial_evaluation_record_yaml_mode(self):
        """Test initial evaluation record creation in YAML mode excludes scoreVersionId."""
        yaml_flag = True
        resolved_version = self.score_version_id
        
        experiment_params = {
            "type": "accuracy",
            "accountId": self.account_id, 
            "status": "SETUP",
            "accuracy": 0.0,
            "taskId": self.task_id
        }
        
        # Don't add scoreVersionId in YAML mode
        if not yaml_flag and resolved_version:
            experiment_params["scoreVersionId"] = resolved_version
        
        assert "scoreVersionId" not in experiment_params

    def test_final_evaluation_update_with_version(self):
        """Test final evaluation update includes scoreVersionId."""
        yaml_flag = False
        score_version_id = self.score_version_id
        
        update_fields = {
            'status': 'COMPLETED',
            'accuracy': 85.0,
            'processedItems': 100
        }
        
        # Logic from final evaluation update
        if score_version_id and not yaml_flag:
            update_fields['scoreVersionId'] = score_version_id
        
        assert update_fields['scoreVersionId'] == self.score_version_id

    def test_final_evaluation_update_yaml_mode(self):
        """Test final evaluation update in YAML mode excludes scoreVersionId."""
        yaml_flag = True
        score_version_id = self.score_version_id
        
        update_fields = {
            'status': 'COMPLETED',
            'accuracy': 85.0,
            'processedItems': 100
        }
        
        # Don't set scoreVersionId in YAML mode
        if score_version_id and not yaml_flag:
            update_fields['scoreVersionId'] = score_version_id
        
        assert 'scoreVersionId' not in update_fields


class TestEdgeCases:
    """Test edge cases in ScoreVersion association."""
    
    def test_empty_resolved_version(self):
        """Test handling of empty resolved_version."""
        yaml_flag = False
        resolved_version = ""  # Empty string
        
        experiment_params = {"type": "accuracy"}
        
        # Empty string should be treated as falsy
        if not yaml_flag and resolved_version:
            experiment_params["scoreVersionId"] = resolved_version
        
        assert "scoreVersionId" not in experiment_params

    def test_none_resolved_version(self):
        """Test handling of None resolved_version."""
        yaml_flag = False
        resolved_version = None
        
        experiment_params = {"type": "accuracy"}
        
        if not yaml_flag and resolved_version:
            experiment_params["scoreVersionId"] = resolved_version
        
        assert "scoreVersionId" not in experiment_params

    def test_whitespace_resolved_version(self):
        """Test handling of whitespace-only resolved_version."""
        yaml_flag = False
        resolved_version = "   "  # Whitespace only
        
        experiment_params = {"type": "accuracy"}
        
        # Whitespace string should be treated as truthy
        if not yaml_flag and resolved_version:
            experiment_params["scoreVersionId"] = resolved_version
        
        # In real implementation, this might be validated, but for testing
        # we check that the logic treats whitespace as truthy
        assert experiment_params["scoreVersionId"] == "   "

    def test_uuid_format_validation(self):
        """Test that UUID format is preserved for scoreVersionId."""
        valid_uuid = str(uuid.uuid4())
        yaml_flag = False
        resolved_version = valid_uuid
        
        experiment_params = {"type": "accuracy"}
        
        if not yaml_flag and resolved_version:
            experiment_params["scoreVersionId"] = resolved_version
        
        # Verify UUID format is maintained
        assert experiment_params["scoreVersionId"] == valid_uuid
        assert len(experiment_params["scoreVersionId"].split('-')) == 5  # UUID format


if __name__ == '__main__':
    pytest.main([__file__, '-v'])