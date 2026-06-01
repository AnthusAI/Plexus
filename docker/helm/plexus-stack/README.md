# Plexus Stack Helm Chart

Complete Kubernetes deployment for the Plexus data processing stack, including PostgreSQL, GraphQL Proxy, and Celery workers.

## Architecture

This umbrella chart deploys three main components:

1. **PostgreSQL** (Bitnami chart) - Stores private data (Items, ScoreResults, FeedbackItems)
2. **GraphQL Proxy** (custom chart) - The Adapter that routes between PostgreSQL and AWS AppSync
3. **Plexus Workers** (custom chart) - Celery workers that process scoring jobs

```
┌─────────────────┐
│   RabbitMQ      │  (External - provided by infrastructure)
│  Message Queue  │
└────────┬────────┘
         │
         │ Job Queue
         ▼
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│ Plexus Workers  │─────▶│  GraphQL Proxy   │─────▶│   PostgreSQL    │
│  (Celery)       │      │  (The Adapter)   │      │ (Private Data)  │
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

- Kubernetes cluster (Docker Desktop, EKS, GKE, or AKS)
- Helm 3.x
- `kubectl` configured to access your cluster
- RabbitMQ accessible from the cluster (or running locally in docker-compose)

## Quick Start (Local Development)

### 1. Start RabbitMQ (in docker-compose)

```bash
cd docker
docker-compose -f docker-compose.full-stack.yml --env-file .env.full-stack up -d rabbitmq postgres
```

This starts RabbitMQ on `localhost:5672` which Kubernetes pods can reach via `host.docker.internal`.

### 2. Build Docker Images

```bash
# Build worker image
cd docker
docker build -t plexus-worker:local -f Dockerfile ..

# Build proxy image
cd ../services/private-graphql-proxy
docker build -t plexus-graphql-proxy:local .
```

### 3. Configure Values

```bash
cd docker/helm/plexus-stack
cp values-local.yaml.example values-local.yaml
```

Edit `values-local.yaml` and set:
- `graphql-proxy.config.upstreamApiKey` - Your AWS AppSync API key
- `plexus-worker.plexus.account.key` - Your Plexus account key
- `plexus-worker.llm.openai.apiKey` - Your OpenAI API key
- `plexus-worker.llm.anthropic.apiKey` - Your Anthropic API key

### 4. Install Bitnami Repository

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
```

### 5. Deploy the Stack

```bash
helm install plexus . \
  --namespace plexus-local \
  --create-namespace \
  --values values-local.yaml
```

### 6. Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n plexus-local

# Check services
kubectl get svc -n plexus-local

# View logs
kubectl logs -n plexus-local -l app.kubernetes.io/name=plexus-worker --tail=50 -f
```

### 7. Test the Stack

```bash
# Port-forward to the proxy
kubectl port-forward -n plexus-local svc/plexus-graphql-proxy 8000:8000

# In another terminal, submit a test job
cd docker
./scripts/quick_test.sh "Courtesy"
```

## Production Deployment

For production deployments, you'll want to:

1. **Use External PostgreSQL** (RDS, Cloud SQL, etc.)
2. **Use External RabbitMQ** (provided by your infrastructure)
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
  workerType: celery
  replicaCount: 10
  
  plexus:
    createSecrets: false
    existingSecret: "plexus-worker-secrets"
  
  celery:
    broker:
      createSecrets: false
      existingSecret: "rabbitmq-credentials"
  
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
| `plexus-worker.workerType` | Worker type | `celery` |
| `plexus-worker.replicaCount` | Number of workers | `2` |
| `plexus-worker.celery.broker.url` | RabbitMQ URL | `` |
| `plexus-worker.celery.queue` | Queue name | `scoring-requests` |
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

### Workers Not Processing Jobs

```bash
# Check worker logs
kubectl logs -n plexus-local -l app.kubernetes.io/name=plexus-worker --tail=100

# Check if worker can reach RabbitMQ
kubectl exec -n plexus-local <worker-pod> -- curl -v amqp://rabbitmq:5672
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
