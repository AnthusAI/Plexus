#!/bin/bash
set -e

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

echo "Discovering Amplify tables..."

# Run discovery script and capture output as JSON
python3 << 'PYTHON_SCRIPT' > /tmp/tables.json
import json
import sys
sys.path.insert(0, '.')
from stacks.shared.amplify_discovery import discover_tables_for_metrics_aggregation

tables = discover_tables_for_metrics_aggregation(
    region='us-west-2',
    stack_pattern='amplify-d1cegb1ft4iove-main-branch'
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

