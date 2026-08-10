import { readFileSync } from 'fs';
import { join } from 'path';
import { App, Stack } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import * as iam from 'aws-cdk-lib/aws-iam';
import {
  denyDashboardIdentityTaskMutations,
  grantCancelCommandTaskAccess,
} from './task-iam';

const root = join(process.cwd(), 'amplify');
const resource = readFileSync(join(root, 'data/resource.ts'), 'utf8');
const backend = readFileSync(join(root, 'backend.ts'), 'utf8');

describe('Task four-principal authorization contract', () => {
  it('preserves TaskStage API-key and user-pool writers while IAM may also write', () => {
    expect(resource).toContain('allow.publicApiKey(),\n            allow.authenticated(),\n            // ECS uses IAM AppSync operations.');
    expect(resource).toContain("allow.authenticated('identityPool').to(['read', 'create', 'update'])");
    // The authoritative Task lifecycle fields remain user/API read-only.
    expect(resource).toContain("dispatchStatus: a.string().authorization((allow) => [allow.publicApiKey().to(['read']), allow.authenticated().to(['read']), allow.authenticated('identityPool').to(['read', 'create', 'update'])])");
  });
  it('grants cancellation only the AppSync fields it requires', () => {
    expect(backend).not.toContain('grantSubmitCommandTaskAccess');
    expect(backend).toContain('grantCancelCommandTaskAccess(cancelCommandFunction, api.attrArn)');
  });

  it('gives submit direct Task-table access without AppSync Task permissions', () => {
    expect(backend).toContain("Environment.Variables.TASK_TABLE_NAME");
    expect(backend).toContain("actions: ['dynamodb:GetItem', 'dynamodb:PutItem'],\n        resources: [backend.data.resources.tables.Task.tableArn]");
  });

  it('synthesizes the dashboard identity-pool Task mutation deny for sandbox roles', () => {
    const app = new App();
    const stack = new Stack(app, 'SandboxBackend');
    const authenticated = new iam.Role(stack, 'AuthenticatedIdentityPoolRole', {
      assumedBy: new iam.AccountRootPrincipal(),
    });
    const unauthenticated = new iam.Role(stack, 'UnauthenticatedIdentityPoolRole', {
      assumedBy: new iam.AccountRootPrincipal(),
    });
    denyDashboardIdentityTaskMutations(
      [authenticated, unauthenticated],
      'arn:aws:appsync:us-east-1:123456789012:apis/example',
    );

    const template = Template.fromStack(stack);
    template.resourceCountIs('AWS::IAM::Policy', 2);
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: [{
          Effect: 'Deny',
          Action: 'appsync:GraphQL',
          Resource: 'arn:aws:appsync:us-east-1:123456789012:apis/example/types/Mutation/fields/*Task',
        }],
      },
    });
  });

  it('synthesizes only the AppSync Task fields required by cancellation', () => {
    const app = new App();
    const stack = new Stack(app, 'ServiceRoles');
    const cancel = new iam.Role(stack, 'CancelCommandRole', { assumedBy: new iam.AccountRootPrincipal() });
    const apiArn = 'arn:aws:appsync:us-east-1:123456789012:apis/example';
    grantCancelCommandTaskAccess(cancel, apiArn);

    const template = Template.fromStack(stack);
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: [{
          Effect: 'Allow',
          Action: 'appsync:GraphQL',
          Resource: [
            `${apiArn}/types/Query/fields/getTask`,
            `${apiArn}/types/Mutation/fields/updateTask`,
          ],
        }],
      },
    });
  });
});
