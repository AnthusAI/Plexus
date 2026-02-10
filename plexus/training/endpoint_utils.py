"""
Endpoint utilities for SageMaker inference.

This module provides helper functions for discovering and managing SageMaker
endpoints using convention-over-configuration naming patterns.
"""

import os
import logging
from typing import Optional, Dict, Any

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    ClientError = None
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)


def get_sagemaker_endpoint(
    scorecard_key: str,
    score_key: str,
    deployment_type: str = 'serverless'
) -> Optional[str]:
    """
    Check if a SageMaker endpoint exists and is InService.

    Uses convention-based naming to construct the expected endpoint name,
    then queries the AWS SageMaker API to check if it exists and is ready.
    This avoids the need for database lookups.

    Args:
        scorecard_key: Normalized scorecard key (filesystem-safe)
        score_key: Normalized score key (filesystem-safe)
        deployment_type: Deployment type ('serverless' or 'realtime')

    Returns:
        Endpoint name if InService, None otherwise

    Example:
        >>> endpoint = get_sagemaker_endpoint('selectquote-hcs', 'compliance-check')
        >>> if endpoint:
        ...     print(f"Found endpoint: {endpoint}")
        ... else:
        ...     print("No endpoint found, will use local model")
    """
    if not BOTO3_AVAILABLE:
        logger.warning("boto3 not available, cannot check for SageMaker endpoints")
        return None

    # Get environment from env vars (PLEXUS_ENVIRONMENT or environment from .env file)
    environment = os.getenv('PLEXUS_ENVIRONMENT', os.getenv('environment', 'development'))

    # Import naming function from infrastructure
    try:
        from infrastructure.stacks.shared.naming import get_sagemaker_endpoint_name
        endpoint_name = get_sagemaker_endpoint_name(scorecard_key, score_key, deployment_type, environment)
    except ImportError:
        # Fallback to inline construction if infrastructure not in path
        endpoint_name = f"plexus-{environment}-{scorecard_key}-{score_key}-{deployment_type}"

    try:
        # Get AWS region from environment
        region = os.getenv('AWS_DEFAULT_REGION', os.getenv('AWS_REGION', 'us-east-1'))
        client = boto3.client('sagemaker', region_name=region)

        response = client.describe_endpoint(EndpointName=endpoint_name)

        status = response['EndpointStatus']
        if status == 'InService':
            logger.info(f"Found SageMaker endpoint: {endpoint_name} (status: {status})")
            return endpoint_name
        else:
            logger.warning(
                f"Endpoint {endpoint_name} exists but is not InService (status: {status})"
            )
            return None

    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException':
            # Endpoint doesn't exist
            logger.info(f"No endpoint found: {endpoint_name}")
            return None
        else:
            logger.error(f"Error checking endpoint {endpoint_name}: {e}")
            return None
    except Exception as e:
        logger.error(f"Unexpected error checking endpoint {endpoint_name}: {e}")
        return None


def should_deploy_endpoint(
    scorecard_key: str,
    score_key: str,
    new_model_s3_uri: str,
    deployment_type: str = 'serverless'
) -> bool:
    """
    Check if endpoint deployment is needed.

    Compares the current endpoint's model S3 URI with the new model URI
    to determine if an update is required.

    Args:
        scorecard_key: Normalized scorecard key
        score_key: Normalized score key
        new_model_s3_uri: S3 URI to new model.tar.gz
        deployment_type: Deployment type ('serverless' or 'realtime')

    Returns:
        True if deployment needed, False if endpoint already up-to-date

    Example:
        >>> if should_deploy_endpoint('selectquote-hcs', 'compliance-check', 's3://...'):
        ...     print("Deploying updated model")
        ... else:
        ...     print("Endpoint already up-to-date")
    """
    if not BOTO3_AVAILABLE:
        logger.warning("boto3 not available, cannot check endpoint status")
        return True  # Assume deployment needed if we can't check

    # Get environment from env vars (PLEXUS_ENVIRONMENT or environment from .env file)
    environment = os.getenv('PLEXUS_ENVIRONMENT', os.getenv('environment', 'development'))

    # Import naming function
    try:
        from infrastructure.stacks.shared.naming import get_sagemaker_endpoint_name
        endpoint_name = get_sagemaker_endpoint_name(scorecard_key, score_key, deployment_type, environment)
    except ImportError:
        endpoint_name = f"plexus-{environment}-{scorecard_key}-{score_key}-{deployment_type}"

    try:
        region = os.getenv('AWS_DEFAULT_REGION', os.getenv('AWS_REGION', 'us-east-1'))
        client = boto3.client('sagemaker', region_name=region)

        # Get endpoint details
        endpoint = client.describe_endpoint(EndpointName=endpoint_name)

        # Get current model URI
        config_name = endpoint['EndpointConfigName']
        config = client.describe_endpoint_config(EndpointConfigName=config_name)
        model_name = config['ProductionVariants'][0]['ModelName']
        model = client.describe_model(ModelName=model_name)
        current_uri = model['PrimaryContainer']['ModelDataUrl']

        if current_uri == new_model_s3_uri:
            logger.info(f"Endpoint {endpoint_name} already uses {new_model_s3_uri}")
            return False
        else:
            logger.info(
                f"Endpoint {endpoint_name} needs update: "
                f"{current_uri} → {new_model_s3_uri}"
            )
            return True

    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException':
            # Endpoint doesn't exist, so deployment is needed
            logger.info(f"Endpoint {endpoint_name} does not exist, deployment needed")
            return True
        else:
            logger.error(f"Error checking endpoint status: {e}")
            return True  # Assume deployment needed on error
    except Exception as e:
        logger.error(f"Unexpected error checking endpoint status: {e}")
        return True  # Assume deployment needed on error


def get_endpoint_status(
    scorecard_key: str,
    score_key: str,
    deployment_type: str = 'serverless'
) -> Optional[Dict[str, Any]]:
    """
    Get detailed status information about an endpoint.

    Args:
        scorecard_key: Normalized scorecard key
        score_key: Normalized score key
        deployment_type: Deployment type ('serverless' or 'realtime')

    Returns:
        Dictionary with endpoint details, or None if endpoint doesn't exist:
            - endpoint_name: Name of the endpoint
            - status: Current status (InService, Creating, Failed, etc.)
            - creation_time: When endpoint was created
            - last_modified_time: When endpoint was last updated
            - model_s3_uri: S3 URI to current model
            - endpoint_arn: ARN of the endpoint

    Example:
        >>> status = get_endpoint_status('selectquote-hcs', 'compliance-check')
        >>> if status:
        ...     print(f"Status: {status['status']}")
        ...     print(f"Model: {status['model_s3_uri']}")
    """
    if not BOTO3_AVAILABLE:
        logger.warning("boto3 not available")
        return None

    # Get environment from env vars (PLEXUS_ENVIRONMENT or environment from .env file)
    environment = os.getenv('PLEXUS_ENVIRONMENT', os.getenv('environment', 'development'))

    try:
        from infrastructure.stacks.shared.naming import get_sagemaker_endpoint_name
        endpoint_name = get_sagemaker_endpoint_name(scorecard_key, score_key, deployment_type, environment)
    except ImportError:
        endpoint_name = f"plexus-{environment}-{scorecard_key}-{score_key}-{deployment_type}"

    try:
        region = os.getenv('AWS_DEFAULT_REGION', os.getenv('AWS_REGION', 'us-east-1'))
        client = boto3.client('sagemaker', region_name=region)

        # Get endpoint details
        endpoint = client.describe_endpoint(EndpointName=endpoint_name)

        # Get model details
        config_name = endpoint['EndpointConfigName']
        config = client.describe_endpoint_config(EndpointConfigName=config_name)
        model_name = config['ProductionVariants'][0]['ModelName']
        model = client.describe_model(ModelName=model_name)
        model_s3_uri = model['PrimaryContainer']['ModelDataUrl']

        return {
            'endpoint_name': endpoint_name,
            'status': endpoint['EndpointStatus'],
            'creation_time': endpoint.get('CreationTime'),
            'last_modified_time': endpoint.get('LastModifiedTime'),
            'model_s3_uri': model_s3_uri,
            'endpoint_arn': endpoint['EndpointArn'],
        }

    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException':
            logger.info(f"Endpoint {endpoint_name} does not exist")
            return None
        else:
            logger.error(f"Error getting endpoint status: {e}")
            return None
    except Exception as e:
        logger.error(f"Unexpected error getting endpoint status: {e}")
        return None


def invoke_sagemaker_endpoint(
    endpoint_name: str,
    payload: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Invoke a SageMaker endpoint for inference.

    Args:
        endpoint_name: Name of the endpoint to invoke
        payload: Input data for inference (will be JSON-serialized)

    Returns:
        Prediction result dictionary, or None on error

    Example:
        >>> result = invoke_sagemaker_endpoint(
        ...     'plexus-selectquote-hcs-compliance-check-serverless',
        ...     {'text': 'Call transcript here...'}
        ... )
        >>> if result:
        ...     print(f"Prediction: {result['value']}")
    """
    if not BOTO3_AVAILABLE:
        logger.error("boto3 not available, cannot invoke endpoint")
        return None

    try:
        import json
    except ImportError:
        logger.error("json not available")
        return None

    try:
        region = os.getenv('AWS_DEFAULT_REGION', os.getenv('AWS_REGION', 'us-east-1'))
        runtime = boto3.client('sagemaker-runtime', region_name=region)

        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='application/json',
            Body=json.dumps(payload)
        )

        result = json.loads(response['Body'].read())
        return result

    except ClientError as e:
        logger.error(f"Error invoking endpoint {endpoint_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error invoking endpoint {endpoint_name}: {e}")
        return None
