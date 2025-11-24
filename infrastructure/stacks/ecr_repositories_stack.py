"""
Stack for ECR repositories used by Lambda functions.

This stack manages ECR repositories for Lambda container images.
Each environment gets its own repository for isolation.
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    Tags,
    aws_ecr as ecr,
)
from constructs import Construct
from .shared.constants import LAMBDA_SCORE_PROCESSOR_REPOSITORY_BASE


class EcrRepositoriesStack(Stack):
    """
    CDK Stack for ECR repositories.

    Creates ECR repositories for Lambda container images, one per environment.
    This stack should be deployed once before deploying pipelines.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs
    ) -> None:
        """
        Initialize the ECR repositories stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        # Add tags
        Tags.of(self).add("Service", "ecr-repositories")
        Tags.of(self).add("ManagedBy", "CDK")

        # Create ECR repository for staging
        self.staging_repository = self._create_repository("staging")

        # Create ECR repository for production
        self.production_repository = self._create_repository("production")

    def _create_repository(self, environment: str) -> ecr.Repository:
        """
        Create an ECR repository for a specific environment.

        Args:
            environment: Environment name ('staging' or 'production')

        Returns:
            ECR repository
        """
        return ecr.Repository(
            self,
            f"ScoreProcessor{environment.title()}Repository",
            repository_name=f"{LAMBDA_SCORE_PROCESSOR_REPOSITORY_BASE}-{environment}",
            image_scan_on_push=True,  # Enable vulnerability scanning
            lifecycle_rules=[
                # Remove untagged images after 1 day (highest priority)
                ecr.LifecycleRule(
                    description="Remove untagged images after 1 day",
                    max_image_age=Duration.days(1),
                    rule_priority=1,
                    tag_status=ecr.TagStatus.UNTAGGED
                ),
                # Keep last 10 images
                ecr.LifecycleRule(
                    description="Keep last 10 images",
                    max_image_count=10,
                    rule_priority=2
                )
            ],
            removal_policy=RemovalPolicy.RETAIN,  # Keep repo if stack is deleted
        )
