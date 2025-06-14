import asyncio
import os
import yaml
import click
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO
from datetime import datetime, timezone
import importlib
import boto3
from botocore.exceptions import NoCredentialsError

from plexus.CustomLogging import logging
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.data_source import DataSource
# from plexus.dashboard.api.models.data_set import DataSet
from plexus.data.DataCache import DataCache
from plexus.cli.identifier_resolution import resolve_data_source


def create_client() -> PlexusDashboardClient:
    """Create a client and log its configuration"""
    client = PlexusDashboardClient()
    logging.debug(f"Using API URL: {client.api_url}")
    return client

def get_amplify_bucket():
    """Reads the Amplify configuration to get the S3 bucket name."""
    try:
        with open('dashboard/amplify_outputs.json', 'r') as f:
            amplify_outputs = yaml.safe_load(f)
        # It's not region, it's bucket name. Let's find the right key.
        # Assuming a structure like "storage": {"plugins": {"awsS3StoragePlugin": {"bucket": "..."}}}
        return amplify_outputs['storage']['plugins']['awsS3StoragePlugin']['bucket']
    except (IOError, KeyError, TypeError) as e:
        logging.error(f"Could not read S3 bucket from amplify_outputs.json: {e}")
        return None

@click.group()
def dataset():
    """Commands for managing datasets."""
    pass


@dataset.command()
@click.option('--source', 'source_identifier', required=True, help='Identifier (ID, key, or name) of the DataSource to load.')
@click.option('--fresh', is_flag=True, help='Force a fresh load, ignoring any caches.')
def load(source_identifier: str, fresh: bool):
    """Loads a dataset from a DataSource, generates a Parquet file, and attaches it to a new DataSet record."""

    async def _load():
        client = create_client()

        # 1. Fetch the DataSource
        logging.info(f"Resolving DataSource with identifier: {source_identifier}")
        data_source = await resolve_data_source(client, source_identifier)
        if not data_source:
            # The resolver already logs an error, so we can just exit.
            return
        
        logging.info(f"Found DataSource: {data_source.name} (ID: {data_source.id})")

        # 2. Parse YAML configuration
        if not data_source.yamlConfiguration:
            logging.error(f"DataSource '{data_source.name}' has no yamlConfiguration.")
            return

        try:
            config = yaml.safe_load(data_source.yamlConfiguration)
        except yaml.YAMLError as e:
            logging.error(f"Error parsing yamlConfiguration: {e}")
            return

        if not isinstance(config, dict):
            logging.error(f"yamlConfiguration must be a YAML dictionary, but got {type(config).__name__}: {config}")
            logging.error("Expected format:")
            logging.error("data:")
            logging.error("  class: plexus_extensions.CallCriteriaDBCache.CallCriteriaDBCache")
            logging.error("  parameters:")
            logging.error("    # ... data cache parameters")
            return

        # Handle both scorecard format (with 'data' section) and dataset format (direct config)
        data_config = config.get('data')
        if not data_config:
            # Check if this is a direct dataset configuration (recommended format)
            if 'class' in config:
                logging.info("Detected direct dataset configuration format")
                data_config = {
                    'class': f"plexus_extensions.{config['class']}.{config['class']}",
                    'parameters': {k: v for k, v in config.items() if k != 'class'}
                }
            else:
                logging.error("No 'data' section in yamlConfiguration and no 'class' specified.")
                logging.error("Expected format for datasets (recommended):")
                logging.error("class: CallCriteriaDBCache")
                logging.error("queries:")
                logging.error("  # ... parameters")
                logging.error("Or scorecard format:")
                logging.error("data:")
                logging.error("  class: plexus_extensions.CallCriteriaDBCache.CallCriteriaDBCache")
                logging.error("  parameters:")
                logging.error("    # ... data cache parameters")
                return

        # 3. Dynamically load DataCache class
        data_cache_class_path = data_config.get('class')
        if not data_cache_class_path:
            logging.error("No 'class' specified in data configuration.")
            return

        try:
            module_path, class_name = data_cache_class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            data_cache_class = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            logging.error(f"Could not import data cache class '{data_cache_class_path}': {e}")
            if 'plexus_extensions' in data_cache_class_path:
                logging.error("The 'plexus_extensions' module is typically part of the Call-Criteria-Python project.")
                logging.error("Make sure you have the Call-Criteria-Python project installed and accessible.")
                logging.error("You may need to set PYTHONPATH or install the plexus_extensions package.")
            return

        # 4. Load dataframe
        logging.info(f"Loading dataframe using {data_cache_class_path}...")
        data_cache_params = data_config.get('parameters', {})
        data_cache = data_cache_class(**data_cache_params)

        # Pass the parameters (which contain queries, searches, etc.) to load_dataframe
        # not the entire data_config which includes class information
        dataframe = data_cache.load_dataframe(data=data_cache_params, fresh=fresh)
        logging.info(f"Loaded dataframe with {len(dataframe)} rows and columns: {dataframe.columns.tolist()}")

        # 5. Generate Parquet file in memory
        if dataframe.empty:
            logging.warning("Dataframe is empty, skipping parquet generation and upload.")
            return

        logging.info("Generating Parquet file in memory...")
        buffer = BytesIO()
        table = pa.Table.from_pandas(dataframe)
        pq.write_table(table, buffer)
        buffer.seek(0)
        logging.info("Parquet file generated successfully.")

        # 6. Create a new DataSet record
        logging.info("Creating new DataSet record...")
        
        if not hasattr(data_source, 'owner') or not data_source.owner:
            logging.error("DataSource is missing owner information (accountId). Cannot proceed.")
            return
        account_id = data_source.owner

        new_dataset_record = await client.execute(
            """
            mutation CreateDataSet($input: CreateDataSetInput!) {
                createDataSet(input: $input) {
                    id
                    name
                    dataSourceId
                }
            }
            """,
            {
                "input": {
                    "name": f"{data_source.name} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
                    "dataSourceId": data_source.id,
                    "status": "GENERATING",
                    "source": "CLI",
                }
            }
        )
        new_dataset = new_dataset_record['createDataSet']
        new_dataset_id = new_dataset['id']
        
        logging.info(f"Created DataSet record with ID: {new_dataset_id}")

        # 7. Upload Parquet to S3
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        file_name = f"{timestamp}-{new_dataset_id}.parquet"
        s3_key = f"datasets/{account_id}/{data_source.id}/{new_dataset_id}/{file_name}"
        
        logging.info(f"Uploading Parquet file to S3 at: {s3_key}")
        
        bucket_name = get_amplify_bucket()
        if not bucket_name:
             logging.error("S3 bucket name not found. Cannot upload file.")
             await client.execute("""
                mutation UpdateDataSet($input: UpdateDataSetInput!) {
                    updateDataSet(input: $input) { id }
                }
             """, {"input": {"id": new_dataset_id, "status": "FAILED", "errorMessage": "S3 bucket not configured."}})
             return

        try:
            s3_client = boto3.client('s3')
            s3_client.upload_fileobj(buffer, bucket_name, f"public/{s3_key}")
            logging.info("File uploaded successfully to S3.")
        except NoCredentialsError:
            logging.error("Boto3: AWS credentials not found.")
            return
        except Exception as e:
            logging.error(f"Failed to upload file to S3: {e}")
            await client.execute("""
               mutation UpdateDataSet($input: UpdateDataSetInput!) {
                   updateDataSet(input: $input) { id }
               }
            """, {"input": {"id": new_dataset_id, "status": "FAILED", "errorMessage": f"S3 upload failed: {e}"}})
            return

        # 8. Update DataSet with file path
        logging.info(f"Updating DataSet record with file path...")
        await client.execute(
            """
            mutation UpdateDataSet($input: UpdateDataSetInput!) {
                updateDataSet(input: $input) {
                    id
                    status
                    filePath
                }
            }
            """,
            {
                "input": {
                    "id": new_dataset_id,
                    "status": "COMPLETED",
                    "filePath": s3_key,
                }
            }
        )
        logging.info("DataSet record updated successfully.")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_load())
        else:
            loop.run_until_complete(_load())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_load()) 