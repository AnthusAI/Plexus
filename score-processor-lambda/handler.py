#!/usr/bin/env python3
"""
Lambda Handler for Score Processing

This handler processes scoring jobs from SQS. It can be invoked:
1. Manually via AWS Console "Test" button - polls queue for 1 message
2. Directly from fan-out Lambda - processes specific message passed in event
3. Later: Directly triggered by SQS (future enhancement)

The handler:
- For manual invocation: Polls SQS queue for ONE scoring job message
- For fan-out invocation: Processes message from event payload
- Retrieves the ScoringJob from DynamoDB
- Performs scoring using Plexus scorecard system
- Creates ScoreResult in DynamoDB
- Sends response to PLEXUS_RESPONSE_WORKER_QUEUE_URL
- Deletes SQS message after success

Environment Variables:
    PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL: SQS queue URL
    PLEXUS_RESPONSE_WORKER_QUEUE_URL: Response queue URL
    PLEXUS_ACCOUNT_KEY: Plexus account key
"""

import asyncio
import json
import os
import traceback
from datetime import datetime, timezone

import boto3
import logging
from plexus.dashboard.api.client import PlexusDashboardClient

# Set writable directory for Lambda environment (only writable dir is /tmp)
os.environ.setdefault('SCORECARD_CACHE_DIR', '/tmp/scorecards')
# Set NLTK data path to use pre-downloaded data in image, with /tmp as fallback
os.environ.setdefault('NLTK_DATA', '/usr/local/share/nltk_data:/tmp/nltk_data')
from plexus.dashboard.api.models.scoring_job import ScoringJob
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.scorecard import Scorecard
from plexus.dashboard.api.models.score import Score
from plexus.utils.scoring import (
    create_scorecard_instance_for_single_score,
    resolve_scorecard_id,
    resolve_score_id,
    get_text_from_item,
    get_metadata_from_item,
    get_external_id_from_item,
    create_score_result
)
from plexus.utils.request_log_capture import capture_request_logs


class LambdaJobProcessor:
    """Processes a single scoring job for Lambda execution"""

    def __init__(self):
        """Initialize the Lambda job processor"""
        logging.info("🚀 Initializing Lambda job processor")

        self.client = PlexusDashboardClient()
        self.sqs_client = boto3.client('sqs')
        self.request_queue_url = os.environ.get('PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL')
        self.response_queue_url = os.environ.get('PLEXUS_RESPONSE_WORKER_QUEUE_URL')
        self.account_key = os.environ.get('PLEXUS_ACCOUNT_KEY')

        if not self.request_queue_url or not self.response_queue_url or not self.account_key:
            raise ValueError(
                "Missing required environment variables: "
                "PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL, "
                "PLEXUS_RESPONSE_WORKER_QUEUE_URL, "
                "PLEXUS_ACCOUNT_KEY"
            )

    async def initialize(self):
        """Initialize by resolving account ID"""
        logging.info(f"🔄 Resolving account: {self.account_key}")

        account = await asyncio.to_thread(Account.get_by_key, self.account_key, self.client)

        if not account:
            raise ValueError(f"No account found with key: {self.account_key}")

        self.account_id = account.id
        logging.info(f"✅ Initialized with account: {account.name} (ID: {self.account_id})")

    async def poll_sqs_once(self):
        """
        Poll SQS queue for ONE message

        Returns:
            Dict with job details and receipt_handle if found, None otherwise
        """
        try:
            logging.info(f"📬 Polling SQS queue: {self.request_queue_url}")

            response = await asyncio.to_thread(
                self.sqs_client.receive_message,
                QueueUrl=self.request_queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10,  # Wait up to 10 seconds
                VisibilityTimeout=300  # 5 minutes to process
            )

            messages = response.get('Messages', [])
            if not messages:
                logging.info("📭 No messages in queue")
                return None

            message = messages[0]
            receipt_handle = message['ReceiptHandle']

            # Parse message body
            body = json.loads(message['Body'])
            scoring_job_id = body.get('scoring_job_id')

            if not scoring_job_id:
                logging.error(f"❌ Message missing scoring_job_id: {body}")
                return None

            logging.info(f"📬 Received message for ScoringJob: {scoring_job_id}")

            # Get ScoringJob from DynamoDB
            scoring_job = await asyncio.to_thread(ScoringJob.get_by_id, scoring_job_id, self.client)

            if not scoring_job:
                logging.error(f"❌ ScoringJob not found: {scoring_job_id}")
                return None

            # Claim it
            await asyncio.to_thread(
                scoring_job.update,
                status='IN_PROGRESS',
                startedAt=datetime.now(timezone.utc).isoformat()
            )

            logging.info(f"✅ Claimed ScoringJob {scoring_job_id}")

            # Get external IDs
            scorecard = await asyncio.to_thread(Scorecard.get_by_id, scoring_job.scorecardId, self.client)
            scorecard_external_id = scorecard.externalId if scorecard else None

            score = await asyncio.to_thread(Score.get_by_id, scoring_job.scoreId, self.client)
            score_external_id = score.externalId if score else None

            return {
                'scoring_job_id': scoring_job_id,
                'item_id': scoring_job.itemId,
                'scorecard_id': scorecard_external_id,
                'score_id': score_external_id,
                'receipt_handle': receipt_handle
            }

        except Exception as e:
            logging.error(f"❌ Error polling SQS: {e}")
            logging.error(traceback.format_exc())
            return None

    async def process_job(self, scoring_job_id, item_id, scorecard_id, score_id, receipt_handle):
        """
        Process a scoring job

        This is adapted from ProcessScoreWorker.process_job()
        """
        try:
            with capture_request_logs() as (request_id, get_logs):
                logging.info(f"🔄 Processing job: {scoring_job_id}")
                logging.info(json.dumps({
                    "message_type": "job_processing_started",
                    "request_id": request_id,
                    "scoring_job_id": scoring_job_id,
                    "item_id": item_id,
                    "scorecard_id": scorecard_id,
                    "score_id": score_id
                }))

                # Get ScoringJob
                scoring_job = await asyncio.to_thread(ScoringJob.get_by_id, scoring_job_id, self.client)

                # Resolve IDs
                dynamo_scorecard_id = await resolve_scorecard_id(scorecard_id, self.account_id, self.client)
                if not dynamo_scorecard_id:
                    raise Exception(f"Could not resolve scorecard ID: {scorecard_id}")

                resolved_score_info = await resolve_score_id(score_id, dynamo_scorecard_id, self.client)
                if not resolved_score_info:
                    raise Exception(f"Could not resolve score ID: {score_id}")

                dynamo_score_id = resolved_score_info['id']

                # Get data from Item
                logging.info("🔄 Fetching transcript and metadata")
                transcript_text = await get_text_from_item(item_id, self.client)
                if not transcript_text:
                    raise Exception(f"No transcript found for item {item_id}")

                metadata = await get_metadata_from_item(item_id, self.client)
                if not metadata:
                    metadata = {}

                # Desanitize metadata (parse JSON strings back to dicts/lists)
                if isinstance(metadata, dict):
                    for key, value in list(metadata.items()):
                        if isinstance(value, str):
                            try:
                                metadata[key] = json.loads(value)
                            except (json.JSONDecodeError, ValueError):
                                pass  # Keep as string

                external_id = await get_external_id_from_item(item_id, self.client)
                if not external_id:
                    raise Exception(f"No external_id found for item {item_id}")

                # Create scorecard and score
                logging.info("🔄 Creating scorecard instance")
                scorecard_instance = await create_scorecard_instance_for_single_score(
                    scorecard_id,
                    score_id
                )

                if not scorecard_instance:
                    raise Exception(f"Failed to create scorecard instance for {scorecard_id}")

                # Perform scoring
                logging.info("🎯 Performing scoring")
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
                    logging.error(f"❌ Scoring returned ERROR")
                    await asyncio.to_thread(
                        scoring_job.update,
                        status='FAILED',
                        errorMessage=explanation[:255] if explanation else "Scoring returned ERROR",
                        completedAt=datetime.now(timezone.utc).isoformat()
                    )
                    return

                # Extract trace data
                trace_data = None
                if "trace" in result.metadata:
                    trace_data = result.metadata["trace"]
                elif "metadata" in result.metadata and isinstance(result.metadata["metadata"], dict):
                    nested_metadata = result.metadata["metadata"]
                    if "trace" in nested_metadata:
                        trace_data = nested_metadata["trace"]

                # Extract cost
                cost = result.metadata.get('cost') if result.metadata else None

                # Get logs
                current_logs = get_logs()
                logging.info(f"📋 Captured {len(current_logs) if current_logs else 0} bytes of logs")

                # Create ScoreResult
                logging.info("💾 Creating ScoreResult in DynamoDB")
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

                if not score_result_id:
                    raise ValueError("Failed to create ScoreResult in DynamoDB")

                logging.info(f"✅ Created ScoreResult: {score_result_id}")

                # Send response message
                response_message = {"score_result_id": score_result_id}
                await asyncio.to_thread(
                    self.sqs_client.send_message,
                    QueueUrl=self.response_queue_url,
                    MessageBody=json.dumps(response_message)
                )
                logging.info(f"📤 Sent response message")

                # Update ScoringJob to COMPLETED
                await asyncio.to_thread(
                    scoring_job.update,
                    status='COMPLETED',
                    completedAt=datetime.now(timezone.utc).isoformat()
                )

                # Delete SQS message
                await asyncio.to_thread(
                    self.sqs_client.delete_message,
                    QueueUrl=self.request_queue_url,
                    ReceiptHandle=receipt_handle
                )

                logging.info(f"✅ Job completed successfully: value={value}")

        except Exception as e:
            logging.error(f"❌ Job processing failed: {e}")
            logging.error(traceback.format_exc())

            # Mark as failed
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
                except Exception as update_error:
                    logging.error(f"Failed to update ScoringJob to FAILED: {update_error}")

            raise  # Re-raise to signal Lambda failure


async def async_handler(event, context):
    """Async Lambda handler"""
    logging.info(f"🚀 Lambda invoked")
    logging.info(f"Event: {json.dumps(event)}")

    try:
        processor = LambdaJobProcessor()
        await processor.initialize()

        # Check if this is a direct invocation from fan-out Lambda
        if event.get('source') == 'fanout':
            logging.info("📨 Processing direct invocation from fan-out Lambda")

            # Extract message details from event
            message_body = event.get('message_body', {})
            receipt_handle = event.get('receipt_handle')
            queue_url = event.get('queue_url')

            scoring_job_id = message_body.get('scoring_job_id')

            if not scoring_job_id or not receipt_handle or not queue_url:
                logging.error(f"❌ Missing required fields in fan-out event")
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'message': 'Invalid fan-out event format',
                        'processed': False
                    })
                }

            # Override the queue URL for this specific message
            processor.request_queue_url = queue_url

            # Get ScoringJob from DynamoDB
            scoring_job = await asyncio.to_thread(ScoringJob.get_by_id, scoring_job_id, processor.client)

            if not scoring_job:
                logging.error(f"❌ ScoringJob not found: {scoring_job_id}")
                return {
                    'statusCode': 404,
                    'body': json.dumps({
                        'message': f'ScoringJob not found: {scoring_job_id}',
                        'processed': False
                    })
                }

            # Claim the job
            await asyncio.to_thread(
                scoring_job.update,
                status='IN_PROGRESS',
                startedAt=datetime.now(timezone.utc).isoformat()
            )

            logging.info(f"✅ Claimed ScoringJob {scoring_job_id}")

            # Get external IDs
            scorecard = await asyncio.to_thread(Scorecard.get_by_id, scoring_job.scorecardId, processor.client)
            scorecard_external_id = scorecard.externalId if scorecard else None

            score = await asyncio.to_thread(Score.get_by_id, scoring_job.scoreId, processor.client)
            score_external_id = score.externalId if score else None

            job = {
                'scoring_job_id': scoring_job_id,
                'item_id': scoring_job.itemId,
                'scorecard_id': scorecard_external_id,
                'score_id': score_external_id,
                'receipt_handle': receipt_handle
            }

        else:
            # Manual invocation - poll for one message
            logging.info("📬 Manual invocation - polling SQS queue")
            job = await processor.poll_sqs_once()

            if not job:
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'No messages in queue',
                        'processed': False
                    })
                }

        # Process the job (common path for both invocation types)
        await processor.process_job(
            job['scoring_job_id'],
            job['item_id'],
            job['scorecard_id'],
            job['score_id'],
            job['receipt_handle']
        )

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Job processed successfully',
                'scoring_job_id': job['scoring_job_id'],
                'processed': True
            })
        }

    except Exception as e:
        logging.error(f"❌ Lambda execution failed: {e}")
        logging.error(traceback.format_exc())

        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Job processing failed',
                'error': str(e),
                'processed': False
            })
        }


def lambda_handler(event, context):
    """Lambda entry point - wraps async handler"""
    return asyncio.run(async_handler(event, context))
