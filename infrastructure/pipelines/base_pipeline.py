"""
Base deployment pipeline for Plexus infrastructure.

This provides shared pipeline logic for both staging and production environments.
"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    pipelines as pipelines,
    aws_codebuild as codebuild,
    aws_ecr as ecr,
    aws_iam as iam,
    SecretValue,
)
from constructs import Construct
from stacks.scoring_worker_stack import ScoringWorkerStack
from stacks.lambda_score_processor_stack import LambdaScoreProcessorStack
from stacks.lambda_fanout_stack import LambdaFanoutStack
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

        # Use GitHub token from Secrets Manager
        source = pipelines.CodePipelineSource.git_hub(
            f"{github_owner}/{github_repo}",
            branch,
            authentication=SecretValue.secrets_manager("github-token")
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
                    "npx cdk synth"
                ],
                primary_output_directory="infrastructure/cdk.out"
            ),
            code_build_defaults=pipelines.CodeBuildOptions(
                build_environment=codebuild.BuildEnvironment(
                    build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                    privileged=True,  # Required for Docker builds
                )
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
                # Push to both latest tag and commit SHA tag
                "export GIT_COMMIT_SHA=$(git rev-parse --short HEAD)",
                f"docker buildx build --platform linux/amd64 --provenance=false --push -f score-processor-lambda/Dockerfile -t {ecr_repository.repository_uri}:$GIT_COMMIT_SHA -t {ecr_repository.repository_uri}:latest ."
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

        # Add deployment stage with Docker build as a pre-step
        pipeline.add_stage(
            deployment_stage,
            pre=[docker_build_step]  # Build Docker image before deploying
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

        # Deploy scoring worker stack (creates SQS queues)
        scoring_worker_stack = ScoringWorkerStack(
            self,
            "ScoringWorker",
            environment=environment,
            stack_name=f"plexus-scoring-worker-{environment}",
            env=kwargs.get("env")
        )

        # Deploy Lambda score processor stack (uses the same queues)
        # Configuration is loaded from SSM Parameter Store by the stack
        lambda_score_processor_stack = LambdaScoreProcessorStack(
            self,
            "LambdaScoreProcessor",
            environment=environment,
            ecr_repository_name=ecr_repository_name,  # Pass repository name to look up
            standard_request_queue_url=scoring_worker_stack.standard_request_queue.queue_url,
            response_queue_url=scoring_worker_stack.response_queue.queue_url,
            stack_name=f"plexus-lambda-score-processor-{environment}",
            env=kwargs.get("env")
        )

        # Deploy fan-out Lambda stack (for controlled rollout)
        LambdaFanoutStack(
            self,
            "LambdaFanout",
            environment=environment,
            score_processor_lambda_arn=lambda_score_processor_stack.lambda_function.function_arn,
            request_queue=scoring_worker_stack.standard_request_queue,
            stack_name=f"plexus-lambda-fanout-{environment}",
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
