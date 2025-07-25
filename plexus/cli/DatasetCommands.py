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
    """Get the S3 bucket name from environment variables or fall back to reading amplify_outputs.json."""
    # First try environment variable (consistent with reporting commands)
    bucket_name = os.environ.get("AMPLIFY_STORAGE_DATASETS_BUCKET_NAME")
    if bucket_name:
        logging.debug(f"Using S3 bucket from environment variable: {bucket_name}")
        return bucket_name
    
    # Fall back to reading from amplify_outputs.json
    try:
        with open('dashboard/amplify_outputs.json', 'r') as f:
            amplify_outputs = yaml.safe_load(f)
        # Assuming a structure like "storage": {"plugins": {"awsS3StoragePlugin": {"bucket": "..."}}}
        bucket_name = amplify_outputs['storage']['plugins']['awsS3StoragePlugin']['bucket']
        logging.debug(f"Using S3 bucket from amplify_outputs.json: {bucket_name}")
        return bucket_name
    except (IOError, KeyError, TypeError) as e:
        logging.error(f"Could not read S3 bucket from environment variable AMPLIFY_STORAGE_DATASETS_BUCKET_NAME or amplify_outputs.json: {e}")
        return None

async def create_initial_data_source_version(client, data_source):
    """Create the initial version for a DataSource that doesn't have one yet."""
    try:
        # Create the first DataSourceVersion
        logging.info(f"Creating initial version for DataSource: {data_source.name}")
        
        create_version_result = client.execute(
            """
            mutation CreateDataSourceVersion($input: CreateDataSourceVersionInput!) {
                createDataSourceVersion(input: $input) {
                    id
                }
            }
            """,
            {
                "input": {
                    "dataSourceId": data_source.id,
                    "yamlConfiguration": data_source.yamlConfiguration or "",
                    "isFeatured": True,
                    "note": "Initial version created automatically",
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "updatedAt": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        if not create_version_result or not create_version_result.get('createDataSourceVersion'):
            logging.error("Failed to create DataSourceVersion record")
            return None
            
        version_id = create_version_result['createDataSourceVersion']['id']
        logging.info(f"Created DataSourceVersion with ID: {version_id}")
        
        # Update the DataSource to point to this version as the current version
        update_result = client.execute(
            """
            mutation UpdateDataSource($input: UpdateDataSourceInput!) {
                updateDataSource(input: $input) {
                    id
                    currentVersionId
                }
            }
            """,
            {
                "input": {
                    "id": data_source.id,
                    "currentVersionId": version_id
                }
            }
        )
        
        if not update_result or not update_result.get('updateDataSource'):
            logging.error("Failed to update DataSource with currentVersionId")
            return None
            
        logging.info(f"Updated DataSource {data_source.id} to use version {version_id} as current version")
        return version_id
        
    except Exception as e:
        logging.error(f"Error creating initial DataSource version: {e}")
        import traceback
        traceback.print_exc()
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
                
                # Handle built-in Plexus classes vs client-specific extensions
                class_name = config['class']
                if class_name in ['FeedbackItems']:
                    # Built-in Plexus classes (single file modules)
                    class_path = f"plexus.data.{class_name}"
                else:
                    # Client-specific extensions (existing behavior)
                    class_path = f"plexus_extensions.{class_name}.{class_name}"
                
                data_config = {
                    'class': class_path,
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

        # 6. Get the current DataSource version and resolve score version
        logging.info("Creating new DataSet record...")
        
        if not hasattr(data_source, 'accountId') or not data_source.accountId:
            logging.error("DataSource is missing accountId. Cannot proceed.")
            return
        account_id = data_source.accountId

        # Get the current version of the DataSource, creating one if it doesn't exist
        if not data_source.currentVersionId:
            logging.info("DataSource has no currentVersionId. Creating initial version...")
            data_source_version_id = await create_initial_data_source_version(client, data_source)
            if not data_source_version_id:
                logging.error("Failed to create initial DataSource version.")
                return
        else:
            data_source_version_id = data_source.currentVersionId
            logging.info(f"Using existing DataSource version ID: {data_source_version_id}")

        # Get the score version - use the score linked to the DataSource if available (optional)
        score_version_id = None
        if hasattr(data_source, 'scoreId') and data_source.scoreId:
            logging.info(f"DataSource is linked to score ID: {data_source.scoreId}")
            # Get the champion version of this score
            score_query = client.execute(
                """
                query GetScore($id: ID!) {
                    getScore(id: $id) {
                        id
                        name
                        championVersionId
                    }
                }
                """,
                {"id": data_source.scoreId}
            )
            
            if score_query and score_query.get('getScore') and score_query['getScore'].get('championVersionId'):
                score_version_id = score_query['getScore']['championVersionId']
                logging.info(f"Using champion version ID: {score_version_id}")
            else:
                logging.warning(f"Score {data_source.scoreId} has no champion version. Creating DataSet without score version.")
        else:
            logging.info("DataSource is not linked to a specific score. Creating DataSet without score version.")

        # Create a DataSet linked to the DataSource version and optionally to a score version
        dataset_input = {
            "name": f"{data_source.name} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
            "accountId": account_id,
            "dataSourceVersionId": data_source_version_id,
        }
        
        # Add optional fields only if they have values
        if score_version_id:
            dataset_input["scoreVersionId"] = score_version_id
        if hasattr(data_source, 'scorecardId') and data_source.scorecardId:
            dataset_input["scorecardId"] = data_source.scorecardId
        if hasattr(data_source, 'scoreId') and data_source.scoreId:
            dataset_input["scoreId"] = data_source.scoreId
            
        new_dataset_record = client.execute(
            """
            mutation CreateDataSet($input: CreateDataSetInput!) {
                createDataSet(input: $input) {
                    id
                    name
                    dataSourceVersionId
                    scoreVersionId
                }
            }
            """,
            {
                "input": dataset_input
            }
        )
        new_dataset = new_dataset_record['createDataSet']
        new_dataset_id = new_dataset['id']
        
        logging.info(f"Created DataSet record with ID: {new_dataset_id}")

        # 7. Upload Parquet to S3
        file_name = "dataset.parquet"
        s3_key = f"datasets/{account_id}/{new_dataset_id}/{file_name}"
        
        logging.info(f"Uploading Parquet file to S3 at: {s3_key}")
        
        bucket_name = get_amplify_bucket()
        if not bucket_name:
             logging.error("S3 bucket name not found. Cannot upload file.")
             client.execute("""
                mutation UpdateDataSet($input: UpdateDataSetInput!) {
                    updateDataSet(input: $input) { id }
                }
             """, {"input": {"id": new_dataset_id, "description": "FAILED: S3 bucket not configured."}})
             return

        try:
            s3_client = boto3.client('s3')
            s3_client.upload_fileobj(buffer, bucket_name, s3_key)
            logging.info("File uploaded successfully to S3.")
        except NoCredentialsError:
            logging.error("Boto3: AWS credentials not found.")
            return
        except Exception as e:
            logging.error(f"Failed to upload file to S3: {e}")
            client.execute("""
               mutation UpdateDataSet($input: UpdateDataSetInput!) {
                   updateDataSet(input: $input) { id }
               }
            """, {"input": {"id": new_dataset_id, "description": f"FAILED: S3 upload failed: {e}"}})
            return

        # 8. Update DataSet with file path
        logging.info(f"Updating DataSet record with file path...")
        client.execute(
            """
            mutation UpdateDataSet($input: UpdateDataSetInput!) {
                updateDataSet(input: $input) {
                    id
                    file
                }
            }
            """,
            {
                "input": {
                    "id": new_dataset_id,
                    "file": s3_key,
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