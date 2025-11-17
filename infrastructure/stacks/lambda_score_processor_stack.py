"""
Stack for Lambda-based score processor.

This stack manages the Lambda function that processes scoring jobs from SQS queues.
The function uses a container image built from the score-processor-lambda directory.
"""

import os
from datetime import datetime
from aws_cdk import (
    Stack,
    Duration,
    Tags,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_ecr as ecr,
)
from constructs import Construct
from .shared.naming import get_resource_name
from .shared.config import EnvironmentConfig


class LambdaScoreProcessorStack(Stack):
    """
    CDK Stack for Lambda-based score processor.

    Creates a Lambda function that processes scoring jobs from SQS queues using
    a container image stored in ECR.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        ecr_repository_name: str,
        standard_request_queue_url: str,
        response_queue_url: str,
        **kwargs
    ) -> None:
        """
        Initialize the Lambda score processor stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            environment: Environment name ('staging' or 'production')
            ecr_repository_name: Name of ECR repository containing Lambda container image
            standard_request_queue_url: SQS queue URL for incoming requests
            response_queue_url: SQS queue URL for responses
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = environment

        # Add environment tags
        Tags.of(self).add("Environment", environment)
        Tags.of(self).add("Service", "lambda-score-processor")
        Tags.of(self).add("ManagedBy", "CDK")

        # Load environment-specific configuration from Secrets Manager
        config = EnvironmentConfig(self, environment)

        # Look up ECR repository by name (created by pipeline)
        ecr_repository = ecr.Repository.from_repository_name(
            self,
            "ScoreProcessorRepository",
            repository_name=ecr_repository_name
        )

        # Create IAM role for Lambda
        lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            role_name=get_resource_name("lambda", self.env_name, "score-processor-role"),
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                # Basic Lambda execution (CloudWatch Logs)
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
                # DynamoDB access for ScoringJob and ScoreResult
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonDynamoDBFullAccess"
                ),
                # S3 access for attachments and report blocks
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonS3FullAccess"
                ),
                # SQS access for polling and sending messages
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSQSFullAccess"
                ),
                # CloudWatch access for custom metrics
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "CloudWatchFullAccess"
                ),
            ]
        )

        # Grant read access to Secrets Manager
        config.secret.grant_read(lambda_role)

        # Get deployment timestamp to force Lambda updates
        # This ensures Lambda pulls the latest image even when using 'latest' tag
        deployment_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S")

        # Create Lambda function with container image
        # Note: The image must be built and pushed to ECR before deployment
        # This is handled by the pipeline's Docker build step
        self.lambda_function = lambda_.DockerImageFunction(
            self,
            "ScoreProcessorFunction",
            function_name=get_resource_name("lambda", self.env_name, "score-processor"),
            code=lambda_.DockerImageCode.from_ecr(
                repository=ecr_repository,  # Direct reference from pipeline
                tag_or_digest="latest"
            ),
            role=lambda_role,
            timeout=Duration.seconds(300),  # 5 minutes
            memory_size=2048,
            environment={
                # SQS Queue URLs (from ScoringWorkerStack)
                "PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL": standard_request_queue_url,
                "PLEXUS_RESPONSE_WORKER_QUEUE_URL": response_queue_url,

                # Plexus API Configuration (from Secrets Manager)
                "PLEXUS_ACCOUNT_KEY": config.get_value("account-key"),
                "PLEXUS_API_KEY": config.get_value("api-key"),
                "PLEXUS_API_URL": config.get_value("api-url"),

                # Database Configuration (from Secrets Manager)
                "PLEXUS_LANGGRAPH_CHECKPOINTER_POSTGRES_URI": config.get_value("postgres-uri"),

                # S3 Bucket Names (from Secrets Manager)
                "AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME": config.get_value("score-result-attachments-bucket"),
                "AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME": config.get_value("report-block-details-bucket"),

                # OpenAI Configuration (from Secrets Manager)
                "OPENAI_API_KEY": config.get_value("openai-api-key"),

                # GraphQL Schema Configuration (hardcoded - not environment-specific)
                "FETCH_SCHEMA_FROM_TRANSPORT": "false",
                "PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT": "0",
                "GQL_FETCH_SCHEMA_FROM_TRANSPORT": "0",

                # Matplotlib Configuration (hardcoded - Lambda /tmp directory)
                "MPLBACKEND": "Agg",
                "MPLCONFIGDIR": "/tmp/mpl",

                # Deployment ID - forces Lambda to update image on every deployment
                "DEPLOYMENT_ID": deployment_id,
            },
            description=f"Processes scoring jobs from SQS queue ({environment}) - Deployed: {deployment_id}"
        )

        # Note: We're intentionally NOT adding SQS as an event source yet
        # The function will be invoked manually until we're ready for automatic triggering
        #
        # Future: Add SQS trigger when ready
        # from aws_cdk import aws_lambda_event_sources as lambda_events
        # self.lambda_function.add_event_source(
        #     lambda_events.SqsEventSource(
        #         queue=standard_request_queue,
        #         batch_size=1
        #     )
        # )
