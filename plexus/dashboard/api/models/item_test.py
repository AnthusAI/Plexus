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

def test_create_serializes_metadata_to_json(mock_client):
    """Test that Item.create properly serializes metadata dict to JSON string."""
    metadata_dict = {
        'source': 'test',
        'duration': 120,
        'schools': [{'name': 'Test School', 'type': 'Campus'}],
        'other_data': {'key1': 'value1', 'key2': 'value2'}
    }
    
    # Mock the GraphQL response
    mock_client.execute.return_value = {
        'createItem': {
            'id': 'test-item-123',
            'evaluationId': 'test-eval',
            'text': 'test text',
            'metadata': '{"source": "test", "duration": 120}',  # JSON string in response
            'accountId': 'test-account',
            'isEvaluation': False,
            'createdAt': '2025-01-01T00:00:00Z',
            'updatedAt': '2025-01-01T00:00:00Z',
            'createdByType': 'prediction'
        }
    }
    
    # Call create with metadata dict
    result = Item.create(
        client=mock_client,
        evaluationId='test-eval',
        text='test text',
        metadata=metadata_dict,
        accountId='test-account',
        isEvaluation=False
    )
    
    # Verify the GraphQL mutation was called
    mock_client.execute.assert_called_once()
    call_args = mock_client.execute.call_args
    
    # Extract the input data from the call - should be in args[1] (variables dict)
    variables = call_args[0][1]  # call_args[0] is args tuple, [1] is variables
    mutation_input = variables['input']
    
    # Verify metadata was JSON serialized
    import json
    assert 'metadata' in mutation_input
    # The metadata should be a JSON string, not a dict
    assert isinstance(mutation_input['metadata'], str)
    
    # Verify we can parse it back to the original dict
    parsed_metadata = json.loads(mutation_input['metadata'])
    assert parsed_metadata == metadata_dict

def test_update_serializes_metadata_to_json(sample_item):
    """Test that Item.update properly serializes metadata dict to JSON string."""
    new_metadata = {
        'source': 'updated',
        'version': 2,
        'tags': ['tag1', 'tag2']
    }
    
    # Mock the GraphQL response
    sample_item._client.execute.return_value = {
        'updateItem': {
            'id': sample_item.id,
            'evaluationId': sample_item.evaluationId,
            'text': sample_item.text,
            'metadata': '{"source": "updated", "version": 2, "tags": ["tag1", "tag2"]}',
            'accountId': sample_item.accountId,
            'isEvaluation': sample_item.isEvaluation,
            'createdAt': sample_item.createdAt.isoformat(),
            'updatedAt': datetime.now(timezone.utc).isoformat()
        }
    }
    
    # Call update with metadata dict
    result = sample_item.update(metadata=new_metadata)
    
    # Verify the GraphQL mutation was called
    sample_item._client.execute.assert_called_once()
    call_args = sample_item._client.execute.call_args
    
    # Extract the input data from the call - should be in variables['input']
    variables = call_args[0][1]  # call_args[0] is args tuple, [1] is variables  
    mutation_input = variables['input']
    
    # Verify metadata was JSON serialized
    import json
    assert 'metadata' in mutation_input
    # The metadata should be a JSON string, not a dict
    assert isinstance(mutation_input['metadata'], str)
    
    # Verify we can parse it back to the original dict
    parsed_metadata = json.loads(mutation_input['metadata'])
    assert parsed_metadata == new_metadata 