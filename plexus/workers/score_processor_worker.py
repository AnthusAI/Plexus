#!/usr/bin/env python3
"""
Score Processor Worker for Kubernetes

This module provides a long-running worker that continuously polls SQS for
scoring jobs and processes them. It's designed to run in Kubernetes pods.

Unlike the Lambda handler which is event-driven, this worker:
- Runs continuously in a loop
- Polls SQS with long polling (WaitTimeSeconds)
- Handles graceful shutdown signals
- Logs structured output for container environments

Usage:
    python -m plexus.workers.score_processor_worker

Environment Variables:
    PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL: SQS queue URL
    PLEXUS_RESPONSE_WORKER_QUEUE_URL: Response queue URL
    PLEXUS_ACCOUNT_KEY: Plexus account key
    PLEXUS_API_URL: Dashboard API URL (optional)
    PLEXUS_API_KEY: Dashboard API key (optional)
    LOG_LEVEL: Logging level (default: INFO)
    MAX_JOBS_PER_WORKER: Max jobs before restart (default: None/unlimited)
    ERROR_RETRY_DELAY: Seconds to wait after error (default: 5)
"""

import asyncio
import os
import signal
import sys
import logging
from typing import Optional

# Import the existing JobProcessor from ProcessScoreWorker
from plexus.workers.ProcessScoreWorker import JobProcessor


def configure_logging():
    """Configure structured logging for container environments"""
    log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

    # Reduce noise from boto/urllib
    for noisy_logger in ("urllib3", "botocore", "boto3", "gql.transport", "gql.dsl"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    return logging.getLogger(__name__)


class WorkerShutdownHandler:
    """Handle graceful shutdown signals"""

    def __init__(self):
        self.shutdown_requested = False
        self.loop = None

    def setup(self, loop: asyncio.AbstractEventLoop):
        """Setup signal handlers"""
        self.loop = loop
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        if not self.shutdown_requested:
            logger.info(f"📥 Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_requested = True
            if self.loop:
                self.loop.stop()


async def run_worker(
    once: bool = False,
    max_jobs: Optional[int] = None,
    error_retry_delay: int = 5
):
    """
    Run the score processor worker continuously

    Args:
        once: If True, process one job and exit (for testing)
        max_jobs: Maximum number of jobs to process before exiting
        error_retry_delay: Seconds to wait after errors before retrying
    """
    logger.info("🚀 Starting Plexus Score Processor Worker for Kubernetes")
    logger.info(f"Configuration: once={once}, max_jobs={max_jobs}, error_retry_delay={error_retry_delay}")

    # Create processor
    processor = JobProcessor(
        error_retry_delay=error_retry_delay,
        max_jobs_per_worker=max_jobs
    )

    # Initialize
    try:
        await processor.initialize()
        logger.info("✅ Worker initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize worker: {e}", exc_info=True)
        sys.exit(1)

    # Run the worker loop
    logger.info("🔄 Starting job processing loop")
    consecutive_errors = 0
    max_consecutive_errors = 10

    while True:
        try:
            # Poll for a job
            job = await processor.poll_sqs_for_job()

            if job:
                # Process the job
                logger.info(f"📊 Processing job: {job['scoring_job_id']}")
                await processor.process_job(
                    job['scoring_job_id'],
                    job['item_id'],
                    job['scorecard_id'],
                    job['score_id'],
                    job['receipt_handle']
                )
                logger.info(f"✅ Job completed: {job['scoring_job_id']}")

                # Reset error counter on success
                consecutive_errors = 0
                processor.jobs_processed += 1

                # Check if we've hit the max jobs limit
                if processor.max_jobs_per_worker and processor.jobs_processed >= processor.max_jobs_per_worker:
                    logger.info(
                        f"🏁 Processed {processor.jobs_processed} jobs (max: {processor.max_jobs_per_worker}), exiting for fresh restart"
                    )
                    break

                # Exit after one job if in once mode
                if once:
                    logger.info("🏁 Processed one job in 'once' mode, exiting")
                    break
            else:
                # No job available, continue polling
                logger.debug("📭 No jobs in queue, continuing to poll...")

        except KeyboardInterrupt:
            logger.info("⚠️  Keyboard interrupt received, shutting down...")
            break

        except Exception as e:
            consecutive_errors += 1
            logger.error(
                f"❌ Error processing job (consecutive errors: {consecutive_errors}/{max_consecutive_errors}): {e}",
                exc_info=True
            )

            # Exit if too many consecutive errors
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"❌ Too many consecutive errors ({consecutive_errors}), exiting")
                sys.exit(1)

            # Wait before retrying
            logger.info(f"⏳ Waiting {error_retry_delay}s before retry...")
            await asyncio.sleep(error_retry_delay)

    logger.info(f"🏁 Worker shutting down gracefully (processed {processor.jobs_processed} jobs)")


def main():
    """Main entry point for the worker"""
    # Configure logging
    global logger
    logger = configure_logging()

    # Get configuration from environment
    once = os.environ.get("WORKER_ONCE", "").lower() == "true"
    max_jobs = os.environ.get("MAX_JOBS_PER_WORKER")
    if max_jobs:
        try:
            max_jobs = int(max_jobs)
        except ValueError:
            logger.warning(f"Invalid MAX_JOBS_PER_WORKER value: {max_jobs}, ignoring")
            max_jobs = None

    error_retry_delay = int(os.environ.get("ERROR_RETRY_DELAY", "5"))

    # Setup shutdown handler
    shutdown_handler = WorkerShutdownHandler()

    # Run the worker
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    shutdown_handler.setup(loop)

    try:
        loop.run_until_complete(
            run_worker(
                once=once,
                max_jobs=max_jobs,
                error_retry_delay=error_retry_delay
            )
        )
    except KeyboardInterrupt:
        logger.info("⚠️  Interrupted by user")
    finally:
        loop.close()
        logger.info("👋 Worker terminated")


if __name__ == "__main__":
    main()
