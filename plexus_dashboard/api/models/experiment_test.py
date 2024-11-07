import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from .experiment import Experiment

@pytest.fixture
def mock_client():
    return Mock()

@pytest.fixture
def sample_experiment(mock_client):
    return Experiment(
        id="test-id",
        type="accuracy",
        accountId="test-account",
        status="PENDING",
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
        client=mock_client
    )

def test_update_preserves_required_fields(sample_experiment):
    """Test that update preserves type and status if not provided"""
    original_type = sample_experiment.type
    original_status = sample_experiment.status
    
    # Mock the GraphQL response
    sample_experiment._client.execute.return_value = {
        'updateExperiment': {
            'id': sample_experiment.id,
            'type': original_type,
            'status': original_status,
            'accountId': sample_experiment.accountId,
            'createdAt': sample_experiment.createdAt.isoformat(),
            'updatedAt': datetime.now(timezone.utc).isoformat(),
            'accuracy': 95.5
        }
    }
    
    # Update with only accuracy
    updated = sample_experiment.update(accuracy=95.5)
    
    # Check that type and status were preserved
    assert updated.type == original_type
    assert updated.status == original_status
    assert updated.accuracy == 95.5

def test_update_allows_overriding_required_fields(sample_experiment):
    """Test that update allows overriding type and status"""
    new_type = "consistency"
    new_status = "COMPLETED"
    
    # Mock the GraphQL response
    sample_experiment._client.execute.return_value = {
        'updateExperiment': {
            'id': sample_experiment.id,
            'type': new_type,
            'status': new_status,
            'accountId': sample_experiment.accountId,
            'createdAt': sample_experiment.createdAt.isoformat(),
            'updatedAt': datetime.now(timezone.utc).isoformat()
        }
    }
    
    # Update type and status
    updated = sample_experiment.update(type=new_type, status=new_status)
    
    # Check that values were updated
    assert updated.type == new_type
    assert updated.status == new_status

def test_update_prevents_modifying_created_at(sample_experiment):
    """Test that update prevents modifying createdAt"""
    with pytest.raises(ValueError, match="createdAt cannot be modified"):
        sample_experiment.update(createdAt=datetime.now(timezone.utc))

def test_update_always_sets_updated_at(sample_experiment):
    """Test that update always sets updatedAt to current time"""
    before = datetime.now(timezone.utc)
    
    # Mock the GraphQL response
    sample_experiment._client.execute.return_value = {
        'updateExperiment': {
            'id': sample_experiment.id,
            'type': sample_experiment.type,
            'status': sample_experiment.status,
            'accountId': sample_experiment.accountId,
            'createdAt': sample_experiment.createdAt.isoformat(),
            'updatedAt': datetime.now(timezone.utc).isoformat()
        }
    }
    
    updated = sample_experiment.update(accuracy=95.5)
    after = datetime.now(timezone.utc)
    
    # Check that updatedAt was set to a time between before and after
    assert before <= updated.updatedAt <= after 