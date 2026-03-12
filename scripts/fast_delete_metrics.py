#!/usr/bin/env python3
"""
Fast batch delete of AggregatedMetrics using DynamoDB batch_write_item.
This is much faster than GraphQL mutations (25 items per API call vs 1).
"""

import boto3
import json
from pathlib import Path

# Load amplify_outputs.json to get table name
amplify_outputs_path = Path(__file__).parent.parent / "dashboard" / "amplify_outputs.json"
with open(amplify_outputs_path) as f:
    amplify_outputs = json.load(f)

# Extract table name from data.url
# Format: https://{api-id}.appsync-api.{region}.amazonaws.com/graphql
data_url = amplify_outputs["data"]["url"]
region = data_url.split(".")[2]  # Extract region

# Get AWS account ID from amplify outputs
aws_account_id = amplify_outputs["data"]["aws_region"]  # This might not be right, let me check

print(f"Region: {region}")
print(f"Looking for AggregatedMetrics table...")

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb', region_name=region)

# List all tables and find the AggregatedMetrics table
response = dynamodb.list_tables()
aggregated_metrics_table = None

for table_name in response['TableNames']:
    if 'AggregatedMetrics' in table_name:
        aggregated_metrics_table = table_name
        break

if not aggregated_metrics_table:
    print("ERROR: Could not find AggregatedMetrics table")
    exit(1)

print(f"Found table: {aggregated_metrics_table}")

# Get account ID from environment
import os
account_id = os.environ.get('PLEXUS_ACCOUNT_ID', '9c929f25-a91f-4db7-8943-5aa93498b8e9')

print(f"Deleting all AggregatedMetrics for account: {account_id}")
print()

# Query all records
deleted = 0
batch = []

# Use the GSI to query by accountId
response = dynamodb.query(
    TableName=aggregated_metrics_table,
    IndexName='byAccountRecordType',
    KeyConditionExpression='accountId = :accountId',
    ExpressionAttributeValues={
        ':accountId': {'S': account_id}
    },
    ProjectionExpression='accountId, compositeKey'
)

items = response.get('Items', [])
print(f"Found {len(items)} items in first page")

while True:
    for item in items:
        # Add to batch
        batch.append({
            'DeleteRequest': {
                'Key': {
                    'accountId': item['accountId'],
                    'compositeKey': item['compositeKey']
                }
            }
        })
        
        # When batch reaches 25 items, write it
        if len(batch) >= 25:
            print(f"Deleting batch of {len(batch)} items... (total deleted: {deleted})")
            dynamodb.batch_write_item(
                RequestItems={
                    aggregated_metrics_table: batch
                }
            )
            deleted += len(batch)
            batch = []
    
    # Check for more pages
    if 'LastEvaluatedKey' not in response:
        break
    
    # Query next page
    response = dynamodb.query(
        TableName=aggregated_metrics_table,
        IndexName='byAccountRecordType',
        KeyConditionExpression='accountId = :accountId',
        ExpressionAttributeValues={
            ':accountId': {'S': account_id}
        },
        ProjectionExpression='accountId, compositeKey',
        ExclusiveStartKey=response['LastEvaluatedKey']
    )
    items = response.get('Items', [])
    print(f"Found {len(items)} items in next page")

# Delete remaining items in batch
if batch:
    print(f"Deleting final batch of {len(batch)} items...")
    dynamodb.batch_write_item(
        RequestItems={
            aggregated_metrics_table: batch
        }
    )
    deleted += len(batch)

print()
print(f"✓ Successfully deleted {deleted} records")

