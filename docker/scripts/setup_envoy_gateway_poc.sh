#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-plexus-envoy-poc}"
NAMESPACE="${NAMESPACE:-plexus-local}"
ENVOY_NAMESPACE="${ENVOY_NAMESPACE:-envoy-gateway-system}"
ENVOY_GATEWAY_CHART_VERSION="${ENVOY_GATEWAY_CHART_VERSION:-1.8.1}"
RELEASE_NAME="${RELEASE_NAME:-plexus}"
VALUES_FILE="${VALUES_FILE:-$PROJECT_ROOT/docker/helm/plexus-stack/values-local.yaml}"

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
}

require_command docker
require_command kind
require_command kubectl
require_command helm

if [ ! -f "$VALUES_FILE" ]; then
  echo "Missing values file: $VALUES_FILE" >&2
  echo "Create it from docker/helm/plexus-stack/values-local.yaml.example and fill in required keys." >&2
  exit 1
fi

if ! kind get clusters | grep -qx "$CLUSTER_NAME"; then
  kind create cluster --name "$CLUSTER_NAME"
fi

kubectl config use-context "kind-$CLUSTER_NAME"

echo "Installing Envoy Gateway controller"
helm upgrade --install envoy-gateway oci://docker.io/envoyproxy/gateway-helm \
  --version "$ENVOY_GATEWAY_CHART_VERSION" \
  --namespace "$ENVOY_NAMESPACE" \
  --create-namespace

kubectl wait --namespace "$ENVOY_NAMESPACE" \
  --for=condition=Available deployment/envoy-gateway \
  --timeout=180s

echo "Ensuring Envoy GatewayClass exists"
kubectl apply -f - <<'EOF'
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: envoy-gateway
spec:
  controllerName: gateway.envoyproxy.io/gatewayclass-controller
EOF

kubectl wait --for=condition=Accepted gatewayclass/envoy-gateway --timeout=180s

echo "Building local native-arch Plexus images for kind"
docker build -t plexus-worker:local -f "$PROJECT_ROOT/docker/Dockerfile" "$PROJECT_ROOT"
docker build -t plexus-graphql-proxy:local -f "$PROJECT_ROOT/services/private-graphql-proxy/Dockerfile" "$PROJECT_ROOT"

echo "Loading images into kind"
kind load docker-image plexus-worker:local --name "$CLUSTER_NAME"
kind load docker-image plexus-graphql-proxy:local --name "$CLUSTER_NAME"

echo "Updating Helm dependencies"
helm dependency update "$PROJECT_ROOT/docker/helm/plexus-stack"

echo "Deploying Plexus stack"
helm upgrade --install "$RELEASE_NAME" "$PROJECT_ROOT/docker/helm/plexus-stack" \
  --namespace "$NAMESPACE" \
  --create-namespace \
  --values "$VALUES_FILE" \
  --set plexus-worker.image.repository=plexus-worker \
  --set plexus-worker.image.tag=local \
  --set plexus-worker.image.pullPolicy=IfNotPresent \
  --set graphql-proxy.image.repository=plexus-graphql-proxy \
  --set graphql-proxy.image.tag=local \
  --set graphql-proxy.image.pullPolicy=IfNotPresent

kubectl rollout restart deployment/"$RELEASE_NAME-graphql-proxy" -n "$NAMESPACE"
kubectl rollout restart deployment/"$RELEASE_NAME-plexus-worker" -n "$NAMESPACE"

kubectl rollout status deployment/"$RELEASE_NAME-graphql-proxy" -n "$NAMESPACE" --timeout=180s
kubectl rollout status deployment/"$RELEASE_NAME-plexus-worker" -n "$NAMESPACE" --timeout=180s

WORKER_TYPE="$(kubectl get deployment/"$RELEASE_NAME-plexus-worker" \
  -n "$NAMESPACE" \
  -o jsonpath='{range .spec.template.spec.containers[*].env[?(@.name=="WORKER_TYPE")]}{.value}{end}')"
if [ "$WORKER_TYPE" != "scoring-api" ]; then
  echo "Expected $VALUES_FILE to deploy WORKER_TYPE=scoring-api, got: ${WORKER_TYPE:-<empty>}" >&2
  exit 1
fi

kubectl get svc/"$RELEASE_NAME-plexus-worker" -n "$NAMESPACE" >/dev/null
kubectl get gateway/"$RELEASE_NAME-plexus-worker-gateway" -n "$NAMESPACE" >/dev/null
kubectl get httproute/"$RELEASE_NAME-plexus-worker-route" -n "$NAMESPACE" >/dev/null

echo "Waiting for Envoy data-plane Service"
ENVOY_SERVICE=""
for _ in {1..60}; do
  ENVOY_SERVICE="$(kubectl get svc -A \
    -l gateway.envoyproxy.io/owning-gateway-name="$RELEASE_NAME-plexus-worker-gateway" \
    -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}' | head -n 1)"
  if [ -n "$ENVOY_SERVICE" ]; then
    break
  fi
  sleep 2
done

if [ -z "$ENVOY_SERVICE" ]; then
  echo "Timed out waiting for Envoy data-plane Service" >&2
  exit 1
fi

cat <<EOF

Envoy Gateway POC deployed.

Envoy data-plane Service:
  $ENVOY_SERVICE

Inspect Gateway API resources:
  kubectl get gateway,httproute -n $NAMESPACE

Find the Envoy data-plane Service created for the Gateway:
  kubectl get svc -A -l gateway.envoyproxy.io/owning-gateway-name=$RELEASE_NAME-plexus-worker-gateway

Port-forward that Service to test locally, then POST to /v1/score:
  kubectl port-forward -n <envoy-service-namespace> svc/<envoy-service-name> 8080:80

EOF
