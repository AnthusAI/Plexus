#!/usr/bin/env python3
"""
Comprehensive tests for LuaRuntime utility.

This test suite covers:
- Python-Lua data conversion
- Lua code execution
- Context bridging
- Error handling
- Logging integration
- Score.Result creation from Lua
"""

import pytest
from unittest.mock import MagicMock, patch
import json

from plexus.scores.nodes.LuaRuntime import (
    LuaRuntime, get_lua_runtime, is_lua_available, 
    LuaCompatibleError
)


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestLuaRuntimeInitialization:
    """Test LuaRuntime initialization and setup"""
    
    def test_lua_runtime_creation(self):
        """Test creating a new LuaRuntime instance"""
        runtime = LuaRuntime()
        assert runtime is not None
        assert runtime.lua is not None
    
    def test_get_lua_runtime_singleton(self):
        """Test that get_lua_runtime returns singleton instance"""
        runtime1 = get_lua_runtime()
        runtime2 = get_lua_runtime()
        assert runtime1 is runtime2
    
    def test_lua_environment_setup(self):
        """Test that Lua environment is properly set up with utilities"""
        runtime = LuaRuntime()
        
        # Test that json utilities are available
        result = runtime.lua.eval('json')
        assert result is not None
        
        # Test that log utilities are available
        result = runtime.lua.eval('log')
        assert result is not None
        
        # Test that print function is available
        result = runtime.lua.eval('print')
        assert result is not None


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestPythonToLuaConversion:
    """Test Python to Lua data conversion"""
    
    def test_basic_types_conversion(self):
        """Test conversion of basic Python types to Lua"""
        runtime = LuaRuntime()
        
        # Test string
        lua_str = runtime.python_to_lua("hello")
        assert lua_str == "hello"
        
        # Test int
        lua_int = runtime.python_to_lua(42)
        assert lua_int == 42
        
        # Test float
        lua_float = runtime.python_to_lua(3.14)
        assert lua_float == 3.14
        
        # Test boolean
        lua_bool = runtime.python_to_lua(True)
        assert lua_bool is True
        
        # Test None
        lua_none = runtime.python_to_lua(None)
        assert lua_none is None
    
    def test_dictionary_conversion(self):
        """Test conversion of Python dictionaries to Lua tables"""
        runtime = LuaRuntime()
        
        python_dict = {
            "name": "test",
            "count": 5,
            "active": True,
            "nested": {"key": "value"}
        }
        
        lua_table = runtime.python_to_lua(python_dict)
        
        # Test that it's a Lua table and can be accessed
        assert lua_table["name"] == "test"
        assert lua_table["count"] == 5
        assert lua_table["active"] is True
        assert lua_table["nested"]["key"] == "value"
    
    def test_list_conversion(self):
        """Test conversion of Python lists to Lua arrays"""
        runtime = LuaRuntime()
        
        python_list = ["apple", "banana", "cherry", 42, True]
        lua_array = runtime.python_to_lua(python_list)
        
        # Lua arrays are 1-indexed
        assert lua_array[1] == "apple"
        assert lua_array[2] == "banana"
        assert lua_array[3] == "cherry"
        assert lua_array[4] == 42
        assert lua_array[5] is True
    
    def test_nested_structure_conversion(self):
        """Test conversion of complex nested Python structures"""
        runtime = LuaRuntime()
        
        complex_data = {
            "users": [
                {"name": "Alice", "age": 30, "active": True},
                {"name": "Bob", "age": 25, "active": False}
            ],
            "metadata": {
                "total": 2,
                "tags": ["user", "profile", "data"]
            }
        }
        
        lua_data = runtime.python_to_lua(complex_data)
        
        # Test nested access
        assert lua_data["users"][1]["name"] == "Alice"
        assert lua_data["users"][2]["age"] == 25
        assert lua_data["metadata"]["total"] == 2
        assert lua_data["metadata"]["tags"][1] == "user"


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestLuaToPythonConversion:
    """Test Lua to Python data conversion"""
    
    def test_basic_types_conversion(self):
        """Test conversion of basic Lua types to Python"""
        runtime = LuaRuntime()
        
        # Create Lua values and convert back
        lua_str = runtime.lua.eval('"hello"')
        python_str = runtime.lua_to_python(lua_str)
        assert python_str == "hello"
        
        lua_num = runtime.lua.eval('42')
        python_num = runtime.lua_to_python(lua_num)
        assert python_num == 42
        
        lua_bool = runtime.lua.eval('true')
        python_bool = runtime.lua_to_python(lua_bool)
        assert python_bool is True
    
    def test_lua_table_to_dict_conversion(self):
        """Test conversion of Lua tables to Python dictionaries"""
        runtime = LuaRuntime()
        
        # Create a Lua table
        runtime.lua.execute('''
            test_table = {
                name = "test",
                count = 5,
                active = true,
                nested = {key = "value"}
            }
        ''')
        
        lua_table = runtime.lua.globals().test_table
        python_dict = runtime.lua_to_python(lua_table)
        
        assert isinstance(python_dict, dict)
        assert python_dict["name"] == "test"
        assert python_dict["count"] == 5
        assert python_dict["active"] is True
        assert python_dict["nested"]["key"] == "value"
    
    def test_lua_array_to_list_conversion(self):
        """Test conversion of Lua arrays to Python lists"""
        runtime = LuaRuntime()
        
        # Create a Lua array (1-indexed)
        runtime.lua.execute('''
            test_array = {"apple", "banana", "cherry", 42, true}
        ''')
        
        lua_array = runtime.lua.globals().test_array
        python_list = runtime.lua_to_python(lua_array)
        
        assert isinstance(python_list, list)
        assert python_list == ["apple", "banana", "cherry", 42, True]
    
    def test_mixed_lua_table_conversion(self):
        """Test conversion of Lua tables with both array and hash parts"""
        runtime = LuaRuntime()
        
        # Create a mixed Lua table
        runtime.lua.execute('''
            mixed_table = {
                "first_item",
                "second_item", 
                name = "test",
                count = 3
            }
        ''')
        
        lua_table = runtime.lua.globals().mixed_table
        python_data = runtime.lua_to_python(lua_table)
        
        # Should be converted to dict since it has non-integer keys
        assert isinstance(python_data, dict)
        assert python_data["name"] == "test"
        assert python_data["count"] == 3


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestLuaFunctionExecution:
    """Test Lua function execution"""
    
    def test_basic_function_execution(self):
        """Test executing a basic Lua function"""
        runtime = LuaRuntime()
        
        lua_code = '''
        function test_func(context)
            return {
                message = "Hello from Lua",
                input_text = context.text
            }
        end
        '''
        
        context = {"text": "test input", "metadata": {}}
        result = runtime.execute_function(lua_code, "test_func", context)
        
        assert isinstance(result, dict)
        assert result["message"] == "Hello from Lua"
        assert result["input_text"] == "test input"
    
    def test_function_with_complex_context(self):
        """Test executing Lua function with complex context"""
        runtime = LuaRuntime()
        
        lua_code = '''
        function process_data(context)
            local text = context.text
            local metadata = context.metadata
            
            local result = {
                text_length = string.len(text),
                metadata_count = 0
            }
            
            for k, v in pairs(metadata) do
                result.metadata_count = result.metadata_count + 1
            end
            
            return result
        end
        '''
        
        context = {
            "text": "This is a test input with some length",
            "metadata": {"source": "test", "priority": "high", "timestamp": "2023-01-01"}
        }
        
        result = runtime.execute_function(lua_code, "process_data", context)
        
        assert result["text_length"] == len(context["text"])
        assert result["metadata_count"] == 3
    
    def test_function_execution_error(self):
        """Test handling of Lua function execution errors"""
        runtime = LuaRuntime()
        
        lua_code = '''
        function error_func(context)
            error("Intentional test error")
        end
        '''
        
        context = {"text": "test"}
        
        with pytest.raises(Exception):
            runtime.execute_function(lua_code, "error_func", context)
    
    def test_missing_function_error(self):
        """Test error when requested function doesn't exist"""
        runtime = LuaRuntime()
        
        lua_code = '''
        function existing_func(context)
            return {result = "ok"}
        end
        '''
        
        context = {"text": "test"}
        
        with pytest.raises(ValueError, match="Lua code must define a 'missing_func' function"):
            runtime.execute_function(lua_code, "missing_func", context)


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestLuaScoreFunctionExecution:
    """Test Lua score function execution with Score.Result creation"""
    
    def test_basic_score_function(self):
        """Test executing a basic Lua score function"""
        runtime = LuaRuntime()
        
        lua_code = '''
        function score(parameters, input)
            local text = string.lower(input.text)
            if string.find(text, "positive") then
                return {
                    value = "Yes",
                    explanation = "Found positive keyword"
                }
            end
            return nil
        end
        '''
        
        # Mock parameters and input
        mock_parameters = MagicMock()
        mock_parameters.model_dump.return_value = {"name": "test_score"}
        
        mock_input = MagicMock()
        mock_input.text = "This is a positive example"
        mock_input.metadata = {}
        mock_input.results = None
        
        result = runtime.execute_score_function(lua_code, mock_parameters, mock_input)
        
        # Should return a Score.Result object
        from plexus.scores.Score import Score
        assert isinstance(result, Score.Result)
        assert result.value == "Yes"
        assert result.explanation == "Found positive keyword"
    
    def test_score_function_with_metadata(self):
        """Test Lua score function that returns metadata"""
        runtime = LuaRuntime()
        
        lua_code = '''
        function score(parameters, input)
            return {
                value = "Analyzed",
                explanation = "Analysis complete",
                confidence = 0.85,
                metadata = {
                    text_length = string.len(input.text),
                    processing_time = 1.2
                }
            }
        end
        '''
        
        mock_parameters = MagicMock()
        mock_parameters.model_dump.return_value = {"name": "test_score"}
        
        mock_input = MagicMock()
        mock_input.text = "Sample input text"
        mock_input.metadata = {}
        mock_input.results = None
        
        result = runtime.execute_score_function(lua_code, mock_parameters, mock_input)
        
        from plexus.scores.Score import Score
        assert isinstance(result, Score.Result)
        assert result.value == "Analyzed"
        assert result.explanation == "Analysis complete"
        assert result.confidence == 0.85
        assert "text_length" in result.metadata
        assert result.metadata["processing_time"] == 1.2
    
    def test_score_function_returns_nil(self):
        """Test Lua score function that returns nil"""
        runtime = LuaRuntime()
        
        lua_code = '''
        function score(parameters, input)
            -- No match found
            return nil
        end
        '''
        
        mock_parameters = MagicMock()
        mock_parameters.model_dump.return_value = {"name": "test_score"}
        
        mock_input = MagicMock()
        mock_input.text = "Test input"
        mock_input.metadata = {}
        mock_input.results = None
        
        result = runtime.execute_score_function(lua_code, mock_parameters, mock_input)
        
        assert result is None


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestLuaLoggingIntegration:
    """Test Lua logging integration"""
    
    def test_lua_logging_functions(self):
        """Test that Lua logging functions work correctly"""
        runtime = LuaRuntime()
        
        lua_code = '''
        function test_logging(context)
            log.info("This is an info message")
            log.debug("This is a debug message")
            log.warning("This is a warning message")
            log.error("This is an error message")
            
            print("This is a print statement")
            
            return {result = "logged"}
        end
        '''
        
        with patch('plexus.CustomLogging.logging') as mock_logging:
            context = {"text": "test"}
            result = runtime.execute_function(lua_code, "test_logging", context)
            
            # Verify all logging functions were called
            assert mock_logging.info.called
            assert mock_logging.debug.called
            assert mock_logging.warning.called
            assert mock_logging.error.called
            
            assert result["result"] == "logged"
    
    def test_lua_json_utilities(self):
        """Test Lua JSON encoding/decoding utilities"""
        runtime = LuaRuntime()
        
        lua_code = '''
        function test_json(context)
            local data = {
                name = "test",
                count = 42,
                active = true
            }
            
            local json_str = json.encode(data)
            local decoded = json.decode(json_str)
            
            return {
                encoded = json_str,
                decoded_name = decoded.name,
                decoded_count = decoded.count
            }
        end
        '''
        
        context = {"text": "test"}
        result = runtime.execute_function(lua_code, "test_json", context)
        
        assert "encoded" in result
        assert result["decoded_name"] == "test"
        assert result["decoded_count"] == 42


class TestLuaAvailability:
    """Test Lua availability checking"""
    
    def test_is_lua_available(self):
        """Test is_lua_available function"""
        # This will return True if lupa is installed, False otherwise
        availability = is_lua_available()
        assert isinstance(availability, bool)
    
    @patch('plexus.scores.nodes.LuaRuntime.LUPA_AVAILABLE', False)
    def test_lua_runtime_creation_without_lupa(self):
        """Test LuaRuntime creation when lupa is not available"""
        with pytest.raises(ImportError, match="lupa library is required"):
            LuaRuntime()


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestLuaRuntimeEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_empty_context(self):
        """Test function execution with empty context"""
        runtime = LuaRuntime()
        
        lua_code = '''
        function handle_empty(context)
            if not context then
                return {error = "no context"}
            end
            
            return {result = "handled empty context"}
        end
        '''
        
        result = runtime.execute_function(lua_code, "handle_empty", {})
        assert result["result"] == "handled empty context"
    
    def test_large_data_conversion(self):
        """Test conversion of large data structures"""
        runtime = LuaRuntime()
        
        # Create a large nested structure
        large_data = {
            "items": [{"id": i, "name": f"item_{i}", "active": i % 2 == 0} for i in range(100)],
            "metadata": {
                "total": 100,
                "created": "2023-01-01",
                "tags": [f"tag_{i}" for i in range(20)]
            }
        }
        
        lua_data = runtime.python_to_lua(large_data)
        python_data = runtime.lua_to_python(lua_data)
        
        # Verify structure is preserved
        assert len(python_data["items"]) == 100
        assert python_data["items"][0]["id"] == 0
        assert python_data["items"][99]["name"] == "item_99"
        assert len(python_data["metadata"]["tags"]) == 20
    
    def test_unicode_handling(self):
        """Test handling of Unicode strings in Lua"""
        runtime = LuaRuntime()
        
        lua_code = '''
        function handle_unicode(context)
            local text = context.text
            return {
                original = text,
                length = string.len(text),
                processed = "Processed: " .. text
            }
        end
        '''
        
        unicode_context = {
            "text": "Hello 世界! Café émojis 🎉",
            "metadata": {}
        }
        
        result = runtime.execute_function(lua_code, "handle_unicode", unicode_context)
        
        assert result["original"] == unicode_context["text"]
        assert "Processed:" in result["processed"]


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])