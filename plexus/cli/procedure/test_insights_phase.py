"""
Tests for the Insights Phase of the Procedure workflow.

The insights phase analyzes tested hypotheses and creates an insights node
that summarizes learnings and guides the next round of hypothesis generation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
from plexus.cli.procedure.service import ProcedureService, ProcedureInfo
from plexus.dashboard.api.models.procedure import Procedure
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
def mock_procedure_info(mock_client):
    """Create a mock ProcedureInfo with basic structure."""
    procedure = Mock(spec=Procedure)
    procedure.id = "test-procedure-id"
    procedure.accountId = "test-account-id"
    procedure.scorecardId = "test-scorecard-id"
    procedure.scoreId = "test-score-id"
    procedure.rootNodeId = "test-root-node-id"

    root_node = Mock(spec=GraphNode)
    root_node.id = "test-root-node-id"
    root_node.metadata = json.dumps({
        'code': 'baseline_config',
        'evaluation_id': 'baseline-eval-id'
    })

    return ProcedureInfo(
        procedure=procedure,
        root_node=root_node,
        node_count=5,  # root + 3 hypotheses + 1 insights
        version_count=5,
        scorecard_name="Test Scorecard",
        score_name="Test Score"
    )


@pytest.fixture
def mock_hypothesis_nodes():
    """Create mock hypothesis nodes with test results."""
    nodes = []

    for i in range(3):
        node = Mock(spec=GraphNode)
        node.id = f"hypothesis-node-{i+1}"
        node.name = f"Hypothesis {i+1}"
        node.parentNodeId = "test-root-node-id"
        node.status = "COMPLETED"
        node.createdAt = f"2025-01-{i+1:02d}T10:00:00Z"
        node.is_root = False
        node.metadata = json.dumps({
            'hypothesis': f'Test hypothesis {i+1} description',
            'scoreVersionId': f'score-version-{i+1}',
            'evaluation_id': f'eval-{i+1}',
            'evaluation_summary': f'Hypothesis {i+1} test results: accuracy improved by {i*5}%',
            'type': 'hypothesis'
        })

        nodes.append(node)

    return nodes


@pytest.fixture
def mock_insights_node():
    """Create a mock insights node."""
    node = Mock(spec=GraphNode)
    node.id = "insights-node-1"
    node.name = "Insights Round 1"
    node.parentNodeId = "test-root-node-id"
    node.status = "COMPLETED"
    node.is_root = False
    node.createdAt = "2025-01-10T10:00:00Z"
    node.metadata = json.dumps({
        'type': 'insights',
        'node_type': 'insights',
        'round': 1,
        'summary': 'Previous insights summary',
        'hypothesis_count': 3
    })

    return node


@pytest.mark.asyncio
async def test_execute_insights_phase_with_hypothesis_nodes(
    procedure_service,
    mock_procedure_info,
    mock_hypothesis_nodes,
    mock_client
):
    """Test insights phase execution with hypothesis nodes."""

    # Mock GraphNode.list_by_procedure to return hypothesis nodes + root
    root_node = mock_procedure_info.root_node
    all_nodes = [root_node] + mock_hypothesis_nodes

    with patch('plexus.cli.procedure.service.GraphNode.list_by_procedure', return_value=all_nodes):
        # Mock GraphNode.create for insights node creation
        mock_insights_node = Mock(spec=GraphNode)
        mock_insights_node.id = "new-insights-node"

        with patch('plexus.cli.procedure.service.GraphNode.create', return_value=mock_insights_node):
            # Mock the LLM insights generation
            mock_insights_summary = "Test insights summary based on hypotheses"
            with patch.object(procedure_service, '_generate_insights_with_llm', return_value=mock_insights_summary):

                # Execute insights phase
                experiment_context = {
                    'procedure_id': 'test-procedure-id',
                    'scorecard_name': 'Test Scorecard',
                    'score_name': 'Test Score'
                }

                result = await procedure_service._execute_insights_phase(
                    procedure_id='test-procedure-id',
                    procedure_info=mock_procedure_info,
                    experiment_context=experiment_context
                )

                # Verify success
                assert result['success'] is True
                assert result['insights_node_id'] == "new-insights-node"
                assert result['insights_summary'] == mock_insights_summary
                assert result['hypothesis_count'] == 3


@pytest.mark.asyncio
async def test_execute_insights_phase_no_hypothesis_nodes(
    procedure_service,
    mock_procedure_info,
    mock_client
):
    """Test insights phase fails gracefully when no hypothesis nodes exist."""

    # Mock GraphNode.list_by_procedure to return only root node
    root_node = mock_procedure_info.root_node

    with patch('plexus.cli.procedure.service.GraphNode.list_by_procedure', return_value=[root_node]):
        # Execute insights phase
        experiment_context = {
            'procedure_id': 'test-procedure-id',
            'scorecard_name': 'Test Scorecard',
            'score_name': 'Test Score'
        }

        result = await procedure_service._execute_insights_phase(
            procedure_id='test-procedure-id',
            procedure_info=mock_procedure_info,
            experiment_context=experiment_context
        )

        # Verify failure
        assert result['success'] is False
        assert 'No hypothesis nodes' in result['error']
        assert result['insights_node_id'] is None


@pytest.mark.asyncio
async def test_execute_insights_phase_with_previous_insights(
    procedure_service,
    mock_procedure_info,
    mock_hypothesis_nodes,
    mock_insights_node,
    mock_client
):
    """Test insights phase creates node under previous insights node."""

    # Mock GraphNode.list_by_procedure to return hypotheses + previous insights + root
    root_node = mock_procedure_info.root_node
    all_nodes = [root_node] + mock_hypothesis_nodes + [mock_insights_node]

    with patch('plexus.cli.procedure.service.GraphNode.list_by_procedure', return_value=all_nodes):
        # Mock GraphNode.create for new insights node
        new_insights_node = Mock(spec=GraphNode)
        new_insights_node.id = "insights-node-2"

        with patch('plexus.cli.procedure.service.GraphNode.create', return_value=new_insights_node) as mock_create:
            # Mock the LLM insights generation
            mock_insights_summary = "Round 2 insights"
            with patch.object(procedure_service, '_generate_insights_with_llm', return_value=mock_insights_summary):

                # Execute insights phase
                experiment_context = {
                    'procedure_id': 'test-procedure-id',
                    'scorecard_name': 'Test Scorecard',
                    'score_name': 'Test Score'
                }

                result = await procedure_service._execute_insights_phase(
                    procedure_id='test-procedure-id',
                    procedure_info=mock_procedure_info,
                    experiment_context=experiment_context
                )

                # Verify node was created under previous insights node
                mock_create.assert_called_once()
                create_kwargs = mock_create.call_args.kwargs
                assert create_kwargs['parentNodeId'] == mock_insights_node.id
                assert create_kwargs['name'] == "Insights Round 2"
                assert create_kwargs['metadata']['round'] == 2


@pytest.mark.asyncio
async def test_build_insights_context(
    procedure_service,
    mock_hypothesis_nodes,
    mock_insights_node,
    mock_procedure_info
):
    """Test building comprehensive context for insights generation."""

    root_node = mock_procedure_info.root_node
    previous_insights = [mock_insights_node]

    experiment_context = {
        'procedure_id': 'test-procedure-id',
        'scorecard_name': 'Test Scorecard',
        'score_name': 'Test Score'
    }

    context = await procedure_service._build_insights_context(
        hypothesis_nodes=mock_hypothesis_nodes,
        previous_insights_nodes=previous_insights,
        root_node=root_node,
        experiment_context=experiment_context
    )

    # Verify context structure
    assert 'hypotheses' in context
    assert 'previous_insights' in context
    assert 'baseline_evaluation' in context
    assert 'scorecard_name' in context
    assert 'score_name' in context

    # Verify hypothesis data
    assert len(context['hypotheses']) == 3
    for i, hyp in enumerate(context['hypotheses']):
        assert hyp['node_id'] == f"hypothesis-node-{i+1}"
        assert hyp['hypothesis'] == f'Test hypothesis {i+1} description'
        assert hyp['evaluation_summary'].startswith('Hypothesis')

    # Verify previous insights data
    assert len(context['previous_insights']) == 1
    assert context['previous_insights'][0]['round'] == 1
    assert context['previous_insights'][0]['summary'] == 'Previous insights summary'


@pytest.mark.asyncio
async def test_generate_insights_with_llm(
    procedure_service,
    mock_client
):
    """Test LLM insights generation."""

    insights_context = {
        'hypotheses': [
            {
                'name': 'Hypothesis 1',
                'hypothesis': 'Test hypothesis 1',
                'evaluation_summary': 'Improved accuracy by 5%',
                'status': 'COMPLETED'
            },
            {
                'name': 'Hypothesis 2',
                'hypothesis': 'Test hypothesis 2',
                'evaluation_summary': 'Reduced accuracy by 2%',
                'status': 'COMPLETED'
            }
        ],
        'previous_insights': [],
        'scorecard_name': 'Test Scorecard',
        'score_name': 'Test Score'
    }

    experiment_context = {
        'scorecard_name': 'Test Scorecard',
        'score_name': 'Test Score'
    }

    # Mock OpenAI API - patch where it's imported (inside the method)
    with patch('langchain_openai.ChatOpenAI') as mock_llm_class:
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "Generated insights summary with learnings and recommendations"
        mock_llm.invoke = Mock(return_value=mock_response)
        mock_llm_class.return_value = mock_llm

        # Mock config loading
        with patch('plexus.config.loader.load_config'):
            with patch('os.getenv', return_value='test-api-key'):

                result = await procedure_service._generate_insights_with_llm(
                    insights_context=insights_context,
                    experiment_context=experiment_context
                )

                # Verify result
                assert result == "Generated insights summary with learnings and recommendations"

                # Verify LLM was called with appropriate prompts
                mock_llm.invoke.assert_called_once()
                call_args = mock_llm.invoke.call_args[0][0]
                assert len(call_args) == 2  # System + Human message
                assert 'expert at analyzing' in call_args[0].content
                assert 'Hypothesis 1' in call_args[1].content
                assert 'Hypothesis 2' in call_args[1].content


@pytest.mark.asyncio
async def test_get_existing_experiment_nodes_with_insights(
    procedure_service,
    mock_hypothesis_nodes,
    mock_insights_node
):
    """Test _get_existing_experiment_nodes includes insights context."""

    # Mock root node
    root_node = Mock(spec=GraphNode)
    root_node.id = "root-id"
    root_node.is_root = True
    root_node.parentNodeId = None  # Root nodes have no parent

    all_nodes = [root_node] + mock_hypothesis_nodes + [mock_insights_node]

    # Mock the Procedure.get_by_id call
    mock_procedure = Mock()
    mock_procedure.id = 'test-procedure-id'
    mock_procedure.scoreId = "test-score-id"
    mock_procedure.scorecardId = "test-scorecard-id"

    with patch('plexus.cli.procedure.service.GraphNode.list_by_procedure', return_value=all_nodes), \
         patch('plexus.dashboard.api.models.procedure.Procedure.get_by_id', return_value=mock_procedure):
        result = await procedure_service._get_existing_experiment_nodes('test-procedure-id')

        # Verify insights are included
        assert '## Previous Insights' in result
        assert 'Insights Round 1' in result
        assert 'Previous insights summary' in result

        # Verify hypotheses are included
        assert '## Previous Hypotheses' in result
        assert 'Hypothesis 1' in result
        assert 'Hypothesis 2' in result
        assert 'Hypothesis 3' in result

        # Verify guidance message
        assert 'Use the insights and previous results' in result


@pytest.mark.asyncio
async def test_get_existing_experiment_nodes_first_round(
    procedure_service
):
    """Test _get_existing_experiment_nodes with no prior nodes (first round)."""

    # Mock only root node
    root_node = Mock(spec=GraphNode)
    root_node.id = "root-id"
    root_node.is_root = True
    root_node.parentNodeId = None  # Root nodes have no parent

    # Mock the Procedure.get_by_id call
    mock_procedure = Mock()
    mock_procedure.id = 'test-procedure-id'
    mock_procedure.scoreId = "test-score-id"
    mock_procedure.scorecardId = "test-scorecard-id"

    with patch('plexus.cli.procedure.service.GraphNode.list_by_procedure', return_value=[root_node]), \
         patch('plexus.dashboard.api.models.procedure.Procedure.get_by_id', return_value=mock_procedure):
        result = await procedure_service._get_existing_experiment_nodes('test-procedure-id')

        # Verify first round message
        assert 'No existing hypothesis or insights nodes found' in result
        assert 'first round' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
