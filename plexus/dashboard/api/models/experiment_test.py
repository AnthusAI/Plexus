"""
Tests for Experiment Model.

Tests the Experiment model's functionality including:
- Creating experiments
- Listing and filtering experiments
- Updating experiment properties
- Managing root nodes
- Deleting experiments
"""

import pytest
import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from plexus.dashboard.api.models.experiment import Experiment


class TestExperiment(unittest.TestCase):
    """Test cases for the Experiment model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.sample_data = {
            'id': 'exp-123',
            'featured': True,
            'rootNodeId': 'node-456',
            'createdAt': '2024-01-15T10:30:00Z',
            'updatedAt': '2024-01-15T11:00:00Z',
            'accountId': 'account-789',
            'scorecardId': 'scorecard-abc',
            'scoreId': 'score-def'
        }
    
    def test_fields(self):
        """Test that fields() returns the correct GraphQL fields."""
        fields = Experiment.fields()
        expected_fields = [
            'id', 'featured', 'rootNodeId', 'createdAt', 'updatedAt',
            'accountId', 'scorecardId', 'scoreId'
        ]
        
        for field in expected_fields:
            self.assertIn(field, fields)
    
    def test_from_dict(self):
        """Test creating an Experiment from dictionary data."""
        experiment = Experiment.from_dict(self.sample_data, self.mock_client)
        
        self.assertEqual(experiment.id, 'exp-123')
        self.assertTrue(experiment.featured)
        self.assertEqual(experiment.rootNodeId, 'node-456')
        self.assertEqual(experiment.accountId, 'account-789')
        self.assertEqual(experiment.scorecardId, 'scorecard-abc')
        self.assertEqual(experiment.scoreId, 'score-def')
        self.assertIsInstance(experiment.createdAt, datetime)
        self.assertIsInstance(experiment.updatedAt, datetime)
        self.assertEqual(experiment._client, self.mock_client)
    
    def test_from_dict_optional_fields(self):
        """Test creating an Experiment with optional fields missing."""
        minimal_data = {
            'id': 'exp-123',
            'createdAt': '2024-01-15T10:30:00Z',
            'updatedAt': '2024-01-15T11:00:00Z',
            'accountId': 'account-789'
        }
        
        experiment = Experiment.from_dict(minimal_data, self.mock_client)
        
        self.assertEqual(experiment.id, 'exp-123')
        self.assertFalse(experiment.featured)  # Should default to False
        self.assertIsNone(experiment.rootNodeId)
        self.assertIsNone(experiment.scorecardId)
        self.assertIsNone(experiment.scoreId)
    
    def test_create(self):
        """Test creating a new experiment."""
        self.mock_client.execute.return_value = {
            'createExperiment': self.sample_data
        }
        
        experiment = Experiment.create(
            client=self.mock_client,
            accountId='account-789',
            scorecardId='scorecard-abc',
            scoreId='score-def',
            featured=True
        )
        
        # Verify GraphQL call
        self.mock_client.execute.assert_called_once()
        call_args = self.mock_client.execute.call_args
        self.assertIn('createExperiment', call_args[0][0])
        
        # Get variables from call args - call_args is (args, kwargs)
        mutation_string = call_args[0][0]
        variables = call_args[0][1]  # Second positional argument
        input_data = variables['input']
        self.assertEqual(input_data['accountId'], 'account-789')
        self.assertEqual(input_data['scorecardId'], 'scorecard-abc')
        self.assertEqual(input_data['scoreId'], 'score-def')
        self.assertTrue(input_data['featured'])
        
        # Verify returned experiment
        self.assertEqual(experiment.id, 'exp-123')
        self.assertTrue(experiment.featured)
    
    def test_list_by_account(self):
        """Test listing experiments by account."""
        self.mock_client.execute.return_value = {
            'listExperimentByAccountIdAndUpdatedAt': {
                'items': [self.sample_data]
            }
        }
        
        experiments = Experiment.list_by_account('account-789', self.mock_client, limit=50)
        
        # Verify GraphQL call
        self.mock_client.execute.assert_called_once()
        call_args = self.mock_client.execute.call_args
        self.assertIn('listExperimentByAccountIdAndUpdatedAt', call_args[0][0])
        self.assertIn('sortDirection: DESC', call_args[0][0])
        
        variables = call_args[0][1]  # Second positional argument
        self.assertEqual(variables['accountId'], 'account-789')
        self.assertEqual(variables['limit'], 50)
        
        # Verify returned experiments
        self.assertEqual(len(experiments), 1)
        self.assertEqual(experiments[0].id, 'exp-123')
    
    def test_list_by_scorecard(self):
        """Test listing experiments by scorecard."""
        self.mock_client.execute.return_value = {
            'listExperimentByScorecardIdAndUpdatedAt': {
                'items': [self.sample_data]
            }
        }
        
        experiments = Experiment.list_by_scorecard('scorecard-abc', self.mock_client)
        
        # Verify GraphQL call
        self.mock_client.execute.assert_called_once()
        call_args = self.mock_client.execute.call_args
        self.assertIn('listExperimentByScorecardIdAndUpdatedAt', call_args[0][0])
        
        variables = call_args[0][1]  # Second positional argument
        self.assertEqual(variables['scorecardId'], 'scorecard-abc')
        
        # Verify returned experiments
        self.assertEqual(len(experiments), 1)
        self.assertEqual(experiments[0].id, 'exp-123')
    
    def test_update(self):
        """Test updating an experiment."""
        experiment = Experiment.from_dict(self.sample_data, self.mock_client)
        
        updated_data = self.sample_data.copy()
        updated_data['featured'] = False
        updated_data['scoreId'] = 'new-score-123'
        updated_data['updatedAt'] = '2024-01-15T12:00:00Z'
        
        self.mock_client.execute.return_value = {
            'updateExperiment': updated_data
        }
        
        result = experiment.update(featured=False, scoreId='new-score-123')
        
        # Verify GraphQL call
        self.mock_client.execute.assert_called_once()
        call_args = self.mock_client.execute.call_args
        self.assertIn('updateExperiment', call_args[0][0])
        
        variables = call_args[0][1]  # Second positional argument
        input_data = variables['input']
        self.assertEqual(input_data['id'], 'exp-123')
        self.assertFalse(input_data['featured'])
        self.assertEqual(input_data['scoreId'], 'new-score-123')
        
        # Verify instance was updated
        self.assertFalse(experiment.featured)
        self.assertEqual(experiment.scoreId, 'new-score-123')
        self.assertEqual(result, experiment)
    
    def test_update_without_client(self):
        """Test that update raises error without client."""
        experiment = Experiment('exp-123', True, 'account-789', datetime.now(), datetime.now())
        
        with self.assertRaises(ValueError):
            experiment.update(featured=False)
    
    def test_delete(self):
        """Test deleting an experiment."""
        experiment = Experiment.from_dict(self.sample_data, self.mock_client)
        
        self.mock_client.execute.return_value = {
            'deleteExperiment': {'id': 'exp-123'}
        }
        
        result = experiment.delete()
        
        # Verify GraphQL call
        self.mock_client.execute.assert_called_once()
        call_args = self.mock_client.execute.call_args
        self.assertIn('deleteExperiment', call_args[0][0])
        
        variables = call_args[0][1]  # Second positional argument
        input_data = variables['input']
        self.assertEqual(input_data['id'], 'exp-123')
        
        # Verify result
        self.assertTrue(result)
    
    def test_delete_failure(self):
        """Test delete when API returns failure."""
        experiment = Experiment.from_dict(self.sample_data, self.mock_client)
        
        self.mock_client.execute.return_value = {
            'deleteExperiment': None
        }
        
        result = experiment.delete()
        self.assertFalse(result)
    
    def test_delete_without_client(self):
        """Test that delete raises error without client."""
        experiment = Experiment('exp-123', True, 'account-789', datetime.now(), datetime.now())
        
        with self.assertRaises(ValueError):
            experiment.delete()
    
    def test_get_root_node(self):
        """Test getting the root node."""
        experiment = Experiment.from_dict(self.sample_data, self.mock_client)
        
        mock_node = Mock()
        
        with patch('plexus.dashboard.api.models.experiment_node.ExperimentNode') as mock_node_class:
            mock_node_class.get_by_id.return_value = mock_node
            
            result = experiment.get_root_node()
            
            mock_node_class.get_by_id.assert_called_once_with('node-456', self.mock_client)
            self.assertEqual(result, mock_node)
    
    def test_get_root_node_without_root_id(self):
        """Test getting root node when no root node ID."""
        data = self.sample_data.copy()
        data['rootNodeId'] = None
        experiment = Experiment.from_dict(data, self.mock_client)
        
        result = experiment.get_root_node()
        self.assertIsNone(result)
    
    def test_get_root_node_without_client(self):
        """Test getting root node without client."""
        experiment = Experiment('exp-123', True, 'account-789', datetime.now(), datetime.now())
        experiment.rootNodeId = 'node-456'
        
        result = experiment.get_root_node()
        self.assertIsNone(result)
    
    def test_create_root_node(self):
        """Test creating a root node with initial version."""
        experiment = Experiment.from_dict(self.sample_data, self.mock_client)
        
        mock_node = Mock()
        mock_node.id = 'new-node-123'
        
        mock_version = Mock()
        mock_version.id = 'version-456'
        
        # Mock the update call
        updated_data = self.sample_data.copy()
        updated_data['rootNodeId'] = 'new-node-123'
        self.mock_client.execute.return_value = {
            'updateExperiment': updated_data
        }
        
        yaml_config = "class: BeamSearch"
        initial_value = {"test": True}
        
        with patch('plexus.dashboard.api.models.experiment_node.ExperimentNode') as mock_node_class, \
             patch('plexus.dashboard.api.models.experiment_node_version.ExperimentNodeVersion') as mock_version_class:
            
            mock_node_class.create.return_value = mock_node
            mock_version_class.create.return_value = mock_version
            
            result = experiment.create_root_node(yaml_config, initial_value)
            
            # Verify node creation
            mock_node_class.create.assert_called_once_with(
                client=self.mock_client,
                experimentId='exp-123',
                parentNodeId=None,
                status='ACTIVE'
            )
            
            # Verify version creation
            mock_version_class.create.assert_called_once_with(
                client=self.mock_client,
                experimentId='exp-123',
                nodeId='new-node-123',
                code=yaml_config,
                status='QUEUED',
                value=initial_value
            )
            
            # Verify experiment update
            call_args = self.mock_client.execute.call_args
            variables = call_args[0][1]  # Second positional argument
            input_data = variables['input']
            self.assertEqual(input_data['rootNodeId'], 'new-node-123')
            
            self.assertEqual(result, mock_node)
    
    def test_update_root_node(self):
        """Test updating the root node ID."""
        experiment = Experiment.from_dict(self.sample_data, self.mock_client)
        
        updated_data = self.sample_data.copy()
        updated_data['rootNodeId'] = 'new-root-node'
        updated_data['updatedAt'] = '2024-01-15T12:00:00Z'
        
        self.mock_client.execute.return_value = {
            'updateExperiment': updated_data
        }
        
        result = experiment.update_root_node('new-root-node')
        
        # Verify GraphQL call
        call_args = self.mock_client.execute.call_args
        variables = call_args[0][1]  # Second positional argument
        input_data = variables['input']
        self.assertEqual(input_data['id'], 'exp-123')
        self.assertEqual(input_data['rootNodeId'], 'new-root-node')
        
        # Verify instance was updated
        self.assertEqual(experiment.rootNodeId, 'new-root-node')
        self.assertEqual(result, experiment)


if __name__ == '__main__':
    unittest.main()