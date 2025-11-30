"""
Centralized naming utilities for Plexus infrastructure resources.

Naming convention: plexus-{service}-{environment}-{resource}
Examples:
  - plexus-scoring-staging-queue
  - plexus-scoring-production-dlq
  - plexus-monitoring-staging-dashboard

SageMaker naming convention: plexus-{scorecard_key}-{score_key}-{resource}
Examples:
  - plexus-selectquote-hcs-compliance-check-serverless
  - plexus-selectquote-hcs-compliance-check-model-abc123ef
  - plexus-selectquote-hcs-compliance-check-config-abc123ef
"""

import hashlib


def get_resource_name(service: str, environment: str, resource: str) -> str:
    """
    Generate a standardized resource name.

    Args:
        service: Service name (e.g., 'scoring', 'monitoring')
        environment: Environment name ('staging' or 'production')
        resource: Resource type (e.g., 'queue', 'dlq', 'topic')

    Returns:
        Formatted resource name following Plexus naming convention
    """
    return f"plexus-{service}-{environment}-{resource}"


def get_sagemaker_endpoint_name(
    scorecard_key: str,
    score_key: str,
    deployment_type: str = 'serverless'
) -> str:
    """
    Generate a standardized SageMaker endpoint name.

    The endpoint name is deterministic and stable - it doesn't change when
    the model is updated. This enables endpoint discovery without database lookups.

    Args:
        scorecard_key: Normalized scorecard key (filesystem-safe)
        score_key: Normalized score key (filesystem-safe)
        deployment_type: Deployment type ('serverless' or 'realtime')

    Returns:
        Endpoint name following convention: plexus-{scorecard_key}-{score_key}-{deployment_type}

    Example:
        >>> get_sagemaker_endpoint_name('selectquote-hcs', 'compliance-check')
        'plexus-selectquote-hcs-compliance-check-serverless'
    """
    return f"plexus-{scorecard_key}-{score_key}-{deployment_type}"


def get_sagemaker_model_name(
    scorecard_key: str,
    score_key: str,
    model_s3_uri: str
) -> str:
    """
    Generate a versioned SageMaker model name.

    The model name includes a hash of the S3 URI to ensure uniqueness when
    models are updated. This allows CDK to detect changes and update the
    endpoint configuration.

    Args:
        scorecard_key: Normalized scorecard key (filesystem-safe)
        score_key: Normalized score key (filesystem-safe)
        model_s3_uri: S3 URI to model.tar.gz

    Returns:
        Model name following convention: plexus-{scorecard_key}-{score_key}-model-{hash}

    Example:
        >>> get_sagemaker_model_name('selectquote-hcs', 'compliance-check',
        ...                          's3://bucket/models/selectquote-hcs/compliance-check/model.tar.gz')
        'plexus-selectquote-hcs-compliance-check-model-abc123ef'
    """
    model_hash = hashlib.md5(model_s3_uri.encode()).hexdigest()[:8]
    return f"plexus-{scorecard_key}-{score_key}-model-{model_hash}"


def get_sagemaker_endpoint_config_name(
    scorecard_key: str,
    score_key: str,
    model_s3_uri: str
) -> str:
    """
    Generate a versioned SageMaker endpoint configuration name.

    The config name includes a hash of the S3 URI to match the model version.
    This ensures the endpoint config is updated when the model changes.

    Args:
        scorecard_key: Normalized scorecard key (filesystem-safe)
        score_key: Normalized score key (filesystem-safe)
        model_s3_uri: S3 URI to model.tar.gz

    Returns:
        Endpoint config name following convention: plexus-{scorecard_key}-{score_key}-config-{hash}

    Example:
        >>> get_sagemaker_endpoint_config_name('selectquote-hcs', 'compliance-check',
        ...                                     's3://bucket/models/selectquote-hcs/compliance-check/model.tar.gz')
        'plexus-selectquote-hcs-compliance-check-config-abc123ef'
    """
    model_hash = hashlib.md5(model_s3_uri.encode()).hexdigest()[:8]
    return f"plexus-{scorecard_key}-{score_key}-config-{model_hash}"
