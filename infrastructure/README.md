# Plexus Infrastructure

CDK-based infrastructure for Plexus custom AWS resources with automated deployment pipelines.

## Structure

```
infrastructure/
├── app.py                           # CDK app entry point
├── cdk.json                         # CDK configuration
├── requirements.txt                 # Python dependencies
│
├── stacks/                          # Infrastructure stacks
│   ├── scoring_worker_stack.py      # SQS queues for scoring workers
│   └── shared/
│       └── naming.py                # Naming convention utilities
│
└── pipelines/                       # Deployment pipelines
    ├── staging_pipeline.py          # Staging deployment (watches 'staging' branch)
    └── production_pipeline.py       # Production deployment (watches 'main' branch)
```

## Deployment Pipelines

### Staging Pipeline
- **Branch**: `staging`
- **Trigger**: Automatic on push to staging branch
- **Deploys**: All stacks with `environment="staging"`

### Production Pipeline
- **Branch**: `main`
- **Trigger**: Automatic on push to main branch
- **Deploys**: All stacks with `environment="production"`

## Setup

### Prerequisites
1. AWS CLI configured with appropriate credentials
2. Python 3.11+
3. Node.js (for CDK CLI)

### Initial Setup

1. **Install dependencies**:
   ```bash
   cd infrastructure
   pip install -r requirements.txt
   npm install -g aws-cdk
   ```

2. **Ensure GitHub Token Exists in AWS Secrets Manager**:
   - The pipelines use a secret named `github-token` from AWS Secrets Manager
   - If you don't already have this secret, create it:
     ```bash
     aws secretsmanager create-secret --name github-token --secret-string "YOUR_GITHUB_PAT"
     ```
   - The token needs repo access to AnthusAI/Plexus

3. **Bootstrap CDK** (one-time per account/region):
   ```bash
   cdk bootstrap aws://ACCOUNT_ID/REGION
   ```

4. **Deploy Pipelines**:
   ```bash
   # Clear Python cache first (if you've made changes)
   find . -type d -name __pycache__ -exec rm -rf {} +

   # Deploy both pipelines
   cdk deploy --all

   # Or deploy individually (use the stack construct IDs, not pipeline names)
   cdk deploy plexus-infrastructure-staging-pipeline
   cdk deploy plexus-infrastructure-production-pipeline
   ```

   **Note**: The pipelines are self-mutating. After the initial deployment:
   - Push to `staging` branch → triggers staging pipeline → deploys staging resources
   - Push to `main` branch → triggers production pipeline → deploys production resources

## Adding New Stacks

1. **Create new stack file** in `stacks/`:
   ```python
   # stacks/monitoring_stack.py
   from aws_cdk import Stack
   from constructs import Construct
   from .shared.naming import get_resource_name

   class MonitoringStack(Stack):
       def __init__(self, scope: Construct, construct_id: str, environment: str, **kwargs):
           super().__init__(scope, construct_id, **kwargs)
           # Add resources here
   ```

2. **Add to deployment stages** in both pipeline files:
   ```python
   # In StagingDeploymentStage and ProductionDeploymentStage
   MonitoringStack(
       self,
       "Monitoring",
       environment="staging",  # or "production"
       env=kwargs.get("env")
   )
   ```

3. **Commit and push** to appropriate branch - pipeline will automatically deploy

## Naming Convention

All resources follow: `plexus-{service}-{environment}-{resource}`

Examples:
- `plexus-scoring-staging-queue`
- `plexus-scoring-production-dlq`
- `plexus-monitoring-staging-dashboard`

Use the `get_resource_name()` helper from `stacks.shared.naming`:
```python
from stacks.shared.naming import get_resource_name

queue_name = get_resource_name("scoring", environment, "queue")
```

## Working with Stacks

### Local Development
```bash
# Synthesize CloudFormation templates
cdk synth

# See what will be deployed
cdk diff

# Deploy directly (not recommended - use pipelines)
cdk deploy
```

### Pipeline Updates
The pipelines are self-mutating - when you push changes to pipeline code, they will update themselves automatically.

## Troubleshooting

### Pipeline not triggering
- Verify GitHub connection is active in AWS Console
- Check CodePipeline execution history for errors
- Ensure branch names match exactly ('staging' or 'main')

### Stack deployment failures
- Check CloudWatch logs for CodeBuild execution
- Verify IAM permissions for pipeline role
- Check stack-specific resource limits (SQS quotas, etc.)

## Current Infrastructure

### Deployed Resources (per environment)

**SQS Queues** (in `scoring_worker_stack.py`):
- `plexus-scoring-{env}-standard-request-queue` - Main scoring requests
- `plexus-scoring-{env}-standard-request-dlq` - Failed requests after 3 retries
- `plexus-scoring-{env}-response-queue` - Scoring responses
- `plexus-scoring-{env}-response-dlq` - Failed responses after 3 retries

**Future Resources** (commented out, ready to enable):
- GPU request queue with DLQ

## Environment-Specific Resources

After deployment, you'll have two complete sets of resources:
- **Staging**: `plexus-scoring-staging-*`
- **Production**: `plexus-scoring-production-*`
