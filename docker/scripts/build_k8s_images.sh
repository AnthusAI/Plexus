#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
}

require_command docker

REGISTRY="${REGISTRY:-}"
IMAGE_TAG="${IMAGE_TAG:-}"
PLATFORMS="${PLATFORMS:-linux/amd64}"
PUSH="${PUSH:-true}"
BUILDER_NAME="${BUILDER_NAME:-plexus-multiarch}"
WORKER_IMAGE_REPOSITORY="${WORKER_IMAGE_REPOSITORY:-plexus-worker}"
PROXY_IMAGE_REPOSITORY="${PROXY_IMAGE_REPOSITORY:-plexus-graphql-proxy}"

if [ -z "$IMAGE_TAG" ]; then
  echo "IMAGE_TAG is required (example: IMAGE_TAG=1.52.0)." >&2
  exit 1
fi

if [ "$PUSH" = "true" ] && [ -z "$REGISTRY" ]; then
  echo "REGISTRY is required when PUSH=true; bare image names would push to docker.io/library and be denied." >&2
  echo "Set REGISTRY=your-registry, or use PUSH=false to load a single-platform image locally." >&2
  exit 1
fi

normalize_image_name() {
  local repository="$1"
  if [ -n "$REGISTRY" ]; then
    echo "${REGISTRY%/}/$repository"
  else
    echo "$repository"
  fi
}

WORKER_IMAGE="$(normalize_image_name "$WORKER_IMAGE_REPOSITORY"):$IMAGE_TAG"
PROXY_IMAGE="$(normalize_image_name "$PROXY_IMAGE_REPOSITORY"):$IMAGE_TAG"

if [ "$PUSH" != "true" ] && [ "$PUSH" != "false" ]; then
  echo "PUSH must be true or false (got: $PUSH)." >&2
  exit 1
fi

if [ "$PUSH" = "false" ] && [[ "$PLATFORMS" == *,* ]]; then
  echo "PUSH=false with multi-platform builds is not supported because docker --load can import only one platform." >&2
  exit 1
fi

# Use --builder per build instead of "docker buildx use" so the machine-global
# default builder is left untouched.
if ! docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
  docker buildx create --name "$BUILDER_NAME" --driver docker-container >/dev/null
fi

docker buildx inspect --builder "$BUILDER_NAME" --bootstrap >/dev/null

BUILD_OUTPUT_FLAG="--push"
if [ "$PUSH" = "false" ]; then
  BUILD_OUTPUT_FLAG="--load"
fi

echo "Building Plexus worker image: $WORKER_IMAGE"
docker buildx build \
  --builder "$BUILDER_NAME" \
  --platform "$PLATFORMS" \
  -f "$PROJECT_ROOT/docker/Dockerfile" \
  -t "$WORKER_IMAGE" \
  "$BUILD_OUTPUT_FLAG" \
  "$PROJECT_ROOT"

echo "Building GraphQL proxy image: $PROXY_IMAGE"
docker buildx build \
  --builder "$BUILDER_NAME" \
  --platform "$PLATFORMS" \
  -f "$PROJECT_ROOT/services/private-graphql-proxy/Dockerfile" \
  -t "$PROXY_IMAGE" \
  "$BUILD_OUTPUT_FLAG" \
  "$PROJECT_ROOT"

cat <<EOF

Image build complete.
Worker image: $WORKER_IMAGE
Proxy image:  $PROXY_IMAGE
Platforms:    $PLATFORMS
Push:         $PUSH

EOF
