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
from .api.client import PlexusAPIClient
from .api.models.account import Account
from .api.models.experiment import Experiment
from .api.models.scorecard import Scorecard
from .api.models.score import Score
from .api.models.sample import Sample
from .api.models.score_result import ScoreResult
import json

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
    client = PlexusAPIClient()
    
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
    client = PlexusAPIClient()
    
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
def sample():
    """Manage experiment samples"""
    pass

@sample.command()
@click.argument('experiment-id', required=True)
@click.option('--data', required=True, type=str, 
              help='JSON string of sample data')
@click.option('--prediction', help='Model prediction')
@click.option('--ground-truth', help='Ground truth label')
@click.option('--is-correct', type=bool, help='Whether prediction matches truth')
def create(
    experiment_id: str,
    data: str,
    prediction: Optional[str] = None,
    ground_truth: Optional[str] = None,
    is_correct: Optional[bool] = None,
):
    """Create a new sample for an experiment.
    
    Examples:
        plexus-dashboard sample create abc123 --data '{"text": "example"}'
        plexus-dashboard sample create def456 --data '{"text": "test"}' \
            --prediction "positive" --ground-truth "negative"
    """
    client = PlexusAPIClient()
    
    try:
        # Validate experiment exists
        logger.info(f"Looking up experiment: {experiment_id}")
        experiment = Experiment.get_by_id(experiment_id, client)
        logger.info(f"Found experiment: {experiment.id}")
        
        # Parse data JSON
        try:
            data_dict = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in data: {str(e)}")
        
        # Create sample
        logger.info("Creating sample...")
        sample = Sample.create(
            client=client,
            experimentId=experiment_id,
            data=data_dict,
            prediction=prediction,
            groundTruth=ground_truth,
            isCorrect=is_correct
        )
        logger.info(f"Created sample: {sample.id}")
        
        # Output results
        click.echo(f"Created sample: {sample.id}")
        click.echo(f"Experiment: {sample.experimentId}")
        click.echo(f"Created at: {sample.createdAt}")
        
    except Exception as e:
        logger.error(f"Error creating sample: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)

@sample.command()
@click.argument('id', required=True)
@click.option('--prediction', help='Model prediction')
@click.option('--ground-truth', help='Ground truth label')
@click.option('--is-correct', type=bool, help='Whether prediction matches truth')
def update(
    id: str,
    prediction: Optional[str] = None,
    ground_truth: Optional[str] = None,
    is_correct: Optional[bool] = None,
):
    """Update an existing sample.
    
    Examples:
        plexus-dashboard sample update abc123 --prediction "positive"
        plexus-dashboard sample update def456 --is-correct true
    """
    client = PlexusAPIClient()
    
    try:
        # Get existing sample
        logger.info(f"Looking up sample: {id}")
        sample = Sample.get_by_id(id, client)
        logger.info(f"Found sample: {sample.id}")
        
        # Build update data
        update_data = {}
        if prediction is not None: update_data['prediction'] = prediction
        if ground_truth is not None: update_data['groundTruth'] = ground_truth
        if is_correct is not None: update_data['isCorrect'] = is_correct
        
        # Update sample
        logger.info("Updating sample...")
        updated = sample.update(**update_data)
        logger.info(f"Updated sample: {updated.id}")
        
        # Output results
        click.echo(f"Updated sample: {updated.id}")
        click.echo(f"Updated at: {updated.updatedAt}")
        
    except Exception as e:
        logger.error(f"Error updating sample: {str(e)}")
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
    client = PlexusAPIClient()
    
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
    client = PlexusAPIClient()
    
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

if __name__ == '__main__':
    cli() 