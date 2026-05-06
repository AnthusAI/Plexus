#!/usr/bin/env sh
set -eu

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  cat <<'EOF'
Run the private GraphQL proxy scoring integration harness.

Required environment:
  PLEXUS_PROXY_UPSTREAM_API_URL
  PLEXUS_PROXY_UPSTREAM_API_KEY
  PLEXUS_ACCOUNT_KEY
  PLEXUS_PROXY_SCORING_SCORECARD
  PLEXUS_PROXY_SCORING_SCORE

Optional:
  PLEXUS_PROXY_SCORING_DATASET=fancyzhx/ag_news
  PLEXUS_PROXY_SCORING_SPLIT=test
  PLEXUS_PROXY_SCORING_FIXTURE_LIMIT=3
EOF
  exit 0
fi

cd "$(dirname "$0")/.."
docker compose -f docker-compose.smoke.yml --profile scoring-integration up --build --abort-on-container-exit --exit-code-from scoring-integration scoring-integration
