#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ec2-user/projects/Plexus}"
CONDA_BIN="${CONDA_BIN:-/home/ec2-user/miniconda3/bin/conda}"
RUNTIME_ENV="${RUNTIME_ENV:-py311}"
DEV_ENV="${DEV_ENV:-py311-dev}"

if [ ! -x "$CONDA_BIN" ]; then
  echo "Conda not found at: $CONDA_BIN" >&2
  exit 1
fi

if [ ! -d "$APP_DIR" ]; then
  echo "Plexus app directory not found: $APP_DIR" >&2
  exit 1
fi

echo "Creating/updating developer environment: $DEV_ENV"
"$CONDA_BIN" create -n "$DEV_ENV" --clone "$RUNTIME_ENV" -y

echo "Installing Poetry and dev dependencies in $DEV_ENV"
"$CONDA_BIN" run -n "$DEV_ENV" bash -lc "
set -euo pipefail
cd '$APP_DIR'
python -m pip install --upgrade 'pip<25' 'poetry>=1.8,<2.0'
python -m poetry config virtualenvs.create false --local || true
python -m poetry install --with dev --no-interaction --no-ansi
"

echo
echo "Developer environment is ready: $DEV_ENV"
echo "Example:"
echo "  $CONDA_BIN run -n $DEV_ENV pytest"
