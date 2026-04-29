#!/usr/bin/env python3
import os
import sys
import subprocess
import aws_cdk as cdk
from stacks.metrics_aggregation_stack import MetricsAggregationStack

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Hardcode the stack pattern for production deployment
os.environ['AMPLIFY_STACK_PATTERN'] = 'amplify-d1cegb1ft4iove-main-branch'

# Build Lambda functions before deploying
print("Building Lambda functions...")
build_script = os.path.join(os.path.dirname(__file__), 'build_lambda.sh')
result = subprocess.run([build_script], cwd=os.path.dirname(__file__))
if result.returncode != 0:
    print("ERROR: Lambda build failed")
    sys.exit(1)
print()

app = cdk.App()

account = os.environ.get('CDK_DEFAULT_ACCOUNT')
# Use AWS_REGION from .env, fallback to CDK_DEFAULT_REGION, then us-west-2
region = os.environ.get('AWS_REGION') or os.environ.get('CDK_DEFAULT_REGION', 'us-west-2')
env = cdk.Environment(account=account, region=region)

print(f"Deploying to region: {region}")

# Deploy just the metrics aggregation stack for production
MetricsAggregationStack(
    app,
    "plexus-metrics-aggregation-production",
    environment="production",
    stack_name="plexus-metrics-aggregation-production",
    env=env
)

app.synth()
