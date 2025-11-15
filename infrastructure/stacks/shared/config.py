"""
Shared configuration management for Plexus infrastructure.

This module provides utilities for loading environment-specific configuration
from AWS Systems Manager Parameter Store.
"""

from aws_cdk import (
    aws_ssm as ssm,
)
from constructs import Construct


class EnvironmentConfig:
    """
    Environment-specific configuration loaded from SSM Parameter Store.

    Configuration is stored in SSM with the following structure:
    /plexus/{environment}/config/{key}

    Example:
    /plexus/staging/config/account-key
    /plexus/staging/config/api-key
    /plexus/staging/config/api-url
    /plexus/production/config/account-key
    /plexus/production/config/api-key
    /plexus/production/config/api-url
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
        self.base_path = f"/plexus/{environment}/config"

    def get_parameter(self, key: str) -> str:
        """
        Get a configuration parameter from SSM Parameter Store.

        Args:
            key: Parameter key (e.g., 'account-key', 'api-url')

        Returns:
            Parameter value as a CDK token (resolved at deploy time)
        """
        parameter = ssm.StringParameter.from_string_parameter_name(
            self.scope,
            f"Param{key.replace('-', '').title()}",
            string_parameter_name=f"{self.base_path}/{key}"
        )
        return parameter.string_value

    def get_secret_parameter(self, key: str) -> str:
        """
        Get a secret configuration parameter from SSM Parameter Store (SecureString).

        Args:
            key: Parameter key (e.g., 'openai-api-key', 'postgres-uri')

        Returns:
            Parameter value as a CDK token (resolved at deploy time)
        """
        parameter = ssm.StringParameter.from_secure_string_parameter_attributes(
            self.scope,
            f"SecretParam{key.replace('-', '').title()}",
            parameter_name=f"{self.base_path}/{key}",
            version=1  # Use latest version
        )
        return parameter.string_value