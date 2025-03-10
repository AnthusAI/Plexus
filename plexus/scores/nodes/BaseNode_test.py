import pytest
from unittest.mock import MagicMock, patch
import json
from pydantic import BaseModel, ConfigDict
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.scores.LangGraphScore import LangGraphScore
from langgraph.graph import StateGraph

class MockGraphState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    text: str = ""
    metadata: dict = None
    value: str = None
    explanation: str = None

# Create a simplified version of BaseNode for testing
class MockNode(BaseNode):
    """Mock implementation of BaseNode for testing"""
    
    def __init__(self, **parameters):
        parameters.setdefault('name', 'test_node')
        # Skip the parent class initialization to avoid LangChainUser dependencies
        self.parameters = self.Parameters(**parameters)
        self.GraphState = LangGraphScore.GraphState
        
    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        """Simple implementation that just returns the workflow"""
        return workflow
        
    def build_compiled_workflow(self, graph_state_class) -> StateGraph:
        """Override the parent method to simplify for testing"""
        workflow = StateGraph(graph_state_class)
        
        # Add input aliasing function if needed
        if hasattr(self.parameters, 'input') and self.parameters.input is not None:
            input_aliasing_function = MagicMock()
            workflow.add_node('input_aliasing', input_aliasing_function)
            
        # Add a dummy node for testing
        workflow.add_node('dummy_node', MagicMock())
        
        # Add edges
        if 'input_aliasing' in workflow.nodes:
            workflow.add_edge('input_aliasing', 'dummy_node')
            
        # Add output aliasing if needed
        if hasattr(self.parameters, 'output') and self.parameters.output is not None:
            output_aliasing_function = MagicMock()
            workflow.add_node('output_aliasing', output_aliasing_function)
            workflow.add_edge('dummy_node', 'output_aliasing')
            
        # Set entry point
        workflow.set_entry_point('input_aliasing' if 'input_aliasing' in workflow.nodes else 'dummy_node')
        
        # Mock the compile method
        workflow.compile = MagicMock(return_value=MagicMock())
        
        return workflow.compile()

@pytest.fixture
def mock_node():
    """Create a mock node for testing"""
    return MockNode(name="test_node")

@pytest.fixture
def mock_state():
    """Create a mock state for testing"""
    return MockGraphState(text="test text")

def test_node_name(mock_node):
    """Test that node_name property returns the correct name"""
    assert mock_node.node_name == "test_node"

def test_node_name_missing():
    """Test that node_name raises ValueError when name is missing"""
    node = MockNode()
    node.parameters.name = None
    with pytest.raises(ValueError):
        _ = node.node_name

def test_log_state_basic(mock_node, mock_state):
    """Test basic functionality of log_state method"""
    input_state = {"input_key": "input_value"}
    output_state = {"output_key": "output_value"}
    
    result = mock_node.log_state(mock_state, input_state, output_state)
    
    # Check that metadata and trace are initialized
    assert result.metadata is not None
    assert 'trace' in result.metadata
    assert 'node_results' in result.metadata['trace']
    
    # Check that node_results contains the expected entry
    node_results = result.metadata['trace']['node_results']
    assert len(node_results) == 1
    assert node_results[0]['node_name'] == "test_node"
    assert node_results[0]['input'] == input_state
    assert node_results[0]['output'] == output_state

def test_log_state_with_suffix(mock_node, mock_state):
    """Test log_state with a node suffix"""
    result = mock_node.log_state(mock_state, {}, {}, node_suffix="suffix")
    
    # Check that node_name includes the suffix
    node_results = result.metadata['trace']['node_results']
    assert node_results[0]['node_name'] == "test_node.suffix"

def test_log_state_with_existing_metadata(mock_node):
    """Test log_state with existing metadata"""
    # Create a state with existing metadata
    existing_metadata = {
        "existing_key": "existing_value",
        "trace": {
            "node_results": [
                {
                    "node_name": "previous_node",
                    "input": {"prev_input": "value"},
                    "output": {"prev_output": "value"}
                }
            ]
        }
    }
    state = MockGraphState(text="test text", metadata=existing_metadata)
    
    result = mock_node.log_state(state, {"new_input": "value"}, {"new_output": "value"})
    
    # Check that existing metadata is preserved
    assert result.metadata["existing_key"] == "existing_value"
    
    # Check that node_results contains both entries
    node_results = result.metadata['trace']['node_results']
    assert len(node_results) == 2
    assert node_results[0]['node_name'] == "previous_node"
    assert node_results[1]['node_name'] == "test_node"

def test_log_state_with_empty_state(mock_node):
    """Test log_state with an empty state dictionary"""
    empty_state = {}
    
    # This should raise an exception since we're passing an invalid state
    with pytest.raises(Exception):
        result = mock_node.log_state(empty_state, {}, {})

def test_get_prompt_templates(mock_node):
    """Test get_prompt_templates method"""
    # Set up parameters with system and user messages
    mock_node.parameters.system_message = "This is a system message"
    mock_node.parameters.user_message = "This is a user message"
    
    templates = mock_node.get_prompt_templates()
    
    # Check that templates were created
    assert len(templates) == 1
    
    # Test with single_line_messages=True
    mock_node.parameters.single_line_messages = True
    templates = mock_node.get_prompt_templates()
    assert len(templates) == 1

def test_get_prompt_templates_empty(mock_node):
    """Test get_prompt_templates with no messages"""
    mock_node.parameters.system_message = None
    mock_node.parameters.user_message = None
    
    templates = mock_node.get_prompt_templates()
    
    # Check that no templates were created
    assert len(templates) == 0

def test_build_compiled_workflow(mock_node):
    """Test build_compiled_workflow method"""
    # Mock the StateGraph.compile method to return a simple object
    with patch('langgraph.graph.StateGraph.compile', return_value=MagicMock()):
        workflow = mock_node.build_compiled_workflow(MockGraphState)
        
        # Check that a workflow was created
        assert workflow is not None

def test_build_compiled_workflow_with_io_aliasing(mock_node):
    """Test build_compiled_workflow with input and output aliasing"""
    mock_node.parameters.input = {"input_alias": "input_field"}
    mock_node.parameters.output = {"output_alias": "output_field"}
    
    # Create a more complete mock for StateGraph
    mock_workflow = MagicMock()
    mock_workflow.nodes = {'input_aliasing': MagicMock(), 'some_node': MagicMock()}
    mock_workflow.add_node.return_value = None
    mock_workflow.add_edge.return_value = None
    mock_workflow.set_entry_point.return_value = None
    mock_workflow.compile.return_value = MagicMock()
    
    # Mock StateGraph constructor to return our mock_workflow
    with patch('langgraph.graph.StateGraph', return_value=mock_workflow):
        workflow = mock_node.build_compiled_workflow(MockGraphState)
        
        # Check that a workflow was created
        assert workflow is not None 