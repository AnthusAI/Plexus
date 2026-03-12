"""
Staging deployment pipeline for Plexus infrastructure.

This pipeline watches the 'staging' branch and automatically deploys
infrastructure changes to the staging environment.
"""

from constructs import Construct
from .base_pipeline import BasePipelineStack


class StagingPipelineStack(BasePipelineStack):
    """
    CDK Pipeline for staging environment deployments.

    Watches the 'staging' branch and deploys all infrastructure stacks
    to the staging environment when changes are pushed.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        github_owner: str = "AnthusAI",
        github_repo: str = "Plexus",
        **kwargs
    ) -> None:
        """
        Initialize the staging pipeline.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            github_owner: GitHub organization/owner name
            github_repo: GitHub repository name
            **kwargs: Additional stack properties
        """
        super().__init__(
            scope,
            construct_id,
            environment="staging",
            branch="staging",
            github_owner=github_owner,
            github_repo=github_repo,
            **kwargs
        )
