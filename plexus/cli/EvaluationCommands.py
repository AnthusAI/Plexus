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
from typing import Optional
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
from plexus.cli.stage_configurations import get_evaluation_stage_configs

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
    if os.path.exists(configuration_file_path):
        with open(configuration_file_path, 'r') as file:
            return yaml.safe_load(file)
    else:
        logging.info(f"Configuration file not found: {configuration_file_path}")
        return {}

@evaluate.command()
@click.option('--scorecard-name', 'scorecard_name', default=None, help='Name of the scorecard to evaluate')
@click.option('--use-langsmith-trace', is_flag=True, default=False, help='Activate LangSmith trace client for LangGraphScore')
@click.option('--number-of-samples', default=1, type=int, help='Number of texts to sample')
@click.option('--sampling-method', default='random', type=str, help='Method for sampling texts')
@click.option('--random-seed', default=None, type=int, help='Random seed for sampling')
@click.option('--content-ids-to-sample', default='', type=str, help='Comma-separated list of content IDs to sample')
@click.option('--score-name', default='', type=str, help='Comma-separated list of score names to evaluate')
@click.option('--experiment-label', default='', type=str, help='Label for the experiment')
@click.option('--fresh', is_flag=True, help='Pull fresh, non-cached data from the data lake.')
@click.option('--visualize', is_flag=True, default=False, help='Generate PNG visualization of LangGraph scores')
@click.option('--task-id', default=None, type=str, help='Task ID for progress tracking')
def accuracy(
    scorecard_name: str,
    use_langsmith_trace: bool,
    number_of_samples: int,
    sampling_method: str,
    random_seed: int,
    content_ids_to_sample: str,
    score_name: str,
    experiment_label: str,
    fresh: bool,
    visualize: bool,
    task_id: Optional[str]
    ):
    """
    Evaluate the accuracy of the scorecard using the current configuration against labeled samples.
    """
    async def _run_accuracy():
        nonlocal task_id  # Make task_id accessible to modify in the async function
        experiment = None
        task = None
        evaluation_record = None  # Track the evaluation record
        tracker = None  # Initialize tracker at the top level
        scorecard_record = None  # Initialize scorecard record at the top level
        score_id = None  # Initialize score ID at the top level
        try:
            # Create or get Task record for progress tracking
            client = PlexusDashboardClient()  # Create client at the top level
            account = None  # Initialize account at the top level
            
            try:
                # Get the account ID for call-criteria regardless of path
                logging.info("Looking up call-criteria account...")
                account = Account.list_by_key(key="call-criteria", client=client)
                if not account:
                    raise Exception("Could not find account with key: call-criteria")
                logging.info(f"Found account: {account.name} ({account.id})")
            except Exception as e:
                logging.error(f"Failed to get account: {str(e)}")
                raise

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
                            target=f"evaluation/accuracy/{scorecard_name}",
                            command=f"evaluate accuracy --scorecard-name {scorecard_name}",
                            description=f"Accuracy evaluation for {scorecard_name}",
                            dispatch_status="DISPATCHED",
                            prevent_new_task=False,
                            metadata={
                                "type": "Accuracy Evaluation",
                                "scorecard": scorecard_name,
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
                                update_data = {
                                    'id': evaluation_record.id,
                                    'taskId': task.id
                                }
                                logging.info(f"Attempting to update evaluation record {evaluation_record.id} with data:\n{json.dumps(update_data, indent=2)}")
                                result = client.execute(mutation, {'input': update_data})
                                logging.info(f"Update result:\n{json.dumps(result, indent=2)}")

                            # Update evaluation record with scorecard ID if we have one
                            if scorecard_record and 'id' in scorecard_record:
                                update_data = {
                                    'id': evaluation_record.id,
                                    'taskId': task.id,  # Always include task ID in updates
                                    'scorecardId': scorecard_record['id']
                                }
                                logging.info(f"Updating evaluation record {evaluation_record.id} with data:\n{json.dumps(update_data, indent=2)}")
                                mutation = """mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                                    updateEvaluation(input: $input) {
                                        id
                                        taskId
                                        scorecardId
                                    }
                                }"""
                                result = client.execute(mutation, {'input': update_data})
                                logging.info(f"Update result:\n{json.dumps(result, indent=2)}")

                            # Update evaluation record with score ID if we have one
                            if score_id:
                                update_data = {
                                    'id': evaluation_record.id,
                                    'taskId': task.id,  # Always include task ID in updates
                                    'scoreId': score_id
                                }
                                logging.info(f"Updating evaluation record {evaluation_record.id} with data:\n{json.dumps(update_data, indent=2)}")
                                mutation = """mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                                    updateEvaluation(input: $input) {
                                        id
                                        taskId
                                        scoreId
                                    }
                                }"""
                                result = client.execute(mutation, {'input': update_data})
                                logging.info(f"Update result:\n{json.dumps(result, indent=2)}")

                        except Exception as e:
                            logging.error(f"Failed to create or update Evaluation record: {str(e)}", exc_info=True)
                            raise

                    except Exception as e:
                        logging.error(f"Failed to create task: {str(e)}")
                        logging.error("Error details:", exc_info=True)
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
                    target=f"evaluation/accuracy/{scorecard_name}",
                    command=f"evaluate accuracy --scorecard-name {scorecard_name}",
                    description=f"Accuracy evaluation for {scorecard_name}",
                    dispatch_status="DISPATCHED",
                    prevent_new_task=True,  # Prevent new task creation since we have one
                    metadata={
                        "type": "Accuracy Evaluation",
                        "scorecard": scorecard_name,
                        "task_type": "Accuracy Evaluation"
                    },
                    account_id=account.id  # Now we have account.id available
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
                    logging.info(f"Creating evaluation record with params:\n{json.dumps(experiment_params, indent=2)}")
                    evaluation_record = DashboardEvaluation.create(
                        client=client,
                        **experiment_params
                    )
                    logging.info(f"Created initial Evaluation record with ID: {evaluation_record.id}")

                    # Explicitly update to ensure task ID is set
                    update_data = {
                        'id': evaluation_record.id,
                        'taskId': task.id
                    }
                    logging.info(f"Updating evaluation record {evaluation_record.id} with data:\n{json.dumps(update_data, indent=2)}")
                    mutation = """mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                        updateEvaluation(input: $input) {
                            id
                            taskId
                        }
                    }"""
                    client.execute(mutation, {'input': update_data})
                    logging.info(f"Updated Evaluation record {evaluation_record.id} with taskId: {task.id}")

                    # Update evaluation record with scorecard ID if we have one
                    if scorecard_record and 'id' in scorecard_record:
                        update_data = {
                            'id': evaluation_record.id,
                            'taskId': task.id,  # Always include task ID in updates
                            'scorecardId': scorecard_record['id']
                        }
                        logging.info(f"Updating evaluation record {evaluation_record.id} with data:\n{json.dumps(update_data, indent=2)}")
                        mutation = """mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                            updateEvaluation(input: $input) {
                                id
                                taskId
                                scorecardId
                            }
                        }"""
                        client.execute(mutation, {'input': update_data})
                        logging.info(f"Updated evaluation record with scorecard ID: {scorecard_record['id']}")

                    # Update evaluation record with score ID if we have one
                    if score_id:
                        update_data = {
                            'id': evaluation_record.id,
                            'taskId': task.id,  # Always include task ID in updates
                            'scoreId': score_id
                        }
                        logging.info(f"Updating evaluation record {evaluation_record.id} with data:\n{json.dumps(update_data, indent=2)}")
                        mutation = """mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                            updateEvaluation(input: $input) {
                                id
                                taskId
                                scoreId
                            }
                        }"""
                        client.execute(mutation, {'input': update_data})
                        logging.info(f"Updated evaluation record with score ID: {score_id}")

                except Exception as e:
                    logging.error(f"Failed to create or update Evaluation record in Celery path: {str(e)}", exc_info=True)
                    raise

            if task:
                try:
                    # Start with Setup stage
                    if tracker:
                        tracker.update(current_items=0)
                        
                        # Initial setup stage message
                        tracker.current_stage.status_message = "Starting evaluation setup..."
                        tracker.update(current_items=0)
                        logging.info("Entered Setup stage: Starting evaluation setup")

                    if use_langsmith_trace:
                        os.environ['LANGCHAIN_TRACING_V2'] = 'true'
                        tracker.current_stage.status_message = "Enabled LangSmith tracing for evaluation"
                        tracker.update(current_items=0)
                    else:
                        os.environ.pop('LANGCHAIN_TRACING_V2', None)

                    # Initialize content_ids_to_sample_set from the parameter
                    content_ids_to_sample_set = set()
                    if content_ids_to_sample:
                        content_ids_to_sample_set = {id.strip() for id in content_ids_to_sample.split(',') if id.strip()}
                        logging.info(f"Will sample from content IDs: {content_ids_to_sample_set}")

                    if not scorecard_name:
                        error_msg = "Scorecard not specified"
                        logging.error(error_msg)
                        tracker.current_stage.status_message = error_msg
                        tracker.update(current_items=0)
                        if task:
                            task.fail_processing(error_msg)
                        sys.exit(1)

                    scorecard_folder = os.path.join('scorecards', scorecard_name)
                    override_folder: str = os.path.join(scorecard_folder, 'experiments/calibrations')

                    logging.info('Running accuracy experiment...')
                    tracker.current_stage.status_message = "Loading scorecard configurations..."
                    tracker.update(current_items=0)
                    
                    Scorecard.load_and_register_scorecards('scorecards/')
                    scorecard_type = scorecard_registry.get(scorecard_name)
                    if scorecard_type is None:
                        error_msg = f"Scorecard with name '{scorecard_name}' not found."
                        logging.error(error_msg)
                        tracker.current_stage.status_message = error_msg
                        tracker.update(current_items=0)
                        if task:
                            task.fail_processing(error_msg)
                        return

                    scorecard_instance = scorecard_type(scorecard=scorecard_name)
                    logging.info(f"Using scorecard {scorecard_name} with class {scorecard_instance.__class__.__name__}")
                    tracker.current_stage.status_message = f"Loaded scorecard: {scorecard_name}"
                    tracker.update(current_items=0)

                    # Look up scorecard record using its key
                    try:
                        tracker.current_stage.status_message = "Looking up scorecard record..."
                        tracker.update(current_items=0)
                        
                        scorecard_key = scorecard_instance.properties.get('key')
                        if not scorecard_key:
                            raise ValueError(f"Scorecard {scorecard_name} does not have a key defined in its properties")
                            
                        logging.info(f"Looking up Scorecard record for key: {scorecard_key}")
                        query = """
                        query GetScorecardByKey($key: String!) {
                            listScorecardByKey(key: $key) {
                                items {
                                    id
                                    name
                                    key
                                    sections {
                                        items {
                                            id
                                            scores {
                                                items {
                                                    id
                                                    name
                                                    key
                                                    externalId
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        """
                        
                        result = client.execute(query, {'key': scorecard_key})
                        if not result or 'listScorecardByKey' not in result or not result['listScorecardByKey']['items']:
                            raise ValueError(f"Could not find Scorecard with key: {scorecard_key}")
                        
                        scorecard_record = result['listScorecardByKey']['items'][0]
                        logging.info(f"Found Scorecard record with ID: {scorecard_record['id']}")
                        
                        # Update task with scorecard ID
                        if task:
                            logging.info(f"Updating task {task.id} with scorecard ID: {scorecard_record['id']}")
                            task.update(
                                accountId=task.accountId,
                                type=task.type,
                                status=task.status,
                                target=task.target,
                                command=task.command,
                                scorecardId=scorecard_record['id'],
                                updatedAt=datetime.now(timezone.utc).isoformat()
                            )

                        # If we have a score name, try to find its ID
                        score_id = None
                        if score_name:
                            logging.info(f"Looking up score with name/key: {score_name}")
                            # First try to find the score in the API by name or key
                            for section in scorecard_record['sections']['items']:
                                if section['scores']['items']:
                                    for score in section['scores']['items']:
                                        if (score.get('name') == score_name or 
                                            (score.get('key') and score.get('key') == score_name)):
                                            score_id = score['id']
                                            logging.info(f"Found Score record with ID: {score_id} matching name/key")
                                            break
                                if score_id:
                                    break
                            
                            if not score_id:
                                logging.warning(f"Could not find score with name/key: {score_name} in API, trying local config")
                                # Try to find score in local config by name first
                                score_config = next((score for score in scorecard_instance.scores 
                                                   if score.get('name') == score_name), None)
                                
                                # If not found by name, try by key
                                if not score_config:
                                    logging.info(f"Score not found by name in config, trying key: {score_name}")
                                    score_config = next((score for score in scorecard_instance.scores 
                                                       if score.get('key') == score_name), None)
                                
                                if score_config:
                                    logging.info(f"Found score config: {score_config}")
                                    if 'id' in score_config:
                                        external_id = score_config['id']
                                        # Try to find score by external ID in API
                                        for section in scorecard_record['sections']['items']:
                                            if section['scores']['items']:
                                                for score in section['scores']['items']:
                                                    if str(score.get('externalId', '')) == str(external_id):
                                                        score_id = score['id']
                                                        logging.info(f"Found Score record with ID: {score_id} matching external ID: {external_id}")
                                                        break
                                            if score_id:
                                                break
                                        if not score_id:
                                            logging.warning(f"Could not find score with external ID {external_id} in API")
                                    else:
                                        logging.warning(f"Score config found but missing 'id': {score_config}")
                                else:
                                    logging.warning(f"Could not find score by either name or key in config: {score_name}")

                            # Update task with score ID if found
                            if score_id and task:
                                logging.info(f"Updating task {task.id} with score ID: {score_id}")
                                task.update(
                                    accountId=task.accountId,
                                    type=task.type,
                                    status=task.status,
                                    target=task.target,
                                    command=task.command,
                                    scoreId=score_id,
                                    updatedAt=datetime.now(timezone.utc).isoformat()
                                )

                        # Update evaluation record if it exists
                        if evaluation_record:
                            update_data = {
                                'id': evaluation_record.id,
                                'scorecardId': scorecard_record['id']
                            }
                            if score_id:
                                update_data['scoreId'] = score_id
                                
                            logging.info(f"Updating evaluation record {evaluation_record.id} with data: {update_data}")
                            mutation = """mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                                updateEvaluation(input: $input) {
                                    id
                                    scorecardId
                                    scoreId
                                }
                            }"""
                            client.execute(mutation, {'input': update_data})
                            logging.info("Successfully updated evaluation record with IDs")

                    except Exception as e:
                        error_msg = f"Failed to look up Scorecard/Score records: {str(e)}"
                        logging.error(error_msg)
                        tracker.current_stage.status_message = error_msg
                        tracker.update(current_items=0)
                        if task:
                            task.fail_processing(error_msg)
                        raise

                    # Check if any score in the scorecard uses the data-driven approach
                    uses_data_driven = any('data' in score_config for score_config in scorecard_instance.scores)
                    if uses_data_driven:
                        tracker.update(current_items=0)

                    if score_name is not None and score_name != '':
                        score_names = [score_name]
                    else:
                        score_names = [score['name'] for score in scorecard_instance.scores]

                    # Advance to Processing stage before starting evaluations
                    tracker.advance_stage()
                    tracker.current_stage.status_message = "Starting processing..."
                    tracker.update(current_items=0)
                    logging.info("Entered Processing stage")

                    # Process each score while keeping Processing stage active
                    for single_score_name in score_names:
                        logging.info(f"Running experiment for score: {single_score_name}")
                        tracker.current_stage.status_message = f"Starting evaluation for score: {single_score_name}"
                        tracker.update(current_items=0)
                        
                        single_score_labeled_samples = []
                        labeled_samples_filename = None
                        
                        # Initialize score_id to None
                        score_id = None
                        
                        # Look up Score ID from the API
                        score_config = next((score for score in scorecard_instance.scores 
                                           if score['name'] == single_score_name), None)
                        
                        if score_config and 'id' in score_config:
                            external_id = score_config['id']
                            logging.info(f"Found Score external ID {external_id} for {single_score_name}")
                            
                            # Look up the actual Score record using scorecard ID and external ID
                            try:
                                query = """
                                query GetScoreByExternalId($scorecardId: ID!, $externalId: Int!) {
                                    listScores(filter: {
                                        and: {
                                            externalId: { eq: $externalId },
                                            section: {
                                                scorecardId: { eq: $scorecardId }
                                            }
                                        }
                                    }) {
                                        items {
                                            id
                                            name
                                            externalId
                                        }
                                    }
                                }
                                """
                                score_result = client.execute(query, {
                                    'scorecardId': scorecard_record.id,
                                    'externalId': int(external_id)
                                })
                                
                                if score_result and 'listScores' in score_result and score_result['listScores']['items']:
                                    score = score_result['listScores']['items'][0]
                                    score_id = score['id']
                                    logging.info(f"Found Score record with ID {score_id} for external ID {external_id}")
                                    
                                    # Update evaluation record with score ID if we have one
                                    if evaluation_record:
                                        try:
                                            logging.info(f"Updating Evaluation record {evaluation_record.id} with scoreId: {score_id}")
                                            mutation = """mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                                                updateEvaluation(input: $input) {
                                                    id
                                                    scoreId
                                                }
                                            }"""
                                            client.execute(mutation, {
                                                'input': {
                                                    'id': evaluation_record.id,
                                                    'scoreId': score_id
                                                }
                                            })
                                            logging.info(f"Successfully updated Evaluation record with scoreId")
                                        except Exception as e:
                                            logging.error(f"Failed to update Evaluation record with scoreId: {str(e)}")
                                            # Continue execution even if update fails
                                else:
                                    logging.error(f"Could not find Score record for scorecard ID {scorecard_record.id} and external ID {external_id}")
                            except Exception as e:
                                logging.error(f"Error looking up Score record: {str(e)}")
                                # Continue execution even if lookup fails
                        else:
                            logging.warning(f"No external ID found for score {single_score_name}")

                        if uses_data_driven:
                            if score_config:
                                # Setup stage - dataset preparation
                                with CommandProgress.track(
                                    total=tracker.total_items,
                                    status=f"Loading dataset for {single_score_name}..."
                                ) as progress:
                                    tracker.current_stage.status_message = f"Loading dataset for {single_score_name}..."
                                    tracker.update(current_items=0)

                                    # Define a bound progress callback function
                                    def progress_callback_fn(self, current):
                                        progress.update(
                                            current=current,
                                            total=tracker.total_items,
                                            status=f"Loaded {current} of {tracker.total_items} samples"
                                        )
                                        self.update(current_items=current)
                                        self.current_stage.status_message = f"Loaded {current} of {tracker.total_items} samples for {single_score_name}"
                                    
                                    # Create a bound method from the function
                                    bound_progress_callback = types.MethodType(progress_callback_fn, tracker)

                                    single_score_labeled_samples = get_data_driven_samples(
                                        scorecard_instance, scorecard_name, single_score_name, 
                                        score_config, fresh, content_ids_to_sample_set,
                                        progress_callback=bound_progress_callback,
                                        number_of_samples=tracker.total_items,
                                        random_seed=random_seed
                                    )
                                    
                                    if single_score_labeled_samples:
                                        tracker.current_stage.status_message = f"Successfully loaded {len(single_score_labeled_samples)} samples for {single_score_name}"
                                        tracker.update(current_items=0)
                            else:
                                logging.warning(f"Score '{single_score_name}' not found in scorecard. Skipping.")
                                tracker.current_stage.status_message = f"Score '{single_score_name}' not found in scorecard. Skipping."
                                tracker.update(current_items=0)
                                continue
                        else:
                            # Use the default labeled samples file if not data-driven
                            labeled_samples_filename = os.path.join(scorecard_folder, 'experiments', 'labeled-samples.csv')
                            tracker.current_stage.status_message = f"Using labeled samples from file: {labeled_samples_filename}"
                            tracker.update(current_items=0)
                        
                        single_score_experiment_args = {
                            'scorecard_name': scorecard_name,
                            'scorecard': scorecard_instance,
                            'override_folder': override_folder,
                            'number_of_texts_to_sample': tracker.total_items,
                            'sampling_method': sampling_method,
                            'random_seed': random_seed,
                            'subset_of_score_names': [single_score_name],
                            'experiment_label': experiment_label,
                            'score_id': score_id,
                            'visualize': visualize,
                            'task_id': task_id,  # Pass task_id to experiment
                            'evaluation_id': evaluation_record.id if evaluation_record else None,  # Pass the evaluation ID
                            'account_id': account.id if account else None,  # Pass account ID
                            'scorecard_id': scorecard_record['id'] if scorecard_record else None  # Pass scorecard ID
                        }
                        
                        if uses_data_driven:
                            if not single_score_labeled_samples:
                                error_msg = "The dataset is empty. Cannot proceed with the experiment."
                                logging.error(error_msg)
                                tracker.current_stage.status_message = error_msg
                                tracker.update(current_items=0)
                                if task:
                                    task.fail_processing(error_msg)
                                raise ValueError(error_msg)
                            single_score_experiment_args['labeled_samples'] = single_score_labeled_samples
                        else:
                            single_score_experiment_args['labeled_samples_filename'] = labeled_samples_filename
                        
                        async with AccuracyEvaluation(**single_score_experiment_args) as experiment:
                            with CommandProgress.track(
                                total=tracker.total_items,
                                status=f"Evaluating {single_score_name}..."
                            ) as progress:
                                await experiment.run(
                                    tracker=tracker,
                                    progress_callback=lambda current: (
                                        progress.update(
                                            current=current,
                                            total=tracker.total_items,
                                            status=f"Processed {current} of {tracker.total_items} evaluations"
                                        ),
                                        tracker.update(current_items=current),
                                        setattr(tracker.current_stage, 'status_message',
                                               f"Processing {single_score_name}: {current} of {tracker.total_items} evaluations")
                                    )
                                )

                        logging.info(f"Completed evaluation for score: {single_score_name}")
                        tracker.current_stage.status_message = f"Completed evaluation for score: {single_score_name}"
                        tracker.update(current_items=tracker.total_items)

                    # Only advance to Finalizing stage after ALL scores are processed
                    logging.info("All score evaluations completed")
                    tracker.current_stage.status_message = "All evaluations complete, starting finalization..."
                    tracker.update(current_items=tracker.total_items)
                    
                    # Now safe to advance to Finalizing stage
                    tracker.advance_stage()
                    tracker.current_stage.status_message = "Starting finalization..."
                    tracker.update(current_items=tracker.total_items)
                    logging.info("Entered Finalizing stage")

                    # Complete the task
                    # First log the complete task and evaluation state
                    try:
                        tracker.current_stage.status_message = "Logging final evaluation state..."
                        tracker.update(current_items=tracker.total_items)
                        
                        # Get and log final task state
                        if task:
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

                            # Update task to completed status
                            task.update(
                                accountId=task.accountId,
                                type=task.type,
                                status='COMPLETED',
                                target=task.target,
                                command=task.command,
                                completedAt=datetime.now(timezone.utc).isoformat(),
                                updatedAt=datetime.now(timezone.utc).isoformat()
                            )
                            logging.info(f"Successfully marked task {task.id} as completed")

                        # Get and log final evaluation state
                        if evaluation_record:
                            query = """
                            query GetEvaluation($id: ID!) {
                                getEvaluation(id: $id) {
                                    id
                                    type
                                    accountId
                                    status
                                    accuracy
                                    parameters
                                    metrics
                                    totalItems
                                    processedItems
                                    createdAt
                                    updatedAt
                                    startedAt
                                    taskId
                                    scorecardId
                                    scoreId
                                    estimatedRemainingSeconds
                                    errorMessage
                                    errorDetails
                                    confusionMatrix
                                    scoreResults {
                                        items {
                                            id
                                            value
                                            confidence
                                            metadata
                                            correct
                                            createdAt
                                        }
                                    }
                                }
                            }
                            """
                            result = client.execute(query, {'id': evaluation_record.id})
                            if result and 'getEvaluation' in result:
                                eval_details = result['getEvaluation']
                                logging.info(f"Final evaluation state:\n{json.dumps(truncate_dict_strings(eval_details), indent=2)}")

                        tracker.current_stage.status_message = "Evaluation completed."
                        tracker.update(current_items=tracker.total_items)
                        tracker.complete()

                    except Exception as e:
                        error_msg = f"Error logging final states: {str(e)}"
                        error_details = ''.join(traceback.format_exc())
                        logging.error(error_msg)
                        logging.error("Error details:", exc_info=True)
                        logging.error(f"Stack trace:\n{error_details}")
                        
                        # Set error message on the tracker's current stage
                        if tracker and tracker.current_stage:
                            tracker.current_stage.status_message = error_msg
                            tracker.update(current_items=tracker.total_items)
                            
                        # Update task with error information
                        if task:
                            try:
                                task.update(
                                    accountId=task.accountId,
                                    type=task.type,
                                    status='FAILED',
                                    target=task.target,
                                    command=task.command,
                                    errorMessage=error_msg,
                                    errorDetails=error_details,
                                    completedAt=datetime.now(timezone.utc).isoformat(),
                                    updatedAt=datetime.now(timezone.utc).isoformat()
                                )
                                logging.info(f"Updated task {task.id} with error information")
                            except Exception as task_update_error:
                                logging.error(f"Failed to update task with error information: {str(task_update_error)}")
                        
                        # Update evaluation record with error information if it exists
                        if evaluation_record:
                            try:
                                mutation = """mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                                    updateEvaluation(input: $input) {
                                        id
                                        status
                                        errorMessage
                                        errorDetails
                                        taskId
                                    }
                                }"""
                                update_data = {
                                    'id': evaluation_record.id,
                                    'taskId': task.id,  # Always include task ID in error updates
                                    'status': 'FAILED',
                                    'errorMessage': error_msg,
                                    'errorDetails': error_details
                                }
                                logging.info(f"Updating evaluation record with error data:\n{json.dumps(update_data, indent=2)}")
                                result = client.execute(mutation, {'input': update_data})
                                logging.info(f"Error update result:\n{json.dumps(result, indent=2)}")
                            except Exception as eval_update_error:
                                logging.error(f"Failed to update evaluation record with error information: {str(eval_update_error)}")
                        
                        # Continue with completion even if logging fails, but mark as failed
                        tracker.fail(error_msg)

                except Exception as e:
                    error_msg = f"Failed to create task stages: {str(e)}"
                    logging.error(error_msg)
                    logging.error("Error details:", exc_info=True)
                    if tracker:
                        tracker.current_stage.status_message = error_msg
                        tracker.update(current_items=0)
                        tracker.fail(str(e))
                    raise

        except Exception as e:
            logging.error(f"Evaluation failed: {str(e)}")
            if task:
                task.fail_processing(str(e))
            raise
        finally:
            if experiment:
                await experiment.cleanup()

    # Create and run the event loop
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
@click.option('--scorecard-name', required=True, help='Name of the scorecard to evaluate')
@click.option('--number-of-samples', default=100, help='Number of samples to evaluate')
@click.option('--subset-of-scores', default='', help='Comma-separated list of score names to evaluate')
@click.option('--max-workers', default=10, help='Maximum number of parallel workers')
def distribution(
    scorecard_name: str,
    number_of_samples: int,
    subset_of_scores: str,
    max_workers: int
):
    start_time = time.time()
    logging.info(f"Starting distribution evaluation for Scorecard {scorecard_name} at {time.strftime('%H:%M:%S')}")

    Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_name)

    if scorecard_class is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return

    # We're removing support for a list of scores.
    # scores_to_evaluate = subset_of_scores.split(',') if subset_of_scores else list(scorecard_class.scores.keys())[:10]
    scores_to_evaluate = subset_of_scores
    total_scores = len(scores_to_evaluate)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_score = {executor.submit(evaluate_score_distribution, score_name, scorecard_class, number_of_samples): score_name for score_name in scores_to_evaluate}
        for future in concurrent.futures.as_completed(future_to_score):
            score_name = future_to_score[future]
            try:
                future.result()
            except Exception as exc:
                logging.error(f'{score_name} generated an exception: {exc}')

    end_time = time.time()
    logging.info(f"Finished distribution evaluation at {time.strftime('%H:%M:%S')}. Total time: {end_time - start_time:.2f} seconds")

def evaluate_score_distribution(score_name, scorecard_class, number_of_samples):
    start_time = time.time()
    logging.info(f"Started evaluating distribution for Score {score_name} at {time.strftime('%H:%M:%S')}")
    
    score_configuration = next((score for score in scorecard_class.scores if score['name'] == score_name), {})

    if not score_configuration:
        logging.error(f"Score with name '{score_name}' not found in scorecard '{scorecard_class.name}'.")
        return

    score_class_name = score_configuration['class']
    score_module_path = f'plexus.scores.{score_class_name}'
    score_module = importlib.import_module(score_module_path)
    score_class = getattr(score_module, score_class_name)

    if not isinstance(score_class, type):
        logging.error(f"{score_class_name} is not a class.")
        return

    score_configuration['scorecard_name'] = scorecard_class.name
    score_configuration['score_name'] = score_name
    score_instance = score_class(**score_configuration)

    score_instance.record_configuration(score_configuration)

    logging.info(f"Loading data for {score_name} at {time.strftime('%H:%M:%S')}")
    score_instance.load_data(data=score_configuration['data'])
    
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
            metadata.update({
                'account_key': account_key,
                'scorecard_key': scorecard_class.key,
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