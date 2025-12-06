#!/bin/bash
set -e

echo "Validating services are running..."

# Check if plexus-command-worker service exists and validate it
if sudo systemctl list-unit-files | grep -q plexus-command-worker; then
    if sudo systemctl is-active --quiet plexus-command-worker; then
        echo "✓ plexus-command-worker service is running"
    else
        echo "✗ plexus-command-worker service is not running"
        exit 1
    fi
else
    echo "○ plexus-command-worker service not found (staging environment)"
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
    echo "○ fastapi service not found (staging environment)"
fi

echo "Service validation completed successfully!"
