# Command-service foundation deployment

Deploy the stable foundation first, then the matching Amplify environment.

`main`/`production` uses the production foundation; `staging` uses the staging
foundation. Sandboxes do not deploy this foundation or ECS resources.

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
