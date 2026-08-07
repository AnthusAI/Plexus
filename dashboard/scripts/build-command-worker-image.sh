#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
handoff_file="dashboard/.command-worker-image.env"
rm -f "$handoff_file"

environment="${AWS_BRANCH:-${AMPLIFY_ENV:-}}"
environment="$(printf '%s' "$environment" | tr '[:upper:]' '[:lower:]')"
case "$environment" in
  main|production) environment=production ;;
  staging) environment=staging ;;
  *) exit 0 ;;
esac

prefix="${PLEXUS_SERVICE_PREFIX:-plexus}"
parameter="/${prefix}/${environment}/command-service/worker-image-repository-uri"
repository_uri="$(aws ssm get-parameter --name "$parameter" --query 'Parameter.Value' --output text)"
if [[ ! "$repository_uri" =~ ^[^[:space:]@]+/[^[:space:]@]+$ ]]; then
  echo "Invalid command-worker repository response." >&2
  exit 1
fi
# The task definition changes only when the worker runtime inputs change. A
# general dashboard commit must not replace an ECS task that is protecting an
# active command. The Dockerfile copies the entire plexus package, so every
# copied file participates in the content address.
worker_content_hash="$({
  printf '%s\n' plexus/command_worker/Dockerfile pyproject.toml poetry.lock
  find plexus -type f -print
} | LC_ALL=C sort | while IFS= read -r file; do shasum -a 256 "$file"; done | shasum -a 256 | awk '{print $1}')"
tag="worker-${worker_content_hash}"
aws ecr get-login-password | docker login --username AWS --password-stdin "${repository_uri%%/*}"
if ! aws ecr describe-images --repository-name "${repository_uri##*/}" --image-ids imageTag="$tag" >/dev/null 2>&1; then
  docker buildx build --platform linux/amd64 --provenance=false --push \
    -f plexus/command_worker/Dockerfile -t "${repository_uri}:${tag}" .
fi
digest="$(aws ecr describe-images --repository-name "${repository_uri##*/}" --image-ids imageTag="$tag" --query 'imageDetails[0].imageDigest' --output text)"
if [[ ! "$digest" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo "Invalid command-worker image digest response." >&2
  exit 1
fi
candidate_image_uri="${repository_uri}@${digest}"

# A deployment supplies the currently running digest and Task table name. If
# the worker image would change while a command is active, retain the current
# digest and defer the replacement. This avoids terminating protected work and
# avoids waiting past CloudFormation's three-hour operation timeout.
selected_image_uri="$candidate_image_uri"
replacement_deferred=0
parameter_error="$(mktemp)"
trap 'rm -f "$parameter_error"' EXIT
read_optional_parameter() {
  local parameter_name="$1"
  local value
  if value="$(aws ssm get-parameter --name "$parameter_name" --query 'Parameter.Value' --output text 2>"$parameter_error")"; then
    printf '%s' "$value"
    return 0
  fi
  if grep -q 'ParameterNotFound' "$parameter_error"; then
    return 1
  fi
  cat "$parameter_error" >&2
  return 2
}

current_image_uri=""
current_image_exists=0
if current_image_uri="$(read_optional_parameter "/${prefix}/${environment}/command-service/current-worker-image-uri")"; then
  current_image_exists=1
else
  status=$?
  if [ "$status" -ne 1 ]; then
    exit 1
  fi
fi
if [ "$current_image_exists" -eq 1 ]; then
  if [[ ! "$current_image_uri" =~ @sha256:[a-f0-9]{64}$ ]] || [ "${current_image_uri%@*}" != "$repository_uri" ]; then
    echo "Failing closed: invalid current worker image response." >&2
    exit 1
  fi
else
  # A genuinely new application has neither deployment-state parameter. If
  # the Task table is already published, losing the current digest must not be
  # misclassified as bootstrap and advance an un-gated candidate.
  if task_table_name="$(read_optional_parameter "/${prefix}/${environment}/command-service/task-table-name")"; then
    echo "Failing closed: current worker image state is missing for an established deployment." >&2
    exit 1
  else
    status=$?
    if [ "$status" -ne 1 ]; then
      exit 1
    fi
  fi
fi

if [ "$current_image_exists" -eq 1 ] && [ "$current_image_uri" != "$candidate_image_uri" ]; then
  task_table_name=""
  if task_table_name="$(read_optional_parameter "/${prefix}/${environment}/command-service/task-table-name")"; then
    if [[ ! "$task_table_name" =~ ^[A-Za-z0-9_.-]{3,255}$ ]]; then
      echo "Failing closed: invalid Task table identity response." >&2
      exit 1
    fi
    active_command_counts="$(aws dynamodb scan \
      --table-name "$task_table_name" \
      --select COUNT \
      --consistent-read \
      --filter-expression '#lifecycle IN (:running, :cancelling)' \
      --expression-attribute-names '{"#lifecycle":"lifecycleStatus"}' \
      --expression-attribute-values '{":running":{"S":"RUNNING"},":cancelling":{"S":"CANCEL_REQUESTED"}}' \
      --query Count --output text)"
    active_command_detected=0
    while IFS= read -r page_count; do
      if [[ ! "$page_count" =~ ^[0-9]+$ ]]; then
        echo "Failing closed: invalid active command count response." >&2
        exit 1
      fi
      if [ "$page_count" != "0" ]; then
        active_command_detected=1
      fi
    done <<EOF
$active_command_counts
EOF
    if [ "$active_command_detected" -eq 1 ]; then
      echo "Deferring command-worker image replacement: active command(s) detected." >&2
      selected_image_uri="$current_image_uri"
      replacement_deferred=1
    fi
  else
    status=$?
    if [ "$status" -ne 1 ]; then
      exit 1
    fi
    echo "Deferring command-worker image replacement: Task table identity is not available." >&2
    selected_image_uri="$current_image_uri"
    replacement_deferred=1
  fi
fi
{
  printf 'export PLEXUS_COMMAND_WORKER_FOUNDATION_REPOSITORY_URI=%q\n' "$repository_uri"
  printf 'export PLEXUS_COMMAND_WORKER_IMAGE_URI=%q\n' "$selected_image_uri"
  printf 'export PLEXUS_COMMAND_WORKER_IMAGE_CONTENT_HASH=%q\n' "$worker_content_hash"
  printf 'export PLEXUS_COMMAND_WORKER_IMAGE_REPLACEMENT_DEFERRED=%q\n' "$replacement_deferred"
} > "$handoff_file"
