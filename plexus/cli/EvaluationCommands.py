import os
from dotenv import load_dotenv
load_dotenv(override=True, verbose=True)

import re
import sys
import json
import click
import yaml
import asyncio
import pandas as pd
import traceback
from typing import Optional, Dict
import numpy as np
from datetime import datetime, timezone, timedelta
import tempfile
import urllib.parse
import boto3
from botocore.exceptions import ClientError
import yaml

from plexus.CustomLogging import logging, set_log_group
from plexus.Scorecard import Scorecard
from plexus.Evaluation import AccuracyEvaluation
from plexus.cli.console import console

# Import dashboard-specific modules
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.evaluation import Evaluation as DashboardEvaluation
from plexus.dashboard.api.models.scorecard import Scorecard as DashboardScorecard
from plexus.dashboard.api.models.score import Score as DashboardScore
from plexus.dashboard.api.models.score_result import ScoreResult

import importlib
from collections import Counter
import concurrent.futures
import time
import threading
import socket
import types  # Add this at the top with other imports
import uuid
import inspect
from concurrent.futures import ThreadPoolExecutor

def truncate_dict_strings(d, max_length=100):
    """Recursively truncate long string values in a dictionary."""
    if isinstance(d, dict):
        return {k: truncate_dict_strings(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [truncate_dict_strings(v) for v in d]
    elif isinstance(d, str) and len(d) > max_length:
        return d[:max_length] + "..."
    return d

set_log_group('plexus/cli/evaluation')

from plexus.scores.Score import Score
from plexus.dashboard.api.models.task import Task
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.cli.CommandProgress import CommandProgress
from plexus.cli.task_progress_tracker import TaskProgressTracker, StageConfig
from plexus.cli.stage_configurations import get_evaluation_stage_configs

from plexus.utils import truncate_dict_strings_inner

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
        amplify_file = 'dashboard/amplify_outputs.json'
        if not os.path.exists(amplify_file):
            amplify_file = 'amplify_outputs.json'  # Try root level too
        
        with open(amplify_file, 'r') as f:
            amplify_outputs = yaml.safe_load(f)
        # Assuming a structure like "storage": {"plugins": {"awsS3StoragePlugin": {"bucket": "..."}}}
        bucket_name = amplify_outputs['storage']['plugins']['awsS3StoragePlugin']['bucket']
        logging.debug(f"Using S3 bucket from amplify_outputs.json: {bucket_name}")
        return bucket_name
    except (IOError, KeyError, TypeError) as e:
        logging.error(f"Could not read S3 bucket from environment variable AMPLIFY_STORAGE_DATASETS_BUCKET_NAME or amplify_outputs.json: {e}")
        return None

def lookup_data_source(client: PlexusDashboardClient, name: Optional[str] = None, 
                      key: Optional[str] = None, id: Optional[str] = None) -> dict:
    """Look up a DataSource by name, key, or ID"""
    if not any([name, key, id]):
        raise ValueError("Must provide either name, key, or id to look up DataSource")
    
    if id:
        logging.info(f"Looking up DataSource by ID: {id}")
        query = """
        query GetDataSource($id: ID!) {
            getDataSource(id: $id) {
                id
                name
                key
                currentVersionId
                attachedFiles
                yamlConfiguration
                accountId
            }
        }
        """
        result = client.execute(query, {'id': id})
        if not result or 'getDataSource' not in result or not result['getDataSource']:
            raise ValueError(f"DataSource with ID {id} not found")
        return result['getDataSource']
    
    elif key:
        logging.info(f"Looking up DataSource by key: {key}")
        query = """
        query ListDataSourcesByKey($key: String!) {
            listDataSourcesByKey(key: $key) {
                items {
                    id
                    name
                    key
                    currentVersionId
                    attachedFiles
                    yamlConfiguration
                    accountId
                }
            }
        }
        """
        result = client.execute(query, {'key': key})
        if not result or 'listDataSourcesByKey' not in result or not result['listDataSourcesByKey']['items']:
            raise ValueError(f"DataSource with key {key} not found")
        return result['listDataSourcesByKey']['items'][0]
    
    else:  # name
        logging.info(f"Looking up DataSource by name: {name}")
        query = """
        query ListDataSourcesByName($name: String!) {
            listDataSourcesByName(name: $name) {
                items {
                    id
                    name
                    key
                    currentVersionId
                    attachedFiles
                    yamlConfiguration
                    accountId
                }
            }
        }
        """
        result = client.execute(query, {'name': name})
        if not result or 'listDataSourcesByName' not in result or not result['listDataSourcesByName']['items']:
            raise ValueError(f"DataSource with name {name} not found")
        return result['listDataSourcesByName']['items'][0]

def get_latest_dataset_for_data_source(client: PlexusDashboardClient, data_source_id: str) -> dict:
    """Get the most recent DataSet for a DataSource by finding its current version"""
    logging.info(f"Looking up latest dataset for DataSource ID: {data_source_id}")
    
    # First, get the DataSource and its current version
    data_source = lookup_data_source(client, id=data_source_id)
    current_version_id = data_source.get('currentVersionId')
    
    if not current_version_id:
        raise ValueError(f"DataSource {data_source_id} has no current version")
    
    logging.info(f"Found current version ID: {current_version_id}")
    
    # Now get datasets for this version
    query = """
    query ListDataSetsForDataSourceVersion($dataSourceVersionId: ID!) {
        listDataSets(filter: {dataSourceVersionId: {eq: $dataSourceVersionId}}) {
            items {
                id
                name
                description
                file
                dataSourceVersionId
                attachedFiles
                createdAt
                updatedAt
                accountId
            }
        }
    }
    """
    result = client.execute(query, {'dataSourceVersionId': current_version_id})
    if not result or 'listDataSets' not in result or not result['listDataSets']['items']:
        raise ValueError(f"No datasets found for DataSource version ID {current_version_id}")
    
    # Sort by createdAt to get the most recent
    datasets = result['listDataSets']['items']
    datasets.sort(key=lambda x: x['createdAt'], reverse=True)
    latest_dataset = datasets[0]
    
    logging.info(f"Found latest dataset: {latest_dataset['id']} (created: {latest_dataset['createdAt']})")
    return latest_dataset

def get_dataset_by_id(client: PlexusDashboardClient, dataset_id: str) -> dict:
    """Get a specific DataSet by ID"""
    logging.info(f"Looking up dataset by ID: {dataset_id}")
    query = """
    query GetDataSet($id: ID!) {
        getDataSet(id: $id) {
            id
            name
            description
            file
            dataSourceVersionId
            attachedFiles
            createdAt
            updatedAt
            accountId
        }
    }
    """
    result = client.execute(query, {'id': dataset_id})
    if not result or 'getDataSet' not in result or not result['getDataSet']:
        raise ValueError(f"Dataset with ID {dataset_id} not found")
    return result['getDataSet']

def load_samples_from_cloud_dataset(dataset: dict, score_name: str, score_config: dict,
                                   number_of_samples: Optional[int] = None,
                                   random_seed: Optional[int] = None,
                                   progress_callback=None) -> list:
    """Load samples from a cloud dataset (Parquet file) and convert to evaluation format"""
    logging.info(f"Loading samples from cloud dataset: {dataset['id']}")
    
    # Find data files - check both 'file' field and 'attachedFiles'
    main_file = dataset.get('file')
    attached_files = dataset.get('attachedFiles', [])
    if attached_files is None:
        attached_files = []
    
    # Combine all available files
    all_files = []
    if main_file:
        all_files.append(main_file)
    all_files.extend(attached_files)
        
    logging.info(f"Dataset {dataset['id']} has main file: {main_file}")
    logging.info(f"Dataset {dataset['id']} has {len(attached_files)} attached files: {attached_files}")
    logging.info(f"All available files: {all_files}")
    
    # Look for Parquet files first (preferred)
    parquet_files = [f for f in all_files if f.lower().endswith('.parquet')]
    
    if parquet_files:
        data_file_path = parquet_files[0]
        file_type = 'parquet'
        logging.info(f"Using Parquet file: {data_file_path}")
    else:
        # Fall back to CSV files
        csv_files = [f for f in all_files if f.lower().endswith('.csv')]
        if csv_files:
            data_file_path = csv_files[0]
            file_type = 'csv'
            logging.info(f"Using CSV file: {data_file_path}")
        else:
            # List available file types for better error message
            file_extensions = [f.split('.')[-1].lower() for f in all_files if '.' in f]
            raise ValueError(f"No Parquet or CSV files found in dataset {dataset['id']}. "
                           f"Main file: {main_file}. "
                           f"Attached files: {attached_files}. "
                           f"File extensions found: {file_extensions}")
    
    # Handle both full S3 URLs and relative paths
    if data_file_path.startswith('s3://'):
        # Full S3 URL - parse normally
        s3_path = data_file_path[5:]
        bucket_name, key = s3_path.split('/', 1)
    else:
        # Relative path - construct full S3 URL
        bucket_name = get_amplify_bucket()
        if not bucket_name:
            raise ValueError(f"S3 bucket name not found. Cannot download file: {data_file_path}")
        key = data_file_path
        full_s3_url = f"s3://{bucket_name}/{key}"
        logging.info(f"Constructed full S3 URL: {full_s3_url}")
        data_file_path = full_s3_url  # Update for logging consistency
    
    logging.info(f"Downloading from S3 bucket: {bucket_name}, key: {key}")
    
    # Download the data file from S3
    s3_client = boto3.client('s3')
    
    try:
        # Create appropriate temp file extension
        file_extension = f".{file_type}"
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            temp_file_path = temp_file.name
            
        logging.info(f"Downloading {file_type} file to: {temp_file_path}")
        s3_client.download_file(bucket_name, key, temp_file_path)
        
        # Load the data file into a DataFrame
        logging.info(f"Loading {file_type} file into DataFrame")
        if file_type == 'parquet':
            df = pd.read_parquet(temp_file_path)
        elif file_type == 'csv':
            df = pd.read_csv(temp_file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        # Clean up the temporary file
        os.unlink(temp_file_path)
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            raise ValueError(f"{file_type.upper()} file not found in S3: {data_file_path}")
        elif error_code == 'NoSuchBucket':
            raise ValueError(f"S3 bucket not found: {bucket_name}")
        else:
            raise ValueError(f"Failed to download {file_type} file from S3: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to load {file_type} file: {str(e)}")
    
    logging.info(f"Loaded DataFrame with {len(df)} rows and columns: {df.columns.tolist()}")
    
    # Sample the dataframe if number_of_samples is specified
    if number_of_samples and number_of_samples < len(df):
        logging.info(f"Sampling {number_of_samples} records from {len(df)} total records")
        df = df.sample(n=number_of_samples, random_state=random_seed)
        actual_sample_count = number_of_samples
        logging.info(f"Using random_seed: {random_seed if random_seed is not None else 'None (fully random)'}")
    else:
        actual_sample_count = len(df)
        logging.info(f"Using all {actual_sample_count} records (no sampling needed)")

    # Update progress tracker with actual count
    if progress_callback and hasattr(progress_callback, '__self__'):
        tracker = progress_callback.__self__
        
        # Set the actual total items count we just discovered
        new_total = tracker.set_total_items(actual_sample_count)
        
        # Verify the total was set correctly before proceeding
        if new_total != actual_sample_count:
            raise RuntimeError(f"Failed to set total items to {actual_sample_count}")
        
        # Set the status message
        status_message = f"Successfully loaded {actual_sample_count} samples from cloud dataset"
        if tracker.current_stage:
            tracker.current_stage.status_message = status_message
            # Reset processed items to 0 since we're starting fresh
            tracker.current_stage.processed_items = 0
            
            # Verify stage total_items was updated
            if tracker.current_stage.total_items != actual_sample_count:
                raise RuntimeError(f"Stage {tracker.current_stage.name} total_items not updated correctly")
        
        # Now update progress - by this point total_items is set to actual_sample_count
        tracker.update(0, status_message)
        
        # Final verification after update
        if tracker.total_items != actual_sample_count:
            raise RuntimeError("Total items not maintained after update")
    elif progress_callback:
        progress_callback(0)

    # Convert DataFrame to samples in the expected format
    samples = df.to_dict('records')
    
    # Determine the score name column
    score_name_column_name = score_name
    if score_config.get('label_score_name'):
        label_score_name = score_config['label_score_name']
    else:
        label_score_name = score_name
        
    if score_config.get('label_field'):
        score_name_column_name = f"{label_score_name} {score_config['label_field']}"
    else:
        score_name_column_name = label_score_name

    logging.info(f"Looking for label column: {score_name_column_name}")
    
    # Convert to the expected evaluation format
    processed_samples = []
    for sample in samples:
        # Get metadata from the sample if it exists
        metadata = sample.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                logging.warning(f"Failed to parse metadata as JSON for content_id {sample.get('content_id')}")
                metadata = {}
        
        # Create the sample dictionary with metadata included
        processed_sample = {
            'text': sample.get('text', ''),
            f'{score_name_column_name}_label': sample.get(score_name_column_name, ''),
            'content_id': sample.get('content_id', ''),
            'columns': {
                **{k: v for k, v in sample.items() if k not in ['text', score_name_column_name, 'content_id', 'metadata']},
                'metadata': metadata  # Include the metadata in the columns
            }
        }
        processed_samples.append(processed_sample)
    
    logging.info(f"Converted {len(processed_samples)} samples to evaluation format")
    return processed_samples

@click.group()
def evaluate():
    """
    Evaluating current scorecard configurations against labeled samples.
    """
    pass

def load_configuration_from_yaml_file(configuration_file_path):
    """Load configuration from a YAML file."""
    try:
        with open(configuration_file_path, 'r') as f:
            configuration = yaml.safe_load(f)
        return configuration
    except FileNotFoundError:
        logging.error(f"File not found: {configuration_file_path}")
        return None
    except yaml.YAMLError as e:
        logging.error(f"YAML parsing error in {configuration_file_path}: {str(e)}")
        return None
    except Exception as e:
        logging.error(f"Error loading configuration from {configuration_file_path}: {str(e)}")
        return None

def load_scorecard_from_api(scorecard_identifier: str, score_names=None, use_cache=False):
    """
    Load a scorecard from the Plexus Dashboard API.
    
    Args:
        scorecard_identifier: A string that can identify the scorecard (id, key, name, etc.)
        score_names: Optional list of specific score names to load
        use_cache: Whether to prefer local cache files over API (default: False)
                   When False, will always fetch from API but still write cache files
                   When True, will check local cache first and only fetch missing configs
        
    Returns:
        Scorecard: An initialized Scorecard instance with required scores loaded
        
    Raises:
        ValueError: If the scorecard cannot be found
    """
    from plexus.Scorecard import Scorecard
    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.cli.direct_memoized_resolvers import direct_memoized_resolve_scorecard_identifier
    from plexus.cli.iterative_config_fetching import iteratively_fetch_configurations
    from plexus.cli.fetch_scorecard_structure import fetch_scorecard_structure
    from plexus.cli.identify_target_scores import identify_target_scores
    import logging
    
    if use_cache:
        logging.info(f"Loading scorecard '{scorecard_identifier}' from API with local cache preference")
    else:
        logging.info(f"Loading scorecard '{scorecard_identifier}' from API (ignoring local cache)")
    
    try:
        # Create client directly without context manager
        client = PlexusDashboardClient()
        
        # 1. Resolve the scorecard ID
        scorecard_id = direct_memoized_resolve_scorecard_identifier(client, scorecard_identifier)
        if not scorecard_id:
            error_msg = f"Could not resolve scorecard identifier: {scorecard_identifier}"
            logging.error(error_msg)
            error_hint = "\nPlease check the identifier and ensure it exists in the dashboard."
            error_hint += "\nIf using a local scorecard, add the --yaml flag to load from YAML files."
            raise ValueError(f"{error_msg}{error_hint}")
        
        logging.info(f"Resolved scorecard ID: {scorecard_id}")
        
        # 2. Fetch scorecard structure
        try:
            scorecard_structure = fetch_scorecard_structure(client, scorecard_id)
            if not scorecard_structure:
                error_msg = f"Could not fetch structure for scorecard: {scorecard_id}"
                logging.error(error_msg)
                raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"API error fetching scorecard structure: {str(e)}"
            logging.error(error_msg)
            raise ValueError(error_msg) from e
        
        # 3. Identify target scores
        try:
            target_scores = identify_target_scores(scorecard_structure, score_names)
            if not target_scores:
                if score_names:
                    error_msg = f"No scores found in scorecard matching names: {score_names}"
                else:
                    error_msg = f"No scores found in scorecard {scorecard_identifier}"
                logging.error(error_msg)
                raise ValueError(error_msg)
                
            # Log score IDs and championVersionIds for all target scores
            for score in target_scores:
                score_id = score.get('id')
                score_name = score.get('name', 'Unknown')
                championVersionId = score.get('championVersionId')
                score_key = score.get('key', 'Unknown')
                logging.info(f"Score ID: {score_id}")
                logging.info(f"Score Key: {score_key}")
                logging.info(f"Champion Version ID: {championVersionId}")
                
            # Store the first target score's ID and championVersionId for later use
            # This is critical for setting the evaluation record properly
            primary_score = target_scores[0] if target_scores else None
            if primary_score:
                primary_score_id = primary_score.get('id')
                primary_score_version_id = primary_score.get('championVersionId')
        except Exception as e:
            error_msg = f"Error identifying target scores: {str(e)}"
            logging.error(error_msg)
            raise ValueError(error_msg) from e
        
        # 4. Iteratively fetch configurations with dependency discovery
        try:
            scores_config = iteratively_fetch_configurations(
                client, 
                scorecard_structure, 
                target_scores,
                use_cache=use_cache
            )
            if not scores_config:
                error_msg = f"Failed to fetch score configurations for scorecard: {scorecard_identifier}"
                logging.error(error_msg)
                raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Error fetching score configurations: {str(e)}"
            logging.error(error_msg)
            raise ValueError(error_msg) from e
        
        # 5. Create scorecard instance from API data
        try:
            # Parse string configuration into dictionaries if needed
            parsed_configs = []
            from ruamel.yaml import YAML
            yaml_parser = YAML(typ='safe')
            
            for score_id, config in scores_config.items():
                try:
                    # If config is a string, parse it as YAML
                    if isinstance(config, str):
                        parsed_config = yaml_parser.load(config)
                        # Add the score ID as an identifier if not present
                        if 'id' not in parsed_config:
                            parsed_config['id'] = score_id
                        parsed_configs.append(parsed_config)
                    elif isinstance(config, dict):
                        # If already a dict, add as is
                        if 'id' not in config:
                            config['id'] = score_id
                        parsed_configs.append(config)
                    else:
                        logging.warning(f"Skipping config with unexpected type: {type(config)}")
                except Exception as parse_err:
                    logging.error(f"Failed to parse configuration for score {score_id}: {str(parse_err)}")
            
            # Create instance with parsed configurations
            scorecard_instance = Scorecard.create_instance_from_api_data(
                scorecard_id=scorecard_id,
                api_data=scorecard_structure,
                scores_config=parsed_configs
            )
        except Exception as e:
            error_msg = f"Error creating scorecard instance: {str(e)}"
            logging.error(error_msg)
            raise ValueError(error_msg) from e
        
        # Get actual name from the properties
        scorecard_name = scorecard_structure.get('name', scorecard_identifier)
        logging.info(f"Successfully loaded scorecard '{scorecard_name}' with " +
                    f"{len(scores_config)} scores and their dependencies")

        return scorecard_instance
        
    except Exception as e:
        if not isinstance(e, ValueError):
            # For unexpected errors not already handled
            error_msg = f"Error loading scorecard from API: {str(e)}"
            logging.error(error_msg)
            raise ValueError(f"{error_msg}\nThis might be due to API connectivity issues or invalid configurations.\nTry using the --yaml flag to load from local YAML files instead.") from e
        raise

def load_scorecard_from_yaml_files(scorecard_identifier: str, score_names=None):
    """
    Load a scorecard from individual YAML configuration files saved by fetch_score_configurations.
    
    Args:
        scorecard_identifier: A string that identifies the scorecard (ID, name, key, or external ID)
        score_names: Optional list of specific score names to load
        
    Returns:
        Scorecard: An initialized Scorecard instance with required scores loaded from YAML files
        
    Raises:
        ValueError: If the scorecard cannot be constructed from YAML files
    """
    from pathlib import Path
    from ruamel.yaml import YAML
    from plexus.cli.direct_memoized_resolvers import direct_memoized_resolve_scorecard_identifier
    from plexus.cli.fetch_scorecard_structure import fetch_scorecard_structure
    
    logging.info(f"Loading scorecard '{scorecard_identifier}' from individual YAML files")
    
    try:
        # First resolve the scorecard identifier to get the actual scorecard name
        client = PlexusDashboardClient()
        
        # 1. Resolve the scorecard ID
        scorecard_id = direct_memoized_resolve_scorecard_identifier(client, scorecard_identifier)
        if not scorecard_id:
            raise ValueError(f"Could not resolve scorecard identifier: {scorecard_identifier}")
        
        logging.info(f"Resolved scorecard ID: {scorecard_id}")
        
        # 2. Fetch scorecard structure to get the actual name
        scorecard_structure = fetch_scorecard_structure(client, scorecard_id)
        if not scorecard_structure:
            raise ValueError(f"Could not fetch structure for scorecard: {scorecard_id}")
        
        # Get the actual scorecard name from the API data
        actual_scorecard_name = scorecard_structure.get('name')
        if not actual_scorecard_name:
            raise ValueError(f"No name found in scorecard structure: {scorecard_structure}")
        
        logging.info(f"Resolved scorecard name: '{actual_scorecard_name}'")
        
        # Look for scorecard directory using the actual name
        scorecards_root = Path('scorecards')
        scorecard_dir = scorecards_root / actual_scorecard_name
        
        if not scorecard_dir.exists():
            available_dirs = [d.name for d in scorecards_root.iterdir() if d.is_dir()] if scorecards_root.exists() else []
            raise ValueError(f"Scorecard directory not found: {scorecard_dir}. Available directories: {available_dirs}")
        
        logging.info(f"Found scorecard directory: {scorecard_dir}")
        
        # Find all YAML files in the scorecard directory
        yaml_files = list(scorecard_dir.glob('*.yaml'))
        if not yaml_files:
            raise ValueError(f"No YAML files found in scorecard directory: {scorecard_dir}")
        
        logging.info(f"Found {len(yaml_files)} YAML files in {scorecard_dir}")
        
        # Parse YAML files to get score configurations
        yaml_parser = YAML(typ='safe')
        parsed_configs = []
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r') as f:
                    config = yaml_parser.load(f)
                
                if not isinstance(config, dict):
                    logging.warning(f"Skipping non-dict configuration in {yaml_file}")
                    continue
                
                score_name = config.get('name')
                if not score_name:
                    logging.warning(f"Skipping configuration without name in {yaml_file}")
                    continue
                
                # Filter by score_names if provided
                if score_names and score_name not in score_names:
                    logging.info(f"Skipping score '{score_name}' (not in requested scores)")
                    continue
                
                parsed_configs.append(config)
                logging.info(f"Loaded configuration for score: {score_name}")
                
            except Exception as e:
                logging.error(f"Error parsing {yaml_file}: {str(e)}")
                continue
        
        if not parsed_configs:
            if score_names:
                raise ValueError(f"No valid configurations found for requested scores: {score_names}")
            else:
                raise ValueError(f"No valid configurations found in {scorecard_dir}")
        
        # Create scorecard structure using the resolved API data
        scorecard_data = {
            'id': scorecard_id,
            'name': actual_scorecard_name,
            'key': scorecard_structure.get('key', actual_scorecard_name),
            'description': scorecard_structure.get('description', f'Scorecard loaded from YAML files in {scorecard_dir}')
        }
        
        # Create scorecard instance using the same method as API loading
        scorecard_instance = Scorecard.create_instance_from_api_data(
            scorecard_id=scorecard_id,
            api_data=scorecard_data,
            scores_config=parsed_configs
        )
        
        logging.info(f"Successfully created scorecard '{scorecard_identifier}' with {len(parsed_configs)} scores from YAML files")
        return scorecard_instance
        
    except Exception as e:
        error_msg = f"Error loading scorecard from YAML files: {str(e)}"
        logging.error(error_msg)
        raise ValueError(f"{error_msg}\nEnsure that individual score YAML files exist in the scorecard directory.\nYou may need to run fetch_score_configurations first to create these files.") from e

@evaluate.command()
@click.option('--scorecard', 'scorecard', default=None, help='Scorecard identifier (ID, name, key, or external ID)')
@click.option('--yaml', is_flag=True, help='Load scorecard from individual YAML files (from fetch_score_configurations) instead of the API')
@click.option('--use-langsmith-trace', is_flag=True, default=False, help='Activate LangSmith trace client for LangGraphScore')
@click.option('--number-of-samples', default=1, type=int, help='Number of texts to sample')
@click.option('--sampling-method', default='random', type=str, help='Method for sampling texts')
@click.option('--random-seed', default=None, type=int, help='Random seed for sampling')
@click.option('--content-ids-to-sample', default='', type=str, help='Comma-separated list of content IDs to sample')
@click.option('--score', 'score', default='', type=str, help='Score identifier (ID, name, key, or external ID). Can be comma-separated for multiple scores.')
@click.option('--experiment-label', default='', type=str, help='Label for the experiment')
@click.option('--fresh', is_flag=True, help='Pull fresh, non-cached data from the data lake.')
@click.option('--visualize', is_flag=True, default=False, help='Generate PNG visualization of LangGraph scores')
@click.option('--task-id', default=None, type=str, help='Task ID for progress tracking')
@click.option('--dry-run', is_flag=True, help='Skip database operations (for testing API loading)')
@click.option('--data-source-name', default=None, type=str, help='Name of the cloud data source to use (overrides score data config)')
@click.option('--data-source-key', default=None, type=str, help='Key of the cloud data source to use (overrides score data config)')
@click.option('--data-source-id', default=None, type=str, help='ID of the cloud data source to use (overrides score data config)')
@click.option('--dataset-id', default=None, type=str, help='Specific dataset ID to use (overrides score data config)')
def accuracy(
    scorecard: str,
    yaml: bool,
    use_langsmith_trace: bool,
    number_of_samples: int,
    sampling_method: str,
    random_seed: int,
    content_ids_to_sample: str,
    score: str,
    experiment_label: str,
    fresh: bool,
    visualize: bool,
    task_id: Optional[str],
    dry_run: bool,
    data_source_name: Optional[str],
    data_source_key: Optional[str],
    data_source_id: Optional[str],
    dataset_id: Optional[str]
    ):
    """
    Evaluate the accuracy of the scorecard using the current configuration against labeled samples.
    """
    logging.info("=== ACCURACY COMMAND STARTED ===")
    logging.info(f"Parameters: scorecard={scorecard}, yaml={yaml}, score='{score}', number_of_samples={number_of_samples}, dry_run={dry_run}")
    
    # If dry-run is enabled, provide a simplified successful execution path
    if dry_run:
        # Log the dry run mode message
        logging.info("Dry run mode enabled - database operations will be skipped")
        console.print("[bold green]Dry run mode enabled - database operations will be skipped[/bold green]")
        
        # Log the parameters that would be used
        console.print(f"[bold]Scorecard:[/bold] {scorecard}")
        console.print(f"[bold]Loading from:[/bold] {'YAML files' if yaml else 'API'}")
        console.print(f"[bold]Number of samples:[/bold] {number_of_samples}")
        if score:
            console.print(f"[bold]Target scores:[/bold] {score}")
        else:
            console.print("[bold]Target scores:[/bold] All scores in scorecard")
        
        # Make it clear that sample retrieval and evaluation would happen in normal mode
        console.print("\n[yellow]In normal mode, the following operations would be performed:[/yellow]")
        console.print("1. Load data and retrieve samples from data sources")
        console.print("2. Evaluate each sample using the scorecard")
        console.print("3. Calculate accuracy by comparing expected vs. actual results")
        console.print("4. Store results in the database")
        
        # Simulate successful completion
        console.print("\n[bold green]Dry run completed successfully.[/bold green]")
        console.print("[dim]No actual evaluation or database operations were performed.[/dim]")
        console.print("[dim]To run with actual sample evaluation, remove the --dry-run flag.[/dim]")
        return
    
    logging.info("=== NOT DRY RUN - PROCEEDING WITH NORMAL EXECUTION ===")
    # Original implementation for non-dry-run mode
    async def _run_accuracy():
        logging.info("=== STARTING _run_accuracy FUNCTION ===")
        nonlocal task_id, score  # Make task_id and score accessible to modify in the async function
        
        task = None  # Track the task
        evaluation_record = None  # Track the evaluation record
        score_id_for_eval = None  # Track the score ID for the evaluation
        score_version_id_for_eval = None  # Track the score version ID for the evaluation
        
        started_at = datetime.now(timezone.utc)
        
        # Initialize our tracker
        tracker = None  # Initialize tracker at the top level
        scorecard_record = None  # Initialize scorecard record at the top level
        scorecard_instance = None  # Initialize scorecard_instance
        
        try:
            # Create or get Task record for progress tracking
            client = PlexusDashboardClient()  # Create client at the top level
            account = None  # Initialize account at the top level
            
            # Get the account ID for call-criteria regardless of path
            logging.info("Looking up call-criteria account...")
            account = Account.list_by_key(key="call-criteria", client=client)
            if not account:
                raise Exception("Could not find account with key: call-criteria")
            logging.info(f"Found account: {account.name} ({account.id})")
            
            if task_id:
                # Get existing task if task_id provided (Celery path)
                try:
                    task = Task.get_by_id(task_id, client)
                    logging.info(f"Using existing task: {task_id}")
                except Exception as e:
                    logging.error(f"Failed to get existing task {task_id}: {str(e)}")
                    raise
            else:
                # Create new task if running standalone
                api_url = os.environ.get('PLEXUS_API_URL')
                api_key = os.environ.get('PLEXUS_API_KEY')
                if api_url and api_key:
                    try:
                        # Initialize TaskProgressTracker with evaluation-specific stage configs
                        stage_configs = get_evaluation_stage_configs(total_items=number_of_samples)

                        # Create tracker with proper task configuration
                        tracker = TaskProgressTracker(
                            total_items=number_of_samples,
                            stage_configs=stage_configs,
                            target=f"evaluation/accuracy/{scorecard}",
                            command=f"evaluate accuracy --scorecard {scorecard}",
                            description=f"Accuracy evaluation for {scorecard}",
                            dispatch_status="DISPATCHED",
                            prevent_new_task=False,
                            metadata={
                                "type": "Accuracy Evaluation",
                                "scorecard": scorecard,
                                "task_type": "Accuracy Evaluation"
                            },
                            account_id=account.id
                        )

                        # Get the task from the tracker
                        task = tracker.task
                        task_id = task.id
                        
                        # Set worker ID immediately to show task as claimed
                        worker_id = f"{socket.gethostname()}-{os.getpid()}"
                        task.update(
                            accountId=task.accountId,
                            type=task.type,
                            status='RUNNING',
                            target=task.target,
                            command=task.command,
                            workerNodeId=worker_id,
                            startedAt=datetime.now(timezone.utc).isoformat(),
                            updatedAt=datetime.now(timezone.utc).isoformat()
                        )
                        logging.info(f"Successfully claimed task {task.id} with worker ID {worker_id}")
                        
                        # Create the Evaluation record immediately after Task setup
                        started_at = datetime.now(timezone.utc)
                        experiment_params = {
                            "type": "accuracy",
                            "accountId": account.id,
                            "status": "SETUP",
                            "accuracy": 0.0,
                            "createdAt": started_at.isoformat().replace('+00:00', 'Z'),
                            "updatedAt": started_at.isoformat().replace('+00:00', 'Z'),
                            "totalItems": number_of_samples,
                            "processedItems": 0,
                            "parameters": json.dumps({
                                "sampling_method": sampling_method,
                                "sample_size": number_of_samples
                            }),
                            "startedAt": started_at.isoformat().replace('+00:00', 'Z'),
                            "estimatedRemainingSeconds": number_of_samples,
                            "taskId": task.id
                        }
                        
                        # Validate 'score' parameter
                        if score is None:
                            score = ""  # Default to empty string if None
                            logging.warning("'score' parameter is None, defaulting to empty string")
                        
                        # Parse the score option to get target score identifiers
                        target_score_identifiers = [s.strip() for s in score.split(',')] if score else []
                        
                        evaluation_record = DashboardEvaluation.create(
                            client=client,
                            **experiment_params
                        )
                        logging.info(f"Created initial Evaluation record with ID: {evaluation_record.id}")

                    except Exception as e:
                        logging.error(f"Error creating task or evaluation: {str(e)}")
                        raise
                else:
                    logging.warning("PLEXUS_API_URL or PLEXUS_API_KEY not set, skipping task creation")

            # If we have a task but no tracker yet (Celery path), create the tracker now
            if task and not tracker:
                # Use evaluation-specific stage configs
                stage_configs = get_evaluation_stage_configs(total_items=number_of_samples)
                
                # Create tracker with existing task
                tracker = TaskProgressTracker(
                    total_items=number_of_samples,
                    stage_configs=stage_configs,
                    task_id=task.id,  # Use existing task ID
                    target=f"evaluation/accuracy/{scorecard}",
                    command=f"evaluate accuracy --scorecard {scorecard}",
                    description=f"Accuracy evaluation for {scorecard}",
                    dispatch_status="DISPATCHED",
                    prevent_new_task=True,  # Prevent new task creation since we have one
                    metadata={
                        "type": "Accuracy Evaluation",
                        "scorecard": scorecard,
                        "task_type": "Accuracy Evaluation"
                    },
                    account_id=account.id
                )
                
                # Create the Evaluation record for Celery path
                started_at = datetime.now(timezone.utc)
                experiment_params = {
                    "type": "accuracy",
                    "accountId": account.id,
                    "status": "SETUP",
                    "accuracy": 0.0,
                    "createdAt": started_at.isoformat().replace('+00:00', 'Z'),
                    "updatedAt": started_at.isoformat().replace('+00:00', 'Z'),
                    "totalItems": number_of_samples,
                    "processedItems": 0,
                    "parameters": json.dumps({
                        "sampling_method": sampling_method,
                        "sample_size": number_of_samples
                    }),
                    "startedAt": started_at.isoformat().replace('+00:00', 'Z'),
                    "estimatedRemainingSeconds": number_of_samples,
                    "taskId": task.id
                }
                
                try:
                    logging.info("Creating initial Evaluation record for Celery path...")
                    evaluation_record = DashboardEvaluation.create(
                        client=client,
                        **experiment_params
                    )
                    logging.info(f"Created initial Evaluation record with ID: {evaluation_record.id}")
                except Exception as e:
                    logging.error(f"Failed to create or update Evaluation record in Celery path: {str(e)}", exc_info=True)
                    raise

            # Enter the Setup stage
            if tracker:
                tracker.current_stage.status_message = "Starting evaluation setup"
                tracker.update(current_items=0)
                logging.info("Entered Setup stage: Starting evaluation setup")
            else:
                logging.info("Running accuracy experiment...")
            
            # Load the scorecard either from YAML or API
            if yaml:
                # Load from individual YAML files (from fetch_score_configurations)
                logging.info(f"Loading scorecard '{scorecard}' from individual YAML configuration files")
                
                # Validate 'score' parameter and parse target scores
                if score is None:
                    score = ""  # Default to empty string if None
                    logging.warning("'score' parameter is None, defaulting to empty string")
                
                target_score_identifiers = [s.strip() for s in score.split(',')] if score else []
                try:
                    scorecard_instance = load_scorecard_from_yaml_files(scorecard, target_score_identifiers)
                    logging.info(f"Successfully loaded scorecard '{scorecard}' from YAML files with {len(scorecard_instance.scores)} scores")
                    
                    # Extract score_id and score_version_id for the primary score
                    primary_score_identifier = target_score_identifiers[0] if target_score_identifiers else None
                    score_id_for_eval = None
                    score_version_id_for_eval = None
                    
                    if primary_score_identifier and scorecard_instance.scores:
                        logging.info(f"Identifying primary score '{primary_score_identifier}' for evaluation record")
                        for sc_config in scorecard_instance.scores:
                            if (sc_config.get('name') == primary_score_identifier or
                                sc_config.get('key') == primary_score_identifier or 
                                str(sc_config.get('id', '')) == primary_score_identifier or
                                sc_config.get('externalId') == primary_score_identifier):
                                score_id_for_eval = sc_config.get('id')
                                score_version_id_for_eval = sc_config.get('version')
                                
                                if not score_version_id_for_eval:
                                    score_version_id_for_eval = sc_config.get('championVersionId')
                                
                                if isinstance(score_id_for_eval, str) and '-' in score_id_for_eval:
                                    logging.info(f"Found primary score from YAML: {sc_config.get('name')} with ID: {score_id_for_eval}")
                                    logging.info(f"Using version ID: {score_version_id_for_eval}")
                                break
                    
                    # If no match found, fall back to first score
                    if not score_id_for_eval and scorecard_instance.scores:
                        sc_config = scorecard_instance.scores[0]
                        score_id_for_eval = sc_config.get('id')
                        score_version_id_for_eval = sc_config.get('version')
                        
                        if not score_version_id_for_eval:
                            score_version_id_for_eval = sc_config.get('championVersionId')
                        
                        if isinstance(score_id_for_eval, str) and '-' in score_id_for_eval:
                            logging.info(f"Using first score from YAML for evaluation record: {sc_config.get('name')} with ID: {score_id_for_eval}")
                            logging.info(f"Using version ID: {score_version_id_for_eval}")
                    
                except Exception as e:
                    error_msg = f"Error loading scorecard from YAML files: {str(e)}"
                    logging.error(error_msg)
                    raise ValueError(error_msg)
            else:
                # Load from API (new approach)
                # Validate 'score' parameter
                if score is None:
                    score = ""  # Default to empty string if None
                    logging.warning("'score' parameter is None, defaulting to empty string")
                
                target_score_identifiers = [s.strip() for s in score.split(',')] if score else []
                try:
                    scorecard_instance = load_scorecard_from_api(scorecard, target_score_identifiers, use_cache=yaml)
                        
                    # Immediately identify the primary score and extract score_id and score_version_id
                    primary_score_identifier = target_score_identifiers[0] if target_score_identifiers else None
                    score_id_for_eval = None
                    score_version_id_for_eval = None
                    
                    if primary_score_identifier and scorecard_instance.scores:
                        logging.info(f"Identifying primary score '{primary_score_identifier}' for evaluation record")
                        for sc_config in scorecard_instance.scores:
                            if (sc_config.get('name') == primary_score_identifier or
                                sc_config.get('key') == primary_score_identifier or 
                                str(sc_config.get('id', '')) == primary_score_identifier or
                                sc_config.get('externalId') == primary_score_identifier):
                                score_id_for_eval = sc_config.get('id')
                                score_version_id_for_eval = sc_config.get('version')
                                
                                if not score_version_id_for_eval:
                                    score_version_id_for_eval = sc_config.get('championVersionId')
                                
                                if isinstance(score_id_for_eval, str) and '-' in score_id_for_eval:
                                    logging.info(f"Found primary score early: {sc_config.get('name')} with ID: {score_id_for_eval}")
                                    logging.info(f"Using champion version ID: {score_version_id_for_eval}")
                                break
                    
                    # If no match found, fall back to first score
                    if not score_id_for_eval and scorecard_instance.scores:
                        sc_config = scorecard_instance.scores[0]
                        score_id_for_eval = sc_config.get('id')
                        score_version_id_for_eval = sc_config.get('version')
                        
                        if not score_version_id_for_eval:
                            score_version_id_for_eval = sc_config.get('championVersionId')
                        
                        if isinstance(score_id_for_eval, str) and '-' in score_id_for_eval:
                            logging.info(f"Using first score for evaluation record: {sc_config.get('name')} with ID: {score_id_for_eval}")
                            logging.info(f"Using champion version ID: {score_version_id_for_eval}")
                        
                except Exception as e:
                    error_msg = f"Failed to load scorecard from API: {str(e)}"
                    logging.error(error_msg)
                    raise ValueError(error_msg)

            if tracker:
                tracker.update(current_items=0)
            
            # Look up the Scorecard record for this experiment
            try:
                scorecard_key = getattr(scorecard_instance, 'key', None) or getattr(scorecard_instance, 'properties', {}).get('key')
                if not scorecard_key:
                    logging.warning("Could not find scorecard key in instance properties")
                    
                if scorecard_key:
                    logging.info(f"Looking up Scorecard record for key: {scorecard_key}")
                    scorecard_record = DashboardScorecard.list_by_key(key=scorecard_key, client=client)
                    if scorecard_record:
                        scorecard_id = scorecard_record.id
                        logging.info(f"Found Scorecard record with ID: {scorecard_id}")
                        
                        # Update the task with the scorecard ID
                        if task:
                            logging.info(f"Updating task {task.id} with scorecard ID: {scorecard_id}")
                            task.update(scorecardId=scorecard_id)
                            
                        # Update the evaluation record with the scorecard ID
                        if evaluation_record:
                            logging.info(f"Updating evaluation record {evaluation_record.id} with scorecard ID: {scorecard_id}")
                            evaluation_record.update(scorecardId=scorecard_id)
                            logging.info(f"Successfully updated evaluation record with IDs")
                    else:
                        logging.warning(f"Could not find matching dashboard scorecard for key {scorecard_key}")
                else:
                    logging.warning("Could not find scorecard key")
            except Exception as e:
                logging.warning(f"Could not find matching dashboard scorecard: {str(e)}")
            
            if tracker:
                tracker.update(current_items=0)
            
            # Determine the primary score for fetching data
            if score is None:
                score = ""
                logging.warning("'score' parameter is None, defaulting to empty string")
            
            target_score_identifiers = [s.strip() for s in score.split(',')] if score else []
            primary_score_identifier = target_score_identifiers[0] if target_score_identifiers else None
            primary_score_config = None
            primary_score_name = None
            primary_score_index = -1

            if not scorecard_instance or not hasattr(scorecard_instance, 'scores') or not scorecard_instance.scores:
                 error_msg = "Scorecard instance has no scores to evaluate."
                 logging.error(error_msg)
                 if tracker: tracker.fail_current_stage(error_msg)
                 raise ValueError(error_msg)

            if primary_score_identifier:
                # Find the config for the specified primary score
                for i, sc_config in enumerate(scorecard_instance.scores):
                    logging.info(f"Checking score: {sc_config.get('name')} (ID: {sc_config.get('id')}, Key: {sc_config.get('key')})")
                    if (sc_config.get('name') == primary_score_identifier or
                        sc_config.get('key') == primary_score_identifier or
                        str(sc_config.get('id', '')) == primary_score_identifier or
                        sc_config.get('externalId') == primary_score_identifier):
                        primary_score_config = sc_config
                        primary_score_name = sc_config.get('name')
                        primary_score_index = i
                        logging.info(f"Found primary score: {sc_config.get('name')} with ID: {sc_config.get('id')}")
                        logging.info(f"Using specified score '{primary_score_name}' for fetching samples.")
                        break
                if not primary_score_config:
                    logging.warning(f"Could not find specified primary score '{primary_score_identifier}'. Using first score for samples.")
            
            if not primary_score_config:
                # Default to the first score in the scorecard if none specified or found
                primary_score_config = scorecard_instance.scores[0]
                primary_score_name = primary_score_config.get('name', 'Score 0')
                primary_score_index = 0
                logging.info(f"Using first score as primary: {primary_score_config.get('name')} (ID: {primary_score_config.get('id')})")
                logging.info(f"Using first score '{primary_score_name}' for fetching samples.")

            # Resolve the canonical scorecard name, key, and ID
            scorecard_name_resolved = None
            scorecard_key_resolved = None
            scorecard_id_resolved = None
            if hasattr(scorecard_instance, 'properties') and isinstance(scorecard_instance.properties, dict):
                scorecard_name_resolved = scorecard_instance.properties.get('name')
                scorecard_key_resolved = scorecard_instance.properties.get('key')
                scorecard_id_resolved = scorecard_instance.properties.get('id')
                logging.info(f"Resolved from properties: name='{scorecard_name_resolved}', key='{scorecard_key_resolved}', id='{scorecard_id_resolved}' (type: {type(scorecard_id_resolved)})")
            elif hasattr(scorecard_instance, 'name') and not callable(scorecard_instance.name):
                scorecard_name_resolved = scorecard_instance.name
                scorecard_key_resolved = getattr(scorecard_instance, 'key', None)
                scorecard_id_resolved = getattr(scorecard_instance, 'id', None)
                logging.info(f"Resolved from attributes: name='{scorecard_name_resolved}', key='{scorecard_key_resolved}', id='{scorecard_id_resolved}' (type: {type(scorecard_id_resolved)})")
            else:
                scorecard_name_resolved = scorecard # Fallback to initial identifier
                scorecard_key_resolved = scorecard # Fallback to initial identifier
                scorecard_id_resolved = scorecard # Fallback to initial identifier
                logging.info(f"Using fallback: name='{scorecard_name_resolved}', key='{scorecard_key_resolved}', id='{scorecard_id_resolved}' (type: {type(scorecard_id_resolved)})")
            
            # Check if any cloud dataset options are provided
            use_cloud_dataset = any([data_source_name, data_source_key, data_source_id, dataset_id])
            
            if use_cloud_dataset:
                # Load samples from cloud dataset
                try:
                    if dataset_id:
                        logging.info(f"Using specific dataset ID: {dataset_id}")
                        cloud_dataset = get_dataset_by_id(client, dataset_id)
                    else:
                        # Look up data source and get latest dataset
                        data_source = lookup_data_source(
                            client, 
                            name=data_source_name, 
                            key=data_source_key, 
                            id=data_source_id
                        )
                        logging.info(f"Found data source: {data_source['name']} (ID: {data_source['id']})")
                        cloud_dataset = get_latest_dataset_for_data_source(client, data_source['id'])
                    
                    logging.info(f"Using cloud dataset: {cloud_dataset['name']} (ID: {cloud_dataset['id']})")
                    
                    labeled_samples_data = load_samples_from_cloud_dataset(
                        cloud_dataset, primary_score_name, primary_score_config,
                        number_of_samples=number_of_samples,
                        random_seed=random_seed,
                        progress_callback=tracker.update if tracker else None
                    )
                    
                except Exception as e:
                    error_msg = f"Failed to load samples from cloud dataset: {str(e)}"
                    logging.error(error_msg)
                    if tracker:
                        tracker.fail_current_stage(error_msg)
                    raise ValueError(error_msg)
            else:
                # Fetch samples using the primary score's config
                logging.info(f"Fetching samples using data source for score: '{primary_score_name}'")
                labeled_samples_data = get_data_driven_samples(
                    scorecard_instance=scorecard_instance,
                    scorecard_name=scorecard_name_resolved,
                    score_name=primary_score_name,
                    score_config=primary_score_config,
                    fresh=fresh,
                    content_ids_to_sample_set=set(content_ids_to_sample.split(',') if content_ids_to_sample else []),
                    progress_callback=tracker.update if tracker else None,
                    number_of_samples=number_of_samples,
                    random_seed=random_seed
                )
            
            logging.info(f"Retrieved {len(labeled_samples_data)} samples.")

            # Determine the subset of score names to evaluate
            subset_of_score_names = None
            if target_score_identifiers:
                 subset_of_score_names = [sc.get('name') for sc in scorecard_instance.scores 
                                            if sc.get('name') and any(sc.get('name') == tid or 
                                                                      sc.get('key') == tid or 
                                                                      str(sc.get('id', '')) == tid or
                                                                      sc.get('externalId') == tid for tid in target_score_identifiers)]
                 logging.info(f"Evaluating subset of scores: {subset_of_score_names}")
            else:
                 logging.info("Evaluating all scores in the loaded scorecard.")
                 subset_of_score_names = [sc.get('name') for sc in scorecard_instance.scores if sc.get('name')]

            # Get score ID and version ID if a specific score was targeted
            score_id_for_eval = None
            score_version_id_for_eval = None

            if primary_score_config:
                score_id_for_eval = primary_score_config.get('id')
                score_version_id_for_eval = primary_score_config.get('version')
                
                if not score_version_id_for_eval:
                    score_version_id_for_eval = primary_score_config.get('championVersionId')
                
                if not (isinstance(score_id_for_eval, str) and '-' in score_id_for_eval):
                    logging.warning(f"WARNING: Score ID for evaluation doesn't appear to be in DynamoDB UUID format: {score_id_for_eval}")
                    score_id_for_eval = None

            # Instantiate AccuracyEvaluation
            logging.info("Instantiating AccuracyEvaluation...")
            sc_id_for_eval = scorecard_id if scorecard_record else getattr(scorecard_instance, 'id', None)
            acc_id_for_eval = account.id if account else None
            eval_id_for_eval = evaluation_record.id if evaluation_record else None
            
            if not eval_id_for_eval:
                error_msg = "No evaluation ID available - check if evaluation_record was created successfully"
                logging.error(error_msg)
                if tracker:
                    tracker.fail_current_stage(error_msg)
                raise ValueError(error_msg)
            
            # For Score.from_name(), we need the integer scorecard ID from the YAML, not the UUID from dashboard
            yaml_scorecard_id = None
            
            if hasattr(scorecard_instance, 'properties') and isinstance(scorecard_instance.properties, dict):
                yaml_scorecard_id = scorecard_instance.properties.get('externalId')
                if yaml_scorecard_id and yaml_scorecard_id.isdigit():
                    yaml_scorecard_id = int(yaml_scorecard_id)
                logging.info(f"Found scorecard ID from properties.externalId: {yaml_scorecard_id} (type: {type(yaml_scorecard_id)})")
            
            if not yaml_scorecard_id and hasattr(scorecard_instance, 'scorecard_configurations') and scorecard_instance.scorecard_configurations:
                config = scorecard_instance.scorecard_configurations[0]
                yaml_scorecard_id = config.get('id')
                logging.info(f"Found scorecard ID from scorecard_configurations: {yaml_scorecard_id} (type: {type(yaml_scorecard_id)})")
            
            if not yaml_scorecard_id:
                yaml_scorecard_id = scorecard_id_resolved
                logging.info(f"Using scorecard_id_resolved: {yaml_scorecard_id} (type: {type(yaml_scorecard_id)})")
            
            if yaml and isinstance(yaml_scorecard_id, int):
                scorecard_identifier = yaml_scorecard_id
                logging.info(f"Using integer scorecard ID for YAML-loaded scorecard: {scorecard_identifier}")
            else:
                if scorecard_key_resolved:
                    scorecard_identifier = str(scorecard_key_resolved)
                elif scorecard_name_resolved:
                    scorecard_identifier = str(scorecard_name_resolved)
                elif hasattr(scorecard_instance, 'name') and callable(scorecard_instance.name):
                    scorecard_identifier = scorecard_instance.name()
                elif hasattr(scorecard_instance, 'properties') and isinstance(scorecard_instance.properties, dict):
                    scorecard_identifier = scorecard_instance.properties.get('name') or scorecard_instance.properties.get('key')
                else:
                    scorecard_identifier = str(scorecard)
                
                logging.info(f"Using scorecard identifier for AccuracyEvaluation: {scorecard_identifier} (type: {type(scorecard_identifier)})")
            
            accuracy_eval = AccuracyEvaluation(
                scorecard_name=scorecard_identifier,
                scorecard=scorecard_instance,
                labeled_samples=labeled_samples_data,
                number_of_texts_to_sample=len(labeled_samples_data),
                sampling_method='provided',
                random_seed=random_seed,
                subset_of_score_names=subset_of_score_names,
                visualize=visualize,
                task_id=task_id,
                evaluation_id=eval_id_for_eval,
                account_id=acc_id_for_eval,
                scorecard_id=sc_id_for_eval,
                score_id=score_id_for_eval,
                score_version_id=score_version_id_for_eval,
                override_folder=f"./overrides/{scorecard_name_resolved}"
            )
            logging.info(f"AccuracyEvaluation instantiated for task {task_id} and evaluation {eval_id_for_eval}")

            # Advance to Processing stage
            if tracker:
                tracker.advance_stage()
                logging.info("Entered Processing stage: Running AccuracyEvaluation")

            # Initialize final_metrics with default values
            final_metrics = {
                'accuracy': 0.0,
                'precision': 0.0,
                'alignment': 0.0,
                'recall': 0.0
            }
            
            # Run the evaluation using the AccuracyEvaluation instance
            logging.info("Running accuracy evaluation...")
            try:
                final_metrics = await accuracy_eval.run(tracker=tracker)
            except Exception as e:
                error_msg = f"Error during execution: {str(e)}"
                logging.error(error_msg)
                if tracker:
                    tracker.fail_current_stage(error_msg)
                raise
                

            # Advance to the Finalizing stage after evaluation completes
            if tracker:
                tracker.advance_stage()
            
            # Final update to the evaluation record
            if evaluation_record:
                try:
                    # Use metrics returned by AccuracyEvaluation
                    update_payload_metrics = []
                    if final_metrics.get("accuracy") is not None:
                        update_payload_metrics.append({"name": "Accuracy", "value": final_metrics["accuracy"] * 100})
                    if final_metrics.get("alignment") is not None:
                        update_payload_metrics.append({"name": "Alignment", "value": final_metrics["alignment"] * 100})
                    if final_metrics.get("precision") is not None:
                        update_payload_metrics.append({"name": "Precision", "value": final_metrics["precision"] * 100})
                    if final_metrics.get("recall") is not None:
                        update_payload_metrics.append({"name": "Recall", "value": final_metrics["recall"] * 100})

                    # Find and extract score ID and score version ID
                    score_id = None
                    score_version_id = None
                    
                    if primary_score_config:
                        score_id = primary_score_config.get('id')
                        score_version_id = primary_score_config.get('version')
                        
                        if not score_version_id:
                            score_version_id = primary_score_config.get('championVersionId')
                        
                        logging.info(f"Using score ID: {score_id} and score version ID: {score_version_id}")

                    # The allowed fields are documented in the GraphQL schema
                    update_fields = {
                        'status': "COMPLETED",
                        'accuracy': final_metrics.get("accuracy", 0) * 100,
                        'metrics': json.dumps(update_payload_metrics),
                        'estimatedRemainingSeconds': 0,
                        'processedItems': len(labeled_samples_data),
                    }
                    
                    # Add score IDs if available and correctly formatted
                    if score_id and isinstance(score_id, str) and '-' in score_id:
                        update_fields['scoreId'] = score_id
                    
                    if score_version_id:
                        update_fields['scoreVersionId'] = score_version_id
                    
                    # Add other data fields
                    if final_metrics.get("confusionMatrix"):
                        update_fields['confusionMatrix'] = json.dumps(final_metrics.get("confusionMatrix"))
                    
                    if final_metrics.get("predictedClassDistribution"):
                        update_fields['predictedClassDistribution'] = json.dumps(final_metrics.get("predictedClassDistribution"))
                    
                    if final_metrics.get("datasetClassDistribution"):
                        update_fields['datasetClassDistribution'] = json.dumps(final_metrics.get("datasetClassDistribution"))
                    
                    # Remove None values from update_fields
                    update_fields = {k: v for k, v in update_fields.items() if v is not None}
                    
                    logging.info(f"Updating evaluation with the following fields: {json.dumps(update_fields, default=str)}")
                    
                    try:
                        evaluation_record.update(**update_fields)
                        logging.info(f"Marked evaluation as COMPLETED with final accuracy: {update_payload_metrics[0]['value']:.2f}%")
                    except Exception as graphql_err:
                        logging.error(f"GraphQL error updating evaluation: {str(graphql_err)}")
                        raise
                except Exception as e:
                    logging.error(f"Could not complete evaluation record - error details: {str(e)}")
            
            # Display final results summary
            logging.info(f"\n{'='*50}\nEVALUATION RESULTS\n{'='*50}")
            logging.info(f"Completed evaluation of {len(labeled_samples_data)} samples")
            logging.info(f"Overall accuracy: {final_metrics.get('accuracy', 'N/A')}")
            logging.info(f"Precision: {final_metrics.get('precision', 'N/A')}")
            logging.info(f"Alignment: {final_metrics.get('alignment', 'N/A')}")
            logging.info(f"Recall: {final_metrics.get('recall', 'N/A')}")

        except Exception as e:
            logging.error(f"Evaluation failed: {str(e)}")
            if task and tracker:
                tracker.fail_processing(str(e), traceback.format_exc())
            elif task:
                task.update(status='FAILED', errorMessage=str(e), errorDetails=traceback.format_exc())
            raise

    # Create and run the event loop
    logging.info("=== ABOUT TO START EVENT LOOP AND CALL _run_accuracy ===")
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        logging.info("=== CALLING loop.run_until_complete(_run_accuracy()) ===")
        loop.run_until_complete(_run_accuracy())
    except asyncio.CancelledError:
        logging.info("Task was cancelled - cleaning up...")
    except Exception as e:
        logging.error(f"Error during execution: {e}")
        raise
    finally:
        try:
            tasks = [t for t in asyncio.all_tasks(loop) 
                    if not t.done()]
            if tasks:
                loop.run_until_complete(
                    asyncio.wait(tasks, timeout=2.0)
                )
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

def get_data_driven_samples(
    scorecard_instance, 
    scorecard_name, 
    score_name, 
    score_config, 
    fresh, 
    content_ids_to_sample_set,
    progress_callback=None,
    number_of_samples=None,
    random_seed=None
):
    logging.info(f"=== Starting get_data_driven_samples ===")
    logging.info(f"scorecard_name: {scorecard_name}")
    logging.info(f"score_name: {score_name}")
    logging.info(f"fresh: {fresh}")
    logging.info(f"number_of_samples: {number_of_samples}")
    logging.info(f"random_seed: {random_seed}")
    
    # Get score class name for error messages
    score_class_name = score_config.get('class', 'UnknownScore')
    
    try:
        # Use the standardized Score.load() method instead of manual instantiation
        try:
            score_instance = Score.load(
                scorecard_identifier=scorecard_name,
                score_name=score_name,
                use_cache=True,  # Use cached YAML files when available (supports --yaml mode)
                yaml_only=False  # Allow API calls if needed
            )
            logging.info(f"Successfully loaded score '{score_name}' using Score.load()")
        except ValueError as load_error:
            logging.warning(f"Score.load() failed: {load_error}")
            # Fallback to manual instantiation for backward compatibility
            score_class_name = score_config['class']
            score_module_path = f'plexus.scores.{score_class_name}'
            score_module = importlib.import_module(score_module_path)
            score_class = getattr(score_module, score_class_name)

            score_config['scorecard_name'] = scorecard_name
            score_config['score_name'] = score_name
            score_instance = score_class(**score_config)
            logging.info(f"Fallback to manual instantiation successful for '{score_name}'")

        # ADD THESE LOGGING STATEMENTS:
        logging.info(f"=== DEBUGGING SCORE CONFIGURATION ===")
        logging.info(f"Score name: {score_name}")
        logging.info(f"Score class: {score_class_name}")
        logging.info(f"Full score_config keys: {list(score_config.keys())}")
        
        if 'data' in score_config:
            logging.info(f"Data config found: {score_config['data']}")
            data_config = score_config['data']
            if isinstance(data_config, dict):
                logging.info(f"Data config keys: {list(data_config.keys())}")
                if 'queries' in data_config:
                    logging.info(f"Queries found: {data_config['queries']}")
                    logging.info(f"Number of queries: {len(data_config['queries']) if isinstance(data_config['queries'], list) else 'not a list'}")
                else:
                    logging.info("No 'queries' key found in data config")
                if 'searches' in data_config:
                    logging.info(f"Searches found: {data_config['searches']}")
                    logging.info(f"Number of searches: {len(data_config['searches']) if isinstance(data_config['searches'], list) else 'not a list'}")
                else:
                    logging.info("No 'searches' key found in data config")
            else:
                logging.info(f"Data config is not a dict, type: {type(data_config)}")
        else:
            logging.info("No 'data' key found in score_config")
        logging.info(f"=== END DEBUGGING SCORE CONFIGURATION ===")

        # Load and process the data
        logging.info("Loading data...")
        score_instance.load_data(data=score_config['data'], fresh=fresh)
        logging.info("Processing data...")
        score_instance.process_data()

        # Check if dataframe exists and has data
        if not hasattr(score_instance, 'dataframe'):
            error_msg = f"Score instance {score_class_name} does not have a 'dataframe' attribute after data loading"
            logging.error(error_msg)
            # Don't raise here - let the general exception handler catch it
            return []
        
        if score_instance.dataframe is None:
            error_msg = f"Score instance {score_class_name} dataframe is None after data loading"
            logging.error(error_msg)
            # Don't raise here - let the general exception handler catch it
            return []
        
        if len(score_instance.dataframe) == 0:
            error_msg = f"Score instance {score_class_name} dataframe is empty after data loading"
            logging.error(error_msg)
            logging.error("This could be caused by:")
            logging.error("1. No data matching the specified criteria")
            logging.error("2. Database connectivity issues")
            logging.error("3. Invalid data configuration")
            logging.error("4. Data cache issues when using --fresh flag")
            # Don't raise here - let the general exception handler catch it
            return []

        logging.info(f"Successfully loaded dataframe with {len(score_instance.dataframe)} rows")

        # Sample the dataframe if number_of_samples is specified
        if number_of_samples and number_of_samples < len(score_instance.dataframe):
            logging.info(f"Sampling {number_of_samples} records from {len(score_instance.dataframe)} total records")
            score_instance.dataframe = score_instance.dataframe.sample(n=number_of_samples, random_state=random_seed)
            actual_sample_count = number_of_samples
            logging.info(f"Using random_seed: {random_seed if random_seed is not None else 'None (fully random)'}")
        else:
            actual_sample_count = len(score_instance.dataframe)
            logging.info(f"Using all {actual_sample_count} records (no sampling needed)")

        # Set the actual count as our single source of truth right when we find it
        if progress_callback and hasattr(progress_callback, '__self__'):
            tracker = progress_callback.__self__
            
            # First, set the actual total items count we just discovered
            # This is our single source of truth for the total count
            new_total = tracker.set_total_items(actual_sample_count)
            
            # Verify the total was set correctly before proceeding
            if new_total != actual_sample_count:
                raise RuntimeError(f"Failed to set total items to {actual_sample_count}")
            
            # Set the status message
            status_message = f"Successfully loaded {actual_sample_count} samples for {score_name}"
            if tracker.current_stage:
                tracker.current_stage.status_message = status_message
                # Reset processed items to 0 since we're starting fresh
                tracker.current_stage.processed_items = 0
                
                # Verify stage total_items was updated
                if tracker.current_stage.total_items != actual_sample_count:
                    raise RuntimeError(f"Stage {tracker.current_stage.name} total_items not updated correctly")
            
            # Now update progress - by this point total_items is set to actual_sample_count
            tracker.update(0, status_message)
            
            # Final verification after update
            if tracker.total_items != actual_sample_count:
                raise RuntimeError("Total items not maintained after update")
        elif progress_callback:
            progress_callback(0)

        samples = score_instance.dataframe.to_dict('records')
        logging.info(f"Converted dataframe to {len(samples)} sample records")

        content_ids_to_exclude_filename = f"tuning/{scorecard_name}/{score_name}/training_ids.txt"
        if os.path.exists(content_ids_to_exclude_filename):
            with open(content_ids_to_exclude_filename, 'r') as file:
                content_ids_to_exclude = file.read().splitlines()
            samples = [sample for sample in samples if str(sample['content_id']) not in content_ids_to_exclude]
            logging.info(f"Number of samples after filtering out training examples: {len(samples)}")

        # Filter samples based on content_ids_to_sample if provided
        if content_ids_to_sample_set:
            content_ids_as_integers = {int(content_id) for content_id in content_ids_to_sample_set}
            samples = [sample for sample in samples if sample['content_id'] in content_ids_as_integers]
            logging.info(f"Number of samples after filtering by specified content IDs: {len(samples)}")

        score_name_column_name = score_name
        if score_config.get('label_score_name'):
            score_name = score_config['label_score_name']
        if score_config.get('label_field'):
            score_name_column_name = f"{score_name} {score_config['label_field']}"

        processed_samples = []
        for sample in samples:
            # Get metadata from the sample if it exists
            metadata = sample.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    logging.warning(f"Failed to parse metadata as JSON for content_id {sample.get('content_id')}")
                    metadata = {}
            
            # Create the sample dictionary with metadata included
            processed_sample = {
                'text': sample.get('text', ''),
                f'{score_name_column_name}_label': sample.get(score_name_column_name, ''),
                'content_id': sample.get('content_id', ''),
                'columns': {
                    **{k: v for k, v in sample.items() if k not in ['text', score_name, 'content_id', 'metadata']},
                    'metadata': metadata  # Include the metadata in the columns
                }
            }
            processed_samples.append(processed_sample)
        
        logging.info(f"=== Completed get_data_driven_samples successfully ===")
        logging.info(f"Returning {len(processed_samples)} processed samples")
        
        # No need for a final progress update here since we're just returning the samples
        # The actual processing/progress will happen when these samples are used
        return processed_samples
        
    except Exception as e:
        logging.error(f"=== Error in get_data_driven_samples ===")
        logging.error(f"Error type: {type(e).__name__}")
        logging.error(f"Error message: {str(e)}")
        logging.error("This error occurred while trying to load labeled samples for evaluation")
        if hasattr(e, '__traceback__'):
            import traceback
            logging.error(f"Full traceback: {traceback.format_exc()}")
        
        # Return empty list on error to prevent further issues
        logging.error("Returning empty list due to error")
        return []

def get_csv_samples(csv_filename):
    if not os.path.exists(csv_filename):
        logging.error(f"labeled-samples.csv not found at {csv_filename}")
        return []

    df = pd.read_csv(csv_filename)
    return df.to_dict('records')

# *** START ADDITION: Helper functions for JSON serializability ***
def is_json_serializable(obj):
    try:
        # Use a basic check first for common types
        if isinstance(obj, (str, int, float, bool, type(None))):
             return True
        # Try dumping for more complex structures
        json.dumps(obj)
        return True
    except (TypeError, OverflowError):
        return False

def check_dict_serializability(d, path=""):
    non_serializable_paths = []
    if not isinstance(d, dict):
        if not is_json_serializable(d):
            # Log the problematic object type directly
            logging.warning(f"Non-serializable object found at path '{path if path else '<root>'}': type={type(d)}")
            non_serializable_paths.append(path if path else "<root>")
        return non_serializable_paths

    for k, v in d.items():
        current_path = f"{path}.{k}" if path else k
        if isinstance(v, dict):
            non_serializable_paths.extend(check_dict_serializability(v, current_path))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                item_path = f"{current_path}[{i}]"
                # Check items within the list recursively for dicts/lists, or directly for primitives
                if isinstance(item, dict):
                    non_serializable_paths.extend(check_dict_serializability(item, item_path))
                elif isinstance(item, list):
                     # Handle nested lists if necessary, though less common in typical results
                     pass # Or add recursive list check if needed
                elif not is_json_serializable(item):
                    logging.warning(f"Non-serializable list item found at path '{item_path}': type={type(item)}")
                    non_serializable_paths.append(item_path)
        elif not is_json_serializable(v):
            # Log the problematic object type directly
            logging.warning(f"Non-serializable value found at path '{current_path}': type={type(v)}")
            non_serializable_paths.append(current_path)
            
    return non_serializable_paths
# *** END ADDITION ***

def score_text_wrapper(scorecard_instance, text, score_name, scorecard_name=None, executor=None):
    """Wrapper to handle the scoring of text with proper error handling and logging.
    
    This function is called from within an async context (_run_accuracy), 
    so we expect an event loop to be running. We use ThreadPoolExecutor to run 
    the async score_entire_text method in a separate thread to avoid nested loop issues.
    """
    import asyncio
    import inspect
    import concurrent.futures
    logging.debug(f"Attempting to score text with score: {score_name}")
    
    # Create metadata dictionary
    metadata = {"scorecard_name": scorecard_name} if scorecard_name else {}
    
    try:
        # Get the coroutine from score_entire_text function
        score_entire_text_coroutine = scorecard_instance.score_entire_text(
                           text=text, 
                           subset_of_score_names=[score_name],
                           metadata=metadata)
        
        # Check if we got a coroutine (async function result)
        if inspect.iscoroutine(score_entire_text_coroutine):
            logging.debug(f"Detected coroutine result. Running in ThreadPoolExecutor.")
            # Since we are called from within a running loop (_run_accuracy),
            # run the coroutine in a separate thread using asyncio.run.
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, score_entire_text_coroutine)
                result = future.result()
        else:
            # This case should ideally not happen if score_entire_text is always async
            logging.warning(f"Expected coroutine from score_entire_text but got direct result")
            result = score_entire_text_coroutine
        
        # Process the result
        if result is None:
            logging.warning(f"No result returned for score '{score_name}'")
            return {"error": "No result returned", "value": "ERROR"}
            
        # Extract the specific score result from the returned dictionary
        if isinstance(result, dict):
            # Find the score result for our specific score name
            # The result dict keys are score IDs, values are Score.Result objects
            for score_id, score_result_obj in result.items():
                # Access the name from the Result object's parameters if available
                score_result_name = None
                if hasattr(score_result_obj, 'parameters') and hasattr(score_result_obj.parameters, 'name'):
                    score_result_name = score_result_obj.parameters.name
                elif hasattr(score_result_obj, 'name'): # Fallback if name is directly on the object
                     score_result_name = score_result_obj.name

                if score_result_name == score_name:
                    # Ensure the returned object is a Score.Result instance or similar
                    if hasattr(score_result_obj, 'value'):
                         return score_result_obj
                    else:
                         # If it doesn't look like a Result object, wrap it or return error
                         logging.warning(f"Found matching score name '{score_name}' but object type is unexpected: {type(score_result_obj)}")
                         return {"error": "Unexpected result type", "value": "ERROR", "data": str(score_result_obj)}

            # If no exact match found by name, log and return error (or first result as fallback?)
            logging.warning(f"Could not find result for score name '{score_name}' in the returned dictionary.")
            # Option 1: Return error if exact name not found
            return {"error": f"Score name '{score_name}' not found in results", "value": "ERROR"}
            # Option 2: Return the first result as a fallback (uncomment if preferred)
            # if result:
            #     first_key = next(iter(result))
            #     logging.debug(f"Returning first available result as fallback.")
            #     return result[first_key]
            # else:
            #     return {"error": "Empty result dictionary", "value": "ERROR"}
        elif hasattr(result, 'value'): # Handle case where a single Result object is returned directly
             return result
        else:
            # Handle unexpected result types
            logging.warning(f"Unexpected result type from score_entire_text: {type(result)}")
            return {"error": "Unexpected result type", "value": "ERROR", "data": str(result)}
                
    except Exception as e:
        logging.error(f"Error in score_text_wrapper: {str(e)}", exc_info=True)
        return {"error": str(e), "value": "ERROR"}

@click.group()
def evaluations():
    """Manage evaluation records in the dashboard"""
    pass

@evaluations.command()
@click.option('--account-key', default='call-criteria', help='Account key identifier')
@click.option('--type', required=True, help='Type of evaluation (e.g., accuracy, consistency)')
@click.option('--task-id', required=True, help='Associated task ID')
@click.option('--parameters', type=str, help='JSON string of evaluation parameters')
@click.option('--metrics', type=str, help='JSON string of evaluation metrics')
@click.option('--inferences', type=int, help='Number of inferences made')
@click.option('--results', type=int, help='Number of results processed')
@click.option('--cost', type=float, help='Cost of the evaluation')
@click.option('--progress', type=float, help='Progress percentage (0-100)')
@click.option('--accuracy', type=float, help='Accuracy percentage (0-100)')
@click.option('--accuracy-type', help='Type of accuracy measurement')
@click.option('--sensitivity', type=float, help='Sensitivity/recall percentage (0-100)')
@click.option('--specificity', type=float, help='Specificity percentage (0-100)')
@click.option('--precision', type=float, help='Precision percentage (0-100)')
@click.option('--status', default='PENDING', 
              type=click.Choice(['PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED']),
              help='Status of the evaluation')
@click.option('--total-items', type=int, help='Total number of items to process')
@click.option('--processed-items', type=int, help='Number of items processed')
@click.option('--error-message', help='Error message if evaluation failed')
@click.option('--error-details', type=str, help='JSON string of detailed error information')
@click.option('--scorecard-id', help='Scorecard ID (if known)')
@click.option('--scorecard-key', help='Scorecard key to look up')
@click.option('--scorecard-name', help='Scorecard name to look up')
@click.option('--score-id', help='Score ID (if known)')
@click.option('--score-key', help='Score key to look up')
@click.option('--score-name', help='Score name to look up')
@click.option('--confusion-matrix', type=str, help='JSON string of confusion matrix data')
def create(
    account_key: str,
    type: str,
    task_id: str,
    parameters: Optional[str] = None,
    metrics: Optional[str] = None,
    inferences: Optional[int] = None,
    results: Optional[int] = None,
    cost: Optional[float] = None,
    progress: Optional[float] = None,
    accuracy: Optional[float] = None,
    accuracy_type: Optional[str] = None,
    sensitivity: Optional[float] = None,
    specificity: Optional[float] = None,
    precision: Optional[float] = None,
    status: str = 'PENDING',
    total_items: Optional[int] = None,
    processed_items: Optional[int] = None,
    error_message: Optional[str] = None,
    error_details: Optional[str] = None,
    scorecard_id: Optional[str] = None,
    scorecard_key: Optional[str] = None,
    scorecard_name: Optional[str] = None,
    score_id: Optional[str] = None,
    score_key: Optional[str] = None,
    score_name: Optional[str] = None,
    confusion_matrix: Optional[str] = None,
):
    """Create a new evaluation record"""
    client = create_client()
    
    try:
        # First get the account
        logging.info(f"Looking up account with key: {account_key}")
        account = Account.get_by_key(account_key, client)
        logging.info(f"Found account: {account.name} ({account.id})")
        
        # Verify task exists
        logging.info(f"Verifying task ID: {task_id}")
        task = Task.get_by_id(task_id, client)
        if not task:
            error_msg = f"Task with ID {task_id} not found"
            logging.error(error_msg)
            raise ValueError(error_msg)
        logging.info(f"Found task: {task.id}")
        
        # Build input dictionary with all provided values
        input_data = {
            'type': type,
            'accountId': account.id,
            'status': status,
            'taskId': task_id
        }
        
        # Look up scorecard if any identifier was provided
        if any([scorecard_id, scorecard_key, scorecard_name]):
            if scorecard_id:
                logging.info(f"Using provided scorecard ID: {scorecard_id}")
                scorecard = DashboardScorecard.get_by_id(scorecard_id, client)
            elif scorecard_key:
                logging.info(f"Looking up scorecard by key: {scorecard_key}")
                scorecard = DashboardScorecard.get_by_key(scorecard_key, client)
            else:
                logging.info(f"Looking up scorecard by name: {scorecard_name}")
                scorecard = DashboardScorecard.get_by_name(scorecard_name, client)
            logging.info(f"Found scorecard: {scorecard.name} ({scorecard.id})")
            input_data['scorecardId'] = scorecard.id
        
        # Look up score if any identifier was provided
        if any([score_id, score_key, score_name]):
            if score_id:
                logging.info(f"Using provided score ID: {score_id}")
                score = DashboardScore.get_by_id(score_id, client)
            elif score_key:
                logging.info(f"Looking up score by key: {score_key}")
                score = DashboardScore.get_by_key(score_key, client)
            else:
                logging.info(f"Looking up score by name: {score_name}")
                score = DashboardScore.get_by_name(score_name, client)
            logging.info(f"Found score: {score.name} ({score.id})")
            input_data['scoreId'] = score.id
        
        # Add optional fields if provided
        if parameters: input_data['parameters'] = parameters
        if metrics: input_data['metrics'] = metrics
        if inferences is not None: input_data['inferences'] = inferences
        if results is not None: input_data['results'] = results
        if cost is not None: input_data['cost'] = cost
        if progress is not None: input_data['progress'] = progress
        if accuracy is not None: input_data['accuracy'] = accuracy
        if accuracy_type: input_data['accuracyType'] = accuracy_type
        if sensitivity is not None: input_data['sensitivity'] = sensitivity
        if specificity is not None: input_data['specificity'] = specificity
        if precision is not None: input_data['precision'] = precision
        if total_items is not None: input_data['totalItems'] = total_items
        if processed_items is not None: input_data['processedItems'] = processed_items
        if error_message: input_data['errorMessage'] = error_message
        if error_details is not None: input_data['errorDetails'] = error_details
        if confusion_matrix: input_data['confusionMatrix'] = confusion_matrix
        
        # Create the evaluation
        logging.info("Creating evaluation...")
        evaluation = DashboardEvaluation.create(client=client, **input_data)
        logging.info(f"Created evaluation: {evaluation.id}")
        
        # Output results
        click.echo(f"Created evaluation: {evaluation.id}")
        click.echo(f"Type: {evaluation.type}")
        click.echo(f"Status: {evaluation.status}")
        click.echo(f"Created at: {evaluation.createdAt}")
        
    except Exception as e:
        logging.error(f"Error creating evaluation: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)

@evaluations.command()
@click.argument('id', required=True)
@click.option('--type', help='Type of evaluation (e.g., accuracy, consistency)')
@click.option('--status',
              type=click.Choice(['PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED']),
              help='Status of the evaluation')
@click.option('--parameters', type=str, help='JSON string of evaluation parameters')
@click.option('--metrics', type=str, help='JSON string of evaluation metrics')
@click.option('--inferences', type=int, help='Number of inferences made')
@click.option('--results', type=int, help='Number of results processed')
@click.option('--cost', type=float, help='Cost of the evaluation')
@click.option('--progress', type=float, help='Progress percentage (0-100)')
@click.option('--accuracy', type=float, help='Accuracy percentage (0-100)')
@click.option('--accuracy-type', help='Type of accuracy measurement')
@click.option('--sensitivity', type=float, help='Sensitivity/recall percentage (0-100)')
@click.option('--specificity', type=float, help='Specificity percentage (0-100)')
@click.option('--precision', type=float, help='Precision percentage (0-100)')
@click.option('--total-items', type=int, help='Total number of items to process')
@click.option('--processed-items', type=int, help='Number of items processed')
@click.option('--error-message', help='Error message if evaluation failed')
@click.option('--error-details', type=str, help='JSON string of detailed error information')
@click.option('--scorecard-id', help='Scorecard ID (if known)')
@click.option('--scorecard-key', help='Scorecard key to look up')
@click.option('--scorecard-name', help='Scorecard name to look up')
@click.option('--score-id', help='Score ID (if known)')
@click.option('--score-key', help='Score key to look up')
@click.option('--score-name', help='Score name to look up')
@click.option('--confusion-matrix', type=str, help='JSON string of confusion matrix data')
def update(
    id: str,
    type: Optional[str] = None,
    status: Optional[str] = None,
    parameters: dict = None,
    metrics: dict = None,
    inferences: list = None,
    results: list = None,
    cost: float = None,
    progress: float = None,
    accuracy: float = None,
    accuracy_type: str = None,
    sensitivity: float = None,
    specificity: float = None,
    precision: float = None,
    total_items: int = None,
    processed_items: int = None,
    error_message: str = None,
    error_details: dict = None,
    confusion_matrix: dict = None
):
    """Update an existing evaluation record"""
    client = create_client()
    
    try:
        # First get the existing evaluation
        logging.info(f"Looking up evaluation: {id}")
        evaluation = DashboardEvaluation.get_by_id(id, client)
        logging.info(f"Found evaluation: {evaluation.id}")
        
        # Build update data with only provided fields
        update_data = {}
        
        # Add optional fields if provided
        if type is not None: update_data['type'] = type
        if status is not None: update_data['status'] = status
        if parameters is not None: update_data['parameters'] = parameters
        if metrics is not None: update_data['metrics'] = metrics
        if inferences is not None: update_data['inferences'] = inferences
        if results is not None: update_data['results'] = results
        if cost is not None: update_data['cost'] = cost
        if progress is not None: update_data['progress'] = progress
        if accuracy is not None: update_data['accuracy'] = accuracy
        if accuracy_type is not None: update_data['accuracyType'] = accuracy_type
        if sensitivity is not None: update_data['sensitivity'] = sensitivity
        if specificity is not None: update_data['specificity'] = specificity
        if precision is not None: update_data['precision'] = precision
        if total_items is not None: update_data['totalItems'] = total_items
        if processed_items is not None: update_data['processedItems'] = processed_items
        if error_message is not None: update_data['errorMessage'] = error_message
        if error_details is not None: update_data['errorDetails'] = error_details
        if confusion_matrix is not None: update_data['confusionMatrix'] = confusion_matrix
        
        # Update the evaluation
        logging.info("Updating evaluation...")
        try:
            logging.info(f"Updating evaluation record {evaluation.id} with: {update_data}")
            mutation = """mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                updateEvaluation(input: $input) {
                    id
                    scorecardId
                    scoreId
                }
            }"""
            client.execute(mutation, {
                'input': {
                    'id': evaluation.id,
                    **update_data
                }
            })
            logging.info("Successfully updated evaluation record with scorecard ID")
        except Exception as e:
            logging.error(f"Failed to update evaluation record with IDs: {str(e)}")
            # Continue execution even if update fails
        
        # Output results
        click.echo(f"Updated evaluation: {evaluation.id}")
        click.echo(f"Type: {evaluation.type}")
        click.echo(f"Status: {evaluation.status}")
        click.echo(f"Updated at: {evaluation.updatedAt}")
        
    except Exception as e:
        logging.error(f"Error updating evaluation: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)

@evaluations.command()
@click.argument('id', required=True)
@click.option('--limit', type=int, default=1000, help='Maximum number of results to return')
def list_results(id: str, limit: int):
    """List score results for an evaluation record"""
    client = create_client()
    
    try:
        # Get evaluation with score results included
        response = client.execute("""
            query GetEvaluation($id: ID!, $limit: Int) {
                getEvaluation(id: $id) {
                    scoreResults(limit: $limit) {
                        items {
                            id
                            value
                            confidence
                            metadata
                            correct
                            createdAt
                            evaluationId
                        }
                    }
                }
            }
        """, {'id': id, 'limit': limit})
        
        # Get the items array directly from the nested response
        items = response.get('getEvaluation', {}).get('scoreResults', {}).get('items', [])
        result_count = len(items)
            
        click.echo(f"Found {result_count} score results for evaluation {id}:")
        
        for item in items:
            created = item.get('createdAt', '').replace('Z', '').replace('T', ' ')
            click.echo(
                f"ID: {item.get('id')}, "
                f"EvaluationId: {item.get('evaluationId')}, "
                f"Value: {item.get('value')}, "
                f"Confidence: {item.get('confidence')}, "
                f"Correct: {item.get('correct')}, "
                f"Created: {created}"
            )
        
    except Exception as e:
        logging.error(f"Error listing results: {e}")
        click.echo(f"Error: {e}", err=True)