import re
import rich
from rich import print
from rich.panel import Panel
from rich.columns import Columns
import click
import plexus
import os
import json
import pandas as pd
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_openai import ChatOpenAI
import concurrent.futures
from functools import partial
from typing import List, Dict, Any, Optional
import asyncio
from openai import OpenAI
import aiohttp
import requests
import traceback

from plexus.CustomLogging import logging
from plexus.Registries import scorecard_registry
from plexus.scores.Score import Score
from plexus.Scorecard import Scorecard
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.batch_job import BatchJob
from plexus.cli.shared import select_sample_data_driven, select_sample_csv

# Maximum number of requests per batch
MAX_BATCH_SIZE = 1000

# Add this constant near the top with other constants
STATUS_MAPPING = {
    'validating': 'PROCESSING',
    'created': 'PROCESSING',
    'processing': 'PROCESSING',
    'in_progress': 'PROCESSING',
    'completed': 'PROCESSED',  # Changed from COMPLETED to PROCESSED
    'failed': 'ERROR'
}

# Add this mapping near the top with other constants
MESSAGE_TYPE_MAPPING = {
    'human': 'user',
    'ai': 'assistant',
    'system': 'system'
}

def select_sample(scorecard_class, score_name, content_id, fresh):
    """Wrapper for select_sample functions from PredictionCommands"""
    score_configuration = next(
        (score for score in scorecard_class.scores if score['name'] == score_name), 
        {}
    )
    
    # Check if the score uses the new data-driven approach
    if 'data' in score_configuration:
        return select_sample_data_driven(
            scorecard_class, 
            score_name, 
            content_id, 
            score_configuration, 
            fresh
        )
    else:
        # Use labeled-samples.csv for old scores
        scorecard_key = scorecard_class.properties.get('key')        
        csv_path = os.path.join('scorecards', scorecard_key, 'experiments', 'labeled-samples.csv')
        return select_sample_csv(csv_path, content_id)

@click.group()
def batch():
    """Commands for batch processing with OpenAI models."""
    pass

def get_output_dir(scorecard_name, score_name):
    return f"batch/{scorecard_name}/{score_name}"

def get_file_path(output_dir):
    return f"{output_dir}/batch.jsonl"

async def get_batch_jobs_for_processing(
    client: PlexusDashboardClient,
    account_id: str,
    scorecard_id: Optional[str] = None
) -> List[BatchJob]:
    """Get all CLOSED batch jobs ready for processing."""
    filter_params = {
        'accountId': { 'eq': account_id },
        'status': { 'eq': 'CLOSED' }
    }
    
    if scorecard_id:
        filter_params['scorecardId'] = { 'eq': scorecard_id }
    
    query = """
    query GetClosedBatchJobs($filter: ModelBatchJobFilterInput) {
        listBatchJobs(filter: $filter) {
            items {
                id
                accountId
                type
                batchId
                status
                modelProvider
                modelName
                totalRequests
                scorecardId
                scoreId
                startedAt
                estimatedEndAt
                completedAt
                errorMessage
                errorDetails
                scoringJobCountCache
            }
        }
    }
    """
    result = client.execute(query, {'filter': filter_params})
    return [BatchJob.from_dict(item, client) 
            for item in result.get('listBatchJobs', {}).get('items', [])]

async def get_scoring_jobs_for_batch(
    client: PlexusDashboardClient,
    batch_job_id: str
) -> List[Dict[str, Any]]:
    """Get all scoring jobs associated with a batch job."""
    query = """
    query GetBatchScoringJobs($batchJobId: String!) {
        listBatchJobScoringJobs(
            filter: { batchJobId: { eq: $batchJobId } }
            limit: 1000
        ) {
            items {
                scoringJob {
                    id
                    itemId
                    status
                    metadata
                }
                createdAt
            }
        }
    }
    """
    result = client.execute(query, {'batchJobId': batch_job_id})
    scoring_jobs = [item['scoringJob'] 
                   for item in result.get('listBatchJobScoringJobs', {}).get('items', [])]
    logging.info(f"Found {len(scoring_jobs)} scoring jobs for batch {batch_job_id}")
    return scoring_jobs

@batch.command(help="Generate JSON-L files for batch processing.")
@click.option(
    '--account-key', 
    required=True, 
    help='The account key.'
)
@click.option(
    '--scorecard-key', 
    required=False, 
    default=None, 
    help='Optional: Filter by scorecard key.',
    type=str
)
@click.option(
    '--score-name', 
    required=False, 
    default=None, 
    help='The name of the score to generate JSON-L for.',
    type=str
)
@click.option(
    '--clean-existing', 
    is_flag=True, 
    help='Clean existing JSON-L files.'
)
@click.option(
    '--verbose', 
    is_flag=True, 
    help='Verbose output.'
)
@click.option(
    '--no-submit',
    is_flag=True,
    help='Generate batch file without submitting to OpenAI.'
)
def generate(account_key, scorecard_key, score_name, clean_existing, 
                  verbose, no_submit):
    """Generate JSON-L files in the format required by the OpenAI batching API."""
    
    # Load and register scorecards
    from plexus.Scorecard import Scorecard
    from plexus.Registries import scorecard_registry
    Scorecard.load_and_register_scorecards('scorecards/')
    
    # Debug the registry state
    logging.info("Checking scorecard registry at startup:")
    logging.info(f"Registry items: {list(scorecard_registry.items())}")
    logging.info(f"Registry classes by ID: {scorecard_registry._classes_by_id}")
    logging.info(f"Registry classes by key: {scorecard_registry._classes_by_key}")
    
    asyncio.run(_generate_batch(
        account_key, scorecard_key, score_name, clean_existing, verbose, no_submit
    ))

async def submit_batch_to_openai(batch_file_path: str, model_name: str) -> dict:
    """Submit a batch job to OpenAI's batch processing endpoint."""
    client = OpenAI()
    
    try:
        # First upload the file
        with open(batch_file_path, 'rb') as f:
            file_response = client.files.create(
                file=f,
                purpose='batch'
            )
        logging.info(f"File uploaded to OpenAI with ID: {file_response.id}")
        
        # Create the batch processing job
        batch_response = client.batches.create(
            input_file_id=file_response.id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        
        # Log the full response to see what we're getting
        logging.info(f"OpenAI batch response: {batch_response}")
        
        # Make sure we're using the correct batch ID format
        if not batch_response.id.startswith('batch_'):
            logging.error(f"Unexpected batch ID format: {batch_response.id}")
            
        return batch_response
        
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Failed to submit batch to OpenAI: {error_msg}")
        
        # Try to parse validation errors from OpenAI
        if hasattr(e, 'response') and hasattr(e.response, 'json'):
            try:
                error_details = e.response.json()
                if 'error' in error_details:
                    error_msg = error_details['error'].get('message', error_msg)
            except:
                pass
        
        raise Exception(f"OpenAI batch submission failed: {error_msg}")

async def _generate_batch(account_key, scorecard_key, score_name, clean_existing, 
                         verbose, no_submit):
    """Async implementation of batch generation."""
    raise NotImplementedError(
        "Batch generation functionality is not currently available. "
        "It required client-specific database integration that has been removed."
    )

@batch.command(help="Check status of running batch jobs")
@click.option(
    '--account-key',
    required=True,
    help='The account key'
)
def status(account_key):
    """Check status of running OpenAI batch jobs."""
    asyncio.run(_check_status(account_key))

async def _check_status(account_key):
    """Async implementation of status check."""
    client = PlexusDashboardClient.for_account(account_key)
    account_id = client._resolve_account_id()
    
    # Query for batch jobs that are in progress
    query = """
    query GetProcessingBatchJobs($filter: ModelBatchJobFilterInput) {
        listBatchJobs(filter: $filter) {
            items {
                id
                accountId
                batchId
                status
                completedRequests
                totalRequests
                failedRequests
                modelProvider
                modelName
                type
            }
        }
    }
    """
    filter_params = {
        'accountId': {'eq': account_id},
        'status': {'eq': 'PROCESSING'},
        'and': [
            {'modelProvider': {'attributeExists': True}},
            {'modelName': {'attributeExists': True}}
        ]
    }
    
    result = client.execute(query, {'filter': filter_params})
    batch_jobs = result.get('listBatchJobs', {}).get('items', [])
    
    if not batch_jobs:
        logging.info("No in-progress batch jobs found with required fields")
        return
        
    openai_client = OpenAI()
    
    for job in batch_jobs:
        try:
            openai_batch_id = job['batchId']
            if not openai_batch_id:
                logging.warning(f"Batch job {job['id']} has no OpenAI batch ID")
                continue
                
            # Get the batch info to get the output file ID
            batch_info = openai_client.batches.retrieve(job['batchId'])
            logging.info(f"Retrieved batch info for {job['batchId']}")
            logging.info("Batch info:")
            logging.info(f"  status: {batch_info.status}")
            logging.info(f"  output_file_id: {batch_info.output_file_id}")
            logging.info(f"  request_counts: total={batch_info.request_counts.total}, "
                        f"completed={batch_info.request_counts.completed}, "
                        f"failed={batch_info.request_counts.failed}")
            
            # Update counts if they've changed
            if (batch_info.request_counts.completed != job.get('completedRequests') or
                batch_info.request_counts.failed != job.get('failedRequests')):
                update_mutation = """
                mutation UpdateBatchJob($input: UpdateBatchJobInput!) {
                    updateBatchJob(input: $input) {
                        id
                        status
                        completedRequests
                        failedRequests
                        totalRequests
                    }
                }
                """
                
                update_input = {
                    'id': job['id'],
                    'accountId': job['accountId'],
                    'status': STATUS_MAPPING.get(batch_info.status, 'PROCESSING'),
                    'type': job.get('type', 'MultiStepScore'),
                    'batchId': job['batchId'],
                    'modelProvider': job['modelProvider'],
                    'modelName': job['modelName'],
                    'completedRequests': batch_info.request_counts.completed,
                    'failedRequests': batch_info.request_counts.failed,
                    'totalRequests': batch_info.request_counts.total
                }
                
                logging.info(f"Updating batch job {job['id']} with new counts:")
                logging.info(f"  Completed: {batch_info.request_counts.completed}")
                logging.info(f"  Failed: {batch_info.request_counts.failed}")
                logging.info(f"  Total: {batch_info.request_counts.total}")
                
                client.execute(update_mutation, {'input': update_input})
            
            # Check if batch failed
            if batch_info.status == 'failed' or batch_info.request_counts.failed == batch_info.request_counts.total:
                logging.error(f"Batch {job['batchId']} failed")
                # Update batch job with error status
                error_mutation = """
                mutation UpdateBatchJob($input: UpdateBatchJobInput!) {
                    updateBatchJob(input: $input) {
                        id
                        status
                        errorMessage
                    }
                }
                """
                
                error_input = {
                    'id': job['id'],
                    'accountId': job['accountId'],
                    'status': 'ERROR',
                    'type': 'MultiStepScore',
                    'batchId': job['batchId'],
                    'modelProvider': job['modelProvider'],
                    'modelName': job['modelName'],
                    'errorMessage': f"OpenAI batch failed: {batch_info.status}"
                }
                
                client.execute(error_mutation, {'input': error_input})
                continue
            
            # Only try to get output file if batch completed successfully
            if batch_info.status == 'completed' and batch_info.output_file_id:
                content = openai_client.files.retrieve_content(batch_info.output_file_id)
                logging.info(f"Retrieved content from output file {batch_info.output_file_id}")
                # ... rest of output file processing code ...
                
        except Exception as e:
            logging.error(f"Error processing batch {job['id']}: {str(e)}")
            logging.error(f"Full traceback: {traceback.format_exc()}")
            
            # Update batch job with error status
            error_mutation = """
            mutation UpdateBatchJob($input: UpdateBatchJobInput!) {
                updateBatchJob(input: $input) {
                    id
                    status
                    errorMessage
                }
            }
            """
            
            error_input = {
                'id': job['id'],
                'accountId': job['accountId'],
                'status': 'ERROR',
                'type': 'MultiStepScore',
                'batchId': job['batchId'],
                'modelProvider': job['modelProvider'],
                'modelName': job['modelName'],
                'errorMessage': str(e)[:1000]  # Truncate if too long
            }
            
            client.execute(error_mutation, {'input': error_input})

@batch.command(help="Process results from completed OpenAI batch jobs")
@click.option(
    '--account-key',
    required=True,
    help='The account key'
)
def complete(account_key):
    """Process results from OpenAI batch jobs marked as PROCESSED."""
    asyncio.run(_complete_batches(account_key))

async def _complete_batches(account_key):
    """Async implementation of batch completion."""
    client = PlexusDashboardClient.for_account(account_key)
    account_id = client._resolve_account_id()
    openai_client = OpenAI()
    
    # Load and register scorecards
    Scorecard.load_and_register_scorecards('scorecards/')
    
    # Get processed batch jobs
    query = """
    query GetProcessedBatches($filter: ModelBatchJobFilterInput) {
        listBatchJobs(filter: $filter) {
            items {
                id
                accountId
                batchId
                status
                modelProvider
                modelName
                scorecardId
                scoreId
                completedRequests
                totalRequests
                failedRequests
            }
        }
    }
    """
    
    filter_params = {
        'accountId': {'eq': account_id},
        'status': {'eq': 'PROCESSED'}
    }
    
    result = client.execute(query, {'filter': filter_params})
    batch_jobs = result.get('listBatchJobs', {}).get('items', [])
    
    if not batch_jobs:
        logging.info("No processed batch jobs found waiting for completion")
        return
        
    for job in batch_jobs:
        logging.info(f"\nProcessing batch job:")
        logging.info(f"  ID: {job['id']}")
        logging.info(f"  OpenAI Batch ID: {job['batchId']}")
        
        try:
            # Get the batch info to get the output file ID
            batch_info = openai_client.batches.retrieve(job['batchId'])
            logging.info(f"Retrieved batch info for {job['batchId']}")
            
            # Skip if batch is still in progress or has no output
            if batch_info.status in ['validating', 'created', 'processing', 'in_progress'] or \
               not batch_info.output_file_id:
                logging.info(f"Batch {job['batchId']} is still in progress or has no output - skipping")
                continue
            
            # Get the output file content
            content = openai_client.files.retrieve_content(batch_info.output_file_id)
            logging.info(f"Retrieved content from output file {batch_info.output_file_id}")
            
            # Get scoring jobs for this batch
            scoring_jobs = await get_scoring_jobs_for_batch(client, job['id'])
            if not scoring_jobs:
                logging.error(f"No scoring jobs found for batch {job['id']}")
                continue
            
            # Get scorecard and score info
            scorecard_result = client.execute("""
                query GetScorecardInfo($scorecardId: ID!) {
                    getScorecard(id: $scorecardId) {
                        key
                        name
                    }
                }
            """, {'scorecardId': job['scorecardId']})
            scorecard_key = scorecard_result['getScorecard']['key']
            
            score_result = client.execute("""
                query GetScoreInfo($scoreId: ID!) {
                    getScore(id: $scoreId) {
                        name
                    }
                }
            """, {'scoreId': job['scoreId']})
            score_name = score_result['getScore']['name']
            
            # Get scorecard class
            scorecard_class = scorecard_registry.get(scorecard_key.lower())
            if not scorecard_class:
                logging.error(f"Could not find scorecard class for key: {scorecard_key}")
                continue
            
            # Process each line of the output
            for line in content.splitlines():
                result = json.loads(line)
                content_id = result['custom_id']
                response_content = result['response']['body']['choices'][0]['message']['content']
                logging.info(f"Processing result for content_id {content_id}")
                
                try:
                    # Get sample data
                    sample_row, used_content_id = select_sample(
                        scorecard_class, 
                        score_name,
                        content_id,
                        fresh=False
                    )
                    
                    if sample_row is None or sample_row.empty:
                        logging.error(f"Could not find sample data for content_id {content_id}")
                        continue
                    
                    # Create metadata for Score.Input
                    metadata = {
                        "content_id": str(content_id),
                        "account_key": account_key,
                        "scorecard_key": scorecard_key,
                        "score_name": score_name,
                        "batch": {
                            "completion": response_content
                        }
                    }
                    logging.info(f"Created metadata for Score.Input: {metadata}")

                    # Create Score.Input with batch completion in metadata
                    score_input = Score.Input(
                        text=sample_row.iloc[0]['text'],
                        metadata=metadata
                    )

                    # Create config for the score
                    config = {
                        "configurable": {
                            "thread_id": str(content_id)
                        }
                    }

                    # Let the score class handle all LangGraph details
                    async with Score.from_name(scorecard_key, score_name) as score:
                        result = await score.predict(config, score_input)
                        logging.info(f"Prediction completed with result: {result}")

                    # Get scoring job for this content_id - moved outside the if result check
                    scoring_job = next(
                        (sj for sj in scoring_jobs if sj['itemId'] == content_id),
                        None
                    )
                    
                    if scoring_job:
                        # Update scoring job status to COMPLETED
                        update_mutation = """
                        mutation UpdateScoringJob($input: UpdateScoringJobInput!) {
                            updateScoringJob(input: $input) {
                                id
                                status
                            }
                        }
                        """
                        
                        update_input = {
                            'id': scoring_job['id'],
                            'status': 'COMPLETED',
                            'accountId': job['accountId'],
                            'scorecardId': job['scorecardId'],
                            'itemId': content_id
                        }
                        
                        client.execute(update_mutation, {'input': update_input})
                        logging.info(f"Updated scoring job {scoring_job['id']} status to COMPLETED")

                        # Create score result if we have a value
                        if isinstance(result, dict) and 'value' in result:
                            create_result_mutation = """
                            mutation CreateScoreResult($input: CreateScoreResultInput!) {
                                createScoreResult(input: $input) {
                                    id
                                    value
                                }
                            }
                            """
                            
                            result_input = {
                                'accountId': job['accountId'],
                                'scorecardId': job['scorecardId'],
                                'itemId': content_id,
                                'scoringJobId': scoring_job['id'],
                                'value': result['value'],
                                'code': '200',
                                'type': 'prediction'  # Batch processing creates prediction results
                            }
                            
                            client.execute(create_result_mutation, {'input': result_input})
                            logging.info(f"Created score result for scoring job {scoring_job['id']}")

                except Exception as e:
                    logging.error(f"Error processing content_id {content_id}: {str(e)}")
                    logging.error(f"Full traceback: {traceback.format_exc()}")
                    continue

            # After processing all results, update batch job status to COMPLETED
            update_batch_mutation = """
            mutation UpdateBatchJob($input: UpdateBatchJobInput!) {
                updateBatchJob(input: $input) {
                    id
                    status
                }
            }
            """
            
            update_batch_input = {
                'id': job['id'],
                'accountId': job['accountId'],
                'status': 'COMPLETED',
                'type': 'MultiStepScore',
                'batchId': job['batchId'],
                'modelProvider': job['modelProvider'],
                'modelName': job['modelName']
            }
            
            client.execute(update_batch_mutation, {'input': update_batch_input})
            logging.info(f"Updated batch job {job['id']} status to COMPLETED")

        except Exception as e:
            logging.error(f"Error processing batch {job['id']}: {str(e)}")
            logging.error(f"Full traceback: {traceback.format_exc()}")

@batch.command(help="Mark a batch job as PROCESSED for testing")
@click.option(
    '--account-key',
    required=True,
    help='The account key'
)
@click.option(
    '--batch-id',
    required=True,
    help='The batch job ID to mark as PROCESSED'
)
def mark_processed(account_key, batch_id):
    """Manually mark a batch job as PROCESSED for testing."""
    asyncio.run(_mark_processed(account_key, batch_id))

async def _mark_processed(account_key, batch_id):
    """Async implementation of marking a batch as PROCESSED."""
    client = PlexusDashboardClient.for_account(account_key)
    
    update_mutation = """
    mutation UpdateBatchJob($input: UpdateBatchJobInput!) {
        updateBatchJob(input: $input) {
            id
            status
        }
    }
    """
    
    # First get the current batch job to get its accountId
    query = """
    query GetBatchJob($id: ID!) {
        getBatchJob(id: $id) {
            id
            accountId
            type
            modelProvider
            modelName
            batchId
        }
    }
    """
    
    result = client.execute(query, {'id': batch_id})
    batch_job = result.get('getBatchJob')
    
    if not batch_job:
        logging.error(f"Could not find batch job with ID {batch_id}")
        return
        
    update_input = {
        'id': batch_id,
        'accountId': batch_job['accountId'],
        'status': 'PROCESSED',
        'type': batch_job.get('type', 'MultiStepScore'),
        'modelProvider': batch_job.get('modelProvider', 'ChatOpenAI'),
        'modelName': batch_job.get('modelName', 'gpt-4'),
        'batchId': batch_job.get('batchId')
    }
    
    result = client.execute(update_mutation, {'input': update_input})
    logging.info(f"Marked batch job {batch_id} as PROCESSED")