"""
Unit tests for the CLI record count commands.
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from plexus.cli.record_count.counting import count_items, count_scoreresults, count_results, count_group


class TestRecordCountCommands:
    """Test cases for the CLI record count commands."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.runner = CliRunner()
        self.test_account_id = "test-account-123"
        
        # Mock metrics data
        self.mock_metrics = {
            'itemsPerHour': 5,
            'scoreResultsPerHour': 10,
            'itemsAveragePerHour': 3.5,
            'scoreResultsAveragePerHour': 8.2,
            'itemsPeakHourly': 8,
            'scoreResultsPeakHourly': 15,
            'itemsTotal24h': 84,
            'scoreResultsTotal24h': 196,
            'chartData': [
                {
                    'time': '2 Hours Ago',
                    'items': 8,
                    'scoreResults': 15,
                    'bucketStart': '2024-01-01T10:00:00Z',
                    'bucketEnd': '2024-01-01T11:00:00Z'
                },
                {
                    'time': '1 Hour Ago',
                    'items': 3,
                    'scoreResults': 7,
                    'bucketStart': '2024-01-01T11:00:00Z',
                    'bucketEnd': '2024-01-01T12:00:00Z'
                },
                {
                    'time': 'Current Hour',
                    'items': 5,
                    'scoreResults': 10,
                    'bucketStart': '2024-01-01T12:00:00Z',
                    'bucketEnd': '2024-01-01T13:00:00Z'
                }
            ]
        }
    
    @patch('plexus.cli.record_count.counting.create_calculator_from_env')
    @patch('plexus.cli.record_count.counting.resolve_account_id')
    def test_count_items_success(self, mock_resolve_account_id, mock_create_calculator):
        """Test successful items counting command."""
        # Mock calculator
        mock_calculator = Mock()
        mock_calculator.get_items_summary.return_value = self.mock_metrics
        mock_create_calculator.return_value = mock_calculator
        
        # Mock account resolution
        mock_resolve_account_id.return_value = 'test-account-123'
        
        result = self.runner.invoke(count_items, [])
        
        assert result.exit_code == 0
        mock_calculator.get_items_summary.assert_called_once_with('test-account-123', 24)
        
        # Check that output contains expected metrics
        assert "Items Summary" in result.output
        assert "Current Hour" in result.output
        assert "5" in result.output  # Current hour count
    
    @patch('plexus.cli.record_count.counting.create_calculator_from_env')
    @patch('plexus.cli.record_count.counting.resolve_account_id')
    def test_count_items_with_account_id_option(self, mock_resolve_account_id, mock_create_calculator):
        """Test items counting with explicit account ID."""
        mock_calculator = Mock()
        mock_calculator.get_items_summary.return_value = self.mock_metrics
        mock_create_calculator.return_value = mock_calculator
        
        # Mock account resolution
        mock_resolve_account_id.return_value = 'custom-account'
        
        result = self.runner.invoke(count_items, ['--account-id', 'custom-account'])
        
        assert result.exit_code == 0
        mock_calculator.get_items_summary.assert_called_once_with('custom-account', 24)
    
    @patch('plexus.cli.record_count.counting.create_calculator_from_env')
    @patch('plexus.cli.record_count.counting.resolve_account_id')
    def test_count_items_with_custom_hours(self, mock_resolve_account_id, mock_create_calculator):
        """Test items counting with custom hours parameter."""
        mock_calculator = Mock()
        mock_calculator.get_items_summary.return_value = self.mock_metrics
        mock_create_calculator.return_value = mock_calculator
        
        # Mock account resolution
        mock_resolve_account_id.return_value = self.test_account_id
        
        result = self.runner.invoke(count_items, [
            '--account-id', self.test_account_id,
            '--hours', '12'
        ])
        
        assert result.exit_code == 0
        mock_calculator.get_items_summary.assert_called_once_with(self.test_account_id, 12)
    
    @patch('plexus.cli.record_count.counting.create_calculator_from_env')
    def test_count_items_json_output(self, mock_create_calculator):
        """Test items counting with JSON output."""
        mock_calculator = Mock()
        mock_calculator.get_items_summary.return_value = self.mock_metrics
        mock_create_calculator.return_value = mock_calculator
        
        result = self.runner.invoke(count_items, [
            '--account-id', self.test_account_id,
            '--json-output'
        ])
        
        assert result.exit_code == 0
        
        # Parse and verify JSON output
        output_data = json.loads(result.output)
        assert output_data['account_id'] == self.test_account_id
        assert output_data['items_current_hour'] == 5
        assert output_data['items_total'] == 84
        assert len(output_data['hourly_breakdown']) == 3
    
    @patch('plexus.cli.record_count.counting.resolve_account_id')
    def test_count_items_missing_account_id(self, mock_resolve_account_id):
        """Test items counting without account ID - should try to resolve and fail gracefully."""
        # Mock the resolve function to raise an exception
        from click import Abort
        mock_resolve_account_id.side_effect = Abort("Could not resolve account ID")
        
        result = self.runner.invoke(count_items, [])
        
        assert result.exit_code != 0
        # The command should abort when account resolution fails
        assert result.exit_code == 1
    
    @patch('plexus.cli.record_count.counting.create_calculator_from_env')
    @patch('plexus.cli.record_count.counting.resolve_account_id')
    def test_count_items_calculator_error(self, mock_resolve_account_id, mock_create_calculator):
        """Test items counting with calculator error."""
        mock_create_calculator.side_effect = Exception("Test calculator error")
        mock_resolve_account_id.return_value = self.test_account_id
        
        result = self.runner.invoke(count_items, ['--account-id', self.test_account_id])
        
        assert result.exit_code != 0
        # The error message might be formatted by Rich, so check for a more generic error pattern
        assert "Error" in result.output
    
    @patch('plexus.cli.record_count.counting.create_calculator_from_env')
    @patch('plexus.cli.record_count.counting.resolve_account_id')
    def test_count_scoreresults_success(self, mock_resolve_account_id, mock_create_calculator):
        """Test successful score results counting command."""
        mock_calculator = Mock()
        mock_calculator.get_score_results_summary.return_value = self.mock_metrics
        mock_create_calculator.return_value = mock_calculator
        mock_resolve_account_id.return_value = 'test-account-123'
        
        result = self.runner.invoke(count_scoreresults, [])
        
        assert result.exit_code == 0
        mock_calculator.get_score_results_summary.assert_called_once_with('test-account-123', 24)
        
        # Check that output contains expected metrics
        assert "Score Results Summary" in result.output
        assert "10" in result.output  # Current hour count
    
    @patch('plexus.cli.record_count.counting.create_calculator_from_env')
    def test_count_scoreresults_json_output(self, mock_create_calculator):
        """Test score results counting with JSON output."""
        mock_calculator = Mock()
        mock_calculator.get_score_results_summary.return_value = self.mock_metrics
        mock_create_calculator.return_value = mock_calculator
        
        result = self.runner.invoke(count_scoreresults, [
            '--account-id', self.test_account_id,
            '--json-output'
        ])
        
        assert result.exit_code == 0
        
        # Parse and verify JSON output
        output_data = json.loads(result.output)
        assert output_data['account_id'] == self.test_account_id
        assert output_data['score_results_current_hour'] == 10
        assert output_data['score_results_total'] == 196
        assert len(output_data['hourly_breakdown']) == 3
    
    @patch('plexus.cli.record_count.counting.count_scoreresults')
    def test_count_results_alias(self, mock_count_scoreresults):
        """Test that 'results' command works as an alias for 'scoreresults' by checking if the target function is called."""
        
        # We replace the actual function with a mock
        # The alias command 'results' should invoke this mock
        
        result = self.runner.invoke(count_results, [
            '--account-id', self.test_account_id,
            '--hours', '12'
        ])
        
        assert result.exit_code == 0
        
        # Verify that the mocked 'count_scoreresults' function was called once
        mock_count_scoreresults.assert_called_once()
        
        # Optionally, check if it was called with the correct arguments
        # The CLI passes arguments as a tuple in the 'args' attribute of the call object
        # Note: click passes parameters as a dictionary to the invoked function.
        # The mock call object's 'kwargs' will hold these.
        mock_count_scoreresults.assert_called_with(
            account_id=self.test_account_id,
            hours=12,
            bucket_width=15, # default value
            verbose=False,    # default value
            json_output=False # default value
        )
    
    def test_count_group_help(self):
        """Test the help message for the count group."""
        result = self.runner.invoke(count_group, ['--help'])
        
        assert result.exit_code == 0
        assert "Count items and score results" in result.output
        assert "items" in result.output
        assert "scoreresults" in result.output
        assert "results" in result.output
    
    def test_count_items_help(self):
        """Test the help message for the items command."""
        result = self.runner.invoke(count_items, ['--help'])
        
        assert result.exit_code == 0
        assert "Count items created in the specified timeframe" in result.output
        assert "--account-id" in result.output
        assert "--hours" in result.output
        assert "--verbose" in result.output
        assert "--json-output" in result.output
    
    def test_count_scoreresults_help(self):
        """Test the help message for the scoreresults command."""
        result = self.runner.invoke(count_scoreresults, ['--help'])
        
        assert result.exit_code == 0
        assert "Count score results created in the specified timeframe" in result.output
        assert "--account-id" in result.output
        assert "--hours" in result.output
    
    @patch('plexus.cli.record_count.counting.create_calculator_from_env')
    @patch('plexus.cli.record_count.counting.resolve_account_id')
    def test_verbose_logging(self, mock_resolve_account_id, mock_create_calculator):
        """Test verbose logging flag."""
        mock_calculator = Mock()
        mock_calculator.get_items_summary.return_value = self.mock_metrics
        mock_create_calculator.return_value = mock_calculator
        mock_resolve_account_id.return_value = self.test_account_id
        
        result = self.runner.invoke(count_items, [
            '--account-id', self.test_account_id,
            '--verbose'
        ])
        
        assert result.exit_code == 0
        # When verbose is enabled, logging level should be set to DEBUG
        # We can't easily test the logging level here, but we can ensure the command still works
    
    @patch('plexus.cli.record_count.counting.create_calculator_from_env')
    def test_json_error_output(self, mock_create_calculator):
        """Test JSON error output format."""
        mock_create_calculator.side_effect = Exception("Test error")
        
        result = self.runner.invoke(count_items, [
            '--account-id', self.test_account_id,
            '--json-output'
        ])
        
        assert result.exit_code != 0
        
        # Extract just the JSON part from the output
        output_lines = result.output.strip().split('\n')
        json_lines = []
        in_json = False
        
        for line in output_lines:
            if line.strip().startswith('{'):
                in_json = True
            if in_json:
                json_lines.append(line)
            if line.strip().endswith('}') and in_json:
                break
        
        json_text = '\n'.join(json_lines)
        
        # Parse error output as JSON
        error_data = json.loads(json_text)
        assert 'error' in error_data
        assert error_data['error'] == "Test error"


if __name__ == '__main__':
    pytest.main([__file__]) 