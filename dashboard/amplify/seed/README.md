# Plexus Sandbox Seeding

Automated utility for populating Amplify Gen2 sandboxes with production data to enable realistic development and testing.

## Overview

This seed script copies data from your production environment into an Amplify sandbox using smart strategies:
- **Small reference tables** (Account, Scorecard, Score): Full copy
- **Operational tables** (Task, Evaluation, Report): Last 30 days only
- **Large-scale tables** (Item, ScoreResult): Recent 1000 + random sample of 1000 older records

**S3 file copying is disabled by default** (opt-in via `INCLUDE_S3_SYNC=true` flag).

## Prerequisites

- Node.js 18+ and npm
- Amplify Gen2 CLI (`@aws-amplify/backend-cli`)
- Production API URL and API key
- Account ID to seed

## Installation

The `@aws-amplify/seed` package is already installed as a dev dependency.

```bash
# Verify installation
cd dashboard
npm list @aws-amplify/seed
```

## Setup

### 1. Find Your Production Credentials

You'll need these values from your production environment:

**PROD_API_URL**: Get from production `amplify_outputs.json`:
```json
{
  "data": {
    "url": "https://xxxxx.appsync-api.us-east-1.amazonaws.com/graphql"
  }
}
```

**PROD_API_KEY**: Get from production `amplify_outputs.json`:
```json
{
  "data": {
    "api_key": "da2-xxxxxxxxxxxxx"
  }
}
```

**PROD_ACCOUNT_ID**: Your Plexus account UUID (NOT AWS account ID or Amplify app ID).
This is the `id` field from your Account table. For example: `9c929f25-a91f-4db7-8943-5aa93498b8e9`

To find your account ID:
- Query your production database: `SELECT id, key, name FROM Account;`
- Look for the account with key "call-criteria" or your organization name
- Use the UUID `id` value (not the `key` string)

### 2. Configure Secrets

Set up required secrets for accessing production data:

```bash
# Required secrets
npx ampx sandbox secret set PROD_API_URL
# Enter: https://{prod-api-id}.appsync-api.us-east-1.amazonaws.com/graphql

npx ampx sandbox secret set PROD_API_KEY
# Enter: da2-xxxxxxxxxxxxx

npx ampx sandbox secret set PROD_ACCOUNT_ID
# Enter: 9c929f25-a91f-4db7-8943-5aa93498b8e9 (your Plexus Account UUID)

npx ampx sandbox secret set SEED_USER_PASSWORD
# Enter: (secure password for sandbox seed user, min 8 characters)

# Optional configuration (defaults work for most cases)
npx ampx sandbox secret set DAYS_RECENT
# Enter: 30 (default: 30 days of recent data)

# Only needed if you want to copy S3 files (disabled by default)
npx ampx sandbox secret set INCLUDE_S3_SYNC
# Enter: true (default: false - S3 copying is OFF)
```

## Usage

### Running the Seed Script

```bash
# Step 1: Start your sandbox (in one terminal)
npx ampx sandbox

# Step 2: Generate IAM policy (in another terminal, after sandbox starts)
npx ampx sandbox seed generate-policy

# Step 3: Run the seed script
npx ampx sandbox seed
```

**Note:** The sandbox must be running before you can generate the policy or run the seed script.

The `generate-policy` command creates permissions for:
- Reading from production DynamoDB tables (via AppSync GraphQL API)
- Writing to sandbox DynamoDB tables
- Reading/writing S3 buckets (if S3 sync is enabled)

The seed script will:
1. Create/sign in a seed user (`sandbox-seed@plexus.internal`)
2. Connect to production and sandbox environments
3. Execute 5 phases of data copying:
   - Phase 1: Foundation (Account, User)
   - Phase 2: Core Structure (Scorecard hierarchy)
   - Phase 3: Reference Data (DataSource, Procedure, etc.)
   - Phase 4: Operational & Large-Scale (Task, Item, ScoreResult, etc.)
   - Phase 5: Derived & Linked Data (Report, ChatMessage, etc.)
4. Optionally sync S3 files (if `INCLUDE_S3_SYNC=true`)

### Performance Estimates

**Small Sandbox (~1K records):**
- DynamoDB seeding: ~5 minutes
- With S3 (optional): +2 minutes

**Medium Sandbox (~10K records):**
- DynamoDB seeding: ~12 minutes
- With S3 (optional): +5 minutes

**Large Sandbox (~50K records):**
- DynamoDB seeding: ~47 minutes
- With S3 (optional): +10 minutes

### Cost Estimates

**Per sandbox seed (DynamoDB only):**
- AppSync API calls: ~$0.20
- DynamoDB writes: ~$0.03
- **Total: ~$0.23**

**With S3 sync enabled:**
- S3 read/write: ~$0.0004
- **Total: ~$0.23**

## Configuration

### Table Strategies

Defined in [config.ts](./config.ts):

- **`full`**: Copy all records (for small reference tables)
- **`recent`**: Copy records from last N days (configurable via `DAYS_RECENT`)
- **`sampled`**: Copy recent N records + random sample of N older records

### Dependency Ordering

The seed script respects foreign key dependencies through 5-phase execution:

```
Phase 1: Account, User
Phase 2: Scorecard → Section → Score → Version
Phase 3: DataSource, Procedure, ReportConfiguration
Phase 4: Item, ScoreResult, ScoringJob, Task, Evaluation
Phase 5: Report, ChatMessage, Identifier, etc.
```

### S3 Buckets

When `INCLUDE_S3_SYNC=true`, the following buckets are synced:
- `reportBlockDetails`
- `dataSources`
- `scoreResultAttachments`
- `taskAttachments`
- `rubricMemory`

**Limits:**
- Only files modified in last N days (matches `DAYS_RECENT`)
- Max 5GB per bucket
- Files >100MB are skipped

## Troubleshooting

### "UsernameExistsError"

This is normal on subsequent runs. The seed script will sign in with the existing user.

### "Secret not found"

Run `npx ampx sandbox secret list` to verify secrets are set. If missing, run the setup commands above.

### "Failed to copy item"

Individual item failures are logged but don't stop the seeding process. Common causes:
- Foreign key references missing (table seeded in wrong order - shouldn't happen with proper phases)
- Item already exists (re-running seed is idempotent)
- Invalid data (rare, will be logged)

### S3 Files Not Copying

Ensure:
1. `INCLUDE_S3_SYNC=true` is set
2. Production API credentials have S3 read permissions
3. Sandbox has S3 write permissions

### Slow Performance

Expected for large data sets. Tips:
- Reduce `DAYS_RECENT` (e.g., set to 7 for last week only)
- Disable S3 sync if not needed
- Run during off-peak hours

### API Throttling

AppSync has a 1000 req/sec limit. The seed script runs at ~10-20 req/sec, well below the limit. If throttled, the script will log errors but continue.

## Verification Checklist

After seeding completes, verify:

- [ ] Sandbox started successfully (`npx ampx sandbox`)
- [ ] Seed script completed without fatal errors
- [ ] Account records exist
- [ ] Scorecard hierarchy is complete (Scorecard → Section → Score → Version)
- [ ] Items exist with recent data (check `createdAt` dates)
- [ ] ScoreResults are linked to Items
- [ ] Dashboard loads against sandbox
- [ ] Can navigate scorecards, items, evaluations in UI
- [ ] No console errors in browser
- [ ] S3 files copied (if `INCLUDE_S3_SYNC=true`)

## Re-running the Seed Script

The seed script is **idempotent** - safe to run multiple times:
- Existing records are skipped (GraphQL `create` fails gracefully)
- New records since last seed are added
- No duplicates are created

## Security Notes

- **Production credentials**: Stored in AWS Parameter Store (not in code)
- **Read-only access**: Seed script only reads from production
- **No PII filtering**: Currently copies data as-is. Consider adding PII scrubbing for sensitive environments (future enhancement)
- **Sandbox isolation**: Each developer's sandbox is isolated

## Architecture

```
amplify/seed/
├── seed.ts                    # Main entry point
├── config.ts                  # Table configurations
├── types.ts                   # TypeScript interfaces
├── phases/                    # 5-phase execution
│   ├── phase1-foundation.ts
│   ├── phase2-structure.ts
│   ├── phase3-reference.ts
│   ├── phase4-operational.ts
│   └── phase5-derived.ts
├── strategies/                # Data copying strategies
│   ├── full-copy.ts
│   ├── recent-copy.ts
│   └── sampled-copy.ts
└── utils/                     # Utilities
    ├── logger.ts
    ├── production-client.ts
    ├── sandbox-client.ts
    └── storage-sync.ts
```

## Future Enhancements

- **Differential seeding**: Only copy new/updated records since last seed
- **Data anonymization**: PII scrubbing for sensitive fields
- **Seed profiles**: Predefined configurations (minimal, standard, full)
- **Clear sandbox**: `--clear-first` flag to wipe before seeding
- **Dry run**: Preview what will be seeded without executing
- **Parallel seeding**: Concurrent table operations for 5-10x speedup

## Support

For issues or questions:
- Check [Troubleshooting](#troubleshooting) section above
- Review seed script logs for specific errors
- Check Amplify Gen2 documentation: https://docs.amplify.aws/react/deploy-and-host/sandbox-environments/seed/
