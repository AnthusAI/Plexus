# ML Training and Inference Infrastructure - Master Plan

**Last Updated:** 2025-01-28
**Status:** Phase 1 Complete, Phase 2 In Progress
**Document Type:** Unified implementation plan and status tracker

---

## Executive Summary

This document provides a comprehensive plan for Plexus's ML training and inference infrastructure, covering:

1. **Training Infrastructure** (✅ Phase 1 Complete): Unified training system for local and SageMaker training
2. **Endpoint Provisioning** (🔄 Phase 2 Current): SageMaker Serverless endpoint deployment
3. **Production Inference** (📋 Phase 3 Planned): Auto-discovery and remote prediction via endpoints

**Key Achievement**: `plexus train` now works for ML models (BERTClassifier) locally.

**Current Gap**: Trained models cannot yet be provisioned to SageMaker endpoints or used in production predictions.

**Next Milestone**: Enable `plexus provision` command to deploy trained models to SageMaker Serverless endpoints.

---

## Table of Contents

1. [Current State](#current-state)
2. [Architecture Overview](#architecture-overview)
3. [Phase 1: Training Infrastructure](#phase-1-training-infrastructure-completed)
4. [Phase 2: Endpoint Provisioning](#phase-2-endpoint-provisioning-in-progress)
5. [Phase 3: Production Inference](#phase-3-production-inference-planned)
6. [Implementation Roadmap](#implementation-roadmap)
7. [Testing Strategy](#testing-strategy)
8. [Configuration Reference](#configuration-reference)
9. [Troubleshooting](#troubleshooting)

---

## Current State

### What Works Today ✅

**Training:**
```bash
# Train a BERT classifier locally
plexus train --scorecard "SelectQuote HCS" --score "Compliance Check" \
  --data feedback-items --yaml
```

**Evaluation:**
```bash
# Evaluate model accuracy
plexus evaluate accuracy --scorecard "SelectQuote HCS" \
  --score "Compliance Check" --number-of-samples 100 --yaml
```

**Prediction (Local Only):**
```bash
# Predict using local model
plexus predict --scorecard "SelectQuote HCS" --score "Compliance Check" \
  --item 12345 --yaml
```

### What Doesn't Work Yet ❌

**SageMaker Endpoint Provisioning:**
- Cannot provision trained models to SageMaker Serverless endpoints
- No `plexus provision` command
- No integration with CDK deployment from Python

**Production Inference:**
- `plexus predict` only uses local models
- Cannot invoke SageMaker Runtime API
- No auto-discovery of deployed endpoints

**Model Packaging:**
- Trained models don't include inference code
- No standard packaging for SageMaker inference containers

### Reference Architecture

The sibling project **text-classifier-distillation** demonstrates:
- Training → Model packaging → CDK deployment → Serverless endpoint
- Predictable endpoint naming: `multi-task-classifier`
- Direct SageMaker Runtime invocation (~270ms latency)
- Optional Lambda/API Gateway wrapper (~460ms latency)

**Our Goal:** Replicate this pattern for Plexus scores.

---

## Architecture Overview

### End-to-End Flow (Target State)

```
┌─────────────────────────────────────────────────────────┐
│ Developer: plexus train --scorecard X --score Y         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │ 1. Training (Local/SageMaker)│
        │    → model saved locally OR  │
        │    → model.tar.gz in S3      │
        └──────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Developer: plexus provision --scorecard X --score Y     │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │ 1. Find Trained Model        │
        │    → Local or S3             │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │ 2. Package for Inference     │
        │    → Add inference.py        │
        │    → Upload to S3            │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │ 3. CDK Deployment            │
        │    → SageMaker Model         │
        │    → Endpoint Config         │
        │    → Endpoint (Serverless)   │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │ Endpoint: plexus-{sc}-{s}-   │
        │           serverless          │
        │ Status: InService             │
        └──────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Production: plexus predict --scorecard X --score Y      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │ Score.predict()              │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │ Check for SageMaker Endpoint │
        │ via naming convention        │
        └──────────┬───────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
    Found                 Not Found
        │                     │
        ▼                     ▼
┌──────────────┐      ┌──────────────┐
│ Invoke       │      │ Load local   │
│ SageMaker    │      │ model from   │
│ Runtime API  │      │ disk         │
└──────┬───────┘      └──────┬───────┘
       │                     │
       └──────────┬──────────┘
                  │
                  ▼
          ┌───────────────┐
          │ Score.Result  │
          └───────────────┘
```

### Key Design Principles

1. **Convention Over Configuration**: Predictable naming eliminates database dependencies
2. **AWS API as Source of Truth**: Check endpoint existence via `describe_endpoint()`
3. **Idempotent Provisioning**: CDK can be run repeatedly without side effects
4. **Graceful Fallback**: Missing endpoint → use local model automatically
5. **Minimal Schema Changes**: No GraphQL changes required for MVP

---

## Phase 1: Training Infrastructure (✅ Completed)

### Goal
Enable local and SageMaker training for ML classifiers with unified CLI.

### Implementation Summary

**Unified Trainer Abstraction:**
- Abstract `Trainer` base class with Template Method pattern
- `MLTrainerLocal`: Train PyTorch models locally
- `MLTrainerSageMaker`: Launch SageMaker training jobs (code complete, untested)
- `LLMFineTuneTrainer`: Generate JSON-L files for OpenAI fine-tuning
- `TrainingDispatcher`: Route to correct trainer based on score config

**BERTClassifier Implementation:**
- PyTorch-based binary classifier
- Configurable BERT base model (default: distilbert-base-uncased)
- Trainable layer control, dropout, GPU support
- Automatic model saving to `models/{scorecard_key}/{score_key}/`

**Supporting Infrastructure:**
- `DatasetCache`: Unified caching for training/eval datasets
- Path normalization via `normalize_name_to_key()`
- Scorecard name injection into Score instances
- Parallel evaluation with asyncio.gather()

### Key Files Created
```
plexus/
├── training/
│   ├── trainer.py                    # Abstract base class
│   ├── ml_trainer_local.py           # Local ML training
│   ├── ml_trainer_sagemaker.py       # SageMaker ML training (untested)
│   ├── llm_finetune_trainer.py       # LLM fine-tuning
│   ├── training_dispatcher.py        # Routing logic
│   └── utils.py                      # Path normalization
├── scores/
│   └── BERTClassifier.py             # PyTorch BERT classifier
└── data/
    └── DatasetCache.py               # Unified data caching
```

### Usage
```bash
# Local training (works today)
plexus train --scorecard "SelectQuote HCS" --score "Compliance Check" --yaml

# SageMaker training (code exists, not tested)
plexus train --scorecard "SelectQuote HCS" --score "Compliance Check" \
  --platform sagemaker
```

### Known Limitations

**Model Loading Bottleneck:**
- BERTClassifier loads PyTorch model from disk for EVERY prediction
- ~250ms overhead per prediction
- Root cause: `Scorecard.get_score_result()` creates new instance each time
- Mitigation: Parallel evaluation (20 concurrent predictions)
- Status: Working but suboptimal

**SageMaker Training:**
- Code complete but untested in production
- Requires AWS infrastructure provisioning
- Training script generation incomplete

---

## Phase 2: Endpoint Provisioning (🔄 In Progress)

### Goal
Enable provisioning of trained models to SageMaker Serverless Inference endpoints via `plexus provision` command.

### Design Principle: Separation of Concerns
**Training and provisioning are separate operations:**
- `plexus train` → Trains model, saves locally or to S3
- `plexus provision` → Takes trained model, provisions SageMaker endpoint
- No `--deploy` flag on `plexus train` command
- Follows same DRY pattern as `plexus train` and `plexus evaluate` for scorecard/score resolution

### Naming Convention (Core Design Decision)

All SageMaker resources follow this pattern:

```
Endpoint:        plexus-{scorecard_key}-{score_key}-{deployment_type}
Model:           plexus-{scorecard_key}-{score_key}-model-{hash}
Endpoint Config: plexus-{scorecard_key}-{score_key}-config-{hash}
```

**Examples:**
```
Endpoint: plexus-selectquote-hcs-compliance-check-serverless
Model:    plexus-selectquote-hcs-compliance-check-model-abc123ef
Config:   plexus-selectquote-hcs-compliance-check-config-abc123ef
```

**Rationale:**
- `{scorecard_key}`: From `get_scorecard_key()` (normalized)
- `{score_key}`: From `get_score_key()` (normalized)
- `{deployment_type}`: `serverless` | `realtime`
- `{hash}`: MD5 of model S3 path for Model/Config uniqueness

**Why this matters:**
- Enables endpoint discovery without database lookups
- AWS API becomes source of truth
- Idempotent CDK deployments
- Human-readable endpoint names

### S3 Path Conventions

```
Training artifacts:
s3://{bucket}/training-output/{training-job-name}/model.tar.gz

Inference-ready models:
s3://{bucket}/models/{scorecard_key}/{score_key}/model.tar.gz

Training code:
s3://{bucket}/training-code/{scorecard_key}/{score_key}/{timestamp}/sourcedir.tar.gz
```

### Model Packaging Workflow

**Problem:** Trained models lack inference code for SageMaker containers.

**Solution:** Package model with inference handler.

**Required Structure:**
```
model.tar.gz
├── model.pt              # PyTorch weights
├── tokenizer/            # BERT tokenizer files
├── config.json           # Model config
└── code/
    ├── inference.py      # SageMaker inference handler
    ├── requirements.txt  # Python dependencies
    └── model.py          # Model architecture
```

**Inference Handler Template:**
```python
# plexus/training/templates/inference_bert.py.template

def model_fn(model_dir: str):
    """Load model from model_dir."""
    model = torch.load(os.path.join(model_dir, 'model.pt'))
    model.eval()
    return model

def input_fn(request_body: str, content_type: str):
    """Parse input."""
    return json.loads(request_body)

def predict_fn(input_data: dict, model):
    """Run prediction."""
    text = input_data.get('text', '')
    with torch.no_grad():
        prediction = model.predict(text)
    return {'value': prediction, 'explanation': ''}

def output_fn(prediction: dict, accept: str):
    """Format output."""
    return json.dumps(prediction)
```

**Packaging Function:**
```python
def package_model_for_inference(
    training_job_name: str,
    model_s3_uri: str,
    score_instance: Score
) -> str:
    """
    Download model, add inference code, repackage for SageMaker.

    Returns:
        S3 URI to inference-ready model.tar.gz
    """
    # 1. Download model artifacts
    local_dir = download_from_s3(model_s3_uri)

    # 2. Generate inference.py from Score class
    inference_code = generate_inference_code(score_instance)

    # 3. Add inference code to model.tar.gz
    code_dir = os.path.join(local_dir, 'code')
    os.makedirs(code_dir)
    with open(os.path.join(code_dir, 'inference.py'), 'w') as f:
        f.write(inference_code)

    # 4. Repackage and upload
    inference_s3_uri = f"s3://{bucket}/models/{scorecard_key}/{score_key}/model.tar.gz"
    upload_tarball(local_dir, inference_s3_uri)

    return inference_s3_uri
```

### CDK Stack for Endpoint Provisioning

**Stack Structure:**
```python
# plexus/cli/deployment/cdk/stacks/sagemaker_inference_stack.py

class PlexusSageMakerInferenceStack(Stack):
    """
    Provisions SageMaker Serverless Inference endpoint.

    Resources:
    1. SageMaker Model (with PyTorch container + model.tar.gz)
    2. SageMaker Endpoint Configuration (serverless settings)
    3. SageMaker Endpoint (with conventional name)
    """

    def __init__(self, scope, construct_id,
                 scorecard_key: str,
                 score_key: str,
                 model_s3_uri: str,
                 deployment_type: str = 'serverless',
                 memory_mb: int = 4096,
                 max_concurrency: int = 10,
                 **kwargs):

        super().__init__(scope, construct_id, **kwargs)

        # Conventional endpoint name
        endpoint_name = f"plexus-{scorecard_key}-{score_key}-{deployment_type}"

        # Model name with hash for versioning
        model_hash = hashlib.md5(model_s3_uri.encode()).hexdigest()[:8]
        model_name = f"plexus-{scorecard_key}-{score_key}-model-{model_hash}"

        # IAM role for SageMaker
        sagemaker_role = iam.Role(
            self, "SageMakerExecutionRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSageMakerFullAccess"
                )
            ]
        )

        # SageMaker Model
        pytorch_image = f"763104351884.dkr.ecr.{self.region}.amazonaws.com/pytorch-inference:2.3.0-cpu-py311"

        model = sagemaker.CfnModel(
            self, "Model",
            execution_role_arn=sagemaker_role.role_arn,
            primary_container=sagemaker.CfnModel.ContainerDefinitionProperty(
                image=pytorch_image,
                model_data_url=model_s3_uri,
                environment={
                    "SAGEMAKER_PROGRAM": "inference.py",
                    "SAGEMAKER_SUBMIT_DIRECTORY": model_s3_uri
                }
            ),
            model_name=model_name
        )

        # Serverless Endpoint Configuration
        endpoint_config = sagemaker.CfnEndpointConfig(
            self, "EndpointConfig",
            endpoint_config_name=f"{endpoint_name}-config-{model_hash}",
            production_variants=[
                sagemaker.CfnEndpointConfig.ProductionVariantProperty(
                    model_name=model.model_name,
                    variant_name="AllTraffic",
                    serverless_config=sagemaker.CfnEndpointConfig.ServerlessConfigProperty(
                        max_concurrency=max_concurrency,
                        memory_size_in_mb=memory_mb
                    )
                )
            ]
        )
        endpoint_config.add_dependency(model)

        # SageMaker Endpoint
        endpoint = sagemaker.CfnEndpoint(
            self, "Endpoint",
            endpoint_name=endpoint_name,
            endpoint_config_name=endpoint_config.endpoint_config_name
        )
        endpoint.add_dependency(endpoint_config)

        # Outputs
        CfnOutput(self, "EndpointName", value=endpoint_name)
        CfnOutput(self, "ModelDataURL", value=model_s3_uri)
```

**CDK App:**
```python
# plexus/cli/deployment/cdk/app.py

import aws_cdk as cdk
from stacks.sagemaker_inference_stack import PlexusSageMakerInferenceStack

app = cdk.App()

# Get context from CLI invocation
scorecard_key = app.node.try_get_context("scorecard_key")
score_key = app.node.try_get_context("score_key")
model_s3_uri = app.node.try_get_context("model_s3_uri")
deployment_type = app.node.try_get_context("deployment_type") or "serverless"

if not model_s3_uri:
    raise ValueError("model_s3_uri is required")

PlexusSageMakerInferenceStack(
    app,
    f"PlexusInference-{scorecard_key}-{score_key}",
    scorecard_key=scorecard_key,
    score_key=score_key,
    model_s3_uri=model_s3_uri,
    deployment_type=deployment_type
)

app.synth()
```

**Invocation from Python:**
```python
def deploy_endpoint(scorecard_key: str, score_key: str, model_s3_uri: str):
    """Deploy endpoint using CDK."""
    cdk_dir = Path(__file__).parent.parent / "deployment" / "cdk"

    cmd = [
        "cdk", "deploy",
        "--app", "python3 app.py",
        "--require-approval", "never",
        "-c", f"scorecard_key={scorecard_key}",
        "-c", f"score_key={score_key}",
        "-c", f"model_s3_uri={model_s3_uri}",
        "-c", "deployment_type=serverless"
    ]

    subprocess.run(cmd, cwd=cdk_dir, check=True)
    print(f"✓ Deployed endpoint: plexus-{scorecard_key}-{score_key}-serverless")
```

### Idempotency Strategy

**Key Insight:** Endpoint NAME is deterministic, but underlying resources are versioned.

```
Endpoint:        plexus-selectquote-compliance-serverless  (stable)
   ↓
EndpointConfig:  plexus-selectquote-compliance-config-abc123  (versioned)
   ↓
Model:           plexus-selectquote-compliance-model-abc123  (versioned)
   ↓
S3:              s3://.../training-output/{job-name}/model.tar.gz  (unique)
```

**Behavior on Repeated CDK Deployment:**

1. **Same model S3 path**: CDK detects no changes → no update
2. **Different model S3 path**: CDK creates new Model + EndpointConfig → updates Endpoint reference
3. **Endpoint name unchanged**: Always discoverable at `plexus-{sc}-{s}-serverless`

**Decision Function:**
```python
def should_deploy_endpoint(scorecard_key: str, score_key: str,
                           new_model_s3_uri: str) -> bool:
    """Check if deployment needed."""
    endpoint_name = f"plexus-{scorecard_key}-{score_key}-serverless"

    try:
        client = boto3.client('sagemaker')
        endpoint = client.describe_endpoint(EndpointName=endpoint_name)

        # Get current model URI
        config_name = endpoint['EndpointConfigName']
        config = client.describe_endpoint_config(EndpointConfigName=config_name)
        model_name = config['ProductionVariants'][0]['ModelName']
        model = client.describe_model(ModelName=model_name)
        current_uri = model['PrimaryContainer']['ModelDataUrl']

        if current_uri == new_model_s3_uri:
            print(f"✓ Endpoint already uses {new_model_s3_uri}")
            return False
        else:
            print(f"→ Update needed: {current_uri} → {new_model_s3_uri}")
            return True

    except client.exceptions.ResourceNotFound:
        print(f"→ Endpoint {endpoint_name} does not exist, will create")
        return True
```

### New CLI Commands

**Provision endpoint for trained model:**
```bash
# Provision with defaults (uses local trained model)
plexus provision --scorecard "SelectQuote HCS" --score "Compliance Check"

# Provision with custom resources
plexus provision --scorecard "SelectQuote HCS" --score "Compliance Check" \
  --memory 8192 --max-concurrency 20

# Provision from specific S3 model
plexus provision --scorecard "SelectQuote HCS" --score "Compliance Check" \
  --model-s3-uri s3://bucket/path/to/model.tar.gz
```

**Check endpoint status:**
```bash
plexus provision status --scorecard "SelectQuote HCS" --score "Compliance Check"

# Output:
# Endpoint: plexus-selectquote-hcs-compliance-check-serverless
# Status: InService
# Model: s3://plexus-training/models/selectquote-hcs/compliance-check/model.tar.gz
# Created: 2025-01-15T10:30:00Z
```

**Delete endpoint:**
```bash
plexus provision delete --scorecard "SelectQuote HCS" --score "Compliance Check"
```

### Files to Create

```
plexus/
├── cli/
│   └── provisioning/
│       ├── __init__.py
│       ├── provision.py             # Main provision command (follows train/evaluate pattern)
│       └── operations.py            # Provisioning operations
infrastructure/
├── stacks/
│   ├── sagemaker_inference_stack.py # CDK stack (✅ DONE)
│   └── shared/
│       └── naming.py                # Naming functions (✅ DONE)
plexus/training/
│   ├── endpoint_utils.py            # Endpoint discovery/invocation (✅ DONE)
│   ├── inference_template.py        # Base inference handler
│   └── templates/
│       ├── inference_bert.py.template
│       ├── inference_fasttext.py.template
│       └── inference_svm.py.template
```

### Files to Modify

```
plexus/
├── training/
│   ├── ml_trainer_sagemaker.py
│   │   # Add: package_model_for_inference()
│   │   # Add: deploy_endpoint()
│   └── training_dispatcher.py
│       # Add: --deploy flag handling
└── scores/
    ├── Score.py
    │   # Add: supports_remote_inference() classmethod
    └── BERTClassifier.py
        # Override: supports_remote_inference() → True
        # Override: get_inference_template()
```

---

## Phase 3: Production Inference (📋 Planned)

### Goal
Enable `plexus predict` to automatically discover and invoke SageMaker endpoints.

### Endpoint Discovery

**Core Function:**
```python
def get_sagemaker_endpoint(
    scorecard_key: str,
    score_key: str,
    deployment_type: str = 'serverless'
) -> Optional[str]:
    """
    Check if endpoint exists using naming convention.

    Returns:
        Endpoint name if InService, else None
    """
    endpoint_name = f"plexus-{scorecard_key}-{score_key}-{deployment_type}"

    try:
        client = boto3.client('sagemaker')
        response = client.describe_endpoint(EndpointName=endpoint_name)

        if response['EndpointStatus'] == 'InService':
            logger.info(f"Found endpoint: {endpoint_name}")
            return endpoint_name
        else:
            logger.warning(f"Endpoint {endpoint_name} is {response['EndpointStatus']}")
            return None

    except client.exceptions.ResourceNotFound:
        logger.info(f"No endpoint found: {endpoint_name}")
        return None
```

### Integration in Score.predict()

**Modified Prediction Flow:**
```python
class Score:
    async def predict(self, input_data: Score.Input) -> Score.Result:
        """
        Predict using SageMaker endpoint if available, else local model.
        """
        # Check for remote endpoint
        endpoint_name = get_sagemaker_endpoint(
            scorecard_key=self.scorecard_key,
            score_key=self.score_key,
            deployment_type=self.parameters.deployment_target
        )

        if endpoint_name:
            return await self._predict_via_sagemaker(endpoint_name, input_data)
        else:
            return await self._predict_local(input_data)

    async def _predict_via_sagemaker(
        self,
        endpoint_name: str,
        input_data: Score.Input
    ) -> Score.Result:
        """Invoke SageMaker endpoint."""
        import boto3

        runtime = boto3.client('sagemaker-runtime')

        payload = {
            'text': input_data.text,
            'metadata': input_data.metadata
        }

        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='application/json',
            Body=json.dumps(payload)
        )

        result = json.loads(response['Body'].read())

        return Score.Result(
            value=result['value'],
            explanation=result.get('explanation'),
            metadata={
                'endpoint': endpoint_name,
                'inference_type': 'sagemaker'
            }
        )

    async def _predict_local(self, input_data: Score.Input) -> Score.Result:
        """Use local model (existing implementation)."""
        # Existing logic...
        pass
```

### Files to Modify

```
plexus/
└── scores/
    ├── Score.py
    │   # Modify: predict() to check for endpoint
    │   # Add: _predict_via_sagemaker()
    │   # Add: _predict_local()
    │   # Add: get_sagemaker_endpoint() helper
    └── BERTClassifier.py
        # No changes needed (inherits from Score)
```

### User Experience

**Transparent Endpoint Usage:**
```bash
# Same command, auto-detects endpoint
plexus predict --scorecard "SelectQuote HCS" --score "Compliance Check" --item 12345

# Logs show detection:
# INFO: Found endpoint: plexus-selectquote-hcs-compliance-check-serverless
# INFO: Using SageMaker inference (270ms)
# Result: {...}
```

**Graceful Fallback:**
```bash
# Endpoint doesn't exist → falls back to local
plexus predict --scorecard "SelectQuote HCS" --score "Compliance Check" --item 12345

# Logs:
# INFO: No endpoint found: plexus-selectquote-hcs-compliance-check-serverless
# INFO: Using local model inference (550ms)
# Result: {...}
```

---

## Implementation Roadmap

### Phase 2: Endpoint Provisioning (Current - Weeks 1-8)

#### Week 1-2: Foundation (✅ COMPLETED)
- [x] Created naming convention helpers in `infrastructure/stacks/shared/naming.py`
- [x] Created `SageMakerInferenceStack` CDK stack
- [x] Created `plexus/training/endpoint_utils.py` for endpoint discovery
- [x] Unit tests for naming conventions (22 tests)
- [x] Unit tests for endpoint_utils (16 tests)
- [x] Integration tests (10 tests)
- [x] CDK synthesis tests (4 tests)
- [ ] Implement `package_model_for_inference()` in `ml_trainer_sagemaker.py`

#### Week 3-4: Manual Provisioning
- [ ] Create `PlexusSageMakerInferenceStack` CDK stack (✅ DONE)
- [ ] Create CDK app with context parameters
- [ ] Implement `plexus provision` CLI command (follows train/evaluate pattern)
- [ ] Test CDK deployment to dev AWS account
- [ ] Integration tests with real SageMaker endpoint

#### Week 5-6: Inference Templates
- [ ] Create base inference handler template
- [ ] Create BERT-specific inference template
- [ ] Add `get_inference_template()` classmethod to BERTClassifier
- [ ] Test inference handler in SageMaker container locally
- [ ] Test end-to-end: train → package → deploy → invoke

#### Week 7-8: Streamlined Workflow
- [ ] Add convenience wrapper: `plexus train && plexus provision` workflow
- [ ] Implement idempotency checks in `plexus provision` (skip if endpoint up-to-date)
- [ ] End-to-end testing: train → provision → predict
- [ ] Documentation and examples

**Milestone:** `plexus provision` successfully creates InService endpoints after training

### Phase 3: Production Inference (Weeks 9-10)

#### Week 9: Auto-Discovery
- [ ] Implement `get_sagemaker_endpoint()` helper
- [ ] Modify `Score.predict()` to check for endpoint first
- [ ] Implement `_predict_via_sagemaker()` method
- [ ] Add fallback to local prediction
- [ ] Test discovery and fallback logic
- [ ] Add logging for transparency

#### Week 10: Management Tooling
- [ ] Implement `plexus endpoint status` command
- [ ] Implement `plexus endpoint list` command
- [ ] Implement `plexus endpoint delete` command
- [ ] Add cost estimation utilities
- [ ] Performance benchmarking
- [ ] User documentation

**Milestone:** `plexus predict` automatically uses SageMaker endpoints when available

### Future Enhancements (Post-MVP)

#### GraphQL Schema Integration
- Store endpoint metadata in ScoreVersion records
- Query endpoint status via API
- Support multiple concurrent versions
- Historical deployment tracking

#### Multi-Score Endpoints
- Deploy multiple scores to single multi-model endpoint
- Shared resources for cost optimization
- Atomic updates for dependent scores

#### A/B Testing
- Deploy multiple versions side-by-side
- Traffic splitting between variants
- Gradual rollout capabilities

#### Auto-Scaling
- Configure auto-scaling policies
- Target-based scaling metrics
- Cost optimization strategies

---

## Testing Strategy

### Unit Tests

**Naming Conventions:**
```python
def test_endpoint_name_generation():
    assert get_endpoint_name("SelectQuote HCS", "Compliance Check") == \
           "plexus-selectquote-hcs-compliance-check-serverless"

def test_model_s3_path():
    assert get_model_s3_path("selectquote-hcs", "compliance-check") == \
           "s3://bucket/models/selectquote-hcs/compliance-check/model.tar.gz"
```

**Discovery Logic (mocked boto3):**
```python
@mock_aws
def test_endpoint_discovery_found():
    # Mock describe_endpoint returning InService
    endpoint = get_sagemaker_endpoint("sc", "score")
    assert endpoint == "plexus-sc-score-serverless"

@mock_aws
def test_endpoint_discovery_not_found():
    # Mock ResourceNotFoundException
    endpoint = get_sagemaker_endpoint("sc", "score")
    assert endpoint is None
```

### Integration Tests

**Training → Packaging:**
```python
def test_train_and_package():
    # Train small model on synthetic data
    result = train_bert_classifier(synthetic_dataset)
    assert result.success

    # Verify model.tar.gz in S3
    assert s3_object_exists(result.artifacts['model_s3_path'])

    # Package for inference
    inference_uri = package_model_for_inference(result.artifacts)

    # Verify inference code added
    inference_tarball = download_from_s3(inference_uri)
    assert 'code/inference.py' in list_tarball_contents(inference_tarball)
```

**CDK Deployment:**
```python
def test_cdk_deployment():
    # Deploy to test account
    deploy_endpoint(
        scorecard_key="test-sc",
        score_key="test-score",
        model_s3_uri="s3://bucket/models/test/model.tar.gz"
    )

    # Verify endpoint created
    client = boto3.client('sagemaker')
    endpoint = client.describe_endpoint(
        EndpointName="plexus-test-sc-test-score-serverless"
    )
    assert endpoint['EndpointStatus'] == 'InService'
```

**Prediction via Endpoint:**
```python
@pytest.mark.integration
async def test_predict_via_endpoint():
    # Assume endpoint deployed
    score = BERTClassifier(
        scorecard_key="test-sc",
        score_key="test-score"
    )

    result = await score.predict(Score.Input(
        text="Test input text",
        metadata={}
    ))

    assert result.value in [0, 1]
    assert result.metadata['inference_type'] == 'sagemaker'
```

### End-to-End Tests

```bash
#!/bin/bash
# E2E test script

set -e

SCORECARD="TestScorecard"
SCORE="TestScore"
ITEM="test-item-1"

echo "1. Training model with deployment..."
plexus train --scorecard "$SCORECARD" --score "$SCORE" --deploy --yaml

echo "2. Checking endpoint status..."
plexus endpoint status --scorecard "$SCORECARD" --score "$SCORE"

echo "3. Predicting via endpoint..."
plexus predict --scorecard "$SCORECARD" --score "$SCORE" --item "$ITEM" --yaml

echo "4. Deleting endpoint..."
plexus endpoint delete --scorecard "$SCORECARD" --score "$SCORE"

echo "5. Predicting locally (fallback)..."
plexus predict --scorecard "$SCORECARD" --score "$SCORE" --item "$ITEM" --yaml

echo "✓ E2E test passed"
```

---

## Configuration Reference

### Score YAML Configuration

**Current (Phase 1):**
```yaml
name: "Compliance Check"
class: BERTClassifier
embeddings_model: "distilbert-base-uncased"
embeddings_model_trainable_layers: 2
dropout_rate: 0.3
epochs: 3
batch_size: 16
learning_rate: 0.00002

data:
  class: FeedbackItems
  parameters:
    scorecard_id: "scorecard-uuid"
    score_id: "score-uuid"
    days: 90

training:
  type: ml
  deployment_target: local  # or sagemaker_serverless
```

**Enhanced (Phase 2):**
```yaml
name: "Compliance Check"
class: BERTClassifier
embeddings_model: "distilbert-base-uncased"
embeddings_model_trainable_layers: 2
dropout_rate: 0.3
epochs: 3
batch_size: 16
learning_rate: 0.00002

data:
  class: FeedbackItems
  parameters:
    scorecard_id: "scorecard-uuid"
    score_id: "score-uuid"
    days: 90

training:
  type: ml
  deployment_target: sagemaker_serverless  # triggers endpoint provisioning

  # Optional: Override endpoint settings
  endpoint:
    memory_mb: 4096           # default: 4096
    max_concurrency: 10       # default: 10
```

**Deployment Target Values:**
- `local`: Train and predict locally (existing)
- `sagemaker`: Train on SageMaker, predict locally
- `sagemaker_serverless`: Train on SageMaker, deploy endpoint, predict via endpoint
- `sagemaker_realtime`: Train on SageMaker, deploy real-time endpoint

### CLI Commands

**Training:**
```bash
# Local training
plexus train --scorecard "SelectQuote HCS" --score "Compliance Check" --yaml

# SageMaker training (when implemented)
plexus train --scorecard "SelectQuote HCS" --score "Compliance Check" --platform sagemaker
```

**Provisioning (Phase 2):**
```bash
# Provision endpoint from trained model
plexus provision --scorecard "SelectQuote HCS" --score "Compliance Check"

# Check status
plexus provision status --scorecard "SelectQuote HCS" --score "Compliance Check"

# Delete endpoint
plexus provision delete --scorecard "SelectQuote HCS" --score "Compliance Check"
```

**Prediction (Phase 3):**
```bash
# Auto-detects endpoint or falls back to local
plexus predict --scorecard "SelectQuote HCS" --score "Compliance Check" --item 12345 --yaml
```

**Evaluation:**
```bash
plexus evaluate accuracy \
  --scorecard "SelectQuote HCS" \
  --score "Compliance Check" \
  --number-of-samples 100 \
  --yaml
```

---

## Troubleshooting

### Common Issues

**Issue:** `AttributeError: 'NoneType' object has no attribute 'name'` during evaluation
- **Cause:** scorecard_name not set during Score instantiation
- **Status:** ✅ Fixed in `Score._create_score_from_config()`

**Issue:** Model loading takes too long during evaluation
- **Cause:** Model loaded from disk for each prediction
- **Current State:** Mitigated by parallel evaluation (20 concurrent)
- **Future Fix:** Score instance pooling/reuse

**Issue:** Training runs out of memory
- **Solution:** Reduce `batch_size` in score config
- **Typical Values:** 8-16 for local, 32-64 for GPU/SageMaker

**Issue:** CDK deployment fails with `ResourceNotFoundException`
- **Cause:** S3 bucket or model.tar.gz doesn't exist
- **Solution:** Verify model was uploaded successfully after training

**Issue:** Endpoint shows `Creating` status for too long
- **Expected:** 3-5 minutes for serverless endpoints
- **Action:** Check CloudWatch logs for errors
- **Command:** `aws logs tail /aws/sagemaker/Endpoints/{endpoint-name}`

**Issue:** `plexus predict` doesn't use endpoint even though it exists
- **Cause:** `deployment_target` in config doesn't match endpoint type
- **Solution:** Ensure config has `deployment_target: sagemaker_serverless`

**Issue:** SageMaker inference returns error
- **Debug Steps:**
  1. Check CloudWatch logs: `/aws/sagemaker/Endpoints/{name}`
  2. Test inference.py locally with sample input
  3. Verify model.tar.gz structure matches expected format
  4. Check environment variables in container

---

## Dependencies

### Python Packages
```
torch>=2.0.0              # PyTorch for BERT
transformers>=4.30.0      # Hugging Face transformers
scikit-learn>=1.3.0       # Metrics and baseline models
sagemaker>=2.0.0          # AWS SageMaker SDK (optional)
aws-cdk-lib>=2.0.0        # AWS CDK for infrastructure
```

### Infrastructure Requirements
- AWS Account with SageMaker access
- S3 bucket for model artifacts (e.g., `plexus-training`)
- IAM role for SageMaker execution
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- Docker (for local CDK synthesis)

### Model Storage
- Local: `~/.plexus/models/{scorecard}/{score}/` (~500MB per BERT model)
- S3: `s3://{bucket}/models/{scorecard}/{score}/model.tar.gz`

---

## Success Metrics

**Phase 2 (Endpoint Provisioning):**
1. Provisioning Success Rate: % of `plexus provision` commands that create InService endpoints (target: >95%)
2. Deployment Time: Time from provision command to InService (target: <5 minutes)
3. Idempotency: Repeated provisioning should detect no-op correctly (target: 100%)

**Phase 3 (Production Inference):**
1. Discovery Success Rate: % of predictions that correctly find endpoints (target: >99%)
2. Prediction Latency: Median SageMaker endpoint response time (target: <500ms p50)
3. Fallback Rate: % of predictions using local fallback (target: <5% in prod)

**Overall:**
1. Developer Adoption: % of ML scores using `deployment_target: sagemaker_serverless` (target: >50%)
2. Cost Efficiency: Cost per 1000 predictions vs local inference
3. Uptime: % of time endpoints are InService (target: >99.9%)

---

## Document Maintenance

This is a **living document**. Update it when:
- ✅ Phases are completed (move from 📋 Planned to ✅ Complete)
- 🐛 Issues are discovered and resolved
- 📝 New requirements emerge
- 🔄 Implementation details change

**Version History:**
- 2025-01-28: Initial unified document (merged status + plan)
- [Future updates here]

---

**For questions or clarifications, refer to:**
- Code comments in key files
- CDK stack documentation
- AWS SageMaker Serverless Inference docs
