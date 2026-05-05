#!/usr/bin/env python3
"""
Script to read SQS messages containing scoring job IDs and generate a CSV report.
Optionally delete messages that match a specific external ID.

This script:
1. Reads all messages from an SQS queue (without deleting them by default)
2. Extracts the scoring_job_id from each message
3. Queries the database to get the external_id, scorecard_id, and score_id for each scoring job (in parallel)
4. Generates a CSV with results (optionally deduplicated by any column)
5. Optionally deletes messages matching a specific external_id (with confirmation)

Performance:
- Uses parallel processing (default: 20 workers) for database lookups
- On a powerful machine, can process hundreds of messages in seconds instead of minutes
- Adjust max_workers parameter based on your system capabilities

Usage:
    python scripts/extract_scoring_jobs_from_sqs.py <SQS_QUEUE_URL> [output_file.csv] [max_workers] [--dedupe COLUMN] [--delete-by-external-id EXTERNAL_ID] [--dry-run]

Examples:
    # Basic usage - all scoring jobs without deduplication (default)
    python scripts/extract_scoring_jobs_from_sqs.py https://sqs.us-east-1.amazonaws.com/123456789/my-queue

    # Specify output file
    python scripts/extract_scoring_jobs_from_sqs.py https://sqs.us-east-1.amazonaws.com/123456789/my-queue output.csv

    # Use 50 parallel workers for maximum speed on a powerful machine
    python scripts/extract_scoring_jobs_from_sqs.py https://sqs.us-east-1.amazonaws.com/123456789/my-queue output.csv 50

    # Deduplicate by external_id (one result per external_id)
    python scripts/extract_scoring_jobs_from_sqs.py https://sqs.us-east-1.amazonaws.com/123456789/my-queue output.csv 20 --dedupe external_id

    # Dry-run: See what messages would be deleted without actually deleting
    python scripts/extract_scoring_jobs_from_sqs.py https://sqs.us-east-1.amazonaws.com/123456789/my-queue --delete-by-external-id 295667063 --dry-run

    # Delete messages matching external_id 295667063 (with confirmation prompt)
    python scripts/extract_scoring_jobs_from_sqs.py https://sqs.us-east-1.amazonaws.com/123456789/my-queue --delete-by-external-id 295667063
"""

import os
import sys
import json
import csv
import boto3
from datetime import datetime
from typing import Dict, List, Set, Optional, Tuple
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Plexus client
try:
    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.dashboard.api.models.scoring_job import ScoringJob
    from plexus.dashboard.api.models.score import Score
except ImportError as e:
    logger.error(f"Failed to import Plexus modules: {e}")
    logger.error("Make sure you're running this from the Plexus project root")
    sys.exit(1)


class ScoringJobExtractor:
    """Extracts scoring job information from SQS queue and generates CSV report."""

    def __init__(self, queue_url: str, max_workers: int = 20, dedupe_column: str = None,
                 delete_external_id: str = None, dry_run: bool = False,
                 source_queue_url: Optional[str] = None,
                 requeue_filter: str = 'none',
                 apply_requeue: bool = False):
        """
        Initialize the extractor.

        Args:
            queue_url: The SQS queue URL to read messages from
            max_workers: Maximum number of parallel workers for database lookups
            dedupe_column: Column name to deduplicate on (None = no deduplication)
            delete_external_id: External ID to match for deletion (None = no deletion)
            dry_run: If True, show what would be deleted without actually deleting
        """
        self.queue_url = queue_url
        self.max_workers = max_workers
        self.dedupe_column = dedupe_column
        self.delete_external_id = delete_external_id
        self.dry_run = dry_run
        self.source_queue_url = source_queue_url
        self.requeue_filter = requeue_filter
        self.apply_requeue = apply_requeue
        self.sqs_client = boto3.client('sqs')
        self.dashboard_client = PlexusDashboardClient()

        # Storage for results
        self.results: List[Dict[str, str]] = []
        self.seen_values: Set[str] = set()  # Track seen values for deduplication
        self.results_lock = Lock()  # Thread-safe access to results

        # Storage for messages to delete
        self.messages_to_delete: List[Dict] = []
        self.messages_to_delete_lock = Lock()  # Thread-safe access to deletion list
        self.messages_to_requeue: List[Dict] = []
        self.messages_to_requeue_lock = Lock()  # Thread-safe access to requeue list
        self.score_cache: Dict[str, Dict[str, str]] = {}
        self.score_cache_lock = Lock()

    def get_score_details(self, score_id: str) -> Dict[str, str]:
        """Get score provider/model/name with a simple thread-safe cache."""
        if not score_id:
            return {
                'score_provider': '',
                'score_model': '',
                'score_name': ''
            }

        with self.score_cache_lock:
            cached = self.score_cache.get(score_id)
        if cached is not None:
            return cached

        details = {
            'score_provider': 'LOOKUP_ERROR',
            'score_model': '',
            'score_name': ''
        }
        try:
            score = Score.get_by_id(score_id, self.dashboard_client)
            details = {
                'score_provider': score.aiProvider or 'unknown',
                'score_model': score.aiModel or 'unknown',
                'score_name': score.name or ''
            }
        except Exception as e:
            logger.warning(f"Failed to lookup score details for score_id={score_id}: {e}")

        with self.score_cache_lock:
            self.score_cache[score_id] = details

        return details

    def categorize_result(self, result: Dict[str, str]) -> str:
        """Categorize each message result for DLQ triage."""
        status = (result.get('scoring_job_status') or '').upper()
        provider = (result.get('score_provider') or '').lower()
        error = (result.get('scoring_job_error_message') or '').lower()

        if status == 'LOOKUP_ERROR':
            return 'lookup_error'
        if status == 'COMPLETED':
            return 'completed_stale'
        if status == 'FAILED':
            if 'invalidclienttokenid' in error:
                return 'failed_invalid_token_reprocessable'
            if 'converse operation: operation not allowed' in error or 'validationexception' in error:
                return 'failed_bedrock_converse_issue'
            return 'failed_other_issue'
        if status in ('PENDING', 'RUNNING', 'IN_PROGRESS'):
            if 'bedrock' in provider:
                return 'inflight_bedrock'
            if provider in ('unknown', 'lookup_error', ''):
                return 'inflight_unknown_provider'
            return 'inflight_non_bedrock'
        return f"status_{status.lower()}" if status else 'status_unknown'

    def should_requeue_result(self, result: Dict[str, str]) -> bool:
        """Determine whether a message should be requeued under selected filter."""
        if self.requeue_filter == 'none':
            return False

        category = result.get('dlq_category', '')
        provider = (result.get('score_provider') or '').lower()

        if self.requeue_filter == 'all':
            return True
        if self.requeue_filter == 'chatopenai':
            return provider == 'chatopenai'
        if self.requeue_filter == 'non-bedrock':
            if provider in ('', 'unknown', 'lookup_error'):
                return False
            return 'bedrock' not in provider
        if self.requeue_filter == 'retryable':
            return category in {
                'completed_stale',
                'failed_invalid_token_reprocessable',
                'inflight_non_bedrock'
            }

        return False

    def extract_external_id_from_item_id(self, item_id: str) -> str:
        """
        Extract external ID from the item ID.

        The external ID is everything after the last '-' in the item ID.

        Args:
            item_id: The full item ID (e.g., "account-scorecard-123456")

        Returns:
            The external ID (e.g., "123456")
        """
        if not item_id:
            return ""

        parts = item_id.split('-')
        if len(parts) > 0:
            return parts[-1]
        return ""

    def read_sqs_messages(self) -> List[tuple]:
        """
        Read all messages from the SQS queue without deleting them.

        Uses long polling to efficiently retrieve messages.

        Returns:
            List of tuples (message_object, parsed_body) where message_object contains
            ReceiptHandle needed for deletion
        """
        logger.info(f"Reading messages from SQS queue: {self.queue_url}")

        all_messages = []
        messages_received = 0
        empty_receives = 0
        max_empty_receives = 3  # Stop after 3 consecutive empty receives

        while empty_receives < max_empty_receives:
            try:
                # Receive messages (up to 10 at a time)
                response = self.sqs_client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=10,  # Max allowed by SQS
                    WaitTimeSeconds=1,  # Shorter wait time for faster iteration
                    AttributeNames=['All']
                )

                messages = response.get('Messages', [])

                if not messages:
                    empty_receives += 1
                    logger.debug(f"Empty receive {empty_receives}/{max_empty_receives}")
                    continue

                # Reset empty counter when we get messages
                empty_receives = 0

                messages_received += len(messages)
                logger.info(f"Received {len(messages)} messages (total: {messages_received})")

                # Parse message bodies and store with full message object
                for message in messages:
                    try:
                        body = json.loads(message['Body'])
                        all_messages.append((message, body))
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse message body: {e}")
                        logger.error(f"Message body: {message.get('Body', 'N/A')}")

                # Note: We intentionally do NOT delete messages here
                # They will become visible again after the visibility timeout
                # Deletion happens later if --delete-by-external-id is specified

            except Exception as e:
                logger.error(f"Error reading from SQS: {e}")
                break

        logger.info(f"Total messages read: {len(all_messages)}")
        return all_messages

    def lookup_scoring_job(self, scoring_job_id: str) -> Dict[str, str]:
        """
        Look up scoring job details from the database.

        Args:
            scoring_job_id: The scoring job ID to look up

        Returns:
            Dictionary with scoring_job_id, external_id, scorecard_id, and score_id
        """
        try:
            logger.debug(f"Looking up scoring job: {scoring_job_id}")

            # Get the scoring job
            scoring_job = ScoringJob.get_by_id(scoring_job_id, self.dashboard_client)
            score_details = self.get_score_details(scoring_job.scoreId or '')

            # Extract external ID from itemId
            external_id = self.extract_external_id_from_item_id(scoring_job.itemId)

            result = {
                'scoring_job_id': scoring_job_id,
                'external_id': external_id,
                'scorecard_id': scoring_job.scorecardId,
                'score_id': scoring_job.scoreId or '',
                'scoring_job_status': scoring_job.status or '',
                'scoring_job_error_message': scoring_job.errorMessage or '',
                'score_provider': score_details.get('score_provider', ''),
                'score_model': score_details.get('score_model', ''),
                'score_name': score_details.get('score_name', '')
            }
            result['dlq_category'] = self.categorize_result(result)

            logger.debug(f"Found: {result}")
            return result

        except Exception as e:
            logger.error(f"Error looking up scoring job {scoring_job_id}: {e}")
            return {
                'scoring_job_id': scoring_job_id,
                'external_id': 'ERROR',
                'scorecard_id': 'ERROR',
                'score_id': 'ERROR',
                'scoring_job_status': 'LOOKUP_ERROR',
                'scoring_job_error_message': str(e),
                'score_provider': 'LOOKUP_ERROR',
                'score_model': '',
                'score_name': '',
                'dlq_category': 'lookup_error'
            }

    def should_delete_message(self, external_id: str) -> bool:
        """
        Check if a message should be deleted based on external ID.

        Args:
            external_id: The external ID extracted from the scoring job

        Returns:
            True if the message matches the deletion criteria, False otherwise
        """
        if not self.delete_external_id:
            return False
        return external_id == self.delete_external_id

    def confirm_deletion(self) -> bool:
        """
        Prompt user to confirm deletion of messages.

        Shows the count of messages to delete and a sample of the first 5.

        Returns:
            True if user confirms deletion, False otherwise
        """
        count = len(self.messages_to_delete)
        if count == 0:
            return False

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"DELETION CONFIRMATION")
        logger.info("=" * 80)
        logger.info(f"Found {count} message(s) matching external_id: {self.delete_external_id}")
        logger.info("")
        logger.info("The following messages will be deleted:")

        # Show first 5 messages as sample
        sample_size = min(5, count)
        for msg_data in self.messages_to_delete[:sample_size]:
            result = msg_data['result']
            logger.info(f"  - scoring_job_id={result['scoring_job_id']}, external_id={result['external_id']}")

        if count > sample_size:
            logger.info(f"  ... and {count - sample_size} more")

        logger.info("")
        try:
            response = input(f"Delete {count} message(s)? (yes/no): ").strip().lower()
            return response in ['yes', 'y']
        except (EOFError, KeyboardInterrupt):
            logger.info("\nDeletion cancelled by user")
            return False

    def delete_messages_batch(self) -> Dict[str, int]:
        """
        Delete messages in batches using SQS batch delete API.

        Returns:
            Dictionary with 'success' and 'failed' counts
        """
        total = len(self.messages_to_delete)
        success_count = 0
        failed_count = 0

        logger.info("")
        logger.info("Deleting messages...")

        # Process in batches of 10 (SQS limit)
        for i in range(0, total, 10):
            batch = self.messages_to_delete[i:i + 10]

            # Prepare batch delete entries
            entries = []
            for j, msg_data in enumerate(batch):
                entries.append({
                    'Id': str(i + j),
                    'ReceiptHandle': msg_data['message']['ReceiptHandle']
                })

            try:
                response = self.sqs_client.delete_message_batch(
                    QueueUrl=self.queue_url,
                    Entries=entries
                )

                # Count successes
                successful = response.get('Successful', [])
                success_count += len(successful)

                # Log failures
                failed = response.get('Failed', [])
                failed_count += len(failed)

                for failure in failed:
                    idx = int(failure['Id'])
                    msg_data = self.messages_to_delete[idx]
                    result = msg_data['result']
                    logger.error(f"Failed to delete message: scoring_job_id={result['scoring_job_id']}, "
                               f"external_id={result['external_id']}, "
                               f"reason={failure.get('Message', 'Unknown')}")

            except Exception as e:
                logger.error(f"Error deleting batch: {e}")
                failed_count += len(batch)

        logger.info(f"Successfully deleted: {success_count}")
        if failed_count > 0:
            logger.error(f"Failed to delete: {failed_count}")

        return {
            'success': success_count,
            'failed': failed_count
        }

    def process_single_message(self, message_tuple: tuple, message_num: int) -> Dict[str, str]:
        """
        Process a single message (for parallel execution).

        Args:
            message_tuple: Tuple of (message_object, message_body) from SQS
            message_num: Message number for logging

        Returns:
            Result dictionary or None if message should be skipped
        """
        try:
            message_obj, message_body = message_tuple
            scoring_job_id = message_body.get('scoring_job_id')

            if not scoring_job_id:
                logger.warning(f"Message {message_num} missing 'scoring_job_id' field: {message_body}")
                return None

            # Look up the scoring job
            result = self.lookup_scoring_job(scoring_job_id)

            # Check if this message should be marked for deletion
            if result and self.should_delete_message(result['external_id']):
                with self.messages_to_delete_lock:
                    self.messages_to_delete.append({
                        'message': message_obj,
                        'result': result
                    })
                    logger.debug(f"Marked for deletion: scoring_job_id={result['scoring_job_id']}, "
                               f"external_id={result['external_id']}")

            # Check if this message should be marked for requeue
            if result and self.should_requeue_result(result):
                with self.messages_to_requeue_lock:
                    self.messages_to_requeue.append({
                        'message': message_obj,
                        'result': result
                    })

            return result

        except Exception as e:
            logger.error(f"Error processing message {message_num}: {e}")
            return None

    def process_messages(self, messages: List[Dict]) -> None:
        """
        Process all messages in parallel and build results list.

        Args:
            messages: List of message bodies from SQS
        """
        if self.dedupe_column:
            dedup_status = f"with deduplication on '{self.dedupe_column}'"
        else:
            dedup_status = "without deduplication"
        logger.info(f"Processing {len(messages)} messages with {self.max_workers} parallel workers ({dedup_status})...")

        completed = 0
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_message = {
                executor.submit(self.process_single_message, msg, i): i 
                for i, msg in enumerate(messages, 1)
            }

            # Process completed tasks
            for future in as_completed(future_to_message):
                completed += 1
                
                try:
                    result = future.result()
                    
                    if result is None:
                        continue

                    # Thread-safe check and add
                    with self.results_lock:
                        if self.dedupe_column:
                            # Only add if we haven't seen this value in the dedupe column
                            dedupe_value = result.get(self.dedupe_column, '')
                            if dedupe_value not in self.seen_values:
                                self.results.append(result)
                                self.seen_values.add(dedupe_value)
                            else:
                                logger.debug(f"Skipping duplicate {self.dedupe_column}: {dedupe_value}")
                        else:
                            # Add all results without deduplication
                            self.results.append(result)

                    # Progress logging
                    if completed % 50 == 0:
                        with self.results_lock:
                            result_label = f"unique by {self.dedupe_column}" if self.dedupe_column else "results"
                            logger.info(f"Processed {completed}/{len(messages)} messages, {len(self.results)} {result_label}")

                except Exception as e:
                    logger.error(f"Error getting result from future: {e}")

        result_label = f"unique by {self.dedupe_column}" if self.dedupe_column else "results"
        logger.info(f"Completed processing. Found {len(self.results)} {result_label}")

        # Log deletion statistics if deletion is enabled
        if self.delete_external_id:
            logger.info(f"Messages marked for deletion: {len(self.messages_to_delete)}")
        if self.requeue_filter != 'none':
            logger.info(f"Messages marked for requeue ({self.requeue_filter}): {len(self.messages_to_requeue)}")

    def summarize_categories(self) -> None:
        """Print category and provider summary for quick DLQ triage."""
        category_counts: Dict[str, int] = {}
        provider_counts: Dict[str, int] = {}

        for row in self.results:
            category = row.get('dlq_category', 'unknown')
            provider = row.get('score_provider', 'unknown')
            category_counts[category] = category_counts.get(category, 0) + 1
            provider_counts[provider] = provider_counts.get(provider, 0) + 1

        logger.info("")
        logger.info("DLQ Category Summary:")
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {category}: {count}")

        logger.info("")
        logger.info("Provider Summary:")
        for provider, count in sorted(provider_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {provider}: {count}")

    def requeue_messages_batch(self) -> Dict[str, int]:
        """
        Requeue selected messages to the source queue and delete them from DLQ.
        Deletes only messages successfully re-sent.
        """
        if not self.source_queue_url:
            raise ValueError("source_queue_url is required for requeue mode")

        total = len(self.messages_to_requeue)
        sent_count = 0
        send_failed = 0
        deleted_count = 0
        delete_failed = 0
        successfully_sent_messages: List[Dict] = []

        logger.info("")
        logger.info(f"Requeueing {total} message(s) to source queue: {self.source_queue_url}")

        # Step 1: Send selected messages to source queue in batches
        for i in range(0, total, 10):
            batch = self.messages_to_requeue[i:i + 10]
            entries = []
            for j, msg_data in enumerate(batch):
                entries.append({
                    'Id': str(j),
                    'MessageBody': msg_data['message']['Body']
                })

            try:
                response = self.sqs_client.send_message_batch(
                    QueueUrl=self.source_queue_url,
                    Entries=entries
                )
                successful = {entry['Id'] for entry in response.get('Successful', [])}
                failed = response.get('Failed', [])

                sent_count += len(successful)
                send_failed += len(failed)

                for j, msg_data in enumerate(batch):
                    if str(j) in successful:
                        successfully_sent_messages.append(msg_data)

                for failure in failed:
                    logger.error(f"Failed to send message to source queue: {failure.get('Message', 'Unknown')}")
            except Exception as e:
                logger.error(f"Error sending requeue batch: {e}")
                send_failed += len(batch)

        # Step 2: Delete only successfully re-sent messages from DLQ
        for i in range(0, len(successfully_sent_messages), 10):
            batch = successfully_sent_messages[i:i + 10]
            entries = []
            for j, msg_data in enumerate(batch):
                entries.append({
                    'Id': str(j),
                    'ReceiptHandle': msg_data['message']['ReceiptHandle']
                })

            try:
                response = self.sqs_client.delete_message_batch(
                    QueueUrl=self.queue_url,
                    Entries=entries
                )
                deleted_count += len(response.get('Successful', []))
                failed = response.get('Failed', [])
                delete_failed += len(failed)
                for failure in failed:
                    logger.error(f"Failed to delete DLQ message after successful resend: {failure.get('Message', 'Unknown')}")
            except Exception as e:
                logger.error(f"Error deleting requeued DLQ batch: {e}")
                delete_failed += len(batch)

        logger.info(f"Requeue send successful: {sent_count}")
        logger.info(f"Requeue send failed: {send_failed}")
        logger.info(f"DLQ delete successful: {deleted_count}")
        logger.info(f"DLQ delete failed: {delete_failed}")

        return {
            'sent_success': sent_count,
            'sent_failed': send_failed,
            'deleted_success': deleted_count,
            'deleted_failed': delete_failed,
        }

    def write_csv(self, output_file: str) -> None:
        """
        Write results to a CSV file.

        Args:
            output_file: Path to the output CSV file
        """
        logger.info(f"Writing results to: {output_file}")

        try:
            with open(output_file, 'w', newline='') as csvfile:
                fieldnames = [
                    'scoring_job_id',
                    'external_id',
                    'scorecard_id',
                    'score_id',
                    'scoring_job_status',
                    'score_provider',
                    'score_model',
                    'score_name',
                    'dlq_category',
                    'scoring_job_error_message',
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                writer.writerows(self.results)

            logger.info(f"Successfully wrote {len(self.results)} rows to {output_file}")

        except Exception as e:
            logger.error(f"Error writing CSV file: {e}")
            raise

    def run(self, output_file: str = None) -> None:
        """
        Run the complete extraction process.

        Args:
            output_file: Path to output CSV file (defaults to timestamped filename)
        """
        # Generate default output filename if not provided
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'scoring_jobs_{timestamp}.csv'

        logger.info("=" * 80)
        logger.info("SQS Scoring Job Extractor")
        logger.info("=" * 80)
        logger.info(f"Queue URL: {self.queue_url}")
        logger.info(f"Output file: {output_file}")
        logger.info(f"Parallel workers: {self.max_workers}")
        if self.dedupe_column:
            logger.info(f"Deduplication: enabled (column: {self.dedupe_column})")
        else:
            logger.info(f"Deduplication: disabled")
        if self.delete_external_id:
            logger.info(f"Deletion mode: enabled (external_id: {self.delete_external_id})")
            if self.dry_run:
                logger.info(f"Dry-run: enabled (no messages will be deleted)")
            else:
                logger.info(f"Dry-run: disabled (messages will be deleted after confirmation)")
        else:
            logger.info(f"Deletion mode: disabled")
        if self.requeue_filter != 'none':
            logger.info(f"Requeue mode: enabled (filter: {self.requeue_filter})")
            logger.info(f"Source queue: {self.source_queue_url or 'NOT SET'}")
            logger.info(f"Apply requeue: {'yes' if self.apply_requeue else 'no (analysis only)'}")
        else:
            logger.info("Requeue mode: disabled")
        logger.info("")

        # Step 1: Read messages from SQS
        messages = self.read_sqs_messages()

        if not messages:
            logger.warning("No messages found in queue. Exiting.")
            return

        # Step 2: Process messages and look up scoring jobs
        self.process_messages(messages)

        if not self.results:
            logger.warning("No valid results to write. Exiting.")
            return

        # Step 3: Write CSV
        self.write_csv(output_file)
        self.summarize_categories()

        # Step 4: Handle deletion if enabled
        deletion_stats = None
        if self.delete_external_id and len(self.messages_to_delete) > 0:
            if self.dry_run:
                # Dry run mode - show what would be deleted
                logger.info("")
                logger.info("=" * 80)
                logger.info("DRY RUN MODE")
                logger.info("=" * 80)
                logger.info(f"Would delete {len(self.messages_to_delete)} message(s) matching external_id: {self.delete_external_id}")
                logger.info("")
                logger.info("Sample messages that would be deleted:")
                sample_size = min(5, len(self.messages_to_delete))
                for msg_data in self.messages_to_delete[:sample_size]:
                    result = msg_data['result']
                    logger.info(f"  - scoring_job_id={result['scoring_job_id']}, external_id={result['external_id']}")
                if len(self.messages_to_delete) > sample_size:
                    logger.info(f"  ... and {len(self.messages_to_delete) - sample_size} more")
                logger.info("")
                logger.info("No messages were deleted (dry-run mode).")
                logger.info("=" * 80)
            else:
                # Real deletion - confirm and delete
                if self.confirm_deletion():
                    deletion_stats = self.delete_messages_batch()
                else:
                    logger.info("Deletion cancelled by user.")

        # Step 5: Handle requeue if enabled
        requeue_stats = None
        if self.requeue_filter != 'none' and len(self.messages_to_requeue) > 0:
            if not self.apply_requeue:
                logger.info("")
                logger.info("=" * 80)
                logger.info("REQUEUE ANALYSIS MODE")
                logger.info("=" * 80)
                logger.info(f"Would requeue {len(self.messages_to_requeue)} message(s) with filter={self.requeue_filter}")
                logger.info("No messages were sent/deleted (set --apply-requeue to execute).")
                logger.info("=" * 80)
            elif self.dry_run:
                logger.info("")
                logger.info("=" * 80)
                logger.info("DRY RUN MODE")
                logger.info("=" * 80)
                logger.info(f"Would requeue {len(self.messages_to_requeue)} message(s) with filter={self.requeue_filter}")
                logger.info("No messages were sent/deleted (dry-run mode).")
                logger.info("=" * 80)
            else:
                requeue_stats = self.requeue_messages_batch()

        logger.info("")
        logger.info("=" * 80)
        logger.info("Summary:")
        logger.info(f"  Messages read: {len(messages)}")
        if self.dedupe_column:
            result_label = f"Unique results (by {self.dedupe_column})"
        else:
            result_label = "Total results"
        logger.info(f"  {result_label}: {len(self.results)}")
        logger.info(f"  Output file: {output_file}")
        if self.delete_external_id:
            logger.info(f"  Deletion target: external_id={self.delete_external_id}")
            logger.info(f"  Messages matched for deletion: {len(self.messages_to_delete)}")
            if deletion_stats:
                logger.info(f"  Successfully deleted: {deletion_stats['success']}")
                if deletion_stats['failed'] > 0:
                    logger.info(f"  Failed to delete: {deletion_stats['failed']}")
            elif self.dry_run:
                logger.info(f"  Deletion status: DRY RUN (no messages deleted)")
            else:
                logger.info(f"  Deletion status: Cancelled or no matches")
        if self.requeue_filter != 'none':
            logger.info(f"  Requeue filter: {self.requeue_filter}")
            logger.info(f"  Messages matched for requeue: {len(self.messages_to_requeue)}")
            if requeue_stats:
                logger.info(f"  Requeue sent successfully: {requeue_stats['sent_success']}")
                logger.info(f"  Requeue send failures: {requeue_stats['sent_failed']}")
                logger.info(f"  DLQ deletes after requeue: {requeue_stats['deleted_success']}")
                if requeue_stats['deleted_failed'] > 0:
                    logger.info(f"  DLQ delete failures: {requeue_stats['deleted_failed']}")
            elif self.apply_requeue and self.dry_run:
                logger.info("  Requeue status: DRY RUN (no messages sent/deleted)")
            elif not self.apply_requeue:
                logger.info("  Requeue status: Analysis-only (set --apply-requeue to execute)")
        logger.info("=" * 80)


def main():
    """Main entry point for the script."""
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python extract_scoring_jobs_from_sqs.py <SQS_QUEUE_URL> [output_file.csv] [max_workers] [--dedupe COLUMN] [--delete-by-external-id EXTERNAL_ID] [--dry-run] [--source-queue-url URL] [--requeue-filter FILTER] [--apply-requeue]")
        print("")
        print("Arguments:")
        print("  SQS_QUEUE_URL              - The SQS queue URL to read from")
        print("  output_file.csv            - (Optional) Output CSV filename")
        print("  max_workers                - (Optional) Number of parallel workers (default: 20)")
        print("  --dedupe COLUMN            - (Optional) Deduplicate results by specified column")
        print("  --delete-by-external-id ID - (Optional) Delete messages matching this external_id")
        print("  --dry-run                  - (Optional) Show what would be deleted without deleting")
        print("  --source-queue-url URL     - (Optional) Source queue URL for requeue mode")
        print("  --requeue-filter FILTER    - (Optional) Requeue selector: none|chatopenai|non-bedrock|retryable|all")
        print("  --apply-requeue            - (Optional) Actually send selected messages to source queue and delete from DLQ")
        print("")
        print("Available columns for deduplication:")
        print("  - scoring_job_id")
        print("  - external_id")
        print("  - scorecard_id")
        print("  - score_id")
        print("")
        print("Examples:")
        print("  # Basic usage without deduplication (all scoring jobs)")
        print("  python extract_scoring_jobs_from_sqs.py \\")
        print("    https://sqs.us-east-1.amazonaws.com/123456789/my-queue")
        print("")
        print("  # With custom output file")
        print("  python extract_scoring_jobs_from_sqs.py \\")
        print("    https://sqs.us-east-1.amazonaws.com/123456789/my-queue \\")
        print("    my_output.csv")
        print("")
        print("  # With 50 workers for maximum speed")
        print("  python extract_scoring_jobs_from_sqs.py \\")
        print("    https://sqs.us-east-1.amazonaws.com/123456789/my-queue \\")
        print("    my_output.csv \\")
        print("    50")
        print("")
        print("  # Deduplicate by external_id (one result per external_id)")
        print("  python extract_scoring_jobs_from_sqs.py \\")
        print("    https://sqs.us-east-1.amazonaws.com/123456789/my-queue \\")
        print("    my_output.csv \\")
        print("    20 \\")
        print("    --dedupe external_id")
        print("")
        print("  # Dry-run: See what would be deleted")
        print("  python extract_scoring_jobs_from_sqs.py \\")
        print("    https://sqs.us-east-1.amazonaws.com/123456789/my-queue \\")
        print("    --delete-by-external-id 295667063 \\")
        print("    --dry-run")
        print("")
        print("  # Delete messages matching external_id 295667063")
        print("  python extract_scoring_jobs_from_sqs.py \\")
        print("    https://sqs.us-east-1.amazonaws.com/123456789/my-queue \\")
        print("    --delete-by-external-id 295667063")
        sys.exit(1)

    # Parse arguments
    queue_url = sys.argv[1]

    # Check for optional flags
    dedupe_column = None
    delete_external_id = None
    dry_run = False
    source_queue_url = None
    requeue_filter = 'none'
    apply_requeue = False
    filtered_argv = []
    i = 0
    while i < len(sys.argv):
        if sys.argv[i] == '--dedupe' and i + 1 < len(sys.argv):
            dedupe_column = sys.argv[i + 1]
            i += 2  # Skip both --dedupe and the column name
        elif sys.argv[i] == '--delete-by-external-id' and i + 1 < len(sys.argv):
            delete_external_id = sys.argv[i + 1]
            i += 2  # Skip both --delete-by-external-id and the external_id value
        elif sys.argv[i] == '--dry-run':
            dry_run = True
            i += 1
        elif sys.argv[i] == '--source-queue-url' and i + 1 < len(sys.argv):
            source_queue_url = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--requeue-filter' and i + 1 < len(sys.argv):
            requeue_filter = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--apply-requeue':
            apply_requeue = True
            i += 1
        else:
            filtered_argv.append(sys.argv[i])
            i += 1

    output_file = filtered_argv[2] if len(filtered_argv) > 2 else None
    max_workers = int(filtered_argv[3]) if len(filtered_argv) > 3 else 20

    # Validate dedupe_column if provided
    valid_columns = ['scoring_job_id', 'external_id', 'scorecard_id', 'score_id']
    if dedupe_column and dedupe_column not in valid_columns:
        logger.error(f"Invalid dedupe column: {dedupe_column}")
        logger.error(f"Valid columns are: {', '.join(valid_columns)}")
        sys.exit(1)

    # Validate dry_run is only used with delete_external_id
    if dry_run and not delete_external_id:
        if not (requeue_filter != 'none' and apply_requeue):
            logger.error("--dry-run can only be used with --delete-by-external-id or --apply-requeue")
            sys.exit(1)

    valid_requeue_filters = {'none', 'chatopenai', 'non-bedrock', 'retryable', 'all'}
    if requeue_filter not in valid_requeue_filters:
        logger.error(f"Invalid requeue filter: {requeue_filter}")
        logger.error(f"Valid filters are: {', '.join(sorted(valid_requeue_filters))}")
        sys.exit(1)

    if apply_requeue and requeue_filter == 'none':
        logger.error("--apply-requeue requires --requeue-filter to be set")
        sys.exit(1)

    if requeue_filter != 'none' and not source_queue_url:
        logger.error("--source-queue-url is required when using --requeue-filter")
        sys.exit(1)

    if delete_external_id and requeue_filter != 'none':
        logger.error("Combining --delete-by-external-id with requeue mode is not supported in one run")
        sys.exit(1)

    # Validate environment variables
    required_env_vars = ['PLEXUS_API_URL', 'PLEXUS_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these before running the script.")
        sys.exit(1)

    # Run the extractor
    try:
        extractor = ScoringJobExtractor(
            queue_url,
            max_workers=max_workers,
            dedupe_column=dedupe_column,
            delete_external_id=delete_external_id,
            dry_run=dry_run,
            source_queue_url=source_queue_url,
            requeue_filter=requeue_filter,
            apply_requeue=apply_requeue,
        )
        extractor.run(output_file)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
