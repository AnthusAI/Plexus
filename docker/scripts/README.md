# Docker Scripts

These scripts support the Kubernetes/Envoy Gateway deployment path. Do not add
new one-off variants here without updating this inventory.

## Current Entry Points

| Script | Purpose |
| --- | --- |
| `setup_envoy_gateway_poc.sh` | Create or reuse a local kind cluster, install Envoy Gateway, build/load local images, and deploy the Plexus stack in `scoring-api` mode. |
| `test_envoy_scoring_api.sh` | Send a real `POST /v1/score` request through the Envoy listener. Use after port-forwarding the Envoy data-plane Service. |
| `build_k8s_images.sh` | Build publishable `linux/amd64` or multi-arch worker and GraphQL proxy images for registry-backed cluster deployments. |
| `setup_demo_scorecard.py` | Create a demo-safe call-center scorecard in the configured backend. |
| `fetch_demo_transcripts.py` | Seed demo-safe call-center transcript items through the GraphQL proxy. |

## Local Envoy Flow

```bash
docker/scripts/setup_envoy_gateway_poc.sh

kubectl get svc -A \
  -l gateway.envoyproxy.io/owning-gateway-name=plexus-plexus-worker-gateway

kubectl port-forward -n <envoy-service-namespace> svc/<envoy-service-name> 8080:80

SCORING_API_KEY=local-scoring-api-key \
docker/scripts/test_envoy_scoring_api.sh \
  --scorecard <scorecard-id-or-key> \
  --score <score-name-or-key> \
  --item-id <item-id>
```

## Retired Helpers

The older RabbitMQ/Docker Compose helper scripts were starter-phase scaffolding
and are not part of the Kubernetes target path. They were removed to keep this
directory focused on the deployment flow that should be shown and maintained.
