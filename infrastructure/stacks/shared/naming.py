"""
Centralized naming utilities for Plexus infrastructure resources.

Naming convention: plexus-{service}-{environment}-{resource}
Examples:
  - plexus-scoring-staging-queue
  - plexus-scoring-production-dlq
  - plexus-monitoring-staging-dashboard
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
    Generate stable SageMaker endpoint name (doesn't change with model updates).

    Pattern: plexus-{scorecard_key}-{score_key}-{deployment_type}
    Example: plexus-call-quality-compliance-check-serverless

    Args:
        scorecard_key: Normalized scorecard key (filesystem-safe)
        score_key: Normalized score key (filesystem-safe)
        deployment_type: Deployment type ('serverless' or 'realtime')

    Returns:
        Stable endpoint name for resource discovery
    """
    return f"plexus-{scorecard_key}-{score_key}-{deployment_type}"


def get_sagemaker_model_name(
    scorecard_key: str,
    score_key: str,
    model_s3_uri: str
) -> str:
    """
    Generate versioned SageMaker model name (includes hash of model S3 URI).

    Pattern: plexus-{scorecard_key}-{score_key}-{hash[:8]}
    Example: plexus-call-quality-compliance-check-a1b2c3d4

    Args:
        scorecard_key: Normalized scorecard key (filesystem-safe)
        score_key: Normalized score key (filesystem-safe)
        model_s3_uri: S3 URI to model.tar.gz

    Returns:
        Versioned model name (changes when model S3 URI changes)
    """
    uri_hash = hashlib.sha256(model_s3_uri.encode()).hexdigest()[:8]
    return f"plexus-{scorecard_key}-{score_key}-{uri_hash}"


def get_sagemaker_endpoint_config_name(
    scorecard_key: str,
    score_key: str,
    model_s3_uri: str
) -> str:
    """
    Generate versioned SageMaker endpoint config name (includes hash of model S3 URI).

    Pattern: plexus-{scorecard_key}-{score_key}-config-{hash[:8]}
    Example: plexus-call-quality-compliance-check-config-a1b2c3d4

    Args:
        scorecard_key: Normalized scorecard key (filesystem-safe)
        score_key: Normalized score key (filesystem-safe)
        model_s3_uri: S3 URI to model.tar.gz

    Returns:
        Versioned endpoint config name (changes when model S3 URI changes)
    """
    uri_hash = hashlib.sha256(model_s3_uri.encode()).hexdigest()[:8]
    return f"plexus-{scorecard_key}-{score_key}-config-{uri_hash}"
