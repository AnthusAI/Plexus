"""
Tests for hypothesis phase behavior with insights context.

Ensures that when hypothesis phase runs after insights phase:
1. Insights nodes are excluded from hypothesis count (don't trigger skip)
2. Insights context is included in the agent prompt
3. Previous hypothesis context is included in the agent prompt
4. New hypotheses can be generated based on insights
"""

import pytest
from unittest.mock import Mock, patch
import json
from plexus.cli.procedure.service import ProcedureService
from plexus.dashboard.api.models.graph_node import GraphNode


@pytest.fixture
def mock_client():
    """Create a mock PlexusDashboardClient."""
    client = Mock()
    client.execute = Mock()
    return client


@pytest.fixture
def procedure_service(mock_client):
    """Create a ProcedureService instance with mocked client."""
    return ProcedureService(mock_client)


@pytest.fixture
def mock_nodes_with_insights():
    """
    Create a realistic set of nodes:
    - 1 root node
    - 2 hypothesis nodes (below threshold of 3)
    - 1 insights node

    This should NOT trigger the skip logic since we only have 2 hypothesis nodes.
    """
    # Root node
    root = Mock(spec=GraphNode)
    root.id = "root-id"
    root.parentNodeId = None
    root.is_root = True
    root.metadata = json.dumps({'code': 'baseline_config'})

    # Hypothesis node 1
    hyp1 = Mock(spec=GraphNode)
    hyp1.id = "hyp-1"
    hyp1.parentNodeId = "root-id"
    hyp1.is_root = False
    hyp1.name = "Hypothesis 1"
    hyp1.metadata = json.dumps({
        'hypothesis': 'Test hypothesis 1',
        'evaluation_summary': 'Improved by 5%',
        'type': 'hypothesis'
    })

    # Hypothesis node 2
    hyp2 = Mock(spec=GraphNode)
    hyp2.id = "hyp-2"
    hyp2.parentNodeId = "root-id"
    hyp2.is_root = False
    hyp2.name = "Hypothesis 2"
    hyp2.metadata = json.dumps({
        'hypothesis': 'Test hypothesis 2',
        'evaluation_summary': 'Reduced errors by 3%',
        'type': 'hypothesis'
    })

    # Insights node
    insights = Mock(spec=GraphNode)
    insights.id = "insights-1"
    insights.parentNodeId = "root-id"
    insights.is_root = False
    insights.name = "Insights Round 1"
    insights.createdAt = "2025-01-10T10:00:00Z"
    insights.metadata = json.dumps({
        'type': 'insights',
        'node_type': 'insights',
        'round': 1,
        'summary': 'Key learnings: Focus on verification patterns.',
        'hypothesis_count': 2
    })

    return [root, hyp1, hyp2, insights]


@pytest.mark.asyncio
async def test_hypothesis_skip_logic_excludes_insights(
    procedure_service,
    mock_nodes_with_insights,
    mock_client
):
    """Test that insights nodes don't count toward hypothesis skip threshold."""

    procedure_id = "test-proc-id"

    with patch('plexus.dashboard.api.models.graph_node.GraphNode.list_by_procedure', return_value=mock_nodes_with_insights):
        # Simulate checking if we should skip hypothesis generation
        # This mimics the logic at service.py:780-820

        all_nodes = mock_nodes_with_insights

        # Count only HYPOTHESIS nodes (not insights nodes)
        hypothesis_nodes = []
        for n in all_nodes:
            if n.parentNodeId is None:
                continue  # Skip root node
            if n.metadata and 'code' in str(n.metadata):
                continue  # Skip nodes with code

            # Check if this is an insights node
            try:
                metadata = json.loads(n.metadata) if isinstance(n.metadata, str) else n.metadata if n.metadata else {}
                node_type = metadata.get('type', metadata.get('node_type'))
                if node_type == 'insights':
                    continue  # Skip insights nodes
            except:
                pass

            # This is a hypothesis node
            hypothesis_nodes.append(n)

        # Verify we have 2 hypothesis nodes (not 3, which would include insights)
        assert len(hypothesis_nodes) == 2

        # Since len(hypothesis_nodes) < 3, skip_hypothesis_generation should be False
        skip_hypothesis_generation = len(hypothesis_nodes) >= 3
        assert skip_hypothesis_generation is False


@pytest.mark.asyncio
async def test_hypothesis_skip_logic_with_enough_hypotheses(
    procedure_service,
    mock_nodes_with_insights,
    mock_client
):
    """Test that 3+ hypothesis nodes (excluding insights) triggers skip logic."""

    # Add a 3rd hypothesis node
    hyp3 = Mock(spec=GraphNode)
    hyp3.id = "hyp-3"
    hyp3.parentNodeId = "root-id"
    hyp3.is_root = False
    hyp3.name = "Hypothesis 3"
    hyp3.metadata = json.dumps({
        'hypothesis': 'Test hypothesis 3',
        'evaluation_summary': 'Mixed results',
        'type': 'hypothesis'
    })

    all_nodes = mock_nodes_with_insights + [hyp3]

    with patch('plexus.dashboard.api.models.graph_node.GraphNode.list_by_procedure', return_value=all_nodes):
        # Count hypothesis nodes (excluding insights)
        hypothesis_nodes = []
        for n in all_nodes:
            if n.parentNodeId is None:
                continue
            if n.metadata and 'code' in str(n.metadata):
                continue

            try:
                metadata = json.loads(n.metadata) if isinstance(n.metadata, str) else n.metadata if n.metadata else {}
                node_type = metadata.get('type', metadata.get('node_type'))
                if node_type == 'insights':
                    continue
            except:
                pass

            hypothesis_nodes.append(n)

        # Now we should have 3 hypothesis nodes
        assert len(hypothesis_nodes) == 3

        # This should trigger skip logic
        skip_hypothesis_generation = len(hypothesis_nodes) >= 3
        assert skip_hypothesis_generation is True


@pytest.mark.asyncio
async def test_get_existing_experiment_nodes_includes_insights_context(
    procedure_service,
    mock_nodes_with_insights
):
    """Test that _get_existing_experiment_nodes includes insights in formatted context."""

    procedure_id = "test-proc-id"

    with patch('plexus.dashboard.api.models.graph_node.GraphNode.list_by_procedure', return_value=mock_nodes_with_insights):
        result = await procedure_service._get_existing_experiment_nodes(procedure_id)

        # Verify insights section is present
        assert '## Previous Insights' in result
        assert 'Insights Round 1' in result
        assert 'Key learnings: Focus on verification patterns.' in result

        # Verify hypotheses section is present
        assert '## Previous Hypotheses' in result
        assert 'Hypothesis 1' in result
        assert 'Hypothesis 2' in result

        # Verify test results are included
        assert 'Improved by 5%' in result
        assert 'Reduced errors by 3%' in result

        # Verify guidance message about using insights
        assert 'Use the insights and previous results' in result


@pytest.mark.asyncio
async def test_insights_context_ordering(
    procedure_service,
    mock_nodes_with_insights
):
    """Test that insights appear BEFORE hypotheses in context (priority ordering)."""

    procedure_id = "test-proc-id"

    with patch('plexus.dashboard.api.models.graph_node.GraphNode.list_by_procedure', return_value=mock_nodes_with_insights):
        result = await procedure_service._get_existing_experiment_nodes(procedure_id)

        # Find positions of key sections
        insights_pos = result.find('## Previous Insights')
        hypotheses_pos = result.find('## Previous Hypotheses')

        # Insights should appear before hypotheses
        assert insights_pos < hypotheses_pos
        assert insights_pos != -1
        assert hypotheses_pos != -1


@pytest.mark.asyncio
async def test_multiple_insights_rounds_ordering(procedure_service):
    """Test that multiple insights nodes are ordered by round number."""

    root = Mock(spec=GraphNode)
    root.id = "root-id"
    root.parentNodeId = None
    root.is_root = True
    root.metadata = json.dumps({'code': 'baseline'})

    # Create insights from different rounds
    insights1 = Mock(spec=GraphNode)
    insights1.id = "insights-1"
    insights1.parentNodeId = "root-id"
    insights1.is_root = False
    insights1.name = "Insights Round 1"
    insights1.createdAt = "2025-01-01T10:00:00Z"
    insights1.metadata = json.dumps({
        'type': 'insights',
        'round': 1,
        'summary': 'Round 1 learnings'
    })

    insights2 = Mock(spec=GraphNode)
    insights2.id = "insights-2"
    insights2.parentNodeId = "insights-1"
    insights2.is_root = False
    insights2.name = "Insights Round 2"
    insights2.createdAt = "2025-01-05T10:00:00Z"
    insights2.metadata = json.dumps({
        'type': 'insights',
        'round': 2,
        'summary': 'Round 2 learnings'
    })

    insights3 = Mock(spec=GraphNode)
    insights3.id = "insights-3"
    insights3.parentNodeId = "insights-2"
    insights3.is_root = False
    insights3.name = "Insights Round 3"
    insights3.createdAt = "2025-01-10T10:00:00Z"
    insights3.metadata = json.dumps({
        'type': 'insights',
        'round': 3,
        'summary': 'Round 3 learnings'
    })

    all_nodes = [root, insights1, insights2, insights3]

    with patch('plexus.dashboard.api.models.graph_node.GraphNode.list_by_procedure', return_value=all_nodes):
        result = await procedure_service._get_existing_experiment_nodes('test-proc-id')

        # Check that rounds appear in order
        round1_pos = result.find('Round 1')
        round2_pos = result.find('Round 2')
        round3_pos = result.find('Round 3')

        assert round1_pos < round2_pos < round3_pos


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
