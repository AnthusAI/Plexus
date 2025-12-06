"""
Base deployment pipeline for Plexus infrastructure.

This provides shared pipeline logic for both staging and production environments.
"""

import aws_cdk as cdk
import os
import boto3
from aws_cdk import (
    Stack,
    pipelines as pipelines,
    aws_codebuild as codebuild,
    aws_ecr as ecr,
    aws_iam as iam,
)
from constructs import Construct
from stacks.scoring_worker_stack import ScoringWorkerStack
from stacks.lambda_score_processor_stack import LambdaScoreProcessorStack
from stacks.metrics_aggregation_stack import MetricsAggregationStack
from stacks.command_worker_stack import CommandWorkerStack
from stacks.shared.constants import LAMBDA_SCORE_PROCESSOR_REPOSITORY_BASE


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

        # Fetch GitHub CodeConnection ARN from SSM Parameter Store at synth time
        # This avoids storing the ARN in the repository
        # Create the parameter with: aws ssm put-parameter --name /plexus/github-connection-arn --value "arn:aws:..." --type String
        ssm = boto3.client('ssm', region_name=kwargs.get('env').region if kwargs.get('env') else 'us-west-2')
        try:
            response = ssm.get_parameter(Name='/plexus/github-connection-arn')
            connection_arn = response['Parameter']['Value']
        except Exception as e:
            raise ValueError(
                f"Failed to fetch GitHub connection ARN from SSM Parameter Store: {e}\n"
                "Create it with: aws ssm put-parameter --name /plexus/github-connection-arn "
                "--value 'arn:aws:codeconnections:us-west-2:ACCOUNT:connection/ID' --type String"
            )

        # Use CodeConnection for GitHub source (no automatic webhook triggers)
        # Pipeline will only run when manually triggered (e.g., by GitHub Actions)
        source = pipelines.CodePipelineSource.connection(
            f"{github_owner}/{github_repo}",
            branch,
            connection_arn=connection_arn,
            trigger_on_push=False  # Disable automatic triggers - GitHub Actions will trigger it
        )

        # Reference ECR repository (created in separate EcrRepositoriesStack)
        # Must be deployed first: cdk deploy plexus-ecr-repositories
        ecr_repository_name = f"{LAMBDA_SCORE_PROCESSOR_REPOSITORY_BASE}-{environment}"
        ecr_repository = ecr.Repository.from_repository_name(
            self,
            "LambdaEcrRepository",
            repository_name=ecr_repository_name
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
                    # Build Lambda functions (metrics aggregator, etc.) before CDK synth
                    "./build_lambda.sh",
                    "npx cdk synth"
                ],
                primary_output_directory="infrastructure/cdk.out"
            ),
            code_build_defaults=pipelines.CodeBuildOptions(
                build_environment=codebuild.BuildEnvironment(
                    build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                    privileged=True,  # Required for Docker builds
                ),
                role_policy=[
                    # Grant permission to read GitHub connection ARN from SSM
                    iam.PolicyStatement(
                        actions=["ssm:GetParameter"],
                        resources=[f"arn:aws:ssm:{kwargs.get('env').region if kwargs.get('env') else 'us-west-2'}:{kwargs.get('env').account if kwargs.get('env') else '*'}:parameter/plexus/github-connection-arn"]
                    )
                ]
            ),
            docker_enabled_for_synth=True,  # Enable Docker for the synth step
        )

        # Add Docker build step before deployment
        docker_build_step = pipelines.CodeBuildStep(
            "BuildLambdaImage",
            input=source,
            commands=[
                # Login to Docker Hub to avoid rate limits on base image pulls
                "export DOCKERHUB_USERNAME=$(aws secretsmanager get-secret-value --secret-id dockerhub-credentials --query SecretString --output text | jq -r .username)",
                "export DOCKERHUB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id dockerhub-credentials --query SecretString --output text | jq -r .password)",
                "echo $DOCKERHUB_PASSWORD | docker login --username $DOCKERHUB_USERNAME --password-stdin",
                # Login to ECR
                f"aws ecr get-login-password --region {kwargs.get('env').region if kwargs.get('env') else 'us-west-2'} | docker login --username AWS --password-stdin {ecr_repository.repository_uri.split('/')[0]}",
                # Build and push Docker image with proper flags for Lambda
                f"docker buildx build --platform linux/amd64 --provenance=false --push -f score-processor-lambda/Dockerfile -t {ecr_repository.repository_uri}:latest ."
            ],
            build_environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True,  # Required for Docker builds
            ),
            role_policy_statements=[
                # Grant permissions to push to ECR
                iam.PolicyStatement(
                    actions=[
                        "ecr:GetAuthorizationToken",
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage",
                        "ecr:PutImage",
                        "ecr:InitiateLayerUpload",
                        "ecr:UploadLayerPart",
                        "ecr:CompleteLayerUpload"
                    ],
                    resources=[ecr_repository.repository_arn]
                ),
                # Grant permission to get ECR auth token
                iam.PolicyStatement(
                    actions=["ecr:GetAuthorizationToken"],
                    resources=["*"]
                ),
                # Grant permission to read Docker Hub credentials from Secrets Manager
                iam.PolicyStatement(
                    actions=["secretsmanager:GetSecretValue"],
                    resources=["arn:aws:secretsmanager:*:*:secret:dockerhub-credentials-*"]
                )
            ]
        )

        # Add deployment stage with all stacks
        # Note: We can't pass the repository object across stage boundaries,
        # so we pass the repository name as a string instead
        deployment_stage = DeploymentStage(
            self,
            f"{environment.title()}Deployment",
            environment=environment,
            ecr_repository_name=ecr_repository.repository_name,  # Pass name, not object
            env=kwargs.get("env")
        )

        # Add deployment stage with Docker build as pre-step
        # App deployment is now handled by separate app deployment pipeline
        pipeline.add_stage(
            deployment_stage,
            pre=[docker_build_step]  # Build Docker image before deploying infrastructure
        )


class DeploymentStage(cdk.Stage):
    """
    Deployment stage containing all infrastructure stacks.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        ecr_repository_name: str,
        **kwargs
    ) -> None:
        """
        Initialize the deployment stage.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stage
            environment: Environment name ('staging' or 'production')
            ecr_repository_name: Name of the ECR repository for Lambda images
            **kwargs: Additional stage properties
        """
        super().__init__(scope, construct_id, **kwargs)

        # Deploy Lambda score processor stack (with SQS queues)
        # Only deploy in production - staging can't use Lambda due to reserved concurrency limits
        if environment == "production":
            # Deploy scoring worker stack (creates SQS queues) - only for production
            scoring_worker_stack = ScoringWorkerStack(
                self,
                "ScoringWorker",
                environment=environment,
                stack_name=f"plexus-scoring-worker-{environment}",
                env=kwargs.get("env")
            )

            LambdaScoreProcessorStack(
                self,
                "LambdaScoreProcessor",
                environment=environment,
                ecr_repository_name=ecr_repository_name,  # Pass repository name to look up
                standard_request_queue=scoring_worker_stack.standard_request_queue,
                response_queue_url=scoring_worker_stack.response_queue.queue_url,
                stack_name=f"plexus-lambda-score-processor-{environment}",
                env=kwargs.get("env")
            )

        # Deploy metrics aggregation stack (processes DynamoDB streams)
        # Only deploy in production - staging doesn't need metrics aggregation
        if environment == "production":
            MetricsAggregationStack(
                self,
                "MetricsAggregation",
                environment=environment,
                stack_name=f"plexus-metrics-aggregation-{environment}",
                env=kwargs.get("env")
            )

        # Deploy command worker stack (manages EC2 command worker configuration)
        # Only deploy in production - staging doesn't need command worker
        if environment == "production":
            CommandWorkerStack(
                self,
                "CommandWorker",
                environment=environment,
                stack_name=f"plexus-command-worker-{environment}",
                env=kwargs.get("env")
            )

        # Future stacks will be added here:
        # MonitoringStack(
        #     self,
        #     "Monitoring",
        #     environment=environment,
        #     stack_name=f"plexus-monitoring-{environment}",
        #     env=kwargs.get("env")
        # )
