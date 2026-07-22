# Async Score Processing Construct

`plexus.infrastructure.constructs.AsyncScoreProcessing` defines the reusable infrastructure pattern for async score processing.

It is intentionally deployment-owner agnostic. It does not choose account IDs, deployment pipelines, source branches, secret names, or downstream environment names.

## What It Creates

By default, the construct creates:

- standard request queue
- standard request dead-letter queue
- response queue
- response dead-letter queue
- score processor Lambda function from an ECR image reference
- SQS event source mapping
- Lambda execution role
- DLQ visibility alarms

Deployment owners can pass existing request/response queues instead of letting the construct create queues.

## Required Inputs

```python
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_secretsmanager as secretsmanager
from plexus.infrastructure.constructs import AsyncScoreProcessing
from plexus.infrastructure.constructs.async_score_processing import (
    AsyncScoreProcessingProps,
)

repository = ecr.Repository.from_repository_name(
    self,
    "ScoreProcessorRepository",
    repository_name="plexus/score-processor-artifacts-development",
)

runtime_config = secretsmanager.Secret.from_secret_name_v2(
    self,
    "RuntimeConfig",
    secret_name="plexus/development/config",
)

score_processing = AsyncScoreProcessing(
    self,
    "AsyncScoreProcessing",
    props=AsyncScoreProcessingProps(
        resource_prefix="my-platform-development-scoring",
        environment_name="development",
        image_repository=repository,
        image_tag_or_digest="sha256:...",
        runtime_config_secret=runtime_config,
    ),
)
```

Use an immutable image digest or immutable tag. Do not deploy mutable tags such as `latest`.

## Runtime Secret Mapping

The default JSON secret mapping is:

| Lambda environment variable | Secret JSON key |
| --- | --- |
| `PLEXUS_ACCOUNT_KEY` | `account-key` |
| `PLEXUS_API_KEY` | `api-key` |
| `PLEXUS_API_URL` | `api-url` |
| `OPENAI_API_KEY` | `openai-api-key` |
| `AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME` | `score-result-attachments-bucket` |
| `AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME` | `report-block-details-bucket` |

Override `secret_environment` when a deployment stores equivalent values under different JSON keys.

## Permissions

The construct grants only the baseline permissions it can infer:

- consume messages from the request queue
- send messages to the response queue
- read the runtime config secret
- pull the ECR image
- write Lambda logs

It does not grant broad DynamoDB, S3, SQS, or CloudWatch managed policies.

Deployment owners must pass extra scoped permissions through `additional_policy_statements` for any deployment-specific buckets, tables, or services.

Bedrock model access is opt-in through `bedrock_model_resources`.

## Exposed Properties

The construct exposes:

- `queues.request_queue`
- `queues.response_queue`
- `queues.request_dead_letter_queue`
- `queues.response_dead_letter_queue`
- `function`
- `role`
- `dead_letter_queue_alarms`
