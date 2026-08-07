import { readFileSync } from 'fs';
import { join } from 'path';
import { App, Stack } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import * as iam from 'aws-cdk-lib/aws-iam';
import {
  denyDashboardIdentityTaskMutations,
  grantCancelCommandTaskAccess,
  grantSubmitCommandTaskAccess,
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
  it('grants submit only get/create and cancellation only get/update AppSync fields', () => {
    expect(backend).toContain('grantSubmitCommandTaskAccess(submitCommandFunction, api.attrArn)');
    expect(backend).toContain('grantCancelCommandTaskAccess(cancelCommandFunction, api.attrArn)');
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

  it('synthesizes only the service Task fields required by submit and cancel', () => {
    const app = new App();
    const stack = new Stack(app, 'ServiceRoles');
    const submit = new iam.Role(stack, 'SubmitCommandRole', { assumedBy: new iam.AccountRootPrincipal() });
    const cancel = new iam.Role(stack, 'CancelCommandRole', { assumedBy: new iam.AccountRootPrincipal() });
    const apiArn = 'arn:aws:appsync:us-east-1:123456789012:apis/example';
    grantSubmitCommandTaskAccess(submit, apiArn);
    grantCancelCommandTaskAccess(cancel, apiArn);

    const template = Template.fromStack(stack);
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: [{
          Effect: 'Allow',
          Action: 'appsync:GraphQL',
          Resource: [
            `${apiArn}/types/Mutation/fields/createTask`,
            `${apiArn}/types/Query/fields/getTask`,
          ],
        }],
      },
    });
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
