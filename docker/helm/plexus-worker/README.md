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
    ├── service.yaml
    ├── gateway.yaml
    ├── httproute.yaml
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
    authMode: api_key
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

For non-local environments, set `global.environment` to the target environment
and use an immutable worker image tag such as a git SHA or digest-derived tag.
The chart rejects `latest` and `local` tags when `global.environment` is not
`local`, `development`, `dev`, or `test`.

Set `plexus.api.authMode` explicitly to `api_key` for current secret-backed
deployments or `iam` for a service account with an authorized AWS role. IAM
mode does not inject `PLEXUS_API_KEY` into worker or recovery-job containers.
Any other authentication mode is rejected during chart rendering.

## Envoy Gateway Scoring API

Set `workerType: scoring-api` to expose synchronous scoring over HTTP. This mode creates a ClusterIP Service and, when `scoringApi.gateway.enabled` is true, Gateway API resources for Envoy Gateway.

```yaml
workerType: scoring-api

service:
  enabled: true
  port: 8000

scoringApi:
  enabled: true
  port: 8000
  auth:
    enabled: true
    required: true
    apiKey: "set-via-secret-manager"
  gateway:
    enabled: true
    createGateway: true
    gatewayClassName: envoy-gateway
    pathPrefix: /v1/score
```

For exposed environments, keep `scoringApi.auth.enabled` on and require callers
to send `x-plexus-scoring-api-key`. This inbound key is separate from the
worker's `PLEXUS_API_KEY`, which is used for backend GraphQL access.
`scoringApi.auth.required` sets `SCORING_API_AUTH_REQUIRED=true` so the API
fails closed if the inbound key is missing.

For a platform-managed Gateway, set `createGateway: false`, `gatewayName`, and optionally `gatewayNamespace`.

The referenced `gatewayClassName` must already exist. For the local POC, `docker/scripts/setup_envoy_gateway_poc.sh` installs Envoy Gateway and creates the `envoy-gateway` `GatewayClass`.

The chart keeps `workerType` out of the Deployment selector so a local release can switch between worker modes without hitting Kubernetes immutable selector errors. The worker type remains on pod labels and Service selectors so the Service only targets the expected worker pods.

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
