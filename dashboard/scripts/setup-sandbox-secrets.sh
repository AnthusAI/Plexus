#!/bin/bash

# Amplify Sandbox Secrets Setup Script
# Reads from .env and sets sandbox secrets for seeding

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$DASHBOARD_DIR/.env"

echo "=================================="
echo "Amplify Sandbox Secrets Setup"
echo "=================================="
echo ""

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: .env file not found at $ENV_FILE"
    echo "Please create a .env file with the required variables."
    exit 1
fi

# Load .env
echo "📂 Loading environment variables from .env..."
export $(grep -v '^#' "$ENV_FILE" | xargs)

# Function to set secret with value or prompt
set_secret() {
    local secret_name=$1
    local env_var_name=$2
    local default_value=$3

    # Get value from environment variable
    local value="${!env_var_name}"

    # Use default if env var is empty
    if [ -z "$value" ]; then
        value="$default_value"
    fi

    if [ -z "$value" ]; then
        echo "⚠️  Skipping $secret_name (no value in .env and no default)"
        return
    fi

    echo "✓ Setting $secret_name"
    echo "$value" | npx ampx sandbox secret set "$secret_name" > /dev/null 2>&1
}

echo ""
echo "🔐 Setting seed script secrets..."
echo ""

# Seed script secrets (from .env)
set_secret "PROD_API_URL" "PLEXUS_API_URL"
set_secret "PROD_API_KEY" "PLEXUS_API_KEY"
set_secret "PROD_ACCOUNT_ID" "PLEXUS_ACCOUNT_UUID"

# Optional seed configuration (defaults)
set_secret "DAYS_RECENT" "" "30"
set_secret "INCLUDE_S3_SYNC" "" "false"

echo ""
echo "🔧 Setting TaskDispatcher secrets (dummy values for sandbox)..."
echo ""

# TaskDispatcher dummy values (not needed for seed script)
set_secret "CELERY_AWS_ACCESS_KEY_ID" "" "dummy"
set_secret "CELERY_AWS_SECRET_ACCESS_KEY" "" "dummy"
set_secret "CELERY_AWS_REGION_NAME" "" "us-west-2"
set_secret "CELERY_QUEUE_NAME" "" "dummy"
set_secret "CELERY_RESULT_BACKEND_TEMPLATE" "" "dummy"

echo ""
echo "⚙️  Setting other required secrets..."
echo ""

# Seed user password (prompt if not in .env)
if [ -z "$SANDBOX_SEED_PASSWORD" ]; then
    echo "🔑 Seed user password not found in .env"
    echo "   Add SANDBOX_SEED_PASSWORD=your-password to .env to skip this prompt next time"
    echo ""
    read -sp "Enter password for sandbox seed user (min 8 chars): " SEED_PASSWORD
    echo ""
    echo "$SEED_PASSWORD" | npx ampx sandbox secret set "SEED_USER_PASSWORD" > /dev/null 2>&1
    echo "✓ Setting SEED_USER_PASSWORD"
else
    set_secret "SEED_USER_PASSWORD" "SANDBOX_SEED_PASSWORD"
fi

echo ""
echo "=================================="
echo "✅ All secrets configured!"
echo "=================================="
echo ""
echo "💡 Note: For sandbox deployment, TaskDispatcher env vars must be set"
echo "   as environment variables, not secrets."
echo ""
echo "Run sandbox with dummy values:"
echo ""
echo "  CELERY_AWS_ACCESS_KEY_ID=dummy \\"
echo "  CELERY_AWS_SECRET_ACCESS_KEY=dummy \\"
echo "  CELERY_AWS_REGION_NAME=us-west-2 \\"
echo "  CELERY_QUEUE_NAME=dummy \\"
echo "  CELERY_RESULT_BACKEND_TEMPLATE=dummy \\"
echo "  npx ampx sandbox"
echo ""
echo "Or add these to your .env and source it before running sandbox."
echo ""
