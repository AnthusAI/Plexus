# Plexus Kubernetes Deployment

Production-ready Kubernetes deployment for Plexus workers using Helm charts and Octopus Deploy.

## Overview

This directory contains everything needed to deploy Plexus workers to Kubernetes:

- **Dockerfile** - Multi-worker container image (score-processor, celery, scoring-api, console-worker)
- **helm/plexus-worker/** - Helm chart for Kubernetes deployment
- **docker-compose.yml** - Local testing environment
- **SECURITY.md** - Security best practices and hardening guide

## Quick Start

### Envoy Gateway Scoring API POC

For the Docker-backed Kubernetes proof of concept, use the umbrella stack and Envoy Gateway bootstrap script:

```bash
cp docker/helm/plexus-stack/values-local.yaml.example \
   docker/helm/plexus-stack/values-local.yaml

# Edit values-local.yaml with API and LLM keys, then run:
docker/scripts/setup_envoy_gateway_poc.sh
```

This path creates or reuses a local kind cluster, installs Envoy Gateway, creates the local `GatewayClass`, builds and loads local images, deploys `workerType: scoring-api`, exposes `POST /v1/score`, and routes traffic through Envoy Gateway. The local values file is the source of truth for scoring API, Service, and Gateway settings; the script only overrides image references so kind uses the locally built images, then validates that the expected scoring API resources exist. Existing SQS and Celery modes remain available as separate deployment paths.

The script pins the Envoy Gateway Helm chart for reproducibility. Override
`ENVOY_GATEWAY_CHART_VERSION` only when intentionally validating a newer
Gateway release.

In kind, the Envoy data-plane Service usually remains `EXTERNAL-IP <pending>` because there is no cloud load balancer. Use the Service printed by the script, or find it again with:

```bash
kubectl get svc -A \
  -l gateway.envoyproxy.io/owning-gateway-name=plexus-plexus-worker-gateway
```

Then port-forward that Envoy Service and smoke test the route:

```bash
kubectl port-forward -n <envoy-service-namespace> svc/<envoy-service-name> 8080:80

# Missing required fields should return HTTP 422 from the scoring API.
curl -i -X POST http://localhost:8080/v1/score \
  -H 'content-type: application/json' \
  -d '{"scoring_job_id":"poc-route-test"}'
```

A complete scoring request reaches the real scoring code path. To get a successful score result, use valid API/LLM credentials in `values-local.yaml` and real existing `scorecard`, `score`, and `item_id` values:

```bash
curl -X POST http://localhost:8080/v1/score \
  -H 'content-type: application/json' \
  -d '{
    "scoring_job_id": "poc-job-1",
    "scorecard": "scorecard-key-or-name",
    "score": "score-key-or-name",
    "item_id": "item-id"
  }'
```

For exposed environments, configure a separate inbound scoring API key with
`plexus-worker.scoringApi.auth.enabled=true` and send it as
`x-plexus-scoring-api-key`. Do not reuse the worker's backend `PLEXUS_API_KEY`
for external callers.

### 1. Configure Environment

Create your environment-specific values file:

```bash
# Copy example template
cp docker/helm/plexus-worker/values-dev.yaml.example \
   docker/helm/plexus-worker/values-dev.yaml

# Edit with your credentials
vim docker/helm/plexus-worker/values-dev.yaml
```

**⚠️ Important**: Values files contain credentials and are git-ignored. Never commit them!

Available templates:
- `values-dev.yaml.example` - Development environment
- `values-staging.yaml.example` - Staging environment  
- `values-prod.yaml.example` - Production environment

### 2. Build Docker Image

```bash
# Publish linux/amd64 images for real cluster deploys.
REGISTRY=your-registry \
IMAGE_TAG=1.52.0 \
docker/scripts/build_k8s_images.sh

# Optional: add linux/arm64 for a multi-arch manifest list.
REGISTRY=your-registry \
IMAGE_TAG=1.52.0 \
PLATFORMS=linux/amd64,linux/arm64 \
docker/scripts/build_k8s_images.sh
```

### 3. Deploy with Helm

```bash
# Package the chart
helm package docker/helm/plexus-worker

# Install to Kubernetes
helm install plexus-worker docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-prod.yaml \
  --set image.repository=your-registry/plexus-worker \
  --set image.tag=1.52.0 \
  --set plexus.api.key=your-api-key \
  --namespace plexus-prod \
  --create-namespace
```

## Deployment with Octopus Deploy

Octopus Deploy has native Helm chart support for Kubernetes deployments.

### Setup Steps

#### 1. Package the Helm Chart

```bash
cd docker/helm
helm package plexus-worker
# Creates: plexus-worker-1.0.0.tgz
```

#### 2. Upload to Octopus

1. Go to **Library** → **Packages** → **Upload Package**
2. Upload `plexus-worker-1.0.0.tgz`

#### 3. Create Octopus Project

1. **Projects** → **Add Project**: "Plexus Worker Deployment"
2. **Process** → **Add Step** → **Deploy Helm Chart**

**Step Configuration**:
- **Package ID**: `plexus-worker`
- **Release Name**: `plexus-worker-#{Octopus.Environment.Name | ToLower}`
- **Namespace**: `#{Kubernetes.Namespace}`
- **Reset Values**: ✅ Checked

**Values Files** (scoped by environment):
- Dev: `values-dev.yaml`
- Staging: `values-staging.yaml`
- Production: `values-prod.yaml`

**Explicit Key Values** (Raw YAML):
```yaml
image:
  repository: "#{Docker.Registry}/plexus-worker"
  tag: "#{Docker.Image.Tag}"

plexus:
  api:
    url: "#{Plexus.ApiUrl}"
    key: "#{Plexus.ApiKey}"
  account:
    key: "#{Plexus.AccountKey}"

scoreProcessor:
  aws:
    region: "#{AWS.Region}"
    accessKeyId: "#{AWS.AccessKeyId}"
    secretAccessKey: "#{AWS.SecretAccessKey}"
  sqs:
    requestQueueUrl: "#{AWS.SQS.RequestQueue}"
    responseQueueUrl: "#{AWS.SQS.ResponseQueue}"
```

#### 4. Configure Octopus Variables

| Variable | Example | Scope | Sensitive |
|----------|---------|-------|-----------|
| `Docker.Registry` | `123456.dkr.ecr.us-west-2.amazonaws.com` | All | No |
| `Docker.Image.Tag` | `1.52.0` | Per Release | No |
| `Kubernetes.Namespace` | `plexus-prod` | Per Environment | No |
| `Plexus.ApiUrl` | `https://api.plexus.example.com` | Per Environment | No |
| `Plexus.ApiKey` | `***` | Per Environment | **Yes** |
| `Plexus.AccountKey` | `***` | Per Environment | **Yes** |
| `AWS.Region` | `us-west-2` | Per Environment | No |
| `AWS.AccessKeyId` | `***` | Per Environment | **Yes** |
| `AWS.SecretAccessKey` | `***` | Per Environment | **Yes** |
| `AWS.SQS.RequestQueue` | `https://sqs...` | Per Environment | No |
| `AWS.SQS.ResponseQueue` | `https://sqs...` | Per Environment | No |

#### 5. Deploy

1. **Create Release** → Enter version
2. **Deploy to Dev** → Monitor deployment
3. **Promote to Staging** → Test
4. **Promote to Production** → After approval

### Automated CI/CD

Integrate with GitHub Actions:

```yaml
- name: Create Octopus Release
  uses: OctopusDeploy/create-release-action@v3
  with:
    api_key: ${{ secrets.OCTOPUS_API_KEY }}
    server: ${{ secrets.OCTOPUS_SERVER_URL }}
    project: "Plexus Worker Deployment"
    release_number: ${{ steps.version.outputs.VERSION }}

- name: Deploy to Dev
  uses: OctopusDeploy/deploy-release-action@v3
  with:
    api_key: ${{ secrets.OCTOPUS_API_KEY }}
    server: ${{ secrets.OCTOPUS_SERVER_URL }}
    project: "Plexus Worker Deployment"
    release_number: ${{ steps.version.outputs.VERSION }}
    environment: "Development"
```

## Worker Types

The image supports four worker modes via `workerType` value:

### 1. Scoring API (`scoring-api`)
Exposes synchronous HTTP scoring for Envoy Gateway deployments.

**Required Config**:
- `PLEXUS_API_URL`
- `PLEXUS_API_KEY`
- `PLEXUS_ACCOUNT_KEY`
- Optional: `SCORING_API_HOST`, `SCORING_API_PORT`

**Endpoint**:
- `POST /v1/score`

### 2. Score Processor (`score-processor`)
Polls SQS queues and processes scoring jobs.

**Required Config**:
- `PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL`
- `PLEXUS_RESPONSE_WORKER_QUEUE_URL`
- AWS credentials (or IRSA)

### 3. Celery Worker (`celery`)
Processes async tasks from RabbitMQ/Redis.

**Required Config**:
- `CELERY_BROKER_URL`
- `CELERY_APP`, `CELERY_QUEUE`, `CELERY_CONCURRENCY`

### 4. Console Worker (`console-worker`)
Polls for console chat messages.

**Required Config**:
- `CONSOLE_RESPONSE_TARGET`

## Configuration

### Environment Values Files

Environment-specific configuration is managed through values files:

```
helm/plexus-worker/
├── values.yaml                    # Base configuration (committed to git)
├── values-dev.yaml.example        # Dev template (committed)
├── values-staging.yaml.example    # Staging template (committed)
├── values-prod.yaml.example       # Production template (committed)
│
├── values-dev.yaml               # Your dev config (git-ignored)
├── values-staging.yaml           # Your staging config (git-ignored)
└── values-prod.yaml              # Your production config (git-ignored)
```

**Setup Process:**
1. Copy `.example` file to remove `.example` extension
2. Fill in your actual credentials
3. Use with `helm install -f values-{env}.yaml`

**Security**: Actual values files are git-ignored to prevent credential leaks.

### Environment-Specific Values

**Development** (`values-dev.yaml.example` → `values-dev.yaml`):
- 1 replica
- DEBUG logging
- Lower resources

**Staging** (`values-staging.yaml`):
- 2-10 replicas (HPA)
- INFO logging
- Moderate resources

**Production** (`values-prod.yaml`):
- 5-30 replicas (HPA)
- INFO logging
- High resources
- Network policies enabled
- IRSA enabled (no AWS credentials in secrets)
- Pod Disruption Budget

### Key Helm Values

```yaml
# Worker type
workerType: score-processor

# Image
image:
  repository: your-registry/plexus-worker
  tag: "1.52.0"

# Resources
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "1500m"

# Autoscaling
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20

# Security (Production)
networkPolicy:
  enabled: true

serviceAccount:
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT:role/PlexusWorkerRole
```

## Local Testing

Use Docker Compose for local development:

```bash
# Copy environment template
cp docker/.env.example docker/.env

# Edit with your credentials
vim docker/.env

# Start services
docker-compose -f docker/docker-compose.yml up

# View logs
docker-compose -f docker/docker-compose.yml logs -f

# Clean up
docker-compose -f docker/docker-compose.yml down
```

## Security

This deployment follows security best practices:

✅ **Non-root user** - Container runs as UID 1000  
✅ **No privilege escalation** - `allowPrivilegeEscalation: false`  
✅ **Dropped capabilities** - All Linux capabilities dropped  
✅ **seccomp profile** - RuntimeDefault applied  
✅ **Network policies** - Pod-to-pod communication restricted  
✅ **IRSA support** - No AWS credentials in secrets (production)  
✅ **Secrets management** - All sensitive data in Kubernetes Secrets  
✅ **Resource limits** - CPU and memory limits enforced  

See [SECURITY.md](SECURITY.md) for detailed security documentation and hardening guide.

## Monitoring

### Check Deployment Status

```bash
# Pods
kubectl get pods -l app.kubernetes.io/name=plexus-worker -n plexus-prod

# Deployment
kubectl get deployment -n plexus-prod

# HPA
kubectl get hpa -n plexus-prod

# Logs
kubectl logs -f deployment/plexus-worker-score-processor -n plexus-prod
```

### Key Metrics

- **CPU/Memory usage** - For autoscaling
- **Job processing rate** - Jobs per minute
- **Error rate** - Failed jobs percentage
- **HTTP request rate/latency** - For `scoring-api`
- **Queue depth** - SQS queue size for `score-processor`

## Scaling

### Manual Scaling

```bash
kubectl scale deployment plexus-worker-score-processor --replicas=10 -n plexus-prod
```

### Automatic Scaling (HPA)

Enabled by default in staging/production:
- **Min**: 3 replicas (5 in prod)
- **Max**: 20 replicas (30 in prod)
- **Target CPU**: 70%
- **Target Memory**: 80%

### Queue-Based Autoscaling (Advanced)

Use [KEDA](https://keda.sh/) for SQS queue depth-based scaling in the `score-processor` deployment path:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: plexus-score-processor-scaler
spec:
  scaleTargetRef:
    name: plexus-worker-score-processor
  minReplicaCount: 5
  maxReplicaCount: 50
  triggers:
  - type: aws-sqs-queue
    metadata:
      queueURL: https://sqs.us-west-2.amazonaws.com/123/queue
      queueLength: "10"
      awsRegion: "us-west-2"
```

## Troubleshooting

### Pods CrashLoopBackOff

```bash
kubectl logs <pod-name> -n plexus-prod
kubectl describe pod <pod-name> -n plexus-prod

# Common causes:
# - Missing environment variables
# - Invalid AWS credentials
# - Image pull errors
# - Insufficient resources
```

### Scoring API Not Responding

```bash
# Check worker logs
kubectl logs -f deployment/plexus-worker -n plexus-prod | grep ERROR

# Verify Service and Gateway API resources
kubectl get svc,gateway,httproute -n plexus-prod

# Bypass Envoy to isolate worker health
kubectl port-forward -n plexus-prod svc/plexus-worker 8000:8000
curl http://localhost:8000/readyz

# For local kind POCs, find and port-forward the Envoy data-plane Service.
kubectl get svc -A \
  -l gateway.envoyproxy.io/owning-gateway-name=plexus-plexus-worker-gateway
kubectl port-forward -n <envoy-service-namespace> svc/<envoy-service-name> 8080:80
```

### Score Processor Not Processing Jobs

```bash
# Check worker logs
kubectl logs -f deployment/plexus-worker-score-processor -n plexus-prod | grep ERROR

# Verify environment variables
kubectl exec -it <pod-name> -n plexus-prod -- env | grep PLEXUS

# Check SQS queue
aws sqs get-queue-attributes \
  --queue-url $QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages
```

### High Memory Usage

- Reduce `CELERY_CONCURRENCY` for Celery workers
- Set `MAX_JOBS_PER_WORKER` to force periodic restarts
- Increase memory limits in values file
- Profile scoring logic for memory leaks

### Helm Deployment Fails

```bash
# Dry run to check for errors
helm install plexus-worker docker/helm/plexus-worker --dry-run --debug

# Validate templates
helm template plexus-worker docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-prod.yaml

# Check for missing values
helm lint docker/helm/plexus-worker
```

## Production Checklist

Before deploying to production:

### Security
- [ ] Container runs as non-root (UID 1000)
- [ ] Network policies enabled
- [ ] IRSA configured (no AWS creds in secrets)
- [ ] Secrets in Kubernetes Secrets (marked sensitive in Octopus)
- [ ] Image scanned for vulnerabilities
- [ ] Pod Security Standards enforced

### Reliability
- [ ] Min 5 replicas configured
- [ ] HPA enabled and tested
- [ ] Pod Disruption Budget configured
- [ ] Health checks working
- [ ] Graceful shutdown tested (60s grace period)

### Operations
- [ ] Specific image tag (not `:latest`)
- [ ] Resource limits appropriate for workload
- [ ] Monitoring and alerting configured
- [ ] Logging aggregation set up
- [ ] Runbook documented
- [ ] Rollback tested

## Differences from Lambda

This Kubernetes deployment complements the existing Lambda setup in `score-processor-lambda/`:

| Aspect | Lambda | Kubernetes |
|--------|--------|------------|
| Execution | Event-driven | Continuous process |
| Scaling | 0-1000s automatic | 3-30 via HPA |
| Cost | Pay per invocation | Pay for running pods |
| Startup | Cold start (1-3s) | Always warm |
| Max Duration | 15 minutes | Unlimited |
| Infrastructure | AWS managed | Self-managed |

**Both can run simultaneously** in a hybrid architecture.

## Files Structure

```
docker/
├── Dockerfile                    # Multi-worker container image
├── entrypoint.sh                 # Worker type selector
├── docker-compose.yml            # Local testing
├── .dockerignore                 # Build optimization
├── .env.example                  # Environment template
├── .gitignore                    # Protect secrets
├── README.md                     # This file
├── SECURITY.md                   # Security guide
└── helm/plexus-worker/          # Helm chart
    ├── Chart.yaml
    ├── values.yaml              # Default config
    ├── values-dev.yaml          # Dev overrides
    ├── values-staging.yaml      # Staging overrides
    ├── values-prod.yaml         # Production overrides
    └── templates/               # K8s resources
        ├── deployment.yaml
        ├── configmap.yaml
        ├── secret.yaml
        ├── hpa.yaml
        ├── pdb.yaml
        ├── serviceaccount.yaml
        └── networkpolicy.yaml
```

## Support

- **Helm Chart**: See `helm/plexus-worker/README.md`
- **Security**: See `SECURITY.md`
- **Kubernetes Issues**: Check pod logs and events
- **Octopus Deploy**: Check Octopus logs and deployment history

## License

MIT License - See repository root for details.
