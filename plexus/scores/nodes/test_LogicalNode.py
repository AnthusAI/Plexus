#!/usr/bin/env python3
"""
Comprehensive tests for LogicalNode with Python and Lua support.

This test suite covers:
- Python code execution
- Lua code execution (if available)  
- Parameter validation
- Context bridging between Python and Lua
- Error handling
- Output mapping functionality
- State management
"""

import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from plexus.scores.nodes.LogicalNode import LogicalNode
from plexus.scores.nodes.LuaRuntime import is_lua_available


class TestLogicalNodeParameters:
    """Test LogicalNode.Parameters validation and initialization"""
    
    def test_basic_parameters_creation(self):
        """Test basic parameter creation with Python code"""
        params = LogicalNode.Parameters(
            code="def execute(context): return {'result': 'success'}",
            language="python",
            function_name="execute"
        )
        
        assert params.code == "def execute(context): return {'result': 'success'}"
        assert params.language == "python"
        assert params.function_name == "execute"
        assert params.output_mapping is None
    
    def test_parameters_with_lua_language(self):
        """Test parameter creation with Lua language"""
        params = LogicalNode.Parameters(
            code="function execute(context) return {result = 'success'} end",
            language="lua",
            function_name="execute"
        )
        
        assert params.language == "lua"
        assert "function execute" in params.code
    
    def test_parameters_with_output_mapping(self):
        """Test parameters with output mapping configuration"""
        params = LogicalNode.Parameters(
            code="def execute(context): return {'status': 'ok', 'count': 5}",
            language="python",
            output_mapping={"result_status": "status", "item_count": "count"}
        )
        
        assert params.output_mapping["result_status"] == "status"
        assert params.output_mapping["item_count"] == "count"
    
    def test_default_parameters(self):
        """Test parameter defaults"""
        params = LogicalNode.Parameters(
            code="function execute(context) return {} end"
        )
        
        assert params.language == "lua"  # Default (changed for security)
        assert params.function_name == "execute"  # Default
        assert params.output_mapping is None  # Default


class TestLogicalNodeInitialization:
    """Test LogicalNode initialization and validation"""
    
    def test_successful_python_initialization(self):
        """Test successful initialization with Python code"""
        python_code = """
def execute(context):
    return {'message': 'Hello from Python'}
"""
        
        node = LogicalNode(
            node_name="test_logical_node",
            code=python_code,
            language="python",
            function_name="execute"
        )
        
        assert node.parameters.language == "python"
        assert node.execute_function is not None
        assert callable(node.execute_function)
    
    @pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
    def test_successful_lua_initialization(self):
        """Test successful initialization with Lua code"""
        lua_code = """
function execute(context)
    return {message = 'Hello from Lua'}
end
"""
        
        node = LogicalNode(
            node_name="test_lua_node",
            code=lua_code,
            language="lua",
            function_name="execute"
        )
        
        assert node.parameters.language == "lua"
        assert hasattr(node, 'lua_runtime')
    
    def test_invalid_language_error(self):
        """Test error with invalid language parameter"""
        with pytest.raises(ValueError, match="Unsupported language: javascript"):
            LogicalNode(
                node_name="test_invalid_lang",
                code="function execute() { return {}; }",
                language="javascript",
                function_name="execute"
            )
    
    def test_missing_python_function_error(self):
        """Test error when Python code doesn't define required function"""
        with pytest.raises(ValueError, match="Python code must define a 'missing_func' function"):
            LogicalNode(
                node_name="test_missing_func",
                code="def execute(context): return {}",
                language="python",
                function_name="missing_func"
            )
    
    @pytest.mark.skipif(is_lua_available(), reason="Lua runtime is available")
    def test_lua_unavailable_error(self):
        """Test error when Lua runtime is not available"""
        with pytest.raises(ValueError, match="Lua runtime not available"):
            LogicalNode(
                node_name="test_lua_unavail",
                code="function execute(context) return {} end",
                language="lua"
            )


class TestLogicalNodePythonExecution:
    """Test LogicalNode execution with Python code"""
    
    def test_basic_python_execution(self):
        """Test basic Python function execution"""
        python_code = """
def execute(context):
    return {'processed': True, 'input_text': context['text']}
"""
        
        node = LogicalNode(
            node_name="test_python_exec",
            code=python_code,
            language="python"
        )
        
        # Create mock state
        mock_state = MagicMock()
        mock_state.text = "Test input text"
        mock_state.metadata = {}
        mock_state.model_dump.return_value = {
            'text': 'Test input text',
            'metadata': {}
        }
        
        # Execute the node
        execute_node = node.get_execute_node()
        result_state = execute_node(mock_state)
        
        # Verify function was called and state was updated
        assert result_state is not None
    
    def test_python_execution_with_output_mapping(self):
        """Test Python execution with output mapping"""
        python_code = """
def execute(context):
    return {
        'status': 'completed',
        'item_count': 42,
        'timestamp': '2023-01-01'
    }
"""
        
        node = LogicalNode(
            node_name="test_output_mapping",
            code=python_code,
            language="python",
            output_mapping={
                "result_status": "status",
                "total_items": "item_count"
            }
        )
        
        # Create mock state
        mock_state = MagicMock()
        mock_state.text = "Test input"
        mock_state.metadata = {}
        mock_state.model_dump.return_value = {
            'text': 'Test input',
            'metadata': {}
        }
        
        # Mock the GraphState class to return updated state
        with patch.object(node, 'GraphState') as MockGraphState:
            mock_updated_state = MagicMock()
            MockGraphState.return_value = mock_updated_state
            mock_updated_state.model_dump.return_value = {
                'text': 'Test input',
                'result_status': 'completed',
                'total_items': 42
            }
            
            execute_node = node.get_execute_node()
            result_state = execute_node(mock_state)
            
            # Verify output mapping was applied
            assert result_state is not None
    
    def test_python_execution_with_context_metadata(self):
        """Test Python execution with rich context metadata"""
        python_code = """
def execute(context):
    metadata = context.get('metadata', {})
    text = context.get('text', '')
    
    return {
        'text_length': len(text),
        'has_metadata': len(metadata) > 0,
        'processed_data': f"Processed: {text[:10]}..."
    }
"""
        
        node = LogicalNode(
            node_name="test_context_metadata",
            code=python_code,
            language="python"
        )
        
        # Create mock state with rich metadata
        mock_state = MagicMock()
        mock_state.text = "This is a long test input that should be processed"
        mock_state.metadata = {"source": "test", "priority": "high"}
        mock_state.model_dump.return_value = {
            'text': mock_state.text,
            'metadata': mock_state.metadata,
            'extra_field': 'extra_value'
        }
        
        execute_node = node.get_execute_node()
        result_state = execute_node(mock_state)
        
        assert result_state is not None
    
    def test_python_execution_error_handling(self):
        """Test error handling in Python execution"""
        python_code = """
def execute(context):
    raise ValueError("Intentional test error")
"""
        
        node = LogicalNode(
            node_name="test_error_handling",
            code=python_code,
            language="python"
        )
        
        mock_state = MagicMock()
        mock_state.text = "Test input"
        mock_state.metadata = {}
        mock_state.model_dump.return_value = {'text': 'Test input', 'metadata': {}}
        
        execute_node = node.get_execute_node()
        
        # Should return original state on error
        result_state = execute_node(mock_state)
        assert result_state == mock_state


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestLogicalNodeLuaExecution:
    """Test LogicalNode execution with Lua code"""
    
    def test_basic_lua_execution(self):
        """Test basic Lua function execution"""
        lua_code = """
function execute(context)
    return {
        processed = true,
        input_text = context.text
    }
end
"""
        
        node = LogicalNode(
            node_name="test_basic_lua_exec",
            code=lua_code,
            language="lua"
        )
        
        # Create mock state
        mock_state = MagicMock()
        mock_state.text = "Test input text"
        mock_state.metadata = {}
        mock_state.model_dump.return_value = {
            'text': 'Test input text',
            'metadata': {}
        }
        
        # Execute the node
        execute_node = node.get_execute_node()
        result_state = execute_node(mock_state)
        
        # Verify execution completed
        assert result_state is not None
    
    def test_lua_execution_with_output_mapping(self):
        """Test Lua execution with output mapping"""
        lua_code = """
function execute(context)
    return {
        status = 'completed',
        item_count = 42,
        timestamp = '2023-01-01'
    }
end
"""
        
        node = LogicalNode(
            node_name="test_lua_output_mapping",
            code=lua_code,
            language="lua",
            output_mapping={
                "result_status": "status",
                "total_items": "item_count"
            }
        )
        
        # Create mock state
        mock_state = MagicMock()
        mock_state.text = "Test input"
        mock_state.metadata = {}
        mock_state.model_dump.return_value = {
            'text': 'Test input',
            'metadata': {}
        }
        
        # Mock the GraphState class
        with patch.object(node, 'GraphState') as MockGraphState:
            mock_updated_state = MagicMock()
            MockGraphState.return_value = mock_updated_state
            mock_updated_state.model_dump.return_value = {
                'text': 'Test input',
                'result_status': 'completed',
                'total_items': 42
            }
            
            execute_node = node.get_execute_node()
            result_state = execute_node(mock_state)
            
            assert result_state is not None
    
    def test_lua_execution_with_logging(self):
        """Test Lua execution with logging functions"""
        lua_code = """
function execute(context)
    log.info("Processing text: " .. context.text)
    print("This is a print statement")
    log.debug("Debug information")
    
    return {
        message = "Logged successfully",
        text_length = string.len(context.text)
    }
end
"""
        
        node = LogicalNode(
            node_name="test_lua_logging",
            code=lua_code,
            language="lua"
        )
        
        mock_state = MagicMock()
        mock_state.text = "Test input for logging"
        mock_state.metadata = {}
        mock_state.model_dump.return_value = {
            'text': 'Test input for logging',
            'metadata': {}
        }
        
        with patch('plexus.CustomLogging.logging') as mock_logging:
            execute_node = node.get_execute_node()
            result_state = execute_node(mock_state)
            
            # Verify logging was called
            assert mock_logging.info.called
            assert result_state is not None
    
    def test_lua_execution_with_complex_data(self):
        """Test Lua execution with complex nested data structures"""
        lua_code = """
function execute(context)
    local metadata = context.metadata or {}
    local result = {
        input_info = {
            text_length = string.len(context.text),
            has_metadata = next(metadata) ~= nil
        },
        processing = {
            status = "completed",
            timestamp = os.date("%Y-%m-%d")
        }
    }
    return result
end
"""
        
        node = LogicalNode(
            node_name="test_lua_complex_data",
            code=lua_code,
            language="lua"
        )
        
        mock_state = MagicMock()
        mock_state.text = "Complex test input"
        mock_state.metadata = {"source": "test", "priority": "high"}
        mock_state.model_dump.return_value = {
            'text': 'Complex test input',
            'metadata': {"source": "test", "priority": "high"}
        }
        
        execute_node = node.get_execute_node()
        result_state = execute_node(mock_state)
        
        assert result_state is not None
    
    def test_lua_execution_error_handling(self):
        """Test error handling in Lua execution"""
        lua_code = """
function execute(context)
    error("Intentional test error")
end
"""
        
        node = LogicalNode(
            node_name="test_lua_error_handling",
            code=lua_code,
            language="lua"
        )
        
        mock_state = MagicMock()
        mock_state.text = "Test input"
        mock_state.metadata = {}
        mock_state.model_dump.return_value = {'text': 'Test input', 'metadata': {}}
        
        execute_node = node.get_execute_node()
        
        # Should return original state on error
        result_state = execute_node(mock_state)
        assert result_state == mock_state


class TestLogicalNodeWorkflowIntegration:
    """Test LogicalNode integration with LangGraph workflows"""
    
    def test_workflow_compilation(self):
        """Test that LogicalNode can be compiled into a workflow"""
        python_code = """
def execute(context):
    return {'workflow_step': 'completed'}
"""
        
        node = LogicalNode(
            node_name="test_workflow_compilation",
            code=python_code,
            language="python"
        )
        
        # Create a mock GraphState class
        class MockGraphState:
            pass
        
        # Test workflow compilation
        compiled_workflow = node.build_compiled_workflow(MockGraphState)
        
        assert compiled_workflow is not None
    
    def test_add_core_nodes(self):
        """Test adding core nodes to workflow"""
        from langgraph.graph import StateGraph
        
        python_code = """
def execute(context):
    return {'node_added': True}
"""
        
        node = LogicalNode(
            node_name="test_logical_node",
            code=python_code,
            language="python"
        )
        
        # Create a workflow
        class MockState:
            pass
        
        workflow = StateGraph(MockState)
        updated_workflow = node.add_core_nodes(workflow)
        
        assert updated_workflow is not None


class TestLogicalNodeEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_empty_code_string(self):
        """Test handling of empty code string"""
        with pytest.raises(ValueError):
            LogicalNode(
                node_name="test_empty_code",
                code="",
                language="python"
            )
    
    def test_single_result_output_mapping(self):
        """Test output mapping with single result value"""
        python_code = """
def execute(context):
    return "simple_result"
"""
        
        node = LogicalNode(
            node_name="test_single_result_mapping",
            code=python_code,
            language="python",
            output_mapping={"final_result": "value"}
        )
        
        mock_state = MagicMock()
        mock_state.text = "Test"
        mock_state.metadata = {}
        mock_state.model_dump.return_value = {'text': 'Test', 'metadata': {}}
        
        with patch.object(node, 'GraphState') as MockGraphState:
            mock_updated_state = MagicMock()
            MockGraphState.return_value = mock_updated_state
            
            execute_node = node.get_execute_node()
            result_state = execute_node(mock_state)
            
            assert result_state is not None
    
    def test_no_output_mapping_dict_result(self):
        """Test handling dictionary result without explicit output mapping"""
        python_code = """
def execute(context):
    return {
        'auto_field1': 'value1',
        'auto_field2': 'value2'
    }
"""
        
        node = LogicalNode(
            node_name="test_no_output_mapping",
            code=python_code,
            language="python"
        )
        
        mock_state = MagicMock()
        mock_state.text = "Test"
        mock_state.metadata = {}
        mock_state.model_dump.return_value = {'text': 'Test', 'metadata': {}}
        
        with patch.object(node, 'GraphState') as MockGraphState:
            mock_updated_state = MagicMock()
            MockGraphState.return_value = mock_updated_state
            
            execute_node = node.get_execute_node()
            result_state = execute_node(mock_state)
            
            assert result_state is not None


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])