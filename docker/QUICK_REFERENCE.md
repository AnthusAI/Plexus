# Quick Reference - Plexus Kubernetes Deployment

## TL;DR - Envoy Gateway POC Locally

```bash
# 1. Create local stack values
cp docker/helm/plexus-stack/values-local.yaml.example \
   docker/helm/plexus-stack/values-local.yaml

# 2. Edit values with API/account/LLM keys
vim docker/helm/plexus-stack/values-local.yaml

# 3. Build, install Envoy Gateway, and deploy to kind
docker/scripts/setup_envoy_gateway_poc.sh

# 4. Check status
kubectl get pods -n plexus-local
kubectl get gateway,httproute -n plexus-local

# 5. Find and port-forward the Envoy data-plane Service
kubectl get svc -A \
  -l gateway.envoyproxy.io/owning-gateway-name=plexus-plexus-worker-gateway
kubectl port-forward -n <envoy-service-namespace> svc/<envoy-service-name> 8080:80

# 6. Smoke test routing to the scoring API
curl -i -X POST http://localhost:8080/v1/score \
  -H 'content-type: application/json' \
  -d '{"scoring_job_id":"poc-route-test"}'
```

The local kind Service can show `EXTERNAL-IP <pending>` and the Gateway can remain unprogrammed while waiting for a load-balancer address. Port-forward the Envoy data-plane Service for local testing. The smoke test above should return HTTP 422 from FastAPI, proving the request reached the scoring API. A real score requires valid local credentials plus existing `scorecard`, `score`, and `item_id` values.

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
| `scoring-api` | Envoy-routed synchronous HTTP scoring | Plexus API/account keys |
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
