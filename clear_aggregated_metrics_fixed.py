#!/usr/bin/env python3
"""
Safe script to delete all records from the AggregatedMetrics DynamoDB table.
Handles eventual consistency and stops when table is actually empty.
"""

import boto3
import time
import sys

def clear_aggregated_metrics():
    """Safely delete all records, handling eventual consistency."""
    
    print("🚀 Starting safe AggregatedMetrics cleanup...")
    
    table_name = "AggregatedMetrics-qh4jgzgazfd2ncwbekhi4woj7a-NONE"
    
    try:
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        table = dynamodb.Table(table_name)
        
        deleted_total = 0
        round_num = 1
        
        while True:
            print(f"\n🔄 Round {round_num}: Scanning for records...")
            
            # Scan for more items at once (DynamoDB default limit is 1MB or 1000 items)
            response = table.scan(Limit=1000)
            items = response.get('Items', [])
            
            if not items:
                print("✅ No more records found - table is empty!")
                break
            
            print(f"📦 Found {len(items)} records in this batch")
            
            # Delete in chunks of 25 (DynamoDB batch write limit)
            batch_deleted = 0
            for i in range(0, len(items), 25):
                chunk = items[i:i + 25]
                
                with table.batch_writer() as batch:
                    for item in chunk:
                        batch.delete_item(Key={'id': item['id']})
                        batch_deleted += 1
                
                # Small delay between batch writes to avoid throttling
                if i + 25 < len(items):  # Don't delay after the last chunk
                    time.sleep(0.1)
            
            deleted_total += batch_deleted
            print(f"🗑️  Deleted {batch_deleted} records (total: {deleted_total})")
            
            # Shorter delay since we're processing larger batches
            time.sleep(0.5)
            round_num += 1
            
            # Safety check - don't run forever
            if round_num > 50:  # Reduced since we're processing more per round
                print("⚠️  Safety limit reached (50 rounds) - stopping")
                break
        
        # Final verification
        print("\n🔍 Final verification...")
        final_response = table.scan(Select='COUNT')
        final_count = final_response['Count']
        print(f"📊 Final record count: {final_count}")
        print(f"✅ Total records deleted: {deleted_total}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    clear_aggregated_metrics() 