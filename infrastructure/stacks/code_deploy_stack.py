"""
Stack for Plexus CodeDeploy resources.

This stack manages the CodeDeploy infrastructure for deploying Plexus code
to EC2 instances, including the application and deployment groups.
The actual deployment is triggered by the main infrastructure pipeline.
"""

from aws_cdk import (
    Stack,
    aws_codedeploy as codedeploy,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_assets as assets,
    RemovalPolicy,
    Tags,
)
from constructs import Construct
import os
from .shared.naming import get_resource_name


class CodeDeployStack(Stack):
    """
    CDK Stack for CodeDeploy resources.

    Creates environment-specific CodeDeploy applications and deployment groups
    for deploying Plexus code to EC2 instances.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        ec2_role: iam.Role,
        **kwargs
    ) -> None:
        """
        Initialize the CodeDeploy stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            environment: Environment name ('staging' or 'production')
            ec2_role: IAM role for EC2 instances (from CommandWorkerStack)
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = environment
        self.app_name = get_resource_name("code-deploy", environment, "app")

        # Add environment tag to all resources in this stack
        Tags.of(self).add("Environment", environment)
        Tags.of(self).add("Service", "code-deploy")
        Tags.of(self).add("ManagedBy", "CDK")

        # Store EC2 role for reference
        self.ec2_role = ec2_role

        # Create CodeDeploy service role
        self.codedeploy_service_role = self._create_codedeploy_service_role()

        # Create S3 bucket for code deployments
        self.deployment_bucket = s3.Bucket(
            self,
            f"DeploymentBucket-{environment}",
            bucket_name=f"plexus-{environment}-code-deployments",
            removal_policy=RemovalPolicy.RETAIN,  # Keep deployment history
            versioned=True,  # Enable versioning for rollback capability
            encryption=s3.BucketEncryption.S3_MANAGED
        )

        # Grant EC2 role read access to deployment bucket
        self.deployment_bucket.grant_read(self.ec2_role)

        # Grant CodeDeploy service role read access to deployment bucket
        self.deployment_bucket.grant_read(self.codedeploy_service_role)

        # Create deployment artifacts asset (for appspec, scripts, etc.)
        self.deployment_artifacts = assets.Asset(
            self,
            f"DeploymentArtifacts-{environment}",
            path=os.path.join(os.path.dirname(__file__), "..", "deployment_artifacts")
        )

        # Grant EC2 role read access to deployment artifacts
        self.deployment_artifacts.grant_read(self.ec2_role)

        # Create CodeDeploy Application
        self.app = codedeploy.ServerApplication(
            self,
            f"CodeDeployApplication-{environment}",
            application_name=self.app_name
        )

        # Create CodeDeploy Deployment Group
        self.deployment_group = codedeploy.ServerDeploymentGroup(
            self,
            f"DeploymentGroup-{environment}",
            application=self.app,
            deployment_group_name=get_resource_name("code-deploy", environment, "group"),
            install_agent=True,
            ec2_instance_tags=codedeploy.InstanceTagSet({
                "Environment": [environment]
            }),
            role=self.codedeploy_service_role,
            deployment_config=codedeploy.ServerDeploymentConfig.ALL_AT_ONCE,
            ignore_poll_alarms_failure=False,
            auto_rollback=codedeploy.AutoRollbackConfig(
                failed_deployment=True,
                stopped_deployment=True,
                deployment_in_alarm=False
            )
        )

    def _create_codedeploy_service_role(self) -> iam.Role:
        """
        Create CodeDeploy service role.

        Returns:
            IAM Role for CodeDeploy service
        """
        return iam.Role(
            self,
            f"CodeDeployServiceRole-{self.env_name}",
            role_name=get_resource_name("code-deploy", self.env_name, "service-role"),
            assumed_by=iam.ServicePrincipal("codedeploy.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSCodeDeployRole")
            ]
        )
