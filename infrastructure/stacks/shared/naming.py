"""
Centralized naming utilities for Plexus infrastructure resources.

Naming convention: plexus-{service}-{environment}-{resource}
Examples:
  - plexus-scoring-staging-queue
  - plexus-scoring-production-dlq
  - plexus-monitoring-staging-dashboard

SageMaker naming convention (hybrid hash + truncation):
  plexus-{env_abbrev}-{hash}-{scorecard_trunc}-{score_trunc}-{resource}

Examples:
  - plexus-dev-a7f3c2d1-aw-confirm-accurate-d-realtime
  - plexus-staging-a7f3c2d1-aw-confirm-accurate-d-realtime-adapter
  - plexus-prod-a7f3c2d1-aw-confirm-accurate-d-model

This pattern ensures:
  - Names always fit within 63-character SageMaker limits
  - Hash provides uniqueness (SHA256, 8 chars = ~16 trillion combinations)
  - Truncated names provide human readability
  - Full names stored in CloudFormation tags for discovery
"""

import hashlib
from typing import Dict, Any


def _abbreviate_environment(environment: str) -> str:
    """
    Abbreviate environment name for resource naming.

    Args:
        environment: Full environment name

    Returns:
        Abbreviated environment (staging stays full for clarity)
    """
    env_map = {
        'development': 'dev',
        'staging': 'staging',  # Keep full name for clarity
        'production': 'prod'
    }
    return env_map.get(environment, environment)


def _generate_resource_hash(scorecard_key: str, score_key: str) -> str:
    """
    Generate deterministic 8-character hash for resource uniqueness.

    Args:
        scorecard_key: Normalized scorecard key
        score_key: Normalized score key

    Returns:
        8-character hex hash (provides ~16 trillion unique combinations)
    """
    hash_input = f"{scorecard_key}-{score_key}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:8]


def _truncate_name(name: str, max_length: int = 10) -> str:
    """
    Truncate name to fit within character budget.

    Args:
        name: Original name
        max_length: Maximum length (default: 10 chars)

    Returns:
        Truncated name
    """
    return name[:max_length]


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
    deployment_type: str = 'serverless',
    environment: str = 'development'
) -> str:
    """
    Generate stable SageMaker endpoint name with hash + truncation.

    Pattern: plexus-{env_abbrev}-{hash}-{scorecard_trunc}-{score_trunc}-{type}
    Example: plexus-dev-a7f3c2d1-aw-confirm-accurate-d-realtime

    Budget analysis (worst case with staging + realtime):
      plexus-staging-{hash8}-{scorecard10}-{score10}-realtime = 55 chars
      Component suffix adds: -base (5) or -adapter (8) = 60-63 chars

    Args:
        scorecard_key: Normalized scorecard key (filesystem-safe)
        score_key: Normalized score key (filesystem-safe)
        deployment_type: Deployment type ('serverless' or 'realtime')
        environment: Environment name ('development', 'staging', 'production')

    Returns:
        Stable endpoint name guaranteed to fit within 63-char limit
    """
    # Replace underscores with hyphens for SageMaker compatibility
    scorecard_key = scorecard_key.replace('_', '-')
    score_key = score_key.replace('_', '-')

    # Generate components
    env_abbrev = _abbreviate_environment(environment)
    resource_hash = _generate_resource_hash(scorecard_key, score_key)
    scorecard_trunc = _truncate_name(scorecard_key, 10)
    score_trunc = _truncate_name(score_key, 10)

    return f"plexus-{env_abbrev}-{resource_hash}-{scorecard_trunc}-{score_trunc}-{deployment_type}"


def get_sagemaker_model_name(
    scorecard_key: str,
    score_key: str,
    model_s3_uri: str,
    environment: str = 'development'
) -> str:
    """
    Generate versioned SageMaker model name with hash + truncation.

    Pattern: plexus-{env_abbrev}-{resource_hash}-{scorecard_trunc}-{score_trunc}-{model_hash}
    Example: plexus-dev-a7f3c2d1-aw-confirm-accurate-d-b4e8f2a9

    Args:
        scorecard_key: Normalized scorecard key (filesystem-safe)
        score_key: Normalized score key (filesystem-safe)
        model_s3_uri: S3 URI to model.tar.gz
        environment: Environment name ('development', 'staging', 'production')

    Returns:
        Versioned model name (changes when model S3 URI changes)
    """
    # Replace underscores with hyphens for SageMaker compatibility
    scorecard_key = scorecard_key.replace('_', '-')
    score_key = score_key.replace('_', '-')

    # Generate components
    env_abbrev = _abbreviate_environment(environment)
    resource_hash = _generate_resource_hash(scorecard_key, score_key)
    scorecard_trunc = _truncate_name(scorecard_key, 10)
    score_trunc = _truncate_name(score_key, 10)
    model_hash = hashlib.sha256(model_s3_uri.encode()).hexdigest()[:8]

    return f"plexus-{env_abbrev}-{resource_hash}-{scorecard_trunc}-{score_trunc}-{model_hash}"


def get_sagemaker_endpoint_config_name(
    scorecard_key: str,
    score_key: str,
    model_s3_uri: str,
    environment: str = 'development'
) -> str:
    """
    Generate versioned SageMaker endpoint config name with hash + truncation.

    Pattern: plexus-{env_abbrev}-{resource_hash}-{scorecard_trunc}-{score_trunc}-config-{model_hash}
    Example: plexus-dev-a7f3c2d1-aw-confirm-accurate-d-config-b4e8f2a9

    Args:
        scorecard_key: Normalized scorecard key (filesystem-safe)
        score_key: Normalized score key (filesystem-safe)
        model_s3_uri: S3 URI to model.tar.gz
        environment: Environment name ('development', 'staging', 'production')

    Returns:
        Versioned endpoint config name (changes when model S3 URI changes)
    """
    # Replace underscores with hyphens for SageMaker compatibility
    scorecard_key = scorecard_key.replace('_', '-')
    score_key = score_key.replace('_', '-')

    # Generate components
    env_abbrev = _abbreviate_environment(environment)
    resource_hash = _generate_resource_hash(scorecard_key, score_key)
    scorecard_trunc = _truncate_name(scorecard_key, 10)
    score_trunc = _truncate_name(score_key, 10)
    model_hash = hashlib.sha256(model_s3_uri.encode()).hexdigest()[:8]

    return f"plexus-{env_abbrev}-{resource_hash}-{scorecard_trunc}-{score_trunc}-config-{model_hash}"


def get_sagemaker_resource_metadata(
    scorecard_key: str,
    score_key: str,
    environment: str = 'development'
) -> Dict[str, Any]:
    """
    Generate metadata dict for CloudFormation tags and outputs.

    This provides full names and identifiers for resource discovery when
    truncated names are used in actual resource names.

    Args:
        scorecard_key: Normalized scorecard key (filesystem-safe)
        score_key: Normalized score key (filesystem-safe)
        environment: Environment name ('development', 'staging', 'production')

    Returns:
        Dict with full names, truncated names, hash, and environment info
    """
    # Replace underscores with hyphens
    scorecard_key_normalized = scorecard_key.replace('_', '-')
    score_key_normalized = score_key.replace('_', '-')

    return {
        'environment': environment,
        'env_abbrev': _abbreviate_environment(environment),
        'resource_hash': _generate_resource_hash(scorecard_key_normalized, score_key_normalized),
        'scorecard_key': scorecard_key_normalized,
        'score_key': score_key_normalized,
        'scorecard_trunc': _truncate_name(scorecard_key_normalized, 10),
        'score_trunc': _truncate_name(score_key_normalized, 10)
    }
