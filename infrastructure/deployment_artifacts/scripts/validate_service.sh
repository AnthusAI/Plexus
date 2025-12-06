#!/bin/bash
set -e

echo "Validating services are running..."

# Check if plexus-command-worker service is active
if sudo systemctl is-active --quiet plexus-command-worker; then
    echo "✓ plexus-command-worker service is running"
else
    echo "✗ plexus-command-worker service is not running"
    exit 1
fi

# Check if fastapi service is active
if sudo systemctl is-active --quiet fastapi; then
    echo "✓ fastapi service is running"
else
    echo "✗ fastapi service is not running"
    exit 1
fi

echo "All services validated successfully!"
