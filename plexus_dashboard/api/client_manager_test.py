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

def test_client_caches_resolved_ids(mock_client):
    """Test that resolved IDs are cached"""
    with patch('plexus_dashboard.api.client_manager.PlexusDashboardClient') as mock_client_class:
        mock_client_class.return_value = mock_client
        manager = ClientManager.for_account("test-account")
        
        # First call should resolve ID
        account_id = manager._resolve_account_id()
        assert mock_client.execute.call_count == 1
        
        # Second call should use cache
        account_id_2 = manager._resolve_account_id()
        assert mock_client.execute.call_count == 1
        assert account_id == account_id_2

def test_client_handles_missing_ids(mock_client):
    """Test handling of missing IDs"""
    with patch('plexus_dashboard.api.client_manager.PlexusDashboardClient') as mock_client_class:
        mock_client_class.return_value = mock_client
        manager = ClientManager.for_account("test-account")
        
        # Mock empty response
        mock_client.execute.return_value = {
            'listAccounts': {'items': []}
        }
        
        with pytest.raises(ValueError, match="No account found"):
            manager._resolve_account_id()

def test_client_batches_score_logs(mock_client):
    """Test that score logging uses batching"""
    with patch('plexus_dashboard.api.client_manager.PlexusDashboardClient') as mock_client_class:
        mock_client_class.return_value = mock_client
        manager = ClientManager.for_account("test-account")
        
        # Setup account resolution
        mock_client.execute.return_value = {
            'listAccounts': {'items': [{
                'id': 'acc-123',
                'key': 'test-account',
                'name': 'Test Account',
                'description': 'Test account description'
            }]}
        }
        
        # Log multiple scores
        for i in range(3):
            manager.log_score(0.95, f"item-{i}", batch_size=5)
        
        # Verify batching behavior
        assert mock_client.log_score.call_count == 3
        for i, call in enumerate(mock_client.log_score.call_args_list):
            assert call[1]['itemId'] == f"item-{i}"
            assert call[1]['batch_size'] == 5

def test_client_handles_immediate_logging(mock_client):
    """Test immediate (non-batched) score logging"""
    with patch('plexus_dashboard.api.client_manager.PlexusDashboardClient') as mock_client_class:
        mock_client_class.return_value = mock_client
        manager = ClientManager.for_account("test-account")
        
        # Setup account resolution
        mock_client.execute.return_value = {
            'listAccounts': {'items': [{
                'id': 'acc-123',
                'key': 'test-account',
                'name': 'Test Account',
                'description': 'Test account description'
            }]}
        }
        
        # Log score with immediate=True
        manager.log_score(0.95, "item-123", immediate=True)
        
        # Verify immediate logging
        mock_client.log_score.assert_called_once()
        assert mock_client.log_score.call_args[1]['immediate'] is True

def test_client_maintains_context(mock_client):
    """Test that client maintains context between calls"""
    with patch('plexus_dashboard.api.client_manager.PlexusDashboardClient') as mock_client_class:
        mock_client_class.return_value = mock_client
        manager = ClientManager.for_scorecard(
            account_key="test-account",
            scorecard_key="test-scorecard"
        )
        
        # Setup mock responses
        mock_client.execute.side_effect = [
            # Account resolution
            {'listAccounts': {'items': [{
                'id': 'acc-123',
                'key': 'test-account',
                'name': 'Test Account',
                'description': 'Test account description'
            }]}},
            # Scorecard resolution
            {'listScorecards': {'items': [{
                'id': 'card-123',
                'key': 'test-scorecard',
                'name': 'Test Scorecard',
                'description': 'Test scorecard description',
                'accountId': 'acc-123',
                'externalId': 'ext-123'
            }]}}
        ]
        
        # Log multiple scores - should reuse resolved IDs
        manager.log_score(0.95, "item-1")
        manager.log_score(0.85, "item-2")
        
        # Verify ID resolution happened only once per type
        assert mock_client.execute.call_count == 2
        
        # Verify both scores used same IDs
        calls = mock_client.log_score.call_args_list
        assert calls[0][1]['accountId'] == calls[1][1]['accountId']
        assert calls[0][1]['scorecardId'] == calls[1][1]['scorecardId'] 