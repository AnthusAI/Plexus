import os
import logging
import tempfile
import boto3
import json
import traceback
from botocore.exceptions import ClientError
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Default bucket name for score result attachments S3 storage
# This should match the resource name in amplify/storage/resource.ts
DEFAULT_BUCKET_NAME = "scoreresultattachments-production"

def get_bucket_name():
    """
    Get the S3 bucket name for score result attachments from environment variables
    or fall back to the default.
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
    
    logger.info(f"Starting S3 upload for score result {score_result_id}, file {file_name}")
    logger.info(f"Using S3 bucket: {bucket_name}")
    
    # Check if bucket name exists
    if not bucket_name:
        logger.error("S3 bucket name is empty or None! Check environment variables or default config.")
        raise ValueError("S3 bucket name is missing")
    
    # Check if trace data is empty
    if not trace_data:
        logger.warning(f"Trace data for score result {score_result_id} is empty or None!")
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
        logger.error(f"Failed to serialize trace data to JSON: {e}")
        raise ValueError(f"Trace data is not JSON serializable: {e}")
    
    logger.info(f"Creating temporary file for trace data (content length: {len(json_content)})")
    
    # Create a temporary file to upload from
    with tempfile.NamedTemporaryFile(mode='w+', suffix=f"_{file_name}", delete=False) as temp_file:
        temp_file_path = temp_file.name
        logger.info(f"Created temp file at {temp_file_path}")
        temp_file.write(json_content)
    
    try:
        # Set content type for JSON files
        extra_args = {
            'ContentType': 'application/json'
        }
            
        logger.info(f"Starting S3 upload to s3://{bucket_name}/{s3_key} with args: {extra_args}")
        
        # Upload the file to S3
        s3_client.upload_file(
            Filename=temp_file_path,
            Bucket=bucket_name, 
            Key=s3_key,
            ExtraArgs=extra_args
        )
        
        logger.info(f"Successfully uploaded {file_name} to s3://{bucket_name}/{s3_key}")
        
        # Return just the S3 path (key) as specified in the docstring
        return s3_key
    except ClientError as e:
        logger.error(f"AWS ClientError uploading trace file to S3: {str(e)}")
        logger.error(f"Error details: {e.response['Error'] if hasattr(e, 'response') else 'No response details'}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading trace file to S3: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    finally:
        # Always remove the temporary file
        if os.path.exists(temp_file_path):
            logger.info(f"Removing temp file {temp_file_path}")
            os.remove(temp_file_path)

def download_score_result_trace_file(s3_path, local_path=None):
    """
    Download a trace file from the score result attachments S3 bucket.
    
    Args:
        s3_path: S3 key path for the file (e.g., 'scoreresults/123/trace.json')
        local_path: Optional local path to save the file to
        
    Returns:
        The content of the file as a dictionary (parsed JSON), and the local path if saved
    """
    bucket_name = get_bucket_name()
    s3_client = boto3.client('s3')
    
    # Create a temporary file if no local path provided
    if not local_path:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            local_path = temp_file.name
            
    try:
        # Download the file
        s3_client.download_file(
            Bucket=bucket_name,
            Key=s3_path,
            Filename=local_path
        )
        
        # Read and parse the JSON file contents
        with open(local_path, 'r') as f:
            content = json.load(f)
            
        logger.info(f"Successfully downloaded and parsed s3://{bucket_name}/{s3_path}")
        return content, local_path
    
    except ClientError as e:
        logger.error(f"Error downloading trace file from S3: {e}")
        if os.path.exists(local_path):
            os.remove(local_path)
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON content: {e}")
        if os.path.exists(local_path):
            os.remove(local_path)
        raise
    except Exception as e:
        logger.error(f"Unexpected error downloading trace file: {e}")
        if os.path.exists(local_path):
            os.remove(local_path)
        raise

def check_s3_bucket_access(bucket_name=None):
    """
    Diagnostic function to check if the S3 bucket exists and is accessible.
    
    Args:
        bucket_name: Name of the bucket to check, or None to use the default
        
    Returns:
        Dict with diagnostic information
    """
    if bucket_name is None:
        bucket_name = get_bucket_name()
        
    logger.info(f"Running S3 bucket access check for: {bucket_name}")
    
    try:
        s3_client = boto3.client('s3')
        
        # Check if we can list the bucket
        logger.info("Attempting to list objects in bucket...")
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            MaxKeys=1,
            Prefix="scoreresults/"
        )
        
        # Log the response status
        logger.info(f"List operation succeeded. Found {response.get('KeyCount', 0)} objects")
        
        # Try to create a test file
        test_content = {"test": f"S3 bucket access test at {datetime.now(timezone.utc).isoformat()}"}
        test_key = f"scoreresults/test/access_check_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.json"
        
        logger.info(f"Attempting to upload test file: {test_key}")
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            temp_file_path = temp_file.name
            json.dump(test_content, temp_file)
        
        try:
            # Upload the file
            s3_client.upload_file(
                Filename=temp_file_path,
                Bucket=bucket_name,
                Key=test_key,
                ExtraArgs={'ContentType': 'application/json'}
            )
            logger.info(f"Successfully uploaded test file: {test_key}")
            
            # Try to download it
            download_path = tempfile.mktemp()
            s3_client.download_file(
                Bucket=bucket_name,
                Key=test_key,
                Filename=download_path
            )
            
            with open(download_path, 'r') as f:
                downloaded_content = json.load(f)
                
            logger.info(f"Successfully downloaded test file. Content matches: {downloaded_content == test_content}")
            
            # Clean up
            s3_client.delete_object(
                Bucket=bucket_name,
                Key=test_key
            )
            logger.info(f"Successfully deleted test file: {test_key}")
            
            # Make sure to clean up local files
            if os.path.exists(download_path):
                os.remove(download_path)
            
            return {
                "bucket_exists": True,
                "can_list": True,
                "can_write": True,
                "can_read": True,
                "can_delete": True,
                "bucket_name": bucket_name
            }
            
        except Exception as e:
            logger.error(f"Error during upload/download/delete test: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                "bucket_exists": True,
                "can_list": True,
                "can_write": False,
                "can_read": False,
                "can_delete": False,
                "error": str(e),
                "bucket_name": bucket_name
            }
            
        finally:
            # Clean up the temp file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
    except ClientError as e:
        logger.error(f"AWS ClientError during S3 bucket check: {str(e)}")
        error_code = e.response.get('Error', {}).get('Code')
        
        if error_code == 'NoSuchBucket':
            return {
                "bucket_exists": False,
                "error": f"Bucket '{bucket_name}' does not exist",
                "bucket_name": bucket_name
            }
        elif error_code == 'AccessDenied':
            return {
                "bucket_exists": True,  # Probably exists if access was denied
                "error": f"Access denied to bucket '{bucket_name}'",
                "bucket_name": bucket_name
            }
        else:
            return {
                "error": f"AWS error: {error_code} - {str(e)}",
                "bucket_name": bucket_name
            }
    
    except Exception as e:
        logger.error(f"Unexpected error during S3 bucket check: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "error": f"Unexpected error: {str(e)}",
            "bucket_name": bucket_name
        }


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
        
        logger.info(f"Starting log upload for score result {score_result_id}")
        logger.info(f"Using S3 bucket: {bucket_name}")
        
        # Check if bucket name exists
        if not bucket_name:
            logger.error("S3 bucket name is empty or None! Check environment variables or default config.")
            raise ValueError("S3 bucket name is missing")
        
        # Check if log content is empty
        if not log_content:
            logger.warning(f"Log content for score result {score_result_id} is empty!")
            return None
        
        # Initialize S3 client
        s3_client = boto3.client('s3')
        
        # Generate S3 key - use same path structure as trace files
        s3_key = f"scoreresults/{score_result_id}/log.txt"
        
        logger.info(f"Creating log file with content length: {len(log_content)} bytes")
        
        # Create a temporary file to upload from - use UTF-8 encoding for Unicode support
        with tempfile.NamedTemporaryFile(mode='w+', suffix="_log.txt", delete=False, encoding='utf-8') as temp_file:
            temp_file_path = temp_file.name
            logger.info(f"Created temp file at {temp_file_path}")
            temp_file.write(log_content)
        
        try:
            # Set content type for text files
            extra_args = {
                'ContentType': 'text/plain'
            }
            
            logger.info(f"Starting S3 upload to s3://{bucket_name}/{s3_key} with args: {extra_args}")
            
            # Upload the file to S3
            s3_client.upload_file(
                Filename=temp_file_path,
                Bucket=bucket_name,
                Key=s3_key,
                ExtraArgs=extra_args
            )
            
            logger.info(f"Successfully uploaded log file to s3://{bucket_name}/{s3_key}")
            
            # Return just the S3 path (key) to match trace file behavior
            return s3_key
            
        except ClientError as e:
            logger.error(f"AWS ClientError uploading log file to S3: {str(e)}")
            logger.error(f"Error details: {e.response['Error'] if hasattr(e, 'response') else 'No response details'}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error uploading log file to S3: {str(e)}")
            logger.error(traceback.format_exc())
            raise
        finally:
            # Always remove the temporary file
            if os.path.exists(temp_file_path):
                logger.info(f"Removing temp file {temp_file_path}")
                os.remove(temp_file_path)
        
    except Exception as e:
        logger.error(f"Error uploading log file to S3: {str(e)}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return None

def download_score_result_log_file(s3_path, local_path=None):
    """
    Download a log file from the score result attachments S3 bucket.
    
    Args:
        s3_path: S3 key path for the file (e.g., 'scoreresults/123/log.txt')
        local_path: Optional local path to save the file to
        
    Returns:
        The content of the file as a string, and the local path if saved
    """
    bucket_name = get_bucket_name()
    s3_client = boto3.client('s3')
    
    # Create a temporary file if no local path provided
    if not local_path:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            local_path = temp_file.name
            
    try:
        # Download the file
        s3_client.download_file(
            Bucket=bucket_name,
            Key=s3_path,
            Filename=local_path
        )
        
        # Read the text file contents
        with open(local_path, 'r') as f:
            content = f.read()
            
        logger.info(f"Successfully downloaded log file s3://{bucket_name}/{s3_path}")
        return content, local_path
    
    except ClientError as e:
        logger.error(f"Error downloading log file from S3: {e}")
        if os.path.exists(local_path):
            os.remove(local_path)
        raise
    except Exception as e:
        logger.error(f"Unexpected error downloading log file: {e}")
        if os.path.exists(local_path):
            os.remove(local_path)
        raise 