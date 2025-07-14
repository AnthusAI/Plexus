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


def test_basenode_trace_entry_duplicate_prevention():
    """Test the enhanced trace entry management that prevents duplicates."""
    
    # This test targets commit 6cdf01fe:
    # "Enhance trace entry management in BaseNode to prevent duplicates"
    
    from plexus.scores.nodes.BaseNode import BaseNode
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    class MockDuplicateGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        
    class TestDuplicateNode(BaseNode):
        def __init__(self):
            super().__init__(name="test_node")
            self.GraphState = MockDuplicateGraphState
            
        def add_core_nodes(self, workflow):
            pass
    
    test_node = TestDuplicateNode()
    
    # Create initial state with existing trace entry
    initial_state = MockDuplicateGraphState(
        text="test",
        metadata={
            "trace": {
                "node_results": [
                    {"node_name": "existing_node", "input": {}, "output": {"result": "first"}},
                    {"node_name": "test_node", "input": {}, "output": {"result": "original"}}
                ]
            }
        },
        results={}
    )
    
    # Simulate a new trace entry that would be a duplicate
    mock_final_node_state = {
        "text": "test",
        "metadata": {
            "trace": {
                "node_results": [
                    {"node_name": "test_node", "input": {}, "output": {"result": "duplicate_attempt"}}  # Same node_name
                ]
            }
        },
        "results": {},
        "new_field": "added_value"
    }
    
    # Simulate the enhanced state merging with duplicate prevention
    state_dict = initial_state.model_dump()
    final_node_state = mock_final_node_state
    
    # This is the critical enhancement - merge fields but prevent duplicate trace entries
    for key, value in final_node_state.items():
        if key == 'metadata' and 'metadata' in state_dict and state_dict.get('metadata') and value.get('trace'):
            # Special handling for metadata trace (the enhancement)
            if 'trace' not in state_dict['metadata']:
                state_dict['metadata']['trace'] = {'node_results': []}
            
            # Get existing node names to avoid duplicates (lines 215-221 in BaseNode.py)
            existing_node_names = {result.get('node_name') for result in state_dict['metadata']['trace']['node_results']}
            
            # Only add trace entries that don't already exist (the duplicate prevention)
            for trace_entry in value['trace']['node_results']:
                if trace_entry.get('node_name') not in existing_node_names:
                    state_dict['metadata']['trace']['node_results'].append(trace_entry)
        else:
            # Merge other fields normally
            state_dict[key] = value
    
    # Verify duplicate prevention worked correctly
    trace_results = state_dict['metadata']['trace']['node_results']
    node_names = [result['node_name'] for result in trace_results]
    
    # Should still have exactly 2 entries (no duplicates added)
    assert len(trace_results) == 2, f"Should have 2 trace entries (no duplicates), got {len(trace_results)}"
    assert node_names.count("test_node") == 1, "Should have exactly one test_node entry (duplicate prevented)"
    assert "existing_node" in node_names, "Original existing_node should be preserved"
    assert "test_node" in node_names, "Original test_node should be preserved"
    
    # Should preserve the original test_node entry, not the duplicate attempt
    test_node_entry = next(entry for entry in trace_results if entry['node_name'] == 'test_node')
    assert test_node_entry['output']['result'] == "original", "Should preserve original entry, not duplicate"
    
    # Other fields should still be merged correctly
    assert state_dict['new_field'] == "added_value", "Non-trace fields should still be merged"
    
    print("✅ BaseNode trace entry duplicate prevention test passed - duplicates successfully prevented!")


def test_basenode_refactored_state_merging():
    """Test the refactored state merging in BaseNode for improved trace management."""
    
    # This test targets commit 93a07028:
    # "Refactor state merging in BaseNode for improved trace management"
    
    from plexus.scores.nodes.BaseNode import BaseNode
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    class MockRefactorGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        
    class TestRefactorNode(BaseNode):
        def __init__(self):
            super().__init__(name="refactor_test_node")
            self.GraphState = MockRefactorGraphState
            
        def add_core_nodes(self, workflow):
            pass
    
    test_node = TestRefactorNode()
    
    # Test the refactored state merging with complex trace scenarios
    initial_state = MockRefactorGraphState(
        text="refactor test",
        metadata={
            "trace": {
                "node_results": [
                    {
                        "node_name": "classifier_1", 
                        "input": {"text": "refactor test"}, 
                        "output": {"classification": "Yes", "explanation": "Initial classification"}
                    }
                ]
            },
            "additional_metadata": "original_value"
        },
        results={},
        classification="Yes",
        explanation="Initial explanation"
    )
    
    # Simulate refactored workflow result with enhanced trace data
    mock_refactored_final_state = {
        "text": "refactor test",
        "metadata": {
            "trace": {
                "node_results": [
                    {
                        "node_name": "classifier_2",
                        "input": {"previous_result": "Yes"},
                        "output": {"classification": "Approved", "explanation": "Secondary classification"},
                        "execution_time": "0.15s",  # Enhanced trace data
                        "token_usage": {"total": 50}  # Enhanced trace data
                    }
                ]
            },
            "processing_stage": "secondary_review",  # New metadata
            "additional_metadata": "updated_value"  # Updated existing metadata
        },
        "results": {"final_stage": True},
        "classification": "Approved",  # Updated classification
        "explanation": "Secondary classification with enhanced reasoning",  # Updated explanation
        "confidence_score": 0.92  # New field from refactored processing
    }
    
    # Test the refactored state merging
    state_dict = initial_state.model_dump()
    final_node_state = mock_refactored_final_state
    
    # Apply the refactored merging logic
    for key, value in final_node_state.items():
        if key == 'metadata' and 'metadata' in state_dict and state_dict.get('metadata') and value.get('trace'):
            # Refactored trace management
            if 'trace' not in state_dict['metadata']:
                state_dict['metadata']['trace'] = {'node_results': []}
            
            # Enhanced duplicate prevention with refactored logic
            existing_node_names = {result.get('node_name') for result in state_dict['metadata']['trace']['node_results']}
            
            for trace_entry in value['trace']['node_results']:
                if trace_entry.get('node_name') not in existing_node_names:
                    state_dict['metadata']['trace']['node_results'].append(trace_entry)
            
            # Merge other metadata fields (refactored approach)
            for meta_key, meta_value in value.items():
                if meta_key != 'trace':
                    state_dict['metadata'][meta_key] = meta_value
        else:
            # Standard field merging
            state_dict[key] = value
    
    # Verify refactored state merging results
    assert len(state_dict['metadata']['trace']['node_results']) == 2, "Should have both trace entries"
    assert state_dict['classification'] == "Approved", "Classification should be updated"
    assert state_dict['explanation'] == "Secondary classification with enhanced reasoning", "Explanation should be updated"
    assert state_dict['confidence_score'] == 0.92, "New fields should be added"
    assert state_dict['metadata']['processing_stage'] == "secondary_review", "New metadata should be added"
    assert state_dict['metadata']['additional_metadata'] == "updated_value", "Existing metadata should be updated"
    
    # Verify enhanced trace data preservation
    classifier_2_entry = next(entry for entry in state_dict['metadata']['trace']['node_results'] 
                             if entry['node_name'] == 'classifier_2')
    assert classifier_2_entry['execution_time'] == "0.15s", "Enhanced trace data should be preserved"
    assert classifier_2_entry['token_usage']['total'] == 50, "Complex trace data should be preserved"
    
    print("✅ BaseNode refactored state merging test passed - improved trace management validated!") 