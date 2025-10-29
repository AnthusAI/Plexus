"""
Stack for Plexus scoring worker resources.

This stack manages the infrastructure needed for scoring workers,
including SQS queues and related resources.
"""

from aws_cdk import (
    Stack,
    aws_sqs as sqs,
    aws_ssm as ssm,
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

        # Create SSM document for scoring worker service management
        self._create_worker_service_document()

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

    def _create_worker_service_document(self):
        """
        Create SSM document for managing the scoring worker systemd service.

        This document configures a systemd service that runs the ProcessScoreWorker
        with gunicorn managing multiple worker processes.
        """
        # Define the SSM Document content
        ssm_doc_content = {
            "schemaVersion": "2.2",
            "description": f"Configure and manage scoring worker service for {self.env_name}",
            "parameters": {
                "ServiceName": {
                    "type": "String",
                    "description": "Name of the systemd service.",
                    "default": "plexus-scoring-worker.service"
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
                    "default": "/home/ec2-user/projects/Plexus"
                },
                "ScoringRequestQueueUrl": {
                    "type": "String",
                    "description": "SQS queue URL for scoring requests.",
                    "default": self.standard_request_queue.queue_url
                },
                "ScoringResponseQueueUrl": {
                    "type": "String",
                    "description": "SQS queue URL for scoring responses.",
                    "default": self.response_queue.queue_url
                },
                "PlexusAccountKey": {
                    "type": "String",
                    "description": "Plexus account key for authentication.",
                    "default": "CHANGE_ME"
                },
                "NumWorkers": {
                    "type": "String",
                    "description": "Number of worker processes to run.",
                    "default": "4"
                }
            },
            "mainSteps": [
                {
                    "action": "aws:runShellScript",
                    "name": "configureScoringWorkerService",
                    "inputs": {
                        "runCommand": [
                            "set -euxo pipefail",
                            # Ensure working directory exists
                            "mkdir -p {{ WorkingDirectory }}",
                            "chown {{ ServiceUser }}:{{ ServiceGroup }} {{ WorkingDirectory }}",

                            # Create the systemd service file
                            "cat << 'EOF' | tee /etc/systemd/system/{{ ServiceName }} > /dev/null",
                            "[Unit]",
                            "Description=Plexus Scoring Worker Service (Managed by SSM)",
                            "After=network.target",
                            "",
                            "[Service]",
                            "User={{ ServiceUser }}",
                            "Group={{ ServiceGroup }}",
                            "WorkingDirectory={{ WorkingDirectory }}",
                            "ExecStart=/home/ec2-user/miniconda3/envs/py311/bin/python -m plexus.workers.ProcessScoreWorker",
                            "Restart=on-failure",
                            "RestartSec=5s",
                            "StandardOutput=journal",
                            "StandardError=journal",
                            "Environment=PYTHONPATH={{ WorkingDirectory }}",
                            "Environment=SCORING_REQUEST_STANDARD_QUEUE_URL={{ ScoringRequestQueueUrl }}",
                            "Environment=SCORING_RESPONSE_QUEUE_URL={{ ScoringResponseQueueUrl }}",
                            "Environment=PLEXUS_ACCOUNT_KEY={{ PlexusAccountKey }}",
                            "Environment=NUM_WORKERS={{ NumWorkers }}",
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
            f"ScoringWorkerConfigDoc-{self.env_name}",
            content=ssm_doc_content,
            document_type="Command"
            # Note: name is omitted to allow CloudFormation to auto-generate it
            # This enables updates without requiring resource replacement
        )

        # Create the SSM Association to apply the document to tagged instances
        ssm_association = ssm.CfnAssociation(
            self,
            f"ScoringWorkerAssociation-{self.env_name}",
            name=ssm_doc.ref,
            targets=[ssm.CfnAssociation.TargetProperty(
                key="tag:Environment",
                values=[self.env_name]
            )],
        )

        # Add dependency to ensure Document exists before Association
        ssm_association.add_dependency(ssm_doc)

        # Store document reference
        self.worker_config_document = ssm_doc