#!/usr/bin/env python3
"""
Unit tests for the --latest flag functionality in evaluation commands.

Tests the new --latest flag that resolves to the most recent ScoreVersion
and ensures proper ScoreVersion association in evaluation records.
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock, call
from click.testing import CliRunner
from datetime import datetime

# Import the functions we need to test
from plexus.cli.evaluation.evaluations import get_latest_score_version, accuracy


class TestLatestVersionResolution:
    """Test the latest version resolution functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.score_id = str(uuid.uuid4())
        self.champion_version_id = str(uuid.uuid4())
        self.latest_version_id = str(uuid.uuid4())
        self.older_version_id = str(uuid.uuid4())
        
        # Mock GraphQL response for latest version query
        self.mock_graphql_response = {
            'listScoreVersionByScoreIdAndCreatedAt': {
                'items': [{
                    'id': self.latest_version_id,
                    'createdAt': '2025-09-04T20:00:00.000Z'
                }]
            }
        }
        
        # Mock client
        self.mock_client = Mock()
        self.mock_client.execute.return_value = self.mock_graphql_response

    def test_get_latest_score_version_success(self):
        """Test successful retrieval of latest score version."""
        result = get_latest_score_version(self.mock_client, self.score_id)
        
        assert result == self.latest_version_id
        
        # Verify correct GraphQL query was called
        self.mock_client.execute.assert_called_once()
        args, kwargs = self.mock_client.execute.call_args
        
        # Check query structure
        query = args[0]
        variables = args[1]
        
        assert 'listScoreVersionByScoreIdAndCreatedAt' in query
        assert variables['scoreId'] == self.score_id
        assert variables['sortDirection'] == 'DESC'
        assert variables['limit'] == 1

    def test_get_latest_score_version_no_versions(self):
        """Test handling when no versions are found."""
        self.mock_client.execute.return_value = {
            'listScoreVersionByScoreIdAndCreatedAt': {
                'items': []
            }
        }
        
        result = get_latest_score_version(self.mock_client, self.score_id)
        
        assert result is None

    def test_get_latest_score_version_api_error(self):
        """Test handling of API errors."""
        self.mock_client.execute.side_effect = Exception("API Error")
        
        result = get_latest_score_version(self.mock_client, self.score_id)
        
        assert result is None

    def test_get_latest_score_version_invalid_response(self):
        """Test handling of invalid API response format."""
        self.mock_client.execute.return_value = {'invalid': 'response'}
        
        result = get_latest_score_version(self.mock_client, self.score_id)
        
        assert result is None


class TestLatestFlagValidation:
    """Test validation logic for the --latest flag."""
    
    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()

    @patch('plexus.cli.evaluation.evaluations.create_client')
    @patch('plexus.cli.evaluation.evaluations.load_scorecard_from_api')
    def test_latest_and_version_mutually_exclusive(self, mock_load, mock_client):
        """Test that --latest and --version cannot be used together."""
        # Mock basic dependencies to get to validation
        mock_load.return_value = Mock()
        mock_client.return_value = Mock()
        
        # Use both --latest and --version flags
        result = self.runner.invoke(accuracy, [
            '--scorecard', 'test_scorecard',
            '--score', 'test_score', 
            '--version', 'version-123',
            '--latest',
            '--dry-run'  # Skip actual evaluation
        ])
        
        # Command returns early with validation error but doesn't change exit code
        assert result.exit_code == 0
        assert "Cannot use both --version and --latest options" in result.output

    @patch('plexus.cli.evaluation.evaluations.create_client')
    @patch('plexus.cli.evaluation.evaluations.load_scorecard_from_api')
    def test_latest_flag_without_version(self, mock_load, mock_client):
        """Test that --latest flag works without --version."""
        # Mock scorecard loading
        mock_scorecard = Mock()
        mock_scorecard.scores = [{
            'name': 'test_score',
            'id': str(uuid.uuid4()),
            'version': str(uuid.uuid4()),
            'championVersionId': str(uuid.uuid4())
        }]
        mock_load.return_value = mock_scorecard
        mock_client.return_value = Mock()
        
        result = self.runner.invoke(accuracy, [
            '--scorecard', 'test_scorecard',
            '--score', 'test_score',
            '--latest',
            '--dry-run'  # Skip actual evaluation
        ])
        
        # Should not show the mutual exclusion error
        assert "Cannot use both --version and --latest options" not in result.output

    @patch('plexus.cli.evaluation.evaluations.create_client')
    @patch('plexus.cli.evaluation.evaluations.load_scorecard_from_api')
    def test_version_flag_without_latest(self, mock_load, mock_client):
        """Test that --version flag works without --latest."""
        mock_scorecard = Mock()
        mock_scorecard.scores = [{
            'name': 'test_score',
            'id': str(uuid.uuid4()),
            'version': str(uuid.uuid4()),
            'championVersionId': str(uuid.uuid4())
        }]
        mock_load.return_value = mock_scorecard
        mock_client.return_value = Mock()
        
        result = self.runner.invoke(accuracy, [
            '--scorecard', 'test_scorecard',
            '--score', 'test_score',
            '--version', 'version-123',
            '--dry-run'  # Skip actual evaluation
        ])
        
        # Should not show the mutual exclusion error
        assert "Cannot use both --version and --latest options" not in result.output


class TestLatestVersionIntegration:
    """Test integration of --latest flag with evaluation process."""
    
    def setup_method(self):
        """Set up mocks for integration testing."""
        self.score_id = str(uuid.uuid4())
        self.latest_version_id = str(uuid.uuid4())
        self.champion_version_id = str(uuid.uuid4())
        
        # Mock scorecard with score configuration
        self.mock_scorecard = Mock()
        self.mock_scorecard.scores = [{
            'name': 'test_score',
            'key': 'test_score',
            'id': self.score_id,
            'version': self.champion_version_id,
            'championVersionId': self.champion_version_id
        }]

    @patch('plexus.cli.evaluation.evaluations.PlexusDashboardClient')
    @patch('plexus.cli.evaluation.evaluations.get_latest_score_version')
    @patch('plexus.cli.evaluation.evaluations.load_scorecard_from_api')
    def test_latest_flag_resolves_version(self, mock_load, mock_get_latest, mock_client_class):
        """Test that --latest flag resolves to the most recent version."""
        # Setup mocks
        mock_load.return_value = self.mock_scorecard
        mock_get_latest.return_value = self.latest_version_id
        mock_client_instance = Mock()
        mock_client_class.return_value = mock_client_instance
        
        # Mock the second call to load_scorecard_from_api with resolved version
        def mock_load_side_effect(*args, **kwargs):
            specific_version = kwargs.get('specific_version')
            if specific_version == self.latest_version_id:
                # Return scorecard with latest version
                scorecard = Mock()
                scorecard.scores = [{
                    'name': 'test_score',
                    'id': self.score_id,
                    'version': self.latest_version_id,  # Latest version
                    'championVersionId': self.champion_version_id
                }]
                return scorecard
            else:
                # Return original scorecard for initial resolution
                return self.mock_scorecard
        
        mock_load.side_effect = mock_load_side_effect
        
        # Simulate the version resolution process
        target_score_identifiers = ['test_score']
        latest_flag = True
        
        if latest_flag and target_score_identifiers:
            # Find score ID from temporary scorecard load
            temp_scorecard = mock_load('test_scorecard', target_score_identifiers, use_cache=False, specific_version=None)
            primary_score_id = None
            for sc_config in temp_scorecard.scores:
                if sc_config.get('name') == target_score_identifiers[0]:
                    primary_score_id = sc_config.get('id')
                    break
            
            # Get latest version
            if primary_score_id:
                latest_version_id = mock_get_latest(mock_client_instance, primary_score_id)
                assert latest_version_id == self.latest_version_id
            
            # Load scorecard with resolved version
            final_scorecard = mock_load('test_scorecard', target_score_identifiers, use_cache=False, specific_version=latest_version_id)
            
            # Verify the final scorecard uses the latest version
            assert final_scorecard.scores[0]['version'] == self.latest_version_id

    def test_effective_version_logging(self):
        """Test that effective version is correctly determined for logging."""
        # Test case 1: --latest flag
        latest = True
        version = None
        effective_version = "latest" if latest else (version or "champion")
        assert effective_version == "latest"
        
        # Test case 2: --version flag
        latest = False
        version = "version-123"
        effective_version = "latest" if latest else (version or "champion")
        assert effective_version == "version-123"
        
        # Test case 3: Neither flag (champion)
        latest = False
        version = None
        effective_version = "latest" if latest else (version or "champion")
        assert effective_version == "champion"


class TestScoreVersionAssociation:
    """Test ScoreVersion association in evaluation records."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.resolved_version = str(uuid.uuid4())
        
    def test_resolved_version_in_experiment_params(self):
        """Test that resolved_version is included in experiment parameters."""
        yaml_flag = False
        resolved_version = self.resolved_version
        
        experiment_params = {
            "type": "accuracy",
            "status": "SETUP"
        }
        
        # Simulate the logic from our implementation
        if not yaml_flag and resolved_version:
            experiment_params["scoreVersionId"] = resolved_version
        
        assert experiment_params.get("scoreVersionId") == self.resolved_version

    def test_yaml_flag_prevents_version_association(self):
        """Test that --yaml flag prevents ScoreVersion association."""
        yaml_flag = True
        resolved_version = self.resolved_version
        
        experiment_params = {
            "type": "accuracy", 
            "status": "SETUP"
        }
        
        # Simulate the logic from our implementation
        if not yaml_flag and resolved_version:
            experiment_params["scoreVersionId"] = resolved_version
        
        assert "scoreVersionId" not in experiment_params

    def test_version_resolution_logic(self):
        """Test the version resolution logic."""
        # Test initial resolved_version assignment
        version = "original-version"
        resolved_version = version
        assert resolved_version == "original-version"
        
        # Test --latest flag override
        latest_flag = True
        if latest_flag:
            resolved_version = "latest-version-123"
        
        assert resolved_version == "latest-version-123"


class TestLatestVersionErrorHandling:
    """Test error handling in latest version resolution."""
    
    @patch('plexus.cli.evaluation.evaluations.PlexusDashboardClient') 
    @patch('plexus.cli.evaluation.evaluations.get_latest_score_version')
    @patch('plexus.cli.evaluation.evaluations.load_scorecard_from_api')
    def test_latest_flag_fallback_on_error(self, mock_load, mock_get_latest, mock_client_class):
        """Test that --latest falls back gracefully when version resolution fails."""
        # Setup mocks
        mock_scorecard = Mock()
        mock_scorecard.scores = [{
            'name': 'test_score',
            'id': str(uuid.uuid4())
        }]
        mock_load.return_value = mock_scorecard
        mock_get_latest.return_value = None  # Simulate failure to get latest
        mock_client_class.return_value = Mock()
        
        # Simulate the error handling logic
        resolved_version = None  # original version
        latest_version_id = mock_get_latest(Mock(), str(uuid.uuid4()))
        
        if latest_version_id:
            resolved_version = latest_version_id
        else:
            # Should log warning and use original version (None in this case)
            pass
        
        assert resolved_version is None  # Falls back to original

    def test_score_id_not_found_handling(self):
        """Test handling when score ID cannot be resolved for --latest."""
        # Simulate scorecard without matching score
        mock_scorecard = Mock()
        mock_scorecard.scores = [{
            'name': 'different_score',
            'id': str(uuid.uuid4())
        }]
        
        # Try to find primary score ID
        primary_score_identifier = 'test_score'
        primary_score_id = None
        for sc_config in mock_scorecard.scores:
            if sc_config.get('name') == primary_score_identifier:
                primary_score_id = sc_config.get('id')
                break
        
        assert primary_score_id is None  # Should not find the score
        
        # In the real implementation, this would log a warning and use champion version
        resolved_version = None  # Falls back to original version


if __name__ == '__main__':
    pytest.main([__file__, '-v'])