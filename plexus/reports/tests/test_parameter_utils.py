"""
Tests for report parameter utility functions.

Tests parameter extraction, validation, and Jinja2 rendering.
"""

import pytest
from unittest.mock import Mock, MagicMock
from plexus.reports.parameter_utils import (
    extract_parameters_from_config,
    has_parameters,
    validate_parameter_value,
    validate_all_parameters,
    render_configuration_with_parameters,
    get_parameter_display_value,
    normalize_parameter_value,
    enrich_parameters_with_names
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


class TestParameterEnrichment:
    """Test parameter enrichment with name resolution."""
    
    def test_enrich_scorecard_select_by_id(self):
        """Test enriching scorecard_select parameter resolves name by ID."""
        # Mock scorecard
        mock_scorecard = Mock()
        mock_scorecard.name = 'Test Scorecard'
        
        # Mock client
        mock_client = Mock()
        
        # Mock Scorecard.get_by_id to return our mock
        from plexus.dashboard.api.models import scorecard
        original_get_by_id = scorecard.Scorecard.get_by_id
        scorecard.Scorecard.get_by_id = Mock(return_value=mock_scorecard)
        
        try:
            param_defs = [
                {'name': 'scorecard', 'type': 'scorecard_select'},
                {'name': 'days', 'type': 'number'}
            ]
            parameters = {
                'scorecard': 'scorecard-123',
                'days': 30
            }
            
            result = enrich_parameters_with_names(param_defs, parameters, mock_client)
            
            assert result['scorecard'] == 'scorecard-123'
            assert result['scorecard_name'] == 'Test Scorecard'
            assert result['days'] == 30
            assert 'days_name' not in result  # Non-select parameters shouldn't get _name
        finally:
            scorecard.Scorecard.get_by_id = original_get_by_id
    
    def test_enrich_scorecard_select_fallback_to_identifier(self):
        """Test enrichment falls back to identifier when resolution fails."""
        # Mock client that raises exceptions
        mock_client = Mock()
        
        # Mock all Scorecard lookup methods to raise exceptions
        from plexus.dashboard.api.models import scorecard
        original_methods = {
            'get_by_id': scorecard.Scorecard.get_by_id,
            'get_by_key': scorecard.Scorecard.get_by_key,
            'get_by_external_id': scorecard.Scorecard.get_by_external_id,
            'get_by_name': scorecard.Scorecard.get_by_name
        }
        
        scorecard.Scorecard.get_by_id = Mock(side_effect=Exception("Not found"))
        scorecard.Scorecard.get_by_key = Mock(side_effect=Exception("Not found"))
        scorecard.Scorecard.get_by_external_id = Mock(side_effect=Exception("Not found"))
        scorecard.Scorecard.get_by_name = Mock(side_effect=Exception("Not found"))
        
        try:
            param_defs = [
                {'name': 'scorecard', 'type': 'scorecard_select'}
            ]
            parameters = {
                'scorecard': 'unknown-scorecard'
            }
            
            result = enrich_parameters_with_names(param_defs, parameters, mock_client)
            
            # Should fall back to using the identifier as the name
            assert result['scorecard'] == 'unknown-scorecard'
            assert result['scorecard_name'] == 'unknown-scorecard'
        finally:
            # Restore original methods
            for method_name, original_method in original_methods.items():
                setattr(scorecard.Scorecard, method_name, original_method)
    
    def test_enrich_score_select_with_scorecard_context(self):
        """Test enriching score_select parameter with scorecard context."""
        # Mock score
        mock_score = Mock()
        mock_score.name = 'Test Score'
        
        # Mock client
        mock_client = Mock()
        
        # Mock Score.get_by_id to return our mock
        from plexus.dashboard.api.models import score
        original_get_by_id = score.Score.get_by_id
        score.Score.get_by_id = Mock(return_value=mock_score)
        
        try:
            param_defs = [
                {'name': 'scorecard', 'type': 'scorecard_select'},
                {'name': 'score', 'type': 'score_select', 'depends_on': 'scorecard'}
            ]
            parameters = {
                'scorecard': 'scorecard-123',
                'score': 'score-456'
            }
            
            result = enrich_parameters_with_names(param_defs, parameters, mock_client)
            
            assert result['score'] == 'score-456'
            assert result['score_name'] == 'Test Score'
        finally:
            score.Score.get_by_id = original_get_by_id
    
    def test_enrich_score_select_without_scorecard_context(self):
        """Test enriching score_select without scorecard context falls back."""
        mock_client = Mock()
        
        param_defs = [
            {'name': 'score', 'type': 'score_select'}  # No depends_on
        ]
        parameters = {
            'score': 'score-456'
        }
        
        result = enrich_parameters_with_names(param_defs, parameters, mock_client)
        
        # Should fall back to identifier when no scorecard context
        assert result['score'] == 'score-456'
        assert result['score_name'] == 'score-456'
    
    def test_enrich_multiple_select_parameters(self):
        """Test enriching multiple select parameters."""
        # Mock scorecard
        mock_scorecard = Mock()
        mock_scorecard.name = 'My Scorecard'
        
        # Mock score
        mock_score = Mock()
        mock_score.name = 'My Score'
        
        mock_client = Mock()
        
        from plexus.dashboard.api.models import scorecard, score
        original_scorecard_get = scorecard.Scorecard.get_by_id
        original_score_get = score.Score.get_by_id
        
        scorecard.Scorecard.get_by_id = Mock(return_value=mock_scorecard)
        score.Score.get_by_id = Mock(return_value=mock_score)
        
        try:
            param_defs = [
                {'name': 'scorecard', 'type': 'scorecard_select'},
                {'name': 'score', 'type': 'score_select', 'depends_on': 'scorecard'},
                {'name': 'days', 'type': 'number'}
            ]
            parameters = {
                'scorecard': 'sc-123',
                'score': 'score-456',
                'days': 7
            }
            
            result = enrich_parameters_with_names(param_defs, parameters, mock_client)
            
            assert result['scorecard'] == 'sc-123'
            assert result['scorecard_name'] == 'My Scorecard'
            assert result['score'] == 'score-456'
            assert result['score_name'] == 'My Score'
            assert result['days'] == 7
            assert 'days_name' not in result
        finally:
            scorecard.Scorecard.get_by_id = original_scorecard_get
            score.Score.get_by_id = original_score_get
    
    def test_enrich_preserves_original_parameters(self):
        """Test enrichment doesn't modify original parameters dict."""
        mock_client = Mock()
        
        param_defs = [
            {'name': 'test', 'type': 'text'}
        ]
        original_params = {'test': 'value'}
        
        result = enrich_parameters_with_names(param_defs, original_params, mock_client)
        
        # Original should be unchanged
        assert original_params == {'test': 'value'}
        # Result should be a copy
        assert result == {'test': 'value'}
        assert result is not original_params
    
    def test_enrich_skips_missing_parameters(self):
        """Test enrichment skips parameters not in values dict."""
        mock_client = Mock()
        
        param_defs = [
            {'name': 'scorecard', 'type': 'scorecard_select'},
            {'name': 'optional', 'type': 'scorecard_select'}
        ]
        parameters = {
            'scorecard': 'sc-123'
            # 'optional' is not provided
        }
        
        # Should not raise an error
        result = enrich_parameters_with_names(param_defs, parameters, mock_client)
        
        assert 'scorecard' in result
        assert 'optional' not in result
        assert 'optional_name' not in result
    
    def test_enrich_handles_none_values(self):
        """Test enrichment handles None parameter values gracefully."""
        mock_client = Mock()
        
        param_defs = [
            {'name': 'scorecard', 'type': 'scorecard_select'}
        ]
        parameters = {
            'scorecard': None
        }
        
        result = enrich_parameters_with_names(param_defs, parameters, mock_client)
        
        # Should not add _name for None values
        assert result['scorecard'] is None
        assert 'scorecard_name' not in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

