#!/bin/bash
set -euo pipefail

cd /home/ec2-user/projects/Plexus

echo "Installing Poetry (if needed) and syncing runtime dependencies from poetry.lock..."
/home/ec2-user/miniconda3/bin/conda run -n py311 bash -lc '
if ! command -v poetry >/dev/null 2>&1; then
    pip install "poetry>=1.8,<2.0"
fi

poetry config virtualenvs.create false
poetry install --only main --sync --no-interaction --no-ansi
'

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
