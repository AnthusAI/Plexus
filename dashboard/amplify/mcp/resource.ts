import { Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { McpStack } from '../../../infrastructure/MCP/mcp/mcp_stack.js';

export interface McpResourceProps extends StackProps {
  deploymentTagKey?: string;
  deploymentTagValue?: string;
}

export class McpResource extends Stack {
  public readonly mcpStack: McpStack;

  constructor(scope: Construct, id: string, props?: McpResourceProps) {
    super(scope, id, props);

    // Create the MCP stack as a nested stack
    this.mcpStack = new McpStack(this, 'McpNestedStack', {
      deploymentTagKey: props?.deploymentTagKey || 'Environment',
      deploymentTagValue: props?.deploymentTagValue || 'production',
      ...props
    });
  }
}