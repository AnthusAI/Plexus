import pytest
from unittest.mock import AsyncMock, patch
from click.testing import CliRunner

from plexus.cli.DatasetCommands import dataset
from plexus.dashboard.api.models.data_source import DataSource

@pytest.fixture
def runner():
    return CliRunner()

@pytest.mark.asyncio
@patch('plexus.cli.DatasetCommands.create_client')
@patch('plexus.cli.identifier_resolution.resolve_data_source')
async def test_load_command_success(mock_resolve, mock_create_client, runner):
    """Test the happy path of the load command."""
    
    # Arrange
    mock_client = AsyncMock()
    mock_create_client.return_value = mock_client
    
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
    mock_resolve.return_value = mock_data_source
    
    # Mock the rest of the chain
    mock_client.execute = AsyncMock(side_effect=[
        # Mock response for createDataSet
        {'createDataSet': {'id': 'new-ds-456', 'name': 'New Dataset', 'dataSourceId': 'ds-123'}},
        # Mock response for updateDataSet
        {'updateDataSet': {'id': 'new-ds-456', 'status': 'COMPLETED'}}
    ])
    
    # Mock data loading
    with patch('importlib.import_module') as mock_import:
        # Mock the module and the class
        mock_dummy_cache_module = AsyncMock()
        mock_dummy_cache_class = AsyncMock()
        mock_dummy_cache_instance = AsyncMock()
        
        # Make load_dataframe return a mock dataframe
        from pandas import DataFrame
        mock_dummy_cache_instance.load_dataframe.return_value = DataFrame({'col1': [1, 2], 'col2': [3, 4]})
        
        mock_dummy_cache_class.return_value = mock_dummy_cache_instance
        mock_dummy_cache_module.DummyDataCache = mock_dummy_cache_class
        mock_import.return_value = mock_dummy_cache_module
        
        # Mock S3 upload
        with patch('plexus.cli.DatasetCommands.get_amplify_bucket') as mock_get_bucket:
            mock_get_bucket.return_value = 'test-bucket'
            with patch('boto3.client') as mock_boto3:
                mock_s3_client = AsyncMock()
                mock_boto3.return_value = mock_s3_client

                # Act
                result = runner.invoke(dataset, ['load', '--source', 'test-source'])
    
    # Assert
    assert result.exit_code == 0
    mock_resolve.assert_called_once_with(mock_client, 'test-source')
    assert "Loaded dataframe with 2 rows" in result.output
    assert "DataSet record updated successfully" in result.output

@pytest.mark.asyncio
@patch('plexus.cli.DatasetCommands.create_client')
@patch('plexus.cli.identifier_resolution.resolve_data_source')
async def test_load_command_source_not_found(mock_resolve, mock_create_client, runner):
    """Test when the data source cannot be resolved."""
    
    # Arrange
    mock_client = AsyncMock()
    mock_create_client.return_value = mock_client
    mock_resolve.return_value = None
    
    # Act
    result = runner.invoke(dataset, ['load', '--source', 'non-existent'])
    
    # Assert
    assert result.exit_code == 0 # The command exits gracefully
    mock_resolve.assert_called_once_with(mock_client, 'non-existent')
    # The resolver logs the error, so we don't need to check stdout
    
@pytest.mark.asyncio
@patch('plexus.cli.DatasetCommands.create_client')
async def test_resolve_data_source_by_id(mock_create_client):
    """Test the resolver function's ability to find a DataSource by ID."""
    from plexus.cli.identifier_resolution import resolve_data_source
    
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
@patch('plexus.cli.DatasetCommands.create_client')
async def test_resolve_data_source_by_key(mock_create_client):
    """Test the resolver function's ability to find a DataSource by key."""
    from plexus.cli.identifier_resolution import resolve_data_source
    
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
@patch('plexus.cli.DatasetCommands.create_client')
async def test_resolve_data_source_by_name(mock_create_client):
    """Test the resolver function's ability to find a DataSource by name."""
    from plexus.cli.identifier_resolution import resolve_data_source
    
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