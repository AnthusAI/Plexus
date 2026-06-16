# Local Kubernetes Testing Guide

This guide shows how to test the Plexus Kubernetes deployment locally without access to production infrastructure.

## Option 1: Docker Desktop Kubernetes (Recommended for Mac)

### Setup

1. **Enable Kubernetes in Docker Desktop**
   - Open Docker Desktop
   - Go to Settings → Kubernetes
   - Check "Enable Kubernetes"
   - Click "Apply & Restart"
   - Wait for Kubernetes to start (green icon)

2. **Verify Installation**
   ```bash
   kubectl cluster-info
   kubectl get nodes
   ```

3. **Install Helm**
   ```bash
   brew install helm
   ```

### Deploy Plexus Worker

```bash
# 1. Build the Docker image locally (from repository root)
docker build -f docker/Dockerfile -t plexus-worker:local .

# 2. Verify image exists
docker images | grep plexus-worker

# 3. Create a local values file (this is git-ignored)
# You can also copy from the dev example:
# cp docker/helm/plexus-worker/values-dev.yaml.example docker/helm/plexus-worker/values-local.yaml
# Then edit values-local.yaml with your credentials

cat > docker/helm/plexus-worker/values-local.yaml <<EOF
workerType: score-processor

image:
  repository: plexus-worker
  tag: local
  pullPolicy: IfNotPresent

replicaCount: 1

resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "500m"

autoscaling:
  enabled: false

podDisruptionBudget:
  enabled: false

# Minimal security for local testing
networkPolicy:
  enabled: false

env:
  LOG_LEVEL: DEBUG
  MAX_JOBS_PER_WORKER: "5"

# Your local credentials
plexus:
  createSecrets: true
  api:
    url: "https://dev-api.plexus.example.com"
    key: "your-dev-api-key"
  account:
    key: "your-dev-account-key"

scoreProcessor:
  aws:
    region: us-west-2
    createSecrets: true
    accessKeyId: "your-aws-key"
    secretAccessKey: "your-aws-secret"
  sqs:
    requestQueueUrl: "https://sqs.us-west-2.amazonaws.com/123/dev-requests"
    responseQueueUrl: "https://sqs.us-west-2.amazonaws.com/123/dev-responses"
EOF

# 4. Install with Helm
helm install plexus-worker-local docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-local.yaml \
  --namespace plexus-local \
  --create-namespace

# 5. Watch deployment
kubectl get pods -n plexus-local -w

# 6. Check logs
kubectl logs -f deployment/plexus-worker-local -n plexus-local
```

### Verify Deployment

```bash
# Check all resources
kubectl get all -n plexus-local

# Check pod details
kubectl describe pod -n plexus-local -l app.kubernetes.io/name=plexus-worker

# Check secrets
kubectl get secrets -n plexus-local

# Check configmap
kubectl get configmap -n plexus-local
```

### Test Changes

```bash
# Make code changes, then rebuild and upgrade
docker build -f docker/Dockerfile -t plexus-worker:local .

helm upgrade plexus-worker-local docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-local.yaml \
  --namespace plexus-local

# Force pod restart
kubectl rollout restart deployment/plexus-worker-local -n plexus-local
```

### Clean Up

```bash
# Uninstall Helm release
helm uninstall plexus-worker-local -n plexus-local

# Delete namespace
kubectl delete namespace plexus-local

# Remove Docker image
docker rmi plexus-worker:local
```

## Option 2: Minikube

### Setup

```bash
# Install Minikube
brew install minikube

# Start cluster
minikube start --cpus=4 --memory=8192

# Enable metrics server (for HPA)
minikube addons enable metrics-server

# Verify
kubectl get nodes
```

### Deploy

```bash
# Build image directly in Minikube
eval $(minikube docker-env)
docker build -f docker/Dockerfile -t plexus-worker:local .

# Deploy with Helm (same commands as Docker Desktop above)
helm install plexus-worker-local docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-local.yaml \
  --namespace plexus-local \
  --create-namespace
```

### Access

```bash
# Get Minikube IP
minikube ip

# Open Kubernetes dashboard
minikube dashboard
```

### Clean Up

```bash
minikube stop
minikube delete
```

## Option 3: Kind (Kubernetes in Docker)

### Setup

```bash
# Install Kind
brew install kind

# Create cluster
kind create cluster --name plexus-test

# Verify
kubectl cluster-info --context kind-plexus-test
```

### Load Image

```bash
# Build image
docker build -f docker/Dockerfile -t plexus-worker:local .

# Load into Kind
kind load docker-image plexus-worker:local --name plexus-test
```

### Deploy

```bash
# Same Helm commands as above
helm install plexus-worker-local docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-local.yaml \
  --namespace plexus-local \
  --create-namespace
```

### Clean Up

```bash
kind delete cluster --name plexus-test
```

## Logging in K8s

The K8s worker uses stdout-based structured logging — no CloudWatch dependency.
All service logs are captured natively by `kubectl logs`.

### How it works

- `scoring_api.py` configures `logging.basicConfig()` to emit structured lines
  (`timestamp level logger message`) to stdout.
- `PLEXUS_DISABLE_CLOUDWATCH_LOGS=1` is set in Helm values to prevent any
  transitive import from activating the watchtower CloudWatch handler.
- Uvicorn access logs and application logs both write to stdout/stderr.

### Verifying log visibility

```bash
# Automated: runs a scoring request and asserts logs are visible
docker/scripts/smoke_test_k8s_logging.sh

# With LLM-backed score (tests full inference path)
docker/scripts/smoke_test_k8s_logging.sh --score nira-resolution-quality

# Manual: tail logs from the worker deployment
kubectl logs -f -n plexus-local deployment/plexus-plexus-worker
```

### Log format

```
2026-06-16 17:45:03,123 INFO plexus.workers.scoring_job Processing scoring job: log-test-1
2026-06-16 17:45:03,456 INFO plexus.workers.scoring_job Fetching item nira-demo-item-1 for scoring job log-test-1
2026-06-16 17:45:03,789 INFO plexus.workers.scoring_job Storing score result for scoring job log-test-1
```

## Testing Without Real AWS/API

If you don't have real credentials or want to test just the Kubernetes parts:

### 1. Mock Worker Mode

Create a mock values file:

```yaml
# values-mock.yaml
workerType: console-worker  # Doesn't need AWS

image:
  repository: plexus-worker
  tag: local

replicaCount: 1

plexus:
  createSecrets: true
  api:
    url: "http://mock-api:8080"
    key: "mock-key"
  account:
    key: "mock-account"

console:
  responseTarget: "local:developer"
```

### 2. Test Helm Rendering Only

See what Kubernetes manifests would be created without deploying:

```bash
# Render templates
helm template plexus-worker-test docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-local.yaml \
  --namespace plexus-local

# Save to file for inspection
helm template plexus-worker-test docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-local.yaml \
  --namespace plexus-local > rendered-manifests.yaml

# View rendered manifests
less rendered-manifests.yaml
```

### 3. Dry Run Deployment

Test deployment without actually creating resources:

```bash
helm install plexus-worker-test docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-local.yaml \
  --namespace plexus-local \
  --dry-run --debug
```

## Common Local Testing Scenarios

### Test Autoscaling

```bash
# Install with HPA enabled
cat > values-hpa-test.yaml <<EOF
workerType: score-processor
image:
  repository: plexus-worker
  tag: local
autoscaling:
  enabled: true
  minReplicas: 1
  maxReplicas: 3
  targetCPUUtilizationPercentage: 50
EOF

helm install plexus-worker-hpa docker/helm/plexus-worker \
  -f values-hpa-test.yaml \
  --namespace plexus-local \
  --create-namespace

# Generate load (if metrics-server is running)
kubectl run -i --tty load-generator --rm --image=busybox --restart=Never -- /bin/sh

# Watch HPA
kubectl get hpa -n plexus-local -w
```

### Test Rolling Update

```bash
# Make a change to code
# Rebuild image with new tag
docker build -f docker/Dockerfile -t plexus-worker:v2 .

# Upgrade
helm upgrade plexus-worker-local docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-local.yaml \
  --set image.tag=v2 \
  --namespace plexus-local

# Watch rollout
kubectl rollout status deployment/plexus-worker-local -n plexus-local
```

### Test Secret Changes

```bash
# Update secret
helm upgrade plexus-worker-local docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-local.yaml \
  --set plexus.api.key=new-api-key \
  --namespace plexus-local

# Pods should restart automatically due to checksum annotation
kubectl get pods -n plexus-local -w
```

### Test Network Policy

```bash
# Enable network policy
helm upgrade plexus-worker-local docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-local.yaml \
  --set networkPolicy.enabled=true \
  --namespace plexus-local

# Check network policy
kubectl get networkpolicy -n plexus-local
kubectl describe networkpolicy -n plexus-local
```

## Debugging Tips

### View All Resources

```bash
kubectl get all,cm,secret,pdb,hpa,networkpolicy -n plexus-local
```

### Pod Not Starting

```bash
# Check events
kubectl get events -n plexus-local --sort-by='.lastTimestamp'

# Describe pod
kubectl describe pod <pod-name> -n plexus-local

# Common issues:
# - ImagePullBackOff: Image not found in local registry
# - CrashLoopBackOff: Container starting but crashing
# - Pending: Insufficient resources
```

### Check Logs

```bash
# Current logs
kubectl logs <pod-name> -n plexus-local

# Follow logs
kubectl logs -f <pod-name> -n plexus-local

# Previous container logs (if crashed)
kubectl logs <pod-name> -n plexus-local --previous
```

### Exec into Pod

```bash
kubectl exec -it <pod-name> -n plexus-local -- /bin/bash

# Check environment
env | grep PLEXUS

# Check files
ls -la /app

# Check running processes
ps aux
```

### Helm Status

```bash
# List releases
helm list -n plexus-local

# Get release status
helm status plexus-worker-local -n plexus-local

# Get release values
helm get values plexus-worker-local -n plexus-local

# Get release manifest
helm get manifest plexus-worker-local -n plexus-local
```

### Test Rollback

```bash
# List revisions
helm history plexus-worker-local -n plexus-local

# Rollback to previous
helm rollback plexus-worker-local -n plexus-local

# Rollback to specific revision
helm rollback plexus-worker-local 1 -n plexus-local
```

## Quick Test Script

Save this as `test-local.sh`:

```bash
#!/bin/bash
set -e

echo "🐳 Building Docker image..."
docker build -f docker/Dockerfile -t plexus-worker:local .

echo "📦 Installing Helm chart..."
helm install plexus-worker-test docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-local.yaml \
  --namespace plexus-test \
  --create-namespace \
  --wait --timeout 5m

echo "✅ Deployment complete!"
echo ""
echo "📊 Status:"
kubectl get all -n plexus-test

echo ""
echo "📋 Logs (Ctrl+C to exit):"
kubectl logs -f deployment/plexus-worker-test -n plexus-test
```

Run with:
```bash
chmod +x test-local.sh
./test-local.sh
```

## Simulating Octopus Deploy

To simulate what Octopus would do:

```bash
# 1. Package chart (Octopus would do this)
helm package docker/helm/plexus-worker

# 2. Simulate variable substitution
cat > octopus-vars.yaml <<EOF
image:
  repository: plexus-worker
  tag: "local"
plexus:
  api:
    url: "https://dev-api.example.com"
    key: "dev-key-from-octopus"
  account:
    key: "dev-account-from-octopus"
EOF

# 3. Deploy (simulating Octopus Deploy step)
helm install plexus-worker docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-dev.yaml \
  -f octopus-vars.yaml \
  --namespace plexus-dev \
  --create-namespace

# 4. Upgrade (simulating promotion to next environment)
helm upgrade plexus-worker docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-staging.yaml \
  -f octopus-vars.yaml \
  --namespace plexus-staging
```

## Recommended: Docker Desktop + Helm

For Mac, the easiest setup:

1. ✅ **Docker Desktop** - Already installed, just enable Kubernetes
2. ✅ **Helm** - `brew install helm`
3. ✅ **kubectl** - Comes with Docker Desktop

This gives you a fully functional Kubernetes cluster that:
- Uses your local Docker images (no registry needed)
- Runs on your laptop (no cloud costs)
- Supports all Kubernetes features
- Works offline

**You're ready to test everything locally before handing off to DevOps!**
