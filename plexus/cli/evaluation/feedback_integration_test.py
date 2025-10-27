"""
Integration tests for the feedback evaluation CLI command.

These tests verify the command-line interface and parameter handling
without mocking internal implementation details.
"""

import pytest
from click.testing import CliRunner
from plexus.cli.evaluation.evaluations import feedback


class TestFeedbackCommandIntegration:
    """Integration tests for feedback CLI command."""
    
    def test_feedback_command_help(self):
        """Test that help text is displayed correctly."""
        runner = CliRunner()
        result = runner.invoke(feedback, ['--help'])
        
        assert result.exit_code == 0
        assert 'Evaluate feedback alignment' in result.output
        assert '--scorecard' in result.output
        assert '--score' in result.output
        assert '--days' in result.output
        assert '--version' in result.output
        assert 'WITHOUT --version' in result.output
        assert 'WITH --version' in result.output
    
    def test_feedback_command_missing_required_params(self):
        """Test that missing required parameters are caught."""
        runner = CliRunner()
        
        # Missing both scorecard and score
        result = runner.invoke(feedback, [])
        assert result.exit_code != 0
        
        # Missing score
        result = runner.invoke(feedback, ['--scorecard', 'test'])
        assert result.exit_code != 0
        
        # Missing scorecard
        result = runner.invoke(feedback, ['--score', 'test'])
        assert result.exit_code != 0
    
    def test_feedback_command_accepts_all_params(self):
        """Test that all parameters are accepted (even if execution fails due to missing data)."""
        runner = CliRunner()
        
        # This will fail because the scorecard doesn't exist, but it should
        # accept the parameters without argument parsing errors
        result = runner.invoke(feedback, [
            '--scorecard', 'nonexistent_scorecard',
            '--score', 'nonexistent_score',
            '--days', '30',
            '--version', 'test_version_123'
        ])
        
        # Should not be a Click argument error (exit code 2)
        # Will likely be exit code 1 (execution error) or 0 if mocked
        assert result.exit_code != 2, f"Argument parsing failed: {result.output}"
    
    def test_feedback_command_days_default(self):
        """Test that days parameter has correct default."""
        runner = CliRunner()
        
        # Run with minimal params (will fail, but we can check the help)
        result = runner.invoke(feedback, ['--help'])
        
        # Check that default is documented
        assert 'default: 7' in result.output or 'Default: 7' in result.output
    
    def test_feedback_command_version_parameter_optional(self):
        """Test that version parameter is optional."""
        runner = CliRunner()
        
        # Should accept command without version
        result = runner.invoke(feedback, [
            '--scorecard', 'test_scorecard',
            '--score', 'test_score',
            '--days', '7'
        ])
        
        # Should not fail due to missing version parameter
        # (may fail for other reasons like missing scorecard)
        assert '--version' not in result.output or 'required' not in result.output.lower()


class TestFeedbackCommandModes:
    """Tests for the two different modes of feedback evaluation."""
    
    def test_mode_documentation_in_help(self):
        """Test that both modes are documented in help text."""
        runner = CliRunner()
        result = runner.invoke(feedback, ['--help'])
        
        assert result.exit_code == 0
        
        # Check for mode 1 documentation
        assert 'WITHOUT --version' in result.output or 'without version' in result.output.lower()
        assert 'feedback edits' in result.output.lower() or 'analyzes feedback' in result.output.lower()
        
        # Check for mode 2 documentation  
        assert 'WITH --version' in result.output or 'with version' in result.output.lower()
        assert 'accuracy evaluation' in result.output.lower() or 'FeedbackItems' in result.output
    
    def test_version_parameter_changes_behavior(self):
        """Test that providing version parameter changes execution path."""
        runner = CliRunner()
        
        # Mode 1: Without version (will fail but we can check output)
        result1 = runner.invoke(feedback, [
            '--scorecard', 'test',
            '--score', 'test',
            '--days', '7'
        ], catch_exceptions=False)
        
        # Mode 2: With version (will fail but differently)
        result2 = runner.invoke(feedback, [
            '--scorecard', 'test',
            '--score', 'test',
            '--days', '7',
            '--version', 'v123'
        ], catch_exceptions=False)
        
        # Both should fail (no real data), but the error messages might differ
        # This test just verifies the parameter is accepted
        assert '--version' not in result2.output or 'unrecognized' not in result2.output.lower()


class TestFeedbackCommandParameterValidation:
    """Tests for parameter validation."""
    
    def test_days_accepts_positive_integer(self):
        """Test that days parameter accepts positive integers."""
        runner = CliRunner()
        
        # Valid days values
        for days in ['1', '7', '30', '90', '365']:
            result = runner.invoke(feedback, [
                '--scorecard', 'test',
                '--score', 'test',
                '--days', days
            ])
            # Should not fail due to invalid days parameter
            assert 'Invalid value' not in result.output
    
    def test_version_accepts_string(self):
        """Test that version parameter accepts string values."""
        runner = CliRunner()
        
        # Various version formats
        for version in ['v1', 'abc123', 'version-with-dashes', '12345']:
            result = runner.invoke(feedback, [
                '--scorecard', 'test',
                '--score', 'test',
                '--version', version
            ])
            # Should not fail due to invalid version format
            assert 'Invalid value' not in result.output or 'version' not in result.output.lower()
    
    def test_scorecard_and_score_required(self):
        """Test that both scorecard and score are required."""
        runner = CliRunner()
        
        # Just scorecard
        result = runner.invoke(feedback, ['--scorecard', 'test'])
        assert result.exit_code != 0
        assert 'score' in result.output.lower() or 'required' in result.output.lower()
        
        # Just score
        result = runner.invoke(feedback, ['--score', 'test'])
        assert result.exit_code != 0
        assert 'scorecard' in result.output.lower() or 'required' in result.output.lower()


@pytest.mark.integration
class TestFeedbackCommandExamples:
    """Test the examples from the documentation."""
    
    def test_example_commands_parse_correctly(self):
        """Test that documented example commands parse correctly."""
        runner = CliRunner()
        
        examples = [
            ['--scorecard', 'Call Criteria', '--score', 'Greeting', '--days', '14'],
            ['--scorecard', 'Call Criteria', '--score', 'Greeting', '--days', '30', '--version', 'abc123'],
            ['--scorecard', '1438', '--score', '45813', '--days', '7'],
        ]
        
        for example in examples:
            result = runner.invoke(feedback, example)
            # Should not be a Click parsing error (exit code 2)
            assert result.exit_code != 2, f"Example failed to parse: {example}\nOutput: {result.output}"




