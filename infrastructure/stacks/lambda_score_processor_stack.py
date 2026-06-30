"""
Stack for Lambda-based score processor.

This stack manages the Lambda function that processes scoring jobs from SQS queues.
The function uses a container image built from the score-processor-lambda directory.
"""

import os
from datetime import datetime, timezone
from typing import Optional
from aws_cdk import (
    CfnOutput,
    Stack,
    Duration,
    Tags,
    CustomResource,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_events,
    aws_iam as iam,
    aws_ecr as ecr,
    aws_sqs as sqs,
    custom_resources as cr,
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
        response_queue_url: str,
        standard_request_queue: Optional[sqs.IQueue] = None,
        standard_request_queue_arn: Optional[str] = None,
        standard_request_queue_url: Optional[str] = None,
        reserved_concurrency: Optional[int] = 500,
        max_event_source_concurrency: int = 500,
        **kwargs
    ) -> None:
        """
        Initialize the Lambda score processor stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            environment: Environment name ('staging' or 'production')
            ecr_repository_name: Name of ECR repository containing Lambda container image
            standard_request_queue: SQS queue for incoming requests
            response_queue_url: SQS queue URL for responses
            standard_request_queue_arn: ARN for an existing request queue to import
            standard_request_queue_url: URL for an existing request queue to import
            reserved_concurrency: Reserved Lambda concurrency for production backlog processing.
            max_event_source_concurrency: SQS event source concurrency cap.
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

        if standard_request_queue is None:
            if not standard_request_queue_arn or not standard_request_queue_url:
                raise ValueError(
                    "Provide standard_request_queue or both standard_request_queue_arn "
                    "and standard_request_queue_url."
                )
            standard_request_queue = sqs.Queue.from_queue_attributes(
                self,
                "ImportedStandardRequestQueue",
                queue_arn=standard_request_queue_arn,
                queue_url=standard_request_queue_url,
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

        # Add Bedrock permissions for LLM invocations
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    # Allow access to all Bedrock foundation models
                    "arn:aws:bedrock:*::foundation-model/*",
                    "arn:aws:bedrock:*:*:inference-profile/*",
                    "arn:aws:bedrock:*:*:application-inference-profile/*",
                ]
            )
        )

        # Grant read access to Secrets Manager
        config.secret.grant_read(lambda_role)
        ecr_repository.grant_pull(lambda_role)

        lambda_environment = {
            "environment": self.env_name,
            # SQS Queue URLs
            "PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL": standard_request_queue.queue_url,
            "PLEXUS_RESPONSE_WORKER_QUEUE_URL": response_queue_url,

            # Plexus API Configuration (from Secrets Manager)
            "PLEXUS_ACCOUNT_KEY": config.get_value("account-key"),
            "PLEXUS_API_KEY": config.get_value("api-key"),
            "PLEXUS_API_URL": config.get_value("api-url"),

            # S3 Bucket Names (from Secrets Manager)
            "AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME": config.get_value("score-result-attachments-bucket"),
            "AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME": config.get_value("report-block-details-bucket"),

            # OpenAI Configuration (from Secrets Manager)
            "OPENAI_API_KEY": config.get_value("openai-api-key"),

            # GraphQL Schema Configuration (hardcoded - not environment-specific)
            "FETCH_SCHEMA_FROM_TRANSPORT": "false",
            "PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT": "0",
            "GQL_FETCH_SCHEMA_FROM_TRANSPORT": "0",

            # Prevent native libraries from exhausting Lambda thread limits under high concurrency.
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",

            # Matplotlib Configuration (hardcoded - Lambda /tmp directory)
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": "/tmp/mpl",
        }

        # Create Lambda function with container image
        # Note: The image must be built and pushed to ECR before deployment
        # This is handled by the pipeline's Docker build step
        self.lambda_function = lambda_.DockerImageFunction(
            self,
            "ScoreProcessorFunction",
            function_name=get_resource_name("lambda", self.env_name, "score-processor"),
            code=lambda_.DockerImageCode.from_ecr(
                repository=ecr_repository,
                tag_or_digest="latest"
            ),
            role=lambda_role,
            timeout=Duration.seconds(300),  # 5 minutes
            memory_size=3008,
            reserved_concurrent_executions=reserved_concurrency,
            environment=lambda_environment,
            description=f"Processes scoring jobs from SQS queue ({environment})"
        )

        # Custom resource to force Lambda image update on every deployment
        # This calls UpdateFunctionCode API which forces Lambda to pull latest image
        update_lambda_code = cr.AwsCustomResource(
            self,
            "UpdateLambdaCode",
            on_update=cr.AwsSdkCall(
                service="Lambda",
                action="updateFunctionCode",
                parameters={
                    "FunctionName": self.lambda_function.function_name,
                    "ImageUri": f"{ecr_repository.repository_uri}:latest",
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"UpdateLambdaCode-{datetime.now(timezone.utc).timestamp()}"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["lambda:UpdateFunctionCode"],
                    resources=[self.lambda_function.function_arn]
                )
            ])
        )

        # Ensure custom resource runs after Lambda is created
        update_lambda_code.node.add_dependency(self.lambda_function)

        # Add SQS event source trigger
        # This enables automatic Lambda invocation for each message in the queue
        self.lambda_function.add_event_source(
            lambda_events.SqsEventSource(
                queue=standard_request_queue,
                batch_size=1,  # Process one message per Lambda invocation
                max_concurrency=max_event_source_concurrency,
                # report_batch_item_failures=False (default) - Lambda handles deletion manually
                # On exception, SQS returns message to queue for retry
            )
        )

        CfnOutput(self, "ScoreProcessorFunctionName", value=self.lambda_function.function_name)
        CfnOutput(self, "ScoreProcessorQueueUrl", value=standard_request_queue.queue_url)
        CfnOutput(self, "ScoreProcessorReservedConcurrency", value=str(reserved_concurrency or "unreserved"))
        CfnOutput(self, "ScoreProcessorMaxEventSourceConcurrency", value=str(max_event_source_concurrency))
