"""Pytest configuration and fixtures for score-processor-lambda tests"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add parent directory to path so we can import handler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Set required environment variables for tests
os.environ.setdefault('SCORECARD_CACHE_DIR', '/tmp/scorecards')
os.environ.setdefault('NLTK_DATA', '/usr/local/share/nltk_data:/tmp/nltk_data')
os.environ['AWS_ACCESS_KEY_ID'] = 'test-access-key'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'test-secret-key'
os.environ['AWS_DEFAULT_REGION'] = 'us-west-2'
os.environ['PLEXUS_API_KEY'] = 'test-key'
os.environ['PLEXUS_API_URL'] = 'https://test.example.com/graphql'
os.environ['PLEXUS_ACCOUNT_KEY'] = 'test-account'
os.environ['PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL'] = 'https://sqs.us-west-2.amazonaws.com/123456789/test-queue'
os.environ['PLEXUS_RESPONSE_WORKER_QUEUE_URL'] = 'https://sqs.us-west-2.amazonaws.com/123456789/test-response-queue'


@pytest.fixture
def mock_boto3_client():
    """Mock boto3 SQS client"""
    with patch('boto3.client') as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_plexus_client():
    """Mock PlexusDashboardClient"""
    with patch('plexus.dashboard.api.client.PlexusDashboardClient') as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def sample_scoring_job():
    """Sample ScoringJob for testing"""
    job = MagicMock()
    job.id = 'test-job-123'
    job.itemId = 'test-item-456'
    job.scorecardId = 'test-scorecard-789'
    job.scoreId = 'test-score-012'
    job.status = 'PENDING'
    return job


@pytest.fixture
def sample_sqs_event():
    """Sample SQS event source trigger for Lambda"""
    return {
        'Records': [
            {
                'eventSource': 'aws:sqs',
                'body': '{"scoring_job_id": "test-job-123"}',
                'receiptHandle': 'test-receipt-handle'
            }
        ]
    }


@pytest.fixture
def sample_manual_event():
    """Sample manual invocation event (no Records)"""
    return {}


@pytest.fixture
def lambda_context():
    """Mock Lambda context"""
    context = MagicMock()
    context.function_name = 'test-function'
    context.function_version = '$LATEST'
    context.invoked_function_arn = 'arn:aws:lambda:us-west-2:123456789:function:test-function'
    context.memory_limit_in_mb = 2048
    context.aws_request_id = 'test-request-id'
    context.log_group_name = '/aws/lambda/test-function'
    context.log_stream_name = '2026/02/03/[$LATEST]test'
    return context
