"""
Stack for Lambda-based fan-out controller.

This stack manages the Lambda function that fans out scoring jobs to multiple
score processor Lambda functions for controlled rollout.
"""

from aws_cdk import (
    Stack,
    Duration,
    Tags,
    aws_lambda as lambda_,
    aws_iam as iam,
)
from constructs import Construct
from .shared.naming import get_resource_name


class LambdaFanoutStack(Stack):
    """
    CDK Stack for Lambda-based fan-out controller.

    Creates a lightweight Lambda function that polls SQS and invokes multiple
    score processor Lambda functions asynchronously for controlled rollout.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        score_processor_lambda_arn: str,
        standard_request_queue_url: str,
        **kwargs
    ) -> None:
        """
        Initialize the Lambda fan-out stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            environment: Environment name ('staging' or 'production')
            score_processor_lambda_arn: ARN of score processor Lambda to invoke
            standard_request_queue_url: SQS queue URL for incoming requests
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = environment

        # Add environment tags
        Tags.of(self).add("Environment", environment)
        Tags.of(self).add("Service", "lambda-fanout")
        Tags.of(self).add("ManagedBy", "CDK")

        # Create IAM role for Lambda function
        lambda_role = iam.Role(
            self,
            "FanoutLambdaRole",
            role_name=get_resource_name("lambda", environment, "fanout-role"),
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for fan-out Lambda function",
        )

        # Add basic Lambda execution permissions for CloudWatch Logs
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )

        # Add SQS permissions (ReceiveMessage, ChangeMessageVisibility, GetQueueAttributes)
        # Note: NOT DeleteMessage - score processor handles that
        queue_arn = self._get_queue_arn_from_url(standard_request_queue_url)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sqs:ReceiveMessage",
                    "sqs:ChangeMessageVisibility",
                    "sqs:GetQueueAttributes",
                ],
                resources=[queue_arn],
            )
        )

        # Add Lambda invoke permissions for score processor
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[score_processor_lambda_arn],
            )
        )

        # Create Lambda function
        fanout_function = lambda_.Function(
            self,
            "FanoutFunction",
            function_name=get_resource_name("lambda", environment, "fanout"),
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("score-processor-fanout-lambda"),
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=512,
            environment={
                "FANOUT_BATCH_SIZE": "10",  # Default batch size
                "SCORE_PROCESSOR_LAMBDA_ARN": score_processor_lambda_arn,
                "PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL": standard_request_queue_url,
            },
            description="Fan-out controller for score processor Lambda invocations",
        )

        # Store function for potential cross-stack references
        self.fanout_function = fanout_function

    def _get_queue_arn_from_url(self, queue_url: str) -> str:
        """
        Convert SQS queue URL to ARN.

        Args:
            queue_url: SQS queue URL

        Returns:
            Queue ARN
        """
        # Queue URL format: https://sqs.{region}.amazonaws.com/{account_id}/{queue_name}
        parts = queue_url.split("/")
        queue_name = parts[-1]
        account_id = parts[-2]
        region = queue_url.split(".")[1]

        return f"arn:aws:sqs:{region}:{account_id}:{queue_name}"
