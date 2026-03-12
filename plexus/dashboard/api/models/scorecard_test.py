"""
Test suite for Scorecard model.

Tests all lookup methods and data handling for the Scorecard model.
"""
import pytest
from unittest.mock import Mock
from .scorecard import Scorecard


@pytest.fixture
def mock_client():
    """Create a mock API client."""
    return Mock()


@pytest.fixture
def sample_scorecard_data():
    """Sample scorecard data for testing."""
    return {
        'id': 'scorecard-123',
        'name': 'Test Scorecard',
        'key': 'test-scorecard',
        'externalId': 'ext-123',
        'accountId': 'account-456',
        'description': 'A test scorecard for unit tests'
    }


@pytest.fixture
def sample_scorecard(mock_client, sample_scorecard_data):
    """Create a sample Scorecard instance."""
    return Scorecard.from_dict(sample_scorecard_data, mock_client)


class TestScorecardFromDict:
    """Test Scorecard.from_dict() method."""
    
    def test_from_dict_with_all_fields(self, mock_client, sample_scorecard_data):
        """Test creating a Scorecard from dict with all fields."""
        scorecard = Scorecard.from_dict(sample_scorecard_data, mock_client)
        
        assert scorecard.id == sample_scorecard_data['id']
        assert scorecard.name == sample_scorecard_data['name']
        assert scorecard.key == sample_scorecard_data['key']
        assert scorecard.externalId == sample_scorecard_data['externalId']
        assert scorecard.accountId == sample_scorecard_data['accountId']
        assert scorecard.description == sample_scorecard_data['description']
    
    def test_from_dict_without_description(self, mock_client):
        """Test creating a Scorecard without optional description field."""
        minimal_data = {
            'id': 'scorecard-123',
            'name': 'Test Scorecard',
            'key': 'test-scorecard',
            'externalId': 'ext-123',
            'accountId': 'account-456'
        }
        
        scorecard = Scorecard.from_dict(minimal_data, mock_client)
        
        assert scorecard.id == minimal_data['id']
        assert scorecard.name == minimal_data['name']
        assert scorecard.description is None


class TestScorecardGetById:
    """Test Scorecard.get_by_id() method."""
    
    def test_get_by_id_success(self, mock_client, sample_scorecard_data):
        """Test successfully getting a scorecard by ID."""
        mock_client.execute.return_value = {
            'getScorecard': sample_scorecard_data
        }
        
        scorecard = Scorecard.get_by_id('scorecard-123', mock_client)
        
        assert scorecard.id == sample_scorecard_data['id']
        assert scorecard.name == sample_scorecard_data['name']
        
        # Verify the query was called correctly
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        variables = call_args[0][1]
        
        assert 'getScorecard' in query
        assert variables == {'id': 'scorecard-123'}
    
    def test_get_by_id_not_found(self, mock_client):
        """Test get_by_id when scorecard doesn't exist."""
        mock_client.execute.side_effect = Exception("Failed to get Scorecard scorecard-999")
        
        with pytest.raises(Exception):
            Scorecard.get_by_id('scorecard-999', mock_client)


class TestScorecardGetByKey:
    """Test Scorecard.get_by_key() method."""
    
    def test_get_by_key_success(self, mock_client, sample_scorecard_data):
        """Test successfully getting a scorecard by key."""
        mock_client.execute.return_value = {
            'listScorecards': {
                'items': [sample_scorecard_data]
            }
        }
        
        scorecard = Scorecard.get_by_key('test-scorecard', mock_client)
        
        assert scorecard.key == 'test-scorecard'
        
        # Verify the query was called correctly
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        variables = call_args[0][1]
        
        assert 'listScorecards' in query
        assert variables == {'key': 'test-scorecard'}
    
    def test_get_by_key_not_found(self, mock_client):
        """Test get_by_key when scorecard doesn't exist."""
        mock_client.execute.return_value = {
            'listScorecards': {
                'items': []
            }
        }
        
        with pytest.raises(ValueError, match="No scorecard found with key"):
            Scorecard.get_by_key('nonexistent-key', mock_client)


class TestScorecardGetByName:
    """Test Scorecard.get_by_name() method."""
    
    def test_get_by_name_success(self, mock_client, sample_scorecard_data):
        """Test successfully getting a scorecard by name."""
        mock_client.execute.return_value = {
            'listScorecards': {
                'items': [sample_scorecard_data]
            }
        }
        
        scorecard = Scorecard.get_by_name('Test Scorecard', mock_client)
        
        assert scorecard.name == 'Test Scorecard'
        
        # Verify the query was called correctly
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        variables = call_args[0][1]
        
        assert 'listScorecards' in query
        assert 'filter:' in query
        assert variables == {'name': 'Test Scorecard'}
    
    def test_get_by_name_not_found(self, mock_client):
        """Test get_by_name when scorecard doesn't exist."""
        mock_client.execute.return_value = {
            'listScorecards': {
                'items': []
            }
        }
        
        with pytest.raises(ValueError, match="No scorecard found with name"):
            Scorecard.get_by_name('Nonexistent Scorecard', mock_client)


class TestScorecardGetByExternalId:
    """Test Scorecard.get_by_external_id() method."""
    
    def test_get_by_external_id_success(self, mock_client, sample_scorecard_data):
        """Test successfully getting a scorecard by external ID."""
        mock_client.execute.return_value = {
            'listScorecards': {
                'items': [sample_scorecard_data]
            }
        }
        
        scorecard = Scorecard.get_by_external_id('ext-123', mock_client)
        
        assert scorecard.externalId == 'ext-123'
        
        # Verify the query was called correctly
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        variables = call_args[0][1]
        
        assert 'listScorecards' in query
        assert 'filter:' in query
        assert 'externalId:' in query
        assert variables == {'externalId': 'ext-123'}
    
    def test_get_by_external_id_not_found(self, mock_client):
        """Test get_by_external_id when scorecard doesn't exist."""
        mock_client.execute.return_value = {
            'listScorecards': {
                'items': []
            }
        }
        
        with pytest.raises(ValueError, match="No scorecard found with external ID"):
            Scorecard.get_by_external_id('nonexistent-ext', mock_client)


class TestScorecardGetByAccountAndExternalId:
    """Test Scorecard.get_by_account_and_external_id() method."""
    
    def test_get_by_account_and_external_id_success(self, mock_client, sample_scorecard_data):
        """Test successfully getting a scorecard by account ID and external ID."""
        mock_client.execute.return_value = {
            'listScorecardByAccountIdAndExternalId': {
                'items': [sample_scorecard_data]
            }
        }
        
        scorecard = Scorecard.get_by_account_and_external_id('account-456', 'ext-123', mock_client)
        
        assert scorecard is not None
        assert scorecard.accountId == 'account-456'
        assert scorecard.externalId == 'ext-123'
        assert isinstance(scorecard, Scorecard)
        
        # Verify the query was called correctly
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        variables = call_args[0][1]
        
        assert 'listScorecardByAccountIdAndExternalId' in query
        assert variables == {
            'accountId': 'account-456',
            'externalId': 'ext-123'
        }
    
    def test_get_by_account_and_external_id_not_found(self, mock_client):
        """Test get_by_account_and_external_id when scorecard doesn't exist."""
        mock_client.execute.return_value = {
            'listScorecardByAccountIdAndExternalId': {
                'items': []
            }
        }
        
        scorecard = Scorecard.get_by_account_and_external_id('account-456', 'nonexistent', mock_client)
        
        assert scorecard is None
    
    def test_get_by_account_and_external_id_uses_gsi(self, mock_client, sample_scorecard_data):
        """Test that get_by_account_and_external_id uses the correct GSI."""
        mock_client.execute.return_value = {
            'listScorecardByAccountIdAndExternalId': {
                'items': [sample_scorecard_data]
            }
        }
        
        Scorecard.get_by_account_and_external_id('account-456', 'ext-123', mock_client)
        
        # Verify it uses the GSI query with limit
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        
        assert 'listScorecardByAccountIdAndExternalId' in query
        assert 'limit: 1' in query
        assert 'accountId: $accountId' in query
        assert 'externalId: {eq: $externalId}' in query
    
    def test_get_by_account_and_external_id_returns_full_scorecard(self, mock_client, sample_scorecard_data):
        """Test that the method returns a full Scorecard object with all fields."""
        mock_client.execute.return_value = {
            'listScorecardByAccountIdAndExternalId': {
                'items': [sample_scorecard_data]
            }
        }
        
        scorecard = Scorecard.get_by_account_and_external_id('account-456', 'ext-123', mock_client)
        
        # Should return full Scorecard object, not just dict
        assert isinstance(scorecard, Scorecard)
        assert scorecard.id == sample_scorecard_data['id']
        assert scorecard.name == sample_scorecard_data['name']
        assert scorecard.key == sample_scorecard_data['key']
        assert scorecard.description == sample_scorecard_data['description']
    
    def test_get_by_account_and_external_id_empty_result(self, mock_client):
        """Test handling of empty result from GraphQL."""
        mock_client.execute.return_value = {
            'listScorecardByAccountIdAndExternalId': {
                'items': []
            }
        }
        
        scorecard = Scorecard.get_by_account_and_external_id('account-999', 'ext-999', mock_client)
        
        assert scorecard is None


class TestScorecardListByExternalId:
    """Test Scorecard.list_by_external_id() method."""
    
    def test_list_by_external_id_success(self, mock_client, sample_scorecard_data):
        """Test successfully getting a scorecard using list_by_external_id."""
        mock_client.execute.return_value = {
            'listScorecards': {
                'items': [sample_scorecard_data]
            }
        }
        
        scorecard = Scorecard.list_by_external_id('ext-123', mock_client)
        
        assert scorecard is not None
        assert scorecard.externalId == 'ext-123'
    
    def test_list_by_external_id_not_found(self, mock_client):
        """Test list_by_external_id returns None when not found."""
        mock_client.execute.return_value = {
            'listScorecards': {
                'items': []
            }
        }
        
        scorecard = Scorecard.list_by_external_id('nonexistent', mock_client)
        
        # Should return None, not raise exception
        assert scorecard is None


class TestScorecardFields:
    """Test Scorecard.fields() method."""
    
    def test_fields_includes_required_fields(self):
        """Test that fields() includes all required fields."""
        fields = Scorecard.fields()
        
        required_fields = [
            'id', 'name', 'key', 'externalId', 'accountId'
        ]
        
        for field in required_fields:
            assert field in fields, f"Required field '{field}' missing from fields()"
    
    def test_fields_includes_optional_fields(self):
        """Test that fields() includes optional fields."""
        fields = Scorecard.fields()
        
        # Description is optional
        assert 'description' in fields


class TestScorecardIntegration:
    """Integration tests for Scorecard model."""
    
    def test_scorecard_lookup_chain(self, mock_client, sample_scorecard_data):
        """Test that different lookup methods can find the same scorecard."""
        # Setup mock to return the same scorecard for different lookups
        mock_client.execute.return_value = {
            'listScorecards': {'items': [sample_scorecard_data]}
        }
        by_key = Scorecard.get_by_key('test-scorecard', mock_client)
        
        mock_client.execute.return_value = {
            'listScorecards': {'items': [sample_scorecard_data]}
        }
        by_name = Scorecard.get_by_name('Test Scorecard', mock_client)
        by_external = Scorecard.get_by_external_id('ext-123', mock_client)
        
        # All lookups should find the same scorecard
        assert by_key.id == by_name.id == by_external.id == 'scorecard-123'
    
    def test_scorecard_with_client_reference(self, mock_client, sample_scorecard_data):
        """Test that Scorecard maintains reference to its client."""
        scorecard = Scorecard.from_dict(sample_scorecard_data, mock_client)
        
        assert scorecard._client is mock_client
    
    def test_account_scoped_lookup_vs_global_lookup(self, mock_client, sample_scorecard_data):
        """Test that account-scoped lookup is more specific than global lookup."""
        # Account-scoped lookup should use GSI
        mock_client.execute.return_value = {
            'listScorecardByAccountIdAndExternalId': {'items': [sample_scorecard_data]}
        }
        
        account_scoped = Scorecard.get_by_account_and_external_id('account-456', 'ext-123', mock_client)
        
        # Verify it used the account-scoped GSI
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        assert 'listScorecardByAccountIdAndExternalId' in query
        
        # Global lookup should use different query
        mock_client.execute.return_value = {
            'listScorecards': {'items': [sample_scorecard_data]}
        }
        
        global_lookup = Scorecard.get_by_external_id('ext-123', mock_client)
        
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        assert 'listScorecards' in query
        
        # Both should find the same scorecard
        assert account_scoped.id == global_lookup.id


class TestScorecardErrorHandling:
    """Test error handling in Scorecard model."""
    
    def test_get_by_key_raises_on_not_found(self, mock_client):
        """Test that get_by_key raises ValueError when not found."""
        mock_client.execute.return_value = {
            'listScorecards': {'items': []}
        }
        
        with pytest.raises(ValueError):
            Scorecard.get_by_key('nonexistent', mock_client)
    
    def test_get_by_name_raises_on_not_found(self, mock_client):
        """Test that get_by_name raises ValueError when not found."""
        mock_client.execute.return_value = {
            'listScorecards': {'items': []}
        }
        
        with pytest.raises(ValueError):
            Scorecard.get_by_name('Nonexistent', mock_client)
    
    def test_get_by_external_id_raises_on_not_found(self, mock_client):
        """Test that get_by_external_id raises ValueError when not found."""
        mock_client.execute.return_value = {
            'listScorecards': {'items': []}
        }
        
        with pytest.raises(ValueError):
            Scorecard.get_by_external_id('nonexistent', mock_client)
    
    def test_list_by_external_id_returns_none_on_not_found(self, mock_client):
        """Test that list_by_external_id returns None instead of raising."""
        mock_client.execute.return_value = {
            'listScorecards': {'items': []}
        }
        
        # Should not raise, should return None
        result = Scorecard.list_by_external_id('nonexistent', mock_client)
        assert result is None
    
    def test_get_by_account_and_external_id_returns_none_on_not_found(self, mock_client):
        """Test that get_by_account_and_external_id returns None instead of raising."""
        mock_client.execute.return_value = {
            'listScorecardByAccountIdAndExternalId': {'items': []}
        }
        
        # Should not raise, should return None
        result = Scorecard.get_by_account_and_external_id('account-999', 'ext-999', mock_client)
        assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

