#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/services/private-graphql-proxy/docker-compose.smoke.yml"

export PLEXUS_BACKEND_MODE="${PLEXUS_BACKEND_MODE:-local}"
export PLEXUS_PROXY_UPSTREAM_DISABLED="${PLEXUS_PROXY_UPSTREAM_DISABLED:-true}"
export PLEXUS_PROXY_API_KEY="${PLEXUS_PROXY_API_KEY:-local-smoke-key}"

cd "$ROOT_DIR"
docker compose -f "$COMPOSE_FILE" up -d --build postgres proxy

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
