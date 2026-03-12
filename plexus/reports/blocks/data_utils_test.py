import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import tempfile
import shutil
import json
from typing import Dict, Any, Optional, Tuple

from plexus.reports.blocks.data_utils import DatasetResolver


@pytest.fixture
def mock_api_client():
    """Creates a mock API client."""
    client = MagicMock()
    client.account_id = "test-account-id"
    return client


@pytest.fixture
def temp_cache_dir():
    """Creates a temporary cache directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def dataset_resolver(mock_api_client):
    """Creates a DatasetResolver instance for testing."""
    return DatasetResolver(mock_api_client)


class TestDatasetResolver:
    """Tests for the DatasetResolver class."""
    
    def test_init(self, mock_api_client):
        """Test DatasetResolver initialization."""
        resolver = DatasetResolver(mock_api_client)
        assert resolver.client == mock_api_client
        
    @pytest.mark.asyncio
    async def test_resolve_and_cache_dataset_validation_both_params(self, dataset_resolver):
        """Test that providing both source and dataset raises ValueError."""
        with pytest.raises(ValueError, match="Cannot specify both 'source' and 'dataset' parameters"):
            await dataset_resolver.resolve_and_cache_dataset(source="test-source", dataset="test-dataset")
            
    @pytest.mark.asyncio
    async def test_resolve_and_cache_dataset_validation_no_params(self, dataset_resolver):
        """Test that providing neither source nor dataset raises ValueError."""
        with pytest.raises(ValueError, match="Must specify either 'source' or 'dataset' parameter"):
            await dataset_resolver.resolve_and_cache_dataset()
            
    @pytest.mark.asyncio
    async def test_resolve_and_cache_dataset_by_dataset_id(self, dataset_resolver):
        """Test resolving dataset by dataset ID."""
        with patch.object(dataset_resolver, '_resolve_dataset_by_id', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ("/path/to/dataset.parquet", {"id": "test-dataset"})
            
            result = await dataset_resolver.resolve_and_cache_dataset(dataset="test-dataset")
            
            assert result == ("/path/to/dataset.parquet", {"id": "test-dataset"})
            mock_resolve.assert_called_once_with("test-dataset", False)
            
    @pytest.mark.asyncio
    async def test_resolve_and_cache_dataset_by_source(self, dataset_resolver):
        """Test resolving dataset by source identifier."""
        with patch.object(dataset_resolver, '_resolve_dataset_by_source', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ("/path/to/dataset.parquet", {"source": "test-source"})
            
            result = await dataset_resolver.resolve_and_cache_dataset(source="test-source")
            
            assert result == ("/path/to/dataset.parquet", {"source": "test-source"})
            mock_resolve.assert_called_once_with("test-source", False)
            
    @pytest.mark.asyncio
    async def test_resolve_and_cache_dataset_fresh_flag(self, dataset_resolver):
        """Test that fresh flag is passed correctly."""
        with patch.object(dataset_resolver, '_resolve_dataset_by_id', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ("/path/to/dataset.parquet", {"id": "test-dataset"})
            
            await dataset_resolver.resolve_and_cache_dataset(dataset="test-dataset", fresh=True)
            
            mock_resolve.assert_called_once_with("test-dataset", True)
            
    @pytest.mark.asyncio
    async def test_resolve_dataset_by_id_success(self, dataset_resolver, temp_cache_dir):
        """Test successful dataset resolution by ID."""
        dataset_id = "test-dataset-123"
        
        # Mock the GraphQL response
        mock_response = {
            'getDataSet': {
                'id': dataset_id,
                'name': 'Test Dataset',
                'file': 's3://bucket/path/to/dataset.parquet',
                'dataSourceId': 'source-123',
                'scoreVersionId': 'score-version-123',
                'dataSourceVersionId': 'source-version-123',
                'createdAt': '2023-01-01T00:00:00Z',
                'updatedAt': '2023-01-02T00:00:00Z'
            }
        }
        
        dataset_resolver.client.execute.return_value = mock_response
        
        with patch.object(dataset_resolver, '_download_and_cache_file', new_callable=AsyncMock) as mock_download:
            mock_download.return_value = str(temp_cache_dir / "dataset.parquet")
            
            with patch.object(dataset_resolver, '_save_metadata') as mock_save_metadata:
                result = await dataset_resolver._resolve_dataset_by_id(dataset_id, False)
                
                assert result[0] == str(temp_cache_dir / "dataset.parquet")
                assert result[1]['id'] == dataset_id
                assert result[1]['name'] == 'Test Dataset'
                assert result[1]['source_type'] == 'dataset'
                
                mock_download.assert_called_once()
                mock_save_metadata.assert_called_once()
                
    @pytest.mark.asyncio
    async def test_resolve_dataset_by_id_not_found(self, dataset_resolver):
        """Test dataset resolution when dataset is not found."""
        dataset_id = "nonexistent-dataset"
        
        dataset_resolver.client.execute.return_value = {'getDataSet': None}
        
        result = await dataset_resolver._resolve_dataset_by_id(dataset_id, False)
        
        assert result == (None, None)
        
    @pytest.mark.asyncio
    async def test_resolve_dataset_by_id_no_file(self, dataset_resolver):
        """Test dataset resolution when dataset has no file."""
        dataset_id = "test-dataset-123"
        
        mock_response = {
            'getDataSet': {
                'id': dataset_id,
                'name': 'Test Dataset',
                'file': None  # No file attached
            }
        }
        
        dataset_resolver.client.execute.return_value = mock_response
        
        result = await dataset_resolver._resolve_dataset_by_id(dataset_id, False)
        
        assert result == (None, None)
        
    def test_save_metadata(self, dataset_resolver, temp_cache_dir):
        """Test saving metadata to file."""
        metadata_file = temp_cache_dir / "metadata.json"
        metadata = {"id": "test", "name": "Test Dataset"}
        
        dataset_resolver._save_metadata(metadata_file, metadata)
        
        assert metadata_file.exists()
        saved_data = json.loads(metadata_file.read_text())
        assert saved_data == metadata
        
    def test_load_metadata_success(self, dataset_resolver, temp_cache_dir):
        """Test loading metadata from file."""
        metadata_file = temp_cache_dir / "metadata.json"
        metadata = {"id": "test", "name": "Test Dataset"}
        metadata_file.write_text(json.dumps(metadata))
        
        result = dataset_resolver._load_metadata(metadata_file)
        
        assert result == metadata
        
    def test_load_metadata_file_not_exists(self, dataset_resolver, temp_cache_dir):
        """Test loading metadata when file doesn't exist."""
        metadata_file = temp_cache_dir / "nonexistent.json"
        
        result = dataset_resolver._load_metadata(metadata_file)
        
        assert result is None
        
    def test_load_metadata_invalid_json(self, dataset_resolver, temp_cache_dir):
        """Test loading metadata with invalid JSON."""
        metadata_file = temp_cache_dir / "metadata.json"
        metadata_file.write_text("invalid json content")
        
        result = dataset_resolver._load_metadata(metadata_file)
        
        assert result is None 