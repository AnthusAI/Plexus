import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from click.testing import CliRunner
import os

from plexus.cli.dataset.datasets import dataset
from plexus.dashboard.api.models.data_source import DataSource

@pytest.fixture
def runner():
    return CliRunner()

@patch('plexus.cli.dataset.datasets.resolve_data_source')  # Patch in the right module  
def test_load_command_success(mock_resolve, runner):
    """Test the happy path of the load command."""
    
    # Arrange - set up environment variables for the client
    with patch.dict('os.environ', {
        'PLEXUS_API_URL': 'https://test-api.example.com',
        'PLEXUS_API_KEY': 'test-key-123'
    }):
        # Create a mock DataSource
        mock_data_source = DataSource(
            id='ds-123',
            name='Test Source',
            key='test-source',
            yamlConfiguration="""
            data:
                class: plexus.data.dummy.DummyDataCache
                parameters:
                    rows: 10
            """,
            owner='account-123'
        )
        
        # Add the attributes that are needed but not in constructor
        mock_data_source.accountId = 'account-123'
        mock_data_source.currentVersionId = 'version-123'
        mock_data_source.scoreId = 'score-123'
        mock_data_source.scorecardId = 'scorecard-123'
        
        mock_resolve.return_value = mock_data_source
        
        # Mock all the external dependencies
        with patch('plexus.cli.dataset.datasets.PlexusDashboardClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            # Mock the GraphQL responses - execute is synchronous, not async
            mock_client.execute = MagicMock(side_effect=[
                # Mock response for score query
                {'getScore': {'id': 'score-123', 'name': 'Test Score', 'championVersionId': 'score-version-123'}},
                # Mock response for createDataSet
                {'createDataSet': {'id': 'new-ds-456', 'name': 'New Dataset', 'dataSourceVersionId': 'version-123', 'scoreVersionId': 'score-version-123'}},
                # Mock response for updateDataSet
                {'updateDataSet': {'id': 'new-ds-456', 'file': 'datasets/account-123/ds-123/new-ds-456/test.parquet'}}
            ])
            
            # Mock data loading
            with patch('importlib.import_module') as mock_import:
                mock_dummy_cache_module = MagicMock()
                mock_dummy_cache_class = MagicMock()
                mock_dummy_cache_instance = MagicMock()
                
                from pandas import DataFrame
                mock_dummy_cache_instance.load_dataframe.return_value = DataFrame({'col1': [1, 2], 'col2': [3, 4]})
                
                mock_dummy_cache_class.return_value = mock_dummy_cache_instance
                mock_dummy_cache_module.DummyDataCache = mock_dummy_cache_class
                mock_import.return_value = mock_dummy_cache_module
                
                # Mock S3 upload
                with patch('plexus.cli.dataset.datasets.get_amplify_bucket') as mock_get_bucket:
                    mock_get_bucket.return_value = 'test-bucket'
                    with patch('boto3.client') as mock_boto3:
                        mock_s3_client = MagicMock()
                        mock_boto3.return_value = mock_s3_client

                        # Act
                        result = runner.invoke(dataset, ['load', '--source', 'test-source'])
        
        # Assert - just check that the command completed successfully
        assert result.exit_code == 0
        # Verify that resolve_data_source was called
        mock_resolve.assert_called_once()

@patch('plexus.cli.dataset.datasets.create_client')
@patch('plexus.cli.dataset.datasets.resolve_data_source')  # Patch in the right module
def test_load_command_source_not_found(mock_resolve, mock_create_client, runner):
    """Test when the data source cannot be resolved."""
    
    # Arrange
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_resolve.return_value = None
    
    # Act
    result = runner.invoke(dataset, ['load', '--source', 'non-existent'])
    
    # Assert
    assert result.exit_code == 0 # The command exits gracefully
    mock_resolve.assert_called_once_with(mock_client, 'non-existent')
    
@pytest.mark.asyncio
@patch('plexus.cli.dataset.datasets.create_client')
async def test_resolve_data_source_by_id(mock_create_client):
    """Test the resolver function's ability to find a DataSource by ID."""
    from plexus.cli.shared.identifier_resolution import resolve_data_source
    
    # Arrange
    mock_client = AsyncMock()
    mock_create_client.return_value = mock_client
    
    mock_data_source = DataSource(id='ds-123', name='Test Source')
    
    with patch.object(DataSource, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_data_source
        
        # Act
        result = await resolve_data_source(mock_client, 'ds-123')
        
        # Assert
        mock_get.assert_called_once_with(mock_client, 'ds-123')
        assert result is not None
        assert result.id == 'ds-123'
        
@pytest.mark.asyncio
@patch('plexus.cli.dataset.datasets.create_client')
async def test_resolve_data_source_by_key(mock_create_client):
    """Test the resolver function's ability to find a DataSource by key."""
    from plexus.cli.shared.identifier_resolution import resolve_data_source
    
    # Arrange
    mock_client = AsyncMock()
    mock_create_client.return_value = mock_client
    
    mock_data_source = DataSource(id='ds-123', name='Test Source', key='test-key')
    
    with patch.object(DataSource, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None # It will fail the ID lookup
        with patch.object(DataSource, 'list_by_key', new_callable=AsyncMock) as mock_list_by_key:
            mock_list_by_key.return_value = [mock_data_source]
            
            # Act
            result = await resolve_data_source(mock_client, 'test-key')
            
            # Assert
            mock_list_by_key.assert_called_once_with(mock_client, 'test-key')
            assert result is not None
            assert result.key == 'test-key'
            
@pytest.mark.asyncio
@patch('plexus.cli.dataset.datasets.create_client')
async def test_resolve_data_source_by_name(mock_create_client):
    """Test the resolver function's ability to find a DataSource by name."""
    from plexus.cli.shared.identifier_resolution import resolve_data_source
    
    # Arrange
    mock_client = AsyncMock()
    mock_create_client.return_value = mock_client
    
    mock_data_source = DataSource(id='ds-123', name='Test Source', key='test-key')
    
    with patch.object(DataSource, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None # It will fail the ID lookup
        with patch.object(DataSource, 'list_by_key', new_callable=AsyncMock) as mock_list_by_key:
            mock_list_by_key.return_value = [] # It will fail the key lookup
            with patch.object(DataSource, 'list_by_name', new_callable=AsyncMock) as mock_list_by_name:
                mock_list_by_name.return_value = [mock_data_source]
                
                # Act
                result = await resolve_data_source(mock_client, 'Test Source')
                
                # Assert
                mock_list_by_name.assert_called_once_with(mock_client, 'Test Source')
                assert result is not None
                assert result.name == 'Test Source' 