"""
Plexus Dashboard CLI - Command line interface for the Plexus Dashboard API.

This CLI mirrors the GraphQL API schema structure, providing commands and options
that map directly to the API's models and their attributes. The command hierarchy
is organized by model (evaluation, account, etc.), with subcommands for operations
(create, update, etc.).

Example command structure:
    plexus-dashboard evaluation create  # Creates an Evaluation record
    plexus-dashboard evaluation update  # Updates an Evaluation record
    plexus-dashboard account list      # Lists Account records

Each command's options correspond directly to the GraphQL model's fields,
making it easy to set any attribute that exists in the schema.
"""

import os
import click
import logging
from dotenv import load_dotenv
from typing import Optional
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.evaluation import Evaluation
from plexus.dashboard.api.models.scorecard import Scorecard
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.score_result import ScoreResult
import json
import random
import time
import numpy as np
import threading
from datetime import datetime, timezone, timedelta
from sklearn.metrics import (
    confusion_matrix,
    accuracy_score
)
from plexus.dashboard.commands.simulate import (
    generate_class_distribution,
    simulate_prediction,
    select_metrics_and_explanation,
    calculate_metrics,
    select_num_classes,
    SCORE_GOALS,
    CLASS_SETS
)
import yaml
import boto3
from botocore.config import Config

from plexus.CustomLogging import logging

# Add after other constants
SCORE_TYPES = ['binary', 'multiclass']
DATA_BALANCES = ['balanced', 'unbalanced']

def generate_key(name: str) -> str:
    """Generate a URL-safe key from a name."""
    return name.lower().replace(' ', '-')

@click.group()
def cli():
    """Plexus Dashboard CLI"""
    load_dotenv(override=True)

@cli.group()
def evaluation():
    """Manage evaluations"""
    pass

def create_client() -> PlexusDashboardClient:
    """Create a client and log its configuration"""
    client = PlexusDashboardClient()
    logging.info(f"Using API URL: {client.api_url}")
    return client

@evaluation.command()
@click.option('--account-key', default='call-criteria', help='Account key identifier')
@click.option('--type', required=True, help='Type of evaluation (e.g., accuracy, consistency)')
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
    """Create a new evaluation with specified attributes.
    
    Examples:
        plexus-dashboard evaluation create --type accuracy
        plexus-dashboard evaluation create --type accuracy --accuracy 95.5 --status COMPLETED
        plexus-dashboard evaluation create --type consistency --scorecard-id abc123
    """
    client = create_client()
    
    try:
        # First get the account
        logging.info(f"Looking up account with key: {account_key}")
        account = Account.get_by_key(account_key, client)
        logging.info(f"Found account: {account.name} ({account.id})")
        
        # Build input dictionary with all provided values
        input_data = {
            'type': type,
            'accountId': account.id,
            'status': status
        }
        
        # Look up scorecard if any identifier was provided
        if any([scorecard_id, scorecard_key, scorecard_name]):
            if scorecard_id:
                logging.info(f"Using provided scorecard ID: {scorecard_id}")
                scorecard = Scorecard.get_by_id(scorecard_id, client)
            elif scorecard_key:
                logging.info(f"Looking up scorecard by key: {scorecard_key}")
                scorecard = Scorecard.get_by_key(scorecard_key, client)
            else:
                logging.info(f"Looking up scorecard by name: {scorecard_name}")
                scorecard = Scorecard.get_by_name(scorecard_name, client)
            logging.info(f"Found scorecard: {scorecard.name} ({scorecard.id})")
            input_data['scorecardId'] = scorecard.id
        
        # Look up score if any identifier was provided
        if any([score_id, score_key, score_name]):
            if score_id:
                logging.info(f"Using provided score ID: {score_id}")
                score = Score.get_by_id(score_id, client)
            elif score_key:
                logging.info(f"Looking up score by key: {score_key}")
                score = Score.get_by_key(score_key, client)
            else:
                logging.info(f"Looking up score by name: {score_name}")
                score = Score.get_by_name(score_name, client)
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
        evaluation = Evaluation.create(
            client=client,
            type=type,
            accountId=account.id,
            status=status,
            parameters=parameters,
            metrics=metrics,
            inferences=inferences,
            results=results,
            cost=cost,
            progress=progress,
            totalItems=total_items,
            processedItems=processed_items,
            errorMessage=error_message,
            errorDetails=error_details,
            scorecardId=scorecard.id if 'scorecard' in locals() else None,
            scoreId=score.id if 'score' in locals() else None,
            confusionMatrix=confusion_matrix,
        )
        logging.info(f"Created evaluation: {evaluation.id}")
        
        # Output results
        click.echo(f"Created evaluation: {evaluation.id}")
        click.echo(f"Type: {evaluation.type}")
        click.echo(f"Status: {evaluation.status}")
        click.echo(f"Created at: {evaluation.createdAt}")
        
    except Exception as e:
        logging.error(f"Error creating evaluation: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)

@evaluation.command()
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
    """Update an existing evaluation.
    
    Required fields (type, status) will keep their previous values if not specified.
    The updatedAt timestamp is automatically set to the current time.
    
    Examples:
        plexus-dashboard evaluation update abc123 --accuracy 97.8
        plexus-dashboard evaluation update def456 --status COMPLETED
        plexus-dashboard evaluation update ghi789 --type consistency --status FAILED
    """
    client = create_client()
    
    try:
        # First get the existing evaluation
        logging.info(f"Looking up evaluation: {id}")
        evaluation = Evaluation.get_by_id(id, client)
        logging.info(f"Found evaluation: {evaluation.id}")
        
        # Build update data with only provided fields
        update_data = {
            # Use provided values or fall back to existing values for required fields
            'type': type or evaluation.type,
            'status': status or evaluation.status,
        }
        
        # Add optional fields if provided
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
        updated = evaluation.update(**update_data)
        logging.info(f"Updated evaluation: {updated.id}")
        
        # Output results
        click.echo(f"Updated evaluation: {updated.id}")
        click.echo(f"Type: {updated.type}")
        click.echo(f"Status: {updated.status}")
        click.echo(f"Updated at: {updated.updatedAt}")
        
    except Exception as e:
        logging.error(f"Error updating evaluation: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)

@cli.group()
def score_result():
    """Manage score results"""
    pass

@score_result.command()
@click.option('--value', type=float, required=True, help='Score value')
@click.option('--item-id', required=True, help='ID of the item being scored')
@click.option('--account-id', required=True, help='ID of the account')
@click.option('--scoring-job-id', required=True, help='ID of the scoring job')
@click.option('--scorecard-id', required=True, help='ID of the scorecard')
@click.option('--confidence', type=float, help='Confidence score (optional)')
@click.option('--metadata', type=str, help='JSON metadata (optional)')
def create(value, item_id, account_id, scoring_job_id, scorecard_id, confidence, metadata):
    """Create a new score result"""
    client = PlexusDashboardClient()
    
    kwargs = {}
    if confidence is not None:
        kwargs['confidence'] = confidence
    if metadata is not None:
        kwargs['metadata'] = json.loads(metadata)
        
    result = ScoreResult.create(
        client=client,
        value=value,
        itemId=item_id,
        accountId=account_id,
        scoringJobId=scoring_job_id,
        scorecardId=scorecard_id,
        **kwargs
    )
    
    click.echo(json.dumps({
        'id': result.id,
        'value': result.value,
        'confidence': result.confidence,
        'metadata': result.metadata
    }, indent=2))

@score_result.command()
@click.argument('id', required=True)
@click.option('--value', type=float, help='Score value')
@click.option('--confidence', type=float, help='Confidence score')
@click.option('--metadata', type=str, help='JSON metadata')
def update(id: str, value: Optional[float], confidence: Optional[float], metadata: Optional[str]):
    """Update an existing score result
    
    Examples:
        plexus-dashboard score-result update abc123 --value 0.98
        plexus-dashboard score-result update def456 --confidence 0.95
        plexus-dashboard score-result update ghi789 --metadata '{"source": "updated"}'
    """
    client = PlexusDashboardClient()
    
    try:
        # Get existing score result
        logging.getLogger(__name__).info(f"Looking up score result: {id}")
        result = ScoreResult.get_by_id(id, client)
        logging.getLogger(__name__).info(f"Found score result: {result.id}")
        
        # Build update data
        update_data = {}
        if value is not None: update_data['value'] = value
        if confidence is not None: update_data['confidence'] = confidence
        if metadata is not None: update_data['metadata'] = json.loads(metadata)
        
        logging.getLogger(__name__).info("Updating score result...")
        updated = result.update(**update_data)
        logging.getLogger(__name__).info(f"Updated score result: {updated.id}")
        
        # Output results
        click.echo(json.dumps({
            'id': updated.id,
            'value': updated.value,
            'confidence': updated.confidence,
            'metadata': updated.metadata
        }, indent=2))
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Error updating score result: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)

@score_result.command()
@click.option('--dry-run', is_flag=True, help='Show what would be updated without making changes')
def fix_missing_external_ids(dry_run: bool):
    """Fix scores that are missing required externalId field"""
    client = create_client()
    
    try:
        scores_to_fix = []
        next_token = None
        page_size = 100
        total_processed = 0
        page_number = 0
        
        logging.info("Starting to fetch scores...")
        
        while True:
            page_number += 1
            logging.info(f"Fetching page {page_number} (size: {page_size}, next_token: {next_token})")
            
            # Query scores with pagination
            query = """
            query ListScores($limit: Int, $nextToken: String) {
                listScores(limit: $limit, nextToken: $nextToken) {
                    items {
                        id
                        name
                        type
                        sectionId
                    }
                    nextToken
                }
            }
            """
            
            try:
                logging.info("Executing ListScores query...")
                response = client.execute(query, {
                    'limit': page_size,
                    'nextToken': next_token
                })
                logging.info("Received response from ListScores query")
                
                items = response['listScores']['items']
                total_processed += len(items)
                logging.info(f"Found {len(items)} scores on this page")
                
                # Try to get externalId for each score
                for i, score in enumerate(items):
                    logging.info(f"Checking score {i+1}/{len(items)} on page {page_number} (ID: {score['id']})")
                    detail_query = """
                    query GetScore($id: ID!) {
                        getScore(id: $id) {
                            id
                            name
                            externalId
                        }
                    }
                    """
                    
                    try:
                        detail = client.execute(detail_query, {'id': score['id']})
                        if not detail['getScore'].get('externalId'):
                            logging.info(f"Found score missing externalId: {score['id']} ({score['name']})")
                            scores_to_fix.append(score)
                    except Exception as e:
                        if 'non-nullable' in str(e) and 'externalId' in str(e):
                            logging.info(f"Found score with null externalId: {score['id']} ({score['name']})")
                            scores_to_fix.append(score)
                        else:
                            logging.error(f"Error checking score {score['id']}: {str(e)}")
                
                next_token = response['listScores'].get('nextToken')
                logging.info(f"Next token: {next_token}")
                
                if not next_token:
                    logging.info("No more pages to process")
                    break
                    
            except Exception as e:
                logging.error(f"Error processing page {page_number}: {str(e)}")
                if 'non-nullable' in str(e) and 'externalId' in str(e):
                    # Try to extract the problematic score index
                    try:
                        error_str = str(e)
                        if 'items[' in error_str:
                            index = int(error_str.split('items[')[1].split(']')[0])
                            if len(items) > index:
                                logging.info(f"Adding problematic score from error: {items[index]['id']}")
                                scores_to_fix.append(items[index])
                    except:
                        pass
                break
        
        if not scores_to_fix:
            click.echo("No scores found with missing externalId")
            return
            
        click.echo(f"Found {len(scores_to_fix)} scores with missing externalId")
        click.echo(f"Processed {total_processed} total scores")
        
        for score in scores_to_fix:
            # Generate deterministic external ID based on score ID
            external_id = f"score_{score['id']}"
            
            click.echo(f"Updating score {score['id']} ({score['name']}) with externalId: {external_id}")
            if not dry_run:
                mutation = """
                mutation UpdateScore($input: UpdateScoreInput!) {
                    updateScore(input: $input) {
                        id
                        name
                    }
                }
                """
                
                client.execute(mutation, {
                    'input': {
                        'id': score['id'],
                        'externalId': external_id
                    }
                })
        
        click.echo("Update complete")
        
    except Exception as e:
        logging.error(f"Error fixing scores: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)

@evaluation.command()
@click.option('--account-key', help='Account key')
@click.option('--account-name', help='Account name')
@click.option('--account-id', help='Account ID')
@click.option('--scorecard-key', help='Scorecard key')
@click.option('--scorecard-name', help='Scorecard name')
@click.option('--scorecard-id', help='Scorecard ID')
@click.option('--score-key', help='Score key')
@click.option('--score-name', help='Score name')
@click.option('--score-id', help='Score ID')
@click.option('--num-items', type=int, default=100, help='Number of items to simulate')
@click.option('--accuracy', type=float, default=0.85, help='Target accuracy')
def simulate(
    account_key: Optional[str],
    account_name: Optional[str],
    account_id: Optional[str],
    scorecard_key: Optional[str],
    scorecard_name: Optional[str],
    scorecard_id: Optional[str],
    score_key: Optional[str],
    score_name: Optional[str],
    score_id: Optional[str],
    num_items: int,
    accuracy: float,
):
    """Simulate a machine learning evaluation evaluation with synthetic data.
    
    This command creates a realistic simulation of an ML model evaluation run by:
    1. Creating an Evaluation record to track the evaluation
    2. Generating synthetic binary classification results (Yes/No predictions)
    3. Creating ScoreResult records for each prediction
    4. Computing standard ML metrics (accuracy, precision, sensitivity, specificity)
    5. Updating the Evaluation with real-time metric calculations
    """
    try:
        # Initial client for setup
        client = PlexusDashboardClient()
        
        # Look up or validate account
        if account_id:
            logging.info(f"Using provided account ID: {account_id}")
            account = Account.get_by_id(account_id, client)
        elif account_key:
            logging.info(f"Looking up account by key: {account_key}")
            account = Account.get_by_key(account_key, client)
        elif account_name:
            logging.info(f"Looking up account by name: {account_name}")
            account = Account.get_by_name(account_name, client)
        else:
            raise click.UsageError("Must provide account-id, account-key, or account-name")
        
        # Look up or validate scorecard
        if scorecard_id:
            logging.info(f"Using provided scorecard ID: {scorecard_id}")
            scorecard = Scorecard.get_by_id(scorecard_id, client)
        elif scorecard_key:
            logging.info(f"Looking up scorecard by key: {scorecard_key}")
            scorecard = Scorecard.get_by_key(scorecard_key, client)
        elif scorecard_name:
            logging.info(f"Looking up scorecard by name: {scorecard_name}")
            scorecard = Scorecard.get_by_name(scorecard_name, client)
        else:
            raise click.UsageError("Must provide scorecard-id, scorecard-key, or scorecard-name")
            
        # Optionally look up score
        score = None
        if any([score_id, score_key, score_name]):
            if score_id:
                logging.info(f"Using provided score ID: {score_id}")
                score = Score.get_by_id(score_id, client)
            elif score_key:
                logging.info(f"Looking up score by key: {score_key}")
                score = Score.get_by_key(score_key, client)
            else:
                logging.info(f"Looking up score by name: {score_name}")
                score = Score.get_by_name(score_name, client)
            logging.info(f"Using score: {score.name} ({score.id})")

        # Randomly decide evaluation characteristics
        is_binary = random.random() < 0.3  # 30% chance of binary classification
        num_classes = select_num_classes()
        is_balanced = random.random() < 0.5  # 50% chance of balanced distribution
        score_goal = random.choice(SCORE_GOALS)
        
        # Generate class distribution
        dataset_distribution = generate_class_distribution(
            num_classes=num_classes,
            total_items=num_items,
            balanced=is_balanced
        )
        
        # Create pools of true values based on the distribution
        true_values_pool = []
        for class_info in dataset_distribution:
            true_values_pool.extend([class_info["label"]] * class_info["count"])
        random.shuffle(true_values_pool)
        
        # Get list of valid labels for prediction
        valid_labels = [item["label"] for item in dataset_distribution]

        # First get the initial metrics and explanation
        initial_metrics, initial_explanation = select_metrics_and_explanation(
            is_binary=(num_classes == 2),
            is_balanced=is_balanced,
            score_goal=score_goal
        )

        # Create initial evaluation record
        started_at = datetime.now(timezone.utc)
        evaluation = Evaluation.create(
            client=client,
            type="accuracy",
            accountId=account.id,
            status="RUNNING",
            accuracy=0.0,
            createdAt=started_at.isoformat().replace('+00:00', 'Z'),
            updatedAt=started_at.isoformat().replace('+00:00', 'Z'),
            totalItems=num_items,
            processedItems=0,
            scorecardId=scorecard.id,
            scoreId=score.id if score else None,
            parameters=json.dumps({
                "target_accuracy": accuracy,
                "num_items": num_items,
                "num_classes": num_classes,
                "is_balanced": is_balanced
            }),
            startedAt=started_at.isoformat().replace('+00:00', 'Z'),
            estimatedRemainingSeconds=num_items,
            scoreGoal=score_goal,
            datasetClassDistribution=json.dumps(dataset_distribution),
            isDatasetClassDistributionBalanced=is_balanced,
            metricsExplanation=initial_explanation,
            cost=0.0
        )
        
        # Lists to store true and predicted values for metrics calculation
        true_values = []
        predicted_values = []
        
        # Simulate results
        for i in range(num_items):
            try:
                # Create new client for each iteration
                iteration_client = PlexusDashboardClient()
                
                # Get next true value from pool
                true_value = true_values_pool[i]
                predicted_value = simulate_prediction(true_value, accuracy, valid_labels)
                
                true_values.append(true_value)
                predicted_values.append(predicted_value)
                
                # Add debug logging
                is_correct = true_value == predicted_value
                logging.info(f"Result {i}: true={true_value}, "
                          f"predicted={predicted_value}, correct={is_correct}")

                create_args = {
                    "value": 1.0 if is_correct else 0.0,
                    "confidence": random.uniform(0.7, 0.99),
                    "correct": is_correct,
                    "itemId": f"item_{i}",
                    "accountId": account.id,
                    "evaluationId": evaluation.id,
                    "scorecardId": scorecard.id,
                    "scoringJobId": None,
                    "metadata": {
                        "true_value": true_value,
                        "predicted_value": predicted_value,
                        "label": predicted_value
                    }
                }
                
                logging.info(f"Creating score result with args: {create_args}")
                result = ScoreResult.create(
                    client=iteration_client,
                    **create_args
                )
                logging.info(f"Created score result: {result.id}, correct={result.correct}")

                # Calculate metrics immediately after each result
                metrics, metrics_explanation = calculate_metrics(
                    true_values,
                    predicted_values,
                    num_classes == 2,
                    is_balanced,
                    score_goal
                )
                
                # Find accuracy in metrics or calculate it directly
                accuracy_metric = next(
                    (m for m in metrics if m["name"] == "Accuracy"), 
                    {"value": accuracy_score(true_values, predicted_values) * 100}
                )
                
                # Calculate timing values
                processed_items = len(true_values)
                elapsed_seconds = int((datetime.now(timezone.utc) - started_at).total_seconds())
                estimated_remaining_seconds = int(elapsed_seconds * (num_items - processed_items) / processed_items) if processed_items > 0 else 0

                # Calculate predicted class distribution
                unique_classes, class_counts = np.unique(predicted_values, return_counts=True)
                predicted_distribution = [
                    {"label": str(label), "count": int(count)} 
                    for label, count in zip(unique_classes, class_counts)
                ]
                
                # Calculate if predictions are balanced
                total = sum(class_counts)
                expected_count = total / len(class_counts)
                tolerance = 0.2  # 20% tolerance
                is_predicted_balanced = all(
                    abs(count - expected_count) <= expected_count * tolerance
                    for count in class_counts
                )

                # Update evaluation with current metrics and accuracy
                update_data = {
                    "type": "accuracy",
                    "metrics": json.dumps(metrics) if metrics else None,
                    "processedItems": processed_items,
                    "elapsedSeconds": elapsed_seconds,
                    "estimatedRemainingSeconds": estimated_remaining_seconds,
                    "predictedClassDistribution": json.dumps(predicted_distribution),
                    "isPredictedClassDistributionBalanced": is_predicted_balanced,
                    "metricsExplanation": metrics_explanation,
                    "accuracy": accuracy_metric["value"],
                    "confusionMatrix": json.dumps({
                        "matrix": confusion_matrix(
                            true_values, 
                            predicted_values,
                            labels=valid_labels
                        ).tolist(),
                        "labels": valid_labels
                    })
                }
                
                # Log the update data to verify metricsExplanation is included
                logging.info(f"Updating evaluation with data: {json.dumps(update_data, indent=2)}")
                
                # Create new client for update
                update_client = PlexusDashboardClient()
                # Use the client's updateEvaluation method directly
                update_client.updateEvaluation(
                    id=evaluation.id,
                    **update_data
                )
                
            except Exception as e:
                logging.error(f"Error in iteration {i}: {str(e)}")
                continue  # Continue to next iteration instead of failing completely
            
            # Random delay between results
            time.sleep(random.uniform(0.1, 1.0))
            
            # Progress update
            if (i + 1) % 10 == 0:
                logging.info(f"Generated {i + 1} of {num_items} results")
        
        # Final update
        final_client = PlexusDashboardClient()
        final_client.updateEvaluation(
            id=evaluation.id,
            status="COMPLETED",
            elapsedSeconds=int((datetime.now(timezone.utc) - started_at).total_seconds()),
            estimatedRemainingSeconds=0,
            accuracy=accuracy_metric["value"]
        )
        logging.info("Simulation completed")
        
    except Exception as e:
        logging.error(f"Error in simulation: {str(e)}")
        if 'evaluation' in locals():
            try:
                # Error update
                error_client = PlexusDashboardClient()
                error_client.updateEvaluation(
                    id=evaluation.id,
                    status="FAILED",
                    errorMessage=str(e),
                    elapsedSeconds=int((datetime.now(timezone.utc) - started_at).total_seconds()),
                    estimatedRemainingSeconds=None
                )
            except Exception as update_error:
                logging.error(f"Error updating evaluation status: {str(update_error)}")
        click.echo(f"Error: {str(e)}", err=True)

def simulate_evaluation_progress(evaluation_id: str, client: PlexusDashboardClient):
    """Simulate evaluation progress by updating metrics over time."""
    evaluation = client.get_evaluation(evaluation_id)
    
    # Initial values
    total_items = 100
    processed = 0
    start_time = datetime.now(timezone.utc)
    
    # Initialize confusion matrix with zeros
    labels = ["Yes", "No", "NA"]
    matrix_size = len(labels)
    confusion_matrix = {
        "matrix": [[0] * matrix_size for _ in range(matrix_size)],
        "labels": labels
    }
    
    while processed < total_items:
        processed += random.randint(5, 15)
        processed = min(processed, total_items)
        elapsed = datetime.now(timezone.utc) - start_time
        
        # Calculate metrics based on processed items
        accuracy = random.uniform(85, 95)
        sensitivity = random.uniform(85, 95)
        specificity = random.uniform(85, 95)
        precision = random.uniform(85, 95)
        
        # Update confusion matrix based on current processed items
        # Scale the matrix values proportionally to processed items
        base_correct = int((processed / total_items) * 40)
        base_error = int((processed / total_items) * 3)
        
        confusion_matrix["matrix"] = [
            [base_correct + random.randint(-2, 2), 
             base_error + random.randint(-1, 1),
             base_error + random.randint(-1, 1)],
            [base_error + random.randint(-1, 1),
             base_correct + random.randint(-2, 2),
             base_error + random.randint(-1, 1)],
            [base_error + random.randint(-1, 1),
             base_error + random.randint(-1, 1),
             base_correct + random.randint(-2, 2)]
        ]
        
        # Convert confusion matrix to JSON string
        confusion_matrix_json = json.dumps(confusion_matrix)
        
        # Update evaluation
        evaluation.update(
            status="RUNNING",
            processedItems=processed,
            totalItems=total_items,
            accuracy=accuracy,
            sensitivity=sensitivity,
            specificity=specificity,
            precision=precision,
            elapsedTime=str(elapsed).split('.')[0],
            estimatedTimeRemaining=str(elapsed * ((total_items - processed) / processed)).split('.')[0],
            confusionMatrix=confusion_matrix_json,  # Now passing as JSON string
            inferences=processed * 2,
            cost=processed * 0.2
        )
        
        if processed < total_items:
            time.sleep(random.uniform(0.5, 2.0))
    
    # Final update
    evaluation.update(
        status="COMPLETED",
        processedItems=total_items,
        totalItems=total_items,
        estimatedTimeRemaining="00:00:00"
    )

@evaluation.command()
@click.argument('id', required=True)
@click.option('--limit', type=int, default=1000, help='Maximum number of results to return')
def list_results(id: str, limit: int):
    """List score results for an evaluation"""
    client = PlexusDashboardClient()
    
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

@cli.group()
def result_test():
    """Manage result test records"""
    pass

@result_test.command()
@click.argument('evaluation_id', required=True)
@click.option('--value', required=True, help='Test value to record')
def create(evaluation_id: str, value: str):
    """Create a new result test record
    
    Example:
        plexus-dashboard result-test create abc123 --value "test-value-1"
    """
    client = PlexusDashboardClient()
    
    try:
        # Execute the mutation directly since this is a test model
        mutation = """
        mutation CreateResultTest($input: CreateResultTestInput!) {
            createResultTest(input: $input) {
                id
                value
                evaluationId
                createdAt
            }
        }
        """
        
        variables = {
            'input': {
                'value': value,
                'evaluationId': evaluation_id
            }
        }
        
        result = client.execute(mutation, variables)
        
        if not result or 'createResultTest' not in result:
            raise Exception(f"Failed to create result test. Response: {result}")
            
        created = result['createResultTest']
        click.echo(f"Created result test: {created['id']}")
        click.echo(f"Value: {created['value']}")
        click.echo(f"Evaluation ID: {created['evaluationId']}")
        click.echo(f"Created at: {created['createdAt']}")
        
    except Exception as e:
        logging.error(f"Error creating result test: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)

@cli.group()
def scorecard():
    """Manage scorecards"""
    click.echo("WARNING: The 'plexus-dashboard scorecard' commands are deprecated.", err=True)
    click.echo("Please use the main 'plexus scorecards' commands instead.", err=True)
    pass

@scorecard.command()
@click.option('--account-key', help='Filter by account key')
@click.option('--name', help='Filter by name')
@click.option('--key', help='Filter by key')
def list(account_key: Optional[str], name: Optional[str], key: Optional[str]):
    """List scorecards with optional filtering.
    
    Examples:
        plexus-dashboard scorecard list
        plexus-dashboard scorecard list --account-key my-account
        plexus-dashboard scorecard list --name "QA Scorecard"
        plexus-dashboard scorecard list --key qa-v1
    """
    click.echo("WARNING: This command is deprecated. Please use 'plexus scorecards list-scorecards' instead.", err=True)
    # Forward to the main CLI command
    os.system(f"plexus scorecards list-scorecards {' --account-key ' + account_key if account_key else ''} {' --name ' + name if name else ''} {' --key ' + key if key else ''}")

@scorecard.command()
@click.option('--account-key', default='call-criteria', help='Account key identifier')
@click.option('--directory', default='scorecards', help='Directory containing YAML scorecard files')
def sync(account_key: str, directory: str):
    """Sync YAML scorecards to the API.
    
    Examples:
        plexus-dashboard scorecard sync
        plexus-dashboard scorecard sync --account-key my-account
        plexus-dashboard scorecard sync --directory path/to/scorecards
    """
    click.echo("WARNING: This command is deprecated. Please use 'plexus scorecards sync' instead.", err=True)
    # Forward to the main CLI command
    os.system(f"plexus scorecards sync --account-key {account_key} --directory {directory}")

@scorecard.command()
@click.option('--account-key', required=True, help='Account key')
@click.option('--fix', is_flag=True, help='Fix duplicates by removing newer copies')
def find_duplicates(account_key: str, fix: bool):
    """Find and optionally fix duplicate scores based on name+order+section combination."""
    click.echo("WARNING: This command is deprecated. Please use 'plexus scorecards find-duplicates' instead.", err=True)
    # Forward to the main CLI command
    os.system(f"plexus scorecards find-duplicates --account-key {account_key}{' --fix' if fix else ''}")

@scorecard.command()
@click.option('--scorecard-id', help='Scorecard ID')
@click.option('--scorecard-key', help='Scorecard key')
@click.option('--scorecard-name', help='Scorecard name')
def list_scores(scorecard_id: Optional[str], scorecard_key: Optional[str], scorecard_name: Optional[str]):
    """List all scores for a specific scorecard."""
    client = create_client()
    
    try:
        # Get scorecard
        if scorecard_id:
            logging.info(f"Using provided scorecard ID: {scorecard_id}")
            scorecard = Scorecard.get_by_id(scorecard_id, client)
        elif scorecard_key:
            logging.info(f"Looking up scorecard by key: {scorecard_key}")
            scorecard = Scorecard.get_by_key(scorecard_key, client)
        elif scorecard_name:
            logging.info(f"Looking up scorecard by name: {scorecard_name}")
            scorecard = Scorecard.get_by_name(scorecard_name, client)
        else:
            raise click.UsageError("Must provide scorecard-id, scorecard-key, or scorecard-name")
        
        logging.info(f"Found scorecard: {scorecard.name} ({scorecard.id})")
        
        # First get all sections for this scorecard
        sections_query = """
            query GetSections($scorecardId: String!) {
                listScorecardSections(filter: {scorecardId: {eq: $scorecardId}}) {
                    items {
                        id
                        name
                        order
                        scores {
                            items {
                                id
                                name
                                type
                                order
                                externalId
                                createdAt
                                updatedAt
                            }
                        }
                    }
                }
            }
        """
        
        result = client.execute(sections_query, {
            'scorecardId': scorecard.id
        })
        
        sections = result['listScorecardSections']['items']
        
        # Flatten scores from all sections
        all_scores = []
        for section in sections:
            for score in section['scores']['items']:
                score['section'] = {
                    'name': section['name'],
                    'order': section['order']
                }
                all_scores.append(score)
        
        # Sort scores by section order, then score order
        sorted_scores = sorted(
            all_scores,
            key=lambda s: (
                s['section']['order'] if s.get('section') else 999,
                s.get('order', 999)
            )
        )
        
        click.echo(f"\nFound {len(sorted_scores)} scores in scorecard {scorecard.name}:\n")
        
        current_section = None
        for score in sorted_scores:
            # Print section header if changed
            section_name = score['section']['name'] if score.get('section') else 'Unknown Section'
            if section_name != current_section:
                current_section = section_name
                click.echo(f"\nSection: {section_name}")
                click.echo("-" * (len(section_name) + 9))
            
            # Print score details
            click.echo(f"ID: {score['id']}")
            click.echo(f"  Name: {score['name']}")
            click.echo(f"  Type: {score['type']}")
            click.echo(f"  Order: {score.get('order', 'N/A')}")
            click.echo(f"  External ID: {score.get('externalId', 'N/A')}")
            click.echo(f"  Created: {score['createdAt']}")
            click.echo(f"  Updated: {score['updatedAt']}")
            click.echo("")
            
    except Exception as e:
        logging.error(f"Error listing scores: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)

if __name__ == '__main__':
    cli() 