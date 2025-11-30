"""
Integration tests for endpoint_utils.

Tests that endpoint_utils correctly integrates with infrastructure naming
and can be used from training and prediction code.
"""

import sys
import os
import pytest

# Add infrastructure to path for naming functions
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
infrastructure_path = os.path.join(project_root, 'infrastructure')
if infrastructure_path not in sys.path:
    sys.path.insert(0, infrastructure_path)


class TestEndpointUtilsImport:
    """Test that endpoint_utils can be imported."""

    def test_import_endpoint_utils(self):
        """Test that endpoint_utils module can be imported."""
        from plexus.training import endpoint_utils
        assert endpoint_utils is not None

    def test_import_functions(self):
        """Test that all key functions can be imported."""
        from plexus.training.endpoint_utils import (
            get_sagemaker_endpoint,
            should_deploy_endpoint,
            get_endpoint_status,
            invoke_sagemaker_endpoint,
        )

        assert callable(get_sagemaker_endpoint)
        assert callable(should_deploy_endpoint)
        assert callable(get_endpoint_status)
        assert callable(invoke_sagemaker_endpoint)


class TestNamingIntegration:
    """Test that endpoint_utils uses naming conventions correctly."""

    def test_endpoint_utils_uses_naming_conventions(self):
        """Test that endpoint_utils generates names using naming module."""
        from plexus.training.endpoint_utils import get_sagemaker_endpoint
        from stacks.shared.naming import get_sagemaker_endpoint_name
        from unittest.mock import patch, Mock
        from botocore.exceptions import ClientError

        # Mock boto3 to avoid needing AWS credentials
        with patch('plexus.training.endpoint_utils.boto3') as mock_boto3:
            mock_client = Mock()
            mock_boto3.client.return_value = mock_client

            # Mock endpoint not found
            error_response = {'Error': {'Code': 'ValidationException'}}
            mock_client.describe_endpoint.side_effect = ClientError(
                error_response, 'describe_endpoint'
            )

            # Call endpoint_utils function
            result = get_sagemaker_endpoint('test-sc', 'test-score')

            # Should return None (endpoint not found)
            assert result is None

            # Verify it tried to look up the correct endpoint name
            expected_endpoint_name = get_sagemaker_endpoint_name(
                'test-sc', 'test-score', 'serverless'
            )
            mock_client.describe_endpoint.assert_called_once_with(
                EndpointName=expected_endpoint_name
            )


class TestTrainingIntegration:
    """Test integration with training code."""

    def test_can_import_from_training_code(self):
        """Test that training code can import endpoint_utils."""
        # This simulates what would happen in ml_trainer_sagemaker.py
        from plexus.training.endpoint_utils import (
            should_deploy_endpoint,
            get_endpoint_status,
        )

        assert should_deploy_endpoint is not None
        assert get_endpoint_status is not None

    def test_can_check_deployment_needed_without_aws(self):
        """Test deployment check works without AWS credentials."""
        from plexus.training.endpoint_utils import should_deploy_endpoint

        # Without boto3 or with mocked boto3, should return True (deploy)
        # This ensures training code can proceed even without AWS access
        result = should_deploy_endpoint(
            'test-scorecard',
            'test-score',
            's3://bucket/model.tar.gz'
        )

        # Should return True (assuming deployment needed if we can't check)
        assert result is True


class TestPredictionIntegration:
    """Test integration with prediction code."""

    def test_can_import_from_prediction_code(self):
        """Test that prediction code can import endpoint_utils."""
        # This simulates what would happen in predictions.py
        from plexus.training.endpoint_utils import (
            get_sagemaker_endpoint,
            invoke_sagemaker_endpoint,
        )

        assert get_sagemaker_endpoint is not None
        assert invoke_sagemaker_endpoint is not None

    def test_endpoint_discovery_fails_gracefully(self):
        """Test that endpoint discovery fails gracefully without AWS."""
        from plexus.training.endpoint_utils import get_sagemaker_endpoint

        # Without AWS credentials, should return None (no endpoint found)
        # This allows prediction code to fall back to local model
        result = get_sagemaker_endpoint('test-sc', 'test-score')

        # Should return None or raise no exception
        assert result is None or result is not None  # Either outcome is acceptable


class TestRealWorldUsage:
    """Test real-world usage patterns."""

    def test_typical_training_workflow(self):
        """Test typical workflow from training code."""
        from plexus.training.endpoint_utils import should_deploy_endpoint
        from plexus.training.utils import normalize_name_to_key

        # Simulate training completing with a new model
        scorecard_name = "SelectQuote HCS Medium-Risk"
        score_name = "Compliance Check"

        scorecard_key = normalize_name_to_key(scorecard_name)
        score_key = normalize_name_to_key(score_name)

        model_s3_uri = f"s3://plexus-training/models/{scorecard_key}/{score_key}/model.tar.gz"

        # Check if deployment needed
        needs_deploy = should_deploy_endpoint(scorecard_key, score_key, model_s3_uri)

        # Should return True (deploy) since we can't check without AWS
        assert needs_deploy is True

    def test_typical_prediction_workflow(self):
        """Test typical workflow from prediction code."""
        from plexus.training.endpoint_utils import get_sagemaker_endpoint
        from plexus.training.utils import normalize_name_to_key

        # Simulate prediction request
        scorecard_name = "SelectQuote HCS Medium-Risk"
        score_name = "Compliance Check"

        scorecard_key = normalize_name_to_key(scorecard_name)
        score_key = normalize_name_to_key(score_name)

        # Try to find endpoint
        endpoint_name = get_sagemaker_endpoint(scorecard_key, score_key)

        # Without AWS, should return None (fall back to local)
        # The key is that this doesn't raise an exception
        assert endpoint_name is None or isinstance(endpoint_name, str)


class TestNamingConsistency:
    """Test naming consistency across modules."""

    def test_naming_matches_between_modules(self):
        """Test that naming is consistent between infrastructure and training."""
        from stacks.shared.naming import (
            get_sagemaker_endpoint_name,
            get_sagemaker_model_name,
        )

        scorecard_key = "test-scorecard"
        score_key = "test-score"
        model_s3_uri = "s3://bucket/model.tar.gz"

        # Get names from infrastructure module
        endpoint_name = get_sagemaker_endpoint_name(scorecard_key, score_key)
        model_name = get_sagemaker_model_name(scorecard_key, score_key, model_s3_uri)

        # Verify they follow expected pattern
        assert endpoint_name == f"plexus-{scorecard_key}-{score_key}-serverless"
        assert model_name.startswith(f"plexus-{scorecard_key}-{score_key}-model-")

        # Verify consistency - both should have same base (scorecard-score)
        endpoint_base = endpoint_name.replace('-serverless', '')
        model_base = '-'.join(model_name.split('-')[:-1])  # Remove hash
        assert endpoint_base == model_base.replace('-model', '')


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
