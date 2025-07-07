"""
Utility functions for data source and dataset management in report blocks.
"""
import os
import logging
import shutil
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import pandas as pd
import importlib
import boto3
from botocore.exceptions import NoCredentialsError

from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.data_source import DataSource
from plexus.cli.identifier_resolution import resolve_data_source

logger = logging.getLogger(__name__)

class DatasetResolver:
    """Handles resolution and caching of datasets from DataSource or DataSet records."""
    
    def __init__(self, client: PlexusDashboardClient):
        self.client = client
        
    async def resolve_and_cache_dataset(
        self, 
        source: Optional[str] = None, 
        dataset: Optional[str] = None,
        fresh: bool = False
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Resolve a dataset from either a DataSource or DataSet identifier and cache locally.
        
        Args:
            source: DataSource identifier (name, key, or ID)
            dataset: DataSet ID 
            fresh: If True, bypass cache and fetch from API
            
        Returns:
            Tuple of (local_file_path, metadata_dict) or (None, None) if failed
        """
        if source and dataset:
            raise ValueError("Cannot specify both 'source' and 'dataset' parameters")
        if not source and not dataset:
            raise ValueError("Must specify either 'source' or 'dataset' parameter")
            
        logger.info(f"🎯 DatasetResolver.resolve_and_cache_dataset: source='{source}', dataset='{dataset}', fresh={fresh}")
            
        if dataset:
            logger.info(f"🔍 Resolving by dataset ID: {dataset}")
            return await self._resolve_dataset_by_id(dataset, fresh)
        else:
            logger.info(f"🔍 Resolving by source identifier: {source}")
            return await self._resolve_dataset_by_source(source, fresh)
    
    async def _resolve_dataset_by_id(self, dataset_id: str, fresh: bool) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Resolve dataset by DataSet ID."""
        logger.info(f"Resolving dataset by ID: {dataset_id}")
        
        # Check local cache first (unless fresh=True)  
        cache_dir = Path(".plexus") / "cache" / "datasets" / dataset_id
        cache_file = cache_dir / "dataset.parquet"
        metadata_file = cache_dir / "metadata.json"
        
        if not fresh and cache_file.exists() and metadata_file.exists():
            logger.info(f"Using cached dataset: {cache_file}")
            metadata = self._load_metadata(metadata_file)
            return str(cache_file), metadata
        
        # Fetch dataset record from API
        try:
            query = """
            query GetDataSet($id: ID!) {
                getDataSet(id: $id) {
                    id
                    name
                    file
                    dataSourceId
                    scoreVersionId
                    dataSourceVersionId
                    createdAt
                    updatedAt
                }
            }
            """
            response = self.client.execute(query, {"id": dataset_id})
            dataset_record = response.get('getDataSet')
            
            if not dataset_record:
                logger.error(f"DataSet not found: {dataset_id}")
                return None, None
                
            if not dataset_record.get('file'):
                logger.error(f"DataSet {dataset_id} has no file attached")
                return None, None
                
            # Download and cache the file
            s3_path = dataset_record['file']
            local_path = await self._download_and_cache_file(
                s3_path, cache_file, dataset_id, dataset_record
            )
            
            if local_path:
                metadata = {
                    "id": dataset_record['id'],
                    "name": dataset_record['name'],
                    "source_type": "dataset",
                    "dataSourceId": dataset_record.get('dataSourceId'),
                    "scoreVersionId": dataset_record.get('scoreVersionId'),
                    "dataSourceVersionId": dataset_record.get('dataSourceVersionId'),
                    "createdAt": dataset_record.get('createdAt'),
                    "updatedAt": dataset_record.get('updatedAt'),
                    "s3_path": s3_path
                }
                self._save_metadata(metadata_file, metadata)
                return local_path, metadata
                
        except Exception as e:
            logger.error(f"Error resolving dataset {dataset_id}: {e}")
            
        return None, None
    
    async def _resolve_dataset_by_source(self, source_id: str, fresh: bool) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Resolve dataset by DataSource identifier."""
        logger.info(f"Resolving dataset by DataSource: {source_id}")
        
        # Resolve DataSource with currentVersionId
        data_source = await resolve_data_source(self.client, source_id)
        if not data_source:
            logger.error(f"DataSource not found: {source_id}")
            return None, None
            
        # Get the full DataSource record with currentVersionId
        try:
            query = """
            query GetDataSource($id: ID!) {
                getDataSource(id: $id) {
                    id
                    name
                    key
                    description
                    yamlConfiguration
                    currentVersionId
                    createdAt
                    updatedAt
                }
            }
            """
            response = self.client.execute(query, {"id": data_source.id})
            full_data_source = response.get('getDataSource')
            
            if not full_data_source:
                logger.error(f"Could not fetch full DataSource record for ID: {data_source.id}")
                return None, None
                
            logger.info(f"✅ Found DataSource: {full_data_source['name']} (ID: {full_data_source['id']})")
            logger.debug(f"DataSource key: {full_data_source.get('key')}")
            logger.debug(f"DataSource currentVersionId: {full_data_source.get('currentVersionId')}")
            
        except Exception as e:
            logger.error(f"Error fetching full DataSource record: {e}")
            return None, None
            
        # Get the current DataSourceVersion ID for cache key
        data_source_version_id = full_data_source.get('currentVersionId')
        if not data_source_version_id:
            logger.error(f"❌ DataSource '{full_data_source['name']}' has no currentVersionId")
            return None, None
        
        # Use DataSourceVersion ID as cache key instead of DataSource ID
        # This ensures each version gets its own cache directory
        cache_dir = Path(".plexus") / "cache" / "datasets" / data_source_version_id
        cache_file = cache_dir / "dataset.parquet"
        metadata_file = cache_dir / "metadata.json"
        
        if not fresh and cache_file.exists() and metadata_file.exists():
            logger.info(f"Using cached dataset for DataSourceVersion {data_source_version_id}: {cache_file}")
            metadata = self._load_metadata(metadata_file)
            return str(cache_file), metadata
        
        # Look for existing DataSets associated with this DataSource
        logger.info(f"Looking for existing DataSets for DataSource {full_data_source['name']}")
        logger.info(f"Using DataSourceVersion ID: {data_source_version_id}")
        try:
            
            # Query DataSets using the dataSourceVersionId GSI
            query = """
            query ListDataSetsByDataSourceVersion($filter: ModelDataSetFilterInput) {
                listDataSets(filter: $filter) {
                    items {
                        id
                        name
                        file
                        createdAt
                        updatedAt
                        dataSourceVersionId
                    }
                }
            }
            """
            response = self.client.execute(query, {
                "filter": {"dataSourceVersionId": {"eq": data_source_version_id}}
            })
            datasets = response.get('listDataSets', {}).get('items', [])
            
            logger.info(f"Found {len(datasets)} DataSets for DataSourceVersion {data_source_version_id}")
            
            if not datasets:
                logger.error(f"❌ No DataSets found for DataSource '{full_data_source['name']}' (ID: {full_data_source['id']})")
                logger.error("Reports can only use existing DataSets, not generate new ones")
                return None, None
            
            # Use the most recent dataset
            latest_dataset = max(datasets, key=lambda d: d.get('updatedAt', d.get('createdAt', '0')))
            logger.info(f"✅ Found {len(datasets)} DataSets, using latest: {latest_dataset['name']} (ID: {latest_dataset['id']})")
            
            if not latest_dataset.get('file'):
                logger.error(f"❌ DataSet {latest_dataset['id']} has no file attached")
                return None, None
                
            # Download and cache the file
            s3_path = latest_dataset['file']
            logger.info(f"📁 DataSet file path: {s3_path}")
            local_path = await self._download_and_cache_file(
                s3_path, cache_file, latest_dataset['id'], latest_dataset
            )
            
            if local_path:
                metadata = {
                    "id": latest_dataset['id'],
                    "name": latest_dataset['name'],
                    "source_type": "dataset_from_source",
                    "dataSourceId": full_data_source['id'],
                    "dataSourceName": full_data_source['name'],
                    "dataSourceKey": full_data_source.get('key'),
                    "createdAt": latest_dataset.get('createdAt'),
                    "updatedAt": latest_dataset.get('updatedAt'),
                    "s3_path": s3_path
                }
                self._save_metadata(metadata_file, metadata)
                return local_path, metadata
                
        except Exception as e:
            logger.error(f"❌ Error fetching DataSets for DataSource {full_data_source['id']}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
        return None, None
    
    async def _generate_dataset_from_source(self, data_source: DataSource, cache_file: Path) -> Optional[str]:
        """Generate dataset from DataSource YAML configuration."""
        logger.info(f"🔄 Generating dataset from DataSource: {data_source.name}")
        
        if not data_source.yamlConfiguration:
            logger.error(f"❌ DataSource '{data_source.name}' has no yamlConfiguration")
            return None
            
        logger.debug(f"📄 YAML Configuration:\n{data_source.yamlConfiguration}")
            
        try:
            import yaml
            config = yaml.safe_load(data_source.yamlConfiguration)
            logger.debug(f"✅ Parsed YAML config: {config}")
        except yaml.YAMLError as e:
            logger.error(f"❌ Error parsing yamlConfiguration: {e}")
            return None
            
        if not isinstance(config, dict):
            logger.error(f"❌ yamlConfiguration must be a YAML dictionary, got {type(config)}")
            return None
            
        # Handle both scorecard format (with 'data' section) and dataset format (direct config)
        data_config = config.get('data')
        logger.debug(f"📋 Initial data_config from 'data' section: {data_config}")
        
        if not data_config:
            if 'class' in config:
                logger.info("🔄 Detected direct dataset configuration format")
                data_config = {
                    'class': f"plexus_extensions.{config['class']}",
                    'parameters': {k: v for k, v in config.items() if k != 'class'}
                }
                logger.debug(f"📋 Converted data_config: {data_config}")
            else:
                logger.error("❌ No 'data' section in yamlConfiguration and no 'class' specified")
                return None
                
        # Dynamically load DataCache class
        data_cache_class_path = data_config.get('class')
        logger.debug(f"🎯 Data cache class path: {data_cache_class_path}")
        
        if not data_cache_class_path:
            logger.error("❌ No 'class' specified in data configuration")
            return None
            
        try:
            module_path, class_name = data_cache_class_path.rsplit('.', 1)
            logger.info(f"📦 Importing module: {module_path}")
            logger.info(f"🏗️  Getting class: {class_name}")
            module = importlib.import_module(module_path)
            data_cache_class = getattr(module, class_name)
            logger.info(f"✅ Successfully imported data cache class: {data_cache_class}")
        except (ImportError, AttributeError) as e:
            logger.error(f"❌ Could not import data cache class '{data_cache_class_path}': {e}")
            return None
            
        # Load dataframe
        logger.info(f"📊 Loading dataframe using {data_cache_class_path}...")
        data_cache_params = data_config.get('parameters', {})
        logger.info(f"🔧 Data cache parameters: {data_cache_params}")
        
        try:
            data_cache = data_cache_class(**data_cache_params)
            logger.info(f"✅ Created data cache instance: {data_cache}")
        except Exception as e:
            logger.error(f"❌ Failed to create data cache instance: {e}")
            return None
        
        # Create cache directory
        logger.debug(f"📁 Creating cache directory: {cache_file.parent}")
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load and save dataframe
        logger.info(f"🔄 Loading dataframe from data cache...")
        try:
            dataframe = data_cache.load_dataframe(data=data_cache_params, fresh=True)
            logger.info(f"✅ Loaded dataframe with {len(dataframe)} rows and columns: {dataframe.columns.tolist()}")
            
            # Debug: Show sample of actual data loaded
            if not dataframe.empty and 'text' in dataframe.columns:
                logger.info(f"🔍 DEBUG: Sample of loaded data (first 3 rows):")
                for i, row in dataframe.head(3).iterrows():
                    text_content = str(row.get('text', ''))[:100]
                    logger.info(f"   Row {i}: {text_content}...")
            else:
                logger.warning(f"⚠️  No 'text' column found in dataframe or dataframe is empty")
                logger.info(f"Available columns: {dataframe.columns.tolist()}")
                
        except Exception as e:
            logger.error(f"❌ Failed to load dataframe: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None
        
        if dataframe.empty:
            logger.warning("⚠️  Dataframe is empty")
            return None
            
        logger.info(f"💾 Saving dataframe to cache: {cache_file}")
        try:
            dataframe.to_parquet(cache_file, index=False)
            logger.info(f"✅ Successfully cached dataset to: {cache_file}")
        except Exception as e:
            logger.error(f"❌ Failed to save dataframe to cache: {e}")
            return None
        
        return str(cache_file)
    
    async def _download_and_cache_file(
        self, 
        s3_path: str, 
        cache_file: Path, 
        dataset_id: str, 
        dataset_record: Dict[str, Any]
    ) -> Optional[str]:
        """Download file from S3 and cache locally."""
        try:
            # Create cache directory
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Get S3 bucket from amplify config
            bucket_name = self._get_amplify_bucket()
            if not bucket_name:
                logger.error("S3 bucket name not found")
                return None
                
            # Download from S3 
            s3_client = boto3.client('s3')
            # For DataSources bucket, use the path directly without prefix
            s3_key = s3_path
            
            logger.info(f"Downloading dataset from S3: {s3_key}")
            logger.debug(f"S3 bucket: {bucket_name}")
            s3_client.download_file(bucket_name, s3_key, str(cache_file))
            logger.info(f"Cached dataset to: {cache_file}")
            
            return str(cache_file)
            
        except (NoCredentialsError, Exception) as e:
            logger.error(f"Error downloading dataset {dataset_id} from S3: {e}")
            return None
    
    def _get_amplify_bucket(self) -> Optional[str]:
        """Get S3 bucket name from environment variable or amplify config."""
        # First try DataSets bucket environment variable (for datasets)
        bucket_name = os.environ.get("AMPLIFY_STORAGE_DATASETS_BUCKET_NAME")
        if bucket_name:
            logger.info(f"Using DataSets S3 bucket from environment: {bucket_name}")
            return bucket_name
            
        # Fallback to report block details bucket
        bucket_name = os.environ.get("AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME")
        if bucket_name:
            logger.info(f"Using ReportBlockDetails S3 bucket from environment: {bucket_name}")
            return bucket_name
            
        # Fallback to amplify config file
        try:
            import yaml
            with open('dashboard/amplify_outputs.json', 'r') as f:
                amplify_outputs = yaml.safe_load(f)
            bucket_name = amplify_outputs['storage']['plugins']['awsS3StoragePlugin']['bucket']
            logger.info(f"Using S3 bucket from amplify_outputs.json: {bucket_name}")
            return bucket_name
        except (IOError, KeyError, TypeError) as e:
            logger.error(f"Could not read S3 bucket from amplify_outputs.json: {e}")
            logger.error("Set AMPLIFY_STORAGE_DATASOURCES_BUCKET_NAME or AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME environment variable as fallback")
            return None
    
    def _save_metadata(self, metadata_file: Path, metadata: Dict[str, Any]):
        """Save metadata to JSON file."""
        import json
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _load_metadata(self, metadata_file: Path) -> Optional[Dict[str, Any]]:
        """Load metadata from JSON file."""
        try:
            import json
            with open(metadata_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading metadata from {metadata_file}: {e}")
            return None
    
    def clear_cache(self, identifier: Optional[str] = None):
        """Clear dataset cache. If identifier provided, clear only that dataset."""
        cache_base = Path(".plexus") / "cache" / "datasets"
        
        if identifier:
            cache_dir = cache_base / identifier
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                logger.info(f"Cleared cache for dataset: {identifier}")
        else:
            if cache_base.exists():
                shutil.rmtree(cache_base)
                logger.info("Cleared all dataset caches")