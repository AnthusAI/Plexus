import pytest
from unittest.mock import patch, MagicMock, mock_open
from click.testing import CliRunner
import click
import os

# Adjust the import path based on your project structure
# from plexus.cli.ReportCommands import config as report_config_commands # Old import
from plexus.cli import ReportCommands # New import
from plexus.cli.ReportCommands import report # Import the specific command group
from plexus.dashboard.api.models import ReportConfiguration, Account # Assuming these models exist

# Fixture for CliRunner
@pytest.fixture
def runner():
    return CliRunner()

# Fixture for mock client
@pytest.fixture
def mock_plexus_client():
    mock = MagicMock()
    # Mock the account resolution part of the client
    mock._resolve_account_id.return_value = 'test-account-id'
    # Mock the model methods attached/called via the client
    # For simplicity, assume methods are directly on the model classes for mocking here
    return mock

# --- Tests for `config create` command ---

@patch('plexus.cli.ReportCommands.create_client')
@patch('plexus.cli.ReportCommands.Account')
@patch('plexus.cli.ReportCommands.ReportConfiguration')
@patch('click.confirm')
def test_create_config_no_duplicate(mock_click_confirm, MockReportConfig, MockAccount, mock_create_client, runner, mock_plexus_client):
    """Test `config create` when no duplicate exists."""
    # Arrange
    mock_create_client.return_value = mock_plexus_client
    MockAccount.get_by_key.return_value = None # Simulate resolving by default env var
    MockAccount.get_by_id.return_value = None # Simulate resolving by default env var
    # Mock get_by_name to return None (no duplicate found)
    MockReportConfig.get_by_name.return_value = None
    # Mock the create method
    mock_created_config = MagicMock(spec=ReportConfiguration)
    mock_created_config.id = 'new-config-id'
    mock_created_config.name = 'My New Config'
    mock_created_config.accountId = 'test-account-id'
    MockReportConfig.create.return_value = mock_created_config

    # Use isolated filesystem
    with runner.isolated_filesystem():
        # Create a dummy file for Click to find
        with open("dummy_path.md", "w", encoding="utf-8") as f:
            f.write("# Test Config Content")

        # Act
        result = runner.invoke(report, ['config', 'create', '--name', 'My New Config', '--file', 'dummy_path.md'])

    # Assert
    assert result.exit_code == 0
    assert "Checking for existing configurations" in result.output
    assert "No existing configuration found" in result.output
    mock_click_confirm.assert_not_called() # Confirm should not be called
    MockReportConfig.get_by_name.assert_called_once_with(name='My New Config', account_id='test-account-id', client=mock_plexus_client)
    MockReportConfig.create.assert_called_once()
    # Check if the correct args were passed to create
    create_args, create_kwargs = MockReportConfig.create.call_args
    assert create_kwargs.get('name') == 'My New Config'
    assert create_kwargs.get('accountId') == 'test-account-id'
    assert create_kwargs.get('configuration') == "# Test Config Content"
    assert "Successfully created Report Configuration" in result.output
    assert "ID: new-config-id" in result.output

@patch('plexus.cli.ReportCommands.create_client')
@patch('plexus.cli.ReportCommands.Account')
@patch('plexus.cli.ReportCommands.ReportConfiguration')
@patch('click.confirm')
def test_create_config_duplicate_identical_content_abort(mock_click_confirm, MockReportConfig, MockAccount, mock_create_client, runner, mock_plexus_client):
    """Test `config create` with identical duplicate, user aborts."""
    # Arrange
    mock_create_client.return_value = mock_plexus_client
    MockAccount.get_by_key.return_value = None
    MockAccount.get_by_id.return_value = None

    # Mock get_by_name to return an existing config with identical content
    mock_existing_config = MagicMock(spec=ReportConfiguration)
    mock_existing_config.id = 'existing-config-id'
    mock_existing_config.name = 'Duplicate Config'
    mock_existing_config.configuration = "# Identical Content"
    MockReportConfig.get_by_name.return_value = mock_existing_config

    # Mock click.confirm to return False (user aborts)
    mock_click_confirm.return_value = False

    # Use isolated filesystem
    with runner.isolated_filesystem():
        with open("dummy_path.md", "w", encoding="utf-8") as f:
            f.write("# Identical Content")

        # Act
        result = runner.invoke(report, ['config', 'create', '--name', 'Duplicate Config', '--file', 'dummy_path.md'])

    # Assert
    assert "Operation cancelled by user." in result.output
    assert isinstance(result.exception, SystemExit)
    assert result.exit_code == 1
    mock_click_confirm.assert_called_once_with("Do you want to proceed and create a duplicate configuration?", default=False)
    MockReportConfig.create.assert_not_called() # Create should not be called

@patch('plexus.cli.ReportCommands.create_client')
@patch('plexus.cli.ReportCommands.Account')
@patch('plexus.cli.ReportCommands.ReportConfiguration')
@patch('click.confirm')
def test_create_config_duplicate_identical_content_proceed(mock_click_confirm, MockReportConfig, MockAccount, mock_create_client, runner, mock_plexus_client):
    """Test `config create` with identical duplicate, user proceeds."""
    # Arrange
    mock_create_client.return_value = mock_plexus_client
    MockAccount.get_by_key.return_value = None
    MockAccount.get_by_id.return_value = None

    # Mock get_by_name to return an existing config with identical content
    mock_existing_config = MagicMock(spec=ReportConfiguration)
    mock_existing_config.id = 'existing-config-id'
    mock_existing_config.name = 'Duplicate Config'
    mock_existing_config.configuration = "# Identical Content"
    MockReportConfig.get_by_name.return_value = mock_existing_config

    # Mock click.confirm to return True (user proceeds)
    mock_click_confirm.return_value = True

    # Mock the create method for the new config
    mock_created_config = MagicMock(spec=ReportConfiguration)
    mock_created_config.id = 'new-duplicate-config-id'
    mock_created_config.name = 'Duplicate Config'
    mock_created_config.accountId = 'test-account-id'
    MockReportConfig.create.return_value = mock_created_config

    # Use isolated filesystem
    with runner.isolated_filesystem():
        with open("dummy_path.md", "w", encoding="utf-8") as f:
            f.write("# Identical Content")

        # Act
        result = runner.invoke(report, ['config', 'create', '--name', 'Duplicate Config', '--file', 'dummy_path.md'])

    # Assert
    assert result.exit_code == 0
    assert "Warning: An existing configuration" in result.output
    assert "with the name 'Duplicate Config'" in result.output
    assert "identical content already exists." in result.output
    mock_click_confirm.assert_called_once_with("Do you want to proceed and create a duplicate configuration?", default=False)
    MockReportConfig.create.assert_called_once() # Create should be called
    assert "Successfully created Report Configuration" in result.output
    assert "ID: new-duplicate-config-id" in result.output

@patch('plexus.cli.ReportCommands.create_client')
@patch('plexus.cli.ReportCommands.Account')
@patch('plexus.cli.ReportCommands.ReportConfiguration')
@patch('click.confirm')
def test_create_config_duplicate_different_content_abort(mock_click_confirm, MockReportConfig, MockAccount, mock_create_client, runner, mock_plexus_client):
    """Test `config create` with duplicate name, different content, user aborts."""
    # Arrange
    mock_create_client.return_value = mock_plexus_client
    MockAccount.get_by_key.return_value = None
    MockAccount.get_by_id.return_value = None

    # Mock get_by_name to return an existing config with different content
    mock_existing_config = MagicMock(spec=ReportConfiguration)
    mock_existing_config.id = 'existing-config-id'
    mock_existing_config.name = 'Duplicate Name'
    mock_existing_config.configuration = "# Original Content" # Different from read_data
    MockReportConfig.get_by_name.return_value = mock_existing_config

    # Mock click.confirm to return False (user aborts)
    mock_click_confirm.return_value = False

    # Use isolated filesystem
    with runner.isolated_filesystem():
        with open("dummy_path.md", "w", encoding="utf-8") as f:
            f.write("# Different Content")

        # Act
        result = runner.invoke(report, ['config', 'create', '--name', 'Duplicate Name', '--file', 'dummy_path.md'])

    # Assert
    assert "Operation cancelled by user." in result.output
    assert isinstance(result.exception, SystemExit)
    assert result.exit_code == 1
    mock_click_confirm.assert_called_once_with("Do you want to proceed and create a new configuration with this name?", default=False)
    MockReportConfig.create.assert_not_called()

@patch('plexus.cli.ReportCommands.create_client')
@patch('plexus.cli.ReportCommands.Account')
@patch('plexus.cli.ReportCommands.ReportConfiguration')
@patch('click.confirm')
def test_create_config_duplicate_different_content_proceed(mock_click_confirm, MockReportConfig, MockAccount, mock_create_client, runner, mock_plexus_client):
    """Test `config create` with duplicate name, different content, user proceeds."""
    # Arrange
    mock_create_client.return_value = mock_plexus_client
    MockAccount.get_by_key.return_value = None
    MockAccount.get_by_id.return_value = None

    # Mock get_by_name to return an existing config with different content
    mock_existing_config = MagicMock(spec=ReportConfiguration)
    mock_existing_config.id = 'existing-config-id'
    mock_existing_config.name = 'Duplicate Name'
    mock_existing_config.configuration = "# Original Content"
    MockReportConfig.get_by_name.return_value = mock_existing_config

    # Mock click.confirm to return True (user proceeds)
    mock_click_confirm.return_value = True

    # Mock the create method
    mock_created_config = MagicMock(spec=ReportConfiguration)
    mock_created_config.id = 'new-diff-content-config-id'
    mock_created_config.name = 'Duplicate Name'
    mock_created_config.accountId = 'test-account-id'
    MockReportConfig.create.return_value = mock_created_config

    # Use isolated filesystem
    with runner.isolated_filesystem():
        with open("dummy_path.md", "w", encoding="utf-8") as f:
            f.write("# Different Content")

        # Act
        result = runner.invoke(report, ['config', 'create', '--name', 'Duplicate Name', '--file', 'dummy_path.md'])

    # Assert
    assert result.exit_code == 0
    assert "Warning: An existing configuration" in result.output
    assert "with the name 'Duplicate Name'" in result.output
    normalized_output = ' '.join(result.output.split())
    assert "different content already exists." in normalized_output
    mock_click_confirm.assert_called_once_with("Do you want to proceed and create a new configuration with this name?", default=False)
    MockReportConfig.create.assert_called_once()
    assert "Successfully created Report Configuration" in result.output
    assert "ID: new-diff-content-config-id" in result.output

@patch('plexus.cli.ReportCommands.create_client')
@patch('plexus.cli.ReportCommands.Account')
@patch('plexus.cli.ReportCommands.ReportConfiguration')
@patch('click.confirm')
def test_create_config_with_description(mock_click_confirm, MockReportConfig, MockAccount, mock_create_client, runner, mock_plexus_client):
    """Test `config create` with the --description option."""
    # Arrange
    mock_create_client.return_value = mock_plexus_client
    MockAccount.get_by_key.return_value = None
    MockAccount.get_by_id.return_value = None
    MockReportConfig.get_by_name.return_value = None # No duplicate

    mock_created_config = MagicMock(spec=ReportConfiguration)
    mock_created_config.id = 'config-with-desc-id'
    mock_created_config.name = 'Config With Desc'
    mock_created_config.accountId = 'test-account-id'
    MockReportConfig.create.return_value = mock_created_config

    # Use isolated filesystem
    with runner.isolated_filesystem():
        with open("dummy_path.md", "w", encoding="utf-8") as f:
            f.write("# Config with Desc")

        # Act
        result = runner.invoke(report, [
            'config', 'create',
            '--name', 'Config With Desc',
            '--file', 'dummy_path.md',
            '--description', 'This is a test description.'
        ])

    # Assert
    assert result.exit_code == 0
    mock_click_confirm.assert_not_called()
    MockReportConfig.create.assert_called_once()
    create_args, create_kwargs = MockReportConfig.create.call_args
    assert create_kwargs.get('name') == 'Config With Desc'
    assert create_kwargs.get('description') == 'This is a test description.' # Verify description is passed
    assert create_kwargs.get('configuration') == "# Config with Desc"
    assert "Successfully created Report Configuration" in result.output
    assert "ID: config-with-desc-id" in result.output

# TODO: Add test case for file not found or empty file if not covered elsewhere
# TODO: Add test case for API error during get_by_name check
# TODO: Add test case for API error during create call

