import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
from .item import Item

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
def sample_item(mock_client, sample_data):
    return Item(
        id="test-id",
        evaluationId="test-evaluation",
        data=sample_data,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
        client=mock_client
    )

def test_update_prediction(sample_item):
    new_prediction = "positive"
    
    sample_item._client.execute.return_value = {
        'updateItem': {
            'id': sample_item.id,
            'evaluationId': sample_item.evaluationId,
            'data': sample_item.data,
            'createdAt': sample_item.createdAt.isoformat(),
            'updatedAt': datetime.now(timezone.utc).isoformat(),
            'prediction': new_prediction,
            'groundTruth': None,
            'isCorrect': None
        }
    }
    
    updated = sample_item.update(prediction=new_prediction)
    assert updated.prediction == new_prediction

def test_update_prevents_modifying_created_at(sample_item):
    with pytest.raises(ValueError, match="createdAt cannot be modified"):
        sample_item.update(createdAt=datetime.now(timezone.utc))

def test_create_requires_evaluation_id_and_data(mock_client):
    with pytest.raises(TypeError):
        Item.create(client=mock_client) 