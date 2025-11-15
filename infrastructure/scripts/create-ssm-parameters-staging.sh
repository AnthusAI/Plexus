#!/bin/bash
# Script to create SSM parameters for staging environment
# Run this script to populate SSM Parameter Store with configuration values from .env file

set -e

ENVIRONMENT="staging"
BASE_PATH="/plexus/$ENVIRONMENT/config"

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
echo "Creating SSM parameters for $ENVIRONMENT environment..."
echo ""

# NOTE: For staging, we're using the same values as production from .env
# If you have staging-specific values, uncomment and use those instead in .env

# Regular parameters (String type)
echo "Creating regular parameters..."

aws ssm put-parameter \
  --name "$BASE_PATH/account-key" \
  --value "${PLEXUS_ACCOUNT_KEY}" \
  --type String \
  --description "Plexus account key for staging" \
  --overwrite

aws ssm put-parameter \
  --name "$BASE_PATH/api-url" \
  --value "${PLEXUS_API_URL}" \
  --type String \
  --description "Plexus API GraphQL endpoint for staging" \
  --overwrite

aws ssm put-parameter \
  --name "$BASE_PATH/score-result-attachments-bucket" \
  --value "${AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME}" \
  --type String \
  --description "S3 bucket for score result attachments (staging)" \
  --overwrite

aws ssm put-parameter \
  --name "$BASE_PATH/report-block-details-bucket" \
  --value "${AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME}" \
  --type String \
  --description "S3 bucket for report block details (staging)" \
  --overwrite

# Secret parameters (SecureString type)
echo ""
echo "Creating secret parameters (SecureString)..."

aws ssm put-parameter \
  --name "$BASE_PATH/api-key" \
  --value "${PLEXUS_API_KEY}" \
  --type SecureString \
  --description "Plexus API key for staging" \
  --overwrite

aws ssm put-parameter \
  --name "$BASE_PATH/postgres-uri" \
  --value "${PLEXUS_LANGGRAPH_CHECKPOINTER_POSTGRES_URI}" \
  --type SecureString \
  --description "PostgreSQL connection URI for LangGraph checkpointer (staging)" \
  --overwrite

aws ssm put-parameter \
  --name "$BASE_PATH/openai-api-key" \
  --value "${OPENAI_API_KEY}" \
  --type SecureString \
  --description "OpenAI API key for staging" \
  --overwrite

echo ""
echo "✅ SSM parameters created successfully for $ENVIRONMENT"
echo ""
echo "📋 Created parameters:"
echo "  $BASE_PATH/account-key (String)"
echo "  $BASE_PATH/api-url (String)"
echo "  $BASE_PATH/score-result-attachments-bucket (String)"
echo "  $BASE_PATH/report-block-details-bucket (String)"
echo "  $BASE_PATH/api-key (SecureString)"
echo "  $BASE_PATH/postgres-uri (SecureString)"
echo "  $BASE_PATH/openai-api-key (SecureString)"
echo ""
echo "🔍 View parameters:"
echo "  aws ssm get-parameters-by-path --path $BASE_PATH --with-decryption"
