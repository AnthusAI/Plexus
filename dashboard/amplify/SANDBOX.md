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
- ConsoleRunWorker (requires Docker image URI)
- Vector store (TopicMemoryVectorStore)

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

If you need TaskDispatcher and ConsoleWorker in your sandbox:

### 1. Set Required Environment Variables

Add to your `.env`:

```bash
# Celery Configuration
CELERY_AWS_ACCESS_KEY_ID=your-key
CELERY_AWS_SECRET_ACCESS_KEY=your-secret
CELERY_AWS_REGION_NAME=us-west-2
CELERY_QUEUE_NAME=your-queue-name
CELERY_RESULT_BACKEND_TEMPLATE=dynamodb://...
CELERY_QUEUE_URL=https://sqs.us-west-2.amazonaws.com/...

# Console Worker Configuration
CONSOLE_WORKER_IMAGE_URI=your-ecr-image-uri
PLEXUS_API_URL=https://your-api.appsync-api.us-west-2.amazonaws.com/graphql
```

### 2. Modify backend.ts

In `amplify/backend.ts`, change the sandbox detection logic:

```typescript
// Option A: Always enable (no sandbox mode)
const isSandbox = false;

// Option B: Enable for specific sandbox identifiers
const isSandbox = process.env.AMPLIFY_SANDBOX_IDENTIFIER !== 'full-app';
// Then run: npx ampx sandbox --identifier full-app
```

### 3. Infrastructure Requirements

- **Celery Queue**: Must be created separately (not in Amplify stack)
- **Docker Image**: Console worker image must be pushed to ECR
- **DynamoDB Backend**: Celery result backend table must exist

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

The seed script works perfectly in sandbox mode:

```bash
cd dashboard
./scripts/setup-sandbox-secrets.sh  # One-time setup
npx ampx sandbox                    # Start sandbox (no env vars needed!)
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

Same as above - sandbox mode isn't detected properly.

### Want Full App in Sandbox

Follow the "Enabling Full Application in Sandboxes" section above.
