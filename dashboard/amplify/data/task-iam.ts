import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export type TaskAppSyncPrincipal = iam.IRole;

function taskFieldArn(apiGraphqlArn: string, type: 'Query' | 'Mutation', field: string): string {
  return `${apiGraphqlArn}/types/${type}/fields/${field}`;
}

/**
 * Dashboard identity-pool credentials may use ordinary Task model operations,
 * but must never create or change dispatch-eligible command Tasks directly.
 * This policy is deliberately attached in the always-created Amplify backend so
 * sandboxes receive the same boundary as production and staging.
 */
export function denyDashboardIdentityTaskMutations(
  scope: Construct,
  dashboardIdentityRoles: readonly TaskAppSyncPrincipal[],
  apiGraphqlArn: string,
): void {
  const policy = new iam.Policy(scope, 'DenyDashboardIdentityTaskMutations', {
    statements: [new iam.PolicyStatement({
      effect: iam.Effect.DENY,
      actions: ['appsync:GraphQL'],
      resources: [
        taskFieldArn(apiGraphqlArn, 'Mutation', '*Task'),
      ],
    })],
  });
  for (const role of dashboardIdentityRoles) {
    policy.attachToRole(role);
  }
}

export function grantCancelCommandTaskAccess(role: iam.IGrantable, apiGraphqlArn: string): void {
  role.grantPrincipal.addToPrincipalPolicy(new iam.PolicyStatement({
    effect: iam.Effect.ALLOW,
    actions: ['appsync:GraphQL'],
    resources: [
      taskFieldArn(apiGraphqlArn, 'Query', 'getTask'),
      taskFieldArn(apiGraphqlArn, 'Mutation', 'updateTask'),
    ],
  }));
}
