"""
Lambda handler for processing DynamoDB streams and updating AggregatedMetrics.

This handler:
1. Gets triggered by DynamoDB stream events (tells us something changed)
2. Identifies the table and account from the stream event
3. Queries ALL records in current + previous hour from that table
4. Counts them efficiently into all bucket sizes (1/5/15/60 min)
5. Updates AggregatedMetrics with the actual counts
"""

import json
import os
from typing import Dict, Any, Set

from graphql_client import get_client_from_env
from graphql_queries import query_records_for_counting
from bucket_counter import count_records_efficiently, get_time_window


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for DynamoDB stream events.
    
    Strategy:
    - Stream events tell us which table/account had changes
    - We query the full 2-hour window (current + previous hour)
    - Count all records into buckets efficiently (O(n) iteration)
    - Update all bucket counts in AggregatedMetrics
    
    Args:
        event: Lambda event containing DynamoDB stream records
        context: Lambda context
        
    Returns:
        Response dict with status and processing summary
    """
    print(f"\n{'='*60}")
    print(f"METRICS AGGREGATION LAMBDA")
    print(f"{'='*60}")
    print(f"Stream records: {len(event.get('Records', []))}")
    
    try:
        # Initialize GraphQL client
        graphql_client = get_client_from_env()
        
        # Extract unique (record_type, account_id) pairs from stream events
        affected_tables = extract_affected_tables(event.get('Records', []))
        
        if not affected_tables:
            print("No affected tables identified from stream events")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No tables to process'})
            }
        
        print(f"Affected: {len(affected_tables)} table/account pairs")
        for record_type, account_id in affected_tables:
            print(f"  - {record_type} / {account_id[:12]}...")
        
        # Get the 2-hour time window (current + previous hour)
        start_time, end_time = get_time_window()
        print(f"Time window: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}")
        
        total_updates = 0
        total_errors = 0
        
        # Process each affected table
        for record_type, account_id in affected_tables:
            print(f"\n{'='*60}")
            print(f"Processing {record_type} for account {account_id}")
            print(f"{'='*60}")
            
            try:
                # Query all records in the time window with pagination
                print(f"[1/3] Querying {record_type}...")
                records = query_records_for_counting(
                    graphql_client,
                    record_type,
                    account_id,
                    start_time,
                    end_time
                )
                
                print(f"[1/3] Retrieved {len(records)} {record_type} records")
                
                # Count records into all buckets efficiently (O(n))
                print(f"[2/3] Counting into buckets...")
                bucket_counts = count_records_efficiently(records, account_id, record_type)
                
                print(f"[2/3] Generated {len(bucket_counts)} bucket updates")
                
                # Update all buckets in AggregatedMetrics
                print(f"[3/3] Updating AggregatedMetrics...")
                updates, errors = update_buckets(graphql_client, bucket_counts)
                
                total_updates += updates
                total_errors += errors
                
                if errors > 0:
                    print(f"[3/3] ⚠ Updated {updates} buckets with {errors} errors")
                else:
                    print(f"[3/3] ✓ Updated {updates} buckets successfully")
                
            except Exception as e:
                print(f"✗ Error processing {record_type}: {e}")
                import traceback
                traceback.print_exc()
                total_errors += 1
        
        summary = {
            'affected_tables': len(affected_tables),
            'time_window': f"{start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}",
            'buckets_updated': total_updates,
            'errors': total_errors
        }
        
        print(f"\n{'='*60}")
        if total_errors == 0:
            print(f"✓ SUCCESS: {total_updates} buckets updated")
        else:
            print(f"⚠ PARTIAL: {total_updates} buckets updated, {total_errors} errors")
        print(f"{'='*60}\n")
        
        return {
            'statusCode': 200,
            'body': json.dumps(summary)
        }
        
    except Exception as e:
        error_msg = f"Error in Lambda handler: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': error_msg})
        }


def extract_affected_tables(records: list) -> Set[tuple]:
    """
    Extract unique (record_type, account_id) pairs from stream events.
    
    Args:
        records: DynamoDB stream records
        
    Returns:
        Set of (record_type, account_id) tuples
    """
    affected = set()
    
    for record in records:
        # Get table name from event source ARN
        event_source_arn = record.get('eventSourceARN', '')
        record_type = determine_record_type(event_source_arn)
        
        if not record_type:
            continue
        
        # Get account ID from the record
        new_image = record.get('dynamodb', {}).get('NewImage', {})
        if new_image and 'accountId' in new_image:
            account_id = new_image['accountId'].get('S', '')
            if account_id:
                affected.add((record_type, account_id))
    
    return affected


def determine_record_type(event_source_arn: str) -> str:
    """
    Determine record type from DynamoDB stream ARN.
    
    Args:
        event_source_arn: Stream ARN like 'arn:aws:dynamodb:...:table/Item-xxx/stream/...'
        
    Returns:
        Record type ('items', 'scoreResults', 'tasks', 'evaluations') or empty string
    """
    arn_lower = event_source_arn.lower()
    
    if 'item' in arn_lower and 'feedback' not in arn_lower:
        return 'items'
    elif 'scoreresult' in arn_lower:
        return 'scoreResults'
    elif 'task' in arn_lower:
        return 'tasks'
    elif 'evaluation' in arn_lower:
        return 'evaluations'
    
    return ''


def update_buckets(graphql_client, bucket_counts: list) -> tuple:
    """
    Update all bucket counts in AggregatedMetrics.
    
    Args:
        graphql_client: GraphQL client instance
        bucket_counts: List of bucket count dicts
        
    Returns:
        Tuple of (successful_updates, failed_updates)
    """
    updates = 0
    errors = 0
    
    for bucket in bucket_counts:
        try:
            graphql_client.upsert_aggregated_metrics(
                account_id=bucket['account_id'],
                record_type=bucket['record_type'],
                time_range_start=bucket['time_range_start'],
                time_range_end=bucket['time_range_end'],
                number_of_minutes=bucket['number_of_minutes'],
                count=bucket['count'],
                complete=bucket['complete']
            )
            updates += 1
            
        except Exception as e:
            errors += 1
            print(f"Error updating bucket {bucket['time_range_start']} "
                  f"({bucket['number_of_minutes']}min): {e}")
    
    return updates, errors


