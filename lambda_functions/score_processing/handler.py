# handler.py
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")
os.environ.setdefault("MPLBACKEND", "Agg")
# Redirect scorecard cache to /tmp for Lambda's read-only filesystem
os.environ.setdefault("SCORECARD_CACHE_DIR", "/tmp/scorecards")

import requests
API_URL = os.environ.get("PLEXUS_API_URL")
API_KEY = os.environ.get("PLEXUS_API_KEY")
ACCOUNT_KEY = os.environ.get("PLEXUS_ACCOUNT_KEY")

def gql(query: str, variables: dict | None = None) -> dict:
    if not API_URL or not API_KEY:
        raise ValueError("Missing PLEXUS_API_URL or PLEXUS_API_KEY")
    r = requests.post(
        API_URL,
        json={"query": query, "variables": variables or {}},
        headers={"Content-Type": "application/json", "x-api-key": API_KEY},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise Exception(f"GraphQL query failed: {data['errors'][0].get('message')}")
    return data.get("data") or {}

# tell the plexus client/gql not to introspect schema
# (works with gql-style clients: fetch_schema_from_transport=False)
os.environ.setdefault("PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT", "0")
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict
import traceback
import json
import boto3
from botocore.exceptions import ClientError
import tempfile
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.scoring_job import ScoringJob
from plexus.Scorecard import Scorecard
from plexus.dashboard.api.models.item import Item
from plexus.CustomLogging import logging, set_log_group
from plexus.plexus_logging.Cloudwatch import CloudWatchLogger

# Import Item model for upsert functionality
try:
    from plexus.dashboard.api.models.item import Item
    PLEXUS_ITEM_AVAILABLE = True
except ImportError:
    PLEXUS_ITEM_AVAILABLE = False

set_log_group('plexus/lambda-score-processing')
cloudwatch_logger = CloudWatchLogger(namespace="Plexus/LambdaScoreProcessing")

# Default bucket name for score result attachments S3 storage
# This should match the resource name in amplify/storage/resource.ts
DEFAULT_BUCKET_NAME = "scoreresultattachments-production"

def sanitize_metadata_for_graphql(metadata: dict) -> dict:
    """
    Sanitize metadata for GraphQL compatibility.

    Handles various data types and applies size limits to ensure the metadata
    can be safely stored in GraphQL/DynamoDB:
    - Truncates long strings
    - Summarizes large complex objects
    - Removes problematic characters
    - Handles serialization errors gracefully

    Args:
        metadata: Dictionary of metadata to sanitize

    Returns:
        Sanitized metadata dictionary safe for GraphQL operations
    """
    sanitized_metadata = {}
    if metadata:
        for key, meta_value in metadata.items():
            try:
                if meta_value is None:
                    sanitized_metadata[key] = None
                elif isinstance(meta_value, bool):
                    sanitized_metadata[key] = meta_value
                elif isinstance(meta_value, (int, float)):
                    # Ensure numeric values are reasonable for GraphQL
                    if abs(meta_value) < 1e10:
                        sanitized_metadata[key] = meta_value
                elif isinstance(meta_value, str):
                    # Truncate very long strings and remove problematic characters
                    cleaned_str = meta_value.replace('\x00', '').replace('\r', '').replace('\n', ' ')
                    if len(cleaned_str) > 500:
                        cleaned_str = cleaned_str[:497] + "..."
                    sanitized_metadata[key] = cleaned_str
                elif isinstance(meta_value, (dict, list)):
                    # Convert complex objects to JSON strings with size limit
                    json_str = json.dumps(meta_value, default=str)
                    if len(json_str) > 1000:
                        # Store summary instead of full object
                        if isinstance(meta_value, dict):
                            sanitized_metadata[key] = f"{{dict with {len(meta_value)} keys}}"
                        elif isinstance(meta_value, list):
                            sanitized_metadata[key] = f"[list with {len(meta_value)} items]"
                    else:
                        sanitized_metadata[key] = json_str
                else:
                    # Convert other types to string with size limit
                    str_value = str(meta_value)[:500]
                    sanitized_metadata[key] = str_value
            except Exception as e:
                logging.warning(f"Failed to sanitize metadata key '{key}': {e}")
                # Store a safe placeholder instead of skipping
                sanitized_metadata[key] = f"<serialization_error: {type(meta_value).__name__}>"

    return sanitized_metadata


def get_bucket_name():
    """
    Get the S3 bucket name for score result attachments from environment variables or fall back to the default.
    """
    return os.environ.get("AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME", DEFAULT_BUCKET_NAME)

def upload_score_result_trace_file(score_result_id, trace_data, file_name="trace.json"):
    """
    Upload trace data as a JSON file to the score result attachments S3 bucket.
    
    Args:
        score_result_id: ID of the score result this file belongs to
        trace_data: Dictionary or JSON-serializable data to upload
        file_name: Name of the file to create (default: "trace.json")
    
    Returns:
        The S3 path (key) for the file, formatted for Amplify Gen2
    """
    bucket_name = get_bucket_name()
    
    logging.info(f"Starting S3 upload for score result {score_result_id}, file {file_name}")
    logging.info(f"Using S3 bucket: {bucket_name}")
    
    # Check if bucket name exists
    if not bucket_name:
        logging.error("S3 bucket name is empty or None! Check environment variables or default config.")
        raise ValueError("S3 bucket name is missing")
    
    # Check if trace data is empty
    if not trace_data:
        logging.warning(f"Trace data for score result {score_result_id} is empty or None!")
        return None
    
    s3_client = boto3.client('s3')
    
    # Format path according to Amplify Gen2 expectations
    # The path should match what's defined in amplify/storage/resource.ts
    s3_key = f"scoreresults/{score_result_id}/{file_name}"
    
    # Convert trace data to JSON string
    try:
        if isinstance(trace_data, str):
            # If it's already a string, assume it's JSON
            json_content = trace_data
        else:
            # Convert to JSON string
            json_content = json.dumps(trace_data, indent=2)
    except (TypeError, ValueError) as e:
        logging.error(f"Failed to serialize trace data to JSON: {e}")
        raise ValueError(f"Trace data is not JSON serializable: {e}")
    
    logging.info(f"Creating temporary file for trace data (content length: {len(json_content)})")
    
    # Create a temporary file to upload from
    with tempfile.NamedTemporaryFile(mode='w+', suffix=f"_{file_name}", delete=False) as temp_file:
        temp_file_path = temp_file.name
        logging.info(f"Created temp file at {temp_file_path}")
        temp_file.write(json_content)
    
    try:
        # Set content type for JSON files
        extra_args = {
            'ContentType': 'application/json'
        }
            
        logging.info(f"Starting S3 upload to s3://{bucket_name}/{s3_key} with args: {extra_args}")
        
        # Upload the file to S3
        s3_client.upload_file(
            Filename=temp_file_path,
            Bucket=bucket_name, 
            Key=s3_key,
            ExtraArgs=extra_args
        )
        
        logging.info(f"Successfully uploaded {file_name} to s3://{bucket_name}/{s3_key}")
        
        # Return just the S3 path (key) as specified in the docstring
        return s3_key
    except ClientError as e:
        logging.error(f"AWS ClientError uploading trace file to S3: {str(e)}")
        logging.error(f"Error details: {e.response['Error'] if hasattr(e, 'response') else 'No response details'}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error uploading trace file to S3: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        raise
    finally:
        # Always remove the temporary file
        if os.path.exists(temp_file_path):
            logging.info(f"Removing temp file {temp_file_path}")
            os.remove(temp_file_path)

def upload_score_result_log_file(score_result_id: str, log_content: str) -> Optional[str]:
    """
    Upload a log file to S3 for a ScoreResult.
    
    Args:
        score_result_id: The ScoreResult ID
        log_content: The log content to upload
        
    Returns:
        The S3 path (key) if successful, None otherwise
    """
    try:
        # Use the same bucket as trace files
        bucket_name = get_bucket_name()
        
        logging.info(f"Starting log upload for score result {score_result_id}")
        logging.info(f"Using S3 bucket: {bucket_name}")
        
        # Check if bucket name exists
        if not bucket_name:
            logging.error("S3 bucket name is empty or None! Check environment variables or default config.")
            raise ValueError("S3 bucket name is missing")
        
        # Check if log content is empty
        if not log_content:
            logging.warning(f"Log content for score result {score_result_id} is empty!")
            return None
        
        # Initialize S3 client
        s3_client = boto3.client('s3')
        
        # Generate S3 key - use same path structure as trace files
        s3_key = f"scoreresults/{score_result_id}/log.txt"
        
        logging.info(f"Creating log file with content length: {len(log_content)} bytes")
        
        # Create a temporary file to upload from - use UTF-8 encoding for Unicode support
        with tempfile.NamedTemporaryFile(mode='w+', suffix="_log.txt", delete=False, encoding='utf-8') as temp_file:
            temp_file_path = temp_file.name
            logging.info(f"Created temp file at {temp_file_path}")
            temp_file.write(log_content)
        
        try:
            # Set content type for text files
            extra_args = {
                'ContentType': 'text/plain'
            }
            
            logging.info(f"Starting S3 upload to s3://{bucket_name}/{s3_key} with args: {extra_args}")
            
            # Upload the file to S3
            s3_client.upload_file(
                Filename=temp_file_path,
                Bucket=bucket_name,
                Key=s3_key,
                ExtraArgs=extra_args
            )
            
            logging.info(f"Successfully uploaded log file to s3://{bucket_name}/{s3_key}")
            
            # Return just the S3 path (key) to match trace file behavior
            return s3_key
            
        except ClientError as e:
            logging.error(f"AWS ClientError uploading log file to S3: {str(e)}")
            logging.error(f"Error details: {e.response['Error'] if hasattr(e, 'response') else 'No response details'}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error uploading log file to S3: {str(e)}")
            logging.error(traceback.format_exc())
            raise
        finally:
            # Always remove the temporary file
            if os.path.exists(temp_file_path):
                logging.info(f"Removing temp file {temp_file_path}")
                os.remove(temp_file_path)
        
    except Exception as e:
        logging.error(f"Error uploading log file to S3: {str(e)}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return None

async def create_score_result_for_api(report_id: str, scorecard_id: str, score_id: str, value: str, explanation: str, trace_data: dict = None, log_content: str = None, request_id: str = None, code: str = "200", status: str = "COMPLETED", cost: Optional[dict] = None):
    """
    Create a score result in DynamoDB for API memoization.
    This function creates an Item (if needed) and a ScoreResult to cache the scoring results.
    If trace data is provided, it will be uploaded to S3 and its path will be returned.
    
    Args:
        report_id: The report ID (used as external ID for the item)
        scorecard_id: The scorecard external ID
        score_id: The score external ID
        value: The score value
        explanation: The explanation for the score
        trace_data: Optional trace data to upload to S3 as an attachment
        log_content: Optional log content to upload to S3 as an attachment
        request_id: Optional request ID for logging
        code: Optional code to include in the score result
        status: Optional status to include in the score result
        cost: Optional cost to include in the score result
        
    Returns:
        A dictionary containing score_result_id, item_id, value, explanation, and trace_attachment_path (or None)
    """
    try:
        # Prevent caching if the result is an error or disabled
        value_str = str(value) if not isinstance(value, str) else value
        if value_str.upper() == "ERROR":
            logging.warning(f"CACHE SKIPPED (ERROR): Skipping cache for report_id={report_id}, scorecard={scorecard_id}, score={score_id} because value is 'ERROR'.")
            return { "score_result_id": None, "item_id": None, "value": value, "explanation": explanation, "trace_attachment_path": None }
        elif value_str.upper() == "DISABLED":
            logging.warning(f"CACHE SKIPPED (DISABLED): Skipping cache for report_id={report_id}, scorecard={scorecard_id}, score={score_id} because value is 'DISABLED'.")
            return { "score_result_id": None, "item_id": None, "value": value, "explanation": explanation, "trace_attachment_path": None }

        # Log cache creation attempt
        logging.info(f"💾 CACHE CREATION START: Creating cache entry for report_id={report_id}, scorecard={scorecard_id}, score={score_id}, value={value}")
        logging.info(json.dumps({
            "message_type": "cache_creation_start",
            "report_id": report_id,
            "scorecard_id": scorecard_id,
            "score_id": score_id,
            "value": value,
            "status": status,
            "has_trace_data": bool(trace_data),
            "operation": "creating_score_result_for_cache_and_trace_upload"
        }))
        
        # Use the dashboard client to execute the query
        from plexus.dashboard.api.client import PlexusDashboardClient
        client = PlexusDashboardClient()
        
        # First, look up the Account ID using the key from the environment variable
        account_query = """
        query GetAccountByKey($key: String!) {
            listAccountByKey(key: $key) {
                items {
                    id
                    name
                }
            }
        }
        """
        
        account_variables = {
            "key": ACCOUNT_KEY
        }
        
        logging.info(f"Looking up Account ID for key: {ACCOUNT_KEY}")
        account_response = await asyncio.to_thread(gql, account_query, account_variables)
        
        account_items = account_response.get('listAccountByKey', {}).get('items', [])
        if not account_items:
            logging.error(f"No account found with key: {ACCOUNT_KEY}. Cannot proceed with cache creation.")
            # If account resolution fails, we can't reliably create scoped cache entries.
            return { "score_result_id": None, "item_id": None, "value": value, "explanation": explanation, "trace_attachment_path": None }
        account_id = account_items[0]['id']
        account_name = account_items[0]['name']
        logging.info(f"Found account: {account_name} with ID: {account_id}")
        
        # Resolve the scorecard external ID to its DynamoDB ID
        logging.info(f"Resolving scorecard external ID: {scorecard_id}")
        dynamo_scorecard_id = await resolve_scorecard_id(scorecard_id, account_id, client)
        if not dynamo_scorecard_id:
            logging.warning(f"Cache creation: Scorecard external ID {scorecard_id} for account {account_id} could not be resolved. Using external ID as fallback for scorecard component of cache key.")
            # Fallback for scorecard ID. This is risky for cache consistency if ScoreResult.scorecardId must be a DynamoDB ID.
            # For now, adopting the original code's tendency to use external_id as fallback.
            # If createScoreResult strictly needs a dynamo_scorecard_id, this path needs more thought (e.g., abort caching).
            dynamo_scorecard_id = scorecard_id # Fallback
        logging.info(f"Using scorecard DynamoDB ID {dynamo_scorecard_id} (or fallback) for cache storage")
        
        # Resolve the score external ID to its DynamoDB ID
        logging.info(f"Resolving score external ID: {score_id} for scorecard DynamoDB ID: {dynamo_scorecard_id}")
        resolved_score_info = await resolve_score_id(score_id, dynamo_scorecard_id, client)

        dynamo_score_id = None
        if resolved_score_info:
            dynamo_score_id = resolved_score_info['id']

        if not dynamo_score_id:
            logging.warning(f"Cache creation: Score external ID {score_id} for scorecard {dynamo_scorecard_id} could not be resolved to a DynamoDB ID. Using external ID as fallback for cache storage.")
            # Use external ID as fallback - this should match what cache lookup does
            dynamo_score_id = score_id
        
        logging.info(f"Using resolved score DynamoDB ID {dynamo_score_id} for cache storage")

        # Use Item.upsert_by_identifiers to handle deduplication automatically
        logging.info(f"🔍 Using SDK upsert for Item with externalId: {report_id} in account: {account_id}")
        
        # Check if SDK is available
        if not PLEXUS_ITEM_AVAILABLE:
            logging.error("Plexus Item SDK not available - falling back to manual creation")
            return {
                "score_result_id": None,
                "item_id": None,
                "value": value,
                "explanation": explanation,
                "trace_attachment_path": None,
                "status": status
            }
        
        # Get text and metadata from the report
        text = await get_text_from_report(report_id)
        metadata = await get_metadata_from_report(report_id)
        
        if not text:
            logging.error(f"Cannot create Item without text for report_id: {report_id}")
            return {
                "score_result_id": None,
                "item_id": None,
                "value": value,
                "explanation": explanation,
                "trace_attachment_path": None,
                "status": status
            }
        
        # 🔍 COMPREHENSIVE METADATA LOGGING
        logging.info(f"📊 METADATA CONTENT for report_id={report_id}:")
        logging.info(json.dumps({
            "message_type": "metadata_content_full",
            "report_id": report_id,
            "metadata_keys": list(metadata.keys()) if metadata else [],
            "metadata_size": len(str(metadata)) if metadata else 0,
            "full_metadata": metadata,
            "text_length": len(text) if text else 0,
            "text_preview": text[:200] + "..." if text and len(text) > 200 else text
        }, indent=2))

        # Sanitize metadata for GraphQL compatibility
        sanitized_metadata = sanitize_metadata_for_graphql(metadata)

        logging.info(f"📊 SANITIZED METADATA for GraphQL (size: {len(str(sanitized_metadata))})")
        logging.info(json.dumps({
            "message_type": "sanitized_metadata",
            "report_id": report_id,
            "original_size": len(str(metadata)) if metadata else 0,
            "sanitized_size": len(str(sanitized_metadata)),
            "sanitized_keys": list(sanitized_metadata.keys()),
            "sanitization_applied": "string_truncation_complex_object_summarization"
        }, indent=2))
        
        # Look up form_id and session_id from database for the identifiers
        form_id = None
        session_id = None
                
        # Create identifiers dict for SDK upsert
        # ALWAYS ensure we have reportId and sessionId
        identifiers = {
            'reportId': report_id  # Always present
        }
        
        # Add sessionId - use actual session_id if found, otherwise use report_id as fallback
        if session_id is not None:
            identifiers['sessionId'] = session_id
            logging.info(f"🔑 Using actual session_id: {session_id}")
        else:
            # Fallback: use report_id as session_id (better than no session_id at all)
            identifiers['sessionId'] = report_id
            logging.warning(f"⚠️ SESSION ID FALLBACK: Using report_id {report_id} as session_id because database lookup failed")
        
        # Only add formId if we found one (it's optional)
        if form_id is not None:
            identifiers['formId'] = form_id
            logging.info(f"🔑 Using form_id: {form_id}")
        else:
            logging.info(f"🔑 No form_id found - this is normal when Form doesn't exist yet")
        
        # Validate final identifiers (should never be empty now)
        if not identifiers:
            logging.error(f"❌ CRITICAL: No identifiers created for report_id {report_id} - this should be impossible!")
        elif len(identifiers) < 2:
            logging.warning(f"⚠️ Only {len(identifiers)} identifiers created: {identifiers}")
        else:
            logging.info(f"✅ Created {len(identifiers)} identifiers: {list(identifiers.keys())}")
        
        logging.info(f"🔑 Using identifiers for SDK upsert: {identifiers}")
        
        try:
            # Use SDK upsert functionality to handle deduplication automatically
            item_id, was_created, error_msg = await asyncio.to_thread(
                Item.upsert_by_identifiers,
                client=client,
                account_id=account_id,
                identifiers=identifiers,
                external_id=report_id,
                description=f"API Call - Report {report_id}",
                text=text,
                is_evaluation=False,
                metadata=sanitized_metadata,  # SDK should handle JSON conversion consistently
                debug=True  # Enable debug logging
            )
            
            if error_msg:
                logging.error(f"SDK Item upsert failed: {error_msg}")
                return {
                    "score_result_id": None,
                    "item_id": None,
                    "value": value,
                    "explanation": explanation,
                    "trace_attachment_path": None
                }
            
            # Log the SDK upsert result
            if was_created:
                logging.info(f"✅ SDK created new Item with ID: {item_id} for externalId: {report_id}")
            else:
                logging.info(f"✅ SDK found and updated existing Item with ID: {item_id} for externalId: {report_id}")
                
            logging.info(json.dumps({
                "message_type": "sdk_item_upsert_complete",
                "item_id": item_id,
                "was_created": was_created,
                "external_id": report_id,
                "account_id": account_id,
                "identifiers": identifiers,
                "text_length": len(text) if text else 0,
                "metadata_size": len(str(metadata)) if metadata else 0
            }, indent=2))
            
            # Verify identifier records were actually created
            if was_created and identifiers:
                logging.info(f"🔍 IDENTIFIER VERIFICATION: Checking if identifier records were created for new Item {item_id}")
                try:
                    # Try to find the item by one of its identifiers to verify they exist
                    verification_item = await asyncio.to_thread(
                        Item.find_by_identifier,
                        client=client,
                        account_id=account_id,
                        identifier_key="reportId",
                        identifier_value=report_id,
                        debug=True
                    )
                    
                    if verification_item and verification_item.id == item_id:
                        logging.info(f"✅ IDENTIFIER VERIFICATION: Successfully verified identifier records exist for Item {item_id}")
                    else:
                        logging.error(f"❌ IDENTIFIER VERIFICATION FAILED: Could not find Item {item_id} by reportId {report_id} - identifier records may not have been created!")
                        logging.error(f"❌ This means the Item was created but without proper identifiers - this is the bug we're trying to fix!")
                        
                except Exception as verify_error:
                    logging.error(f"❌ IDENTIFIER VERIFICATION ERROR: Could not verify identifier records for Item {item_id}: {verify_error}")
                    logging.error(f"❌ This suggests identifier creation may have failed silently")
            
        except Exception as e:
            logging.error(f"Error during SDK Item upsert: {str(e)}")
            logging.error(f"Stack trace: {traceback.format_exc()}")
            return {
                "score_result_id": None,
                "item_id": None,
                "value": value,
                "explanation": explanation,
                "trace_attachment_path": None
            }
        
        # Now create the ScoreResult
        logging.info(f"📊 Creating ScoreResult for item_id: {item_id}, scorecard: {dynamo_scorecard_id}, score: {dynamo_score_id}")
        
        # Validate required fields before creating ScoreResult
        if not all([value, item_id, account_id, dynamo_scorecard_id]):
            missing_fields = []
            if not value:
                missing_fields.append("value")
            if not item_id:
                missing_fields.append("item_id")
            if not account_id:
                missing_fields.append("account_id")
            if not dynamo_scorecard_id:
                missing_fields.append("dynamo_scorecard_id")
            
            error_msg = f"Cannot create ScoreResult, missing required fields: {', '.join(missing_fields)}"
            logging.error(error_msg)
            logging.error(json.dumps({
                "message_type": "score_result_validation_error",
                "missing_fields": missing_fields,
                "value": value,
                "item_id": item_id,
                "report_id": report_id,
                "account_id": account_id,
                "dynamo_scorecard_id": dynamo_scorecard_id,
                "dynamo_score_id": dynamo_score_id,
                "status": status
            }))
            return
        
        create_score_result_mutation = """
        mutation CreateScoreResult($input: CreateScoreResultInput!) {
            createScoreResult(input: $input) {
                id
                value
                explanation
                itemId
                scorecardId
                scoreId
                createdAt
                updatedAt
                type
                status
            }
        }
        """
        
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        score_result_metadata = {
            "source": "API",
            "cached_at": now,
            "report_id": report_id,
            "explanation": explanation
        }
        # Persist cost if provided
        if cost is not None:
            try:
                # Ensure cost is JSON-serializable; if not, convert to string
                json.dumps(cost, default=str)
                score_result_metadata["cost"] = cost
            except Exception:
                score_result_metadata["cost"] = str(cost)
        
        # Determine code value for ScoreResult
        # Handle case where value might be a list or other type
        value_str = str(value) if not isinstance(value, str) else value
        if value_str.upper() == "ERROR":
            code = "500"
        elif value_str.upper() == "DISABLED":
            code = "403"
        else:
            code = "200"
        
        # Convert value to appropriate string format for ScoreResult
        if isinstance(value, list):
            # If it's a list, join with commas or take first element
            display_value = str(value[0]) if len(value) == 1 else ", ".join(map(str, value))
        else:
            display_value = str(value)
        
        create_score_result_input = {
            "value": display_value,  # Ensure value is a string for ScoreResult
            "explanation": explanation,
            "metadata": json.dumps(score_result_metadata, default=str),
            "itemId": item_id,
            "accountId": account_id,
            "scorecardId": dynamo_scorecard_id,
            "scoreId": dynamo_score_id,
            "evaluationId": None,  # Not part of an evaluation
            "createdAt": now,
            "updatedAt": now,
            "code": code,  # <-- Set code here
            "type": "prediction",  # API calls are predictions
            "status": status,
        }
        
        # Add trace data if available (same approach as evaluation)
        if trace_data:
            logging.info(f"🔍 Adding trace data to ScoreResult creation: {type(trace_data)}")
            try:
                create_score_result_input["trace"] = json.dumps(trace_data)
                logging.info(f"✅ Successfully added trace to ScoreResult creation")
            except Exception as e:
                logging.error(f"❌ Error serializing trace data for ScoreResult: {e}")
                # Continue without trace if serialization fails
        else:
            logging.info("ℹ️ No trace data to add to ScoreResult creation")
        
        create_score_result_variables = {
            "input": create_score_result_input
        }
        
        # ==> DIAGNOSTIC LOGGING FOR DEBUGGING STRANGE CODES <==
        logging.info(json.dumps({
            "message_type": "CACHE_CREATION_DIAGNOSTIC",
            "source_function": "create_score_result_for_api",
            "final_code_to_be_saved": code,
            "original_value": value,
            "report_id": report_id,
            "scorecard_id": scorecard_id,
            "score_id": score_id,
            "explanation": explanation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status
        }, indent=2))
        
        logging.info(json.dumps({
            "message_type": "creating_score_result",
            "item_id": item_id,
            "scorecard_id": dynamo_scorecard_id,
            "score_id": dynamo_score_id,
            "report_id": report_id,
            "value": value,
            "has_explanation": bool(explanation),
            "status": status
        }))
        
        create_result = await asyncio.to_thread(gql, create_score_result_mutation, create_score_result_variables)
        
        if not create_result or 'createScoreResult' not in create_result:
            logging.error(f"Failed to create ScoreResult: {create_result}")
            return
        
        score_result_id = create_result['createScoreResult']['id']
        score_result_created_at = create_result['createScoreResult']['createdAt']  # Store for GSI updates
        logging.info(f"✅ Created ScoreResult with ID: {score_result_id}")
        logging.info(json.dumps({
            "message_type": "cache_created_successfully",
            "score_result_id": score_result_id,
            "item_id": item_id,
            "report_id": report_id,
            "scorecard_id": scorecard_id,
            "score_id": score_id,
            "value": value,
            "status": status
        }))
        
        # Log cache created metric to CloudWatch
        cloudwatch_logger.log_metric(
            metric_name="CacheCreated",
            metric_value=1,
            dimensions={
                "Environment": os.getenv('environment', 'unknown')
            }
        )
        
        # Handle trace data upload and attachment with improved reliability  
        trace_attachment_s3_path = None # Initialize to None
        log_attachment_s3_path = None # Initialize to None for log files
        upload_errors = []
        
        # Track what we're trying to upload for better logging
        upload_attempts = {
            "trace": bool(trace_data),
            "log": bool(log_content)
        }
        
        logging.info(f"🚀 Starting trace and log attachment upload process for ScoreResult {score_result_id}")
        logging.info(json.dumps({
            "message_type": "attachment_upload_start",
            "score_result_id": score_result_id,
            "will_upload_trace": upload_attempts["trace"],
            "will_upload_log": upload_attempts["log"],
            "trace_data_size": len(str(trace_data)) if trace_data else 0,
            "log_content_size": len(log_content) if log_content else 0
        }))
        
        # Handle trace data upload with proper async wrapping
        if trace_data:
            try:
                logging.info(f"🔄 Starting trace data upload to S3 for ScoreResult {score_result_id}")
                # Wrap the synchronous S3 upload in asyncio.to_thread for proper async handling
                s3_path = await asyncio.to_thread(upload_score_result_trace_file, score_result_id, trace_data)
                if s3_path:
                    trace_attachment_s3_path = s3_path # Store the path
                    logging.info(f"✅ Successfully uploaded trace data to S3: {s3_path}")
                    logging.info(json.dumps({
                        "message_type": "trace_upload_success",
                        "score_result_id": score_result_id,
                        "s3_path": s3_path,
                        "trace_data_size": len(str(trace_data))
                    }))
                else:
                    error_msg = "No S3 path returned from trace upload"
                    upload_errors.append(f"trace: {error_msg}")
                    logging.warning(f"⚠️ {error_msg}")
                    logging.warning(json.dumps({
                        "message_type": "trace_upload_warning",
                        "score_result_id": score_result_id,
                        "issue": "no_s3_path_returned"
                    }))
            except Exception as trace_error:
                error_msg = f"Error uploading trace data: {str(trace_error)}"
                upload_errors.append(f"trace: {error_msg}")
                logging.error(f"❌ {error_msg}")
                logging.error(f"Stack trace: {traceback.format_exc()}")
                logging.error(json.dumps({
                    "message_type": "trace_upload_error",
                    "score_result_id": score_result_id,
                    "error": str(trace_error),
                    "error_type": type(trace_error).__name__
                }))
        else:
            logging.info(f"ℹ️ No trace data provided for ScoreResult {score_result_id}")
        
        # Handle log content upload with proper async wrapping
        if log_content:
            try:
                logging.info(f"🔄 Starting log content upload to S3 for ScoreResult {score_result_id}")
                # Wrap the synchronous S3 upload in asyncio.to_thread for proper async handling
                s3_path = await asyncio.to_thread(upload_score_result_log_file, score_result_id, log_content)
                if s3_path:
                    log_attachment_s3_path = s3_path # Store the path
                    logging.info(f"✅ Successfully uploaded log content to S3: {s3_path}")
                    logging.info(json.dumps({
                        "message_type": "log_upload_success",
                        "score_result_id": score_result_id,
                        "s3_path": s3_path,
                        "log_content_size": len(log_content)
                    }))
                else:
                    error_msg = "No S3 path returned from log upload"
                    upload_errors.append(f"log: {error_msg}")
                    logging.warning(f"⚠️ {error_msg}")
                    logging.warning(json.dumps({
                        "message_type": "log_upload_warning",
                        "score_result_id": score_result_id,
                        "issue": "no_s3_path_returned"
                    }))
            except Exception as log_error:
                error_msg = f"Error uploading log content: {str(log_error)}"
                upload_errors.append(f"log: {error_msg}")
                logging.error(f"❌ {error_msg}")
                logging.error(f"Stack trace: {traceback.format_exc()}")
                logging.error(json.dumps({
                    "message_type": "log_upload_error",
                    "score_result_id": score_result_id,
                    "error": str(log_error),
                    "error_type": type(log_error).__name__
                }))
        else:
            logging.info(f"ℹ️ No log content provided for ScoreResult {score_result_id}")
            
        # Log upload summary for both trace and log
        successful_uploads = (1 if trace_attachment_s3_path else 0) + (1 if log_attachment_s3_path else 0)
        total_attempts = (1 if upload_attempts["trace"] else 0) + (1 if upload_attempts["log"] else 0)
        
        logging.info(f"📊 Upload summary: {successful_uploads}/{total_attempts} uploads successful")
        logging.info(json.dumps({
            "message_type": "upload_summary",
            "score_result_id": score_result_id,
            "attempted_trace_upload": upload_attempts["trace"],
            "attempted_log_upload": upload_attempts["log"],
            "successful_trace_upload": 1 if trace_attachment_s3_path else 0,
            "successful_log_upload": 1 if log_attachment_s3_path else 0,
            "trace_attachment_path": trace_attachment_s3_path,
            "log_attachment_path": log_attachment_s3_path,
            "upload_errors": upload_errors
        }))
            
        # Update the ScoreResult with both trace and log attachments if they were uploaded successfully
        attachment_paths = []
        if trace_attachment_s3_path:
            attachment_paths.append(trace_attachment_s3_path)
        if log_attachment_s3_path:
            attachment_paths.append(log_attachment_s3_path)
            
        if attachment_paths:
            try:
                update_score_result_mutation = """
                mutation UpdateScoreResult($input: UpdateScoreResultInput!) {
                    updateScoreResult(input: $input) {
                        id
                        attachments
                        updatedAt
                    }
                }
                """
                
                # When updating any field, DynamoDB automatically updates 'updatedAt', which triggers
                # GSI composite key requirements. Must include all fields for affected GSIs:
                # - byItemScorecardScoreUpdated: itemId + scorecardId + scoreId + updatedAt
                # - byScorecardItemAndCreatedAt: scorecardId + itemId + createdAt  
                # - byAccountCodeAndUpdatedAt: accountId + code + updatedAt
                update_score_result_input = {
                    "id": score_result_id,
                    "attachments": attachment_paths, # Both trace and log attachments
                    "itemId": item_id,               # Required for multiple GSIs
                    "accountId": account_id,         # Required for byAccountCodeAndUpdatedAt GSI
                    "scorecardId": dynamo_scorecard_id, # Required for multiple GSIs  
                    "scoreId": dynamo_score_id,      # Required for byItemScorecardScoreUpdated GSI
                    "createdAt": score_result_created_at, # Required for byScorecardItemAndCreatedAt GSI
                    "code": code                     # Required for byAccountCodeAndUpdatedAt GSI
                }
                
                update_score_result_variables = {
                    "input": update_score_result_input
                }
                
                logging.info(f"📎 Updating ScoreResult {score_result_id} with {len(attachment_paths)} attachments: {attachment_paths}")
                logging.info(json.dumps({
                    "message_type": "score_result_attachment_update_attempt",
                    "score_result_id": score_result_id,
                    "attachments": attachment_paths
                }))
                
                # Use asyncio.to_thread for the GraphQL mutation as well
                update_score_result_result = await asyncio.to_thread(gql, update_score_result_mutation, update_score_result_variables)
                
                if update_score_result_result and 'updateScoreResult' in update_score_result_result:
                    logging.info(f"✅ Successfully updated ScoreResult with {len(attachment_paths)} attachments")
                    logging.info(json.dumps({
                        "message_type": "score_result_updated_with_attachments",
                        "score_result_id": score_result_id,
                        "attachments": attachment_paths,
                        "updated_at": update_score_result_result['updateScoreResult']['updatedAt']
                    }))
                else:
                    error_msg = f"GraphQL update mutation failed: {update_score_result_result}"
                    upload_errors.append(f"update_attachments: {error_msg}")
                    logging.error(f"❌ Failed to update ScoreResult with attachments: {update_score_result_result}")
                    logging.error(json.dumps({
                        "message_type": "score_result_attachment_update_failed",
                        "score_result_id": score_result_id,
                        "mutation_result": update_score_result_result,
                        "attempted_attachments": attachment_paths
                    }))
            except Exception as attachment_error:
                error_msg = f"Exception during ScoreResult attachment update: {str(attachment_error)}"
                upload_errors.append(f"update_attachments: {error_msg}")
                logging.error(f"❌ Error updating ScoreResult with attachments: {str(attachment_error)}")
                logging.error(f"Stack trace: {traceback.format_exc()}")
                logging.error(json.dumps({
                    "message_type": "score_result_attachment_update_exception",
                    "score_result_id": score_result_id,
                    "error": str(attachment_error),
                    "error_type": type(attachment_error).__name__,
                    "attempted_attachments": attachment_paths
                }))
        else:
            logging.info(f"ℹ️ No attachments to update ScoreResult {score_result_id} with")
            logging.info(json.dumps({
                "message_type": "no_attachments_to_update",
                "score_result_id": score_result_id,
                "attempted_trace_upload": upload_attempts["trace"],
                "attempted_log_upload": upload_attempts["log"],
                "upload_errors": upload_errors
            }))
        
        # Log final attachment status for monitoring and debugging
        final_status = {
            "score_result_id": score_result_id,
            "requested_trace_attachment": upload_attempts["trace"],
            "requested_log_attachment": upload_attempts["log"],
            "successful_trace_attachment": 1 if trace_attachment_s3_path else 0,
            "successful_log_attachment": 1 if log_attachment_s3_path else 0,
            "trace_attachment_path": trace_attachment_s3_path,
            "log_attachment_path": log_attachment_s3_path,
            "any_errors": len(upload_errors) > 0,
            "error_summary": upload_errors
        }
        
        if upload_errors:
            logging.warning(f"⚠️ Attachment process completed with errors for ScoreResult {score_result_id}")
            logging.warning(json.dumps({
                "message_type": "attachment_process_completed_with_errors",
                **final_status
            }))
        else:
            logging.info(f"✅ Attachment process completed successfully for ScoreResult {score_result_id}")
            logging.info(json.dumps({
                "message_type": "attachment_process_completed_successfully", 
                **final_status
            }))
        
        # Update the Item's updatedAt timestamp to reflect score computation completion
        try:
            update_item_mutation = """
            mutation UpdateItem($input: UpdateItemInput!) {
                updateItem(input: $input) {
                    id
                    updatedAt
                }
            }
            """
            
            now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            update_item_input = {
                "id": item_id,
                "updatedAt": now
            }
            
            update_item_variables = {
                "input": update_item_input
            }
            
            logging.info(f"📝 Updating Item {item_id} timestamp to mark score computation completion")
            update_item_result = await asyncio.to_thread(gql, update_item_mutation, update_item_variables)
            
            if update_item_result and 'updateItem' in update_item_result:
                final_updated_at = update_item_result['updateItem']['updatedAt']
                logging.info(f"✅ Successfully updated Item {item_id} timestamp to {final_updated_at}")
                logging.info(json.dumps({
                    "message_type": "item_timestamp_updated",
                    "item_id": item_id,
                    "score_result_id": score_result_id,
                    "final_updated_at": final_updated_at,
                    "operation": "score_computation_complete"
                }))
            else:
                logging.warning(f"⚠️ Failed to update Item {item_id} timestamp: {update_item_result}")
                
        except Exception as timestamp_error:
            logging.error(f"❌ Error updating Item {item_id} timestamp: {str(timestamp_error)}")
            logging.error(f"Stack trace: {traceback.format_exc()}")
            # Continue despite the error - timestamp update is not critical for functionality

        return {
            "score_result_id": score_result_id,
            "item_id": item_id,
            "value": value,
            "explanation": explanation,
            "trace_attachment_path": trace_attachment_s3_path, # Return trace path
            "log_attachment_path": log_attachment_s3_path # Return log path
        }
            
    except Exception as e:
        logging.error(f"Error creating score result for API: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        logging.error(json.dumps({
            "message_type": "cache_creation_error",
            "error": str(e),
            "report_id": report_id,
            "scorecard_id": scorecard_id,
            "score_id": score_id,
            "has_trace_data": bool(trace_data) # Add trace data presence to error log
        }))
        # We'll continue despite the error - this is just for caching
        # Return None or some error indicator if this function must guarantee ScoreResult creation
        # For now, it mostly continues, but the caller (read_score) will proceed to return the computed score.
        # If ScoreResult creation is absolutely critical before returning, this error handling needs adjustment.
        # However, the primary goal is to return the score; caching/attachments are secondary.
        return { # Still return something so read_score doesn't break, even if caching failed
            "score_result_id": None,
            "item_id": None,
            "value": value, # The computed value might still be useful to the caller via read_score
            "explanation": explanation,
            "trace_attachment_path": None
        }


async def resolve_scorecard_id(external_id: str, account_id: str, client) -> Optional[str]:
    """
    Resolve a scorecard external ID to its DynamoDB ID using the GSI, scoped by accountId.
    
    Args:
        external_id: The external ID of the scorecard
        account_id: The DynamoDB ID of the account
        client: The dashboard client
        
    Returns:
        The DynamoDB ID of the scorecard if found, None otherwise
    """
    try:
        # Use the byAccountIdAndExternalId GSI for fast lookup
        query = """
        query GetScorecardByAccountIdAndExternalId($accountId: String!, $externalId: String!) {
            listScorecardByAccountIdAndExternalId(accountId: $accountId, externalId: {eq: $externalId}, limit: 1) {
                items {
                    id
                }
            }
        }
        """
        
        variables = {
            "accountId": account_id,
            "externalId": external_id
        }
        
        result = await asyncio.to_thread(gql, query, variables)
        items = result.get('listScorecardByAccountIdAndExternalId', {}).get('items', [])
        
        if items and len(items) > 0:
            logging.info(f"Resolved scorecard external ID {external_id} for account {account_id} to DynamoDB ID {items[0]['id']}")
            return items[0]['id']
            
        logging.warning(f"Could not resolve scorecard external ID: {external_id} for account {account_id}")
        return None
    except Exception as e:
        logging.error(f"Error resolving scorecard external ID for account {account_id}: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return None

async def create_scorecard_instance_for_single_score(scorecard_identifier: str, score_identifier: str) -> Optional[Scorecard]:
    """Create a scorecard instance optimized for a single score request."""
    try:
        logging.info(f"Creating targeted scorecard instance for scorecard: {scorecard_identifier}, score: {score_identifier}")
        
        # Import the individual functions we need for targeted loading
        from plexus.cli.shared.direct_memoized_resolvers import direct_memoized_resolve_scorecard_identifier
        from plexus.cli.shared.fetch_scorecard_structure import fetch_scorecard_structure
        from plexus.cli.shared.identify_target_scores import identify_target_scores
        from plexus.cli.shared.iterative_config_fetching import iteratively_fetch_configurations
        from plexus.Scorecard import Scorecard
        
        # Step 1: Get API client and resolve scorecard identifier
        from plexus.dashboard.api.client import PlexusDashboardClient
        client = PlexusDashboardClient()
        
        scorecard_id = await asyncio.to_thread(direct_memoized_resolve_scorecard_identifier, client, scorecard_identifier)
        if not scorecard_id:
            logging.error(f"Could not resolve scorecard identifier: {scorecard_identifier}")
            return None
            
        logging.info(f"Resolved scorecard ID: {scorecard_id}")
        
        # Step 2: Fetch minimal scorecard structure (just metadata, not full configs)
        scorecard_structure = await asyncio.to_thread(fetch_scorecard_structure, client, scorecard_id)
        if not scorecard_structure:
            logging.error(f"Could not fetch scorecard structure for ID: {scorecard_id}")
            return None
            
        # Step 3: Find the specific target score by its identifier
        # Convert the score identifier to a list for the function
        target_scores = await asyncio.to_thread(
            identify_target_scores, 
            scorecard_structure, 
            [score_identifier]  # Only the one score we want
        )
        
        if not target_scores:
            logging.error(f"Could not find score {score_identifier} in scorecard {scorecard_identifier}")
            return None
            
        logging.info(f"Identified target score: {target_scores[0]}")
        
        # Step 4: Fetch only the required configurations (target + dependencies)
        # This will do just-in-time dependency resolution
        scorecard_configs = await asyncio.to_thread(
            iteratively_fetch_configurations,
            client,
            scorecard_structure,
            target_scores,
            use_cache=False  # Always fresh for API requests
        )
        
        if not scorecard_configs:
            logging.error(f"Could not fetch configurations for score {score_identifier}")
            return None
            
        logging.info(f"Fetched {len(scorecard_configs)} score configurations (target + dependencies)")
        
        # Step 5: Create scorecard instance with only the required scores
        # Parse string configurations into dictionaries (same as in evaluations.py)
        parsed_configs = []
        from ruamel.yaml import YAML
        yaml_parser = YAML(typ='safe')
        
        for score_id, config in scorecard_configs.items():
            try:
                # If config is a string, parse it as YAML
                if isinstance(config, str):
                    parsed_config = yaml_parser.load(config)
                    # Add the score ID as an identifier if not present
                    if 'id' not in parsed_config:
                        parsed_config['id'] = score_id
                    parsed_configs.append(parsed_config)
                elif isinstance(config, dict):
                    # If already a dict, add as is
                    if 'id' not in config:
                        config['id'] = score_id
                    parsed_configs.append(config)
                else:
                    logging.warning(f"Skipping config with unexpected type: {type(config)}")
            except Exception as parse_err:
                logging.error(f"Failed to parse configuration for score {score_id}: {str(parse_err)}")
        
        scorecard_instance = await asyncio.to_thread(
            Scorecard.create_instance_from_api_data,
            scorecard_id,
            scorecard_structure, 
            parsed_configs
        )
        
        if scorecard_instance:
            logging.info(f"Successfully created targeted scorecard instance with {len(scorecard_configs)} scores")
            return scorecard_instance
        else:
            logging.error("Failed to create scorecard instance from API data")
            return None
            
    except Exception as e:
        logging.error(f"Error creating targeted scorecard instance: {str(e)}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return None

async def get_plexus_client():
    """Get the Plexus Dashboard client for API operations."""
    from plexus.dashboard.api.client import PlexusDashboardClient
    return PlexusDashboardClient()

async def get_metadata_from_report(report_id: str) -> dict:
    """Get metadata from Item record by its external ID."""
    query = """
    query GetItemByExternalId($externalId: String!) {
        listItemByExternalId(externalId: $externalId, limit: 1) {
            items {
                id
                metadata
            }
        }
    }
    """
    variables = {
        "externalId": report_id
    }
    try:
        client = await get_plexus_client()
        result = await asyncio.to_thread(gql, query, variables)
        items = result.get('listItemByExternalId', {}).get('items', [])
        if items and len(items) > 0:
            metadata_raw = items[0].get('metadata')
            # metadata is stored as a JSON string in DynamoDB, parse it
            if isinstance(metadata_raw, str):
                try:
                    return json.loads(metadata_raw)
                except json.JSONDecodeError:
                    logging.warning(f"Failed to parse metadata JSON for report {report_id}: {metadata_raw}")
                    return {}
            elif isinstance(metadata_raw, dict):
                return metadata_raw
            else:
                return {}
        return {}
    except Exception as e:
        logging.error(f"Error getting metadata from report {report_id}: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return {}

async def get_text_from_report(report_id: str) -> Optional[str]:
    """Get the transcript text from Item record by its external ID."""
    query = """
    query GetItemByExternalId($externalId: String!) {
        listItemByExternalId(externalId: $externalId, limit: 1) {
            items {
                id
                text
            }
        }
    }
    """
    variables = {
        "externalId": report_id
    }
    try:
        client = await get_plexus_client()
        result = await asyncio.to_thread(gql, query, variables)
        items = result.get('listItemByExternalId', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['text']
        return None
    except Exception as e:
        logging.error(f"Error getting text from report {report_id}: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return None

async def resolve_score_id(external_id: str, scorecard_dynamo_id: str, client) -> Optional[Dict[str, str]]:
    """
    Resolve a score external ID to its DynamoDB ID and name, scoped by its parent scorecard's DynamoDB ID.
    
    Args:
        external_id: The external ID of the score (e.g., "0")
        scorecard_dynamo_id: The DynamoDB ID of the parent scorecard
        client: The dashboard client
        
    Returns:
        A dictionary with 'id' (DynamoDB ID) and 'name' of the score if found, None otherwise
    """
    try:
        # Use the byScorecardIdAndExternalId GSI for fast lookup
        query = """
        query GetScoreByScorecardIdAndExternalId($scorecardId: String!, $externalId: String!) {
            listScoreByScorecardIdAndExternalId(scorecardId: $scorecardId, externalId: {eq: $externalId}, limit: 1) {
                items {
                    id
                    name # Fetch the name field as well
                }
            }
        }
        """
        
        variables = {
            "scorecardId": scorecard_dynamo_id,
            "externalId": external_id
        }
        
        result = await asyncio.to_thread(gql, query, variables)
        items = result.get('listScoreByScorecardIdAndExternalId', {}).get('items', [])
        
        if items and len(items) > 0:
            score_data = items[0]
            logging.info(f"Resolved score external ID {external_id} for scorecard {scorecard_dynamo_id} to DynamoDB ID {score_data['id']} with name {score_data['name']}")
            return {"id": score_data['id'], "name": score_data['name']}
            
        logging.warning(f"Could not resolve score external ID: {external_id} for scorecard {scorecard_dynamo_id}")
        return None
    except Exception as e:
        logging.error(f"Error resolving score external ID {external_id} for scorecard {scorecard_dynamo_id}: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return None

class JobProcessor:
    def __init__(self, account_key=ACCOUNT_KEY):
        from plexus.dashboard.api.client import PlexusDashboardClient
        self.client = PlexusDashboardClient()
        self.account_key = account_key
        self.account_id = None

    async def initialize(self):
        q = """
        query GetAccountByKey($key: String!) {
            listAccountByKey(key: $key) { items { id name } }
        }
        """
        resp = await asyncio.to_thread(gql, q, {"key": self.account_key})
        items = resp.get("listAccountByKey", {}).get("items", []) or []
        if not items:
            raise RuntimeError(f"No account found with key: {self.account_key}")
        self.account_id = items[0]["id"]
        logging.info(f"Initialized with account {items[0]['name']} ({self.account_id})")

    async def find_and_claim_pending_job(self):
        q = """
        query ListScoringJobsByAccount($accountId: String!) {
            listScoringJobByAccountId(accountId: $accountId, limit: 500) {
                items { id itemId scorecardId scoreId status createdAt }
            }
        }
        """
        res = await asyncio.to_thread(gql, q, {"accountId": self.account_id})
        items = res.get("listScoringJobByAccountId", {}).get("items", []) or []
        pending = [j for j in items if j.get("status") == "PENDING"]
        if not pending:
            return None

        pending.sort(key=lambda x: x.get("createdAt") or "")
        job = pending[0]

        # Use ScoringJob model
        sj = await asyncio.to_thread(ScoringJob.get_by_id, job["id"], self.client)
        await asyncio.to_thread(
            sj.update,
            status="IN_PROGRESS",
            startedAt=datetime.now(timezone.utc).isoformat(),
        )

        iq = """query GetItem($id: ID!) { getItem(id: $id) { id externalId } }"""
        item_res = await asyncio.to_thread(gql, iq, {"id": job["itemId"]})
        item_data = item_res.get("getItem")
        if not item_data:
            logging.error(f"Item not found: {job['itemId']}")
            return None

        scq = """query GetScorecard($id: ID!) { getScorecard(id: $id) { externalId } }"""
        sc_res = await asyncio.to_thread(gql, scq, {"id": job["scorecardId"]})
        scorecard_ext = (sc_res.get("getScorecard") or {}).get("externalId")

        sq = """query GetScore($id: ID!) { getScore(id: $id) { externalId } }"""
        s_res = await asyncio.to_thread(gql, sq, {"id": job["scoreId"]})
        score_ext = (s_res.get("getScore") or {}).get("externalId")

        return {
            "scoring_job_id": job["id"],
            "report_id": item_data["externalId"],
            "scorecard_id": scorecard_ext,
            "score_id": score_ext,
        }

    async def process_job(self, scoring_job_id, report_id, scorecard_id, score_id):
        try:
            logging.info(
                f"Processing job {scoring_job_id} report={report_id} sc={scorecard_id} s={score_id}"
            )
            scoring_job = await asyncio.to_thread(ScoringJob.get_by_id, scoring_job_id, self.client)

            dyn_sc_id = await resolve_scorecard_id(scorecard_id, self.account_id, self.client)
            if not dyn_sc_id:
                raise RuntimeError(f"Could not resolve scorecard: {scorecard_id}")

            resolved = await resolve_score_id(score_id, dyn_sc_id, self.client)
            if not resolved:
                raise RuntimeError(f"Could not resolve score: {score_id}")
            dyn_score_id = resolved["id"]

            transcript_text = await get_text_from_report(report_id)
            item = None
            if PLEXUS_ITEM_AVAILABLE and scoring_job.itemId:
                try:
                    item = await asyncio.to_thread(Item.get_by_id, scoring_job.itemId, self.client)
                except Exception as e:
                    logging.warning(f"Could not fetch Item {scoring_job.itemId}: {e}")
            if item and item.text:
                transcript_text = item.text
            if not transcript_text and not item:
                raise RuntimeError(f"No transcript for report {report_id}")

            metadata = await get_metadata_from_report(report_id) or {}

            scorecard_instance = await create_scorecard_instance_for_single_score(
                scorecard_id, score_id
            )
            if not scorecard_instance:
                raise RuntimeError(f"Failed to create scorecard instance for {scorecard_id}")

            score_results = await scorecard_instance.score_entire_text(
                text=transcript_text or "",
                metadata=metadata,
                modality="Worker",
                item=item,
            )
            result = score_results.get(dyn_score_id)
            if not result:
                raise RuntimeError(f"No result for score {dyn_score_id}")

            value = str(result.value) if result.value is not None else None
            explanation = (result.metadata or {}).get("explanation", "")

            if value and value.upper() == "ERROR":
                await asyncio.to_thread(
                    scoring_job.update,
                    status="FAILED",
                    errorMessage=explanation[:255] or "ERROR value",
                    completedAt=datetime.now(timezone.utc).isoformat(),
                )
                return {"status": "failed", "reason": "ERROR value"}

            trace_data = (result.metadata or {}).get("trace")
            cost = (result.metadata or {}).get("cost")

            await create_score_result_for_api(
                report_id=report_id,
                scorecard_id=scorecard_id,
                score_id=score_id,
                value=value,
                explanation=explanation,
                trace_data=trace_data,
                log_content=None,
                request_id=None,
                code="200",
                cost=cost,
            )

            await asyncio.to_thread(
                scoring_job.update,
                status="COMPLETED",
                completedAt=datetime.now(timezone.utc).isoformat(),
            )

            return {"status": "completed", "value": value}

        except Exception as e:
            logging.error(f"Job processing failed: {e}", exc_info=True)
            try:
                sj = await asyncio.to_thread(ScoringJob.get_by_id, scoring_job_id, self.client)
                await asyncio.to_thread(
                    sj.update,
                    status="FAILED",
                    errorMessage=str(e)[:255],
                    completedAt=datetime.now(timezone.utc).isoformat(),
                )
            except Exception:
                pass
            return {"status": "failed", "error": str(e)[:255]}

    async def process_once(self):
        await self.initialize()
        job = await self.find_and_claim_pending_job()
        if not job:
            return {"status": "no_job"}
        return await self.process_job(
            job["scoring_job_id"], job["report_id"], job["scorecard_id"], job["score_id"]
        )

def handler(event, context):
    return asyncio.run(JobProcessor(account_key=ACCOUNT_KEY).process_once())
