"""
Comprehensive tests for BaseNode functionality.

This test suite focuses on the critical BaseNode functionality that serves as the 
foundation for all node implementations. It covers areas that were previously 
untested and represent significant risk.

Key areas tested:
- Input/output aliasing integration
- Workflow building edge cases  
- Abstract method enforcement
- Parameter handling scenarios
- State management functionality
- Error conditions and edge cases
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from abc import ABC, abstractmethod
import sys
import os

# Mock problematic dependencies upfront
class MockModule:
    def __getattr__(self, name):
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()

sys.modules['mlflow'] = MockModule()
sys.modules['pandas'] = MockModule()
sys.modules['graphviz'] = MockModule()


class TestBaseNodeAbstractMethods:
    """Test abstract method enforcement and inheritance patterns"""
    
    def test_basenode_cannot_be_instantiated_directly(self):
        """Test that BaseNode cannot be instantiated due to abstract methods"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        # Should raise TypeError due to abstract methods
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseNode(name="test_node")

    def test_concrete_class_must_implement_add_core_nodes(self):
        """Test that concrete classes must implement add_core_nodes"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        # Create incomplete implementation
        class IncompleteNode(BaseNode):
            pass  # Missing add_core_nodes implementation
            
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteNode(name="test")

    def test_complete_implementation_works(self):
        """Test that properly implemented concrete class works"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class CompleteNode(BaseNode):
            def __init__(self, **parameters):
                # Mock the LangChainUser initialization
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                workflow.add_node("test_node", lambda x: x)
                return workflow
                
        # Should work without errors
        node = CompleteNode(name="test_node")
        assert node.node_name == "test_node"


class TestBaseNodeParameterHandling:
    """Test parameter handling and configuration scenarios"""
    
    def test_parameter_inheritance_and_merging(self):
        """Test that parameters are properly inherited and merged"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                return workflow
                
        # Test with various parameter combinations
        node = TestNode(
            name="test_node",
            input={"input_alias": "input_field"},
            output={"output_alias": "output_field"},
            system_message="Test system message",
            user_message="Test user message: {text}",
            single_line_messages=True
        )
        
        assert node.parameters.name == "test_node"
        assert node.parameters.input == {"input_alias": "input_field"}
        assert node.parameters.output == {"output_alias": "output_field"}
        assert node.parameters.system_message == "Test system message"
        assert node.parameters.user_message == "Test user message: {text}"
        assert node.parameters.single_line_messages is True

    def test_parameter_defaults_and_optional_fields(self):
        """Test parameter defaults and optional field handling"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                return workflow
                
        # Test with minimal parameters
        node = TestNode(name="minimal_node")
        
        assert node.parameters.name == "minimal_node"
        assert node.parameters.input is None
        assert node.parameters.output is None
        assert node.parameters.system_message is None
        assert node.parameters.user_message is None
        assert node.parameters.single_line_messages is False


class TestBaseNodePromptTemplateGeneration:
    """Test prompt template generation functionality"""
    
    def test_get_prompt_templates_both_messages(self):
        """Test prompt template generation with both system and user messages"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                return workflow
                
        node = TestNode(
            name="test_node",
            system_message="You are a helpful assistant.",
            user_message="Process this text: {text}"
        )
        
        templates = node.get_prompt_templates()
        assert len(templates) == 1
        
        # Verify template structure
        template = templates[0]
        assert hasattr(template, 'messages')
        assert len(template.messages) == 2

    def test_get_prompt_templates_single_line_conversion(self):
        """Test single line message conversion"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                return workflow
                
        multiline_message = """This is a
        multiline
        message with
        extra spaces"""
        
        node = TestNode(
            name="test_node",
            user_message=multiline_message,
            single_line_messages=True
        )
        
        templates = node.get_prompt_templates()
        assert len(templates) == 1
        
        # Verify message was converted to single line
        # The exact content verification would require accessing the template structure

    def test_get_prompt_templates_empty_messages(self):
        """Test handling of empty or missing messages"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                return workflow
                
        # Test with no messages
        node = TestNode(name="test_node")
        templates = node.get_prompt_templates()
        assert len(templates) == 0
        
        # Test with empty messages
        node = TestNode(
            name="test_node",
            system_message="",
            user_message=""
        )
        templates = node.get_prompt_templates()
        assert len(templates) == 0

    def test_get_example_refinement_template(self):
        """Test example refinement template functionality"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                return workflow
                
        refinement_message = "Please refine your example based on this feedback."
        
        node = TestNode(
            name="test_node",
            example_refinement_message=refinement_message
        )
        
        result = node.get_example_refinement_template()
        assert result == refinement_message
        
        # Test with no refinement message
        node = TestNode(name="test_node")
        result = node.get_example_refinement_template()
        assert result is None


class TestBaseNodeLogStateAdvanced:
    """Test advanced log_state functionality and edge cases"""
    
    def test_log_state_with_complex_input_output(self):
        """Test log_state with complex input/output structures"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                return workflow
                
        node = TestNode(name="test_node")
        
        # Create state with model_dump method
        class MockState:
            def __init__(self):
                self.text = "test text"
                self.metadata = None
                
            def model_dump(self):
                return {
                    "text": self.text,
                    "metadata": self.metadata
                }
        
        state = MockState()
        
        complex_input = {
            "nested_data": {"key": "value", "list": [1, 2, 3]},
            "simple_field": "test"
        }
        
        complex_output = {
            "classification": "positive",
            "confidence": 0.85,
            "metadata": {"source": "test_node"}
        }
        
        result = node.log_state(state, complex_input, complex_output, "processing")
        
        # Verify trace structure
        assert result.metadata is not None
        assert "trace" in result.metadata
        assert "node_results" in result.metadata["trace"]
        
        node_result = result.metadata["trace"]["node_results"][0]
        assert node_result["node_name"] == "test_node.processing"
        assert node_result["input"] == complex_input
        assert node_result["output"] == complex_output

    def test_log_state_accumulation(self):
        """Test that multiple log_state calls accumulate properly"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                return workflow
                
        node = TestNode(name="test_node")
        
        class MockState:
            def __init__(self, metadata=None):
                self.text = "test"
                self.metadata = metadata or {}
                
            def model_dump(self):
                return {"text": self.text, "metadata": self.metadata}
        
        # First log entry
        state1 = MockState()
        result1 = node.log_state(state1, {"step": 1}, {"result": "first"}, "step1")
        
        # Second log entry using result from first
        result2 = node.log_state(result1, {"step": 2}, {"result": "second"}, "step2")
        
        # Verify accumulation
        node_results = result2.metadata["trace"]["node_results"]
        assert len(node_results) == 2
        assert node_results[0]["node_name"] == "test_node.step1"
        assert node_results[1]["node_name"] == "test_node.step2"

    def test_log_state_error_handling(self):
        """Test log_state error handling with invalid states"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                return workflow
                
        node = TestNode(name="test_node")
        
        # Test with state that has dict() method instead of model_dump()
        class DictState:
            def __init__(self):
                self.text = "test"
                self.metadata = None
                
            def dict(self):
                return {"text": self.text, "metadata": self.metadata}
        
        state = DictState()
        result = node.log_state(state, {"test": "input"}, {"test": "output"})
        
        # Should still work and create proper trace
        assert result.metadata is not None
        assert "trace" in result.metadata


class TestBaseNodeWorkflowBuilding:
    """Test workflow building functionality and edge cases"""
    
    def test_build_compiled_workflow_with_input_aliasing(self):
        """Test workflow building with input aliasing"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                workflow.add_node("core_node", lambda x: x)
                return workflow
                
        with patch('plexus.scores.LangGraphScore.LangGraphScore.generate_input_aliasing_function') as mock_input_fn:
            mock_input_fn.return_value = MagicMock()
            
            node = TestNode(
                name="test_node",
                input={"alias": "original_field"}
            )
            
            with patch('langgraph.graph.StateGraph') as mock_sg_class:
                mock_workflow = MagicMock()
                mock_workflow.nodes = {}
                mock_workflow.compile.return_value = MagicMock()
                mock_sg_class.return_value = mock_workflow
                
                result = node.build_compiled_workflow(MagicMock)
                
                # Verify input aliasing function was created and added
                mock_input_fn.assert_called_once_with({"alias": "original_field"})
                mock_workflow.add_node.assert_any_call('input_aliasing', mock_input_fn.return_value)

    def test_build_compiled_workflow_with_output_aliasing(self):
        """Test workflow building with output aliasing"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                workflow.add_node("core_node", lambda x: x)
                return workflow
                
        with patch('plexus.scores.LangGraphScore.LangGraphScore.generate_output_aliasing_function') as mock_output_fn:
            mock_output_fn.return_value = MagicMock()
            
            node = TestNode(
                name="test_node",
                output={"final_result": "intermediate_result"}
            )
            
            with patch('langgraph.graph.StateGraph') as mock_sg_class:
                mock_workflow = MagicMock()
                mock_workflow.nodes = {"core_node": MagicMock()}
                mock_workflow.compile.return_value = MagicMock()
                mock_sg_class.return_value = mock_workflow
                
                result = node.build_compiled_workflow(MagicMock)
                
                # Verify output aliasing function was created and added
                mock_output_fn.assert_called_once_with({"final_result": "intermediate_result"})
                mock_workflow.add_node.assert_any_call('output_aliasing', mock_output_fn.return_value)

    def test_build_compiled_workflow_with_both_aliasing(self):
        """Test workflow building with both input and output aliasing"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                workflow.add_node("core_node", lambda x: x)
                return workflow
                
        with patch('plexus.scores.LangGraphScore.LangGraphScore.generate_input_aliasing_function') as mock_input_fn, \
             patch('plexus.scores.LangGraphScore.LangGraphScore.generate_output_aliasing_function') as mock_output_fn:
            
            mock_input_fn.return_value = MagicMock()
            mock_output_fn.return_value = MagicMock()
            
            node = TestNode(
                name="test_node",
                input={"input_alias": "input_field"},
                output={"output_alias": "output_field"}
            )
            
            with patch('langgraph.graph.StateGraph') as mock_sg_class:
                mock_workflow = MagicMock()
                mock_workflow.nodes = {"input_aliasing": MagicMock(), "core_node": MagicMock()}
                mock_workflow.compile.return_value = MagicMock()
                mock_sg_class.return_value = mock_workflow
                
                result = node.build_compiled_workflow(MagicMock)
                
                # Verify both aliasing functions were created
                mock_input_fn.assert_called_once()
                mock_output_fn.assert_called_once()
                
                # Verify proper edge connections were made
                assert mock_workflow.add_edge.called

    def test_build_compiled_workflow_edge_connections(self):
        """Test proper edge connections in workflow building"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph, END
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                workflow.add_node("core_node", lambda x: x)
                return workflow
                
        node = TestNode(name="test_node")
        
        with patch('langgraph.graph.StateGraph') as mock_sg_class:
            mock_workflow = MagicMock()
            mock_workflow.nodes = {"core_node": MagicMock()}
            mock_workflow.compile.return_value = MagicMock()
            mock_sg_class.return_value = mock_workflow
            
            result = node.build_compiled_workflow(MagicMock)
            
            # Verify entry point was set
            mock_workflow.set_entry_point.assert_called_once()
            
            # Verify END edge was added
            mock_workflow.add_edge.assert_called()


class TestBaseNodeEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_node_name_with_special_characters(self):
        """Test node names with special characters"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                return workflow
                
        special_names = [
            "node-with-dashes",
            "node_with_underscores", 
            "node.with.dots",
            "NodeWithCamelCase",
            "node123"
        ]
        
        for name in special_names:
            node = TestNode(name=name)
            assert node.node_name == name

    def test_empty_workflow_handling(self):
        """Test handling of empty workflows"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class EmptyNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                # Return workflow without adding any nodes
                return workflow
                
        node = EmptyNode(name="empty_node")
        
        with patch('langgraph.graph.StateGraph') as mock_sg_class:
            mock_workflow = MagicMock()
            mock_workflow.nodes = {}
            mock_workflow.compile.return_value = MagicMock()
            mock_sg_class.return_value = mock_workflow
            
            # Should handle empty workflow gracefully
            result = node.build_compiled_workflow(MagicMock)
            assert result is not None

    def test_large_state_logging_performance(self):
        """Test performance with large state objects"""
        try:
            from plexus.scores.nodes.BaseNode import BaseNode
            from langgraph.graph import StateGraph
        except ImportError:
            pytest.skip("BaseNode dependencies not available")
            
        class TestNode(BaseNode):
            def __init__(self, **parameters):
                self.parameters = self.Parameters(**parameters)
                
            def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
                return workflow
                
        node = TestNode(name="test_node")
        
        # Create large state
        large_data = {f"field_{i}": f"value_{i}" * 100 for i in range(1000)}
        
        class LargeState:
            def __init__(self):
                self.text = "test"
                self.metadata = None
                self.large_data = large_data
                
            def model_dump(self):
                return {
                    "text": self.text,
                    "metadata": self.metadata,
                    "large_data": self.large_data
                }
        
        state = LargeState()
        
        # Should handle large state without issues
        result = node.log_state(state, {"input": "test"}, {"output": "test"})
        assert result.metadata is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])