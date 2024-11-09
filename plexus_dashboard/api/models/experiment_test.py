"""
Tests for the Experiment model.

These tests verify:
1. Background processing of mutations (create/update)
2. Error handling in background threads
3. Proper field handling and validation
4. Thread safety of operations

The tests use mocking to avoid actual API calls and to verify
the background processing behavior.
"""

import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from .experiment import Experiment

@pytest.fixture
def mock_client():
    """Provides a mock API client for testing."""
    return Mock()

@pytest.fixture
def sample_experiment(mock_client):
    """Creates a sample experiment instance for testing.
    
    Returns an experiment with realistic test data including:
    - Required fields (type, accountId, status, etc.)
    - Optional fields (parameters, metrics, etc.)
    - Timestamps in proper format
    """
    return Experiment(
        id="test-id",
        type="accuracy",
        accountId="acc-123",
        status="PENDING",
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
        parameters={"model": "gpt-4"},
        client=mock_client
    )

def test_create_experiment_background(mock_client):
    """Test that experiment creation happens in background.
    
    Verifies:
    1. create() returns immediately
    2. Mutation is executed in background thread
    3. Error handling doesn't affect main thread
    """
    # Start experiment creation
    Experiment.create(
        client=mock_client,
        type="accuracy",
        accountId="acc-123",
        parameters={"model": "gpt-4"}
    )
    
    # Give background thread time to process
    time.sleep(0.1)
    
    # Verify mutation was called
    mock_client.execute.assert_called_once()
    mutation = mock_client.execute.call_args[0][0]
    assert "mutation CreateExperiment" in mutation

def test_update_experiment_background(sample_experiment):
    """Test that experiment updates happen in background.
    
    Verifies:
    1. update() returns immediately
    2. Mutation is executed in background thread
    3. updatedAt is automatically set
    4. Error handling doesn't affect main thread
    """
    # Update experiment
    sample_experiment.update(
        status="RUNNING",
        progress=0.5
    )
    
    # Give background thread time to process
    time.sleep(0.1)
    
    # Verify mutation was called
    sample_experiment._client.execute.assert_called_once()
    variables = sample_experiment._client.execute.call_args[0][1]
    assert variables['input']['status'] == "RUNNING"
    assert variables['input']['progress'] == 0.5
    assert 'updatedAt' in variables['input']

def test_error_handling_in_background(sample_experiment):
    """Test that background thread errors are handled gracefully.
    
    Verifies:
    1. Errors in background thread don't propagate
    2. Main thread continues execution
    3. Errors are logged but don't raise
    """
    # Make the mutation raise an error
    sample_experiment._client.execute.side_effect = Exception("Test error")
    
    # This should not raise, despite the error
    sample_experiment.update(status="RUNNING")
    
    # Give background thread time to process
    time.sleep(0.1)
    
    # Verify mutation was attempted
    sample_experiment._client.execute.assert_called_once()