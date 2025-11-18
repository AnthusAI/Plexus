#!/usr/bin/env python3
"""
Temporary script to trigger the fan-out Lambda function at regular intervals.

This script continuously invokes the fan-out Lambda function every N seconds
until stopped with Ctrl+C. Used for controlled rollout testing before enabling
the full SQS event source trigger.

Usage:
    # Staging
    python trigger_fanout.py --environment staging

    # Production (default)
    python trigger_fanout.py --environment production

    # Custom interval
    python trigger_fanout.py --interval 15

    # Run in background
    nohup python trigger_fanout.py > fanout.log 2>&1 &
"""

import boto3
import time
import sys
import argparse
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(
        description="Trigger fan-out Lambda function at regular intervals"
    )
    parser.add_argument(
        "--environment",
        "-e",
        choices=["staging", "production"],
        default="production",
        help="Environment to target (default: production)"
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=10,
        help="Interval in seconds between invocations (default: 10)"
    )
    parser.add_argument(
        "--region",
        "-r",
        default="us-west-2",
        help="AWS region (default: us-west-2)"
    )

    args = parser.parse_args()

    function_name = f"plexus-lambda-{args.environment}-fanout"

    print("=" * 60)
    print("Fan-Out Lambda Trigger")
    print("=" * 60)
    print(f"Environment:  {args.environment}")
    print(f"Function:     {function_name}")
    print(f"Region:       {args.region}")
    print(f"Interval:     {args.interval} seconds")
    print(f"Started:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("\nPress Ctrl+C to stop\n")

    # Initialize Lambda client
    try:
        lambda_client = boto3.client('lambda', region_name=args.region)
    except Exception as e:
        print(f"ERROR: Failed to create Lambda client: {e}")
        print("\nMake sure you have AWS credentials configured.")
        print("Run: aws configure")
        sys.exit(1)

    invocation_count = 0
    success_count = 0
    failure_count = 0
    total_messages_processed = 0

    # Track stats for last 10 invocations
    last_summary_invocation = 0
    last_summary_messages = 0

    try:
        while True:
            invocation_count += 1
            timestamp = datetime.now().strftime('%H:%M:%S')

            print(f"[{timestamp}] Invocation #{invocation_count}: ", end="", flush=True)

            # Track Lambda execution time
            start_time = time.time()

            try:
                response = lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType='RequestResponse',  # Synchronous invocation to get response
                    Payload=b'{}'  # Empty payload
                )

                execution_time = time.time() - start_time

                status_code = response['StatusCode']

                if status_code == 200:
                    # Parse the response payload
                    import json
                    payload = json.loads(response['Payload'].read())

                    # Extract message processing info from fan-out response
                    if 'body' in payload:
                        body = json.loads(payload['body'])
                        invocations = body.get('invocations', 0)
                        successes = body.get('successes', 0)
                        failures = body.get('failures', 0)

                        if invocations > 0:
                            success_count += 1
                            total_messages_processed += invocations
                            print(f"✓ Processed {invocations} messages ({successes} successful, {failures} failed) [{execution_time:.1f}s]")
                        else:
                            print(f"⊘ No messages in queue [{execution_time:.1f}s]")
                    else:
                        success_count += 1
                        print(f"✓ Success (status: {status_code}) [{execution_time:.1f}s]")
                else:
                    failure_count += 1
                    print(f"✗ Unexpected status: {status_code} [{execution_time:.1f}s]")

            except lambda_client.exceptions.ResourceNotFoundException:
                failure_count += 1
                execution_time = time.time() - start_time
                print(f"✗ Function not found: {function_name}")
                print("\nERROR: Lambda function does not exist.")
                print(f"Expected function name: {function_name}")
                print("\nPlease verify:")
                print("1. The function has been deployed")
                print("2. You're using the correct environment (--environment)")
                print("3. You're using the correct region (--region)")
                sys.exit(1)

            except lambda_client.exceptions.TooManyRequestsException:
                failure_count += 1
                execution_time = time.time() - start_time
                print(f"✗ Throttled (too many requests) [{execution_time:.1f}s]")
                print("\nWARNING: Lambda invocation throttled. Consider:")
                print("1. Increasing the interval (--interval)")
                print("2. Requesting Lambda concurrency limit increase")

            except Exception as e:
                failure_count += 1
                execution_time = time.time() - start_time
                print(f"✗ Error: {e} [{execution_time:.1f}s]")

            # Print summary every 10 invocations
            if invocation_count % 10 == 0:
                # Calculate stats for last 10 invocations
                invocations_since_summary = invocation_count - last_summary_invocation
                messages_since_summary = total_messages_processed - last_summary_messages

                print(f"\n--- Last {invocations_since_summary} invocations: {messages_since_summary} messages processed | Total: {total_messages_processed} messages ({success_count} successful, {failure_count} failed) ---\n")

                # Update tracking for next summary
                last_summary_invocation = invocation_count
                last_summary_messages = total_messages_processed

            # Calculate remaining sleep time to maintain consistent interval
            remaining_sleep = max(0, args.interval - execution_time)
            if remaining_sleep > 0:
                time.sleep(remaining_sleep)

    except KeyboardInterrupt:
        print("\n")
        print("=" * 60)
        print("Stopped by user")
        print("=" * 60)
        print(f"Total invocations:     {invocation_count}")
        print(f"Successful:            {success_count}")
        print(f"Failed:                {failure_count}")
        print(f"Messages processed:    {total_messages_processed}")
        print(f"Stopped at:            {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        sys.exit(0)


if __name__ == "__main__":
    main()
