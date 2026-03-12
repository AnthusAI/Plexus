"""
Stack for basic EC2 IAM role.

This stack creates a minimal EC2 role for staging environments that don't need
the full CommandWorker stack but still need an IAM role for CodeDeploy.
"""

from aws_cdk import (
    Stack,
    aws_iam as iam,
    Tags,
)
from constructs import Construct


class EC2RoleStack(Stack):
    """
    CDK Stack for basic EC2 IAM role.

    Creates a minimal IAM role for EC2 instances that need CodeDeploy access
    but don't require the full CommandWorker SSM management.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        **kwargs
    ) -> None:
        """
        Initialize the EC2 role stack.

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
        Tags.of(self).add("Service", "ec2-role")
        Tags.of(self).add("ManagedBy", "CDK")

        # Create basic EC2 role
        self.ec2_role = iam.Role(
            self,
            f"EC2Role-{environment}",
            role_name=f"plexus-ec2-basic-role-{environment}",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodeDeployFullAccess")
            ]
        )
