"""
Tests for report parameter utility functions.

Tests parameter extraction, validation, and Jinja2 rendering.
"""

import pytest
from plexus.reports.parameter_utils import (
    extract_parameters_from_config,
    has_parameters,
    validate_parameter_value,
    validate_all_parameters,
    render_configuration_with_parameters,
    get_parameter_display_value,
    normalize_parameter_value
)


class TestParameterExtraction:
    """Test extracting parameters from configuration YAML."""
    
    def test_extract_parameters_with_frontmatter(self):
        """Test extracting parameters from YAML frontmatter."""
        config = """parameters:
  - name: scorecard_id
    type: scorecard_select
    required: true
  - name: time_range
    type: number
    default: 30

---

# Report Content
{{ scorecard_id }}
"""
        params, content = extract_parameters_from_config(config)
        
        assert len(params) == 2
        assert params[0]['name'] == 'scorecard_id'
        assert params[0]['type'] == 'scorecard_select'
        assert params[1]['name'] == 'time_range'
        assert params[1]['default'] == 30
        assert '# Report Content' in content
    
    def test_extract_no_parameters(self):
        """Test extracting from config without parameters."""
        config = "# Simple Report\n\nNo parameters here."
        params, content = extract_parameters_from_config(config)
        
        assert len(params) == 0
        assert content == config
    
    def test_has_parameters_true(self):
        """Test has_parameters returns True when parameters exist."""
        config = "parameters:\n  - name: test\n---\nContent"
        assert has_parameters(config) is True
    
    def test_has_parameters_false(self):
        """Test has_parameters returns False when no parameters."""
        config = "# Report\nNo parameters"
        assert has_parameters(config) is False


class TestParameterValidation:
    """Test parameter value validation."""
    
    def test_validate_required_parameter_provided(self):
        """Test validation passes for required parameter with value."""
        param_def = {'name': 'test', 'type': 'text', 'required': True}
        is_valid, error = validate_parameter_value(param_def, 'some value')
        
        assert is_valid is True
        assert error is None
    
    def test_validate_required_parameter_missing(self):
        """Test validation fails for required parameter without value."""
        param_def = {'name': 'test', 'type': 'text', 'required': True}
        is_valid, error = validate_parameter_value(param_def, None)
        
        assert is_valid is False
        assert 'required' in error.lower()
    
    def test_validate_optional_parameter_missing(self):
        """Test validation passes for optional parameter without value."""
        param_def = {'name': 'test', 'type': 'text', 'required': False}
        is_valid, error = validate_parameter_value(param_def, None)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_number_in_range(self):
        """Test number validation with min/max constraints."""
        param_def = {'name': 'days', 'type': 'number', 'min': 1, 'max': 365}
        
        is_valid, _ = validate_parameter_value(param_def, 30)
        assert is_valid is True
        
        is_valid, _ = validate_parameter_value(param_def, 1)
        assert is_valid is True
        
        is_valid, _ = validate_parameter_value(param_def, 365)
        assert is_valid is True
    
    def test_validate_number_out_of_range(self):
        """Test number validation fails outside constraints."""
        param_def = {'name': 'days', 'type': 'number', 'min': 1, 'max': 365}
        
        is_valid, error = validate_parameter_value(param_def, 0)
        assert is_valid is False
        assert '>=' in error
        
        is_valid, error = validate_parameter_value(param_def, 400)
        assert is_valid is False
        assert '<=' in error
    
    def test_validate_boolean_valid(self):
        """Test boolean validation with various formats."""
        param_def = {'name': 'flag', 'type': 'boolean'}
        
        assert validate_parameter_value(param_def, True)[0] is True
        assert validate_parameter_value(param_def, False)[0] is True
        assert validate_parameter_value(param_def, 'true')[0] is True
        assert validate_parameter_value(param_def, 'yes')[0] is True
        assert validate_parameter_value(param_def, 'false')[0] is True
    
    def test_validate_boolean_invalid(self):
        """Test boolean validation fails for invalid values."""
        param_def = {'name': 'flag', 'type': 'boolean'}
        is_valid, error = validate_parameter_value(param_def, 'maybe')
        
        assert is_valid is False
        assert 'boolean' in error.lower()
    
    def test_validate_select_valid_option(self):
        """Test select validation with valid option."""
        param_def = {
            'name': 'choice',
            'type': 'select',
            'options': [
                {'value': 'a', 'label': 'Option A'},
                {'value': 'b', 'label': 'Option B'}
            ]
        }
        
        is_valid, _ = validate_parameter_value(param_def, 'a')
        assert is_valid is True
    
    def test_validate_select_invalid_option(self):
        """Test select validation fails for invalid option."""
        param_def = {
            'name': 'choice',
            'type': 'select',
            'options': [{'value': 'a'}, {'value': 'b'}]
        }
        
        is_valid, error = validate_parameter_value(param_def, 'c')
        assert is_valid is False
        assert 'must be one of' in error.lower()
    
    def test_validate_all_parameters_success(self):
        """Test validating multiple parameters successfully."""
        param_defs = [
            {'name': 'text_param', 'type': 'text', 'required': True},
            {'name': 'num_param', 'type': 'number', 'min': 0, 'max': 100}
        ]
        values = {
            'text_param': 'Hello',
            'num_param': 50
        }
        
        is_valid, errors = validate_all_parameters(param_defs, values)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_all_parameters_failure(self):
        """Test validating multiple parameters with failures."""
        param_defs = [
            {'name': 'required_param', 'type': 'text', 'required': True},
            {'name': 'num_param', 'type': 'number', 'min': 10}
        ]
        values = {
            'required_param': '',  # Missing
            'num_param': 5  # Too small
        }
        
        is_valid, errors = validate_all_parameters(param_defs, values)
        
        assert is_valid is False
        assert len(errors) == 2


class TestJinja2Rendering:
    """Test Jinja2 template rendering with parameters."""
    
    def test_render_simple_variables(self):
        """Test rendering simple variable interpolation."""
        config = "parameters:\n  - name: name\n---\nHello {{ name }}!"
        params = {'name': 'World'}
        
        result = render_configuration_with_parameters(config, params)
        
        assert result == 'Hello World!'
    
    def test_render_conditional(self):
        """Test rendering conditional blocks."""
        config = """parameters:
  - name: show_details
---
{% if show_details %}
Details shown
{% else %}
Details hidden
{% endif %}"""
        
        result = render_configuration_with_parameters(config, {'show_details': True})
        assert 'Details shown' in result
        assert 'Details hidden' not in result
    
    def test_render_missing_parameter_strict(self):
        """Test rendering fails with missing parameter in strict mode."""
        config = "---\n{{ missing_param }}"
        
        with pytest.raises(Exception):
            render_configuration_with_parameters(config, {}, strict=True)
    
    def test_render_with_number(self):
        """Test rendering with number parameter."""
        config = "parameters:\n  - name: days\n---\nDays: {{ days }}"
        result = render_configuration_with_parameters(config, {'days': 30})
        
        assert 'Days: 30' in result
    
    def test_render_with_boolean(self):
        """Test rendering with boolean parameter."""
        config = "parameters:\n  - name: enabled\n---\nEnabled: {{ enabled }}"
        result = render_configuration_with_parameters(config, {'enabled': True})
        
        assert 'Enabled: True' in result


class TestParameterHelpers:
    """Test helper utility functions."""
    
    def test_get_display_value_text(self):
        """Test display value for text parameter."""
        param_def = {'name': 'test', 'type': 'text'}
        assert get_parameter_display_value(param_def, 'hello') == 'hello'
    
    def test_get_display_value_none(self):
        """Test display value for None."""
        param_def = {'name': 'test', 'type': 'text'}
        assert get_parameter_display_value(param_def, None) == '<not set>'
    
    def test_get_display_value_boolean(self):
        """Test display value for boolean."""
        param_def = {'name': 'test', 'type': 'boolean'}
        assert get_parameter_display_value(param_def, True) == 'Yes'
        assert get_parameter_display_value(param_def, False) == 'No'
    
    def test_get_display_value_select_with_label(self):
        """Test display value for select shows label."""
        param_def = {
            'name': 'choice',
            'type': 'select',
            'options': [{'value': 'a', 'label': 'Option A'}]
        }
        assert get_parameter_display_value(param_def, 'a') == 'Option A'
    
    def test_normalize_number(self):
        """Test normalizing number parameter."""
        param_def = {'name': 'num', 'type': 'number'}
        
        assert normalize_parameter_value(param_def, '42') == 42
        assert normalize_parameter_value(param_def, '3.14') == 3.14
    
    def test_normalize_boolean(self):
        """Test normalizing boolean parameter."""
        param_def = {'name': 'flag', 'type': 'boolean'}
        
        assert normalize_parameter_value(param_def, 'true') is True
        assert normalize_parameter_value(param_def, 'yes') is True
        assert normalize_parameter_value(param_def, 'false') is False
        assert normalize_parameter_value(param_def, 'no') is False
    
    def test_normalize_text(self):
        """Test normalizing text parameter."""
        param_def = {'name': 'text', 'type': 'text'}
        
        assert normalize_parameter_value(param_def, 'hello') == 'hello'
        assert normalize_parameter_value(param_def, 123) == '123'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

