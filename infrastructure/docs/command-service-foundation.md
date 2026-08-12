# Command-service foundation deployment

Deploy the stable foundation first, then the matching Amplify environment.

`main`/`production` uses the production foundation; `staging` uses the staging
foundation. Sandboxes do not deploy this foundation or the long-lived
`CommandServiceStack`. For fast dev iteration on the command worker without
a staging deploy, a personal sandbox can instead borrow the staging
foundation's VPC and run its own ECS worker built from a local Docker
asset — see `dashboard/amplify/SANDBOX.md` ("Full Async Command-Service
Iteration in Sandboxes").

## Production first deployment runbook

The production foundation is a prerequisite for the first `main` deployment
that includes the command service. It owns the production VPC, private
subnets, ECR repository, and the SSM parameters that the Amplify backend
imports. Do not rely on the staging foundation: each environment has an
isolated network and repository.

1. Identify the IAM role used by the production Amplify backend deployment.
   Set its ARN as `PLEXUS_AMPLIFY_DEPLOYMENT_ROLE_ARN` in the Amplify `main`
   branch environment. The same ARN is passed to the foundation deployment so
   that it can grant only the ECR and SSM access required by the build.
   The production branch must have this variable before the Amplify deployment;
   it is required by the backend definition.

2. From a checkout containing the intended `main` commit, deploy the
   production foundation in the same account and region as the production
   Amplify app. Bootstrap CDK first if that account/region has not been
   bootstrapped.

   ```bash
   cd infrastructure
   npx cdk bootstrap aws://ACCOUNT_ID/REGION
   PLEXUS_COMMAND_SERVICE_ENVIRONMENT=production \
   PLEXUS_AMPLIFY_DEPLOYMENT_ROLE_ARN=ROLE_ARN \
   npx cdk --app "python3 command_service_foundation_app.py" deploy CommandServiceFoundationProduction
   ```

   This creates two NAT gateways and therefore has ongoing AWS cost. Review the
   CloudFormation change set before confirming it.

3. Verify the foundation and its contract before merging or deploying the
   application:

   ```bash
   aws cloudformation describe-stacks \
     --stack-name plexus-command-service-foundation-production
   aws ssm get-parameters \
     --names \
       /plexus/production/command-service/vpc-id \
       /plexus/production/command-service/availability-zones \
       /plexus/production/command-service/private-subnet-ids \
       /plexus/production/command-service/worker-image-repository-uri \
       /plexus/production/command-service/worker-image-repository-arn
   ```

4. Merge the application to `main`. The Amplify build publishes the immutable
   command-worker image to that production repository and deploys the
   application-owned ECS service. Do not manually create an ECS service or
   substitute a mutable image tag.

The current account has the staging foundation but not the production
foundation, so this runbook must be completed before the first production
command-service deployment.

The Amplify build obtains the foundation's environment-scoped ECR repository
URI from SSM, builds `plexus/command_worker/Dockerfile` from the repository
root, resolves a digest, and passes only `repository@sha256` to the backend
deployment. Its immutable tag is the SHA-256 of the Dockerfile, lockfile,
package metadata, and every file under the copied `plexus` package tree.
Dashboard-only
changes therefore do not replace the ECS task definition.

Configure `PLEXUS_AMPLIFY_DEPLOYMENT_ROLE_ARN` in both the foundation deployment
and the matching Amplify build environment. The initial application deployment
attaches an inline policy to that identity containing only `dynamodb:Scan` on
the generated Task table. This application-owned grant avoids a foundation
dependency on a table that does not exist until Amplify performs its first
deployment.

Before a digest replacement, the build scans the authoritative Task table for
`RUNNING` and `CANCEL_REQUESTED` commands. If any exist, it keeps the deployed
digest and writes a deferred marker for a later deployment. Configure
the deployment-role ARN as described above; the application publishes the
current deployed digest and Task table name through environment-scoped SSM
parameters. The build exports the selected foundation repository and immutable
digest before invoking the backend deployment.

On the first deployment both the current-image and Task-table parameters are
absent, so the candidate digest is selected and the exact Task-table grant is
installed. A missing current-image parameter alongside an existing Task-table
parameter is treated as lost deployment state and fails closed. On later
deployments, a changed candidate remains deferred while any Task is `RUNNING`
or `CANCEL_REQUESTED`. The gate uses a strongly consistent scan, validates the
count returned for every AWS CLI page, and advances the candidate only when all
page counts are zero. Missing Task-table identity retains the valid deployed
digest.
Denied parameter access, malformed parameter or count responses, and scan
failure stop the build without producing a handoff, so unreadable activity
state can never advance the image.

This is a deliberate deferral, not a wait loop: CloudFormation stack operations
have a three-hour timeout, so waiting for an arbitrarily long command in the
backend deployment can otherwise fail the stack update and lose the intended
protection boundary.

## Worker execution authority

The ECS task role uses IAM-signed AppSync requests and has no static dashboard
credentials. Its lifecycle grant remains the six Task/TaskStage roots used for
claiming, fencing, progress, cancellation, and stage detail. Execution grants
are maintained separately in
`dashboard/amplify/command-service/action-authority.json`, which maps every
registered action to its audited domain roots, storage requirements, and code
evidence. The synthesized role receives the union of those explicit field ARNs;
it does not receive an AppSync wildcard.

Direct object-storage access is limited to known workload prefixes:

- dataset and data-source objects are read-only;
- procedure/report-block objects may be read or written;
- score-result/evaluation objects may be read or written.

Procedure state normally uses `createArtifactTransferTickets` and short-lived
HTTPS URLs, keeping bucket credentials out of the procedure storage adapter.
Bucket names are supplied to the container only for registered evaluation,
prediction, and report implementations that still use the corresponding
scoped AWS SDK paths.
