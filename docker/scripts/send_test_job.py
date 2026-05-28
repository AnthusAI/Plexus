#!/usr/bin/env python3
"""
Send a test scoring job to RabbitMQ for local testing.

Usage:
    python send_test_job.py --scoring-job-id <id> --scorecard <name> --score <name>
"""

import argparse
import json
import sys
from celery import Celery

def send_test_job(
    broker_url: str,
    scoring_job_id: str,
    scorecard: str = None,
    score: str = None,
    item_id: str = None,
    account_key: str = None
):
    """
    Send a test scoring job to the Celery queue.

    Args:
        broker_url: RabbitMQ broker URL
        scoring_job_id: ID of the scoring job
        scorecard: Scorecard name (optional)
        score: Score name (optional)
        item_id: Item ID (optional)
        account_key: Account key (optional)
    """
    # Create Celery app with result backend
    result_backend = broker_url.replace('amqp://', 'rpc://')
    app = Celery('test-client', broker=broker_url, backend=result_backend)

    # Prepare task kwargs
    kwargs = {}
    if scorecard:
        kwargs['scorecard_name'] = scorecard
    if score:
        kwargs['score_name'] = score
    if item_id:
        kwargs['item_id'] = item_id
    if account_key:
        kwargs['account_key'] = account_key

    print(f"📤 Sending scoring job to queue...")
    print(f"   Job ID: {scoring_job_id}")
    if kwargs:
        print(f"   Parameters: {json.dumps(kwargs, indent=2)}")

    # Send task
    result = app.send_task(
        'plexus.workers.celery_tasks.process_scoring_job',
        args=[scoring_job_id],
        kwargs=kwargs,
        queue='scoring-requests'
    )

    print(f"\n✅ Task sent successfully!")
    print(f"   Celery Task ID: {result.id}")
    print(f"\n📊 You can monitor progress:")
    print(f"   - RabbitMQ UI: http://localhost:15672")
    print(f"   - Worker logs: docker-compose logs -f plexus-worker-celery")

    # Optionally wait for result
    if input("\n⏳ Wait for result? (y/n): ").lower() == 'y':
        print("Waiting for task to complete (timeout: 60s)...")
        try:
            task_result = result.get(timeout=60)
            print(f"\n✅ Task completed!")
            print(json.dumps(task_result, indent=2))
        except Exception as e:
            print(f"\n❌ Error getting result: {e}")
            sys.exit(1)


def send_health_check(broker_url: str):
    """Send a simple health check task."""
    # Parse broker URL to construct result backend URL
    result_backend = broker_url.replace('amqp://', 'rpc://')

    app = Celery('test-client', broker=broker_url, backend=result_backend)

    print("📤 Sending health check task...")
    result = app.send_task(
        'plexus.workers.celery_tasks.health_check',
        queue='scoring-requests'
    )

    print(f"✅ Task sent! Task ID: {result.id}")
    print("Waiting for response...")

    try:
        response = result.get(timeout=10)
        print(f"\n✅ Worker is healthy!")
        print(json.dumps(response, indent=2))
    except Exception as e:
        print(f"\n❌ Health check failed: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Send test scoring jobs to RabbitMQ"
    )
    parser.add_argument(
        "--broker",
        default="amqp://plexus:plexus@localhost:5672/",
        help="RabbitMQ broker URL"
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Send a health check task instead of a scoring job"
    )
    parser.add_argument(
        "--scoring-job-id",
        help="Scoring job ID to process"
    )
    parser.add_argument(
        "--scorecard",
        help="Scorecard name (for ad-hoc scoring)"
    )
    parser.add_argument(
        "--score",
        help="Score name (for ad-hoc scoring)"
    )
    parser.add_argument(
        "--item-id",
        help="Item ID to score (for ad-hoc scoring)"
    )
    parser.add_argument(
        "--account-key",
        help="Account key override"
    )

    args = parser.parse_args()

    if args.health_check:
        send_health_check(args.broker)
    elif args.scoring_job_id:
        send_test_job(
            broker_url=args.broker,
            scoring_job_id=args.scoring_job_id,
            scorecard=args.scorecard,
            score=args.score,
            item_id=args.item_id,
            account_key=args.account_key
        )
    else:
        parser.print_help()
        print("\n❌ Error: Either --health-check or --scoring-job-id is required")
        sys.exit(1)


if __name__ == "__main__":
    main()
