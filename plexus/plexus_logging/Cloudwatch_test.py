import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
from .Cloudwatch import CloudWatchLogger

def test_init_without_aws_credentials():
    with patch.dict('os.environ', clear=True):
        logger = CloudWatchLogger()
        assert logger.cloudwatch_client is None

def test_log_metric_without_client():
    with patch.dict('os.environ', clear=True):
        logger = CloudWatchLogger()
        # Should not raise any exception
        logger.log_metric('test_metric', 1.0, {'dim1': 'value1'})

@patch('boto3.client')
def test_log_metric_success(mock_boto):
    mock_client = MagicMock()
    mock_boto.return_value = mock_client
    
    with patch.dict('os.environ', {
        'AWS_ACCESS_KEY_ID': 'test',
        'AWS_SECRET_ACCESS_KEY': 'test',
        'AWS_REGION_NAME': 'test'
    }):
        logger = CloudWatchLogger()
        logger.log_metric('test_metric', 1.0, {'dim1': 'value1'})
        
        mock_boto.assert_called_once_with('cloudwatch', region_name='test')
        mock_client.put_metric_data.assert_called_once()

@patch('boto3.client')
def test_log_metric_client_error(mock_boto):
    mock_client = MagicMock()
    mock_client.put_metric_data.side_effect = ClientError(
        {'Error': {'Code': 'TestError', 'Message': 'Test error message'}},
        'PutMetricData'
    )
    mock_boto.return_value = mock_client
    
    with patch.dict('os.environ', {
        'AWS_ACCESS_KEY_ID': 'test',
        'AWS_SECRET_ACCESS_KEY': 'test',
        'AWS_REGION_NAME': 'test'
    }):
        logger = CloudWatchLogger()
        # Should not raise exception, but log error instead
        logger.log_metric('test_metric', 1.0, {'dim1': 'value1'})
        
        mock_boto.assert_called_once_with('cloudwatch', region_name='test')
        mock_client.put_metric_data.assert_called_once()

@patch('boto3.client')
def test_init_ignores_static_aws_keys(mock_boto):
    mock_boto.return_value = MagicMock()

    with patch.dict('os.environ', {
        'AWS_ACCESS_KEY_ID': 'AKIATESTKEY1234567890',
        'AWS_SECRET_ACCESS_KEY': 'test-secret',
        'AWS_REGION_NAME': 'test'
    }):
        CloudWatchLogger._shared_clients = {}
        CloudWatchLogger()

    mock_boto.assert_called_once_with('cloudwatch', region_name='test')

@patch('boto3.client')
def test_log_metric_redacts_dimensions(mock_boto):
    mock_client = MagicMock()
    mock_boto.return_value = mock_client

    with patch.dict('os.environ', {'AWS_REGION_NAME': 'test'}, clear=True):
        CloudWatchLogger._shared_clients = {}
        logger = CloudWatchLogger()
        logger.log_metric('test_metric', 1.0, {'email': 'person@example.com'})

    metric_data = mock_client.put_metric_data.call_args.kwargs['MetricData'][0]
    assert metric_data['Dimensions'][0]['Value'] == '[REDACTED_EMAIL]'
