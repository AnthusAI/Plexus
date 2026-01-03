#!/bin/bash

# Wait a bit for the service to fully start
sleep 5

# Check if the plexus-command-worker service is running
if ! systemctl is-active --quiet plexus-command-worker; then
    echo "Service plexus-command-worker is not running"
    systemctl status plexus-command-worker --no-pager
    exit 1
fi

echo "Service plexus-command-worker is running successfully"
systemctl status plexus-command-worker --no-pager
exit 0 
