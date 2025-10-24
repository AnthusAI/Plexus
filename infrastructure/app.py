#!/usr/bin/env python3
import os
import aws_cdk as cdk
from pipelines.staging_pipeline import StagingPipelineStack
from pipelines.production_pipeline import ProductionPipelineStack

app = cdk.App()

# Get AWS account and region from environment or use defaults
account = os.environ.get('CDK_DEFAULT_ACCOUNT')
region = os.environ.get('CDK_DEFAULT_REGION', 'us-east-1')

env = cdk.Environment(account=account, region=region)

# Create staging pipeline - watches staging branch
StagingPipelineStack(
    app,
    "plexus-infrastructure-staging-pipeline",
    env=env,
    description="Pipeline for deploying Plexus infrastructure to staging"
)

# Create production pipeline - watches main branch
ProductionPipelineStack(
    app,
    "plexus-infrastructure-production-pipeline",
    env=env,
    description="Pipeline for deploying Plexus infrastructure to production"
)

app.synth()
