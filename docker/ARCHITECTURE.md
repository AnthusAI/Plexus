# Plexus Kubernetes Architecture

This document explains the complete architecture for deploying Plexus workers to Kubernetes, including the data plane separation strategy with the private GraphQL proxy.

## Overview

The Plexus Kubernetes deployment consists of four main components:

1. **Message Queue** (RabbitMQ or AWS SQS)
2. **Private Data Store** (PostgreSQL)
3. **GraphQL Proxy** ("The Adapter")
4. **Plexus Workers** (processing pods)

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
    │  │  RabbitMQ        │      │  PostgreSQL         │  │
    │  │  (Message Queue) │      │  (Private Data)     │  │
    │  │                  │      │  - Items            │  │
    │  │  Queues:         │      │  - ScoreResults     │  │
    │  │  - scoring-      │      │  - FeedbackItems    │  │
    │  │    requests      │      │  - Identifiers      │  │
    │  │  - chat-messages │      └─────────┬───────────┘  │
    │  └────────┬─────────┘                │              │
    │           │                           │              │
    │  ┌────────▼───────────────────────────▼────────┐   │
    │  │  GraphQL Proxy ("The Adapter")              │   │
    │  │  Deployment: 2-5 pods                       │   │
    │  │  Service: ClusterIP                         │   │
    │  │                                              │   │
    │  │  Responsibilities:                           │   │
    │  │  ✓ Store private models in PostgreSQL       │   │
    │  │  ✓ Forward control-plane queries to AWS     │   │
    │  │  ✓ Cache control-plane data (15min TTL)     │   │
    │  │  ✓ Expose /graphql endpoint to workers      │   │
    │  └──────────────────┬───────────────────────────┘   │
    │                     │                                │
    │                     │ HTTP (in-cluster)              │
    │  ┌──────────────────▼───────────────────────────┐  │
    │  │  Plexus Workers                              │  │
    │  │  Deployment: 5-30 pods (HPA)                 │  │
    │  │                                               │  │
    │  │  Worker Modes:                                │  │
    │  │  1. Celery Worker (RabbitMQ consumer)        │  │
    │  │  2. Score Processor (SQS poller)             │  │
    │  │  3. Console Worker (chat processor)          │  │
    │  │                                               │  │
    │  │  Responsibilities:                            │  │
    │  │  ✓ Consume scoring requests from queue       │  │
    │  │  ✓ Load scorecard configuration              │  │
    │  │  ✓ Execute score prediction                  │  │
    │  │  ✓ Store results via GraphQL proxy           │  │
    │  └───────────────────────────────────────────────┘  │
    │                                                      │
    └──────────────────────────────────────────────────────┘
```

## Component Details

### 1. RabbitMQ (Message Queue)

**Purpose**: Distribute scoring requests across worker pods.

**Deployment**:
- Standalone deployment or Bitnami Helm chart
- Persistent volume for durability
- Management UI for monitoring

**Queues**:
- `scoring-requests` - Main scoring job queue
- `chat-messages` - Console chat processing
- `dlq-*` - Dead letter queues for failed messages

**Production Considerations**:
- High availability: 3-node cluster
- Persistent storage: EBS volumes or similar
- Monitoring: Prometheus + Grafana
- Alternative: AWS MQ (managed RabbitMQ)

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

#### Celery Worker (RabbitMQ)
```yaml
env:
  WORKER_TYPE: celery
  CELERY_BROKER_URL: amqp://user:pass@rabbitmq:5672/
  CELERY_APP: plexus.workers.celery_app
  CELERY_QUEUE: scoring-requests
  CELERY_CONCURRENCY: "4"
```

**Best for**:
- Real-time request/response workflows
- Priority queues
- Task retries with exponential backoff
- Task chaining and workflows

#### Score Processor (SQS)
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
   └─> RabbitMQ: scoring-requests queue

2. Worker pod consumes message
   ├─> Load scorecard configuration (via proxy → AWS AppSync)
   └─> Fetch item data (via proxy → PostgreSQL)

3. Worker executes score
   ├─> Call LLM APIs (OpenAI, Anthropic, etc.)
   └─> Generate score result

4. Worker stores result
   └─> GraphQL Proxy → PostgreSQL: score_results table

5. Worker acknowledges message
   └─> RabbitMQ: remove from queue
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

# RabbitMQ (internal only)
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq
  namespace: plexus
spec:
  type: ClusterIP
  selector:
    app: rabbitmq
  ports:
  - name: amqp
    port: 5672
  - name: management
    port: 15672

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

**No LoadBalancer or Ingress needed** - all communication is in-cluster.

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
  - {}  # Deny all (workers don't accept inbound)
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: graphql-proxy
    ports:
    - protocol: TCP
      port: 8000
  - to:
    - podSelector:
        matchLabels:
          app: rabbitmq
    ports:
    - protocol: TCP
      port: 5672
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
- Jobs processed per minute
- Job processing duration (p50, p95, p99)
- Job success/failure rate
- Queue depth
- Memory usage per job

**Proxy Metrics**:
- Request rate (queries/mutations per second)
- Response latency
- Cache hit rate
- Upstream API error rate
- Database connection pool usage

**RabbitMQ Metrics**:
- Queue length
- Message rate (in/out)
- Consumer count
- Unacked message count

### Logging

**Structured Logging**:
```json
{
  "timestamp": "2025-05-27T10:30:00Z",
  "level": "info",
  "component": "celery-worker",
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
- RabbitMQ queue depth > 1000
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

# Switch traffic (update message routing)
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

**KEDA (Queue Depth)**:
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

**RabbitMQ**:
- Persistent queues with durable storage
- Regular configuration backups
- Message TTL to prevent unbounded growth

### Failure Scenarios

| Failure | Impact | Recovery |
|---------|--------|----------|
| Worker pod crash | Single job fails, retried | Automatic (Kubernetes restarts) |
| RabbitMQ down | New jobs queue, processing pauses | Jobs resume when RabbitMQ returns |
| PostgreSQL down | Cannot store results | Proxy caches writes, replays on recovery |
| AWS AppSync down | Cannot load new scorecards | Proxy serves stale cache (24h) |
| GraphQL Proxy down | Workers cannot fetch/store data | Workers retry with exponential backoff |

## Future Enhancements

1. **Multi-region Deployment**: Deploy workers in multiple regions for latency reduction
2. **Federated GraphQL**: Split proxy into multiple domain-specific services
3. **Event Streaming**: Replace RabbitMQ with Kafka for higher throughput
4. **ML Model Caching**: Cache expensive model downloads at pod level
5. **Batch Processing**: Optimize for bulk scoring workloads
6. **Service Mesh**: Add Istio/Linkerd for advanced traffic management

## References

- [Helm Chart Documentation](helm/plexus-worker/README.md)
- [Security Best Practices](SECURITY.md)
- [Local Testing Guide](LOCAL_TESTING.md)
- [Full Stack Local Setup](FULL_STACK_LOCAL.md)
