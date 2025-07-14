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


# Tests for find_by_identifier method
class TestFindByIdentifier:
    """Test suite for Item.find_by_identifier method"""
    
    @pytest.fixture
    def mock_item_response(self, sample_item):
        """Mock response for successful item lookup"""
        return sample_item
    
    def test_find_by_identifier_success(self, mock_client, mock_item_response):
        """Test successful item lookup by identifier"""
        # Mock the internal lookup methods - _lookup_item_by_identifiers now returns a dict
        mock_item_dict = {
            'id': 'test-item-id',
            'externalId': 'test-external-id', 
            'description': 'test description',
            'accountId': 'test-account',
            'identifiers': {},
            'text': 'test text'
        }
        Item._lookup_item_by_identifiers = Mock(return_value=mock_item_dict)
        Item.get_by_id = Mock(return_value=mock_item_response)
        
        # Test finding by reportId
        result = Item.find_by_identifier(
            client=mock_client,
            account_id="test-account",
            identifier_key="reportId", 
            identifier_value="277307013"
        )
        
        # Verify the result
        assert result is not None
        assert result == mock_item_response
        
        # Verify internal methods were called correctly
        Item._lookup_item_by_identifiers.assert_called_once_with(
            client=mock_client,
            account_id="test-account",
            identifiers={"reportId": "277307013"},
            debug=False
        )
        Item.get_by_id.assert_called_once_with("test-item-id", mock_client)
    
    def test_find_by_identifier_not_found(self, mock_client):
        """Test item not found scenario"""
        # Mock the lookup to return None (not found)
        Item._lookup_item_by_identifiers = Mock(return_value=None)
        Item.get_by_id = Mock()
        
        result = Item.find_by_identifier(
            client=mock_client,
            account_id="test-account", 
            identifier_key="formId",
            identifier_value="nonexistent"
        )
        
        # Verify no item returned
        assert result is None
        
        # Verify lookup was attempted but get_by_id was not called
        Item._lookup_item_by_identifiers.assert_called_once()
        Item.get_by_id.assert_not_called()
    
    def test_find_by_identifier_different_types(self, mock_client, mock_item_response):
        """Test finding items by different identifier types"""
        mock_item_dict = {
            'id': 'test-item-id',
            'externalId': 'test-external-id', 
            'description': 'test description',
            'accountId': 'test-account',
            'identifiers': {},
            'text': 'test text'
        }
        Item._lookup_item_by_identifiers = Mock(return_value=mock_item_dict)
        Item.get_by_id = Mock(return_value=mock_item_response)
        
        # Test different identifier types
        identifier_types = [
            ("reportId", "277307013"),
            ("formId", "12345"),
            ("sessionId", "session-abc-123"),
            ("ccId", "cc-999")
        ]
        
        for identifier_key, identifier_value in identifier_types:
            result = Item.find_by_identifier(
                client=mock_client,
                account_id="test-account",
                identifier_key=identifier_key,
                identifier_value=identifier_value
            )
            
            assert result == mock_item_response
    
    def test_find_by_identifier_with_debug(self, mock_client, mock_item_response):
        """Test find_by_identifier with debug logging enabled"""
        mock_item_dict = {
            'id': 'test-item-id',
            'externalId': 'test-external-id', 
            'description': 'test description',
            'accountId': 'test-account',
            'identifiers': {},
            'text': 'test text'
        }
        Item._lookup_item_by_identifiers = Mock(return_value=mock_item_dict)
        Item.get_by_id = Mock(return_value=mock_item_response)
        
        # Test with debug=True
        result = Item.find_by_identifier(
            client=mock_client,
            account_id="test-account",
            identifier_key="reportId",
            identifier_value="277307013",
            debug=True
        )
        
        assert result == mock_item_response
        
        # Verify debug was passed through to internal method
        Item._lookup_item_by_identifiers.assert_called_once_with(
            client=mock_client,
            account_id="test-account", 
            identifiers={"reportId": "277307013"},
            debug=True
        )
    
    def test_find_by_identifier_exception_handling(self, mock_client):
        """Test exception handling in find_by_identifier"""
        # Mock the lookup to raise an exception
        Item._lookup_item_by_identifiers = Mock(side_effect=Exception("Database error"))
        Item.get_by_id = Mock()
        
        # Should not raise exception, should return None
        result = Item.find_by_identifier(
            client=mock_client,
            account_id="test-account",
            identifier_key="reportId", 
            identifier_value="277307013"
        )
        
        assert result is None
        Item.get_by_id.assert_not_called()
    
    def test_find_by_identifier_get_by_id_fails(self, mock_client):
        """Test when _lookup_item_by_identifiers succeeds but get_by_id fails"""
        mock_item_dict = {
            'id': 'test-item-id',
            'externalId': 'test-external-id', 
            'description': 'test description',
            'accountId': 'test-account',
            'identifiers': {},
            'text': 'test text'
        }
        Item._lookup_item_by_identifiers = Mock(return_value=mock_item_dict)
        Item.get_by_id = Mock(return_value=None)  # get_by_id fails
        
        result = Item.find_by_identifier(
            client=mock_client,
            account_id="test-account",
            identifier_key="reportId",
            identifier_value="277307013"
        )
        
        # Should return None when get_by_id fails
        assert result is None
        
        # Verify both methods were called
        Item._lookup_item_by_identifiers.assert_called_once()
        Item.get_by_id.assert_called_once_with("test-item-id", mock_client)
    
    def test_find_by_identifier_empty_values(self, mock_client):
        """Test find_by_identifier with empty/invalid values"""
        Item._lookup_item_by_identifiers = Mock(return_value=None)
        
        # Test with empty identifier value
        result = Item.find_by_identifier(
            client=mock_client,
            account_id="test-account",
            identifier_key="reportId",
            identifier_value=""  # empty string
        )
        
        assert result is None
        
        # Test with None identifier value (should be handled gracefully)
        result = Item.find_by_identifier(
            client=mock_client, 
            account_id="test-account",
            identifier_key="reportId",
            identifier_value=None
        )
        
        assert result is None 