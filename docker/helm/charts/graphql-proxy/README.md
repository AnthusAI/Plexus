# GraphQL Proxy Helm Chart

Helm chart for deploying the Plexus GraphQL Proxy service that routes between PostgreSQL (private data) and AWS AppSync (control plane).

## Overview

The GraphQL Proxy acts as "The Adapter" in the Plexus architecture, providing:
- Connection pooling and caching for AWS AppSync queries
- Storage of private data (Items, ScoreResults, FeedbackItems) in PostgreSQL
- API key authentication for workers
- Health check endpoints for Kubernetes probes

## Configuration

### Database Connection

The proxy constructs its PostgreSQL connection URL at runtime from individual environment variables:
- `DB_USER` - Database username
- `DB_PASSWORD` - Database password (from Secret)
- `DB_HOST` - Database hostname
- `DB_PORT` - Database port
- `DB_NAME` - Database name

This approach allows Kubernetes to inject sensitive passwords from Secrets without requiring shell variable expansion in the deployment manifest.

### Required Values

```yaml
config:
  proxyApiKey: ""          # API key for worker authentication
  upstreamApiUrl: ""       # AWS AppSync GraphQL endpoint
  upstreamApiKey: ""       # AWS AppSync API key

postgresql:
  host: ""                 # PostgreSQL host (or use global.services.postgresql.host)
  port: 5432
  database: ""
  username: ""
  existingSecret: ""       # Name of Secret containing password
```

## Deployment

When deployed as part of the plexus-stack umbrella chart, the PostgreSQL connection details are automatically configured from global values.

For standalone deployment:

```bash
helm install graphql-proxy . \
  --set config.proxyApiKey=your-key \
  --set config.upstreamApiUrl=https://your-appsync-endpoint.amazonaws.com/graphql \
  --set config.upstreamApiKey=your-appsync-key \
  --set postgresql.host=your-postgres-host \
  --set postgresql.username=your-user \
  --set postgresql.existingSecret=your-secret
```

## Health Checks

- `/healthz` - Basic liveness probe
- `/readyz` - Readiness probe (checks database connectivity)

## Security

- Runs as non-root user (UID 1000)
- Read-only root filesystem
- No privilege escalation
- Secrets managed via Kubernetes Secrets
- API keys stored in Secrets, not ConfigMaps
