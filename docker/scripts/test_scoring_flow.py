#!/usr/bin/env python3
"""
Test the complete scoring flow end-to-end:
1. Create a test item in PostgreSQL via the GraphQL proxy
2. Submit a scoring job to RabbitMQ
3. Worker processes the job
4. Verify the result is stored in PostgreSQL

Usage:
    python test_scoring_flow.py --scorecard <name> --score <name>
"""

import argparse
import json
import time
import requests
from celery import Celery


def create_test_item(proxy_url: str, api_key: str) -> str:
    """Create a test item via the GraphQL proxy."""
    print("📝 Creating test item in proxy...")

    mutation = """
    mutation CreateItem($input: CreateItemInput!) {
      createItem(input: $input) {
        id
        data
        createdAt
      }
    }
    """

    variables = {
        "input": {
            "accountId": "test-account",
            "data": json.dumps({
                "text": "This is a test message for scoring",
                "metadata": {
                    "source": "test_script",
                    "timestamp": time.time()
                }
            })
        }
    }

    response = requests.post(
        proxy_url,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key
        },
        json={
            "query": mutation,
            "variables": variables
        }
    )

    if response.status_code != 200:
        print(f"❌ Failed to create item: {response.status_code}")
        print(response.text)
        return None

    data = response.json()
    if "errors" in data:
        print(f"❌ GraphQL errors: {json.dumps(data['errors'], indent=2)}")
        return None

    item = data["data"]["createItem"]
    print(f"✅ Created item: {item['id']}")
    return item["id"]


def create_scoring_job(proxy_url: str, api_key: str, item_id: str, scorecard_name: str, score_name: str) -> str:
    """Create a scoring job via the GraphQL proxy."""
    print(f"\n📋 Creating scoring job for scorecard='{scorecard_name}', score='{score_name}'...")

    # Note: This mutation might need to be adjusted based on your actual GraphQL schema
    mutation = """
    mutation CreateScoringJob($input: CreateScoringJobInput!) {
      createScoringJob(input: $input) {
        id
        status
      }
    }
    """

    variables = {
        "input": {
            "itemId": item_id,
            "scorecardName": scorecard_name,
            "scoreName": score_name,
            "status": "PENDING"
        }
    }

    response = requests.post(
        proxy_url,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key
        },
        json={
            "query": mutation,
            "variables": variables
        }
    )

    if response.status_code != 200:
        print(f"❌ Failed to create scoring job: {response.status_code}")
        print(response.text)
        return None

    data = response.json()
    if "errors" in data:
        print(f"❌ GraphQL errors: {json.dumps(data['errors'], indent=2)}")
        print("\n⚠️  Note: The scoring job mutation might not be implemented in the proxy yet.")
        print("    You can still test by manually creating a job ID and using it.")
        return None

    job = data["data"]["createScoringJob"]
    print(f"✅ Created scoring job: {job['id']}")
    return job["id"]


def submit_to_queue(broker_url: str, scoring_job_id: str, scorecard: str, score: str, item_id: str):
    """Submit the scoring job to RabbitMQ."""
    print(f"\n📤 Submitting job {scoring_job_id} to queue...")

    result_backend = broker_url.replace('amqp://', 'rpc://')
    app = Celery('test-client', broker=broker_url, backend=result_backend)

    result = app.send_task(
        'plexus.workers.celery_tasks.process_scoring_job',
        args=[scoring_job_id],
        kwargs={
            'scorecard_name': scorecard,
            'score_name': score,
            'item_id': item_id
        },
        queue='scoring-requests'
    )

    print(f"✅ Task sent! Celery Task ID: {result.id}")
    return result


def check_result(proxy_url: str, api_key: str, scoring_job_id: str):
    """Check if the scoring result was stored."""
    print(f"\n🔍 Checking for results...")

    query = """
    query GetScoreResults($scoringJobId: ID!) {
      listScoreResults(filter: { scoringJobId: $scoringJobId }) {
        items {
          id
          value
          reasoning
          createdAt
        }
      }
    }
    """

    response = requests.post(
        proxy_url,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key
        },
        json={
            "query": query,
            "variables": {"scoringJobId": scoring_job_id}
        }
    )

    if response.status_code != 200:
        print(f"❌ Failed to query results: {response.status_code}")
        return None

    data = response.json()
    if "errors" in data:
        print(f"❌ GraphQL errors: {json.dumps(data['errors'], indent=2)}")
        return None

    results = data.get("data", {}).get("listScoreResults", {}).get("items", [])
    return results


def main():
    parser = argparse.ArgumentParser(description="Test end-to-end scoring flow")
    parser.add_argument("--proxy-url", default="http://localhost:18080/graphql", help="GraphQL proxy URL")
    parser.add_argument("--proxy-api-key", default="local-dev-key", help="Proxy API key")
    parser.add_argument("--broker", default="amqp://plexus:plexus@localhost:5672/", help="RabbitMQ broker URL")
    parser.add_argument("--scorecard", required=True, help="Scorecard name")
    parser.add_argument("--score", required=True, help="Score name")
    parser.add_argument("--scoring-job-id", help="Use existing scoring job ID (skip creation)")
    parser.add_argument("--item-id", help="Use existing item ID (skip creation)")

    args = parser.parse_args()

    print("🚀 Testing End-to-End Scoring Flow")
    print("=" * 60)

    # Step 1: Create or use existing item
    if args.item_id:
        item_id = args.item_id
        print(f"📝 Using existing item: {item_id}")
    else:
        item_id = create_test_item(args.proxy_url, args.proxy_api_key)
        if not item_id:
            print("\n❌ Failed to create test item. Exiting.")
            return

    # Step 2: Create or use existing scoring job
    if args.scoring_job_id:
        scoring_job_id = args.scoring_job_id
        print(f"\n📋 Using existing scoring job: {scoring_job_id}")
    else:
        scoring_job_id = create_scoring_job(
            args.proxy_url,
            args.proxy_api_key,
            item_id,
            args.scorecard,
            args.score
        )

        # If job creation failed, create a test job ID
        if not scoring_job_id:
            import uuid
            scoring_job_id = f"test-job-{uuid.uuid4()}"
            print(f"\n⚠️  Using generated job ID: {scoring_job_id}")
            print("    (The proxy might not have scoring job mutations yet)")

    # Step 3: Submit to RabbitMQ queue
    result = submit_to_queue(
        args.broker,
        scoring_job_id,
        args.scorecard,
        args.score,
        item_id
    )

    # Step 4: Wait for processing
    print("\n⏳ Waiting for worker to process (timeout: 60s)...")
    try:
        task_result = result.get(timeout=60)
        print(f"\n✅ Task completed!")
        print(json.dumps(task_result, indent=2))
    except Exception as e:
        print(f"\n⚠️  Task processing: {e}")
        print("    Check worker logs for details:")
        print("    docker-compose -f docker-compose.full-stack.yml logs plexus-worker-celery")

    # Step 5: Verify result in database
    time.sleep(2)  # Give it a moment to commit
    results = check_result(args.proxy_url, args.proxy_api_key, scoring_job_id)

    if results:
        print(f"\n✅ Found {len(results)} result(s) in database!")
        for result in results:
            print(json.dumps(result, indent=2))
    else:
        print("\n⚠️  No results found in database yet")
        print("    This might be because:")
        print("    1. The worker is still processing")
        print("    2. The result mutation isn't implemented in the proxy")
        print("    3. There was an error during scoring")

    print("\n" + "=" * 60)
    print("🏁 Test complete!")


if __name__ == "__main__":
    main()
