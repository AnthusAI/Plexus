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
from langchain_community.chat_models import ChatOpenAI
import concurrent.futures
from functools import partial
from typing import List, Dict, Any, Optional
import asyncio
from openai import OpenAI
import aiohttp
import requests

from plexus.CustomLogging import logging
from plexus.Registries import scorecard_registry
from plexus.scores.Score import Score
from plexus_dashboard.api.client import PlexusDashboardClient
from plexus_dashboard.api.models.batch_job import BatchJob

# Maximum number of requests per batch
MAX_BATCH_SIZE = 1000

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
def generate_batch(account_key, scorecard_key, score_name, clean_existing, 
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

async def _generate_batch(account_key, scorecard_key, score_name, clean_existing, 
                         verbose, no_submit):
    """Async implementation of batch generation."""
    client = PlexusDashboardClient.for_account(account_key)
    
    account_id = client._resolve_account_id()
    scorecard_id = client._resolve_scorecard_id(scorecard_key) if scorecard_key else None
    
    filter_desc = f"account_id={account_id}"
    if scorecard_id:
        filter_desc += f", scorecard_id={scorecard_id}"
    logging.info(f"Looking for batch jobs with {filter_desc}")
    
    batch_jobs = await get_batch_jobs_for_processing(
        client, account_id, scorecard_id
    )
    
    logging.info(f"Found {len(batch_jobs)} closed batch jobs")
    
    if not batch_jobs:
        logging.info("No closed batch jobs found ready for processing")
        return

    # Import DB-related classes
    from call_criteria_database import DB, VWForm
    from sqlalchemy import select
    import os
    from dotenv import load_dotenv
    
    # Load environment variables and initialize DB
    load_dotenv()
    DB.initialize(
        os.getenv('DB_SERVER'),
        os.getenv('DB_NAME'),
        os.getenv('DB_USER'),
        os.getenv('DB_PASS')
    )

    for batch_job in batch_jobs:
        logging.info(f"\nProcessing batch job {batch_job.id}:")
        logging.info(f"  Model: {batch_job.modelProvider}/{batch_job.modelName}")
        logging.info(f"  Scorecard: {batch_job.scorecardId}")
        logging.info(f"  Score: {batch_job.scoreId}")
        
        scoring_jobs = await get_scoring_jobs_for_batch(client, batch_job.id)
        report_ids = [job['itemId'] for job in scoring_jobs]
        
        if not report_ids:
            logging.warning(f"No items found for batch job {batch_job.id}")
            continue
            
        logging.info(f"  Found {len(report_ids)} report IDs to process:")
        for report_id in report_ids:
            logging.info(f"    - {report_id}")

        # Look up form IDs from report IDs
        with DB.get_session() as session:
            query = select(VWForm.f_id).where(VWForm.review_id.in_(report_ids))
            form_ids = [row[0] for row in session.execute(query)]
            
        logging.info(f"  Mapped to {len(form_ids)} form IDs:")
        for form_id in form_ids:
            logging.info(f"    - {form_id}")

        # Create data configuration for CallCriteriaDBCache
        data_config = {
            'class': 'CallCriteriaDBCache',
            'searches': [{
                'items': [{'form_id': form_id} for form_id in form_ids],
                'scorecard_id': batch_job.scorecardId
            }]
        }
        
        # Initialize the cache
        from plexus.data.DataCache import DataCache
        from plexus_extensions.CallCriteriaDBCache import CallCriteriaDBCache
        
        cache = CallCriteriaDBCache(**data_config)
        df = cache.load_dataframe(data=data_config)
        
        logging.info(f"Loaded dataframe with {len(df)} rows")
        if len(df) > 0:
            # Create output directory
            output_dir = get_output_dir(scorecard_key or "all", score_name or "all")
            os.makedirs(output_dir, exist_ok=True)
            batch_file_path = get_file_path(output_dir)

            if clean_existing and os.path.exists(batch_file_path):
                os.remove(batch_file_path)
                logging.info(f"Removed existing file: {batch_file_path}")

            # Initialize the classifier to get its prompts
            from plexus.scores.nodes.Classifier import Classifier
            
            # Get the scorecard key from DynamoDB using the ID
            query = """
            query GetScorecardAndScore($scorecardId: ID!, $scoreId: ID!) {
                getScorecard(id: $scorecardId) {
                    id
                    key
                    name
                }
                getScore(id: $scoreId) {
                    id
                    name
                    configuration
                }
            }
            """
            result = client.execute(query, {
                'scorecardId': batch_job.scorecardId,
                'scoreId': batch_job.scoreId
            })
            
            if not result or 'getScorecard' not in result:
                logging.error(f"Could not find scorecard in DynamoDB with ID: {batch_job.scorecardId}")
                continue
                
            if not result or 'getScore' not in result:
                logging.error(f"Could not find score in DynamoDB with ID: {batch_job.scoreId}")
                continue
                
            scorecard_key = result['getScorecard']['key'].lower()  # Registry uses lowercase keys
            score_name = result['getScore']['name']
            logging.info(f"Found scorecard key in DynamoDB: {scorecard_key}")
            logging.info(f"Found score name in DynamoDB: {score_name}")
            
            # Now use these to look up the scorecard and score
            scorecard_class = scorecard_registry.get(scorecard_key)
            if not scorecard_class:
                logging.error(f"Could not find scorecard in registry with key: {scorecard_key}")
                logging.info("Available scorecards in registry:")
                for key in scorecard_registry._classes_by_key.keys():
                    logging.info(f"  - {key}")
                continue
            
            # Get the score configuration using the scorecard class and score name
            score = Score.from_name(scorecard_key, score_name)
            
            # Get the classifier parameters from the score configuration
            query = """
            query GetScoreConfig($id: ID!) {
                getScore(id: $id) {
                    id
                    name
                    configuration
                }
            }
            """
            result = client.execute(query, {'id': batch_job.scoreId})
            if not result or 'getScore' not in result:
                logging.error(f"Could not find score configuration for ID: {batch_job.scoreId}")
                continue
                
            score_config = result['getScore'].get('configuration', {}) or {}
            classifier_params = {
                **score.parameters.model_dump(),
                'positive_class': 'Present',  # Default for IVR Present score
                'negative_class': 'Not Present'
            }
            
            # Override defaults with any config from DynamoDB if available
            if score_config:
                classifier_params.update({
                    'positive_class': score_config.get('positive_class', classifier_params['positive_class']),
                    'negative_class': score_config.get('negative_class', classifier_params['negative_class'])
                })
            
            classifier = Classifier(**classifier_params)
            
            entries_written = 0
            with open(batch_file_path, "w") as batch_file:
                logging.info("\nProcessing rows for batch file:")
                
                # Drop duplicates based on content_id, keeping the first occurrence
                df = df.drop_duplicates(subset=['content_id'], keep='first')
                logging.info(f"After deduplication: {len(df)} unique content_ids")
                
                for form_id in form_ids:
                    logging.info(f"\nLooking for rows with form_id={form_id}")
                    matching_rows = df[df['form_id'] == form_id]
                    logging.info(f"Found {len(matching_rows)} matching rows")
                    
                    if not matching_rows.empty:
                        for _, row in matching_rows.iterrows():
                            # Generate messages using the classifier's prompt
                            state = {
                                "text": row['text'],
                                "metadata": {"content_id": row['content_id']}
                            }
                            
                            # Create a specific prompt template for IVR Present classification
                            prompt_template = ChatPromptTemplate.from_messages([
                                ("system", "You are an AI assistant that determines if an IVR system is present in a call transcript."),
                                ("user", "Please analyze this call transcript and determine if an IVR system is present. "
                                        "An IVR (Interactive Voice Response) system is an automated phone system that interacts "
                                        "with callers before connecting to a human agent. "
                                        "Respond with either 'Present' if you detect an IVR system, or 'Not Present' if you don't.\n\n"
                                        "Transcript: {text}")
                            ])
                            
                            messages = prompt_template.format_prompt(**state).to_messages()
                            
                            request = {
                                "custom_id": str(row['content_id']),
                                "method": "POST",
                                "url": "/v1/chat/completions",
                                "body": {
                                    "model": batch_job.modelName,
                                    "messages": [
                                        {
                                            "role": "system" if isinstance(msg, SystemMessage) else "user",
                                            "content": msg.content
                                        }
                                        for msg in messages
                                    ],
                                    "temperature": 0.0,
                                    "top_p": 0.03,
                                    "max_tokens": 1000
                                }
                            }
                            logging.info(f"Writing entry {entries_written + 1}:")
                            logging.info(f"  form_id: {row['form_id']}")
                            logging.info(f"  content_id: {row['content_id']}")
                            logging.info(f"  text length: {len(row['text'])}")
                            logging.info(f"  messages: {[type(m).__name__ for m in messages]}")
                            json.dump(request, batch_file)
                            batch_file.write("\n")
                            entries_written += 1
            
            logging.info(f"\nGenerated batch file with {entries_written} entries for job {batch_job.id} in {output_dir}")

            if not no_submit:
                try:
                    logging.info(f"Submitting batch job to OpenAI...")
                    response = await submit_batch_to_openai(
                        batch_file_path,
                        batch_job.modelName
                    )
                    logging.info(f"Batch job created successfully. ID: {response.id}")
                    logging.info(f"Full OpenAI response: {response}")
                    
                    # Update the batch job with the OpenAI batch ID
                    update_mutation = """
                    mutation UpdateBatchJob($input: UpdateBatchJobInput!) {
                        updateBatchJob(input: $input) {
                            id
                            status
                            batchId
                            totalRequests
                        }
                    }
                    """
                    
                    # Map OpenAI status to our status
                    status_mapping = {
                        'validating': 'PROCESSING',
                        'created': 'PROCESSING',
                        'processing': 'PROCESSING',
                        'in_progress': 'PROCESSING',
                        'completed': 'COMPLETED',
                        'failed': 'ERROR'
                    }
                    
                    new_status = status_mapping.get(response.status, 'ERROR')
                    if new_status == 'ERROR':
                        logging.warning(f"Unrecognized OpenAI status: {response.status}")
                    
                    update_input = {
                        'id': batch_job.id,
                        'accountId': batch_job.accountId,
                        'status': new_status,  # Use mapped status instead of hardcoding 'PROCESSING'
                        'batchId': response.id,
                        'type': batch_job.type,
                        'modelProvider': batch_job.modelProvider,
                        'modelName': batch_job.modelName,
                        'totalRequests': entries_written
                    }
                    
                    client.execute(update_mutation, {'input': update_input})
                    
                    # Get current batch data before updating count
                    batch_query = """
                    query GetBatchJob($batchId: ID!) {
                        getBatchJob(id: $batchId) {
                            id
                            accountId
                            status
                            type
                            batchId
                            modelProvider
                            modelName
                            scoringJobCountCache
                        }
                    }
                    """
                    current_batch = client.execute(batch_query, {'batchId': batch_job.id})
                    batch_data = current_batch.get('getBatchJob', {})

                    # Update count mutation with all required fields
                    update_count_mutation = """
                    mutation UpdateBatchJobCount($input: UpdateBatchJobInput!) {
                        updateBatchJob(input: $input) {
                            id
                            scoringJobCountCache
                            status
                        }
                    }
                    """
                    update_result = client.execute(
                        update_count_mutation,
                        {
                            'input': {
                                'id': batch_job.id,
                                'accountId': batch_data['accountId'],
                                'status': batch_data['status'],
                                'type': batch_data['type'],
                                'batchId': batch_data['batchId'],
                                'modelProvider': batch_data['modelProvider'],
                                'modelName': batch_data['modelName'],
                                'scoringJobCountCache': entries_written
                            }
                        }
                    )
                    logging.info(f"Updated batch job count: {update_result}")
                    
                    # If we've reached or exceeded max_batch_size and batch is still open, close it
                    if entries_written >= MAX_BATCH_SIZE and current_status == 'OPEN':
                        logging.info(
                            f"Batch job {batch_job.id} has reached max size "
                            f"({entries_written}/{MAX_BATCH_SIZE}). Closing batch."
                        )
                        close_mutation = """
                        mutation CloseBatchJob($input: UpdateBatchJobInput!) {
                            updateBatchJob(input: $input) {
                                id
                                status
                                scoringJobCountCache
                            }
                        }
                        """
                        close_result = self.execute(
                            close_mutation, 
                            {
                                'input': {
                                    'id': batch_job.id,
                                    'accountId': batch_data['accountId'],
                                    'status': 'CLOSED',
                                    'type': batch_data['type'],
                                    'batchId': batch_data['batchId'],
                                    'modelProvider': batch_data['modelProvider'],
                                    'modelName': batch_data['modelName'],
                                    'scoringJobCountCache': entries_written
                                }
                            }
                        )
                        logging.info(f"Batch job closed: {close_result}")
                    
                except Exception as e:
                    logging.error(f"Failed to submit batch job to OpenAI: {str(e)}")
                    error_message = str(e)
                    if len(error_message) > 1000:
                        error_message = error_message[:997] + "..."
                        
                    update_data = {
                        'status': "ERROR",
                        'errorMessage': error_message
                    }
                    batch_job.update(**update_data)
            else:
                batch_job.update(status="PROCESSING") 

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
    query GetInProgressBatches($filter: ModelBatchJobFilterInput) {
        listBatchJobs(filter: $filter) {
            items {
                id
                accountId
                batchId
                status
                completedRequests
                totalRequests
                failedRequests
            }
        }
    }
    """
    filter_params = {
        'accountId': {'eq': account_id},
        'status': {'ne': 'COMPLETED'}
    }
    
    result = client.execute(query, {'filter': filter_params})
    batch_jobs = result.get('listBatchJobs', {}).get('items', [])
    
    if not batch_jobs:
        logging.info("No in-progress batch jobs found")
        return
        
    openai_client = OpenAI()
    
    for job in batch_jobs:
        openai_batch_id = job['batchId']
        if not openai_batch_id:
            logging.warning(f"Batch job {job['id']} has no OpenAI batch ID")
            continue
            
        try:
            # Get status from OpenAI using the OpenAI batch ID
            batch_info = openai_client.batches.retrieve(openai_batch_id)
            logging.info(f"OpenAI batch status: {batch_info.status}")
            
            # Map OpenAI status to our status
            status_mapping = {
                'validating': 'PROCESSING',
                'created': 'PROCESSING',
                'processing': 'PROCESSING',
                'in_progress': 'PROCESSING',
                'completed': 'COMPLETED',
                'failed': 'ERROR'
            }
            
            new_status = status_mapping.get(batch_info.status, 'ERROR')
            if new_status == 'ERROR':
                logging.warning(f"Unrecognized OpenAI status: {batch_info.status}")
            
            # Update mutation
            update_mutation = """
            mutation UpdateBatchJob($input: UpdateBatchJobInput!) {
                updateBatchJob(input: $input) {
                    id
                    status
                    completedRequests
                    totalRequests
                    failedRequests
                }
            }
            """
            
            # Get the counts directly from batch_info
            logging.info(f"OpenAI batch request_counts: {batch_info.request_counts}")
            completed_count = batch_info.request_counts.completed
            total_count = batch_info.request_counts.total
            failed_count = batch_info.request_counts.failed
            logging.info(
                f"Parsed counts - completed: {completed_count}, "
                f"total: {total_count}, failed: {failed_count}"
            )
            
            update_input = {
                'id': job['id'],
                'accountId': job['accountId'],
                'status': new_status,
                'completedRequests': completed_count,
                'totalRequests': total_count,
                'failedRequests': failed_count
            }
            
            result = client.execute(update_mutation, {'input': update_input})
            logging.info(f"Update result: {result}")
            
        except Exception as e:
            logging.error(f"Error checking batch {job['batchId']}: {str(e)}") 