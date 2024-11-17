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
from plexus_dashboard.api.client import PlexusDashboardClient
from plexus_dashboard.api.models.account import Account
from plexus_dashboard.api.models.experiment import Experiment
from plexus_dashboard.api.models.scorecard import Scorecard
from plexus_dashboard.api.models.score import Score
from plexus_dashboard.api.models.score_result import ScoreResult
import json
import random
import time
import threading
from sklearn.metrics import (
    accuracy_score, 
    precision_score,
    recall_score,  # sensitivity
    confusion_matrix,
    balanced_accuracy_score,
    f1_score
)
import numpy as np
from datetime import datetime, timezone, timedelta
from plexus_dashboard.commands.simulate import (
    generate_class_distribution,
    simulate_prediction,
    select_metrics_and_explanation,
    calculate_metrics,
    SCORE_GOALS,
    POSSIBLE_CLASSES
)

# Configure logging with a more concise format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname).1s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add after other constants
SCORE_TYPES = ['binary', 'multiclass']
DATA_BALANCES = ['balanced', 'unbalanced']
SCORE_GOALS = ['sensitivity', 'precision', 'balanced']
POSSIBLE_CLASSES = [
    "3rd Party Clinic", "Agent calling for a Patient", "Follow-up Appointment",
    "New Patient Registration", "Insurance Verification", "Patient Referral",
    "Lab Results Inquiry", "Medication Refill Request", "Appointment Cancellation",
    "Telehealth Consultation", "Patient Feedback", "Emergency Contact",
    "Billing Inquiry", "Health Record Request"
]

def generate_class_distribution(num_classes: int, total_items: int, balanced: bool) -> list:
    """Generate a distribution of classes with counts."""
    if balanced:
        # Even distribution
        base_count = total_items // num_classes
        remainder = total_items % num_classes
        counts = [base_count for _ in range(num_classes)]
        # Distribute remainder
        for i in range(remainder):
            counts[i] += 1
    else:
        # Generate imbalanced distribution using exponential decay
        remaining_items = total_items
        counts = []
        for i in range(num_classes - 1):
            # Take a random portion of remaining items, more for earlier classes
            portion = random.uniform(0.3, 0.7) if i == 0 else random.uniform(0.1, 0.4)
            count = int(remaining_items * portion)
            counts.append(count)
            remaining_items -= count
        counts.append(remaining_items)  # Last class gets the remainder
    
    # Shuffle the classes
    selected_classes = random.sample(POSSIBLE_CLASSES, num_classes)
    
    return [
        {"label": label, "count": count}
        for label, count in zip(selected_classes, counts)
    ]

def simulate_prediction(true_label: str, accuracy: float, valid_labels: list) -> str:
    """Generate a prediction that's correct with probability accuracy."""
    if random.random() < accuracy:
        return true_label
    else:
        # Pick a random incorrect label
        other_labels = [l for l in valid_labels if l != true_label]
        return random.choice(other_labels)

def select_metrics_and_explanation(
    is_binary: bool,
    is_balanced: bool,
    score_goal: str
) -> tuple[list[str], str]:
    """Select appropriate metrics and explanation based on experiment characteristics"""
    metrics_config = {
        "binary": {
            "balanced": {
                "sensitivity": (
                    ["Sensitivity", "Accuracy", "Precision", "F1"],
                    "Sensitivity is prioritized to maximize true positive detection rate"
                ),
                "precision": (
                    ["Precision", "Accuracy", "Sensitivity", "F1"],
                    "Precision is prioritized to minimize false positive predictions"
                ),
                "balanced": (
                    ["Balanced Accuracy", "Precision", "Sensitivity", "F1"],
                    "Balanced accuracy ensures equal treatment of all classes"
                )
            },
            "unbalanced": {
                "sensitivity": (
                    ["Sensitivity", "Balanced Accuracy", "Precision", "F1"],
                    "Sensitivity focus with balanced accuracy for imbalanced data"
                ),
                "precision": (
                    ["Precision", "Balanced Accuracy", "Sensitivity", "NPV"],
                    "Precision focus with balanced metrics for imbalanced data"
                ),
                "balanced": (
                    ["Balanced Accuracy", "Precision", "Sensitivity", "F1"],
                    "Balanced metrics chosen for imbalanced dataset"
                )
            }
        },
        "multiclass": {
            "balanced": {
                "sensitivity": (
                    ["Macro Sensitivity", "Accuracy", "Macro Precision", "Macro F1"],
                    "Macro sensitivity prioritized across all classes"
                ),
                "precision": (
                    ["Macro Precision", "Accuracy", "Macro Sensitivity", "Macro F1"],
                    "Macro precision prioritized for reliable predictions"
                ),
                "balanced": (
                    ["Accuracy", "Macro Precision", "Macro Sensitivity", "Macro F1"],
                    "Balanced evaluation across all classes"
                )
            },
            "unbalanced": {
                "sensitivity": (
                    ["Macro Sensitivity", "Balanced Accuracy", "Macro Precision", 
                     "Macro F1"],
                    "Macro sensitivity with balanced accuracy for fairness"
                ),
                "precision": (
                    ["Macro Precision", "Balanced Accuracy", "Macro Sensitivity", 
                     "Macro F1"],
                    "Macro precision with balanced handling of classes"
                ),
                "balanced": (
                    ["Balanced Accuracy", "Macro Precision", "Macro Sensitivity", 
                     "Macro F1"],
                    "Balanced metrics for fair multiclass evaluation"
                )
            }
        }
    }
    
    classification_type = "binary" if is_binary else "multiclass"
    balance_type = "balanced" if is_balanced else "unbalanced"
    
    return metrics_config[classification_type][balance_type][score_goal]

def calculate_metrics(true_values, predicted_values, is_binary, is_balanced, score_goal):
    """Calculate metrics based on experiment characteristics"""
    metric_names, explanation = select_metrics_and_explanation(
        is_binary, is_balanced, score_goal
    )
    
    # Convert lists to numpy arrays
    y_true = np.array(true_values)
    y_pred = np.array(predicted_values)
    
    metrics = []
    for metric_name in metric_names:
        if metric_name == "Accuracy":
            value = accuracy_score(y_true, y_pred) * 100
        elif metric_name == "Balanced Accuracy":
            value = balanced_accuracy_score(y_true, y_pred) * 100
        elif metric_name in ["Precision", "Macro Precision"]:
            value = precision_score(y_true, y_pred, average='macro', 
                                  zero_division=0) * 100
        elif metric_name in ["Sensitivity", "Macro Sensitivity"]:
            value = recall_score(y_true, y_pred, average='macro', 
                               zero_division=0) * 100
        elif metric_name in ["F1", "Macro F1"]:
            value = f1_score(y_true, y_pred, average='macro', 
                           zero_division=0) * 100
        else:  # NPV - custom calculation
            tn = np.sum((y_true != 1) & (y_pred != 1))
            fn = np.sum((y_true == 1) & (y_pred != 1))
            value = (tn / (tn + fn) if (tn + fn) > 0 else 0) * 100
        
        metrics.append({
            "name": metric_name,
            "value": float(value),
            "unit": "%",
            "maximum": 100,
            "priority": metric_names.index(metric_name) == 0
        })
    
    return metrics, explanation

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
    """
    try:
        # Initial client for setup
        client = PlexusDashboardClient()
        
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

        # Randomly decide experiment characteristics
        is_binary = random.random() < 0.3  # 30% chance of binary classification
        num_classes = 2 if is_binary else random.randint(3, 14)
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
                "num_items": num_items,
                "num_classes": num_classes,
                "is_balanced": is_balanced
            }),
            startedAt=started_at.isoformat().replace('+00:00', 'Z'),
            estimatedRemainingSeconds=num_items,
            scoreGoal=score_goal,
            datasetClassDistribution=json.dumps(dataset_distribution),
            isDatasetClassDistributionBalanced=is_balanced,
            metricsExplanation=initial_explanation  # Use the explanation from our function
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
                logger.info(f"Result {i}: true={true_value}, "
                          f"predicted={predicted_value}, correct={is_correct}")

                create_args = {
                    "value": 1.0 if is_correct else 0.0,
                    "confidence": random.uniform(0.7, 0.99),
                    "correct": is_correct,
                    "itemId": f"item_{i}",
                    "accountId": account.id,
                    "experimentId": experiment.id,
                    "scorecardId": scorecard.id,
                    "scoringJobId": None,
                    "metadata": {
                        "true_value": true_value,
                        "predicted_value": predicted_value,
                        "label": predicted_value
                    }
                }
                
                logger.info(f"Creating score result with args: {create_args}")
                result = ScoreResult.create(
                    client=iteration_client,
                    **create_args
                )
                logger.info(f"Created score result: {result.id}, correct={result.correct}")

                # Calculate metrics immediately after each result
                metrics, metrics_explanation = calculate_metrics(
                    true_values,
                    predicted_values,
                    num_classes == 2,
                    is_balanced,
                    score_goal
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

                # Update experiment with current metrics
                update_data = {
                    "metrics": json.dumps(metrics) if metrics else None,
                    "processedItems": processed_items,
                    "elapsedSeconds": elapsed_seconds,
                    "estimatedRemainingSeconds": estimated_remaining_seconds,
                    "predictedClassDistribution": json.dumps(predicted_distribution),
                    "isPredictedClassDistributionBalanced": is_predicted_balanced,
                    "metricsExplanation": metrics_explanation,
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
                logger.info(f"Updating experiment with data: {json.dumps(update_data, indent=2)}")
                
                # Create new client for update
                update_client = PlexusDashboardClient()
                # Use the client's updateExperiment method directly
                update_client.updateExperiment(
                    id=experiment.id,
                    **update_data
                )
                
            except Exception as e:
                logger.error(f"Error in iteration {i}: {str(e)}")
                continue  # Continue to next iteration instead of failing completely
            
            # Random delay between results
            time.sleep(random.uniform(0.1, 1.0))
            
            # Progress update
            if (i + 1) % 10 == 0:
                logger.info(f"Generated {i + 1} of {num_items} results")
        
        # Final update
        final_client = PlexusDashboardClient()
        final_client.updateExperiment(
            id=experiment.id,
            status="COMPLETED",
            elapsedSeconds=int((datetime.now(timezone.utc) - started_at).total_seconds()),
            estimatedRemainingSeconds=0
        )
        logger.info("Simulation completed")
        
    except Exception as e:
        logger.error(f"Error in simulation: {str(e)}")
        if 'experiment' in locals():
            try:
                # Error update
                error_client = PlexusDashboardClient()
                error_client.updateExperiment(
                    id=experiment.id,
                    status="FAILED",
                    errorMessage=str(e),
                    elapsedSeconds=int((datetime.now(timezone.utc) - started_at).total_seconds()),
                    estimatedRemainingSeconds=None
                )
            except Exception as update_error:
                logger.error(f"Error updating experiment status: {str(update_error)}")
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

@experiment.command()
@click.argument('id', required=True)
def count_results(id: str):
    """Count score results for an experiment"""
    client = PlexusDashboardClient()
    
    try:
        # Get experiment with score results included
        response = client.execute("""
            query GetExperiment($id: ID!) {
                getExperiment(id: $id) {
                    scoreResults {
                        items {
                            value
                            confidence
                            metadata
                            correct
                        }
                    }
                }
            }
        """, {'id': id})
        
        # Get the items array directly from the nested response
        items = response.get('getExperiment', {}).get('scoreResults', {}).get('items', [])
        result_count = len(items)
            
        click.echo(f"Score results for experiment {id}: {result_count}")
        
    except Exception as e:
        logger.error(f"Error counting results: {e}")
        click.echo(f"Error: {e}", err=True)

if __name__ == '__main__':
    cli() 