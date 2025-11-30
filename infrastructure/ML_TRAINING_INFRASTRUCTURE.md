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

## Outputs

The stack creates the following CloudFormation outputs:

- **TrainingBucketName**: S3 bucket name (e.g., `plexus-development-training`)
- **TrainingBucketArn**: S3 bucket ARN
- **SageMakerTrainingRoleArn**: IAM role ARN for SageMaker training jobs

These are exported with names like:
- `plexus-{environment}-training-bucket-name`
- `plexus-{environment}-training-bucket-arn`
- `plexus-{environment}-sagemaker-training-role-arn`

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
