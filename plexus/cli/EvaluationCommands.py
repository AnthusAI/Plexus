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

def load_scorecard_from_api(scorecard_identifier: str, score_names=None):
    """
    Load a scorecard from the Plexus Dashboard API.
    
    Args:
        scorecard_identifier: A string that can identify the scorecard (id, key, name, etc.)
        score_names: Optional list of specific score names to load
        
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
    
    logging.info(f"Loading scorecard '{scorecard_identifier}' from API")
    
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
        except Exception as e:
            error_msg = f"Error identifying target scores: {str(e)}"
            logging.error(error_msg)
            raise ValueError(error_msg) from e
        
        # 4. Iteratively fetch configurations with dependency discovery
        try:
            scores_config = iteratively_fetch_configurations(client, scorecard_structure, target_scores)
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
        
        # Simulate successful completion
        console.print("\n[bold green]Dry run completed successfully.[/bold green]")
        console.print("[dim]No actual evaluation or database operations were performed.[/dim]")
        console.print("[dim]To run with actual database operations, remove the --dry-run flag.[/dim]")
        return
    
    # Original implementation for non-dry-run mode
    async def _run_accuracy():
        nonlocal task_id  # Make task_id accessible to modify in the async function
        experiment = None
        task = None
        evaluation_record = None  # Track the evaluation record
        tracker = None  # Initialize tracker at the top level
        scorecard_record = None  # Initialize scorecard record at the top level
        score_id = None  # Initialize score ID at the top level
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
                        logging.info(f"Successfully created and verified task: {task.id}")

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

                            logging.info("Creating initial Evaluation record...")
                            logging.info(f"Creating evaluation with params:\n{json.dumps(experiment_params, indent=2)}")
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
                target_score_identifiers = score.split(',') if score else None
                try:
                    scorecard_instance = load_scorecard_from_api(scorecard, target_score_identifiers)
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
            
            # Extract scores
            single_scores = []
            
            if score:
                # Split comma separated score identifiers
                target_score_identifiers = [identifier.strip() for identifier in score.split(',')]
                for target_score_identifier in target_score_identifiers:
                    found = False
                    # First, try to find the score directly by name in the scores list
                    for i, score_obj in enumerate(scorecard_instance.scores):
                        if (score_obj.get('name') == target_score_identifier or
                            score_obj.get('key') == target_score_identifier or
                            str(score_obj.get('id', '')) == target_score_identifier or
                            score_obj.get('externalId') == target_score_identifier):
                            single_scores.append((i, score_obj))
                            found = True
                            break
                    
                    if not found:
                        logging.warning(f"Could not find score with identifier '{target_score_identifier}'")
            
            # If no specific scores requested, use all scores
            if not single_scores:
                single_scores = list(enumerate(scorecard_instance.scores))
                
            if not single_scores:
                error_msg = "No scores found in scorecard configuration"
                logging.error(error_msg)
                if tracker:
                    tracker.fail_current_stage(error_msg)
                raise ValueError(error_msg)
            
            # Convert content IDs to a set for lookups
            content_ids_to_sample_set = set()
            if content_ids_to_sample:
                content_ids_to_sample_set = set(content_ids_to_sample.split(','))

            # Process the samples
            progress_unit = 1.0 / len(single_scores) if single_scores else 0
            progress_so_far = 0.0
            
            # Create samples for each score
            for i, (score_index, score_config) in enumerate(single_scores):
                try:
                    score_name = score_config.get('name', f"Score {score_index+1}")
                    logging.info(f"Processing score '{score_name}'")
                    
                    # Check for Score record to update the evaluation with
                    if scorecard_record and not dry_run:
                        try:
                            # Look up Score record via API
                            score_key = score_config.get('key', None)
                            if score_key:
                                logging.info(f"Looking up Score record for key: {score_key}")
                                score_record = DashboardScore.list_by_key_and_scorecard_id(
                                    key=score_key, 
                                    scorecardId=scorecard_record.id,
                                    client=client
                                )
                                if score_record:
                                    score_id = score_record.id
                                    logging.info(f"Found Score record with ID: {score_id}")
                                    
                                    # Update evaluation record with score ID for this iteration
                                    if evaluation_record:
                                        logging.info(f"Updating evaluation record with score ID: {score_id}")
                                        evaluation_record.update(scoreId=score_id)
                                        logging.info(f"Successfully updated evaluation with score ID")
                        except Exception as e:
                            logging.warning(f"Could not find Score record: {str(e)}")
                    elif dry_run:
                        logging.info(f"[DRY RUN] Skipping Score record lookup for: {score_name}")
                        score_id = f"mock-score-id-{i}"
                        logging.info(f"[DRY RUN] Using mock score ID: {score_id}")
                        
                        # Update mock evaluation with score ID
                        if evaluation_record:
                            evaluation_record.scoreId = score_id
                            logging.info(f"[DRY RUN] Updated evaluation with score ID: {score_id}")
                    
                    # ... code that processes samples ...
                    
                    # When creating score results
                    for result_data in results_to_create:
                        try:
                            if not dry_run:
                                # Create the ScoreResult record
                                ScoreResult.create(
                                    client=client,
                                    **result_data
                                )
                                logging.debug(f"Created score result: {result_data.get('contentId')}")
                            else:
                                # Log what would have been created in dry run mode
                                logging.debug(f"[DRY RUN] Would create score result: {json.dumps(truncate_dict_strings(result_data, 100))}")
                        except Exception as e:
                            if not dry_run:
                                logging.error(f"Error creating score result: {str(e)}")
                            else:
                                logging.debug(f"[DRY RUN] Error simulation for score result creation: {str(e)}")
                    
                    # Update the evaluation after processing each score
                    if evaluation_record and not dry_run:
                        try:
                            # Update with current metrics
                            evaluation_record.update(
                                accuracy=metrics["accuracy"],
                                processedItems=processed_items,
                                status="RUNNING",
                                estimatedRemainingSeconds=estimated_remaining_seconds,
                                metrics=json.dumps(metrics)
                            )
                            logging.info(f"Updated evaluation record with accuracy: {metrics['accuracy']:.2f}%")
                        except Exception as e:
                            logging.warning(f"Could not update evaluation record: {str(e)}")
                    elif evaluation_record and dry_run:
                        # Log the update that would happen in dry run mode
                        logging.info(f"[DRY RUN] Would update evaluation with accuracy: {metrics['accuracy']:.2f}%")
                        # Update mock properties for consistency
                        evaluation_record.accuracy = metrics["accuracy"]
                        evaluation_record.processedItems = processed_items
                        evaluation_record.status = "RUNNING"
                        evaluation_record.estimatedRemainingSeconds = estimated_remaining_seconds
                        evaluation_record.metrics = json.dumps(metrics)
                
                except Exception as score_error:
                    logging.error(f"Error processing score {score_name}: {str(score_error)}")
                    traceback.print_exc()
                    if not dry_run and task:
                        task.fail_processing(f"Error in score {score_name}: {str(score_error)}")
                    elif dry_run and task:
                        logging.info(f"[DRY RUN] Would mark task as failed: Error in score {score_name}: {str(score_error)}")
                    raise
            
            # Final update to the evaluation record
            if evaluation_record and not dry_run:
                try:
                    final_metrics = {
                        "accuracy": evaluation_metrics["accuracy"],
                        "precision": evaluation_metrics.get("precision"),
                        "sensitivity": evaluation_metrics.get("sensitivity"),
                        "specificity": evaluation_metrics.get("specificity"),
                    }
                    
                    evaluation_record.update(
                        status="COMPLETED",
                        accuracy=evaluation_metrics["accuracy"],
                        metrics=json.dumps(final_metrics),
                        completedAt=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                        estimatedRemainingSeconds=0
                    )
                    logging.info(f"Marked evaluation as COMPLETED with final accuracy: {evaluation_metrics['accuracy']:.2f}%")
                except Exception as e:
                    logging.warning(f"Could not complete evaluation record: {str(e)}")
            elif evaluation_record and dry_run:
                # Log the final update that would happen in dry run mode
                logging.info(f"[DRY RUN] Would mark evaluation as COMPLETED with final accuracy: {evaluation_metrics['accuracy']:.2f}%")
                # Update mock properties
                evaluation_record.status = "COMPLETED"
                evaluation_record.accuracy = evaluation_metrics["accuracy"]
                evaluation_record.completedAt = datetime.now(timezone.utc).isoformat()
                evaluation_record.estimatedRemainingSeconds = 0
            
            # Finalize task if needed
            if task and tracker and not dry_run:
                try:
                    tracker.complete_with_message(f"Completed accuracy evaluation with {len(all_results)} samples")
                    logging.info(f"Marked task as completed: {task.id}")
                except Exception as e:
                    logging.warning(f"Could not complete task: {str(e)}")
            elif task and dry_run:
                logging.info(f"[DRY RUN] Would mark task as completed with message: Completed accuracy evaluation with {len(all_results)} samples")
            
            # Display final results summary
            logging.info(f"\n{'='*50}\nEVALUATION RESULTS\n{'='*50}")
            logging.info(f"Completed evaluation of {len(all_results)} samples")
            logging.info(f"Overall accuracy: {evaluation_metrics['accuracy']:.2f}%")
            logging.info(f"Precision: {evaluation_metrics.get('precision', 'N/A')}")
            logging.info(f"Sensitivity: {evaluation_metrics.get('sensitivity', 'N/A')}")
            logging.info(f"Specificity: {evaluation_metrics.get('specificity', 'N/A')}")
            
            if dry_run:
                logging.info("\n[DRY RUN SUMMARY]")
                logging.info("Dry run completed successfully - no database operations were performed")
                logging.info(f"Scorecard loaded: {scorecard}")
                logging.info(f"Total scores evaluated: {len(single_scores)}")
                logging.info(f"Total samples processed: {len(all_results)}")
                logging.info("To run with actual database operations, remove the --dry-run flag")

        except Exception as e:
            logging.error(f"Evaluation failed: {str(e)}")
            if task and not dry_run:
                task.fail_processing(str(e))
            elif task and dry_run:
                logging.info(f"[DRY RUN] Would mark task as failed with error: {str(e)}")
            raise
        finally:
            if experiment:
                await experiment.cleanup()

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

    score_config['scorecard_name'] = scorecard_instance.name
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

@evaluate.command()
@click.option('--scorecard', required=True, help='Scorecard identifier (ID, name, key, or external ID)')
@click.option('--yaml', is_flag=True, help='Load scorecard from local YAML file instead of the API')
@click.option('--number-of-samples', default=100, help='Number of samples to evaluate')
@click.option('--subset-of-scores', default='', help='Comma-separated list of score names to evaluate')
@click.option('--max-workers', default=10, help='Maximum number of parallel workers')
@click.option('--dry-run', is_flag=True, help='Skip database operations (for testing API loading)')
def distribution(
    scorecard: str,
    yaml: bool,
    number_of_samples: int,
    subset_of_scores: str,
    max_workers: int,
    dry_run: bool
):
    """
    Evaluate the distribution of scores within a scorecard.
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
        if subset_of_scores:
            console.print(f"[bold]Target scores:[/bold] {subset_of_scores}")
        else:
            console.print("[bold]Target scores:[/bold] All scores in scorecard")
        console.print(f"[bold]Max workers:[/bold] {max_workers}")
        
        # Simulate successful completion
        console.print("\n[bold green]Dry run completed successfully.[/bold green]")
        console.print("[dim]No actual evaluation or database operations were performed.[/dim]")
        console.print("[dim]To run with actual database operations, remove the --dry-run flag.[/dim]")
        return
    
    # Original implementation
    start_time = time.time()
    logging.info(f"Starting distribution evaluation for Scorecard {scorecard} at {time.strftime('%H:%M:%S')}")

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
        target_score_names = subset_of_scores.split(',') if subset_of_scores else None
        try:
            scorecard_instance = load_scorecard_from_api(scorecard, target_score_names)
        except Exception as e:
            logging.error(f"Failed to load scorecard from API: {str(e)}")
            return

    # Extract score names to evaluate
    if subset_of_scores:
        scores_to_evaluate = subset_of_scores.split(',')
    else:
        scores_to_evaluate = [score['name'] for score in scorecard_instance.scores]
        
    logging.info(f"Evaluating {len(scores_to_evaluate)} scores: {', '.join(scores_to_evaluate)}")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_score = {executor.submit(evaluate_score_distribution, score_name, scorecard_instance, number_of_samples): score_name for score_name in scores_to_evaluate}
        for future in concurrent.futures.as_completed(future_to_score):
            score_name = future_to_score[future]
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error evaluating score {score_name}: {str(e)}")
                traceback.print_exc()

    end_time = time.time()
    logging.info(f"Distribution evaluation completed in {end_time - start_time:.2f} seconds")

def evaluate_score_distribution(score_name, scorecard_instance, number_of_samples):
    start_time = time.time()
    logging.info(f"Started evaluating distribution for Score {score_name} at {time.strftime('%H:%M:%S')}")
    
    score_configuration = next((score for score in scorecard_instance.scores if score['name'] == score_name), {})

    if not score_configuration:
        # Get the scorecard name safely from either properties or method
        scorecard_name = getattr(scorecard_instance, 'properties', {}).get('name') or scorecard_instance.__class__.__name__
        logging.error(f"Score with name '{score_name}' not found in scorecard '{scorecard_name}'.")
        return

    score_class_name = score_configuration['class']
    score_module_path = f'plexus.scores.{score_class_name}'
    score_module = importlib.import_module(score_module_path)
    score_class = getattr(score_module, score_class_name)

    if not isinstance(score_class, type):
        logging.error(f"{score_class_name} is not a class.")
        return

    # Get the scorecard name safely from either properties or method
    scorecard_name = getattr(scorecard_instance, 'properties', {}).get('name') or scorecard_instance.__class__.__name__
    
    # Make a copy of the score configuration to avoid modifying the original
    score_config_copy = score_configuration.copy()
    score_config_copy['scorecard_name'] = scorecard_name
    score_config_copy['score_name'] = score_name
    
    score_instance = score_class(**score_config_copy)

    score_instance.record_configuration(score_config_copy)

    logging.info(f"Loading data for {score_name} at {time.strftime('%H:%M:%S')}")
    score_instance.load_data(data=score_config_copy['data'])
    
    logging.info(f"Processing data for {score_name} at {time.strftime('%H:%M:%S')}")
    score_instance.process_data()

    logging.info(f"Starting predictions for {score_name} at {time.strftime('%H:%M:%S')}")
    sample_rows = score_instance.dataframe.sample(n=number_of_samples)
    predictions = []

    for _, row in sample_rows.iterrows():
        row_dictionary = row.to_dict()
        text = row_dictionary.get('text', '')
        metadata_str = row_dictionary.get('metadata', '{}')
        metadata = json.loads(metadata_str)
        model_input_class = getattr(score_class, 'Input')
        # Add required metadata for LangGraphScore
        if score_class_name == 'LangGraphScore':
            account_key = os.getenv('PLEXUS_ACCOUNT_KEY')
            if not account_key:
                raise ValueError("PLEXUS_ACCOUNT_KEY not found in environment")
                
            # Get scorecard key safely
            scorecard_key = getattr(scorecard_instance, 'properties', {}).get('key') or getattr(scorecard_instance, 'key', None)
            
            metadata.update({
                'account_key': account_key,
                'scorecard_key': scorecard_key,
                'score_name': score_name
            })
        prediction_result = score_instance.predict(
            model_input_class(
                text=text,
                metadata=metadata
            )
        )
        predictions.append(prediction_result)

    answer_counts = Counter(pred.score for pred in predictions)
    
    logging.info(f"\nResults for {score_name}:")
    logging.info(f"Total samples: {number_of_samples}")
    logging.info(f"Yes answers: {answer_counts['Yes']}")
    logging.info(f"No answers: {answer_counts['No']}")
    
    yes_percentage = (answer_counts['Yes'] / number_of_samples) * 100
    no_percentage = (answer_counts['No'] / number_of_samples) * 100
    
    logging.info(f"Yes percentage: {yes_percentage:.2f}%")
    logging.info(f"No percentage: {no_percentage:.2f}%")
    
    end_time = time.time()
    logging.info(f"Finished {score_name} at {time.strftime('%H:%M:%S')}. Time taken: {end_time - start_time:.2f} seconds")

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
        if error_details: input_data['errorDetails'] = error_details
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