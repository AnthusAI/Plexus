"""
Tests for TestPhaseAgent.

Tests the TestPhaseAgent functionality including:
- Creating ScoreVersions from hypotheses
- YAML editing with LLM
- YAML validation with and without test items
- Handling missing test items gracefully
"""

import pytest
import unittest
from unittest.mock import Mock, patch, AsyncMock, mock_open, MagicMock
import tempfile
import os

from plexus.cli.procedure.test_phase_agent import TestPhaseAgent


class TestTestPhaseAgent(unittest.IsolatedAsyncioTestCase):
    """Test cases for the TestPhaseAgent."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.agent = TestPhaseAgent(self.mock_client)

        # Valid YAML content
        self.valid_yaml = """
name: Test Score
type: SimpleLLMScore
nodes:
  - id: evaluate
    type: llm
    prompt: "Evaluate the input"
"""

        # Mock hypothesis node
        self.mock_hypothesis_node = Mock()
        self.mock_hypothesis_node.id = 'node-123'
        self.mock_hypothesis_node.metadata = '{"hypothesis": "Make the prompt more lenient"}'

        # Mock procedure context
        self.procedure_context = {
            'scorecard_name': 'Test Scorecard',
            'score_name': 'Test Score',
            'score_id': 'score-123',
            'scorecard_id': 'scorecard-456',
            'score_yaml_format_docs': 'Score YAML documentation...'
        }

    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self.agent, 'temp_dir') and self.agent.temp_dir and os.path.exists(self.agent.temp_dir):
            import shutil
            shutil.rmtree(self.agent.temp_dir)

    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._push_new_version')
    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._validate_yaml')
    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._edit_yaml_with_llm')
    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._create_temp_copy')
    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._pull_score_yaml')
    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._update_node_metadata')
    async def test_execute_success(
        self,
        mock_update_metadata,
        mock_pull_yaml,
        mock_create_temp,
        mock_edit_yaml,
        mock_validate,
        mock_push
    ):
        """Test successful execution of test phase."""
        # Setup mocks
        mock_pull_yaml.return_value = '/tmp/score.yaml'
        mock_create_temp.return_value = '/tmp/temp_score.yaml'
        mock_edit_yaml.return_value = True
        mock_validate.return_value = {'success': True}
        mock_push.return_value = 'new-version-123'
        mock_update_metadata.return_value = True

        # Execute
        result = await self.agent.execute(
            self.mock_hypothesis_node,
            'baseline-version-456',
            self.procedure_context
        )

        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['score_version_id'], 'new-version-123')
        self.assertEqual(result['node_id'], 'node-123')

        # Verify all steps were called
        mock_pull_yaml.assert_called_once_with('baseline-version-456', self.procedure_context)
        mock_create_temp.assert_called_once_with('/tmp/score.yaml')
        mock_edit_yaml.assert_called_once()
        mock_validate.assert_called_once()
        mock_push.assert_called_once()
        mock_update_metadata.assert_called_once_with('node-123', 'new-version-123')

    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._pull_score_yaml')
    async def test_execute_pull_failure(self, mock_pull_yaml):
        """Test execution when pulling YAML fails."""
        mock_pull_yaml.return_value = None

        result = await self.agent.execute(
            self.mock_hypothesis_node,
            'baseline-version-456',
            self.procedure_context
        )

        self.assertFalse(result['success'])
        self.assertIn('Failed to pull score YAML', result['error'])

    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._edit_yaml_with_llm')
    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._create_temp_copy')
    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._pull_score_yaml')
    async def test_execute_edit_failure(self, mock_pull_yaml, mock_create_temp, mock_edit_yaml):
        """Test execution when LLM editing fails."""
        mock_pull_yaml.return_value = '/tmp/score.yaml'
        mock_create_temp.return_value = '/tmp/temp_score.yaml'
        mock_edit_yaml.return_value = False

        result = await self.agent.execute(
            self.mock_hypothesis_node,
            'baseline-version-456',
            self.procedure_context
        )

        self.assertFalse(result['success'])
        self.assertIn('LLM failed to edit YAML', result['error'])

    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._validate_yaml')
    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._edit_yaml_with_llm')
    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._create_temp_copy')
    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent._pull_score_yaml')
    async def test_execute_validation_failure(self, mock_pull_yaml, mock_create_temp, mock_edit_yaml, mock_validate):
        """Test execution when YAML validation fails."""
        mock_pull_yaml.return_value = '/tmp/score.yaml'
        mock_create_temp.return_value = '/tmp/temp_score.yaml'
        mock_edit_yaml.return_value = True
        mock_validate.return_value = {
            'success': False,
            'error': 'Invalid YAML syntax'
        }

        result = await self.agent.execute(
            self.mock_hypothesis_node,
            'baseline-version-456',
            self.procedure_context
        )

        self.assertFalse(result['success'])
        self.assertIn('YAML validation failed', result['error'])

    async def test_pull_score_yaml_success(self):
        """Test successful pulling of score YAML."""
        # Mock GraphQL response
        self.mock_client.execute.return_value = {
            'getScoreVersion': {
                'id': 'version-123',
                'configuration': self.valid_yaml
            }
        }

        with patch('plexus.cli.shared.get_score_yaml_path') as mock_get_path, \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('os.makedirs'):

            mock_get_path.return_value = '/tmp/scorecards/Test Scorecard/Test Score.yaml'

            result = await self.agent._pull_score_yaml('version-123', self.procedure_context)

            self.assertEqual(result, '/tmp/scorecards/Test Scorecard/Test Score.yaml')
            mock_file.assert_called_once()

    async def test_pull_score_yaml_not_found(self):
        """Test pulling YAML when version doesn't exist."""
        self.mock_client.execute.return_value = {
            'getScoreVersion': None
        }

        result = await self.agent._pull_score_yaml('missing-version', self.procedure_context)

        self.assertIsNone(result)

    def test_create_temp_copy(self):
        """Test creating a temporary copy of YAML file."""
        # Create a real temp file to copy from
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.valid_yaml)
            source_path = f.name

        try:
            result = self.agent._create_temp_copy(source_path)

            # Verify temp file exists
            self.assertTrue(os.path.exists(result))

            # Verify content matches
            with open(result, 'r') as f:
                content = f.read()
            self.assertEqual(content, self.valid_yaml)

            # Verify temp directory was created
            self.assertIsNotNone(self.agent.temp_dir)
            self.assertTrue(os.path.exists(self.agent.temp_dir))

        finally:
            os.unlink(source_path)

    async def test_validate_yaml_syntax_valid(self):
        """Test YAML validation with valid syntax."""
        # Create temp file with valid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.valid_yaml)
            yaml_path = f.name

        try:
            result = await self.agent._validate_yaml(yaml_path, self.procedure_context)

            self.assertTrue(result['success'])
        finally:
            os.unlink(yaml_path)

    async def test_validate_yaml_syntax_invalid(self):
        """Test YAML validation with invalid syntax."""
        invalid_yaml = "invalid: yaml: [unclosed"

        # Create temp file with invalid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(invalid_yaml)
            yaml_path = f.name

        try:
            result = await self.agent._validate_yaml(yaml_path, self.procedure_context)

            self.assertFalse(result['success'])
            self.assertIn('Invalid YAML syntax', result['error'])
        finally:
            os.unlink(yaml_path)

    async def test_validate_yaml_no_test_items_skips_predictions(self):
        """
        Test YAML validation gracefully skips prediction testing when no test items are available.

        This is the critical test case that locks in the behavior observed in the logs:
        "No test items available, skipping prediction validation"
        """
        # Create temp file with valid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.valid_yaml)
            yaml_path = f.name

        try:
            # Context has no evaluation_results or test items
            context = {
                'scorecard_name': 'Test Scorecard',
                'score_name': 'Test Score',
                # No 'evaluation_results' key
            }

            with patch('plexus.cli.procedure.test_phase_agent.logger') as mock_logger:
                result = await self.agent._validate_yaml(yaml_path, context)

                # Should succeed without running predictions
                self.assertTrue(result['success'])

                # Should log that prediction validation was skipped
                mock_logger.info.assert_any_call("No test items available, skipping prediction validation")
        finally:
            os.unlink(yaml_path)

    async def test_validate_yaml_with_test_items_runs_predictions(self):
        """
        Test YAML validation runs predictions when test items are available.

        This ensures we don't accidentally break the prediction testing path.
        """
        # Create temp file with valid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.valid_yaml)
            yaml_path = f.name

        try:
            # Context has test items
            context = {
                'scorecard_name': 'Test Scorecard',
                'score_name': 'Test Score',
                'evaluation_results': '{"sample_items": ["item-1", "item-2"]}'
            }

            # Mock the MCP predict function
            mock_predict_fn = AsyncMock(return_value={'success': True, 'value': 'yes'})

            with patch('fastmcp.FastMCP') as mock_mcp_class, \
                 patch('MCP.tools.prediction.predictions.register_prediction_tools'), \
                 patch('plexus.cli.procedure.test_phase_agent.logger') as mock_logger:

                # Setup mock MCP instance
                mock_mcp = MagicMock()
                mock_tool = Mock()
                mock_tool.name = 'plexus_predict'
                mock_tool.fn = mock_predict_fn
                mock_mcp.list_tools.return_value = [mock_tool]
                mock_mcp_class.return_value = mock_mcp

                result = await self.agent._validate_yaml(yaml_path, context)

                # Should succeed after running predictions
                self.assertTrue(result['success'])

                # Should log that predictions were tested
                mock_logger.info.assert_any_call("Testing with 2 sample items")

                # Verify predictions were called
                self.assertEqual(mock_predict_fn.call_count, 2)
        finally:
            os.unlink(yaml_path)

    async def test_validate_yaml_prediction_error_fails_validation(self):
        """
        Test YAML validation fails when predictions encounter errors.
        """
        # Create temp file with valid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.valid_yaml)
            yaml_path = f.name

        try:
            # Context has test items
            context = {
                'scorecard_name': 'Test Scorecard',
                'score_name': 'Test Score',
                'evaluation_results': '{"sample_items": ["item-1"]}'
            }

            # Mock predict function that raises an error
            mock_predict_fn = AsyncMock(side_effect=Exception("Prediction failed"))

            with patch('fastmcp.FastMCP') as mock_mcp_class, \
                 patch('MCP.tools.prediction.predictions.register_prediction_tools'):

                # Setup mock MCP instance
                mock_mcp = MagicMock()
                mock_tool = Mock()
                mock_tool.name = 'plexus_predict'
                mock_tool.fn = mock_predict_fn
                mock_mcp.list_tools.return_value = [mock_tool]
                mock_mcp_class.return_value = mock_mcp

                result = await self.agent._validate_yaml(yaml_path, context)

                # Should fail validation
                self.assertFalse(result['success'])
                self.assertIn('Prediction error', result['error'])
        finally:
            os.unlink(yaml_path)

    async def test_push_new_version_success(self):
        """Test successful pushing of new ScoreVersion."""
        # Create temp file with YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.valid_yaml)
            yaml_path = f.name

        try:
            # Mock Score model
            with patch('plexus.dashboard.api.models.score.Score') as mock_score_class:
                mock_score = Mock()
                mock_score.create_version_from_code.return_value = {
                    'success': True,
                    'version_id': 'new-version-789'
                }
                mock_score_class.get_by_id.return_value = mock_score

                result = await self.agent._push_new_version(
                    yaml_path,
                    'parent-version-456',
                    self.procedure_context,
                    self.mock_hypothesis_node
                )

                self.assertEqual(result, 'new-version-789')
                mock_score.create_version_from_code.assert_called_once()
        finally:
            os.unlink(yaml_path)

    async def test_push_new_version_failure(self):
        """Test pushing new version when creation fails."""
        # Create temp file with YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.valid_yaml)
            yaml_path = f.name

        try:
            # Mock Score model with failure
            with patch('plexus.dashboard.api.models.score.Score') as mock_score_class:
                mock_score = Mock()
                mock_score.create_version_from_code.return_value = {
                    'success': False,
                    'message': 'Creation failed'
                }
                mock_score_class.get_by_id.return_value = mock_score

                result = await self.agent._push_new_version(
                    yaml_path,
                    'parent-version-456',
                    self.procedure_context,
                    self.mock_hypothesis_node
                )

                self.assertIsNone(result)
        finally:
            os.unlink(yaml_path)

    async def test_update_node_metadata_success(self):
        """Test successful update of GraphNode metadata."""
        with patch('plexus.dashboard.api.models.graph_node.GraphNode') as mock_node_class:
            mock_node = Mock()
            mock_node.metadata = '{"hypothesis": "Test"}'
            mock_node_class.get_by_id.return_value = mock_node

            result = await self.agent._update_node_metadata('node-123', 'version-789')

            self.assertTrue(result)
            mock_node.update_content.assert_called_once()

            # Verify metadata includes scoreVersionId
            call_args = mock_node.update_content.call_args
            metadata = call_args.kwargs['metadata']
            self.assertEqual(metadata['scoreVersionId'], 'version-789')

    def test_cleanup(self):
        """Test cleanup of temporary directory."""
        # Create temp directory
        self.agent.temp_dir = tempfile.mkdtemp(prefix="plexus_test_")
        temp_dir = self.agent.temp_dir

        # Verify it exists
        self.assertTrue(os.path.exists(temp_dir))

        # Cleanup
        self.agent.cleanup()

        # Verify it's gone
        self.assertFalse(os.path.exists(temp_dir))


if __name__ == '__main__':
    unittest.main()
