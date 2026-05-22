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
- ConsoleRunWorker (can be enabled per sandbox deployment with a sandbox image URI)

### Why This Design?

**Rationale:**
1. **Sandboxes are ephemeral** - They're meant for quick dev/test cycles, not running the full production application
2. **Reduced complexity** - Developers don't need Celery queues or Docker images to test Data API or seed scripts
3. **Faster deployment** - Skipping these stacks reduces sandbox deployment time
4. **Lower cost** - Fewer resources = lower AWS costs per developer

**Trade-off:**
- Task dispatching and console chat won't work in sandboxes
- This is acceptable since sandboxes are primarily for:
  - Testing GraphQL queries/mutations
  - Testing the seed script
  - UI development with realistic data

## Enabling Full Application in Sandboxes

If you need ConsoleRunWorker in your sandbox:

### 1. Build and Push a Sandbox Worker Image

Run:

```bash
cd dashboard
./scripts/build-and-push-console-worker-image.sh --region us-west-2
```

This prints:

```bash
CONSOLE_WORKER_IMAGE_URI=<account>.dkr.ecr.<region>.amazonaws.com/plexus-console-run-worker:<tag>
```

### 2. Start Sandbox with Worker Enabled

```bash
cd dashboard
./scripts/start-sandbox-with-console-worker.sh --region us-west-2
```

This script:
- Builds and pushes the image (unless `--skip-build` is set)
- Sets `AMPLIFY_ENABLE_SANDBOX_CONSOLE_WORKER=true`
- Sets `CONSOLE_WORKER_IMAGE_URI=<image>`
- Runs `npx ampx sandbox`

You can pass normal sandbox args after `--`, for example:

```bash
./scripts/start-sandbox-with-console-worker.sh -- --identifier full-app
```

If your provider secret is not `plexus/development/config`, pass it explicitly:

```bash
./scripts/start-sandbox-with-console-worker.sh \
  --config-secret-name plexus/production/config \
  --region us-west-2
```

### 3. Optional Manual Path

If you already have an image URI:

```bash
cd dashboard
export AMPLIFY_ENABLE_SANDBOX_CONSOLE_WORKER=true
export CONSOLE_WORKER_IMAGE_URI=<your-ecr-image-uri>
export PLEXUS_CONFIG_SECRET_NAME=plexus/production/config
npx ampx sandbox
```

### 4. Infrastructure Requirements

- **Docker Image**: Console worker image must be pushed to ECR
- **Secrets Manager**: `plexus/<environment>/config` secret must exist with provider keys
- **No TaskDispatcher in sandbox**: TaskDispatcher remains disabled in sandbox mode

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

### Error: "CONSOLE_WORKER_IMAGE_URI must be set"

`AMPLIFY_ENABLE_SANDBOX_CONSOLE_WORKER=true` was set but no image URI was provided.

Use one of:

```bash
./scripts/start-sandbox-with-console-worker.sh
```

or

```bash
export AMPLIFY_ENABLE_SANDBOX_CONSOLE_WORKER=true
export CONSOLE_WORKER_IMAGE_URI=<your-ecr-image-uri>
npx ampx sandbox
```

### Want Full App in Sandbox

Follow the "Enabling Full Application in Sandboxes" section above.
