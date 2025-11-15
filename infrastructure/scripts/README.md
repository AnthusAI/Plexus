# SSM Parameter Setup Scripts

These scripts populate AWS Systems Manager Parameter Store with configuration values from your root `.env` file.

## Overview

The scripts automatically read configuration from `Plexus/.env` and create SSM parameters for each environment.

## Usage

### For Production Environment

Run this to create production SSM parameters using current `.env` values:

```bash
cd infrastructure/scripts
./create-ssm-parameters-production.sh
```

This will create:
- `/plexus/production/config/account-key`
- `/plexus/production/config/api-url`
- `/plexus/production/config/api-key` (SecureString)
- `/plexus/production/config/postgres-uri` (SecureString)
- `/plexus/production/config/openai-api-key` (SecureString)
- `/plexus/production/config/score-result-attachments-bucket`
- `/plexus/production/config/report-block-details-bucket`

### For Staging Environment

ToDo: Add staging config

## What Gets Created

### SSM Parameter Structure

```
/plexus/
├── staging/
│   └── config/
│       ├── account-key (String)
│       ├── api-url (String)
│       ├── api-key (SecureString) 🔒
│       ├── postgres-uri (SecureString) 🔒
│       ├── openai-api-key (SecureString) 🔒
│       ├── score-result-attachments-bucket (String)
│       └── report-block-details-bucket (String)
└── production/
    └── config/
        ├── account-key (String)
        ├── api-url (String)
        ├── api-key (SecureString) 🔒
        ├── postgres-uri (SecureString) 🔒
        ├── openai-api-key (SecureString) 🔒
        ├── score-result-attachments-bucket (String)
        └── report-block-details-bucket (String)
```

## Variable Mapping

| SSM Parameter | .env Variable | Notes |
|---------------|---------------|-------|
| `account-key` | `PLEXUS_ACCOUNT_KEY` | Account identifier |
| `api-url` | `PLEXUS_API_URL` | GraphQL endpoint |
| `api-key` | `PLEXUS_API_KEY` | API authentication key |
| `postgres-uri` | `PLEXUS_LANGGRAPH_CHECKPOINTER_POSTGRES_URI` | Database connection |
| `openai-api-key` | `OPENAI_API_KEY` | OpenAI API key |
| `score-result-attachments-bucket` | `AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME` | S3 bucket |
| `report-block-details-bucket` | `AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME` | S3 bucket |

## Verification

After running the scripts, verify parameters were created:

```bash
# List all staging parameters
aws ssm get-parameters-by-path \
  --path "/plexus/staging/config" \
  --with-decryption \
  --output table

# List all production parameters
aws ssm get-parameters-by-path \
  --path "/plexus/production/config" \
  --with-decryption \
  --output table
```

## Updating Parameters

To update a single parameter:

```bash
# Update in .env file first

# Then re-run the script (uses --overwrite flag)
./create-ssm-parameters-staging.sh
```

Or update directly:

```bash
aws ssm put-parameter \
  --name "/plexus/staging/config/api-key" \
  --value "new-api-key-value" \
  --type SecureString \
  --overwrite
```

## Security Notes

1. **SecureString Parameters**: API keys, database URIs, and OpenAI keys are stored as SecureString (encrypted with AWS KMS)
2. **IAM Permissions**: You need `ssm:PutParameter` permission to run these scripts
3. **Parameter History**: SSM keeps version history of all parameter changes

## Troubleshooting

### Error: .env file not found

```
❌ Error: .env file not found at ...
```

**Solution**: Make sure you're running the script from `infrastructure/scripts/` directory, or the `.env` file exists in the project root.

### Error: Variable is empty

If a parameter gets an empty value, check that the variable is defined in `.env`:

```bash
# Check what's loaded
source ../../.env
echo $PLEXUS_API_KEY
```

### Error: Access Denied

```
An error occurred (AccessDeniedException) when calling the PutParameter operation
```

**Solution**: Add SSM permissions to your IAM user:
```json
{
  "Effect": "Allow",
  "Action": ["ssm:PutParameter"],
  "Resource": "arn:aws:ssm:*:*:parameter/plexus/*"
}
```