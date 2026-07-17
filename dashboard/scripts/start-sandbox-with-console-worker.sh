#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DASHBOARD_DIR/.." && pwd)"

REGION="${AWS_REGION:-${AWS_REGION_NAME:-us-west-2}}"
PROFILE="${AWS_PROFILE:-}"
CONFIG_SECRET_NAME="${PLEXUS_CONFIG_SECRET_NAME:-}"

usage() {
  cat <<EOF
Start Amplify sandbox with ConsoleRunWorker enabled.

Usage:
  $(basename "$0") [--region <region>] [--profile <profile>] [--config-secret-name <name>] [-- <ampx sandbox args>]

Examples:
  $(basename "$0")
  $(basename "$0") -- --identifier my-sandbox
  $(basename "$0") --config-secret-name plexus/production/config
EOF
}

AMPX_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      REGION="$2"
      shift 2
      ;;
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --config-secret-name)
      CONFIG_SECRET_NAME="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      AMPX_ARGS+=("$@")
      break
      ;;
    *)
      AMPX_ARGS+=("$1")
      shift
      ;;
  esac
done

echo ""
echo "Starting sandbox with ConsoleRunWorker enabled..."
echo "Console worker image will be built/published by CDK asset deployment."
echo ""

cd "$DASHBOARD_DIR"

# A sandbox must never inherit branch/runtime wiring from a production or
# staging deployment shell.  Let Amplify resolve its own sandbox data API.
unset AWS_BRANCH AMPLIFY_ENV PLEXUS_API_URL

export AMPLIFY_ENABLE_SANDBOX_CONSOLE_WORKER=true
export AWS_REGION="$REGION"
if [[ -z "$CONFIG_SECRET_NAME" ]]; then
  CONFIG_SECRET_NAME="plexus/staging/config"
fi
if [[ "$CONFIG_SECRET_NAME" == "plexus/production/config" ]]; then
  echo "Refusing to start a sandbox Console worker with a production secret." >&2
  exit 1
fi
if [[ -n "$CONFIG_SECRET_NAME" ]]; then
  export PLEXUS_CONFIG_SECRET_NAME="$CONFIG_SECRET_NAME"
fi
if [[ -n "$PROFILE" ]]; then
  export AWS_PROFILE="$PROFILE"
fi

if [[ ${#AMPX_ARGS[@]} -gt 0 ]]; then
  npx ampx sandbox "${AMPX_ARGS[@]}"
else
  npx ampx sandbox
fi
