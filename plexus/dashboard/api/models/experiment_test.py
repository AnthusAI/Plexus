"""
Tests for Procedure Model.

Tests the Procedure model's functionality including:
- Creating procedures
- Listing and filtering procedures
- Updating procedure properties
- Managing root nodes
- Deleting procedures
"""

import pytest
import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from plexus.dashboard.api.models.procedure import Procedure


class TestProcedure(unittest.TestCase):
    """Test cases for the Procedure model."""
    
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
        fields = Procedure.fields()
        expected_fields = [
            'id', 'featured', 'rootNodeId', 'createdAt', 'updatedAt',
            'accountId', 'scorecardId', 'scoreId'
        ]
        
        for field in expected_fields:
            self.assertIn(field, fields)
    
    def test_from_dict(self):
        """Test creating a Procedure from dictionary data."""
        procedure = Procedure.from_dict(self.sample_data, self.mock_client)
        
        self.assertEqual(procedure.id, 'exp-123')
        self.assertTrue(procedure.featured)
        self.assertEqual(procedure.rootNodeId, 'node-456')
        self.assertEqual(procedure.accountId, 'account-789')
        self.assertEqual(procedure.scorecardId, 'scorecard-abc')
        self.assertEqual(procedure.scoreId, 'score-def')
        self.assertIsInstance(procedure.createdAt, datetime)
        self.assertIsInstance(procedure.updatedAt, datetime)
        self.assertEqual(procedure._client, self.mock_client)
    
    def test_from_dict_optional_fields(self):
        """Test creating a Procedure with optional fields missing."""
        minimal_data = {
            'id': 'exp-123',
            'createdAt': '2024-01-15T10:30:00Z',
            'updatedAt': '2024-01-15T11:00:00Z',
            'accountId': 'account-789'
        }
        
        procedure = Procedure.from_dict(minimal_data, self.mock_client)
        
        self.assertEqual(procedure.id, 'exp-123')
        self.assertFalse(procedure.featured)  # Should default to False
        self.assertIsNone(procedure.rootNodeId)
        self.assertIsNone(procedure.scorecardId)
        self.assertIsNone(procedure.scoreId)
    
    def test_create(self):
        """Test creating a new procedure."""
        self.mock_client.execute.return_value = {
            'createProcedure': self.sample_data
        }
        
        procedure = Procedure.create(
            client=self.mock_client,
            accountId='account-789',
            scorecardId='scorecard-abc',
            scoreId='score-def',
            featured=True
        )
        
        # Verify GraphQL call
        self.mock_client.execute.assert_called_once()
        call_args = self.mock_client.execute.call_args
        self.assertIn('createProcedure', call_args[0][0])
        
        # Get variables from call args - call_args is (args, kwargs)
        mutation_string = call_args[0][0]
        variables = call_args[0][1]  # Second positional argument
        input_data = variables['input']
        self.assertEqual(input_data['accountId'], 'account-789')
        self.assertEqual(input_data['scorecardId'], 'scorecard-abc')
        self.assertEqual(input_data['scoreId'], 'score-def')
        self.assertTrue(input_data['featured'])
        
        # Verify returned procedure
        self.assertEqual(procedure.id, 'exp-123')
        self.assertTrue(procedure.featured)
    
    def test_list_by_account(self):
        """Test listing procedures by account."""
        self.mock_client.execute.return_value = {
            'listProcedureByAccountIdAndUpdatedAt': {
                'items': [self.sample_data]
            }
        }
        
        procedures = Procedure.list_by_account('account-789', self.mock_client, limit=50)
        
        # Verify GraphQL call
        self.mock_client.execute.assert_called_once()
        call_args = self.mock_client.execute.call_args
        self.assertIn('listProcedureByAccountIdAndUpdatedAt', call_args[0][0])
        self.assertIn('sortDirection: DESC', call_args[0][0])
        
        variables = call_args[0][1]  # Second positional argument
        self.assertEqual(variables['accountId'], 'account-789')
        self.assertEqual(variables['limit'], 50)
        
        # Verify returned procedures
        self.assertEqual(len(procedures), 1)
        self.assertEqual(procedures[0].id, 'exp-123')
    
    def test_list_by_scorecard(self):
        """Test listing procedures by scorecard."""
        self.mock_client.execute.return_value = {
            'listProcedureByScorecardIdAndUpdatedAt': {
                'items': [self.sample_data]
            }
        }
        
        procedures = Procedure.list_by_scorecard('scorecard-abc', self.mock_client)
        
        # Verify GraphQL call
        self.mock_client.execute.assert_called_once()
        call_args = self.mock_client.execute.call_args
        self.assertIn('listProcedureByScorecardIdAndUpdatedAt', call_args[0][0])
        
        variables = call_args[0][1]  # Second positional argument
        self.assertEqual(variables['scorecardId'], 'scorecard-abc')
        
        # Verify returned procedures
        self.assertEqual(len(procedures), 1)
        self.assertEqual(procedures[0].id, 'exp-123')
    
    def test_update(self):
        """Test updating a procedure."""
        procedure = Procedure.from_dict(self.sample_data, self.mock_client)
        
        updated_data = self.sample_data.copy()
        updated_data['featured'] = False
        updated_data['scoreId'] = 'new-score-123'
        updated_data['updatedAt'] = '2024-01-15T12:00:00Z'
        
        self.mock_client.execute.return_value = {
            'updateProcedure': updated_data
        }
        
        result = procedure.update(featured=False, scoreId='new-score-123')
        
        # Verify GraphQL call
        self.mock_client.execute.assert_called_once()
        call_args = self.mock_client.execute.call_args
        self.assertIn('updateProcedure', call_args[0][0])
        
        variables = call_args[0][1]  # Second positional argument
        input_data = variables['input']
        self.assertEqual(input_data['id'], 'exp-123')
        self.assertFalse(input_data['featured'])
        self.assertEqual(input_data['scoreId'], 'new-score-123')
        
        # Verify instance was updated
        self.assertFalse(procedure.featured)
        self.assertEqual(procedure.scoreId, 'new-score-123')
        self.assertEqual(result, procedure)
    
    def test_update_without_client(self):
        """Test that update raises error without client."""
        procedure = Procedure('exp-123', True, 'account-789', datetime.now(), datetime.now())
        
        with self.assertRaises(ValueError):
            procedure.update(featured=False)
    
    def test_delete(self):
        """Test deleting a procedure."""
        procedure = Procedure.from_dict(self.sample_data, self.mock_client)
        
        self.mock_client.execute.return_value = {
            'deleteProcedure': {'id': 'exp-123'}
        }
        
        result = procedure.delete()
        
        # Verify GraphQL call
        self.mock_client.execute.assert_called_once()
        call_args = self.mock_client.execute.call_args
        self.assertIn('deleteProcedure', call_args[0][0])
        
        variables = call_args[0][1]  # Second positional argument
        input_data = variables['input']
        self.assertEqual(input_data['id'], 'exp-123')
        
        # Verify result
        self.assertTrue(result)
    
    def test_delete_failure(self):
        """Test delete when API returns failure."""
        procedure = Procedure.from_dict(self.sample_data, self.mock_client)
        
        self.mock_client.execute.return_value = {
            'deleteProcedure': None
        }
        
        result = procedure.delete()
        self.assertFalse(result)
    
    def test_delete_without_client(self):
        """Test that delete raises error without client."""
        procedure = Procedure('exp-123', True, 'account-789', datetime.now(), datetime.now())
        
        with self.assertRaises(ValueError):
            procedure.delete()
    
    def test_get_root_node(self):
        """Test getting the root node."""
        procedure = Procedure.from_dict(self.sample_data, self.mock_client)
        
        mock_node = Mock()
        
        with patch('plexus.dashboard.api.models.graph_node.GraphNode') as mock_node_class:
            mock_node_class.get_by_id.return_value = mock_node
            
            result = procedure.get_root_node()
            
            mock_node_class.get_by_id.assert_called_once_with('node-456', self.mock_client)
            self.assertEqual(result, mock_node)
    
    def test_get_root_node_without_root_id(self):
        """Test getting root node when no root node ID."""
        data = self.sample_data.copy()
        data['rootNodeId'] = None
        procedure = Procedure.from_dict(data, self.mock_client)
        
        result = procedure.get_root_node()
        self.assertIsNone(result)
    
    def test_get_root_node_without_client(self):
        """Test getting root node without client."""
        procedure = Procedure('exp-123', True, 'account-789', datetime.now(), datetime.now())
        procedure.rootNodeId = 'node-456'
        
        result = procedure.get_root_node()
        self.assertIsNone(result)
    
    def test_create_root_node(self):
        """Test creating a root node with initial metadata."""
        procedure = Procedure.from_dict(self.sample_data, self.mock_client)
        
        mock_node = Mock()
        mock_node.id = 'new-node-123'
        
        # Mock the update call
        updated_data = self.sample_data.copy()
        updated_data['rootNodeId'] = 'new-node-123'
        self.mock_client.execute.return_value = {
            'updateProcedure': updated_data
        }
        
        yaml_config = "class: BeamSearch"
        initial_metadata = {"test": True}
        
        with patch('plexus.dashboard.api.models.graph_node.GraphNode') as mock_node_class:
            
            mock_node_class.create.return_value = mock_node
            
            result = procedure.create_root_node(yaml_config, initial_metadata)
            
            # Verify node creation
            mock_node_class.create.assert_called_once_with(
                client=self.mock_client,
                procedureId='exp-123',
                parentNodeId=None,
                status='ACTIVE'
            )
            
            # Verify procedure update
            call_args = self.mock_client.execute.call_args
            variables = call_args[0][1]  # Second positional argument
            input_data = variables['input']
            self.assertEqual(input_data['rootNodeId'], 'new-node-123')
            
            self.assertEqual(result, mock_node)
    
    def test_update_root_node(self):
        """Test updating the root node ID."""
        procedure = Procedure.from_dict(self.sample_data, self.mock_client)
        
        updated_data = self.sample_data.copy()
        updated_data['rootNodeId'] = 'new-root-node'
        updated_data['updatedAt'] = '2024-01-15T12:00:00Z'
        
        self.mock_client.execute.return_value = {
            'updateProcedure': updated_data
        }
        
        result = procedure.update_root_node('new-root-node')
        
        # Verify GraphQL call
        call_args = self.mock_client.execute.call_args
        variables = call_args[0][1]  # Second positional argument
        input_data = variables['input']
        self.assertEqual(input_data['id'], 'exp-123')
        self.assertEqual(input_data['rootNodeId'], 'new-root-node')
        
        # Verify instance was updated
        self.assertEqual(procedure.rootNodeId, 'new-root-node')
        self.assertEqual(result, procedure)


if __name__ == '__main__':
    unittest.main()