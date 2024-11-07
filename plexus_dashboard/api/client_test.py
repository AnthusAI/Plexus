import pytest
from unittest.mock import Mock, patch
from gql.transport.exceptions import TransportQueryError
from .client import PlexusAPIClient

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

def test_client_requires_api_credentials():
    """Test that client requires API URL and key"""
    with pytest.raises(ValueError, match="Missing required API URL or API key"):
        PlexusAPIClient()

def test_client_accepts_manual_credentials():
    """Test that client accepts manually provided credentials"""
    client = PlexusAPIClient(
        api_url='https://test.api',
        api_key='test-key'
    )
    assert client.api_url == 'https://test.api'
    assert client.api_key == 'test-key'

def test_client_uses_environment_variables(mock_env):
    """Test that client uses environment variables"""
    client = PlexusAPIClient()
    assert client.api_url == 'https://test.api'
    assert client.api_key == 'test-key'

def test_client_configures_transport_correctly(mock_env, mock_transport):
    """Test that transport is configured with correct headers"""
    PlexusAPIClient()
    
    mock_transport.assert_called_once()
    transport_kwargs = mock_transport.call_args[1]
    
    assert transport_kwargs['url'] == 'https://test.api'
    assert transport_kwargs['headers']['x-api-key'] == 'test-key'
    assert transport_kwargs['headers']['Content-Type'] == 'application/json'
    assert transport_kwargs['verify'] is True
    assert transport_kwargs['retries'] == 3

def test_execute_handles_query_error(mock_env, mock_gql_client):
    """Test that execute handles GraphQL query errors"""
    client = PlexusAPIClient()
    
    # Make the GQL client raise an error
    mock_gql_client.return_value.execute.side_effect = \
        TransportQueryError("Test error")
    
    with pytest.raises(Exception, match="GraphQL query failed: Test error"):
        client.execute("query { test }")

def test_execute_returns_query_result(mock_env, mock_gql_client):
    """Test that execute returns query results"""
    client = PlexusAPIClient()
    
    expected_result = {'data': {'test': 'value'}}
    mock_gql_client.return_value.execute.return_value = expected_result
    
    result = client.execute("query { test }")
    assert result == expected_result 