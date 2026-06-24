#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.ecr_repositories_stack import EcrRepositoriesStack
from stacks.app_deployment_pipeline_stack import AppDeploymentPipelineStack
from stacks.console_worker_image_pipeline_stack import ConsoleWorkerImagePipelineStack
from stacks.lambda_score_processor_stack import LambdaScoreProcessorStack
from stacks.score_processor_image_pipeline_stack import ScoreProcessorImagePipelineStack
from stacks.shared.constants import LAMBDA_SCORE_PROCESSOR_REPOSITORY_BASE
from pipelines.production_pipeline import ProductionPipelineStack

app = cdk.App()

# Get AWS account and region from environment or use defaults
account = os.environ.get('CDK_DEFAULT_ACCOUNT')
region = os.environ.get('CDK_DEFAULT_REGION', 'us-west-2')

env = cdk.Environment(account=account, region=region)


def optional_int_env(name: str, default=None):
    value = os.environ.get(name)
    if value is None:
        return default
    if value.strip().lower() in ("", "none", "null", "unreserved"):
        return None
    return int(value)


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

# Create staging console worker image pipeline
ConsoleWorkerImagePipelineStack(
    app,
    "plexus-console-worker-staging-pipeline",
    environment="staging",
    branch="staging",
    env=env,
    description="Manual pipeline for building the staging Amplify console worker image"
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

# Create production console worker image pipeline
ConsoleWorkerImagePipelineStack(
    app,
    "plexus-console-worker-production-pipeline",
    environment="production",
    branch="main",
    env=env,
    description="Manual pipeline for building the production Amplify console worker image"
)

ScoreProcessorImagePipelineStack(
    app,
    "plexus-score-processor-production-image-pipeline",
    environment="production",
    branch="main",
    env=env,
    description="Manual pipeline for building the production Lambda score processor image"
)

LambdaScoreProcessorStack(
    app,
    "plexus-lambda-score-processor-production",
    environment="production",
    ecr_repository_name=f"{LAMBDA_SCORE_PROCESSOR_REPOSITORY_BASE}-production",
    response_queue_url=f"https://sqs.{region}.amazonaws.com/{account}/call-criteria-production-response-queue",
    standard_request_queue_arn=f"arn:aws:sqs:{region}:{account}:call-criteria-production-standard-request-queue",
    standard_request_queue_url=f"https://sqs.{region}.amazonaws.com/{account}/call-criteria-production-standard-request-queue",
    reserved_concurrency=optional_int_env("PLEXUS_SCORE_PROCESSOR_RESERVED_CONCURRENCY"),
    max_event_source_concurrency=int(os.environ.get("PLEXUS_SCORE_PROCESSOR_MAX_EVENT_SOURCE_CONCURRENCY", "5")),
    env=env,
    description="Production Lambda score processor consuming the Call Criteria production queue"
)

app.synth()
