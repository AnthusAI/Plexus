"""
Tests for endpoint utility functions.

Tests the SageMaker endpoint discovery and invocation functions.
Uses mocking to avoid requiring actual AWS credentials.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError


class TestGetSageMakerEndpoint:
    """Test the get_sagemaker_endpoint function."""

    @patch('plexus.training.endpoint_utils.boto3')
    def test_endpoint_found_and_in_service(self, mock_boto3):
        """Test finding an InService endpoint."""
        from plexus.training.endpoint_utils import get_sagemaker_endpoint

        # Mock SageMaker client
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client
        mock_client.describe_endpoint.return_value = {
            'EndpointStatus': 'InService',
            'EndpointName': 'plexus-sc-score-serverless'
        }

        result = get_sagemaker_endpoint('sc', 'score')

        assert result == 'plexus-sc-score-serverless'
        mock_client.describe_endpoint.assert_called_once_with(
            EndpointName='plexus-sc-score-serverless'
        )

    @patch('plexus.training.endpoint_utils.boto3')
    def test_endpoint_exists_but_not_in_service(self, mock_boto3):
        """Test endpoint exists but is not InService."""
        from plexus.training.endpoint_utils import get_sagemaker_endpoint

        mock_client = Mock()
        mock_boto3.client.return_value = mock_client
        mock_client.describe_endpoint.return_value = {
            'EndpointStatus': 'Creating',
            'EndpointName': 'plexus-sc-score-serverless'
        }

        result = get_sagemaker_endpoint('sc', 'score')

        assert result is None

    @patch('plexus.training.endpoint_utils.boto3')
    def test_endpoint_not_found(self, mock_boto3):
        """Test endpoint doesn't exist."""
        from plexus.training.endpoint_utils import get_sagemaker_endpoint

        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        # Simulate ValidationException
        error_response = {'Error': {'Code': 'ValidationException'}}
        mock_client.describe_endpoint.side_effect = ClientError(
            error_response, 'describe_endpoint'
        )

        result = get_sagemaker_endpoint('sc', 'score')

        assert result is None

    @patch('plexus.training.endpoint_utils.boto3')
    def test_realtime_deployment_type(self, mock_boto3):
        """Test with realtime deployment type."""
        from plexus.training.endpoint_utils import get_sagemaker_endpoint

        mock_client = Mock()
        mock_boto3.client.return_value = mock_client
        mock_client.describe_endpoint.return_value = {
            'EndpointStatus': 'InService',
            'EndpointName': 'plexus-sc-score-realtime'
        }

        result = get_sagemaker_endpoint('sc', 'score', 'realtime')

        assert result == 'plexus-sc-score-realtime'
        mock_client.describe_endpoint.assert_called_once_with(
            EndpointName='plexus-sc-score-realtime'
        )

    @patch('plexus.training.endpoint_utils.boto3', None)
    def test_boto3_not_available(self):
        """Test behavior when boto3 is not available."""
        from plexus.training.endpoint_utils import get_sagemaker_endpoint

        result = get_sagemaker_endpoint('sc', 'score')

        assert result is None


class TestShouldDeployEndpoint:
    """Test the should_deploy_endpoint function."""

    @patch('plexus.training.endpoint_utils.boto3')
    def test_endpoint_does_not_exist(self, mock_boto3):
        """Test when endpoint doesn't exist (should deploy)."""
        from plexus.training.endpoint_utils import should_deploy_endpoint

        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        # Simulate ValidationException
        error_response = {'Error': {'Code': 'ValidationException'}}
        mock_client.describe_endpoint.side_effect = ClientError(
            error_response, 'describe_endpoint'
        )

        result = should_deploy_endpoint('sc', 'score', 's3://bucket/new/model.tar.gz')

        assert result is True

    @patch('plexus.training.endpoint_utils.boto3')
    def test_endpoint_has_different_model(self, mock_boto3):
        """Test when endpoint exists with different model (should deploy)."""
        from plexus.training.endpoint_utils import should_deploy_endpoint

        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        # Mock endpoint
        mock_client.describe_endpoint.return_value = {
            'EndpointConfigName': 'config-abc123'
        }

        # Mock endpoint config
        mock_client.describe_endpoint_config.return_value = {
            'ProductionVariants': [{'ModelName': 'model-abc123'}]
        }

        # Mock model with old S3 URI
        mock_client.describe_model.return_value = {
            'PrimaryContainer': {
                'ModelDataUrl': 's3://bucket/old/model.tar.gz'
            }
        }

        result = should_deploy_endpoint('sc', 'score', 's3://bucket/new/model.tar.gz')

        assert result is True

    @patch('plexus.training.endpoint_utils.boto3')
    def test_endpoint_has_same_model(self, mock_boto3):
        """Test when endpoint exists with same model (should not deploy)."""
        from plexus.training.endpoint_utils import should_deploy_endpoint

        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        model_s3_uri = 's3://bucket/models/test/model.tar.gz'

        # Mock endpoint
        mock_client.describe_endpoint.return_value = {
            'EndpointConfigName': 'config-abc123'
        }

        # Mock endpoint config
        mock_client.describe_endpoint_config.return_value = {
            'ProductionVariants': [{'ModelName': 'model-abc123'}]
        }

        # Mock model with same S3 URI
        mock_client.describe_model.return_value = {
            'PrimaryContainer': {
                'ModelDataUrl': model_s3_uri
            }
        }

        result = should_deploy_endpoint('sc', 'score', model_s3_uri)

        assert result is False

    @patch('plexus.training.endpoint_utils.boto3', None)
    def test_boto3_not_available(self):
        """Test behavior when boto3 is not available (should deploy)."""
        from plexus.training.endpoint_utils import should_deploy_endpoint

        result = should_deploy_endpoint('sc', 'score', 's3://bucket/model.tar.gz')

        # Should assume deployment needed if can't check
        assert result is True


class TestGetEndpointStatus:
    """Test the get_endpoint_status function."""

    @patch('plexus.training.endpoint_utils.boto3')
    def test_get_status_success(self, mock_boto3):
        """Test successfully getting endpoint status."""
        from plexus.training.endpoint_utils import get_endpoint_status

        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        # Mock endpoint
        mock_client.describe_endpoint.return_value = {
            'EndpointName': 'plexus-sc-score-serverless',
            'EndpointStatus': 'InService',
            'CreationTime': '2025-01-01T00:00:00Z',
            'LastModifiedTime': '2025-01-02T00:00:00Z',
            'EndpointArn': 'arn:aws:sagemaker:us-west-2:123456789012:endpoint/plexus-sc-score-serverless',
            'EndpointConfigName': 'config-abc123'
        }

        # Mock endpoint config
        mock_client.describe_endpoint_config.return_value = {
            'ProductionVariants': [{'ModelName': 'model-abc123'}]
        }

        # Mock model
        mock_client.describe_model.return_value = {
            'PrimaryContainer': {
                'ModelDataUrl': 's3://bucket/models/test/model.tar.gz'
            }
        }

        result = get_endpoint_status('sc', 'score')

        assert result is not None
        assert result['endpoint_name'] == 'plexus-sc-score-serverless'
        assert result['status'] == 'InService'
        assert result['model_s3_uri'] == 's3://bucket/models/test/model.tar.gz'
        assert 'arn:aws:sagemaker' in result['endpoint_arn']

    @patch('plexus.training.endpoint_utils.boto3')
    def test_get_status_endpoint_not_found(self, mock_boto3):
        """Test getting status when endpoint doesn't exist."""
        from plexus.training.endpoint_utils import get_endpoint_status

        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        # Simulate ValidationException
        error_response = {'Error': {'Code': 'ValidationException'}}
        mock_client.describe_endpoint.side_effect = ClientError(
            error_response, 'describe_endpoint'
        )

        result = get_endpoint_status('sc', 'score')

        assert result is None

    @patch('plexus.training.endpoint_utils.boto3', None)
    def test_get_status_boto3_not_available(self):
        """Test behavior when boto3 is not available."""
        from plexus.training.endpoint_utils import get_endpoint_status

        result = get_endpoint_status('sc', 'score')

        assert result is None


class TestInvokeSageMakerEndpoint:
    """Test the invoke_sagemaker_endpoint function."""

    @patch('plexus.training.endpoint_utils.boto3')
    def test_invoke_success(self, mock_boto3):
        """Test successful endpoint invocation."""
        from plexus.training.endpoint_utils import invoke_sagemaker_endpoint

        mock_runtime = Mock()
        mock_boto3.client.return_value = mock_runtime

        # Mock response
        mock_body = Mock()
        mock_body.read.return_value = b'{"value": "Yes", "confidence": 0.95}'
        mock_runtime.invoke_endpoint.return_value = {
            'Body': mock_body
        }

        payload = {'text': 'Test input'}
        result = invoke_sagemaker_endpoint('plexus-sc-score-serverless', payload)

        assert result is not None
        assert result['value'] == 'Yes'
        assert result['confidence'] == 0.95
        mock_runtime.invoke_endpoint.assert_called_once()

    @patch('plexus.training.endpoint_utils.boto3')
    def test_invoke_client_error(self, mock_boto3):
        """Test invocation with ClientError."""
        from plexus.training.endpoint_utils import invoke_sagemaker_endpoint

        mock_runtime = Mock()
        mock_boto3.client.return_value = mock_runtime

        # Simulate error
        error_response = {'Error': {'Code': 'ModelError', 'Message': 'Model failed'}}
        mock_runtime.invoke_endpoint.side_effect = ClientError(
            error_response, 'invoke_endpoint'
        )

        result = invoke_sagemaker_endpoint('plexus-sc-score-serverless', {'text': 'test'})

        assert result is None

    @patch('plexus.training.endpoint_utils.boto3', None)
    def test_invoke_boto3_not_available(self):
        """Test invocation when boto3 is not available."""
        from plexus.training.endpoint_utils import invoke_sagemaker_endpoint

        result = invoke_sagemaker_endpoint('endpoint-name', {'text': 'test'})

        assert result is None


class TestEndpointUtilsIntegration:
    """Integration tests for endpoint utilities."""

    @patch('plexus.training.endpoint_utils.boto3')
    def test_typical_workflow(self, mock_boto3):
        """Test typical workflow: check endpoint, deploy if needed, invoke."""
        from plexus.training.endpoint_utils import (
            get_sagemaker_endpoint,
            should_deploy_endpoint,
            invoke_sagemaker_endpoint
        )

        mock_client = Mock()
        mock_runtime = Mock()

        def client_factory(service, **kwargs):
            if service == 'sagemaker':
                return mock_client
            elif service == 'sagemaker-runtime':
                return mock_runtime
            return Mock()

        mock_boto3.client.side_effect = client_factory

        # First check: endpoint doesn't exist
        error_response = {'Error': {'Code': 'ValidationException'}}
        mock_client.describe_endpoint.side_effect = ClientError(
            error_response, 'describe_endpoint'
        )

        endpoint = get_sagemaker_endpoint('sc', 'score')
        assert endpoint is None

        # Should deploy
        should_deploy = should_deploy_endpoint('sc', 'score', 's3://bucket/model.tar.gz')
        assert should_deploy is True

        # After deployment, endpoint exists
        mock_client.describe_endpoint.side_effect = None
        mock_client.describe_endpoint.return_value = {
            'EndpointStatus': 'InService',
            'EndpointName': 'plexus-sc-score-serverless'
        }

        endpoint = get_sagemaker_endpoint('sc', 'score')
        assert endpoint == 'plexus-sc-score-serverless'

        # Can now invoke
        mock_body = Mock()
        mock_body.read.return_value = b'{"value": "Yes"}'
        mock_runtime.invoke_endpoint.return_value = {'Body': mock_body}

        result = invoke_sagemaker_endpoint(endpoint, {'text': 'test'})
        assert result['value'] == 'Yes'
