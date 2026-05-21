#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DASHBOARD_DIR/.." && pwd)"

REGION="${AWS_REGION:-${AWS_REGION_NAME:-us-west-2}}"
PROFILE="${AWS_PROFILE:-}"
REPOSITORY_NAME="${CONSOLE_WORKER_ECR_REPOSITORY:-plexus-console-run-worker}"
TAG="${CONSOLE_WORKER_IMAGE_TAG:-sandbox-$(whoami)-latest}"
CONFIG_SECRET_NAME="${PLEXUS_CONFIG_SECRET_NAME:-}"
SKIP_BUILD="false"

usage() {
  cat <<EOF
Build/push ConsoleRunWorker image and start Amplify sandbox with worker enabled.

Usage:
  $(basename "$0") [--skip-build] [--region <region>] [--profile <profile>] [--repository <name>] [--tag <tag>] [--config-secret-name <name>] [-- <ampx sandbox args>]

Examples:
  $(basename "$0")
  $(basename "$0") --tag sandbox-\$(whoami)-dev -- --identifier my-sandbox
  $(basename "$0") --skip-build --tag sandbox-\$(whoami)-latest
  $(basename "$0") --config-secret-name plexus/production/config
EOF
}

AMPX_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-build)
      SKIP_BUILD="true"
      shift
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --repository)
      REPOSITORY_NAME="$2"
      shift 2
      ;;
    --tag)
      TAG="$2"
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

AWS_ARGS=(--region "$REGION")
if [[ -n "$PROFILE" ]]; then
  AWS_ARGS+=(--profile "$PROFILE")
fi

ACCOUNT_ID="$(aws "${AWS_ARGS[@]}" sts get-caller-identity --query Account --output text)"
if [[ -z "$ACCOUNT_ID" || "$ACCOUNT_ID" == "None" ]]; then
  echo "Failed to resolve AWS account ID" >&2
  exit 1
fi

IMAGE_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPOSITORY_NAME}:${TAG}"

if [[ "$SKIP_BUILD" != "true" ]]; then
  "$SCRIPT_DIR/build-and-push-console-worker-image.sh" \
    --region "$REGION" \
    ${PROFILE:+--profile "$PROFILE"} \
    --repository "$REPOSITORY_NAME" \
    --tag "$TAG"
else
  echo "Skipping image build/push. Using image: $IMAGE_URI"
fi

echo ""
echo "Starting sandbox with ConsoleRunWorker enabled..."
echo "CONSOLE_WORKER_IMAGE_URI=$IMAGE_URI"
echo ""

cd "$DASHBOARD_DIR"

export AMPLIFY_ENABLE_SANDBOX_CONSOLE_WORKER=true
export CONSOLE_WORKER_IMAGE_URI="$IMAGE_URI"
export AWS_REGION="$REGION"
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
