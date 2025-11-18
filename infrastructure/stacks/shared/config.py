"""
Shared configuration management for Plexus infrastructure.

This module provides utilities for loading environment-specific configuration
from AWS Secrets Manager.
"""

from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class EnvironmentConfig:
    """
    Environment-specific configuration loaded from AWS Secrets Manager.

    All configuration (both sensitive and non-sensitive) is stored in a single
    JSON secret with the naming pattern: plexus/{environment}/config

    Example secret names:
    - plexus/staging/config
    - plexus/production/config

    Example secret structure:
    {
        "account-key": "...",
        "api-key": "...",
        "api-url": "...",
        "postgres-uri": "...",
        "openai-api-key": "...",
        "score-result-attachments-bucket": "...",
        "report-block-details-bucket": "..."
    }
    """

    def __init__(self, scope: Construct, environment: str):
        """
        Initialize environment configuration.

        Args:
            scope: CDK construct scope
            environment: Environment name ('staging' or 'production')
        """
        self.scope = scope
        self.environment = environment
        self.secret_name = f"plexus/{environment}/config"

        # Look up the secret (must exist before deployment)
        self.secret = secretsmanager.Secret.from_secret_name_v2(
            scope,
            "PlexusConfig",
            secret_name=self.secret_name
        )

    def get_value(self, key: str) -> str:
        """
        Get a configuration value from the secret.

        Args:
            key: Configuration key (e.g., 'account-key', 'api-url', 'openai-api-key')

        Returns:
            Secret value as a CDK token (resolved at deploy time)
        """
        return self.secret.secret_value_from_json(key).unsafe_unwrap()