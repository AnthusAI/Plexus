# Private GraphQL Proxy Prototype

This service is a standalone prototype for keeping Plexus private data-plane
models out of AWS while preserving the existing GraphQL client contract.

The proxy exposes:

- `POST /graphql`
- `GET /healthz`
- `GET /readyz`

Private models are authoritative in PostgreSQL:

- `Item`
- `ScoreResult`
- `FeedbackItem`
- `Identifier`

Read-only control-plane queries are forwarded to AppSync and cached in
PostgreSQL. The default cache freshness TTL is 15 minutes and the stale-serving
window is 24 hours.

## Configuration

```bash
export PLEXUS_PROXY_DATABASE_URL=postgresql://plexus:plexus@localhost:55432/plexus_proxy
export PLEXUS_PROXY_API_KEY=local-smoke-key
export PLEXUS_PROXY_UPSTREAM_API_URL=https://example.appsync-api.us-east-1.amazonaws.com/graphql
# Set PLEXUS_PROXY_UPSTREAM_API_KEY in your shell or secret manager.
export PLEXUS_PROXY_CACHE_TTL_SECONDS=900
export PLEXUS_PROXY_CACHE_STALE_SECONDS=86400
```

Scoring-side clients should point `PLEXUS_API_URL` at the proxy endpoint and
use `PLEXUS_API_KEY` for the proxy API key.

## Smoke Tests

The smoke harness starts PostgreSQL, the proxy, and a pytest runner:

```bash
services/private-graphql-proxy/scripts/smoke.sh
```

Real AppSync smoke coverage is read-only and requires fixture IDs:

```bash
export PLEXUS_PROXY_UPSTREAM_API_URL=...
# Set PLEXUS_PROXY_UPSTREAM_API_KEY in your shell or secret manager.
export PLEXUS_PROXY_SMOKE_ACCOUNT_ID=...
export PLEXUS_PROXY_SMOKE_SCORECARD_ID=...
export PLEXUS_PROXY_SMOKE_SCORE_ID=...
export PLEXUS_PROXY_SMOKE_SCORE_VERSION_ID=...
export PLEXUS_PROXY_SMOKE_EVALUATION_ID=...
```

Private model smoke writes use generated test IDs and only write to local
PostgreSQL through the proxy.

## Scoring Integration

The scoring integration harness starts PostgreSQL, the proxy, and a full Plexus
dependency runner. It seeds public Hugging Face text-classification examples as
local private `Item` and `Identifier` rows, then runs the normal Plexus
prediction CLI through the proxy.

Required control-plane and score configuration values:

```bash
export PLEXUS_PROXY_UPSTREAM_API_URL="$PLEXUS_API_URL"
# Set PLEXUS_PROXY_UPSTREAM_API_KEY from your shell or secret manager.
export PLEXUS_ACCOUNT_KEY=...
export PLEXUS_PROXY_SCORING_SCORECARD=...
export PLEXUS_PROXY_SCORING_SCORE=...
```

Optional fixture controls:

```bash
export PLEXUS_PROXY_SCORING_DATASET=fancyzhx/ag_news
export PLEXUS_PROXY_SCORING_SPLIT=test
export PLEXUS_PROXY_SCORING_FIXTURE_LIMIT=3
```

Run the integration harness:

```bash
services/private-graphql-proxy/scripts/scoring-integration.sh
```

The runner sets `PLEXUS_API_URL` to the local proxy and clears the
`NEXT_PUBLIC_PLEXUS_API_*` variables so the Plexus client cannot bypass the
proxy. The test uses AppSync for read-only control-plane data and writes fixture
private rows only to local PostgreSQL.
