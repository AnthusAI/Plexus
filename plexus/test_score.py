#!/usr/bin/env python3
"""
Comprehensive tests for Score.py - the foundation class of the entire scoring system.

This test suite focuses on the most critical aspects of the Score base class:
- Score.Parameters validation and data conversion
- Score.Input standardization and edge cases
- Score.Result creation, comparison, and helper methods
- Score initialization and parameter validation
- Registry integration (Score.from_name)
- Path generation and utilities
- Cost tracking interface

The Score class is the foundation that all other scoring classes inherit from,
making these tests critical for the reliability of the entire scoring system.
"""

import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError
from decimal import Decimal

from plexus.scores.Score import Score


class ConcreteScore(Score):
    """Concrete implementation of Score for testing since Score is abstract"""
    
    def predict(self, context, model_input: Score.Input):
        """Concrete implementation of the abstract predict method"""
        return Score.Result(
            parameters=self.parameters,
            value="test_result",
            explanation="Test prediction result"
        )


class TestScoreParameters:
    """Test Score.Parameters validation and data conversion"""
    
    def test_basic_parameters_creation(self):
        """Test basic Score.Parameters creation with valid data"""
        params = Score.Parameters(
            name="test_score",
            scorecard_name="test_scorecard",
            id="test_id_123"
        )
        
        assert params.name == "test_score"
        assert params.scorecard_name == "test_scorecard"
        assert params.id == "test_id_123"
        assert params.data is None  # Default value
        assert params.dependencies is None  # Default value
    
    def test_parameters_with_data_percentage_conversion(self):
        """Test automatic percentage conversion in data field"""
        # Test with percentage string
        params = Score.Parameters(
            name="test_score",
            data={"percentage": "85%", "other_field": "value"}
        )
        
        assert params.data["percentage"] == 85.0
        assert params.data["other_field"] == "value"
    
    def test_parameters_with_numeric_percentage(self):
        """Test percentage handling when already numeric"""
        params = Score.Parameters(
            name="test_score",
            data={"percentage": 75.5, "threshold": 0.8}
        )
        
        assert params.data["percentage"] == 75.5
        assert params.data["threshold"] == 0.8
    
    def test_parameters_without_percentage_gets_default(self):
        """Test that missing percentage gets default value of 100.0"""
        params = Score.Parameters(
            name="test_score",
            data={"other_field": "value"}
        )
        
        assert params.data["percentage"] == 100.0
        assert params.data["other_field"] == "value"
    
    def test_parameters_with_string_percentage_variations(self):
        """Test various string percentage formats"""
        test_cases = [
            ("50%", 50.0),
            ("  75% ", 75.0),  # With whitespace
            ("100.5%", 100.5),  # Decimal percentage
            ("0%", 0.0),  # Zero percentage
        ]
        
        for input_val, expected in test_cases:
            params = Score.Parameters(
                name="test_score",
                data={"percentage": input_val}
            )
            assert params.data["percentage"] == expected
    
    def test_parameters_with_dependencies(self):
        """Test parameters with dependency configuration"""
        dependencies = [
            {"name": "prerequisite_score", "condition": "value == 'yes'"},
            {"name": "another_score", "condition": "confidence > 0.8"}
        ]
        
        params = Score.Parameters(
            name="dependent_score",
            dependencies=dependencies,
            label_score_name="custom_label",
            label_field="special_field"
        )
        
        assert len(params.dependencies) == 2
        assert params.dependencies[0]["name"] == "prerequisite_score"
        assert params.label_score_name == "custom_label"
        assert params.label_field == "special_field"
    
    def test_parameters_with_all_optional_fields(self):
        """Test parameters with all optional fields populated"""
        params = Score.Parameters(
            scorecard_name="comprehensive_scorecard",
            name="comprehensive_score",
            id=12345,  # Numeric ID
            key="comp_score_key",
            dependencies=[{"name": "dep1"}],
            data={"percentage": "90%", "model": "gpt-4"},
            number_of_classes=5,
            label_score_name="custom_label_score",
            label_field="label_suffix"
        )
        
        assert params.scorecard_name == "comprehensive_scorecard"
        assert params.name == "comprehensive_score"
        assert params.id == 12345
        assert params.key == "comp_score_key"
        assert len(params.dependencies) == 1
        assert params.data["percentage"] == 90.0
        assert params.data["model"] == "gpt-4"
        assert params.number_of_classes == 5
        assert params.label_score_name == "custom_label_score"
        assert params.label_field == "label_suffix"


class TestScoreInput:
    """Test Score.Input standardization and validation"""
    
    def test_basic_input_creation(self):
        """Test basic Score.Input creation"""
        input_obj = Score.Input(
            text="Test transcript content",
            metadata={"source": "phone_call", "duration": 300}
        )
        
        assert input_obj.text == "Test transcript content"
        assert input_obj.metadata["source"] == "phone_call"
        assert input_obj.metadata["duration"] == 300
        assert input_obj.results is None  # Default value
    
    def test_input_with_empty_metadata(self):
        """Test Score.Input with empty metadata (default behavior)"""
        input_obj = Score.Input(text="Simple text")
        
        assert input_obj.text == "Simple text"
        assert input_obj.metadata == {}
        assert input_obj.results is None
    
    def test_input_with_results_for_dependencies(self):
        """Test Score.Input with results for dependent scores"""
        previous_results = [
            {"name": "PrerequisiteScore", "result": "yes"},
            {"name": "ConfidenceScore", "result": 0.85}
        ]
        
        input_obj = Score.Input(
            text="Text with dependencies",
            metadata={"context": "multi_step_pipeline"},
            results=previous_results
        )
        
        assert input_obj.text == "Text with dependencies"
        assert input_obj.metadata["context"] == "multi_step_pipeline"
        assert len(input_obj.results) == 2
        assert input_obj.results[0]["name"] == "PrerequisiteScore"
        assert input_obj.results[1]["result"] == 0.85
    
    def test_input_with_complex_metadata(self):
        """Test Score.Input with nested, complex metadata"""
        complex_metadata = {
            "source": "customer_service_call",
            "call_info": {
                "caller_id": "+1234567890",
                "agent_id": "agent_001",
                "call_duration": 1200,
                "call_quality": "high"
            },
            "conversation_context": {
                "topics": ["billing", "technical_support", "complaint"],
                "sentiment": "frustrated",
                "previous_interactions": 3
            },
            "system_metadata": {
                "recording_quality": 0.95,
                "transcript_confidence": 0.88,
                "processing_timestamp": "2023-01-01T12:00:00Z"
            }
        }
        
        input_obj = Score.Input(
            text="Complex conversation transcript...",
            metadata=complex_metadata
        )
        
        assert input_obj.metadata["source"] == "customer_service_call"
        assert input_obj.metadata["call_info"]["caller_id"] == "+1234567890"
        assert len(input_obj.metadata["conversation_context"]["topics"]) == 3
        assert input_obj.metadata["system_metadata"]["recording_quality"] == 0.95
    
    def test_input_with_very_long_text(self):
        """Test Score.Input with very long text content"""
        # Create a 50KB text string
        long_text = "This is a very long transcript. " * 1500  # ~50KB
        
        input_obj = Score.Input(
            text=long_text,
            metadata={"length": len(long_text)}
        )
        
        assert len(input_obj.text) > 45000  # Verify it's actually long
        assert input_obj.metadata["length"] == len(long_text)
    
    def test_input_with_unicode_text(self):
        """Test Score.Input with Unicode and special characters"""
        unicode_text = "Conversation with émojis 🎉, accénts, and 中文字符"
        
        input_obj = Score.Input(
            text=unicode_text,
            metadata={"encoding": "utf-8", "language": "mixed"}
        )
        
        assert input_obj.text == unicode_text
        assert input_obj.metadata["language"] == "mixed"


class TestScoreResult:
    """Test Score.Result creation, comparison, and helper methods"""
    
    @pytest.fixture
    def sample_parameters(self):
        """Sample parameters for testing Results"""
        return Score.Parameters(
            name="test_score",
            scorecard_name="test_scorecard"
        )
    
    def test_basic_result_creation(self, sample_parameters):
        """Test basic Score.Result creation"""
        result = Score.Result(
            parameters=sample_parameters,
            value="Yes",
            explanation="Clear positive indication found",
            confidence=0.95
        )
        
        assert result.parameters.name == "test_score"
        assert result.value == "Yes"
        assert result.explanation == "Clear positive indication found"
        assert result.confidence == 0.95
        assert result.metadata == {}
        assert result.error is None
    
    def test_result_with_metadata(self, sample_parameters):
        """Test Score.Result with metadata"""
        metadata = {
            "processing_time": 1.2,
            "model_version": "gpt-4-turbo",
            "tokens_used": 150,
            "trace": {"step1": "analysis", "step2": "decision"}
        }
        
        result = Score.Result(
            parameters=sample_parameters,
            value="No",
            explanation="No clear indication found",
            confidence=0.75,
            metadata=metadata
        )
        
        assert result.value == "No"
        assert result.metadata["processing_time"] == 1.2
        assert result.metadata["model_version"] == "gpt-4-turbo"
        assert result.metadata["tokens_used"] == 150
        assert result.metadata["trace"]["step1"] == "analysis"
    
    def test_result_with_error(self, sample_parameters):
        """Test Score.Result with error information"""
        result = Score.Result(
            parameters=sample_parameters,
            value="ERROR",
            error="API timeout after 30 seconds",
            explanation="Failed to complete prediction due to timeout"
        )
        
        assert result.value == "ERROR"
        assert result.error == "API timeout after 30 seconds"
        assert result.explanation == "Failed to complete prediction due to timeout"
    
    def test_result_is_yes_method(self, sample_parameters):
        """Test Score.Result.is_yes() method"""
        test_cases = [
            ("yes", True),
            ("Yes", True),
            ("YES", True),
            ("no", False),
            ("No", False),
            ("maybe", False),
            ("true", False),  # Only "yes" should return True
        ]
        
        for value, expected in test_cases:
            result = Score.Result(
                parameters=sample_parameters,
                value=value,
                explanation="Test case"
            )
            assert result.is_yes() == expected
    
    def test_result_is_no_method(self, sample_parameters):
        """Test Score.Result.is_no() method"""
        test_cases = [
            ("no", True),
            ("No", True),
            ("NO", True),
            ("yes", False),
            ("Yes", False),
            ("false", False),  # Only "no" should return True
            ("negative", False),
        ]
        
        for value, expected in test_cases:
            result = Score.Result(
                parameters=sample_parameters,
                value=value,
                explanation="Test case"
            )
            assert result.is_no() == expected
    
    def test_result_equality_with_other_result(self, sample_parameters):
        """Test Score.Result equality comparison with another Result"""
        result1 = Score.Result(
            parameters=sample_parameters,
            value="Yes",
            explanation="First result"
        )
        
        result2 = Score.Result(
            parameters=sample_parameters,
            value="yes",  # Different case
            explanation="Second result"
        )
        
        result3 = Score.Result(
            parameters=sample_parameters,
            value="No",
            explanation="Different value"
        )
        
        assert result1 == result2  # Case-insensitive equality
        assert not (result1 == result3)  # Different values
    
    def test_result_equality_with_string(self, sample_parameters):
        """Test Score.Result equality comparison with string"""
        result = Score.Result(
            parameters=sample_parameters,
            value="Maybe",
            explanation="Uncertain result"
        )
        
        assert result == "maybe"  # Case-insensitive
        assert result == "Maybe"
        assert result == "MAYBE"
        assert not (result == "yes")
        assert not (result == "no")
    
    def test_result_backwards_compatibility_properties(self, sample_parameters):
        """Test backwards compatibility properties for explanation and confidence"""
        metadata_with_compat = {
            "explanation": "Metadata explanation",
            "confidence": 0.82,
            "other_data": "some_value"
        }
        
        result = Score.Result(
            parameters=sample_parameters,
            value="Yes",
            explanation="Direct explanation",  # This should take precedence
            confidence=0.90,  # This should take precedence
            metadata=metadata_with_compat
        )
        
        # Direct properties should be used, not metadata
        assert result.explanation == "Direct explanation"
        assert result.confidence == 0.90
        
        # But backwards compatibility properties should access metadata
        assert result.explanation_from_metadata == "Metadata explanation"
        assert result.confidence_from_metadata == 0.82
    
    def test_result_backwards_compatibility_with_empty_metadata(self, sample_parameters):
        """Test backwards compatibility when metadata is empty"""
        result = Score.Result(
            parameters=sample_parameters,
            value="Yes",
            explanation="Direct explanation"
        )
        
        assert result.explanation_from_metadata is None
        assert result.confidence_from_metadata is None
    
    def test_result_with_boolean_value(self, sample_parameters):
        """Test Score.Result with boolean value"""
        result = Score.Result(
            parameters=sample_parameters,
            value=True,
            explanation="Boolean true result"
        )
        
        assert result.value is True
        assert result.explanation == "Boolean true result"


class TestScoreInitialization:
    """Test Score initialization and parameter validation"""
    
    def test_successful_score_initialization(self):
        """Test successful Score initialization with valid parameters"""
        score = ConcreteScore(
            name="test_score",
            scorecard_name="test_scorecard",
            data={"percentage": "75%"}
        )
        
        assert score.parameters.name == "test_score"
        assert score.parameters.scorecard_name == "test_scorecard"
        assert score.parameters.data["percentage"] == 75.0
        assert score._is_multi_class is None  # Lazy initialization
        assert score._number_of_classes is None  # Lazy initialization
    
    def test_score_initialization_with_validation_error(self):
        """Test Score initialization with parameter validation error"""
        # This should cause a validation error because we're passing invalid data
        with patch('plexus.scores.Score.Score.log_validation_errors') as mock_log:
            with pytest.raises(ValidationError):
                # Try to create parameters that would fail validation
                # Note: Score.Parameters is quite permissive, so we need to force an error
                ConcreteScore(data="not_a_dict")  # data should be dict, not string
    
    def test_log_validation_errors_formatting(self):
        """Test that validation errors are properly formatted and logged"""
        with patch('plexus.scores.Score.logging') as mock_logging:
            # Create a mock ValidationError
            mock_error = MagicMock()
            mock_error.errors.return_value = [
                {"loc": ("data",), "msg": "value is not a valid dict"},
                {"loc": ("name", "field"), "msg": "field required"}
            ]
            
            Score.log_validation_errors(mock_error)
            
            # Verify logging calls
            mock_logging.error.assert_any_call("Parameter validation errors occurred:")
            mock_logging.error.assert_any_call("Field: data, Error: value is not a valid dict")
            mock_logging.error.assert_any_call("Field: name.field, Error: field required")
    
    def test_score_with_complex_initialization(self):
        """Test Score initialization with complex parameter configuration"""
        complex_data = {
            "percentage": "90%",
            "model_settings": {
                "temperature": 0.7,
                "max_tokens": 1000,
                "top_p": 0.9
            },
            "preprocessing": {
                "normalize": True,
                "remove_stopwords": False
            }
        }
        
        dependencies = [
            {"name": "prerequisite_1", "condition": "value == 'ready'"},
            {"name": "prerequisite_2", "condition": "confidence > 0.5"}
        ]
        
        score = ConcreteScore(
            name="complex_score",
            scorecard_name="complex_scorecard",
            id="complex_id_456",
            key="complex_key",
            data=complex_data,
            dependencies=dependencies,
            number_of_classes=3,
            label_score_name="complex_label",
            label_field="suffix"
        )
        
        assert score.parameters.name == "complex_score"
        assert score.parameters.data["percentage"] == 90.0
        assert score.parameters.data["model_settings"]["temperature"] == 0.7
        assert len(score.parameters.dependencies) == 2
        assert score.parameters.number_of_classes == 3


class TestScoreUtilityMethods:
    """Test Score utility methods like path generation and label handling"""
    
    def test_report_directory_path(self):
        """Test report directory path generation"""
        score = ConcreteScore(
            name="Test Score With Spaces",
            scorecard_name="Test Scorecard"
        )
        
        expected_path = "./tmp/reports/Test_Scorecard/Test_Score_With_Spaces/"
        assert score.report_directory_path() == expected_path
    
    def test_model_directory_path(self):
        """Test model directory path generation"""
        score = ConcreteScore(
            name="model-score",
            scorecard_name="ml-scorecard"
        )
        
        expected_path = "./models/ml-scorecard/model-score/"
        assert score.model_directory_path() == expected_path
    
    def test_get_label_score_name_basic(self):
        """Test basic label score name determination"""
        score = ConcreteScore(
            name="basic_score",
            scorecard_name="test_scorecard"
        )
        
        assert score.get_label_score_name() == "basic_score"
    
    def test_get_label_score_name_with_custom_label(self):
        """Test label score name with custom label_score_name"""
        with patch('plexus.scores.Score.logging') as mock_logging:
            score = ConcreteScore(
                name="actual_score",
                scorecard_name="test_scorecard",
                label_score_name="custom_label_score"
            )
            
            result = score.get_label_score_name()
            assert result == "custom_label_score"
            mock_logging.info.assert_called_with("Using label_score_name: custom_label_score")
    
    def test_get_label_score_name_with_label_field(self):
        """Test label score name with label_field suffix"""
        score = ConcreteScore(
            name="base_score",
            scorecard_name="test_scorecard",
            label_field="validation"
        )
        
        assert score.get_label_score_name() == "base_score validation"
    
    def test_get_label_score_name_with_both_custom_and_field(self):
        """Test label score name with both custom label and field"""
        score = ConcreteScore(
            name="original_score",
            scorecard_name="test_scorecard",
            label_score_name="custom_base",
            label_field="suffix"
        )
        
        assert score.get_label_score_name() == "custom_base suffix"
    
    def test_get_accumulated_costs_default(self):
        """Test default cost accumulation (should return zero cost)"""
        score = ConcreteScore(
            name="cost_test_score",
            scorecard_name="test_scorecard"
        )
        
        costs = score.get_accumulated_costs()
        assert costs == {"total_cost": 0}


class TestScoreFromName:
    """Test Score.from_name registry integration"""
    
    def test_successful_score_from_name(self):
        """Test successful Score.from_name with valid scorecard and score"""
        # Mock the registry system
        mock_scorecard_class = MagicMock()
        mock_score_class = MagicMock()
        mock_score_instance = MagicMock()
        
        mock_scorecard_class.score_registry.get_properties.return_value = {
            "name": "test_score",
            "scorecard_name": "test_scorecard"
        }
        mock_scorecard_class.score_registry.get.return_value = mock_score_class
        mock_score_class.return_value = mock_score_instance
        
        with patch('plexus.scores.Score.scorecard_registry') as mock_registry:
            mock_registry.get.return_value = mock_scorecard_class
            
            result = Score.from_name("test_scorecard", "test_score")
            
            # Verify registry calls
            mock_registry.get.assert_called_once_with("test_scorecard")
            mock_scorecard_class.score_registry.get_properties.assert_called_once_with("test_score")
            mock_scorecard_class.score_registry.get.assert_called_once_with("test_score")
            
            # Verify score instantiation
            mock_score_class.assert_called_once_with(
                name="test_score",
                scorecard_name="test_scorecard"
            )
            
            assert result == mock_score_instance
    
    def test_score_from_name_scorecard_not_found(self):
        """Test Score.from_name with nonexistent scorecard"""
        with patch('plexus.scores.Score.scorecard_registry') as mock_registry:
            mock_registry.get.return_value = None
            
            with pytest.raises(ValueError, match="Scorecard 'nonexistent_scorecard' not found"):
                Score.from_name("nonexistent_scorecard", "some_score")
    
    def test_score_from_name_score_not_found(self):
        """Test Score.from_name with nonexistent score in valid scorecard"""
        mock_scorecard_class = MagicMock()
        mock_scorecard_class.score_registry.get_properties.return_value = {}
        mock_scorecard_class.score_registry.get.return_value = None  # Score not found
        
        with patch('plexus.scores.Score.scorecard_registry') as mock_registry:
            mock_registry.get.return_value = mock_scorecard_class
            
            with pytest.raises(ValueError, match="Score 'nonexistent_score' not found in scorecard 'valid_scorecard'"):
                Score.from_name("valid_scorecard", "nonexistent_score")
    
    def test_score_from_name_with_complex_parameters(self):
        """Test Score.from_name with complex score parameters"""
        complex_parameters = {
            "name": "complex_score",
            "scorecard_name": "advanced_scorecard",
            "data": {"percentage": "80%", "model": "gpt-4"},
            "dependencies": [{"name": "dep1"}],
            "number_of_classes": 5
        }
        
        mock_scorecard_class = MagicMock()
        mock_score_class = MagicMock()
        
        mock_scorecard_class.score_registry.get_properties.return_value = complex_parameters
        mock_scorecard_class.score_registry.get.return_value = mock_score_class
        
        with patch('plexus.scores.Score.scorecard_registry') as mock_registry:
            mock_registry.get.return_value = mock_scorecard_class
            
            Score.from_name("advanced_scorecard", "complex_score")
            
            # Verify the score was instantiated with complex parameters
            mock_score_class.assert_called_once_with(**complex_parameters)


class TestScoreEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_score_with_numeric_string_values(self):
        """Test Score handling with numeric string parameters"""
        score = ConcreteScore(
            name="numeric_test",
            scorecard_name="test_scorecard",
            id="12345",  # String ID
            number_of_classes=3  # Integer value
        )
        
        assert score.parameters.id == "12345"
        assert score.parameters.number_of_classes == 3
    
    def test_score_parameters_with_none_values(self):
        """Test Score.Parameters with None values (should use defaults)"""
        params = Score.Parameters()  # All defaults
        
        assert params.scorecard_name is None
        assert params.name is None
        assert params.id is None
        assert params.key is None
        assert params.dependencies is None
        assert params.data is None
        assert params.number_of_classes is None
        assert params.label_score_name is None
        assert params.label_field is None
    
    def test_result_with_decimal_confidence(self):
        """Test Score.Result with Decimal confidence value"""
        params = Score.Parameters(name="decimal_test")
        
        result = Score.Result(
            parameters=params,
            value="Yes",
            confidence=float(Decimal('0.85')),  # Convert to float
            explanation="Test with decimal confidence"
        )
        
        assert result.confidence == 0.85
        assert result.value == "Yes"
    
    def test_input_with_empty_string_text(self):
        """Test Score.Input with empty string text"""
        input_obj = Score.Input(
            text="",
            metadata={"note": "empty_text_test"}
        )
        
        assert input_obj.text == ""
        assert input_obj.metadata["note"] == "empty_text_test"
    
    def test_result_equality_with_invalid_type(self):
        """Test Score.Result equality with invalid comparison type"""
        params = Score.Parameters(name="test")
        result = Score.Result(parameters=params, value="Yes")
        
        # Should return NotImplemented for unsupported types
        # In Python, when == returns NotImplemented, it becomes False
        assert (result == 123) == False
        assert (result == []) == False
        assert (result == {}) == False


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])