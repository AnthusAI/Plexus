"""
Tests for the Evaluation model.

These tests verify:
1. Create/update mutation execution
2. Error handling in update path
3. Proper field handling and validation
4. Local instance synchronization after updates

The tests use mocking to avoid actual API calls and to verify
mutation behavior.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from .evaluation import Evaluation

@pytest.fixture
def mock_client():
    """Create a mock client with required execute method"""
    client = Mock()
    client.execute.return_value = {
        'createEvaluation': {
            'id': 'test-id',
            'type': 'accuracy',
            'accountId': 'acc-123',
            'status': 'PENDING',
            'createdAt': datetime.now(timezone.utc).isoformat(),
            'updatedAt': datetime.now(timezone.utc).isoformat()
        }
    }
    return client

@pytest.fixture
def sample_evaluation(mock_client):
    return Evaluation(
        id="test-id",
        type="accuracy",
        accountId="acc-123",
        status="PENDING",
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
        client=mock_client
    )

def test_create_evaluation(mock_client):
    """Test evaluation creation mutation."""
    # Configure mock response
    mock_client.execute.return_value = {
        'createEvaluation': {
            'id': 'test-id',
            'type': 'accuracy',
            'accountId': 'acc-123',
            'status': 'PENDING',
            'createdAt': datetime.now(timezone.utc).isoformat(),
            'updatedAt': datetime.now(timezone.utc).isoformat()
        }
    }
    
    # Start evaluation creation
    Evaluation.create(
        client=mock_client,
        type="accuracy",
        accountId="acc-123"
    )
    
    # Verify mutation was called
    mock_client.execute.assert_called_once()
    mutation = mock_client.execute.call_args[0][0]
    assert "mutation CreateEvaluation" in mutation

def test_update_evaluation(sample_evaluation):
    """Test that evaluation updates execute and sync locally."""
    sample_evaluation._client.execute.return_value = {
        'updateEvaluation': {
            'id': 'test-id',
            'type': 'accuracy',
            'accountId': 'acc-123',
            'status': 'RUNNING',
            'createdAt': datetime.now(timezone.utc).isoformat(),
            'updatedAt': datetime.now(timezone.utc).isoformat()
        }
    }

    # Update evaluation
    sample_evaluation.update(
        status="RUNNING",
        progress=0.5
    )

    # Verify mutation was called
    sample_evaluation._client.execute.assert_called_once()
    variables = sample_evaluation._client.execute.call_args[0][1]
    assert variables['input']['status'] == "RUNNING"
    assert variables['input']['progress'] == 0.5
    assert 'updatedAt' in variables['input']
    assert sample_evaluation.status == "RUNNING"

def test_error_handling_in_update(sample_evaluation):
    """Test that update errors are surfaced."""
    # Make the mutation raise an error
    sample_evaluation._client.execute.side_effect = Exception("Test error")
    
    # This should raise
    with pytest.raises(Exception, match="Test error"):
        sample_evaluation.update(status="RUNNING")
    
    # Verify mutation was attempted
    sample_evaluation._client.execute.assert_called_once()
