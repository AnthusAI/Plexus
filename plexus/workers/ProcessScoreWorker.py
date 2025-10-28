#!/usr/bin/env python3
"""
Process Score Worker - Async Job Processor

This script polls an SQS queue for scoring job messages, retrieves the
corresponding ScoringJob from DynamoDB, performs the scoring work, and
creates ScoreResults in DynamoDB for caching.

The worker:
- Polls an SQS queue (SCORING_REQUEST_STANDARD_QUEUE_URL) for job messages
- Retrieves text and metadata directly from DynamoDB Item records
- Performs scoring using the Plexus scorecard system
- Creates ScoreResult records in DynamoDB
- Sends response message with score_result_id to another SQS queue (SCORING_RESPONSE_QUEUE_URL)
- Deletes SQS messages after successful processing

This worker interacts with DynamoDB and SQS.

Usage:
    python ProcessScoreWorker.py [--once] [--poll-interval SECONDS]

Options:
    --once: Process one job and exit (for testing)
    --poll-interval: Seconds to wait between error retries (default: 5)

Environment Variables:
    SCORING_REQUEST_STANDARD_QUEUE_URL: SQS queue URL for receiving scoring requests
    SCORING_RESPONSE_QUEUE_URL: SQS queue URL for sending score result responses
    PLEXUS_ACCOUNT_KEY: Plexus account key
"""

import asyncio
import argparse
import traceback
import json
import os
import boto3
from datetime import datetime, timezone
from dotenv import load_dotenv

# Setup logging
from plexus.CustomLogging import logging, set_log_group
set_log_group('plexus/score/worker')

# Import Plexus components
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.scoring_job import ScoringJob
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.scorecard import Scorecard
from plexus.dashboard.api.models.score import Score
from plexus.utils.scoring import create_scorecard_instance_for_single_score, resolve_scorecard_id, resolve_score_id
from plexus.utils.request_log_capture import capture_request_logs
from plexus.utils.scoring import get_text_from_item, get_metadata_from_item, get_external_id_from_item, create_score_result

class JobProcessor:
    """Handles polling and processing of scoring jobs"""

    def __init__(self, poll_interval=5):
        """
        Initialize the job processor

        Args:
            poll_interval: Number of seconds to wait between polls for new jobs
        """
        self.poll_interval = poll_interval
        self.client = PlexusDashboardClient()
        self.sqs_client = boto3.client('sqs')
        self.request_queue_url = os.environ.get('SCORING_REQUEST_STANDARD_QUEUE_URL')
        self.response_queue_url = os.environ.get('SCORING_RESPONSE_QUEUE_URL')
        self.account_key = os.environ.get('PLEXUS_ACCOUNT_KEY')

        if not self.request_queue_url or not self.response_queue_url or not self.account_key:
            raise ValueError("Missing required environment variables: SCORING_REQUEST_STANDARD_QUEUE_URL, SCORING_RESPONSE_QUEUE_URL, PLEXUS_ACCOUNT_KEY")

    async def initialize(self):
        """Initialize the processor by resolving account ID"""
        logging.info(f"🔄 Initializing job processor for account: {self.account_key}...")

        # Get the account using SDK method
        account = await asyncio.to_thread(Account.get_by_key, self.account_key, self.client)
        
        if not account:
            logging.error(f"No account found with key: {self.account_key}")
            return None
            
        account_id = account.id
        logging.info(f"Initialized with account: {account.name} (ID: {account_id})")
        self.account_id = account_id

    async def poll_sqs_for_job(self):
        """
        Poll SQS queue for a scoring job message

        Returns:
            Dict with scoring_job_id, item_id, scorecard_id, score_id, receipt_handle if found, None otherwise
        """
        try:
            # Receive message from SQS queue
            response = await asyncio.to_thread(
                self.sqs_client.receive_message,
                QueueUrl=self.request_queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,  # Long polling
                VisibilityTimeout=300  # 5 minutes to process
            )

            messages = response.get('Messages', [])
            if not messages:
                return None

            message = messages[0]
            receipt_handle = message['ReceiptHandle']

            # Parse the message body
            try:
                body = json.loads(message['Body'])
                scoring_job_id = body.get('scoring_job_id')

                if not scoring_job_id:
                    logging.error(f"Message missing scoring_job_id: {body}")
                    return None

                logging.info(f"📬 Received SQS message for ScoringJob: {scoring_job_id}")

                # Get the ScoringJob from DynamoDB
                scoring_job = await asyncio.to_thread(ScoringJob.get_by_id, scoring_job_id, self.client)

                if not scoring_job:
                    logging.error(f"ScoringJob not found: {scoring_job_id}")
                    return None

                # Claim it by updating status to IN_PROGRESS
                await asyncio.to_thread(
                    scoring_job.update,
                    status='IN_PROGRESS',
                    startedAt=datetime.now(timezone.utc).isoformat()
                )

                logging.info(f"✅ Claimed ScoringJob {scoring_job_id}, updated to IN_PROGRESS")

                # Get item_id, scorecard_id, and score_id from the job
                item_id = scoring_job.itemId
                scorecard_id = scoring_job.scorecardId
                score_id = scoring_job.scoreId

                # Get scorecard and score external IDs using model methods
                scorecard = await asyncio.to_thread(Scorecard.get_by_id, scorecard_id, self.client)
                scorecard_external_id = scorecard.externalId if scorecard else None

                score = await asyncio.to_thread(Score.get_by_id, score_id, self.client)
                score_external_id = score.externalId if score else None

                return {
                    'scoring_job_id': scoring_job_id,
                    'item_id': item_id,
                    'scorecard_id': scorecard_external_id,
                    'score_id': score_external_id,
                    'receipt_handle': receipt_handle
                }

            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse SQS message body: {message['Body']}, error: {e}")
                return None

        except Exception as e:
            logging.error(f"Error polling SQS queue: {e}")
            logging.error(traceback.format_exc())
            return None

    async def process_job(self, scoring_job_id, item_id, scorecard_id, score_id, receipt_handle):
        """
        Process a claimed scoring job

        Args:
            scoring_job_id: The DynamoDB ScoringJob ID
            item_id: The DynamoDB Item ID
            scorecard_id: The scorecard external ID
            score_id: The score external ID
            receipt_handle: The SQS message receipt handle for deletion
        """

        try:
            with capture_request_logs() as (request_id, get_logs):
                logging.info(f"🔄 Processing job: scoring_job_id={scoring_job_id}, item_id={item_id}, scorecard_id={scorecard_id}, score_id={score_id}")
                logging.info(json.dumps({
                    "message_type": "job_processing_started",
                    "request_id": request_id,
                    "scoring_job_id": scoring_job_id,
                    "item_id": item_id,
                    "scorecard_id": scorecard_id,
                    "score_id": score_id
                }))

                # Get the ScoringJob object
                scoring_job = await asyncio.to_thread(ScoringJob.get_by_id, scoring_job_id, self.client)

                # Resolve DynamoDB IDs
                dynamo_scorecard_id = await resolve_scorecard_id(scorecard_id, self.account_id, self.client)
                if not dynamo_scorecard_id:
                    raise Exception(f"Could not resolve scorecard ID: {scorecard_id}")

                resolved_score_info = await resolve_score_id(score_id, dynamo_scorecard_id, self.client)
                if not resolved_score_info:
                    raise Exception(f"Could not resolve score ID: {score_id}")

                dynamo_score_id = resolved_score_info['id']

                # Get transcript, metadata, and external_id from Item
                logging.info(f"🔄 Fetching transcript, metadata, and external_id from Item")
                transcript_text = await get_text_from_item(item_id, self.client)
                if not transcript_text:
                    raise Exception(f"No transcript found for item {item_id}")

                metadata = await get_metadata_from_item(item_id, self.client)
                if not metadata:
                    metadata = {}

                external_id = await get_external_id_from_item(item_id, self.client)
                if not external_id:
                    raise Exception(f"No external_id found for item {item_id}")

                # Create scorecard instance and perform scoring
                logging.info(f"🔄 Creating scorecard instance and scoring...")
                scorecard_instance = await create_scorecard_instance_for_single_score(
                    scorecard_id,
                    score_id
                )

                if not scorecard_instance:
                    raise Exception(f"Failed to create scorecard instance for {scorecard_id}")

                # Perform scoring
                score_results = await scorecard_instance.score_entire_text(
                    text=transcript_text,
                    metadata=metadata,
                    modality="API"
                )

                result = score_results.get(dynamo_score_id)
                if not result:
                    raise Exception(f"No result returned for score {dynamo_score_id}")

                value = str(result.value) if result.value is not None else None
                explanation = result.metadata.get('explanation', '') if result.metadata else ''

                # Check for ERROR result
                if value and value.upper() == "ERROR":
                    logging.error(f"❌ Scoring returned ERROR for item_id={item_id}")

                    # Update ScoringJob to FAILED
                    await asyncio.to_thread(
                        scoring_job.update,
                        status='FAILED',
                        errorMessage=explanation[:255] if explanation else "Scoring returned ERROR value",
                        completedAt=datetime.now(timezone.utc).isoformat()
                    )

                    logging.info(f"❌ Job failed with ERROR result")
                    return

                # Success - create ScoreResult in DynamoDB for caching
                logging.info(f"💾 Creating ScoreResult in DynamoDB for future cache hits")
                try:
                    # Check specifically for trace - try multiple possible locations based on BaseNode.log_state
                    trace_data = None
                    
                    # First try direct access (for backward compatibility)
                    if "trace" in result.metadata:
                        trace_data = result.metadata["trace"]
                        logging.info(f"🔍 Found trace data directly in metadata: {type(trace_data)}")
                    
                    # Check for BaseNode trace structure: metadata.trace.node_results
                    elif "metadata" in result.metadata and isinstance(result.metadata["metadata"], dict):
                        nested_metadata = result.metadata["metadata"]
                        if "trace" in nested_metadata and isinstance(nested_metadata["trace"], dict):
                            if "node_results" in nested_metadata["trace"]:
                                trace_data = nested_metadata["trace"]
                                logging.info(f"🔍 Found BaseNode trace data in metadata.trace: {type(trace_data)}")
                                logging.info(f"🔍 Node results count: {len(trace_data.get('node_results', []))}")
                            else:
                                trace_data = nested_metadata["trace"]
                                logging.info(f"🔍 Found trace data in nested metadata: {type(trace_data)}")
                    
                    # NEW: Check if the entire result.metadata IS the LangGraph state
                    # This happens when LangGraph workflow returns the full state as metadata
                    elif "text" in result.metadata and "metadata" in result.metadata:
                        # This looks like the full LangGraph state was returned as metadata
                        logging.info("🔍 Detected full LangGraph state in metadata - extracting trace from nested structure")
                        if isinstance(result.metadata.get("metadata"), dict):
                            nested_meta = result.metadata["metadata"]
                            if "trace" in nested_meta and isinstance(nested_meta["trace"], dict):
                                trace_data = nested_meta["trace"]
                                logging.info(f"🔍 Found trace in LangGraph state structure: {type(trace_data)}")
                                if "node_results" in trace_data:
                                    logging.info(f"🔍 Node results count: {len(trace_data['node_results'])}")
                    
                    # ADDITIONAL: Check if trace data is directly in the LangGraph state fields
                    # Sometimes the BaseNode.log_state puts trace data directly in the state
                    elif "metadata" in result.metadata and isinstance(result.metadata["metadata"], dict):
                        state_metadata = result.metadata["metadata"]
                        if "trace" in state_metadata:
                            trace_data = state_metadata["trace"]
                            logging.info(f"🔍 Found trace data in state metadata: {type(trace_data)}")
                            if isinstance(trace_data, dict) and "node_results" in trace_data:
                                logging.info(f"🔍 Node results count: {len(trace_data['node_results'])}")
                    
                    # Log what we found
                    if trace_data:
                        logging.info(f"🔍 Trace data extracted successfully: {type(trace_data)}")
                        logging.info(f"🔍 Trace data content: {json.dumps(trace_data, indent=2, default=str)}")
                    else:
                        logging.info("🔍 No trace data found in any expected location")
                        # Log all possible locations we checked
                        logging.info("🔍 Checked locations:")
                        logging.info("🔍   - result.metadata['trace']")
                        logging.info("🔍   - result.metadata['metadata']['trace']")
                        logging.info("🔍   - result.metadata['metadata']['trace']['node_results']")
                        logging.info("🔍   - result.metadata (as LangGraph state).metadata.trace")

                    # Extract cost if available
                    cost = None
                    if result.metadata and 'cost' in result.metadata:
                        cost = result.metadata.get('cost')

                    # Get current logs before storing the result
                    current_logs = get_logs()
                    logging.info(f"📋 Captured {len(current_logs) if current_logs else 0} bytes of logs for upload")
                    if current_logs:
                        logging.info(f"📋 First 200 chars of captured logs: {current_logs[:200]}...")
                    else:
                        logging.info("📋 No logs captured - get_logs() returned empty/None")

                    score_result_id = await create_score_result(
                        item_id=item_id,
                        scorecard_id=dynamo_scorecard_id,
                        score_id=dynamo_score_id,
                        account_id=self.account_id,
                        scoring_job_id=scoring_job_id,
                        external_id=external_id,
                        value=value,
                        explanation=explanation,
                        trace_data=trace_data,
                        log_content=current_logs,
                        cost=cost,
                        client=self.client
                    )

                    # Check if ScoreResult creation was successful
                    if not score_result_id:
                        logging.error("❌ Failed to create ScoreResult - score_result_id is None")
                        raise ValueError("Failed to create ScoreResult in DynamoDB")
                    
                    logging.info(f"✅ Successfully created ScoreResult cache entry: {score_result_id}")
                    
                    # Send response message to SCORING_RESPONSE_QUEUE_URL
                    try:
                        response_message = {
                            "score_result_id": score_result_id
                        }
                        await asyncio.to_thread(
                            self.sqs_client.send_message,
                            QueueUrl=self.response_queue_url,
                            MessageBody=json.dumps(response_message)
                        )
                        logging.info(f"📤 Sent response message to queue for ScoreResult: {score_result_id}")
                    except Exception as send_error:
                        logging.error(f"Failed to send response message: {send_error}")
                        logging.error(traceback.format_exc())
                        raise  # Re-raise to prevent marking job as completed
                        
                except Exception as cache_error:
                    logging.error(f"Failed to create ScoreResult cache entry: {cache_error}")
                    logging.error(traceback.format_exc())
                    raise  # Re-raise to trigger the outer exception handler

                # Success - update ScoringJob to COMPLETED
                await asyncio.to_thread(
                    scoring_job.update,
                    status='COMPLETED',
                    completedAt=datetime.now(timezone.utc).isoformat()
                )

                # Delete the SQS message after successful processing
                await asyncio.to_thread(
                    self.sqs_client.delete_message,
                    QueueUrl=self.request_queue_url,
                    ReceiptHandle=receipt_handle
                )

                logging.info(f"✅ Job completed successfully: value={value}")
                logging.info(f"📌 ScoreResult created in DynamoDB")

        except Exception as e:
            logging.error(f"❌ Job processing failed: {e}")
            logging.error(traceback.format_exc())

            # Mark job as failed in DynamoDB
            if scoring_job_id:
                try:
                    scoring_job = await asyncio.to_thread(
                        ScoringJob.get_by_id,
                        scoring_job_id,
                        self.client
                    )
                    await asyncio.to_thread(
                        scoring_job.update,
                        status='FAILED',
                        errorMessage=str(e)[:255],
                        completedAt=datetime.now(timezone.utc).isoformat()
                    )
                    logging.info(f"✅ Updated ScoringJob to FAILED in DynamoDB")

                except Exception as update_error:
                    logging.error(f"Failed to update ScoringJob to FAILED: {update_error}")

    async def run(self, once=False):
        """
        Main run loop - poll for jobs and process them

        Args:
            once: If True, process one job and exit. If False, run continuously.
        """
        await self.initialize()

        logging.info(f"🚀 Worker started (Request Queue: {self.request_queue_url}, Response Queue: {self.response_queue_url}, once={once})")

        while True:
            try:
                # Poll SQS for a job
                job = await self.poll_sqs_for_job()

                if job:
                    await self.process_job(
                        job['scoring_job_id'],
                        job['item_id'],
                        job['scorecard_id'],
                        job['score_id'],
                        job['receipt_handle']
                    )

                    if once:
                        logging.info("✅ Processed one job, exiting (--once mode)")
                        break
                else:
                    # No messages in queue
                    if once:
                        logging.info("No jobs available, exiting (--once mode)")
                        break
                    else:
                        # SQS long polling will wait, so we can immediately poll again
                        logging.debug("No messages received, polling again...")

            except KeyboardInterrupt:
                logging.info("🛑 Worker stopped by user")
                break
            except Exception as e:
                logging.error(f"❌ Unexpected error in run loop: {e}")
                logging.error(traceback.format_exc())

                if once:
                    break
                else:
                    # Wait before retrying on error
                    await asyncio.sleep(self.poll_interval)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Process async scoring jobs')
    parser.add_argument('--once', action='store_true', help='Process one job and exit')
    parser.add_argument('--poll-interval', type=int, default=5, help='Seconds between polls (default: 5)')
    args = parser.parse_args()

    # Load environment - search up directory tree for .env file
    load_dotenv()

    # Create and run processor
    processor = JobProcessor(poll_interval=args.poll_interval)
    await processor.run(once=args.once)


if __name__ == "__main__":
    asyncio.run(main())

def run():
    """Wrapper for gunicorn to run the worker"""
    asyncio.run(main())