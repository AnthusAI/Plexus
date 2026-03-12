#!/usr/bin/env python3
"""
Discover Amplify DynamoDB tables and save their ARNs to .env file.
Run this before deploying the MetricsAggregationStack.
"""

import os
import sys
sys.path.insert(0, '.')

from stacks.shared.amplify_discovery import discover_tables_for_metrics_aggregation

# Load existing .env
env_path = '.env'
env_lines = []
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        env_lines = f.readlines()

# Discover tables
print("Discovering Amplify tables...")
tables = discover_tables_for_metrics_aggregation(
    region='us-west-2',
    stack_pattern='amplify-d1cegb1ft4iove-main-branch'
)

if not tables:
    print("ERROR: Could not discover tables!")
    sys.exit(1)

print(f"Discovered {len(tables)} tables")

# Remove old table entries from .env
filtered_lines = [line for line in env_lines if not line.startswith('TABLE_')]

# Add new table entries
filtered_lines.append('\n# Discovered table ARNs (auto-generated)\n')
for table_key, table_info in tables.items():
    filtered_lines.append(f"TABLE_{table_key.upper()}_NAME={table_info['table_name']}\n")
    filtered_lines.append(f"TABLE_{table_key.upper()}_ARN={table_info['table_arn']}\n")
    filtered_lines.append(f"TABLE_{table_key.upper()}_STREAM_ARN={table_info['stream_arn']}\n")

# Write back to .env
with open(env_path, 'w') as f:
    f.writelines(filtered_lines)

print(f"\nSaved table ARNs to {env_path}")
print("You can now deploy with: npx cdk deploy plexus-metrics-aggregation-production")

