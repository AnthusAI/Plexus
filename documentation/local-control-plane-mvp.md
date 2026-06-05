# Local Control Plane MVP Runbook

This runbook proves the local GraphQL control plane is usable by CLI tools and the dashboard without AppSync/Cognito.

## 1) Bootstrap host dependencies

Run:

```bash
cd /Users/ryan.porter/Projects/Plexus-codex-control-plane
bash scripts/bootstrap-local-mvp.sh
```

This script enforces:

- Docker CLI is available and daemon is running.
- Docker credential helper compatibility for `docker compose` pulls.
- Host prerequisites are installed/usable: `node@20`, `postgresql@16` client tools (`psql`, `pg_isready`), and `poetry`.
- `poetry install` succeeds at repo root.
- `npm ci` succeeds in `dashboard/`.

## 2) Start local control plane and dashboard

Run:

```bash
cd /Users/ryan.porter/Projects/Plexus-codex-control-plane/dashboard
npm run dev:local-control-plane
```

Expected local mode settings:

- `PLEXUS_BACKEND_MODE=local`
- `NEXT_PUBLIC_PLEXUS_BACKEND=local`
- `PLEXUS_API_URL=http://localhost:18080/graphql`
- `PLEXUS_API_KEY=local-smoke-key`
- `PLEXUS_ACCOUNT_KEY=local-demo`

## 3) Assert backend health and seeded data

Health check:

```bash
curl -s http://localhost:18080/readyz
```

Expected:

```json
{"status":"ready"}
```

Seed assertions are performed by the smoke script and check these IDs:

- `local-demo-account`
- `local-demo-scorecard`
- `local-demo-item-1`
- `local-demo-task`
- `local-demo-evaluation`
- `local-demo-report`
- `local-demo-procedure`
- `local-demo-chat-session`

## 4) Run CLI smoke

Run:

```bash
cd /Users/ryan.porter/Projects/Plexus-codex-control-plane
bash scripts/smoke-local-cli.sh
```

The script validates:

- Read checks: `items list` and `tasks last` through local index roots. There is no fallback path in proof mode.
- Write check: `items create` + `items info` roundtrip (by created item ID).
- Optional cleanup (enabled by default): delete the created smoke item.
- The proxy debug audit shows no upstream GraphQL requests.

To keep created smoke data for inspection:

```bash
SMOKE_CLEANUP=0 bash scripts/smoke-local-cli.sh
```

## 5) Run prediction smoke

Run:

```bash
cd /Users/ryan.porter/Projects/Plexus-codex-control-plane
bash scripts/smoke-local-predict.sh
```

The prediction smoke is strict and validates:

- Nira call-center fixture records exist (`nira-demo-scorecard`, `nira-demo-score`, `nira-demo-score-version`, `nira-demo-item-1`).
- Champion path is wired (`getScore(...).championVersionId` resolves to the seeded version).
- Champion version config is executable local score config (`class: TactusScore`).
- `plexus predict` succeeds against local GraphQL with `--no-cache --format json`.
- The returned `score_result_id` exists in GraphQL and is linked to expected `itemId`, `accountId`, `scorecardId`, `scoreId`, and `scoreVersionId`.
- The exact `score_result_id` is written to `tmp/local-control-plane-proof/prediction.json`.
- The proxy debug audit shows no upstream GraphQL requests.

Note:

- This smoke intentionally uses the champion-version path only.
- It does not use `--latest` until ScoreVersion index-root naming compatibility is aligned.

## 6) Run browser smoke

After prediction smoke has written `tmp/local-control-plane-proof/prediction.json`, run:

```bash
cd /Users/ryan.porter/Projects/Plexus-codex-control-plane
bash scripts/smoke-local-browser.sh
```

The browser smoke validates:

- Local dashboard pages render through `http://localhost:3000`.
- The browser makes no non-local hosted HTTP requests, including AWS/AppSync/Cognito/S3.
- The rendered pages produce no browser console errors.
- Demo user/account context is visible.
- The Nira item and Nira scorecard render.
- Local GraphQL can read back the exact prediction `ScoreResult` from the proof file.

Screenshots are written to:

```bash
tmp/local-control-plane-browser-smoke/
```

## 7) Run clean proof harness

To prove the full MVP path from a clean smoke database, run:

```bash
cd /Users/ryan.porter/Projects/Plexus-codex-control-plane
bash scripts/prove-local-control-plane.sh
```

The proof harness:

- Resets only the smoke Docker Compose stack and volumes from `services/private-graphql-proxy/docker-compose.smoke.yml`.
- Starts PostgreSQL and the local GraphQL proxy with `PLEXUS_BACKEND_MODE=local` and `PLEXUS_PROXY_UPSTREAM_DISABLED=true`.
- Seeds deterministic local demo data.
- Runs strict CLI smoke with no fallback reads.
- Runs prediction smoke and writes the exact proof file.
- Asserts `/debug/upstream-requests` is empty.
- Runs browser smoke when `http://localhost:3000` is reachable; otherwise it skips only the browser step.
