"""
Stack for Plexus command worker resources.

This stack manages the infrastructure needed for command workers running on EC2,
including SSM documents, IAM roles, and instance profiles.
"""

from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_ssm as ssm,
    Tags,
)
from constructs import Construct
from .shared.naming import get_resource_name


class CommandWorkerStack(Stack):
    """
    CDK Stack for command worker resources.

    Creates environment-specific resources for the Plexus command worker system
    that runs on EC2 instances.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        **kwargs
    ) -> None:
        """
        Initialize the command worker stack.

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
        Tags.of(self).add("Service", "command-worker")
        Tags.of(self).add("ManagedBy", "CDK")

        # Create EC2 instance role
        self.ec2_role = self._create_ec2_role()

        # Create instance profile
        self.instance_profile = iam.CfnInstanceProfile(
            self,
            f"CommandWorkerInstanceProfile-{environment}",
            roles=[self.ec2_role.role_name],
            instance_profile_name=get_resource_name("command-worker", environment, "instance-profile")
        )

        # Create SSM document for command worker service management
        self._create_worker_service_document()

    def _create_ec2_role(self) -> iam.Role:
        """
        Create EC2 instance role with necessary permissions for command worker.

        Returns:
            IAM Role for EC2 instances
        """
        role = iam.Role(
            self,
            f"CommandWorkerEC2Role-{self.env_name}",
            role_name=get_resource_name("command-worker", self.env_name, "ec2-role"),
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodeDeployFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ],
            inline_policies={
                "KMSPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "kms:Decrypt",
                                "kms:DescribeKey"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        return role

    def _create_worker_service_document(self):
        """
        Create SSM document for managing the command worker systemd service.

        This document configures a systemd service that runs the Plexus command worker.
        """
        # Define the SSM Document content
        ssm_doc_content = {
            "schemaVersion": "2.2",
            "description": f"Configure and manage plexus-command-worker service for {self.env_name}",
            "parameters": {
                "ServiceName": {
                    "type": "String",
                    "description": "Name of the systemd service.",
                    "default": "plexus-command-worker.service"
                },
                "ServiceUser": {
                    "type": "String",
                    "description": "User to run the service as.",
                    "default": "ec2-user"
                },
                "ServiceGroup": {
                    "type": "String",
                    "description": "Group to run the service as.",
                    "default": "ec2-user"
                },
                "WorkingDirectory": {
                    "type": "String",
                    "description": "Absolute path to the working directory for the service.",
                    "default": "/home/ec2-user/projects/Call-Criteria-Python"
                },
                "PlexusExecutable": {
                    "type": "String",
                    "description": "Absolute path to the plexus executable.",
                    "default": "/home/ec2-user/miniconda3/envs/py311/bin/plexus"
                },
                "Environment": {
                    "type": "String",
                    "description": "Environment variables for the service.",
                    "default": "PYTHONPATH=/home/ec2-user/projects/Call-Criteria-Python"
                }
            },
            "mainSteps": [
                {
                    "action": "aws:runShellScript",
                    "name": "configureCommandWorkerService",
                    "inputs": {
                        "runCommand": [
                            "set -euxo pipefail",
                            # Ensure working directory exists
                            "mkdir -p {{ WorkingDirectory }}",
                            "chown {{ ServiceUser }}:{{ ServiceGroup }} {{ WorkingDirectory }}",

                            # Create the systemd service file
                            "cat << 'EOF' | tee /etc/systemd/system/{{ ServiceName }} > /dev/null",
                            "[Unit]",
                            "Description=Plexus Command Worker Service (Managed by SSM)",
                            "After=network.target",
                            "",
                            "[Service]",
                            "User={{ ServiceUser }}",
                            "Group={{ ServiceGroup }}",
                            "WorkingDirectory={{ WorkingDirectory }}",
                            "ExecStart={{ PlexusExecutable }} command worker",
                            "Restart=on-failure",
                            "RestartSec=5s",
                            "StandardOutput=journal",
                            "StandardError=journal",
                            "Environment={{ Environment }}",
                            "",
                            "[Install]",
                            "WantedBy=multi-user.target",
                            "EOF",

                            # Set permissions
                            "chmod 644 /etc/systemd/system/{{ ServiceName }}",

                            # Reload, enable, and restart
                            "systemctl daemon-reload",
                            "systemctl enable {{ ServiceName }}",
                            "systemctl restart {{ ServiceName }}",
                            "systemctl status {{ ServiceName }} --no-pager"
                        ]
                    }
                }
            ]
        }

        # Create the SSM Document resource
        ssm_doc = ssm.CfnDocument(
            self,
            f"CommandWorkerConfigDoc-{self.env_name}",
            content=ssm_doc_content,
            document_type="Command"
            # Note: name is omitted to allow CloudFormation to auto-generate it
            # This enables updates without requiring resource replacement
        )

        # Create the SSM Association to apply the document to tagged instances
        # Targets instances with Environment tag matching the environment
        ssm_association = ssm.CfnAssociation(
            self,
            f"CommandWorkerAssociation-{self.env_name}",
            name=ssm_doc.ref,
            targets=[
                ssm.CfnAssociation.TargetProperty(
                    key="tag:Environment",
                    values=[self.env_name]
                )
            ],
        )

        # Add dependency to ensure Document exists before Association
        ssm_association.add_dependency(ssm_doc)

        # Store document reference
        self.worker_config_document = ssm_doc