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
        text=sample_data['text'],
        metadata=sample_data['metadata'],
        accountId="test-account",
        isEvaluation=True,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
        client=mock_client
    )

def test_update_prediction(sample_item):
    new_text = "updated text"
    
    sample_item._client.execute.return_value = {
        'updateItem': {
            'id': sample_item.id,
            'evaluationId': sample_item.evaluationId,
            'text': new_text,
            'metadata': sample_item.metadata,
            'accountId': sample_item.accountId,
            'isEvaluation': sample_item.isEvaluation,
            'createdAt': sample_item.createdAt.isoformat(),
            'updatedAt': datetime.now(timezone.utc).isoformat()
        }
    }
    
    updated = sample_item.update(text=new_text)
    assert updated.text == new_text

def test_update_prevents_modifying_created_at(sample_item):
    with pytest.raises(ValueError, match="createdAt cannot be modified"):
        sample_item.update(createdAt=datetime.now(timezone.utc))

def test_create_requires_evaluation_id(mock_client):
    with pytest.raises(TypeError):
        Item.create(client=mock_client) 