# Configuration Setup Scripts

These scripts populate AWS Secrets Manager with configuration values from your root `.env` file.

## Overview

The scripts automatically read configuration from `Plexus/.env` and create a single JSON secret in Secrets Manager for each environment. This provides a unified, secure location for all configuration values (both sensitive and non-sensitive).

## Usage

### For Production Environment

Run this to create/update the production secret using current `.env` values:

```bash
cd infrastructure/scripts
./create-secrets-production.sh
```

This creates a secret named `plexus/production/config` with the following keys:
- `account-key`
- `api-key`
- `api-url`
- `postgres-uri`
- `openai-api-key`
- `score-result-attachments-bucket`
- `report-block-details-bucket`

### For Staging Environment

Run this to create/update the staging secret:

```bash
cd infrastructure/scripts
./create-secrets-staging.sh
```

This creates a secret named `plexus/staging/config` with the same structure.

## What Gets Created

### Secrets Manager Structure

```
AWS Secrets Manager
├── plexus/staging/config (JSON secret)
│   └── {
│         "account-key": "...",
│         "api-key": "...",
│         "api-url": "...",
│         "postgres-uri": "...",
│         "openai-api-key": "...",
│         "score-result-attachments-bucket": "...",
│         "report-block-details-bucket": "..."
│       }
└── plexus/production/config (JSON secret)
    └── {
          "account-key": "...",
          "api-key": "...",
          "api-url": "...",
          "postgres-uri": "...",
          "openai-api-key": "...",
          "score-result-attachments-bucket": "...",
          "report-block-details-bucket": "..."
        }
```

## Variable Mapping

| Secret Key | .env Variable | Notes |
|-----------|---------------|-------|
| `account-key` | `PLEXUS_ACCOUNT_KEY` | Account identifier |
| `api-url` | `PLEXUS_API_URL` | GraphQL endpoint |
| `api-key` | `PLEXUS_API_KEY` | API authentication key |
| `postgres-uri` | `PLEXUS_LANGGRAPH_CHECKPOINTER_POSTGRES_URI` | Database connection |
| `openai-api-key` | `OPENAI_API_KEY` | OpenAI API key |
| `score-result-attachments-bucket` | `AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME` | S3 bucket |
| `report-block-details-bucket` | `AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME` | S3 bucket |

## Verification

After running the scripts, verify secrets were created:

```bash
# View staging secret metadata (no values)
aws secretsmanager describe-secret --secret-id plexus/staging/config

# View staging secret with values
aws secretsmanager get-secret-value --secret-id plexus/staging/config \
  --query SecretString --output text | jq

# View production secret with values
aws secretsmanager get-secret-value --secret-id plexus/production/config \
  --query SecretString --output text | jq
```

## Updating Configuration

### Update All Values

To update all configuration values from `.env`:

```bash
# Update values in .env file first

# Then re-run the script (will update the secret)
./create-secrets-production.sh
```

### Update Single Value

To update a single key in the secret:

```bash
# Get current secret value
CURRENT=$(aws secretsmanager get-secret-value \
  --secret-id plexus/production/config \
  --query SecretString --output text)

# Update the key using jq
UPDATED=$(echo "$CURRENT" | jq '.["api-key"] = "new-value"')

# Update the secret
aws secretsmanager update-secret \
  --secret-id plexus/production/config \
  --secret-string "$UPDATED"
```

## Security Notes

1. **Encryption**: All values in Secrets Manager are encrypted at rest using AWS KMS
2. **IAM Permissions**: Lambda functions are granted read-only access to the secret
3. **Version History**: Secrets Manager keeps version history of all changes
4. **Cost**: Secrets Manager charges per secret ($0.40/month per secret + $0.05 per 10,000 API calls)

## Troubleshooting

### Error: .env file not found

```
❌ Error: .env file not found at ...
```

**Solution**: Make sure you're running the script from `infrastructure/scripts/` directory, or the `.env` file exists in the project root.

### Error: Variable is empty

If a key gets an empty value in the secret, check that the variable is defined in `.env`:

```bash
# Check what's loaded
source ../../.env
echo $PLEXUS_API_KEY
```

### Error: Access Denied

```
An error occurred (AccessDeniedException) when calling the CreateSecret operation
```

**Solution**: Add Secrets Manager permissions to your IAM user:
```json
{
  "Effect": "Allow",
  "Action": [
    "secretsmanager:CreateSecret",
    "secretsmanager:UpdateSecret",
    "secretsmanager:DescribeSecret",
    "secretsmanager:GetSecretValue"
  ],
  "Resource": "arn:aws:secretsmanager:*:*:secret:plexus/*"
}
```