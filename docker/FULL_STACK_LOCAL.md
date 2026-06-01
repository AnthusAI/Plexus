# Full Stack Local Testing Guide

This guide shows how to run the complete Plexus architecture locally, including:
- **RabbitMQ** (message queue, replaces AWS SQS)
- **PostgreSQL** (private data storage)
- **GraphQL Proxy** ("The Adapter" - stores Items/ScoreResults locally)
- **Plexus Workers** (process scoring jobs from RabbitMQ)

This simulates the production Kubernetes deployment end-to-end on your local machine.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Local Docker Environment (simulates Kubernetes)            │
│                                                              │
│  ┌──────────────┐         ┌──────────────────────────┐    │
│  │  RabbitMQ    │         │  PostgreSQL              │    │
│  │  Port: 5672  │         │  Port: 55432             │    │
│  │  UI: 15672   │         │  (private data storage)  │    │
│  └──────┬───────┘         └────────┬─────────────────┘    │
│         │                           │                       │
│         │    ┌──────────────────────▼───────────────┐     │
│         │    │  GraphQL Proxy "The Adapter"         │     │
│         │    │  Port: 18080                         │     │
│         │    │  - /graphql endpoint                 │     │
│         │    │  - Stores Items/ScoreResults in PG   │     │
│         │    │  - Forwards control-plane to AWS     │     │
│         │    └──────────────────┬───────────────────┘     │
│         │                       │                          │
│         │                       │ HTTP                     │
│  ┌──────▼───────────────────────▼───────────────────┐    │
│  │  Plexus Worker (Celery mode)                     │    │
│  │  - Consumes from RabbitMQ queue                  │    │
│  │  - Calls proxy for Items/ScoreResults            │    │
│  │  - Processes scoring jobs                        │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
            ▲
            │ Control-plane queries (Scorecards, Scores, etc)
            │
    ┌───────▼────────┐
    │  AWS AppSync   │
    │  (read-only)   │
    └────────────────┘
```

## Prerequisites

1. **Docker Desktop** with Docker Compose
2. **AWS AppSync credentials** (for control-plane data)
3. **LLM API keys** (OpenAI, Anthropic, etc. for scoring)

## Step 1: Configuration

Create your environment file:

```bash
cd docker
cp .env.full-stack.example .env.full-stack
```

Edit `.env.full-stack` with your credentials:

```bash
# Required: AWS AppSync for control-plane data
PLEXUS_API_URL=https://your-appsync-endpoint.appsync-api.us-east-1.amazonaws.com/graphql
PLEXUS_API_KEY=your-appsync-api-key
PLEXUS_ACCOUNT_KEY=your-account-key

# Required: LLM API keys for scoring
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional: AWS for S3 attachments
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-west-2
```

## Step 2: Start the Full Stack

```bash
# From the docker/ directory
docker-compose -f docker-compose.full-stack.yml --env-file .env.full-stack up --build
```

This will start:
1. **PostgreSQL** - Database for private data
2. **RabbitMQ** - Message queue (with management UI)
3. **GraphQL Proxy** - The Adapter for data storage
4. **Plexus Worker** - Celery worker consuming from RabbitMQ

## Step 3: Verify Services

### Check Service Health

```bash
# Check all containers are running
docker-compose -f docker-compose.full-stack.yml ps

# Should see:
# - postgres (healthy)
# - rabbitmq (healthy)
# - graphql-proxy (healthy)
# - plexus-worker-celery (running)
```

### Access Management UIs

**RabbitMQ Management UI**: http://localhost:15672
- Username: `plexus`
- Password: `plexus`
- Check queues are created: `scoring-requests`

**GraphQL Proxy Health**: http://localhost:18080/healthz
- Should return: `{"status": "healthy"}`

**PostgreSQL**:
```bash
psql -h localhost -p 55432 -U plexus -d plexus_proxy
# Password: plexus

# Check tables
\dt

# Should see: items, score_results, feedback_items, identifiers, etc.
```

## Step 4: Send Test Scoring Job

### Option A: Using Python

Create a test script to send a scoring job to RabbitMQ:

```python
# test_send_job.py
import pika
import json

# Connect to RabbitMQ
connection = pika.BlockingConnection(
    pika.ConnectionParameters('localhost', 5672, '/', 
        pika.PlainCredentials('plexus', 'plexus'))
)
channel = connection.channel()

# Declare queue (should already exist from worker startup)
channel.queue_declare(queue='scoring-requests', durable=True)

# Create a test scoring job
task = {
    "task": "plexus.workers.celery_tasks.process_scoring_job",
    "id": "test-job-001",
    "args": ["test-scoring-job-id-123"],
    "kwargs": {
        "scorecard_name": "your-scorecard",
        "score_name": "your-score",
        "account_key": "your-account-key"
    }
}

# Send to queue
channel.basic_publish(
    exchange='',
    routing_key='scoring-requests',
    body=json.dumps(task),
    properties=pika.BasicProperties(
        delivery_mode=2,  # make message persistent
        content_type='application/json'
    )
)

print("✅ Sent scoring job to queue")
connection.close()
```

Run it:
```bash
python test_send_job.py
```

### Option B: Using Celery CLI

```bash
# Send a test health check task
docker-compose -f docker-compose.full-stack.yml exec plexus-worker-celery \
    celery -A plexus.workers.celery_app call plexus.workers.celery_tasks.health_check
```

## Step 5: Monitor Processing

### Watch Worker Logs

```bash
# Follow worker logs
docker-compose -f docker-compose.full-stack.yml logs -f plexus-worker-celery

# You should see:
# - Worker starting
# - Connecting to RabbitMQ
# - Consuming from scoring-requests queue
# - Processing tasks
```

### Check RabbitMQ Queue

Go to http://localhost:15672 → Queues → `scoring-requests`
- **Ready**: Messages waiting to be processed
- **Unacked**: Messages being processed
- **Total**: Total messages

### Query Results from PostgreSQL

```bash
docker-compose -f docker-compose.full-stack.yml exec postgres \
    psql -U plexus -d plexus_proxy -c "SELECT * FROM score_results ORDER BY created_at DESC LIMIT 10;"
```

### Query via GraphQL Proxy

```bash
curl -X POST http://localhost:18080/graphql \
  -H "Content-Type: application/json" \
  -H "x-api-key: local-dev-key" \
  -d '{
    "query": "{ listScoreResults { items { id value reasoning } } }"
  }'
```

## Step 6: Test End-to-End Workflow

### Create Test Items in Proxy

```bash
# Create a test item
curl -X POST http://localhost:18080/graphql \
  -H "Content-Type: application/json" \
  -H "x-api-key: local-dev-key" \
  -d '{
    "query": "mutation { createItem(input: { accountId: \"test\", data: \"{\\\"text\\\": \\\"This is a test message\\\"}\" }) { id } }"
  }'
```

### Submit Scoring Job

```python
# submit_job.py
from celery import Celery

app = Celery('plexus', broker='amqp://plexus:plexus@localhost:5672/')

# Send scoring job
result = app.send_task(
    'plexus.workers.celery_tasks.process_scoring_job',
    args=['your-scoring-job-id'],
    kwargs={
        'scorecard_name': 'your-scorecard',
        'score_name': 'your-score'
    }
)

print(f"Task ID: {result.id}")
print("Waiting for result...")
print(result.get(timeout=60))
```

### Verify Result

Check PostgreSQL for the score result:

```sql
SELECT 
    sr.id,
    sr.value,
    sr.reasoning,
    sr.created_at,
    i.data as item_data
FROM score_results sr
JOIN items i ON sr.item_id = i.id
ORDER BY sr.created_at DESC
LIMIT 1;
```

## Troubleshooting

### Worker Not Connecting to RabbitMQ

```bash
# Check RabbitMQ logs
docker-compose -f docker-compose.full-stack.yml logs rabbitmq

# Verify RabbitMQ is accepting connections
docker-compose -f docker-compose.full-stack.yml exec rabbitmq rabbitmqctl status
```

### Worker Not Processing Jobs

```bash
# Check worker logs for errors
docker-compose -f docker-compose.full-stack.yml logs plexus-worker-celery

# Common issues:
# - Missing PLEXUS_API_KEY
# - Invalid scorecard/score names
# - Network connectivity to AWS AppSync
```

### GraphQL Proxy Errors

```bash
# Check proxy logs
docker-compose -f docker-compose.full-stack.yml logs graphql-proxy

# Test proxy health
curl http://localhost:18080/healthz
curl http://localhost:18080/readyz

# Check database connection
docker-compose -f docker-compose.full-stack.yml exec postgres \
    psql -U plexus -d plexus_proxy -c "SELECT 1;"
```

### Items Not Appearing in PostgreSQL

The proxy creates tables on first use. Send a test mutation:

```bash
curl -X POST http://localhost:18080/graphql \
  -H "Content-Type: application/json" \
  -H "x-api-key: local-dev-key" \
  -d '{
    "query": "mutation { createItem(input: { accountId: \"test\", data: \"{}\" }) { id } }"
  }'
```

## Cleaning Up

```bash
# Stop all services
docker-compose -f docker-compose.full-stack.yml down

# Remove volumes (deletes all data)
docker-compose -f docker-compose.full-stack.yml down -v

# Remove images
docker-compose -f docker-compose.full-stack.yml down --rmi all
```

## Next Steps: Moving to Kubernetes

Once you've verified the full stack works locally with Docker Compose, you can deploy to Kubernetes:

1. **Create Helm charts** for each component:
   - `plexus-rabbitmq` (or use Bitnami RabbitMQ chart)
   - `plexus-postgresql` (or use Bitnami PostgreSQL chart)
   - `plexus-graphql-proxy` (new chart needed)
   - `plexus-worker` (already exists)

2. **Deploy to local Kubernetes**:
   ```bash
   # Install RabbitMQ
   helm install rabbitmq bitnami/rabbitmq --namespace plexus-local --create-namespace

   # Install PostgreSQL
   helm install postgresql bitnami/postgresql --namespace plexus-local

   # Install GraphQL Proxy (custom chart)
   helm install graphql-proxy ./helm/graphql-proxy --namespace plexus-local

   # Install Plexus Worker
   helm install plexus-worker ./helm/plexus-worker \
     -f ./helm/plexus-worker/values-local.yaml \
     --namespace plexus-local
   ```

3. **Test the Kubernetes deployment** using the same verification steps

4. **Package for production** with proper credentials, scaling, and security settings

## Comparing to Production

| Component | Local (Docker Compose) | Production (Kubernetes) |
|-----------|------------------------|-------------------------|
| Message Queue | RabbitMQ container | Managed RabbitMQ or AWS MQ |
| Database | PostgreSQL container | RDS PostgreSQL or managed |
| Workers | Single container | 5-30 pods with HPA |
| Networking | Docker networks | Kubernetes Services + Ingress |
| Secrets | .env file | Kubernetes Secrets + external secret manager |
| Scaling | Manual | Automatic (HPA) |
| Monitoring | Docker logs | Prometheus + Grafana |

The local setup is functionally identical but runs as single containers instead of scaled pods.
