"""
Comprehensive tests for Score validation functionality.

Tests cover all validation scenarios including:
- valid_classes validation
- pattern validation  
- mixed validation (valid_classes + patterns)
- length validation
- NQ- pattern exclusion scenarios
- predict_with_validation method integration
"""

import pytest
from plexus.scores.Score import Score


class MockScore(Score):
    """Mock implementation of Score for testing validation."""
    
    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.mock_result = None
    
    def set_mock_result(self, result: Score.Result):
        """Set the result this mock should return."""
        self.mock_result = result
    
    def predict(self, context, model_input: Score.Input) -> Score.Result:
        """Return the pre-configured mock result."""
        if self.mock_result is None:
            return Score.Result(
                parameters=self.parameters,
                value="Yes",
                explanation="Mock result"
            )
        return self.mock_result


class TestScoreValidation:
    """Test cases for Score validation functionality."""
    
    def test_no_validation_config_passes(self):
        """Test that results pass validation when no validation config is provided."""
        score = MockScore()
        result = Score.Result(
            parameters=score.parameters,
            value="Any Value",
            explanation="Any explanation"
        )
        
        # Should not raise any exception
        result.validate(None)
        result.validate(Score.ValidationConfig())
    
    def test_valid_classes_validation_success(self):
        """Test successful validation with valid_classes."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(valid_classes=["Yes", "No", "Maybe"])
        )
        
        result = Score.Result(
            parameters=Score.Parameters(),
            value="Yes",
            explanation="Test explanation"
        )
        
        # Should not raise exception
        result.validate(validation_config)
    
    def test_valid_classes_validation_failure(self):
        """Test validation failure with invalid class."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(valid_classes=["Yes", "No"])
        )
        
        result = Score.Result(
            parameters=Score.Parameters(),
            value="Maybe",
            explanation="Test explanation"
        )
        
        with pytest.raises(Score.ValidationError) as exc_info:
            result.validate(validation_config)
        
        assert exc_info.value.field_name == "value"
        assert exc_info.value.value == "Maybe"
        assert "'Maybe' is not in valid_classes ['Yes', 'No']" in str(exc_info.value)
    
    def test_pattern_validation_success(self):
        """Test successful validation with regex patterns."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(patterns=["^(Yes|No)$", "^Maybe.*"])
        )
        
        # Test first pattern match
        result1 = Score.Result(
            parameters=Score.Parameters(),
            value="Yes",
            explanation="Test"
        )
        result1.validate(validation_config)
        
        # Test second pattern match
        result2 = Score.Result(
            parameters=Score.Parameters(),
            value="Maybe sometimes",
            explanation="Test"
        )
        result2.validate(validation_config)
    
    def test_pattern_validation_failure(self):
        """Test validation failure with patterns that don't match."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(patterns=["^(Yes|No)$"])
        )
        
        result = Score.Result(
            parameters=Score.Parameters(),
            value="Maybe",
            explanation="Test"
        )
        
        with pytest.raises(Score.ValidationError) as exc_info:
            result.validate(validation_config)
        
        assert "'Maybe' does not match any required patterns" in str(exc_info.value)
    
    def test_nq_pattern_exclusion_success(self):
        """Test NQ- pattern that excludes 'NQ - Other'."""
        # Pattern matches "NQ - " followed by anything except "Other"
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(patterns=["^NQ - (?!Other$).*"])
        )
        
        # These should pass
        valid_values = [
            "NQ - Pricing",
            "NQ - Technical Support", 
            "NQ - Billing",
            "NQ - General Info"
        ]
        
        for value in valid_values:
            result = Score.Result(
                parameters=Score.Parameters(),
                value=value,
                explanation="Test"
            )
            result.validate(validation_config)  # Should not raise
    
    def test_nq_pattern_exclusion_failure(self):
        """Test NQ- pattern correctly excludes 'NQ - Other'."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(patterns=["^NQ - (?!Other$).*"])
        )
        
        result = Score.Result(
            parameters=Score.Parameters(),
            value="NQ - Other",
            explanation="Test"
        )
        
        with pytest.raises(Score.ValidationError) as exc_info:
            result.validate(validation_config)
        
        assert "'NQ - Other' does not match any required patterns" in str(exc_info.value)
    
    def test_mixed_validation_success(self):
        """Test successful validation with both valid_classes and patterns."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(
                valid_classes=["Yes", "No", "NQ - Pricing"],
                patterns=["^(Yes|No)$", "^NQ - (?!Other$).*"]
            )
        )
        
        # Value must be in valid_classes AND match a pattern
        result = Score.Result(
            parameters=Score.Parameters(),
            value="NQ - Pricing",  # In valid_classes AND matches NQ pattern
            explanation="Test"
        )
        
        result.validate(validation_config)  # Should not raise
    
    def test_mixed_validation_failure_valid_classes(self):
        """Test mixed validation fails when valid_classes check fails."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(
                valid_classes=["Yes", "No"],
                patterns=["^NQ - (?!Other$).*"]
            )
        )
        
        result = Score.Result(
            parameters=Score.Parameters(),
            value="NQ - Pricing",  # Matches pattern but NOT in valid_classes
            explanation="Test"
        )
        
        with pytest.raises(Score.ValidationError) as exc_info:
            result.validate(validation_config)
        
        assert "'NQ - Pricing' is not in valid_classes ['Yes', 'No']" in str(exc_info.value)
    
    def test_mixed_validation_failure_patterns(self):
        """Test mixed validation fails when pattern check fails."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(
                valid_classes=["Yes", "No", "Maybe"],
                patterns=["^(Yes|No)$"]  # "Maybe" won't match this pattern
            )
        )
        
        result = Score.Result(
            parameters=Score.Parameters(),
            value="Maybe",  # In valid_classes but doesn't match pattern
            explanation="Test"
        )
        
        with pytest.raises(Score.ValidationError) as exc_info:
            result.validate(validation_config)
        
        assert "'Maybe' does not match any required patterns" in str(exc_info.value)
    
    def test_length_validation_success(self):
        """Test successful length validation."""
        validation_config = Score.ValidationConfig(
            explanation=Score.FieldValidation(
                minimum_length=5,
                maximum_length=50
            )
        )
        
        result = Score.Result(
            parameters=Score.Parameters(),
            value="Yes",
            explanation="This explanation is just right"
        )
        
        result.validate(validation_config)  # Should not raise
    
    def test_minimum_length_validation_failure(self):
        """Test validation failure when text is too short."""
        validation_config = Score.ValidationConfig(
            explanation=Score.FieldValidation(minimum_length=10)
        )
        
        result = Score.Result(
            parameters=Score.Parameters(),
            value="Yes",
            explanation="Short"  # Only 5 characters
        )
        
        with pytest.raises(Score.ValidationError) as exc_info:
            result.validate(validation_config)
        
        assert "length 5 is below minimum_length 10" in str(exc_info.value)
    
    def test_maximum_length_validation_failure(self):
        """Test validation failure when text is too long."""
        validation_config = Score.ValidationConfig(
            explanation=Score.FieldValidation(maximum_length=10)
        )
        
        result = Score.Result(
            parameters=Score.Parameters(),
            value="Yes",
            explanation="This explanation is way too long for the limit"
        )
        
        with pytest.raises(Score.ValidationError) as exc_info:
            result.validate(validation_config)
        
        assert "exceeds maximum_length 10" in str(exc_info.value)
    
    def test_explanation_none_skips_validation(self):
        """Test that None explanation skips validation."""
        validation_config = Score.ValidationConfig(
            explanation=Score.FieldValidation(minimum_length=10)
        )
        
        result = Score.Result(
            parameters=Score.Parameters(),
            value="Yes",
            explanation=None
        )
        
        # Should not raise exception even though explanation is None
        result.validate(validation_config)
    
    def test_invalid_regex_pattern_error(self):
        """Test that invalid regex patterns raise appropriate errors."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(patterns=["[invalid regex"])
        )
        
        result = Score.Result(
            parameters=Score.Parameters(),
            value="Test",
            explanation="Test"
        )
        
        with pytest.raises(Score.ValidationError) as exc_info:
            result.validate(validation_config)
        
        assert "Invalid regex pattern" in str(exc_info.value)
    
    def test_predict_with_validation_success(self):
        """Test predict method with successful validation."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(valid_classes=["Yes", "No"])
        )
        
        score = MockScore(validation=validation_config)
        mock_result = Score.Result(
            parameters=score.parameters,
            value="Yes",
            explanation="Valid result"
        )
        score.set_mock_result(mock_result)
        
        input_data = Score.Input(text="test input")
        result = score.predict(None, input_data)
        
        assert result.value == "Yes"
    
    def test_predict_with_validation_failure(self):
        """Test predict method with validation failure."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(valid_classes=["Yes", "No"])
        )
        
        score = MockScore(validation=validation_config)
        mock_result = Score.Result(
            parameters=score.parameters,
            value="Maybe",  # Invalid according to validation config
            explanation="Invalid result"
        )
        score.set_mock_result(mock_result)
        
        input_data = Score.Input(text="test input")
        
        with pytest.raises(Score.ValidationError) as exc_info:
            score.predict(None, input_data)
        
        assert "'Maybe' is not in valid_classes ['Yes', 'No']" in str(exc_info.value)
    
    def test_predict_with_validation_list_results(self):
        """Test predict method with list of results."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(valid_classes=["Yes", "No"])
        )
        
        # Create a custom MockScore class for this test
        class ListResultsMockScore(MockScore):
            def predict(self, context, model_input):
                return [
                    Score.Result(parameters=self.parameters, value="Yes", explanation="First"),
                    Score.Result(parameters=self.parameters, value="No", explanation="Second")
                ]
        
        score = ListResultsMockScore(validation=validation_config)
        
        input_data = Score.Input(text="test input")
        results = score.predict(None, input_data)
        
        assert len(results) == 2
        assert results[0].value == "Yes"
        assert results[1].value == "No"
    
    def test_predict_with_validation_list_results_failure(self):
        """Test predict method with invalid result in list."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(valid_classes=["Yes", "No"])
        )
        
        # Create a custom MockScore class for this test
        class ListResultsMockScore(MockScore):
            def predict(self, context, model_input):
                return [
                    Score.Result(parameters=self.parameters, value="Yes", explanation="Valid"),
                    Score.Result(parameters=self.parameters, value="Maybe", explanation="Invalid")
                ]
        
        score = ListResultsMockScore(validation=validation_config)
        
        input_data = Score.Input(text="test input")
        
        with pytest.raises(Score.ValidationError) as exc_info:
            score.predict(None, input_data)
        
        assert "'Maybe' is not in valid_classes ['Yes', 'No']" in str(exc_info.value)
    
    def test_predict_with_validation_no_config(self):
        """Test predict method works normally without validation config."""
        score = MockScore()  # No validation config
        mock_result = Score.Result(
            parameters=score.parameters,
            value="Any Value",
            explanation="Any explanation"
        )
        score.set_mock_result(mock_result)
        
        input_data = Score.Input(text="test input")
        result = score.predict(None, input_data)
        
        assert result.value == "Any Value"
    
    def test_comprehensive_validation_scenario(self):
        """Test a comprehensive validation scenario with multiple constraints."""
        validation_config = Score.ValidationConfig(
            value=Score.FieldValidation(
                valid_classes=["NQ - Pricing", "NQ - Technical", "NQ - Billing", "Yes", "No"],
                patterns=["^(Yes|No)$", "^NQ - (?!Other$).*"]
            ),
            explanation=Score.FieldValidation(
                minimum_length=15,
                maximum_length=200,
                patterns=[".*found.*", ".*evidence.*", ".*clear.*"]
            )
        )
        
        # This should pass all validations
        result = Score.Result(
            parameters=Score.Parameters(),
            value="NQ - Pricing",  # In valid_classes AND matches NQ pattern
            explanation="Clear evidence found in the transcript"  # Right length AND contains required words
        )
        
        result.validate(validation_config)  # Should not raise
        
        # This should fail explanation pattern validation
        result_bad_explanation = Score.Result(
            parameters=Score.Parameters(),
            value="NQ - Pricing",
            explanation="This explanation does not contain the required terms"
        )
        
        with pytest.raises(Score.ValidationError) as exc_info:
            result_bad_explanation.validate(validation_config)
        
        assert "does not match any required patterns" in str(exc_info.value)
        assert exc_info.value.field_name == "explanation"


if __name__ == "__main__":
    pytest.main([__file__])