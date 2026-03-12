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
def score(parameters, input_data):
    """Simple classification based on text length"""
    text_length = len(input_data.text)
    
    if text_length > 100:
        classification = "long"
        explanation = f"Text is long with {text_length} characters"
    elif text_length > 50:
        classification = "medium" 
        explanation = f"Text is medium with {text_length} characters"
    else:
        classification = "short"
        explanation = f"Text is short with {text_length} characters"
    
    return Score.Result(
        parameters=parameters,
        value=classification,
        explanation=explanation,
        metadata={
            "text_length": text_length,
            "explanation": explanation
        }
    )
'''


@pytest.fixture
def logging_score_code():
    """Score function that uses logging features"""
    return '''
def score(parameters, input_data):
    """Score function that tests logging capabilities"""
    print("Using print function")
    log("Using log function")
    log_info("Using log_info function")
    log_debug("Using log_debug function")
    log_warning("Using log_warning function")
    
    return Score.Result(
        parameters=parameters,
        value="logged",
        explanation="Logging test completed",
        metadata={"logged": True}
    )
'''


@pytest.fixture
def none_returning_score_code():
    """Score function that returns None (continuation logic)"""
    return '''
def score(parameters, input_data):
    """Score function that returns None for continuation"""
    log_info("Checking conditions for continuation")
    
    # Simulate a condition that doesn't match
    if "skip" in input_data.text.lower():
        return None  # Continue to next node
    
    return Score.Result(
        parameters=parameters,
        value="processed",
        explanation="Text was processed",
        metadata={"processed": True, "explanation": "Text was processed"}
    )
'''


@pytest.fixture
def error_score_code():
    """Score function that raises an error"""
    return '''
def score(parameters, input_data):
    """Score function that raises an error"""
    raise ValueError("Intentional test error")
'''


@pytest.fixture
def mock_parameters():
    """Mock parameters for LangChainUser compatibility"""
    return {
        'name': 'test_classifier',
        'temperature': 0.7,
        'model_name': 'gpt-3.5-turbo'
    }


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
def other_function():
    return "not a score function"
'''
        params = {
            **mock_parameters,
            'code': invalid_code
        }
        
        with pytest.raises(ValueError, match="Code must define a 'score' function"):
            LogicalClassifier(**params)
    
    def test_invalid_code_syntax_error(self, mock_parameters):
        """Test error when code has syntax errors"""
        invalid_code = '''
def score(parameters, input_data)
    # Missing colon - syntax error
    return None
'''
        params = {
            **mock_parameters,
            'code': invalid_code
        }
        
        with pytest.raises(SyntaxError):
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
def score(parameters, input_data):
    return Score.Result(
        parameters=parameters,
        value="test_value",
        explanation="Test explanation", 
        metadata={
            "custom_field": "custom_value",
            "numeric_field": 42,
            "boolean_field": True,
            "explanation": "This should be handled specially"
        }
    )
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
def score(parameters, input_data):
    # Test that all logging functions are available
    functions = ['print', 'log', 'log_info', 'log_debug', 'log_warning', 'log_error', 'logging']
    available_functions = []
    
    for func_name in functions:
        if func_name in globals():
            available_functions.append(func_name)
    
    return Score.Result(
        parameters=parameters,
        value="logging_test",
        explanation="Logging functions tested",
        metadata={"available_functions": available_functions}
    )
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
        
        with pytest.raises(ValueError, match="Intentional test error"):
            score_node(state)
    
    def test_invalid_score_result_type(self, mock_parameters):
        """Test handling of invalid return type from score function"""
        invalid_return_code = '''
def score(parameters, input_data):
    return "This is not a Score.Result object"
'''
        params = {
            **mock_parameters,
            'code': invalid_return_code
        }
        classifier = LogicalClassifier(**params)
        
        state = MockGraphState(text="Test", metadata={})
        score_node = classifier.get_score_node()
        
        # This should raise an AttributeError when trying to access .value on a string
        with pytest.raises(AttributeError):
            score_node(state)
    
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


class TestCodeNamespaceSecurityAndAvailability:
    """Test the security and availability of the code execution namespace"""
    
    def test_score_class_availability(self, mock_parameters):
        """Test that Score class is available in the code namespace"""
        code_using_score = '''
def score(parameters, input_data):
    # Test that Score class is available
    result = Score.Result(
        parameters=parameters,
        value="available",
        explanation="Score class is available",
        metadata={"score_available": True}
    )
    return result
'''
        params = {
            **mock_parameters,
            'code': code_using_score
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
def score(parameters, input_data):
    # Test what modules are available
    available_modules = []
    restricted_modules = ['os', 'sys', 'subprocess', 'importlib']
    
    for module_name in restricted_modules:
        try:
            # Try to access the module from globals
            if module_name in globals():
                available_modules.append(module_name)
        except:
            pass
    
    return Score.Result(
        parameters=parameters,
        value="security_test",
        explanation="Security test completed",
        metadata={"available_restricted_modules": available_modules}
    )
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
def score(parameters, input_data):
    # Test safe built-ins
    safe_functions = ['len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple']
    available_functions = []
    
    for func_name in safe_functions:
        try:
            func = eval(func_name)
            if callable(func):
                available_functions.append(func_name)
        except:
            pass
    
    return Score.Result(
        parameters=parameters,
        value="builtins_test",
        explanation="Built-ins test completed",
        metadata={"available_safe_functions": available_functions}
    )
'''
        params = {
            **mock_parameters,
            'code': code_testing_builtins
        }
        classifier = LogicalClassifier(**params)
        
        state = MockGraphState(text="Test", metadata={})
        score_node = classifier.get_score_node()
        result_state = score_node(state)
        
        # Safe built-ins should be available
        expected_functions = ['len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple']
        for func in expected_functions:
            assert func in result_state.available_safe_functions


class TestIntegration:
    """Integration tests combining multiple LogicalClassifier features"""
    
    def test_complex_scoring_workflow(self, mock_parameters):
        """Test a complex scoring scenario with multiple features"""
        complex_code = '''
def score(parameters, input_data):
    """Complex scoring that uses multiple features"""
    text = input_data.text
    metadata = input_data.metadata
    
    # Log the processing
    log_info(f"Processing text of length {len(text)}")
    print(f"Metadata keys: {list(metadata.keys())}")
    
    # Complex classification logic
    word_count = len(text.split())
    char_count = len(text)
    has_numbers = any(char.isdigit() for char in text)
    
    # Determine classification
    if word_count > 50:
        classification = "verbose"
        confidence = 0.9
    elif word_count > 20:
        classification = "detailed"  
        confidence = 0.8
    elif word_count > 5:
        classification = "brief"
        confidence = 0.7
    else:
        classification = "minimal"
        confidence = 0.6
    
    # Adjust confidence based on additional factors
    if has_numbers:
        confidence += 0.1
    
    explanation = f"Text classified as {classification} based on {word_count} words and {char_count} characters"
    
    return Score.Result(
        parameters=parameters,
        value=classification,
        explanation=explanation,
        metadata={
            "word_count": word_count,
            "char_count": char_count,
            "has_numbers": has_numbers,
            "confidence": confidence,
            "explanation": explanation
        }
    )
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
def score(parameters, input_data):
    """Score function with comprehensive logging"""
    log_info("Starting classification process")
    
    text_length = len(input_data.text)
    log_debug(f"Text length: {text_length}")
    
    if text_length == 0:
        log_warning("Empty text received")
        return Score.Result(
            parameters=parameters,
            value="empty",
            explanation="Empty text classification",
            metadata={"warning": "empty_text"}
        )
    
    print(f"Processing non-empty text with {text_length} characters")
    
    classification = "processed"
    log_info(f"Classification completed: {classification}")
    
    return Score.Result(
        parameters=parameters,
        value=classification,
        explanation="Text successfully processed",
        metadata={"processed": True}
    )
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