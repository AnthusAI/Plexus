"""
Comprehensive integration tests for CLI report commands.
These tests focus on critical high-level functionality missing test coverage.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from click.testing import CliRunner
import json
from datetime import datetime, timezone

from plexus.cli.report.report_commands import (
    run, list_reports, show_report, show_last_report, delete_report, purge_reports
)
from plexus.dashboard.api.models.report_configuration import ReportConfiguration
from plexus.dashboard.api.models.report import Report
from plexus.dashboard.api.models.task import Task
from plexus.dashboard.api.models.report_block import ReportBlock
from plexus.cli.shared.task_progress_tracker import TaskProgressTracker


class TestReportRunCommand:
    """Test the 'plexus report run' command integration."""

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report_config')
    @patch('plexus.reports.service.generate_report_with_parameters')
    def test_run_command_success(self, mock_generate, mock_resolve_config, mock_resolve_account, mock_create_client):
        """Test successful report run command execution."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"

        mock_config = MagicMock()
        mock_config.id = "config-456"
        mock_config.name = "Test Config"
        mock_config.configuration = ""  # No parameters
        mock_resolve_config.return_value = mock_config

        # Mock successful generation - returns (report_id, error, task_id)
        mock_generate.return_value = ("report-123", None, "task-789")

        # Execute command
        runner = CliRunner()
        result = runner.invoke(run, ['--config', 'test-config'])

        # Verify success
        assert result.exit_code == 0
        assert "Report generation completed successfully!" in result.output
        assert "Report ID: report-123" in result.output

        # Verify key integrations
        mock_resolve_config.assert_called_once_with("test-config", "test-account-123", mock_client)
        mock_generate.assert_called_once()

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report_config')
    def test_run_command_config_not_found(self, mock_resolve_config, mock_resolve_account, mock_create_client):
        """Test run command when config is not found."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"
        mock_resolve_config.return_value = None  # Config not found
        
        # Execute command
        runner = CliRunner()
        result = runner.invoke(run, ['--config', 'nonexistent-config'])
        
        # Verify error message is displayed (exit code may be 0 or 1 depending on implementation)
        assert "not found" in result.output

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report_config')
    @patch('plexus.reports.service.generate_report_with_parameters')
    def test_run_command_with_parameters(self, mock_generate, mock_resolve_config, mock_resolve_account, mock_create_client):
        """Test run command with additional parameters."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"

        mock_config = MagicMock()
        mock_config.id = "config-456"
        mock_config.name = "Test Config"
        mock_config.configuration = ""  # No parameters in config
        mock_resolve_config.return_value = mock_config

        # Mock successful generation
        mock_generate.return_value = ("report-123", None, "task-789")

        # Execute command with parameters
        runner = CliRunner()
        result = runner.invoke(run, [
            '--config', 'test-config',
            '--days', '30',
            '--fresh',
            'start_date=2023-01-01',
            'end_date=2023-12-31'
        ])

        # Verify success
        assert result.exit_code == 0

        # Verify parameters were passed to generate function
        call_args = mock_generate.call_args
        parameters = call_args.kwargs['parameters']
        assert parameters['days'] == '30'
        assert parameters['start_date'] == '2023-01-01'
        assert parameters['end_date'] == '2023-12-31'

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report_config')
    @patch('plexus.reports.service.generate_report_with_parameters')
    def test_run_command_with_errors(self, mock_generate, mock_resolve_config, mock_resolve_account, mock_create_client):
        """Test run command handling block errors."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"

        mock_config = MagicMock()
        mock_config.id = "config-456"
        mock_config.name = "Test Config"
        mock_config.configuration = ""  # No parameters
        mock_resolve_config.return_value = mock_config

        # Mock generation with error
        mock_generate.return_value = ("report-123", "Block execution failed", "task-789")

        # Execute command
        runner = CliRunner()
        result = runner.invoke(run, ['--config', 'test-config'])

        # Verify error handling
        assert result.exit_code == 0  # Command succeeds but reports errors
        assert "finished with errors" in result.output
        assert "Block execution failed" in result.output


class TestReportListCommand:
    """Test the 'plexus report list' command integration."""

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.Report.list_by_account_id')
    @patch('plexus.cli.report.report_commands.ReportConfiguration.get_by_id')
    @patch('plexus.cli.report.report_commands.Task.get_by_id')
    def test_list_reports_success(self, mock_task_get, mock_config_get, mock_report_list, 
                                 mock_resolve_account, mock_create_client):
        """Test successful report listing."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"
        
        # Mock reports
        mock_report1 = MagicMock()
        mock_report1.id = "report-1"
        mock_report1.name = "Test Report 1"
        mock_report1.reportConfigurationId = "config-1"
        mock_report1.taskId = "task-1"
        mock_report1.createdAt = datetime.now(timezone.utc)
        
        mock_report2 = MagicMock()
        mock_report2.id = "report-2"
        mock_report2.name = "Test Report 2"
        mock_report2.reportConfigurationId = "config-2"
        mock_report2.taskId = "task-2"
        mock_report2.createdAt = datetime.now(timezone.utc)
        
        mock_report_list.return_value = [mock_report1, mock_report2]
        
        # Mock config and task lookups
        mock_config = MagicMock()
        mock_config.name = "Test Config"
        mock_config_get.return_value = mock_config
        
        mock_task = MagicMock()
        mock_task.status = "COMPLETED"
        mock_task_get.return_value = mock_task
        
        # Execute command
        runner = CliRunner()
        result = runner.invoke(list_reports, ['--limit', '10'])
        
        # Verify success
        assert result.exit_code == 0
        assert "Test Report 1" in result.output
        assert "Test Report 2" in result.output
        
        # Verify API calls
        mock_report_list.assert_called_once_with(
            account_id="test-account-123",
            client=mock_client,
            limit=200
        )

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report_config')
    @patch('plexus.cli.report.report_commands.Report.list_by_account_id')
    def test_list_reports_with_config_filter(self, mock_report_list, mock_resolve_config, 
                                           mock_resolve_account, mock_create_client):
        """Test report listing with configuration filter."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"
        
        mock_config = MagicMock()
        mock_config.id = "config-456"
        mock_config.name = "Test Config"
        mock_resolve_config.return_value = mock_config
        
        mock_report_list.return_value = []
        
        # Execute command
        runner = CliRunner()
        result = runner.invoke(list_reports, ['--config', 'test-config'])
        
        # Verify success
        assert result.exit_code == 0
        assert "Filtering reports for Configuration ID: config-456" in result.output
        
        # Verify config resolution
        mock_resolve_config.assert_called_once_with("test-config", "test-account-123", mock_client)

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.Report.list_by_account_id')
    def test_list_reports_empty_result(self, mock_report_list, mock_resolve_account, mock_create_client):
        """Test report listing when no reports exist."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"
        mock_report_list.return_value = []
        
        # Execute command
        runner = CliRunner()
        result = runner.invoke(list_reports)
        
        # Verify empty result handling
        assert result.exit_code == 0
        assert "No reports found" in result.output


class TestReportShowCommand:
    """Test the 'plexus report show' command integration."""

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report')
    @patch('plexus.cli.report.report_commands.Task.get_by_id')
    @patch('plexus.cli.report.report_commands.ReportConfiguration.get_by_id')
    @patch('plexus.cli.report.report_commands.ReportBlock.list_by_report_id')
    def test_show_report_success(self, mock_blocks_list, mock_config_get, mock_task_get, 
                                mock_resolve_report, mock_resolve_account, mock_create_client):
        """Test successful report show command."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"
        
        # Mock report
        mock_report = MagicMock()
        mock_report.id = "report-123"
        mock_report.name = "Test Report"
        mock_report.taskId = "task-456"
        mock_report.reportConfigurationId = "config-789"
        mock_report.accountId = "test-account-123"
        mock_report.createdAt = datetime.now(timezone.utc)
        mock_report.updatedAt = datetime.now(timezone.utc)
        mock_report.parameters = {"test": "value"}
        mock_report.output = "# Report Output\n\nThis is test content."
        mock_resolve_report.return_value = mock_report
        
        # Mock task
        mock_task = MagicMock()
        mock_task.id = "task-456"
        mock_task.status = "COMPLETED"
        mock_task.createdAt = datetime.now(timezone.utc)
        mock_task.updatedAt = datetime.now(timezone.utc)
        mock_task.startedAt = datetime.now(timezone.utc)
        mock_task.completedAt = datetime.now(timezone.utc)
        mock_task.errorMessage = None
        mock_task.metadata = {"test": "metadata"}
        mock_task.description = "Test task"
        mock_task_get.return_value = mock_task
        
        # Mock config
        mock_config = MagicMock()
        mock_config.id = "config-789"
        mock_config.name = "Test Config"
        mock_config_get.return_value = mock_config
        
        # Mock blocks
        mock_block = MagicMock()
        mock_block.id = "block-1"
        mock_block.name = "Test Block"
        mock_block.position = 0
        mock_block.type = "TestBlock"
        mock_block.output = {"result": "success"}
        mock_block.log = "Block executed successfully"
        mock_blocks_list.return_value = [mock_block]
        
        # Execute command
        runner = CliRunner()
        result = runner.invoke(show_report, ['report-123'])
        
        # Verify success
        assert result.exit_code == 0
        assert "Test Report" in result.output
        assert "COMPLETED" in result.output
        assert "Test Config" in result.output
        
        # Verify API calls
        mock_resolve_report.assert_called_once_with("report-123", "test-account-123", mock_client)
        mock_task_get.assert_called_once_with("task-456", client=mock_client)
        mock_config_get.assert_called_once_with("config-789", mock_client)
        mock_blocks_list.assert_called_once_with("report-123", mock_client)

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report')
    def test_show_report_not_found(self, mock_resolve_report, mock_resolve_account, mock_create_client):
        """Test show command when report is not found."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"
        mock_resolve_report.return_value = None  # Report not found
        
        # Execute command
        runner = CliRunner()
        result = runner.invoke(show_report, ['nonexistent-report'])
        
        # Verify failure
        assert result.exit_code != 0
        assert "not found" in result.output


class TestReportDeleteCommand:
    """Test the 'plexus report delete' command integration."""

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report')
    def test_delete_report_success_with_yes_flag(self, mock_resolve_report, mock_resolve_account, mock_create_client):
        """Test successful report deletion with --yes flag."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"
        
        mock_report = MagicMock()
        mock_report.id = "report-123"
        mock_report.name = "Test Report"
        mock_report.delete.return_value = True
        mock_resolve_report.return_value = mock_report
        
        # Execute command
        runner = CliRunner()
        result = runner.invoke(delete_report, ['report-123', '--yes'])
        
        # Verify success
        assert result.exit_code == 0
        assert "Successfully deleted report" in result.output
        assert "Test Report" in result.output
        
        # Verify deletion was called
        mock_report.delete.assert_called_once()

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report')
    def test_delete_report_with_confirmation(self, mock_resolve_report, mock_resolve_account, mock_create_client):
        """Test report deletion with interactive confirmation."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"
        
        mock_report = MagicMock()
        mock_report.id = "report-123"
        mock_report.name = "Test Report"
        mock_report.delete.return_value = True
        mock_resolve_report.return_value = mock_report
        
        # Execute command with confirmation
        runner = CliRunner()
        result = runner.invoke(delete_report, ['report-123'], input='y\n')
        
        # Verify success
        assert result.exit_code == 0
        assert "Successfully deleted report" in result.output
        mock_report.delete.assert_called_once()

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report')
    def test_delete_report_cancelled(self, mock_resolve_report, mock_resolve_account, mock_create_client):
        """Test report deletion cancellation."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"
        
        mock_report = MagicMock()
        mock_report.id = "report-123"
        mock_report.name = "Test Report"
        mock_resolve_report.return_value = mock_report
        
        # Execute command with cancellation
        runner = CliRunner()
        result = runner.invoke(delete_report, ['report-123'], input='n\n')
        
        # Verify cancellation
        assert result.exit_code == 0
        assert "Deletion cancelled" in result.output
        mock_report.delete.assert_not_called()


class TestReportPurgeCommand:
    """Test the 'plexus report purge' command integration."""

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.Report.list_by_account_id')
    @patch('plexus.cli.report.report_commands.Report.delete_multiple')
    def test_purge_reports_success(self, mock_delete_multiple, mock_report_list, 
                                  mock_resolve_account, mock_create_client):
        """Test successful report purging."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"
        
        # Mock reports to purge
        mock_report1 = MagicMock()
        mock_report1.id = "report-1"
        mock_report1.name = "Old Report 1"
        mock_report1.createdAt = datetime.now(timezone.utc)
        
        mock_report2 = MagicMock()
        mock_report2.id = "report-2"
        mock_report2.name = "Old Report 2"
        mock_report2.createdAt = datetime.now(timezone.utc)
        
        mock_report_list.return_value = [mock_report1, mock_report2]
        
        # Mock successful deletion
        mock_delete_multiple.return_value = {
            "report-1": True,
            "report-2": True
        }
        
        # Execute command
        runner = CliRunner()
        result = runner.invoke(purge_reports, ['--limit', '2', '--yes'])
        
        # Verify success
        assert result.exit_code == 0
        assert "Successfully deleted 2 reports" in result.output
        
        # Verify deletion was called
        mock_delete_multiple.assert_called_once_with(["report-1", "report-2"], mock_client)

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report_config')
    @patch('plexus.cli.report.report_commands.Report.list_by_account_id')
    def test_purge_reports_with_config_filter(self, mock_report_list, mock_resolve_config, 
                                             mock_resolve_account, mock_create_client):
        """Test report purging with configuration filter."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"
        
        mock_config = MagicMock()
        mock_config.id = "config-456"
        mock_config.name = "Test Config"
        mock_resolve_config.return_value = mock_config
        
        mock_report_list.return_value = []
        
        # Execute command
        runner = CliRunner()
        result = runner.invoke(purge_reports, ['--config', 'test-config', '--yes'])
        
        # Verify success
        assert result.exit_code == 0
        assert "configuration Test Config" in result.output
        
        # Verify config resolution
        mock_resolve_config.assert_called_once_with("test-config", "test-account-123", mock_client)


class TestReportCommandsErrorHandling:
    """Test error handling across report commands."""

    @patch('plexus.cli.report.report_commands.create_client')
    def test_client_creation_failure(self, mock_create_client):
        """Test handling of client creation failures."""
        mock_create_client.side_effect = Exception("Client creation failed")
        
        runner = CliRunner()
        result = runner.invoke(run, ['--config', 'test-config'])
        
        # Verify error handling
        assert result.exit_code != 0

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    def test_account_resolution_failure(self, mock_resolve_account, mock_create_client):
        """Test handling of account resolution failures."""
        mock_create_client.return_value = MagicMock()
        mock_resolve_account.side_effect = Exception("Account resolution failed")
        
        runner = CliRunner()
        result = runner.invoke(list_reports)
        
        # Verify error handling
        assert result.exit_code != 0

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report_config')
    @patch('plexus.reports.service.generate_report_with_parameters')
    def test_task_creation_failure(self, mock_generate, mock_resolve_config, mock_resolve_account, mock_create_client):
        """Test handling of task creation failures."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"

        mock_config = MagicMock()
        mock_config.id = "config-456"
        mock_config.name = "Test Config"
        mock_config.configuration = ""  # No parameters
        mock_resolve_config.return_value = mock_config

        # Mock task creation failure inside generate function
        mock_generate.side_effect = Exception("Task creation failed")

        # Execute command
        runner = CliRunner()
        result = runner.invoke(run, ['--config', 'test-config'])

        # Verify error handling
        assert result.exit_code != 0
        assert "Task creation failed" in result.output or "Unexpected error" in result.output

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report_config')
    @patch('plexus.reports.service.generate_report_with_parameters')
    def test_tracker_initialization_failure(self, mock_generate, mock_resolve_config, mock_resolve_account, mock_create_client):
        """Test handling of tracker initialization failures."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"

        mock_config = MagicMock()
        mock_config.id = "config-456"
        mock_config.name = "Test Config"
        mock_config.configuration = ""  # No parameters
        mock_resolve_config.return_value = mock_config

        # Mock tracker initialization failure inside generate function
        mock_generate.side_effect = Exception("Tracker initialization failed")

        # Execute command
        runner = CliRunner()
        result = runner.invoke(run, ['--config', 'test-config'])

        # Verify error handling
        assert result.exit_code != 0
        assert "Tracker initialization failed" in result.output or "Unexpected error" in result.output

    @patch('plexus.cli.report.report_commands.create_client')
    @patch('plexus.cli.report.report_commands.resolve_account_id_for_command')
    @patch('plexus.cli.report.report_commands.resolve_report_config')
    @patch('plexus.reports.service.generate_report_with_parameters')
    def test_core_generation_failure(self, mock_generate, mock_resolve_config, mock_resolve_account, mock_create_client):
        """Test handling of core generation failures."""
        # Setup mocks
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = "test-account-123"

        mock_config = MagicMock()
        mock_config.id = "config-456"
        mock_config.name = "Test Config"
        mock_config.configuration = ""  # No parameters
        mock_resolve_config.return_value = mock_config

        # Mock core generation failure inside generate function
        mock_generate.side_effect = Exception("Core generation failed")

        # Execute command
        runner = CliRunner()
        result = runner.invoke(run, ['--config', 'test-config'])

        # Verify error handling
        assert result.exit_code != 0
        assert "Core generation failed" in result.output or "Unexpected error" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])