#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.ecr_repositories_stack import EcrRepositoriesStack
from stacks.app_deployment_pipeline_stack import AppDeploymentPipelineStack
from pipelines.production_pipeline import ProductionPipelineStack

app = cdk.App()

# Get AWS account and region from environment or use defaults
account = os.environ.get('CDK_DEFAULT_ACCOUNT')
region = os.environ.get('CDK_DEFAULT_REGION', 'us-west-2')

env = cdk.Environment(account=account, region=region)

# Create ECR repositories stack (deploy this first)
# Contains repositories for both staging and production
EcrRepositoriesStack(
    app,
    "plexus-ecr-repositories",
    stack_name="plexus-ecr-repositories",
    env=env,
    description="ECR repositories for Lambda container images (staging and production)"
)

# Create production pipeline - watches main branch
# Note: Staging infrastructure pipeline removed - staging only uses app deployment pipeline
ProductionPipelineStack(
    app,
    "plexus-infrastructure-production-pipeline",
    env=env,
    description="Pipeline for deploying Plexus infrastructure to production"
)

# Create staging app deployment pipeline
AppDeploymentPipelineStack(
    app,
    "plexus-app-deployment-staging-pipeline",
    environment="staging",
    branch="staging",
    env=env,
    description="Pipeline for deploying Plexus application code to staging"
)

# Create production app deployment pipeline
AppDeploymentPipelineStack(
    app,
    "plexus-app-deployment-production-pipeline",
    environment="production",
    branch="main",
    env=env,
    description="Pipeline for deploying Plexus application code to production"
)

app.synth()
