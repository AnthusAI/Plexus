"""
Fan-out Lambda handler for score processor.

This Lambda function polls SQS for multiple messages and invokes multiple
score processor Lambda functions asynchronously for controlled rollout.
"""

import json
import os
import boto3
from typing import Dict, List, Any

# Initialize AWS clients
sqs_client = boto3.client('sqs')
lambda_client = boto3.client('lambda')

# Configuration from environment variables
FANOUT_BATCH_SIZE = int(os.environ.get('FANOUT_BATCH_SIZE', '10'))
SCORE_PROCESSOR_LAMBDA_ARN = os.environ['SCORE_PROCESSOR_LAMBDA_ARN']
REQUEST_QUEUE_URL = os.environ['PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL']

# Extended visibility timeout to prevent re-processing during Lambda execution
# Score processor has 300s timeout, add buffer
VISIBILITY_TIMEOUT_SECONDS = 360


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for fan-out invocation.

    Polls SQS queue for messages and invokes score processor Lambda for each.
    Does NOT delete messages - score processor handles deletion after success.

    Args:
        event: Lambda event (unused for manual invocation)
        context: Lambda context

    Returns:
        Dict with invocation summary
    """
    print(f"Starting fan-out with batch size: {FANOUT_BATCH_SIZE}")

    # Poll SQS for messages
    messages = poll_sqs_messages(FANOUT_BATCH_SIZE)

    if not messages:
        print("No messages found in queue")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'No messages to process',
                'invocations': 0,
                'successes': 0,
                'failures': 0
            })
        }

    print(f"Retrieved {len(messages)} messages from queue")

    # Extend visibility timeout on all messages
    extend_visibility_timeout(messages)

    # Invoke score processor Lambda for each message
    results = invoke_score_processors(messages)

    # Generate summary
    successes = sum(1 for r in results if r['success'])
    failures = sum(1 for r in results if not r['success'])

    summary = {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Invoked {len(messages)} score processor Lambdas',
            'invocations': len(messages),
            'successes': successes,
            'failures': failures,
            'details': results
        })
    }

    print(f"Fan-out complete: {successes} successes, {failures} failures")
    return summary


def poll_sqs_messages(max_messages: int) -> List[Dict[str, Any]]:
    """
    Poll SQS queue for messages.

    Args:
        max_messages: Maximum number of messages to retrieve

    Returns:
        List of SQS messages
    """
    try:
        response = sqs_client.receive_message(
            QueueUrl=REQUEST_QUEUE_URL,
            MaxNumberOfMessages=min(max_messages, 10),  # SQS limit is 10
            WaitTimeSeconds=10,  # Long polling
            VisibilityTimeout=VISIBILITY_TIMEOUT_SECONDS
        )

        return response.get('Messages', [])

    except Exception as e:
        print(f"Error polling SQS: {str(e)}")
        raise


def extend_visibility_timeout(messages: List[Dict[str, Any]]) -> None:
    """
    Extend visibility timeout on messages to prevent re-processing.

    Args:
        messages: List of SQS messages
    """
    for message in messages:
        try:
            sqs_client.change_message_visibility(
                QueueUrl=REQUEST_QUEUE_URL,
                ReceiptHandle=message['ReceiptHandle'],
                VisibilityTimeout=VISIBILITY_TIMEOUT_SECONDS
            )
        except Exception as e:
            print(f"Warning: Failed to extend visibility timeout for message: {str(e)}")


def invoke_score_processors(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Invoke score processor Lambda for each message.

    Args:
        messages: List of SQS messages

    Returns:
        List of invocation results
    """
    results = []

    for message in messages:
        result = invoke_single_processor(message)
        results.append(result)

    return results


def invoke_single_processor(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Invoke score processor Lambda for a single message.

    Args:
        message: SQS message

    Returns:
        Dict with invocation result
    """
    try:
        # Parse message body
        message_body = json.loads(message['Body'])
        scoring_job_id = message_body.get('scoring_job_id')

        # Prepare payload for score processor Lambda
        payload = {
            'source': 'fanout',
            'message_body': message_body,
            'receipt_handle': message['ReceiptHandle'],
            'queue_url': REQUEST_QUEUE_URL
        }

        # Invoke asynchronously (Event type - fire and forget)
        response = lambda_client.invoke(
            FunctionName=SCORE_PROCESSOR_LAMBDA_ARN,
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps(payload)
        )

        # For async invocations, StatusCode 202 means accepted
        success = response['StatusCode'] == 202

        result = {
            'success': success,
            'scoring_job_id': scoring_job_id,
            'status_code': response['StatusCode']
        }

        if success:
            print(f"Successfully invoked score processor for job: {scoring_job_id}")
        else:
            print(f"Failed to invoke score processor for job: {scoring_job_id}, status: {response['StatusCode']}")

        return result

    except Exception as e:
        error_msg = str(e)
        print(f"Error invoking score processor for message: {error_msg}")

        return {
            'success': False,
            'scoring_job_id': message_body.get('scoring_job_id', 'unknown'),
            'error': error_msg
        }
