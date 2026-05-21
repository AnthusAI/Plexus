#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DASHBOARD_DIR/.." && pwd)"

REGION="${AWS_REGION:-${AWS_REGION_NAME:-us-west-2}}"
PROFILE="${AWS_PROFILE:-}"
REPOSITORY_NAME="${CONSOLE_WORKER_ECR_REPOSITORY:-plexus-console-run-worker}"
TAG="${CONSOLE_WORKER_IMAGE_TAG:-sandbox-$(whoami)-$(date +%Y%m%d%H%M%S)}"

usage() {
  cat <<EOF
Build and push the ConsoleRunWorker Lambda image to ECR.

Usage:
  $(basename "$0") [--region <region>] [--profile <profile>] [--repository <name>] [--tag <tag>]

Environment overrides:
  AWS_REGION / AWS_REGION_NAME
  AWS_PROFILE
  CONSOLE_WORKER_ECR_REPOSITORY
  CONSOLE_WORKER_IMAGE_TAG
EOF
}

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
    --repository)
      REPOSITORY_NAME="$2"
      shift 2
      ;;
    --tag)
      TAG="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

AWS_ARGS=(--region "$REGION")
if [[ -n "$PROFILE" ]]; then
  AWS_ARGS+=(--profile "$PROFILE")
fi

echo "Resolving AWS account..."
ACCOUNT_ID="$(aws "${AWS_ARGS[@]}" sts get-caller-identity --query Account --output text)"
if [[ -z "$ACCOUNT_ID" || "$ACCOUNT_ID" == "None" ]]; then
  echo "Failed to resolve AWS account ID" >&2
  exit 1
fi

REPOSITORY_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPOSITORY_NAME}"
IMAGE_URI="${REPOSITORY_URI}:${TAG}"

echo "Ensuring ECR repository exists: ${REPOSITORY_NAME}"
if ! aws "${AWS_ARGS[@]}" ecr describe-repositories --repository-names "$REPOSITORY_NAME" >/dev/null 2>&1; then
  aws "${AWS_ARGS[@]}" ecr create-repository --repository-name "$REPOSITORY_NAME" >/dev/null
fi

echo "Logging in to ECR..."
aws "${AWS_ARGS[@]}" ecr get-login-password | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com" >/dev/null

echo "Building and pushing Lambda-compatible image: ${IMAGE_URI}"
# Lambda requires a single-platform image manifest. BuildKit attestations
# (provenance/SBOM) can produce unsupported media types, so disable them.
if docker buildx version >/dev/null 2>&1; then
  docker buildx build \
    --platform linux/amd64 \
    --provenance=false \
    --sbom=false \
    -f "$DASHBOARD_DIR/amplify/functions/consoleRunWorker/Dockerfile" \
    -t "$IMAGE_URI" \
    --push \
    "$REPO_ROOT"
else
  DOCKER_BUILDKIT=0 docker build \
    --platform linux/amd64 \
    -f "$DASHBOARD_DIR/amplify/functions/consoleRunWorker/Dockerfile" \
    -t "$IMAGE_URI" \
    "$REPO_ROOT"
  docker push "$IMAGE_URI"
fi

echo ""
echo "Console worker image pushed successfully."
echo "CONSOLE_WORKER_IMAGE_URI=$IMAGE_URI"
