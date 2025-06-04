import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
from .identifier import Identifier

@pytest.fixture
def mock_client():
    return Mock()

@pytest.fixture
def sample_identifier_data():
    return {
        'id': 'test-identifier-id',
        'itemId': 'test-item-id',
        'name': 'Customer ID',
        'value': 'CUST-123456',
        'accountId': 'test-account',
        'createdAt': datetime.now(timezone.utc).isoformat(),
        'updatedAt': datetime.now(timezone.utc).isoformat(),
        'url': 'https://example.com/customers/123456'
    }

@pytest.fixture
def sample_identifier(mock_client, sample_identifier_data):
    return Identifier.from_dict(sample_identifier_data, mock_client)

def test_create_identifier(mock_client):
    """Test creating a new identifier record."""
    mock_client.execute.return_value = {
        'createIdentifier': {
            'id': 'new-id',
            'itemId': 'item-123',
            'name': 'Order ID',
            'value': 'ORD-789012',
            'accountId': 'account-456',
            'createdAt': '2024-01-01T00:00:00Z',
            'updatedAt': '2024-01-01T00:00:00Z',
            'url': None
        }
    }
    
    identifier = Identifier.create(
        client=mock_client,
        itemId='item-123',
        name='Order ID',
        value='ORD-789012',
        accountId='account-456'
    )
    
    assert identifier.itemId == 'item-123'
    assert identifier.name == 'Order ID'
    assert identifier.value == 'ORD-789012'
    assert identifier.accountId == 'account-456'
    assert identifier.url is None

def test_find_by_value(mock_client):
    """Test finding identifier by exact value."""
    mock_client.execute.return_value = {
        'listIdentifiers': {
            'items': [{
                'id': 'found-id',
                'itemId': 'item-123',
                'name': 'Customer ID',
                'value': 'CUST-123456',
                'accountId': 'account-456',
                'createdAt': '2024-01-01T00:00:00Z',
                'updatedAt': '2024-01-01T00:00:00Z',
                'url': 'https://example.com'
            }]
        }
    }
    
    identifier = Identifier.find_by_value('CUST-123456', 'account-456', mock_client)
    
    assert identifier is not None
    assert identifier.value == 'CUST-123456'
    assert identifier.accountId == 'account-456'

def test_find_by_value_not_found(mock_client):
    """Test finding identifier when none exists."""
    mock_client.execute.return_value = {
        'listIdentifiers': {
            'items': []
        }
    }
    
    identifier = Identifier.find_by_value('NONEXISTENT', 'account-456', mock_client)
    assert identifier is None

def test_list_by_item_id(mock_client):
    """Test getting all identifiers for an item."""
    mock_client.execute.return_value = {
        'listIdentifiers': {
            'items': [
                {
                    'id': 'id-1',
                    'itemId': 'item-123',
                    'name': 'Customer ID',
                    'value': 'CUST-123456',
                    'accountId': 'account-456',
                    'createdAt': '2024-01-01T00:00:00Z',
                    'updatedAt': '2024-01-01T00:00:00Z',
                    'url': None
                },
                {
                    'id': 'id-2',
                    'itemId': 'item-123',
                    'name': 'Order ID',
                    'value': 'ORD-789012',
                    'accountId': 'account-456',
                    'createdAt': '2024-01-01T00:00:00Z',
                    'updatedAt': '2024-01-01T00:00:00Z',
                    'url': None
                }
            ]
        }
    }
    
    identifiers = Identifier.list_by_item_id('item-123', mock_client)
    
    assert len(identifiers) == 2
    assert identifiers[0].name == 'Customer ID'
    assert identifiers[1].name == 'Order ID'

def test_batch_find_by_values(mock_client):
    """Test batch lookup of multiple identifier values."""
    mock_client.execute.return_value = {
        'listIdentifiers': {
            'items': [
                {
                    'id': 'id-1',
                    'itemId': 'item-123',
                    'name': 'Customer ID',
                    'value': 'CUST-123456',
                    'accountId': 'account-456',
                    'createdAt': '2024-01-01T00:00:00Z',
                    'updatedAt': '2024-01-01T00:00:00Z',
                    'url': None
                },
                {
                    'id': 'id-2',
                    'itemId': 'item-789',
                    'name': 'Order ID',
                    'value': 'ORD-789012',
                    'accountId': 'account-456',
                    'createdAt': '2024-01-01T00:00:00Z',
                    'updatedAt': '2024-01-01T00:00:00Z',
                    'url': None
                }
            ]
        }
    }
    
    result = Identifier.batch_find_by_values(
        ['CUST-123456', 'ORD-789012', 'MISSING-123'], 
        'account-456', 
        mock_client
    )
    
    assert len(result) == 2
    assert 'CUST-123456' in result
    assert 'ORD-789012' in result
    assert 'MISSING-123' not in result
    assert result['CUST-123456'].itemId == 'item-123'
    assert result['ORD-789012'].itemId == 'item-789'

def test_update_identifier(sample_identifier):
    """Test updating an identifier."""
    sample_identifier._client.execute.return_value = {
        'updateIdentifier': {
            'id': sample_identifier.id,
            'itemId': sample_identifier.itemId,
            'name': 'Updated Name',
            'value': sample_identifier.value,
            'accountId': sample_identifier.accountId,
            'createdAt': sample_identifier.createdAt.isoformat(),
            'updatedAt': datetime.now(timezone.utc).isoformat(),
            'url': sample_identifier.url
        }
    }
    
    updated = sample_identifier.update(name='Updated Name')
    assert updated.name == 'Updated Name'

def test_update_prevents_modifying_immutable_fields(sample_identifier):
    """Test that certain fields cannot be modified after creation."""
    with pytest.raises(ValueError, match="createdAt cannot be modified"):
        sample_identifier.update(createdAt=datetime.now(timezone.utc))
    
    with pytest.raises(ValueError, match="id cannot be modified"):
        sample_identifier.update(id='new-id')
    
    with pytest.raises(ValueError, match="itemId cannot be modified"):
        sample_identifier.update(itemId='new-item-id')
    
    with pytest.raises(ValueError, match="accountId cannot be modified"):
        sample_identifier.update(accountId='new-account-id')

def test_delete_identifier(sample_identifier):
    """Test deleting an identifier."""
    sample_identifier._client.execute.return_value = {
        'deleteIdentifier': {
            'id': sample_identifier.id
        }
    }
    
    result = sample_identifier.delete()
    assert result is True

def test_delete_identifier_failure(sample_identifier):
    """Test delete failure handling."""
    sample_identifier._client.execute.side_effect = Exception("Delete failed")
    
    result = sample_identifier.delete()
    assert result is False 