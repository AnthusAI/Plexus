#!/usr/bin/env python3
from __future__ import annotations

import os

import aws_cdk as cdk

from stacks.score_processor_artifact_pipeline_stack import (
    ScoreProcessorArtifactPipelineStack,
)


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


app = cdk.App()

account = os.environ.get("CDK_DEFAULT_ACCOUNT")
region = os.environ.get("CDK_DEFAULT_REGION", "us-east-1")
channel = os.environ.get("PLEXUS_SCORE_PROCESSOR_ARTIFACT_CHANNEL", "development")
branch = os.environ.get("PLEXUS_SCORE_PROCESSOR_ARTIFACT_BRANCH", "develop")
github_owner = os.environ.get("PLEXUS_SCORE_PROCESSOR_GITHUB_OWNER", "AnthusAI")
github_repo = os.environ.get("PLEXUS_SCORE_PROCESSOR_GITHUB_REPO", "Plexus")
trigger_on_push = _bool_env("PLEXUS_SCORE_PROCESSOR_TRIGGER_ON_PUSH", True)

env = cdk.Environment(account=account, region=region)

ScoreProcessorArtifactPipelineStack(
    app,
    f"plexus-score-processor-artifacts-{channel}",
    channel=channel,
    branch=branch,
    github_owner=github_owner,
    github_repo=github_repo,
    trigger_on_push=trigger_on_push,
    env=env,
    description=(
        "Publishes immutable Plexus score processor container image artifacts"
    ),
)

app.synth()

