#!/usr/bin/env python3
"""
Comprehensive unit tests for LogicalClassifier - a critical scoring component.

LogicalClassifier executes programmatic scoring logic through embedded Python code,
making it essential for the scoring system. This test suite covers:
- Code compilation and execution safety
- Score function behavior
- State management and metadata processing
- Error handling and edge cases
- Logging functionality
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
import json
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_core import ValidationError as CoreValidationError
from io import StringIO
import sys
import logging

from plexus.scores.nodes.LogicalClassifier import LogicalClassifier
from plexus.scores.nodes.LuaRuntime import is_lua_available
from plexus.scores.Score import Score
from plexus.dashboard.api.models.score_result import ScoreResult


class MockGraphState(BaseModel):
    """Mock GraphState for testing"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    text: str = ""
    metadata: dict = {}
    classification: str = None
    explanation: str = None
    value: str = None
    criteria_met: bool = None


@pytest.fixture
def valid_score_code():
    """Valid score function code for testing"""
    return '''
function score(parameters, input_data)
    -- Simple classification based on text length
    local text_length = string.len(input_data.text)
    
    local classification, explanation
    if text_length > 100 then
        classification = "long"
        explanation = "Text is long with " .. text_length .. " characters"
    elseif text_length > 50 then
        classification = "medium"
        explanation = "Text is medium with " .. text_length .. " characters"
    else
        classification = "short"
        explanation = "Text is short with " .. text_length .. " characters"
    end
    
    return {
        value = classification,
        explanation = explanation,
        metadata = {
            text_length = text_length,
            explanation = explanation
        }
    }
end
'''


@pytest.fixture
def logging_score_code():
    """Score function that uses logging features"""
    return '''
function score(parameters, input_data)
    -- Score function that tests logging capabilities
    print("Using print function")
    log.info("Using log function")
    log.info("Using log_info function")
    log.debug("Using log_debug function")
    log.warning("Using log_warning function")
    
    return {
        value = "logged",
        explanation = "Logging test completed",
        metadata = {
            logged = true
        }
    }
end
'''


@pytest.fixture
def none_returning_score_code():
    """Score function that returns None (continuation logic)"""
    return '''
function score(parameters, input_data)
    -- Score function that returns nil for continuation
    log.info("Checking conditions for continuation")
    
    -- Simulate a condition that doesn't match
    if string.find(string.lower(input_data.text), "skip") then
        return nil  -- Continue to next node
    end
    
    return {
        value = "processed",
        explanation = "Text was processed",
        metadata = {
            processed = true,
            explanation = "Text was processed"
        }
    }
end
'''


@pytest.fixture
def error_score_code():
    """Score function that raises an error"""
    return '''
function score(parameters, input_data)
    -- Score function that raises an error
    error("Intentional test error")
end
'''


@pytest.fixture
def mock_parameters():
    """Mock parameters for LangChainUser compatibility"""
    return {
        'name': 'test_classifier',
        'temperature': 0.7,
        'model_name': 'gpt-3.5-turbo'
    }


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestLogicalClassifierInstantiation:
    """Test LogicalClassifier instantiation and parameter validation"""
    
    def test_valid_instantiation(self, valid_score_code, mock_parameters):
        """Test successful instantiation with valid parameters"""
        params = {
            **mock_parameters,
            'code': valid_score_code
        }
        
        classifier = LogicalClassifier(**params)
        
        assert classifier is not None
        assert classifier.score_function is not None
        assert callable(classifier.score_function)
        assert classifier.parameters.code == valid_score_code
    
    def test_missing_score_function_error(self, mock_parameters):
        """Test error when code doesn't define a score function"""
        invalid_code = '''
function other_function()
    return "not a score function"
end
'''
        params = {
            **mock_parameters,
            'code': invalid_code
        }
        
        with pytest.raises(ValueError, match="Lua code must define a 'score' function"):
            LogicalClassifier(**params)
    
    def test_invalid_code_syntax_error(self, mock_parameters):
        """Test error when code has syntax errors"""
        invalid_code = '''
function score(parameters, input_data
    -- Missing closing parenthesis - syntax error
    return nil
end
'''
        params = {
            **mock_parameters,
            'code': invalid_code
        }
        
        with pytest.raises(Exception):  # Lua syntax errors may come as different exception types
            LogicalClassifier(**params)
    
    def test_optional_conditions_parameter(self, valid_score_code, mock_parameters):
        """Test that conditions parameter is optional"""
        params = {
            **mock_parameters,
            'code': valid_score_code,
            'conditions': None  # Should be allowed
        }
        
        classifier = LogicalClassifier(**params)
        assert classifier.parameters.conditions is None
        
        # Also test with conditions provided
        params['conditions'] = [{'condition': 'value == "test"', 'target': 'next_node'}]
        classifier = LogicalClassifier(**params)
        assert classifier.parameters.conditions is not None


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestScoreFunctionExecution:
    """Test the score function execution and result handling"""
    
    def test_successful_score_execution(self, valid_score_code, mock_parameters):
        """Test successful execution of score function"""
        params = {
            **mock_parameters,
            'code': valid_score_code
        }
        classifier = LogicalClassifier(**params)
        
        # Create mock state
        state = MockGraphState(
            text="This is a test text that is definitely longer than fifty characters to trigger medium classification",
            metadata={"test": "data"}
        )
        
        # Execute the score node
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        assert result_state is not None
        assert result_state.classification == "medium"
        assert result_state.value == "medium"
        assert "medium" in result_state.explanation
        assert "characters" in result_state.explanation
    
    def test_short_text_classification(self, valid_score_code, mock_parameters):
        """Test classification of short text"""
        params = {
            **mock_parameters,
            'code': valid_score_code
        }
        classifier = LogicalClassifier(**params)
        
        state = MockGraphState(text="Short text", metadata={})
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        assert result_state.classification == "short"
        assert result_state.value == "short"
        assert "short" in result_state.explanation
    
    def test_long_text_classification(self, valid_score_code, mock_parameters):
        """Test classification of long text"""
        params = {
            **mock_parameters,
            'code': valid_score_code
        }
        classifier = LogicalClassifier(**params)
        
        # Create long text (over 100 characters)
        long_text = "This is a very long text " * 10  # Creates text over 100 characters
        state = MockGraphState(text=long_text, metadata={})
        
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        assert result_state.classification == "long"
        assert result_state.value == "long"
        assert "long" in result_state.explanation
    
    def test_none_return_continuation(self, none_returning_score_code, mock_parameters):
        """Test that returning None allows flow continuation"""
        params = {
            **mock_parameters,
            'code': none_returning_score_code
        }
        classifier = LogicalClassifier(**params)
        
        # Test with text that should trigger None return
        state = MockGraphState(text="Please skip this text", metadata={})
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        # Should return original state unchanged
        assert result_state.text == "Please skip this text"
        assert result_state.classification is None
        assert result_state.value is None
    
    def test_normal_processing_after_continuation_check(self, none_returning_score_code, mock_parameters):
        """Test normal processing when continuation condition is not met"""
        params = {
            **mock_parameters,
            'code': none_returning_score_code
        }
        classifier = LogicalClassifier(**params)
        
        # Test with text that should NOT trigger None return
        state = MockGraphState(text="Process this text normally", metadata={})
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        assert result_state.classification == "processed"
        assert result_state.value == "processed"
        assert result_state.explanation == "Text was processed"


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestStateManagement:
    """Test state management and metadata processing"""
    
    def test_metadata_merging(self, valid_score_code, mock_parameters):
        """Test that state metadata is properly merged"""
        params = {
            **mock_parameters,
            'code': valid_score_code
        }
        classifier = LogicalClassifier(**params)
        
        # Create state with metadata
        state = MockGraphState(
            text="Test text for metadata",
            metadata={"original": "data", "source": "test"},
            explanation="Previous explanation"
        )
        
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        # Check that original metadata and state attributes are preserved
        # The score function should have access to both in its input
        assert result_state is not None
        assert result_state.classification is not None
    
    def test_result_metadata_integration(self, mock_parameters):
        """Test that result metadata becomes part of state"""
        code_with_metadata = '''
function score(parameters, input_data)
    return {
        value = "test_value",
        explanation = "Test explanation",
        metadata = {
            custom_field = "custom_value",
            numeric_field = 42,
            boolean_field = true,
            explanation = "This should be handled specially"
        }
    }
end
'''
        params = {
            **mock_parameters,
            'code': code_with_metadata
        }
        classifier = LogicalClassifier(**params)
        
        state = MockGraphState(text="Test", metadata={})
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        # Check that metadata fields become state attributes
        assert result_state.custom_field == "custom_value"
        assert result_state.numeric_field == 42
        assert result_state.boolean_field == True
        
        # Check that explanation comes from metadata (LogicalClassifier uses metadata.get('explanation'))
        assert result_state.explanation == "This should be handled specially"
    
    def test_dict_state_input_conversion(self, valid_score_code, mock_parameters):
        """Test conversion of dict state input to GraphState"""
        params = {
            **mock_parameters,
            'code': valid_score_code
        }
        classifier = LogicalClassifier(**params)
        
        # Pass dict instead of GraphState object
        dict_state = {
            'text': 'Dictionary state input',
            'metadata': {'type': 'dict'},
            'classification': None,
            'explanation': None,
            'value': None,
            'criteria_met': None
        }
        
        score_node = classifier.get_score_node()
        result_state = score_node(dict_state)
        
        assert result_state is not None
        assert result_state.classification == "short"  # Text is short
        assert isinstance(result_state, classifier.GraphState)


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestLoggingFunctionality:
    """Test the logging capabilities of LogicalClassifier"""
    
    @patch('plexus.scores.nodes.LogicalClassifier.logging')
    def test_print_function_logging(self, mock_logging, logging_score_code, mock_parameters):
        """Test that print function logs messages"""
        params = {
            **mock_parameters,
            'code': logging_score_code
        }
        classifier = LogicalClassifier(**params)
        
        state = MockGraphState(text="Test logging", metadata={})
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        # Verify logging calls were made
        mock_logging.info.assert_any_call("[LogicalClassifier] Using print function")
        mock_logging.info.assert_any_call("[LogicalClassifier] Using log function")
        mock_logging.info.assert_any_call("[LogicalClassifier] Using log_info function")
        mock_logging.debug.assert_called_with("[LogicalClassifier] Using log_debug function")
        mock_logging.warning.assert_called_with("[LogicalClassifier] Using log_warning function")
    
    def test_logging_functions_availability(self, mock_parameters):
        """Test that all logging functions are available in the code namespace"""
        code_testing_logging = '''
function score(parameters, input_data)
    -- Test that logging functions are available
    local available_functions = {}
    
    -- Test print function
    if print then
        table.insert(available_functions, "print")
    end
    
    -- Test log functions
    if log and log.info then
        table.insert(available_functions, "log.info")
    end
    if log and log.debug then
        table.insert(available_functions, "log.debug")
    end
    if log and log.warning then
        table.insert(available_functions, "log.warning")
    end
    
    return {
        value = "logging_test",
        explanation = "Logging functions tested",
        metadata = {
            available_functions = available_functions
        }
    }
end
'''
        params = {
            **mock_parameters,
            'code': code_testing_logging
        }
        classifier = LogicalClassifier(**params)
        
        state = MockGraphState(text="Test", metadata={})
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        # All logging functions should be available
        expected_functions = ['print', 'log', 'log_info', 'log_debug', 'log_warning', 'log_error', 'logging']
        assert result_state.available_functions == expected_functions


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_score_function_exception_propagation(self, error_score_code, mock_parameters):
        """Test that exceptions in score function are properly propagated"""
        params = {
            **mock_parameters,
            'code': error_score_code
        }
        classifier = LogicalClassifier(**params)
        
        state = MockGraphState(text="Test", metadata={})
        score_node = classifier.get_score_node()
        
        # With error handling in place, errors should be caught and original state returned
        result_state = score_node(state)
        assert result_state == state  # Should return original state on error
    
    def test_invalid_score_result_type(self, mock_parameters):
        """Test handling of invalid return type from score function"""
        invalid_return_code = '''
function score(parameters, input_data)
    return "This is not a valid result table"
end
'''
        params = {
            **mock_parameters,
            'code': invalid_return_code
        }
        classifier = LogicalClassifier(**params)
        
        state = MockGraphState(text="Test", metadata={})
        score_node = classifier.get_score_node()
        
        # This should also return original state due to error handling 
        result_state = score_node(state)
        assert result_state == state  # Should return original state on invalid return
    
    def test_empty_text_handling(self, valid_score_code, mock_parameters):
        """Test handling of empty text input"""
        params = {
            **mock_parameters,
            'code': valid_score_code
        }
        classifier = LogicalClassifier(**params)
        
        state = MockGraphState(text="", metadata={})
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        # Empty text should be classified as "short"
        assert result_state.classification == "short"
        assert result_state.value == "short"
    
    def test_missing_text_attribute(self, valid_score_code, mock_parameters):
        """Test handling when state doesn't have text attribute"""
        params = {
            **mock_parameters,
            'code': valid_score_code
        }
        classifier = LogicalClassifier(**params)
        
        # Create state without text attribute (using dict) - should fail GraphState validation
        state_dict = {'metadata': {}}  # Missing required 'text' field
        
        score_node = classifier.get_score_node()
        
        # This should raise an error due to missing required text field in GraphState
        with pytest.raises((ValidationError, CoreValidationError, TypeError)):
            score_node(state_dict)


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestCodeNamespaceSecurityAndAvailability:
    """Test the security and availability of the code execution namespace"""
    
    def test_score_result_creation(self, mock_parameters):
        """Test that score results can be created in Lua"""
        code_creating_result = '''
function score(parameters, input_data)
    -- Test that we can create result tables
    return {
        value = "available",
        explanation = "Result creation works",
        metadata = {
            score_available = true
        }
    }
end
'''
        params = {
            **mock_parameters,
            'code': code_creating_result
        }
        classifier = LogicalClassifier(**params)
        
        state = MockGraphState(text="Test", metadata={})
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        assert result_state.classification == "available"
        assert result_state.score_available == True
    
    def test_restricted_module_access(self, mock_parameters):
        """Test that dangerous modules are not available by default"""
        code_testing_imports = '''
function score(parameters, input_data)
    -- Test what potentially dangerous functions are available
    local available_modules = {}
    
    -- Test if dangerous Lua functions are restricted
    if os then
        table.insert(available_modules, "os")
    end
    if io then
        table.insert(available_modules, "io")
    end
    if require then
        table.insert(available_modules, "require")
    end
    if loadfile then
        table.insert(available_modules, "loadfile")
    end
    
    return {
        value = "security_test",
        explanation = "Security test completed",
        metadata = {
            available_restricted_modules = available_modules
        }
    }
end
'''
        params = {
            **mock_parameters,
            'code': code_testing_imports
        }
        classifier = LogicalClassifier(**params)
        
        state = MockGraphState(text="Test", metadata={})
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        # Restricted modules should not be available
        assert result_state.available_restricted_modules == []
    
    def test_safe_builtins_availability(self, mock_parameters):
        """Test that safe built-in functions are available"""
        code_testing_builtins = '''
function score(parameters, input_data)
    -- Test safe Lua built-ins
    local available_functions = {}
    
    -- Test Lua standard library functions
    if string then
        table.insert(available_functions, "string")
    end
    if table then
        table.insert(available_functions, "table")
    end
    if math then
        table.insert(available_functions, "math")
    end
    if type then
        table.insert(available_functions, "type")
    end
    if tostring then
        table.insert(available_functions, "tostring")
    end
    if tonumber then
        table.insert(available_functions, "tonumber")
    end
    
    return {
        value = "builtins_test",
        explanation = "Built-ins test completed",
        metadata = {
            available_safe_functions = available_functions
        }
    }
end
'''
        params = {
            **mock_parameters,
            'code': code_testing_builtins
        }
        classifier = LogicalClassifier(**params)
        
        state = MockGraphState(text="Test", metadata={})
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        # Safe Lua built-ins should be available
        expected_functions = ['string', 'table', 'math', 'type', 'tostring', 'tonumber']
        for func in expected_functions:
            assert func in result_state.available_safe_functions


@pytest.mark.skipif(not is_lua_available(), reason="Lua runtime not available")
class TestIntegration:
    """Integration tests combining multiple LogicalClassifier features"""
    
    def test_complex_scoring_workflow(self, mock_parameters):
        """Test a complex scoring scenario with multiple features"""
        complex_code = '''
function score(parameters, input_data)
    -- Complex scoring that uses multiple features
    local text = input_data.text
    local metadata = input_data.metadata or {}
    
    -- Log the processing
    log.info("Processing text of length " .. string.len(text))
    print("Processing complex scoring")
    
    -- Complex classification logic
    local word_count = 0
    for word in string.gmatch(text, "%S+") do
        word_count = word_count + 1
    end
    
    local char_count = string.len(text)
    local has_numbers = string.find(text, "%d") ~= nil
    
    -- Determine classification
    local classification, confidence
    if word_count > 50 then
        classification = "verbose"
        confidence = 0.9
    elseif word_count > 20 then
        classification = "detailed"
        confidence = 0.8
    elseif word_count > 5 then
        classification = "brief"
        confidence = 0.7
    else
        classification = "minimal"
        confidence = 0.6
    end
    
    -- Adjust confidence based on additional factors
    if has_numbers then
        confidence = confidence + 0.1
    end
    
    local explanation = "Text classified as " .. classification .. " based on " .. 
                       word_count .. " words and " .. char_count .. " characters"
    
    return {
        value = classification,
        explanation = explanation,
        metadata = {
            word_count = word_count,
            char_count = char_count,
            has_numbers = has_numbers,
            confidence = confidence,
            explanation = explanation
        }
    }
end
'''
        params = {
            **mock_parameters,
            'code': complex_code
        }
        classifier = LogicalClassifier(**params)
        
        # Test with detailed text
        state = MockGraphState(
            text="This is a moderately detailed text that contains multiple sentences and provides a reasonable amount of information for classification testing purposes with numbers like 123.",
            metadata={"source": "test", "priority": "high"}
        )
        
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        # Verify complex scoring results
        assert result_state.classification == "detailed"  # Should be detailed based on word count
        assert result_state.value == "detailed"
        assert "detailed" in result_state.explanation
        assert result_state.word_count > 20
        assert result_state.has_numbers == True
        assert result_state.confidence > 0.8  # Should be boosted due to numbers
    
    @patch('plexus.scores.nodes.LogicalClassifier.logging')
    def test_logging_integration_workflow(self, mock_logging, mock_parameters):
        """Test that logging works properly in complex workflow"""
        logging_workflow_code = '''
function score(parameters, input_data)
    -- Score function with comprehensive logging
    log.info("Starting classification process")
    
    local text_length = string.len(input_data.text)
    log.debug("Text length: " .. text_length)
    
    if text_length == 0 then
        log.warning("Empty text received")
        return {
            value = "empty",
            explanation = "Empty text classification",
            metadata = {
                warning = "empty_text"
            }
        }
    end
    
    print("Processing non-empty text with " .. text_length .. " characters")
    
    local classification = "processed"
    log.info("Classification completed: " .. classification)
    
    return {
        value = classification,
        explanation = "Text successfully processed",
        metadata = {
            processed = true
        }
    }
end
'''
        params = {
            **mock_parameters,
            'code': logging_workflow_code
        }
        classifier = LogicalClassifier(**params)
        
        # Test with normal text
        state = MockGraphState(text="Normal text for processing", metadata={})
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        # Verify results
        assert result_state.classification == "processed"
        assert result_state.processed == True
        
        # Verify logging calls
        mock_logging.info.assert_any_call("[LogicalClassifier] Starting classification process")
        mock_logging.debug.assert_any_call("[LogicalClassifier] Text length: 26")  # Actual length of "Normal text for processing"
        mock_logging.info.assert_any_call("[LogicalClassifier] Processing non-empty text with 26 characters")  # Actual length
        mock_logging.info.assert_any_call("[LogicalClassifier] Classification completed: processed")


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])