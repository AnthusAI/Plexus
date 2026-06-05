#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/services/private-graphql-proxy/docker-compose.smoke.yml"

export PLEXUS_BACKEND_MODE="${PLEXUS_BACKEND_MODE:-local}"
export PLEXUS_PROXY_UPSTREAM_DISABLED="${PLEXUS_PROXY_UPSTREAM_DISABLED:-true}"
export PLEXUS_PROXY_API_KEY="${PLEXUS_PROXY_API_KEY:-local-smoke-key}"
export PLEXUS_PROXY_AUTH_MODE="${PLEXUS_PROXY_AUTH_MODE:-}"
export AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME="${AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME:-plexus-local-report-block-details}"
export EMBEDDING_CACHE_BUCKET="${EMBEDDING_CACHE_BUCKET:-plexus-embeddings}"
export PLEXUS_OBJECT_STORE_ENDPOINT="${PLEXUS_OBJECT_STORE_ENDPOINT:-http://localhost:19000}"
export PLEXUS_OBJECT_STORE_REGION="${PLEXUS_OBJECT_STORE_REGION:-us-east-1}"
export PLEXUS_OBJECT_STORE_FORCE_PATH_STYLE="${PLEXUS_OBJECT_STORE_FORCE_PATH_STYLE:-true}"
export PLEXUS_OBJECT_STORE_ACCESS_KEY_ID="${PLEXUS_OBJECT_STORE_ACCESS_KEY_ID:-plexus-local}"
export PLEXUS_OBJECT_STORE_SECRET_ACCESS_KEY="${PLEXUS_OBJECT_STORE_SECRET_ACCESS_KEY:-plexus-local-secret}"
export PLEXUS_VECTOR_STORE_PROVIDER="${PLEXUS_VECTOR_STORE_PROVIDER:-qdrant}"
export PLEXUS_VECTOR_STORE_URL="${PLEXUS_VECTOR_STORE_URL:-http://localhost:19002}"
export PLEXUS_VECTOR_STORE_COLLECTION="${PLEXUS_VECTOR_STORE_COLLECTION:-topic-memory-local}"

cd "$ROOT_DIR"
docker compose -f "$COMPOSE_FILE" up -d --build postgres minio minio-init qdrant proxy

docker compose -f "$COMPOSE_FILE" run --rm \
  -e PLEXUS_API_URL=http://proxy:8000/graphql \
  -e PLEXUS_API_KEY="$PLEXUS_PROXY_API_KEY" \
  smoke-tests \
  sh -c "pip install --no-cache-dir -r services/private-graphql-proxy/requirements.txt >/dev/null && python services/private-graphql-proxy/scripts/seed_local_demo.py"

cd "$ROOT_DIR/dashboard"
export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"
export PLEXUS_API_KEY="${PLEXUS_API_KEY:-$PLEXUS_PROXY_API_KEY}"
export PLEXUS_ACCOUNT_KEY="${PLEXUS_ACCOUNT_KEY:-local-demo}"
export NEXT_PUBLIC_PLEXUS_BACKEND=local
export NEXT_PUBLIC_PLEXUS_API_URL="$PLEXUS_API_URL"
export NEXT_PUBLIC_PLEXUS_API_KEY="$PLEXUS_API_KEY"
export NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY="$PLEXUS_ACCOUNT_KEY"
export NEXT_PUBLIC_PLEXUS_API_REGION="${NEXT_PUBLIC_PLEXUS_API_REGION:-local}"

npm run dev:web
