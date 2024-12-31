import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from .base import BaseModel

class TestModel(BaseModel):
    """Test implementation of BaseModel"""
    @classmethod
    def fields(cls) -> str:
        return "id name createdAt"
    
    @classmethod
    def from_dict(cls, data, client):
        return cls(id=data['id'], client=client)

@pytest.fixture
def mock_client():
    return Mock()

@pytest.fixture
def test_model(mock_client):
    return TestModel(id="test-id", client=mock_client)

def test_get_by_id_constructs_correct_query(test_model, mock_client):
    """Test that get_by_id generates correct GraphQL query"""
    mock_client.execute.return_value = {
        'getTestModel': {
            'id': 'test-id',
            'name': 'test',
            'createdAt': datetime.now(timezone.utc).isoformat()
        }
    }
    
    TestModel.get_by_id('test-id', mock_client)
    
    # Verify query structure
    called_query = mock_client.execute.call_args[0][0]
    assert 'query GetTestModel($id: ID!)' in called_query
    assert 'getTestModel(id: $id)' in called_query
    assert 'id name createdAt' in called_query
    
    # Verify variables
    called_variables = mock_client.execute.call_args[0][1]
    assert called_variables == {'id': 'test-id'}

def test_get_by_id_returns_model_instance(mock_client):
    """Test that get_by_id returns instance of correct model class"""
    mock_client.execute.return_value = {
        'getTestModel': {
            'id': 'test-id',
            'name': 'test',
            'createdAt': datetime.now(timezone.utc).isoformat()
        }
    }
    
    result = TestModel.get_by_id('test-id', mock_client)
    assert isinstance(result, TestModel)
    assert result.id == 'test-id'
    assert result._client == mock_client

def test_base_model_requires_fields_implementation():
    """Test that BaseModel requires fields() to be implemented"""
    class IncompleteModel(BaseModel):
        pass
    
    with pytest.raises(NotImplementedError):
        IncompleteModel.fields()

def test_base_model_requires_from_dict_implementation():
    """Test that BaseModel requires from_dict() to be implemented"""
    class IncompleteModel(BaseModel):
        @classmethod
        def fields(cls): 
            return "id"
    
    with pytest.raises(NotImplementedError):
        IncompleteModel.from_dict({}, Mock()) 