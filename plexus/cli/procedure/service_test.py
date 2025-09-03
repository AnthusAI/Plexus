"""
Tests for Procedure Service.

Tests the ProcedureService functionality including:
- Creating experiments with validation
- Listing and filtering experiments
- Getting procedure information
- Updating configurations
- Deleting experiments
- YAML configuration management
"""

import pytest
import unittest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime
import yaml

from plexus.cli.procedure.service import ProcedureService, ProcedureCreationResult, ProcedureInfo, DEFAULT_PROCEDURE_YAML


class TestProcedureService(unittest.TestCase):
    """Test cases for the ProcedureService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.service = ProcedureService(self.mock_client)
        
        # Valid YAML configuration for testing
        self.valid_yaml_config = """class: BeamSearch
prompts:
  worker_system_prompt: "You are a test worker assistant."
  worker_user_prompt: "Begin test analysis."
  manager_system_prompt: "You are a test coaching manager."
"""
        
        # Mock procedure data
        self.mock_procedure = Mock()
        self.mock_procedure.id = 'exp-123'
        self.mock_procedure.featured = True
        self.mock_procedure.accountId = 'account-789'
        self.mock_procedure.scorecardId = 'scorecard-abc'
        self.mock_procedure.scoreId = 'score-def'
        self.mock_procedure.rootNodeId = 'node-456'
        self.mock_procedure.createdAt = datetime(2024, 1, 15, 10, 30)
        self.mock_procedure.updatedAt = datetime(2024, 1, 15, 11, 0)
        
        # Mock root node and version
        self.mock_root_node = Mock()
        self.mock_root_node.id = 'node-456'
        
        self.mock_initial_version = Mock()
        self.mock_initial_version.id = 'version-789'
    
    @patch('plexus.cli.procedure.service.resolve_account_identifier')
    @patch('plexus.cli.procedure.service.resolve_scorecard_identifier')
    @patch('plexus.cli.procedure.service.Procedure')
    @patch('plexus.cli.procedure.service.ProcedureTemplate')
    def test_create_procedure_success(self, mock_template_class, mock_procedure_class, mock_resolve_scorecard, mock_resolve_account):
        """Test successful procedure creation."""
        # Setup mocks
        mock_resolve_account.return_value = 'account-123'
        mock_resolve_scorecard.return_value = 'scorecard-456'
        
        # Mock template
        mock_template = Mock()
        mock_template.id = 'template-123'
        mock_template.get_template_content.return_value = self.valid_yaml_config
        mock_template_class.get_default_for_account.return_value = None  # Force creation
        mock_template_class.create.return_value = mock_template
        
        mock_procedure_class.create.return_value = self.mock_procedure
        self.mock_procedure.create_root_node.return_value = self.mock_root_node
        
        # Mock score resolution
        with patch.object(self.service, '_resolve_score_identifier', return_value='score-789'):
            result = self.service.create_procedure(
                account_identifier='test-account',
                scorecard_identifier='test-scorecard',
                score_identifier='test-score',
                yaml_config=self.valid_yaml_config,
                featured=True
            )
        
        # Verify success
        self.assertTrue(result.success)
        self.assertEqual(result.procedure, self.mock_procedure)
        self.assertEqual(result.root_node, self.mock_root_node)
        
        # Verify calls
        mock_resolve_account.assert_called_once_with(self.mock_client, 'test-account')
        mock_resolve_scorecard.assert_called_once_with(self.mock_client, 'test-scorecard')
        mock_procedure_class.create.assert_called_once_with(
            client=self.mock_client,
            accountId='account-123',
            scorecardId='scorecard-456',
            scoreId='score-789',
            templateId='template-123',
            featured=True
        )
        self.mock_procedure.create_root_node.assert_called_once_with(self.valid_yaml_config, None)
    
    @patch('plexus.cli.procedure.service.resolve_account_identifier')
    def test_create_procedure_account_not_found(self, mock_resolve_account):
        """Test procedure creation when account is not found."""
        mock_resolve_account.return_value = None
        
        result = self.service.create_procedure(
            account_identifier='missing-account',
            scorecard_identifier='test-scorecard',
            score_identifier='test-score'
        )
        
        self.assertFalse(result.success)
        self.assertIn('Could not resolve account', result.message)
        self.assertIsNone(result.procedure)
    
    @patch('plexus.cli.procedure.service.resolve_account_identifier')
    @patch('plexus.cli.procedure.service.resolve_scorecard_identifier')
    def test_create_procedure_scorecard_not_found(self, mock_resolve_scorecard, mock_resolve_account):
        """Test procedure creation when scorecard is not found."""
        mock_resolve_account.return_value = 'account-123'
        mock_resolve_scorecard.return_value = None
        
        result = self.service.create_procedure(
            account_identifier='test-account',
            scorecard_identifier='missing-scorecard',
            score_identifier='test-score'
        )
        
        self.assertFalse(result.success)
        self.assertIn('Could not resolve scorecard', result.message)
        self.assertIsNone(result.procedure)
    
    @patch('plexus.cli.procedure.service.resolve_account_identifier')
    @patch('plexus.cli.procedure.service.resolve_scorecard_identifier')
    def test_create_procedure_score_not_found(self, mock_resolve_scorecard, mock_resolve_account):
        """Test procedure creation when score is not found."""
        mock_resolve_account.return_value = 'account-123'
        mock_resolve_scorecard.return_value = 'scorecard-456'
        
        with patch.object(self.service, '_resolve_score_identifier', return_value=None):
            result = self.service.create_procedure(
                account_identifier='test-account',
                scorecard_identifier='test-scorecard',
                score_identifier='missing-score'
            )
        
        self.assertFalse(result.success)
        self.assertIn('Could not resolve score', result.message)
        self.assertIsNone(result.procedure)
    
    @patch('plexus.cli.procedure.service.resolve_account_identifier')
    @patch('plexus.cli.procedure.service.resolve_scorecard_identifier')
    @patch('plexus.cli.procedure.service.ProcedureTemplate')
    def test_create_procedure_invalid_yaml(self, mock_template_class, mock_resolve_scorecard, mock_resolve_account):
        """Test procedure creation with invalid YAML."""
        mock_resolve_account.return_value = 'account-123'
        mock_resolve_scorecard.return_value = 'scorecard-456'
        
        # Mock template (not used for invalid YAML test but needed for service)
        mock_template = Mock()
        mock_template.id = 'template-123'
        mock_template_class.get_default_for_account.return_value = None
        mock_template_class.create.return_value = mock_template
        
        with patch.object(self.service, '_resolve_score_identifier', return_value='score-789'):
            result = self.service.create_procedure(
                account_identifier='test-account',
                scorecard_identifier='test-scorecard',
                score_identifier='test-score',
                yaml_config='invalid: yaml: content: ['  # Invalid YAML
            )
        
        self.assertFalse(result.success)
        self.assertIn('Invalid YAML configuration', result.message)
        self.assertIsNone(result.procedure)
    
    @patch('plexus.cli.procedure.service.resolve_account_identifier')
    @patch('plexus.cli.procedure.service.resolve_scorecard_identifier')
    @patch('plexus.cli.procedure.service.ProcedureTemplate')
    def test_create_procedure_uses_default_yaml(self, mock_template_class, mock_resolve_scorecard, mock_resolve_account):
        """Test procedure creation uses default YAML when none provided."""
        mock_resolve_account.return_value = 'account-123'
        mock_resolve_scorecard.return_value = 'scorecard-456'
        
        # Mock template
        mock_template = Mock()
        mock_template.id = 'template-123'
        mock_template.get_template_content.return_value = DEFAULT_PROCEDURE_YAML
        mock_template_class.get_default_for_account.return_value = None  # Force creation
        mock_template_class.create.return_value = mock_template
        
        mock_procedure_class = Mock()
        mock_procedure_class.create.return_value = self.mock_procedure
        self.mock_procedure.create_root_node.return_value = self.mock_root_node
        
        with patch.object(self.service, '_resolve_score_identifier', return_value='score-789'), \
             patch('plexus.cli.procedure.service.Procedure', mock_procedure_class):
            
            result = self.service.create_procedure(
                account_identifier='test-account',
                scorecard_identifier='test-scorecard',
                score_identifier='test-score'
                # No yaml_config provided
            )
        
        self.assertTrue(result.success)
        # Verify default YAML was used
        self.mock_procedure.create_root_node.assert_called_once_with(DEFAULT_PROCEDURE_YAML, None)
    
    @patch('plexus.cli.procedure.service.Procedure')
    def test_get_procedure_info_success(self, mock_procedure_class):
        """Test getting procedure info successfully."""
        # Setup mocks
        mock_procedure_class.get_by_id.return_value = self.mock_procedure
        self.mock_procedure.get_root_node.return_value = self.mock_root_node
        self.mock_root_node.get_latest_version.return_value = self.mock_initial_version
        
        # Mock node listing
        mock_nodes = [Mock(), Mock(), Mock()]
        for i, node in enumerate(mock_nodes):
            node.get_versions.return_value = [Mock(), Mock()]  # 2 versions each
        
        with patch('plexus.cli.procedure.service.GraphNode') as mock_node_class:
            mock_node_class.list_by_procedure.return_value = mock_nodes
            
            result = self.service.get_procedure_info('exp-123')
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.procedure, self.mock_procedure)
        self.assertEqual(result.root_node, self.mock_root_node)
        # Note: latest_version no longer exists in simplified schema
        self.assertEqual(result.node_count, 3)
        self.assertEqual(result.version_count, 3)  # In simplified schema, version_count equals node_count
        
        # Verify calls
        mock_procedure_class.get_by_id.assert_called_once_with('exp-123', self.mock_client)
        self.mock_procedure.get_root_node.assert_called_once()
    
    @patch('plexus.cli.procedure.service.Procedure')
    def test_get_procedure_info_not_found(self, mock_procedure_class):
        """Test getting procedure info when procedure not found."""
        mock_procedure_class.get_by_id.side_effect = ValueError("Not found")
        
        result = self.service.get_procedure_info('missing-exp')
        
        self.assertIsNone(result)
    
    @patch('plexus.cli.procedure.service.resolve_account_identifier')
    @patch('plexus.cli.procedure.service.Procedure')
    def test_list_procedures_by_account(self, mock_procedure_class, mock_resolve_account):
        """Test listing experiments by account."""
        mock_resolve_account.return_value = 'account-123'
        mock_procedures = [Mock(), Mock()]
        mock_procedure_class.list_by_account.return_value = mock_procedures
        
        result = self.service.list_procedures('test-account', limit=50)
        
        self.assertEqual(result, mock_procedures)
        mock_resolve_account.assert_called_once_with(self.mock_client, 'test-account')
        mock_procedure_class.list_by_account.assert_called_once_with('account-123', self.mock_client, 50)
    
    @patch('plexus.cli.procedure.service.resolve_account_identifier')
    @patch('plexus.cli.procedure.service.resolve_scorecard_identifier')
    @patch('plexus.cli.procedure.service.Procedure')
    def test_list_procedures_by_scorecard(self, mock_procedure_class, mock_resolve_scorecard, mock_resolve_account):
        """Test listing experiments filtered by scorecard."""
        mock_resolve_account.return_value = 'account-123'
        mock_resolve_scorecard.return_value = 'scorecard-456'
        mock_procedures = [Mock()]
        mock_procedure_class.list_by_scorecard.return_value = mock_procedures
        
        result = self.service.list_procedures('test-account', 'test-scorecard')
        
        self.assertEqual(result, mock_procedures)
        mock_resolve_scorecard.assert_called_once_with(self.mock_client, 'test-scorecard')
        mock_procedure_class.list_by_scorecard.assert_called_once_with('scorecard-456', self.mock_client, 100)
    
    @patch('plexus.cli.procedure.service.resolve_account_identifier')
    def test_list_procedures_account_not_found(self, mock_resolve_account):
        """Test listing experiments when account not found."""
        mock_resolve_account.return_value = None
        
        result = self.service.list_procedures('missing-account')
        
        self.assertEqual(result, [])
    
    @patch('plexus.cli.procedure.service.Procedure')
    @patch('plexus.cli.procedure.service.GraphNode')
    def test_delete_procedure_success(self, mock_node_class, mock_procedure_class):
        """Test successful procedure deletion."""
        # Setup mocks
        mock_procedure_class.get_by_id.return_value = self.mock_procedure
        
        mock_nodes = [Mock(), Mock()]
        mock_node_class.list_by_procedure.return_value = mock_nodes
        
        # Each node no longer has separate versions in simplified schema
        for node in mock_nodes:
            node.delete.return_value = True
        
        self.mock_procedure.delete.return_value = True
        
        success, message = self.service.delete_procedure('exp-123')
        
        # Verify success
        self.assertTrue(success)
        self.assertIn('Deleted procedure', message)
        
        # Verify all nodes were deleted (no separate versions in simplified schema)
        for node in mock_nodes:
            node.delete.assert_called_once()
        
        self.mock_procedure.delete.assert_called_once()
    
    @patch('plexus.cli.procedure.service.Procedure')
    def test_delete_procedure_not_found(self, mock_procedure_class):
        """Test deleting procedure when not found."""
        mock_procedure_class.get_by_id.side_effect = ValueError("Not found")
        
        success, message = self.service.delete_procedure('missing-exp')
        
        self.assertFalse(success)
        self.assertIn('Error deleting experiment', message)
    
    @patch('plexus.cli.procedure.service.Procedure')
    def test_update_procedure_config_success(self, mock_procedure_class):
        """Test successful procedure configuration update."""
        mock_procedure_class.get_by_id.return_value = self.mock_procedure
        self.mock_procedure.get_root_node.return_value = self.mock_root_node
        
        # Mock root node update (no separate versions in simplified schema)
        yaml_config = self.valid_yaml_config
        note = "Updated configuration"
        
        success, message = self.service.update_procedure_config('exp-123', yaml_config, note)
        
        # Verify success
        self.assertTrue(success)
        self.assertIn('Updated procedure configuration', message)
        
        # Verify root node content was updated directly
        self.mock_root_node.update_content.assert_called_once_with(
            code=yaml_config,
            status='QUEUED',
            hypothesis=note,
            value={"note": note}
        )
    
    @patch('plexus.cli.procedure.service.Procedure')
    def test_update_procedure_config_invalid_yaml(self, mock_procedure_class):
        """Test updating procedure config with invalid YAML."""
        invalid_yaml = "invalid: yaml: content: ["
        
        success, message = self.service.update_procedure_config('exp-123', invalid_yaml)
        
        self.assertFalse(success)
        self.assertIn('Invalid YAML configuration', message)
    
    @patch('plexus.cli.procedure.service.Procedure')
    def test_update_procedure_config_no_root_node(self, mock_procedure_class):
        """Test updating procedure config when no root node exists."""
        mock_procedure_class.get_by_id.return_value = self.mock_procedure
        self.mock_procedure.get_root_node.return_value = None
        
        success, message = self.service.update_procedure_config('exp-123', self.valid_yaml_config)
        
        self.assertFalse(success)
        self.assertEqual(message, 'Procedure has no root node')
    
    @patch('plexus.cli.procedure.service.Procedure')
    @patch('plexus.cli.procedure.service.ProcedureTemplate')
    def test_get_experiment_yaml_success(self, mock_template_class, mock_procedure_class):
        """Test getting procedure YAML successfully."""
        mock_procedure_class.get_by_id.return_value = self.mock_procedure
        self.mock_procedure.templateId = 'template-123'
        
        # Mock template
        mock_template = Mock()
        mock_template.get_template_content.return_value = self.valid_yaml_config
        mock_template_class.get_by_id.return_value = mock_template
        
        result = self.service.get_procedure_yaml('exp-123')
        
        self.assertEqual(result, self.valid_yaml_config)
    
    @patch('plexus.cli.procedure.service.Procedure')
    def test_get_experiment_yaml_no_root_node(self, mock_procedure_class):
        """Test getting procedure YAML when no root node."""
        mock_procedure_class.get_by_id.return_value = self.mock_procedure
        self.mock_procedure.get_root_node.return_value = None
        
        result = self.service.get_procedure_yaml('exp-123')
        
        self.assertIsNone(result)
    
    @patch('plexus.cli.procedure.service.Procedure')
    def test_get_experiment_yaml_no_versions(self, mock_procedure_class):
        """Test getting procedure YAML when no versions exist."""
        mock_procedure_class.get_by_id.return_value = self.mock_procedure
        self.mock_procedure.get_root_node.return_value = self.mock_root_node
        self.mock_root_node.get_latest_version.return_value = None
        
        result = self.service.get_procedure_yaml('exp-123')
        
        self.assertIsNone(result)
    
    def test_resolve_score_identifier_by_id(self):
        """Test resolving score by direct ID."""
        # Mock score lookup
        mock_score = Mock()
        mock_score.scorecard_id = 'scorecard-123'
        
        with patch('plexus.cli.procedure.service.Score') as mock_score_class:
            mock_score_class.get_by_id.return_value = mock_score
            
            result = self.service._resolve_score_identifier('scorecard-123', 'score-456')
        
        self.assertEqual(result, 'score-456')
    
    def test_resolve_score_identifier_wrong_scorecard(self):
        """Test resolving score ID that belongs to wrong scorecard."""
        # Mock score lookup
        mock_score = Mock()
        mock_score.scorecard_id = 'different-scorecard'
        
        with patch('plexus.cli.procedure.service.Score') as mock_score_class:
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