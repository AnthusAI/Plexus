from aws_cdk import (
    Stack,
    aws_ssm as ssm,
)
from constructs import Construct

class McpStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, 
                 deployment_tag_key: str = "Environment", 
                 deployment_tag_value: str = "production",
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define the SSM Document content for MCP service
        ssm_doc_content = {
            "schemaVersion": "2.2",
            "description": "Configure and manage MCP systemd service",
            "parameters": {
                "ServiceName": {
                    "type": "String",
                    "description": "Name of the systemd service.",
                    "default": "mcp-server.service"
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
                "PythonExecutable": {
                    "type": "String",
                    "description": "Absolute path to the Python executable.",
                    "default": "/home/ec2-user/miniconda3/envs/py311/bin/python"
                },
                "Environment": {
                    "type": "String",
                    "description": "Environment variables for the service.",
                    "default": "PYTHONPATH=/home/ec2-user/projects/Plexus"
                },
                "Workers": {
                    "type": "String",
                    "description": "Number of uvicorn workers.",
                    "default": "3"
                }
            },
            "mainSteps": [
                {
                    "action": "aws:runShellScript",
                    "name": "configureMcpService",
                    "inputs": {
                        "runCommand": [
                            "set -euxo pipefail",
                            # Ensure working directory exists
                            "mkdir -p {{ WorkingDirectory }}",
                            "chown {{ ServiceUser }}:{{ ServiceGroup }} {{ WorkingDirectory }}",

                            # Create the systemd service file
                            "cat << EOF | tee /etc/systemd/system/{{ ServiceName }} > /dev/null",
                            "[Unit]",
                            "Description=Plexus MCP Server (Managed by SSM)",
                            "After=network.target",
                            "",
                            "[Service]",
                            "User={{ ServiceUser }}",
                            "Group={{ ServiceGroup }}",
                            "WorkingDirectory={{ WorkingDirectory }}/MCP",
                            "ExecStart={{ PythonExecutable }} -m uvicorn asgi_cognito_app:app --host 0.0.0.0 --port 8002 --workers {{ Workers }}",
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
        self.ssm_doc = ssm.CfnDocument(
            self,
            f"{construct_id}-McpServiceConfigDoc",
            content=ssm_doc_content,
            document_type="Command",
        )

        # Create the SSM Association to apply the document to tagged instances
        self.ssm_association = ssm.CfnAssociation(
            self,
            f"{construct_id}-McpServiceAssociation",
            name=self.ssm_doc.ref,
            targets=[ssm.CfnAssociation.TargetProperty(
                key=f"tag:{deployment_tag_key}",
                values=[deployment_tag_value]
            )]
        )

        # Add dependency to ensure Document exists before Association
        self.ssm_association.add_dependency(self.ssm_doc)
