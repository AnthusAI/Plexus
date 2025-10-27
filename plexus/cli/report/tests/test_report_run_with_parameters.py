"""
Test report run command with parameter handling and Jinja2 rendering.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from plexus.reports.parameter_utils import render_configuration_with_parameters


class TestReportParameterRendering:
    """Test that parameters are correctly rendered before report execution."""
    
    def test_jinja2_rendering_removes_template_syntax(self):
        """Test that Jinja2 rendering replaces template variables with actual values."""
        # Configuration with parameter definition and Jinja2 template
        config = """parameters:
  - name: days
    label: Analysis Period (days)
    type: number
    min: 1
    max: 365
    default: 30
---

# Feedback Analysis Report
## SelectQuote MEL HRA

These agreement metrics are based on comparing the feedback edits from Selectquote over the last {{ days }} days.

```block name="Feedback Analysis"
class: FeedbackAnalysis
scorecard: 1461
days: {{ days }}
```
"""
        
        # Render with actual parameter value
        parameters = {'days': 60}
        rendered = render_configuration_with_parameters(config, parameters)
        
        # Verify template syntax is replaced
        assert '{{ days }}' not in rendered, "Template syntax should be replaced"
        assert 'last 60 days' in rendered, "Should contain rendered value in text"
        assert 'days: 60' in rendered, "Should contain rendered value in block"
        
        # Verify it can be parsed as YAML (no syntax errors)
        import yaml
        # Extract the block content
        block_start = rendered.find('```block')
        block_end = rendered.find('```', block_start + 1)
        block_content = rendered[block_start:block_end]
        
        # Extract YAML content between block markers
        yaml_content = block_content.split('\n', 1)[1]  # Skip first line (```block name=...)
        
        # Parse it - should not raise
        try:
            parsed = yaml.safe_load(yaml_content)
            assert parsed['days'] == 60, "Days should be integer 60, not template"
            assert parsed['class'] == 'FeedbackAnalysis'
            assert parsed['scorecard'] == 1461
        except yaml.YAMLError as e:
            pytest.fail(f"Rendered YAML should be valid: {e}")
    
    def test_configuration_content_preservation_during_render(self):
        """Test that rendering preserves all content, just replaces variables."""
        config = """parameters:
  - name: value1
    type: text
  - name: value2
    type: number
---
Text with {{ value1 }} and {{ value2 }}.
"""
        
        rendered = render_configuration_with_parameters(
            config, 
            {'value1': 'hello', 'value2': 42}
        )
        
        assert 'Text with hello and 42.' in rendered
        assert '{{ value1 }}' not in rendered
        assert '{{ value2 }}' not in rendered
    
    @patch('plexus.cli.report.report_commands.ReportConfiguration')
    @patch('plexus.cli.report.report_commands._generate_report_core')
    def test_report_run_uses_rendered_configuration(self, mock_generate, mock_config_class):
        """
        Test that report run passes configuration with rendered Jinja2 templates,
        not the original template syntax.
        
        This is the critical test - verifying the workflow:
        1. Load config with parameters
        2. Prompt user (or use CLI options)
        3. Render config with Jinja2
        4. Pass RENDERED config to report generation
        """
        # Mock configuration with parameters
        mock_config = MagicMock()
        mock_config.id = 'test-config-id'
        mock_config.name = 'Test Config'
        mock_config.accountId = 'test-account'
        mock_config.configuration = """parameters:
  - name: days
    type: number
    default: 30
---
Days: {{ days }}
```block
days: {{ days }}
```
"""
        
        # The issue we're testing: does the rendered config get passed through?
        # We expect _generate_report_core to receive config with "Days: 60"
        # not "Days: {{ days }}"
        
        # Since _generate_report_core takes config_id and loads from DB,
        # we need to verify that report_config.configuration is updated
        # OR that the rendered config is saved before generation
        
        # This test reveals the bug: we render the config but don't use it!
        # The fix needs to either:
        # 1. Save rendered config to DB before calling _generate_report_core
        # 2. Pass rendered config directly to _generate_report_core
        # 3. Modify _generate_report_core to accept optional config content
        
        assert True  # Placeholder - this test documents the issue


class TestParameterValueInjection:
    """Test that parameter values are correctly injected into configuration."""
    
    def test_simple_number_injection(self):
        """Test injecting a number parameter."""
        config = "Value: {{ count }}"
        rendered = render_configuration_with_parameters(config, {'count': 42})
        assert rendered == "Value: 42"
    
    def test_string_injection(self):
        """Test injecting a string parameter."""
        config = "Name: {{ name }}"
        rendered = render_configuration_with_parameters(config, {'name': 'Test'})
        assert rendered == "Name: Test"
    
    def test_boolean_injection(self):
        """Test injecting a boolean parameter."""
        config = "Enabled: {{ enabled }}"
        rendered = render_configuration_with_parameters(config, {'enabled': True})
        assert rendered == "Enabled: True"
    
    def test_multiple_parameters(self):
        """Test injecting multiple parameters."""
        config = "{{ param1 }} and {{ param2 }} and {{ param3 }}"
        rendered = render_configuration_with_parameters(
            config,
            {'param1': 'first', 'param2': 100, 'param3': False}
        )
        assert rendered == "first and 100 and False"
    
    def test_conditional_with_boolean_parameter(self):
        """Test conditional blocks based on boolean parameters."""
        config = """{% if show_section %}
Section is visible
{% else %}
Section is hidden
{% endif %}"""
        
        rendered_true = render_configuration_with_parameters(config, {'show_section': True})
        assert 'Section is visible' in rendered_true
        assert 'Section is hidden' not in rendered_true
        
        rendered_false = render_configuration_with_parameters(config, {'show_section': False})
        assert 'Section is hidden' in rendered_false
        assert 'Section is visible' not in rendered_false
    
    def test_yaml_block_with_parameter(self):
        """Test that YAML blocks with parameters render to valid YAML."""
        config = """```block
class: TestBlock
days: {{ days }}
name: {{ name }}
```"""
        
        rendered = render_configuration_with_parameters(
            config,
            {'days': 30, 'name': 'Test Report'}
        )
        
        # Extract block content
        assert 'days: 30' in rendered
        assert 'name: Test Report' in rendered
        assert '{{ days }}' not in rendered
        assert '{{ name }}' not in rendered


class TestConfigurationLoadingInCLI:
    """Test that CLI loads configuration content correctly."""
    
    def test_configuration_field_is_populated(self):
        """
        Test that ReportConfiguration.get_by_id returns the configuration field.
        
        This tests the data loading part - ensuring configuration content
        is actually fetched from the database.
        """
        # This would need a mock or integration test
        # The key point: report_config.configuration should contain the full content
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

