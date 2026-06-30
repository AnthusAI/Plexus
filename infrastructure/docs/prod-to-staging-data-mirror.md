# Plexus Production-To-Staging Data Mirror

This runbook covers the manual CodeBuild job that destructively refreshes the Amplify `staging` branch from `main` production data in account `656853518159`, region `us-east-1`.

## Deploy the Job

```bash
cd /Users/ryan.porter/Projects/Plexus/infrastructure
AWS_PROFILE=call-criteria AWS_REGION=us-east-1 \
CDK_DEFAULT_ACCOUNT=656853518159 CDK_DEFAULT_REGION=us-east-1 \
npx cdk deploy plexus-prod-to-staging-data-mirror
```

## Non-Mutating Preflight

```bash
AWS_PROFILE=call-criteria AWS_REGION=us-east-1 aws codebuild start-build \
  --project-name plexus-prod-to-staging-data-mirror \
  --environment-variables-override name=MIRROR_MODE,value=preflight,type=PLAINTEXT
```

## Full Destructive Mirror

This wipes staging DynamoDB tables and staging Amplify storage buckets before copying production into staging.

```bash
AWS_PROFILE=call-criteria AWS_REGION=us-east-1 aws codebuild start-build \
  --project-name plexus-prod-to-staging-data-mirror \
  --timeout-in-minutes 480 \
  --environment-variables-override \
    name=MIRROR_MODE,value=full,type=PLAINTEXT \
    name=CONFIRM_DESTRUCTIVE,value=mirror-main-to-staging,type=PLAINTEXT
```

## Cognito

The job can best-effort create/update staging Cognito users, but it cannot preserve production passwords or Cognito `sub` values. If user creation is needed, provide a temporary password override:

```bash
name=STAGING_COGNITO_TEMP_PASSWORD,value='<temporary-password>',type=PLAINTEXT
```

Existing production historical author references are preserved by copying the DynamoDB `User` table exactly.

## Kanbus Note

Add to the Restart data migration task once Kanbus is available:

> Added CDK-managed `plexus-prod-to-staging-data-mirror` CodeBuild job and runner for destructive production-to-staging refreshes. The job runs in AWS, keeps DynamoDB/S3 data inside the account, preserves IDs and object keys, pauses staging stream consumers during import, and requires `CONFIRM_DESTRUCTIVE=mirror-main-to-staging` before wiping staging.

## Bounded Job Modes

If individual CodeBuild builds report a 45-minute timeout, run the mirror as bounded jobs instead of `MIRROR_MODE=full`.

Disable staging stream consumers first:

```bash
AWS_PROFILE=call-criteria AWS_REGION=us-east-1 aws codebuild start-build \
  --project-name plexus-prod-to-staging-data-mirror \
  --environment-variables-override \
    name=MIRROR_MODE,value=disable-consumers,type=PLAINTEXT \
    name=CONFIRM_DESTRUCTIVE,value=mirror-main-to-staging,type=PLAINTEXT
```

Delete or copy one table:

```bash
AWS_PROFILE=call-criteria AWS_REGION=us-east-1 aws codebuild start-build \
  --project-name plexus-prod-to-staging-data-mirror \
  --environment-variables-override \
    name=MIRROR_MODE,value=copy-table,type=PLAINTEXT \
    name=MODEL,value=ScoreResult,type=PLAINTEXT \
    name=SEGMENT,value=0,type=PLAINTEXT \
    name=TOTAL_SEGMENTS,value=256,type=PLAINTEXT \
    name=CONFIRM_DESTRUCTIVE,value=mirror-main-to-staging,type=PLAINTEXT
```

Copy one S3 bucket category, optionally limited to a prefix:

```bash
AWS_PROFILE=call-criteria AWS_REGION=us-east-1 aws codebuild start-build \
  --project-name plexus-prod-to-staging-data-mirror \
  --environment-variables-override \
    name=MIRROR_MODE,value=copy-bucket,type=PLAINTEXT \
    name=S3_CATEGORY,value=scoreResultAttachments,type=PLAINTEXT \
    name=S3_PREFIX,value=items/,type=PLAINTEXT \
    name=CONFIRM_DESTRUCTIVE,value=mirror-main-to-staging,type=PLAINTEXT
```

Re-enable staging stream consumers after all imports validate:

```bash
AWS_PROFILE=call-criteria AWS_REGION=us-east-1 aws codebuild start-build \
  --project-name plexus-prod-to-staging-data-mirror \
  --environment-variables-override \
    name=MIRROR_MODE,value=enable-consumers,type=PLAINTEXT \
    name=CONFIRM_DESTRUCTIVE,value=mirror-main-to-staging,type=PLAINTEXT
```
