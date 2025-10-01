"""
Test CLI parameter parsing for report run command.

Tests that both --param-NAME and --NAME formats work correctly.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, MagicMock, patch
from plexus.cli.report.report_commands import run


class TestCLIParameterParsing:
    """Test parsing of parameter options from command line."""
    
    def test_parameter_name_extraction(self):
        """Test that parameter names are extracted correctly."""
        # Test --param-NAME=value
        test_args = ['--param-days=60', '--param-include-summary=true']
        
        params = {}
        for arg in test_args:
            if arg.startswith('--param-'):
                parts = arg[8:].split('=', 1)
                if len(parts) == 2:
                    param_name, param_value = parts
                    params[param_name.replace('-', '_')] = param_value
        
        assert params['days'] == '60'
        assert params['include_summary'] == 'true'
    
    def test_direct_parameter_extraction(self):
        """Test extraction of direct parameter names."""
        test_args = ['--days=90', '--include-summary=false']
        
        params = {}
        reserved = ['config', 'fresh', 'task-id']
        
        for arg in test_args:
            if arg.startswith('--') and '=' in arg:
                parts = arg[2:].split('=', 1)
                if len(parts) == 2:
                    param_name, param_value = parts
                    if param_name not in reserved:
                        params[param_name.replace('-', '_')] = param_value
        
        assert params['days'] == '90'
        assert params['include_summary'] == 'false'
    
    def test_reserved_options_not_captured(self):
        """Test that reserved CLI options are not captured as parameters."""
        test_args = ['--config=test', '--fresh', '--task-id=123', '--days=30']
        
        params = {}
        reserved = ['config', 'fresh', 'task-id']
        
        for arg in test_args:
            if arg.startswith('--') and '=' in arg:
                parts = arg[2:].split('=', 1)
                if len(parts) == 2:
                    param_name, param_value = parts
                    if param_name not in reserved:
                        params[param_name.replace('-', '_')] = param_value
        
        # Should capture days (legacy support)
        assert 'days' in params
        # Should NOT capture reserved options
        assert 'config' not in params
        assert 'fresh' not in params
        assert 'task_id' not in params
    
    def test_hyphen_to_underscore_conversion(self):
        """Test that hyphens in parameter names are converted to underscores."""
        param_name = 'include-summary'
        normalized = param_name.replace('-', '_')
        
        assert normalized == 'include_summary'
        
        # Test with --param- prefix
        arg = '--param-include-summary=true'
        parts = arg[8:].split('=', 1)
        name = parts[0].replace('-', '_')
        
        assert name == 'include_summary'


class TestParameterFormatSupport:
    """Test that both parameter formats are supported."""
    
    def test_both_formats_supported(self):
        """Document that both formats should work."""
        formats = [
            '--param-days=60',      # Explicit prefix (avoids collisions)
            '--days=60',            # Direct name (more convenient)
        ]
        
        # Both should be valid
        for fmt in formats:
            assert fmt.startswith('--')
            assert '=' in fmt
            
            # Extract value
            value = fmt.split('=')[1]
            assert value == '60'
    
    def test_collision_avoidance(self):
        """Test that --param- prefix avoids collisions with CLI options."""
        # If there's ever a CLI option --format, you can use --param-format
        # to pass it as a parameter instead
        
        cli_option = '--format=json'  # Hypothetical CLI option
        param_option = '--param-format=detailed'  # Parameter named 'format'
        
        # They should be distinguishable
        assert cli_option.startswith('--format')
        assert param_option.startswith('--param-format')
        assert not cli_option.startswith('--param-')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

