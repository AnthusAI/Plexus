# Plexus Stack Helm Chart

Complete Kubernetes deployment for the Plexus data processing stack, including PostgreSQL, GraphQL Proxy, and HTTP scoring workers routed by Envoy Gateway.

## Architecture

This umbrella chart deploys three main components:

1. **PostgreSQL** (Bitnami chart) - Stores private data (Items, ScoreResults, FeedbackItems)
2. **GraphQL Proxy** (custom chart) - The Adapter that routes between PostgreSQL and AWS AppSync
3. **Plexus Workers** (custom chart) - Synchronous scoring API workers

```
┌─────────────────┐
│ Envoy Gateway   │  (Gateway API HTTP entrypoint)
└────────┬────────┘
         │
         │ POST /v1/score
         ▼
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│ Plexus Workers  │─────▶│  GraphQL Proxy   │─────▶│   PostgreSQL    │
│ (scoring-api)   │      │  (The Adapter)   │      │ (Private Data)  │
└─────────────────┘      └────────┬─────────┘      └─────────────────┘
                                  │
                                  │ Control-plane
                                  │ queries (cached)
                                  ▼
                         ┌─────────────────┐
                         │  AWS AppSync    │
                         │ (Scorecards,    │
                         │  Scores, etc)   │
                         └─────────────────┘
```

## Prerequisites

- Kubernetes cluster (kind, Docker Desktop, EKS, GKE, or AKS)
- Helm 3.x
- `kubectl` configured to access your cluster
- Envoy Gateway installed in the cluster, or use `docker/scripts/setup_envoy_gateway_poc.sh` for a local POC

## Quick Start (Local Development)

### 1. Create Local Values

```bash
cd docker/helm/plexus-stack
cp values-local.yaml.example values-local.yaml
```

Edit `values-local.yaml` and set:
- `graphql-proxy.config.upstreamApiUrl` - Your AWS AppSync endpoint
- `graphql-proxy.config.upstreamApiKey` - Your AWS AppSync API key
- `plexus-worker.plexus.account.key` - Your Plexus account key
- `plexus-worker.llm.openai.apiKey` - Your OpenAI API key
- `plexus-worker.llm.anthropic.apiKey` - Your Anthropic API key

### 2. Run the Local Envoy Gateway POC

```bash
cd ../../..
docker/scripts/setup_envoy_gateway_poc.sh
```

The script checks for Docker, kind, kubectl, and Helm; creates a kind cluster if needed; installs Envoy Gateway separately; creates the local `GatewayClass`; builds local images; loads them into kind; deploys this stack with local image references; validates the scoring API Service, Gateway, and HTTPRoute; and prints the Envoy data-plane Service to port-forward. The values file remains the source of truth for worker type and Gateway behavior.

If Helm reports an immutable Deployment selector error in an old disposable kind
cluster, delete the stale local worker Deployment and rerun the script:

```bash
kubectl delete deployment/plexus-plexus-worker -n plexus-local
```

Deleting and recreating the disposable kind cluster is also valid.

### 3. Manual Deployment

```bash
# Build images
docker build -t plexus-worker:local -f docker/Dockerfile .
docker build -t plexus-graphql-proxy:local -f services/private-graphql-proxy/Dockerfile .

# Install chart dependencies
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm dependency update docker/helm/plexus-stack

# Deploy
helm upgrade --install plexus docker/helm/plexus-stack \
  --namespace plexus-local \
  --create-namespace \
  --values docker/helm/plexus-stack/values-local.yaml
```

### 4. Verify Deployment

```bash
kubectl get pods -n plexus-local
kubectl get svc -n plexus-local
kubectl get gateway,httproute -n plexus-local
kubectl logs -n plexus-local -l app.kubernetes.io/name=plexus-worker --tail=50 -f

# Bypass Envoy when isolating worker health.
kubectl port-forward -n plexus-local svc/plexus-plexus-worker 8000:8000
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

### 5. Test Through Envoy Gateway

```bash
# Find the Envoy Service for the Gateway and port-forward it.
kubectl get svc -A -l gateway.envoyproxy.io/owning-gateway-name=plexus-plexus-worker-gateway
kubectl port-forward -n <envoy-service-namespace> svc/<envoy-service-name> 8080:80

# Missing required fields should return HTTP 422 from FastAPI.
curl -i -X POST http://localhost:8080/v1/score \
  -H 'content-type: application/json' \
  -d '{"scoring_job_id":"poc-route-test"}'

# A complete request reaches the scoring path. Use real existing IDs for a success.
curl -X POST http://localhost:8080/v1/score \
  -H 'content-type: application/json' \
  -d '{
    "scoring_job_id": "job-123",
    "scorecard": "scorecard-key-or-name",
    "score": "score-key-or-name",
    "item_id": "item-123"
  }'
```

In kind, the Envoy data-plane Service commonly shows `EXTERNAL-IP <pending>` and the Gateway may report `Programmed=False` while it waits for a load-balancer address. Local validation should use the Envoy Service port-forward above. A successful scoring response also depends on valid API/LLM credentials and real existing `scorecard`, `score`, and `item_id` values.

## Production Deployment

For production deployments, you'll want to:

1. **Use External PostgreSQL** (RDS, Cloud SQL, etc.)
2. **Use Platform Envoy Gateway** (provided by your infrastructure)
3. **Use External Secrets** (AWS Secrets Manager, etc.)
4. **Enable Autoscaling**
5. **Configure Resource Limits**
6. **Enable Monitoring**

### Example Production Values

```yaml
# values-production.yaml
global:
  environment: production

# Don't deploy PostgreSQL - use external RDS
postgresql:
  enabled: false

graphql-proxy:
  enabled: true
  replicaCount: 5
  
  config:
    # Use existing secret
    upstreamApiUrl: "https://YOUR-PROD-APPSYNC.appsync-api.us-west-2.amazonaws.com/graphql"
  
  createSecrets: false
  existingSecret: "graphql-proxy-secrets"
  
  postgresql:
    host: "plexus-prod.cluster-xxxxx.us-west-2.rds.amazonaws.com"
    existingSecret: "rds-credentials"
  
  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 50

plexus-worker:
  enabled: true
  workerType: scoring-api
  replicaCount: 10
  
  plexus:
    createSecrets: false
    existingSecret: "plexus-worker-secrets"
  
  scoringApi:
    enabled: true
    gateway:
      enabled: true
      createGateway: false
      gatewayName: "platform-gateway"
      gatewayNamespace: "gateway-system"
      pathPrefix: /v1/score
  
  llm:
    createSecrets: false
    existingSecret: "llm-api-keys"
  
  autoscaling:
    enabled: true
    minReplicas: 10
    maxReplicas: 100
```

Deploy to production:

```bash
helm install plexus . \
  --namespace plexus-prod \
  --create-namespace \
  --values values-production.yaml
```

## Configuration

### Global Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.namespace` | Namespace for all resources | `plexus` |
| `global.environment` | Environment identifier | `development` |
| `global.services.postgresql.host` | PostgreSQL hostname | `{{ .Release.Name }}-postgresql` |
| `global.services.graphqlProxy.host` | Proxy hostname | `{{ .Release.Name }}-graphql-proxy` |

### PostgreSQL

See [Bitnami PostgreSQL Chart](https://github.com/bitnami/charts/tree/main/bitnami/postgresql) for full configuration options.

Key parameters:
- `postgresql.enabled` - Deploy PostgreSQL in cluster (default: `true`)
- `postgresql.auth.username` - Database username
- `postgresql.auth.password` - Database password
- `postgresql.primary.persistence.size` - Disk size

### GraphQL Proxy

| Parameter | Description | Default |
|-----------|-------------|---------|
| `graphql-proxy.enabled` | Deploy the proxy | `true` |
| `graphql-proxy.replicaCount` | Number of replicas | `2` |
| `graphql-proxy.config.proxyApiKey` | Proxy API key | `local-dev-key` |
| `graphql-proxy.config.upstreamApiUrl` | AWS AppSync URL | `` |
| `graphql-proxy.config.upstreamApiKey` | AWS AppSync API key | `` |
| `graphql-proxy.autoscaling.enabled` | Enable HPA | `false` |

### Plexus Worker

| Parameter | Description | Default |
|-----------|-------------|---------|
| `plexus-worker.enabled` | Deploy workers | `true` |
| `plexus-worker.workerType` | Worker type | `scoring-api` |
| `plexus-worker.replicaCount` | Number of workers | `2` |
| `plexus-worker.scoringApi.gateway.enabled` | Create Gateway API route | `true` |
| `plexus-worker.scoringApi.gateway.pathPrefix` | HTTP path prefix | `/v1/score` |
| `plexus-worker.llm.openai.apiKey` | OpenAI API key | `` |
| `plexus-worker.autoscaling.enabled` | Enable HPA | `false` |

## Upgrading

```bash
# Upgrade the stack
helm upgrade plexus . \
  --namespace plexus-local \
  --values values-local.yaml

# Upgrade just the workers (without touching database/proxy)
helm upgrade plexus . \
  --namespace plexus-local \
  --reuse-values \
  --set plexus-worker.image.tag=v1.54.0
```

## Uninstalling

```bash
# Uninstall the stack
helm uninstall plexus --namespace plexus-local

# Delete the namespace (and PVCs)
kubectl delete namespace plexus-local
```

## Troubleshooting

### Pods are Pending

```bash
kubectl describe pod <pod-name> -n plexus-local
```

Common issues:
- Insufficient resources (CPU/memory)
- PVC not bound (check storage class)
- Image pull errors (check image name/tag)

### Scoring API Not Responding

```bash
# Check worker logs
kubectl logs -n plexus-local -l app.kubernetes.io/name=plexus-worker --tail=100

# Check worker Service and Gateway API route
kubectl get svc,gateway,httproute -n plexus-local

# Port-forward directly to isolate Envoy from worker issues
kubectl port-forward -n plexus-local svc/plexus-plexus-worker 8000:8000
curl http://localhost:8000/readyz
```

### Proxy Returns 500 Errors

```bash
# Check proxy logs
kubectl logs -n plexus-local -l app.kubernetes.io/name=graphql-proxy --tail=100

# Check database connection
kubectl exec -n plexus-local <proxy-pod> -- env | grep DATABASE

# Test database connectivity
kubectl exec -n plexus-local <proxy-pod> -- curl -v postgresql://...
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
kubectl get pods -n plexus-local | grep postgresql

# Check database credentials
kubectl get secret -n plexus-local plexus-postgresql -o yaml

# Connect to database directly
kubectl port-forward -n plexus-local svc/plexus-postgresql 5432:5432
psql -h localhost -U plexus_proxy -d plexus_proxy
```

## Development

### Testing Chart Changes Locally

```bash
# Lint the chart
helm lint .

# Dry-run to see generated manifests
helm install plexus . \
  --namespace plexus-local \
  --values values-local.yaml \
  --dry-run --debug

# Template to file for inspection
helm template plexus . --values values-local.yaml > rendered.yaml
```

### Updating Dependencies

```bash
# Update Bitnami PostgreSQL to latest version
helm dependency update

# List current dependencies
helm dependency list
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/AnthusAI/Plexus/issues
- Documentation: See `docker/ARCHITECTURE.md` and `docker/FULL_STACK_LOCAL.md`
