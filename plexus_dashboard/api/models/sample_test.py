import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
from .sample import Sample

@pytest.fixture
def mock_client():
    return Mock()

@pytest.fixture
def sample_data():
    return {
        'text': 'example text',
        'metadata': {'source': 'test'}
    }

@pytest.fixture
def sample_sample(mock_client, sample_data):
    return Sample(
        id="test-id",
        evaluationId="test-evaluation",
        data=sample_data,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
        client=mock_client
    )

def test_update_prediction(sample_sample):
    """Test updating sample prediction"""
    new_prediction = "positive"
    
    sample_sample._client.execute.return_value = {
        'updateSample': {
            'id': sample_sample.id,
            'evaluationId': sample_sample.evaluationId,
            'data': sample_sample.data,
            'createdAt': sample_sample.createdAt.isoformat(),
            'updatedAt': datetime.now(timezone.utc).isoformat(),
            'prediction': new_prediction,
            'groundTruth': None,
            'isCorrect': None
        }
    }
    
    updated = sample_sample.update(prediction=new_prediction)
    assert updated.prediction == new_prediction

def test_update_prevents_modifying_created_at(sample_sample):
    """Test that update prevents modifying createdAt"""
    with pytest.raises(ValueError, match="createdAt cannot be modified"):
        sample_sample.update(createdAt=datetime.now(timezone.utc))

def test_create_requires_evaluation_id_and_data(mock_client):
    """Test that create requires evaluationId and data"""
    with pytest.raises(TypeError):
        Sample.create(client=mock_client)