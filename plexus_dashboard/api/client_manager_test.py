import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from .client_manager import ClientManager, ClientContext
from .models.account import Account
from .models.scorecard import Scorecard

@pytest.fixture
def mock_client():
    """Create a mock client with required methods"""
    client = Mock()
    # Mock execute method with proper GraphQL response structure including all required fields
    client.execute.return_value = {
        'listAccounts': {'items': [{
            'id': 'acc-123',
            'key': 'test-account',
            'name': 'Test Account',
            'description': 'Test account description'
        }]},
        'listScorecards': {'items': [{
            'id': 'card-123',
            'key': 'test-scorecard',
            'name': 'Test Scorecard',
            'description': 'Test scorecard description',
            'accountId': 'acc-123',
            'externalId': 'ext-123'
        }]}
    }
    return client

@pytest.fixture
def mock_account():
    account = Mock(spec=Account)
    account.id = "acc-123"
    return account

@pytest.fixture
def mock_scorecard():
    scorecard = Mock(spec=Scorecard)
    scorecard.id = "card-123"
    return scorecard

def test_for_account_factory(mock_client):
    """Test creating manager with account context"""
    with patch('plexus_dashboard.api.client_manager.PlexusDashboardClient') as mock_client_class:
        mock_client_class.return_value = mock_client
        manager = ClientManager.for_account("test-account")
        assert manager.context.account_key == "test-account"
        assert manager.context.account_id is None

def test_for_scorecard_factory(mock_client):
    """Test creating manager with scorecard context"""
    with patch('plexus_dashboard.api.client_manager.PlexusDashboardClient') as mock_client_class:
        mock_client_class.return_value = mock_client
        manager = ClientManager.for_scorecard(
            account_key="test-account",
            scorecard_key="test-scorecard",
            score_name="accuracy"
        )
        assert manager.context.account_key == "test-account"
        assert manager.context.scorecard_key == "test-scorecard"
        assert manager.context.score_name == "accuracy"

def test_resolve_account_id_caching(mock_client, mock_account):
    """Test that account ID resolution uses caching"""
    with patch('plexus_dashboard.api.client_manager.PlexusDashboardClient') as mock_client_class:
        mock_client_class.return_value = mock_client
        manager = ClientManager.for_account("test-account")
        
        # Setup mock response
        mock_client.execute.return_value = {
            'listAccounts': {
                'items': [{
                    'id': 'acc-123',
                    'key': 'test-account',
                    'name': 'Test Account',
                    'description': 'Test account description'
                }]
            }
        }
        
        # First resolution should call API
        account_id = manager._resolve_account_id()
        assert account_id == "acc-123"
        mock_client.execute.assert_called_once()
        
        # Second resolution should use cache
        mock_client.execute.reset_mock()
        account_id = manager._resolve_account_id()
        assert account_id == "acc-123"
        mock_client.execute.assert_not_called()

def test_resolve_scorecard_id_caching(mock_client, mock_scorecard):
    """Test that scorecard ID resolution uses caching"""
    with patch('plexus_dashboard.api.client_manager.PlexusDashboardClient') as mock_client_class:
        mock_client_class.return_value = mock_client
        manager = ClientManager.for_scorecard("test-account", "test-scorecard")
        
        # Setup mock response
        mock_client.execute.return_value = {
            'listScorecards': {
                'items': [{
                    'id': 'card-123',
                    'key': 'test-scorecard',
                    'name': 'Test Scorecard',
                    'description': 'Test scorecard description',
                    'accountId': 'acc-123',
                    'externalId': 'ext-123'
                }]
            }
        }
        
        # First resolution should call API
        scorecard_id = manager._resolve_scorecard_id()
        assert scorecard_id == "card-123"
        mock_client.execute.assert_called_once()
        
        # Second resolution should use cache
        mock_client.execute.reset_mock()
        scorecard_id = manager._resolve_scorecard_id()
        assert scorecard_id == "card-123"
        mock_client.execute.assert_not_called()

def test_log_score_resolves_ids(mock_client, mock_account, mock_scorecard):
    """Test that log_score resolves necessary IDs"""
    with patch('plexus_dashboard.api.client_manager.PlexusDashboardClient') as mock_client_class:
        mock_client_class.return_value = mock_client
        manager = ClientManager.for_scorecard("test-account", "test-scorecard")
        
        # Setup mock responses
        mock_client.execute.side_effect = [
            # First call - resolve account
            {'listAccounts': {'items': [{
                'id': 'acc-123',
                'key': 'test-account',
                'name': 'Test Account',
                'description': 'Test account description'
            }]}},
            # Second call - resolve scorecard
            {'listScorecards': {'items': [{
                'id': 'card-123',
                'key': 'test-scorecard',
                'name': 'Test Scorecard',
                'description': 'Test scorecard description',
                'accountId': 'acc-123',
                'externalId': 'ext-123'
            }]}}
        ]
        
        # Log score
        manager.log_score(0.95, "item-123", confidence=0.87)
        
        # Verify ID resolution
        assert mock_client.execute.call_count == 2
        
        # Verify score logging
        mock_client.log_score.assert_called_once()
        call_kwargs = mock_client.log_score.call_args[1]
        assert call_kwargs['value'] == 0.95
        assert call_kwargs['itemId'] == "item-123"
        assert call_kwargs['accountId'] == "acc-123"
        assert call_kwargs['scorecardId'] == "card-123"
        assert call_kwargs['confidence'] == 0.87

def test_log_score_with_override(mock_client, mock_account, mock_scorecard):
    """Test logging score with context override"""
    with patch('plexus_dashboard.api.client_manager.PlexusDashboardClient') as mock_client_class:
        mock_client_class.return_value = mock_client
        manager = ClientManager.for_scorecard("test-account", "test-scorecard")
        
        # Setup mock responses
        mock_client.execute.side_effect = [
            # First call - resolve account
            {'listAccounts': {'items': [{
                'id': 'acc-123',
                'key': 'test-account',
                'name': 'Test Account',
                'description': 'Test account description'
            }]}},
            # Second call - resolve override scorecard
            {'listScorecards': {'items': [{
                'id': 'card-456',
                'key': 'other-scorecard',
                'name': 'Other Scorecard',
                'description': 'Other scorecard description',
                'accountId': 'acc-123',
                'externalId': 'ext-456'
            }]}}
        ]
        
        # Log score with override
        manager.log_score(
            0.95,
            "item-123",
            scorecard_key="other-scorecard",
            metadata={'source': 'test'}
        )
        
        # Verify score logging with metadata
        call_kwargs = mock_client.log_score.call_args[1]
        assert call_kwargs['scorecardId'] == "card-456"
        assert call_kwargs['metadata'] == {'source': 'test'} 