# Quick Reference - Plexus Kubernetes Deployment

## TL;DR - Test Locally Right Now

```bash
# 1. Enable Kubernetes in Docker Desktop (Settings → Kubernetes)

# 2. Build image
docker build -f docker/Dockerfile -t plexus-worker:local .

# 3. Create local config
cat > docker/helm/plexus-worker/values-local.yaml <<EOF
workerType: score-processor
image:
  repository: plexus-worker
  tag: local
  pullPolicy: IfNotPresent
replicaCount: 1
autoscaling:
  enabled: false
env:
  LOG_LEVEL: DEBUG
plexus:
  createSecrets: true
  api:
    url: "https://your-api-url"
    key: "your-api-key"
  account:
    key: "your-account-key"
scoreProcessor:
  aws:
    region: us-west-2
    createSecrets: true
    accessKeyId: "your-aws-key"
    secretAccessKey: "your-aws-secret"
  sqs:
    requestQueueUrl: "https://sqs.../queue"
    responseQueueUrl: "https://sqs.../response"
EOF

# 4. Deploy
helm install plexus-local docker/helm/plexus-worker \
  -f docker/helm/plexus-worker/values-local.yaml \
  --namespace plexus-local \
  --create-namespace

# 5. Check status
kubectl get pods -n plexus-local
kubectl logs -f deployment/plexus-local -n plexus-local
```

## File Structure

```
docker/
├── Dockerfile                    # The container image
├── entrypoint.sh                 # Worker selector
├── README.md                     # Complete guide
├── SECURITY.md                   # Security practices
├── LOCAL_TESTING.md             # This guide for local testing
└── helm/plexus-worker/          # Helm chart for deployment
    ├── values-dev.yaml          # Dev environment
    ├── values-staging.yaml      # Staging environment
    ├── values-prod.yaml         # Production environment
    └── templates/               # Kubernetes resources
```

## Common Commands

### Build & Deploy
```bash
# Build
docker build -f docker/Dockerfile -t plexus-worker:VERSION .

# Deploy to local K8s
helm install RELEASE docker/helm/plexus-worker -f values-ENV.yaml

# Upgrade
helm upgrade RELEASE docker/helm/plexus-worker -f values-ENV.yaml
```

### Debug
```bash
# Logs
kubectl logs -f deployment/RELEASE -n NAMESPACE

# Describe pod
kubectl describe pod POD_NAME -n NAMESPACE

# Exec into pod
kubectl exec -it POD_NAME -n NAMESPACE -- /bin/bash

# Events
kubectl get events -n NAMESPACE --sort-by='.lastTimestamp'
```

### Manage
```bash
# List releases
helm list -n NAMESPACE

# Status
helm status RELEASE -n NAMESPACE

# Rollback
helm rollback RELEASE -n NAMESPACE

# Uninstall
helm uninstall RELEASE -n NAMESPACE
```

## Worker Types

Set via `workerType` in values:

| Type | Purpose | Required Config |
|------|---------|----------------|
| `score-processor` | SQS-based scoring | AWS creds, SQS URLs |
| `celery` | RabbitMQ tasks | Broker URL |
| `console-worker` | Console chat | Response target |

## Environment Values Files

- **values-local.yaml** - Your local testing (create manually)
- **values-dev.yaml** - Development (1 replica, DEBUG)
- **values-staging.yaml** - Staging (2-10 replicas, HPA)
- **values-prod.yaml** - Production (5-30 replicas, security hardened)

## Key Configuration

```yaml
# Image
image:
  repository: your-registry/plexus-worker
  tag: "1.52.0"

# Worker type
workerType: score-processor

# Scaling
replicaCount: 3
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20

# Resources
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "1500m"

# Security
networkPolicy:
  enabled: true  # Production only

# IRSA (Production)
serviceAccount:
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT:role/Role
```

## Security Checklist

✅ Container runs as non-root (UID 1000)  
✅ No privilege escalation  
✅ All capabilities dropped  
✅ Network policies (prod)  
✅ IRSA for AWS (prod)  
✅ Secrets in Kubernetes Secrets  

## Troubleshooting

**ImagePullBackOff**: Image not found
```bash
docker images | grep plexus-worker
```

**CrashLoopBackOff**: Check logs
```bash
kubectl logs POD_NAME -n NAMESPACE
kubectl logs POD_NAME -n NAMESPACE --previous
```

**Pending**: Insufficient resources
```bash
kubectl describe pod POD_NAME -n NAMESPACE
```

## Next Steps

1. **Local testing**: See [LOCAL_TESTING.md](LOCAL_TESTING.md)
2. **Full documentation**: See [README.md](README.md)
3. **Security guide**: See [SECURITY.md](SECURITY.md)
4. **Production deploy**: Use Octopus Deploy (see README.md)

## Support

- **Local issues**: Check LOCAL_TESTING.md
- **Deployment**: Check README.md
- **Security**: Check SECURITY.md
