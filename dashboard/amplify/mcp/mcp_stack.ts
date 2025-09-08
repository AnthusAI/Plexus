import { Stack, StackProps } from 'aws-cdk-lib';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

export interface McpStackProps extends StackProps {
  deploymentTagKey?: string;
  deploymentTagValue?: string;
}

export class McpStack extends Stack {
  public readonly ssmDoc: ssm.CfnDocument;
  public readonly ssmAssociation: ssm.CfnAssociation;

  constructor(scope: Construct, constructId: string, props?: McpStackProps) {
    super(scope, constructId, props);

    const deploymentTagKey = props?.deploymentTagKey || 'Environment';
    const deploymentTagValue = props?.deploymentTagValue || 'production';

    // Define the SSM Document content for MCP service
    const ssmDocContent = {
      schemaVersion: '2.2',
      description: 'Configure and manage MCP systemd service',
      parameters: {
        ServiceName: {
          type: 'String',
          description: 'Name of the systemd service.',
          default: 'mcp-server-oauth.service'
        },
        ServiceUser: {
          type: 'String',
          description: 'User to run the service as.',
          default: 'ec2-user'
        },
        ServiceGroup: {
          type: 'String',
          description: 'Group to run the service as.',
          default: 'ec2-user'
        },
        WorkingDirectory: {
          type: 'String',
          description: 'Absolute path to the working directory for the service.',
          default: '/home/ec2-user/projects/Plexus'
        },
        PythonExecutable: {
          type: 'String',
          description: 'Absolute path to the Python executable.',
          default: '/home/ec2-user/miniconda3/envs/py311/bin/python'
        },
        Environment: {
          type: 'String',
          description: 'Environment variables for the service.',
          default: 'PYTHONPATH=/home/ec2-user/projects/Plexus'
        },
        Workers: {
          type: 'String',
          description: 'Number of uvicorn workers.',
          default: '3'
        }
      },
      mainSteps: [
        {
          action: 'aws:runShellScript',
          name: 'configureMcpService',
          inputs: {
            runCommand: [
              'set -euxo pipefail',
              // Ensure working directory exists
              'mkdir -p {{ WorkingDirectory }}',
              'chown {{ ServiceUser }}:{{ ServiceGroup }} {{ WorkingDirectory }}',

              // Create the systemd service file
              'cat << EOF | tee /etc/systemd/system/{{ ServiceName }} > /dev/null',
              '[Unit]',
              'Description=Plexus MCP Server (Managed by SSM)',
              'After=network.target',
              '',
              '[Service]',
              'User={{ ServiceUser }}',
              'Group={{ ServiceGroup }}',
              'WorkingDirectory={{ WorkingDirectory }}/MCP',
              'ExecStart={{ PythonExecutable }} -m uvicorn asgi_cognito_app:app --host 0.0.0.0 --port 8002 --workers {{ Workers }}',
              'Restart=on-failure',
              'RestartSec=5s',
              'StandardOutput=journal',
              'StandardError=journal',
              'Environment={{ Environment }}',
              '',
              '[Install]',
              'WantedBy=multi-user.target',
              'EOF',

              // Set permissions
              'chmod 644 /etc/systemd/system/{{ ServiceName }}',

              // Reload, enable, and restart
              'systemctl daemon-reload',
              'systemctl enable {{ ServiceName }}',
              'systemctl restart {{ ServiceName }}',
              'systemctl status {{ ServiceName }} --no-pager'
            ]
          }
        }
      ]
    };

    // Create the SSM Document resource
    this.ssmDoc = new ssm.CfnDocument(
      this,
      `${constructId}-McpServiceConfigDoc`,
      {
        content: ssmDocContent,
        documentType: 'Command',
        documentFormat: 'JSON',
        versionName: `v${Date.now()}` // Force new version on each deployment
      }
    );

    // Create the SSM Association to apply the document to tagged instances
    this.ssmAssociation = new ssm.CfnAssociation(
      this,
      `${constructId}-McpServiceAssociation`,
      {
        name: this.ssmDoc.ref,
        targets: [
          {
            key: `tag:${deploymentTagKey}`,
            values: [deploymentTagValue]
          }
        ],
        scheduleExpression: 'rate(30 minutes)', // Re-run every 30 minutes
        complianceSeverity: 'HIGH',
        maxConcurrency: '100%',
        maxErrors: '0',
        associationName: `${constructId}-McpServiceAssociation-${deploymentTagValue}`
      }
    );

    // Add dependency to ensure Document exists before Association
    this.ssmAssociation.addDependency(this.ssmDoc);
  }
}