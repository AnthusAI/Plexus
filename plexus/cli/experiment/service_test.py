"""
Tests for Experiment Service.

Tests the ExperimentService functionality including:
- Creating experiments with validation
- Listing and filtering experiments
- Getting experiment information
- Updating configurations
- Deleting experiments
- YAML configuration management
"""

import pytest
import unittest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime
import yaml

from plexus.cli.experiment.service import ExperimentService, ExperimentCreationResult, ExperimentInfo, DEFAULT_EXPERIMENT_YAML


class TestExperimentService(unittest.TestCase):
    """Test cases for the ExperimentService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.service = ExperimentService(self.mock_client)
        
        # Mock experiment data
        self.mock_experiment = Mock()
        self.mock_experiment.id = 'exp-123'
        self.mock_experiment.featured = True
        self.mock_experiment.accountId = 'account-789'
        self.mock_experiment.scorecardId = 'scorecard-abc'
        self.mock_experiment.scoreId = 'score-def'
        self.mock_experiment.rootNodeId = 'node-456'
        self.mock_experiment.createdAt = datetime(2024, 1, 15, 10, 30)
        self.mock_experiment.updatedAt = datetime(2024, 1, 15, 11, 0)
        
        # Mock root node and version
        self.mock_root_node = Mock()
        self.mock_root_node.id = 'node-456'
        
        self.mock_initial_version = Mock()
        self.mock_initial_version.id = 'version-789'
    
    @patch('plexus.cli.experiment.service.resolve_account_identifier')
    @patch('plexus.cli.experiment.service.resolve_scorecard_identifier')
    @patch('plexus.cli.experiment.service.Experiment')
    def test_create_experiment_success(self, mock_experiment_class, mock_resolve_scorecard, mock_resolve_account):
        """Test successful experiment creation."""
        # Setup mocks
        mock_resolve_account.return_value = 'account-123'
        mock_resolve_scorecard.return_value = 'scorecard-456'
        
        mock_experiment_class.create.return_value = self.mock_experiment
        self.mock_experiment.create_root_node.return_value = self.mock_root_node
        self.mock_root_node.get_latest_version.return_value = self.mock_initial_version
        
        # Mock score resolution
        with patch.object(self.service, '_resolve_score_identifier', return_value='score-789'):
            result = self.service.create_experiment(
                account_identifier='test-account',
                scorecard_identifier='test-scorecard',
                score_identifier='test-score',
                yaml_config='class: BeamSearch',
                featured=True
            )
        
        # Verify success
        self.assertTrue(result.success)
        self.assertEqual(result.experiment, self.mock_experiment)
        self.assertEqual(result.root_node, self.mock_root_node)
        self.assertEqual(result.initial_version, self.mock_initial_version)
        
        # Verify calls
        mock_resolve_account.assert_called_once_with(self.mock_client, 'test-account')
        mock_resolve_scorecard.assert_called_once_with(self.mock_client, 'test-scorecard')
        mock_experiment_class.create.assert_called_once_with(
            client=self.mock_client,
            accountId='account-123',
            scorecardId='scorecard-456',
            scoreId='score-789',
            featured=True
        )
        self.mock_experiment.create_root_node.assert_called_once_with('class: BeamSearch', None)
    
    @patch('plexus.cli.experiment.service.resolve_account_identifier')
    def test_create_experiment_account_not_found(self, mock_resolve_account):
        """Test experiment creation when account is not found."""
        mock_resolve_account.return_value = None
        
        result = self.service.create_experiment(
            account_identifier='missing-account',
            scorecard_identifier='test-scorecard',
            score_identifier='test-score'
        )
        
        self.assertFalse(result.success)
        self.assertIn('Could not resolve account', result.message)
        self.assertIsNone(result.experiment)
    
    @patch('plexus.cli.experiment.service.resolve_account_identifier')
    @patch('plexus.cli.experiment.service.resolve_scorecard_identifier')
    def test_create_experiment_scorecard_not_found(self, mock_resolve_scorecard, mock_resolve_account):
        """Test experiment creation when scorecard is not found."""
        mock_resolve_account.return_value = 'account-123'
        mock_resolve_scorecard.return_value = None
        
        result = self.service.create_experiment(
            account_identifier='test-account',
            scorecard_identifier='missing-scorecard',
            score_identifier='test-score'
        )
        
        self.assertFalse(result.success)
        self.assertIn('Could not resolve scorecard', result.message)
        self.assertIsNone(result.experiment)
    
    @patch('plexus.cli.experiment.service.resolve_account_identifier')
    @patch('plexus.cli.experiment.service.resolve_scorecard_identifier')
    def test_create_experiment_score_not_found(self, mock_resolve_scorecard, mock_resolve_account):
        """Test experiment creation when score is not found."""
        mock_resolve_account.return_value = 'account-123'
        mock_resolve_scorecard.return_value = 'scorecard-456'
        
        with patch.object(self.service, '_resolve_score_identifier', return_value=None):
            result = self.service.create_experiment(
                account_identifier='test-account',
                scorecard_identifier='test-scorecard',
                score_identifier='missing-score'
            )
        
        self.assertFalse(result.success)
        self.assertIn('Could not resolve score', result.message)
        self.assertIsNone(result.experiment)
    
    @patch('plexus.cli.experiment.service.resolve_account_identifier')
    @patch('plexus.cli.experiment.service.resolve_scorecard_identifier')
    def test_create_experiment_invalid_yaml(self, mock_resolve_scorecard, mock_resolve_account):
        """Test experiment creation with invalid YAML."""
        mock_resolve_account.return_value = 'account-123'
        mock_resolve_scorecard.return_value = 'scorecard-456'
        
        with patch.object(self.service, '_resolve_score_identifier', return_value='score-789'):
            result = self.service.create_experiment(
                account_identifier='test-account',
                scorecard_identifier='test-scorecard',
                score_identifier='test-score',
                yaml_config='invalid: yaml: content: ['  # Invalid YAML
            )
        
        self.assertFalse(result.success)
        self.assertIn('Invalid YAML configuration', result.message)
        self.assertIsNone(result.experiment)
    
    @patch('plexus.cli.experiment.service.resolve_account_identifier')
    @patch('plexus.cli.experiment.service.resolve_scorecard_identifier')
    def test_create_experiment_uses_default_yaml(self, mock_resolve_scorecard, mock_resolve_account):
        """Test experiment creation uses default YAML when none provided."""
        mock_resolve_account.return_value = 'account-123'
        mock_resolve_scorecard.return_value = 'scorecard-456'
        
        mock_experiment_class = Mock()
        mock_experiment_class.create.return_value = self.mock_experiment
        self.mock_experiment.create_root_node.return_value = self.mock_root_node
        self.mock_root_node.get_latest_version.return_value = self.mock_initial_version
        
        with patch.object(self.service, '_resolve_score_identifier', return_value='score-789'), \
             patch('plexus.cli.experiment.service.Experiment', mock_experiment_class):
            
            result = self.service.create_experiment(
                account_identifier='test-account',
                scorecard_identifier='test-scorecard',
                score_identifier='test-score'
                # No yaml_config provided
            )
        
        self.assertTrue(result.success)
        # Verify default YAML was used
        self.mock_experiment.create_root_node.assert_called_once_with(DEFAULT_EXPERIMENT_YAML, None)
    
    @patch('plexus.cli.experiment.service.Experiment')
    def test_get_experiment_info_success(self, mock_experiment_class):
        """Test getting experiment info successfully."""
        # Setup mocks
        mock_experiment_class.get_by_id.return_value = self.mock_experiment
        self.mock_experiment.get_root_node.return_value = self.mock_root_node
        self.mock_root_node.get_latest_version.return_value = self.mock_initial_version
        
        # Mock node listing
        mock_nodes = [Mock(), Mock(), Mock()]
        for i, node in enumerate(mock_nodes):
            node.get_versions.return_value = [Mock(), Mock()]  # 2 versions each
        
        with patch('plexus.cli.experiment.service.ExperimentNode') as mock_node_class:
            mock_node_class.list_by_experiment.return_value = mock_nodes
            
            result = self.service.get_experiment_info('exp-123')
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.experiment, self.mock_experiment)
        self.assertEqual(result.root_node, self.mock_root_node)
        self.assertEqual(result.latest_version, self.mock_initial_version)
        self.assertEqual(result.node_count, 3)
        self.assertEqual(result.version_count, 6)  # 3 nodes * 2 versions each
        
        # Verify calls
        mock_experiment_class.get_by_id.assert_called_once_with('exp-123', self.mock_client)
        self.mock_experiment.get_root_node.assert_called_once()
    
    @patch('plexus.cli.experiment.service.Experiment')
    def test_get_experiment_info_not_found(self, mock_experiment_class):
        """Test getting experiment info when experiment not found."""
        mock_experiment_class.get_by_id.side_effect = ValueError("Not found")
        
        result = self.service.get_experiment_info('missing-exp')
        
        self.assertIsNone(result)
    
    @patch('plexus.cli.experiment.service.resolve_account_identifier')
    @patch('plexus.cli.experiment.service.Experiment')
    def test_list_experiments_by_account(self, mock_experiment_class, mock_resolve_account):
        """Test listing experiments by account."""
        mock_resolve_account.return_value = 'account-123'
        mock_experiments = [Mock(), Mock()]
        mock_experiment_class.list_by_account.return_value = mock_experiments
        
        result = self.service.list_experiments('test-account', limit=50)
        
        self.assertEqual(result, mock_experiments)
        mock_resolve_account.assert_called_once_with(self.mock_client, 'test-account')
        mock_experiment_class.list_by_account.assert_called_once_with('account-123', self.mock_client, 50)
    
    @patch('plexus.cli.experiment.service.resolve_account_identifier')
    @patch('plexus.cli.experiment.service.resolve_scorecard_identifier')
    @patch('plexus.cli.experiment.service.Experiment')
    def test_list_experiments_by_scorecard(self, mock_experiment_class, mock_resolve_scorecard, mock_resolve_account):
        """Test listing experiments filtered by scorecard."""
        mock_resolve_account.return_value = 'account-123'
        mock_resolve_scorecard.return_value = 'scorecard-456'
        mock_experiments = [Mock()]
        mock_experiment_class.list_by_scorecard.return_value = mock_experiments
        
        result = self.service.list_experiments('test-account', 'test-scorecard')
        
        self.assertEqual(result, mock_experiments)
        mock_resolve_scorecard.assert_called_once_with(self.mock_client, 'test-scorecard')
        mock_experiment_class.list_by_scorecard.assert_called_once_with('scorecard-456', self.mock_client, 100)
    
    @patch('plexus.cli.experiment.service.resolve_account_identifier')
    def test_list_experiments_account_not_found(self, mock_resolve_account):
        """Test listing experiments when account not found."""
        mock_resolve_account.return_value = None
        
        result = self.service.list_experiments('missing-account')
        
        self.assertEqual(result, [])
    
    @patch('plexus.cli.experiment.service.Experiment')
    @patch('plexus.cli.experiment.service.ExperimentNode')
    def test_delete_experiment_success(self, mock_node_class, mock_experiment_class):
        """Test successful experiment deletion."""
        # Setup mocks
        mock_experiment_class.get_by_id.return_value = self.mock_experiment
        
        mock_nodes = [Mock(), Mock()]
        mock_node_class.list_by_experiment.return_value = mock_nodes
        
        # Each node has versions
        for node in mock_nodes:
            node.get_versions.return_value = [Mock(), Mock()]
            node.delete.return_value = True
            for version in node.get_versions():
                version.delete.return_value = True
        
        self.mock_experiment.delete.return_value = True
        
        success, message = self.service.delete_experiment('exp-123')
        
        # Verify success
        self.assertTrue(success)
        self.assertIn('Deleted experiment', message)
        
        # Verify all versions and nodes were deleted
        for node in mock_nodes:
            for version in node.get_versions():
                version.delete.assert_called_once()
            node.delete.assert_called_once()
        
        self.mock_experiment.delete.assert_called_once()
    
    @patch('plexus.cli.experiment.service.Experiment')
    def test_delete_experiment_not_found(self, mock_experiment_class):
        """Test deleting experiment when not found."""
        mock_experiment_class.get_by_id.side_effect = ValueError("Not found")
        
        success, message = self.service.delete_experiment('missing-exp')
        
        self.assertFalse(success)
        self.assertIn('Error deleting experiment', message)
    
    @patch('plexus.cli.experiment.service.Experiment')
    def test_update_experiment_config_success(self, mock_experiment_class):
        """Test successful experiment configuration update."""
        mock_experiment_class.get_by_id.return_value = self.mock_experiment
        self.mock_experiment.get_root_node.return_value = self.mock_root_node
        
        # Mock existing versions
        mock_versions = [Mock(), Mock()]
        mock_versions[0].seq = 1
        mock_versions[1].seq = 2
        self.mock_root_node.get_versions.return_value = mock_versions
        
        # Mock new version creation
        mock_new_version = Mock()
        mock_new_version.id = 'version-new'
        self.mock_root_node.create_version.return_value = mock_new_version
        
        yaml_config = "class: ImprovedBeamSearch"
        note = "Updated configuration"
        
        success, message = self.service.update_experiment_config('exp-123', yaml_config, note)
        
        # Verify success
        self.assertTrue(success)
        self.assertIn('Updated experiment configuration', message)
        
        # Verify new version was created with correct seq
        self.mock_root_node.create_version.assert_called_once_with(
            seq=3,  # Should be max(1,2) + 1
            yaml_config=yaml_config,
            value={"note": note},
            status='QUEUED'
        )
    
    @patch('plexus.cli.experiment.service.Experiment')
    def test_update_experiment_config_invalid_yaml(self, mock_experiment_class):
        """Test updating experiment config with invalid YAML."""
        invalid_yaml = "invalid: yaml: content: ["
        
        success, message = self.service.update_experiment_config('exp-123', invalid_yaml)
        
        self.assertFalse(success)
        self.assertIn('Invalid YAML configuration', message)
    
    @patch('plexus.cli.experiment.service.Experiment')
    def test_update_experiment_config_no_root_node(self, mock_experiment_class):
        """Test updating experiment config when no root node exists."""
        mock_experiment_class.get_by_id.return_value = self.mock_experiment
        self.mock_experiment.get_root_node.return_value = None
        
        success, message = self.service.update_experiment_config('exp-123', 'class: BeamSearch')
        
        self.assertFalse(success)
        self.assertEqual(message, 'Experiment has no root node')
    
    @patch('plexus.cli.experiment.service.Experiment')
    def test_get_experiment_yaml_success(self, mock_experiment_class):
        """Test getting experiment YAML successfully."""
        mock_experiment_class.get_by_id.return_value = self.mock_experiment
        self.mock_experiment.get_root_node.return_value = self.mock_root_node
        self.mock_root_node.get_latest_version.return_value = self.mock_initial_version
        self.mock_initial_version.get_yaml_config.return_value = 'class: BeamSearch'
        
        result = self.service.get_experiment_yaml('exp-123')
        
        self.assertEqual(result, 'class: BeamSearch')
    
    @patch('plexus.cli.experiment.service.Experiment')
    def test_get_experiment_yaml_no_root_node(self, mock_experiment_class):
        """Test getting experiment YAML when no root node."""
        mock_experiment_class.get_by_id.return_value = self.mock_experiment
        self.mock_experiment.get_root_node.return_value = None
        
        result = self.service.get_experiment_yaml('exp-123')
        
        self.assertIsNone(result)
    
    @patch('plexus.cli.experiment.service.Experiment')
    def test_get_experiment_yaml_no_versions(self, mock_experiment_class):
        """Test getting experiment YAML when no versions exist."""
        mock_experiment_class.get_by_id.return_value = self.mock_experiment
        self.mock_experiment.get_root_node.return_value = self.mock_root_node
        self.mock_root_node.get_latest_version.return_value = None
        
        result = self.service.get_experiment_yaml('exp-123')
        
        self.assertIsNone(result)
    
    def test_resolve_score_identifier_by_id(self):
        """Test resolving score by direct ID."""
        # Mock score lookup
        mock_score = Mock()
        mock_score.scorecard_id = 'scorecard-123'
        
        with patch('plexus.cli.experiment.service.Score') as mock_score_class:
            mock_score_class.get_by_id.return_value = mock_score
            
            result = self.service._resolve_score_identifier('scorecard-123', 'score-456')
        
        self.assertEqual(result, 'score-456')
    
    def test_resolve_score_identifier_wrong_scorecard(self):
        """Test resolving score ID that belongs to wrong scorecard."""
        # Mock score lookup
        mock_score = Mock()
        mock_score.scorecard_id = 'different-scorecard'
        
        with patch('plexus.cli.experiment.service.Score') as mock_score_class:
            mock_score_class.get_by_id.return_value = mock_score
            
            # Should fall through to GraphQL search since scorecard doesn't match
            self.mock_client.execute.return_value = {
                'getScorecard': {
                    'sections': {
                        'items': []
                    }
                }
            }
            
            result = self.service._resolve_score_identifier('scorecard-123', 'score-456')
        
        self.assertIsNone(result)
    
    def test_resolve_score_identifier_by_name(self):
        """Test resolving score by name within scorecard."""
        self.mock_client.execute.return_value = {
            'getScorecard': {
                'sections': {
                    'items': [
                        {
                            'scores': {
                                'items': [
                                    {
                                        'id': 'score-123',
                                        'name': 'Test Score',
                                        'key': 'test-score',
                                        'externalId': 'ext-123'
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }
        
        result = self.service._resolve_score_identifier('scorecard-456', 'Test Score')
        
        self.assertEqual(result, 'score-123')
    
    def test_resolve_score_identifier_by_key(self):
        """Test resolving score by key within scorecard."""
        self.mock_client.execute.return_value = {
            'getScorecard': {
                'sections': {
                    'items': [
                        {
                            'scores': {
                                'items': [
                                    {
                                        'id': 'score-123',
                                        'name': 'Test Score',
                                        'key': 'test-score',
                                        'externalId': 'ext-123'
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }
        
        result = self.service._resolve_score_identifier('scorecard-456', 'test-score')
        
        self.assertEqual(result, 'score-123')
    
    def test_resolve_score_identifier_not_found(self):
        """Test resolving score that doesn't exist."""
        self.mock_client.execute.return_value = {
            'getScorecard': {
                'sections': {
                    'items': [
                        {
                            'scores': {
                                'items': []
                            }
                        }
                    ]
                }
            }
        }
        
        result = self.service._resolve_score_identifier('scorecard-456', 'missing-score')
        
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()