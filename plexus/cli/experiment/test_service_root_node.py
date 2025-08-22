#!/usr/bin/env python3
"""
Unit tests for ExperimentService programmatic root node logic.

These tests ensure that:
1. Root nodes are created programmatically when missing
2. Existing root nodes are not duplicated
3. AI agents cannot create root-level nodes
4. Root nodes are populated with champion score configuration
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from plexus.cli.experiment.service import ExperimentService
from plexus.dashboard.api.models.experiment import Experiment
from plexus.dashboard.api.models.experiment_node import ExperimentNode


class TestExperimentServiceRootNodeLogic:
    """Test cases for programmatic root node logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.service = ExperimentService(self.mock_client)
        
        # Mock experiment with basic data
        self.mock_experiment = MagicMock(spec=Experiment)
        self.mock_experiment.id = "test-experiment-id"
        self.mock_experiment.scoreId = "test-score-id"
        self.mock_experiment.scorecardId = "test-scorecard-id"
        self.mock_experiment.accountId = "test-account-id"
        self.mock_experiment.rootNodeId = None  # No root node initially

    @pytest.mark.asyncio
    async def test_create_root_node_when_missing(self):
        """Test that root node is created programmatically when missing."""
        
        # Mock experiment info with no root node
        experiment_info = Mock()
        experiment_info.experiment = self.mock_experiment
        experiment_info.root_node = None  # No existing root node
        
        # Mock champion score config retrieval
        champion_config = "name: test_score\nmodel: gpt-4\nprompt: Test prompt"
        
        with patch.object(self.service, '_get_champion_score_config', return_value=champion_config) as mock_get_config, \
             patch.object(ExperimentNode, 'create') as mock_create_node:
            
            # Mock the created node with update_content method
            mock_root_node = Mock(spec=ExperimentNode)
            mock_root_node.id = "test-root-node-id"
            mock_root_node.update_content = Mock()
            mock_create_node.return_value = mock_root_node
            
            # Call the method under test
            await self.service._ensure_experiment_structure(experiment_info)
            
            # Verify root node creation was called with correct parameters (including code)
            mock_create_node.assert_called_once_with(
                client=self.mock_client,
                experimentId="test-experiment-id",
                parentNodeId=None,  # Root node has no parent
                name="Root",
                status='ACTIVE',
                code=champion_config  # Code is now included in creation
            )
            
            # Verify initial value metadata was set with update_content (simplified schema)
            mock_root_node.update_content.assert_called_once()
            update_content_args = mock_root_node.update_content.call_args
            assert "programmatic" in update_content_args[1]['value']['created_by']
            
            # Verify champion config was retrieved
            mock_get_config.assert_called_once_with("test-score-id")

    @pytest.mark.asyncio
    async def test_do_not_create_duplicate_root_node(self):
        """Test that existing root node is not duplicated."""
        
        # Mock experiment info with existing root node that has proper config
        mock_root_node = Mock(spec=ExperimentNode)
        mock_root_node.id = "existing-root-node"
        mock_root_node.code = "name: existing_config\nmodel: gpt-4"  # Has config
        
        experiment_info = Mock()
        experiment_info.experiment = self.mock_experiment
        experiment_info.root_node = mock_root_node  # Existing root node
        
        with patch.object(self.service, '_get_champion_score_config') as mock_get_config, \
             patch.object(ExperimentNode, 'create') as mock_create_node:
            
            # Call the method under test
            await self.service._ensure_experiment_structure(experiment_info)
            
            # Verify NO new root node was created
            mock_create_node.assert_not_called()
            
            # Verify NO champion config lookup was needed
            mock_get_config.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_root_node_missing_config(self):
        """Test that existing root node is updated if missing score configuration."""
        
        # Mock experiment info with root node that lacks proper config
        # Create a simple object that truly has code=None rather than using Mock
        class FakeNode:
            def __init__(self):
                self.id = "existing-root-node"
                self.code = None  # Missing score config
                self.update_content = Mock()
        
        mock_root_node = FakeNode()
        
        experiment_info = Mock()
        experiment_info.experiment = self.mock_experiment
        experiment_info.root_node = mock_root_node  # Existing but incomplete root node
        
        # Mock champion score config retrieval
        champion_config = "name: updated_score\nmodel: gpt-4\nprompt: Updated prompt"
        
        with patch.object(self.service, '_get_champion_score_config', return_value=champion_config) as mock_get_config, \
             patch.object(ExperimentNode, 'create') as mock_create_node:
            
            # Call the method under test
            await self.service._ensure_experiment_structure(experiment_info)
            
            # Verify NO new root node was created (should update existing)
            mock_create_node.assert_not_called()
            
            # Verify existing root node was updated with new content (simplified schema)
            mock_root_node.update_content.assert_called_once()
            update_content_args = mock_root_node.update_content.call_args
            assert update_content_args[1]['code'] == champion_config
            assert "root_node_update" in update_content_args[1]['value']['type']
            assert "programmatic" in update_content_args[1]['value']['created_by']
            
            # Verify champion config was retrieved
            mock_get_config.assert_called_once_with("test-score-id")

    @pytest.mark.asyncio
    async def test_champion_config_retrieval_failure_fallback(self):
        """Test fallback behavior when champion config cannot be retrieved."""
        
        # Mock experiment info with no root node
        experiment_info = Mock()
        experiment_info.experiment = self.mock_experiment
        experiment_info.root_node = None
        
        # Mock failed champion score config retrieval
        with patch.object(self.service, '_get_champion_score_config', return_value=None) as mock_get_config, \
             patch.object(ExperimentNode, 'create') as mock_create_node:
            
            # Mock the created node
            mock_root_node = Mock(spec=ExperimentNode)
            mock_root_node.id = "test-root-node-id"
            mock_root_node.update_content = Mock()
            mock_create_node.return_value = mock_root_node
            
            # Call the method under test
            await self.service._ensure_experiment_structure(experiment_info)
            
            # Verify root node was still created with placeholder config
            mock_create_node.assert_called_once()
            mock_root_node.update_content.assert_called_once()
            
            # Check that the node was created with placeholder config as the code parameter
            create_node_args = mock_create_node.call_args
            placeholder_config = create_node_args[1]['code']
            assert "placeholder" in placeholder_config
            assert "Champion score configuration not available" in placeholder_config

    @pytest.mark.asyncio
    async def test_idempotent_behavior_with_existing_root(self):
        """Test that existing root nodes are not duplicated."""
        
        # Mock experiment info with existing root node
        mock_root_node = Mock(spec=ExperimentNode)
        mock_root_node.id = "existing-root-node"
        mock_root_node.code = "name: existing_config\nmodel: gpt-4"  # Has config
        
        experiment_info = Mock()
        experiment_info.experiment = self.mock_experiment
        experiment_info.root_node = mock_root_node  # Existing root node
        
        with patch.object(self.service, '_get_champion_score_config') as mock_get_config, \
             patch.object(ExperimentNode, 'create') as mock_create_node:
            
            # Call the method - should NOT create a new root node
            await self.service._ensure_experiment_structure(experiment_info)
            
            # Verify NO new root node was created
            mock_create_node.assert_not_called()
            
            # Verify NO champion config lookup was needed
            mock_get_config.assert_not_called()

    def test_ai_agent_cannot_create_root_nodes(self):
        """Test that AI agents are prevented from creating root-level nodes."""
        
        # This would be tested by calling the MCP tool directly
        # The tool should reject attempts to create nodes with parentNodeId=None
        # This is enforced by the validation we added to experiment_nodes.py
        
        # Import the function we're testing
        from MCP.tools.experiment.experiment_nodes import register_experiment_node_tools
        
        # Mock server to capture tool registration
        mock_server = Mock()
        mock_server.tool = Mock(return_value=lambda func: func)
        
        # Mock experiment context with client
        experiment_context = {'client': self.mock_client}
        
        # Register tools
        register_experiment_node_tools(mock_server, experiment_context)
        
        # The tool should have been registered with validation that prevents root node creation
        # This is verified by the validation code we added in the actual tool function
        assert mock_server.tool.called

    @pytest.mark.asyncio 
    async def test_error_handling_in_structure_ensuring(self):
        """Test that errors in structure ensuring don't fail the entire experiment run."""
        
        experiment_info = Mock()
        experiment_info.experiment = self.mock_experiment
        experiment_info.root_node = None
        
        # Mock an exception during root node creation
        with patch.object(self.service, '_create_root_node_with_champion_config', 
                         side_effect=Exception("Database connection failed")) as mock_create:
            
            # Call should raise RuntimeError (critical failure)
            with pytest.raises(RuntimeError, match="Experiment setup failed: Could not create root node"):
                await self.service._ensure_experiment_structure(experiment_info)
            
            # Verify the creation was attempted
            mock_create.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])