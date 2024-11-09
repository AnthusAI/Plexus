import pytest
import time
from unittest.mock import Mock, patch
from gql.transport.exceptions import TransportQueryError
from .client import PlexusDashboardClient

@pytest.fixture
def mock_env(monkeypatch):
    """Set up test environment variables"""
    monkeypatch.setenv('PLEXUS_API_URL', 'https://test.api')
    monkeypatch.setenv('PLEXUS_API_KEY', 'test-key')

@pytest.fixture
def mock_transport():
    with patch('plexus_dashboard.api.client.RequestsHTTPTransport') as mock:
        yield mock

@pytest.fixture
def mock_gql_client():
    with patch('plexus_dashboard.api.client.Client') as mock:
        yield mock

@pytest.fixture
def mock_score_result():
    with patch('plexus_dashboard.api.models.score_result.ScoreResult') as mock:
        yield mock

def test_client_requires_api_credentials():
    """Test that client requires API URL and key"""
    with pytest.raises(ValueError, match="Missing required API URL or API key"):
        PlexusDashboardClient()

def test_client_accepts_manual_credentials():
    """Test that client accepts manually provided credentials"""
    client = PlexusDashboardClient(
        api_url='https://test.api',
        api_key='test-key'
    )
    assert client.api_url == 'https://test.api'
    assert client.api_key == 'test-key'

def test_client_uses_environment_variables(mock_env):
    """Test that client uses environment variables"""
    client = PlexusDashboardClient()
    assert client.api_url == 'https://test.api'
    assert client.api_key == 'test-key'

def test_client_configures_transport_correctly(mock_env, mock_transport):
    """Test that transport is configured with correct headers"""
    PlexusDashboardClient()
    
    mock_transport.assert_called_once()
    transport_kwargs = mock_transport.call_args[1]
    
    assert transport_kwargs['url'] == 'https://test.api'
    assert transport_kwargs['headers']['x-api-key'] == 'test-key'
    assert transport_kwargs['headers']['Content-Type'] == 'application/json'
    assert transport_kwargs['verify'] is True
    assert transport_kwargs['retries'] == 3

def test_execute_handles_query_error(mock_env, mock_gql_client):
    """Test that execute handles GraphQL query errors"""
    client = PlexusDashboardClient()
    
    # Make the GQL client raise an error
    mock_gql_client.return_value.execute.side_effect = \
        TransportQueryError("Test error")
    
    with pytest.raises(Exception, match="GraphQL query failed: Test error"):
        client.execute("query { test }")

def test_execute_returns_query_result(mock_env, mock_gql_client):
    """Test that execute returns query results"""
    client = PlexusDashboardClient()
    
    expected_result = {'data': {'test': 'value'}}
    mock_gql_client.return_value.execute.return_value = expected_result
    
    result = client.execute("query { test }")
    assert result == expected_result

def test_background_logging_flushes_on_batch_size(mock_score_result):
    """Test that logs are flushed when batch size is reached"""
    client = PlexusDashboardClient(api_url="http://test", api_key="test")
    
    # Log enough items to trigger a batch flush
    for i in range(10):
        client.log_score(0.95, f"item-{i}", 
                        accountId="acc-1",
                        scoringJobId="job-1",
                        scorecardId="card-1")
    
    # Give the background thread time to process
    time.sleep(0.1)
    
    # Verify batch_create was called with all items
    mock_score_result.batch_create.assert_called_once()
    args = mock_score_result.batch_create.call_args[0]
    assert len(args[1]) == 10

def test_background_logging_flushes_on_shutdown(mock_score_result):
    """Test that remaining logs are flushed when client is destroyed"""
    client = PlexusDashboardClient(api_url="http://test", api_key="test")
    
    # Log a few items (less than batch size)
    for i in range(5):
        client.log_score(0.95, f"item-{i}", 
                        accountId="acc-1",
                        scoringJobId="job-1",
                        scorecardId="card-1")
    
    # Explicitly flush (simulating shutdown)
    client.flush()
    
    # Verify items were flushed
    mock_score_result.batch_create.assert_called_once()
    args = mock_score_result.batch_create.call_args[0]
    assert len(args[1]) == 5

def test_background_logging_handles_errors_gracefully(mock_score_result):
    """Test that logging errors don't affect the main thread"""
    client = PlexusDashboardClient(api_url="http://test", api_key="test")
    
    # Make batch_create raise an exception
    mock_score_result.batch_create.side_effect = Exception("Test error")
    
    # Log should not raise even though flush will fail
    client.log_score(0.95, "item-1", 
                    accountId="acc-1",
                    scoringJobId="job-1",
                    scorecardId="card-1")
    
    # Flush should also not raise
    client.flush()
    
    # Verify batch_create was attempted
    mock_score_result.batch_create.assert_called_once()

def test_immediate_logging_creates_score_result(mock_score_result):
    """Test that immediate logging creates a score result without batching"""
    client = PlexusDashboardClient(api_url="http://test", api_key="test")
    
    # Log a score for immediate processing
    client.log_score(
        value=0.95,
        item_id="item-1",
        immediate=True,
        accountId="acc-1",
        scoringJobId="job-1",
        scorecardId="card-1"
    )
    
    # Give the background thread time to complete
    time.sleep(0.1)
    
    # Verify create was called (not batch_create)
    mock_score_result.create.assert_called_once()
    args = mock_score_result.create.call_args
    assert args[1]['value'] == 0.95
    assert args[1]['itemId'] == "item-1"

def test_score_logging_with_different_configs(mock_score_result):
    """Test score logging with different configurations"""
    client = PlexusDashboardClient(api_url="http://test", api_key="test")
    
    # Test immediate logging
    client.log_score(0.95, "item-1", immediate=True,
                    accountId="acc-1",
                    scoringJobId="job-1",
                    scorecardId="card-1")
    
    time.sleep(0.1)  # Give thread time to complete
    mock_score_result.create.assert_called_once()
    
    # Test default batch size (10)
    for i in range(10):
        client.log_score(0.95, f"item-{i}", 
                        accountId="acc-1",
                        scoringJobId="job-1",
                        scorecardId="card-1")
    
    time.sleep(0.1)  # Give batch time to process
    mock_score_result.batch_create.assert_called_once()
    args = mock_score_result.batch_create.call_args[0]
    assert len(args[1]) == 10  # Verify default batch size