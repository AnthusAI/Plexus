#!/bin/bash
set -euo pipefail

APP_DIR="/home/ec2-user/projects/Plexus"
CONDA_BIN="/home/ec2-user/miniconda3/bin/conda"
CONDA_ENV="py311"

cd "$APP_DIR"

echo "Installing Poetry (if needed) and syncing runtime dependencies from poetry.lock..."
"$CONDA_BIN" run -n "$CONDA_ENV" bash -lc '
set -euo pipefail

if [ ! -f pyproject.toml ] || [ ! -f poetry.lock ]; then
    echo "Missing pyproject.toml and/or poetry.lock in deployment directory" >&2
    exit 1
fi

python -m pip install --upgrade "pip<25"
python -m pip install --upgrade "poetry>=1.8,<2.0"
python -m poetry --version

# Install into the conda environment (no nested virtualenv).
# Do not use --sync here: Poetry is installed in this same env for bootstrap,
# and --sync can remove Poetry itself mid-run.
python -m poetry config virtualenvs.create false --local || true
python -m poetry install --only main --no-interaction --no-ansi
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
