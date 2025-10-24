"""
Base deployment pipeline for Plexus infrastructure.

This provides shared pipeline logic for both staging and production environments.
"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    pipelines as pipelines,
    aws_codebuild as codebuild,
    SecretValue,
)
from constructs import Construct
from stacks.scoring_worker_stack import ScoringWorkerStack


class BasePipelineStack(Stack):
    """
    Base CDK Pipeline for infrastructure deployments.

    Provides common pipeline configuration that can be customized per environment.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        branch: str,
        github_owner: str = "AnthusAI",
        github_repo: str = "Plexus",
        **kwargs
    ) -> None:
        """
        Initialize the infrastructure pipeline.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            environment: Environment name ('staging' or 'production')
            branch: Git branch to watch ('staging' or 'main')
            github_owner: GitHub organization/owner name
            github_repo: GitHub repository name
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        # Use GitHub token from Secrets Manager
        source = pipelines.CodePipelineSource.git_hub(
            f"{github_owner}/{github_repo}",
            branch,
            authentication=SecretValue.secrets_manager("github-token")
        )

        # Create the pipeline
        pipeline = pipelines.CodePipeline(
            self,
            "Pipeline",
            pipeline_name=f"plexus-infrastructure-{environment}-pipeline",
            synth=pipelines.ShellStep(
                "Synth",
                input=source,
                commands=[
                    "cd infrastructure",
                    "pip install -r requirements.txt",
                    "npx cdk synth"
                ],
                primary_output_directory="infrastructure/cdk.out"
            ),
            code_build_defaults=pipelines.CodeBuildOptions(
                build_environment=codebuild.BuildEnvironment(
                    build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                )
            )
        )

        # Add deployment stage with all stacks
        deployment_stage = DeploymentStage(
            self,
            f"{environment.title()}Deployment",
            environment=environment,
            env=kwargs.get("env")
        )
        pipeline.add_stage(deployment_stage)


class DeploymentStage(cdk.Stage):
    """
    Deployment stage containing all infrastructure stacks.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        **kwargs
    ) -> None:
        """
        Initialize the deployment stage.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stage
            environment: Environment name ('staging' or 'production')
            **kwargs: Additional stage properties
        """
        super().__init__(scope, construct_id, **kwargs)

        # Deploy scoring worker stack
        ScoringWorkerStack(
            self,
            "ScoringWorker",
            environment=environment,
            env=kwargs.get("env")
        )

        # Future stacks will be added here:
        # MonitoringStack(self, "Monitoring", environment=environment, env=kwargs.get("env"))
        # DataPipelineStack(self, "DataPipeline", environment=environment, env=kwargs.get("env"))
