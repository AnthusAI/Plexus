"""
Plexus Dashboard CLI - Command line interface for the Plexus Dashboard API.

This CLI mirrors the GraphQL API schema structure, providing commands and options
that map directly to the API's models and their attributes. The command hierarchy
is organized by model (experiment, account, etc.), with subcommands for operations
(create, update, etc.).

Example command structure:
    plexus-dashboard experiment create  # Creates an Experiment record
    plexus-dashboard experiment update  # Updates an Experiment record
    plexus-dashboard account list      # Lists Account records

Each command's options correspond directly to the GraphQL model's fields,
making it easy to set any attribute that exists in the schema.
"""

import os
import click
import logging
from dotenv import load_dotenv
from typing import Optional
from .api.client import PlexusDashboardClient
from .api.models.account import Account
from .api.models.experiment import Experiment
from .api.models.scorecard import Scorecard
from .api.models.score import Score
from .api.models.score_result import ScoreResult
import json
import random
import time
import threading
from sklearn.metrics import (
    accuracy_score, 
    precision_score,
    recall_score,  # sensitivity
    confusion_matrix
)
import numpy as np
from datetime import datetime, timezone, timedelta

# Configure logging with a more concise format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname).1s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

@click.group()
def cli():
    """Plexus Dashboard CLI"""
    load_dotenv()

@cli.group()
def experiment():
    """Manage experiments"""
    pass

@experiment.command()
@click.option('--account-key', default='call-criteria', help='Account key identifier')
@click.option('--type', required=True, help='Type of experiment (e.g., accuracy, consistency)')
@click.option('--parameters', type=str, help='JSON string of experiment parameters')
@click.option('--metrics', type=str, help='JSON string of experiment metrics')
@click.option('--inferences', type=int, help='Number of inferences made')
@click.option('--results', type=int, help='Number of results processed')
@click.option('--cost', type=float, help='Cost of the experiment')
@click.option('--progress', type=float, help='Progress percentage (0-100)')
@click.option('--accuracy', type=float, help='Accuracy percentage (0-100)')
@click.option('--accuracy-type', help='Type of accuracy measurement')
@click.option('--sensitivity', type=float, help='Sensitivity/recall percentage (0-100)')
@click.option('--specificity', type=float, help='Specificity percentage (0-100)')
@click.option('--precision', type=float, help='Precision percentage (0-100)')
@click.option('--status', default='PENDING', 
              type=click.Choice(['PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED']),
              help='Status of the experiment')
@click.option('--total-items', type=int, help='Total number of items to process')
@click.option('--processed-items', type=int, help='Number of items processed')
@click.option('--error-message', help='Error message if experiment failed')
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
    """Create a new experiment with specified attributes.
    
    Examples:
        plexus-dashboard experiment create --type accuracy
        plexus-dashboard experiment create --type accuracy --accuracy 95.5 --status COMPLETED
        plexus-dashboard experiment create --type consistency --scorecard-id abc123
    """
    client = PlexusDashboardClient()
    
    try:
        # First get the account
        logger.info(f"Looking up account with key: {account_key}")
        account = Account.get_by_key(account_key, client)
        logger.info(f"Found account: {account.name} ({account.id})")
        
        # Build input dictionary with all provided values
        input_data = {
            'type': type,
            'accountId': account.id,
            'status': status
        }
        
        # Look up scorecard if any identifier was provided
        if any([scorecard_id, scorecard_key, scorecard_name]):
            if scorecard_id:
                logger.info(f"Using provided scorecard ID: {scorecard_id}")
                scorecard = Scorecard.get_by_id(scorecard_id, client)
            elif scorecard_key:
                logger.info(f"Looking up scorecard by key: {scorecard_key}")
                scorecard = Scorecard.get_by_key(scorecard_key, client)
            else:
                logger.info(f"Looking up scorecard by name: {scorecard_name}")
                scorecard = Scorecard.get_by_name(scorecard_name, client)
            logger.info(f"Found scorecard: {scorecard.name} ({scorecard.id})")
            input_data['scorecardId'] = scorecard.id
        
        # Look up score if any identifier was provided
        if any([score_id, score_key, score_name]):
            if score_id:
                logger.info(f"Using provided score ID: {score_id}")
                score = Score.get_by_id(score_id, client)
            elif score_key:
                logger.info(f"Looking up score by key: {score_key}")
                score = Score.get_by_key(score_key, client)
            else:
                logger.info(f"Looking up score by name: {score_name}")
                score = Score.get_by_name(score_name, client)
            logger.info(f"Found score: {score.name} ({score.id})")
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
        
        # Create the experiment
        logger.info("Creating experiment...")
        experiment = Experiment.create(
            client=client,
            type=type,
            accountId=account.id,
            status=status,
            accuracy=accuracy,
            accuracyType=accuracy_type,
            sensitivity=sensitivity,
            specificity=specificity,
            precision=precision,
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
        logger.info(f"Created experiment: {experiment.id}")
        
        # Output results
        click.echo(f"Created experiment: {experiment.id}")
        click.echo(f"Type: {experiment.type}")
        click.echo(f"Status: {experiment.status}")
        click.echo(f"Created at: {experiment.createdAt}")
        
    except Exception as e:
        logger.error(f"Error creating experiment: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)

@experiment.command()
@click.argument('id', required=True)
@click.option('--type', help='Type of experiment (e.g., accuracy, consistency)')
@click.option('--status',
              type=click.Choice(['PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED']),
              help='Status of the experiment')
@click.option('--parameters', type=str, help='JSON string of experiment parameters')
@click.option('--metrics', type=str, help='JSON string of experiment metrics')
@click.option('--inferences', type=int, help='Number of inferences made')
@click.option('--results', type=int, help='Number of results processed')
@click.option('--cost', type=float, help='Cost of the experiment')
@click.option('--progress', type=float, help='Progress percentage (0-100)')
@click.option('--accuracy', type=float, help='Accuracy percentage (0-100)')
@click.option('--accuracy-type', help='Type of accuracy measurement')
@click.option('--sensitivity', type=float, help='Sensitivity/recall percentage (0-100)')
@click.option('--specificity', type=float, help='Specificity percentage (0-100)')
@click.option('--precision', type=float, help='Precision percentage (0-100)')
@click.option('--total-items', type=int, help='Total number of items to process')
@click.option('--processed-items', type=int, help='Number of items processed')
@click.option('--error-message', help='Error message if experiment failed')
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
    """Update an existing experiment.
    
    Required fields (type, status) will keep their previous values if not specified.
    The updatedAt timestamp is automatically set to the current time.
    
    Examples:
        plexus-dashboard experiment update abc123 --accuracy 97.8
        plexus-dashboard experiment update def456 --status COMPLETED
        plexus-dashboard experiment update ghi789 --type consistency --status FAILED
    """
    client = PlexusDashboardClient()
    
    try:
        # First get the existing experiment
        logger.info(f"Looking up experiment: {id}")
        experiment = Experiment.get_by_id(id, client)
        logger.info(f"Found experiment: {experiment.id}")
        
        # Build update data with only provided fields
        update_data = {
            # Use provided values or fall back to existing values for required fields
            'type': type or experiment.type,
            'status': status or experiment.status,
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
        
        # Update the experiment
        logger.info("Updating experiment...")
        updated = experiment.update(**update_data)
        logger.info(f"Updated experiment: {updated.id}")
        
        # Output results
        click.echo(f"Updated experiment: {updated.id}")
        click.echo(f"Type: {updated.type}")
        click.echo(f"Status: {updated.status}")
        click.echo(f"Updated at: {updated.updatedAt}")
        
    except Exception as e:
        logger.error(f"Error updating experiment: {str(e)}")
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
        logger.info(f"Looking up score result: {id}")
        result = ScoreResult.get_by_id(id, client)
        logger.info(f"Found score result: {result.id}")
        
        # Build update data
        update_data = {}
        if value is not None: update_data['value'] = value
        if confidence is not None: update_data['confidence'] = confidence
        if metadata is not None: update_data['metadata'] = json.loads(metadata)
        
        # Update score result
        logger.info("Updating score result...")
        updated = result.update(**update_data)
        logger.info(f"Updated score result: {updated.id}")
        
        # Output results
        click.echo(json.dumps({
            'id': updated.id,
            'value': updated.value,
            'confidence': updated.confidence,
            'metadata': updated.metadata
        }, indent=2))
        
    except Exception as e:
        logger.error(f"Error updating score result: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)

@experiment.command()
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
    """Simulate a machine learning evaluation experiment with synthetic data.
    
    This command creates a realistic simulation of an ML model evaluation run by:
    1. Creating an Experiment record to track the evaluation
    2. Generating synthetic binary classification results (Yes/No predictions)
    3. Creating ScoreResult records for each prediction
    4. Computing standard ML metrics (accuracy, precision, sensitivity, specificity)
    5. Updating the Experiment with real-time metric calculations
    
    The simulation uses a target accuracy parameter to generate synthetic predictions
    that will approximately achieve that accuracy level. It introduces random
    variations and delays to simulate real-world conditions.
    
    Metrics are computed using scikit-learn and include:
    - Accuracy: Overall correct predictions
    - Precision: True positives / (True positives + False positives)
    - Sensitivity (Recall): True positives / (True positives + False negatives)
    - Specificity: True negatives / (True negatives + False positives)
    
    The command handles background metric updates using threads, ensuring the
    experiment record stays current as new results are generated.
    
    Args:
        account_key/name/id: Account context (one required)
        scorecard_key/name/id: Scorecard to evaluate (one required)
        score_key/name/id: Optional specific score to evaluate
        num_items: Number of synthetic results to generate (default: 100)
        accuracy: Target accuracy for synthetic data (default: 0.85)
    
    Examples:
        # Basic simulation with 100 items
        plexus-dashboard experiment simulate \
            --account-key call-criteria \
            --scorecard-key agent-scorecard \
            --num-items 100 \
            --accuracy 0.85
            
        # Larger simulation for specific score
        plexus-dashboard experiment simulate \
            --account-key call-criteria \
            --scorecard-key agent-scorecard \
            --score-key compliance \
            --num-items 1000 \
            --accuracy 0.92
    """
    client = PlexusDashboardClient()
    
    try:
        # Look up or validate account
        if account_id:
            logger.info(f"Using provided account ID: {account_id}")
            account = Account.get_by_id(account_id, client)
        elif account_key:
            logger.info(f"Looking up account by key: {account_key}")
            account = Account.get_by_key(account_key, client)
        elif account_name:
            logger.info(f"Looking up account by name: {account_name}")
            account = Account.get_by_name(account_name, client)
        else:
            raise click.UsageError("Must provide account-id, account-key, or account-name")
        
        logger.info(f"Using account: {account.name} ({account.id})")
        
        # Look up or validate scorecard
        if scorecard_id:
            logger.info(f"Using provided scorecard ID: {scorecard_id}")
            scorecard = Scorecard.get_by_id(scorecard_id, client)
        elif scorecard_key:
            logger.info(f"Looking up scorecard by key: {scorecard_key}")
            scorecard = Scorecard.get_by_key(scorecard_key, client)
        elif scorecard_name:
            logger.info(f"Looking up scorecard by name: {scorecard_name}")
            scorecard = Scorecard.get_by_name(scorecard_name, client)
        else:
            raise click.UsageError("Must provide scorecard-id, scorecard-key, or scorecard-name")
            
        logger.info(f"Using scorecard: {scorecard.name} ({scorecard.id})")
        
        # Optionally look up score
        score = None
        if any([score_id, score_key, score_name]):
            if score_id:
                logger.info(f"Using provided score ID: {score_id}")
                score = Score.get_by_id(score_id, client)
            elif score_key:
                logger.info(f"Looking up score by key: {score_key}")
                score = Score.get_by_key(score_key, client)
            else:
                logger.info(f"Looking up score by name: {score_name}")
                score = Score.get_by_name(score_name, client)
            logger.info(f"Using score: {score.name} ({score.id})")

        # Create initial experiment record
        started_at = datetime.now(timezone.utc)
        experiment = Experiment.create(
            client=client,
            type="evaluation",
            accountId=account.id,
            status="RUNNING",
            totalItems=num_items,
            processedItems=0,
            scorecardId=scorecard.id,
            scoreId=score.id if score else None,
            parameters=json.dumps({
                "target_accuracy": accuracy,
                "num_items": num_items
            }),
            startedAt=started_at.isoformat().replace('+00:00', 'Z'),
            # Initial estimate based on 1 second per item
            estimatedEndAt=(started_at + timedelta(seconds=num_items))\
                .isoformat().replace('+00:00', 'Z')
        )
        
        # Lists to store true and predicted values for metrics calculation
        true_values = []
        predicted_values = []
        
        def update_metrics():
            """Calculate and update experiment metrics"""
            try:
                thread_client = PlexusDashboardClient()
                
                y_true = np.array(true_values)
                y_pred = np.array(predicted_values)
                
                # Calculate metrics (convert to percentages)
                acc = accuracy_score(y_true, y_pred) * 100
                prec = precision_score(y_true, y_pred, pos_label="Yes") * 100
                sens = recall_score(y_true, y_pred, pos_label="Yes") * 100
                conf_matrix = confusion_matrix(y_true, y_pred, labels=["Yes", "No"])
                
                # Calculate specificity safely (as percentage)
                tn = conf_matrix[1,1]  # true negatives
                fp = conf_matrix[0,1]  # false positives
                spec = float(tn / (tn + fp) * 100) if (tn + fp) > 0 else None
                
                # Calculate time estimates
                items_processed = len(true_values)
                if items_processed > 0:
                    elapsed_seconds = int((datetime.now(timezone.utc) - started_at)\
                        .total_seconds())
                    avg_time_per_item = elapsed_seconds / items_processed
                    remaining_items = num_items - items_processed
                    estimated_remaining_seconds = int(avg_time_per_item * remaining_items)
                    
                    thread_experiment = Experiment.get_by_id(experiment.id, thread_client)
                    thread_experiment.update(
                        accuracy=float(acc),
                        precision=float(prec),
                        sensitivity=float(sens),
                        specificity=spec if spec is not None else None,
                        processedItems=items_processed,
                        confusionMatrix=json.dumps({
                            "matrix": conf_matrix.tolist(),
                            "labels": ["Yes", "No"]
                        }),
                        elapsedSeconds=elapsed_seconds,
                        estimatedRemainingSeconds=estimated_remaining_seconds
                    )
                
            except Exception as e:
                logger.error(f"Error updating metrics: {str(e)}")
        
        # Pre-generate balanced true values
        yes_count = num_items // 2
        no_count = num_items - yes_count
        true_values_pool = ["Yes"] * yes_count + ["No"] * no_count
        random.shuffle(true_values_pool)
        
        # Simulate results
        for i in range(num_items):
            # Get next true value from balanced pool
            true_value = true_values_pool[i]
            predicted_value = true_value if random.random() < accuracy else \
                            ("No" if true_value == "Yes" else "Yes")
            
            true_values.append(true_value)
            predicted_values.append(predicted_value)
            
            # Create score result
            ScoreResult.create(
                client=client,
                value=1.0 if predicted_value == "Yes" else 0.0,
                confidence=random.uniform(0.7, 0.99),
                correct=(true_value == predicted_value),
                itemId=f"item_{i}",
                accountId=account.id,
                experimentId=experiment.id,
                scorecardId=scorecard.id,
                scoringJobId=None,  # Explicitly set to None since we're using experimentId
                metadata={
                    "true_value": true_value,
                    "predicted_value": predicted_value
                }
            )
            
            # Update metrics in background thread
            thread = threading.Thread(target=update_metrics)
            thread.start()
            
            # Random delay between results
            time.sleep(random.uniform(0.1, 1.0))
            
            # Progress update
            if (i + 1) % 10 == 0:
                logger.info(f"Generated {i + 1} of {num_items} results")
        
        # Final update
        experiment.update(
            status="COMPLETED",
            elapsedSeconds=int((datetime.now(timezone.utc) - started_at).total_seconds()),
            estimatedRemainingSeconds=0  # No remaining time on completion
        )
        logger.info("Simulation completed")
        
    except Exception as e:
        logger.error(f"Error in simulation: {str(e)}")
        if 'experiment' in locals():
            experiment.update(
                status="FAILED",
                errorMessage=str(e),
                elapsedSeconds=int((datetime.now(timezone.utc) - started_at).total_seconds()),
                estimatedRemainingSeconds=None  # Clear estimate on failure
            )
        click.echo(f"Error: {str(e)}", err=True)

def simulate_experiment_progress(experiment_id: str, client: PlexusDashboardClient):
    """Simulate experiment progress by updating metrics over time."""
    experiment = client.get_experiment(experiment_id)
    
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
        
        # Update experiment
        experiment.update(
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
    experiment.update(
        status="COMPLETED",
        processedItems=total_items,
        totalItems=total_items,
        estimatedTimeRemaining="00:00:00"
    )

if __name__ == '__main__':
    cli() 