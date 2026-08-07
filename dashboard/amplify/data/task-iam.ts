import * as iam from 'aws-cdk-lib/aws-iam';

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
  dashboardIdentityRoles: readonly TaskAppSyncPrincipal[],
  apiGraphqlArn: string,
): void {
  for (const role of dashboardIdentityRoles) {
    role.addToPrincipalPolicy(new iam.PolicyStatement({
      effect: iam.Effect.DENY,
      actions: ['appsync:GraphQL'],
      resources: [
        taskFieldArn(apiGraphqlArn, 'Mutation', '*Task'),
      ],
    }));
  }
}

export function grantSubmitCommandTaskAccess(role: iam.IGrantable, apiGraphqlArn: string): void {
  role.grantPrincipal.addToPrincipalPolicy(new iam.PolicyStatement({
    effect: iam.Effect.ALLOW,
    actions: ['appsync:GraphQL'],
    resources: [
      taskFieldArn(apiGraphqlArn, 'Mutation', 'createTask'),
      taskFieldArn(apiGraphqlArn, 'Query', 'getTask'),
    ],
  }));
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
