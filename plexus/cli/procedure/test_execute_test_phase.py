"""
Tests for _execute_test_phase method in ProcedureService.

Tests the complete test phase workflow including:
- Creating ScoreVersions for hypothesis nodes
- Running evaluations for each ScoreVersion
- Generating LLM summaries of evaluation results
- Storing evaluation data in node metadata
- Resume from partial completion (versions or evaluations)
"""

import pytest
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json

from plexus.cli.procedure.service import ProcedureService


class TestExecuteTestPhase(unittest.IsolatedAsyncioTestCase):
    """Test cases for _execute_test_phase method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.service = ProcedureService(self.mock_client)

        # Mock procedure info
        self.mock_procedure = Mock()
        self.mock_procedure.id = 'proc-123'
        self.mock_procedure.accountId = 'account-789'
        self.mock_procedure.scoreId = 'score-def'
        self.mock_procedure.scorecardId = 'scorecard-abc'
        self.mock_procedure.rootNodeId = 'root-node-456'

        self.mock_procedure_info = Mock()
        self.mock_procedure_info.procedure = self.mock_procedure
        self.mock_procedure_info.scorecard_name = 'Test Scorecard'
        self.mock_procedure_info.score_name = 'Test Score'

        # Experiment context
        self.experiment_context = {
            'procedure_id': 'proc-123',
            'account_id': 'account-789',
            'scorecard_id': 'scorecard-abc',
            'score_id': 'score-def',
            'score_version_id': 'baseline-version-123',
            'scorecard_name': 'Test Scorecard',
            'score_name': 'Test Score'
        }

        # Mock evaluation result with correct structure
        self.mock_eval_result = {
            'evaluation_id': 'eval-123',
            'scorecard_id': 'scorecard-abc',
            'score_id': 'score-def',
            'accuracy': 64.0,  # Top-level, already in %
            'metrics': [
                {'name': 'Accuracy', 'value': 64.0},
                {'name': 'Alignment', 'value': 45.2},
                {'name': 'Precision', 'value': 73.2},
                {'name': 'Recall', 'value': 81.1}
            ],
            'confusionMatrix': {
                'yes_yes': 20,
                'yes_no': 5,
                'no_yes': 10,
                'no_no': 15
            }
        }

    def _create_mock_node(self, node_id, has_version=False, has_eval=False, parent_id='root'):
        """Helper to create a mock GraphNode with specified state."""
        node = Mock()
        node.id = node_id
        node.parentNodeId = parent_id

        metadata = {
            'hypothesis': f'Test hypothesis for node {node_id}'
        }

        if has_version:
            metadata['scoreVersionId'] = f'version-{node_id}'

        if has_eval:
            metadata['evaluation_id'] = f'eval-{node_id}'
            metadata['evaluation_summary'] = f'Summary for node {node_id}'

        node.metadata = json.dumps(metadata)

        return node

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    async def test_all_nodes_complete(self, mock_graphnode):
        """Test when all hypothesis nodes already have versions and evaluations."""
        # Setup: All nodes are complete
        complete_node1 = self._create_mock_node('node-1', has_version=True, has_eval=True)
        complete_node2 = self._create_mock_node('node-2', has_version=True, has_eval=True)

        mock_graphnode.list_by_procedure.return_value = [complete_node1, complete_node2]

        # Execute
        result = await self.service._execute_test_phase(
            procedure_id='proc-123',
            procedure_info=self.mock_procedure_info,
            experiment_context=self.experiment_context
        )

        # Verify: Should return success without doing any work
        self.assertTrue(result['success'])
        self.assertEqual(result['nodes_tested'], 0)
        self.assertEqual(result['nodes_skipped'], 2)
        self.assertIn('already have ScoreVersions and evaluations', result['message'])

        # Verify: No work was done (all nodes already complete)

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent')
    async def test_resume_from_partial_version_creation(self, mock_agent_class, mock_graphnode):
        """Test resuming when some nodes have versions but others don't."""
        # Setup: 1 node needs version, 1 already has version (needs eval)
        node_needs_version = self._create_mock_node('node-1', has_version=False, has_eval=False)
        node_has_version = self._create_mock_node('node-2', has_version=True, has_eval=False)

        mock_graphnode.list_by_procedure.return_value = [node_needs_version, node_has_version]

        # Mock TestPhaseAgent
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        mock_agent.cleanup = Mock()

        # Mock ScoreVersion creation success
        mock_agent.execute = AsyncMock(return_value={
            'success': True,
            'score_version_id': 'new-version-1',
            'node_id': 'node-1'
        })

        # Mock GraphNode.get_by_id to return updated node after version creation
        updated_node1 = self._create_mock_node('node-1', has_version=True, has_eval=False)
        mock_graphnode.get_by_id.side_effect = [updated_node1, node_has_version]

        # Mock evaluation and summary generation
        with patch.object(self.service, '_run_evaluation_for_hypothesis_node', new_callable=AsyncMock) as mock_eval, \
             patch.object(self.service, '_create_evaluation_summary', new_callable=AsyncMock) as mock_summary, \
             patch.object(self.service, '_update_node_with_evaluation', new_callable=AsyncMock) as mock_update:

            mock_eval.return_value = self.mock_eval_result
            mock_summary.return_value = "Hypothesis validated. Accuracy improved to 64%."
            mock_update.return_value = True

            # Execute
            result = await self.service._execute_test_phase(
                procedure_id='proc-123',
                procedure_info=self.mock_procedure_info,
                experiment_context=self.experiment_context
            )

        # Verify: Created version for 1 node, evaluated both nodes
        self.assertTrue(result['success'])
        self.assertEqual(result['nodes_needing_versions'], 1)
        self.assertEqual(result['nodes_needing_evaluation'], 1)
        self.assertEqual(result['nodes_successful'], 2)
        self.assertEqual(result['nodes_failed'], 0)

        # Verify: TestPhaseAgent was used
        mock_agent.execute.assert_called_once()
        mock_agent.cleanup.assert_called_once()

        # Verify: Evaluations ran for both nodes
        self.assertEqual(mock_eval.call_count, 2)
        self.assertEqual(mock_summary.call_count, 2)
        self.assertEqual(mock_update.call_count, 2)

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    async def test_resume_from_partial_evaluation(self, mock_graphnode):
        """Test resuming when all nodes have versions but some need evaluation."""
        # Setup: All nodes have versions, 1 already has eval, 1 needs eval
        node_complete = self._create_mock_node('node-1', has_version=True, has_eval=True)
        node_needs_eval = self._create_mock_node('node-2', has_version=True, has_eval=False)

        mock_graphnode.list_by_procedure.return_value = [node_complete, node_needs_eval]

        # Mock evaluation and summary generation
        with patch.object(self.service, '_run_evaluation_for_hypothesis_node', new_callable=AsyncMock) as mock_eval, \
             patch.object(self.service, '_create_evaluation_summary', new_callable=AsyncMock) as mock_summary, \
             patch.object(self.service, '_update_node_with_evaluation', new_callable=AsyncMock) as mock_update:

            mock_eval.return_value = self.mock_eval_result
            mock_summary.return_value = "Hypothesis not validated. Accuracy decreased to 64%."
            mock_update.return_value = True

            # Execute
            result = await self.service._execute_test_phase(
                procedure_id='proc-123',
                procedure_info=self.mock_procedure_info,
                experiment_context=self.experiment_context
            )

        # Verify: No versions created, only 1 evaluation ran
        self.assertTrue(result['success'])
        self.assertEqual(result['nodes_needing_versions'], 0)
        self.assertEqual(result['nodes_needing_evaluation'], 1)
        self.assertEqual(result['nodes_successful'], 1)
        self.assertEqual(result['nodes_failed'], 0)

        # Verify: Evaluation ran only for node needing eval
        mock_eval.assert_called_once()
        mock_summary.assert_called_once()
        mock_update.assert_called_once()

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    @patch('plexus.cli.procedure.test_phase_agent.TestPhaseAgent')
    async def test_version_creation_failure(self, mock_agent_class, mock_graphnode):
        """Test handling of ScoreVersion creation failure."""
        # Setup: 2 nodes need versions
        node1 = self._create_mock_node('node-1', has_version=False)
        node2 = self._create_mock_node('node-2', has_version=False)

        mock_graphnode.list_by_procedure.return_value = [node1, node2]

        # Mock TestPhaseAgent with one success, one failure
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        mock_agent.cleanup = Mock()

        mock_agent.execute = AsyncMock(side_effect=[
            {'success': True, 'score_version_id': 'new-version-1', 'node_id': 'node-1'},
            {'success': False, 'error': 'YAML validation failed', 'node_id': 'node-2'}
        ])

        # Execute
        result = await self.service._execute_test_phase(
            procedure_id='proc-123',
            procedure_info=self.mock_procedure_info,
            experiment_context=self.experiment_context
        )

        # Verify: Should fail and not proceed to evaluation
        self.assertFalse(result['success'])
        self.assertEqual(result['nodes_tested'], 2)
        self.assertEqual(result['nodes_successful'], 1)
        self.assertEqual(result['nodes_failed'], 1)
        self.assertIn('ScoreVersion creation failed', result['message'])

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    async def test_evaluation_failure_handling(self, mock_graphnode):
        """Test handling when evaluation fails for some nodes."""
        # Setup: All nodes have versions, need evaluation
        node1 = self._create_mock_node('node-1', has_version=True, has_eval=False)
        node2 = self._create_mock_node('node-2', has_version=True, has_eval=False)

        mock_graphnode.list_by_procedure.return_value = [node1, node2]

        # Mock evaluation: one success, one failure
        with patch.object(self.service, '_run_evaluation_for_hypothesis_node', new_callable=AsyncMock) as mock_eval, \
             patch.object(self.service, '_create_evaluation_summary', new_callable=AsyncMock) as mock_summary, \
             patch.object(self.service, '_update_node_with_evaluation', new_callable=AsyncMock) as mock_update:

            # First call succeeds, second fails
            mock_eval.side_effect = [self.mock_eval_result, None]
            mock_summary.return_value = "Summary"
            mock_update.return_value = True

            # Execute
            result = await self.service._execute_test_phase(
                procedure_id='proc-123',
                procedure_info=self.mock_procedure_info,
                experiment_context=self.experiment_context
            )

        # Verify: Should report partial success
        self.assertFalse(result['success'])  # Overall failure due to 1 failed eval
        self.assertEqual(result['nodes_successful'], 1)
        self.assertEqual(result['nodes_failed'], 1)

        # Verify: Summary was only called for successful evaluation
        mock_summary.assert_called_once()
        mock_update.assert_called_once()

    async def test_create_evaluation_summary_with_correct_metrics(self):
        """Test that _create_evaluation_summary correctly parses metrics list."""
        # Create a mock node with hypothesis
        node = self._create_mock_node('node-1', has_version=True)

        # Mock LLM call
        with patch('langchain_openai.ChatOpenAI') as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            mock_response = Mock()
            mock_response.content = "Test summary of evaluation results."
            mock_llm.invoke.return_value = mock_response

            # Execute
            summary = await self.service._create_evaluation_summary(node, self.mock_eval_result)

        # Verify: Summary was generated
        self.assertEqual(summary, "Test summary of evaluation results.")

        # Verify: LLM was called with correct data structure
        mock_llm.invoke.assert_called_once()
        call_args = mock_llm.invoke.call_args[0][0]

        # Find the HumanMessage with the metrics
        human_message = None
        for msg in call_args:
            if hasattr(msg, 'content') and 'Accuracy:' in msg.content:
                human_message = msg.content
                break

        # Verify metrics were extracted correctly
        self.assertIn('Accuracy: 64.0', human_message)
        self.assertIn('AC1 Agreement: 45.2', human_message)  # The prompt says "AC1 Agreement"

    async def test_create_evaluation_summary_fallback(self):
        """Test that _create_evaluation_summary falls back gracefully on error."""
        # Create a mock node
        node = self._create_mock_node('node-1', has_version=True)

        # Mock LLM to raise an error
        with patch('langchain_openai.ChatOpenAI') as mock_llm_class:
            mock_llm_class.side_effect = Exception("API error")

            # Execute
            summary = await self.service._create_evaluation_summary(node, self.mock_eval_result)

        # Verify: Fallback summary was generated
        self.assertIn('Evaluation complete', summary)
        self.assertIn('64.0', summary)  # Accuracy
        self.assertIn('45.2', summary)  # Alignment

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    async def test_no_hypothesis_nodes(self, mock_graphnode):
        """Test when there are no hypothesis nodes to test."""
        # Setup: Only root node exists (no children)
        mock_graphnode.list_by_procedure.return_value = []

        # Execute
        result = await self.service._execute_test_phase(
            procedure_id='proc-123',
            procedure_info=self.mock_procedure_info,
            experiment_context=self.experiment_context
        )

        # Verify: Should return failure with appropriate message
        self.assertFalse(result['success'])
        self.assertEqual(result['nodes_tested'], 0)
        self.assertIn('No hypothesis nodes found', result['error'])


if __name__ == '__main__':
    unittest.main()
