"""
Stack for Plexus scoring worker resources.

This stack manages the infrastructure needed for scoring workers,
including SQS queues and related resources.
"""

from aws_cdk import (
    Stack,
    aws_sqs as sqs,
    Duration,
    Tags,
)
from constructs import Construct
from typing import Tuple
from .shared.naming import get_resource_name


class ScoringWorkerStack(Stack):
    """
    CDK Stack for scoring worker resources.

    Creates environment-specific resources for the Plexus scoring worker system.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        **kwargs
    ) -> None:
        """
        Initialize the scoring worker stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            environment: Environment name ('staging' or 'production')
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = environment

        # Add environment tag to all resources in this stack
        Tags.of(self).add("Environment", environment)
        Tags.of(self).add("Service", "scoring-worker")
        Tags.of(self).add("ManagedBy", "CDK")

        # Create queues with DLQs
        self.standard_request_queue, self.standard_request_dlq = self._create_queue_with_dlq(
            "StandardRequest",
            "standard-request"
        )

        self.response_queue, self.response_dlq = self._create_queue_with_dlq(
            "Response",
            "response"
        )

        # Future: GPU Request Queue (when needed)
        # self.gpu_request_queue, self.gpu_request_dlq = self._create_queue_with_dlq(
        #     "GpuRequest",
        #     "gpu-request"
        # )

    def _create_queue_with_dlq(
        self,
        logical_name: str,
        resource_name: str,
        visibility_timeout: Duration = Duration.seconds(300),
        retention_period: Duration = Duration.days(14),
        max_receive_count: int = 3
    ) -> Tuple[sqs.Queue, sqs.Queue]:
        """
        Create a queue with an associated dead letter queue.

        Args:
            logical_name: CloudFormation logical name prefix (e.g., "StandardRequest")
            resource_name: Resource name for naming convention (e.g., "standard-request")
            visibility_timeout: Message visibility timeout
            retention_period: Message retention period
            max_receive_count: Max retries before moving to DLQ

        Returns:
            Tuple of (main_queue, dlq)
        """
        # Create DLQ first
        dlq = sqs.Queue(
            self,
            f"{logical_name}DLQ",
            queue_name=get_resource_name("scoring", self.env_name, f"{resource_name}-dlq"),
            retention_period=retention_period
        )

        # Create main queue with DLQ
        queue = sqs.Queue(
            self,
            f"{logical_name}Queue",
            queue_name=get_resource_name("scoring", self.env_name, f"{resource_name}-queue"),
            visibility_timeout=visibility_timeout,
            retention_period=retention_period,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=max_receive_count,
                queue=dlq
            )
        )

        return queue, dlq