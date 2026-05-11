"""
Tests for ProcedureService task creation logic.

Verifies that tasks created for procedures have the correct command format
and dispatch status based on dispatch mode.
"""

import json
from unittest.mock import Mock
import pytest

from plexus.cli.procedure.service import ProcedureService


class TestProcedureTaskCreation:
    """Test task creation with correct command format and dispatch status."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock dashboard client that returns appropriate responses."""
        client = Mock()
        client._resolve_account_id = Mock(return_value="test-account-id")

        # Mock execute to return empty task list when querying, and capture create calls
        def mock_execute(query, variables=None):
            if 'listTaskByAccountIdAndUpdatedAt' in query:
                # Return empty list so it creates a new task
                return {
                    'listTaskByAccountIdAndUpdatedAt': {
                        'items': []
                    }
                }
            elif 'createTask' in query:
                # Capture the createTask mutation and return a valid response
                return {
                    'createTask': {
                        'id': 'task-123',
                        'command': variables.get('input', {}).get('command'),
                        'dispatchStatus': variables.get('input', {}).get('dispatchStatus'),
                        'metadata': variables.get('input', {}).get('metadata'),
                    }
                }
            return {}

        client.execute = Mock(side_effect=mock_execute)
        return client

    @pytest.fixture
    def service(self, mock_client):
        """Create a ProcedureService with mocked client."""
        return ProcedureService(mock_client)

    def test_celery_mode_creates_pending_task_with_run_command(self, service, mock_client):
        """Test that celery dispatch mode creates task with 'procedure run' command and PENDING status."""
        procedure_id = "proc-abc-123"
        account_id = "account-xyz"
        dispatch_mode = "celery"

        # Call the internal method that creates tasks
        service._get_or_create_task_with_stages_for_procedure(
            procedure_id=procedure_id,
            account_id=account_id,
            dispatch_mode=dispatch_mode,
        )

        # Find the createTask mutation call
        create_calls = [
            call_args for call_args in mock_client.execute.call_args_list
            if 'createTask' in str(call_args)
        ]

        assert len(create_calls) > 0, "Task.create should have been called"

        # Get the variables from the createTask mutation
        create_call = create_calls[0]
        variables = create_call[0][1]  # Second argument to execute()
        task_input = variables['input']

        # Verify command includes 'run' subcommand
        assert task_input['command'] == f"procedure run {procedure_id}", \
            f"Expected 'procedure run {procedure_id}', got '{task_input['command']}'"

        # Verify dispatch status is PENDING for celery mode
        assert task_input['dispatchStatus'] == "PENDING", \
            f"Expected dispatchStatus='PENDING' for celery mode, got '{task_input['dispatchStatus']}'"

        # Verify metadata contains dispatch_mode
        metadata = json.loads(task_input['metadata'])
        assert metadata['dispatch_mode'] == "celery"

    def test_local_mode_creates_local_task_with_run_command(self, service, mock_client):
        """Test that local dispatch mode creates task with 'procedure run' command and LOCAL status."""
        procedure_id = "proc-def-456"
        account_id = "account-xyz"
        dispatch_mode = "local"

        # Call the internal method
        service._get_or_create_task_with_stages_for_procedure(
            procedure_id=procedure_id,
            account_id=account_id,
            dispatch_mode=dispatch_mode,
        )

        # Find the createTask mutation call
        create_calls = [
            call_args for call_args in mock_client.execute.call_args_list
            if 'createTask' in str(call_args)
        ]

        assert len(create_calls) > 0, "Task.create should have been called"

        # Get the variables from the createTask mutation
        create_call = create_calls[0]
        variables = create_call[0][1]
        task_input = variables['input']

        # Verify command includes 'run' subcommand
        assert task_input['command'] == f"procedure run {procedure_id}", \
            f"Expected 'procedure run {procedure_id}', got '{task_input['command']}'"

        # Verify dispatch status is LOCAL for local mode
        assert task_input['dispatchStatus'] == "LOCAL", \
            f"Expected dispatchStatus='LOCAL' for local mode, got '{task_input['dispatchStatus']}'"

        # Verify metadata contains dispatch_mode
        metadata = json.loads(task_input['metadata'])
        assert metadata['dispatch_mode'] == "local"

    def test_command_format_matches_cli_structure(self, service, mock_client):
        """
        Test that the command format matches the actual CLI command structure.

        The CLI command is: plexus procedure run <procedure-id>
        So the Task command should be: procedure run <procedure-id>
        """
        procedure_id = "proc-ghi-789"

        service._get_or_create_task_with_stages_for_procedure(
            procedure_id=procedure_id,
            account_id="test-account",
            dispatch_mode="celery",
        )

        # Find the createTask mutation call
        create_calls = [
            call_args for call_args in mock_client.execute.call_args_list
            if 'createTask' in str(call_args)
        ]

        create_call = create_calls[0]
        variables = create_call[0][1]
        command = variables['input']['command']

        # The command should have exactly 3 parts: 'procedure', 'run', and the ID
        parts = command.split()
        assert len(parts) == 3, \
            f"Command should have 3 parts (procedure run <id>), got {len(parts)}: {command}"
        assert parts[0] == "procedure", f"First part should be 'procedure', got '{parts[0]}'"
        assert parts[1] == "run", f"Second part should be 'run', got '{parts[1]}'"
        assert parts[2] == procedure_id, f"Third part should be procedure ID, got '{parts[2]}'"
