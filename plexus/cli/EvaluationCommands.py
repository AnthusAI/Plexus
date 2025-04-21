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

from plexus.CustomLogging import logging, set_log_group
from plexus.Scorecard import Scorecard
from plexus.Registries import scorecard_registry
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

from plexus.utils import truncate_dict_strings_inner

def create_client() -> PlexusDashboardClient:
    """Create a client and log its configuration"""
    client = PlexusDashboardClient()
    logging.debug(f"Using API URL: {client.api_url}")
    return client

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

@evaluate.command()
@click.option('--scorecard', 'scorecard', default=None, help='Scorecard identifier (ID, name, key, or external ID)')
@click.option('--yaml', is_flag=True, help='Load scorecard from local YAML file instead of the API')
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
    dry_run: bool
    ):
    """
    Evaluate the accuracy of the scorecard using the current configuration against labeled samples.
    """
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
    
    # Original implementation for non-dry-run mode
    async def _run_accuracy():
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
            
            if task_id and not dry_run:
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
                if (api_url and api_key and not dry_run):
                    try:
                        # Initialize TaskProgressTracker with proper stage configs
                        stage_configs = {
                            "Setup": StageConfig(
                                order=1,
                                status_message="Setting up evaluation..."
                            ),
                            "Processing": StageConfig(
                                order=2,
                                total_items=number_of_samples,
                                status_message="Starting processing..."
                            ),
                            "Finalizing": StageConfig(
                                order=3,
                                status_message="Starting finalization..."
                            )
                        }

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
                                "task_type": "Accuracy Evaluation"  # Move type to metadata
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
                        
                        # Log complete task details
                        task_details = {
                            "id": task.id,
                            "type": task.type,
                            "target": task.target,
                            "command": task.command,
                            "description": task.description,
                            "status": task.status,
                            "dispatchStatus": task.dispatchStatus,
                            "accountId": task.accountId,
                            "scorecardId": task.scorecardId if hasattr(task, 'scorecardId') else None,
                            "scoreId": task.scoreId if hasattr(task, 'scoreId') else None,
                            "metadata": task.metadata,
                            "errorMessage": task.errorMessage if hasattr(task, 'errorMessage') else None,
                            "errorDetails": task.errorDetails if hasattr(task, 'errorDetails') else None,
                            "createdAt": task.createdAt.isoformat() if task.createdAt else None,
                            "updatedAt": task.updatedAt.isoformat() if task.updatedAt else None,
                            "startedAt": task.startedAt.isoformat() if task.startedAt else None,
                            "completedAt": task.completedAt.isoformat() if task.completedAt else None,
                            "stages": [
                                {
                                    "id": stage.id,
                                    "order": stage.order,
                                    "name": stage.name,
                                    "status": stage.status,
                                    "statusMessage": stage.statusMessage,
                                    "totalItems": stage.totalItems,
                                    "processedItems": stage.processedItems
                                }
                                for stage in task.get_stages()
                            ]
                        }
                        logging.info(f"Created task with details:\n{json.dumps(task_details, indent=2)}")

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
                            "taskId": task.id  # Add task ID directly in creation params
                        }
                        
                        try:
                            if not task or not task.id:
                                error_msg = "Cannot create evaluation record without a valid task ID"
                                logging.error(error_msg)
                                raise ValueError(error_msg)

                            logging.info(f"Creating evaluation with params:\n{json.dumps(experiment_params, indent=2)}")
                            
                            # Validate 'score' parameter
                            if score is None:
                                score = ""  # Default to empty string if None
                                logging.warning("'score' parameter is None, defaulting to empty string")
                            
                            # Parse the score option to get target score identifiers
                            target_score_identifiers = [s.strip() for s in score.split(',')] if score else []
                            
                            # Check the target scores from target_score_identifiers
                            target_id = None
                            if target_score_identifiers and target_score_identifiers[0]:
                                target_id = target_score_identifiers[0]
                                logging.info(f"Using target score identifier: {target_id}")
                                
                            evaluation_record = DashboardEvaluation.create(
                                client=client,
                                **experiment_params
                            )
                            logging.info(f"Created initial Evaluation record with ID: {evaluation_record.id}")

                            # Verify the task ID was set
                            if not evaluation_record.taskId:
                                error_msg = f"Evaluation record {evaluation_record.id} was created but task ID was not set"
                                logging.error(error_msg)
                                # Try to update it one more time
                                mutation = """mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                                    updateEvaluation(input: $input) {
                                        id
                                        taskId
                                    }
                                }"""
                                try:
                                    client.execute(mutation, {
                                        'input': {
                                            'id': evaluation_record.id,
                                            'taskId': task.id
                                        }
                                    })
                                    logging.info(f"Successfully updated task ID for evaluation {evaluation_record.id}")
                                except Exception as update_err:
                                    logging.error(f"Failed to update task ID: {str(update_err)}")
                        except Exception as eval_err:
                            logging.error(f"Error creating evaluation record: {str(eval_err)}")
                    except Exception as e:
                        logging.error(f"Error creating task or evaluation: {str(e)}")
                        raise
                elif dry_run:
                    # Create mock objects for dry run mode
                    mock_started_at = datetime.now(timezone.utc)
                    
                    # Mock task with needed methods
                    task = types.SimpleNamespace(
                        id="mock-task-id",
                        type="ACCURACY_EVALUATION",
                        target=f"evaluation/accuracy/{scorecard}",
                        command=f"evaluate accuracy --scorecard {scorecard}",
                        description=f"Accuracy evaluation for {scorecard} (Dry Run)",
                        status="RUNNING",
                        dispatchStatus="DISPATCHED",
                        accountId=account.id,
                        scorecardId=None,  # Will be set later
                        scoreId=None,      # Will be set later
                        metadata={
                            "type": "Accuracy Evaluation",
                            "scorecard": scorecard,
                            "task_type": "Accuracy Evaluation",
                            "is_dry_run": True
                        },
                        createdAt=mock_started_at,
                        updatedAt=mock_started_at,
                        startedAt=mock_started_at,
                        completedAt=None,
                        # Mock methods
                        fail_processing=lambda msg: logging.info(f"[DRY RUN] Task would fail with: {msg}"),
                        update=lambda **kwargs: logging.info(f"[DRY RUN] Task would update with: {kwargs}"),
                        get_stages=lambda: []
                    )
                    logging.info(f"Using mock task: {task.id}")
                    
                    # Mock evaluation
                    evaluation_record = types.SimpleNamespace(
                        id="mock-evaluation-id",
                        type="accuracy",
                        accountId=account.id,
                        status="SETUP",
                        accuracy=0.0,
                        totalItems=number_of_samples,
                        processedItems=0,
                        parameters=json.dumps({
                            "sampling_method": sampling_method,
                            "sample_size": number_of_samples,
                            "is_dry_run": True
                        }),
                        startedAt=mock_started_at.isoformat(),
                        estimatedRemainingSeconds=number_of_samples,
                        taskId=task.id,
                        # Mock methods
                        update=lambda **kwargs: logging.info(f"[DRY RUN] Evaluation would update with: {kwargs}")
                    )
                    logging.info(f"Using mock evaluation: {evaluation_record.id}")
            
            # Enter the Setup stage
            if tracker and not dry_run:
                tracker.current_stage.status_message = "Starting evaluation setup"
                tracker.update(current_items=0)
                logging.info("Entered Setup stage: Starting evaluation setup")
            elif dry_run:
                logging.info("[DRY RUN] Setup stage: Starting evaluation setup")
            else:
                logging.info("Running accuracy experiment...")
            
            # Load the scorecard either from YAML or API
            if yaml:
                # Load from YAML (legacy approach)
                logging.info(f"Loading scorecard '{scorecard}' from local YAML files")
                try:
                    logging.debug("Calling Scorecard.load_and_register_scorecards('scorecards/')")
                    Scorecard.load_and_register_scorecards('scorecards/')
                    logging.debug(f"Successfully loaded scorecard YAML files from scorecards/ directory")
                    
                    logging.debug(f"Looking up scorecard '{scorecard}' in scorecard_registry")
                    scorecard_class = scorecard_registry.get(scorecard)
                    
                    if scorecard_class is None:
                        error_msg = f"Scorecard with name '{scorecard}' not found."
                        logging.error(error_msg)
                        raise ValueError(error_msg)
                        
                    logging.debug(f"Instantiating scorecard class: {scorecard_class.__name__}")
                    scorecard_instance = scorecard_class(scorecard=scorecard)
                    logging.info(f"Using scorecard {scorecard} with class {scorecard_instance.__class__.__name__}")
                except Exception as e:
                    error_msg = f"Error loading scorecard from YAML: {str(e)}"
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
                    # This needs to happen before evaluation record creation
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
                                # First try to get from the configuration
                                score_version_id_for_eval = sc_config.get('version')
                                
                                # Fall back to championVersionId if available
                                if not score_version_id_for_eval:
                                    score_version_id_for_eval = sc_config.get('championVersionId')
                                
                                # Validate score_id format - must be a UUID with hyphens
                                if not (isinstance(score_id_for_eval, str) and '-' in score_id_for_eval):
                                    logging.warning(f"Early detection: Score ID doesn't appear to be in UUID format: {score_id_for_eval}")
                                    
                                    # Try to find the correct ID in the original API data
                                    if hasattr(scorecard_instance, 'properties') and scorecard_instance.properties:
                                        for section in scorecard_instance.properties.get('sections', {}).get('items', []):
                                            for score_data in section.get('scores', {}).get('items', []):
                                                if score_data.get('name') == sc_config.get('name'):
                                                    uuid_id = score_data.get('id')
                                                    if isinstance(uuid_id, str) and '-' in uuid_id:
                                                        logging.info(f"Found correctly formatted UUID for {sc_config.get('name')}: {uuid_id}")
                                                        score_id_for_eval = uuid_id
                                                        # Also update version ID if available
                                                        if score_data.get('championVersionId'):
                                                            score_version_id_for_eval = score_data.get('championVersionId')
                                
                                if isinstance(score_id_for_eval, str) and '-' in score_id_for_eval:
                                    logging.info(f"Found primary score early: {sc_config.get('name')} with ID: {score_id_for_eval}")
                                    logging.info(f"Using champion version ID: {score_version_id_for_eval}")
                                else:
                                    logging.warning(f"Could not find correctly formatted UUID ID for {sc_config.get('name')}")
                                    score_id_for_eval = None  # Clear invalid ID
                                break
                    
                    # If no match found, fall back to first score
                    if not score_id_for_eval and scorecard_instance.scores:
                        sc_config = scorecard_instance.scores[0]
                        score_id_for_eval = sc_config.get('id')
                        # First try to get from the configuration
                        score_version_id_for_eval = sc_config.get('version')
                        
                        # Fall back to championVersionId if available
                        if not score_version_id_for_eval:
                            score_version_id_for_eval = sc_config.get('championVersionId')
                        
                        # Validate score_id format - must be a UUID with hyphens
                        if not (isinstance(score_id_for_eval, str) and '-' in score_id_for_eval):
                            logging.warning(f"First score fallback: ID doesn't appear to be in UUID format: {score_id_for_eval}")
                            
                            # Try to find the correct ID in the original API data
                            if hasattr(scorecard_instance, 'properties') and scorecard_instance.properties:
                                for section in scorecard_instance.properties.get('sections', {}).get('items', []):
                                    for score_data in section.get('scores', {}).get('items', []):
                                        if score_data.get('name') == sc_config.get('name'):
                                            uuid_id = score_data.get('id')
                                            if isinstance(uuid_id, str) and '-' in uuid_id:
                                                logging.info(f"Found correctly formatted UUID for {sc_config.get('name')}: {uuid_id}")
                                                score_id_for_eval = uuid_id
                                                # Also update version ID if available
                                                if score_data.get('championVersionId'):
                                                    score_version_id_for_eval = score_data.get('championVersionId')
                        
                        if isinstance(score_id_for_eval, str) and '-' in score_id_for_eval:
                            logging.info(f"Using first score for evaluation record: {sc_config.get('name')} with ID: {score_id_for_eval}")
                            logging.info(f"Using champion version ID: {score_version_id_for_eval}")
                        else:
                            logging.warning(f"Could not find correctly formatted UUID ID for {sc_config.get('name')}")
                            score_id_for_eval = None  # Clear invalid ID
                    
                    logging.info(f"===== EARLY SCORE ID DETECTION =====")
                    logging.info(f"Score ID: {score_id_for_eval}")
                    logging.info(f"Score Version ID: {score_version_id_for_eval}")
                    logging.info(f"===================================")
                    
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
                    
                if scorecard_key and not dry_run:
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
                            logging.info(f"Updating evaluation record {evaluation_record.id} with data: " +
                                        f"{{\"id\": \"{evaluation_record.id}\", \"scorecardId\": \"{scorecard_id}\"}}")
                            evaluation_record.update(scorecardId=scorecard_id)
                            logging.info(f"Successfully updated evaluation record with IDs")
                    else:
                        logging.warning(f"Could not find matching dashboard scorecard for key {scorecard_key}")
                elif dry_run:
                    logging.info(f"[DRY RUN] Skipping scorecard record lookup for key: {scorecard_key}")
                    # Create a mock scorecard record
                    scorecard_id = "mock-scorecard-id"
                    scorecard_record = types.SimpleNamespace(
                        id=scorecard_id,
                        key=scorecard_key,
                        name=getattr(scorecard_instance, 'name', None) or 
                             getattr(scorecard_instance, 'properties', {}).get('name', "Mock Scorecard")
                    )
                    logging.info(f"Using mock scorecard record: {scorecard_record.name} ({scorecard_id})")
                    
                    # Update mock task and evaluation with scorecard ID
                    if task:
                        task.scorecardId = scorecard_id
                        logging.info(f"[DRY RUN] Updated task with scorecard ID: {scorecard_id}")
                        
                    if evaluation_record:
                        evaluation_record.scorecardId = scorecard_id
                        logging.info(f"[DRY RUN] Updated evaluation with scorecard ID: {scorecard_id}")
                else:
                    logging.warning("Could not find scorecard key")
            except Exception as e:
                if dry_run:
                    logging.info(f"[DRY RUN] Ignoring scorecard lookup error: {str(e)}")
                else:
                    logging.warning(f"Could not find matching dashboard scorecard: {str(e)}")
            
            if tracker and not dry_run:
                tracker.update(current_items=0)
            
            # Determine the primary score for fetching data
            # Validate 'score' parameter
            if score is None:
                score = ""  # Default to empty string if None
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

            # Log what we have loaded in the scorecard_instance
            logging.info("===== SCORECARD INSTANCE SCORE DATA =====")
            for idx, score_data in enumerate(scorecard_instance.scores):
                logging.info(f"Score {idx+1}:")
                logging.info(f"  Name: {score_data.get('name', 'Unknown')}")
                logging.info(f"  ID: {score_data.get('id', 'Unknown')}")
                logging.info(f"  Key: {score_data.get('key', 'Unknown')}")
                logging.info(f"  ChampionVersionId: {score_data.get('championVersionId', 'Unknown')}")
                # Check if we can find version or championVersionId via different paths
                if 'version' not in score_data and 'championVersionId' not in score_data:
                    alt_version_id = score_data.get('champion_version_id') or score_data.get('championVersion', {}).get('id')
                    if alt_version_id:
                        logging.info(f"  Found alternative version ID: {alt_version_id}")
            logging.info("=======================================")

            # Additional logging about primary score identifier
            logging.info(f"Primary score identifier from command line: {primary_score_identifier}")

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

            # Resolve the canonical scorecard name
            scorecard_name_resolved = None
            if hasattr(scorecard_instance, 'properties') and isinstance(scorecard_instance.properties, dict):
                scorecard_name_resolved = scorecard_instance.properties.get('name')
            elif hasattr(scorecard_instance, 'name') and not callable(scorecard_instance.name):
                scorecard_name_resolved = scorecard_instance.name
            else:
                scorecard_name_resolved = scorecard # Fallback to initial identifier
            
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
            # Use the names resolved during scorecard loading if available
            subset_of_score_names = None
            if target_score_identifiers:
                 # Ensure we have loaded all necessary scores during load_scorecard_from_api
                 # The 'scores' attribute of scorecard_instance should contain only the requested scores + dependencies
                 subset_of_score_names = [sc.get('name') for sc in scorecard_instance.scores 
                                            if sc.get('name') and any(sc.get('name') == tid or 
                                                                      sc.get('key') == tid or 
                                                                      str(sc.get('id', '')) == tid or
                                                                      sc.get('externalId') == tid for tid in target_score_identifiers)]
                 logging.info(f"Evaluating subset of scores: {subset_of_score_names}")
            else:
                 logging.info("Evaluating all scores in the loaded scorecard.")
                 # If no specific scores requested, evaluate all *loaded* scores
                 subset_of_score_names = [sc.get('name') for sc in scorecard_instance.scores if sc.get('name')]

            # Get score ID and version ID if a specific score was targeted
            score_id_for_eval = None
            score_version_id_for_eval = None

            if primary_score_config:
                score_id_for_eval = primary_score_config.get('id')
                # First try to get from the configuration
                score_version_id_for_eval = primary_score_config.get('version')
                
                # Fall back to championVersionId if available
                if not score_version_id_for_eval:
                    score_version_id_for_eval = primary_score_config.get('championVersionId')
                
                # Validate score_id format - should be a UUID with hyphens
                if not (isinstance(score_id_for_eval, str) and '-' in score_id_for_eval):
                    logging.warning(f"WARNING: Score ID for evaluation doesn't appear to be in DynamoDB UUID format: {score_id_for_eval}")
                    logging.warning("This will cause issues with Evaluation records. Expected format is UUID with hyphens.")
                    
                    # Look for a correctly formatted ID in all scores
                    if hasattr(scorecard_instance, 'properties') and scorecard_instance.properties:
                        for section in scorecard_instance.properties.get('sections', {}).get('items', []):
                            for score_item in section.get('scores', {}).get('items', []):
                                # Try to match by name first
                                if score_item.get('name') == primary_score_config.get('name') or not primary_score_config.get('name'):
                                    alt_id = score_item.get('id')
                                    if isinstance(alt_id, str) and '-' in alt_id:
                                        logging.info(f"Found correctly formatted UUID Score ID: {alt_id}")
                                        score_id_for_eval = alt_id
                                        # Also update score_version_id if present
                                        if score_item.get('championVersionId'):
                                            score_version_id_for_eval = score_item.get('championVersionId')
                                        break
                    
                    # If we still have an incorrectly formatted ID, skip using it
                    if not (isinstance(score_id_for_eval, str) and '-' in score_id_for_eval):
                        logging.warning(f"Could not find a correctly formatted Score ID. Not using ID: {score_id_for_eval}")
                        score_id_for_eval = None
                
                # Only log the score_id if it's correctly formatted
                if score_id_for_eval:
                    logging.info(f"Using score ID: {score_id_for_eval} and score version ID: {score_version_id_for_eval}")
                    logging.info(f"====== SCORE ID AND VERSION FOR EVALUATION ======")
                    logging.info(f"Score ID: {score_id_for_eval}")
                    logging.info(f"Score Version ID: {score_version_id_for_eval}")
                    logging.info(f"===============================================")
                else:
                    logging.warning("No valid score ID found for evaluation.")

            # Instantiate AccuracyEvaluation
            logging.info("Instantiating AccuracyEvaluation...")
            # Ensure scorecard_id is passed correctly
            sc_id_for_eval = scorecard_id if scorecard_record else getattr(scorecard_instance, 'id', None)
            # Ensure account_id is passed correctly
            acc_id_for_eval = account.id if account else None
            # Ensure evaluation_id is passed correctly (from created record or task metadata)
            eval_id_for_eval = evaluation_record.id if evaluation_record else None
            if not eval_id_for_eval and task and task.metadata and 'evaluation_id' in task.metadata:
                eval_id_for_eval = task.metadata['evaluation_id']
                
            # Log crucial information before proceeding
            logging.info(f"=== ACCURACY EVALUATION INITIALIZATION ===")
            logging.info(f"Evaluation ID: {eval_id_for_eval}")
            logging.info(f"Scorecard ID: {sc_id_for_eval}")
            logging.info(f"Score ID: {score_id_for_eval}")
            logging.info(f"Score Version ID: {score_version_id_for_eval}")
            logging.info(f"Account ID: {acc_id_for_eval}")
            logging.info(f"Task ID: {task_id}")
            logging.info(f"=====================================")
                
            # Make sure evaluation_id is not None - it's required by AccuracyEvaluation
            if not eval_id_for_eval and not dry_run:
                # This is a critical error - AccuracyEvaluation requires an evaluation_id
                error_msg = "No evaluation ID available - check if evaluation_record was created successfully"
                logging.error(error_msg)
                if tracker:
                    tracker.fail_current_stage(error_msg)
                raise ValueError(error_msg)
            elif not eval_id_for_eval and dry_run:
                logging.info("[DRY RUN] Using mock evaluation ID since no evaluation record was created")
                # In dry run mode, we'll use a mock ID that will be set in AccuracyEvaluation.run
                eval_id_for_eval = None
            
            accuracy_eval = AccuracyEvaluation(
                scorecard_name=scorecard_name_resolved,
                scorecard=scorecard_instance,
                labeled_samples=labeled_samples_data,
                number_of_texts_to_sample=len(labeled_samples_data), # Use actual sample count
                sampling_method='provided', # Indicate samples are already provided
                random_seed=random_seed,
                subset_of_score_names=subset_of_score_names,
                visualize=visualize,
                task_id=task_id,
                evaluation_id=eval_id_for_eval,
                account_id=acc_id_for_eval,
                scorecard_id=sc_id_for_eval,
                score_id=score_id_for_eval, # Pass score_id from primary score config
                score_version_id=score_version_id_for_eval, # Pass score_version_id from primary score config
                # override_folder might be needed if AccuracyEvaluation uses it
                override_folder=f"./overrides/{scorecard_name_resolved}" # Example path
            )
            logging.info(f"AccuracyEvaluation instantiated for task {task_id} and evaluation {eval_id_for_eval}")

            # Advance to Processing stage
            if tracker:
                tracker.advance_stage()
                logging.info("Entered Processing stage: Running AccuracyEvaluation")

            # Run the evaluation using the AccuracyEvaluation instance
            logging.info("Running accuracy evaluation...")
            try:
                final_metrics = await accuracy_eval.run(tracker=tracker, dry_run=dry_run)
            except Exception as e:
                error_msg = f"Error during execution: {str(e)}"
                logging.error(error_msg)
                if tracker:
                    tracker.fail_current_stage(error_msg)
                raise ValueError(error_msg)

            # Advance to the Finalizing stage after evaluation completes
            if tracker:
                tracker.advance_stage()
            
            # Final update to the evaluation record
            if evaluation_record and not dry_run:
                try:
                    # Use metrics returned by AccuracyEvaluation
                    # Format metrics for the update payload as an array of name/value objects
                    update_payload_metrics = []
                    if final_metrics.get("accuracy") is not None:
                        update_payload_metrics.append({"name": "Accuracy", "value": final_metrics["accuracy"] * 100})
                    if final_metrics.get("precision") is not None:
                        update_payload_metrics.append({"name": "Precision", "value": final_metrics["precision"] * 100})
                    if final_metrics.get("sensitivity") is not None:
                        update_payload_metrics.append({"name": "Sensitivity", "value": final_metrics["sensitivity"] * 100})
                    if final_metrics.get("specificity") is not None:
                        update_payload_metrics.append({"name": "Specificity", "value": final_metrics["specificity"] * 100})

                    # Find and extract score ID and score version ID
                    score_id = None
                    score_version_id = None
                    
                    if primary_score_config:
                        # Extract scoreId from the primary score configuration
                        # IMPORTANT: Use the ID field which contains the DynamoDB UUID-format ID
                        # NOT the externalId which is a simple numeric ID
                        score_id = primary_score_config.get('id')
                        
                        # Log warning if the Score ID doesn't match the expected UUID format
                        if score_id and not (isinstance(score_id, str) and '-' in score_id):
                            logging.warning(f"Score ID doesn't appear to be in DynamoDB UUID format: {score_id}")
                            # Try to find the UUID ID from the primary_score_config
                            if 'externalId' in primary_score_config:
                                logging.warning(f"Found externalId: {primary_score_config.get('externalId')} which should NOT be used as the Score ID")
                            
                        # Extract scoreVersionId (version) from the configuration
                        score_version_id = primary_score_config.get('version')
                        
                        # Fall back to championVersionId if available
                        if not score_version_id:
                            score_version_id = primary_score_config.get('championVersionId')
                        
                        # Log both IDs for debugging
                        logging.info(f"Using score ID: {score_id} and score version ID: {score_version_id}")
                        logging.info(f"Score ID type: {type(score_id)}, Score Version ID type: {type(score_version_id)}")

                    # The allowed fields are documented in the GraphQL schema
                    update_fields = {
                        'status': "COMPLETED",
                        'accuracy': final_metrics.get("accuracy", 0) * 100, # Use calculated accuracy
                        'metrics': json.dumps(update_payload_metrics), # Store detailed metrics
                        'estimatedRemainingSeconds': 0,
                        'processedItems': len(labeled_samples_data), # Add processed items count
                    }
                    
                    # Add score IDs if available and correctly formatted
                    if score_id:
                        if isinstance(score_id, str) and '-' in score_id:
                            update_fields['scoreId'] = score_id
                        else:
                            logging.warning(f"Final update: Score ID not in proper UUID format: {score_id}. Not using it.")
                    
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
                    
                    # Log all fields we're sending to help debug API errors
                    logging.info(f"Updating evaluation with the following fields: {json.dumps(update_fields, default=str)}")
                    
                    # Make the update request
                    try:
                        evaluation_record.update(**update_fields)
                        logging.info(f"Marked evaluation as COMPLETED with final accuracy: {update_payload_metrics[0]['value']:.2f}%")
                    except Exception as graphql_err:
                        # Log detailed error information for GraphQL errors
                        logging.error(f"GraphQL error updating evaluation: {str(graphql_err)}")
                        if hasattr(graphql_err, 'errors'):
                            for error in getattr(graphql_err, 'errors'):
                                logging.error(f"GraphQL error details: {error}")
                        else:
                            logging.error(f"No detailed GraphQL errors available")
                        raise
                except Exception as e:
                    logging.error(f"Could not complete evaluation record - error details: {str(e)}")
                    # Print more details if possible
                    if hasattr(e, 'errors'):
                        logging.error(f"GraphQL errors: {getattr(e, 'errors')}")
            elif evaluation_record and dry_run:
                # Log the final update that would happen in dry run mode
                logging.info(f"[DRY RUN] Would mark evaluation as COMPLETED with final accuracy: {final_metrics['accuracy']:.2f}%")
                # Update mock properties
                evaluation_record.status = "COMPLETED"
                evaluation_record.accuracy = final_metrics["accuracy"]
                evaluation_record.completedAt = datetime.now(timezone.utc).isoformat()
                evaluation_record.estimatedRemainingSeconds = 0
            
            # Display final results summary
            logging.info(f"\n{'='*50}\nEVALUATION RESULTS\n{'='*50}")
            logging.info(f"Completed evaluation of {len(labeled_samples_data)} samples")
            logging.info(f"Overall accuracy: {final_metrics['accuracy']:.2f}%")
            logging.info(f"Precision: {final_metrics.get('precision', 'N/A')}")
            logging.info(f"Sensitivity: {final_metrics.get('sensitivity', 'N/A')}")
            logging.info(f"Specificity: {final_metrics.get('specificity', 'N/A')}")
            
            if dry_run:
                logging.info("\n[DRY RUN SUMMARY]")
                logging.info("Dry run completed successfully - no database operations were performed")
                logging.info(f"Scorecard loaded: {scorecard}")
                logging.info(f"Total scores evaluated: {len(subset_of_score_names)}")
                logging.info(f"Total samples processed: {len(labeled_samples_data)}")
                logging.info("To run with actual database operations, remove the --dry-run flag")

        except Exception as e:
            logging.error(f"Evaluation failed: {str(e)}")
            if task and not dry_run and tracker:
                # Use tracker to fail the task properly
                tracker.fail_processing(str(e), traceback.format_exc())
            elif task and not dry_run and not tracker:
                # Fallback if tracker wasn't initialized
                 task.update(status='FAILED', errorMessage=str(e), errorDetails=traceback.format_exc())
            elif task and dry_run:
                logging.info(f"[DRY RUN] Would mark task as failed with error: {str(e)}")
            # Ensure the exception is re-raised to be caught by the outer try/except
            raise
        finally:
            # Cleanup is handled by AccuracyEvaluation's __aexit__ if used as context manager
            # Or we might need manual cleanup if not using context manager
            # if accuracy_eval:
            #     await accuracy_eval.cleanup()
            pass # Keep simple for now

    # Create and run the event loop for non-dry-run mode
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
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
    score_class_name = score_config['class']
    score_module_path = f'plexus.scores.{score_class_name}'
    score_module = importlib.import_module(score_module_path)
    score_class = getattr(score_module, score_class_name)

    score_config['scorecard_name'] = scorecard_name
    score_config['score_name'] = score_name
    score_instance = score_class(**score_config)

    score_instance.load_data(data=score_config['data'], fresh=fresh)
    score_instance.process_data()

    # Log dataframe information
    logging.info(f"Dataframe info for score {score_name}:")
    logging.info(f"Columns: {score_instance.dataframe.columns.tolist()}")
    logging.info(f"Shape: {score_instance.dataframe.shape}")

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
    
    # No need for a final progress update here since we're just returning the samples
    # The actual processing/progress will happen when these samples are used
    return processed_samples

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