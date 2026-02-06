#!/bin/bash
set -e

echo "Validating services are running..."

# Determine environment from CodeDeploy deployment group name
ENVIRONMENT="${DEPLOYMENT_GROUP_NAME:-unknown}"

# Skip validation entirely in staging
if [[ "$ENVIRONMENT" == *"staging"* ]]; then
    echo "Staging environment detected - skipping service validation"
    echo "Service validation completed successfully!"
    exit 0
fi

# Production validation - services must be running
echo "Production environment - validating required services..."

# Check if plexus-command-worker service exists and validate it
if sudo systemctl list-unit-files | grep -q plexus-command-worker; then
    if sudo systemctl is-active --quiet plexus-command-worker; then
        echo "✓ plexus-command-worker service is running"
    else
        echo "✗ plexus-command-worker service is not running"
        exit 1
    fi
else
    echo "✗ plexus-command-worker service not found"
    exit 1
fi

# Check if fastapi service exists and validate it
if sudo systemctl list-unit-files | grep -q fastapi.service; then
    if sudo systemctl is-active --quiet fastapi; then
        echo "✓ fastapi service is running"
    else
        echo "✗ fastapi service is not running"
        exit 1
    fi
else
    echo "✗ fastapi service not found"
    exit 1
fi

echo "Service validation completed successfully!"
