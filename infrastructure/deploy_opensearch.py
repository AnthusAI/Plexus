#!/usr/bin/env python3
"""
Deploy dual-store stack for Semantic Reinforcement Memory (development).

Usage:
    cd infrastructure
    python deploy_opensearch.py

Prerequisites:
    - AWS CLI configured
    - CDK bootstrapped: cdk bootstrap aws://ACCOUNT/REGION

After deployment, set in your environment:
    export OPENSEARCH_ENDPOINT=<opensearch endpoint from stack output>   # optional
    export S3_VECTOR_BUCKET_NAME=<vector bucket from stack output>
    export S3_VECTOR_INDEX_NAME=<vector index from stack output>
    export EMBEDDING_CACHE_BUCKET=plexus-embeddings-development
"""
import os

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

from stacks.opensearch_stack import TopicMemoryVectorStack

app = cdk.App()

account = os.environ.get("CDK_DEFAULT_ACCOUNT")
region = os.environ.get("AWS_REGION") or os.environ.get("CDK_DEFAULT_REGION", "us-west-2")
env = cdk.Environment(account=account, region=region)

environment = os.environ.get("ENVIRONMENT", "development")

# Keep stack name/id unchanged for in-place migration in this feature branch.
TopicMemoryVectorStack(
    app,
    "plexus-opensearch-development",
    environment=environment,
    stack_name=f"plexus-opensearch-{environment}",
    env=env,
    description="OpenSearch + S3 Vectors + Embeddings for Semantic Reinforcement Memory",
)

app.synth()
