"""
Tests for ProcedureParameterParser
"""

import pytest
from plexus.cli.procedure.parameter_parser import (
    ProcedureParameterParser,
    ParameterDefinition
)


class TestParameterDefinitionParsing:
    """Tests for parsing parameter definitions from YAML."""
    
    def test_parse_single_parameter(self):
        """Test parsing a single parameter definition."""
        yaml_code = """
configurable_parameters:
  - name: scorecard_id
    type: scorecard_select
    label: Scorecard
    required: true
"""
        params = ProcedureParameterParser.parse_parameter_definitions(yaml_code)
        
        assert len(params) == 1
        assert params[0].name == "scorecard_id"
        assert params[0].type == "scorecard_select"
        assert params[0].label == "Scorecard"
        assert params[0].required is True
    
    def test_parse_multiple_parameters(self):
        """Test parsing multiple parameter definitions."""
        yaml_code = """
configurable_parameters:
  - name: scorecard_id
    type: scorecard_select
    label: Scorecard
    required: true
  - name: score_id
    type: score_select
    label: Score
    required: true
  - name: score_version_id
    type: score_version_select
    label: Score Version
    required: false
"""
        params = ProcedureParameterParser.parse_parameter_definitions(yaml_code)
        
        assert len(params) == 3
        assert params[0].name == "scorecard_id"
        assert params[1].name == "score_id"
        assert params[2].name == "score_version_id"
        assert params[2].required is False
    
    def test_parse_parameter_with_default(self):
        """Test parsing parameter with default value."""
        yaml_code = """
configurable_parameters:
  - name: threshold
    type: number
    label: Threshold
    default: 0.5
"""
        params = ProcedureParameterParser.parse_parameter_definitions(yaml_code)
        
        assert len(params) == 1
        assert params[0].default == 0.5
    
    def test_parse_parameter_with_options(self):
        """Test parsing parameter with options."""
        yaml_code = """
configurable_parameters:
  - name: mode
    type: select
    label: Mode
    options:
      - fast
      - accurate
      - balanced
"""
        params = ProcedureParameterParser.parse_parameter_definitions(yaml_code)
        
        assert len(params) == 1
        assert params[0].options == ["fast", "accurate", "balanced"]
    
    def test_parse_empty_yaml(self):
        """Test parsing YAML with no parameters."""
        yaml_code = """
class: BeamSearch
prompts:
  worker_system_prompt: "Test prompt"
"""
        params = ProcedureParameterParser.parse_parameter_definitions(yaml_code)
        
        assert len(params) == 0
    
    def test_parse_invalid_yaml(self):
        """Test parsing invalid YAML."""
        yaml_code = "invalid: yaml: structure:"
        params = ProcedureParameterParser.parse_parameter_definitions(yaml_code)
        
        assert len(params) == 0


class TestParameterValueExtraction:
    """Tests for extracting parameter values from YAML."""
    
    def test_extract_single_value(self):
        """Test extracting a single parameter value."""
        yaml_code = """
configurable_parameters:
  - name: scorecard_id
    type: scorecard_select
    label: Scorecard
    required: true

scorecard_id: "abc-123-def-456"
"""
        values = ProcedureParameterParser.extract_parameter_values(yaml_code)
        
        assert "scorecard_id" in values
        assert values["scorecard_id"] == "abc-123-def-456"
    
    def test_extract_multiple_values(self):
        """Test extracting multiple parameter values."""
        yaml_code = """
configurable_parameters:
  - name: scorecard_id
    type: scorecard_select
    label: Scorecard
  - name: score_id
    type: score_select
    label: Score
  - name: days
    type: number
    label: Days

scorecard_id: "abc-123"
score_id: "def-456"
days: 7
"""
        values = ProcedureParameterParser.extract_parameter_values(yaml_code)
        
        assert values["scorecard_id"] == "abc-123"
        assert values["score_id"] == "def-456"
        assert values["days"] == 7
    
    def test_extract_nested_value(self):
        """Test extracting values from nested YAML structure."""
        yaml_code = """
configurable_parameters:
  - name: scorecard_id
    type: scorecard_select
    label: Scorecard

settings:
  scorecard_id: "nested-abc-123"
"""
        values = ProcedureParameterParser.extract_parameter_values(yaml_code)
        
        assert values["scorecard_id"] == "nested-abc-123"
    
    def test_extract_from_list(self):
        """Test extracting values from lists in YAML."""
        yaml_code = """
configurable_parameters:
  - name: model_name
    type: string
    label: Model

items:
  - model_name: "gpt-4"
    other: "data"
"""
        values = ProcedureParameterParser.extract_parameter_values(yaml_code)
        
        assert values["model_name"] == "gpt-4"
    
    def test_extract_no_values(self):
        """Test extraction when no values are present."""
        yaml_code = """
configurable_parameters:
  - name: scorecard_id
    type: scorecard_select
    label: Scorecard

class: BeamSearch
"""
        values = ProcedureParameterParser.extract_parameter_values(yaml_code)
        
        assert "scorecard_id" not in values


class TestRequiredParametersValidation:
    """Tests for required parameter validation."""
    
    def test_get_required_parameters(self):
        """Test getting only required parameters."""
        yaml_code = """
configurable_parameters:
  - name: scorecard_id
    type: scorecard_select
    required: true
  - name: score_id
    type: score_select
    required: true
  - name: optional_param
    type: string
    required: false
"""
        required = ProcedureParameterParser.get_required_parameters(yaml_code)
        
        assert len(required) == 2
        assert "scorecard_id" in required
        assert "score_id" in required
        assert "optional_param" not in required
    
    def test_validate_all_required_present(self):
        """Test validation when all required parameters are present."""
        yaml_code = """
configurable_parameters:
  - name: scorecard_id
    type: scorecard_select
    required: true
  - name: score_id
    type: score_select
    required: true

scorecard_id: "abc-123"
score_id: "def-456"
"""
        is_valid, missing = ProcedureParameterParser.validate_parameter_values(yaml_code)
        
        assert is_valid is True
        assert len(missing) == 0
    
    def test_validate_missing_required(self):
        """Test validation when required parameters are missing."""
        yaml_code = """
configurable_parameters:
  - name: scorecard_id
    type: scorecard_select
    required: true
  - name: score_id
    type: score_select
    required: true

scorecard_id: "abc-123"
"""
        is_valid, missing = ProcedureParameterParser.validate_parameter_values(yaml_code)
        
        assert is_valid is False
        assert "score_id" in missing
        assert "scorecard_id" not in missing
    
    def test_validate_empty_string_value(self):
        """Test that empty string values are treated as missing."""
        yaml_code = """
configurable_parameters:
  - name: scorecard_id
    type: scorecard_select
    required: true

scorecard_id: ""
"""
        is_valid, missing = ProcedureParameterParser.validate_parameter_values(yaml_code)
        
        assert is_valid is False
        assert "scorecard_id" in missing
    
    def test_validate_with_provided_values(self):
        """Test validation with externally provided values."""
        yaml_code = """
configurable_parameters:
  - name: scorecard_id
    type: scorecard_select
    required: true
  - name: score_id
    type: score_select
    required: true
"""
        provided_values = {
            "scorecard_id": "abc-123",
            "score_id": "def-456"
        }
        
        is_valid, missing = ProcedureParameterParser.validate_parameter_values(
            yaml_code, provided_values
        )
        
        assert is_valid is True
        assert len(missing) == 0


class TestComplexScenarios:
    """Tests for complex real-world scenarios."""
    
    def test_full_procedure_yaml(self):
        """Test with a complete procedure YAML structure."""
        yaml_code = """
class: BeamSearch
max_total_rounds: 500

configurable_parameters:
  - name: scorecard_id
    type: scorecard_select
    label: Scorecard
    required: true
  - name: score_id
    type: score_select
    label: Score
    required: true
  - name: score_version_id
    type: score_version_select
    label: Score Version
    required: false
  - name: days_to_analyze
    type: number
    label: Days to Analyze
    default: 7

prompts:
  worker_system_prompt: "You are an assistant"
  worker_user_prompt: "Analyze data"

# Injected values
scorecard_id: "scorecard-abc-123"
score_id: "score-def-456"
score_version_id: "version-ghi-789"
days_to_analyze: 14
"""
        # Test parameter parsing
        params = ProcedureParameterParser.parse_parameter_definitions(yaml_code)
        assert len(params) == 4
        
        # Test value extraction
        values = ProcedureParameterParser.extract_parameter_values(yaml_code)
        assert values["scorecard_id"] == "scorecard-abc-123"
        assert values["score_id"] == "score-def-456"
        assert values["score_version_id"] == "version-ghi-789"
        assert values["days_to_analyze"] == 14
        
        # Test validation
        is_valid, missing = ProcedureParameterParser.validate_parameter_values(yaml_code)
        assert is_valid is True
    
    def test_parameter_types(self):
        """Test various parameter types."""
        yaml_code = """
configurable_parameters:
  - name: string_param
    type: string
  - name: number_param
    type: number
  - name: boolean_param
    type: boolean
  - name: select_param
    type: select
    options: [a, b, c]

string_param: "test"
number_param: 42
boolean_param: true
select_param: "b"
"""
        values = ProcedureParameterParser.extract_parameter_values(yaml_code)
        
        assert values["string_param"] == "test"
        assert values["number_param"] == 42
        assert values["boolean_param"] is True
        assert values["select_param"] == "b"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
