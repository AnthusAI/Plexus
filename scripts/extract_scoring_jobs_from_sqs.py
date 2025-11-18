#!/usr/bin/env python3
"""
Script to read SQS messages containing scoring job IDs and generate a CSV report.

This script:
1. Reads all messages from an SQS queue (without deleting them)
2. Extracts the scoring_job_id from each message
3. Queries the database to get the report_id and scorecard_id for each scoring job
4. Generates a CSV with deduplicated results based on report_id

Usage:
    python scripts/extract_scoring_jobs_from_sqs.py <SQS_QUEUE_URL>

Example:
    python scripts/extract_scoring_jobs_from_sqs.py https://sqs.us-east-1.amazonaws.com/123456789/my-queue
"""

import os
import sys
import json
import csv
import boto3
from datetime import datetime
from typing import Dict, List, Set
import logging

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

    def __init__(self, queue_url: str):
        """
        Initialize the extractor.

        Args:
            queue_url: The SQS queue URL to read messages from
        """
        self.queue_url = queue_url
        self.sqs_client = boto3.client('sqs')
        self.dashboard_client = PlexusDashboardClient()

        # Storage for results
        self.results: List[Dict[str, str]] = []
        self.seen_report_ids: Set[str] = set()

    def extract_report_id_from_item_id(self, item_id: str) -> str:
        """
        Extract report ID from the item ID.

        The report ID is everything after the last '-' in the item ID.

        Args:
            item_id: The full item ID (e.g., "account-scorecard-123456")

        Returns:
            The report ID (e.g., "123456")
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

        while True:
            try:
                # Receive messages (up to 10 at a time)
                response = self.sqs_client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=10,  # Max allowed by SQS
                    WaitTimeSeconds=5,  # Short poll since we're iterating
                    AttributeNames=['All']
                )

                messages = response.get('Messages', [])

                if not messages:
                    # No more messages available
                    logger.info("No more messages in queue")
                    break

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
            Dictionary with scoring_job_id, report_id, and scorecard_id
        """
        try:
            logger.debug(f"Looking up scoring job: {scoring_job_id}")

            # Get the scoring job
            scoring_job = ScoringJob.get_by_id(scoring_job_id, self.dashboard_client)

            # Extract report ID from itemId
            report_id = self.extract_report_id_from_item_id(scoring_job.itemId)

            result = {
                'scoring_job_id': scoring_job_id,
                'report_id': report_id,
                'scorecard_id': scoring_job.scorecardId
            }

            logger.debug(f"Found: {result}")
            return result

        except Exception as e:
            logger.error(f"Error looking up scoring job {scoring_job_id}: {e}")
            return {
                'scoring_job_id': scoring_job_id,
                'report_id': 'ERROR',
                'scorecard_id': 'ERROR'
            }

    def process_messages(self, messages: List[Dict]) -> None:
        """
        Process all messages and build results list.

        Args:
            messages: List of message bodies from SQS
        """
        logger.info(f"Processing {len(messages)} messages...")

        for i, message in enumerate(messages, 1):
            try:
                scoring_job_id = message.get('scoring_job_id')

                if not scoring_job_id:
                    logger.warning(f"Message {i} missing 'scoring_job_id' field: {message}")
                    continue

                # Look up the scoring job
                result = self.lookup_scoring_job(scoring_job_id)

                # Check if we've already seen this report_id
                report_id = result['report_id']

                if report_id in self.seen_report_ids:
                    logger.debug(f"Skipping duplicate report_id: {report_id}")
                    continue

                # Add to results
                self.results.append(result)
                self.seen_report_ids.add(report_id)

                if i % 10 == 0:
                    logger.info(f"Processed {i}/{len(messages)} messages, {len(self.results)} unique reports")

            except Exception as e:
                logger.error(f"Error processing message {i}: {e}")
                continue

        logger.info(f"Completed processing. Found {len(self.results)} unique reports")

    def write_csv(self, output_file: str) -> None:
        """
        Write results to a CSV file.

        Args:
            output_file: Path to the output CSV file
        """
        logger.info(f"Writing results to: {output_file}")

        try:
            with open(output_file, 'w', newline='') as csvfile:
                fieldnames = ['scoring_job_id', 'report_id', 'scorecard_id']
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
        logger.info(f"  Unique reports: {len(self.results)}")
        logger.info(f"  Output file: {output_file}")
        logger.info("=" * 80)


def main():
    """Main entry point for the script."""
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python extract_scoring_jobs_from_sqs.py <SQS_QUEUE_URL> [output_file.csv]")
        print("")
        print("Example:")
        print("  python extract_scoring_jobs_from_sqs.py \\")
        print("    https://sqs.us-east-1.amazonaws.com/123456789/my-queue")
        print("")
        print("  python extract_scoring_jobs_from_sqs.py \\")
        print("    https://sqs.us-east-1.amazonaws.com/123456789/my-queue \\")
        print("    my_output.csv")
        sys.exit(1)

    queue_url = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    # Validate environment variables
    required_env_vars = ['PLEXUS_API_URL', 'PLEXUS_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these before running the script.")
        sys.exit(1)

    # Run the extractor
    try:
        extractor = ScoringJobExtractor(queue_url)
        extractor.run(output_file)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
