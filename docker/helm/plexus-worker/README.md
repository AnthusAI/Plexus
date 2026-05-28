# Plexus Worker Helm Chart

Helm chart for deploying Plexus workers to Kubernetes.

## Files Structure

```
plexus-worker/
├── Chart.yaml                     # Chart metadata
├── values.yaml                    # Default values (committed)
├── values-dev.yaml.example        # Dev template (committed)
├── values-staging.yaml.example    # Staging template (committed)
├── values-prod.yaml.example       # Production template (committed)
├── .gitignore                     # Ignores actual values files
├── README.md                      # This file
└── templates/                     # Kubernetes manifests
    ├── deployment.yaml
    ├── configmap.yaml
    ├── secret.yaml
    ├── hpa.yaml
    ├── pdb.yaml
    ├── serviceaccount.yaml
    └── networkpolicy.yaml
```

## Setup

### 1. Create Your Values File

Copy the example template for your environment:

```bash
# Development
cp values-dev.yaml.example values-dev.yaml

# Staging
cp values-staging.yaml.example values-staging.yaml

# Production
cp values-prod.yaml.example values-prod.yaml
```

### 2. Configure Credentials

Edit your values file and replace placeholders:

```yaml
plexus:
  api:
    url: "https://your-actual-api-url"
    key: "your-actual-api-key"
  account:
    key: "your-account-key"

scoreProcessor:
  aws:
    accessKeyId: "AKIA..."
    secretAccessKey: "your-secret"
  sqs:
    requestQueueUrl: "https://sqs.us-west-2.amazonaws.com/..."
    responseQueueUrl: "https://sqs.us-west-2.amazonaws.com/..."
```

### 3. Deploy

```bash
helm install plexus-worker . \
  -f values-dev.yaml \
  --namespace plexus-dev \
  --create-namespace
```

## Security

**⚠️ Important**: Actual values files (`values-dev.yaml`, `values-staging.yaml`, `values-prod.yaml`) contain credentials and are **git-ignored**.

- ✅ **Commit**: `.example` template files
- ❌ **Never commit**: Actual values files with credentials

## Configuration

See the parent [README.md](../../README.md) for complete configuration documentation.

## Quick Reference

```bash
# Install
helm install RELEASE . -f values-ENV.yaml --namespace NAMESPACE --create-namespace

# Upgrade
helm upgrade RELEASE . -f values-ENV.yaml --namespace NAMESPACE

# Uninstall  
helm uninstall RELEASE --namespace NAMESPACE

# Template (dry run)
helm template RELEASE . -f values-ENV.yaml --namespace NAMESPACE

# Lint
helm lint .
```

## Octopus Deploy

For Octopus Deploy integration, use the example files as templates and configure variables in Octopus to override the values. See parent README.md for details.
