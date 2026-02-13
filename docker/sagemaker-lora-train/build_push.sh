#!/usr/bin/env bash
set -euo pipefail

REGION=${AWS_REGION:-${AWS_DEFAULT_REGION:-us-west-2}}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPO_NAME=${REPO_NAME:-plexus-lora-train}
IMAGE_TAG=${IMAGE_TAG:-latest}

ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:$IMAGE_TAG"

aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO_NAME" --region "$REGION" >/dev/null

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# Login to AWS Deep Learning Containers (base image registry)
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "763104351884.dkr.ecr.$REGION.amazonaws.com"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

docker build -t "$REPO_NAME:$IMAGE_TAG" "$SCRIPT_DIR"
docker tag "$REPO_NAME:$IMAGE_TAG" "$ECR_URI"
docker push "$ECR_URI"

echo "Pushed: $ECR_URI"
