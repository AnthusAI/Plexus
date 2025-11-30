#!/usr/bin/env python3
"""
Deploy ML Training infrastructure.

This script deploys the ML training stack (S3 bucket and IAM roles) to your
AWS account for local testing before pushing to staging/production.

Usage:
    cd infrastructure

    # Deploy to development (default)
    cdk deploy -c environment=development --app "python deploy_ml_training.py"

    # Deploy to staging
    cdk deploy -c environment=staging --app "python deploy_ml_training.py"

    # Deploy to production
    cdk deploy -c environment=production --app "python deploy_ml_training.py"

Note: Staging and production are normally deployed via the CodePipeline.
This script is primarily for local development testing.
"""

import os
import sys
import aws_cdk as cdk
from stacks.ml_training_stack import MLTrainingStack

app = cdk.App()

# Get environment from context (default to development for local testing)
environment = app.node.try_get_context("environment") or "development"

if environment not in ["development", "staging", "production"]:
    print(f"ERROR: Invalid environment '{environment}'")
    print("Must be one of: development, staging, production")
    sys.exit(1)

# Get AWS account and region from environment or use defaults
account = os.environ.get('CDK_DEFAULT_ACCOUNT')
# Check standard AWS region environment variables, default to us-east-1
region = (
    os.environ.get('AWS_REGION') or
    os.environ.get('AWS_DEFAULT_REGION') or
    os.environ.get('PLEXUS_AWS_REGION_NAME') or
    'us-east-1'
)

env = cdk.Environment(account=account, region=region)

print(f"Deploying ML training infrastructure to {environment} environment in {region}")

# Deploy ML Training stack
MLTrainingStack(
    app,
    f"plexus-ml-training-{environment}",
    environment=environment,
    stack_name=f"plexus-ml-training-{environment}",
    env=env,
    description=f"ML training infrastructure (S3 bucket, IAM roles) for {environment}"
)

app.synth()
