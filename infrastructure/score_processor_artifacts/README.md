# Score Processor Artifacts

`infrastructure/score_processor_artifacts` is an isolated CDK app for publishing Plexus score processor container images. It does not deploy scoring queues, Lambda functions, event source mappings, or downstream environment resources.

The app exists so external deployment owners can consume a pinned score processor image without depending on the legacy Plexus infrastructure pipeline.

## Resources

The stack creates:

- an ECR repository for score processor image artifacts
- a CodePipeline V2 pipeline
- a CodeBuild project with Docker enabled
- generic SSM parameters containing the latest published artifact metadata for the configured channel

The pipeline builds `score-processor-lambda/Dockerfile.scoring-runtime` from a clean checkout and pushes an immutable `git-<source-sha>` tag. This dedicated image installs only the Plexus `scoring` extra; the existing `score-processor-lambda/Dockerfile` and legacy deployment pipeline continue to install `all`. The pipeline then resolves the ECR image digest and writes the digest-pinned image URI to SSM.

## Metadata

For the default `development` channel, the build writes:

- `/plexus/score-processor-artifacts/development/image-uri`
- `/plexus/score-processor-artifacts/development/image-digest`
- `/plexus/score-processor-artifacts/development/image-tag`
- `/plexus/score-processor-artifacts/development/source-revision`

Downstream deployments should deploy the digest-pinned `image-uri`, not a mutable tag.

## Configuration

Environment variables control the app without changing source:

```bash
export PLEXUS_SCORE_PROCESSOR_ARTIFACT_CHANNEL=development
export PLEXUS_SCORE_PROCESSOR_ARTIFACT_BRANCH=develop
export PLEXUS_SCORE_PROCESSOR_TRIGGER_ON_PUSH=true
```

The GitHub CodeConnections ARN is read from `PLEXUS_GITHUB_CONNECTION_ARN` when set, otherwise from `/plexus/github-connection-arn`.

## Validation

```bash
cd infrastructure/score_processor_artifacts
python -m pytest tests/unit -q
cdk synth
```

## Deployment

```bash
cd infrastructure/score_processor_artifacts
cdk deploy plexus-score-processor-artifacts-development
```
