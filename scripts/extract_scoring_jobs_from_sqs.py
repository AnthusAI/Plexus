#!/usr/bin/env python3
"""
Script to read SQS messages containing scoring job IDs and generate a CSV report.

This script:
1. Reads all messages from an SQS queue (without deleting them)
2. Extracts the scoring_job_id from each message
3. Queries the database to get the external_id, scorecard_id, and score_id for each scoring job (in parallel)
4. Generates a CSV with results (optionally deduplicated by any column)

Performance:
- Uses parallel processing (default: 20 workers) for database lookups
- On a powerful machine, can process hundreds of messages in seconds instead of minutes
- Adjust max_workers parameter based on your system capabilities

Usage:
    python scripts/extract_scoring_jobs_from_sqs.py <SQS_QUEUE_URL> [output_file.csv] [max_workers] [--dedupe COLUMN]

Examples:
    # Basic usage - all scoring jobs without deduplication (default)
    python scripts/extract_scoring_jobs_from_sqs.py https://sqs.us-east-1.amazonaws.com/123456789/my-queue
    
    # Specify output file
    python scripts/extract_scoring_jobs_from_sqs.py https://sqs.us-east-1.amazonaws.com/123456789/my-queue output.csv
    
    # Use 50 parallel workers for maximum speed on a powerful machine
    python scripts/extract_scoring_jobs_from_sqs.py https://sqs.us-east-1.amazonaws.com/123456789/my-queue output.csv 50
    
    # Deduplicate by external_id (one result per external_id)
    python scripts/extract_scoring_jobs_from_sqs.py https://sqs.us-east-1.amazonaws.com/123456789/my-queue output.csv 20 --dedupe external_id
"""

import os
import sys
import json
import csv
import boto3
from datetime import datetime
from typing import Dict, List, Set
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
except ImportError as e:
    logger.error(f"Failed to import Plexus modules: {e}")
    logger.error("Make sure you're running this from the Plexus project root")
    sys.exit(1)


class ScoringJobExtractor:
    """Extracts scoring job information from SQS queue and generates CSV report."""

    def __init__(self, queue_url: str, max_workers: int = 20, dedupe_column: str = None):
        """
        Initialize the extractor.

        Args:
            queue_url: The SQS queue URL to read messages from
            max_workers: Maximum number of parallel workers for database lookups
            dedupe_column: Column name to deduplicate on (None = no deduplication)
        """
        self.queue_url = queue_url
        self.max_workers = max_workers
        self.dedupe_column = dedupe_column
        self.sqs_client = boto3.client('sqs')
        self.dashboard_client = PlexusDashboardClient()

        # Storage for results
        self.results: List[Dict[str, str]] = []
        self.seen_values: Set[str] = set()  # Track seen values for deduplication
        self.results_lock = Lock()  # Thread-safe access to results

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

    def read_sqs_messages(self) -> List[Dict]:
        """
        Read all messages from the SQS queue without deleting them.

        Uses long polling to efficiently retrieve messages.

        Returns:
            List of message bodies as dictionaries
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

                # Parse message bodies
                for message in messages:
                    try:
                        body = json.loads(message['Body'])
                        all_messages.append(body)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse message body: {e}")
                        logger.error(f"Message body: {message.get('Body', 'N/A')}")

                # Note: We intentionally do NOT delete messages
                # They will become visible again after the visibility timeout

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

            # Extract external ID from itemId
            external_id = self.extract_external_id_from_item_id(scoring_job.itemId)

            result = {
                'scoring_job_id': scoring_job_id,
                'external_id': external_id,
                'scorecard_id': scoring_job.scorecardId,
                'score_id': scoring_job.scoreId or ''
            }

            logger.debug(f"Found: {result}")
            return result

        except Exception as e:
            logger.error(f"Error looking up scoring job {scoring_job_id}: {e}")
            return {
                'scoring_job_id': scoring_job_id,
                'external_id': 'ERROR',
                'scorecard_id': 'ERROR',
                'score_id': 'ERROR'
            }

    def process_single_message(self, message: Dict, message_num: int) -> Dict[str, str]:
        """
        Process a single message (for parallel execution).

        Args:
            message: Message body from SQS
            message_num: Message number for logging

        Returns:
            Result dictionary or None if message should be skipped
        """
        try:
            scoring_job_id = message.get('scoring_job_id')

            if not scoring_job_id:
                logger.warning(f"Message {message_num} missing 'scoring_job_id' field: {message}")
                return None

            # Look up the scoring job
            result = self.lookup_scoring_job(scoring_job_id)
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

    def write_csv(self, output_file: str) -> None:
        """
        Write results to a CSV file.

        Args:
            output_file: Path to the output CSV file
        """
        logger.info(f"Writing results to: {output_file}")

        try:
            with open(output_file, 'w', newline='') as csvfile:
                fieldnames = ['scoring_job_id', 'external_id', 'scorecard_id', 'score_id']
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
        logger.info("=" * 80)


def main():
    """Main entry point for the script."""
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python extract_scoring_jobs_from_sqs.py <SQS_QUEUE_URL> [output_file.csv] [max_workers] [--dedupe COLUMN]")
        print("")
        print("Arguments:")
        print("  SQS_QUEUE_URL   - The SQS queue URL to read from")
        print("  output_file.csv - (Optional) Output CSV filename")
        print("  max_workers     - (Optional) Number of parallel workers (default: 20)")
        print("  --dedupe COLUMN - (Optional) Deduplicate results by specified column")
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
        print("  # Deduplicate by score_id")
        print("  python extract_scoring_jobs_from_sqs.py \\")
        print("    https://sqs.us-east-1.amazonaws.com/123456789/my-queue \\")
        print("    my_output.csv \\")
        print("    20 \\")
        print("    --dedupe score_id")
        sys.exit(1)

    # Parse arguments
    queue_url = sys.argv[1]
    
    # Check for --dedupe flag and its argument
    dedupe_column = None
    filtered_argv = []
    i = 0
    while i < len(sys.argv):
        if sys.argv[i] == '--dedupe' and i + 1 < len(sys.argv):
            dedupe_column = sys.argv[i + 1]
            i += 2  # Skip both --dedupe and the column name
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

    # Validate environment variables
    required_env_vars = ['PLEXUS_API_URL', 'PLEXUS_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these before running the script.")
        sys.exit(1)

    # Run the extractor
    try:
        extractor = ScoringJobExtractor(queue_url, max_workers=max_workers, dedupe_column=dedupe_column)
        extractor.run(output_file)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
