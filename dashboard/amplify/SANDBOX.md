# Amplify Sandbox Configuration

## Sandbox vs Production Architecture

Amplify sandboxes in this project are configured for **development and testing**, specifically for:
- Testing the Data API (GraphQL)
- Testing authentication flows
- **Seeding with production data** (via `amplify/seed/`)
- Testing UI components against real data

### What's Included in Sandboxes

✅ **Enabled:**
- Auth (Cognito)
- Data (AppSync GraphQL API + DynamoDB)
- Storage (S3 buckets)
- Backup plans
- MCP stack

❌ **Disabled:**
- TaskDispatcher (requires Celery infrastructure)
- Vector store (TopicMemoryVectorStore)

⚙️ **Optional (off by default):**
- ConsoleRunWorker (can be enabled per sandbox deployment; image is built by CDK asset flow)

### Why This Design?

**Rationale:**
1. **Sandboxes are ephemeral** - They're meant for quick dev/test cycles, not running the full production application
2. **Reduced complexity** - Developers don't need Celery queues or Docker images to test Data API or seed scripts
3. **Faster deployment** - Skipping these stacks reduces sandbox deployment time
4. **Lower cost** - Fewer resources = lower AWS costs per developer

**Trade-off:**
- With the optional ConsoleRunWorker enabled, interactive Console chat and its
  synchronous read-only/score-version workflows can run in a sandbox.
- Asynchronous work that creates a `Task` record—reports, evaluations, and
  other Celery-dispatched jobs—will remain pending because TaskDispatcher and
  the isolated Celery consumer are not deployed.
- This is acceptable since sandboxes are primarily for:
  - Testing GraphQL queries/mutations
  - Testing the seed script
  - UI development with realistic data

## Enabling Full Application in Sandboxes

If you need ConsoleRunWorker in your sandbox:

### 1. Start Sandbox with Worker Enabled

```bash
cd dashboard
./scripts/start-sandbox-with-console-worker.sh --region us-west-2
```

This script:
- Sets `AMPLIFY_ENABLE_SANDBOX_CONSOLE_WORKER=true`
- Runs `npx ampx sandbox`
- Lets CDK build and publish the worker Lambda container image as an image asset

You can pass normal sandbox args after `--`, for example:

```bash
./scripts/start-sandbox-with-console-worker.sh -- --identifier full-app
```

If your sandbox-region provider secret is not `plexus/staging/config`, pass it explicitly:

```bash
./scripts/start-sandbox-with-console-worker.sh \
  --config-secret-name plexus/development/config \
  --region us-west-2
```

The launcher rejects `plexus/production/config` so a sandbox worker cannot
silently use production model credentials.

### 2. Infrastructure Requirements

- **Docker available locally**: CDK image asset build requires Docker
- **Secrets Manager**: `plexus/<environment>/config` secret must exist with provider keys
- **No TaskDispatcher in sandbox**: TaskDispatcher remains disabled in sandbox mode.
  Do not dispatch reports/evaluations for completion testing in this setup;
  they will create durable `PENDING` tasks but no worker can consume them.
  Full async acceptance testing requires a separate, isolated Celery queue,
  result backend, dispatcher, and consumer.

## Sandbox Detection Logic

Location: `amplify/backend.ts`

```typescript
const isSandbox = process.env.AWS_BRANCH === undefined && 
                  process.env.AMPLIFY_ENV === undefined;
```

**How it works:**
- `AWS_BRANCH` is set by Amplify hosting (production/staging deployments)
- `AMPLIFY_ENV` is set by `ampx pipeline-deploy` (CI/CD deployments)
- If neither is set → we're in a sandbox (running `npx ampx sandbox`)

## Testing Seed Script in Sandbox

The seed script works in both default sandbox mode and worker-enabled sandbox mode:

```bash
cd dashboard
./scripts/setup-sandbox-secrets.sh  # One-time setup
npx ampx sandbox                    # Default lightweight sandbox
# OR:
./scripts/start-sandbox-with-console-worker.sh
npx ampx sandbox seed generate-policy
npx ampx sandbox seed               # Seed from production
```

See `amplify/seed/README.md` for complete seeding documentation.

## Troubleshooting

### Error: "TaskDispatcher requires CELERY_AWS_ACCESS_KEY_ID"

This means `isSandbox` is false. Check:
1. Are you running `npx ampx sandbox`? (not `ampx pipeline-deploy`)
2. Is `AWS_BRANCH` or `AMPLIFY_ENV` accidentally set in your shell?

Solution: Unset those variables:
```bash
unset AWS_BRANCH AMPLIFY_ENV
npx ampx sandbox
```

### Error: Docker build/publish failed for ConsoleRunWorker image asset

`AMPLIFY_ENABLE_SANDBOX_CONSOLE_WORKER=true` was set and CDK could not build/publish the container image.

Check:
1. Docker Desktop/daemon is running
2. You can run `docker build` locally
3. Your AWS credentials can publish CDK assets in this account/region

### Want Full App in Sandbox

Follow the "Enabling Full Application in Sandboxes" section above.
