#!/bin/bash
set -e

# Load environment variables without overriding explicitly supplied values.
if [ -f .env ]; then
    while IFS='=' read -r key value; do
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
        key="${key%%[[:space:]]*}"
        if [ -z "${!key+x}" ]; then
            export "$key=${value%$'\r'}"
        fi
    done < .env
fi

: "${AWS_REGION:=${CDK_DEFAULT_REGION:-us-west-2}}"
: "${AMPLIFY_STACK_PATTERN:?Set AMPLIFY_STACK_PATTERN to the target Amplify root stack pattern}"

echo "Discovering Amplify tables..."

# Run discovery script and capture output as JSON
python3 << 'PYTHON_SCRIPT' > /tmp/tables.json
import json
import os
import sys
sys.path.insert(0, '.')
from stacks.shared.amplify_discovery import discover_tables_for_metrics_aggregation

tables = discover_tables_for_metrics_aggregation(
    region=os.environ.get('CDK_DEFAULT_REGION') or os.environ.get('AWS_REGION', 'us-west-2'),
    stack_pattern=os.environ.get('AMPLIFY_STACK_PATTERN')
)

# Convert to format suitable for CDK context
context = {}
for table_key, table_info in tables.items():
    context[f"table_{table_key}_name"] = table_info['table_name']
    context[f"table_{table_key}_arn"] = table_info['table_arn']
    context[f"table_{table_key}_stream_arn"] = table_info['stream_arn']

print(json.dumps(context))
PYTHON_SCRIPT

# Build context arguments for CDK
CONTEXT_ARGS=""
while IFS= read -r line; do
    key=$(echo "$line" | cut -d'"' -f2)
    value=$(echo "$line" | cut -d'"' -f4)
    if [ -n "$key" ] && [ -n "$value" ]; then
        CONTEXT_ARGS="$CONTEXT_ARGS -c $key=$value"
    fi
done < <(cat /tmp/tables.json | jq -r 'to_entries[] | "\"\(.key)\" \"\(.value)\""')

echo "Deploying MetricsAggregationStack..."
npx cdk deploy \
    --app "python3 deploy_metrics_only.py" \
    plexus-metrics-aggregation-production \
    $CONTEXT_ARGS \
    --require-approval never

rm /tmp/tables.json
