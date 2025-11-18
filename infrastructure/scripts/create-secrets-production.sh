#!/bin/bash
# Script to create Secrets Manager secret for production environment
# Run this script to populate Secrets Manager with configuration values from .env file

set -e

ENVIRONMENT="production"
SECRET_NAME="plexus/$ENVIRONMENT/config"

# Load environment variables from root .env file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../../.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: .env file not found at $ENV_FILE"
    exit 1
fi

echo "📄 Loading configuration from $ENV_FILE"
set -a  # Automatically export all variables
source "$ENV_FILE"
set +a

echo ""
echo "Creating Secrets Manager secret for $ENVIRONMENT environment..."
echo ""

# Build JSON secret value from environment variables
SECRET_VALUE=$(cat <<EOF
{
  "account-key": "${PLEXUS_ACCOUNT_KEY}",
  "api-key": "${PLEXUS_API_KEY}",
  "api-url": "${PLEXUS_API_URL}",
  "postgres-uri": "${PLEXUS_LANGGRAPH_CHECKPOINTER_POSTGRES_URI}",
  "openai-api-key": "${OPENAI_API_KEY}",
  "score-result-attachments-bucket": "${AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME}",
  "report-block-details-bucket": "${AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME}"
}
EOF
)

# Try to create the secret (will fail if it already exists)
if aws secretsmanager create-secret \
    --name "$SECRET_NAME" \
    --description "Plexus configuration for $ENVIRONMENT environment" \
    --secret-string "$SECRET_VALUE" \
    2>/dev/null; then
    echo "✅ Secret created successfully: $SECRET_NAME"
else
    # If creation failed, update the existing secret
    echo "Secret already exists, updating..."
    aws secretsmanager update-secret \
        --secret-id "$SECRET_NAME" \
        --secret-string "$SECRET_VALUE"
    echo "✅ Secret updated successfully: $SECRET_NAME"
fi

echo ""
echo "📋 Secret details:"
echo "  Name: $SECRET_NAME"
echo "  Keys: account-key, api-key, api-url, postgres-uri, openai-api-key, score-result-attachments-bucket, report-block-details-bucket"
echo ""
echo "🔍 View secret (without values):"
echo "  aws secretsmanager describe-secret --secret-id $SECRET_NAME"
echo ""
echo "🔍 View secret (with values):"
echo "  aws secretsmanager get-secret-value --secret-id $SECRET_NAME --query SecretString --output text | jq"
