#!/usr/bin/env python3
"""
Simple and efficient script to clear all AggregatedMetrics records.
Uses batch operations for maximum efficiency.
"""

import boto3
from boto3.dynamodb.conditions import Key
import time

def clear_aggregated_metrics():
    """Clear all records from AggregatedMetrics table efficiently."""
    
    print("🚀 Clearing AggregatedMetrics table...")
    
    table_name = "AggregatedMetrics-qh4jgzgazfd2ncwbekhi4woj7a-NONE"
    
    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    table = dynamodb.Table(table_name)
    
    try:
        # Get current count
        response = table.scan(Select='COUNT')
        total_count = response['Count']
        print(f"📊 Found {total_count} records")
        
        if total_count == 0:
            print("✅ Table already empty")
            return
        
        # Confirm
        confirm = input(f"Delete all {total_count} records? (yes/no): ")
        if confirm.lower() != 'yes':
            print("❌ Cancelled")
            return
        
        print("🗑️  Deleting records...")
        
        # Scan and delete in efficient batches
        deleted = 0
        
        while True:
            # Scan for a batch of items (limit to 100 for efficiency)
            scan_response = table.scan(Limit=100)
            items = scan_response.get('Items', [])
            
            if not items:
                break
            
            # Use batch_writer for efficient deletion
            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={'id': item['id']})
                    deleted += 1
            
            print(f"🗑️  Deleted {deleted} records...")
            
            # Small delay to avoid throttling
            time.sleep(0.1)
        
        print(f"✅ Deleted {deleted} records")
        
        # Verify
        final_response = table.scan(Select='COUNT')
        final_count = final_response['Count']
        print(f"📊 Final count: {final_count}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    clear_aggregated_metrics() 