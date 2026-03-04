#!/usr/bin/env python3
"""
Deploy OpenSearch + Embeddings stack for Vector Topic Memory (development).

Usage:
    cd infrastructure
    python deploy_opensearch.py

Prerequisites:
    - AWS CLI configured
    - CDK bootstrapped: cdk bootstrap aws://ACCOUNT/REGION
    - Service-linked role for OpenSearch (created automatically by AWS Console, or):
      aws iam create-service-linked-role --aws-service-name es.amazonaws.com

After deployment, set in your environment:
    export OPENSEARCH_ENDPOINT=<endpoint from stack output>
    export EMBEDDING_CACHE_BUCKET=plexus-embeddings-development
"""
import os
import sys

# Load .env if present
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

import aws_cdk as cdk

from stacks.opensearch_stack import OpenSearchStack

app = cdk.App()

account = os.environ.get("CDK_DEFAULT_ACCOUNT")
region = os.environ.get("AWS_REGION") or os.environ.get("CDK_DEFAULT_REGION", "us-west-2")
env = cdk.Environment(account=account, region=region)

environment = os.environ.get("ENVIRONMENT", "development")

OpenSearchStack(
    app,
    "plexus-opensearch-development",
    environment=environment,
    stack_name=f"plexus-opensearch-{environment}",
    env=env,
    description="OpenSearch + Embeddings for Vector Topic Memory",
)

app.synth()
