#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

APP_DIR="${APP_DIR:-$REPO_DIR}"
DEV_ENV="${DEV_ENV:-py311-dev}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"

if [ -z "${CONDA_BIN:-}" ]; then
  for candidate in \
    "$HOME/miniconda3/bin/conda" \
    "$HOME/anaconda3/bin/conda" \
    "/opt/conda/bin/conda"
  do
    if [ -x "$candidate" ]; then
      CONDA_BIN="$candidate"
      break
    fi
  done

  if [ -z "${CONDA_BIN:-}" ] && command -v conda >/dev/null 2>&1; then
    CONDA_BIN="$(command -v conda)"
  fi
fi

if [ -z "${CONDA_BIN:-}" ] || [ ! -x "$CONDA_BIN" ]; then
  echo "Conda binary not found. Set CONDA_BIN explicitly." >&2
  exit 1
fi

if [ ! -d "$APP_DIR" ]; then
  echo "Plexus app directory not found: $APP_DIR" >&2
  exit 1
fi

echo "Recreating fresh developer environment: $DEV_ENV (python=$PYTHON_VERSION)"
"$CONDA_BIN" env remove -n "$DEV_ENV" -y >/dev/null 2>&1 || true
"$CONDA_BIN" create -n "$DEV_ENV" "python=$PYTHON_VERSION" -y

echo "Installing Poetry and dev dependencies in $DEV_ENV"
"$CONDA_BIN" run -n "$DEV_ENV" bash -lc "
set -euo pipefail
cd '$APP_DIR'
python -m pip install --upgrade 'pip<25' 'poetry>=1.8,<2.0'
POETRY_VIRTUALENVS_CREATE=false python -m poetry install --with dev --sync --no-interaction --no-ansi
"

echo
echo "Developer environment is ready: $DEV_ENV"
echo "Example:"
echo "  $CONDA_BIN run -n $DEV_ENV pytest"
