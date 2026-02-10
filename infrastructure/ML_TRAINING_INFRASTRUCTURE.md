# ML Training Infrastructure

This document describes the ML training infrastructure setup for Plexus.

## Overview

The ML training infrastructure consists of:
- **S3 Bucket**: `plexus-{environment}-training` for storing training data and model artifacts
- **IAM Roles**: SageMaker execution role with permissions to access the training bucket
- **Lifecycle Policies**: Automatic data retention and archival policies

## Bucket Structure

```
s3://plexus-{environment}-training/
├── training-data/
│   └── {scorecard_key}/
│       └── {score_key}/
│           └── data.csv           # Training dataset
├── models/
│   └── {scorecard_key}/
│       └── {score_key}/
│           └── model.tar.gz       # Trained model artifacts
└── training-code/
    └── {scorecard_key}/
        └── {score_key}/
            └── sourcedir.tar.gz   # Training code (for SageMaker)
```

## Environments

### Development

- **Bucket**: `plexus-development-training`
- **Lifecycle**: Training data deleted after 7 days, models after 30 days
- **Removal Policy**: DESTROY (bucket deleted when stack is destroyed)
- **Use Case**: Local development and testing

### Staging

- **Bucket**: `plexus-staging-training`
- **Lifecycle**: Data transitioned to Infrequent Access after 30 days, Glacier after 90 days
- **Removal Policy**: RETAIN (bucket preserved when stack is destroyed)
- **Use Case**: Pre-production testing

### Production

- **Bucket**: `plexus-production-training`
- **Lifecycle**: Same as staging
- **Removal Policy**: RETAIN
- **Use Case**: Production model training

## Deployment

### Local Development (Manual)

Deploy the ML training infrastructure to your development account for local testing:

```bash
cd infrastructure

# Synthesize the stack to verify configuration (defaults to development)
cdk synth -c environment=development --app "python deploy_ml_training.py"

# Deploy to your AWS account
cdk deploy -c environment=development --app "python deploy_ml_training.py"

# Or just omit environment (defaults to development)
cdk deploy --app "python deploy_ml_training.py"
```

After deployment, the bucket name will be output. Set the environment variable:

```bash
export PLEXUS_S3_BUCKET=plexus-development-training
```

**Note**: You can also use this script to manually deploy to staging/production if needed:
```bash
cdk deploy -c environment=staging --app "python deploy_ml_training.py"
```
However, staging and production are normally deployed automatically via the CodePipeline.

### Staging/Production (Automated via Pipeline)

The ML training stack is automatically deployed to staging and production environments via the CodePipeline infrastructure pipelines:

- **Staging**: Watches `staging` branch, deploys to staging environment
- **Production**: Watches `main` branch, deploys to production environment

The stack is included in the deployment stage in `pipelines/base_pipeline.py`.

## Training Platform vs. Deployment Target

**Important**: These are two separate concerns:

- **Training Platform** (`training.platform` or `--platform`): Where the model is **trained**
  - `local`: Train on your local machine (fast, good for development)
  - `sagemaker`: Train on SageMaker (for large datasets or GPU requirements)

- **Deployment Target** (`training.deployment_target`): Where the model is **deployed for inference**
  - `local`: Run predictions locally (not recommended for production)
  - `sagemaker_serverless`: Deploy to SageMaker Serverless Inference (auto-scaling, cost-effective)
  - `sagemaker_realtime`: Deploy to SageMaker real-time endpoint (dedicated instances)

**Default Behavior**: Models train **locally** by default, regardless of `deployment_target`.

### Score YAML Configuration

In your score YAML file:

```yaml
- name: My Score
  class: BERTClassifier
  training:
    platform: local                        # Where to TRAIN (default: local)
    deployment_target: sagemaker_serverless  # Where to DEPLOY for inference
```

You can train locally and still deploy to SageMaker for inference!

## Using the Infrastructure

### Training with Local Platform

Train models locally (default):

```bash
# Train using local platform (no --platform flag needed, local is default)
plexus train --scorecard "My Scorecard" --score "My Score" --yaml --data MyDataSource

# Or explicitly specify local platform
plexus train --scorecard "My Scorecard" --score "My Score" --yaml --data MyDataSource --platform local
```

The local trainer will:
1. Train the model on your local machine
2. Save artifacts to `models/{scorecard_key}/{score_key}/model.pt`
3. When you provision, the model is automatically uploaded to S3

### Training with SageMaker Platform

Train models on SageMaker (requires S3):

```bash
# Set the S3 bucket for your environment
export PLEXUS_S3_BUCKET=plexus-development-training

# Train using SageMaker platform
plexus train --scorecard "My Scorecard" --score "My Score" --platform sagemaker
```

The SageMaker trainer will:
1. Upload training data to S3
2. Launch SageMaker training job
3. Save trained model to S3

### Provisioning Endpoints

After training, provision a SageMaker endpoint:

```bash
# Provision endpoint (finds model in S3 or local)
plexus provision endpoint --scorecard "My Scorecard" --score "My Score"

# Or specify model location explicitly
plexus provision endpoint --scorecard "My Scorecard" --score "My Score" \
    --model-s3-uri s3://plexus-development-training/models/my-scorecard/my-score/model.tar.gz
```

## Real-time Inference Endpoints with Scale-to-Zero

Plexus supports provisioning real-time SageMaker inference endpoints with scale-to-zero capability for large fine-tuned models that require GPU instances.

### Environment Configuration

All SageMaker resources (endpoints, models, endpoint configs) include an environment prefix to prevent naming conflicts between development, staging, and production:

**Setting the environment:**
```bash
# In your .env file (recommended)
environment=development

# Or via environment variable
export PLEXUS_ENVIRONMENT=production
```

**Resource naming pattern:**
- Endpoints: `plexus-{environment}-{scorecard-key}-{score-key}-{deployment-type}`
- Models: `plexus-{environment}-{scorecard-key}-{score-key}-{hash}`
- Configs: `plexus-{environment}-{scorecard-key}-{score-key}-config-{hash}`

**Example:**
- Development: `plexus-development-my-scorecard-my-score-realtime`
- Production: `plexus-production-my-scorecard-my-score-realtime`

This ensures you can safely deploy the same score to multiple environments without resource name collisions.

### When to Use Real-time Endpoints

Use real-time endpoints instead of serverless when:
- Your model requires GPU acceleration (e.g., large language models with LoRA adapters)
- Your model exceeds serverless memory limits (4GB max)
- You need inference times longer than 6 minutes (serverless timeout)
- You want scale-to-zero cost optimization for sporadic traffic

### Inference Components Architecture

Real-time endpoints use **SageMaker Inference Components** to support LoRA (Low-Rank Adaptation) fine-tuned models:

- **Base Component**: Foundation model (e.g., Llama-3.1-8B-Instruct from HuggingFace)
- **Adapter Component**: LoRA adapter weights (from training, stored in S3)

This architecture allows:
- Multiple adapters to share the same base model (future enhancement)
- Efficient inference with minimal memory overhead
- Direct loading from HuggingFace Hub for base models

### Scale-to-Zero Behavior

Real-time endpoints automatically scale based on traffic:

1. **Idle State (0 instances)**: No cost except storage (~$0.01/month)
2. **First Request**: CloudWatch alarm detects `NoCapacityInvocationFailures`
3. **Scale-out**: Step scaling policy provisions 1 instance (~30-60 seconds cold start)
4. **Active State (1 instance)**: Processes requests with low latency
5. **Inactivity**: Target tracking policy scales down to 0 after cooldown period (default 5 minutes)

**Scaling Configuration**:
- **min_instances**: 0 (for scale-to-zero)
- **max_instances**: 1 (cost optimization, can be increased for horizontal scaling)
- **scale_in_cooldown**: 300 seconds (5 minutes idle before scaling down)
- **scale_out_cooldown**: 60 seconds (1 minute before scaling up)
- **target_invocations_per_instance**: 1.0 (triggers scale-out when needed)

### Score YAML Configuration

Configure real-time deployment in your score YAML file:

```yaml
name: My LoRA Classifier
class: LoRAClassifier  # Or BERTClassifier, etc.

# Deployment configuration for real-time inference
deployment:
  type: realtime
  instance_type: ml.g6e.xlarge  # GPU instance for large models
  min_instances: 0  # Scale to zero when idle
  max_instances: 1  # Single instance for cost efficiency
  scale_in_cooldown: 300  # 5 minutes before scaling down
  scale_out_cooldown: 60  # 1 minute before scaling up
  target_invocations_per_instance: 1.0

  # Inference components configuration
  base_model_hf_id: meta-llama/Llama-3.1-8B-Instruct  # HuggingFace model ID
  adapter_s3_uri: s3://my-bucket/adapters/my-adapter.tar.gz  # LoRA adapter from training

  # Optional: HuggingFace token for gated models
  hf_token: hf_xxxxxxxxxxxxx

  # Optional: Custom container image (defaults to DJL LMI if not specified)
  container_image: 763104351884.dkr.ecr.us-east-1.amazonaws.com/djl-inference:0.31.0-lmi13.0.0-cu124

  # Optional: Environment variables for vLLM inference
  environment:
    OPTION_ROLLING_BATCH: vllm
    OPTION_ENABLE_LORA: "true"
    OPTION_MAX_LORAS: "10"
    OPTION_MAX_LORA_RANK: "64"
    OPTION_MAX_MODEL_LEN: "4096"
    OPTION_GPU_MEMORY_UTILIZATION: "0.8"
```

**Simpler Configuration (Base Model Only, No Adapter)**:
```yaml
deployment:
  type: realtime
  instance_type: ml.g6e.xlarge
  min_instances: 0
  max_instances: 1
  base_model_hf_id: meta-llama/Llama-3.1-8B-Instruct
  # No adapter_s3_uri means base component only
```

### Provisioning Real-time Endpoints

#### Using YAML Configuration

Provision an endpoint using the deployment config from your score YAML:

```bash
# Provision using config from score YAML
plexus provision endpoint --scorecard "My Scorecard" --score "My Score"

# Cross-region deployment (e.g., to us-east-1 for quota availability)
plexus provision endpoint --scorecard "My Scorecard" --score "My Score" --region us-east-1
```

#### CLI Overrides

Override YAML configuration with CLI arguments:

```bash
# Override instance type
plexus provision endpoint --scorecard "My Scorecard" --score "My Score" \
  --instance-type ml.g5.2xlarge

# Override scaling parameters
plexus provision endpoint --scorecard "My Scorecard" --score "My Score" \
  --min-instances 1 \
  --max-instances 2 \
  --scale-in-cooldown 600
```

**Available CLI Options**:
- `--deployment-type`: Override deployment type (serverless or realtime)
- `--instance-type`: Override instance type (e.g., ml.g5.xlarge, ml.g6e.xlarge)
- `--min-instances`: Override minimum instance count (0 for scale-to-zero)
- `--max-instances`: Override maximum instance count
- `--scale-in-cooldown`: Override scale-in cooldown (seconds)
- `--scale-out-cooldown`: Override scale-out cooldown (seconds)
- `--target-invocations`: Override target invocations per instance
- `--region`: Deploy to specific AWS region (infrastructure only, doesn't affect DB)

### Instance Type Selection

Common GPU instance types for real-time endpoints:

| Instance Type | vCPUs | GPU Memory | Cost/Hour* | Best For |
|---------------|-------|------------|------------|----------|
| ml.g5.xlarge | 4 | 24 GB | $1.41 | Small models (7B-13B params) |
| ml.g5.2xlarge | 8 | 24 GB | $1.69 | Medium models (13B-30B params) |
| ml.g6e.xlarge | 4 | 22 GB | $1.15 | Cost-optimized for 7B-13B models |
| ml.g6e.2xlarge | 8 | 45 GB | $1.69 | Medium to large models |

*Approximate costs as of 2026. With scale-to-zero, you only pay when instances are running.

### Invoking Real-time Endpoints

Use boto3 to invoke endpoints with inference components:

```python
import boto3
import json

client = boto3.client('sagemaker-runtime', region_name='us-east-1')

payload = {
    "inputs": "Your input text here",
    "parameters": {
        "max_new_tokens": 100,
        "temperature": 0.7
    }
}

response = client.invoke_endpoint(
    EndpointName='plexus-my-scorecard-my-score-realtime',
    InferenceComponentName='plexus-my-scorecard-my-score-realtime-adapter',  # Use adapter component
    Body=json.dumps(payload),
    ContentType='application/json'
)

result = json.loads(response['Body'].read())
print(result)
```

**Important**:
- Always use `InferenceComponentName` to specify the adapter component
- The endpoint name follows the pattern: `plexus-{environment}-{scorecard-key}-{score-key}-realtime`
- Environment comes from `.env` file (`environment=development`) or `PLEXUS_ENVIRONMENT` env var
- Component names: `{endpoint-name}-base` and `{endpoint-name}-adapter`
- Don't use AWS CLI `invoke-endpoint` as it gzip-compresses payloads (causes parsing errors)

### Monitoring Scale-to-Zero

Monitor endpoint scaling via CloudWatch metrics:

```bash
# Check current instance count
aws cloudwatch get-metric-statistics \
  --namespace AWS/SageMaker \
  --metric-name InstanceCount \
  --dimensions Name=EndpointName,Value=plexus-my-scorecard-my-score-realtime \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average \
  --region us-east-1

# Check for capacity failures (triggers scale-out)
aws cloudwatch get-metric-statistics \
  --namespace AWS/SageMaker \
  --metric-name NoCapacityInvocationFailures \
  --dimensions Name=InferenceComponentName,Value=plexus-my-scorecard-my-score-realtime-adapter \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum \
  --region us-east-1
```

Or use the SageMaker console to view endpoint metrics in real-time.

### Architecture Components

The real-time provisioning creates these AWS resources:

1. **SageMaker Endpoint**: Named `plexus-{environment}-{scorecard-key}-{score-key}-realtime`
2. **Endpoint Configuration**: With `ManagedInstanceScaling` (min: 0, max: 1)
3. **Base Inference Component**: Loads foundation model from HuggingFace
4. **Adapter Inference Component**: Loads LoRA adapter from S3 (via custom resource Lambda)
5. **Application Auto Scaling Target**: `inference-component/{base-component-name}`
6. **Target Tracking Policy**: Scales IN to 0 after idle period
7. **Step Scaling Policy**: Scales OUT to 1 on capacity failures
8. **CloudWatch Alarms**: Monitor `NoCapacityInvocationFailures` for both base and adapter

**Custom Resource Lambda**: Workaround for CloudFormation limitation where adapter components can't be created natively. The Lambda handler creates the adapter component via boto3 API after the base component is ready.

**Environment Isolation**: The `{environment}` prefix ensures that development, staging, and production endpoints have unique names and never conflict. The environment is determined from your `.env` file (`environment=development`) or `PLEXUS_ENVIRONMENT` environment variable.

### Cross-Region Deployment

Real-time endpoints can be deployed to different regions than your database:

```bash
# Deploy infrastructure to us-east-1 (e.g., for GPU quota)
# Database connections remain in us-west-2
plexus provision endpoint --scorecard "My Scorecard" --score "My Score" --region us-east-1
```

**Prerequisites for cross-region deployment**:
1. IAM role must be exported in target region (created via CloudFormation export stack)
2. LoRA adapter S3 bucket permissions added to SageMaker inference role
3. HuggingFace token (if using gated models) configured in score YAML

### Cost Optimization

Real-time endpoints with scale-to-zero are highly cost-effective:

**Cost Breakdown**:
- **Active (1 instance)**: ~$1.15-$1.69/hour (depending on instance type)
- **Idle (0 instances)**: ~$0.01/month (storage only)
- **Cold start**: ~30-60 seconds (first request after scale-down)

**Example Monthly Costs** (ml.g6e.xlarge at $1.15/hour):
- 1 hour/day active: ~$35/month
- 8 hours/day active: ~$280/month
- 24/7 active: ~$840/month
- Scale-to-zero idle: ~$0.01/month

Compare to always-on real-time endpoint: ~$840/month regardless of usage.

### LoRAClassifier Score Class

The `LoRAClassifier` is a generic score class for any foundation model + LoRA adapter:

```python
from plexus.scores import LoRAClassifier

class MyCustomScore(LoRAClassifier):
    """
    Custom score using LoRA fine-tuned Llama model.

    The deployment configuration in the score YAML specifies:
    - base_model_hf_id: Foundation model from HuggingFace
    - adapter_s3_uri: LoRA adapter from training
    """

    def predict(self, item) -> Dict[str, Any]:
        # Custom prediction logic
        pass

    def score(self, item) -> Dict[str, Any]:
        # Custom scoring logic
        pass
```

**Key Methods**:
- `supports_training()`: Returns `False` (LoRA training not yet integrated)
- `supports_provisioning()`: Returns `True`
- `provision_endpoint()`: Validates LoRA requirements and provisions endpoint

### Troubleshooting

#### Endpoint Stuck Scaling

If endpoint doesn't scale down after expected idle time:

1. Check CloudWatch metrics for recent invocations
2. Verify `scale_in_cooldown` is configured correctly (default 300 seconds)
3. Check Application Auto Scaling target tracking policy status
4. Review CloudWatch Logs for base component: `/aws/sagemaker/InferenceComponents/{base-component-name}`

#### Cold Start Failures

If first request after scale-down fails:

1. This is expected - the first 1-2 requests may fail while instance scales up
2. CloudWatch alarm will trigger after seeing `NoCapacityInvocationFailures`
3. Step scaling policy provisions instance (~30-60 seconds)
4. Retry request after scale-out completes

#### Container Fails to Load Model

Check CloudWatch Logs for base component:

```bash
aws logs tail /aws/sagemaker/InferenceComponents/plexus-my-scorecard-my-score-realtime-base \
  --since 30m --region us-east-1 --format short
```

Common issues:
- **HuggingFace token invalid**: Update `hf_token` in score YAML
- **Adapter S3 permissions**: Verify SageMaker inference role has access to adapter bucket
- **Memory exhaustion**: Try larger instance type or reduce `OPTION_GPU_MEMORY_UTILIZATION`

#### Payload Format Errors

If you get "Input Parsing failed" or Unicode decode errors:

- **Don't use AWS CLI** `invoke-endpoint` (it gzip-compresses payloads)
- **Use boto3** `invoke_endpoint()` with plain JSON body
- Ensure `ContentType='application/json'` is set
- Use DJL LMI expected format: `{"inputs": "...", "parameters": {...}}`

## Outputs

The stack creates the following CloudFormation outputs:

- **TrainingBucketName**: S3 bucket name (e.g., `plexus-development-training`)
- **TrainingBucketArn**: S3 bucket ARN
- **SageMakerTrainingRoleArn**: IAM role ARN for SageMaker training jobs
- **SageMakerInferenceRoleArn**: IAM role ARN for SageMaker inference endpoints

These are exported with names like:
- `plexus-{environment}-training-bucket-name`
- `plexus-{environment}-training-bucket-arn`
- `plexus-{environment}-sagemaker-training-role-arn`
- `plexus-{environment}-sagemaker-inference-role-arn`

## Cost Optimization

### Development

- Training data automatically deleted after 7 days
- Models automatically deleted after 30 days
- Use lifecycle policies to minimize storage costs

### Staging/Production

- Training data transitioned to Infrequent Access after 30 days (70% cost reduction)
- Training data archived to Glacier after 90 days (85% cost reduction)
- Models kept in Standard storage for fast access

## Cleanup

### Development

```bash
# Delete the development stack and all resources
cdk destroy -c environment=development --app "python deploy_ml_training.py"

# Or just omit environment (defaults to development)
cdk destroy --app "python deploy_ml_training.py"
```

This will delete the S3 bucket and all objects (because `RemovalPolicy.DESTROY` is set for development).

### Staging/Production

The staging and production buckets are retained when the stack is destroyed (because `RemovalPolicy.RETAIN` is set). This prevents accidental data loss.

To manually delete:

```bash
# Empty the bucket first
aws s3 rm s3://plexus-staging-training --recursive

# Then delete the stack
cdk destroy plexus-ml-training-staging
```

## Troubleshooting

### Bucket Already Exists

If you get an error that the bucket already exists:

```bash
# Check if bucket exists
aws s3 ls s3://plexus-development-training

# If it exists from a previous deployment, either:
# 1. Use the existing bucket (just update the stack)
cdk deploy --app "python deploy_ml_training_development.py"

# 2. Or delete it and redeploy
aws s3 rb s3://plexus-development-training --force
cdk deploy --app "python deploy_ml_training_development.py"
```

### Permission Denied

If you get permission errors accessing S3:

1. Verify your AWS credentials are configured
2. Verify the bucket was created: `aws s3 ls s3://plexus-development-training`
3. Verify the PLEXUS_S3_BUCKET environment variable is set: `echo $PLEXUS_S3_BUCKET`

### Training Fails to Upload

If training fails to upload data to S3:

1. Check that the bucket exists: `aws s3 ls s3://plexus-development-training`
2. Check bucket permissions: `aws s3api get-bucket-policy --bucket plexus-development-training`
3. Verify your AWS credentials have write access
