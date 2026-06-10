# Plexus Kubernetes Architecture

This document explains the complete architecture for deploying Plexus workers to Kubernetes, including the data plane separation strategy with the private GraphQL proxy.

## Overview

The Plexus Kubernetes proof of concept consists of four main components:

1. **Envoy Gateway** (HTTP entrypoint using Kubernetes Gateway API)
2. **Private Data Store** (PostgreSQL)
3. **GraphQL Proxy** ("The Adapter")
4. **Plexus Scoring API Workers** (synchronous HTTP scoring pods)

This POC intentionally does **not** preserve RabbitMQ queue semantics. Existing SQS/Lambda infrastructure remains a separate deployment path.

## Architecture Diagram

```
                    ┌──────────────────────────┐
                    │   AWS AppSync            │
                    │   (Control Plane)        │
                    │   - Scorecards           │
                    │   - Scores               │
                    │   - Score Versions       │
                    │   - Accounts             │
                    └────────────┬─────────────┘
                                 │ Read-only
                                 │ (cached)
                                 │
    ┌────────────────────────────▼─────────────────────────┐
    │  Kubernetes Cluster                                  │
    │                                                       │
    │  ┌──────────────────┐      ┌────────────────────┐  │
    │  │ Envoy Gateway    │      │  PostgreSQL         │  │
    │  │ (HTTP entrypoint)│      │  (Private Data)     │  │
    │  │                  │      │  - Items            │  │
    │  │ Gateway API:     │      │  - ScoreResults     │  │
    │  │ - Gateway        │      │  - FeedbackItems    │  │
    │  │ - HTTPRoute      │      │  - Identifiers      │  │
    │  └────────┬─────────┘      └─────────┬───────────┘  │
    │           │ HTTP                      │              │
    │           ▼                           │              │
    │  ┌────────────────────────────────────▼────────┐   │
    │  │  GraphQL Proxy ("The Adapter")              │   │
    │  │  Deployment: 2-5 pods                       │   │
    │  │  Service: ClusterIP                         │   │
    │  │                                              │   │
    │  │  Responsibilities:                           │   │
    │  │  ✓ Store private models in PostgreSQL       │   │
    │  │  ✓ Forward control-plane queries to AWS     │   │
    │  │  ✓ Cache control-plane data (15min TTL)     │   │
    │  │  ✓ Expose /graphql endpoint to workers      │   │
    │  └──────────────────▲───────────────────────────┘   │
    │                     │ HTTP (in-cluster)              │
    │  ┌──────────────────┴───────────────────────────┐  │
    │  │  Plexus Scoring API Workers                  │  │
    │  │  Deployment: 5-30 pods (HPA)                 │  │
    │  │                                               │  │
    │  │  Worker Mode: scoring-api                    │  │
    │  │  - POST /v1/score                            │  │
    │  │  - Synchronous score execution               │  │
    │  │                                               │  │
    │  │  Responsibilities:                            │  │
    │  │  ✓ Accept scoring requests over HTTP         │  │
    │  │  ✓ Load scorecard configuration              │  │
    │  │  ✓ Execute score prediction                  │  │
    │  │  ✓ Store results via GraphQL proxy           │  │
    │  └───────────────────────────────────────────────┘  │
    │                                                      │
    └──────────────────────────────────────────────────────┘
```

## Component Details

### 1. Envoy Gateway (HTTP Entry Point)

**Purpose**: Route external HTTP scoring requests into the Kubernetes cluster.

**Deployment**:
- Envoy Gateway controller installed separately from the Plexus chart
- Gateway API resources created by the Plexus worker chart for the POC
- Future clusters can provide a platform-managed Gateway; Plexus can create only HTTPRoutes
- The local POC script creates the `envoy-gateway` `GatewayClass` and waits for the generated Envoy data-plane Service

**Routes**:
- `POST /v1/score` - Synchronous scoring API
- `/healthz` and `/readyz` - Worker health probes, available directly on the worker Service

For local kind validation, the Envoy data-plane Service can remain `EXTERNAL-IP <pending>` and the Gateway can report `Programmed=False` while waiting for a load-balancer address. Port-forward the generated Envoy Service to test the route locally.

**Production Considerations**:
- Use a platform-managed GatewayClass and shared Gateway where available
- Configure TLS, hostname policy, rate limiting, and request timeouts at the gateway layer
- Keep queue-based SQS/Lambda infrastructure as a separate deployment path where durable async semantics are required

### 2. PostgreSQL (Private Data Store)

**Purpose**: Store private data plane models that must not go to AWS.

**Schema**:
```sql
-- Core private models
CREATE TABLE items (
    id UUID PRIMARY KEY,
    account_id TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE score_results (
    id UUID PRIMARY KEY,
    scoring_job_id UUID,
    item_id UUID REFERENCES items(id),
    score_id UUID NOT NULL,
    value JSONB,
    reasoning TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE feedback_items (
    id UUID PRIMARY KEY,
    score_result_id UUID REFERENCES score_results(id),
    item_id UUID REFERENCES items(id),
    feedback_type TEXT,
    feedback_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE identifiers (
    id UUID PRIMARY KEY,
    item_id UUID REFERENCES items(id),
    identifier_type TEXT,
    identifier_value TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(identifier_type, identifier_value)
);

-- Control-plane cache (from AWS AppSync)
CREATE TABLE cached_scorecards (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT,
    data JSONB,
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE TABLE cached_scores (
    id UUID PRIMARY KEY,
    scorecard_id UUID,
    name TEXT NOT NULL,
    data JSONB,
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);
```

**Production Considerations**:
- Managed service: AWS RDS, Azure Database, or Google Cloud SQL
- Backups: Automated daily backups with point-in-time recovery
- Scaling: Read replicas for query performance
- Monitoring: Connection pooling, slow query logs

### 3. GraphQL Proxy ("The Adapter")

**Purpose**: Provide a unified GraphQL API that stores private data locally while forwarding control-plane queries to AWS.

**Implementation**: FastAPI + Strawberry GraphQL + SQLAlchemy

**Key Features**:
- **Private Model Storage**: Items, ScoreResults, FeedbackItems → PostgreSQL
- **Control-Plane Forwarding**: Scorecards, Scores, Accounts → AWS AppSync
- **Caching**: Control-plane responses cached for 15 minutes
- **Stale Serving**: Serve stale cache for 24 hours if AWS is unavailable
- **Health Endpoints**: `/healthz` and `/readyz` for Kubernetes probes

**Configuration**:
```yaml
# Environment variables
PLEXUS_PROXY_DATABASE_URL: postgresql://user:pass@postgres:5432/plexus_proxy
PLEXUS_PROXY_API_KEY: your-proxy-api-key
PLEXUS_PROXY_UPSTREAM_API_URL: https://appsync.amazonaws.com/graphql
PLEXUS_PROXY_UPSTREAM_API_KEY: your-appsync-key
PLEXUS_PROXY_CACHE_TTL_SECONDS: 900
PLEXUS_PROXY_CACHE_STALE_SECONDS: 86400
```

**Kubernetes Resources**:
```yaml
# Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: graphql-proxy
spec:
  replicas: 2-5
  template:
    spec:
      containers:
      - name: proxy
        image: plexus-graphql-proxy:latest
        ports:
        - containerPort: 8000

# Service (internal only)
apiVersion: v1
kind: Service
metadata:
  name: graphql-proxy
spec:
  type: ClusterIP
  ports:
  - port: 8000
    targetPort: 8000
```

**Does it need HAProxy?**

**No**, in most cases:
- FastAPI/Uvicorn handles concurrent requests efficiently
- Kubernetes Service provides basic load balancing across pods
- Use HPA to scale proxy pods based on CPU/memory

**Yes**, if you need:
- Advanced load balancing (weighted routing, sticky sessions)
- Rate limiting or request throttling
- SSL termination or mTLS
- HTTP caching layer
- Request transformation or filtering

For most deployments, the Kubernetes Service is sufficient.

### 4. Plexus Workers

**Purpose**: Process scoring jobs by executing score predictions on items.

**Worker Modes**:

#### Scoring API Worker (Envoy Gateway HTTP)
```yaml
env:
  WORKER_TYPE: scoring-api
  SCORING_API_HOST: 0.0.0.0
  SCORING_API_PORT: "8000"
```

**Endpoint**:
```http
POST /v1/score
Content-Type: application/json

{
  "scoring_job_id": "job-123",
  "scorecard": "scorecard-key-or-name",
  "score": "score-key-or-name",
  "item_id": "item-123",
  "account_key": "optional-account-key"
}
```

**Best for**:
- Envoy Gateway POC deployments
- Synchronous request/response scoring
- Clusters where RabbitMQ is not part of the target architecture

For route smoke tests, an incomplete request should return HTTP 422 from FastAPI, confirming Envoy reached the scoring API. A successful score result requires valid Plexus credentials, LLM credentials for the selected score, and real existing `scorecard`, `score`, and `item_id` values.

#### Celery Worker (RabbitMQ, optional legacy mode)
```yaml
env:
  WORKER_TYPE: celery
  CELERY_BROKER_URL: amqp://user:pass@rabbitmq:5672/
  CELERY_APP: plexus.workers.celery_app
  CELERY_QUEUE: scoring-requests
  CELERY_CONCURRENCY: "4"
```

**Best for**:
- Existing RabbitMQ deployments
- Priority queues
- Task retries with exponential backoff
- Task chaining and workflows

#### Score Processor (SQS, separate deployment path)
```yaml
env:
  WORKER_TYPE: score-processor
  PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL: https://sqs...
  PLEXUS_RESPONSE_WORKER_QUEUE_URL: https://sqs...
```

**Best for**:
- AWS-native deployments
- Serverless integration
- Simple queue semantics
- AWS Lambda compatibility

#### Console Worker
```yaml
env:
  WORKER_TYPE: console-worker
  CONSOLE_RESPONSE_TARGET: local:developer
```

**Best for**:
- Interactive chat-based scoring
- Development and debugging
- Console UI integration

**Scaling Configuration**:
```yaml
# Horizontal Pod Autoscaler
autoscaling:
  enabled: true
  minReplicas: 5
  maxReplicas: 30
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

# Pod Disruption Budget
podDisruptionBudget:
  enabled: true
  minAvailable: 3
```

## Data Flow

### Scoring Request Flow

```
1. Client submits scoring request
   └─> Envoy Gateway: POST /v1/score

2. Envoy routes request
   └─> Plexus scoring-api Service → worker pod

3. Worker pod handles request synchronously
   ├─> Load scorecard configuration (via proxy → AWS AppSync)
   └─> Fetch item data (via proxy → PostgreSQL)

4. Worker executes score
   ├─> Call LLM APIs (OpenAI, Anthropic, etc.)
   └─> Generate score result

5. Worker stores result
   └─> GraphQL Proxy → PostgreSQL: score_results table

6. Worker returns HTTP response
   └─> Envoy Gateway → Client
```

### Query Flow

#### Control-Plane Query (e.g., "Get Scorecard")
```
Worker → GraphQL Proxy
         ├─> Check cache (PostgreSQL)
         ├─> If fresh: return cached data
         └─> If stale:
             ├─> Forward to AWS AppSync
             ├─> Update cache
             └─> Return data
```

#### Private Data Query (e.g., "Get Items")
```
Worker → GraphQL Proxy
         └─> Query PostgreSQL directly
             └─> Return items
```

## Network Architecture

### Kubernetes Services

```yaml
# GraphQL Proxy (internal only)
apiVersion: v1
kind: Service
metadata:
  name: graphql-proxy
  namespace: plexus
spec:
  type: ClusterIP
  selector:
    app: graphql-proxy
  ports:
  - port: 8000
    targetPort: 8000

# Scoring API Worker (internal Service routed by Envoy Gateway)
apiVersion: v1
kind: Service
metadata:
  name: plexus-worker
  namespace: plexus
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/component: worker
    worker-type: scoring-api
  ports:
  - name: http
    port: 8000
    targetPort: http

# PostgreSQL (internal only)
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: plexus
spec:
  type: ClusterIP
  selector:
    app: postgres
  ports:
  - port: 5432
```

Envoy Gateway owns the external entrypoint. Plexus application pods remain behind ClusterIP Services.

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: plexus-worker-policy
spec:
  podSelector:
    matchLabels:
      app: plexus-worker
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector: {}  # Restrict to the Envoy Gateway namespace in production
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: graphql-proxy
    ports:
    - protocol: TCP
      port: 8000
  - to:  # Allow external LLM APIs
    ports:
    - protocol: TCP
      port: 443
```

## Security

### Authentication Flow

```
Worker Pod
  ├─> GraphQL Proxy: x-api-key header (PLEXUS_PROXY_API_KEY)
  │
  GraphQL Proxy
    ├─> PostgreSQL: user/password (PLEXUS_PROXY_DATABASE_URL)
    └─> AWS AppSync: x-api-key header (PLEXUS_PROXY_UPSTREAM_API_KEY)
```

### Secrets Management

**Kubernetes Secrets**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: plexus-worker-secrets
type: Opaque
stringData:
  PLEXUS_PROXY_API_KEY: "..."
  OPENAI_API_KEY: "..."
  ANTHROPIC_API_KEY: "..."

---
apiVersion: v1
kind: Secret
metadata:
  name: graphql-proxy-secrets
type: Opaque
stringData:
  PLEXUS_PROXY_DATABASE_URL: "postgresql://..."
  PLEXUS_PROXY_UPSTREAM_API_KEY: "..."
```

**Production**: Use AWS Secrets Manager, Azure Key Vault, or HashiCorp Vault with external-secrets operator.

### IAM Roles (AWS)

**IRSA (IAM Roles for Service Accounts)**:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: plexus-worker
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT:role/PlexusWorkerRole
```

This eliminates the need for AWS access keys in secrets.

## Monitoring & Observability

### Metrics

**Worker Metrics**:
- HTTP scoring requests per minute
- Scoring request duration (p50, p95, p99)
- Scoring success/failure rate
- In-flight request count
- Memory usage per job

**Proxy Metrics**:
- Request rate (queries/mutations per second)
- Response latency
- Cache hit rate
- Upstream API error rate
- Database connection pool usage

**Envoy Gateway Metrics**:
- Request rate by route
- Response status by route
- Upstream response latency
- Upstream connection errors

### Logging

**Structured Logging**:
```json
{
  "timestamp": "2025-05-27T10:30:00Z",
  "level": "info",
  "component": "scoring-api",
  "pod": "plexus-worker-abc123",
  "scoring_job_id": "job-456",
  "scorecard": "customer-support",
  "score": "sentiment",
  "duration_ms": 2341,
  "result": "positive"
}
```

**Log Aggregation**: ELK stack, Splunk, or CloudWatch Logs

### Alerting

**Critical Alerts**:
- Worker pods crash looping
- Envoy Gateway route 5xx errors > 5%
- PostgreSQL connection errors
- GraphQL proxy 5xx errors > 5%
- Job processing duration > 30s (p95)

## Deployment Strategies

### Blue-Green Deployment

```bash
# Deploy new version to "green" namespace
helm install plexus-worker-green ./helm/plexus-worker \
  --namespace plexus-green \
  --set image.tag=v1.53.0

# Verify health
kubectl get pods -n plexus-green

# Switch traffic (update HTTPRoute or Gateway references)
# Drain old pods
helm uninstall plexus-worker-blue -n plexus-blue
```

### Canary Deployment

```yaml
# Deploy 10% of workers with new version
apiVersion: apps/v1
kind: Deployment
metadata:
  name: plexus-worker-canary
spec:
  replicas: 1  # 10% of total
  template:
    spec:
      containers:
      - image: plexus-worker:v1.53.0
```

Monitor error rates, then scale up canary and scale down stable.

### Rolling Update (Default)

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
```

Zero-downtime updates by starting new pods before terminating old ones.

## Cost Optimization

### Resource Sizing

**Development**:
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

**Production**:
```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "1500m"
```

### Autoscaling

**HPA (CPU/Memory)**:
- Scale up when CPU > 70%
- Scale down when CPU < 30% (cooldown: 5min)

**Gateway/HTTP Metrics (Advanced)**:
Use Prometheus adapter, KEDA HTTP add-ons, or platform metrics to scale on request rate or in-flight requests when CPU/memory does not reflect scoring load accurately.

The existing SQS deployment path can still use KEDA queue-depth scaling independently of this Envoy Gateway POC.

<!-- Queue-based example intentionally omitted for the Envoy Gateway POC. -->
<!--
```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: plexus-worker-scaler
spec:
  scaleTargetRef:
    name: plexus-worker
  triggers:
  - type: rabbitmq
    metadata:
      queueName: scoring-requests
      queueLength: "10"  # Scale up when > 10 messages per pod
```
-->

### Spot Instances

Use spot/preemptible instances for worker pods (not for stateful services):
```yaml
nodeSelector:
  node-type: spot
tolerations:
- key: spot
  operator: Exists
```

## Disaster Recovery

### Backup Strategy

**PostgreSQL**:
- Automated daily backups
- Point-in-time recovery enabled
- Cross-region replication for production

**Envoy Gateway**:
- Gateway controller and data-plane replicas should run with disruption budgets
- TLS and hostname policy should be managed by the platform
- HTTP requests are synchronous; retry behavior belongs at the client or gateway layer

### Failure Scenarios

| Failure | Impact | Recovery |
|---------|--------|----------|
| Worker pod crash | In-flight HTTP request fails | Client retries; Kubernetes restarts pod |
| Envoy Gateway down | New HTTP requests cannot enter cluster | Restore gateway controller/data plane |
| PostgreSQL down | Cannot store results | Proxy caches writes, replays on recovery |
| AWS AppSync down | Cannot load new scorecards | Proxy serves stale cache (24h) |
| GraphQL Proxy down | Workers cannot fetch/store data | Workers retry with exponential backoff |

## Future Enhancements

1. **Multi-region Deployment**: Deploy workers in multiple regions for latency reduction
2. **Federated GraphQL**: Split proxy into multiple domain-specific services
3. **Async Work Backend**: Add a durable queue or event stream if future deployments need async scoring semantics
4. **ML Model Caching**: Cache expensive model downloads at pod level
5. **Batch Processing**: Optimize for bulk scoring workloads
6. **Service Mesh**: Add Istio/Linkerd for advanced traffic management

## References

- [Helm Chart Documentation](helm/plexus-worker/README.md)
- [Security Best Practices](SECURITY.md)
- [Local Testing Guide](LOCAL_TESTING.md)
- [Full Stack Local Setup](FULL_STACK_LOCAL.md)
