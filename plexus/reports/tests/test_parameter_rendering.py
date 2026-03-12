"""
Tests for Jinja2 parameter rendering in report configurations.

This module tests the interpolation of parameter values into report content
using Jinja2 templates. Parameters are passed directly by their name without
any namespacing.
"""

import pytest
from jinja2 import Template, Environment, StrictUndefined


def render_report_content(content: str, parameters: dict) -> str:
    """
    Render report content with parameter interpolation using Jinja2.
    
    Args:
        content: The report configuration content with Jinja2 templates
        parameters: Dictionary of parameter name -> value mappings
        
    Returns:
        The rendered content with parameters interpolated
        
    Raises:
        jinja2.UndefinedError: If a template references an undefined parameter
    """
    # Use StrictUndefined to catch missing parameters
    env = Environment(undefined=StrictUndefined)
    template = env.from_string(content)
    return template.render(**parameters)


class TestParameterRendering:
    """Test suite for Jinja2 parameter interpolation in reports."""
    
    def test_simple_variable_interpolation(self):
        """Test basic {{ variable }} interpolation."""
        content = """# {{ scorecard_name }} Analysis

Analyzing scorecard: {{ scorecard_name }}
Scorecard ID: {{ scorecard_id }}
Time range: {{ time_range }} days
"""
        
        parameters = {
            'scorecard_id': 'abc-123',
            'scorecard_name': 'Call Criteria',
            'time_range': 30
        }
        
        result = render_report_content(content, parameters)
        
        assert '# Call Criteria Analysis' in result
        assert 'Analyzing scorecard: Call Criteria' in result
        assert 'Scorecard ID: abc-123' in result
        assert 'Time range: 30 days' in result
    
    def test_conditional_blocks(self):
        """Test {% if %} conditional rendering."""
        content = """{% if include_scores %}
## Individual Score Breakdown
Detailed score analysis included.
{% else %}
Individual score analysis omitted.
{% endif %}
"""
        
        # Test with include_scores = True
        result_with_scores = render_report_content(content, {'include_scores': True})
        assert '## Individual Score Breakdown' in result_with_scores
        assert 'Detailed score analysis included' in result_with_scores
        assert 'omitted' not in result_with_scores
        
        # Test with include_scores = False
        result_without_scores = render_report_content(content, {'include_scores': False})
        assert 'Individual score analysis omitted' in result_without_scores
        assert '## Individual Score Breakdown' not in result_without_scores
        assert 'Detailed score analysis included' not in result_without_scores
    
    def test_parameters_in_code_blocks(self):
        """Test parameter interpolation inside code blocks (for report blocks)."""
        content = """```block name="Performance Metrics"
class: ScorecardMetricsBlock
scorecard_id: {{ scorecard_id }}
days: {{ time_range }}
include_details: {{ include_scores }}
```"""
        
        parameters = {
            'scorecard_id': 'scorecard-456',
            'time_range': 60,
            'include_scores': True
        }
        
        result = render_report_content(content, parameters)
        
        assert 'scorecard_id: scorecard-456' in result
        assert 'days: 60' in result
        assert 'include_details: True' in result
    
    def test_multiple_data_types(self):
        """Test interpolation of different parameter types (string, int, bool)."""
        content = """Name: {{ name }}
Count: {{ count }}
Enabled: {{ enabled }}
Score: {{ score }}
"""
        
        parameters = {
            'name': 'Test Report',
            'count': 42,
            'enabled': False,
            'score': 95.5
        }
        
        result = render_report_content(content, parameters)
        
        assert 'Name: Test Report' in result
        assert 'Count: 42' in result
        assert 'Enabled: False' in result
        assert 'Score: 95.5' in result
    
    def test_jinja_filters(self):
        """Test using Jinja2 filters on parameters."""
        content = """Scorecard: {{ scorecard_name | upper }}
Days (doubled): {{ time_range * 2 }}
Formatted: {{ value | round(2) }}
"""
        
        parameters = {
            'scorecard_name': 'call criteria',
            'time_range': 15,
            'value': 3.14159
        }
        
        result = render_report_content(content, parameters)
        
        assert 'Scorecard: CALL CRITERIA' in result
        assert 'Days (doubled): 30' in result
        assert 'Formatted: 3.14' in result
    
    def test_complex_template(self):
        """Test a realistic report template with multiple features."""
        content = """# {{ scorecard_name }} Performance Report

## Overview
This report analyzes the **{{ scorecard_name }}** scorecard (ID: `{{ scorecard_id }}`) 
over the last **{{ time_range }}** days.

{% if include_scores %}
## Score-by-Score Analysis

Individual scores will be analyzed below with detailed metrics.
{% endif %}

## Data Collection

```block name="Metrics Collection"
class: ScorecardMetricsBlock
scorecard_id: {{ scorecard_id }}
days: {{ time_range }}
{% if include_details %}detailed: true{% endif %}
```

## Summary

Report generated for {{ scorecard_name }} with {{ time_range }}-day analysis.
{% if include_scores %}Individual score breakdown included.{% else %}Summary only.{% endif %}
"""
        
        parameters = {
            'scorecard_id': 'test-scorecard-789',
            'scorecard_name': 'Customer Service Quality',
            'time_range': 45,
            'include_scores': True,
            'include_details': False
        }
        
        result = render_report_content(content, parameters)
        
        # Check title
        assert '# Customer Service Quality Performance Report' in result
        
        # Check overview
        assert 'analyzes the **Customer Service Quality** scorecard' in result
        assert '(ID: `test-scorecard-789`)' in result
        assert 'over the last **45** days' in result
        
        # Check conditional score analysis
        assert '## Score-by-Score Analysis' in result
        assert 'Individual scores will be analyzed below' in result
        
        # Check code block with parameters
        assert 'scorecard_id: test-scorecard-789' in result
        assert 'days: 45' in result
        # include_details is False, so this line should not appear
        assert 'detailed: true' not in result
        
        # Check summary
        assert 'Report generated for Customer Service Quality with 45-day analysis.' in result
        assert 'Individual score breakdown included.' in result
    
    def test_missing_parameter_raises_error(self):
        """Test that referencing undefined parameters raises an error."""
        content = """{{ scorecard_name }} - {{ missing_param }}"""
        
        parameters = {
            'scorecard_name': 'Test'
            # missing_param is not provided
        }
        
        with pytest.raises(Exception):  # jinja2.UndefinedError
            render_report_content(content, parameters)
    
    def test_empty_parameters(self):
        """Test rendering content with no parameters."""
        content = """# Static Report

This report has no dynamic parameters.
It will always render the same.
"""
        
        result = render_report_content(content, {})
        
        assert '# Static Report' in result
        assert 'This report has no dynamic parameters' in result
    
    def test_special_characters_in_values(self):
        """Test parameters with special characters are properly escaped."""
        content = """Title: {{ title }}
Description: {{ description }}
"""
        
        parameters = {
            'title': 'Report & Analysis',
            'description': 'Contains "quotes" and <tags>'
        }
        
        result = render_report_content(content, parameters)
        
        # Jinja2 doesn't auto-escape in non-HTML contexts
        assert 'Title: Report & Analysis' in result
        assert 'Description: Contains "quotes" and <tags>' in result
    
    def test_list_iteration(self):
        """Test iterating over list parameters."""
        content = """## Scorecards Analyzed

{% for scorecard in scorecards %}
- {{ scorecard }}
{% endfor %}
"""
        
        parameters = {
            'scorecards': ['Call Criteria', 'Customer Service', 'Sales Quality']
        }
        
        result = render_report_content(content, parameters)
        
        assert '- Call Criteria' in result
        assert '- Customer Service' in result
        assert '- Sales Quality' in result
    
    def test_nested_conditionals(self):
        """Test nested if/else blocks."""
        content = """{% if has_data %}
Data available.
{% if include_details %}
  Detailed view enabled.
{% else %}
  Summary view.
{% endif %}
{% else %}
No data available.
{% endif %}
"""
        
        # Test with data and details
        result1 = render_report_content(content, {
            'has_data': True,
            'include_details': True
        })
        assert 'Data available' in result1
        assert 'Detailed view enabled' in result1
        
        # Test with data but no details
        result2 = render_report_content(content, {
            'has_data': True,
            'include_details': False
        })
        assert 'Data available' in result2
        assert 'Summary view' in result2
        
        # Test with no data
        result3 = render_report_content(content, {
            'has_data': False,
            'include_details': True
        })
        assert 'No data available' in result3
        assert 'Detailed view enabled' not in result3


class TestParameterExtractionFromYAML:
    """Test extracting parameters section from report configuration YAML."""
    
    def test_extract_parameters_from_yaml(self):
        """Test parsing parameters section from YAML configuration."""
        import yaml
        
        config_content = """parameters:
  - name: scorecard_id
    label: Scorecard
    type: scorecard_select
    required: true
  - name: time_range
    label: Time Range (days)
    type: number
    default: 30

---

# {{ scorecard_id }} Report

Content here...
"""
        
        # Split on --- to separate parameters from content
        parts = config_content.split('---', 1)
        param_yaml = parts[0].strip()
        content = parts[1].strip() if len(parts) > 1 else ''
        
        # Parse parameters
        param_data = yaml.safe_load(param_yaml)
        parameters_def = param_data.get('parameters', [])
        
        assert len(parameters_def) == 2
        assert parameters_def[0]['name'] == 'scorecard_id'
        assert parameters_def[0]['type'] == 'scorecard_select'
        assert parameters_def[0]['required'] is True
        
        assert parameters_def[1]['name'] == 'time_range'
        assert parameters_def[1]['type'] == 'number'
        assert parameters_def[1]['default'] == 30
        
        assert '{{ scorecard_id }} Report' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

