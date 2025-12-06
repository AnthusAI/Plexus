#!/bin/bash
cd /home/ec2-user/projects/Plexus

echo "Installing package in editable mode..."
conda activate py311
pip install .

# Only restart services if they exist
if sudo systemctl list-unit-files | grep -q plexus-command-worker; then
    echo "Restarting Plexus Command Worker..."
    sudo systemctl restart plexus-command-worker
else
    echo "Plexus Command Worker service not found (staging environment)"
fi

if sudo systemctl list-unit-files | grep -q fastapi.service; then
    echo "Restarting FastAPI service..."
    sudo systemctl restart fastapi
else
    echo "FastAPI service not found (staging environment)"
fi

echo "Deployment completed successfully!" 